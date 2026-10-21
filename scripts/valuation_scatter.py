"""Valuation at purchase vs the next 10 years' return (S&P composite, Shiller monthly data 1871-2023).

x: trailing P/E (price / last 12 months' earnings) and CAPE (price / 10-year average real earnings), both
   with earnings lagged 4 months so they use only figures already reported.
y: annualized total return (dividends reinvested, nominal) over the following 120 months.
Each dot is one starting month (P/E from 1871, CAPE from 1881, through 2013). Overlapping 10-year windows mean neighbouring dots share
most of their returns, so the effective sample is ~14 independent decades, not ~1,600 points.

    uv run scripts/valuation_scatter.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis import plots
from buying_analysis.data import RAW_DIR, ROOT
from buying_analysis.report import fmt_table

OUT = ROOT / "outputs" / "valuation_scatter"
LAG, H = 4, 120
ERAS = [(1871, 1919, "before 1920"), (1920, 1959, "1920-1959"), (1960, 1989, "1960-1989"),
        (1990, 2100, "1990-2013")]  # fmt: skip


def build() -> tuple[pd.DataFrame, dict]:
    s = pd.read_parquet(RAW_DIR / "shiller_monthly.parquet").set_index("date")
    tr = ((s["P"] + s["D"] / 12) / s["P"].shift(1)).fillna(1).cumprod()
    fwd = (tr.shift(-H) / tr) ** (12 / H) - 1
    real_e = s["E"] / s["CPI"]
    pe = s["P"] / s["E"].shift(LAG)
    cape = (s["P"] / s["CPI"].shift(1)) / real_e.shift(LAG).rolling(120, min_periods=120).mean()
    df = pd.DataFrame({"pe": pe, "cape": cape, "fwd10": fwd})
    df["era"] = pd.cut(
        df.index.year, [e[0] - 1 for e in ERAS] + [2100], labels=[e[2] for e in ERAS]
    )
    latest = {
        "pe": pe.dropna().iloc[-1],
        "cape": cape.dropna().iloc[-1],
        "date": pe.dropna().index[-1],
    }
    return df, latest


def fit(x: pd.Series, y: pd.Series) -> tuple[np.ndarray, float, float, float]:
    """OLS of y on log(x): fitted values, R^2, slope, and the prediction at the latest x (set later)."""
    lx = np.log(x)
    b, a = np.polyfit(lx, y, 1)
    yhat = a + b * lx
    r2 = 1 - ((y - yhat) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return yhat, r2, a, b


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df, latest = build()
    panels, rows, buckets = {}, [], []
    for col, label in (("pe", "Trailing P/E (price / last 12 months' earnings)"),
                       ("cape", "CAPE (price / 10-year avg real earnings)")):  # fmt: skip
        d = df[[col, "fwd10", "era"]].dropna()
        d = d[d[col] > 0]
        yhat, r2, a, b = fit(d[col], d["fwd10"])
        pred = a + b * np.log(latest[col])
        panels[label] = pd.DataFrame({"x": d[col], "y": d["fwd10"] * 100, "group": d["era"].astype(str),
                                      "fit": yhat * 100})  # fmt: skip
        q = pd.qcut(d[col], 5)
        bt = d.groupby(q, observed=True)["fwd10"].agg(["mean", "min", "max", "size"])
        bt.index = [f"{iv.left:.1f}–{iv.right:.1f}" for iv in bt.index]
        buckets.append(bt.assign(measure=col).reset_index(names="range"))
        rows.append({"measure": col, "months": len(d), "first": d.index[0].strftime("%Y-%m"),
                     "last": d.index[-1].strftime("%Y-%m"), "r_squared": r2,
                     "corr": d[col].corr(d["fwd10"]), "latest_value": latest[col],
                     "trend_prediction_at_latest": pred,
                     "range_when_within_10pct_of_latest": f"{d.loc[(d[col] / latest[col] - 1).abs() < 0.1, 'fwd10'].min():.1%}"
                     f" to {d.loc[(d[col] / latest[col] - 1).abs() < 0.1, 'fwd10'].max():.1%}"})  # fmt: skip
    summary = pd.DataFrame(rows)
    bucket_df = pd.concat(buckets, ignore_index=True)
    plots.valuation_scatter(panels, {k: latest[c] for k, c in zip(panels, ("pe", "cape"))},
                            "S&P 500 valuation at purchase vs annualized total return over the next 10 years",
                            "next 10 years, % per year", OUT / "valuation_vs_10y_return.png")  # fmt: skip
    df.to_csv(OUT / "data.csv")
    summary.to_csv(OUT / "summary.csv", index=False)
    bucket_df.to_csv(OUT / "buckets.csv", index=False)
    txt = ["# Valuation vs next-10-year return (Shiller data)", "",
           f"Latest values ({latest['date']:%Y-%m}): trailing P/E {latest['pe']:.1f}, CAPE {latest['cape']:.1f}.", "",
           fmt_table(summary, pct=("r_squared", "corr", "trend_prediction_at_latest")), "",
           "## Next-10-year annualized return by valuation fifth", "",
           fmt_table(bucket_df[["measure", "range", "mean", "min", "max", "size"]], pct=("mean", "min", "max")), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
