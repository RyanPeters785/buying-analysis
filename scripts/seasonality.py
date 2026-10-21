"""Seasonality: average return by calendar month, the average path through the year, and "Sell in May".

- Monthly excess returns (market minus T-bills, Ken French month-end data) by calendar month, 1927-2022,
  split 1927-1974 / 1975-2022 for stability; 95% CIs; Holm adjustment across the 12 months
- Average detrended path through the year (daily, cumulative excess return minus the period's average
  drift): where the market typically sits relative to its normal trend on each day of the year
- Strategy: stocks Nov-Apr, T-bills May-Oct ("Sell in May" / Halloween) vs buy-and-hold, $5,000 each
  January, 1927-2022; 2023-2025 descriptive

  uv run scripts/seasonality.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as tdist

sys.path.insert(0, str(Path(__file__).parent))
from cape_timing import monthly_returns, simulate, stats

from buying_analysis import plots
from buying_analysis.data import RAW_DIR, ROOT, load_prices, rf_daily
from buying_analysis.experiments import log_trials
from buying_analysis.report import fmt_table
from buying_analysis.stats import holm

OUT = ROOT / "outputs" / "seasonality"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WINTER = {11, 12, 1, 2, 3, 4}
PERIODS = {"1927-1974": ("1927", "1974"), "1975-2022": ("1975", "2022")}
SPY = 84398


def by_month(ex: pd.Series) -> pd.DataFrame:
    g = ex.groupby(ex.index.month)
    out = pd.DataFrame({"mean": g.mean(), "median": g.median(), "sd": g.std(), "n": g.size(),
                        "pct_positive": g.apply(lambda v: (v > 0).mean())})  # fmt: skip
    out["ci95"] = tdist.ppf(0.975, out["n"] - 1) * out["sd"] / np.sqrt(out["n"])
    tstat = out["mean"] / (out["sd"] / np.sqrt(out["n"]))
    out["p"] = 2 * tdist.sf(np.abs(tstat), out["n"] - 1)
    out["p_holm"] = holm(out["p"]).to_numpy()
    out.index = MONTHS
    return out


def year_path(daily_ex: pd.Series) -> pd.Series:
    """Average cumulative excess return by day of year, minus the average straight-line drift."""
    paths = []
    for _, x in daily_ex.groupby(daily_ex.index.year):
        cum = np.exp(np.log1p(x).cumsum()) - 1
        doy = cum.copy()
        doy.index = x.index.dayofyear
        doy = doy[~doy.index.duplicated()].reindex(range(1, 367)).ffill().fillna(0.0)
        paths.append(doy)
    avg = pd.concat(paths, axis=1).mean(axis=1)
    drift = avg.loc[365] * (avg.index / 365)
    out = (avg - drift).loc[:365]
    out.index = pd.Timestamp("2001-01-01") + pd.to_timedelta(out.index - 1, unit="D")
    return out


def calendar_day(daily_ex: pd.Series, window: int = 21) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Average daily excess return per calendar day (dummy year 2001; Feb 29 folded into Feb 28), plus a
    centred ``window``-day smoothed mean pooled over all returns in the window and its 95% half-width."""
    x = daily_ex.dropna()
    md = x.index.strftime("%m-%d").str.replace("02-29", "02-28")
    key = pd.to_datetime("2001-" + md)
    grp = pd.Series(x.to_numpy(), index=key)
    per_day = grp.groupby(level=0).mean()
    days = pd.date_range("2001-01-01", "2001-12-31")
    stats_ = (
        grp.groupby(level=0)
        .agg(["sum", "count", lambda v: (v**2).sum()])
        .reindex(days, fill_value=0)
    )
    stats_.columns = ["s", "n", "ss"]
    half = window // 2
    ext = pd.concat([stats_.iloc[-half:], stats_, stats_.iloc[:half]])  # wrap around the year
    roll = ext.rolling(window, center=True).sum().iloc[half:-half]
    mean = roll["s"] / roll["n"]
    sd = np.sqrt(roll["ss"] / roll["n"] - mean**2)
    return per_day, mean, 1.96 * sd / np.sqrt(roll["n"])


