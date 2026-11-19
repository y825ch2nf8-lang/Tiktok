"""Investment-Szenarien inkl. Gebühren, Preis-Einfluss (Slippage) und Verlustfällen."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scenario:
    amount_eur: float
    invested_eur: float      # was nach Kaufkosten tatsächlich im Coin steckt
    entry_cost_pct: float
    exit_cost_pct: float
    outcomes: dict           # Label -> Endwert in € nach Verkaufskosten
    mcap_needed: dict        # Multiplikator -> benötigte Market Cap in $


def price_impact_pct(amount_usd: float, liquidity_usd: float) -> float:
    """Preis-Einfluss eines Kaufs in einem Constant-Product-Pool (x*y=k): ca. Betrag / Quote-Reserve."""
    reserve = max(liquidity_usd / 2, 1.0)
    return amount_usd / (reserve + amount_usd) * 100


def scenario(amount_eur: float, mcap_usd: float, liquidity_usd: float, costs: dict, eur_usd: float,
             multiples: list[float], network_fee_eur: float = 0.0) -> Scenario:
    impact = price_impact_pct(amount_eur * eur_usd, liquidity_usd)
    entry = costs["onramp_pct"] + costs["swap_pct"] + impact
    exit_ = costs["swap_pct"] + costs["exit_slippage_pct"] + impact  # Annahme: Liquidität wächst mit dem Kurs mit
    invested = max(amount_eur * (1 - entry / 100) - network_fee_eur, 0.0)
    outcomes = {}
    for m in multiples:
        outcomes[f"{m:g}x"] = max(invested * m * (1 - exit_ / 100) - network_fee_eur, 0.0)
    for label, m in (("−50 %", 0.5), ("−90 %", 0.1)):
        outcomes[label] = max(invested * m * (1 - exit_ / 100) - network_fee_eur, 0.0)
    outcomes["Rug-Pull"] = 0.0
    return Scenario(amount_eur, invested, entry, exit_, outcomes, {m: mcap_usd * m for m in multiples})
