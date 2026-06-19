---
name: linkedin-job-digest
description: Business rules and architecture for this LinkedIn job scraper — how it scrapes last-24h posts, scores them against the candidate profile, and writes a daily digest of the few best matches. Use when working on scraping, scoring, the daily summary, session/login, or persistence in this repo.
---

# LinkedIn Job Digest — business logic

## Goal
Produce a **daily summary of the last 24h of job posts**, surfacing only a **few
highest-scoring** matches for the candidate (a Senior Python / Data Engineer &
Tech Lead). Everything below exists to serve that goal.

## Pipeline (who does what)
The entry point [main.py](app/scrapper/main.py) `run_scrapper()` orchestrates;
each module has a single responsibility — keep it that way:

1. **Session** — [login.py](app/scrapper/linkedin_roles/login.py) `ensure_logged_in`
   reuses a persistent Chrome profile (`driver/profile`, set in
   [selenium_basefile.py](app/scrapper/base/selenium_basefile.py)) and only logs
   in via credentials when `is_logged_in` (URL-based: `/feed` vs redirect to
   `/login`,`/authwall`,`/checkpoint`) is false.
2. **Scrape** — [posts.py](app/scrapper/linkedin_roles/posts.py) `search_posts`
   is **scrape-only**: it returns `{post_id: record}` for *new* posts, skipping
   any id in `known_ids`. It does NOT load/score/save — the caller does.
3. **Score / persist / summarize** — `main.run_scrapper`: `load_posts_json` →
   `search_posts(known_ids=set(existing))` → `score_post` each new (and backfill
   older) → merge → `save_posts_json` → `write_summary_markdown`.

## Key rules / invariants
- **Post id is the dedup key.** It is NOT in the card HTML. Obtain it by opening
  the post's "⋯" menu → "Copy link to post" → read the id from the confirmation
  toast's "View post" href (`...-share|activity-<19digits>-...`). Dedup the toast
  per post (`dismiss_copy_toast`) so a stale toast isn't re-read.
- **Timestamp** decodes from the id: `int(post_id) >> 22` = unix ms (NOT the
  41-bit slice — that was a bug).
- **Incremental harvest**: `goal_post` counts only *new* posts per run; the JSON
  (`data/posts.json`, gitignored) grows across runs, never duplicating an id.
- **Waits, not sleeps**: use `utils.wait_for_element` (and `WebDriverWait`) — no
  `time.sleep` for rendering. Handle `StaleElementReferenceException` per card.

## Scoring heuristic — [scoring.py](app/scrapper/config/scoring.py) (mechanism) + [buckets.json](app/scrapper/config/buckets.json) (data)
`score_post(text) -> (score, matched)`. `scoring.py` is pure mechanism; the
keywords/weights are **data in `buckets.json`** (loaded at import). Buckets:
- **skill** (+2 each, capped at `skill_cap=6`) — so a long tool dump can't
  outweigh fit signals.
- **role** (+5), **seniority** (+3), **remote** (+5) — counted **by presence**
  (synonyms in a bucket = one signal). The **remote** bucket also holds
  eligibility signals: `latam`/`brazil` and **relocation** (the candidate is open
  to remote *or* relocation, so relocation is a positive).
- **dealbreaker** (−10) — soft skips: onsite/India-locale/junior/staffing-noise.
- **visa_block** (−100) — absolute kill for right-to-work walls the candidate
  can't clear (US/EU citizenship, `w2`/`c2c`, `no visa sponsorship`, …).
Any bucket with **weight < 0** is treated as negative (see below) — `scoring.py`
exposes `NEGATIVE_BUCKETS`. For the full rationale see the `job-scoring-rules`
skill; to regenerate from a resume see `profile-to-buckets`.

## Summary selection — [utils.py](app/scrapper/utils/utils.py) `write_summary_markdown`
- Filter to posts within the last 24h with `score >= JOB_SUMMARY_MIN_SCORE`.
- **Hard-exclude** posts hitting **any negative bucket** (`NEGATIVE_BUCKETS`:
  `dealbreaker`, `visa_block`) when `JOB_EXCLUDE_DEALBREAKERS` (default on);
  require an explicit remote mention when `JOB_REQUIRE_REMOTE` (default off).
- Rank by score desc, take top `JOB_SUMMARY_TOP_N`, write
  `data/summary-YYYY-MM-DD.md`. Negative buckets render on a separate `Flags:`
  line (grouped by bucket), never under `Matched:`.

## Configuration split
- **Keywords & weights** live in data ([buckets.json](app/scrapper/config/buckets.json));
  `scoring.py` just loads and applies them — don't edit it to tune.
- **Selection knobs** are `.env`-overridable via
  [config.py](app/config.py) `settings`: `JOB_SUMMARY_TOP_N`,
  `JOB_SUMMARY_MIN_SCORE`, `JOB_EXCLUDE_DEALBREAKERS`, `JOB_REQUIRE_REMOTE`.

## Operational notes
- The persistent profile allows only one Chrome at a time. A killed run can
  orphan Chrome holding `driver/profile/SingletonLock` → `SessionNotCreatedException`.
  Fix: kill stray Chrome on that profile and remove `driver/profile/Singleton*`.

## Known follow-ups (not yet done)
- Collapse near-duplicate reposts (same job, different `post_id`) in the digest.
- Run from repo root with the venv: `uv run python -m app.scrapper.main`.
