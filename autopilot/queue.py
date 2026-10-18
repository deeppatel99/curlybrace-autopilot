"""Topic queue (topics/queue.yaml). The agent picks the first 'pending' topic."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def save(path: Path, items: list[dict]) -> None:
    header = ("# Topic queue — the agent takes the first item with status: pending.\n"
              "# status: pending | done | skipped. Add new topics at the bottom.\n"
              "# track decides the lead tag: csharp, aspnetcore, design, sql, azure, devops, ai, system-design\n"
              "# format: deep-dive | bug-hunt | build-log | versus | interview | news (empty = config default)\n"
              "# notes: your REAL experience becomes the opening story. auto: true = planner idea, never told as real\n\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.safe_dump(items, fh, sort_keys=False, allow_unicode=True, width=100)


def next_pending(items: list[dict]) -> tuple[dict | None, dict | None]:
    pend = [i for i in items if i.get("status", "pending") == "pending"]
    return (pend[0] if pend else None, pend[1] if len(pend) > 1 else None)


def mark_done(path: Path, topic: str, result: dict) -> None:
    items = load(path)
    for it in items:
        if it.get("topic") == topic and it.get("status", "pending") == "pending":
            it["status"] = "done"
            it["done_on"] = date.today().isoformat()
            it.update({k: v for k, v in result.items() if v})
            break
    save(path, items)
