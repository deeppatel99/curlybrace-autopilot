"""Tell you when a draft is ready: GitHub Actions run summary + optional Telegram."""
from __future__ import annotations

import os

import requests


def notify(cfg, text_md: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text_md + "\n")

    bot, chat = cfg.secret("TELEGRAM_BOT_TOKEN"), cfg.secret("TELEGRAM_CHAT_ID")
    if bot and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{bot}/sendMessage",
                          json={"chat_id": chat, "text": text_md, "disable_web_page_preview": True},
                          timeout=20)
        except requests.RequestException as e:
            print(f"  ! Telegram notify failed: {e}")
