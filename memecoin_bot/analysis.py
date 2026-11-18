"""Reine Analyse-Funktionen (ohne Netzwerk): Kennzahlen, Sicherheits-Checks, Red Flags und Score.

Alle Prozentwerte sind 0–100, Beträge in US-Dollar.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

DEAD_ADDRESSES = {"0x000000000000000000000000000000000000dead", "0x0000000000000000000000000000000000000000",
                  "0xdead000000000000000042069420694206942069"}


def key_of(chain: str, address: str) -> str:
    return f"{chain}:{address if chain == 'solana' else address.lower()}"


def fnum(x: Any, default: float | None = None) -> float | None:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def de(x: float, digits: int = 1) -> str:
    """Deutsche Zahl: 6,0 statt 6.0"""
    return f"{x:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class Candidate:
    chain: str
    address: str
    symbol: str
    name: str
    pair: str
    dex: str
    quote: str
    price: float
    mcap: float
    fdv: float
    liquidity: float          # Summe über alle Pools
    liq_main: float           # Haupt-Pool
    vol24: float
    vol6: float
    vol1: float
    pc1: float | None
    pc6: float | None
    pc24: float | None
    buys24: int
    sells24: int
    age_days: float | None
    pair_addresses: list[str] = field(default_factory=list)
    sources: set[str] = field(default_factory=set)
    websites: list[str] = field(default_factory=list)
    socials: list[str] = field(default_factory=list)
    boosts: int = 0

    @property
    def key(self) -> str:
        return key_of(self.chain, self.address)

    @property
    def supply(self) -> float | None:
        return self.mcap / self.price if self.price else None


@dataclass
class Deep:
    """Rohdaten der Tiefenprüfung (jedes Feld darf None sein, wenn die Quelle nichts lieferte)."""
    info: dict | None = None        # GeckoTerminal token info
    pool: dict | None = None        # GeckoTerminal pool attributes
    ohlcv: list | None = None       # Tageskerzen [ts, o, h, l, c, v], alt -> neu
    trades: list | None = None      # GeckoTerminal trades > min_usd
    rugcheck: dict | None = None    # Solana
    goplus: dict | None = None      # Solana oder EVM
    honeypot: dict | None = None    # EVM


@dataclass
class Analysis:
    cand: Candidate
    metrics: dict
    red_flags: list[str]
    warnings: list[str]
    positives: list[str]
    score: float
    components: dict

    @property
    def excluded(self) -> bool:
        return bool(self.red_flags)


# --------------------------------------------------------------------------------------------------- Kandidaten

def candidates_from_pairs(pairs: list[dict], wanted: set[str] | None, now_ms: float, sources: dict | None = None
                          ) -> dict[str, Candidate]:
    """Fasst DexScreener-Pairs pro Token zusammen. Haupt-Pool = Pool mit der meisten Liquidität."""
    groups: dict[str, list[dict]] = {}
    for p in pairs:
        base = p.get("baseToken") or {}
        chain = p.get("chainId")
        if not chain or not base.get("address"):
            continue
        k = key_of(chain, base["address"])
        if wanted is not None and k not in wanted:
            continue
        if any(x.get("pairAddress") == p.get("pairAddress") for x in groups.get(k, [])):
            continue
        groups.setdefault(k, []).append(p)

    out: dict[str, Candidate] = {}
    for k, ps in groups.items():
        liq = lambda p: fnum((p.get("liquidity") or {}).get("usd"), 0.0)  # noqa: E731
        main = max(ps, key=liq)
        created = [fnum(p.get("pairCreatedAt")) for p in ps if fnum(p.get("pairCreatedAt"))]
        tx = main.get("txns") or {}
        vol = main.get("volume") or {}
        pc = main.get("priceChange") or {}
        info = main.get("info") or {}
        mcap = fnum(main.get("marketCap")) or fnum(main.get("fdv")) or 0.0
        out[k] = Candidate(
            chain=main["chainId"], address=main["baseToken"]["address"],
            symbol=str(main["baseToken"].get("symbol") or "?"), name=str(main["baseToken"].get("name") or "?"),
            pair=main.get("pairAddress") or "", dex=main.get("dexId") or "?",
            quote=str((main.get("quoteToken") or {}).get("symbol") or "?"),
            price=fnum(main.get("priceUsd"), 0.0), mcap=mcap, fdv=fnum(main.get("fdv"), mcap),
            liquidity=sum(liq(p) for p in ps), liq_main=liq(main),
            vol24=sum(fnum((p.get("volume") or {}).get("h24"), 0.0) for p in ps),
            vol6=fnum(vol.get("h6"), 0.0), vol1=fnum(vol.get("h1"), 0.0),
            pc1=fnum(pc.get("h1")), pc6=fnum(pc.get("h6")), pc24=fnum(pc.get("h24")),
            buys24=int((tx.get("h24") or {}).get("buys") or 0), sells24=int((tx.get("h24") or {}).get("sells") or 0),
            age_days=(now_ms - min(created)) / 86_400_000 if created else None,
            pair_addresses=[p.get("pairAddress") for p in ps if p.get("pairAddress")],
            sources=set((sources or {}).get(k, set())),
            websites=[w.get("url") for w in info.get("websites") or [] if w.get("url")],
            socials=[s.get("url") for s in info.get("socials") or [] if s.get("url")],
            boosts=int((main.get("boosts") or {}).get("active") or 0),
        )
    return out


STOCK_LIKE = re.compile(r"^[A-Z]{2,5}[cx]$")  # tokenisierte Aktien wie NVDAc, AAPLx


def is_meme_candidate(c: Candidate, skip_symbols: set[str]) -> bool:
    s = c.symbol.upper()
    if s in skip_symbols or STOCK_LIKE.match(c.symbol):
        return False
    low = c.name.lower()
    return not any(w in low for w in ("usd", "tokenized", "wrapped", "staked", "bridged"))


def prefilter(c: Candidate, f: dict) -> str | None:
    """Gibt den Grund zurück, warum ein Token nicht in die Tiefenprüfung kommt (oder None)."""
    if c.mcap < f["min_mcap_usd"]:
        return "Market Cap zu klein"
    if c.mcap > f["max_mcap_usd"]:
        return "Market Cap zu groß"
    if c.liquidity < f["min_liquidity_usd"]:
        return "zu wenig Liquidität"
    if c.vol24 < f["min_volume24_usd"]:
        return "zu wenig Volumen"
    return None


def prescore(c: Candidate) -> float:
    """Schnelle Vorsortierung: Umschlag, Liquiditätsquote, Käuferüberhang, Momentum."""
    turnover = min(c.vol24 / max(c.mcap, 1), 3) / 3
    liqr = clamp01((c.liquidity / max(c.mcap, 1) - 0.02) / 0.15)
    tx = c.buys24 + c.sells24
    buy = clamp01((c.buys24 / tx - 0.4) / 0.25) if tx else 0.3
    mom = clamp01(((c.pc6 or 0) + 30) / 80)
    return 35 * turnover + 25 * liqr + 25 * buy + 15 * mom


# --------------------------------------------------------------------------------------------------- Kennzahlen

def ohlcv_metrics(ohlcv: list | None, price_now: float | None = None) -> dict:
    if not ohlcv:
        return {}
    closes = [fnum(x[4], 0.0) for x in ohlcv]
    highs = [fnum(x[2], 0.0) for x in ohlcv]
    vols = [fnum(x[5], 0.0) for x in ohlcv]
    last = price_now or closes[-1]
    m: dict[str, Any] = {"days": len(ohlcv), "vol_days": vols[-10:]}
    prev = vols[-10:-3]
    m["vol_last3"] = sum(vols[-3:]) / min(3, len(vols))
    m["vol_prev7"] = sum(prev) / len(prev) if prev else None
    m["vol_trend"] = m["vol_last3"] / m["vol_prev7"] if m["vol_prev7"] else None
    if len(closes) >= 8 and closes[-8]:
        m["chg7d"] = last / closes[-8] - 1
    if len(closes) >= 3 and closes[-3]:
        m["chg48h"] = last / closes[-3] - 1
    hi = max(highs) if highs else 0
    if hi:
        m["dd_from_high"] = last / hi - 1
        idx = highs.index(hi)
        m["high_days_ago"] = len(highs) - 1 - idx
    lows = [c for c in closes[-4:-1] if c > 0]  # Tief der letzten 3 abgeschlossenen Tage
    m["swing_low"] = min(lows) if len(lows) >= 2 else None
    return m


def whale_flow(trades: list | None, big_usd: float = 5000) -> dict:
    if trades is None:
        return {}
    buy = sell = 0.0
    buyers: set[str] = set()
    sellers: set[str] = set()
    big_b = big_s = 0
    for t in trades:
        v = fnum(t.get("volume_in_usd"), 0.0)
        who = t.get("tx_from_address") or ""
        if t.get("kind") == "buy":
            buy += v
            buyers.add(who)
            big_b += v >= big_usd
        elif t.get("kind") == "sell":
            sell += v
            sellers.add(who)
            big_s += v >= big_usd
    ts = sorted(t.get("block_timestamp") for t in trades if t.get("block_timestamp"))
    return {"n": len(trades), "buy_usd": buy, "sell_usd": sell, "buyers": len(buyers), "sellers": len(sellers),
            "big_buys": big_b, "big_sells": big_s, "span": (ts[0], ts[-1]) if ts else None,
            "buy_share": buy / (buy + sell) if buy + sell else None}


def pool_activity(pool: dict | None) -> dict:
    t = (pool or {}).get("transactions") or {}
    out = {}
    for w in ("h1", "h6", "h24"):
        x = t.get(w) or {}
        out[w] = {"buyers": int(x.get("buyers") or 0), "sellers": int(x.get("sellers") or 0),
                  "traders": int(x.get("unique_traders") or 0), "buys": int(x.get("buys") or 0),
                  "sells": int(x.get("sells") or 0)}
    return out


def holder_metrics(goplus: dict | None, info: dict | None = None) -> dict:
    """Holder-Zahl (GoPlus, Fallback GeckoTerminal-Info)."""
    out: dict[str, Any] = {}
    if goplus:
        out["holders"] = int(fnum(goplus.get("holder_count"), 0) or 0) or None
        hs = goplus.get("holders") or []
        if hs:  # GoPlus liefert Anteile als Bruch (0.05 = 5 %)
            out["top10_gp"] = sum(fnum(h.get("percent"), 0.0) for h in hs[:10]) * 100
    if info:
        hd = info.get("holders") or {}
        out.setdefault("holders", int(hd.get("count") or 0) or None)
        out["top10_gt"] = fnum((hd.get("distribution_percentage") or {}).get("top_10"))
        out["dev_pct"] = fnum(info.get("developer_holding_percentage"))
    return out


def solana_security(rc: dict | None, pool_accounts: set[str]) -> dict:
    """RugCheck-Report -> vereinfachte Sicherheitskennzahlen. Pools/Locker zählen nicht als Holder."""
    if not rc:
        return {}
    known = rc.get("knownAccounts") or {}
    skip = set(pool_accounts) | {a for a, v in known.items() if (v or {}).get("type") in ("AMM", "LOCKER")}
    for m in rc.get("markets") or []:
        skip.update(x for x in (m.get("pubkey"), m.get("liquidityA"), m.get("liquidityB")) if x)
    holders = [h for h in rc.get("topHolders") or [] if h.get("owner") not in skip and h.get("address") not in skip]
    tok = rc.get("token") or {}
    supply_raw = fnum(tok.get("supply"))
    clusters = []
    for n in rc.get("insiderNetworks") or []:
        pct = (fnum(n.get("currentHolding"), 0.0) / supply_raw * 100) if supply_raw else None
        clusters.append({"size": int(n.get("size") or 0), "pct": min(pct, 100.0) if pct is not None else None})
    small = [c for c in clusters if c["size"] <= 50 and c["pct"] is not None]
    lp = [fnum((m.get("lp") or {}).get("lpLockedPct")) for m in rc.get("markets") or []]
    lp = [x for x in lp if x is not None]
    creator_pct = None
    if supply_raw and rc.get("creatorBalance") is not None:
        creator_pct = fnum(rc.get("creatorBalance"), 0.0) / supply_raw * 100
    risks = rc.get("risks") or []
    return {
        "mint_authority": rc.get("mintAuthority"), "freeze_authority": rc.get("freezeAuthority"),
        "rc_score": fnum(rc.get("score_normalised")), "rugged": bool(rc.get("rugged")),
        "danger": [r.get("name") for r in risks if r.get("level") == "danger"],
        "warn": [r.get("name") for r in risks if r.get("level") == "warn"],
        "top1": fnum(holders[0].get("pct")) if holders else None,
        "top10": sum(fnum(h.get("pct"), 0.0) for h in holders[:10]) if holders else None,
        "insider_cluster_pct": max((c["pct"] for c in small), default=0.0),
        "insider_cluster_size": max(small, key=lambda c: c["pct"])["size"] if small else 0,
        "bot_network_size": max((c["size"] for c in clusters if c["size"] > 50), default=0),
        "lp_locked_pct": lp[0] if lp else None,
        "transfer_fee_pct": fnum((rc.get("transferFee") or {}).get("pct"), 0.0),
        "creator_pct": creator_pct, "holders_rc": rc.get("totalHolders"),
        "launchpad": (rc.get("launchpad") or {}).get("name"),
    }


def _gp_flag(g: dict, k: str) -> bool:
    return str(g.get(k)) == "1"


def evm_security(gp: dict | None, hp: dict | None) -> dict:
    out: dict[str, Any] = {}
    if gp:
        owner = (gp.get("owner_address") or "").lower()
        renounced = owner in ("", *DEAD_ADDRESSES)
        lp = gp.get("lp_holders") or []
        locked = sum(fnum(h.get("percent"), 0.0) for h in lp
                     if h.get("is_locked") == 1 or str(h.get("address", "")).lower() in DEAD_ADDRESSES)
        holders = [h for h in gp.get("holders") or [] if not h.get("is_contract")
                   and str(h.get("address", "")).lower() not in DEAD_ADDRESSES]
        creator = str(gp.get("creator_address") or "").lower()
        creator_is_contract = any(str(h.get("address", "")).lower() == creator and h.get("is_contract")
                                  for h in gp.get("holders") or [])
        creator_pct = (fnum(gp.get("creator_percent"), 0.0) or 0) * 100
        out.update({
            "honeypot": _gp_flag(gp, "is_honeypot"), "cannot_sell_all": _gp_flag(gp, "cannot_sell_all"),
            "buy_tax": (fnum(gp.get("buy_tax"), 0.0) or 0) * 100, "sell_tax": (fnum(gp.get("sell_tax"), 0.0) or 0) * 100,
            "mintable": _gp_flag(gp, "is_mintable") and not renounced, "owner_renounced": renounced,
            "hidden_owner": _gp_flag(gp, "hidden_owner"), "take_back_ownership": _gp_flag(gp, "can_take_back_ownership"),
            "pausable": _gp_flag(gp, "transfer_pausable") and not renounced,
            "blacklist": _gp_flag(gp, "is_blacklisted") and not renounced,
            "tax_changeable": _gp_flag(gp, "slippage_modifiable") and not renounced,
            "open_source": gp.get("is_open_source") != "0", "proxy": _gp_flag(gp, "is_proxy"),
            "lp_locked_pct": locked * 100 if lp else None,
            "top1": fnum(holders[0].get("percent"), 0.0) * 100 if holders else None,
            "top10": sum(fnum(h.get("percent"), 0.0) for h in holders[:10]) * 100 if holders else None,
            # Launchpad-Factory/Bonding-Curve als "Ersteller" ist kein Entwickler-Bestand
            "creator_pct": 0.0 if creator_is_contract or creator_pct >= 99 else creator_pct,
            "creator_launchpad": creator_is_contract or creator_pct >= 99,
            "holders_gp": int(fnum(gp.get("holder_count"), 0) or 0) or None,
        })
    if hp:
        sim = hp.get("simulationResult") or {}
        flags = [(f.get("flag") if isinstance(f, dict) else f) for f in (hp.get("summary") or {}).get("flags") or []]
        out.update({"hp_honeypot": (hp.get("honeypotResult") or {}).get("isHoneypot"),
                    "hp_risk": (hp.get("summary") or {}).get("risk"), "hp_flags": [f for f in flags if f],
                    "hp_buy_tax": fnum(sim.get("buyTax")), "hp_sell_tax": fnum(sim.get("sellTax"))})
    return out


# --------------------------------------------------------------------------------------------------- Bewertung

WEIGHTS = {"mcap": 10, "vol_trend": 15, "buy_pressure": 10, "whales": 15, "distribution": 15,
           "community": 10, "liquidity": 10, "momentum": 7, "not_extended": 8}


def _pct(x: float | None) -> str:
    return "?" if x is None else f"{x:+.0f} %"


def analyze(c: Candidate, d: Deep, cfg: dict) -> Analysis:
    f, rf = cfg["filters"], cfg["red_flags"]
    om = ohlcv_metrics(d.ohlcv, c.price)
    wf = whale_flow(d.trades, cfg.get("whale_trade_usd", 5000))
    act = pool_activity(d.pool)
    hm = holder_metrics(d.goplus, d.info)
    if c.chain == "solana":
        sec = solana_security(d.rugcheck, set(c.pair_addresses))
    else:
        sec = evm_security(d.goplus, d.honeypot)
    m = {**om, **{f"whale_{k}": v for k, v in wf.items()}, **hm, **{f"sec_{k}": v for k, v in sec.items()},
         "activity": act, "liq_ratio": c.liquidity / c.mcap if c.mcap else 0.0}
    holders = hm.get("holders") or sec.get("holders_gp") or (sec.get("holders_rc") and int(sec["holders_rc"] / 3))
    m["holders"] = holders
    top10 = next((x for x in (sec.get("top10"), hm.get("top10_gt")) if x is not None), None)
    top1 = sec.get("top1")
    m["top10"], m["top1"] = top10, top1

    red: list[str] = []
    warn: list[str] = []
    pos: list[str] = []

    # --- Sicherheit (harte Ausschlüsse)
    if c.chain == "solana":
        if not d.rugcheck:
            warn.append("RugCheck-Daten fehlen – Sicherheit nicht geprüft")
        else:
            if sec.get("rugged"):
                red.append("RugCheck meldet: bereits gerugged")
            if sec.get("mint_authority"):
                red.append("Mint-Authority aktiv – Entwickler kann neue Tokens drucken")
            if sec.get("freeze_authority"):
                red.append("Freeze-Authority aktiv – Wallets können eingefroren werden")
            for name in sec.get("danger") or []:
                if "Mint" not in name and "Freeze" not in name:
                    red.append(f"RugCheck-Gefahr: {name}")
            if (sec.get("transfer_fee_pct") or 0) > rf["max_tax_pct"]:
                red.append(f"Transfer-Gebühr {sec['transfer_fee_pct']:.0f} %")
            lp = sec.get("lp_locked_pct")
            if lp is not None and lp < rf["min_lp_locked_pct"]:
                red.append(f"Nur {lp:.0f} % der Liquidität gesperrt – Rug-Pull möglich")
            if sec.get("insider_cluster_pct", 0) > rf["max_insider_cluster_pct"]:
                red.append(f"Wallet-Netz aus {sec['insider_cluster_size']} verbundenen Wallets hält "
                           f"{de(sec['insider_cluster_pct'], 0)} %")
            elif sec.get("insider_cluster_pct", 0) >= 5:
                warn.append(f"{sec['insider_cluster_size']} verbundene Wallets halten {de(sec['insider_cluster_pct'])} % "
                            f"(können gemeinsam verkaufen)")
            if sec.get("bot_network_size"):
                warn.append(f"Großes Wallet-Netz ({sec['bot_network_size']} Wallets) – Bundle-/Bot-Verdacht")
            if (sec.get("creator_pct") or 0) > rf["max_dev_pct"]:
                red.append(f"Ersteller hält {sec['creator_pct']:.0f} %")
            if not red and sec.get("rc_score") is not None and sec["rc_score"] <= 10:
                pos.append("RugCheck: keine Risiken (Score „Good“), Mint & Freeze deaktiviert")
            for name in sec.get("warn") or []:
                warn.append(f"RugCheck-Hinweis: {name}")
    else:
        if not d.goplus and not d.honeypot:
            warn.append("GoPlus/Honeypot-Daten fehlen – Sicherheit nicht geprüft")
        if sec.get("honeypot") or sec.get("hp_honeypot") is True or sec.get("cannot_sell_all"):
            red.append("HONEYPOT – Verkaufen nicht (vollständig) möglich")
        tax = max(sec.get("buy_tax") or 0, sec.get("sell_tax") or 0, sec.get("hp_buy_tax") or 0, sec.get("hp_sell_tax") or 0)
        if tax > rf["max_tax_pct"]:
            red.append(f"Steuer {tax:.0f} % pro Trade")
        elif tax > 0:
            warn.append(f"Steuer {de(tax)} % pro Trade")
        for k, txt in (("mintable", "Owner kann neue Tokens minten"), ("hidden_owner", "Versteckter Owner"),
                       ("take_back_ownership", "Ownership kann zurückgeholt werden"),
                       ("pausable", "Handel kann pausiert werden"), ("blacklist", "Blacklist-Funktion aktiv"),
                       ("tax_changeable", "Owner kann Steuern ändern")):
            if sec.get(k):
                red.append(txt)
        if sec.get("open_source") is False:
            red.append("Contract-Code nicht verifiziert")
        if "high_fail_rate" in (sec.get("hp_flags") or []):
            red.append("Honeypot.is: viele Verkäufe schlagen fehl")
        lp = sec.get("lp_locked_pct")
        if lp is not None and lp < rf["min_lp_locked_pct"]:
            red.append(f"Nur {lp:.0f} % der Liquidität gesperrt/verbrannt – Rug-Pull möglich")
        elif lp is None and d.goplus:
            warn.append("LP-Sperre nicht prüfbar (V3/V4-Pool)")
        if (sec.get("creator_pct") or 0) > rf["max_dev_pct"]:
            red.append(f"Ersteller hält {sec['creator_pct']:.0f} %")
        if sec.get("creator_launchpad"):
            warn.append("Ersteller-Adresse hält fast alles – vermutlich Launchpad-/Bonding-Curve-Contract, "
                        "Verteilung manuell prüfen")
        if not red and sec.get("owner_renounced") and d.goplus:
            pos.append("Contract: kein Honeypot, 0 % Steuer, Ownership abgegeben")

    # --- Verteilung
    if (hm.get("dev_pct") or 0) > rf["max_dev_pct"]:
        red.append(f"Entwickler hält {hm['dev_pct']:.0f} %")
    if top1 is not None and top1 > rf["max_top1_pct"]:
        red.append(f"Eine Wallet hält {de(top1)} %" + (" (falls Börsen-Wallet: prüfen)" if c.chain != "solana" else ""))
    if top10 is not None and top10 > rf["max_top10_pct"]:
        red.append(f"Top 10 Wallets halten {top10:.0f} %")
    elif top10 is not None and top10 <= 20:
        pos.append(f"Breite Verteilung: Top 10 halten nur {top10:.0f} %")

    # --- Markt / Manipulation
    if c.age_days is not None and c.age_days < f["min_age_days"]:
        red.append(f"Zu jung ({c.age_days * 24:.0f} h) – extremes Dump-/Rug-Risiko")
    if (c.pc24 or 0) > rf["max_pump_24h_pct"]:
        red.append(f"Bereits explodiert ({_pct(c.pc24)} in 24 h) – kein früher Einstieg mehr")
    traders = act.get("h24", {}).get("traders") or 0
    if holders and traders > 5 * holders and holders < 10_000:
        red.append(f"{traders:,} Trader/Tag bei nur {holders:,} Holdern – Wash-Trading-Verdacht".replace(",", "."))
    if wf and c.vol24 > 300_000 and wf.get("n", 0) < 5:
        red.append("Hohes Volumen, aber kaum Trades über 500 $ – Bot-Volumen-Verdacht")
    chg7 = om.get("chg7d")
    vt = om.get("vol_trend")
    if chg7 is not None and chg7 < -0.4 and vt is not None and vt < 0.7:
        red.append(f"Hype vorbei: {_pct(chg7 * 100)} in 7 Tagen, Volumen fällt")
    if c.liquidity / max(c.mcap, 1) < f["min_liq_ratio"]:
        warn.append(f"Dünne Liquidität: nur {de(c.liquidity / max(c.mcap, 1) * 100)} % der Market Cap")
    if om.get("dd_from_high") is not None and om["dd_from_high"] < -0.7 and om.get("high_days_ago", 99) <= 7:
        when = {0: "von heute", 1: "von gestern"}.get(om["high_days_ago"], f"von vor {om['high_days_ago']} Tagen")
        warn.append(f"Hype schon gelaufen: {om['dd_from_high'] * 100:.0f} % unter dem Hoch {when}")
    if om.get("chg48h") is not None and om["chg48h"] > 0.5:
        warn.append(f"Kurz zuvor stark gestiegen ({_pct(om['chg48h'] * 100)} in 48 h) – nicht hinterherkaufen")
    if c.boosts:
        warn.append("Bezahlte DexScreener-Boosts aktiv (Werbung ≠ echte Nachfrage)")
    if not (c.websites or c.socials):
        warn.append("Keine Website/Socials hinterlegt")

    # --- Score-Komponenten (0..1)
    lo, hi = math.log(max(f["min_mcap_usd"], 1)), math.log(f["max_mcap_usd"])
    comp = {"mcap": clamp01((hi - math.log(max(c.mcap, 1))) / (hi - lo))}
    comp["vol_trend"] = clamp01((vt - 0.5) / 2.5) if vt is not None else 0.4
    a24 = act.get("h24") or {}
    if a24.get("buyers") or a24.get("sellers"):
        share = a24["buyers"] / (a24["buyers"] + a24["sellers"])
    else:
        share = c.buys24 / (c.buys24 + c.sells24) if c.buys24 + c.sells24 else 0.5
    comp["buy_pressure"] = clamp01((share - 0.4) / 0.2)
    bs = wf.get("buy_share")
    comp["whales"] = clamp01((bs - 0.35) / 0.3) if bs is not None and wf.get("n", 0) >= 5 else 0.3
    comp["distribution"] = clamp01((50 - top10) / 40) if top10 is not None else 0.3
    per_m = (holders or 0) / max(c.mcap / 1e6, 0.05)
    comp["community"] = clamp01(math.log(per_m / 500) / math.log(20)) if per_m > 0 else 0.0
    comp["liquidity"] = clamp01((m["liq_ratio"] - 0.03) / 0.12)
    if chg7 is None:
        comp["momentum"] = 0.5
    elif chg7 <= 3:
        comp["momentum"] = clamp01((chg7 + 0.4) / 0.9)
    else:  # parabolisch -> Rücksetzer-Gefahr
        comp["momentum"] = 0.3
    run_up = max(c.pc24 or 0, (om.get("chg48h") or 0) * 100)  # schon gelaufen? 24 h oder 48 h
    comp["not_extended"] = clamp01(1 - (run_up - 50) / 250)
    score = sum(WEIGHTS[k] * v for k, v in comp.items())
    if any(w.startswith("Hype schon gelaufen") for w in warn):
        score -= 10

    # --- Positive Fakten
    if vt is not None and vt >= 1.5:
        pos.append(f"Volumen steigt: letzte 3 Tage {de(vt)}× so hoch wie die 7 Tage davor")
    if share >= 0.53:
        pos.append(f"Mehr Käufer als Verkäufer (24 h): {a24.get('buyers') or c.buys24:,} zu "
                   f"{a24.get('sellers') or c.sells24:,}".replace(",", "."))
    if bs is not None and wf.get("n", 0) >= 5 and bs >= 0.52:
        pos.append(f"Große Trades (>500 $) netto Kauf: {wf['buy_usd'] / 1000:.0f} k$ Käufe vs. "
                   f"{wf['sell_usd'] / 1000:.0f} k$ Verkäufe")
    elif bs is not None and wf.get("n", 0) >= 5 and bs < 0.45:
        warn.append(f"Große Wallets verkaufen netto: {wf['sell_usd'] / 1000:.0f} k$ Verkäufe vs. "
                    f"{wf['buy_usd'] / 1000:.0f} k$ Käufe")
    if per_m >= 3000:
        pos.append(f"Große Community für die Größe: {holders:,} Holder".replace(",", "."))
    if chg7 is not None and 0.1 <= chg7 <= 3:
        pos.append(f"Aufwärtstrend: {_pct(chg7 * 100)} in 7 Tagen")
    if c.chain == "solana" and sec.get("lp_locked_pct") is not None and sec["lp_locked_pct"] >= 99:
        pos.append("Liquidität 100 % gesperrt")

    score -= min(2 * len(warn), 12)  # jedes Warnsignal kostet Punkte
    return Analysis(c, m, red, warn, pos, float(round(max(score, 0))), comp)
