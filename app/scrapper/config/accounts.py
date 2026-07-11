"""Filtered posting accounts — company pages that *index/aggregate* jobs rather
than being the actual recruiter (e.g. remoteyeah). Their posts are still scraped
and kept in ``data/posts.json``, but excluded from the daily digest and push
alerts so the noise doesn't crowd out real recruiter posts.

The list is data, loaded from ``filtered_accounts.json`` next to this module —
add a company page there (as a full LinkedIn URL), no code change needed. Matching
is by the ``/company/<slug>`` part of a record's ``author_profile_url``
(case-insensitive, trailing slash ignored), so query strings or extra path
segments on the stored href don't matter.
"""
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

FILTERED_ACCOUNTS_FILE = Path(__file__).resolve().parent / "filtered_accounts.json"

# Pull the slug out of a LinkedIn company URL: .../company/<slug>[/...][?...].
_COMPANY_SLUG_RE = re.compile(r"/company/([^/?#]+)", re.IGNORECASE)


def company_slug(url):
    """Return the normalized ``/company/<slug>`` slug of a LinkedIn URL, or None.

    Returns None for personal (``/in/``) author URLs or anything without a
    company segment. Normalized to lowercase so matching is case-insensitive."""
    match = _COMPANY_SLUG_RE.search(url or "")
    return match.group(1).lower() if match else None


def load_filtered_slugs(path=FILTERED_ACCOUNTS_FILE):
    """Load the set of filtered company-page slugs from the JSON config."""
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return frozenset()
    except json.JSONDecodeError as exc:
        # A malformed config would otherwise silently disable *all* account
        # filtering — surface it instead of quietly letting indexers through.
        logger.warning("filtered_accounts.json is not valid JSON (%s); "
                       "account filtering disabled until fixed", exc)
        return frozenset()
    slugs = (company_slug(url) for url in data.get("company_pages", []))
    return frozenset(slug for slug in slugs if slug)


# Loaded once at import — the digest and alert selectors consult this to drop
# posts authored by an indexer/aggregator company page.
FILTERED_COMPANY_SLUGS = load_filtered_slugs()


def is_filtered_account(record, filtered_slugs=None):
    """True when ``record`` was authored by a filtered (indexer) company page.

    Matches the ``/company/<slug>`` of the record's ``author_profile_url`` against
    ``filtered_slugs`` (defaults to the module-level set loaded from config)."""
    slugs = FILTERED_COMPANY_SLUGS if filtered_slugs is None else filtered_slugs
    slug = company_slug(record.get("author_profile_url"))
    return slug is not None and slug in slugs
