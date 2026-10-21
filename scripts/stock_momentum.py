"""Stock momentum (12-1): hold the stocks with the highest return over the past 12 months, skipping the most
recent month. Ken French value-weighted momentum portfolios, rebalanced monthly, 1927-2022.

Portfolios: top 10% (decile 10), top 20% (deciles 9-10, cap-weighted), big-company winners (top 30% of
large caps, the most investable), and losers (bottom 10%) for contrast. Momentum turns over heavily, so the
after-cost drag is a key unknown: 0.5% / 1% / 2% a year (1% is the headline). Market charged 0.03%.
$5,000 each January; eras (incl. after the 1993 publication), every 20-year window, momentum crashes,
2023-2025 descriptive only.

    uv run scripts/stock_momentum.py
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

OUT = ROOT / "outputs" / "stock_momentum"
START, END = "1927-01-31", "2022-12-31"
DRAGS = (0.005, 0.01, 0.02)
HEADLINE = 0.01
FEE_MKT = 0.0003
ERAS = {"1927-1963": ("1927", "1963"), "1964-1993": ("1964", "1993"), "1994-2022 (after publication)":
        ("1994", "2022"), "2007-2022": ("2007", "2022")}  # fmt: skip


def portfolios() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pd.read_parquet(RAW_DIR / "ff_10_momentum_monthly.parquet")
    s = pd.read_parquet(RAW_DIR / "ff_6_size_momentum_monthly.parquet")
    ret = d.pivot(index="date", columns="col", values="ret")
    cap = (d["n_firms"] * d["avg_size"]).set_axis(d.index)
    w = d.assign(cap=cap).pivot(index="date", columns="col", values="cap").shift(1)
    top2 = (ret[[9, 10]] * w[[9, 10]].div(w[[9, 10]].sum(axis=1), axis=0)).sum(axis=1, min_count=2)
    s_ret = s.pivot(index="date", columns="cell", values="ret")
    p = pd.DataFrame({"top 10% (decile 10)": ret[10], "top 20% (deciles 9-10)": top2,
                      "big-company winners (top 30% of large caps)": s_ret["BIG HiPRIOR"],
                      "losers (bottom 10%)": ret[1]})  # fmt: skip
    firms = pd.DataFrame({"top 10% (decile 10)": d[d["col"] == 10].set_index("date")["n_firms"],
                          "top 20% (deciles 9-10)": d[d["col"] >= 9].groupby("date")["n_firms"].sum(),
                          "big-company winners (top 30% of large caps)":
                              s[s["cell"] == "BIG HiPRIOR"].set_index("date")["n_firms"],
                          "losers (bottom 10%)": d[d["col"] == 1].set_index("date")["n_firms"]})  # fmt: skip
    kf = pd.read_parquet(RAW_DIR / "ff_factors_daily.parquet").set_index("date")
    m = (1 + kf[["mkt", "rf"]]).resample("ME").prod() - 1
    return p.dropna(), m.assign(firms=np.nan), firms


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p, m, firms = portfolios()
    runs, rows = {"market": simulate(m["mkt"], m["rf"], FEE_MKT, START, END)}, []
    rows.append({"strategy": "market", **stats(runs["market"])})
    for name in p.columns:
        a = simulate(p[name], m["rf"], HEADLINE, START, END)
        runs[name] = a
        row = {"strategy": name, **stats(a), "median_firms": firms[name].loc[START:END].median()}
        for d in DRAGS:
            row[f"xirr_drag_{d:.1%}"] = stats(simulate(p[name], m["rf"], d, START, END))["xirr"]
        ex = (p[name] - m["mkt"]).loc[START:END]
        row["gross_gap_per_yr"] = ex.mean() * 12
        row["t_stat"] = ex.mean() / (ex.std() / np.sqrt(len(ex)))
        rows.append(row)
    table = pd.DataFrame(rows)
    table["vs_market"] = table["final_value"] / table.loc[0, "final_value"] - 1
    eras = pd.DataFrame({n: {e: (1 + a.loc[s:t, "ret"]).prod() ** (12 / len(a.loc[s:t])) - 1
                             for e, (s, t) in ERAS.items()} for n, a in runs.items()}).T  # fmt: skip

    # crashes: worst 3- and 12-month stretches for the top decile relative to the market
    rel = (1 + p["top 10% (decile 10)"]).div(1 + m["mkt"]).loc[START:END]
    crash = []
    for k in (3, 12):
        r = rel.rolling(k).apply(np.prod, raw=True) - 1
        for when in r.nsmallest(40).index:
            if all(abs((when - c["end"]).days) > 400 for c in crash if c["months"] == k):
                crash.append({"months": k, "end": when, "top10_vs_market": r.at[when],
                              "top10": (1 + p["top 10% (decile 10)"]).loc[:when].tail(k).prod() - 1,
                              "market": (1 + m["mkt"]).loc[:when].tail(k).prod() - 1})  # fmt: skip
            if sum(c["months"] == k for c in crash) == 3:
                break
    crash = pd.DataFrame(crash)

    roll = []
    for s in m.loc[START:END].index:
        e = s + pd.DateOffset(years=20) - pd.offsets.MonthEnd(1)
        if e > pd.Timestamp(END):
            break
        base = simulate(m["mkt"], m["rf"], FEE_MKT, s, e)["equity"].iloc[-1]
        for n in p.columns:
            roll.append({"start": s, "strategy": n,
                         "vs_market": simulate(p[n], m["rf"], HEADLINE, s, e)["equity"].iloc[-1] / base - 1})  # fmt: skip
    roll = pd.DataFrame(roll)
    rsum = roll.groupby("strategy", sort=False)["vs_market"].agg(
        windows="size", median="median", pct_beat=lambda v: (v > 0).mean(), worst="min", best="max"
    )
    recent = pd.DataFrame([{"strategy": n, **stats(simulate(r, m["rf"], HEADLINE if n != "market" else FEE_MKT,
                                                            "2023-01-31", "2025-12-31"))}
                           for n, r in {"market": m["mkt"], **{c: p[c] for c in p.columns}}.items()])  # fmt: skip

    relw = {
        n: runs[n]["equity"] / runs["market"]["equity"]
        for n in p.columns
        if not n.startswith("losers")
    }
    plots.line_chart(relw, "Account value relative to the market ($5k each January, 1% cost drag)",
                     "ratio to market account (log)", OUT / "relative_to_market.png", log=True,
                     fmt=lambda v: f"{v:.2f}x")  # fmt: skip
    log_trials([{"kind": "stock_momentum", **r} for r in table.to_dict("records")])
    for n, df in [("results", table), ("eras", eras), ("crashes", crash), ("rolling_20y", roll),
                  ("recent_2023_2025", recent)]:  # fmt: skip
        df.to_csv(OUT / f"{n}.csv")
    drag_cols = [f"xirr_drag_{d:.1%}" for d in DRAGS]
    pct = ("xirr", "max_drawdown", "vs_market", "gross_gap_per_yr", "median", "pct_beat", "worst", "best",
           "top10_vs_market", "top10", "market", *drag_cols)  # fmt: skip
    txt = ["# Stock momentum (12-1), Ken French portfolios", "",
           f"{START} → {END}; $5,000 each January; headline cost drag {HEADLINE:.1%}/yr (market {FEE_MKT:.2%}).", "",
           fmt_table(table[["strategy", "final_value", "vs_market", "xirr", *drag_cols, "sharpe", "max_drawdown",
                            "gross_gap_per_yr", "t_stat", "median_firms"]],
                     pct=pct, money=("final_value",), dec2=("sharpe", "t_stat"), ints=("median_firms",)), "",
           "## Annualized return by era (1% drag)", "",
           fmt_table(eras.reset_index(names="strategy"), pct=tuple(eras.columns)), "",
           "## Every 20-year window (monthly starts), ending value vs market", "", fmt_table(rsum.reset_index(), pct=pct),
           "", "## Momentum crashes: worst stretches for the top decile vs the market", "",
           fmt_table(crash.assign(end=crash["end"].dt.strftime("%Y-%m")), pct=pct), "",
           "## 2023-2025 (descriptive)", "",
           fmt_table(recent[["strategy", "final_value", "xirr", "max_drawdown"]], pct=pct, money=("final_value",)),
           ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
