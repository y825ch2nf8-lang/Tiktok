"""Import beliebiger Trades aus CSV (z.B. Politiker-Trades von Capitol Trades / Quiver-Export,
oder eigene Listen). Pflichtspalten: trader, ticker, side, trade_date
Optional: shares, price, value, filed_at, issuer, group, note
side akzeptiert: BUY/SELL, Kauf/Verkauf, purchase/sale, P/S
"""
from __future__ import annotations

import csv
import re
from datetime import date, datetime
from pathlib import Path

from .models import BUY, SELL, Trade

_SIDE = {"buy": BUY, "kauf": BUY, "purchase": BUY, "p": BUY, "b": BUY,
         "sell": SELL, "verkauf": SELL, "sale": SELL, "s": SELL, "sale (full)": SELL, "sale (partial)": SELL}


def _num(s):
    if s in (None, ""):
        return None
    s = re.sub(r"[^\d.\-]", "", str(s))
    return float(s) if s else None


def _date(s) -> date:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return date.fromisoformat(s[:10])


def import_csv(path: Path, default_group: str = "Import") -> list[Trade]:
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            side = _SIDE.get(row.get("side", "").lower())
            if not side or not row.get("ticker"):
                continue
            filed = row.get("filed_at")
            out.append(Trade(
                trader=row.get("trader", "Unbekannt"), ticker=row["ticker"].upper(), side=side,
                trade_date=_date(row["trade_date"]), source="csv",
                shares=_num(row.get("shares")), price=_num(row.get("price")), value=_num(row.get("value")),
                filed_at=datetime.combine(_date(filed), datetime.min.time()) if filed else None,
                issuer=row.get("issuer", ""), group=row.get("group") or default_group, note=row.get("note", ""),
            ))
    return out
