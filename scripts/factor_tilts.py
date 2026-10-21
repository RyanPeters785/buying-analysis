"""Should part of the Roth tilt to small-cap and/or value stocks? (Ken French portfolios, 1927-2022)

Each option invests every $5,000 January deposit immediately and holds; the two tilts rebalance to target
weights at each deposit. Assumed annual fund costs are deducted (paper portfolios have none). Reported:
full period, three eras, every 20-year window (quarterly starts), and 2023-2025 as descriptive only.

    uv run scripts/factor_tilts.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import pandas as pd

from buying_analysis.backtest import MarketData
from buying_analysis.data import KF6, KF_MARKET, ROOT, load_ken_french_portfolios
from buying_analysis.experiments import rolling_windows, run_parallel
from buying_analysis.metrics import summarize
from buying_analysis.report import fmt_table, period_returns
from buying_analysis.stats import block_bootstrap
from buying_analysis.strategies.benchmarks import FixedMix
from buying_analysis.strategies.deployment import LumpSum

OUT = ROOT / "outputs" / "factor_tilts"
START, END = "1927-07-01", "2022-12-30"
FEES = {"market": 0.0003, "big_blend": 0.0003, "big_growth": 0.0005, "big_value": 0.0010,
        "small_blend": 0.0015, "small_growth": 0.0025, "small_value": 0.0025}  # fmt: skip
ERAS = {"1927-1963": ("1927-01-01", "1963-12-31"), "1964-2006": ("1964-01-01", "2006-12-31"),
        "2007-2022": ("2007-01-01", "2022-12-31")}  # fmt: skip


def strategies():
    out = []
    for name, permno in {"market": KF_MARKET, **KF6}.items():
        s = LumpSum(permno)
        s.name = name
        out.append(s)
    out.append(
        FixedMix({KF_MARKET: 0.7, KF6["small_value"]: 0.3}, "annual", "70_market_30_small_value")
    )
    out.append(
        FixedMix({KF_MARKET: 0.7, KF6["big_value"]: 0.3}, "annual", "70_market_30_big_value")
    )
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md = MarketData.load(prices=load_ken_french_portfolios(FEES))
    strats = strategies()
    res = run_parallel(md, [(s, START, END) for s in strats])
    results = dict(zip([s.name for s in strats], res))
    mkt = results["market"]
    rows = []
    for name, r in results.items():
        m = summarize(r)
        m["strategy"] = name
        m["vs_market"] = m["final_value"] / summarize(mkt)["final_value"] - 1
        if name != "market":
            m |= block_bootstrap(r.daily, mkt.daily, n_boot=500)
        rows.append(m)
    full = pd.DataFrame(rows)
    eras = period_returns(results, ERAS)
    roll = rolling_windows(
        md, strats[1:], 20, END, step_months=3, warmup_days=0, benchmark=strats[0]
    )
    roll = roll[roll["strategy"] != "market"]
    rsum = roll.groupby("strategy").agg(windows=("final_vs_b1", "size"), median_vs_market=("final_vs_b1", "median"),
                                        pct_beat_market=("final_vs_b1", lambda v: (v > 0).mean()),
                                        worst=("final_vs_b1", "min"), best=("final_vs_b1", "max"))  # fmt: skip
    late = run_parallel(md, [(s, "2023-01-03", "2025-12-31") for s in strats])
    recent = pd.DataFrame([{**summarize(r), "strategy": s.name} for s, r in zip(strats, late)])
    full.to_csv(OUT / "full_period.csv", index=False)
    eras.to_csv(OUT / "eras.csv")
    roll.to_csv(OUT / "rolling_20y.csv", index=False)
    recent.to_csv(OUT / "recent_2023_2025.csv", index=False)
    pct = ("xirr", "max_drawdown", "vs_market", "final_value_ratio_lo", "final_value_ratio_hi",
           "median_vs_market", "pct_beat_market", "worst", "best")  # fmt: skip
    txt = ["# Factor tilts (Ken French size x value portfolios)", "",
           f"{START} → {END}; $5,000 each January; fees deducted: {FEES}.", "",
           fmt_table(full[["strategy", "final_value", "vs_market", "xirr", "sharpe", "max_drawdown",
                           "longest_dd_days", "final_value_ratio_lo", "final_value_ratio_hi"]],
                     pct=pct, money=("final_value",), dec2=("sharpe",), ints=("longest_dd_days",)), "",
           "## Annualized return by era", "", fmt_table(eras.reset_index(names="strategy"), pct=tuple(eras.columns)),
           "", "## Every 20-year window (quarterly starts), ending value vs market", "",
           fmt_table(rsum.reset_index(), pct=pct), "",
           "## 2023-2025 (descriptive only)", "",
           fmt_table(recent[["strategy", "final_value", "xirr", "max_drawdown"]], pct=pct, money=("final_value",)),
           ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
