"""FIKTIVE Demo-Daten: erfundene Trader-Wallets, erfundene Coins, simulierte Kurse.
Damit läuft alles offline. Nichts davon darf als echte Info verwendet werden."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from .models import Fill, Position, TraderInfo

COINS = {"NOVA": 64000.0, "PIXL": 3100.0, "ZETA": 150.0, "FLUX": 25.0}

# Name, bevorzugte UTC-Stunden, Long-Neigung, Haltedauer (h min/max), Können (0..1), Wochenende ok, Ø Größe $
PERSONAS = [
    ("DemoWal Nachtfalke", range(1, 6), 0.70, (6, 30), 0.30, True, 400_000),
    ("DemoWal Opening-Bell", range(13, 16), 0.50, (1, 6), 0.28, False, 900_000),
    ("DemoWal Swing", range(7, 11), 0.80, (24, 120), 0.25, False, 1_500_000),
    ("DemoWal Scalper", range(12, 21), 0.55, (0.2, 1.5), 0.15, False, 250_000),
    ("DemoWal Wochenende", range(17, 23), 0.60, (3, 18), 0.10, True, 120_000),
    ("DemoWal Shortkönig", range(15, 20), 0.25, (2, 24), 0.30, False, 700_000),
]


def _addr(rng: random.Random) -> str:
    return "0xdemo" + "".join(rng.choice("0123456789abcdef") for _ in range(36))


def make_demo(seed: int = 11, days: int = 120, end: datetime = datetime(2026, 10, 31, 22, tzinfo=timezone.utc)):
    rng = random.Random(seed)
    start = end - timedelta(days=days)
    hours = int((end - start).total_seconds() // 3600) + 1
    prices: dict[str, list[tuple[datetime, float]]] = {}
    for coin, base in COINS.items():
        px, series = base, []
        vol = 0.006 if coin == "NOVA" else 0.009
        for i in range(hours):
            px *= math.exp(rng.gauss(0, vol))
            series.append((start + timedelta(hours=i), round(px, 6)))
        prices[coin] = series

    def price_at(coin: str, t: datetime) -> float:
        i = min(hours - 1, max(0, int((t - start).total_seconds() // 3600)))
        return prices[coin][i][1]

    fills_by: dict[str, list[Fill]] = {}
    infos: dict[str, TraderInfo] = {}
    positions: list[Position] = []
    oid = 1000
    for name, pref_hours, long_bias, (hmin, hmax), skill, weekend_ok, avg_size in PERSONAS:
        addr = _addr(rng)
        fills: list[Fill] = []
        busy: dict[str, datetime] = {}
        n_eps = int(days * (3 if hmax < 2 else 1.2 if hmax < 30 else 0.4))
        opens = []
        for _ in range(n_eps):
            day = start + timedelta(days=rng.randrange(days))
            if day.weekday() >= 5 and not weekend_ok and rng.random() < 0.85:
                continue
            hour = rng.choice(list(pref_hours)) if rng.random() < 0.75 else rng.randrange(24)
            opens.append(day.replace(hour=hour, minute=rng.randrange(60), second=rng.randrange(60)))
        for t_open in sorted(opens):
            coin = rng.choices(list(COINS), weights=[5, 3, 2, 1])[0]
            if busy.get(coin, start) > t_open:
                continue
            hold = timedelta(hours=rng.uniform(hmin, hmax))
            t_close = t_open + hold
            p0 = price_at(coin, t_open)
            fut = price_at(coin, t_close) / p0 - 1
            d = (1 if fut > 0 else -1) if rng.random() < skill else (1 if rng.random() < long_bias else -1)
            notional = avg_size * rng.lognormvariate(0, 0.5)
            size = notional / p0
            oid += 1
            pos, parts = 0.0, rng.choice([1, 1, 2, 3])
            for k in range(parts):  # Einstieg in 1-3 Teilen
                part = size / parts
                fills.append(Fill(addr, coin, "B" if d > 0 else "A", p0 * (1 + rng.gauss(0, 0.0003)), part,
                                  t_open + timedelta(seconds=k * 2), "Open Long" if d > 0 else "Open Short",
                                  0.0, oid, oid * 10 + k, notional / parts * 0.00035, pos))
                pos += d * part
            busy[coin] = t_close
            if t_close > end:  # noch offen -> aktuelle Position
                p1 = price_at(coin, end)
                positions.append(Position(addr, coin, pos, p0, abs(pos) * p1, d * (p1 - p0) * abs(pos), rng.choice([3, 5, 10, 20])))
                continue
            oid += 1
            p1 = price_at(coin, t_close) * (1 + rng.gauss(0, 0.0003))
            fills.append(Fill(addr, coin, "A" if d > 0 else "B", p1, size, t_close, "Close Long" if d > 0 else "Close Short",
                              d * (p1 - p0) * size, oid, oid * 10, size * p1 * 0.00035, pos))
        for coin in rng.sample(list(COINS), rng.randint(1, 3)):  # aktuell offene Positionen
            if any(x.trader == addr and x.coin == coin for x in positions):
                continue
            p1 = price_at(coin, end)
            d = 1 if rng.random() < long_bias + (0.2 if coin == "NOVA" else 0) else -1
            sz = avg_size * rng.lognormvariate(0, 0.5) / p1
            entry = p1 * (1 - d * rng.uniform(-0.03, 0.05))
            positions.append(Position(addr, coin, d * sz, entry, sz * p1, d * (p1 - entry) * sz, rng.choice([2, 3, 5, 10, 20])))
        fills.sort(key=lambda f: f.time)
        fills_by[addr] = fills
        month = sum(f.closed_pnl for f in fills if f.time > end - timedelta(days=30))
        acct = avg_size * rng.uniform(2, 6)
        infos[addr] = TraderInfo(addr, name, acct, pnl_month=month, pnl_all=sum(f.closed_pnl for f in fills),
                                 roi_month=month / acct, vlm_month=sum(f.notional for f in fills if f.time > end - timedelta(days=30)))
    return fills_by, infos, positions, prices
