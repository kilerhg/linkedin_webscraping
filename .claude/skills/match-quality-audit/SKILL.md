---
name: match-quality-audit
description: Step-by-step method for auditing the LinkedIn job heuristic's false positives (bad posts that surface in the digest) and false negatives (good posts wrongly excluded), then turning findings into safe buckets.json changes. Use when asked to "evaluate/analyze false positives and false negatives", audit match quality, find why good posts are missing or junk is surfacing, or before/after-check a scoring change. Ships audit_matches.py to automate it.
---

# Match-quality audit — false positives & false negatives

The method for answering **"is the digest surfacing the right posts?"** against
the real corpus ([data/posts.json](data/posts.json)). It complements
`job-scoring-rules` (the *what/why* of the config) with the *how to measure*: find
where `score_post` misfires, quantify it, and convert findings into keyword moves
that don't create new misses. Descriptive + prescriptive — you read, decide, then
edit [buckets.json](app/scrapper/config/buckets.json) (never `scoring.py`).

## Definitions (in this system's terms)
A post **surfaces** in the digest when `score >= min_score` (`.env`
`JOB_SUMMARY_MIN_SCORE`, default **18**) **and** it hits no **hard** negative
bucket (`HARD_NEGATIVE_BUCKETS` = negatives without `"hard": false`). So:

- **False positive (FP):** a post that **surfaces but the candidate can't/won't
  take it** — a US/Canada right-to-work-gated role, an onsite/India post whose
  locale marker wasn't matched, or a non-target role (Director, Data Scientist,
  QA) that rode `skill+seniority+remote` past 18 without a real `role` hit.
- **False negative (FN):** a post that is **hard-excluded but is a genuine fit** —
  strong `role + remote + skills`, killed by a negative keyword that fired
  spuriously (a lone `java` in a multi-role EU-relocation post; a bare country
  name where the role actually sponsors/relocates).

The two failure modes come from an **asymmetry**: negatives *hard-exclude on a
single keyword*, so one stray token nukes a good post (→ FN), while visa/geo gates
rely on *exact phrases*, so location-locked posts slip through (→ FP). Every fix
trades these off, so **always measure both directions and the collateral**.

## The tool
```bash
uv run python .claude/skills/match-quality-audit/audit_matches.py [fp|fn|diff|all] \
    [--min-score 18] [--limit 15] [--against HEAD] [--probe "remote (usa" ...]
```
It re-scores the corpus **fresh** from the current `buckets.json` (ignoring the
possibly-stale stored `score` in posts.json — see `job-scoring-rules`), using the
exact match semantics of `scoring.py`. `diff` loads a second config from a git ref
in the same process to compare surfaced sets. Run from the repo root.

## Procedure

### 1. False positives — `audit_matches.py fp`
Reports, over the currently-surfaced set:
- **Geo/visa-gated but surfaced** — matches broad *probe* regexes (US/Canada
  locations, "must be based in", state codes, "authorized to work in"). A probe
  hit is a **prompt to eyeball, not a verdict** — probes are deliberately noisier
  than anything you'd put in `buckets.json`.