def halloween(r: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    idx = r.loc[start:end].index
    runs = {"buy_and_hold": pd.Series(1.0, index=idx),
            "sell_in_may (stocks Nov-Apr)": pd.Series([1.0 if t.month in WINTER else 0.0 for t in idx], index=idx),
            "opposite (stocks May-Oct)": pd.Series([0.0 if t.month in WINTER else 1.0 for t in idx], index=idx)}  # fmt: skip
    rows = [{"strategy": n, **stats(simulate(w, r, start, end))} for n, w in runs.items()]
    df = pd.DataFrame(rows)
    df["vs_buy_hold"] = df["final_value"] / df["final_value"].iloc[0] - 1
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    r = monthly_returns()
    ex = (r["mkt"] - r["rf"]).loc["1927":"2022"]
    tables = {name: by_month(ex.loc[a:b]) for name, (a, b) in PERIODS.items()}
    full = by_month(ex)

    # winter vs summer: mean monthly excess return difference, per half
    hw = []
    for name, (a, b) in {**PERIODS, "1927-2022": ("1927", "2022")}.items():
        x = ex.loc[a:b]
        w, s = x[x.index.month.isin(WINTER)], x[~x.index.month.isin(WINTER)]
        diff = w.mean() - s.mean()
        se = np.sqrt(w.var() / len(w) + s.var() / len(s))
        yearly = (
            x.groupby([x.index.year, x.index.month.isin(WINTER)])
            .apply(lambda v: (1 + v).prod() - 1)
            .unstack()
        )
        hw.append({"period": name, "winter_monthly": w.mean(), "summer_monthly": s.mean(), "difference": diff,
                   "t_stat": diff / se, "years_winter_beat_summer": (yearly[True] > yearly[False]).mean()})  # fmt: skip
    hw = pd.DataFrame(hw)

    strat = halloween(r, "1927-01-31", "2022-12-31")
    recent = halloween(r, "2023-01-31", "2025-12-31")
    log_trials([{"kind": "seasonality", **row} for row in strat.to_dict("records")])

    # daily paths
    kf = pd.read_parquet(RAW_DIR / "ff_factors_daily.parquet").set_index("date")
    kex = kf["mkt"] - kf["rf"]
    p = load_prices()
    spy = p[p["permno"] == SPY].set_index("session")["ret"].astype(float)
    spy_ex = (spy - rf_daily(p).reindex(spy.index).fillna(0) / 252).loc["1994":"2022"].dropna()
    paths = {"US market 1927-1974": year_path(kex.loc["1927":"1974"]),
             "US market 1975-2022": year_path(kex.loc["1975":"2022"]), "SPY 1994-2022": year_path(spy_ex)}  # fmt: skip
    path_df = pd.DataFrame(paths)

    # charts
    bars = pd.DataFrame({k: v["mean"] * 100 for k, v in tables.items()})
    errs = pd.DataFrame({k: v["ci95"] * 100 for k, v in tables.items()})
    plots.grouped_bars(bars, errs, "Average monthly return above T-bills, by calendar month (US market)",
                       "% per month (95% CI)", OUT / "monthly_returns.png", fmt=lambda v: f"{v:+.1f}%")  # fmt: skip
    plots.daily_path(
        {k: v * 100 for k, v in paths.items()},
        "Average path through the year, relative to normal growth",
        "% above / below trend",
        OUT / "year_path.png",
        fmt=lambda v: f"{v:+.1f}%",
    )
    cal = {
        "US market 1927-2022": calendar_day(kex.loc["1927":"2022"]),
        "US market 1975-2022": calendar_day(kex.loc["1975":"2022"]),
        "SPY 1994-2022": calendar_day(spy_ex),
    }
    plots.daily_seasonal(
        cal["US market 1927-2022"][0] * 1e4,
        {k: v[1] * 1e4 for k, v in cal.items()},
        {k: v[2] * 1e4 for k, v in cal.items() if k.startswith("US market 1927")},
        "Average daily return above T-bills by calendar day (21-day smoothed)",
        "basis points per day",
        OUT / "daily_returns.png",
        fmt=lambda v: f"{v:+.0f}bp",
    )
    pd.DataFrame({**{f"{k} per day": v[0] for k, v in cal.items()},
                  **{f"{k} smoothed": v[1] for k, v in cal.items()},
                  **{f"{k} ci95": v[2] for k, v in cal.items()}}).to_csv(OUT / "daily_returns.csv")  # fmt: skip
    sm = cal["US market 1927-2022"][1]
    weak = sm[sm < 0]  # fmt: skip

    full.to_csv(OUT / "by_month_1927_2022.csv")
    for k, v in tables.items():
        v.to_csv(OUT / f"by_month_{k}.csv")
    hw.to_csv(OUT / "winter_vs_summer.csv", index=False)
    strat.to_csv(OUT / "sell_in_may.csv", index=False)
    recent.to_csv(OUT / "sell_in_may_2023_2025.csv", index=False)
    path_df.to_csv(OUT / "year_path.csv")
    peaks = {
        k: (v.idxmax().strftime("%b %d"), v.max(), v.idxmin().strftime("%b %d"), v.min())
        for k, v in paths.items()
    }

    pct = ("mean", "median", "ci95", "pct_positive", "winter_monthly", "summer_monthly", "difference",
           "years_winter_beat_summer", "xirr", "max_drawdown", "avg_stock_weight", "vs_buy_hold")  # fmt: skip
    txt = ["# Seasonality (US market, excess return over T-bills)", "",
           "## By calendar month, 1927-2022", "",
           fmt_table(full.reset_index(names="month")[["month", "mean", "median", "ci95", "pct_positive", "p", "p_holm"]],
                     pct=pct, dec2=("p", "p_holm")), "",
           "## Mean by month, two halves", "",
           fmt_table(pd.DataFrame({k: v["mean"] for k, v in tables.items()}).reset_index(names="month"),
                     pct=tuple(PERIODS)), "",
           "## Winter (Nov-Apr) vs summer (May-Oct)", "", fmt_table(hw, pct=pct, dec2=("t_stat",)), "",
           "## Seasonal path (detrended): typical high and low", "",
           *[f"- {k}: highest {hi} ({mx * 100:+.1f}%), lowest {lo} ({mn * 100:+.1f}%)" for k, (hi, mx, lo, mn)
             in peaks.items()], "",
           "## Daily (21-day smoothed), US market 1927-2022", "",
           f"- best stretch centred on {sm.idxmax():%b %d} ({sm.max() * 1e4:+.1f} bp/day), worst centred on "
           f"{sm.idxmin():%b %d} ({sm.min() * 1e4:+.1f} bp/day); smoothed average below zero on {len(weak)} "
           f"days, all between {weak.index.min():%b %d} and {weak.index.max():%b %d}" if len(weak) else "- never below zero",
           "",
           "## Strategy: Sell in May, $5,000 each January, 1927-2022", "",
           fmt_table(strat[["strategy", "final_value", "vs_buy_hold", "xirr", "sharpe", "max_drawdown",
                            "avg_stock_weight"]], pct=pct, money=("final_value",), dec2=("sharpe",)), "",
           "## 2023-2025 (descriptive)", "",
           fmt_table(recent[["strategy", "final_value", "vs_buy_hold", "xirr"]], pct=pct, money=("final_value",)),
           ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
