"""Tell you when a draft is ready: GitHub Actions run summary + optional Telegram.

text_html uses Telegram's HTML subset (<b>, <i>, <a>, <code>); GitHub's run summary renders the same tags.
"""
from __future__ import annotations

import os

import requests


def notify(cfg, text_html: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text_html.replace("\n", "<br>\n") + "\n")

    bot, chat = cfg.secret("TELEGRAM_BOT_TOKEN"), cfg.secret("TELEGRAM_CHAT_ID")
    if bot and chat:
        try:
            r = requests.post(f"https://api.telegram.org/bot{bot}/sendMessage",
                              json={"chat_id": chat, "text": text_html, "parse_mode": "HTML",
                                    "disable_web_page_preview": True},
                              timeout=20)
            if not r.ok:
                print(f"  ! Telegram notify failed: {r.text[:200]}")
        except requests.RequestException as e:
            print(f"  ! Telegram notify failed: {e}")
