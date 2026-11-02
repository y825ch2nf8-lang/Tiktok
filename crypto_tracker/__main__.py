"""Krypto-Bot: python -m crypto_tracker <befehl>

  demo        Komplettlauf mit fiktiven Daten (ohne Internet)
  discover    Die besten Trader aus dem Hyperliquid-Leaderboard auswählen -> Watchlist
  fetch       Trades + aktuelle Positionen der Watchlist laden
  report      Analyse, Signale, Backtest -> output/crypto_report/report.html
  positions   Smart Money: wie sind die Top-Trader JETZT positioniert?
  watch       Live-Bot: neue Trades melden (+Telegram) und per Paper-Trading kopieren
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from .analysis import analyze
from .models import TraderInfo, aggregate, short_addr
from .report import money, pct, write_reports
from .signals import backtest, consensus
from .store import Store

ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv("CRYPTO_DATA_DIR", ROOT / "data"))
OUT = Path(os.getenv("CRYPTO_OUT_DIR", ROOT.parent / "output" / "crypto_report"))


def load_cfg(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def _env():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT.parent / ".env")
    except ImportError:
        pass


def client():
    from .hyperliquid import HyperliquidClient
    return HyperliquidClient(DATA / "cache")


def traders(cfg: dict, store: Store) -> list[TraderInfo]:
    wl = {t.address: t for t in store.watchlist()}
    for t in cfg.get("traders") or []:
        a = t["address"].lower()
        wl[a] = TraderInfo(a, t.get("name") or short_addr(a), weight=t.get("weight", 1.0))
    if not wl:
        sys.exit("Watchlist leer. Erst 'python -m crypto_tracker discover' ausführen.")
    return list(wl.values())


def cmd_discover(args, cfg):
    from .hyperliquid import parse_leaderboard, rank_traders
    d = cfg.get("discover", {})
    infos = parse_leaderboard(client().leaderboard())
    top = rank_traders(infos, args.top or d.get("top", 20), d.get("min_account_value", 100_000), d.get("max_turnover", 150))
    Store(DATA).save_watchlist(top)
    print(f"{len(infos)} Trader im Leaderboard, {len(top)} ausgewählt:\n")
    print(f"{'#':>2}  {'Trader':22s} {'Konto':>12s} {'30T-Gewinn':>12s} {'30T-ROI':>9s} {'Allzeit':>12s}")
    for i, t in enumerate(top, 1):
        print(f"{i:>2}  {t.name[:22]:22s} {money(t.account_value):>12s} {money(t.pnl_month):>12s} {pct(t.roi_month):>9s} {money(t.pnl_all):>12s}")


def cmd_fetch(args, cfg):
    store, c = Store(DATA), client()
    since = datetime.now(timezone.utc) - timedelta(days=args.days or cfg.get("fetch_days", 30))
    all_pos = []
    for t in traders(cfg, store):
        try:
            fills = c.fills(t.address, since)
            new = store.merge_fills(t.address, fills)
            _, pos = c.positions(t.address)
            all_pos += pos
            print(f"  {t.name[:28]:28s} {len(fills):6d} Fills ({new} neu), {len(pos)} offene Positionen")
        except Exception as e:
            print(f"  {t.name[:28]:28s} FEHLER: {e}")
    store.save_positions(all_pos)


def _run(fills_by, infos, positions, prices, cfg, out, demo=False, positions_time=None):
    sc = cfg.get("signals", {})
    delay = cfg.get("copy_delay_minutes", 5)
    res = analyze(fills_by, infos, cfg.get("timezone", "Europe/Berlin"), prices, delay, positions)
    orders = res["orders"]
    names = {a: i.name for a, i in infos.items()}
    weights = {a: i.weight for a, i in infos.items()}
    now = max((o.time for o in orders), default=datetime.now(timezone.utc)) if demo else datetime.now(timezone.utc)
    sigs = consensus(orders, now, sc.get("window_hours", 24), sc.get("min_traders", 3), weights, names)
    bt = backtest(orders, prices, sc.get("hold_hours", 24), window_hours=sc.get("window_hours", 24),
                  min_traders=sc.get("min_traders", 3), delay_min=delay, weights=weights) if prices else None
    hp, mp = write_reports(res, sigs, bt, out, demo, positions_time)
    print(f"{len(res['profiles'])} Trader, {res['overall'].orders} Orders analysiert.\n  HTML: {hp}\n  Markdown: {mp}")
    if bt and bt.get("n"):
        print(f"  Backtest Konsens-Signale: {bt['n']} Trades, Ø {bt['avg']:+.2%}, Trefferquote {bt['win_rate']:.0%}")
    return res


def cmd_report(args, cfg):
    from .hyperliquid import CandleCache
    store = Store(DATA)
    ts = traders(cfg, store)
    fills_by = store.all_fills([t.address for t in ts])
    if not any(fills_by.values()):
        sys.exit("Noch keine Trades. Erst 'fetch' ausführen (oder 'demo').")
    ptime, positions = store.positions()
    prices = None
    if not args.no_prices:
        all_t = [f.time for fs in fills_by.values() for f in fs]
        prices = CandleCache(client(), min(all_t) - timedelta(hours=2), datetime.now(timezone.utc))
    _run(fills_by, {t.address: t for t in ts}, positions, prices, cfg, OUT, positions_time=ptime)


def cmd_positions(args, cfg):
    from .analysis import sentiment
    store, c = Store(DATA), client()
    pos = []
    for t in traders(cfg, store):
        try:
            pos += c.positions(t.address)[1]
        except Exception as e:
            print(f"  {t.name}: {e}")
    store.save_positions(pos)
    print(f"{'Coin':10s} {'Long-Anteil':>11s} {'long/short':>10s} {'Volumen':>14s}")
    for s in sentiment(pos)[:20]:
        bar = "█" * round(s["long_share"] * 20) + "░" * (20 - round(s["long_share"] * 20))
        print(f"{s['coin']:10s} {pct(s['long_share'], False):>11s} {s['n_long']:>4d}/{s['n_short']:<5d} {money(s['total']):>14s}  {bar}")


def cmd_watch(args, cfg):
    from .notify import Notifier
    from .watch import run_watch
    w, sc = cfg.get("watch", {}), cfg.get("signals", {})
    run_watch(client(), traders(cfg, Store(DATA)), DATA, Notifier(), args.interval or w.get("interval_seconds", 60), args.once,
              w.get("min_notional_usd", 25_000), w.get("paper_size_usd", 100), cfg.get("timezone", "Europe/Berlin"),
              sc.get("min_traders", 3), sc.get("window_hours", 24))


def cmd_demo(args, cfg):
    from .demo import make_demo
    from .hyperliquid import CandleCache
    fills_by, infos, positions, prices = make_demo()
    print("DEMO-Modus: alle Trader, Coins und Kurse sind FIKTIV.")
    _run(fills_by, infos, positions, CandleCache(None, None, None, prices), cfg, OUT / "demo", demo=True,
         positions_time="Demo")


def main(argv=None):
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    _env()
    p = argparse.ArgumentParser(prog="crypto_tracker", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo").set_defaults(fn=cmd_demo)
    d = sub.add_parser("discover")
    d.add_argument("--top", type=int)
    d.set_defaults(fn=cmd_discover)
    f = sub.add_parser("fetch")
    f.add_argument("--days", type=int)
    f.set_defaults(fn=cmd_fetch)
    r = sub.add_parser("report")
    r.add_argument("--no-prices", action="store_true")
    r.set_defaults(fn=cmd_report)
    sub.add_parser("positions").set_defaults(fn=cmd_positions)
    w = sub.add_parser("watch")
    w.add_argument("--once", action="store_true", help="nur einmal prüfen (z.B. für Cronjobs)")
    w.add_argument("--interval", type=int)
    w.set_defaults(fn=cmd_watch)
    args = p.parse_args(argv)
    import requests
    try:
        args.fn(args, load_cfg(args.config))
    except requests.RequestException as e:
        sys.exit(f"Keine Verbindung zu Hyperliquid ({type(e).__name__}). Internet/Firewall prüfen.\n{e}")
    except KeyboardInterrupt:
        print("\nBeendet.")


if __name__ == "__main__":
    main()
