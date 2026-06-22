"""Posting-time & day-of-week trend report for the scraped job corpus.

Self-contained (stdlib only): reads data/posts.json and writes a Markdown report
of WHEN good-matching posts appear — day-of-week and hour-of-day distributions —
so you can spot shifts in posting patterns over time and tune when to check / run
the poller. Run weekly. See the `posting-time-trends` SKILL.md for interpretation.

    uv run python .claude/skills/posting-time-trends/analyze_trends.py
    uv run python .claude/skills/posting-time-trends/analyze_trends.py --since-days 30
    uv run python .claude/skills/posting-time-trends/analyze_trends.py --tz -5 --min-score 15
"""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[3]
POSTS_JSON = REPO_ROOT / "data" / "posts.json"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# Reference zones to read the local clock a wave was posted in (helps attribute a
# peak to a region's business hours). Offsets are standard-time; DST shifts ±1h.
REF_ZONES = {"US-ET": -4, "CEST": 2, "IST": 5.5}


def _local(record, tz):
    """Parse posted_at and return it in the report timezone, or None."""
    try:
        return datetime.fromisoformat(record["posted_at"]).astimezone(tz)
    except (TypeError, ValueError, KeyError):
        return None


def _bar(n, scale):
    return "#" * round(n * scale)


def _ref_clocks(hour, tz_off):
    utc = hour - tz_off
    out = []
    for name, off in REF_ZONES.items():
        t = (utc + off) % 24
        out.append(f"{name} {int(t):02d}:{int(round((t % 1) * 60)):02d}")
    return ", ".join(out)


def build_report(posts, tz_off, min_scores, since_days):
    tz = timezone(timedelta(hours=tz_off))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=since_days) if since_days else None

    records = []
    for rec in posts.values():
        local = _local(rec, tz)
        if local is None:
            continue
        if cutoff and datetime.fromisoformat(rec["posted_at"]) < cutoff:
            continue
        records.append((rec.get("score", 0), local))

    window = f"last {since_days} days" if since_days else "all history"
    lines = [
        f"# Posting-time trends — {now:%Y-%m-%d}",
        "",
        f"- Window: **{window}** ({len(records)} posts) · Timezone: **UTC{tz_off:+g}**",
        "- Day = peak weekday for good matches; Hour = when they land in your zone.",
        "",
    ]

    # --- Score-cohort sections: day-of-week + top hours -----------------------
    for thr in min_scores:
        cohort = [(s, d) for s, d in records if s >= thr]
        lines += [f"## Score >= {thr}  ({len(cohort)} posts)", ""]
        if not cohort:
            lines += ["_No posts in this cohort._", ""]
            continue

        days = Counter(d.strftime("%A") for _, d in cohort)
        peak_day = max(DAYS, key=lambda d: days.get(d, 0))
        scale = 30 / max(days.values())
        lines.append("**Day of week**")
        for day in DAYS:
            c = days.get(day, 0)
            marker = "  <- peak" if day == peak_day else ""
            lines.append(f"    {day:9} {_bar(c, scale):30} {c}{marker}")

        hours = Counter(d.hour for _, d in cohort)
        lines += ["", "**Top hours** (your zone | regional business clock)"]
        for h, c in hours.most_common(5):
            lines.append(f"    {h:02d}:00  x{c:<3} ({_ref_clocks(h, tz_off)})")

        # Top-3 hours per weekday: shows whether timing diverges by day.
        per_day = defaultdict(Counter)
        for _, d in cohort:
            per_day[d.strftime("%A")][d.hour] += 1
        lines += ["", "**Top-3 hours per day**"]
        for day in DAYS:
            top = ", ".join(f"{h:02d}:00({n})" for h, n in per_day[day].most_common(3))
            lines.append(f"    {day:9} (n={sum(per_day[day].values()):2}): {top or '—'}")
        lines.append("")

    # --- Hourly quality curve (positive posts only) ---------------------------
    lines += ["## Hourly quality (score >= 0 only)", "",
              "Count and average score per hour — find the slot that is both busy",
              "and high-quality.", "",
              f"    {'hr':>5} {'n':>4} {'avg':>5}"]
    by_hour = defaultdict(list)
    for s, d in records:
        if s >= 0:
            by_hour[d.hour].append(s)
    for h in range(24):
        vals = by_hour.get(h, [])
        avg = f"{mean(vals):4.1f}" if vals else "  - "
        lines.append(f"    {h:02d}:00 {len(vals):4} {avg}  {_bar(len(vals), 1)}")
    lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tz", type=float, default=-5,
                    help="report timezone UTC offset in hours (default -5, Bogota)")
    ap.add_argument("--min-score", type=int, nargs="+", default=[15, 20],
                    help="score cohorts to report (default: 15 20)")
    ap.add_argument("--since-days", type=int, default=0,
                    help="only posts from the last N days (0 = all history)")
    ap.add_argument("--posts", type=Path, default=POSTS_JSON)
    ap.add_argument("--out", type=Path, default=None,
                    help="output path (default data/trends-YYYY-MM-DD.md)")
    args = ap.parse_args()

    with open(args.posts, encoding="utf-8") as fh:
        posts = json.load(fh)

    report = build_report(posts, args.tz, args.min_score, args.since_days)
    out = args.out or REPO_ROOT / "data" / f"trends-{datetime.now():%Y-%m-%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
