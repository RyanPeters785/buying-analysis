"""Trading costs and cash yield. Applied by the engine only, never by strategies."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CostModel:
    commission: float = 0.0
    spread_bps_etf: float = 2.0
    spread_bps_stock: float = 5.0
    spread_multiplier: float = 1.0
    sec_fee_rate: float = 0.0000278
    finra_taf_per_share: float = 0.000166
    finra_taf_cap: float = 8.30
    mmf_expense: float = 0.0010

    @classmethod
    def from_config(cls, cfg: dict) -> CostModel:
        return cls(**cfg)

    def spreads(self, is_etf: np.ndarray) -> np.ndarray:
        """Per-side spread (fraction) for each asset."""
        bps = np.where(is_etf, self.spread_bps_etf, self.spread_bps_stock) * self.spread_multiplier
        return bps / 1e4

    def sell_fees(self, notional: float, shares: float) -> float:
        """SEC Section 31 + FINRA TAF on one sell."""
        taf = min(self.finra_taf_per_share * shares, self.finra_taf_cap)
        return self.sec_fee_rate * notional + taf

    def cash_growth(self, rf_annual: float, days: int) -> float:
        """Growth factor of money-market cash over ``days`` calendar days (yield floored at 0)."""
        y = max((0.0 if np.isnan(rf_annual) else rf_annual) - self.mmf_expense, 0.0)
        return 1.0 + y * days / 365.0
