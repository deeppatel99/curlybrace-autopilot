"""The whole flow: topic -> article -> visuals -> hosting -> Medium -> notify."""
from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

from . import article as art_mod
from . import queue as q
from .notify import notify
from .publish import MediumAPI, to_html, write_local_files


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(cfg, item: dict | None = None, from_file: Path | None = None, mode: str | None = None,
        dry_run: bool = False, skip_review: bool = False, from_queue: bool = False) -> dict:
    mode = mode or cfg.get("publish.mode", "api")
    writer = None
    review_md = "_Review skipped._"
    next_item = None

    # 1. Get the markdown -------------------------------------------------
    if from_file:
        log(f"Using existing article: {from_file}")
        raw_md = Path(from_file).read_text(encoding="utf-8")
    else:
        from .writer import Writer
        writer = Writer(cfg)
        if from_queue:
            items = q.load(cfg.queue_file)
            pending = [i for i in items if i.get("status", "pending") == "pending"]
            if len(pending) < 2 and cfg.get("topics.auto_plan", True):
                log("Queue is running low — asking Claude to plan the next topics...")
                covered = [i["topic"] for i in items] + list(cfg.get("topics.already_published", []) or [])
                new = writer.plan_topics(covered, int(cfg.get("topics.plan_batch", 5)))
                items += new
                q.save(cfg.queue_file, items)
                log(f"Added {len(new)} topics to {cfg.queue_file.name}")
            item, next_item = q.next_pending(items)
            if not item:
                log("Queue is empty — nothing to do. Add topics to topics/queue.yaml.")
                return {"status": "empty"}
        log(f"Writing: {item['topic']}  (model: {writer.model})")
        raw_md = writer.write(item, next_item.get("topic") if next_item else item.get("next"))
        if cfg.get("writer.review", True) and not skip_review:
            log("Reviewing for technical accuracy and format...")
            review_md = writer.review(raw_md)
            if "NEEDS FIXES" in review_md.upper()[:200] and cfg.get("writer.auto_fix", True):
                log("Applying review fixes...")
                raw_md = writer.fix(raw_md, review_md)

    # 2. Parse + render visuals ------------------------------------------
    art = art_mod.parse(raw_md, json_fixer=writer.fix_json if writer else None)
    out = cfg.out_dir / f"{date.today().isoformat()}-{art.slug}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "source.md").write_text(raw_md, encoding="utf-8")
    log(f"Rendering {len(art.assets)} visuals...")
    art_mod.render_all(art, out)
    warnings = art.warnings + art_mod.validate(art, cfg)

    # 3. Host images ------------------------------------------------------
    hosted = (not dry_run) and cfg.get("hosting.enabled", True)
    host = None
    if hosted:
        from .host import GitHubHost
        host = GitHubHost(cfg)
        log(f"Uploading {len(art.assets)} images to github.com/{host.repo} ...")
        for a in art.assets:
            path = host.remote_path(art.slug, a.filename)
            a.url = host.upload(a.local_path, path, f"assets: {art.slug}/{a.local_path.name}")
        if art.assets and not host.wait_until_live(art.assets[0].url):
            warnings.append("Images were uploaded but not reachable yet — Medium may show broken images. "
                            "Check the repo is public.")

    files = write_local_files(art, out, hosted=hosted)

    # 4. Publish ----------------------------------------------------------
    result = {"title": art.title, "slug": art.slug, "out_dir": str(out)}
    next_steps: list[str] = []
    if dry_run:
        next_steps.append(f"Dry run — open {files['preview']} to review. Nothing was uploaded.")
    elif mode == "api":
        token = cfg.secret("MEDIUM_TOKEN")
        if not token:
            raise SystemExit("publish.mode is 'api' but MEDIUM_TOKEN is not set. Use --mode import or local.")
        status = cfg.get("publish.status", "draft")
        log(f"Creating Medium post ({status})...")
        post = MediumAPI(token).create_post(art, status=status,
                                            canonical=cfg.get("publish.canonical_url") or None,
                                            publication_id=cfg.get("publish.publication_id") or None)
        result["medium_url"] = post.get("url")
        next_steps.append(f"Open the {status}: {post.get('url')}")
        if status == "draft":
            next_steps.append("Read it top to bottom, check the GIFs animate, then press Publish (or schedule it).")
        if len(art.tags) > 3:
            next_steps.append(f"Confirm all 5 tags are set — older API integrations keep only the first 3. "
                              f"Full list: {', '.join(art.tags)}")
    elif mode == "import":
        page_path = host.remote_path(art.slug, "index.html")
        host.upload(None, page_path, f"page: {art.slug}", content=to_html(art, use_urls=True).encode("utf-8"))
        page = host.pages_url(page_path.rsplit("/", 1)[0] + "/")
        result["import_url"] = page
        next_steps += [
            f"Open https://medium.com/p/import and paste: {page}",
            "Medium pulls in text, images and GIFs as a draft. Review, set the 5 tags, publish.",
            "Note: imported stories get a canonical link back to the GitHub page.",
        ]
    else:  # local
        if hosted:
            next_steps.append(f"Open {files['paste']} in Chrome, Ctrl+A, Ctrl+C, paste into a new Medium story.")
        else:
            next_steps.append(f"Open {files['preview']} to review.")
        next_steps.append(f"Tags to add: {', '.join(art.tags)}")
        _open_for_paste(cfg, files, hosted)

    # 5. Archive + report -------------------------------------------------
    report = _report(art, "dry-run" if dry_run else mode, result, warnings, review_md, next_steps, writer)
    (out / "review.md").write_text(report, encoding="utf-8")
    if hosted:
        if files.get("paste"):
            paste_path = host.remote_path(art.slug, "paste.html")
            host.upload(files["paste"], paste_path, f"paste page: {art.slug}")
            result["paste_url"] = host.pages_url(paste_path)
            if os.environ.get("CI"):
                step = (f"Open {result['paste_url']} (GitHub Pages), Ctrl+A, Ctrl+C, paste into "
                        "https://medium.com/new-story")
                if mode == "local":  # next_steps[0] is the runner's local paste.html path — useless off the runner
                    report = report.replace(next_steps[0], step, 1)
                    next_steps[0] = step
                else:
                    next_steps.insert(0, step)
                    report = report.replace("## Format check", f"- [ ] {step}\n\n## Format check", 1)
        host.upload(None, host.remote_path(art.slug, "review.md"), f"review: {art.slug}", content=report.encode())
        host.upload(None, host.remote_path(art.slug, "article.md"), f"article: {art.slug}",
                    content=art.to_markdown(use_urls=True).encode())

    if from_queue and item and not dry_run:
        q.mark_done(cfg.queue_file, item["topic"], {"medium_url": result.get("medium_url"),
                                                     "import_url": result.get("import_url"),
                                                     "slug": art.slug})

    notify(cfg, f"Curly Brace autopilot: \"{art.title}\" is ready.\n" + "\n".join(f"- {s}" for s in next_steps)
           + (f"\n- {len(warnings)} format warning(s) — see review.md" if warnings else ""))

    log("Done.")
    print("\n" + "\n".join(f"  -> {s}" for s in next_steps))
    if warnings:
        print(f"\n  {len(warnings)} warning(s) — see {out / 'review.md'}")
    if writer:
        print(f"\n  Claude usage: {writer.cost_estimate()}")
    result["warnings"] = warnings
    return result


