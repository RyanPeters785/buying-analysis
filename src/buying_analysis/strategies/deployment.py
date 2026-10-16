"""How new cash is deployed into one asset: lump sum and dollar-cost averaging."""

from __future__ import annotations

import pandas as pd

from buying_analysis.backtest import Context, Strategy
from buying_analysis.strategies.base import has_idle_cash, horizon_end, is_period_start

PERIOD_FREQ = {"monthly": "M", "weekly": "W", "annual": "Y"}


class LumpSum(Strategy):
    """Invest all available cash in ``asset`` as soon as it arrives, then hold."""

    def __init__(self, asset: int, label: str = ""):
        self.asset = asset
        self.assets = (asset,)
        self.name = f"lump_sum{label}"

    def decide(self, ctx: Context):
        if has_idle_cash(ctx) and ctx.tradable(self.asset):
            return {self.asset: 1.0}
        return None


class DCA(Strategy):
    """Deploy each deposit in equal tranches on the first session of each period until the next deposit.

    Tranche = cash / (periods left before the deposit horizon), so the deposit is fully invested by the last
    period. Uninvested cash earns the money-market yield in the meantime.
    """

    def __init__(self, asset: int, frequency: str = "monthly", default_horizon_days: int = 365):
        self.asset, self.frequency = asset, frequency
        self.assets = (asset,)
        self.default_horizon_days = default_horizon_days
        self.name = f"dca_{frequency}"

    def decide(self, ctx: Context):
        if not (has_idle_cash(ctx) and ctx.tradable(self.asset)):
            return None
        if not (is_period_start(ctx, self.frequency) or ctx.deposit_today()):
            return None
        end = horizon_end(ctx, self.default_horizon_days) - pd.Timedelta(days=1)
        f = PERIOD_FREQ[self.frequency]
        left = max(len(pd.period_range(ctx.date.to_period(f), end.to_period(f), freq=f)), 1)
        tranche = ctx.cash / left
        return {self.asset: min(ctx.weight(self.asset) + tranche / ctx.equity, 1.0)}
