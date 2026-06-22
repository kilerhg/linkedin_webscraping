---
name: posting-time-trends
description: Weekly analysis of WHEN good-matching job posts appear — day-of-week and hour-of-day distributions of high-scoring posts in the scraped corpus — so you can track shifts in posting patterns and tune when to check the digest / run the alert poller. Use when asked about best time/day to look for jobs, to refresh the timing recommendation, or to run the recurring trend report.
---

# Posting-time trends

Answers **"when do the good posts get posted?"** from the real corpus
([data/posts.json](data/posts.json)) and tracks how that drifts week to week.
The output drives two decisions: **when to manually check** the digest, and the
**cron window for the morning alert poller** (see `linkedin-job-digest`). This is
descriptive analytics only — it does not scrape, score, or change config.

## Run it
Self-contained (stdlib only), reads `data/posts.json`, writes
`data/trends-YYYY-MM-DD.md` and prints the same to stdout:

```bash
uv run python .claude/skills/posting-time-trends/analyze_trends.py --since-days 30
```
- `--since-days N` — only posts from the last N days (**use this** for trend
  tracking; `0`/omit = all history, which dilutes recent shifts).
- `--tz OFFSET` — report timezone, default `-5` (Bogotá). All clock times are in
  this zone.
- `--min-score S [S ...]` — score cohorts, default `15 20` (the strong and
  near-ideal tiers; mirror the digest/alert floors here).
- `--out PATH`, `--posts PATH` — overrides.

**Weekly cadence:** run every Monday over `--since-days 30` (a rolling month is
enough signal without being swamped by stale history). Schedule via the
`schedule` skill (a cron routine) or a `/loop`. Compare each week's report to the
prior `data/trends-*.md` to spot movement.

## What it reports
1. **Per score cohort (>=15, >=20):**
   - **Day of week** — count + bar, peak flagged. Where the volume of good
     matches concentrates.
   - **Top hours** — busiest hours in your zone, each annotated with the
     **regional business clock** (US-ET / CEST / IST) so you can attribute a peak
     to a region's working hours (see caveats).
   - **Top-3 hours per day** — whether timing diverges by weekday (it does — e.g.
     a midday Tuesday peak vs. morning Wed–Fri).
2. **Hourly quality curve (score >= 0 only)** — count *and average score* per
   hour, to find the slot that is both busy and high-quality (mean is dragged
   down by deep-negative flagged posts if you don't filter, hence positives-only).

## How to read it (methodology derived from the corpus)
- **Translate hours to the poster's region, not yours.** The corpus is
  India/Europe/US-heavy; each region posts at *its own* ~9am, so a peak in your
  zone is really "9am somewhere." The regional clock annotations exist for this.
  Historically the strong cohort peaked at **08–09:00 Bogotá ≈ 09–10:00 US-ET**
  (the US-morning wave, which carries the most profile-relevant/remote posts),
  with a high-volume overnight band = Europe+India morning.
- **Day pattern:** Tue–Thu has been the reliable core; **weekends are too sparse
  to trust** (single-digit n — treat "peaks" there as noise). Watch whether the
  weekday peak moves (it has shifted between Thursday and Monday as the corpus
  grew — that drift is exactly what weekly runs catch).
- **Quality vs volume are different questions.** A busy hour isn't always the
  highest-scoring; use the hourly quality curve to confirm a slot is worth it.

## Caveats (state these when reporting)
- **Attribution is inferred from timestamps, not poster location** — regional
  mapping is a heuristic. For ground truth you'd capture author region at scrape
  time (a known follow-up in `linkedin-job-digest`).
- **DST:** regional annotations use standard-time offsets; US/EU clocks shift ±1h
  in summer. Bogotá (the default report zone) has no DST.
- **Small cohorts wobble.** With `--since-days 30` the >=20 cohort is ~80 posts;
  per-day-per-hour cells are tiny (counts of 1–6), so read tendencies, not exact
  hours. Don't over-fit the schedule to a single week.
- Posts dedupe by id but **near-duplicate reposts aren't collapsed**, so a heavily
  reposted job can nudge a given hour/day — corroborate big shifts across weeks.