def _open_for_paste(cfg, files, hosted) -> None:
    """On your PC: open paste.html and a blank Medium story side by side."""
    import os
    import webbrowser

    if os.environ.get("CI") or not cfg.get("publish.auto_open", True):
        return
    try:
        webbrowser.open((files.get("paste") if hosted else files["preview"]).resolve().as_uri())
        if hosted:
            webbrowser.open_new_tab("https://medium.com/new-story")
    except Exception:
        pass


def _report(art, mode, result, warnings, review_md, next_steps, writer) -> str:
    lines = [f"# Review — {art.title}", "",
             f"- Mode: `{mode}`",
             f"- Tags: {', '.join(art.tags)}",
             f"- Visuals: {len(art.assets)}"]
    if result.get("medium_url"):
        lines.append(f"- Medium: {result['medium_url']}")
    if result.get("import_url"):
        lines.append(f"- Import URL: {result['import_url']}")
    if writer:
        lines.append(f"- Claude usage: {writer.cost_estimate()}")
    lines += ["", "## Your checklist", ""] + [f"- [ ] {s}" for s in next_steps]
    lines += ["", "## Format check", ""] + ([f"- {w}" for w in warnings] or ["- All format checks passed."])
    lines += ["", "## AI reviewer report", "", review_md, ""]
    return "\n".join(lines)
