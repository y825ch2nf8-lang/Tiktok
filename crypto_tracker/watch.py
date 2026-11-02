"""Live-Bot: prüft regelmäßig neue Trades der Top-Trader, meldet sie und kopiert sie per Paper-Trading."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .analysis import WEEKDAYS
from .models import ACTION_DE, CLOSES, OPENS, TraderInfo, aggregate, dt_to_ms, fmt_px, ms_to_dt
from .paper import PaperBook
from .signals import consensus

log = logging.getLogger(__name__)


def fmt_usd(v: float) -> str:
    return f"{v / 1e6:.2f} Mio. $" if v >= 1e6 else f"{v / 1e3:.0f} Tsd. $" if v >= 1e3 else f"{v:.0f} $"


def run_watch(client, traders: list[TraderInfo], data_dir: Path, notify, interval: int = 60, once: bool = False,
              min_notional: float = 25_000, paper_size: float = 100, tz: str = "Europe/Berlin",
              min_traders: int = 3, window_hours: int = 24):
    zone = ZoneInfo(tz)
    state_p = data_dir / "watch_state.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    book = PaperBook(data_dir / "paper.json", paper_size)
    names = {t.address: t.name for t in traders}
    weights = {t.address: t.weight for t in traders}
    recent = []          # Eröffnungen der letzten Stunden für Konsens-Alarme
    alerted: set = set()
    now = datetime.now(timezone.utc)
    for t in traders:    # beim ersten Start keine alten Trades melden
        state.setdefault(t.address, dt_to_ms(now))
    notify(f"🤖 Crypto-Bot läuft: beobachte {len(traders)} Top-Trader (Paper-Trading, {paper_size:.0f} $ pro Kopie)")
    while True:
        try:
            mids = client.mids()
        except Exception as e:
            log.warning("Kurse nicht abrufbar: %s", e)
            mids = {}
        for t in traders:
            try:
                fills = client.fills(t.address, ms_to_dt(state[t.address] + 1), max_pages=2)
            except Exception as e:
                log.warning("%s: %s", t.name, e)
                continue
            if not fills:
                continue
            state[t.address] = max(dt_to_ms(f.time) for f in fills)
            for o in aggregate(fills):
                if o.action not in OPENS | CLOSES:
                    continue
                if o.action in OPENS:
                    recent.append(o)
                if o.notional >= min_notional:
                    loc = o.time.astimezone(zone)
                    ts = f"{WEEKDAYS[loc.weekday()]} {loc:%H:%M}"
                    pnl = f" | Gewinn/Verlust {o.closed_pnl:+,.0f} $" if o.action in CLOSES else ""
                    notify(f"{'🟢' if o.direction > 0 else '🔴'} {t.name} {ACTION_DE[o.action]} {o.coin} "
                           f"– {fmt_usd(o.notional)} @ {fmt_px(o.px)} ({ts}){pnl}")
                msg = book.on_order(o, t.name, mids)
                if msg:
                    notify(msg)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        recent = [o for o in recent if o.time > cutoff]
        for s in consensus(recent, datetime.now(timezone.utc), window_hours, min_traders, weights, names):
            k = (s.coin, s.direction, s.first.isoformat())
            if k not in alerted:
                alerted.add(k)
                notify(f"🚨 KONSENS: {len(s.traders)} Top-Trader gehen {s.side} auf {s.coin}: {', '.join(s.traders[:5])}")
        book.save()
        state_p.write_text(json.dumps(state))
        if once:
            s = book.summary(mids)
            notify(f"📊 Paper-Depot: {s['open']} offen, {s['closed']} geschlossen, realisiert {s['realized']:+.2f} $, "
                   f"offen {s['unrealized']:+.2f} $")
            return
        time.sleep(interval)
