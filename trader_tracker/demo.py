"""Erzeugt FIKTIVE Demo-Daten (Trader, Aktien, Kurse), damit alles ohne Internet testbar ist.
Alle Namen und Kürzel sind erfunden."""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from .models import BUY, SELL, Trade

TICKERS = ["NOVA", "ORBT", "KRYP", "LUMN", "VELO", "ZENT", "AURA", "QBIT"]

# (Name, Gruppe, Lieblings-Kauftage, Lieblings-Verkaufstage, Trades/Jahr, Tickers)
PERSONAS = [
    ("Demo-Fonds Alpha", "Superinvestor", [0, 1], [3, 4], 14, ["NOVA", "ORBT", "AURA"]),
    ("Demo-Fonds Beta", "Superinvestor", [1, 2], [4], 10, ["NOVA", "QBIT", "ZENT"]),
    ("Anna Demo (CEO, NOVA)", "Insider", [1], [3], 6, ["NOVA"]),
    ("Ben Demo (CFO, NOVA)", "Insider", [1, 2], [3], 5, ["NOVA"]),
    ("Clara Demo (Director, KRYP)", "Insider", [0], [4], 5, ["KRYP"]),
    ("Abgeordneter Demo X", "Politiker", [2, 3], [0, 4], 12, ["LUMN", "VELO", "ORBT"]),
]


def _weekday_near(rng: random.Random, d: date, days: list[int]) -> date:
    target = rng.choice(days)
    return d + timedelta(days=(target - d.weekday()) % 7)


def make_demo(seed: int = 7, start: date = date(2023, 1, 2), end: date = date(2026, 9, 30)):
    rng = random.Random(seed)
    # Kurse: Random Walk; nach Insider-Käufen leicht positiver Drift, damit die Analyse etwas zu zeigen hat
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    bdays = [d for d in days if d.weekday() < 5]
    prices = {tk: [] for tk in TICKERS + ["SPY"]}
    level = {tk: rng.uniform(20, 300) for tk in prices}
    trades: list[Trade] = []

    for name, group, bdays_pref, sdays_pref, per_year, tks in PERSONAS:
        n = int(per_year * (end - start).days / 365)
        for _ in range(n):
            d = _weekday_near(rng, start + timedelta(days=rng.randrange((end - start).days - 7)),
                              bdays_pref if rng.random() < 0.62 else sdays_pref)
            side = BUY if (d.weekday() in bdays_pref) == (rng.random() < 0.85) else SELL
            if group == "Insider" and d.day > 20 and rng.random() < 0.5:
                d = d.replace(day=rng.randint(1, 10))  # Insider kaufen oft nach Quartalszahlen am Monatsanfang
            if d > end:
                continue
            tk = rng.choice(tks)
            shares = rng.choice([500, 1000, 2500, 5000, 20000]) * (10 if group == "Superinvestor" else 1)
            delay = rng.choice([1, 2, 2, 2, 3]) if group != "Politiker" else rng.randint(10, 44)
            filed = datetime.combine(d + timedelta(days=delay), time(rng.choice([16, 16, 17, 17, 18, 21]), rng.randrange(60)))
            trades.append(Trade(trader=name, ticker=tk, side=side, trade_date=d, source="demo", shares=shares,
                                filed_at=filed, issuer=f"{tk} Demo Corp", group=group, note="fiktiv"))

    boosts = {}
    for t in trades:
        if t.group == "Insider" and t.side == BUY:
            boosts.setdefault(t.ticker, set()).add(t.available_date)
    for tk in prices:
        drift_until = None
        for d in bdays:
            if d in boosts.get(tk, ()):
                drift_until = d + timedelta(days=40)
            mu = 0.0025 if drift_until and d <= drift_until else 0.0003
            level[tk] *= 1 + rng.gauss(mu, 0.018)
            prices[tk].append((d, round(level[tk], 2)))

    px = {tk: dict(s) for tk, s in prices.items()}
    for t in trades:
        d = t.trade_date
        while d not in px[t.ticker] and d > start:
            d -= timedelta(days=1)
        t.price = px[t.ticker].get(d, level[t.ticker])
        t.value = t.price * t.shares
    return trades, prices
