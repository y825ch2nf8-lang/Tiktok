"""Telegram-Nachrichten (HTML) auf Deutsch: Scan-Übersicht, Detail-Check mit 7 Punkten, Szenarien."""
from __future__ import annotations

import math
from html import escape
from zoneinfo import ZoneInfo

from .analysis import Analysis, Candidate
from .scanner import Market, ScanResult
from .scenarios import scenario

TZ = ZoneInfo("Europe/Berlin")

CHAIN_INFO = {
    "solana": {"name": "Solana", "native": "SOL", "tw": "Solana", "aggregator": "Jupiter (jup.ag)",
               "extra": "einmalig ~0,002 SOL für das Token-Konto (erstattbar)"},
    "bsc": {"name": "BNB Smart Chain (BEP-20)", "native": "BNB", "tw": "BNB Smart Chain",
            "aggregator": "PancakeSwap / 1inch", "extra": ""},
    "ethereum": {"name": "Ethereum (ERC-20)", "native": "ETH", "tw": "Ethereum", "aggregator": "Uniswap / 1inch",
                 "extra": "Gas schwankt stark – vor dem Bestätigen prüfen"},
    "base": {"name": "Base", "native": "ETH auf Base", "tw": "Base", "aggregator": "Aerodrome / Uniswap", "extra": ""},
}
DEX_NAMES = {"pumpswap": "PumpSwap", "raydium": "Raydium", "meteora": "Meteora", "orca": "Orca",
             "pancakeswap": "PancakeSwap", "uniswap": "Uniswap", "aerodrome": "Aerodrome", "sushiswap": "SushiSwap",
             "fourmeme": "Four.meme", "pumpfun": "pump.fun"}
NATIVE_QUOTES = {"SOL", "WSOL", "USDC", "USDT", "WBNB", "BNB", "WETH", "ETH", "USD1"}


# ------------------------------------------------------------------------------------------------ Formatierung

def num_de(x: float, digits: int = 0) -> str:
    s = f"{x:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def usd(x: float | None) -> str:
    if x is None:
        return "?"
    if abs(x) >= 1e9:
        return f"{num_de(x / 1e9, 2)} Mrd. $"
    if abs(x) >= 1e6:
        return f"{num_de(x / 1e6, 2)} Mio. $"
    if abs(x) >= 1e3:
        return f"{num_de(x / 1e3)} Tsd. $"
    return f"{num_de(x, 2)} $"


def eur(x: float) -> str:
    return f"{num_de(x)} €"


def pct(x: float | None, digits: int = 0) -> str:
    return "?" if x is None else f"{'+' if x > 0 else ''}{num_de(x, digits)} %"


def price(x: float) -> str:
    """Kleine Kurse mit 3 signifikanten Stellen: 0,000636 $ statt 0,00 $."""
    if not x:
        return "?"
    if x >= 1:
        return f"{num_de(x, 2)} $"
    decimals = min(-math.floor(math.log10(x)) + 2, 12)
    return f"{x:.{decimals}f}".replace(".", ",") + " $"


def native_price(market: Market, chain: str) -> float:
    """Preis der Gas-Währung in $ (Base zahlt Gas in ETH)."""
    return market.native_usd.get(chain) or (market.native_usd.get("ethereum", 0.0) if chain == "base" else 0.0)


def h(x) -> str:
    return escape(str(x), quote=False)


def token_title(c: Candidate) -> str:
    return f"<b>{h(c.symbol)}</b> ({h(c.name)}) · {CHAIN_INFO[c.chain]['name']}"


def dex_link(c: Candidate) -> str:
    return f"https://dexscreener.com/{c.chain}/{c.pair}"


def security_link(c: Candidate) -> str:
    if c.chain == "solana":
        return f'<a href="https://rugcheck.xyz/tokens/{c.address}">RugCheck</a>'
    cid = {"bsc": 56, "ethereum": 1, "base": 8453}[c.chain]
    return (f'<a href="https://honeypot.is/?address={c.address}&amp;chain={cid}">Honeypot.is</a> · '
            f'<a href="https://gopluslabs.io/token-security/{cid}/{c.address}">GoPlus</a>')


