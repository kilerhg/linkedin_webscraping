---
name: job-scoring-rules
description: The scoring business logic and validation rules for the LinkedIn job digest — how a post's score is computed, what counts as a fit vs a dealbreaker, the keyword-matching gotchas, and the tuning rationale derived from analyzing the real scraped corpus. Use when reviewing or changing buckets.json weights/keywords, debugging why a post scored the way it did, or auditing match quality.
---

# Job scoring — business logic & validation rules

This skill is the *rationale and rulebook* behind
[buckets.json](app/scrapper/config/buckets.json) and
[scoring.py](app/scrapper/config/scoring.py). For pipeline/architecture see the
`linkedin-job-digest` skill; for regenerating buckets from a fresh resume see
`profile-to-buckets`. This one explains **why the keywords/weights are what they
are** and the **validation rules** a change must respect.

## Business goal
Surface the **few last-24h posts that are genuinely worth this candidate's time**
— a São Paulo–based **Senior Python / Data / AI Engineer & Tech Lead** who is open
to **remote OR relocation** (LATAM/Brazil ideal). The one hard constraint is
**visa status**: he holds **no EU or US work authorization**, so any role gated on
existing EU/US right-to-work (or that won't sponsor) is dead — but **relocation
with sponsorship is a positive, not a dealbreaker**. The score must reward *fit*
and reliably reject the staffing-agency noise that dominates the LinkedIn
`#hiring` firehose (onsite-India and US/EU-work-authorization-gated posts).

## How a score is computed (`score_post`)
`score_post(text) -> (score, matched)`. Text is lowercased; each bucket adds
weight per match:

| Bucket        | Weight | Counting rule                                  |
|---------------|--------|------------------------------------------------|
| `skill`       | +2     | per distinct keyword, **capped at `skill_cap`=6** |
| `role`        | +5     | once **by presence** (any synonym = one signal) |
| `seniority`   | +3     | once by presence                               |
| `remote`      | +5     | once by presence                               |
| `dealbreaker` | −10    | per distinct keyword (compounds)               |
| `visa_block`  | −100   | per distinct keyword — **absolute kill**       |

**Max positive ≈ 25** (12 skill + 5 role + 3 seniority + 5 remote). The skill cap
exists so a long tool-dump can't outweigh true fit signals (role + remote).

### Negative buckets are derived from weight, not name
`scoring.py` exposes `NEGATIVE_BUCKETS = {name for name, b in BUCKETS if
b.weight < 0}`. The digest ([utils.py](app/scrapper/utils/utils.py)) uses this set
— **not** a hard-coded `"dealbreaker"` — to (a) exclude posts that hit any
negative bucket, (b) render them under `Flags:` (grouped by bucket), and (c) keep
them out of the positive `Matched:` line. So adding another negative bucket needs
**no code change** — just give it a negative weight in `buckets.json`.

### `visa_block` — the hard constraint
A separate negative bucket at **−100** for right-to-work gates the candidate
cannot clear. A perfect role (≈+25) that is visa-gated lands at **≈−75**, far
below any `min_score`, and is hard-excluded — *even if* `JOB_EXCLUDE_DEALBREAKERS`
is turned off. It's split from `dealbreaker` (−10) on purpose: a `.net` mention is
a soft "skip"; "US citizens only" is a categorical "never".

## Validation rules (must always hold)
1. **Keyword matching semantics** (mirror these or matches silently fail):
   - Case-insensitive; **keywords must be lowercase**.
   - A keyword with any non-`[\w ]` char (`/`, `#`, `.`) → **substring** match
     (`ci/cd`, `c#`, `.net`). Everything else → **word-boundary** match.
   - **Word boundaries do NOT match plurals/suffixes.** `llm` ≠ "llms",
     `vector database` ≠ "vector databases", `python engineer` ≠ "python
     developer", `data engineer` ≠ "data engineering", `ai agents` ≠ "agent".
     If a form appears in the corpus, **add that exact form** as its own keyword.
     (This is the single most common bug — verify with a quick `re.search` test.)
2. **De-dupe within `skill`** to respect the cap: don't add a variant that's
   already covered by its parts (`azure databricks` when `azure`+`databricks`
   exist). Synonyms that match *different surface forms* (e.g. `genai` vs
   `generative ai`, `llm` vs `llms`) are allowed — they exist to catch wording,
   and the cap bounds any double-count.
3. **`role`/`seniority`/`remote` are presence buckets** — put synonyms of one
   idea in the same bucket; adding more never inflates beyond that bucket's weight.
4. **Negative buckets hard-exclude** the post from the digest by default
   (`JOB_EXCLUDE_DEALBREAKERS`); a bucket is "negative" purely by having a
   `weight < 0` (`dealbreaker`, `visa_block`). Every keyword here can drop an
   otherwise-good post — only add **true disqualifiers**, and prefer **specific**
   forms over ambiguous ones (`embedded systems` not bare `embedded`; `recent
   graduate` not bare `graduate`, which would catch "graduate degree required").
   Use `visa_block` (−100) only for categorical right-to-work walls; everything
   else soft-skips via `dealbreaker` (−10).
5. **Don't edit `scoring.py` for tuning** — it's pure mechanism; all knobs live in
   `buckets.json` (loaded at import) and selection thresholds in `.env`.

## What counts as fit (positive buckets)
- **skill** — concrete tech from the profile that actually appears in posts:
  Python/FastAPI/Flask stack (`pydantic`, `sqlalchemy`, `apis`), data engineering
  (`spark`, `pyspark`, `airflow`, `etl/elt`, `databricks`, `snowflake`,
  `bigquery`, `lakehouse`, `orchestration`), GenAI (`llm`/`llms`, `rag`,
  `agentic`/`agentic ai`, `ai agents`, `langchain`/`langgraph`/`llamaindex`,
  `openai`, `prompt engineering`), DBs (`postgresql`, `pgvector`, `vector
  database(s)`, `mongodb`), cloud/devops (`aws`, `azure`, `gcp`, `docker`,
  `kubernetes`, `ci/cd`, `devops`, `observability`).
- **role** — target titles **and the way posts actually phrase them**: both
  `python engineer` **and** `python developer`, `backend engineer`/`developer`,
  `software engineer`/`developer`, plus `ai engineer`, `ml engineer`,
  `genai engineer`, `agentic ai engineer`, `tech lead`, `data architect`.
- **seniority** — at/above the candidate: senior, staff, lead, principal,
  specialist. (No junior/mid floor here — that's a dealbreaker.)
- **remote** — this is really the **work-mode/eligibility** bucket:
  `remote`/`fully remote`/`100% remote`/`remote-first`, `work from home`,
  `hybrid`, **region-open signals** `latam`/`brazil` (eligible even when "remote"
  isn't spelled out), **and relocation signals** `relocation`/`relocate`/
  `relocation assistance`/`relocation package` — the candidate is happy to move,
  so these count as fit, not disqualifiers.

## What disqualifies
The corpus is dominated by clusters the candidate cannot take; these markers catch
them regardless of how "remote" the post claims to be. They split across **two**
negative buckets by severity:

### `visa_block` (−100, absolute kill)
Right-to-work gates — candidate has no EU/US auth, and these roles either require
existing status or won't sponsor:
  - US: `usc`, `gc only`, `green card`, `us citizen`, `u.s. citizen`,
    `citizenship required`, `h1b`/`h-1b` (hyphenated form is a *substring* miss of
    `h1b` — both needed), `stem opt`, `h4 ead`/`h4ead`, `c2c`, `w2`/`w-2`
    (US tax-employment ⇒ needs US work eligibility), `us-based`/`us based`,
    `local candidates only`, `work authorization`, `security clearance`.
  - EU/UK: `eu citizen`, `eu work permit`, `right to work in the uk`,
    `uk work permit`, `settled status`, `indefinite leave to remain`. Plus
    `australian citizen`.
  - Existing-permit gate (any country): `valid work permit` — requires
    right-to-work the candidate doesn't hold. **Use the `valid `-qualified form,
    NOT bare `work permit`**, which also appears in *offers* ("work permit and
    relocation support provided" — a positive we must not kill).
  - No-sponsorship signals: `no sponsorship`, `no visa sponsorship`,
    `sponsorship is not available`.
  - **Note:** relocation itself is NOT here — it's a positive (see remote bucket).
    Only the *visa gate* disqualifies. Match the **specific** `work authorization`,
    never bare `authorization` (appears in tech contexts like "authn/authz, rbac").
### `dealbreaker` (−10, soft skip)
Strong "not for me" signals that still hard-exclude by default, but aren't
categorical the way a citizenship wall is:
- **Onsite-India staffing / body-shop**: `notice period`, `immediate joiner(s)`,
  `ctc`, `lpa` — plus on-site language (`onsite`, `from office`, `wfo`,
  `no remote`).
- **India-locale** (onsite/India-payroll even when tagged "remote"): bare `india`
  (word-boundary — safe from "Indiana"/"Indianapolis") plus the cities that show
  up `bangalore`/`bengaluru`, `hyderabad`, `noida`, `gurugram`/`gurgaon`, `pune`,
  `chennai`, `mumbai`, `kolkata`, `indore`, `vizag`/`visakhapatnam`, `delhi`,
  `ahmedabad`, `coimbatore`, `kochi`, `jaipur`, `nagpur`, `mysore`/`mysuru`,
  `trivandrum`. **Do NOT** add EU/Canada country/city names — many such roles
  offer visa sponsorship (a relocation positive); those "EU-only" posts are an
  accepted residual.
- **Under-leveling**: `business analyst`, `data analyst` (below target — engineer/
  lead).
- **Seniority floor**: `junior`, `intern(ship)`, `trainee`, `recent/new/fresh
  graduate`, `fresher`, `estagio`/`estagiario`.
- **Tech / role mismatch** (not in profile, common in corpus): `java`, `.net`,
  `c#`, `c++`, `golang`, `sap`, `embedded systems`/`embedded c`, QA-test roles
  (`qa automation`, `test automation`, `automation testing`, `sdet`). **Use the
  specific form** — `c++`/`golang`, never bare `c`/`go`, which match ~25/8 posts
  each on stray "C"/"Go" tokens (grades, "C-level", "go-getter") and silently drop
  good posts.
- **Job-seeker / bench-sales noise** (posts *seeking* work or a recruiter pitching
  candidates, not offering a real role — the inverse of what we want): `hotlist`,
  `bench sales`, `available consultants`, `working with a bench`,
  `represent my consultants`, `c2h`, `opentowork`, `looking for new opportunities`.
  These were validated to hit **only** seeker/bench posts. The trap: "looking
  for"/"seeking"/"exploring" appear in *both* directions — a hiring post says "if
  you're seeking a new opportunity, we'd love to hear from you". So **reject
  ambiguous phrases** (bare `seeking a new opportunity`, bare `open to work` —
  which also matches "open to work from anywhere" in a remote offer) and keep only
  self-referential / bench-specific forms. Use the hashtag `opentowork`, not the
  bare phrase.

## Tuning workflow (when retuning against a corpus)
1. Extract `post_content`, `score`, `matched_keywords` from
   [data/posts.json](data/posts.json) (a `{post_id: record}` dict).
2. Find **frequent unigrams/bigrams in content that no bucket matches** — those
   are candidate keywords (positives if profile-aligned, negatives if they mark
   roles the candidate can't take).
3. Watch for **plural/suffix misses** (rule 1) — re-add the surface form seen.
4. Edit `buckets.json` only; then **re-score the whole corpus** and sanity-check:
   an ideal post (`Senior Python Developer, remote LATAM, FastAPI, agentic ai,
   rag`) should hit ~25; a staffing post (`Bangalore, onsite, immediate joiner,
   CTC LPA`) should go negative and trip a dealbreaker.

## Quick verify
```bash
uv run python -c "from app.scrapper.config.scoring import score_post; \
print(score_post('Senior Python Developer, remote LATAM, FastAPI, agentic ai, rag, langchain')); \
print(score_post('Python Developer, Bangalore, onsite, immediate joiner, CTC 20 LPA'))"
# expect ~ (25, {...role/seniority/remote/skill...}) and a negative score with a 'dealbreaker' hit
```
