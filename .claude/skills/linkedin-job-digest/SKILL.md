---
name: linkedin-job-digest
description: Business rules and architecture for this LinkedIn job scraper — how it scrapes last-24h posts, scores them against the candidate profile, writes a daily digest of the few best matches, and pushes real-time ntfy alerts for fresh strong matches. Use when working on scraping, scoring, the daily summary, the alert poller, session/login, or persistence in this repo.
---

# LinkedIn Job Digest — business logic

## Goal
Produce a **daily summary of the last 24h of job posts**, surfacing only a **few
highest-scoring** matches for the candidate (a Senior Python / Data Engineer &
Tech Lead). A single run *also* fires **real-time push alerts** for fresh, strong
matches so he can apply first (see "Real-time alerts" below). Everything below
serves those two outputs. For *when* posts tend to appear (best time/day to run or
check), see the `posting-time-trends` skill.

## Pipeline (who does what)
The entry point [main.py](app/scrapper/main.py) `run_scrapper()` orchestrates;
each module has a single responsibility — keep it that way. One execution does
**scrape → alert → digest** (there is no separate alert run):

1. **Session** — [login.py](app/scrapper/linkedin_roles/login.py) `ensure_logged_in`
   reuses a persistent Chrome profile (`driver/profile`, set in
   [selenium_basefile.py](app/scrapper/base/selenium_basefile.py)) and only logs
   in via credentials when `is_logged_in` (URL-based: `/feed` vs redirect to
   `/login`,`/authwall`,`/checkpoint`) is false.
2. **Scrape** — [posts.py](app/scrapper/linkedin_roles/posts.py) `search_posts`
   is **scrape-only**: it returns `{post_id: record}` for *new* posts, skipping
   any id in `known_ids`. It does NOT load/score/save — the caller does.
   `main.harvest_new_posts` wraps it: loops the roles, tags each record's `role`,
   scores + email-extracts the new ones.
3. **Alert / persist / summarize** — `main.run_scrapper`: `load_posts_json` →
   `harvest_new_posts` → **`push_alerts(new_posts)`** (ntfy push for fresh strong
   matches) → backfill older → merge → `save_posts_json` → `write_summary_markdown`.
   `run_scrapper` runs under `single_instance_lock` so an overlapping run (e.g. the
   10-min poller firing on a slow run) skips instead of fighting over Chrome.

## Key rules / invariants
- **Post id is the dedup key.** It is NOT in the card HTML. Obtain it by opening
  the post's "⋯" menu → "Copy link to post" → read the id from the confirmation
  toast's "View post" href (`...-share|activity-<19digits>-...`). Dedup the toast
  per post (`dismiss_copy_toast`) so a stale toast isn't re-read.
- **Timestamp** decodes from the id: `int(post_id) >> 22` = unix ms (NOT the
  41-bit slice — that was a bug).
- **Incremental harvest**: `goal_post` counts only *new* posts per run; the JSON
  (`data/posts.json`, gitignored) grows across runs, never duplicating an id.
- **Scrape performance is bounded by two things** (the menu-open to read an id is
  the dominant per-card cost, so don't over-crawl):
  - **DOM pruning** — each handled card is `remove()`d from the DOM, so the browser
    doesn't bloat (the cause of slowdown on long runs) and `find_elements` only
    ever returns cards not yet seen. (Validated: pruning does not break LinkedIn's
    lazy-load — the loader sentinel is separate from the post cards.)
  - **Early-stop at the known boundary** — the feed is sorted newest-first, so a run
    of `stop_after_known` (=5) consecutive already-known ids means we've reached
    previously-scraped territory; stop that role. This is what keeps a re-run fast
    (~10 min → <2 min when little is new) and makes the 10-min poller viable.
- **Waits, not sleeps**: use `utils.wait_for_element` (and `WebDriverWait`) — no
  `time.sleep` for rendering. Handle `StaleElementReferenceException` per card
  (the card stays in the DOM and is retried next pass — don't prune it on stale).

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
  line (grouped by bucket), never under `Matched:`. The digest is **idempotent** —
  rewritten from the full last-24h state each run, so a frequent poller just keeps
  it current.

## Real-time alerts — [alerts.py](app/scrapper/utils/alerts.py) `push_alerts`
A side-channel for *applying first*, stricter than the digest:
- `select_alert_posts(new_posts, …)` keeps only this run's **new** posts that score
  `>= JOB_ALERT_MIN_SCORE` (=18, strong-to-ideal), were posted within
  `JOB_ALERT_MAX_AGE_MIN` (=60) minutes, and hit no negative bucket. Operating on
  *new* posts (incremental dedup) means each qualifying post **alerts exactly
  once** across the morning's runs.
- `send_ntfy_alert` POSTs to `{NTFY_SERVER}/{NTFY_TOPIC}` (high priority, post URL
  as the tap `Click`). The **topic is a 64-hex secret** in `.env` — unguessable, so
  obscurity-private; anyone with the string can read/publish, so keep it secret.
  Optional `NTFY_TOKEN` for an access-controlled topic. ntfy headers must be
  latin-1, so titles are ASCII-sanitised (`_ascii`); the body is UTF-8.
- `send_test_alert` (CLI `test-alert`) verifies delivery without a browser.

## Configuration split
- **Keywords & weights** live in data ([buckets.json](app/scrapper/config/buckets.json));
  `scoring.py` just loads and applies them — don't edit it to tune.
- **Selection knobs** are `.env`-overridable via [config.py](app/config.py)
  `settings`:
  - Digest: `JOB_SUMMARY_TOP_N`, `JOB_SUMMARY_MIN_SCORE`,
    `JOB_EXCLUDE_DEALBREAKERS`, `JOB_REQUIRE_REMOTE`.
  - Alerts: `NTFY_SERVER`, `NTFY_TOPIC`, `NTFY_TOKEN`, `JOB_ALERT_MIN_SCORE`,
    `JOB_ALERT_MAX_AGE_MIN`.

## Running it
```bash
uv run python -m app.scrapper.main            # scrape + alert + digest (one run)
uv run python -m app.scrapper.main test-alert # verify ntfy delivery, no browser
```
Schedule one cron job for the morning poller (machine in local time), e.g. every
10 min 07:00–08:50: `*/10 7-8 * * * cd <repo> && uv run python -m app.scrapper.main`.
Each tick alerts on fresh matches and refreshes the digest; `single_instance_lock`
makes overlapping ticks skip.

## Operational notes
- The persistent profile allows only one Chrome at a time. A killed run can
  orphan Chrome holding `driver/profile/SingletonLock` → `SessionNotCreatedException`.
  Fix: kill stray Chrome on that profile and remove `driver/profile/Singleton*`.
- `single_instance_lock` uses an `flock` on `data/.scraper.lock`; a stale lock from
  a hard-killed run is harmless (the next run re-acquires it) but the file may
  linger.

## Known follow-ups (not yet done)
- Collapse near-duplicate reposts (same job, different `post_id`) in the digest
  and alerts (a heavily reposted job can ping/list more than once).
- Capture author region at scrape time (would make `posting-time-trends`
  attribution exact instead of timezone-inferred).
