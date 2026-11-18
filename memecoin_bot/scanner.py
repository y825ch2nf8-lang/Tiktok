"""Scan-Ablauf: Kandidaten sammeln -> mit Pair-Daten anreichern -> filtern -> Tiefenprüfung -> bewerten."""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

from .analysis import (Analysis, Candidate, Deep, analyze, candidates_from_pairs, is_meme_candidate, key_of,
                       prefilter, prescore)
from .sources import EURC_SOLANA, NATIVE_TOKEN, Sources

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
CHAINS = ["solana", "bsc", "ethereum", "base"]
CHAIN_ALIASES = {"sol": "solana", "solana": "solana", "bsc": "bsc", "bnb": "bsc", "bep20": "bsc", "eth": "ethereum",
                 "ethereum": "ethereum", "erc20": "ethereum", "base": "base"}


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else ROOT / "config.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


@dataclass
class Market:
    native_usd: dict[str, float] = field(default_factory=dict)
    eur_usd: float = 1.15
    eur_usd_live: bool = False


@dataclass
class ScanResult:
    started: datetime
    finished: datetime
    chains: list[str]
    n_raw: int
    n_priced: int
    n_meme: int
    n_filtered: int
    analyses: list[Analysis]
    market: Market
    biggest_meme: Candidate | None

    @property
    def ranked(self) -> list[Analysis]:
        return sorted([a for a in self.analyses if not a.excluded], key=lambda a: -a.score)

    @property
    def top(self) -> list[Analysis]:
        return self.ranked[:3]

    @property
    def excluded(self) -> list[Analysis]:
        return [a for a in self.analyses if a.excluded]

    def favorite(self, min_score: float) -> Analysis | None:
        r = self.ranked
        return r[0] if r and r[0].score >= min_score else None


