"""Statistical tests: paired block bootstrap vs a benchmark, Deflated Sharpe Ratio, Holm adjustment."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

TRADING_DAYS = 252
EULER = 0.5772156649


def _paths(r: np.ndarray, deposits: np.ndarray) -> np.ndarray:
    """Equity paths for return matrices r (B x T) with deposits at fixed positions: E_t = (E_{t-1}+D_t)(1+r_t)."""
    e = np.zeros(r.shape[0])
    for t in range(r.shape[1]):
        e = (e + deposits[t]) * (1 + r[:, t])
    return e


def block_bootstrap(
    strat: pd.DataFrame,
    bench: pd.DataFrame,
    n_boot: int = 1000,
    block: int = 21,
    seed: int = 0,
) -> dict:
    """Paired circular block bootstrap of strategy minus benchmark.

    Inputs are engine ``daily`` frames (twr_ret, deposit, rf). Days are resampled in blocks of ``block``
    sessions with the same indices for both series; deposits stay on their original days. Returns 95% CIs and
    one-sided p-values (share of resamples where the strategy does not beat the benchmark).
    """
    idx = strat.index.intersection(bench.index)
    first = idx[(strat.loc[idx, "equity"] > 0).to_numpy()][0]
    idx = idx[idx > first]
    a = strat.loc[idx, "twr_ret"].to_numpy()
    b = bench.loc[idx, "twr_ret"].to_numpy()
    rf = strat["rf"].shift(1).fillna(0.0).loc[idx].to_numpy() / TRADING_DAYS
    dep = strat.loc[idx, "deposit"].to_numpy().copy()
    dep[0] += strat.loc[first, "equity"]  # money already in the account at the start
    t = len(idx)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(t / block))
    starts = rng.integers(0, t, (n_boot, n_blocks))
    ii = ((starts[:, :, None] + np.arange(block)) % t).reshape(n_boot, -1)[:, :t]
    ra, rb, rr = a[ii], b[ii], rf[ii]
    years = t / TRADING_DAYS

    def cagr(r):
        return np.prod(1 + r, axis=1) ** (1 / years) - 1

    def sharpe(r):
        ex = r - rr
        return ex.mean(axis=1) / r.std(axis=1) * np.sqrt(TRADING_DAYS)

    fa, fb = _paths(ra, dep), _paths(rb, dep)
    d = {
        "final_value_ratio": fa / fb - 1,
        "cagr_diff": cagr(ra) - cagr(rb),
        "sharpe_diff": sharpe(ra) - sharpe(rb),
    }
    out = {}
    for k, v in d.items():
        out[f"{k}_lo"], out[f"{k}_hi"] = np.percentile(v, [2.5, 97.5])
        out[f"{k}_p"] = float((v <= 0).mean())
    return out


def deflated_sharpe(returns: pd.Series, n_trials: int, sr_variance: float) -> float:
    """Probability that the true Sharpe > 0 after selecting the best of ``n_trials`` (Bailey & Lopez de Prado).

    ``sr_variance`` is the variance of the (per-period) Sharpe ratios across all trials.
    """
    r = returns.dropna().to_numpy()
    sr = r.mean() / r.std(ddof=1)
    n = max(n_trials, 1)
    sr0 = 0.0
    if n > 1:
        sr0 = np.sqrt(sr_variance) * (
            (1 - EULER) * norm.ppf(1 - 1 / n) + EULER * norm.ppf(1 - 1 / (n * np.e))
        )
    g3, g4 = skew(r), kurtosis(r, fisher=False)
    denom = np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr**2)
    return float(norm.cdf((sr - sr0) * np.sqrt(len(r) - 1) / denom))


def holm(pvalues: pd.Series) -> pd.Series:
    """Holm-Bonferroni adjusted p-values."""
    p = pvalues.sort_values()
    m = len(p)
    adj = np.maximum.accumulate([(m - i) * v for i, v in enumerate(p.to_numpy())])
    return pd.Series(np.minimum(adj, 1.0), index=p.index).reindex(pvalues.index)
