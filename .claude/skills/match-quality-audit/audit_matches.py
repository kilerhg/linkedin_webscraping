#!/usr/bin/env python
"""Audit the job-matching heuristic for false positives / false negatives.

Re-scores the whole corpus ([data/posts.json]) against a keyword config and
reports where the heuristic misfires, so a human can decide which keywords to
add/move/soften. It is *descriptive* — it never edits buckets.json.

Three lenses (see the ``match-quality-audit`` skill for the full method):
  * ``fp``  false positives — posts that SURFACE (score >= min, no hard flag)
            but carry an uncaught disqualifier signal (geo gate, onsite, no
            target-role, etc.).
  * ``fn``  false negatives — posts HARD-EXCLUDED by a negative bucket that
            still have a strong positive fit (role + remote + skills), grouped
            by what killed them, so spurious single-token kills stand out.
  * ``diff`` before/after — compares the working-tree buckets.json against a git
            ref (default HEAD) and lists which posts each change recovers/drops.

Usage:
    uv run python .claude/skills/match-quality-audit/audit_matches.py [fp|fn|diff|all]
        [--min-score N] [--limit N] [--against GITREF] [--probe SUBSTR ...]

Run from the repo root. Scoring semantics mirror scoring.py exactly (lowercase;
keywords with a non ``[\\w ]`` char match as substrings, else word-boundary), and
the config is read as data so two configs can be compared in one process.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
POSTS_JSON = REPO / "data" / "posts.json"
BUCKETS_JSON = REPO / "app" / "scrapper" / "config" / "buckets.json"

# --- Signals that mark a post as a disqualifier the keyword set may not catch.
# These are *probes for the audit*, deliberately broader/noisier than what you'd
# ever put in buckets.json — a hit here is a prompt to eyeball the post, not proof.
GEO_GATE_PROBES = [
    r"\bunited states\b", r"\busa\b", r"\bu\.s\.a\b", r"\bcanada\b",
    r"remote \(usa", r"remote - usa", r"remote in (the )?us(a)?\b",
    r"\(united states\)", r"only from us\b", r"\bus only\b",
    r"apply only if you are in", r"must be (located|based) in",
    r"authorized to work in", r"\blocals? only\b",
    r", (ny|nj|ca|tx|il|ga|va|wa|ma|fl|az|nc|oh|pa|mi)\b",
    r"\b(new york|chicago|dallas|austin|atlanta|boston|seattle|toronto|"
    r"ontario|vancouver|dearborn)\b",
]
ONSITE_PROBES = [r"\bon-?site\b", r"from office", r"\bwfo\b", r"\bhybrid\b",
                 r"\bist\b(?!\w)", r"\bin[- ]office\b"]


def matches(text, keyword):
    """True when ``keyword`` is present in already-lowercased ``text`` — mirrors
    scoring.py: symbol-bearing keywords match as substrings, others word-bounded."""
    if re.search(r"[^\w ]", keyword):
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def compile_scorer(config):
    """Build ``score(text) -> (score, matched, hard_hit)`` from a buckets config
    dict, independent of the loaded scoring.py singleton so two configs can be
    compared in the same run."""
    cap = config.get("skill_cap", 6)
    buckets = config["buckets"]
    hard = {n for n, b in buckets.items()
            if b["weight"] < 0 and b.get("hard", True)}

    def score(text):
        text = (text or "").lower()
        total, matched = 0, {}
        for name, bucket in buckets.items():
            hits = [k for k in bucket["keywords"] if matches(text, k)]
            if not hits:
                continue
            matched[name] = hits
            count = min(len(hits), cap) if name == "skill" else 1
            total += bucket["weight"] * count
        hard_hit = any(name in matched for name in hard)
        return total, matched, hard_hit

    return score, hard


def positive_fit(matched, cap=6):
    """Score the post as if it had NO negatives — how good the fit *would* be.
    Used to rank false-negative candidates: a high positive fit that was killed
    is the interesting case."""
    s = 0
    if "skill" in matched:
        s += 2 * min(len(matched["skill"]), cap)
    for name, weight in (("role", 5), ("seniority", 3), ("remote", 5)):
        if name in matched:
            s += weight
    return s


def load_corpus():
    with open(POSTS_JSON, encoding="utf-8") as f:
        return json.load(f)


def probe(text, patterns):
    low = (text or "").lower()
    return [p for p in patterns if re.search(p, low)]


def excerpt(text, n=120):
    return " ".join((text or "").split())[:n]


def run_fp(corpus, score, min_score, limit, extra_probes):
    """False positives: posts that surface but look disqualified."""
    geo = GEO_GATE_PROBES + [re.escape(p) for p in extra_probes]
    surfaced = []
    for r in corpus.values():
        total, matched, hard = score(r["post_content"])
        if total >= min_score and not hard:
            surfaced.append((total, matched, r["post_content"]))
    print(f"# FALSE POSITIVES  (surfaced = score>={min_score} & no hard flag: "
          f"{len(surfaced)})\n")

    geo_hits = [(s, probe(t, geo), t) for s, m, t in surfaced if probe(t, geo)]
    print(f"## Geo/visa-gated but surfaced ({len(geo_hits)}) — candidate can't "
          f"take these; consider adding the matched form to a negative bucket")
    for s, hits, t in geo_hits[:limit]:
        print(f"  [{s:>3}] {hits} :: {excerpt(t)}")

    norole = [(s, t) for s, m, t in surfaced if "role" not in m]
    print(f"\n## Surfaced with NO target-role match ({len(norole)}) — rode "
          f"skill+seniority+remote; check for Director/Analyst/Scientist drift "
          f"or a genuine role-phrasing gap")
    for s, t in norole[:limit]:
        print(f"  [{s:>3}] {excerpt(t)}")

    onsite = [(s, probe(t, ONSITE_PROBES), t) for s, m, t in surfaced
              if probe(t, ONSITE_PROBES) and "remote" in m]
    print(f"\n## Surfaced as 'remote' but carry an onsite/hybrid signal "
          f"({len(onsite)}) — eyeball; 'ist'/'hybrid' are noisy probes")
    for s, hits, t in onsite[:limit]:
        print(f"  [{s:>3}] {hits} :: {excerpt(t)}")


def run_fn(corpus, score, hard, min_score, limit):
    """False negatives: hard-killed posts that still have a strong positive fit."""
    killed = []
    for r in corpus.values():
        total, matched, hard_hit = score(r["post_content"])
        if not hard_hit:
            continue
        fit = positive_fit(matched)
        if fit >= 15 and "role" in matched and "remote" in matched:
            negs = {n: matched[n] for n in hard if n in matched}
            killed.append((fit, negs, matched.get("remote", []), r["post_content"]))
    killed.sort(key=lambda x: -x[0])
    print(f"# FALSE NEGATIVES  (hard-killed but role+remote & positive-fit>=15: "
          f"{len(killed)})\n")
    print("Spurious-kill tells: a SINGLE tech token (java/c++/.net) as the only")
    print("flag, or an India city alongside latam/brazil/relocation (the country")
    print("list gave stray remote credit to a real onsite post — a true kill).\n")
    for fit, negs, remote, t in killed[:limit]:
        single_tech = sum(len(v) for v in negs.values()) == 1
        tag = "  <-- single-token kill, inspect" if single_tech else ""
        print(f"  fit={fit:>3} killed-by={negs}{tag}")
        print(f"        remote={remote}")
        print(f"        {excerpt(t, 150)}")


def run_diff(corpus, min_score, limit, against):
    """Before/after: working-tree buckets.json vs a git ref."""
    old_raw = subprocess.run(
        ["git", "show", f"{against}:app/scrapper/config/buckets.json"],
        cwd=REPO, capture_output=True, text=True, check=True).stdout
    old_score, _ = compile_scorer(json.loads(old_raw))
    new_score, _ = compile_scorer(json.loads(BUCKETS_JSON.read_text()))

    def surfaced(score):
        out = {}
        for pid, r in corpus.items():
            total, _, hard = score(r["post_content"])
            if total >= min_score and not hard:
                out[pid] = total
        return out

    old, new = surfaced(old_score), surfaced(new_score)
    recovered = set(new) - set(old)
    dropped = set(old) - set(new)
    print(f"# DIFF vs {against}  (surfaced {len(old)} -> {len(new)};  "
          f"+{len(recovered)} recovered / -{len(dropped)} dropped)\n")
    print(f"## RECOVERED (were excluded, now surface) — verify each is a real fit")
    for pid in list(recovered)[:limit]:
        print(f"  [{new[pid]:>3}] {excerpt(corpus[pid]['post_content'])}")
    print(f"\n## DROPPED (were surfacing, now excluded) — verify none are good roles")
    for pid in list(dropped)[:limit]:
        print(f"  [{old[pid]:>3}] {excerpt(corpus[pid]['post_content'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", default="all",
                    choices=["fp", "fn", "diff", "all"])
    ap.add_argument("--min-score", type=int, default=18,
                    help="surface threshold (match JOB_SUMMARY_MIN_SCORE, default 18)")
    ap.add_argument("--limit", type=int, default=15, help="examples per section")
    ap.add_argument("--against", default="HEAD", help="git ref for diff mode")
    ap.add_argument("--probe", nargs="*", default=[],
                    help="extra literal substrings to flag as geo/gate signals in fp mode")
    args = ap.parse_args()

    corpus = load_corpus()
    score, hard = compile_scorer(json.loads(BUCKETS_JSON.read_text()))

    if args.mode in ("fp", "all"):
        run_fp(corpus, score, args.min_score, args.limit, args.probe)
        print()
    if args.mode in ("fn", "all"):
        run_fn(corpus, score, hard, args.min_score, args.limit)
        print()
    if args.mode in ("diff", "all"):
        try:
            run_diff(corpus, args.min_score, args.limit, args.against)
        except subprocess.CalledProcessError:
            print(f"# DIFF skipped — no committed buckets.json at {args.against}",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
