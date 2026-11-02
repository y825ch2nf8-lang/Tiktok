"""Kommandozeile:  python -m trader_tracker <befehl>

  demo                 Komplettlauf mit fiktiven Daten (ohne Internet)
  fetch                Trades von der SEC laden (braucht SEC_USER_AGENT)
  import-csv DATEI     Eigene Trades / Politiker-Trades importieren
  report               Analyse + Signale + Backtest -> output/trader_report/report.html
  signals              Aktuelle Signale im Terminal anzeigen
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from .analysis import analyze
from .models import TraderConfig
from .report import write_reports
from .signals import backtest, build_signals
from .store import TradeStore

ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv("TRADER_DATA_DIR", ROOT / "data"))
OUT = Path(os.getenv("TRADER_OUT_DIR", ROOT.parent / "output" / "trader_report"))


def load_config(path: Path) -> tuple[list[TraderConfig], dict]:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = [TraderConfig(name=s["name"], kind="13f", cik=str(s["cik"]), group="Superinvestor",
                        weight=s.get("weight", 1.0), extra={"cusip_map": s.get("cusip_map", {})})
           for s in cfg.get("superinvestors", [])]
    out += [TraderConfig(name=f"Insider {c.get('ticker') or c.get('cik')}", kind="form4", cik=c.get("cik"),
                         ticker=c.get("ticker"), group="Insider", weight=c.get("weight", 1.0))
            for c in cfg.get("insider_companies", [])]
    return out, cfg.get("settings", {})


def cmd_fetch(args):
    from .f13 import fetch_13f
    from .form4 import fetch_form4
    from .sec_client import SecClient
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT.parent / ".env")
    except ImportError:
        pass
    traders, st = load_config(Path(args.config))
    try:
        client = SecClient(DATA / "cache" / "sec")
    except RuntimeError as e:
        sys.exit(str(e))
    store = TradeStore(DATA / "trades.json")
    since = date.today() - timedelta(days=st.get("since_days", 730))
    for t in traders:
        try:
            new = fetch_13f(client, t, st.get("quarters", 8)) if t.kind == "13f" else fetch_form4(client, t, since)
            print(f"  {t.name:45s} {len(new):5d} Trades, davon neu: {store.merge(new)}")
        except Exception as e:
            print(f"  {t.name:45s} FEHLER: {e}")


def cmd_import(args):
    from .csv_import import import_csv
    trades = import_csv(Path(args.file), args.group)
    print(f"{len(trades)} Trades gelesen, {TradeStore(DATA / 'trades.json').merge(trades)} neu gespeichert.")


def _weights(path: Path) -> dict[str, float]:
    try:
        traders, _ = load_config(path)
        return {t.name: t.weight for t in traders}
    except Exception:
        return {}


def run_report(trades, prices, weights, out: Path, demo=False, benchmark="SPY", hold=60):
    res = analyze(trades, prices)
    sigs = build_signals(trades, weights)
    bt = backtest(trades, prices, hold_days=hold, benchmark=benchmark, weights=weights) if prices else None
    h, m = write_reports(res, sigs, bt, out, demo=demo)
    print(f"{len(trades)} Trades analysiert.\n  HTML: {h}\n  Markdown: {m}")
    if bt and bt.get("n"):
        print(f"  Backtest: {bt['n']} Trades, Ø {bt['avg']:+.1%}, Trefferquote {bt['win_rate']:.0%}")
    return res, sigs, bt


def cmd_report(args):
    trades = TradeStore(DATA / "trades.json").load()
    if not trades:
        sys.exit("Noch keine Trades. Erst 'fetch' oder 'import-csv' ausführen (oder 'demo').")
    _, st = load_config(Path(args.config))
    prices = None
    if not args.no_prices:
        from .prices import PriceProvider
        prices = PriceProvider(DATA / "cache" / "prices")
    run_report(trades, prices, _weights(Path(args.config)), OUT, benchmark=st.get("benchmark", "SPY"),
               hold=st.get("hold_days", 60))


def cmd_signals(args):
    trades = TradeStore(DATA / "trades.json").load()
    for s in build_signals(trades, _weights(Path(args.config)))[:20]:
        print(f"{s.label:30s} Score {s.score:5.2f}  seit {s.available}  |  {' · '.join(s.reasons)}")


def cmd_demo(args):
    from .demo import make_demo
    from .prices import StaticPrices
    trades, prices = make_demo()
    print("DEMO-Modus: alle Trader, Aktien und Kurse sind FIKTIV.")
    run_report(trades, StaticPrices(prices), {}, OUT / "demo", demo=True)


def main(argv=None):
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="trader_tracker", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=str(ROOT / "traders.yaml"))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo").set_defaults(fn=cmd_demo)
    sub.add_parser("fetch").set_defaults(fn=cmd_fetch)
    r = sub.add_parser("report")
    r.add_argument("--no-prices", action="store_true", help="ohne Kursdaten (keine Performance/Backtest)")
    r.set_defaults(fn=cmd_report)
    sub.add_parser("signals").set_defaults(fn=cmd_signals)
    i = sub.add_parser("import-csv")
    i.add_argument("file")
    i.add_argument("--group", default="Politiker")
    i.set_defaults(fn=cmd_import)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
