"""Offline-Demo: erfundene Tokens, die alle Regeln einmal auslösen (sauberer Favorit, Rug, Honeypot, Wash-Trading …).

Wird von `python -m memecoin_bot demo` und den Tests genutzt. Alle Adressen und Zahlen sind FIKTIV.
"""
from __future__ import annotations

import re
from urllib.parse import unquote

from .sources import EURC_SOLANA, NATIVE_TOKEN

NOW_S = 1_795_010_000  # 18.11.2026 ~13:53 UTC
DAY = 86_400

# symbol, chain, address, mcap, liq, vol24, age_days, extra
TOKENS = {
    "GOODCAT": dict(chain="solana", address="GoodCat1111111111111111111111111111111pump", mcap=4_000_000,
                    liq=320_000, vol24=1_400_000, age=40, pc24=12, closes=[1, 1.1, 1.05, 1.2, 1.15, 1.3, 1.25, 1.4, 1.5, 1.6],
                    vols=[200, 220, 180, 250, 230, 260, 240, 900, 1100, 1400], buyers=5200, sellers=4100,
                    holders=16_000, top_pct=[2.1, 1.9, 1.5, 1.4, 1.2, 1.1, 1.0, 0.9, 0.9, 0.8],
                    trades_buy=60, trades_sell=40),
    "MOONFROG": dict(chain="solana", address="MoonFrog111111111111111111111111111111pump", mcap=1_200_000,
                     liq=110_000, vol24=700_000, age=12, pc24=-8, closes=[1, 1.4, 1.3, 1.2, 1.1, 1.0, 1.05, 1.0, 0.95, 0.9],
                     vols=[300, 400, 350, 300, 280, 260, 250, 400, 450, 500], buyers=1900, sellers=2100,
                     holders=3_100, top_pct=[4.5, 3.2, 2.9, 2.5, 2.2, 2.0, 1.8, 1.7, 1.6, 1.5],
                     trades_buy=30, trades_sell=55),
    "RUGDOG": dict(chain="solana", address="RugDog11111111111111111111111111111111pump", mcap=2_500_000,
                   liq=150_000, vol24=900_000, age=5, pc24=40, mint=True, closes=[1] * 6 + [1.2, 1.4, 1.5, 1.7],
                   vols=[100] * 7 + [500, 700, 900], buyers=2500, sellers=2000, holders=4000,
                   top_pct=[3] * 10, trades_buy=40, trades_sell=30),
    "WASHAPE": dict(chain="solana", address="WashApe111111111111111111111111111111pump", mcap=900_000,
                    liq=90_000, vol24=2_000_000, age=9, pc24=5, closes=[1] * 10, vols=[1500] * 10,
                    buyers=20_000, sellers=20_000, traders=40_000, holders=2_000,
                    top_pct=[3] * 10, trades_buy=50, trades_sell=50),
    "BABYPUMP": dict(chain="solana", address="BabyPump11111111111111111111111111111pump", mcap=1_500_000,
                     liq=95_000, vol24=1_800_000, age=0.3, pc24=2500, closes=[1], vols=[1800], buyers=6000,
                     sellers=2000, holders=5000, top_pct=[1] * 10, trades_buy=80, trades_sell=40),
    "HONEYBEE": dict(chain="bsc", address="0x" + "be" * 20, mcap=3_000_000, liq=200_000, vol24=600_000, age=20,
                     pc24=15, honeypot=True, closes=[1 + i * 0.05 for i in range(10)], vols=[200] * 7 + [400, 500, 600],
                     buyers=900, sellers=300, holders=2500, top_pct=[2] * 10, trades_buy=40, trades_sell=5),
    "BASEBRO": dict(chain="base", address="0x" + "ba" * 20, mcap=8_000_000, liq=900_000, vol24=500_000, age=200,
                    pc24=6, closes=[1, 0.95, 0.9, 0.92, 0.95, 1.0, 1.02, 1.05, 1.1, 1.12],
                    vols=[150, 140, 160, 150, 170, 180, 200, 350, 420, 500], buyers=700, sellers=600,
                    holders=60_000, top_pct=[2.5, 2, 1.8, 1.5, 1.4, 1.3, 1.2, 1.1, 1, 1], trades_buy=35, trades_sell=30),
    "NVDAc": dict(chain="base", address="0x" + "cc" * 20, mcap=5_000_000, liq=1_000_000, vol24=9_000_000, age=30,
                  pc24=1, closes=[1] * 10, vols=[9000] * 10, buyers=3000, sellers=3000, holders=900,
                  top_pct=[5] * 10, trades_buy=10, trades_sell=10),
    "BIGDOGE": dict(chain="solana", address="BigDoge11111111111111111111111111111pump", mcap=900_000_000,
                    liq=20_000_000, vol24=50_000_000, age=700, pc24=2, closes=[1] * 10, vols=[50000] * 10,
                    buyers=9000, sellers=9000, holders=900_000, top_pct=[1] * 10, trades_buy=50, trades_sell=50),
}
PRICES = {NATIVE_TOKEN["solana"].lower(): "73.4", EURC_SOLANA.lower(): "1.16", NATIVE_TOKEN["bsc"]: "583",
          NATIVE_TOKEN["ethereum"]: "1764", NATIVE_TOKEN["base"]: "1764"}
