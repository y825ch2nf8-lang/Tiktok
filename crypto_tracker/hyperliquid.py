"""Client für die öffentliche Hyperliquid-API (kein API-Key nötig).
Doku: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
"""
from __future__ import annotations

import json
import logging
import time
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from .models import Fill, Position, TraderInfo, _f, dt_to_ms, ms_to_dt, short_addr

log = logging.getLogger(__name__)

INFO_URL = "https://api.hyperliquid.xyz/info"
LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
MAX_FILLS_PER_CALL = 2000


class HyperliquidClient:
    def __init__(self, cache_dir: Path, min_interval: float = 0.35, session: requests.Session | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self._last = 0.0
        self.s = session or requests.Session()

    def _throttle(self):
        wait = self.min_interval - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def info(self, payload: dict):
        for attempt in range(5):
            self._throttle()
            r = self.s.post(INFO_URL, json=payload, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:  # Rate-Limit -> warten
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()

    # ---- Leaderboard ----------------------------------------------------
    def leaderboard(self, max_age_s: float = 3600) -> list[dict]:
        p = self.cache_dir / "leaderboard.json"
        if p.exists() and time.time() - p.stat().st_mtime < max_age_s:
            return json.loads(p.read_text())
        self._throttle()
        r = self.s.get(LEADERBOARD_URL, timeout=60)
        r.raise_for_status()
        rows = r.json().get("leaderboardRows", [])
        p.write_text(json.dumps(rows))
        return rows

    # ---- Trades ---------------------------------------------------------
    def fills(self, address: str, start: datetime, end: datetime | None = None, max_pages: int = 10) -> list[Fill]:
        """Alle Fills im Zeitraum. Hyperliquid liefert max. 2000 pro Anfrage (und nur die letzten 10.000)."""
        end_ms = dt_to_ms(end or datetime.now(timezone.utc))
        cur = dt_to_ms(start)
        out: dict[str, Fill] = {}
        for _ in range(max_pages):
            batch = self.info({"type": "userFillsByTime", "user": address, "startTime": cur, "endTime": end_ms,
                               "aggregateByTime": False}) or []
            for d in batch:
                f = Fill.from_api(address, d)
                out[f.key] = f
            if len(batch) < MAX_FILLS_PER_CALL:
                break
            cur = max(d["time"] for d in batch) + 1
        return sorted(out.values(), key=lambda f: f.time)

    def positions(self, address: str) -> tuple[float, list[Position]]:
        st = self.info({"type": "clearinghouseState", "user": address}) or {}
        acct = _f(st.get("marginSummary", {}).get("accountValue"))
        out = []
        for ap in st.get("assetPositions", []):
            p = ap.get("position", ap)
            size = _f(p.get("szi"))
            if size == 0:
                continue
            lev = p.get("leverage") or {}
            out.append(Position(address.lower(), p["coin"], size, _f(p.get("entryPx")), abs(_f(p.get("positionValue"))),
                                _f(p.get("unrealizedPnl")), _f(lev.get("value") if isinstance(lev, dict) else lev, 1)))
        return acct, out

    def mids(self) -> dict[str, float]:
        return {k: _f(v) for k, v in (self.info({"type": "allMids"}) or {}).items()}

    def candles(self, coin: str, start: datetime, end: datetime, interval: str = "1h") -> list[tuple[datetime, float]]:
        """Stündliche Kurse (Eröffnungskurs jeder Kerze), mit Cache. Max. 5000 Kerzen pro Anfrage."""
        p = self.cache_dir / f"candles_{coin.replace('/', '_').replace('@', 'at')}_{interval}.json"
        data: dict[datetime, float] = {}
        cur, cache_start = start, dt_to_ms(start)
        if p.exists():
            c = json.loads(p.read_text())
            if c["start"] <= dt_to_ms(start):
                cache_start = c["start"]
                data = {ms_to_dt(t): px for t, px in c["rows"]}
                if data:
                    cur = max(data) + timedelta(hours=1)
        changed = False
        while cur < end - timedelta(hours=1):
            chunk_end = min(end, cur + timedelta(hours=4900))
            rows = self.info({"type": "candleSnapshot", "req": {"coin": coin, "interval": interval,
                                                                 "startTime": dt_to_ms(cur), "endTime": dt_to_ms(chunk_end)}}) or []
            for r in rows:
                data[ms_to_dt(r["t"])] = _f(r["o"])
            changed = True
            cur = chunk_end
        if changed:
            p.write_text(json.dumps({"start": cache_start, "rows": [[dt_to_ms(t), px] for t, px in sorted(data.items())]}))
        return sorted(data.items())


class CandleCache:
    """Kurse für die Kopier-Analyse; lädt bei Bedarf über den Client nach."""
    def __init__(self, client: HyperliquidClient | None, start: datetime, end: datetime, static: dict | None = None):
        self.client, self.start, self.end = client, start, end
        self.data: dict[str, list[tuple[datetime, float]]] = dict(static or {})

    def series(self, coin: str) -> list[tuple[datetime, float]]:
        if coin not in self.data:
            try:
                self.data[coin] = self.client.candles(coin, self.start, self.end) if self.client else []
            except Exception as e:
                log.warning("Keine Kurse für %s: %s", coin, e)
                self.data[coin] = []
        return self.data[coin]


def forward_return(series: list[tuple[datetime, float]], t0: datetime, hours: int) -> float | None:
    """Rendite vom ersten Kurs >= t0 bis `hours` Stunden später."""
    if not series:
        return None
    times = [t for t, _ in series]
    i = bisect_left(times, t0)
    if i >= len(series) or series[i][0] - t0 > timedelta(hours=2):
        return None
    j = bisect_left(times, series[i][0] + timedelta(hours=hours))
    if j >= len(series) or series[j][0] - series[i][0] > timedelta(hours=hours + 2):
        return None
    return series[j][1] / series[i][1] - 1


# ---- Leaderboard auswerten -----------------------------------------------
def parse_leaderboard(rows: list[dict]) -> list[TraderInfo]:
    out = []
    for r in rows:
        addr = (r.get("ethAddress") or "").lower()
        if not addr:
            continue
        w = {k: v for k, v in r.get("windowPerformances", [])}
        g = lambda win, key: _f((w.get(win) or {}).get(key))  # noqa: E731
        out.append(TraderInfo(address=addr, name=r.get("displayName") or short_addr(addr),
                              account_value=_f(r.get("accountValue")),
                              pnl_week=g("week", "pnl"), pnl_month=g("month", "pnl"), pnl_all=g("allTime", "pnl"),
                              roi_week=g("week", "roi"), roi_month=g("month", "roi"), roi_all=g("allTime", "roi"),
                              vlm_month=g("month", "vlm")))
    return out


def _pct_rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for r, i in enumerate(order):
        ranks[i] = r / max(1, len(values) - 1)
    return ranks


def rank_traders(infos: list[TraderInfo], top: int = 20, min_account: float = 100_000,
                 max_turnover: float = 150) -> list[TraderInfo]:
    """Die 'besten' Trader: dauerhaft profitabel (Woche, Monat, Allzeit im Plus), genug Kapital,
    und KEINE Market-Maker/HFT-Bots (extrem hoher Umsatz im Verhältnis zum Konto)."""
    pool = [t for t in infos if t.account_value >= min_account and t.pnl_all > 0 and t.pnl_month > 0
            and t.pnl_week >= 0 and t.vlm_month > 0 and t.turnover <= max_turnover]
    if not pool:
        return []
    r_month = _pct_rank([t.roi_month for t in pool])
    r_all = _pct_rank([t.pnl_all for t in pool])
    r_week = _pct_rank([t.roi_week for t in pool])
    for t, a, b, c in zip(pool, r_month, r_all, r_week):
        t.score = round(0.45 * a + 0.35 * b + 0.20 * c, 4)
    return sorted(pool, key=lambda t: -t.score)[:top]
