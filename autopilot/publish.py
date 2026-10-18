"""Get the article onto Medium.

Modes (config.yaml -> publish.mode):
  api     Medium API with an integration token -> creates a draft (or public post).
  import  Builds a hosted HTML page; you paste its URL into medium.com/p/import.
  local   No Medium call. Builds preview + paste-ready HTML for copy-paste.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import markdown as md_lib
import requests

MEDIUM = "https://api.medium.com/v1"


# ── Medium API ───────────────────────────────────────────────────────────
class MediumAPI:
    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
        })

    def me(self) -> dict:
        r = self.s.get(f"{MEDIUM}/me", timeout=30)
        if r.status_code != 200:
            raise SystemExit(
                f"Medium token rejected ({r.status_code}). Medium stopped issuing new integration "
                f"tokens, so if yours is new/invalid switch publish.mode to 'import' or 'local'.\n{r.text[:200]}")
        return r.json()["data"]

    def create_post(self, art, status: str = "draft", canonical: str | None = None,
                    publication_id: str | None = None) -> dict:
        user = self.me()
        payload = {
            "title": art.title,
            "contentFormat": "markdown",
            "content": art.to_markdown(use_urls=True),
            "tags": art.tags[:5],
            "publishStatus": status,
            "notifyFollowers": status == "public",
        }
        if canonical:
            payload["canonicalUrl"] = canonical
        url = (f"{MEDIUM}/publications/{publication_id}/posts" if publication_id
               else f"{MEDIUM}/users/{user['id']}/posts")
        r = self.s.post(url, json=payload, timeout=120)
        if r.status_code not in (200, 201):
            raise SystemExit(f"Medium create post failed: {r.status_code} {r.text[:400]}")
        return r.json()["data"]


# ── HTML builders ────────────────────────────────────────────────────────
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="{robots}">
<title>{title}</title>
<meta name="description" content="{subtitle}">
<style>
body{{max-width:740px;margin:40px auto;padding:0 20px;font:19px/1.65 Georgia,serif;color:#1a1a1a;background:#fff}}
h1{{font:700 40px/1.2 -apple-system,Segoe UI,Inter,sans-serif;margin:0 0 8px}}
h2{{font:700 26px/1.3 -apple-system,Segoe UI,Inter,sans-serif;margin:40px 0 10px}}
h2.sub{{font-weight:400;color:#6b6b6b;font-size:22px;margin-top:0}}
img{{max-width:100%;height:auto;display:block;margin:28px auto;border-radius:6px}}
pre{{background:#f4f4f4;padding:16px;overflow:auto;border-radius:4px;font-size:15px;line-height:1.5}}
code{{font-family:Menlo,Consolas,monospace;font-size:.88em}}
blockquote{{border-left:3px solid #1a1a1a;margin:0;padding-left:20px;font-style:italic}}
hr{{border:0;text-align:center;margin:36px 0}}hr:after{{content:"...";letter-spacing:.6em;color:#999}}
.banner{{font:14px/1.5 -apple-system,Segoe UI,sans-serif;background:#fff7d6;border:1px solid #e6d27a;padding:12px 16px;border-radius:6px;margin-bottom:30px;user-select:none;-webkit-user-select:none}}
.banner button{{font:600 16px -apple-system,Segoe UI,sans-serif;background:#1a8917;color:#fff;border:0;border-radius:20px;padding:10px 22px;cursor:pointer;margin-right:12px}}
.banner a{{color:#1a1a1a}}
</style></head><body>
{banner}
<article>
<h1>{title}</h1>
<h2 class="sub">{subtitle}</h2>
{body}
</article></body></html>"""


def to_html(art, use_urls: bool, banner: str = "", robots: str = "noindex,nofollow") -> str:
    body_md = art.to_markdown(use_urls=use_urls, with_title=False)
    body = for_medium_paste(md_lib.markdown(body_md, extensions=["fenced_code", "sane_lists"]))
    return PAGE.format(title=html.escape(art.title), subtitle=html.escape(art.subtitle),
                       body=body, banner=banner, robots=robots)


# Copies exactly what a manual select-all of <article> copies (title, text, hosted images/GIFs, code),
# minus this banner. Async Clipboard API is only the fallback for browsers that refuse execCommand.
COPY_BANNER = """<div class="banner">
<button id="copy" onclick="copyArticle()">Copy article</button>
<a href="https://medium.com/new-story" target="_blank" rel="noopener">Open a new Medium story &#8599;</a>
<div id="msg" style="margin-top:8px">Copies title, text, images, GIFs and code. Then paste into the new story.</div>
</div>
<script>
function copyArticle() {
  var a = document.querySelector('article'), sel = getSelection(), r = document.createRange();
  var msg = function (t) { document.getElementById('msg').textContent = t; };
  var done = 'Copied! Paste it into the new Medium story (Ctrl+V, or long-press then Paste on mobile).';
  r.selectNodeContents(a); sel.removeAllRanges(); sel.addRange(r);
  var ok = false;
  try { ok = document.execCommand('copy'); } catch (e) {}
  sel.removeAllRanges();
  if (ok) return msg(done);
  if (navigator.clipboard && window.ClipboardItem) {
    navigator.clipboard.write([new ClipboardItem({
      'text/html': new Blob([a.innerHTML], {type: 'text/html'}),
      'text/plain': new Blob([a.innerText], {type: 'text/plain'})
    })]).then(function () { msg(done); }, function () { msg('Copy was blocked. Select the article and copy it manually.'); });
  } else msg('Copy is not supported here. Select the article and copy it manually.');
}
</script>"""


def for_medium_paste(body: str) -> str:
    """Shape HTML the way Medium's editor expects on paste (Medium's own export uses the same form).

    - <pre><code>…</code></pre> with newlines: Medium starts a new code block at every blank line.
      -> one <pre>, lines joined with <br>, blank lines hold a &nbsp; so nothing is "empty".
    - <blockquote>\\n<p>…</p>\\n</blockquote>: the trailing newline becomes an extra empty quote line.
      -> <blockquote>text</blockquote>, several paragraphs joined with <br>.
    """
    def pre(m):
        lines = m.group(1).rstrip("\n").split("\n")
        return "<pre>" + "<br>".join(line or "&nbsp;" for line in lines) + "</pre>"

    def quote(m):
        paras = re.findall(r"<p>(.*?)</p>", m.group(1), re.S)
        return f"<blockquote>{'<br>'.join(p.strip() for p in paras)}</blockquote>" if paras else m.group(0)

    body = re.sub(r"<pre><code[^>]*>(.*?)</code></pre>", pre, body, flags=re.S)
    return re.sub(r"<blockquote>(.*?)</blockquote>", quote, body, flags=re.S)


def write_local_files(art, out: Path, hosted: bool) -> dict:
    files = {}
    (out / "article.md").write_text(art.to_markdown(use_urls=False), encoding="utf-8")
    files["markdown"] = out / "article.md"
    (out / "preview.html").write_text(
        to_html(art, use_urls=False, banner='<div class="banner"><b>Local preview</b> — for review only. '
                'Images here are local files, so do not copy this page into Medium.</div>'),
        encoding="utf-8")
    files["preview"] = out / "preview.html"
    if hosted:
        (out / "article.hosted.md").write_text(art.to_markdown(use_urls=True), encoding="utf-8")
        (out / "paste.html").write_text(
            to_html(art, use_urls=True, banner=COPY_BANNER), encoding="utf-8")
        files["paste"] = out / "paste.html"
    return files
