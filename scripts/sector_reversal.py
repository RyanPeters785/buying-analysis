"""Always-invested sector reversal: each month hold the k sector ETFs with the WORST recent return.

Pre-declared (no tuning): k = 3; 1-month lookback (main) and 3-month (robustness); 2000-02 to 2022-12, the
same window as the momentum rotation. Compared with SPY, equal weight of all sectors, momentum rotation, and
100 random-sector portfolios. Halves 2000-2010 / 2011-2022 are reported from the same continuous runs.

    uv run scripts/sector_reversal.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import pandas as pd

from buying_analysis.backtest import MarketData
from buying_analysis.data import ROOT
from buying_analysis.experiments import evaluate_timing, run_parallel
from buying_analysis.metrics import summarize
from buying_analysis.report import fmt_table, period_returns
from buying_analysis.strategies.benchmarks import EqualWeight, spy_buy_and_hold
from buying_analysis.strategies.timing import IEF, SECTORS, SPY, SectorRotation

OUT = ROOT / "outputs" / "sector_reversal"
START, END = "2000-02-01", "2022-12-30"
HALVES = {"2000-2010": ("2000-01-01", "2010-12-31"), "2011-2022": ("2011-01-01", "2022-12-31")}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md = MarketData.load([SPY, IEF, *SECTORS], end=END)
    rows, results = [], {}
    for s in [SectorRotation(3, 1, 0, reversal=True), SectorRotation(3, 3, 0, reversal=True),
              SectorRotation(3, 12, 1)]:  # fmt: skip
        out = evaluate_timing(s, md, START, END, n_random=100)
        results[s.name] = out["_res"]
        rows.append({k: v for k, v in out.items() if not k.startswith("_")})
        print(s.name, "done", flush=True)
    for s in [spy_buy_and_hold(), EqualWeight(SECTORS, name="equal_weight_sectors")]:
        r = run_parallel(md, [(s, START, END)])[0]
        results[s.name] = r
        rows.append(summarize(r))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "results.csv", index=False)
    halves = period_returns(results, HALVES)
    halves.to_csv(OUT / "halves.csv")
    cols = ["strategy", "final_value", "xirr", "sharpe", "max_drawdown", "n_trades", "total_costs",
            "n2_median_final", "n2_pct_final", "n2_pct_sharpe"]  # fmt: skip
    md_txt = ["# Sector reversal (always invested)", "", f"{START} → {END}, $5,000 each January.", "",
              fmt_table(df[[c for c in cols if c in df]], pct=("xirr", "max_drawdown"),
                        money=("final_value", "total_costs", "n2_median_final"), dec2=("sharpe",),
                        ints=("n_trades",)), "",
              "## Annualized return by half", "",
              fmt_table(halves.reset_index(names="strategy"), pct=tuple(halves.columns)), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(md_txt))
    print("\n".join(md_txt))


if __name__ == "__main__":
    main()