def verdict(a: Analysis, min_score: float, max_eur: float) -> str:
    if a.excluded:
        return "⛔ Finger weg – harte Ausschlussgründe gefunden"
    if a.score < min_score:
        return f"✋ Nicht überzeugend (Score unter {min_score:g}) – kein Kauf"
    return f"👀 Watchlist – Kauf nur, wenn alle Bedingungen erfüllt sind (max. {eur(max_eur)} Spielgeld)"


def split_message(text: str, limit: int = 3900) -> list[str]:
    """Telegram erlaubt max. 4096 Zeichen pro Nachricht – an Absätzen/Zeilen trennen."""
    parts, cur = [], ""
    for block in text.split("\n"):
        if len(cur) + len(block) + 1 > limit and cur:
            parts.append(cur.rstrip())
            cur = ""
        while len(block) > limit:
            parts.append(block[:limit])
            block = block[limit:]
        cur += block + "\n"
    if cur.strip():
        parts.append(cur.rstrip())
    return parts


# ------------------------------------------------------------------------------------------------ Bausteine

def market_line(m: Market, chains: list[str]) -> str:
    names = {"solana": "SOL", "bsc": "BNB", "ethereum": "ETH", "base": None}
    bits = [f"{names[c]} {num_de(m.native_usd[c])} $" for c in dict.fromkeys(["solana", *chains])
            if names.get(c) and c in m.native_usd]
    eur_txt = f"1 € = {num_de(m.eur_usd, 3)} $" + ("" if m.eur_usd_live else " (Annahme)")
    return " · ".join(bits + [eur_txt])


def short_card(i: int, a: Analysis, min_score: float) -> str:
    c, m = a.cand, a.metrics
    low = " · ⚠️ unter Mindest-Score" if a.score < min_score else ""
    lines = [f"<b>{i}. {h(c.symbol)}</b> ({CHAIN_INFO[c.chain]['name'].split(' ')[0]}) · Score <b>{a.score:.0f}</b>/100{low}",
             f"MC {usd(c.mcap)} · Liq {usd(c.liquidity)} · Vol 24h {usd(c.vol24)}",
             f"24h {pct(c.pc24)} · 7T {pct((m.get('chg7d') or 0) * 100) if m.get('chg7d') is not None else '?'}"
             f" · Holder {num_de(m['holders']) if m.get('holders') else '?'}"
             f" · Top 10 {num_de(m['top10']) + ' %' if m.get('top10') is not None else '?'}"]
    for p in a.positives[:2]:
        lines.append(f"✅ {h(p)}")
    for w in a.warnings[:2]:
        lines.append(f"⚠️ {h(w)}")
    lines.append(f"CA: <code>{h(c.address)}</code>")
    return "\n".join(lines)


def scenario_block(c: Candidate, cfg: dict, market: Market, amounts: list[float] | None = None) -> str:
    costs = cfg["costs"]
    fee_native = (cfg.get("network_fee_native") or {}).get(c.chain, 0)
    fee_eur = fee_native * native_price(market, c.chain) / market.eur_usd
    mults = cfg["scenario_multiples"]
    out = ["<b>💶 Szenarien</b> (vor Steuern, inkl. geschätzter Gebühren &amp; Slippage)"]
    for amt in amounts or cfg["scenario_amounts_eur"]:
        s = scenario(amt, c.mcap, c.liquidity, costs, market.eur_usd, mults, fee_eur)
        o = s.outcomes
        out.append(f"<b>{eur(amt)}</b> (Kosten Kauf ~{num_de(s.entry_cost_pct, 1)} %, Verkauf ~{num_de(s.exit_cost_pct, 1)} %)")
        out.append("  " + " | ".join(f"{k}: {eur(o[k])}" for k in [f"{m:g}x" for m in mults]))
        out.append(f"  −50 %: {eur(o['−50 %'])} | −90 %: {eur(o['−90 %'])} | Rug: 0 €")
    s = scenario(100, c.mcap, c.liquidity, costs, market.eur_usd, mults)
    out.append("Benötigte Market Cap: " + " · ".join(f"{k:g}x = {usd(v)}" for k, v in s.mcap_needed.items()))
    out.append("<i>Steuer (DE): Gewinne bei &lt; 1 Jahr Haltedauer steuerpflichtig, Freigrenze 1.000 €/Jahr.</i>")
    return "\n".join(out)


