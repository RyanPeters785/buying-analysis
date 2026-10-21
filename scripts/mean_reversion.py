"""Mean-reversion swing study in three pre-declared steps (long-only, Roth IRA).

  step 1 (1993-2007): measure mean reversion for every asset with >= 5 years of data; select the 5 with the
          most negative 10-day variance-ratio z* (VR < 1 required)
  step 2 (1993-2007): pick one band rule (n, entry, exit) from an 8-setting grid by median Sharpe across
          the selected assets
  step 3 (2008-2022): frozen assets + frozen rule vs same-asset buy-and-hold, SPY, and random timing;
          costs at 1x / 2x / 5x

    uv run scripts/mean_reversion.py

Outputs: outputs/mean_reversion/*.csv, report.md. 2023-2025 is not used (lockbox already spent).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd
from scipy.stats import norm

from buying_analysis.backtest import MarketData
from buying_analysis.costs import CostModel
from buying_analysis.data import ROOT
from buying_analysis.experiments import evaluate_timing, log_trials, run_parallel
from buying_analysis.metrics import summarize
from buying_analysis.report import fmt_table
from buying_analysis.stats import holm
from buying_analysis.strategies.deployment import LumpSum
from buying_analysis.strategies.meanrev import MeanReversion, bounce, variance_ratio

OUT = ROOT / "outputs" / "mean_reversion"
SEL_START, SEL_END = "1993-01-29", "2007-12-31"
TEST_START, TEST_END = "2008-01-02", "2022-12-30"
N_SELECT = 5
GRID = [(n, e, x) for n in (20, 50) for e in (1.5, 2.0) for x in (0.0, 0.5)]
MIN_DAYS = 5 * 252


def step1(md: MarketData) -> pd.DataFrame:
    rows = []
    mask = (md.sessions >= SEL_START) & (md.sessions <= SEL_END)
    for p in md.permnos:
        c = md.close_idx[mask, md.col(p)]
        s = pd.Series(c, index=md.sessions[mask]).dropna()
        if len(s) < MIN_DAYS:
            continue
        lr = np.log(s).diff().dropna().to_numpy()
        row = {"permno": int(p), "ticker": md.tickers.get(int(p)), "days": len(s),
               "etf": bool(md.is_etf[md.col(p)]), "ann_vol": lr.std() * np.sqrt(252),
               "autocorr_1d": float(pd.Series(lr).autocorr(1))}  # fmt: skip
        for q in (5, 10, 21):
            row[f"vr_{q}"], row[f"z_{q}"] = variance_ratio(lr, q)
        row |= bounce(s)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["p_10"] = norm.cdf(df["z_10"])  # one-sided: evidence of VR < 1
    df["p_10_holm"] = holm(df["p_10"]).to_numpy()
    df = df.sort_values("z_10").reset_index(drop=True)
    df["selected"] = False
    df.loc[df.index[(df["vr_10"] < 1)][:N_SELECT], "selected"] = True
    return df


def step2(md: MarketData, picks: list[int]) -> tuple[pd.DataFrame, tuple]:
    jobs, keys = [], []
    for p in picks:
        start = max(pd.Timestamp(SEL_START), md.first_session([p]) + pd.Timedelta(days=120))
        for n, e, x in GRID:
            jobs.append((MeanReversion(p, n, e, x), start, SEL_END))
            keys.append((p, n, e, x))
        jobs.append((LumpSum(p), start, SEL_END))
        keys.append((p, "hold", None, None))
    res = run_parallel(md, jobs)
    rows = []
    for (p, n, e, x), r in zip(keys, res):
        m = summarize(r)
        rows.append({"permno": p, "ticker": md.tickers.get(p), "n": n, "entry": e, "exit": x, **m})
    df = pd.DataFrame(rows)
    rules = df[df["n"] != "hold"]
    score = rules.groupby(["n", "entry", "exit"])["sharpe"].median().sort_values(ascending=False)
    best = score.index[0]
    log_trials([{"kind": "meanrev_step2", **r} for r in rules.to_dict("records")])
    return df, (int(best[0]), float(best[1]), float(best[2])), score


def step3(md: MarketData, picks: list[int], rule: tuple, n_random: int = 100) -> pd.DataFrame:
    n, e, x = rule
    rows = []
    for mult in (1.0, 2.0, 5.0):
        cm = CostModel(spread_multiplier=mult)
        for p in picks:
            s = MeanReversion(p, n, e, x)
            out = evaluate_timing(s, md, TEST_START, TEST_END, n_random=n_random if mult == 1.0 else 2,
                                  costs=cm, null_asset=p, log=mult == 1.0)  # fmt: skip
            hold = summarize(run_parallel(md, [(LumpSum(p), TEST_START, TEST_END)], costs=cm)[0])
            rows.append({
                "cost_x": mult, "permno": p, "ticker": md.tickers.get(p), "strategy": s.name,
                "final_value": out["final_value"], "xirr": out["xirr"], "sharpe": out["sharpe"],
                "max_drawdown": out["max_drawdown"], "time_in_market": out["time_in_market"],
                "n_trades": out["n_trades"], "total_costs": out["total_costs"],
                "hold_final": hold["final_value"], "hold_xirr": hold["xirr"], "hold_sharpe": hold["sharpe"],
                "hold_max_drawdown": hold["max_drawdown"],
                "spy_final": out["b1_final"], "spy_xirr": out["b1_xirr"], "spy_sharpe": out["b1_sharpe"],
                "n1_final": out["n1_final"], "n2_pct_final": out["n2_pct_final"] if mult == 1.0 else np.nan,
                "n2_pct_sharpe": out["n2_pct_sharpe"] if mult == 1.0 else np.nan,
            })  # fmt: skip
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md = MarketData.load(end=TEST_END)
    d1 = step1(md)
    d1.to_csv(OUT / "step1_diagnostics.csv", index=False)
    picks = d1.loc[d1["selected"], "permno"].tolist()
    print("STEP 1 selected:", d1.loc[d1["selected"], "ticker"].tolist())
    d2, rule, score = step2(md, picks)
    d2.to_csv(OUT / "step2_grid.csv", index=False)
    score.to_csv(OUT / "step2_rule_scores.csv")
    print("STEP 2 rule (n, entry, exit):", rule)
    d3 = step3(md, picks, rule)
    d3.to_csv(OUT / "step3_test.csv", index=False)
    write_report(d1, d2, score, rule, d3)
    print("done")


def write_report(d1, d2, score, rule, d3) -> None:
    pct = (
        "ann_vol",
        "xirr",
        "hold_xirr",
        "spy_xirr",
        "max_drawdown",
        "hold_max_drawdown",
        "time_in_market",
    )
    t = ["# Mean-reversion swing study", "",
         (f"Selection and rule design on {SEL_START}–{SEL_END}; frozen test on {TEST_START}–{TEST_END}. "
         "$5,000 deposited each January. Long-only."), "",
         "## Step 1: mean-reversion diagnostics (1993–2007), most mean-reverting first", "",
         fmt_table(d1[["ticker", "etf", "days", "ann_vol", "autocorr_1d", "vr_5", "vr_10", "z_10", "p_10_holm",
                       "vr_21", "bounce_excess_bps", "dip_days", "selected"]].round(3), pct=pct), "",
         "## Step 2: rule scores (median Sharpe across selected assets, 1993–2007)", "",
         score.reset_index().round(3).to_markdown(index=False), "", f"Chosen rule (n, entry, exit): {rule}", "",
         "## Step 3: frozen test 2008–2022", "",
         fmt_table(d3[["cost_x", "ticker", "final_value", "hold_final", "spy_final", "xirr", "hold_xirr",
                       "spy_xirr", "sharpe", "hold_sharpe", "spy_sharpe", "max_drawdown", "hold_max_drawdown",
                       "time_in_market", "n_trades", "n2_pct_final", "n2_pct_sharpe"]],
                   pct=pct, money=("final_value", "hold_final", "spy_final"),
                   dec2=("sharpe", "hold_sharpe", "spy_sharpe"), ints=("n_trades",)), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(t))


if __name__ == "__main__":
    main()
