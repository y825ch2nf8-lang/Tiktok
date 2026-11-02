"""Konsens-Signale ('mehrere Top-Trader gehen gleichzeitig Long/Short') + Backtest."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean

from .hyperliquid import forward_return
from .models import OPEN_LONG, OPENS, Order


@dataclass
class Signal:
    coin: str
    direction: int          # +1 Long, -1 Short
    traders: list[str]
    against: list[str]
    score: float
    notional: float
    first: datetime
    last: datetime

    @property
    def side(self) -> str:
        return "LONG" if self.direction > 0 else "SHORT"


def consensus(orders: list[Order], as_of: datetime, window_hours: int = 24, min_traders: int = 3,
              weights: dict[str, float] | None = None, names: dict[str, str] | None = None) -> list[Signal]:
    """Nur Eröffnungen, die bis `as_of` stattgefunden haben (kein Blick in die Zukunft)."""
    weights, names = weights or {}, names or {}
    lo = as_of - timedelta(hours=window_hours)
    by_coin: dict[str, dict] = {}
    for o in orders:
        if o.action not in OPENS or not (lo < o.time <= as_of):
            continue
        a = by_coin.setdefault(o.coin, {1: {}, -1: {}, "notional": {1: 0.0, -1: 0.0}, "times": []})
        d = 1 if o.action == OPEN_LONG else -1
        a[d][o.trader] = weights.get(o.trader, 1.0)
        a["notional"][d] += o.notional
        a["times"].append(o.time)
    out = []
    for coin, a in by_coin.items():
        for d in (1, -1):
            if len(a[d]) >= min_traders and len(a[d]) > len(a[-d]):
                out.append(Signal(coin, d, sorted(names.get(t, t) for t in a[d]), sorted(names.get(t, t) for t in a[-d]),
                                  round(sum(a[d].values()) - sum(a[-d].values()), 2), a["notional"][d],
                                  min(a["times"]), max(a["times"])))
    return sorted(out, key=lambda s: (-s.score, -s.notional))


def backtest(orders: list[Order], prices, hold_hours: int = 24, step_hours: int = 4, window_hours: int = 24,
             min_traders: int = 3, delay_min: int = 5, weights=None) -> dict:
    """Alle `step_hours` Stunden Signale prüfen; neues Signal -> kopieren, `hold_hours` halten."""
    opens = [o for o in orders if o.action in OPENS]
    if not opens:
        return {"n": 0}
    t = min(o.time for o in opens) + timedelta(hours=window_hours)
    end = max(o.time for o in opens)
    last_sig: dict[tuple, datetime] = {}
    rets = []
    while t <= end:
        for s in consensus(orders, t, window_hours, min_traders, weights):
            k = (s.coin, s.direction)
            if k in last_sig and t - last_sig[k] < timedelta(hours=hold_hours):
                continue
            last_sig[k] = t
            r = forward_return(prices.series(s.coin), t + timedelta(minutes=delay_min), hold_hours)
            if r is not None:
                rets.append(r * s.direction)
        t += timedelta(hours=step_hours)
    if not rets:
        return {"n": 0}
    return {"n": len(rets), "avg": mean(rets), "win_rate": sum(r > 0 for r in rets) / len(rets),
            "best": max(rets), "worst": min(rets), "hold_hours": hold_hours, "min_traders": min_traders}