class Scanner:
    def __init__(self, cfg: dict | None = None, sources: Sources | None = None, now: Callable[[], float] = time.time):
        self.cfg = cfg or load_config()
        self.src = sources or Sources()
        self.now = now
        self.skip = {s.upper() for s in self.cfg.get("skip_symbols") or []}

    # ------------------------------------------------------------------ Markt
    def market(self, chains: list[str]) -> Market:
        m = Market(eur_usd=float(self.cfg["costs"].get("eur_usd_fallback", 1.15)))
        for ch in dict.fromkeys(["solana", *chains]):
            px = self.src.dex.price(ch, NATIVE_TOKEN[ch])
            if px:
                m.native_usd[ch] = px
        eur = self.src.dex.price("solana", EURC_SOLANA)
        if eur and 0.8 < eur < 1.6:
            m.eur_usd, m.eur_usd_live = eur, True
        return m

    # ------------------------------------------------------------------ Sammeln
    def collect(self, chains: list[str]) -> dict[str, set[str]]:
        found: dict[str, set[str]] = {}

        def add(chain, addr, src):
            if chain in chains and addr:
                found.setdefault(key_of(chain, addr), set()).add(src)

        dex = self.src.dex
        for name, fn in (("Boost", dex.boosts_top), ("Boost", dex.boosts_latest), ("Profil", dex.profiles_latest),
                         ("Community-Takeover", dex.takeovers_latest)):
            for e in fn():
                add(e.get("chainId"), e.get("tokenAddress"), name)
        for ch in chains:
            for dur, page in self.cfg.get("trending_lists") or [["24h", 1]]:
                for p in self.src.gt.trending(ch, dur, page):
                    add(ch, _gt_base_address(p), f"Trending {dur}")
            if self.cfg.get("include_top_volume"):
                for p in self.src.gt.top_volume(ch):
                    add(ch, _gt_base_address(p), "Top-Volumen")
        return found

    # ------------------------------------------------------------------ Tiefenprüfung
    def deep(self, cands: list[Candidate]) -> dict[str, Deep]:
        """Lädt Kursverlauf, große Trades und Sicherheitsdaten. Verschiedene Hosts laufen parallel,
        Anfragen an denselben Host nacheinander (Rate-Limit)."""
        out = {c.key: Deep() for c in cands}
        by_chain: dict[str, list[Candidate]] = {}
        for c in cands:
            by_chain.setdefault(c.chain, []).append(c)
        min_usd = self.cfg.get("trade_min_usd", 500)

        def market_data(c: Candidate):
            d = out[c.key]
            if c.pair:
                d.ohlcv = self.src.gt.ohlcv_day(c.chain, c.pair)
                d.trades = self.src.gt.trades(c.chain, c.pair, min_usd)

        def security(c: Candidate, gp_batch: dict):
            d = out[c.key]
            if c.chain == "solana":
                d.rugcheck = self.src.rugcheck.report(c.address)
                d.goplus = self.src.goplus.solana(c.address)
            else:
                d.goplus = gp_batch.get(c.address.lower())
                d.honeypot = self.src.honeypot.check(c.chain, c.address)

        def chain_pools(ch: str, cs: list[Candidate]):
            pools = self.src.gt.pools(ch, [c.pair for c in cs if c.pair])
            for c in cs:
                out[c.key].pool = pools.get(c.pair.lower())

        gp = {ch: self.src.goplus.evm(ch, [c.address for c in cs]) for ch, cs in by_chain.items() if ch != "solana"}
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = [ex.submit(chain_pools, ch, cs) for ch, cs in by_chain.items()]
            futs += [ex.submit(security, c, gp.get(c.chain, {})) for c in cands]
            futs += [ex.submit(market_data, c) for c in cands]
            for f in futs:
                try:
                    f.result()
                except Exception:
                    log.exception("Tiefenprüfung teilweise fehlgeschlagen")
        return out

    def _select(self, passed: list[Candidate]) -> list[Candidate]:
        n, per_chain = self.cfg.get("deep_check_count", 12), self.cfg.get("max_per_chain", 6)
        chosen, count = [], {}
        for c in sorted(passed, key=prescore, reverse=True):
            if count.get(c.chain, 0) >= per_chain:
                continue
            chosen.append(c)
            count[c.chain] = count.get(c.chain, 0) + 1
            if len(chosen) >= n:
                break
        return chosen

    # ------------------------------------------------------------------ Öffentliche Befehle
    def scan(self, chains: list[str] | None = None, progress: Callable[[str], None] | None = None) -> ScanResult:
        chains = chains or self.cfg.get("chains") or CHAINS
        say = progress or (lambda s: None)
        started = datetime.now(timezone.utc)
        found = self.collect(chains)
        say(f"{len(found)} Tokens gefunden – lade Marktdaten …")
        pairs = []
        for ch in chains:
            pairs += self.src.dex.tokens(ch, [k.split(":", 1)[1] for k in found if k.startswith(ch + ":")])
        cands = candidates_from_pairs(pairs, set(found), self.now() * 1000, found)
        memes = [c for c in cands.values() if is_meme_candidate(c, self.skip)]
        passed = [c for c in memes if prefilter(c, self.cfg["filters"]) is None]
        chosen = self._select(passed)
        say(f"{len(passed)} im Filter – Tiefenprüfung von {len(chosen)} Kandidaten …")
        deep = self.deep(chosen)
        analyses = [analyze(c, deep[c.key], self.cfg) for c in chosen]
        market = self.market(chains)
        biggest = max(memes, key=lambda c: c.mcap, default=None)
        return ScanResult(started, datetime.now(timezone.utc), chains, len(found), len(cands), len(memes),
                          len(passed), analyses, market, biggest)

    def check(self, address: str, chain: str | None = None) -> tuple[Analysis, Market] | None:
        address = address.strip()
        chains = [chain] if chain else (["solana"] if not address.lower().startswith("0x") else ["bsc", "ethereum", "base"])
        pairs = []
        if chain:
            pairs = self.src.dex.tokens(chain, [address])
        else:
            pairs = [p for p in self.src.dex.search_token(address) if p.get("chainId") in chains]
        wanted = {key_of(ch, address) for ch in chains}
        cands = candidates_from_pairs(pairs, wanted, self.now() * 1000)
        if not cands:
            return None
        c = max(cands.values(), key=lambda x: x.liquidity)
        d = self.deep([c])[c.key]
        return analyze(c, d, self.cfg), self.market([c.chain])


def _gt_base_address(pool: dict) -> str | None:
    try:
        return pool["relationships"]["base_token"]["data"]["id"].split("_", 1)[1]
    except (KeyError, TypeError, IndexError, AttributeError):
        return None
