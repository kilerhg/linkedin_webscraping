import logging
from datetime import datetime

from app.config import settings
from app.scrapper.base.selenium_basefile import SeleniumConfig
from app.scrapper.config.scoring import score_post
from app.scrapper.linkedin_roles import login, posts
from app.scrapper.utils.utils import (
    extract_first_email,
    load_posts_json,
    save_posts_json,
    write_summary_markdown,
)

logging.basicConfig(level=logging.INFO)


def score_record(record):
    """Annotate a post record in place with its match score and matched keywords."""
    record['score'], record['matched_keywords'] = score_post(record.get('post_content', ''))


def add_email(record):
    """Add an ``email`` field with the first email found in the content, if any."""
    email = extract_first_email(record.get('post_content', ''))
    if email:
        record['email'] = email


def run_scrapper():
    driver = SeleniumConfig().get_driver()

    login.ensure_logged_in(driver)

    # Scrape every defined role, skipping posts already stored or collected by an
    # earlier role this run (a post can match more than one search).
    existing = load_posts_json()
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

    # Process new posts; backfill records that predate scoring/email extraction.
    for record in new_posts.values():
        score_record(record)
        add_email(record)
    for record in existing.values():
        if 'score' not in record:
            score_record(record)
        if 'email' not in record:
            add_email(record)

    # Merge, persist, and write the daily digest of the top matches.
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

    




if __name__ == "__main__":
    logging.info(f'Starting Scrapper - {str(datetime.now())}')
    run_scrapper()