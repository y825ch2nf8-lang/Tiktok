"""Einfacher JSON-Speicher mit Duplikat-Erkennung."""
from __future__ import annotations

import json
from pathlib import Path

from .models import Trade


class TradeStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[Trade]:
        if not self.path.exists():
            return []
        return [Trade.from_dict(d) for d in json.loads(self.path.read_text(encoding="utf-8"))]

    def save(self, trades: list[Trade]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        trades = sorted(trades, key=lambda t: (t.trade_date, t.trader, t.ticker))
        self.path.write_text(json.dumps([t.to_dict() for t in trades], indent=1, ensure_ascii=False), encoding="utf-8")

    def merge(self, new: list[Trade]) -> int:
        existing = {t.key: t for t in self.load()}
        added = 0
        for t in new:
            if t.key not in existing:
                existing[t.key] = t
                added += 1
        self.save(list(existing.values()))
        return added
