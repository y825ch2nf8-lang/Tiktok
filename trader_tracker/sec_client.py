"""Minimaler, höflicher SEC-EDGAR-Client (Rate-Limit + Cache).

Die SEC verlangt einen User-Agent mit Name und E-Mail und max. 10 Anfragen/Sekunde:
https://www.sec.gov/os/accessing-edgar-data
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests


class SecClient:
    def __init__(self, cache_dir: Path, user_agent: str | None = None, min_interval: float = 0.15):
        self.user_agent = user_agent or os.getenv("SEC_USER_AGENT", "")
        if "@" not in self.user_agent:
            raise RuntimeError(
                "Bitte SEC_USER_AGENT setzen, z.B. in .env:\n"
                '  SEC_USER_AGENT="Max Mustermann max@example.com"\n'
                "(Pflicht laut SEC, sonst wird man geblockt.)"
            )
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"})

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / hashlib.sha1(url.encode()).hexdigest()

    def get_text(self, url: str, max_age_s: float | None = None) -> str:
        """max_age_s=None -> unbegrenzt cachen (Filings ändern sich nie)."""
        p = self._cache_path(url)
        if p.exists() and (max_age_s is None or time.time() - p.stat().st_mtime < max_age_s):
            return p.read_text(encoding="utf-8")
        for attempt in range(4):
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            r = self.session.get(url, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            p.write_text(r.text, encoding="utf-8")
            return r.text
        r.raise_for_status()
        return r.text

    def get_json(self, url: str, max_age_s: float | None = None):
        return json.loads(self.get_text(url, max_age_s))

    # --- Komfort ---------------------------------------------------------
    def submissions(self, cik: str) -> dict:
        return self.get_json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", max_age_s=6 * 3600)

    def ticker_to_cik(self, ticker: str) -> str:
        data = self.get_json("https://www.sec.gov/files/company_tickers.json", max_age_s=7 * 86400)
        for row in data.values():
            if row["ticker"].upper() == ticker.upper():
                return str(row["cik_str"])
        raise KeyError(f"Ticker {ticker} nicht bei der SEC gefunden")


def recent_filings(submissions: dict, forms: set[str]) -> list[dict]:
    """Wandelt das spaltenweise 'recent'-Format der SEC in eine Liste von Dicts um."""
    rec = submissions.get("filings", {}).get("recent", {})
    keys = list(rec.keys())
    n = len(rec.get("accessionNumber", []))
    rows = [{k: rec[k][i] for k in keys} for i in range(n)]
    return [r for r in rows if r.get("form") in forms]


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
