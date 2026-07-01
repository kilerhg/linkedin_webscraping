"""Real-time push alerts for fresh, high-scoring posts (the 7-9am poller).

Sends a notification via ntfy.sh (https://ntfy.sh/docs/) so the candidate can be
among the first to apply. Selection is intentionally stricter than the daily
digest: a higher score bar (JOB_ALERT_MIN_SCORE) and a freshness window
(JOB_ALERT_MAX_AGE_MIN) — an hours-old post is no good for "apply first".
"""
import logging
from datetime import datetime, timedelta, timezone

import requests

from app.config import settings
from app.scrapper.config.scoring import HARD_NEGATIVE_BUCKETS


def select_alert_posts(posts, min_score, max_age_min, exclude_dealbreakers=True):
    """Return records worth alerting on, highest score first.

    Keeps posts scoring >= ``min_score`` that were posted within the last
    ``max_age_min`` minutes and (when ``exclude_dealbreakers``) hit no hard
    negative bucket (soft-penalty buckets like ``tech_mismatch`` only dock score,
    they don't exclude). ``posts`` is a ``{post_id: record}`` dict — in the alert
    run it is the *new* posts from this poll, so each qualifying post alerts
    exactly once.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_min)
    selected = []
    for record in posts.values():
        if record.get("score", 0) < min_score:
            continue
        matched = record.get("matched_keywords", {})
        if exclude_dealbreakers and any(matched.get(b) for b in HARD_NEGATIVE_BUCKETS):
            continue
        try:
            posted_at = datetime.fromisoformat(record.get("posted_at", ""))
        except (TypeError, ValueError):
            continue
        if posted_at < cutoff:
            continue
        selected.append(record)
    selected.sort(key=lambda r: r.get("score", 0), reverse=True)
    return selected


def _ascii(text):
    """ntfy sends metadata via HTTP headers, which must be latin-1 safe; drop
    anything that isn't (emojis, some accented chars) from header values."""
    return (text or "").encode("ascii", "ignore").decode("ascii")


def send_ntfy_alert(record):
    """Push a single post to the configured ntfy topic. Returns True on success."""
    topic = settings.NTFY_TOPIC
    if not topic:
        logging.warning("NTFY_TOPIC not set; skipping alert")
        return False

    url = f"{settings.NTFY_SERVER.rstrip('/')}/{topic}"
    score = record.get("score", 0)
    role = record.get("role") or "match"
    author = record.get("author_name") or "Unknown"
    link = record.get("post_url") or record.get("linkedin_job_url") or ""
    excerpt = " ".join((record.get("post_content") or "").split())[:240]

    # Title goes in a header (ASCII-only); body is the request payload (UTF-8 ok).
    headers = {
        "Title": _ascii(f"Job {score}: {role} — {author}"),
        "Priority": "high",
        "Tags": "briefcase",
    }
    if link:
        headers["Click"] = link
    if settings.NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {settings.NTFY_TOKEN}"

    body = excerpt or author
    try:
        resp = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logging.error("ntfy alert failed: %s", exc)
        return False


def send_test_alert():
    """Send a sample notification so you can confirm your topic subscription works."""
    return send_ntfy_alert({
        "score": 99,
        "role": "test",
        "author_name": "ntfy setup check",
        "post_url": "https://ntfy.sh/",
        "post_content": "If you can read this on your phone, alerts are wired up correctly.",
    })
