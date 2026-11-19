"""GitHub-Modus: Befehl aus einem Issue-Kommentar ausführen und die Antwort als Kommentar-Text liefern.

Nutzt exakt dieselbe Befehls-Logik wie der Telegram-Bot (/scan, /check, /invest, /hilfe). GitHub rendert die
HTML-Tags der Telegram-Nachrichten (<b>, <i>, <code>, <a>) direkt, Zeilenumbrüche bleiben in Kommentaren erhalten.
Aufruf: python -m memecoin_bot github --out antwort.md   (Befehl steht in der Umgebungsvariable COMMAND)
"""
from __future__ import annotations

import logging

from .scanner import Scanner
from .telegram_bot import Bot

log = logging.getLogger(__name__)

PROGRESS_PREFIXES = ("🔎 Scan gestartet", "🔬 Prüfe", "⏳")
CHAT = 0


class Collector:
    """Ersetzt die Telegram-API: sammelt alle Nachrichten statt sie zu senden."""

    def __init__(self):
        self.sent: list[str] = []

    def send(self, chat_id: int, text: str):
        self.sent.append(text)


def first_command(text: str) -> str:
    """Nur die erste nicht-leere Zeile zählt (der Rest des Kommentars wird ignoriert)."""
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def run_command(text: str, scanner: Scanner) -> str:
    cmd = first_command(text)
    api = Collector()
    bot = Bot(api, scanner, allowed={CHAT})
    bot.handle({"message": {"text": cmd, "chat": {"id": CHAT}}})
    while not bot.jobs.empty():
        job = bot.jobs.get()
        try:
            job.run()
        except Exception as e:  # Antwort trotzdem posten
            log.exception("%s fehlgeschlagen", job.name)
            api.sent.append(f"❌ {job.name} fehlgeschlagen: {e}")
    parts = [m for m in api.sent if not m.startswith(PROGRESS_PREFIXES)]
    if cmd.split()[0].split("@")[0].lower() == "/invest" and any("Kein Favorit" in p for p in parts):
        parts.append("Tipp: Im GitHub-Modus merkt sich der Bot keinen Scan. Nutze <code>/invest 250 &lt;Contract&gt;</code>.")
    head = f"🤖 <b>Antwort auf</b> <code>{_esc(cmd[:80])}</code>"
    return head + "\n\n" + "\n\n---\n\n".join(parts)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("`", "'")
