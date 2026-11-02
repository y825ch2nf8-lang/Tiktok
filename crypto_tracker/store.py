"""Ablage auf der Festplatte: Watchlist, Fills pro Trader, Positions-Snapshot."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import Fill, Position, TraderInfo


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        (self.root / "fills").mkdir(parents=True, exist_ok=True)

    # Watchlist
    def save_watchlist(self, traders: list[TraderInfo]):
        (self.root / "watchlist.json").write_text(json.dumps([asdict(t) for t in traders], indent=1))

    def watchlist(self) -> list[TraderInfo]:
        p = self.root / "watchlist.json"
        return [TraderInfo(**d) for d in json.loads(p.read_text())] if p.exists() else []

    # Fills
    def _fp(self, addr: str) -> Path:
        return self.root / "fills" / f"{addr.lower()}.json"

    def fills(self, addr: str) -> list[Fill]:
        p = self._fp(addr)
        return [Fill.from_dict(d) for d in json.loads(p.read_text())] if p.exists() else []

    def merge_fills(self, addr: str, new: list[Fill]) -> int:
        cur = {f.key: f for f in self.fills(addr)}
        before = len(cur)
        cur.update({f.key: f for f in new})
        self._fp(addr).write_text(json.dumps([f.to_dict() for f in sorted(cur.values(), key=lambda f: f.time)]))
        return len(cur) - before

    def all_fills(self, addrs: list[str]) -> dict[str, list[Fill]]:
        return {a: self.fills(a) for a in addrs}

    # Positionen
    def save_positions(self, positions: list[Position]):
        (self.root / "positions.json").write_text(json.dumps(
            {"time": datetime.now(timezone.utc).isoformat(), "positions": [asdict(p) for p in positions]}, indent=1))

    def positions(self) -> tuple[str | None, list[Position]]:
        p = self.root / "positions.json"
        if not p.exists():
            return None, []
        d = json.loads(p.read_text())
        return d["time"], [Position(**x) for x in d["positions"]]