def potential_block(a: Analysis, biggest: Candidate | None, cfg: dict) -> str:
    c = a.cand
    mults = cfg["scenario_multiples"]
    lines = ["<b>3️⃣ Wachstumspotenzial</b> <i>(Spekulation, regelbasiert)</i>"]
    if biggest and biggest.mcap > c.mcap:
        reachable = [m for m in mults if c.mcap * m <= biggest.mcap]
        lines.append(f"Größtes Meme in den aktuellen Trendlisten: {h(biggest.symbol)} mit {usd(biggest.mcap)}.")
        if reachable and max(reachable) == max(mults):
            lines.append(f"Selbst {max(mults):g}x ({usd(c.mcap * max(mults))}) läge noch darunter – theoretisch "
                         f"möglich, aber nur sehr wenige Memes schaffen das je.")
        elif reachable:
            nxt = min(m for m in mults if m > max(reachable))
            lines.append(f"Bis {max(reachable):g}x ({usd(c.mcap * max(reachable))}) bliebe {h(c.symbol)} darunter. "
                         f"Ab {nxt:g}x ({usd(c.mcap * nxt)}) müsste es größer werden als das größte Meme im Markt – "
                         f"sehr unwahrscheinlich.")
        else:
            lines.append(f"Schon 5x ({usd(c.mcap * 5)}) wäre mehr als das größte Meme im Scan – sehr unwahrscheinlich.")
    lines.append("Häufigster Ausgang bei Memecoins: Verlust. Plane mit Totalverlust.")
    return "\n".join(lines)


def trust_wallet_block(c: Candidate, cfg: dict, market: Market) -> str:
    ci = CHAIN_INFO[c.chain]
    fee_native = (cfg.get("network_fee_native") or {}).get(c.chain, 0)
    px = native_price(market, c.chain)
    fee_txt = f"~{str(fee_native).replace('.', ',')} {ci['native'].split(' ')[0]}" + (f" (≈ {usd(fee_native * px)})" if px else "")
    dex = DEX_NAMES.get(c.dex, c.dex)
    lines = ["<b>5️⃣ Kauf über Trust Wallet</b>",
             f"Netzwerk: {ci['name']} (in Trust Wallet: „{ci['tw']}“) ✅ unterstützt",
             f"Benötigt: <b>{ci['native']}</b> · Haupt-Pool: {h(dex)} ({h(c.symbol)}/{h(c.quote)})",
             f"Netzwerkgebühr pro Swap: {fee_txt}" + (f" · {ci['extra']}" if ci["extra"] else ""),
             "Trust-Wallet-Swapgebühr: laut Quellen 0–0,7 % (genaue Kosten zeigt die Swap-Vorschau)",
             "Schritte: 1) Swap → " + ci["native"] + " auswählen 2) Ziel-Token per Contract-Adresse suchen "
             "3) Slippage 1–3 % 4) Vorschau prüfen → bestätigen",
             "Erst „Manage crypto → + → " + ci["tw"] + " → Contract einfügen“, damit der Token angezeigt wird.",
             f"Taucht er im Swap nicht auf: über {ci['aggregator']} im dApp-Browser von Trust Wallet."]
    if c.quote.upper() not in NATIVE_QUOTES:
        lines.append(f"⚠️ Der Haupt-Pool handelt gegen {h(c.quote)}, nicht gegen {ci['native']} – "
                     f"der Aggregator routet meist automatisch, Vorschau genau prüfen.")
    return "\n".join(lines)


