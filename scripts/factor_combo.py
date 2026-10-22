"""Three-factor combination: low volatility + value (cheap + profitable) + momentum, 1/3 each.

Sleeves (Ken French value-weighted portfolios, monthly, 1964-2022):
  low vol   lowest 20% of stocks by 60-day volatility (re-formed monthly)
  value     cheap + profitable (top 2 x top 2 of the 5x5 B/M x OP sort)
  momentum  top 20% by 12-1 month return
Plans: market; each sleeve alone; 50/50 value + momentum; 50/50 low vol + value; 1/3 each. Rebalanced to
target when each $5,000 January deposit lands. Costs: low vol / value 0.25%/yr, momentum 1%/yr, market 0.03%.
Reported: full period, correlation of sleeve excess returns, worst 3/5/10-year stretches vs market, crashes,
eras, every 20-year window, 2023-2025 descriptive.

    uv run scripts/factor_combo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from low_volatility import CRASHES
from low_volatility import load as load_lowvol
from value_momentum import series as vm_series
from value_momentum import sleeves_sim
from value_profitability import stats

from buying_analysis import plots
from buying_analysis.data import ROOT
from buying_analysis.experiments import log_trials
from buying_analysis.report import fmt_table

OUT = ROOT / "outputs" / "factor_combo"
START, END = "1964-01-31", "2022-12-31"
ERAS = {"1964-1989": ("1964", "1989"), "1990-2006": ("1990", "2006"), "2007-2022": ("2007", "2022")}
FEES = {"market": 0.0003, "low vol": 0.0025, "value": 0.0025, "momentum": 0.01}
PLANS = {
    "market": {"market": 1.0},
    "low vol only": {"low vol": 1.0},
    "value only (cheap + profitable)": {"value": 1.0},
    "momentum only (top 20%)": {"momentum": 1.0},
    "50/50 value + momentum": {"value": 0.5, "momentum": 0.5},
    "50/50 low vol + value": {"low vol": 0.5, "value": 0.5},
    "1/3 each: low vol + value + momentum": {"low vol": 1 / 3, "value": 1 / 3, "momentum": 1 / 3},
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    vm, rf = vm_series()
    lv, _ = load_lowvol()
    r = pd.DataFrame({"market": vm["market"], "low vol": lv["low vol (lowest 20%)"],
                      "value": vm["cheap + profitable"], "momentum": vm["top 20% momentum"]}).dropna()  # fmt: skip
    ex = r[["low vol", "value", "momentum"]].sub(r["market"], axis=0).loc[START:END]
    corr = ex.corr()

    runs = {p: sleeves_sim(r, w, FEES, rf, START, END) for p, w in PLANS.items()}
    base = runs["market"]
    rows = []
    for p, a in runs.items():
        rel = (1 + a["ret"]).cumprod() / (1 + base["ret"]).cumprod()
        rows.append({"plan": p, **stats(a), "vs_market": a["equity"].iloc[-1] / base["equity"].iloc[-1] - 1,
                     "volatility": a["ret"].std() * np.sqrt(12),
                     **{f"worst_{k}y_vs_market": (rel / rel.shift(12 * k) - 1).min() for k in (3, 5, 10)}})  # fmt: skip
    table = pd.DataFrame(rows)

    def ann(x):
        return (1 + x).prod() ** (12 / len(x)) - 1

    eras = pd.DataFrame(
        {p: {e: ann(a.loc[s:t, "ret"]) for e, (s, t) in ERAS.items()} for p, a in runs.items()}
    ).T
    crash = pd.DataFrame({p: {k: (1 + a.loc[s:t, "ret"]).prod() - 1 for k, (s, t) in CRASHES.items()}
                          for p, a in runs.items()}).T  # fmt: skip
    roll = []
    for s in r.loc[START:END].index:
        e = s + pd.DateOffset(years=20) - pd.offsets.MonthEnd(1)
        if e > pd.Timestamp(END):
            break
        b = sleeves_sim(r, PLANS["market"], FEES, rf, s, e)["equity"].iloc[-1]
        for p, w in PLANS.items():
            if p != "market":
                roll.append(
                    {
                        "plan": p,
                        "vs_market": sleeves_sim(r, w, FEES, rf, s, e)["equity"].iloc[-1] / b - 1,
                    }
                )
    rsum = (
        pd.DataFrame(roll)
        .groupby("plan", sort=False)["vs_market"]
        .agg(median="median", pct_beat=lambda v: (v > 0).mean(), worst="min", best="max")
    )
    recent = pd.DataFrame([{"plan": p, **stats(sleeves_sim(r, w, FEES, rf, "2023-01-31", "2025-12-31"))}
                           for p, w in PLANS.items()])  # fmt: skip

    rel = {
        p: (1 + runs[p]["ret"]).cumprod() / (1 + base["ret"]).cumprod()
        for p in ["1/3 each: low vol + value + momentum", "50/50 value + momentum", "low vol only"]
    }
    plots.line_chart(rel, "Growth of $1 relative to the market (time-weighted, after costs)", "ratio to market (log)",
                     OUT / "relative_to_market.png", log=True, fmt=lambda v: f"{v:.2f}x")  # fmt: skip
    log_trials(
        [{"kind": "factor_combo", "strategy": x["plan"], **x} for x in table.to_dict("records")]
    )
    for n, d in [("results", table), ("correlations", corr), ("eras", eras), ("crashes", crash),
                 ("rolling_20y", rsum), ("recent_2023_2025", recent)]:  # fmt: skip
        d.to_csv(OUT / f"{n}.csv")
    pct = ("xirr", "max_drawdown", "vs_market", "volatility", "worst_3y_vs_market", "worst_5y_vs_market",
           "worst_10y_vs_market", "median", "pct_beat", "worst", "best", *ERAS, *CRASHES)  # fmt: skip
    txt = ["# Low volatility + value + momentum (1964-2022)", "",
           f"$5,000 each January, rebalanced to target on each deposit. Costs: {FEES}.", "",
           fmt_table(table[["plan", "final_value", "vs_market", "xirr", "sharpe", "volatility", "max_drawdown",
                            "worst_3y_vs_market", "worst_5y_vs_market", "worst_10y_vs_market"]],
                     pct=pct, money=("final_value",), dec2=("sharpe",)), "",
           "## Correlation of the sleeves' monthly returns in excess of the market", "",
           corr.round(2).reset_index(names="sleeve").to_markdown(index=False), "",
           "## Annualized return by era", "", fmt_table(eras.reset_index(names="plan"), pct=tuple(ERAS)), "",
           "## Total return during crashes", "", fmt_table(crash.reset_index(names="plan"), pct=tuple(CRASHES)), "",
           "## Every 20-year window (monthly starts), ending value vs market", "", fmt_table(rsum.reset_index(), pct=pct),
           "", "## 2023-2025 (descriptive)", "",
           fmt_table(recent[["plan", "final_value", "xirr", "max_drawdown"]], pct=pct, money=("final_value",)), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
