"""Verhaltensanalyse der Top-Trader: Uhrzeit, Wochentag, Session, Long/Short, Haltedauer,
Trefferquote – und ob sich Kopieren (mit Verzögerung) gelohnt hätte."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, median
from zoneinfo import ZoneInfo

from .hyperliquid import forward_return
from .models import (CLOSES, OPEN_LONG, OPEN_SHORT, OPENS, Fill, Order, Position, TraderInfo, aggregate,
                     short_addr)

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
HORIZONS = (1, 4, 24)  # Stunden


def session(t_utc: datetime) -> str:
    h = t_utc.hour
    if h < 7:
        return "Asien"
    if h < 13:
        return "Europa"
    if h < 21:
        return "USA"
    return "Nacht"


SESSIONS = ["Asien", "Europa", "USA", "Nacht"]
SESSION_INFO = "Asien 0–7 · Europa 7–13 · USA 13–21 · Nacht 21–24 Uhr (UTC)"


@dataclass
class Profile:
    address: str
    name: str
    info: TraderInfo | None = None
    orders: int = 0
    open_long: int = 0
    open_short: int = 0
    closes: int = 0
    coins: Counter = field(default_factory=Counter)                 # nach Volumen
    hour_long: Counter = field(default_factory=Counter)              # Long-Eröffnungen nach Ortszeit-Stunde
    hour_short: Counter = field(default_factory=Counter)
    hour_close: Counter = field(default_factory=Counter)
    weekday_open: Counter = field(default_factory=Counter)
    weekday_close: Counter = field(default_factory=Counter)
    session_open: Counter = field(default_factory=Counter)
    weekend_orders: int = 0
    realized_pnl: float = 0.0
    fees: float = 0.0
    wins: int = 0
    losses: int = 0
    gross_win: float = 0.0
    gross_loss: float = 0.0
    hold_hours: list[float] = field(default_factory=list)
    open_sizes: list[float] = field(default_factory=list)
    copy: dict[int, list[float]] = field(default_factory=lambda: defaultdict(list))
    first: datetime | None = None
    last: datetime | None = None

    @property
    def long_ratio(self) -> float | None:
        n = self.open_long + self.open_short
        return self.open_long / n if n else None

    @property
    def win_rate(self) -> float | None:
        n = self.wins + self.losses
        return self.wins / n if n else None

    @property
    def profit_factor(self) -> float | None:
        return self.gross_win / self.gross_loss if self.gross_loss else None

    @property
    def median_hold(self) -> float | None:
        return median(self.hold_hours) if self.hold_hours else None

    @property
    def weekend_share(self) -> float | None:
        return self.weekend_orders / self.orders if self.orders else None

    @property
    def fav_open_hour(self) -> int | None:
        c = self.hour_long + self.hour_short
        return c.most_common(1)[0][0] if c else None

    @property
    def fav_weekday(self) -> str | None:
        return self.weekday_open.most_common(1)[0][0] if self.weekday_open else None

    def copy_avg(self, h: int) -> float | None:
        r = self.copy.get(h)
        return mean(r) if r else None

    def copy_hit(self, h: int) -> float | None:
        r = self.copy.get(h)
        return sum(x > 0 for x in r) / len(r) if r else None


def holding_times(fills: list[Fill]) -> list[float]:
    """Haltedauer in Stunden: von Position 0 -> offen bis wieder 0 (pro Coin)."""
    eps = 1e-9
    opened: dict[str, datetime] = {}
    out = []
    for f in sorted(fills, key=lambda f: f.time):
        if f.start_position is None:
            continue
        start = f.start_position
        new = start + f.sz if f.side == "B" else start - f.sz
        if abs(start) < eps and abs(new) > eps:
            opened[f.coin] = f.time
        elif abs(start) > eps and (abs(new) < eps or start * new < 0):
            if f.coin in opened:
                out.append((f.time - opened.pop(f.coin)).total_seconds() / 3600)
            if start * new < 0:  # Long -> Short gedreht
                opened[f.coin] = f.time
    return out


def build_profile(addr: str, fills: list[Fill], info: TraderInfo | None, tz: ZoneInfo,
                  prices=None, delay_min: int = 5) -> Profile:
    p = Profile(addr, info.name if info else short_addr(addr), info)
    for o in aggregate(fills):
        p.orders += 1
        loc = o.time.astimezone(tz)
        p.first = min(filter(None, [p.first, o.time]))
        p.last = max(filter(None, [p.last, o.time]))
        p.coins[o.coin] += o.notional
        p.fees += o.fee
        if loc.weekday() >= 5:
            p.weekend_orders += 1
        if o.action in OPENS:
            (p.hour_long if o.action == OPEN_LONG else p.hour_short)[loc.hour] += 1
            p.weekday_open[WEEKDAYS[loc.weekday()]] += 1
            p.session_open[session(o.time)] += 1
            p.open_sizes.append(o.notional)
            if o.action == OPEN_LONG:
                p.open_long += 1
            else:
                p.open_short += 1
            if prices is not None:
                series = prices.series(o.coin)
                for h in HORIZONS:
                    r = forward_return(series, o.time + timedelta(minutes=delay_min), h)
                    if r is not None:
                        p.copy[h].append(r * o.direction)
        elif o.action in CLOSES:
            p.closes += 1
            p.hour_close[loc.hour] += 1
            p.weekday_close[WEEKDAYS[loc.weekday()]] += 1
        if o.closed_pnl:
            p.realized_pnl += o.closed_pnl
            if o.closed_pnl > 0:
                p.wins += 1
                p.gross_win += o.closed_pnl
            else:
                p.losses += 1
                p.gross_loss += -o.closed_pnl
    p.hold_hours = holding_times(fills)
    return p


def sentiment(positions: list[Position]) -> list[dict]:
    """Wie sind die Top-Trader JETZT positioniert? Pro Coin Long- vs. Short-Volumen."""
    agg: dict[str, dict] = {}
    for pos in positions:
        a = agg.setdefault(pos.coin, {"coin": pos.coin, "long_value": 0.0, "short_value": 0.0, "n_long": 0,
                                      "n_short": 0, "lev": [], "upnl": 0.0})
        if pos.is_long:
            a["long_value"] += pos.value
            a["n_long"] += 1
        else:
            a["short_value"] += pos.value
            a["n_short"] += 1
        a["lev"].append(pos.leverage)
        a["upnl"] += pos.unrealized_pnl
    rows = []
    for a in agg.values():
        tot = a["long_value"] + a["short_value"]
        rows.append({**a, "total": tot, "long_share": a["long_value"] / tot if tot else 0.5,
                     "avg_lev": mean(a["lev"]) if a["lev"] else None})
    return sorted(rows, key=lambda r: -r["total"])


def analyze(fills_by_trader: dict[str, list[Fill]], infos: dict[str, TraderInfo], tz: str = "Europe/Berlin",
            prices=None, delay_min: int = 5, positions: list[Position] | None = None) -> dict:
    zone = ZoneInfo(tz)
    profiles = [build_profile(a, f, infos.get(a), zone, prices, delay_min) for a, f in fills_by_trader.items() if f]
    overall = Profile("alle", "Alle Trader")
    for p in profiles:
        for attr in ("hour_long", "hour_short", "hour_close", "weekday_open", "weekday_close", "session_open", "coins"):
            getattr(overall, attr).update(getattr(p, attr))
        for attr in ("orders", "open_long", "open_short", "closes", "weekend_orders", "wins", "losses"):
            setattr(overall, attr, getattr(overall, attr) + getattr(p, attr))
        overall.realized_pnl += p.realized_pnl
        overall.hold_hours += p.hold_hours
        overall.open_sizes += p.open_sizes
        for h, v in p.copy.items():
            overall.copy[h] += v
    profiles.sort(key=lambda p: -((p.info.pnl_month if p.info else 0) or p.realized_pnl))
    return {"profiles": profiles, "overall": overall, "tz": tz, "delay_min": delay_min,
            "sentiment": sentiment(positions or []), "orders": [o for f in fills_by_trader.values() for o in aggregate(f)]}