NET_TO_CHAIN = {"solana": "solana", "bsc": "bsc", "eth": "ethereum", "base": "base"}


def _pair_addr(t: dict) -> str:
    a = t["address"]
    return ("Pool" + a[4:]) if t["chain"] == "solana" else "0x" + "11" + a[4:]


def _by_addr(addr: str) -> tuple[str, dict] | None:
    for sym, t in TOKENS.items():
        if t["address"].lower() == addr.lower() or _pair_addr(t).lower() == addr.lower():
            return sym, t
    return None


def _price(t: dict) -> float:
    return t["mcap"] / 1_000_000_000


def dex_pair(sym: str, t: dict) -> dict:
    quote = {"solana": "SOL", "bsc": "WBNB", "ethereum": "WETH", "base": "WETH"}[t["chain"]]
    return {"chainId": t["chain"], "dexId": "pumpswap" if t["chain"] == "solana" else
            ("pancakeswap" if t["chain"] == "bsc" else "aerodrome"),
            "pairAddress": _pair_addr(t), "baseToken": {"address": t["address"], "name": sym.title(), "symbol": sym},
            "quoteToken": {"symbol": quote}, "priceUsd": str(_price(t)),
            "txns": {"h24": {"buys": t["buyers"] * 2, "sells": t["sellers"] * 2}},
            "volume": {"h24": t["vol24"], "h6": t["vol24"] / 4, "h1": t["vol24"] / 24},
            "priceChange": {"h1": 1, "h6": 3, "h24": t["pc24"]}, "liquidity": {"usd": t["liq"]},
            "fdv": t["mcap"], "marketCap": t["mcap"], "pairCreatedAt": (NOW_S - t["age"] * DAY) * 1000,
            "info": {"websites": [{"url": f"https://{sym.lower()}.example"}], "socials": [{"type": "twitter",
                                                                                         "url": f"https://x.com/{sym}"}]}}


