"""Telegram-Bot (Long-Polling, ohne Zusatzbibliothek).

Befehle:
  /scan [solana|bsc|eth|base]   kompletter Scan: Top 3, Favorit mit 7 Punkten, Bedingungen, Szenarien
  /check <Contract> [chain]     einen bestimmten Coin prüfen
  /invest <Betrag> [Contract]   Szenarien für einen eigenen Betrag (ohne Contract: Favorit des letzten Scans)
  /status                       letzter Scan
  /hilfe                        Übersicht

Zugriff: nur Chat-IDs aus TELEGRAM_ALLOWED_CHATS (oder TELEGRAM_CHAT_ID). Ohne Eintrag antwortet der Bot
nur mit der eigenen Chat-ID, damit Fremde deine API-Limits nicht verbrauchen.
"""
from __future__ import annotations

import logging
import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

import requests

from . import report
from .scanner import CHAIN_ALIASES, ScanResult, Scanner

log = logging.getLogger(__name__)

HELP = """🤖 <b>Memecoin-Scanner für Trust Wallet</b>

/scan – alle Chains scannen (Solana, BSC, Ethereum, Base). Dauert ca. 2–4 Minuten.
/scan solana – nur eine Chain (solana, bsc, eth, base)
/check &lt;Contract&gt; – einen Coin auf Rug-Pull, Honeypot, Whales &amp; Co. prüfen
/invest 250 – Szenarien für 250 € mit dem Favoriten des letzten Scans
/invest 250 &lt;Contract&gt; – Szenarien für einen bestimmten Coin
/status – Zeitpunkt und Ergebnis des letzten Scans

Ich prüfe: Market Cap, Volumen-Trend, Käufer vs. Verkäufer, große Trades (Whales), Holder-Verteilung,
Insider-Wallets, Mint/Freeze, Honeypot, Steuern, gesperrte Liquidität – und nenne Kaufbedingungen.
<i>Keine Anlageberatung. Memecoins können jederzeit auf 0 fallen.</i>"""

COMMANDS = [("scan", "Memecoins scannen (optional: solana/bsc/eth/base)"),
            ("check", "Coin prüfen: /check <Contract-Adresse>"),
            ("invest", "Szenarien: /invest <Betrag> [Contract]"),
            ("status", "Letzter Scan"),
            ("hilfe", "Hilfe")]

ADDRESS_RE = re.compile(r"^(0x[0-9a-fA-F]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})$")


class TelegramAPI:
    def __init__(self, token: str, session: requests.Session | None = None):
        self.base = f"https://api.telegram.org/bot{token}"
        self.session = session or requests.Session()

    def call(self, method: str, timeout: float = 30, **params):
        r = self.session.post(f"{self.base}/{method}", json=params, timeout=timeout)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method}: {data.get('description')}")
        return data.get("result")

    def get_updates(self, offset: int | None, timeout: int = 50) -> list[dict]:
        params = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            params["offset"] = offset
        return self.call("getUpdates", timeout=timeout + 10, **params) or []

    def send(self, chat_id: int, text: str):
        for part in report.split_message(text):
            try:
                self.call("sendMessage", chat_id=chat_id, text=part, parse_mode="HTML",
                          disable_web_page_preview=True)
            except RuntimeError as e:  # z. B. kaputtes HTML -> als Klartext nochmal
                log.warning("%s – sende ohne Formatierung", e)
                self.call("sendMessage", chat_id=chat_id, text=re.sub(r"<[^>]+>", "", part),
                          disable_web_page_preview=True)


@dataclass
class Job:
    chat_id: int
    name: str
    run: Callable[[], None]