- **No target-role match** — surfaced on `skill+seniority+remote` alone. Split
  these by hand into *drift* (Director/BA/Data-Scientist/QA — should be a
  dealbreaker) vs a genuine **role-phrasing gap** (e.g. "Senior Python & GCP
  Engineer" is a good post that just misses the `role` keywords — that's an FN
  hiding in the FP list; add the phrasing to `role`, don't penalize it).
- **'remote' + onsite/hybrid signal** — noisiest section (`ist` matches
  "specialist", `hybrid` is often legitimately fine); use only to spot India/IST
  posts that dodged the locale list.

For each real FP, ask: *what exact surface form* marks it? Add **that** form
(rule 1 in `job-scoring-rules`: lowercase; symbol → substring, else word-bound).

### 2. False negatives — `audit_matches.py fn`
Lists hard-killed posts with **positive-fit >= 15 and role+remote**, sorted by
fit, each annotated with **what killed it**. Read the tells:
- **`<-- single-token kill`** — only one negative keyword fired. This is where
  spurious kills hide. But single-token ≠ automatically wrong: a lone **`india`**
  or **`onsite`** is usually a *true* kill (remote-India / onsite). A lone
  **`java`/`c++`/`.net`** on a post that also has heavy Python/data skills +
  relocation/LATAM is the classic **real FN** — the tech is a nice-to-have or a
  sibling role. (These now live in the **soft** `tech_mismatch` bucket, so after
  that fix they should *no longer appear here* — if a hard single-tech kill shows
  up, that token belongs in `tech_mismatch`, not `dealbreaker`.)
- **India city + `latam`/`brazil`/`relocation` in `remote`** — usually a *true*
  kill: a country-list ("US, India, Brazil…") gave stray remote credit to a real
  onsite post. Don't "fix" these by removing the India term.

The real FN signature: **strong, specific fit** (target role phrased plainly,
many profile skills, an explicit remote/LATAM/relocation+sponsorship offer) killed
by **one token unrelated to the role's core**. Fix by **softening** (move to
`tech_mismatch`, `hard:false`) or **narrowing** the offending keyword — not by
deleting a keyword that also catches many true negatives.

### 3. Decide the fix — precision before you commit
Never add/keep a keyword without checking its **collateral** on the whole corpus.
The discipline that caught `usa` (204 hits, killed 6 real EU-remote roles) vs its
anchored forms (`remote (usa`, `(usa)`, … — 24 hits, 2 collateral):

```bash
# how many posts does a candidate keyword hit, and how many of THOSE look good?
uv run python -c "
import json, re
d=json.load(open('data/posts.json'))
def wb(t,k): return re.search(rf'\b{re.escape(k)}\b',(t or '').lower())
GOOD=['brazil','brasil','latam','european union','relocation','internacional']
kw='usa'
hits=[r for r in d.values() if wb(r['post_content'],kw)]
collat=[r for r in hits if any(g in (r['post_content'] or '').lower() for g in GOOD)]
print(kw,'total',len(hits),'| looks-good collateral',len(collat))
for r in collat[:8]: print('  ::',r['post_content'][:90].replace(chr(10),' '))
"
```
Rules of thumb: prefer the **specific** surface form (`c++` not `c`, `embedded
systems` not `embedded`, anchored `remote (usa` not bare `usa`). If a term's
"looks-good collateral" is more than a couple of real roles, **anchor it or drop
it**. Choose the bucket by severity (`job-scoring-rules`): categorical
right-to-work wall → `visa_block` (−100); can't-take but not categorical →
`dealbreaker` (−10, hard); "not my stack but might co-occur" → `tech_mismatch`
(−6, soft, no exclusion).

### 4. Re-score and before/after — `audit_matches.py diff`
After editing `buckets.json`, **re-score the corpus in place** (stored scores are
from scrape time; `main.py` only backfills *missing* ones):
```bash
uv run python -c "
import json; from app.scrapper.config.scoring import score_post
d=json.load(open('data/posts.json'))
for r in d.values(): r['score'],r['matched_keywords']=score_post(r['post_content'])
json.dump(d,open('data/posts.json','w'),indent=2,ensure_ascii=False)"
```
Then `audit_matches.py diff --against HEAD` lists exactly which posts each change
**recovered** (now surface — confirm each is a real fit) and **dropped** (now
excluded — confirm none are good roles). A clean change recovers the FNs you
targeted and drops the FPs, with an empty "dropped-that-look-good" set.

## Acceptance checks (a good audit ends here)
- `fn` no longer shows hard single-`java`/`c++`/`.net` kills (they're soft now).
- `diff` "dropped" list contains no `brazil`/`latam`/`european union` real roles.
- The `job-scoring-rules` quick-verify still holds: ideal LATAM post ≈25;
  Bangalore-onsite-CTC-LPA post negative + `dealbreaker`.
- Note the **accepted residuals** explicitly (e.g. US *state/city*-only tags like
  "Dearborn, MI" aren't caught; a genuine single-`java` role can now surface) —
  audits document what they deliberately leave, not just what they fix.
