"""Buy the dip: hold each deposit in cash until the asset is X% below its trailing 52-week high, then invest
all idle cash; if that does not happen within ``max_wait_months`` of the oldest waiting deposit, invest anyway.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.backtest import Context, Strategy
from buying_analysis.strategies.base import has_idle_cash

WEEKS_52 = 252  # sessions


class BuyTheDip(Strategy):
    def __init__(self, asset: int, dip: float = 0.10, max_wait_months: int = 6):
        self.asset, self.dip, self.max_wait = asset, dip, max_wait_months
        self.assets = (asset,)
        self.name = f"dip_{int(dip * 100)}pct_{max_wait_months}m"

    def reset(self):
        self.waiting_since: pd.Timestamp | None = None

    def decide(self, ctx: Context):
        if not (has_idle_cash(ctx) and ctx.tradable(self.asset)):
            self.waiting_since = None if not has_idle_cash(ctx) else self.waiting_since
            return None
        if self.waiting_since is None:
            self.waiting_since = ctx.date
        x = ctx.close(self.asset)[-WEEKS_52:]
        high = np.nanmax(x)
        in_dip = x[-1] <= (1 - self.dip) * high
        timed_out = ctx.date >= self.waiting_since + pd.DateOffset(months=self.max_wait)
        if in_dip or timed_out:
            self.waiting_since = None
            return {self.asset: 1.0}
        return None
