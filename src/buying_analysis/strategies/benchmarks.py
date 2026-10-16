"""Benchmarks B1-B3. B1 (SPY lump sum on the same deposit schedule) is ``LumpSum(SPY)``."""

from __future__ import annotations

from buying_analysis.backtest import Context, Strategy
from buying_analysis.strategies.base import has_idle_cash, is_period_start
from buying_analysis.strategies.deployment import LumpSum

SPY, IEF = 84398, 89469


def spy_buy_and_hold() -> LumpSum:
    s = LumpSum(SPY)
    s.name = "B1_spy_buy_hold"
    return s


class FixedMix(Strategy):
    """Fixed weights, rebalanced on the first session of each period and whenever a deposit lands."""

    def __init__(
        self, weights: dict[int, float], frequency: str = "monthly", name: str = "fixed_mix"
    ):
        self.target, self.frequency, self.name = weights, frequency, name
        self.assets = tuple(weights)

    def decide(self, ctx: Context):
        if not all(ctx.tradable(p) for p in self.assets):
            return None
        if ctx.deposit_today() or is_period_start(ctx, self.frequency) or not ctx.weights():
            return dict(self.target)
        return None


def sixty_forty(frequency: str = "monthly") -> FixedMix:
    return FixedMix({SPY: 0.6, IEF: 0.4}, frequency, name=f"B2_60_40_{frequency}")


class EqualWeight(Strategy):
    """Equal weight across the universe members tradable that day, rebalanced monthly and on deposits."""

    def __init__(self, universe, frequency: str = "monthly", name: str = "B3_equal_weight"):
        self.assets, self.frequency, self.name = tuple(universe), frequency, name

    def decide(self, ctx: Context):
        live = [p for p in self.assets if ctx.tradable(p)]
        if not live:
            return None
        start = not ctx.weights() and has_idle_cash(ctx)
        if start or ctx.deposit_today() or is_period_start(ctx, self.frequency):
            return {p: 1.0 / len(live) for p in live}
        return None
