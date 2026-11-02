"""Datenmodelle: Fill (Teilausführung), Order (eine Entscheidung), Position, TraderInfo."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

OPEN_LONG, CLOSE_LONG = "OPEN_LONG", "CLOSE_LONG"
OPEN_SHORT, CLOSE_SHORT = "OPEN_SHORT", "CLOSE_SHORT"
SPOT_BUY, SPOT_SELL = "SPOT_BUY", "SPOT_SELL"
OPENS = {OPEN_LONG, OPEN_SHORT}
CLOSES = {CLOSE_LONG, CLOSE_SHORT}

ACTION_DE = {OPEN_LONG: "eröffnet LONG", CLOSE_LONG: "schließt LONG", OPEN_SHORT: "eröffnet SHORT",
             CLOSE_SHORT: "schließt SHORT", SPOT_BUY: "kauft (Spot)", SPOT_SELL: "verkauft (Spot)"}

_DIR = {"open long": OPEN_LONG, "close long": CLOSE_LONG, "open short": OPEN_SHORT, "close short": CLOSE_SHORT,
        "buy": SPOT_BUY, "sell": SPOT_SELL, "long > short": OPEN_SHORT, "short > long": OPEN_LONG}


def action_from_dir(direction: str, side: str) -> str:
    d = (direction or "").strip().lower()
    if d in _DIR:
        return _DIR[d]
    if "liquidat" in d:  # Liquidation = erzwungenes Schließen
        return CLOSE_LONG if side == "A" else CLOSE_SHORT
    return SPOT_BUY if side == "B" else SPOT_SELL


def ms_to_dt(ms: int | float) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def fmt_px(v: float) -> str:
    """Preis lesbar: 101.250 $ / 3.041,50 $ / 0,0123 $"""
    s = f"{v:,.0f}" if v >= 1000 else f"{v:,.2f}" if v >= 1 else f"{v:.4g}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " $"


def short_addr(a: str) -> str:
    return f"{a[:6]}…{a[-4:]}" if len(a) > 12 else a


def _f(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


@dataclass
class Fill:
    trader: str          # Wallet-Adresse
    coin: str
    side: str            # "B" = kauft, "A" = verkauft
    px: float
    sz: float
    time: datetime       # UTC
    dir: str = ""        # Original-Text von Hyperliquid, z.B. "Open Long"
    closed_pnl: float = 0.0
    oid: int = 0
    tid: int = 0
    fee: float = 0.0
    start_position: float | None = None

    @property
    def action(self) -> str:
        return action_from_dir(self.dir, self.side)

    @property
    def notional(self) -> float:
        return self.px * self.sz

    @property
    def key(self) -> str:
        return f"{self.trader}|{self.tid}" if self.tid else f"{self.trader}|{self.oid}|{dt_to_ms(self.time)}|{self.px}|{self.sz}"

    @classmethod
    def from_api(cls, trader: str, d: dict) -> "Fill":
        sp = d.get("startPosition")
        return cls(trader=trader.lower(), coin=str(d["coin"]), side=d["side"], px=_f(d["px"]), sz=_f(d["sz"]),
                   time=ms_to_dt(d["time"]), dir=d.get("dir", ""), closed_pnl=_f(d.get("closedPnl")),
                   oid=int(d.get("oid") or 0), tid=int(d.get("tid") or 0), fee=_f(d.get("fee")),
                   start_position=_f(sp, None) if sp is not None else None)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["time"] = dt_to_ms(self.time)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Fill":
        d = dict(d)
        d["time"] = ms_to_dt(d["time"])
        return cls(**d)


@dataclass
class Order:
    """Alle Fills einer Order zusammengefasst = eine Entscheidung des Traders."""
    trader: str
    coin: str
    action: str
    time: datetime
    px: float
    sz: float
    notional: float
    closed_pnl: float
    fee: float
    n_fills: int

    @property
    def direction(self) -> int:
        return {OPEN_LONG: 1, SPOT_BUY: 1, CLOSE_SHORT: 1, OPEN_SHORT: -1, SPOT_SELL: -1, CLOSE_LONG: -1}[self.action]


def aggregate(fills: list[Fill]) -> list[Order]:
    groups: dict[tuple, list[Fill]] = defaultdict(list)
    for f in fills:
        groups[(f.trader, f.coin, f.oid or f.tid, f.action)].append(f)
    out = []
    for (trader, coin, _, action), fs in groups.items():
        sz = sum(f.sz for f in fs)
        notional = sum(f.notional for f in fs)
        out.append(Order(trader, coin, action, min(f.time for f in fs), notional / sz if sz else 0, sz, notional,
                         sum(f.closed_pnl for f in fs), sum(f.fee for f in fs), len(fs)))
    return sorted(out, key=lambda o: o.time)


@dataclass
class Position:
    trader: str
    coin: str
    size: float           # >0 long, <0 short
    entry_px: float
    value: float          # USD (absolut)
    unrealized_pnl: float
    leverage: float

    @property
    def is_long(self) -> bool:
        return self.size > 0


@dataclass
class TraderInfo:
    address: str
    name: str
    account_value: float = 0.0
    pnl_week: float = 0.0
    pnl_month: float = 0.0
    pnl_all: float = 0.0
    roi_week: float = 0.0
    roi_month: float = 0.0
    roi_all: float = 0.0
    vlm_month: float = 0.0
    score: float = 0.0
    weight: float = 1.0

    @property
    def turnover(self) -> float:
        return self.vlm_month / self.account_value if self.account_value else 0.0
