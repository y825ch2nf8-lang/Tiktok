"""Datenmodell für einen einzelnen Trade."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime

BUY, SELL = "BUY", "SELL"


@dataclass
class Trade:
    trader: str                 # z.B. "Berkshire Hathaway (Buffett)" oder "Jane Doe (CEO)"
    ticker: str                 # Börsenkürzel, bei 13F ggf. "CUSIP:xxxx"
    side: str                   # BUY / SELL
    trade_date: date            # Tag des Trades (bei 13F: Quartalsende)
    source: str                 # form4 | 13f | csv | demo
    shares: float | None = None
    price: float | None = None
    value: float | None = None  # USD
    filed_at: datetime | None = None   # Wann der Trade öffentlich wurde
    issuer: str = ""
    date_precision: str = "day"  # "day" oder "quarter" (13F kennt nur das Quartal)
    note: str = ""
    group: str = ""              # z.B. "Superinvestor", "Insider", "Politiker"

    @property
    def key(self) -> str:
        return f"{self.source}|{self.trader}|{self.ticker}|{self.side}|{self.trade_date}|{self.shares}|{self.price}"

    @property
    def available_date(self) -> date:
        """Ab wann man den Trade frühestens hätte kopieren können."""
        return self.filed_at.date() if self.filed_at else self.trade_date

    @property
    def filing_delay_days(self) -> int | None:
        return (self.filed_at.date() - self.trade_date).days if self.filed_at else None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trade_date"] = self.trade_date.isoformat()
        d["filed_at"] = self.filed_at.isoformat() if self.filed_at else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Trade":
        d = dict(d)
        d["trade_date"] = date.fromisoformat(d["trade_date"])
        d["filed_at"] = datetime.fromisoformat(d["filed_at"]) if d.get("filed_at") else None
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TraderConfig:
    name: str
    kind: str                    # "13f" | "form4"
    cik: str | None = None
    ticker: str | None = None    # bei form4: Firma, deren Insider beobachtet werden
    group: str = ""
    weight: float = 1.0
    extra: dict = field(default_factory=dict)
