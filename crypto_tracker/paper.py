"""Paper-Trading: kopiert die Top-Trader mit SPIELGELD. Es wird nie echtes Geld bewegt."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import CLOSE_LONG, CLOSES, OPEN_LONG, OPENS, Order, fmt_px


class PaperBook:
    def __init__(self, path: Path, size_usd: float = 100.0, fee_rate: float = 0.00045):
        self.path = Path(path)
        self.size_usd = size_usd
        self.fee_rate = fee_rate   # Taker-Gebühr je Seite (Annahme)
        d = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.open: dict[str, dict] = d.get("open", {})
        self.closed: list[dict] = d.get("closed", [])

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"open": self.open, "closed": self.closed}, indent=1))

    def on_order(self, o: Order, name: str, mids: dict[str, float]) -> str | None:
        px = mids.get(o.coin) or o.px
        key = f"{o.trader}|{o.coin}"
        now = datetime.now(timezone.utc).isoformat()
        if o.action in OPENS and key not in self.open:
            d = 1 if o.action == OPEN_LONG else -1
            self.open[key] = {"trader": name, "coin": o.coin, "dir": d, "entry": px, "size_usd": self.size_usd, "opened": now}
            return f"📝 Paper: {'LONG' if d > 0 else 'SHORT'} {o.coin} @ {fmt_px(px)} kopiert ({self.size_usd:.0f} $)"
        if o.action in CLOSES and key in self.open:
            pos = self.open[key]
            if (pos["dir"] > 0) != (o.action == CLOSE_LONG):
                return None
            self.open.pop(key)
            pnl = self._pnl(pos, px) - 2 * self.fee_rate * pos["size_usd"]
            self.closed.append({**pos, "exit": px, "closed": now, "pnl": pnl})
            return f"📝 Paper: {pos['coin']} geschlossen @ {fmt_px(px)} → {pnl:+.2f} $"
        return None

    @staticmethod
    def _pnl(pos: dict, px: float) -> float:
        return pos["dir"] * (px / pos["entry"] - 1) * pos["size_usd"]

    def summary(self, mids: dict[str, float]) -> dict:
        realized = sum(c["pnl"] for c in self.closed)
        unreal = sum(self._pnl(p, mids.get(p["coin"], p["entry"])) for p in self.open.values())
        wins = sum(c["pnl"] > 0 for c in self.closed)
        return {"open": len(self.open), "closed": len(self.closed), "realized": realized, "unrealized": unreal,
                "win_rate": wins / len(self.closed) if self.closed else None}
