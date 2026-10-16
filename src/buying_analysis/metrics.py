"""Performance metrics from an engine Result. Time-weighted metrics use daily TWR returns (deposits removed);
money-weighted return is XIRR over the actual deposits and the final value."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def xirr(dates, flows) -> float:
    """Annual IRR of dated cash flows (negative = money in). Bisection on the NPV, robust to bad guesses."""
    t = (pd.DatetimeIndex(dates) - pd.Timestamp(dates[0])).days.to_numpy() / 365.0
    f = np.asarray(flows, float)

    def npv(r):
        return np.sum(f / (1.0 + r) ** t)

    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return np.nan
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def drawdown(index: pd.Series) -> pd.Series:
    return index / index.cummax() - 1.0


def longest_drawdown_days(index: pd.Series) -> int:
    """Longest stretch (calendar days) spent below a prior peak."""
    under = index < index.cummax()
    longest, start = 0, None
    for d, u in under.items():
        if u and start is None:
            start = d
        elif not u and start is not None:
            longest = max(longest, (d - start).days)
            start = None
    if start is not None:
        longest = max(longest, (index.index[-1] - start).days)
    return longest


def summarize(res, rf_annual: pd.Series | None = None) -> dict:
    d = res.daily
    r = d["twr_ret"]
    # start measuring once money is in the account
    first = d.index[d["equity"] > 0][0]
    r = r[r.index > first]
    idx = (1 + r).cumprod()
    years = (r.index[-1] - first).days / 365.25
    rf = (
        d["rf"].fillna(0.0) if rf_annual is None else rf_annual.reindex(d.index).fillna(0.0)
    ).shift(1)
    rf_daily = (rf[r.index].fillna(0.0)) / TRADING_DAYS
    ex = r - rf_daily
    vol = r.std() * np.sqrt(TRADING_DAYS)
    downside = ex.clip(upper=0)
    sortino_den = np.sqrt((downside**2).mean()) * np.sqrt(TRADING_DAYS)
    cagr = idx.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    mdd = drawdown(idx).min()
    deps = d.loc[d["deposit"] > 0, "deposit"]
    flows_dates = list(deps.index) + [d.index[-1]]
    flows = list(-deps.values) + [d["equity"].iloc[-1]]
    invested_frac = (d["invested"] / d["equity"]).where(d["equity"] > 0)
    tr = res.trades
    traded = tr.loc[tr["side"].isin(["buy", "sell"]), "value"].sum() if len(tr) else 0.0
    avg_eq = d.loc[d.index >= first, "equity"].mean()
    return {
        "strategy": res.name,
        "start": first.date(),
        "end": d.index[-1].date(),
        "years": round(years, 2),
        "total_deposits": deps.sum(),
        "final_value": d["equity"].iloc[-1],
        "xirr": xirr(flows_dates, flows),
        "cagr_twr": cagr,
        "ann_vol": vol,
        "sharpe": ex.mean() / r.std() * np.sqrt(TRADING_DAYS) if r.std() > 0 else np.nan,
        "sortino": ex.mean() * TRADING_DAYS / sortino_den if sortino_den > 0 else np.nan,
        "max_drawdown": mdd,
        "longest_dd_days": longest_drawdown_days(idx),
        "calmar": cagr / -mdd if mdd < 0 else np.nan,
        "time_in_market": invested_frac[invested_frac.index > first].mean(),
        "n_trades": int(tr["side"].isin(["buy", "sell"]).sum()) if len(tr) else 0,
        "turnover_per_yr": traded / avg_eq / years if years > 0 and avg_eq > 0 else np.nan,
        "total_costs": d["costs"].sum(),
    }
