"""
The Curly Brace — Medium autopilot.

  python run.py check                      verify Claude login, GitHub repo and Medium token
  python run.py next                       write + publish the next topic in topics/queue.yaml
  python run.py topic "EF Core N+1" --track sql --format deep-dive
  python run.py add "Topic" --track azure --format bug-hunt   add a topic to the queue
  formats: deep-dive | bug-hunt | build-log | versus | interview | news
  python run.py file samples/sample-article.md   render + publish an article you already have
  python run.py import-medium <export folder>   record everything already on Medium (unzipped data export)

Common flags:
  --mode api|import|local   override publish.mode from config.yaml
  --dry-run                 render everything locally, upload/publish nothing
  --no-review               skip the AI review pass
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from autopilot import config, pipeline  # noqa: E402
from autopilot import queue as q  # noqa: E402
from autopilot.prompts import FORMATS  # noqa: E402


def cmd_check(cfg) -> None:
    ok = True
    print("Checking setup...\n")
    backend = cfg.get("writer.backend", "claude-code")
    if backend == "api":
        key = cfg.secret("ANTHROPIC_API_KEY")
        print(f"  Writer            : API key {'set' if key else 'MISSING'}")
        ok &= bool(key)
        if key:
            try:
                import anthropic
                anthropic.Anthropic(api_key=key).messages.create(
                    model=cfg.get("writer.model", "claude-opus-5-5"), max_tokens=5,
                    messages=[{"role": "user", "content": "ping"}])
                print(f"  Claude API        : ok ({cfg.get('writer.model')})")
            except Exception as e:
                ok = False
                print(f"  Claude API        : FAILED — {e}")
    else:
        from autopilot.writer import Writer, find_claude_cli
        cli = find_claude_cli()
        if not cli:
            ok = False
            print("  Claude Code CLI   : NOT FOUND — install it (README step 2), then run `claude` once to log in")
        else:
            try:
                w = Writer(cfg)
                reply = w._call("Reply with exactly the word: ok", "ping")
                print(f"  Claude Code CLI   : ok — logged in, model {w.model} replied '{reply[:20]}'")
            except SystemExit as e:
                ok = False
                print(f"  Claude Code CLI   : FAILED — {str(e)[:300]}")
    if cfg.get("hosting.enabled", True):
        try:
            from autopilot.host import GitHubHost
            print(f"  GitHub hosting    : {GitHubHost(cfg).check()}")
        except SystemExit as e:
            ok = False
            print(f"  GitHub hosting    : FAILED — {e}")
    mode = cfg.get("publish.mode", "api")
    tok = cfg.secret("MEDIUM_TOKEN")
    if tok:
        try:
            from autopilot.publish import MediumAPI
            me = MediumAPI(tok).me()
            print(f"  Medium token      : ok (@{me.get('username')})")
        except SystemExit as e:
            ok = mode != "api"
            print(f"  Medium token      : FAILED — {str(e).splitlines()[0]}")
    else:
        print(f"  Medium token      : not set" + (" — REQUIRED for mode 'api'" if mode == "api" else " (fine for mode '" + mode + "')"))
        ok &= mode != "api"
    print(f"  Publish mode      : {mode} / status: {cfg.get('publish.status', 'draft')}")
    bot, chat = cfg.secret("TELEGRAM_BOT_TOKEN"), cfg.secret("TELEGRAM_CHAT_ID")
    if bot:
        import requests
        if not chat:
            # find the chat id from the message you sent your bot
            ups = requests.get(f"https://api.telegram.org/bot{bot}/getUpdates", timeout=20).json().get("result", [])
            ids = {u["message"]["chat"]["id"] for u in ups if "message" in u}
            print("  Telegram          : " + (f"put TELEGRAM_CHAT_ID={ids.pop()} in .env" if ids else
                                            "send any message to your bot first, then run check again"))
        else:
            r = requests.post(f"https://api.telegram.org/bot{bot}/sendMessage",
                              json={"chat_id": chat, "text": "✅ Curly Brace autopilot: Telegram works."}, timeout=20)
            print(f"  Telegram          : {'ok — test message sent' if r.ok else 'FAILED — ' + r.text[:150]}")
    else:
        print("  Telegram          : not set (optional)")
    items = q.load(cfg.queue_file)
    pend = [i for i in items if i.get("status", "pending") == "pending"]
    print(f"  Topic queue       : {len(pend)} pending of {len(items)}")
    print("\nAll good." if ok else "\nFix the items above, then run check again.")


def main() -> None:
    p = argparse.ArgumentParser(description="The Curly Brace Medium autopilot")
    p.add_argument("--config", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--mode", choices=["api", "import", "local"])
        sp.add_argument("--dry-run", action="store_true")
        sp.add_argument("--no-review", action="store_true")

    sub.add_parser("check")
    common(sub.add_parser("next"))
    formats = list(FORMATS)
    t = sub.add_parser("topic")
    t.add_argument("topic")
    t.add_argument("--track", default="")
    t.add_argument("--format", choices=formats, default=None)
    t.add_argument("--kicker", default=None)
    t.add_argument("--notes", default=None)
    t.add_argument("--next", default=None, help="next topic for the teaser")
    common(t)
    a = sub.add_parser("add")
    a.add_argument("topic")
    a.add_argument("--track", default="")
    a.add_argument("--format", choices=formats, default=None)
    a.add_argument("--kicker", default=None)
    a.add_argument("--notes", default=None)
    f = sub.add_parser("file")
    f.add_argument("path")
    common(f)
    m = sub.add_parser("import-medium", help="seed topics/published.yaml from an unzipped Medium export")
    m.add_argument("folder")

    args = p.parse_args()
    cfg = config.load(args.config)

    if args.cmd == "check":
        return cmd_check(cfg)
    if args.cmd == "add":
        items = q.load(cfg.queue_file)
        items.append({k: v for k, v in {"topic": args.topic, "track": args.track, "format": args.format,
                                        "kicker": args.kicker, "notes": args.notes,
                                        "status": "pending"}.items() if v})
        q.save(cfg.queue_file, items)
        print(f"Added. {sum(1 for i in items if i.get('status') == 'pending')} pending topics.")
        return
    if args.cmd == "import-medium":
        from autopilot import published
        items = published.import_export(Path(args.folder))
        published.save(cfg, published.merge_feed(cfg, items))
        print(f"Saved {len(items)} published articles to {published.path(cfg)}")
        return
    kw = dict(mode=args.mode, dry_run=args.dry_run, skip_review=args.no_review)
    if args.cmd == "next":
        pipeline.run(cfg, from_queue=True, **kw)
    elif args.cmd == "topic":
        item = {"topic": args.topic, "track": args.track, "format": args.format, "kicker": args.kicker,
                "notes": args.notes, "next": args.next}
        pipeline.run(cfg, item=item, **kw)
    elif args.cmd == "file":
        pipeline.run(cfg, from_file=Path(args.path), **kw)


if __name__ == "__main__":
    main()
