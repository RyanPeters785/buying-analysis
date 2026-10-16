"""Tables for the report: summaries with bootstrap stats, regimes, calendar years, markdown output."""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.metrics import summarize
from buying_analysis.stats import block_bootstrap, deflated_sharpe, holm

REGIMES = {
    "1993-99 bull": ("1993-01-01", "1999-12-31"),
    "2000-02 dot-com bust": ("2000-01-01", "2002-12-31"),
    "2003-07 recovery": ("2003-01-01", "2007-12-31"),
    "2008-09 GFC": ("2008-01-01", "2009-12-31"),
    "2010-19": ("2010-01-01", "2019-12-31"),
    "2020-22": ("2020-01-01", "2022-12-31"),
}
KF_REGIMES = {
    "1927-29 boom": ("1927-01-01", "1929-08-31"),
    "1929-32 crash": ("1929-09-01", "1932-06-30"),
    "1932-45": ("1932-07-01", "1945-12-31"),
    "1946-65": ("1946-01-01", "1965-12-31"),
    "1966-81 stagflation": ("1966-01-01", "1981-12-31"),
    "1982-99 bull": ("1982-01-01", "1999-12-31"),
    "2000-09 lost decade": ("2000-01-01", "2009-12-31"),
    "2010-22": ("2010-01-01", "2022-12-31"),
}
MAIN_COLS = [
    "strategy", "start", "final_value", "b1_final", "xirr", "b1_xirr", "cagr_twr", "sharpe", "b1_sharpe",
    "max_drawdown", "time_in_market", "n_trades", "total_costs",
]  # fmt: skip


def twr(res) -> pd.Series:
    d = res.daily
    first = d.index[d["equity"] > 0][0]
    return d.loc[d.index > first, "twr_ret"]


def excess_vs(res, b1_res) -> pd.Series:
    """Daily TWR return minus the benchmark's on the same sessions (the series DSR is computed on)."""
    a, b = twr(res), twr(b1_res)
    idx = a.index.intersection(b.index)
    return a[idx] - b[idx]


def compare(res, b1_res, n_family: int, sr_var: float, n_boot: int = 1000) -> dict:
    """Summary metrics + paired bootstrap vs B1 + Deflated Sharpe of the excess over B1.

    DSR here = probability that the strategy's true Sharpe *relative to SPY* (information ratio) is > 0,
    after selecting among ``n_family`` trials. A plain DSR on absolute returns is ~1 for any equity
    strategy over 30 years and says nothing about beating SPY.
    """
    m = summarize(res)
    b = summarize(b1_res)
    out = {**m, "b1_final": b["final_value"], "b1_xirr": b["xirr"], "b1_sharpe": b["sharpe"]}
    out |= block_bootstrap(res.daily, b1_res.daily, n_boot=n_boot)
    ex = excess_vs(res, b1_res)
    out["dsr_vs_b1"] = deflated_sharpe(ex, n_family, sr_var) if ex.std() > 0 else np.nan
    return out


def daily_ir(res, b1_res) -> float:
    ex = excess_vs(res, b1_res)
    return float(ex.mean() / ex.std()) if ex.std() > 0 else 0.0


def family_table(pairs: list[tuple], n_boot: int = 1000) -> pd.DataFrame:
    """pairs = [(result, b1_result, extra_dict)]; DSR uses the family size and its IR variance."""
    srs = [daily_ir(r, b) for r, b, _ in pairs]
    var = float(np.var(srs, ddof=1)) if len(srs) > 1 else 0.0
    rows = [{**compare(r, b, len(pairs), var, n_boot), **x} for r, b, x in pairs]
    return pd.DataFrame(rows)


def add_holm(df: pd.DataFrame, col: str = "final_value_ratio_p") -> pd.DataFrame:
    df = df.copy()
    df[col + "_holm"] = holm(df[col]).to_numpy()
    return df


def period_returns(results: dict, periods: dict) -> pd.DataFrame:
    """Annualized TWR return of each strategy in each period (from its continuous run)."""
    rows = {}
    for name, res in results.items():
        r = twr(res)
        row = {}
        for p, (a, b) in periods.items():
            x = r[(r.index >= a) & (r.index <= b)]
            yrs = len(x) / 252
            row[p] = (np.prod(1 + x) ** (1 / yrs) - 1) if yrs >= 0.5 else np.nan
        rows[name] = row
    return pd.DataFrame(rows).T


def calendar_returns(results: dict) -> pd.DataFrame:
    out = {}
    for name, res in results.items():
        r = twr(res)
        out[name] = (1 + r).groupby(r.index.year).prod() - 1
    return pd.DataFrame(out)


def fmt_table(df: pd.DataFrame, pct=(), money=(), dec2=(), ints=()) -> str:
    """Markdown table with readable number formats."""
    d = df.copy()
    for c in d.columns:
        if c in pct:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v * 100:.1f}%")
        elif c in money:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"${v / 1000:,.0f}k")
        elif c in dec2:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
        elif c in ints:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{int(v):,}")
    return d.to_markdown(index=False)