def conditions_block(a: Analysis, cfg: dict) -> list[str]:
    c, m = a.cand, a.metrics
    sup = c.supply or 0
    conds = [f"Contract-Adresse zeichengenau prüfen: <code>{h(c.address)}</code> (Kopien mit gleichem Namen existieren oft)"]
    hot = (m.get("chg48h") or 0) > 0.5 or (c.pc24 or 0) > 50
    if hot:
        conds.append(f"Nicht hinterherkaufen: 24–48 h Konsolidierung abwarten, Einstiegszone ≈ MC "
                     f"{usd(c.mcap * 0.75)}–{usd(c.mcap * 0.9)}")
    if m.get("swing_low") and sup:
        conds.append(f"Ausstieg (Invalidierung): Tagesschluss unter {price(m['swing_low'])} "
                     f"(MC ≈ {usd(m['swing_low'] * sup)}, 7-Tage-Tief)")
    conds.append(f"Liquidität bleibt ≥ {usd(c.liquidity * 0.8)} und Volumen ≥ "
                 f"{usd(max(c.vol24 * 0.5, cfg['filters']['min_volume24_usd']))}/Tag")
    if m.get("holders"):
        conds.append(f"Holder-Zahl wächst weiter über {num_de(m['holders'])}")
    conds.append("Sicherheits-Check bleibt sauber (Link unten erneut öffnen)")
    if (m.get("sec_insider_cluster_pct") or 0) >= 5:
        conds.append(f"Das Wallet-Netz mit {num_de(m['sec_insider_cluster_pct'], 1)} % verkauft nicht (RugCheck → Insider)")
    conds.append("Große Trades bleiben netto auf der Kaufseite (DexScreener → Trades, Filter > 500 $)")
    conds.append("Ausstiegsplan vorher festlegen: bei 2x Einsatz rausziehen, bei 5x ein weiteres Drittel verkaufen")
    conds.append(f"Positionsgröße max. {eur(cfg['recommend']['max_position_eur'])} – nur Geld, das du komplett verlieren kannst")
    return conds


# ------------------------------------------------------------------------------------------------ Nachrichten

def detail(a: Analysis, cfg: dict, market: Market, biggest: Candidate | None = None, title: str = "🔬 Token-Check") -> str:
    c, m = a.cand, a.metrics
    rec = cfg["recommend"]
    act = (m.get("activity") or {}).get("h24") or {}
    L = [f"{title}: {token_title(c)}",
         f"Score <b>{a.score:.0f}</b>/100 · {verdict(a, rec['min_score'], rec['max_position_eur'])}", ""]
    if a.red_flags:
        L.append("<b>⛔ Ausschlussgründe</b>")
        L += [f"❌ {h(x)}" for x in a.red_flags]
        L.append("")
    L.append("<b>1️⃣ Warum dieser Coin?</b> <i>(Fakten aus Live-Daten)</i>")
    L += [f"✅ {h(p)}" for p in a.positives] or ["– keine besonderen Stärken gefunden"]
    L.append("")
    L.append("<b>2️⃣ Market Cap &amp; Markt</b>")
    L.append(f"MC {usd(c.mcap)} (FDV {usd(c.fdv)}) · Preis {price(c.price)}")
    L.append(f"Liquidität {usd(c.liquidity)} ({num_de(m.get('liq_ratio', 0) * 100, 1)} % der MC) · Vol 24h {usd(c.vol24)}")
    chg7 = m.get("chg7d")
    L.append(f"Kurs 1h {pct(c.pc1)} · 24h {pct(c.pc24)} · 7T {pct(chg7 * 100) if chg7 is not None else '?'}"
             + (f" · {pct(m['dd_from_high'] * 100)} vom 30T-Hoch" if m.get("dd_from_high") is not None else ""))
    if m.get("vol_trend") is not None:
        L.append(f"Volumen-Trend: {num_de(m['vol_trend'], 1)}× (Ø letzte 3 Tage vs. 7 Tage davor)")
    L.append(f"Alter {num_de(c.age_days, 0) + ' Tage' if c.age_days is not None else '?'} · Holder "
             f"{num_de(m['holders']) if m.get('holders') else '?'} · Top 10 "
             f"{num_de(m['top10'], 1) + ' %' if m.get('top10') is not None else '?'} · größte Wallet "
             f"{num_de(m['top1'], 1) + ' %' if m.get('top1') is not None else '?'}")
    if act:
        L.append(f"24h: {num_de(act.get('buyers', 0))} Käufer / {num_de(act.get('sellers', 0))} Verkäufer")
    if m.get("whale_n"):
        L.append(f"Große Trades (>500 $, letzte {m['whale_n']}): Käufe {usd(m['whale_buy_usd'])} / "
                 f"Verkäufe {usd(m['whale_sell_usd'])} · Whale-Trades >5k$: "
                 f"{m['whale_big_buys']} Käufe / {m['whale_big_sells']} Verkäufe")
    L.append("")
    L.append(potential_block(a, biggest, cfg))
    L.append("")
    L.append("<b>4️⃣ Risiken</b>")
    L += [f"⚠️ {h(w)}" for w in a.warnings] or ["– keine zusätzlichen Warnungen (Memecoin-Grundrisiko bleibt)"]
    L.append("⚠️ Memecoins haben keinen inneren Wert – Kurs hängt allein an Aufmerksamkeit")
    L.append("")
    L.append(trust_wallet_block(c, cfg, market))
    L.append("")
    L.append("<b>6️⃣ Contract-Adresse</b>")
    L.append(f"<code>{h(c.address)}</code>")
    L.append(f'<a href="{dex_link(c)}">DexScreener</a> · {security_link(c)}')
    L.append("")
    if not a.excluded:
        L.append("<b>7️⃣ Bedingungen vor dem Kauf</b> (alle müssen erfüllt sein)")
        L += [f"☐ {x}" for x in conditions_block(a, cfg)]
        L.append("")
        L.append(scenario_block(c, cfg, market))
        L.append("")
    L.append("<i>Fakten = Live-Daten von DexScreener, GeckoTerminal, RugCheck, GoPlus, Honeypot.is. "
             "Score, Potenzial und Bedingungen = regelbasierte Einschätzung. Keine Anlageberatung.</i>")
    return "\n".join(L)


