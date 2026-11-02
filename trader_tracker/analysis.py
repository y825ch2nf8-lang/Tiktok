"""Verhaltensanalyse: Wann kaufen/verkaufen die Trader? Wie viel? Was? Und lohnt sich Kopieren?"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean, median

from .models import BUY, SELL, Trade
from .prices import forward_return

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
HORIZONS = (5, 20, 60)  # Handelstage ≈ 1 Woche, 1 Monat, 3 Monate


def _month_phase(d: date) -> str:
    return "Monatsanfang (1.–10.)" if d.day <= 10 else ("Monatsmitte (11.–20.)" if d.day <= 20 else "Monatsende (21.+)")


@dataclass
class TimingProfile:
    weekday: dict[str, Counter] = field(default_factory=lambda: {BUY: Counter(), SELL: Counter()})
    month: dict[str, Counter] = field(default_factory=lambda: {BUY: Counter(), SELL: Counter()})
    month_phase: dict[str, Counter] = field(default_factory=lambda: {BUY: Counter(), SELL: Counter()})
    quarter: dict[str, Counter] = field(default_factory=lambda: {BUY: Counter(), SELL: Counter()})
    filing_hour: Counter = field(default_factory=Counter)
    filing_delays: list[int] = field(default_factory=list)

    def add(self, t: Trade):
        q = f"Q{(t.trade_date.month - 1) // 3 + 1}"
        self.quarter[t.side][q] += 1
        if t.date_precision == "day":
            self.weekday[t.side][WEEKDAYS[t.trade_date.weekday()]] += 1
            self.month[t.side][MONTHS[t.trade_date.month - 1]] += 1
            self.month_phase[t.side][_month_phase(t.trade_date)] += 1
        if t.filed_at and (t.filed_at.hour or t.filed_at.minute):
            self.filing_hour[t.filed_at.hour] += 1
        if t.filing_delay_days is not None and t.filing_delay_days >= 0:
            self.filing_delays.append(t.filing_delay_days)

    @staticmethod
    def top(c: Counter) -> str | None:
        return c.most_common(1)[0][0] if c else None


@dataclass
class TraderStats:
    name: str
    group: str
    buys: int = 0
    sells: int = 0
    buy_value: float = 0.0
    sell_value: float = 0.0
    tickers_bought: Counter = field(default_factory=Counter)
    tickers_sold: Counter = field(default_factory=Counter)
    timing: TimingProfile = field(default_factory=TimingProfile)
    trade_values: list[float] = field(default_factory=list)
    first: date | None = None
    last: date | None = None
    fwd: dict[int, list[float]] = field(default_factory=lambda: defaultdict(list))  # Rendite nach Käufen

    @property
    def buy_ratio(self) -> float:
        n = self.buys + self.sells
        return self.buys / n if n else 0.0

    def hit_rate(self, h: int) -> float | None:
        r = self.fwd.get(h) or []
        return sum(1 for x in r if x > 0) / len(r) if r else None

    def avg_return(self, h: int) -> float | None:
        r = self.fwd.get(h) or []
        return mean(r) if r else None


def label(t: Trade) -> str:
    return t.issuer if t.ticker.startswith("CUSIP:") and t.issuer else t.ticker


def analyze(trades: list[Trade], prices=None) -> dict:
    per: dict[str, TraderStats] = {}
    overall = TimingProfile()
    for t in trades:
        s = per.setdefault(t.trader, TraderStats(t.trader, t.group))
        if t.side == BUY:
            s.buys += 1
            s.buy_value += t.value or 0
            s.tickers_bought[label(t)] += 1
        else:
            s.sells += 1
            s.sell_value += t.value or 0
            s.tickers_sold[label(t)] += 1
        if t.value:
            s.trade_values.append(t.value)
        s.timing.add(t)
        overall.add(t)
        s.first = min(filter(None, [s.first, t.trade_date]))
        s.last = max(filter(None, [s.last, t.trade_date]))
        if prices and t.side == BUY:
            series = prices.get(t.ticker)
            for h in HORIZONS:
                # ab dem Tag, an dem der Trade ÖFFENTLICH war – sonst wäre es unfair (Look-ahead)
                r = forward_return(series, t.available_date, h)
                if r is not None:
                    s.fwd[h].append(r)
    return {"traders": per, "overall": overall, "consensus": consensus(trades),
            "clusters": insider_clusters(trades), "n": len(trades)}


def consensus(trades: list[Trade], window_days: int = 120, min_traders: int = 2) -> list[dict]:
    """Aktien, die mehrere verschiedene Trader im Zeitfenster gekauft (oder verkauft) haben."""
    if not trades:
        return []
    end = max(t.trade_date for t in trades)
    start = end - timedelta(days=window_days)
    agg: dict[str, dict] = {}
    for t in trades:
        if t.trade_date < start:
            continue
        a = agg.setdefault(t.ticker, {"ticker": t.ticker, "label": label(t), BUY: set(), SELL: set(),
                                      "buy_value": 0.0, "last": t.trade_date})
        a[t.side].add(t.trader)
        if t.side == BUY:
            a["buy_value"] += t.value or 0
        a["last"] = max(a["last"], t.trade_date)
    rows = []
    for a in agg.values():
        nb, ns = len(a[BUY]), len(a[SELL])
        if max(nb, ns) >= min_traders:
            rows.append({**a, "buyers": sorted(a[BUY]), "sellers": sorted(a[SELL]), "net": nb - ns})
    return sorted(rows, key=lambda r: (-abs(r["net"]), -r["buy_value"]))


def insider_clusters(trades: list[Trade], window_days: int = 30, min_insiders: int = 2) -> list[dict]:
    """Mehrere Insider derselben Firma kaufen kurz hintereinander = historisch eines der stärksten Signale."""
    by_ticker: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        if t.source in ("form4", "demo") and t.group == "Insider" and t.side == BUY:
            by_ticker[t.ticker].append(t)
    out = []
    for tk, ts in by_ticker.items():
        ts.sort(key=lambda t: t.trade_date)
        best = None
        for i, t in enumerate(ts):
            win = [x for x in ts[i:] if (x.trade_date - t.trade_date).days <= window_days]
            people = {x.trader for x in win}
            if len(people) >= min_insiders and (best is None or len(people) > len(best["insiders"])):
                best = {"ticker": tk, "start": t.trade_date, "end": max(x.trade_date for x in win),
                        "insiders": sorted(people), "value": sum(x.value or 0 for x in win),
                        "available": max(x.available_date for x in win)}
        if best:
            out.append(best)
    return sorted(out, key=lambda c: (-len(c["insiders"]), -c["value"]))


def summary_numbers(s: TraderStats) -> dict:
    tv = s.trade_values
    return {"avg_trade": mean(tv) if tv else None, "median_trade": median(tv) if tv else None,
            "median_delay": median(s.timing.filing_delays) if s.timing.filing_delays else None}
