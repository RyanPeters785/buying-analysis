"""Country momentum and US-vs-international trajectory study (prices only, always invested).

Pre-declared, no tuning:
  A. Country momentum: monthly, hold the 3 country funds (22 countries + SPY for the US) with the best
     12-1 month total return. Window 1997-04 → 2022-12. Vs SPY, equal weight of all countries, and 100
     random 3-country portfolios.
  B. US vs international switch: monthly, hold SPY or EFA, whichever had the higher 12-month return.
     Window 2002-09 → 2022-12. Vs SPY, EFA, 50/50, and 100 random switching schedules with the same
     number of switches and time in EFA.
  C. Descriptive: rolling 5- and 10-year annualized return gaps, US minus developed ex-US / emerging / the
     equal-weight average country.
2023-2025 is reported as descriptive only. Costs at 1x and 5x the default spread (country ETFs trade wider).

    uv run scripts/country_momentum.py
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd

from buying_analysis import plots
from buying_analysis.backtest import Context, MarketData
from buying_analysis.costs import CostModel
from buying_analysis.data import ROOT, load_country_etfs
from buying_analysis.experiments import evaluate_timing, log_trials, run_parallel
from buying_analysis.metrics import summarize
from buying_analysis.report import fmt_table, period_returns
from buying_analysis.strategies.benchmarks import EqualWeight, FixedMix, spy_buy_and_hold
from buying_analysis.strategies.deployment import LumpSum
from buying_analysis.strategies.nulls import in_market_spells, random_schedule
from buying_analysis.strategies.timing import SPY, Allocator, SectorRotation, month_end_positions

OUT = ROOT / "outputs" / "countries"
A_START, B_START, END = "1997-04-01", "2002-09-03", "2022-12-30"
RECENT = ("2023-01-03", "2025-12-31")
N_RANDOM = 100


class RelativeMomentum(Allocator):
    """Monthly: hold ``a`` or ``b``, whichever had the higher ``months``-month total return."""

    frequency = "monthly"

    def __init__(self, a: int, b: int, months: int = 12, name: str = "us_vs_intl_12m"):
        self.a, self.b, self.months, self.name = a, b, months, name
        self.assets = (a, b)

    def allocation(self, ctx: Context):
        me = month_end_positions(ctx)
        if len(me) < self.months + 1:
            return None
        i, j = me[-self.months - 1], me[-1]
        xa, xb = ctx.close(self.a), ctx.close(self.b)
        if np.isnan([xa[i], xb[i]]).any():
            return None
        return {self.a: 1.0} if xa[j] / xa[i] >= xb[j] / xb[i] else {self.b: 1.0}


class RandomSwitch(Allocator):
    """Null for B: a pre-drawn schedule says when to hold ``b`` instead of ``a`` (no market data)."""

    def __init__(self, a: int, b: int, schedule: pd.Series, seed: int):
        self.a, self.b, self.schedule = a, b, schedule
        self.assets = (a, b)
        self.name = f"random_switch_{seed}"

    def allocation(self, ctx: Context):
        return {self.b: 1.0} if bool(self.schedule.get(ctx.date, False)) else {self.a: 1.0}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = load_country_etfs()
    tick = c.groupby("permno")["ticker"].last()
    efa, eem = int(tick[tick == "EFA"].index[0]), int(tick[tick == "EEM"].index[0])
    countries = [SPY] + [int(p) for p in tick.index if p not in (efa, eem)]
    md = MarketData.load(permnos=[SPY, *tick.index], extra=c)

    # A. country momentum
    mom = SectorRotation(k=3, lookback=12, skip=1, universe=countries)
    mom.name = "country_top3_12-1"
    ew = EqualWeight(countries, "monthly", name="equal_weight_countries")
    out_a = evaluate_timing(mom, md, A_START, END, n_random=N_RANDOM)
    res_a = {mom.name: out_a["_res"]}
    for s, r in zip([spy_buy_and_hold(), ew], run_parallel(md, [(spy_buy_and_hold(), A_START, END),
                                                               (ew, A_START, END)])):  # fmt: skip
        res_a[s.name] = r
    n2a = out_a["_n2"]["final_value"]

    # B. US vs international switch
    rel = RelativeMomentum(SPY, efa)
    b_strats = [
        rel,
        spy_buy_and_hold(),
        LumpSum(efa),
        FixedMix({SPY: 0.5, efa: 0.5}, "monthly", "50_50_us_intl"),
    ]
    b_strats[2].name = "EFA_buy_hold"
    res_b = dict(
        zip([s.name for s in b_strats], run_parallel(md, [(s, B_START, END) for s in b_strats]))
    )
    w = res_b[rel.name].weights.get(efa, pd.Series(0.0, index=res_b[rel.name].daily.index))
    w = w.reindex(res_b[rel.name].daily.index).fillna(0)
    spells, n_in, n = in_market_spells(w)
    nulls = [RandomSwitch(SPY, efa, pd.Series(random_schedule(n, n_in, spells, np.random.default_rng(s)),
                                              index=w.index), s) for s in range(N_RANDOM)]  # fmt: skip
    n2b = pd.Series(
        [summarize(r)["final_value"] for r in run_parallel(md, [(s, B_START, END) for s in nulls])]
    )

    # summaries, costs, halves, recent
    rows = []
    for label, res in (("A", res_a), ("B", res_b)):
        for name, r in res.items():
            m = summarize(r) | {"study": label}
            if name == mom.name:
                m["pct_beat_random"] = float((n2a < m["final_value"]).mean() * 100)
            if name == rel.name:
                m |= {"pct_beat_random": float((n2b < m["final_value"]).mean() * 100),
                      "months_in_intl": round(n_in / 21), "switches": spells}  # fmt: skip
            rows.append(m)
    table = pd.DataFrame(rows)
    hi_cost = CostModel(spread_multiplier=5.0)
    for s, st, r in zip([mom, rel], [A_START, B_START],
                        run_parallel(md, [(mom, A_START, END), (rel, B_START, END)], costs=hi_cost)):  # fmt: skip
        table.loc[table["strategy"] == s.name, "xirr_costs_x5"] = summarize(r)["xirr"]
    halves = pd.concat([
        period_returns(res_a, {"1997-2009": ("1997-01-01", "2009-12-31"), "2010-2022": ("2010-01-01", END)}),
        period_returns(res_b, {"2002-2009": ("2002-01-01", "2009-12-31"), "2010-2022": ("2010-01-01", END)}),
    ])  # fmt: skip
    recent_strats = [mom, ew, rel, spy_buy_and_hold(), b_strats[2], b_strats[3]]
    recent = pd.DataFrame(
        [summarize(r) for r in run_parallel(md, [(s, *RECENT) for s in recent_strats])]
    )
    log_trials([{"kind": "country", **r} for r in table.to_dict("records")])

    # C. rolling gaps (total-return indexes, monthly)
    gaps = rolling_gaps(md, countries, efa, eem)

    table.to_csv(OUT / "results.csv", index=False)
    halves.to_csv(OUT / "halves.csv")
    recent.to_csv(OUT / "recent_2023_2025.csv", index=False)
    gaps.to_csv(OUT / "rolling_gaps.csv")
    plots.line_chart({k: v.dropna() * 100 for k, v in gaps.items() if k.startswith("10y")},
                     "US annualized return minus other markets, rolling 10 years", "percentage points",
                     OUT / "rolling_10y_gap.png", fmt=lambda v: f"{v:+.1f}pp", zero_line=True)  # fmt: skip
    write_report(table, halves, recent, gaps, n2a, n2b)


def rolling_gaps(md: MarketData, countries, efa, eem) -> pd.DataFrame:
    s = md.sessions
    me = s[np.r_[(s.year * 12 + s.month)[1:] != (s.year * 12 + s.month)[:-1], True]]
    px = pd.DataFrame(md.close_idx, index=s, columns=md.permnos).loc[me]
    mret = px.pct_change()
    ew_ex_us = mret[[p for p in countries if p != SPY]].mean(axis=1, skipna=True)
    series = {"US (SPY)": mret[SPY], "developed ex-US (EFA)": mret[efa], "emerging (EEM)": mret[eem],
              "avg country ex-US": ew_ex_us}  # fmt: skip
    out = {}
    for yrs in (5, 10):
        k = 12 * yrs
        ann = {n: (1 + r).rolling(k, min_periods=k).apply(np.prod, raw=True) ** (1 / yrs) - 1
               for n, r in series.items()}  # fmt: skip
        for n in list(series)[1:]:
            out[f"{yrs}y US minus {n}"] = ann["US (SPY)"] - ann[n]
    return pd.DataFrame(out)


def write_report(table, halves, recent, gaps, n2a, n2b) -> None:
    pct = ("xirr", "xirr_costs_x5", "max_drawdown")
    cols = ["study", "strategy", "start", "final_value", "xirr", "xirr_costs_x5", "sharpe", "max_drawdown",
            "n_trades", "pct_beat_random", "months_in_intl", "switches"]  # fmt: skip
    last = gaps.dropna(how="all").iloc[-1]
    txt = ["# Country momentum and US vs international", "", "$5,000 each January; always invested.", "",
           fmt_table(table[[c for c in cols if c in table]], pct=pct, money=("final_value",), dec2=("sharpe",),
                     ints=("n_trades",)), "",
           f"Random-portfolio medians: A ${n2a.median() / 1e3:,.0f}k, B ${n2b.median() / 1e3:,.0f}k.", "",
           "## Annualized return by sub-period", "", fmt_table(halves.reset_index(names="strategy"),
                                                              pct=tuple(halves.columns)), "",
           "## 2023-2025 (descriptive only)", "",
           fmt_table(recent[["strategy", "final_value", "xirr", "max_drawdown"]], pct=pct, money=("final_value",)),
           "", f"## Rolling gaps, latest ({gaps.dropna(how='all').index[-1]:%Y-%m})", "",
           fmt_table(last.rename_axis("series").rename("gap").reset_index(), pct=("gap",)), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
