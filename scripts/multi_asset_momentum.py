"""Multi-asset momentum: rotate between US stocks (SPY), international stocks (EFA), bonds (IEF) and gold (GLD).

Pre-declared grid (all reported): hold the top 1 or top 2 assets by 3-, 6- or 12-month total return,
rebalanced monthly; plus the 12-month top-1 rule with an absolute filter (cash if the leader did not beat
T-bills). Window 2006-01 → 2022-12 (12 months after GLD listed); 2023-2025 descriptive. $5,000 each January,
next-open fills, 2 bps spreads, T+1 settlement (the project's daily engine). Compared with SPY, an equal-weight
mix of the four assets, 60/40, and 100 random rotations holding the same number of assets.

    uv run scripts/multi_asset_momentum.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import pandas as pd

from buying_analysis.backtest import MarketData
from buying_analysis.data import ROOT, load_country_etfs
from buying_analysis.experiments import evaluate_timing, run_parallel
from buying_analysis.metrics import summarize
from buying_analysis.report import fmt_table, period_returns
from buying_analysis.strategies.benchmarks import EqualWeight, sixty_forty, spy_buy_and_hold
from buying_analysis.strategies.timing import IEF, SPY, AssetMomentum

OUT = ROOT / "outputs" / "multi_asset_momentum"
GLD = 90448
START, END = "2006-01-03", "2022-12-30"
RECENT = ("2023-01-03", "2025-12-31")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = load_country_etfs()
    efa = int(c.loc[c["ticker"] == "EFA", "permno"].iloc[0])
    assets = [SPY, efa, IEF, GLD]
    names = {SPY: "SPY", efa: "EFA", IEF: "IEF", GLD: "GLD"}
    md = MarketData.load(permnos=[*assets], extra=c[c["permno"] == efa])

    grid = [AssetMomentum(assets, k, lb) for k in (1, 2) for lb in (3, 6, 12)]
    grid.append(AssetMomentum(assets, 1, 12, absolute=True))
    rows, results = [], {}
    for s in grid:
        out = evaluate_timing(s, md, START, END, n_random=100)
        results[s.name] = out["_res"]
        held = out["_res"].weights.rename(columns=names)
        share = (held > 0).mean().reindex(names.values()).fillna(0)
        rows.append({k: v for k, v in out.items() if not k.startswith("_")}
                    | {f"time_in_{n}": share[n] for n in names.values()}
                    | {"time_in_cash": float((held.sum(axis=1) < 0.5).mean())})  # fmt: skip
        print(s.name, "done", flush=True)
    bench = [
        spy_buy_and_hold(),
        EqualWeight(assets, "monthly", name="equal_weight_4_assets"),
        sixty_forty(),
    ]
    for s, r in zip(bench, run_parallel(md, [(s, START, END) for s in bench])):
        results[s.name] = r
        rows.append(summarize(r))
    table = pd.DataFrame(rows)
    spy_final = table.loc[table["strategy"] == "B1_spy_buy_hold", "final_value"].iloc[0]
    ew_final = table.loc[table["strategy"] == "equal_weight_4_assets", "final_value"].iloc[0]
    table["vs_spy"] = table["final_value"] / spy_final - 1
    table["vs_equal_weight"] = table["final_value"] / ew_final - 1
    periods = period_returns(results, {"2006-2009 (GFC)": ("2006-01-01", "2009-12-31"),
                                       "2010-2019": ("2010-01-01", "2019-12-31"),
                                       "2020-2022": ("2020-01-01", "2022-12-31")})  # fmt: skip
    recent = pd.DataFrame(
        [summarize(r) for r in run_parallel(md, [(s, *RECENT) for s in [*grid, *bench]])]
    )

    for n, d in [("results", table), ("periods", periods), ("recent_2023_2025", recent)]:
        d.to_csv(OUT / f"{n}.csv")
    pct = ("xirr", "max_drawdown", "vs_spy", "vs_equal_weight", "time_in_SPY", "time_in_EFA", "time_in_IEF",
           "time_in_GLD", "time_in_cash")  # fmt: skip
    cols = ["strategy", "final_value", "vs_spy", "vs_equal_weight", "xirr", "sharpe", "max_drawdown", "n_trades",
            "n2_pct_final", "n2_pct_sharpe", "time_in_SPY", "time_in_EFA", "time_in_IEF", "time_in_GLD",
            "time_in_cash"]  # fmt: skip
    txt = ["# Multi-asset momentum (SPY / EFA / IEF / GLD)", "",
           f"{START} → {END}; $5,000 each January; daily engine (next-open fills, 2 bps, T+1).", "",
           fmt_table(table[[c for c in cols if c in table]], pct=pct, money=("final_value",), dec2=("sharpe",),
                     ints=("n_trades",)), "",
           "`n2_pct_*`: percentile vs 100 random rotations holding the same number of assets.", "",
           "## Annualized return by period", "", fmt_table(periods.reset_index(names="strategy"),
                                                           pct=tuple(periods.columns)), "",
           "## 2023-2025 (descriptive)", "",
           fmt_table(recent[["strategy", "final_value", "xirr", "max_drawdown"]], pct=pct, money=("final_value",)),
           ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
