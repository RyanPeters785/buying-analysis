"""Null baselines for timing strategies.

N1 ExposureMatched: hold SPY at a constant weight equal to the strategy's average time in market.
N2 RandomTiming: random in/out schedules with the same number of in-market spells and in-market days as the
   strategy (the schedule is fixed before the run; it uses no market data).
For sector rotation the matching null is RandomSectors: k random sector ETFs each month.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.strategies.benchmarks import FixedMix
from buying_analysis.strategies.timing import SECTORS, Allocator, SectorRotation


def exposure_matched(asset: int, exposure: float, name: str = "N1_exposure_matched") -> FixedMix:
    return FixedMix({asset: float(np.clip(exposure, 0, 1))}, "monthly", name=name)


def in_market_spells(weights: pd.Series, threshold: float = 0.5) -> tuple[int, int, int]:
    """(#spells, #in-market days, #days) of a daily weight series."""
    on = (weights.fillna(0) > threshold).to_numpy()
    spells = int(on[0]) + int(np.sum(on[1:] & ~on[:-1]))
    return spells, int(on.sum()), len(on)


def random_schedule(n_days: int, n_in: int, n_spells: int, rng: np.random.Generator) -> np.ndarray:
    """Boolean in-market schedule with exactly ``n_in`` days in ``n_spells`` spells, placed uniformly."""
    if n_spells == 0 or n_in == 0:
        return np.zeros(n_days, bool)
    n_spells = min(n_spells, n_in, n_days - n_in + 1)
    on_len = _composition(n_in, n_spells, rng, positive=True)
    gaps = _composition(n_days - n_in, n_spells + 1, rng, positive=False, interior_positive=True)
    out = np.zeros(n_days, bool)
    pos = gaps[0]
    for k in range(n_spells):
        out[pos : pos + on_len[k]] = True
        pos += on_len[k] + gaps[k + 1]
    return out


def _composition(total, parts, rng, positive, interior_positive=False):
    """Random split of ``total`` into ``parts`` integers (>=1 if positive; interior parts >=1 if asked)."""
    if positive:
        cuts = (
            np.sort(rng.choice(np.arange(1, total), parts - 1, replace=False)) if parts > 1 else []
        )
        return np.diff(np.r_[0, cuts, total]).astype(int)
    reserve = max(parts - 2, 0) if interior_positive else 0
    free = total - reserve
    cuts = np.sort(rng.integers(0, free + 1, parts - 1))
    sizes = np.diff(np.r_[0, cuts, free]).astype(int)
    if interior_positive:
        sizes[1:-1] += 1
    return sizes


class RandomTiming(Allocator):
    """Follows a pre-drawn in/out schedule for ``asset`` (indexed by session)."""

    def __init__(self, asset: int, schedule: pd.Series, seed: int):
        self.asset, self.schedule = asset, schedule
        self.assets = (asset,)
        self.name = f"N2_random_{seed}"

    def allocation(self, ctx):
        on = bool(self.schedule.get(ctx.date, False))
        return {self.asset: 1.0} if on else {}


class RandomSectors(SectorRotation):
    """Null for sector rotation: k random sector ETFs (among those eligible) each month."""

    def __init__(self, k: int = 3, seed: int = 0, universe=SECTORS):
        super().__init__(k=k, universe=universe)
        self.seed = seed
        self.name = f"N2_random_sectors_{seed}"

    def reset(self):
        super().reset()
        self.rng = np.random.default_rng(self.seed)

    def allocation(self, ctx):
        sc = self.scores(ctx)  # same eligibility as the real strategy
        if len(sc) < self.k:
            return None
        pick = self.rng.choice(sorted(sc), self.k, replace=False)
        return {int(p): 1.0 / self.k for p in pick}
