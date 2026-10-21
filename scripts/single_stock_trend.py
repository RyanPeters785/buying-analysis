"""Trend rules on single stocks: does a 200-day / 10-month rule protect against picking a stock that blows up?

Pre-declared: every Dow stock in the data (44, today's members = hindsight list, illustrative only); rules
PriceVsSMA(200 days, daily) and TrendSMA(10 months); out to T-bills (no fund fee) below the average.
$5,000 a year into the single stock, from one year after listing (or 1994-01-03) to 2022-12-30; 5 bps stock
spread. Compared with buy-and-hold of the same stock, SPY on the same deposits, and 100 random-timing runs
(200-day rule). Stocks are grouped by how buy-and-hold did (worst drawdown, return vs SPY).

    uv run scripts/single_stock_trend.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd

from buying_analysis import plots
from buying_analysis.backtest import MarketData
from buying_analysis.costs import CostModel
from buying_analysis.data import ROOT
from buying_analysis.experiments import evaluate_timing, log_trials, run_parallel
from buying_analysis.metrics import summarize
from buying_analysis.report import fmt_table
from buying_analysis.strategies.benchmarks import spy_buy_and_hold
from buying_analysis.strategies.deployment import LumpSum
from buying_analysis.strategies.timing import PriceVsSMA, TrendSMA

OUT = ROOT / "outputs" / "single_stock_trend"
START, END = pd.Timestamp("1994-01-03"), "2022-12-30"
TBILL = CostModel(mmf_expense=0.0)


def windows(md: MarketData) -> dict[int, pd.Timestamp]:
    out = {}
    for p in md.permnos:
        if md.is_etf[md.col(p)]:
            continue
        first = md.first_session([int(p)])
        start = max(START, first + pd.Timedelta(days=365))
        live = md.sessions[
            (md.sessions >= start) & (md.sessions <= END) & md.tradable[:, md.col(p)]
        ]
        if len(live) > 3 * 252:
            out[int(p)] = live[0]
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md = MarketData.load(end=END)
    win = windows(md)
    jobs, keys = [], []
    for p, st in win.items():
        for s in (LumpSum(p), PriceVsSMA(p, 200), TrendSMA(p, 10), spy_buy_and_hold()):
            jobs.append((s, st, END))
            keys.append((p, s.name))
    res = run_parallel(md, jobs, costs=TBILL)
    rows = {}
    for (p, name), r in zip(keys, res):
        rows.setdefault(p, {"permno": p, "ticker": md.tickers.get(p), "start": win[p].date()})
        m = summarize(r)
        tag = {"lump_sum": "hold", "above_sma200d": "sma200", "trend_sma10m": "trend10m",
               "B1_spy_buy_hold": "spy"}[name]  # fmt: skip
        for k in ("final_value", "xirr", "sharpe", "max_drawdown", "time_in_market", "n_trades"):
            rows[p][f"{tag}_{k}"] = m[k]
    df = pd.DataFrame(rows.values())
    for t in ("sma200", "trend10m"):
        df[f"{t}_vs_hold"] = df[f"{t}_final_value"] / df["hold_final_value"] - 1
        df[f"{t}_dd_cut"] = (
            df[f"{t}_max_drawdown"] - df["hold_max_drawdown"]
        )  # positive = shallower
    df["hold_vs_spy"] = df["hold_final_value"] / df["spy_final_value"] - 1

    pct_beat = []
    for p, st in win.items():
        out = evaluate_timing(
            PriceVsSMA(p, 200), md, st, END, n_random=100, costs=TBILL, null_asset=p, log=False
        )
        pct_beat.append(out["n2_pct_final"])
    df["sma200_pct_beat_random"] = pct_beat
    log_trials([{"kind": "single_stock_trend", "strategy": f"{t}_{r['ticker']}", "permno": r["permno"],
                 "start": str(r["start"]), "final_value": r[f"{t}_final_value"]}
                for r in df.to_dict("records") for t in ("sma200", "trend10m")])  # fmt: skip

    df["group"] = np.select(
        [df["hold_max_drawdown"] <= -0.80, df["hold_vs_spy"] < 0], ["blew up (B&H drawdown ≤ −80%)",
                                                                     "lagged SPY"], "beat SPY")  # fmt: skip
    summ = df.groupby("group").agg(
        stocks=("ticker", "size"),
        hold_median_xirr=("hold_xirr", "median"),
        hold_median_dd=("hold_max_drawdown", "median"),
        sma200_median_vs_hold=("sma200_vs_hold", "median"),
        sma200_pct_beat_hold=("sma200_vs_hold", lambda v: (v > 0).mean()),
        sma200_median_dd=("sma200_max_drawdown", "median"),
        trend10m_median_vs_hold=("trend10m_vs_hold", "median"),
        trend10m_pct_beat_hold=("trend10m_vs_hold", lambda v: (v > 0).mean()),
        trend10m_median_dd=("trend10m_max_drawdown", "median"),
    )  # fmt: skip
    overall = pd.DataFrame({
        "rule": ["200-day", "10-month"],
        "pct_stocks_beating_hold": [(df["sma200_vs_hold"] > 0).mean(), (df["trend10m_vs_hold"] > 0).mean()],
        "median_vs_hold": [df["sma200_vs_hold"].median(), df["trend10m_vs_hold"].median()],
        "median_dd_cut_pts": [df["sma200_dd_cut"].median() * 100, df["trend10m_dd_cut"].median() * 100],
        "pct_stocks_sharpe_up": [(df["sma200_sharpe"] > df["hold_sharpe"]).mean(),
                                 (df["trend10m_sharpe"] > df["hold_sharpe"]).mean()],
        "median_pct_beat_random": [df["sma200_pct_beat_random"].median(), np.nan],
    })  # fmt: skip

    df.to_csv(OUT / "by_stock.csv", index=False)
    summ.to_csv(OUT / "by_group.csv")
    overall.to_csv(OUT / "overall.csv", index=False)
    plot_df = df.assign(vs_hold_pct=df["sma200_vs_hold"] * 100, label=df["group"])
    plots.strip_chart(plot_df, "vs_hold_pct", "label",
                      "200-day rule: ending value vs buy-and-hold of the same stock (dot = one stock)",
                      "% difference in ending value", OUT / "sma200_vs_hold.png")  # fmt: skip
    pct = ("hold_xirr", "sma200_xirr", "trend10m_xirr", "hold_max_drawdown", "sma200_max_drawdown",
           "trend10m_max_drawdown", "sma200_vs_hold", "trend10m_vs_hold", "hold_vs_spy", "hold_median_xirr",
           "hold_median_dd", "sma200_median_vs_hold", "sma200_pct_beat_hold", "sma200_median_dd",
           "trend10m_median_vs_hold", "trend10m_pct_beat_hold", "trend10m_median_dd",
           "pct_stocks_beating_hold", "median_vs_hold", "pct_stocks_sharpe_up")  # fmt: skip
    cols = [
        "ticker",
        "start",
        "group",
        "hold_xirr",
        "hold_max_drawdown",
        "hold_vs_spy",
        "sma200_vs_hold",
        "sma200_max_drawdown",
        "trend10m_vs_hold",
        "trend10m_max_drawdown",
        "sma200_pct_beat_random",
    ]
    txt = ["# Trend rules on single stocks (Dow stocks, 1994-2022)", "",
           fmt_table(overall, pct=pct, dec2=("median_dd_cut_pts",)), "",
           "## By how buy-and-hold did", "", fmt_table(summ.reset_index(), pct=pct), "",
           "## Every stock", "", fmt_table(df.sort_values("hold_max_drawdown")[cols], pct=pct), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt[:9]))


if __name__ == "__main__":
    main()
