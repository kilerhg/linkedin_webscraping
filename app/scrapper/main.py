import fcntl
import logging
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.scrapper.base.selenium_basefile import PROFILE_DIR, SeleniumConfig
from app.scrapper.config.scoring import score_post
from app.scrapper.linkedin_roles import login, posts
from app.scrapper.utils.alerts import select_alert_posts, send_ntfy_alert, send_test_alert
from app.scrapper.utils.utils import (
    DATA_DIR,
    extract_first_email,
    load_posts_json,
    save_posts_json,
    write_summary_markdown,
)

logging.basicConfig(level=logging.INFO)

# The persistent Chrome profile allows only one instance; this lock stops an
# overlapping run (e.g. the 10-min poller firing while a slow run is still going)
# from orphaning Chrome on driver/profile/SingletonLock.
_LOCK_PATH = DATA_DIR / ".scraper.lock"


@contextmanager
def single_instance_lock():
    """Yield True if we acquired the exclusive run lock, False if another run holds it."""
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = open(_LOCK_PATH, "w")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        handle.close()


def score_record(record):
    """Annotate a post record in place with its match score and matched keywords."""
    record['score'], record['matched_keywords'] = score_post(record.get('post_content', ''))


def add_email(record):
    """Add an ``email`` field with the first email found in the content, if any."""
    email = extract_first_email(record.get('post_content', ''))
    if email:
        record['email'] = email


def harvest_new_posts(driver, existing):
    """Scrape every role for posts not in ``existing``, tag/score/email them, and
    return ``(new_posts, roles)``. Shared by the daily run and the alert poller."""
    new_posts = {}
    roles = posts.QueryPost.role_keywords()
    for role, keywords in roles.items():
        logging.info('Searching role: %s', role)
        found = posts.search_posts(
            driver, keywords, known_ids=set(existing) | set(new_posts),
        )
        # Tag each post with the role that surfaced it (persisted in posts.json).
        for record in found.values():
            record['role'] = role
        new_posts.update(found)

    for record in new_posts.values():
        score_record(record)
        add_email(record)
    return new_posts, roles


def push_alerts(new_posts):
    """Push a notification for each fresh, high-scoring post in this run's harvest.

    Selection is stricter than the digest (JOB_ALERT_MIN_SCORE + a freshness
    window) so you only get pinged about posts worth applying to *first*. Only the
    run's *new* posts are considered, so incremental dedup makes each qualifying
    post alert exactly once across the morning's runs."""
    alerts = select_alert_posts(
        new_posts,
        settings.JOB_ALERT_MIN_SCORE,
        settings.JOB_ALERT_MAX_AGE_MIN,
        exclude_dealbreakers=settings.JOB_EXCLUDE_DEALBREAKERS,
    )
    sent = sum(send_ntfy_alert(record) for record in alerts)
    logging.info('Alerts: %d qualified, %d sent', len(alerts), sent)


def clear_stale_chrome_locks():
    """Remove leftover Chrome ``Singleton*`` lock files from a previously killed
    run (e.g. a ``timeout``-ed cron run) so a fresh Chrome can claim the profile
    instead of failing with ``SessionNotCreatedException``. Safe because
    ``run_scrapper`` holds ``single_instance_lock`` — no other run is using the
    profile right now."""
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        try:
            (PROFILE_DIR / name).unlink()
            logging.info('Cleared stale Chrome lock: %s', name)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logging.warning('Could not remove stale %s: %s', name, exc)


def run_scrapper():
    clear_stale_chrome_locks()
    existing = load_posts_json()

    # Browser is only needed for login + scraping; quit it as soon as the harvest
    # is done (in finally, so a crash/kill can't leak Chrome and wedge the next
    # run), then do the CPU-only persistence/summary below.
    driver = SeleniumConfig().get_driver()
    try:
        login.ensure_logged_in(driver)
        new_posts, roles = harvest_new_posts(driver, existing)
    finally:
        driver.quit()

    # Real-time push for the fresh, strong matches in this harvest (apply first).
    push_alerts(new_posts)

    # Backfill records that predate scoring/email extraction.
    for record in existing.values():
        if 'score' not in record:
            score_record(record)
        if 'email' not in record:
            add_email(record)

    # Merge, persist, and (re)write the daily digest of the top matches.
    existing.update(new_posts)
    save_posts_json(existing)
    summary_path, top = write_summary_markdown(
        existing, settings.JOB_SUMMARY_TOP_N, settings.JOB_SUMMARY_MIN_SCORE,
        roles=list(roles),
        exclude_dealbreakers=settings.JOB_EXCLUDE_DEALBREAKERS,
        require_remote=settings.JOB_REQUIRE_REMOTE,
    )
    logging.info('Collected %d new posts (%d total saved)', len(new_posts), len(existing))
    logging.info('Wrote summary of top %d posts to %s', len(top), summary_path)


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "scrape"

    if command == "test-alert":
        # No browser/lock needed — just verify the ntfy topic delivers.
        logging.info('Sending ntfy test alert')
        send_test_alert()
        return

    if command != "scrape":
        sys.exit(f"Unknown command '{command}'. Use one of: scrape, test-alert.")

    with single_instance_lock() as acquired:
        if not acquired:
            logging.warning('Another run is in progress; skipping this run.')
            return
        logging.info('Starting scrape run - %s', datetime.now())
        run_scrapper()


if __name__ == "__main__":
    main()