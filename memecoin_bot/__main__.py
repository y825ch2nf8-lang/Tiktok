"""Memecoin-Bot: python -m memecoin_bot <befehl>

  bot                       Telegram-Bot starten (MEMECOIN_BOT_TOKEN + TELEGRAM_ALLOWED_CHATS in .env)
  scan [--chain solana]     Scan im Terminal (gleiches Ergebnis wie /scan im Bot)
  check <Contract> [--chain base]   einzelnen Coin prüfen
  demo                      Offline-Durchlauf mit erfundenen Tokens (ohne Internet)
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

from . import report
from .scanner import CHAIN_ALIASES, Scanner, load_config

ROOT = Path(__file__).resolve().parent


def _env():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT.parent / ".env")
    except ImportError:
        pass


def plain(html_text: str) -> str:
    """Telegram-HTML fürs Terminal lesbar machen."""
    t = re.sub(r'<a href="([^"]+)">([^<]+)</a>', r"\2 (\1)", html_text)
    t = re.sub(r"<[^>]+>", "", t)
    return t.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _chain(v: str | None) -> str | None:
    if v is None:
        return None
    if v.lower() not in CHAIN_ALIASES:
        sys.exit(f"Unbekannte Chain '{v}'. Erlaubt: solana, bsc, eth, base")
    return CHAIN_ALIASES[v.lower()]


def print_scan(scanner: Scanner, chains):
    r = scanner.scan(chains, progress=lambda s: print("…", s, flush=True))
    print(plain(report.scan_overview(r, scanner.cfg)))
    fav = r.favorite(scanner.cfg["recommend"]["min_score"])
    if fav:
        print("\n" + "=" * 60 + "\n")
        print(plain(report.detail(fav, scanner.cfg, r.market, r.biggest_meme, title="⭐ Favorit")))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m memecoin_bot", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None, help="eigene config.yaml")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bot", help="Telegram-Bot starten")
    s = sub.add_parser("scan", help="Scan im Terminal")
    s.add_argument("--chain", action="append", help="nur diese Chain (mehrfach möglich)")
    c = sub.add_parser("check", help="einzelnen Coin prüfen")
    c.add_argument("address")
    c.add_argument("--chain")
    sub.add_parser("demo", help="Offline-Demo mit erfundenen Tokens")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _env()
    cfg = load_config(args.config)

    if args.cmd == "demo":
        from .demo import demo_scanner
        print("DEMO – alle Tokens und Zahlen sind erfunden.\n")
        print_scan(demo_scanner(cfg), None)
    elif args.cmd == "scan":
        print_scan(Scanner(cfg), [_chain(x) for x in args.chain] if args.chain else None)
    elif args.cmd == "check":
        res = Scanner(cfg).check(args.address, _chain(args.chain))
        if not res:
            sys.exit("Kein Pool zu dieser Adresse gefunden.")
        print(plain(report.detail(res[0], cfg, res[1])))
    elif args.cmd == "bot":
        from .telegram_bot import Bot, TelegramAPI, parse_allowed
        token = os.getenv("MEMECOIN_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            sys.exit("Bot-Token fehlt. Bot bei @BotFather anlegen und als MEMECOIN_BOT_TOKEN in die .env eintragen.")
        allowed = parse_allowed(os.getenv("TELEGRAM_ALLOWED_CHATS"), os.getenv("TELEGRAM_CHAT_ID"))
        if not allowed:
            print("⚠️  Keine erlaubte Chat-ID gesetzt. Schreib dem Bot /start – er antwortet mit deiner Chat-ID.\n"
                  "   Trage sie als TELEGRAM_ALLOWED_CHATS in die .env ein und starte neu.", flush=True)
        Bot(TelegramAPI(token), Scanner(cfg), allowed).run_forever()


if __name__ == "__main__":
    main()
