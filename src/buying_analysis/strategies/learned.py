"""Learned long/flat swing model (strategy 9).

Features at session t use closes through t only. Label for sample t: did the asset rise from the open of
t+1 to the open of t+1+k (the holding period a signal at t's close actually gets)? Walk-forward: on the first
session of each year the model is refit on every sample whose label is already known (t + 1 + k <= today),
i.e. the k most recent samples are purged. Scaling is part of the pipeline, so it is fit on training data only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from buying_analysis.backtest import Context
from buying_analysis.strategies.base import is_period_start
from buying_analysis.strategies.timing import SPY, Allocator

LOOKBACK = 300  # sessions of history needed for one feature row (52-week windows + slack)
FEATURES = [
    "ret_1", "ret_5", "ret_21", "ret_63", "ret_126", "ret_252",
    "ma_20", "ma_50", "ma_200", "rsi_2", "rsi_14", "vol_21", "vol_63", "from_high", "from_low",
]  # fmt: skip


def _rsi_simple(x: pd.Series, n: int) -> pd.Series:
    """Cutler RSI (simple rolling means), so each value depends only on the last n+1 closes."""
    d = x.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d).clip(lower=0).rolling(n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def features(close: np.ndarray) -> pd.DataFrame:
    """Feature rows for every session; row t depends on close[: t + 1] only (rolling windows <= 253)."""
    x = pd.Series(close)
    lr = np.log(x).diff()
    f = {f"ret_{n}": x / x.shift(n) - 1 for n in (1, 5, 21, 63, 126, 252)}
    f |= {f"ma_{n}": x / x.rolling(n).mean() - 1 for n in (20, 50, 200)}
    f |= {"rsi_2": _rsi_simple(x, 2), "rsi_14": _rsi_simple(x, 14)}
    f |= {f"vol_{n}": lr.rolling(n).std() * np.sqrt(252) for n in (21, 63)}
    f |= {"from_high": x / x.rolling(252).max() - 1, "from_low": x / x.rolling(252).min() - 1}
    return pd.DataFrame(f)[FEATURES]


def labels(open_idx: np.ndarray, k: int) -> np.ndarray:
    """y[t] = 1 if open[t+1+k] > open[t+1]; NaN where not yet observable."""
    o = pd.Series(open_idx)
    return (
        (o.shift(-(1 + k)) / o.shift(-1) > 1)
        .astype(float)
        .where(o.shift(-(1 + k)).notna())
        .to_numpy()
    )


def training_rows(n_known: int, k: int) -> int:
    """Samples t < n_known - 1 - k have labels fully observed by session n_known - 1 (purge k + 1 rows)."""
    return max(n_known - 1 - k, 0)


class SwingModel(Allocator):
    def __init__(self, asset: int = SPY, k: int = 5, threshold: float = 0.5, C: float = 1.0,
                 min_train_years: float = 3.0):  # fmt: skip
        self.asset, self.k, self.threshold, self.C = asset, k, threshold, C
        self.min_train = int(min_train_years * 252)
        self.assets = (asset,)
        self.name = f"swing_lr_k{k}_p{int(threshold * 100)}_C{C:g}"

    def reset(self):
        super().reset()
        self.model = None
        self.trained_through = None

    def _fit(self, ctx: Context) -> None:
        close, opn = ctx.close(self.asset), ctx.open(self.asset)
        ok = ~np.isnan(close)
        X = features(close[ok])
        y = labels(opn[ok], self.k)
        n = training_rows(len(X), self.k)
        X, y = X.iloc[:n], y[:n]
        good = X.notna().all(axis=1).to_numpy() & ~np.isnan(y)
        if good.sum() < self.min_train:
            return
        self.model = make_pipeline(StandardScaler(), LogisticRegression(C=self.C, max_iter=1000))
        self.model.fit(X[good].to_numpy(), y[good].astype(int))
        self.trained_through = ctx.date

    def prob_up(self, ctx: Context) -> float:
        x = ctx.close(self.asset)[-LOOKBACK:]
        row = features(x[~np.isnan(x)]).iloc[[-1]]
        if row.isna().any(axis=None):
            return np.nan
        return float(self.model.predict_proba(row.to_numpy())[0, 1])

    def allocation(self, ctx: Context):
        if self.model is None or is_period_start(ctx, "annual"):
            self._fit(ctx)
        if self.model is None:
            return None
        p = self.prob_up(ctx)
        if np.isnan(p):
            return None
        return {self.asset: 1.0} if p > self.threshold else {}
