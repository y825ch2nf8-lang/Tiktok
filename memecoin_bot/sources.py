"""Datenquellen (alle öffentlich, ohne API-Key): DexScreener, GeckoTerminal, RugCheck, GoPlus, Honeypot.is.

Jede Quelle hängt an einem gemeinsamen `Http`-Objekt mit Rate-Limit pro Host, Retries und kurzem Cache.
Für Tests/Demo kann statt `Http` jedes Objekt mit `get_json(url)` übergeben werden.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

# Mindestabstand zwischen zwei Anfragen pro Host (Sekunden). GeckoTerminal erlaubt ca. 30 Anfragen/Minute –
# bei 429 (zu viele Anfragen) wird der Abstand automatisch vergrößert und danach langsam wieder verkleinert.
HOST_INTERVAL = {
    "api.geckoterminal.com": 2.1,
    "api.dexscreener.com": 0.25,
    "api.rugcheck.xyz": 0.4,
    "api.gopluslabs.io": 0.5,
    "api.honeypot.is": 0.4,
}
MAX_INTERVAL = 15.0

GT_NETWORK = {"solana": "solana", "bsc": "bsc", "ethereum": "eth", "base": "base"}
EVM_CHAIN_ID = {"bsc": 56, "ethereum": 1, "base": 8453}
# Wrapped-Native-Token je Chain (für Preise in $)
NATIVE_TOKEN = {
    "solana": "So11111111111111111111111111111111111111112",
    "bsc": "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",
    "ethereum": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    "base": "0x4200000000000000000000000000000000000006",
}
EURC_SOLANA = "HzwqbKZw8HxMN6bF2yFZNrht3c2iXXzpKcFu7uBEDKtr"  # Euro-Stablecoin -> EUR/USD-Kurs


class Http:
    """requests mit Rate-Limit pro Host (Hosts laufen parallel, Anfragen an denselben Host nacheinander)."""

    def __init__(self, session: requests.Session | None = None, cache_ttl: float = 300,
                 sleep: Callable[[float], None] = time.sleep, timeout: float = 30, max_attempts: int = 8):
        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "memecoin-bot/1.0"})
        self.cache_ttl, self.sleep, self.timeout, self.max_attempts = cache_ttl, sleep, timeout, max_attempts
        self.interval = dict(HOST_INTERVAL)
        self._last: dict[str, float] = {}
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()
        self._host_locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _host_lock(self, host: str) -> threading.Lock:
        with self._guard:
            return self._host_locks.setdefault(host, threading.Lock())

    def _throttle(self, host: str):
        wait = self.interval.get(host, 0.2) - (time.monotonic() - self._last.get(host, 0.0))
        if wait > 0:
            self.sleep(wait)
        self._last[host] = time.monotonic()

    def get_json(self, url: str, ttl: float | None = None) -> Any:
        ttl = self.cache_ttl if ttl is None else ttl
        with self._cache_lock:
            hit = self._cache.get(url)
            if hit and time.monotonic() - hit[0] < ttl:
                return hit[1]
        host = urlparse(url).hostname or ""
        base = HOST_INTERVAL.get(host, 0.2)
        with self._host_lock(host):
            for attempt in range(self.max_attempts):
                self._throttle(host)
                try:
                    r = self.session.get(url, timeout=self.timeout)
                except requests.RequestException as e:
                    log.warning("Netzwerkfehler %s: %s", host, e)
                    self.sleep(2 + 2 * attempt)
                    continue
                if r.status_code == 429:
                    self.interval[host] = min(max(self.interval.get(host, base), 1.0) * 1.6, MAX_INTERVAL)
                    log.info("Rate-Limit bei %s – Abstand jetzt %.1f s", host, self.interval[host])
                    continue
                if r.status_code in (400, 404, 422):
                    return None
                if r.status_code >= 500:
                    self.sleep(2 + 2 * attempt)
                    continue
                self.interval[host] = max(base, self.interval.get(host, base) * 0.9)
                try:
                    data = r.json()
                except ValueError:
                    return None
                with self._cache_lock:
                    self._cache[url] = (time.monotonic(), data)
                return data
        log.warning("Aufgegeben nach %d Versuchen: %s", self.max_attempts, url)
        return None


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class DexScreener:
    BASE = "https://api.dexscreener.com"

    def __init__(self, http):
        self.http = http

    def _list(self, path: str) -> list[dict]:
        d = self.http.get_json(f"{self.BASE}/{path}", ttl=120)
        return d if isinstance(d, list) else []

    def boosts_top(self):
        return self._list("token-boosts/top/v1")

    def boosts_latest(self):
        return self._list("token-boosts/latest/v1")

    def profiles_latest(self):
        return self._list("token-profiles/latest/v1")

    def takeovers_latest(self):
        return self._list("community-takeovers/latest/v1")

    def tokens(self, chain: str, addresses: list[str]) -> list[dict]:
        """Alle Pairs zu bis zu beliebig vielen Token-Adressen einer Chain (intern in 30er-Blöcken)."""
        out: list[dict] = []
        for chunk in _chunks(list(addresses), 30):
            d = self.http.get_json(f"{self.BASE}/tokens/v1/{chain}/{','.join(chunk)}", ttl=60)
            if isinstance(d, list):
                out.extend(d)
        return out

    def price(self, chain: str, address: str) -> float | None:
        """Preis eines Tokens aus seinem liquidesten Pool (für SOL/BNB/ETH und EURC)."""
        pairs = [p for p in self.tokens(chain, [address])
                 if str((p.get("baseToken") or {}).get("address", "")).lower() == address.lower()]
        if not pairs:
            return None
        best = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
        try:
            return float(best.get("priceUsd"))
        except (TypeError, ValueError):
            return None

    def search_token(self, address: str) -> list[dict]:
        """Pairs zu einer Adresse über alle Chains (für /check ohne Chain-Angabe)."""
        d = self.http.get_json(f"{self.BASE}/latest/dex/tokens/{address}", ttl=60)
        if not isinstance(d, dict):
            return []
        return d.get("pairs") or []


class GeckoTerminal:
    BASE = "https://api.geckoterminal.com/api/v2"

    def __init__(self, http):
        self.http = http

    def _data(self, path: str, ttl: float | None = None):
        d = self.http.get_json(f"{self.BASE}/{path}", ttl=ttl)
        return d.get("data") if isinstance(d, dict) else None

    def trending(self, chain: str, duration: str = "24h", page: int = 1) -> list[dict]:
        return self._data(f"networks/{GT_NETWORK[chain]}/trending_pools?page={page}&duration={duration}", ttl=120) or []

    def top_volume(self, chain: str) -> list[dict]:
        return self._data(f"networks/{GT_NETWORK[chain]}/pools?page=1&sort=h24_volume_usd_desc", ttl=120) or []

    def token_info(self, chain: str, address: str) -> dict | None:
        d = self._data(f"networks/{GT_NETWORK[chain]}/tokens/{address}/info", ttl=600)
        return d.get("attributes") if d else None

    def pools(self, chain: str, pool_addresses: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for chunk in _chunks(list(pool_addresses), 30):
            for p in self._data(f"networks/{GT_NETWORK[chain]}/pools/multi/{','.join(chunk)}", ttl=60) or []:
                a = p.get("attributes") or {}
                out[str(a.get("address", "")).lower()] = a
        return out

    def ohlcv_day(self, chain: str, pool: str, limit: int = 30) -> list[list[float]]:
        d = self.http.get_json(f"{self.BASE}/networks/{GT_NETWORK[chain]}/pools/{pool}/ohlcv/day?limit={limit}", ttl=600)
        try:
            return sorted(d["data"]["attributes"]["ohlcv_list"], key=lambda x: x[0])
        except (TypeError, KeyError):
            return []

    def trades(self, chain: str, pool: str, min_usd: float = 500) -> list[dict]:
        d = self._data(f"networks/{GT_NETWORK[chain]}/pools/{pool}/trades?trade_volume_in_usd_greater_than={min_usd:g}", ttl=60)
        return [t.get("attributes") or {} for t in d or []]

    def prices(self, chain: str, addresses: list[str]) -> dict[str, float]:
        d = self._data(f"simple/networks/{GT_NETWORK[chain]}/token_price/{','.join(addresses)}", ttl=600)
        try:
            raw = d["attributes"]["token_prices"]
        except (TypeError, KeyError):
            return {}
        return {k.lower(): float(v) for k, v in raw.items() if v is not None}


class RugCheck:
    BASE = "https://api.rugcheck.xyz/v1"

    def __init__(self, http):
        self.http = http

    def report(self, mint: str) -> dict | None:
        d = self.http.get_json(f"{self.BASE}/tokens/{mint}/report", ttl=600)
        return d if isinstance(d, dict) else None


class GoPlus:
    BASE = "https://api.gopluslabs.io/api/v1"

    def __init__(self, http):
        self.http = http

    def evm(self, chain: str, addresses: list[str]) -> dict[str, dict]:
        cid = EVM_CHAIN_ID[chain]
        out: dict[str, dict] = {}
        for chunk in _chunks(list(addresses), 20):
            d = self.http.get_json(f"{self.BASE}/token_security/{cid}?contract_addresses={','.join(chunk)}", ttl=600)
            for k, v in ((d or {}).get("result") or {}).items():
                out[k.lower()] = v
        return out

    def solana(self, mint: str) -> dict | None:
        d = self.http.get_json(f"{self.BASE}/solana/token_security?contract_addresses={mint}", ttl=600)
        res = (d or {}).get("result") or {}
        return res.get(mint) or (next(iter(res.values()), None) if res else None)


class Honeypot:
    BASE = "https://api.honeypot.is/v2"

    def __init__(self, http):
        self.http = http

    def check(self, chain: str, address: str) -> dict | None:
        d = self.http.get_json(f"{self.BASE}/IsHoneypot?address={address}&chainID={EVM_CHAIN_ID[chain]}", ttl=600)
        return d if isinstance(d, dict) else None


class Sources:
    """Bündelt alle Quellen auf einem gemeinsamen Http-Objekt."""

    def __init__(self, http=None):
        self.http = http or Http()
        self.dex = DexScreener(self.http)
        self.gt = GeckoTerminal(self.http)
        self.rugcheck = RugCheck(self.http)
        self.goplus = GoPlus(self.http)
        self.honeypot = Honeypot(self.http)