def scan_overview(r: ScanResult, cfg: dict) -> str:
    rec = cfg["recommend"]
    t = r.finished.astimezone(TZ).strftime("%d.%m.%Y %H:%M")
    dur = (r.finished - r.started).total_seconds()
    L = [f"🔎 <b>Memecoin-Scan</b> · {t} Uhr ({num_de(dur)} s)",
         f"Chains: {', '.join(CHAIN_INFO[c]['name'].split(' ')[0] for c in r.chains)}",
         f"{r.n_raw} Tokens gefunden → {r.n_meme} Memes mit Kursdaten → {r.n_filtered} im Filter → "
         f"{len(r.analyses)} tief geprüft",
         f"Markt: {market_line(r.market, r.chains)}", ""]
    top = r.top
    if top:
        L.append("🏆 <b>Die besten Kandidaten</b>")
        for i, a in enumerate(top, 1):
            L.append(short_card(i, a, rec["min_score"]))
            L.append("")
    fav = r.favorite(rec["min_score"])
    if fav:
        L.append(f"⭐ <b>Favorit: {h(fav.cand.symbol)}</b> – Details folgen in der nächsten Nachricht")
    else:
        best = f" (bester Score: {top[0].score:.0f})" if top else ""
        L.append(f"🛑 <b>Kein überzeugender Coin gefunden{best} – keine Kaufempfehlung.</b>")
    L.append("")
    if r.excluded:
        L.append(f"❌ <b>Aussortiert ({len(r.excluded)})</b>")
        for a in sorted(r.excluded, key=lambda x: -x.cand.vol24)[:10]:
            L.append(f"• {h(a.cand.symbol)} ({a.cand.chain}): {h(a.red_flags[0])}")
    L.append("")
    L.append("Einzelnen Coin prüfen: /check &lt;Contract-Adresse&gt;")
    return "\n".join(L)


def invest_message(c: Candidate, amount: float, cfg: dict, market: Market) -> str:
    return f"{token_title(c)} · MC {usd(c.mcap)} · Liq {usd(c.liquidity)}\n\n" + \
        scenario_block(c, cfg, market, [amount])
