"""Keyword-based job-matching heuristic, tuned to the candidate profile.

`score_post` scores a job post's free text by summing a weight for every matched
keyword across positive buckets (skills, target roles, seniority, work mode) and
subtracting for deal-breakers. The buckets/weights are data, loaded from
``buckets.json`` next to this module (regenerate it from a profile markdown — see
the ``profile-to-buckets`` skill). Selection thresholds (top-N, minimum score)
are separate and live in .env via ``app.config.settings``.

Keywords are matched case-insensitively. Single-word/phrase tokens use word
boundaries to avoid false positives; tokens containing symbols (e.g. "etl/elt",
"c#") fall back to substring matching.
"""
import json
import re
from pathlib import Path

BUCKETS_FILE = Path(__file__).resolve().parent / "buckets.json"


def load_buckets(path=BUCKETS_FILE):
    """Load ``(skill_cap, buckets)`` from the JSON config file."""
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    return data.get("skill_cap", 6), data.get("buckets", {})


# Cap on how many skill matches can count, so a long tool dump can't outweigh the
# fit signals. The "skill" bucket counts up to SKILL_CAP matched keywords; every
# other bucket is a single signal counted by presence (synonyms mean the same).
SKILL_CAP, BUCKETS = load_buckets()

# Buckets with a negative weight are disqualifiers (dealbreaker, visa_block, …).
# The digest treats them as flags and excludes posts that hit them — derive the
# set from the weights so adding a new negative bucket needs no code change.
NEGATIVE_BUCKETS = frozenset(
    name for name, bucket in BUCKETS.items() if bucket["weight"] < 0
)


def _matches(text, keyword):
    """True when ``keyword`` appears in already-lowercased ``text``."""
    if re.search(r"[^\w ]", keyword):
        # Symbols (slashes, '#', '.') break \b boundaries -> substring match.
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def score_post(text):
    """Return ``(score, matched)`` for a post's free text.

    ``matched`` maps each bucket that hit to the list of keywords found, useful
    for explaining the score in the summary."""
    text = (text or "").lower()
    score = 0
    matched = {}
    for name, bucket in BUCKETS.items():
        hits = [kw for kw in bucket["keywords"] if _matches(text, kw)]
        if not hits:
            continue
        matched[name] = hits
        # Skills count (capped) by number of tools; every other bucket is one
        # signal regardless of how many synonyms matched.
        count = min(len(hits), SKILL_CAP) if name == "skill" else 1
        score += bucket["weight"] * count
    return score, matched