def gt_pool_attrs(t: dict) -> dict:
    traders = t.get("traders", t["buyers"] + t["sellers"])
    tx = {"buyers": t["buyers"], "sellers": t["sellers"], "unique_traders": traders,
          "buys": t["buyers"] * 2, "sells": t["sellers"] * 2}
    small = {k: v // 24 for k, v in tx.items()}
    return {"address": _pair_addr(t), "transactions": {"h1": small, "h6": {k: v // 4 for k, v in tx.items()}, "h24": tx}}


def ohlcv(t: dict) -> list:
    p = _price(t) / t["closes"][-1]
    n = len(t["closes"])
    day0 = (NOW_S // DAY) * DAY
    return [[day0 - (n - 1 - i) * DAY, c * p, c * p * 1.1, c * p * 0.9, c * p, v * 1000]
            for i, (c, v) in enumerate(zip(t["closes"], t["vols"]))]


def trades(t: dict) -> list:
    out = []
    for i in range(t["trades_buy"]):
        out.append({"kind": "buy", "volume_in_usd": "1500" if i % 10 else "6000", "tx_from_address": f"buyer{i}",
                    "block_timestamp": "2026-11-18T12:00:00Z"})
    for i in range(t["trades_sell"]):
        out.append({"kind": "sell", "volume_in_usd": "1500" if i % 10 else "6000", "tx_from_address": f"seller{i}",
                    "block_timestamp": "2026-11-18T13:00:00Z"})
    return out


def rugcheck(t: dict) -> dict:
    supply = 1_000_000_000 * 10**6
    holders = [{"owner": f"holder{i}", "address": f"acct{i}", "pct": p, "insider": False}
               for i, p in enumerate(t["top_pct"])]
    holders.insert(0, {"owner": _pair_addr(t), "address": "poolacct", "pct": 9.0})  # Pool – darf nicht zählen
    return {"mintAuthority": "DevWallet111" if t.get("mint") else None, "freezeAuthority": None,
            "score_normalised": 75 if t.get("mint") else 1, "rugged": False,
            "risks": [{"name": "Mint Authority still enabled", "level": "danger"}] if t.get("mint") else [],
            "token": {"supply": supply, "decimals": 6}, "topHolders": holders, "totalHolders": t["holders"] * 3,
            "insiderNetworks": [{"size": 4, "currentHolding": supply * 0.06}], "knownAccounts": {},
            "markets": [{"pubkey": _pair_addr(t), "lp": {"lpLockedPct": 100}}], "creatorBalance": 0,
            "transferFee": {"pct": 0}, "launchpad": {"name": "Pump.Fun"}}


def goplus(t: dict) -> dict:
    hp = t.get("honeypot")
    return {"is_honeypot": "1" if hp else "0", "buy_tax": "0", "sell_tax": "0.99" if hp else "0",
            "is_mintable": "0", "owner_address": "0x0000000000000000000000000000000000000000", "is_open_source": "1",
            "hidden_owner": "0", "can_take_back_ownership": "0", "transfer_pausable": "0", "slippage_modifiable": "0",
            "is_blacklisted": "0", "cannot_sell_all": "1" if hp else "0", "holder_count": str(t["holders"]),
            "creator_percent": "0", "lp_holders": [{"address": "0x000000000000000000000000000000000000dead",
                                                   "percent": "1", "is_locked": 0}],
            "holders": [{"address": f"0x{i:040x}", "percent": str(p / 100), "is_contract": 0}
                        for i, p in enumerate(t["top_pct"], 1)]}


def honeypot(t: dict) -> dict:
    hp = bool(t.get("honeypot"))
    return {"honeypotResult": {"isHoneypot": hp}, "summary": {"risk": "honeypot" if hp else "low", "flags": []},
            "simulationResult": {"buyTax": 0, "sellTax": 99 if hp else 0}}


def gt_info(sym: str, t: dict) -> dict:
    return {"data": {"attributes": {"holders": {"count": t["holders"], "distribution_percentage":
                                                {"top_10": str(sum(t["top_pct"]))}},
                                    "gt_score": 85.0, "developer_holding_percentage": "0.0", "twitter_handle": sym}}}


class DemoHttp:
    """Beantwortet alle API-URLs mit den fiktiven Daten oben."""

    def __init__(self):
        self.calls: list[str] = []

    def get_json(self, url: str, ttl=None):
        url = unquote(url)
        self.calls.append(url)
        if "dexscreener" in url:
            if "token-boosts/top" in url:
                return [{"chainId": t["chain"], "tokenAddress": t["address"]} for t in TOKENS.values()]
            if any(x in url for x in ("token-boosts/latest", "token-profiles", "community-takeovers")):
                return []
            m = re.search(r"/tokens/v1/[^/]+/(.+)$", url)
            if m:
                out = [dex_pair(*_by_addr(a)) for a in m.group(1).split(",") if _by_addr(a)]
                out += [{"chainId": "x", "baseToken": {"address": a}, "priceUsd": PRICES[a.lower()],
                         "liquidity": {"usd": 1e7}} for a in m.group(1).split(",") if a.lower() in PRICES]
                return out
            m = re.search(r"/latest/dex/tokens/(.+)$", url)
            if m:
                hit = _by_addr(m.group(1))
                return {"pairs": [dex_pair(*hit)] if hit else []}
        if "geckoterminal" in url:
            m = re.search(r"networks/([^/]+)/(trending_pools|pools\?page)", url)
            if m:
                ch = NET_TO_CHAIN[m.group(1)]
                return {"data": [{"relationships": {"base_token": {"data": {"id": f"{m.group(1)}_{t['address']}"}}}}
                                 for t in TOKENS.values() if t["chain"] == ch]}
            m = re.search(r"pools/multi/(.+)$", url)
            if m:
                return {"data": [{"attributes": gt_pool_attrs(_by_addr(a)[1])} for a in m.group(1).split(",") if _by_addr(a)]}
            m = re.search(r"tokens/([^/]+)/info", url)
            if m and _by_addr(m.group(1)):
                return gt_info(*_by_addr(m.group(1)))
            m = re.search(r"pools/([^/]+)/ohlcv", url)
            if m and _by_addr(m.group(1)):
                return {"data": {"attributes": {"ohlcv_list": list(reversed(ohlcv(_by_addr(m.group(1))[1])))}}}
            m = re.search(r"pools/([^/]+)/trades", url)
            if m and _by_addr(m.group(1)):
                return {"data": [{"attributes": x} for x in trades(_by_addr(m.group(1))[1])]}
        if "rugcheck" in url:
            m = re.search(r"tokens/([^/]+)/report", url)
            hit = _by_addr(m.group(1)) if m else None
            return rugcheck(hit[1]) if hit else None
        if "gopluslabs" in url:
            m = re.search(r"contract_addresses=(.+)$", url)
            res = {a.lower(): goplus(_by_addr(a)[1]) for a in m.group(1).split(",") if _by_addr(a)} if m else {}
            return {"code": 1, "result": res}
        if "honeypot.is" in url:
            m = re.search(r"address=([^&]+)", url)
            hit = _by_addr(m.group(1)) if m else None
            return honeypot(hit[1]) if hit else None
        return None


def demo_scanner(cfg=None):
    from .scanner import Scanner
    from .sources import Sources
    return Scanner(cfg, Sources(DemoHttp()), now=lambda: NOW_S)
