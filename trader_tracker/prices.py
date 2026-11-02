"""Tageskurse für die Performance-Analyse (optional). Quelle: Yahoo-Finance-Chart-Endpoint."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

PriceSeries = list[tuple[date, float]]  # sortiert nach Datum


class PriceProvider:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, PriceSeries] = {}

    def get(self, ticker: str) -> PriceSeries:
        if ticker in self._mem:
            return self._mem[ticker]
        if ticker.startswith("CUSIP:"):
            return []
        p = self.cache_dir / f"{ticker.replace('/', '_')}.json"
        if p.exists() and time.time() - p.stat().st_mtime < 86400:
            raw = json.loads(p.read_text())
        else:
            try:
                r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                                 params={"range": "10y", "interval": "1d"},
                                 headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
                r.raise_for_status()
                res = r.json()["chart"]["result"][0]
                closes = res["indicators"]["adjclose"][0]["adjclose"] if "adjclose" in res["indicators"] \
                    else res["indicators"]["quote"][0]["close"]
                raw = [[datetime.fromtimestamp(ts, timezone.utc).date().isoformat(), c]
                       for ts, c in zip(res["timestamp"], closes) if c is not None]
                p.write_text(json.dumps(raw))
            except Exception as e:
                log.warning("Keine Kurse für %s: %s", ticker, e)
                raw = []
        series = [(date.fromisoformat(d), float(c)) for d, c in raw]
        self._mem[ticker] = series
        return series


class StaticPrices:
    """Für Demo & Tests: Kurse aus einem Dict."""
    def __init__(self, data: dict[str, PriceSeries]):
        self.data = data

    def get(self, ticker: str) -> PriceSeries:
        return self.data.get(ticker, [])


def index_on_or_after(series: PriceSeries, d: date) -> int | None:
    lo, hi = 0, len(series)
    while lo < hi:
        mid = (lo + hi) // 2
        if series[mid][0] < d:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(series) else None


def forward_return(series: PriceSeries, start: date, days: int) -> float | None:
    """Rendite vom ersten Handelstag >= start über `days` Handelstage."""
    i = index_on_or_after(series, start)
    if i is None or i + days >= len(series):
        return None
    return series[i + days][1] / series[i][1] - 1
