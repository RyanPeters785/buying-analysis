"""Low-volatility stocks vs simply reducing market exposure (Ken French portfolios, 1964-2022).

  A. Hold low-volatility stocks: lowest 20% / 10% of stocks by 60-day return variance (re-formed monthly),
     and the lowest 20% by 60-month beta (re-formed each June), value-weighted, always fully invested.
  B. Reduce exposure instead: market + T-bills, with the stock share set each month to the ratio of the
     low-vol quintile's to the market's volatility over the prior 60 months (fewer at the start, minimum 6;
     capped at 100%; no hindsight).
Also: the highest-volatility 20% for contrast. Costs: 0.25%/yr for the low-vol / low-beta portfolios,
0.03% for the market. $5,000 each January. Eras, crash periods, every 20-year window, 2023-2025 descriptive.

    uv run scripts/low_volatility.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from value_profitability import simulate, stats

from buying_analysis import plots
from buying_analysis.data import RAW_DIR, ROOT
from buying_analysis.experiments import log_trials
from buying_analysis.report import fmt_table

OUT = ROOT / "outputs" / "low_volatility"
START, END = "1964-01-31", "2022-12-31"
FEE_TILT, FEE_MKT = 0.0025, 0.0003
ERAS = {"1964-1989": ("1964", "1989"), "1990-2006": ("1990", "2006"), "2007-2022": ("2007", "2022")}
CRASHES = {"1973-74": ("1973-01", "1974-09"), "1987 crash": ("1987-09", "1987-11"),
           "2000-02": ("2000-04", "2002-09"), "2008-09": ("2007-11", "2009-02"),
           "2020 COVID": ("2020-02", "2020-03"), "2022": ("2022-01", "2022-09")}  # fmt: skip


def load() -> tuple[pd.DataFrame, pd.Series]:
    var = pd.read_parquet(RAW_DIR / "ff_variance_monthly.parquet").pivot(
        index="date", columns="cell", values="ret"
    )
    beta = pd.read_parquet(RAW_DIR / "ff_beta_monthly.parquet").pivot(
        index="date", columns="cell", values="ret"
    )
    kf = pd.read_parquet(RAW_DIR / "ff_factors_daily.parquet").set_index("date")
    m = (1 + kf[["mkt", "rf"]]).resample("ME").prod() - 1
    df = pd.DataFrame({"market": m["mkt"], "low vol (lowest 20%)": var["Lo 20"], "low vol (lowest 10%)": var["Lo 10"],
                       "low beta (lowest 20%)": beta["Lo 20"], "high vol (highest 20%)": var["Hi 20"]}).dropna()  # fmt: skip
    ratio = (
        df["low vol (lowest 20%)"].rolling(60, min_periods=6).std()
        / df["market"].rolling(60, min_periods=6).std()
    ).clip(upper=1.0)
    w = ratio.shift(1)  # known at the start of each month
    df["market + T-bills (same vol as low vol)"] = w * df["market"] + (1 - w) * m["rf"].reindex(
        df.index
    )
    df.attrs["weight"] = w
    return df, m["rf"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    r, rf = load()
    fees = {c: (FEE_MKT if c.startswith("market") else FEE_TILT) for c in r.columns}
    runs = {c: simulate(r[c], rf, fees[c], START, END) for c in r.columns}
    rows = []
    mk = r["market"].loc[START:END]
    for c, a in runs.items():
        x = r[c].loc[START:END]
        rows.append({"strategy": c, **stats(a),
                     "vs_market": a["equity"].iloc[-1] / runs["market"]["equity"].iloc[-1] - 1,
                     "volatility": x.std() * np.sqrt(12), "beta": x.cov(mk) / mk.var()})  # fmt: skip
    table = pd.DataFrame(rows)
    table.loc[table["strategy"].str.startswith("market +"), "avg_stock_share"] = (
        r.attrs["weight"].loc[START:END].mean()
    )

    def ann(x):
        return (1 + x).prod() ** (12 / len(x)) - 1

    eras = pd.DataFrame(
        {c: {e: ann(a.loc[s:t, "ret"]) for e, (s, t) in ERAS.items()} for c, a in runs.items()}
    ).T
    crash = pd.DataFrame(
        {c: {k: (1 + r[c].loc[s:t]).prod() - 1 for k, (s, t) in CRASHES.items()} for c in r}
    ).T
    roll = []
    for s in r.loc[START:END].index:
        e = s + pd.DateOffset(years=20) - pd.offsets.MonthEnd(1)
        if e > pd.Timestamp(END):
            break
        base = simulate(r["market"], rf, FEE_MKT, s, e)["equity"].iloc[-1]
        for c in r.columns[1:]:
            roll.append(
                {
                    "strategy": c,
                    "vs_market": simulate(r[c], rf, fees[c], s, e)["equity"].iloc[-1] / base - 1,
                }
            )
    rsum = (
        pd.DataFrame(roll)
        .groupby("strategy", sort=False)["vs_market"]
        .agg(median="median", pct_beat=lambda v: (v > 0).mean(), worst="min", best="max")
    )
    recent = pd.DataFrame([{"strategy": c, **stats(simulate(r[c], rf, fees[c], "2023-01-31", "2025-12-31"))}
                           for c in r.columns])  # fmt: skip

    rel = {
        c: (1 + runs[c]["ret"]).cumprod() / (1 + runs["market"]["ret"]).cumprod()
        for c in [
            "low vol (lowest 20%)",
            "market + T-bills (same vol as low vol)",
            "high vol (highest 20%)",
        ]
    }
    plots.line_chart(rel, "Growth of $1 relative to the market (time-weighted, after costs)", "ratio to market (log)",
                     OUT / "relative_to_market.png", log=True, fmt=lambda v: f"{v:.2f}x")  # fmt: skip
    log_trials([{"kind": "low_volatility", **x} for x in table.to_dict("records")])
    for n, d in [("results", table), ("eras", eras), ("crashes", crash), ("rolling_20y", rsum),
                 ("recent_2023_2025", recent)]:  # fmt: skip
        d.to_csv(OUT / f"{n}.csv")
    pct = ("xirr", "max_drawdown", "vs_market", "volatility", "avg_stock_share", "median", "pct_beat", "worst",
           "best", *ERAS, *CRASHES)  # fmt: skip
    txt = ["# Low-volatility stocks vs reducing exposure (1964-2022)", "",
           f"$5,000 each January; costs {FEE_TILT:.2%}/yr tilted, {FEE_MKT:.2%}/yr market.", "",
           fmt_table(table[["strategy", "final_value", "vs_market", "xirr", "sharpe", "volatility", "beta",
                            "max_drawdown", "avg_stock_share"]],
                     pct=pct, money=("final_value",), dec2=("sharpe", "beta")), "",
           "## Annualized return by era", "", fmt_table(eras.reset_index(names="strategy"), pct=tuple(ERAS)), "",
           "## Total return during crashes", "", fmt_table(crash.reset_index(names="strategy"), pct=tuple(CRASHES)), "",
           "## Every 20-year window (monthly starts), ending value vs market", "", fmt_table(rsum.reset_index(), pct=pct),
           "", "## 2023-2025 (descriptive)", "",
           fmt_table(recent[["strategy", "final_value", "xirr", "max_drawdown"]], pct=pct, money=("final_value",)),
           ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
