"""Everything already live on Medium (topics/published.yaml).

Seeded once from a Medium data export (`run import-medium <folder>`), then kept current from the
RSS feed on every run. The planner uses it so nothing is repeated; the writer uses it to link
related past articles and the reviewer to flag overlap.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import yaml

MIN_WORDS = 400  # shorter export entries are replies to comments, not stories


def path(cfg) -> Path:
    return cfg.root / cfg.get("topics.published_file", "topics/published.yaml")


def load(cfg) -> list[dict]:
    p = path(cfg)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def save(cfg, items: list[dict]) -> None:
    items = sorted(items, key=lambda i: i.get("date", ""), reverse=True)
    with open(path(cfg), "w", encoding="utf-8") as fh:
        fh.write("# Articles already live on Medium (newest first). Kept current from the RSS feed.\n"
                 "# The planner never repeats these; the writer links related ones.\n\n")
        yaml.safe_dump(items, fh, sort_keys=False, allow_unicode=True, width=120)


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def import_export(folder: Path) -> list[dict]:
    """Published stories from an unzipped Medium export (posts/*.html). Drafts and replies are skipped."""
    out = []
    for f in sorted((Path(folder) / "posts").glob("*.html")):
        if f.name.startswith("draft"):
            continue
        s = f.read_text(encoding="utf-8", errors="ignore")
        body = re.search(r'<section data-field="body"[^>]*>(.*)</section>', s, re.S)
        if not body or len(_text(body.group(1)).split()) < MIN_WORDS:
            continue
        title = re.search(r'<h1 class="p-name">(.*?)</h1>', s, re.S)
        sub = re.search(r'<section data-field="subtitle"[^>]*>(.*?)</section>', s, re.S)
        url = re.search(r'href="([^"]+)" class="p-canonical"', s)
        out.append({"date": f.name[:10], "title": _text(title.group(1)) if title else f.stem,
                    "subtitle": _text(sub.group(1)) if sub else "", "url": url.group(1) if url else ""})
    return out


def merge_feed(cfg, items: list[dict]) -> list[dict]:
    """Add stories from the RSS feed that are not in the list yet. Best effort: no network, no change."""
    feed = cfg.get("topics.medium_feed")
    if not feed:
        return items
    try:
        import requests
        xml = requests.get(feed, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text
    except Exception:
        return items
    known = {i["title"].lower() for i in items}
    from email.utils import parsedate_to_datetime
    for it in xml.split("<item>")[1:]:
        title = re.search(r"<title><!\[CDATA\[(.*?)\]\]>", it)
        if not title or html.unescape(title.group(1)).lower() in known:
            continue
        link = re.search(r"<link>([^<?]+)", it)
        sub = re.search(r'medium-feed-snippet">(.*?)</p>', it)
        date = re.search(r"<pubDate>(.*?)</pubDate>", it)
        items.append({"date": parsedate_to_datetime(date.group(1)).date().isoformat() if date else "",
                      "title": html.unescape(title.group(1)), "subtitle": _text(sub.group(1)) if sub else "",
                      "url": link.group(1) if link else ""})
    return items


def refresh(cfg) -> list[dict]:
    items = load(cfg)
    before = len(items)
    items = merge_feed(cfg, items)
    if len(items) != before:
        save(cfg, items)
    return items


def as_prompt_list(items: list[dict]) -> str:
    return "\n".join(f"- {i['title']}" + (f" ({i['url']})" if i.get("url") else "") for i in items) or "(none)"
