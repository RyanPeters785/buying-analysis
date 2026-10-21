"""Value + profitability: buy cheap stocks that are also highly profitable (and avoid value traps).

Ken French 5x5 portfolios of US stocks sorted independently on book-to-market (BM 1 = most expensive ..
5 = cheapest) and operating profitability (OP 1 = least .. 5 = most profitable), value-weighted, monthly
from 1963-07, re-formed each June from the prior fiscal year (so only reported accounting data is used).
Combinations are cap-weighted across cells using the previous month's total market cap.

$5,000 each January, 1964-2022, assumed fund costs deducted (0.25%/yr for the tilted portfolios, 0.03% for
the market); 2023-2025 descriptive only. Reported: full period, eras, every 20-year window, a 5x5 heatmap.

    uv run scripts/value_profitability.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import t as tdist

from buying_analysis import plots
from buying_analysis.data import RAW_DIR, ROOT
from buying_analysis.experiments import log_trials
from buying_analysis.metrics import xirr
from buying_analysis.report import fmt_table
from buying_analysis.stats import holm

OUT = ROOT / "outputs" / "value_profitability"
START, END = "1964-01-31", "2022-12-31"
AMOUNT = 5000.0
FEE_TILT, FEE_MKT = 0.0025, 0.0003
COMBOS = {  # name: (bm levels, op levels)
    "cheap + most profitable (corner)": ({5}, {5}),
    "cheap + profitable (top 2 x top 2)": ({4, 5}, {4, 5}),
    "value trap: cheap + unprofitable": ({4, 5}, {1, 2}),
    "cheap (any profitability)": ({4, 5}, {1, 2, 3, 4, 5}),
    "profitable (any price)": ({1, 2, 3, 4, 5}, {4, 5}),
    "junk growth: expensive + unprofitable": ({1, 2}, {1, 2}),
}
ERAS = {"1964-1989": ("1964", "1989"), "1990-2006": ("1990", "2006"), "2007-2022": ("2007", "2022")}


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    p = pd.read_parquet(RAW_DIR / "ff_25_bm_op_monthly.parquet")
    p["cap"] = p["n_firms"] * p["avg_cap"]
    kf = pd.read_parquet(RAW_DIR / "ff_factors_daily.parquet").set_index("date")
    m = (1 + kf[["mkt", "rf"]]).resample("ME").prod() - 1
    return p, m


def combo_returns(p: pd.DataFrame) -> pd.DataFrame:
    ret = p.pivot(index="date", columns=["bm", "op"], values="ret")
    w = p.pivot(index="date", columns=["bm", "op"], values="cap").shift(
        1
    )  # weights known at month start
    out = {}
    for name, (bms, ops) in COMBOS.items():
        cols = [c for c in ret.columns if c[0] in bms and c[1] in ops]
        ww = w[cols].div(w[cols].sum(axis=1), axis=0)
        out[name] = (ret[cols] * ww).sum(axis=1, min_count=1)
    allw = w.div(w.sum(axis=1), axis=0)
    out["all 25 cells (check vs market)"] = (ret * allw).sum(axis=1, min_count=1)
    return pd.DataFrame(out).dropna()


def simulate(r: pd.Series, rf: pd.Series, fee: float, start=START, end=END) -> pd.DataFrame:
    r = r.loc[start:end] - fee / 12
    eq, rows = 0.0, []
    for t, x in r.items():
        dep = AMOUNT if (t.month == 1 or t == r.index[0]) else 0.0
        base = eq + dep
        eq = base * (1 + x)
        rows.append((t, dep, eq, x, rf.get(t, 0.0)))
    return pd.DataFrame(rows, columns=["date", "deposit", "equity", "ret", "rf"]).set_index("date")


def stats(a: pd.DataFrame) -> dict:
    idx = (1 + a["ret"]).cumprod()
    dates = list(a.index[a["deposit"] > 0]) + [a.index[-1]]
    flows = list(-a.loc[a["deposit"] > 0, "deposit"]) + [a["equity"].iloc[-1]]
    return {"final_value": a["equity"].iloc[-1], "xirr": xirr(dates, flows),
            "cagr": idx.iloc[-1] ** (12 / len(a)) - 1,
            "sharpe": (a["ret"] - a["rf"]).mean() / a["ret"].std() * np.sqrt(12),
            "max_drawdown": (idx / idx.cummax() - 1).min()}  # fmt: skip


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p, m = load()
    c = combo_returns(p)
    series = {"market": (m["mkt"], FEE_MKT), **{n: (c[n], FEE_TILT) for n in COMBOS},
              "all 25 cells (check vs market)": (c["all 25 cells (check vs market)"], FEE_MKT)}  # fmt: skip
    rows, runs = [], {}
    for name, (r, fee) in series.items():
        a = simulate(r, m["rf"], fee)
        runs[name] = a
        ex = (r - m["mkt"]).loc[START:END].dropna()
        tstat = ex.mean() / (ex.std() / np.sqrt(len(ex))) if name != "market" else np.nan
        firms = None
        if name in COMBOS:
            bms, ops = COMBOS[name]
            firms = p[p["bm"].isin(bms) & p["op"].isin(ops)].groupby("date")["n_firms"].sum()
        rows.append({"strategy": name, **stats(a), "monthly_vs_market": ex.mean() * 12 if name != "market" else 0,
                     "t_stat": tstat, "p": 2 * tdist.sf(abs(tstat), len(ex) - 1) if name != "market" else np.nan,
                     "median_firms": firms.median() if firms is not None else np.nan})  # fmt: skip
    table = pd.DataFrame(rows)
    mkt_final = table.loc[table["strategy"] == "market", "final_value"].iloc[0]
    table["vs_market"] = table["final_value"] / mkt_final - 1
    tested = table["strategy"].isin(COMBOS)
    table.loc[tested, "p_holm"] = holm(table.loc[tested, "p"]).to_numpy()
    eras = pd.DataFrame({n: {e: (1 + a.loc[s:t, "ret"]).prod() ** (12 / len(a.loc[s:t])) - 1
                             for e, (s, t) in ERAS.items()} for n, a in runs.items()}).T  # fmt: skip
    recent = pd.DataFrame([{"strategy": n, **stats(simulate(r, m["rf"], fee, "2023-01-31", "2025-12-31"))}
                           for n, (r, fee) in series.items()])  # fmt: skip

    # every 20-year window (monthly starts), ending value vs market
    roll = []
    starts = m.loc[START:END].index
    for s in starts:
        e = s + pd.DateOffset(years=20) - pd.offsets.MonthEnd(1)
        if e > pd.Timestamp(END):
            break
        base = simulate(m["mkt"], m["rf"], FEE_MKT, s, e)["equity"].iloc[-1]
        for n in COMBOS:
            roll.append({"start": s, "strategy": n,
                         "vs_market": simulate(c[n], m["rf"], FEE_TILT, s, e)["equity"].iloc[-1] / base - 1})  # fmt: skip
    roll = pd.DataFrame(roll)
    rsum = roll.groupby("strategy", sort=False)["vs_market"].agg(
        windows="size", median="median", pct_beat=lambda v: (v > 0).mean(), worst="min", best="max"
    )

    # heatmaps: annualized return of each cell minus the market (gross of fees)
    ret = p.pivot(index="date", columns=["bm", "op"], values="ret")

    def grid(a, b):
        x = ret.loc[a:b]
        ann = (1 + x).prod() ** (12 / len(x)) - 1
        mk = (1 + m["mkt"].loc[a:b]).prod() ** (12 / len(x)) - 1
        g = (ann - mk).unstack("op") * 100
        g.index = [
            f"BM{i}" + (" (expensive)" if i == 1 else " (cheap)" if i == 5 else "") for i in g.index
        ]
        g.columns = [
            f"OP{j}" + (" low" if j == 1 else " high" if j == 5 else "") for j in g.columns
        ]
        return g

    for label, (a, b) in {"1964_2022": (START, END), "2007_2022": ("2007-01-31", END)}.items():
        plots.heatmap(grid(a, b), f"Annual return minus the market, {label.replace('_', '-')} (gross of fees)",
                      "operating profitability", "book-to-market (cheapness)",
                      OUT / f"heatmap_{label}.png", fmt=lambda v: f"{v:+.1f}", cbar_label="pts per year")  # fmt: skip
    rel = {n: (runs[n]["equity"] / runs["market"]["equity"]) for n in
           ["cheap + profitable (top 2 x top 2)", "value trap: cheap + unprofitable", "profitable (any price)",
            "junk growth: expensive + unprofitable"]}  # fmt: skip
    plots.line_chart(rel, "Account value relative to the market ($5k each January, after fees)",
                     "ratio to market account (log)", OUT / "relative_to_market.png", log=True,
                     fmt=lambda v: f"{v:.2f}x")  # fmt: skip

    log_trials([{"kind": "value_profitability", **r} for r in table.to_dict("records")])
    for n, df in [
        ("results", table),
        ("eras", eras),
        ("recent_2023_2025", recent),
        ("rolling_20y", roll),
    ]:
        df.to_csv(OUT / f"{n}.csv")
    pct = (
        "xirr",
        "cagr",
        "max_drawdown",
        "monthly_vs_market",
        "vs_market",
        "median",
        "pct_beat",
        "worst",
        "best",
    )
    txt = ["# Value + profitability (Ken French 5x5 BM x OP portfolios)", "",
           f"{START} → {END}; $5,000 each January; fees {FEE_TILT:.2%}/yr tilted, {FEE_MKT:.2%}/yr market.", "",
           fmt_table(table[["strategy", "final_value", "vs_market", "xirr", "sharpe", "max_drawdown",
                            "monthly_vs_market", "t_stat", "p_holm", "median_firms"]],
                     pct=pct, money=("final_value",), dec2=("sharpe", "t_stat", "p_holm"), ints=("median_firms",)),
           "", "`monthly_vs_market` is the gross average return gap, annualized (x12).", "",
           "## Annualized return by era (after fees)", "",
           fmt_table(eras.reset_index(names="strategy"), pct=tuple(eras.columns)), "",
           "## Every 20-year window (monthly starts), ending value vs market", "", fmt_table(rsum.reset_index(), pct=pct),
           "", "## 2023-2025 (descriptive)", "",
           fmt_table(recent[["strategy", "final_value", "xirr", "max_drawdown"]], pct=pct, money=("final_value",)),
           ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
