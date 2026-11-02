"""SEC 13F: Quartalsweise Depots großer Fonds (Buffett, Burry, Ackman ...).

Achtung: 13F zeigt nur den Bestand am Quartalsende und wird bis zu 45 Tage später
veröffentlicht. Käufe/Verkäufe werden aus der Differenz zweier Quartale abgeleitet –
das genaue Handelsdatum ist NICHT bekannt (date_precision="quarter").
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime

from .models import BUY, SELL, Trade, TraderConfig
from .sec_client import SecClient, recent_filings, strip_ns

log = logging.getLogger(__name__)


@dataclass
class Holding:
    key: str
    name: str
    cusip: str
    shares: float
    value: float


def parse_info_table(xml_text: str) -> dict[str, Holding]:
    root = ET.fromstring(xml_text.encode() if isinstance(xml_text, str) else xml_text)
    out: dict[str, Holding] = {}
    for row in root.iter():
        if strip_ns(row.tag) != "infoTable":
            continue
        f = {}
        for child in row.iter():
            t = strip_ns(child.tag)
            if child.text and child.text.strip():
                f[t] = child.text.strip()
        cusip = f.get("cusip", "")
        put_call = f.get("putCall", "")
        key = cusip + (f"-{put_call.upper()}" if put_call else "")
        shares = float(f.get("sshPrnamt", 0) or 0)
        value = float(f.get("value", 0) or 0)
        if key in out:  # gleiche Aktie in mehreren Zeilen (Unter-Manager) zusammenfassen
            out[key].shares += shares
            out[key].value += value
        else:
            name = f.get("nameOfIssuer", cusip) + (f" ({put_call})" if put_call else "")
            out[key] = Holding(key, name, cusip, shares, value)
    return out


def diff_holdings(prev: dict[str, Holding], cur: dict[str, Holding], trader: str, period: date,
                  filed_at: datetime | None, group: str, min_change: float = 0.05,
                  cusip_map: dict[str, str] | None = None) -> list[Trade]:
    cusip_map = cusip_map or {}
    trades = []

    def mk(h: Holding, side: str, shares: float, value: float, note: str):
        trades.append(Trade(trader=trader, ticker=cusip_map.get(h.cusip, f"CUSIP:{h.cusip}"), side=side,
                            trade_date=period, source="13f", shares=shares, value=value, filed_at=filed_at,
                            issuer=h.name, date_precision="quarter", note=note, group=group,
                            price=(value / shares) if shares else None))

    for k, h in cur.items():
        p = prev.get(k)
        if p is None or p.shares == 0:
            mk(h, BUY, h.shares, h.value, "Neue Position")
        else:
            ch = (h.shares - p.shares) / p.shares
            px = h.value / h.shares if h.shares else 0
            if ch >= min_change:
                mk(h, BUY, h.shares - p.shares, (h.shares - p.shares) * px, f"Aufgestockt +{ch:.0%}")
            elif ch <= -min_change:
                mk(h, SELL, p.shares - h.shares, (p.shares - h.shares) * px, f"Reduziert {ch:.0%}")
    for k, p in prev.items():
        if k not in cur:
            mk(p, SELL, p.shares, p.value, "Komplett verkauft")
    return trades


def _info_table_url(client: SecClient, cik: str, filing: dict) -> str | None:
    acc = filing["accessionNumber"].replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}"
    idx = client.get_json(f"{base}/index.json")
    primary = filing.get("primaryDocument", "").split("/")[-1].lower()
    xmls = [i["name"] for i in idx.get("directory", {}).get("item", [])
            if i["name"].lower().endswith(".xml") and i["name"].lower() != primary]
    xmls.sort(key=lambda n: 0 if ("info" in n.lower() or "table" in n.lower()) else 1)
    return f"{base}/{xmls[0]}" if xmls else None


def fetch_13f(client: SecClient, cfg: TraderConfig, quarters: int = 8) -> list[Trade]:
    subs = client.submissions(cfg.cik)
    filings = recent_filings(subs, {"13F-HR"})
    # pro Berichtsperiode nur die neueste Meldung
    by_period: dict[str, dict] = {}
    for f in filings:
        per = f.get("reportDate") or f["filingDate"]
        if per not in by_period or f["filingDate"] > by_period[per]["filingDate"]:
            by_period[per] = f
    periods = sorted(by_period)[-(quarters + 1):]
    snapshots = []
    for per in periods:
        f = by_period[per]
        try:
            url = _info_table_url(client, cfg.cik, f)
            if not url:
                continue
            filed = datetime.fromisoformat(f["filingDate"])
            snapshots.append((date.fromisoformat(per), filed, parse_info_table(client.get_text(url))))
        except Exception as e:
            log.warning("13F %s %s übersprungen: %s", cfg.name, per, e)
    trades = []
    for (_, _, prev), (per, filed, cur) in zip(snapshots, snapshots[1:]):
        trades += diff_holdings(prev, cur, cfg.name, per, filed, cfg.group or "Superinvestor",
                                cusip_map=cfg.extra.get("cusip_map"))
    return trades
