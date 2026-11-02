"""Signale + Backtest (Paper-Trading). Es werden KEINE echten Orders ausgeführt."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean

from .models import BUY, Trade
from .prices import forward_return


@dataclass
class Signal:
    ticker: str
    label: str
    score: float
    available: date        # ab wann das Signal öffentlich bekannt war
    reasons: list[str]


def build_signals(trades: list[Trade], weights: dict[str, float] | None = None,
                  lookback_days: int = 120, as_of: date | None = None) -> list[Signal]:
    """Score pro Aktie: gewichtete Anzahl verschiedener Käufer minus Verkäufer, Insider-Cluster zählen extra.
    Nur Trades, die bis `as_of` öffentlich waren, fließen ein (kein Blick in die Zukunft)."""
    weights = weights or {}
    as_of = as_of or max((t.available_date for t in trades), default=date.today())
    recent = [t for t in trades if as_of - timedelta(days=lookback_days) <= t.available_date <= as_of]
    agg: dict[str, dict] = {}
    for t in recent:
        a = agg.setdefault(t.ticker, {"label": t.issuer if t.ticker.startswith("CUSIP:") else t.ticker,
                                      "buyers": {}, "sellers": {}, "insiders": set(), "avail": t.available_date})
        w = weights.get(t.trader, 1.0)
        (a["buyers"] if t.side == BUY else a["sellers"])[t.trader] = w
        if t.side == BUY and t.group == "Insider":
            a["insiders"].add(t.trader)
        a["avail"] = max(a["avail"], t.available_date)
    sigs = []
    for tk, a in agg.items():
        score = sum(a["buyers"].values()) - sum(a["sellers"].values())
        reasons = []
        if a["buyers"]:
            reasons.append("Käufer: " + ", ".join(sorted(a["buyers"])))
        if a["sellers"]:
            reasons.append("Verkäufer: " + ", ".join(sorted(a["sellers"])))
        if len(a["insiders"]) >= 2:
            score += 1.0
            reasons.append(f"Insider-Cluster ({len(a['insiders'])} Insider kaufen)")
        if score >= 1.5:
            sigs.append(Signal(tk, a["label"], round(score, 2), a["avail"], reasons))
    return sorted(sigs, key=lambda s: -s.score)


def backtest(trades: list[Trade], prices, hold_days: int = 60, benchmark: str = "SPY",
             step_days: int = 30, weights: dict[str, float] | None = None) -> dict:
    """Simuliert: alle `step_days` Tage Signale berechnen, gleichgewichtet kaufen, `hold_days` halten."""
    if not trades:
        return {"n": 0}
    start = min(t.available_date for t in trades) + timedelta(days=30)
    end = max(t.available_date for t in trades)
    bench = prices.get(benchmark)
    rets, excess, d = [], [], start
    while d <= end:
        for s in build_signals(trades, weights, as_of=d)[:5]:
            r = forward_return(prices.get(s.ticker), d + timedelta(days=1), hold_days)
            if r is None:
                continue
            rets.append(r)
            b = forward_return(bench, d + timedelta(days=1), hold_days) if bench else None
            if b is not None:
                excess.append(r - b)
        d += timedelta(days=step_days)
    if not rets:
        return {"n": 0}
    return {"n": len(rets), "avg": mean(rets), "win_rate": sum(r > 0 for r in rets) / len(rets),
            "avg_excess": mean(excess) if excess else None, "hold_days": hold_days, "benchmark": benchmark}
