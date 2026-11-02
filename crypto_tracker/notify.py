"""Benachrichtigungen: Terminal und optional Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env)."""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat = os.getenv("TELEGRAM_CHAT_ID")

    def __call__(self, text: str):
        print(text, flush=True)
        if self.token and self.chat:
            try:
                requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                              data={"chat_id": self.chat, "text": text}, timeout=10)
            except Exception as e:
                log.warning("Telegram fehlgeschlagen: %s", e)
