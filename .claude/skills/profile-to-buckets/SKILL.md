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
    "skill":       { "weight": 2,   "keywords": ["python", "spark", "airflow"] },
    "role":        { "weight": 5,   "keywords": ["data engineer", "tech lead"] },
    "seniority":   { "weight": 3,   "keywords": ["senior", "staff", "lead"] },
    "remote":      { "weight": 5,   "keywords": ["remote", "hybrid"] },
    "dealbreaker": { "weight": -10, "keywords": ["junior", "on-site", "relocation"] }
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
- **dealbreaker** is negative and, in the digest, **hard-excludes** the post by
  default (`JOB_EXCLUDE_DEALBREAKERS`). Reserve it for true disqualifiers.

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
5. **remote bucket** — work-modes they want (remote, hybrid, work from home, …).
6. **dealbreaker bucket** — disqualifiers implied by the profile: seniority floor
   (`junior`, `intern`, `trainee`), unwanted on-site/relocation (`on-site`,
   `work from office`, `relocation`), visa/clearance walls (`security clearance`,
   `us citizen`, `green card`), and tech stacks they refuse. Keep it conservative
   — every keyword here can drop an otherwise-good post.
7. **weights** — sensible defaults: skill 2, role 5, seniority 3, remote 5,
   dealbreaker -10. Raise remote / deepen dealbreaker if the user prioritizes
   work-mode; raise role if title-fit matters most.
8. **Write** valid JSON to `app/scrapper/config/buckets.json` (already exempted
   from the `*.json` gitignore rule). Do not edit `scoring.py` — it loads this
   file at import.

## Verify
```bash
uv run python -c "from app.scrapper.config.scoring import SKILL_CAP, BUCKETS, score_post; \
print('cap', SKILL_CAP, 'buckets', list(BUCKETS)); \
print(score_post('Senior Data Engineer, remote, Python, Spark, Airflow'))"
```
Expect a positive score with `role`, `seniority`, `remote`, and `skill` in the
matched buckets. Sanity-check a known-bad post (e.g. "Junior on-site") scores low
/ trips a dealbreaker.