class Bot:
    def __init__(self, api: TelegramAPI, scanner: Scanner, allowed: set[int]):
        self.api, self.scanner, self.allowed = api, scanner, allowed
        self.cfg = scanner.cfg
        self.jobs: queue.Queue[Job] = queue.Queue()
        self.last_scan: ScanResult | None = None
        self.busy: str | None = None

    # ------------------------------------------------------------------ Befehle
    def handle(self, update: dict):
        msg = update.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat_id = (msg.get("chat") or {}).get("id")
        if not text or chat_id is None:
            return
        parts = text.split()
        cmd = parts[0].split("@")[0].lower()
        args = parts[1:]
        if not cmd.startswith("/") and ADDRESS_RE.match(parts[0]):  # nackte Adresse = /check
            cmd, args = "/check", parts
        if chat_id not in self.allowed:
            self.api.send(chat_id, f"🔒 Dieser Bot ist privat.\nDeine Chat-ID: <code>{chat_id}</code>\n"
                                   f"Trage sie in der .env als TELEGRAM_ALLOWED_CHATS ein und starte den Bot neu.")
            return
        if cmd in ("/start", "/hilfe", "/help"):
            self.api.send(chat_id, HELP)
        elif cmd == "/status":
            self.api.send(chat_id, self.status_text())
        elif cmd == "/scan":
            chains = [CHAIN_ALIASES[a.lower()] for a in args if a.lower() in CHAIN_ALIASES] or None
            if args and not chains:
                self.api.send(chat_id, "Unbekannte Chain. Erlaubt: solana, bsc, eth, base")
                return
            self.enqueue(Job(chat_id, "Scan", lambda: self.do_scan(chat_id, chains)))
        elif cmd == "/check":
            if not args or not ADDRESS_RE.match(args[0]):
                self.api.send(chat_id, "Bitte so: /check &lt;Contract-Adresse&gt; [solana|bsc|eth|base]")
                return
            chain = CHAIN_ALIASES.get(args[1].lower()) if len(args) > 1 else None
            self.enqueue(Job(chat_id, "Check", lambda: self.do_check(chat_id, args[0], chain)))
        elif cmd == "/invest":
            try:
                amount = float(args[0].replace("€", "").replace(",", "."))
                assert 0 < amount <= 1_000_000
            except (IndexError, ValueError, AssertionError):
                self.api.send(chat_id, "Bitte so: /invest 250  oder  /invest 250 &lt;Contract-Adresse&gt;")
                return
            addr = args[1] if len(args) > 1 else None
            self.enqueue(Job(chat_id, "Szenario", lambda: self.do_invest(chat_id, amount, addr)))
        else:
            self.api.send(chat_id, "Unbekannter Befehl. /hilfe zeigt alle Befehle.")

    def enqueue(self, job: Job):
        waiting = self.jobs.qsize() + (1 if self.busy else 0)
        self.jobs.put(job)
        if waiting:
            self.api.send(job.chat_id, f"⏳ In der Warteschlange (Position {waiting + 1}) – gerade läuft: {self.busy}")

    def status_text(self) -> str:
        r = self.last_scan
        if not r:
            return "Noch kein Scan in dieser Sitzung. Starte mit /scan"
        fav = r.favorite(self.cfg["recommend"]["min_score"])
        t = r.finished.astimezone(report.TZ).strftime("%d.%m.%Y %H:%M")
        alter = (time.time() - r.finished.timestamp()) / 60
        return (f"Letzter Scan: {t} Uhr (vor {alter:.0f} Min.)\n"
                f"Favorit: {report.h(fav.cand.symbol) + ' (Score ' + format(fav.score, '.0f') + ')' if fav else 'keiner'}\n"
                f"Daten älter als 15 Min.? Neu scannen – Memecoin-Kurse ändern sich in Minuten.")

    # ------------------------------------------------------------------ Aufgaben
    def do_scan(self, chat_id: int, chains: list[str] | None):
        self.api.send(chat_id, "🔎 Scan gestartet – das dauert ca. 2–4 Minuten …")
        last = [0.0]

        def progress(s: str):
            if time.time() - last[0] > 20:
                last[0] = time.time()
                self.api.send(chat_id, f"⏳ {report.h(s)}")

        r = self.scanner.scan(chains, progress=progress)
        self.last_scan = r
        self.api.send(chat_id, report.scan_overview(r, self.cfg))
        fav = r.favorite(self.cfg["recommend"]["min_score"])
        if fav:
            self.api.send(chat_id, report.detail(fav, self.cfg, r.market, r.biggest_meme, title="⭐ Favorit"))

    def do_check(self, chat_id: int, address: str, chain: str | None):
        self.api.send(chat_id, "🔬 Prüfe den Coin – ca. 15–30 Sekunden …")
        res = self.scanner.check(address, chain)
        if not res:
            self.api.send(chat_id, "Keinen handelbaren Pool zu dieser Adresse auf Solana/BSC/Ethereum/Base gefunden. "
                                   "Adresse prüfen oder Chain angeben: /check &lt;Adresse&gt; base")
            return
        a, market = res
        biggest = self.last_scan.biggest_meme if self.last_scan else None
        self.api.send(chat_id, report.detail(a, self.cfg, market, biggest))

    def do_invest(self, chat_id: int, amount: float, address: str | None):
        if address:
            res = self.scanner.check(address)
            if not res:
                self.api.send(chat_id, "Keinen Pool zu dieser Adresse gefunden.")
                return
            cand, market = res[0].cand, res[1]
        else:
            fav = self.last_scan.favorite(self.cfg["recommend"]["min_score"]) if self.last_scan else None
            if not fav:
                self.api.send(chat_id, "Kein Favorit vorhanden – erst /scan ausführen oder Contract angeben.")
                return
            cand, market = fav.cand, self.last_scan.market
        self.api.send(chat_id, report.invest_message(cand, amount, self.cfg, market))

    # ------------------------------------------------------------------ Schleifen
    def worker(self):
        while True:
            job = self.jobs.get()
            self.busy = job.name
            try:
                job.run()
            except Exception as e:  # Bot darf nie abstürzen
                log.exception("%s fehlgeschlagen", job.name)
                try:
                    self.api.send(job.chat_id, f"❌ {job.name} fehlgeschlagen: {report.h(e)}")
                except Exception:
                    pass
            finally:
                self.busy = None
                self.jobs.task_done()

    def run_forever(self):
        try:
            self.api.call("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS])
        except Exception as e:
            log.warning("Befehlsmenü nicht gesetzt: %s", e)
        me = self.api.call("getMe")
        log.info("Bot @%s läuft. Erlaubte Chats: %s", me.get("username"), sorted(self.allowed) or "keine")
        print(f"✅ Bot @{me.get('username')} läuft – schreib ihm in Telegram /hilfe  (Strg+C beendet)", flush=True)
        threading.Thread(target=self.worker, daemon=True).start()
        offset = None
        while True:
            try:
                for u in self.api.get_updates(offset):
                    offset = u["update_id"] + 1
                    try:
                        self.handle(u)
                    except Exception:
                        log.exception("Update fehlgeschlagen")
            except (requests.RequestException, RuntimeError) as e:
                log.warning("Telegram-Verbindung: %s – neuer Versuch in 5 s", e)
                time.sleep(5)


def parse_allowed(*values: str | None) -> set[int]:
    out: set[int] = set()
    for v in values:
        for part in re.split(r"[,\s;]+", v or ""):
            if re.fullmatch(r"-?\d+", part):
                out.add(int(part))
    return out
