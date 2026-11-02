"""SEC Form 4: Insider-Käufe/-Verkäufe mit exaktem Datum (Meldung binnen 2 Werktagen)."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime

from .models import BUY, SELL, Trade, TraderConfig
from .sec_client import SecClient, recent_filings, strip_ns

log = logging.getLogger(__name__)

# P = Kauf am offenen Markt, S = Verkauf am offenen Markt. Andere Codes (Optionen, Geschenke,
# Steuer-Einbehalt ...) sagen wenig über die Überzeugung aus und werden standardmäßig ignoriert.
DEFAULT_CODES = {"P": BUY, "S": SELL}


def _find(el, path: str):
    """Namespace-unabhängiges find mit '/'-Pfad."""
    cur = [el]
    for part in path.split("/"):
        nxt = []
        for c in cur:
            nxt.extend(x for x in c if strip_ns(x.tag) == part)
        cur = nxt
        if not cur:
            return None
    return cur[0]


def _val(el, path: str) -> str | None:
    node = _find(el, path)
    if node is None:
        return None
    v = _find(node, "value")
    txt = (v.text if v is not None else node.text) or ""
    return txt.strip() or None


def _num(s: str | None) -> float | None:
    try:
        return float(s) if s is not None else None
    except ValueError:
        return None


def parse_form4(xml_text: str, filed_at: datetime | None = None, group: str = "Insider",
                codes: dict[str, str] | None = None) -> list[Trade]:
    codes = codes or DEFAULT_CODES
    root = ET.fromstring(xml_text.encode() if isinstance(xml_text, str) else xml_text)
    ticker = (_val(root, "issuer/issuerTradingSymbol") or "").upper()
    issuer = _val(root, "issuer/issuerName") or ticker
    owner = _val(root, "reportingOwner/reportingOwnerId/rptOwnerName") or "Unbekannt"
    rel = _find(root, "reportingOwner/reportingOwnerRelationship")
    role = ""
    if rel is not None:
        role = _val(rel, "officerTitle") or ""
        if not role and (_val(rel, "isDirector") or "").lower() in ("1", "true"):
            role = "Director"
        if not role and (_val(rel, "isTenPercentOwner") or "").lower() in ("1", "true"):
            role = "10%-Eigentümer"
    trader = f"{owner.title()} ({role})" if role else owner.title()

    trades = []
    table = _find(root, "nonDerivativeTable")
    for tx in (table if table is not None else []):
        if strip_ns(tx.tag) != "nonDerivativeTransaction":
            continue
        code = _val(tx, "transactionCoding/transactionCode")
        if code not in codes:
            continue
        d = _val(tx, "transactionDate")
        if not d:
            continue
        shares = _num(_val(tx, "transactionAmounts/transactionShares"))
        price = _num(_val(tx, "transactionAmounts/transactionPricePerShare"))
        trades.append(Trade(
            trader=trader, ticker=ticker, side=codes[code], trade_date=date.fromisoformat(d[:10]),
            source="form4", shares=shares, price=price,
            value=(shares * price) if shares and price else None,
            filed_at=filed_at, issuer=issuer, group=group, note=f"Code {code}",
        ))
    return trades


def _parse_acceptance(s: str | None) -> datetime | None:
    if not s:
        return None
    try:  # EDGAR liefert z.B. "2024-05-01T16:05:12.000Z" (Uhrzeit = US-Ostküste laut EDGAR)
        return datetime.fromisoformat(s.replace("Z", "")[:19])
    except ValueError:
        return None


def fetch_form4(client: SecClient, cfg: TraderConfig, since: date, max_filings: int = 200) -> list[Trade]:
    cik = cfg.cik or client.ticker_to_cik(cfg.ticker)
    subs = client.submissions(cik)
    filings = [f for f in recent_filings(subs, {"4"}) if f["filingDate"] >= since.isoformat()][:max_filings]
    out: list[Trade] = []
    for f in filings:
        acc = f["accessionNumber"].replace("-", "")
        doc = f["primaryDocument"].split("/")[-1]  # "xslF345X05/form4.xml" -> Roh-XML "form4.xml"
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}"
        try:
            ts = client.get_text(url)
            out.extend(parse_form4(ts, _parse_acceptance(f.get("acceptanceDateTime")), cfg.group or "Insider"))
        except Exception as e:  # einzelne kaputte Filings überspringen
            log.warning("Form 4 %s übersprungen: %s", url, e)
    if cfg.ticker:  # nur Trades in der beobachteten Firma
        out = [t for t in out if t.ticker == cfg.ticker.upper()] or out
    return out
