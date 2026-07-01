import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import speedtest

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from app.scrapper.config.scoring import HARD_NEGATIVE_BUCKETS, NEGATIVE_BUCKETS

# Default location for scraped posts. parents[3] = repo root:
# utils -> scrapper -> app -> root.
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
POSTS_JSON = DATA_DIR / "posts.json"


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def extract_first_email(text):
    """Return the first email address found in ``text``, or None if there is none."""
    match = _EMAIL_RE.search(text or "")
    return match.group(0) if match else None


def load_posts_json(path=POSTS_JSON):
    """Return the saved ``{post_id: record}`` dict, or {} when the file is
    missing or unreadable (empty/corrupt)."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_posts_json(posts, path=POSTS_JSON):
    """Write the ``{post_id: record}`` dict to ``path`` as UTF-8 JSON, creating
    the parent directory if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(posts, file, indent=2, ensure_ascii=False)


def _format_matched(matched):
    """Render the positive (non-disqualifier) buckets as a compact one-liner."""
    positives = {b: kws for b, kws in matched.items() if b not in NEGATIVE_BUCKETS}
    if not positives:
        return "_(no keyword matches)_"
    return "; ".join(f"**{bucket}**: {', '.join(keywords)}"
                     for bucket, keywords in positives.items())


def _post_detail_lines(record):
    """Render the detail bullets for a single post."""
    excerpt = " ".join((record.get("post_content") or "").split())[:280]
    matched = record.get("matched_keywords", {})
    lines = [
        f"- **Posted:** {record.get('posted_at', '')}",
        f"- **Link:** {record.get('post_url') or record.get('linkedin_job_url') or '—'}",
        f"- **Matched:** {_format_matched(matched)}",
    ]
    if record.get("email"):
        lines.append(f"- **Contact:** {record['email']}")
    flags = {b: matched[b] for b in NEGATIVE_BUCKETS if matched.get(b)}
    if flags:
        rendered = "; ".join(f"**{bucket}**: {', '.join(kws)}"
                             for bucket, kws in flags.items())
        lines.append(f"- **Flags:** {rendered}")
    lines.append(f"- **Excerpt:** {excerpt}…")
    return lines


def write_summary_markdown(posts, top_n, min_score, roles=None, path=None, hours=24,
                           exclude_dealbreakers=True, require_remote=False):
    """Write a Markdown digest with one section per role, each listing that role's
    top ``top_n`` matches, and return ``(path, selected_records)``.

    Filters ``posts`` (a ``{post_id: record}`` dict) to records posted within the
    window scoring at least ``min_score``; optionally drops posts that hit a
    deal-breaker (``exclude_dealbreakers``) or that don't mention remote work
    (``require_remote``). Groups by each record's ``role``; sections appear in
    ``roles`` order (any leftover roles, incl. untagged, go under "other"). Within
    a section, sorts by score desc then most recent. Writes to
    ``data/summary-YYYY-MM-DD.md`` by default."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    by_role = {}
    for record in posts.values():
        try:
            posted_at = datetime.fromisoformat(record.get("posted_at", ""))
        except (TypeError, ValueError):
            continue
        if posted_at < cutoff or record.get("score", 0) < min_score:
            continue
        matched = record.get("matched_keywords", {})
        if exclude_dealbreakers and any(matched.get(b) for b in HARD_NEGATIVE_BUCKETS):
            continue
        if require_remote and not matched.get("remote"):
            continue
        by_role.setdefault(record.get("role") or "other", []).append(record)

    # Sections in the requested role order, then any leftover groups (e.g. "other").
    ordered_roles = list(roles or [])
    ordered_roles += [role for role in by_role if role not in ordered_roles]

    lines = [f"# Job Summary — {now:%Y-%m-%d}", ""]
    selected = []
    for role in ordered_roles:
        group = by_role.get(role, [])
        # Highest score first; break ties by the most recent post.
        group.sort(
            key=lambda r: (r.get("score", 0), datetime.fromisoformat(r["posted_at"])),
            reverse=True,
        )
        top = group[:top_n]
        selected.extend(top)

        lines += [f"## {role} — top {len(top)} of {len(group)} (last {hours}h)", ""]
        if not top:
            lines += ["_No matches._", ""]
            continue
        for rank, record in enumerate(top, start=1):
            lines.append(f"### {rank}. {record.get('author_name') or 'Unknown'} "
                         f"— score {record.get('score', 0)}")
            lines += _post_detail_lines(record)
            lines.append("")

    path = Path(path) if path else DATA_DIR / f"summary-{now:%Y-%m-%d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))
    return path, selected


def wait_for_element(driver, xpath, timeout=10, clickable=False, context=None):
    """Wait until an element matching ``xpath`` is rendered and return it.

    Polls until the element is present (and, when ``clickable`` is True, also
    visible and enabled). Searches inside ``context`` (a WebElement) when given,
    otherwise the whole page. Returns the element, or None if it never appears
    within ``timeout`` seconds.
    """
    finder = context if context is not None else driver

    def _ready(_driver):
        elements = finder.find_elements(By.XPATH, xpath)
        if not elements:
            return False
        element = elements[0]
        if clickable and not (element.is_displayed() and element.is_enabled()):
            return False
        return element

    try:
        return WebDriverWait(driver, timeout).until(_ready)
    except TimeoutException:
        return None


def checar_conexao():
    try:
        requests.get("https://google.com/")
    except requests.exceptions.ConnectionError:
        erro = sys.stderr
        erro.write("Você não esta conectado a internet.")

def VelocidadeInternet(mostrar=True,retornar=True):
    velocidade = speedtest.Speedtest()

    download = round(velocidade.download()/1000000,2)
    upload = round(velocidade.upload()/1000000,2)
    if mostrar:
        print(f"Velocidade de Download em Mbps: {download}")
        print(f"Velocidade de Upload   em Mbps: {upload}")
    
    if retornar:
        return download, upload
    

class FileHandling:
    ...


class CsvHandling(FileHandling):
    ...