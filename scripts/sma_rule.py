"""The X-day moving-average rule: out to T-bills when the close drops below the X-day SMA, back in when it
closes above. Grid X = 20, 50, 100, 150, 200, 250 (all reported, none selected).

  SPY 1994-2022 with random-timing nulls and 1x / 5x costs; halves 1994-2007 / 2008-2022
  US market (Ken French) 1927-2022: full period, regimes, every 20-year window
  2023-2025 descriptive only
Cash earns the 3-month T-bill rate with no fund fee (direct T-bills / SGOV-like).

    uv run scripts/sma_rule.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import pandas as pd

from buying_analysis.backtest import MarketData
from buying_analysis.costs import CostModel
from buying_analysis.data import KF_MARKET, ROOT, load_ken_french_panel
from buying_analysis.experiments import evaluate_timing, rolling_windows, run_parallel
from buying_analysis.metrics import summarize
from buying_analysis.report import KF_REGIMES, fmt_table, period_returns
from buying_analysis.strategies.deployment import LumpSum
from buying_analysis.strategies.timing import SPY, PriceVsSMA

OUT = ROOT / "outputs" / "sma_rule"
XS = (20, 50, 100, 150, 200, 250)
SPY_START, END = "1994-01-03", "2022-12-30"
TBILL = CostModel(mmf_expense=0.0)
TBILL_5X = CostModel(mmf_expense=0.0, spread_multiplier=5.0)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md = MarketData.load([SPY])
    rows, results = [], {}
    for x in XS:
        out = evaluate_timing(PriceVsSMA(SPY, x), md, SPY_START, END, n_random=100, costs=TBILL)
        results[out["strategy"]] = out["_res"]
        results["B1_spy_buy_hold"] = out["_b1"]
        rows.append({k: v for k, v in out.items() if not k.startswith("_")})
    spy = pd.DataFrame(rows)
    hi = run_parallel(md, [(PriceVsSMA(SPY, x), SPY_START, END) for x in XS], costs=TBILL_5X)
    spy["xirr_costs_x5"] = [summarize(r)["xirr"] for r in hi]
    spy["avg_days_per_trade"] = (pd.Timestamp(END) - pd.Timestamp(SPY_START)).days / spy["n_trades"]
    halves = period_returns(
        results, {"1994-2007": ("1994-01-01", "2007-12-31"), "2008-2022": ("2008-01-01", END)}
    )
    recent = pd.DataFrame([summarize(r) for r in run_parallel(
        md, [(s, "2023-01-03", "2025-12-31") for s in [LumpSum(SPY), *[PriceVsSMA(SPY, x) for x in XS]]],
        costs=TBILL)])  # fmt: skip

    kmd = MarketData.load(prices=load_ken_french_panel(), end=END)
    kstr = [LumpSum(KF_MARKET), *[PriceVsSMA(KF_MARKET, x) for x in XS]]
    kres = run_parallel(kmd, [(s, "1927-07-01", END) for s in kstr], costs=TBILL)
    kf = pd.DataFrame([summarize(r) for r in kres])
    kf["vs_buy_hold"] = kf["final_value"] / kf["final_value"].iloc[0] - 1
    kreg = period_returns(dict(zip([s.name for s in kstr], kres)), KF_REGIMES)
    roll = rolling_windows(
        kmd, kstr[1:], 20, END, step_months=3, warmup_days=400, costs=TBILL, benchmark=kstr[0]
    )
    roll = roll[roll["strategy"] != kstr[0].name]
    rsum = roll.groupby("strategy", sort=False).agg(
        windows=("final_vs_b1", "size"), median_vs_buy_hold=("final_vs_b1", "median"),
        pct_beat_buy_hold=("final_vs_b1", lambda v: (v > 0).mean()))  # fmt: skip

    for name, df in [("spy", spy), ("spy_halves", halves), ("recent", recent), ("kf", kf),
                     ("kf_regimes", kreg), ("kf_rolling_20y", roll)]:  # fmt: skip
        df.to_csv(OUT / f"{name}.csv")
    pct = ("xirr", "b1_xirr", "xirr_costs_x5", "max_drawdown", "time_in_market", "vs_buy_hold",
           "median_vs_buy_hold", "pct_beat_buy_hold")  # fmt: skip
    txt = ["# X-day moving-average rule (out to T-bills below the average)", "",
           "## SPY 1994-2022, $5,000 each January", "",
           fmt_table(spy[["strategy", "final_value", "b1_final", "xirr", "b1_xirr", "xirr_costs_x5", "sharpe",
                          "b1_sharpe", "max_drawdown", "time_in_market", "n_trades", "avg_days_per_trade",
                          "n2_pct_final", "n2_pct_sharpe"]],
                     pct=pct, money=("final_value", "b1_final"), dec2=("sharpe", "b1_sharpe"),
                     ints=("n_trades", "avg_days_per_trade")), "",
           "### By half (annualized)", "", fmt_table(halves.reset_index(names="strategy"), pct=tuple(halves.columns)),
           "", "## US market 1927-2022 (Ken French; trades at next close)", "",
           fmt_table(kf[["strategy", "final_value", "vs_buy_hold", "xirr", "sharpe", "max_drawdown",
                         "time_in_market", "n_trades"]], pct=pct, money=("final_value",), dec2=("sharpe",),
                     ints=("n_trades",)), "",
           "### By regime", "", fmt_table(kreg.reset_index(names="strategy"), pct=tuple(kreg.columns)), "",
           "### Every 20-year window (quarterly starts) vs buy-and-hold", "", fmt_table(rsum.reset_index(), pct=pct),
           "", "## 2023-2025 (descriptive only)", "",
           fmt_table(recent[["strategy", "final_value", "xirr", "max_drawdown", "n_trades"]], pct=pct,
                     money=("final_value",), ints=("n_trades",)), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
