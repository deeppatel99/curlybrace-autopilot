"""Parse a generated article, render its asset blocks, validate the format."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .design import render_asset

ASSET_RE = re.compile(r"```asset\s*\n(.*?)\n```", re.S)


@dataclass
class Asset:
    index: int
    spec: dict
    filename: str = ""
    local_path: Path | None = None
    url: str | None = None

    @property
    def alt(self) -> str:
        return self.spec.get("title") or self.spec.get("type", "image")


@dataclass
class Article:
    title: str
    subtitle: str
    slug: str
    tags: list[str]
    body: str                      # markdown with {{ASSET:n}} placeholders
    assets: list[Asset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # final markdown with image links (local or hosted)
    def to_markdown(self, use_urls: bool, with_title: bool = True) -> str:
        body = self.body
        for a in self.assets:
            src = a.url if use_urls and a.url else a.filename
            body = body.replace(f"{{{{ASSET:{a.index}}}}}", f"![{a.alt}]({src})")
        head = f"# {self.title}\n\n## {self.subtitle}\n\n" if with_title else ""
        return head + body.strip() + "\n"


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80] or "article"


def parse(md: str, json_fixer=None) -> Article:
    warnings: list[str] = []
    fm = {}
    md = md.replace("\r\n", "\n")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", md, re.S)
    if m:
        fm = _front_matter(m.group(1))
        md = md[m.end():]
    else:
        warnings.append("No front matter found (title/subtitle/slug/tags).")

    title = str(fm.get("title") or "Untitled")
    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    art = Article(
        title=title,
        subtitle=str(fm.get("subtitle") or ""),
        slug=_slugify(str(fm.get("slug") or title)),
        tags=[str(t) for t in tags],
        body="",
        warnings=warnings,
    )

    out, idx, pos = [], 0, 0
    for mm in ASSET_RE.finditer(md):
        out.append(md[pos:mm.start()])
        raw = mm.group(1).strip()
        spec = _load_json(raw, json_fixer, art.warnings)
        if spec is None:
            out.append("")  # drop unrenderable block, warned above
        else:
            idx += 1
            art.assets.append(Asset(index=idx, spec=spec))
            out.append(f"{{{{ASSET:{idx}}}}}")
        pos = mm.end()
    out.append(md[pos:])
    art.body = "".join(out)
    return art


def _front_matter(block: str) -> dict:
    """YAML first; if a title contains ':' (very common) fall back to simple key: value lines."""
    try:
        fm = yaml.safe_load(block)
        if isinstance(fm, dict):
            return fm
    except yaml.YAMLError:
        pass
    fm = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        val = val.strip().strip('"').strip("'")
        if key.strip() == "tags":
            val = [t.strip().strip('"').strip("'") for t in val.strip("[]").split(",") if t.strip()]
        fm[key.strip()] = val
    return fm


def _load_json(raw: str, fixer, warnings) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        if fixer:
            try:
                fixed = fixer(raw, str(e))
                fixed = re.sub(r"^```(?:json)?\s*|\s*```$", "", fixed.strip())
                return json.loads(fixed)
            except Exception:
                pass
        warnings.append(f"Asset block skipped (invalid JSON): {raw[:80]}...")
        return None


def render_all(art: Article, out_dir: Path) -> None:
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    counters: dict[str, int] = {}
    for a in art.assets:
        kind = a.spec.get("type", "asset")
        if kind == "diagram":
            kind = f"diagram-{a.spec.get('style', 'flow')}"
        if kind == "gif":
            kind = f"gif-{a.spec.get('style', 'flow')}"
        counters[kind] = counters.get(kind, 0) + 1
        stem = f"{a.index:02d}-{kind}" + (f"-{counters[kind]}" if kind not in ("cover", "revision") else "")
        try:
            p = render_asset(a.spec, img_dir / stem)
            a.local_path = p
            a.filename = f"images/{p.name}"
        except Exception as e:  # never let one bad visual kill the run
            art.warnings.append(f"Could not render asset {a.index} ({kind}): {e}")
            art.body = art.body.replace(f"{{{{ASSET:{a.index}}}}}", "")
    art.assets = [a for a in art.assets if a.local_path]


def validate(art: Article, cfg) -> list[str]:
    """Format checks against the proven article template."""
    w = []
    body = art.body
    n_q = len(re.findall(r"^##\s+Q\d+\.", body, re.M))
    want_q = int(cfg.get("article.questions", 12))
    if n_q != want_q:
        w.append(f"Expected {want_q} questions, found {n_q}.")
    norm = body.replace("\u2019", "'")
    for part, pat in [("What they're testing", r"\*\*What they'?re (actually )?testing"),
                      ("The analogy", r"\*\*The analogy"),
                      ("Say this in the interview", r"\*\*Say this"),
                      ("The trap / follow-up", r"\*\*The trap"),
                      ("Memory hook", r"\*\*Memory hook")]:
        c = len(re.findall(pat, norm))
        if c < n_q:
            w.append(f"'{part}' appears {c}x for {n_q} questions.")
    cta = cfg.get("article.cta", "")
    if cta and cta not in body:
        w.append("Fixed CTA is missing or was reworded.")
    if len(art.tags) != 5:
        w.append(f"Expected exactly 5 tags, got {len(art.tags)}: {art.tags}")
    kinds = [a.spec.get("type") for a in art.assets]
    if kinds[:1] != ["cover"]:
        w.append("First asset is not the cover.")
    for k, lo, hi in [("table", 3, 4), ("diagram", 2, 3), ("gif", 2, 2), ("revision", 1, 1)]:
        c = kinds.count(k)
        if not lo <= c <= hi:
            w.append(f"{k}: {c} (target {lo}-{hi}).")
    if re.search(r"^\|.*\|\s*$", body, re.M):
        w.append("A markdown table slipped in — Medium will not render it.")
    for h in ["## 5-Question Self-Check", "## Coming next"]:
        if h not in body:
            w.append(f"Missing section: {h}")
    return w
