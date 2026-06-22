---
name: profile-to-buckets
description: Generate the job-matching keyword config (app/scrapper/config/buckets.json) from a candidate profile markdown (e.g. eu.md / a resume). Use when onboarding a new profile, retuning match quality, or when the user provides an updated profile and wants the scoring buckets regenerated.
---

# Generate buckets.json from a profile markdown

Turns a candidate profile (markdown resume) into
`app/scrapper/config/buckets.json`, the keyword/weight config consumed by
[scoring.py](app/scrapper/config/scoring.py) `score_post`. The goal of the whole
pipeline is a daily digest of the few best-matching last-24h job posts (see the
`linkedin-job-digest` skill), so the buckets must capture what makes a post a
*good fit for this person* and what disqualifies it.

## Output schema
```json
{
  "skill_cap": 6,
  "buckets": {
    "skill":       { "weight": 2,    "keywords": ["python", "spark", "airflow"] },
    "role":        { "weight": 5,    "keywords": ["data engineer", "tech lead"] },
    "seniority":   { "weight": 3,    "keywords": ["senior", "staff", "lead"] },
    "remote":      { "weight": 5,    "keywords": ["remote", "hybrid", "relocation"] },
    "dealbreaker": { "weight": -10,  "keywords": ["junior", "on-site", "wfo"] },
    "visa_block":  { "weight": -100, "keywords": ["us citizen", "no visa sponsorship"] }
  }
}
```

## Scoring semantics (must match scoring.py)
- Keywords are matched **case-insensitively** on the post text. Single words/
  phrases match on **word boundaries**; tokens with symbols (`etl/elt`, `c#`)
  fall back to substring. So keep keywords lowercase.
- **skill** counts each distinct matched keyword, but its total is **capped at
  `skill_cap`** — a long tool dump can't dominate. Pick `skill_cap` ≈ 6.
- **role / seniority / remote** count **once by presence** (any synonym hitting =
  one signal). Put synonyms of the same idea in the same bucket.
- **Any bucket with `weight < 0` is a disqualifier** (`scoring.py` derives
  `NEGATIVE_BUCKETS` from the weights). In the digest these **hard-exclude** the
  post by default (`JOB_EXCLUDE_DEALBREAKERS`) and render under `Flags:`. Two tiers:
  - **dealbreaker** (−10) — soft "skip" (onsite, staffing noise, wrong stack).
  - **visa_block** (−100) — categorical "never": right-to-work walls. The steep
    weight guarantees even a perfect role (≈+25) nets negative (≈−75) and is
    dropped even if exclusion is disabled. Adding more negative buckets needs no
    code change — just give them a negative weight.
- Keyword matching uses **word boundaries** (symbol-free) — so plurals/suffixes
  do NOT match (`llm`≠"llms", `python engineer`≠"python developer"). Add each
  surface form that appears in real posts.

## Procedure
1. **Read the profile.** Extract: core skills/tools, target roles, seniority
   level, work-mode preference (remote/hybrid/on-site), and location/visa
   constraints. The "Core Skills", "Target Roles", and "Experience" sections are
   the richest sources.
2. **skill bucket** — list concrete, matchable tools/technologies the person
   knows (languages, frameworks, data/cloud tools, DBs). Lowercase. **De-duplicate
   overlapping variants** so one concept isn't counted twice: do NOT include both
   `etl`+`elt` *and* `etl/elt`; prefer `spark` over also `apache spark`; drop
   compounds already covered by parts (`azure databricks` when `azure`+`databricks`
   exist). Skip ultra-generic tokens (`ai`, `data`, single letters).
3. **role bucket** — the person's target job titles + close synonyms.
4. **seniority bucket** — levels at/above the person's (e.g. senior, staff, lead,
   principal). Omit ones they're over/under-qualified for.
5. **remote bucket** — really a **work-mode/eligibility** bucket: the modes they
   want (remote, hybrid, work from home, …) plus region-open signals (`latam`,
   `brazil`) and, **if they're open to moving, relocation signals** (`relocation`,
   `relocation package`). Relocation is a *positive* here unless the profile says
   they won't move.
6. **dealbreaker bucket** (−10) — soft disqualifiers: seniority floor (`junior`,
   `intern`, `trainee`), unwanted on-site (`on-site`, `work from office`, `wfo`),
   unwanted locales (e.g. cities/countries they can't work in), under-leveling
   roles, tech stacks they refuse (use the **specific** form — `c++`/`golang`,
   never bare `c`/`go`), and **job-seeker / bench-sales noise** — posts *seeking*
   work or a recruiter pitching candidates rather than offering a role (`hotlist`,
   `bench sales`, `available consultants`, `c2h`, `opentowork`). Keep it
   conservative, and beware that "looking for"/"seeking" appear in both hiring and
   seeking posts — keep only self-referential/bench-specific forms.
7. **visa_block bucket** (−100) — only **categorical right-to-work walls** the
   person cannot clear (no auth + won't sponsor): citizenship/visa requirements
   (`us citizen`, `green card`, `h1b`, `eu work permit`), US-employment terms that
   imply local auth (`w2`, `c2c`, `us-based`), `security clearance`, and explicit
   `no visa sponsorship`. Do NOT include relocation or country names that *offer*
   sponsorship. Match specific `work authorization`, not bare `authorization`.
8. **weights** — sensible defaults: skill 2, role 5, seniority 3, remote 5,
   dealbreaker -10, visa_block -100. Raise remote / deepen dealbreaker if the user
   prioritizes work-mode; raise role if title-fit matters most.
9. **Write** valid JSON to `app/scrapper/config/buckets.json` (already exempted
   from the `*.json` gitignore rule). Do not edit `scoring.py` — it loads this
   file at import.

## Verify
```bash
uv run python -c "from app.scrapper.config.scoring import SKILL_CAP, BUCKETS, score_post; \
print('cap', SKILL_CAP, 'buckets', list(BUCKETS)); \
print(score_post('Senior Data Engineer, remote, Python, Spark, Airflow'))"
```
Expect a positive score with `role`, `seniority`, `remote`, and `skill` in the
matched buckets (and `NEGATIVE_BUCKETS` importable). Sanity-check a soft-bad post
(e.g. "Junior on-site") trips a `dealbreaker`, and a hard-bad post (e.g. "Remote,
US citizens only") trips `visa_block` and goes deeply negative.
