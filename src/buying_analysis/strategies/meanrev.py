"""Mean reversion: diagnostics (variance ratio, post-dip bounce) and a long-only band swing strategy."""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.backtest import Context
from buying_analysis.strategies.timing import Allocator


def variance_ratio(log_ret: np.ndarray, q: int) -> tuple[float, float]:
    """Lo-MacKinlay variance ratio VR(q) with the heteroskedasticity-robust z* statistic.

    VR < 1 (z* < 0): q-day moves are smaller than q x 1-day moves imply, i.e. moves tend to reverse.
    """
    r = np.asarray(log_ret, float)
    r = r[~np.isnan(r)]
    t = len(r)
    mu = r.mean()
    d = r - mu
    var1 = np.sum(d**2) / (t - 1)
    qsum = np.convolve(r, np.ones(q), "valid") - q * mu
    m = q * (t - q + 1) * (1 - q / t)
    varq = np.sum(qsum**2) / m
    vr = varq / var1
    denom = np.sum(d**2) ** 2
    theta = 0.0
    for j in range(1, q):
        delta = np.sum(d[j:] ** 2 * d[:-j] ** 2) / denom
        theta += (2 * (q - j) / q) ** 2 * delta
    return float(vr), float((vr - 1) / np.sqrt(theta))


def band_z(close: np.ndarray | pd.Series, n: int) -> pd.Series:
    """z-score of log price vs its n-day mean, scaled by the n-day std of log price (row t uses <= t)."""
    lp = np.log(pd.Series(close))
    return (lp - lp.rolling(n).mean()) / lp.rolling(n).std()


def bounce(close: pd.Series, n: int = 20, threshold: float = -2.0, horizon: int = 5) -> dict:
    """Average forward log return over ``horizon`` days after z < threshold, vs all days."""
    lp = np.log(close)
    fwd = lp.shift(-horizon) - lp
    z = band_z(close, n)
    sig = fwd[z < threshold].dropna()
    allr = fwd.dropna()
    return {
        "dip_days": len(sig),
        "fwd_after_dip_bps": sig.mean() * 1e4 if len(sig) else np.nan,
        "fwd_all_bps": allr.mean() * 1e4,
        "bounce_excess_bps": (sig.mean() - allr.mean()) * 1e4 if len(sig) else np.nan,
    }


class MeanReversion(Allocator):
    """Buy when the band z-score falls below -entry; sell to cash when it rises above -exit_z (exit_z = 0
    means back at the n-day mean). New deposits wait in cash for the next entry signal."""

    def __init__(self, asset: int, n: int = 20, entry: float = 2.0, exit_z: float = 0.0):
        self.asset, self.n, self.entry, self.exit_z = asset, n, entry, exit_z
        self.assets = (asset,)
        self.name = f"meanrev_{n}d_in{entry:g}_out{exit_z:g}"

    def allocation(self, ctx: Context):
        x = ctx.close(self.asset)
        x = x[~np.isnan(x)][-(self.n + 1) :]
        if len(x) < self.n:
            return None
        lp = np.log(x[-self.n :])
        sd = lp.std(ddof=1)
        if sd <= 0:
            return None
        z = (lp[-1] - lp.mean()) / sd
        if not self.current:
            return {self.asset: 1.0} if z < -self.entry else {}
        return {} if z > -self.exit_z else {self.asset: 1.0}
