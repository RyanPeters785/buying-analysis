"""Run the whole study end to end: data validation, then every development experiment (through 2022).

    uv run scripts/run_all.py            # development results (1993-2022), ~15 min
    uv run scripts/run_all.py --quick    # fewer random-timing / bootstrap draws, for checking the pipeline
    uv run scripts/run_all.py --lockbox  # the one-time 2023-2025 evaluation of the pre-registered list

Outputs go to outputs/ (CSV, PNG, report_tables.md). All results are hypothetical.
"""

from __future__ import annotations

import os

# one math thread per process: the parallel workers already use every core
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from buying_analysis import plots
from buying_analysis.backtest import Engine, MarketData, contribution_schedule
from buying_analysis.costs import CostModel
from buying_analysis.data import KF_MARKET, ROOT, load_ken_french_panel
from buying_analysis.experiments import (
    evaluate_deployment,
    evaluate_timing,
    log_trials,
    rolling_windows,
    run_parallel,
)
from buying_analysis.metrics import drawdown, summarize
from buying_analysis.report import (
    KF_REGIMES,
    MAIN_COLS,
    REGIMES,
    add_holm,
    calendar_returns,
    family_table,
    fmt_table,
    period_returns,
    twr,
)
from buying_analysis.strategies.benchmarks import EqualWeight, sixty_forty, spy_buy_and_hold
from buying_analysis.strategies.deployment import DCA, LumpSum
from buying_analysis.strategies.dip import BuyTheDip
from buying_analysis.strategies.learned import SwingModel
from buying_analysis.strategies.timing import (
    IEF,
    RSI2,
    SECTORS,
    SPY,
    DualMomentum,
    SectorRotation,
    SMACross,
    TrendSMA,
    VolTarget,
)

OUT = ROOT / "outputs"
CACHE = (
    ROOT / "data" / "cache" / "dev_results.pkl"
)  # contains CRSP-derived series: stays under data/
LOG = True  # write trials.csv (off for --quick pipeline checks)
DIP_GRID = [(x, n) for x in (0.05, 0.10, 0.15, 0.20) for n in (3, 6, 12)]
SWING_GRID = [(k, th, c) for k in (5, 10, 21) for th in (0.50, 0.55) for c in (0.1, 1.0)]
SPY_START = "1994-01-03"  # one year of history for 200-day / 52-week signals
SWING_START = "1997-01-02"  # three years of labelled samples for the first fit
DEV_END = "2022-12-30"

PCT = ("xirr", "b1_xirr", "cagr_twr", "max_drawdown", "time_in_market", "final_value_ratio_lo",
       "final_value_ratio_hi", "median_vs_b1", "pct_windows_beat_b1")  # fmt: skip
MONEY = ("final_value", "b1_final", "total_costs", "n1_final", "n2_median_final")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def timing_strategies():
    return [
        (TrendSMA(), SPY_START), (SMACross(), SPY_START), (VolTarget(), SPY_START), (RSI2(), SPY_START),
        (SectorRotation(), "2000-02-01"), (DualMomentum(), "2003-09-02"),
    ]  # fmt: skip


def deployment_spy():
    return [LumpSum(SPY), DCA(SPY, "monthly"), DCA(SPY, "weekly")] + [
        BuyTheDip(SPY, x, n) for x, n in DIP_GRID
    ]


def main_spy(md, n_random, n_boot, cfg):
    """Families: SPY deployment, timing (with nulls), swing grid (with nulls), benchmarks B2/B3."""
    tables, results, nulls = [], {}, {}
    # deployment on SPY
    strategies = deployment_spy()
    res = run_parallel(md, [(s, SPY_START, DEV_END) for s in [spy_buy_and_hold(), *strategies]])
    b1 = res[0]
    results["B1_spy_buy_hold"] = b1
    pairs = []
    for s, r in zip(strategies, res[1:]):
        results[s.name] = r
        pairs.append((r, b1, {"family": "deployment"}))
    tables.append(family_table(pairs, n_boot))
    log("deployment family done")
    # timing defaults with nulls
    pairs = []
    for s, st in timing_strategies():
        out = evaluate_timing(s, md, st, DEV_END, n_random=n_random, log=LOG)
        results[s.name] = out["_res"]
        nulls[s.name] = out["_n2"]
        keep = {k: out[k] for k in ("n1_exposure", "n1_final", "n1_sharpe", "n2_median_final",
                                    "n2_pct_final", "n2_pct_sharpe", "trades_after_suspect_spy_dates")}  # fmt: skip
        pairs.append((out["_res"], out["_b1"], {"family": "timing", **keep}))
        log(f"timing {s.name} done")
    tables.append(family_table(pairs, n_boot))
    # swing grid: strategy runs in parallel, then nulls
    swings = [SwingModel(k=k, threshold=th, C=c) for k, th, c in SWING_GRID]
    sres = run_parallel(md, [(s, SWING_START, DEV_END) for s in swings])
    pairs = []
    for s, r in zip(swings, sres):
        out = evaluate_timing(s, md, SWING_START, DEV_END, n_random=n_random, res=r, log=LOG)
        results[s.name] = r
        nulls[s.name] = out["_n2"]
        keep = {k: out[k] for k in ("n1_exposure", "n1_final", "n2_median_final", "n2_pct_final",
                                    "n2_pct_sharpe", "trades_after_suspect_spy_dates")}  # fmt: skip
        pairs.append((r, out["_b1"], {"family": "swing", **keep}))
    tables.append(family_table(pairs, n_boot))
    log("swing family done")
    # benchmarks B2 / B3 against B1 on their windows
    b2, b3 = sixty_forty(), EqualWeight(md.permnos)
    b2_start = str(md.first_session([SPY, IEF]).date())
    r2, r2b1, r3 = run_parallel(md, [(b2, b2_start, DEV_END), (spy_buy_and_hold(), b2_start, DEV_END),
                                     (b3, SPY_START, DEV_END)])  # fmt: skip
    results[b2.name], results[b3.name] = r2, r3
    tables.append(family_table([(r2, r2b1, {"family": "benchmark"}), (r3, b1, {"family": "benchmark"})],
                               n_boot))  # fmt: skip
    df = add_holm(pd.concat(tables, ignore_index=True))
    return df, results, nulls


def cost_sensitivity(md):
    jobs = [(s, SPY_START, DEV_END) for s in [spy_buy_and_hold(), *deployment_spy()]]
    jobs += [(s, st, DEV_END) for s, st in timing_strategies()]
    jobs += [(SwingModel(k=k, threshold=th, C=c), SWING_START, DEV_END) for k, th, c in SWING_GRID]
    rows = []
    for mult in (0.0, 1.0, 2.0):
        cm = CostModel(spread_multiplier=mult)
        for (s, st, _), r in zip(jobs, run_parallel(md, jobs, costs=cm)):
            rows.append({"spread_multiplier": mult, **summarize(r)})
        log(f"costs x{mult:g} done")
    return pd.DataFrame(rows)


def framing_b(md):
    """Everyone starts with the same pile (all deposits on day 1); DCA draws it down over 12 months."""
    sessions = md.sessions[(md.sessions >= SPY_START) & (md.sessions <= DEV_END)]
    total = 5000.0 * sessions.year.nunique()
    eng = Engine(md)
    rows = []
    for s in [spy_buy_and_hold(), *deployment_spy()]:
        dep = contribution_schedule(md.sessions, total, "once", start=SPY_START)
        rows.append(summarize(eng.run(s, dep, start=SPY_START, end=DEV_END)))
    return pd.DataFrame(rows)


def rolling(md):
    strategies = [DCA(SPY, "monthly"), DCA(SPY, "weekly")] + [
        BuyTheDip(SPY, x, n) for x, n in DIP_GRID
    ]
    strategies += [s for s, _ in timing_strategies()]
    frames = [rolling_windows(md, strategies, y, DEV_END) for y in (10, 20)]
    return pd.concat(frames, ignore_index=True)


def summarize_rolling(df):
    g = df[df["strategy"] != "B1_spy_buy_hold"].groupby(["years_window", "strategy"])
    return g.agg(windows=("final_vs_b1", "size"), median_vs_b1=("final_vs_b1", "median"),
                 pct_windows_beat_b1=("final_vs_b1", lambda v: (v > 0).mean()),
                 worst_vs_b1=("final_vs_b1", "min"), best_vs_b1=("final_vs_b1", "max")).reset_index()  # fmt: skip


def ken_french():
    md = MarketData.load(prices=load_ken_french_panel(), end=DEV_END)
    start = "1927-07-01"
    strategies = [LumpSum(KF_MARKET), DCA(KF_MARKET, "monthly"), BuyTheDip(KF_MARKET, 0.10, 6),
                  TrendSMA(KF_MARKET), SMACross(KF_MARKET), VolTarget(KF_MARKET), RSI2(KF_MARKET)]  # fmt: skip
    res = run_parallel(md, [(s, start, DEV_END) for s in strategies])
    names = [s.name for s in strategies]
    pairs = [(r, res[0], {"family": "ken_french"}) for r in res]
    table = family_table(pairs, 500)
    table["strategy"] = names
    regimes = period_returns(dict(zip(names, res)), KF_REGIMES)
    win = rolling_windows(md, strategies[1:], 20, DEV_END, step_months=3, warmup_days=400,
                          benchmark=strategies[0])  # fmt: skip
    win = win[win["strategy"] != strategies[0].name]
    return table, regimes, win


def make_plots(results, nulls, dep_tickers, roll):
    p = OUT
    show = ["B1_spy_buy_hold", "dca_monthly", "trend_sma10m", "sma_cross_50_200", "rsi2_10_70"]
    eq = {n: results[n].daily["equity"] for n in show}
    plots.line_chart(eq, "Account value, $5k deposited each January (1994-2022)", "USD (log scale)",
                     p / "equity_curves.png", bench="B1_spy_buy_hold", log=True,
                     fmt=lambda v: f"${v / 1000:,.0f}k")  # fmt: skip
    dd = {n: drawdown((1 + twr(results[n])).cumprod()) * 100
          for n in ["B1_spy_buy_hold", "trend_sma10m", "sma_cross_50_200", "vol_target_15_21d"]}  # fmt: skip
    plots.line_chart(dd, "Drawdown from peak (time-weighted)", "% below peak", p / "drawdowns.png",
                     bench="B1_spy_buy_hold", fmt=lambda v: f"{v:.0f}%")  # fmt: skip
    b1 = twr(results["B1_spy_buy_hold"])
    roll3 = {}
    for n in ["trend_sma10m", "sma_cross_50_200", "vol_target_15_21d", "rsi2_10_70"]:
        a = twr(results[n]).reindex(b1.index).fillna(0)
        ex = (1 + a).rolling(756).apply(np.prod, raw=True) ** (1 / 3) - (1 + b1).rolling(756).apply(
            np.prod, raw=True) ** (1 / 3)  # fmt: skip
        roll3[n] = ex.dropna() * 100
    plots.line_chart(roll3, "Rolling 3-year annualized return minus SPY", "percentage points",
                     p / "rolling_3y_excess.png", fmt=lambda v: f"{v:+.1f}pp", zero_line=True)  # fmt: skip
    vals = {
        n: nulls[n]["final_value"].to_numpy() / 1000 for n in nulls if not n.startswith("swing")
    }
    marks = {n: results[n].daily["equity"].iloc[-1] / 1000 for n in vals}
    plots.hist_panels(vals, marks, "Final value vs 100 random-timing runs with the same time in market",
                      "final value ($k)", p / "random_timing.png")  # fmt: skip
    x = dep_tickers[dep_tickers["strategy"] != "B1_spy_buy_hold"].copy()
    ls = x[x["strategy"] == "lump_sum"].set_index("permno")["xirr"]
    x["vs_lump_pp"] = (x["xirr"] - x["permno"].map(ls)) * 100
    plots.strip_chart(x[x["strategy"] != "lump_sum"], "vs_lump_pp", "strategy",
                      "Annual return vs lump sum, each dot = one ticker (1 yr after listing - 2022)",
                      "percentage points per year (XIRR)", p / "deployment_vs_lump.png")  # fmt: skip
    for y in (10, 20):
        r = roll[(roll["years_window"] == y) & (roll["strategy"] != "B1_spy_buy_hold")].copy()
        r["final_vs_b1_pct"] = r["final_vs_b1"] * 100
        plots.strip_chart(r, "final_vs_b1_pct", "strategy",
                          f"Final value vs SPY, every {y}-year window (dot = start month)",
                          "% difference in final value", p / f"rolling_{y}y_windows.png")  # fmt: skip


def write_tables(main, dep_sum, costs, fb, roll_sum, regimes, cal, kf, kf_reg, kf_roll):
    t = ["# Report tables (generated by scripts/run_all.py)", "",
         ("All values hypothetical: $5,000 deposited on the first trading day of each year; development "
         "window through 2022. Lockbox (2023-2025) not included."), ""]  # fmt: skip
    cols = MAIN_COLS + ["final_value_ratio_lo", "final_value_ratio_hi", "final_value_ratio_p_holm",
                        "sharpe_diff_p", "dsr_vs_b1", "n2_pct_final", "n2_pct_sharpe"]  # fmt: skip
    for fam in main["family"].unique():
        d = main[main["family"] == fam][[c for c in cols if c in main]]
        t += [f"## {fam}", "", fmt_table(d, pct=PCT, money=MONEY,
              dec2=("sharpe", "b1_sharpe", "final_value_ratio_p_holm", "sharpe_diff_p", "dsr_vs_b1"),
              ints=("n_trades",)), ""]  # fmt: skip
    t += [
        "## Deployment across tickers (vs lump sum and SPY)",
        "",
        dep_sum.to_markdown(index=False),
        "",
    ]
    piv = costs.pivot_table(
        index="strategy", columns="spread_multiplier", values="xirr", sort=False
    )
    piv.columns = [f"xirr_costs_x{c:g}" for c in piv.columns]
    t += ["## Cost sensitivity (XIRR at 0x / 1x / 2x spreads)", "",
          fmt_table(piv.reset_index(), pct=tuple(piv.columns)), ""]  # fmt: skip
    t += ["## Framing (b): same pile on day 1, DCA over 12 months", "",
          fmt_table(fb[["strategy", "final_value", "xirr", "max_drawdown", "time_in_market"]],
                    pct=PCT, money=MONEY), ""]  # fmt: skip
    t += ["## Rolling start dates (final value vs SPY on the same deposits)", "",
          fmt_table(roll_sum, pct=PCT + ("worst_vs_b1", "best_vs_b1")), ""]  # fmt: skip
    t += ["## Annualized return by regime", "", fmt_table(regimes.reset_index(names="strategy"),
          pct=tuple(regimes.columns)), ""]  # fmt: skip
    t += [
        "## Calendar-year returns",
        "",
        fmt_table(cal.reset_index(names="year"), pct=tuple(cal.columns)),
        "",
    ]
    t += ["## Ken French US market 1927-2022", "",
          fmt_table(kf[[c for c in MAIN_COLS + ["final_value_ratio_lo", "final_value_ratio_hi"] if c in kf]],
                    pct=PCT, money=MONEY, dec2=("sharpe", "b1_sharpe"), ints=("n_trades",)), "",
          "### By regime", "", fmt_table(kf_reg.reset_index(names="strategy"), pct=tuple(kf_reg.columns)), "",
          "### Every 20-year window (quarterly starts), final value vs lump sum", "",
          fmt_table(summarize_rolling(kf_roll.assign(years_window=20)), pct=PCT + ("worst_vs_b1", "best_vs_b1")),
          ""]  # fmt: skip
    (OUT / "report_tables.md").write_text("\n".join(t))


RESUME = False  # --resume: reuse stages cached by an earlier run of the same code


def stage(name: str, fn):
    """Run a pipeline stage, caching its result under data/cache so --resume can skip it."""
    path = CACHE.parent / f"stage_{name}.pkl"
    if RESUME and path.exists():
        log(f"{name}: reusing {path.name}")
        with open(path, "rb") as fh:
            return pickle.load(fh)
    out = fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(out, fh)
    return out


def run_dev(quick: bool, cfg: dict) -> None:
    global LOG
    LOG = not quick
    n_random, n_boot = (20, 200) if quick else (100, 1000)
    md = MarketData.load([SPY, IEF, *SECTORS], end=DEV_END)
    md_all = MarketData.load(end=DEV_END)
    log("main SPY suite")
    main, results, nulls = stage("main", lambda: main_spy(md_all, n_random, n_boot, cfg))
    main.to_csv(OUT / "main_spy.csv", index=False)
    log("deployment across tickers")
    dep = stage(
        "deploy", lambda: evaluate_deployment(md_all, list(md_all.permnos), DEV_END, log=LOG)
    )
    dep.to_csv(OUT / "deployment_by_ticker.csv", index=False)
    dep_sum = deployment_summary(dep, md_all)
    dep_sum.to_csv(OUT / "deployment_summary.csv", index=False)
    log("cost sensitivity")
    costs = stage("costs", lambda: cost_sensitivity(md))
    costs.to_csv(OUT / "cost_sensitivity.csv", index=False)
    fb = stage("framing_b", lambda: framing_b(md))
    fb.to_csv(OUT / "framing_b.csv", index=False)
    log("rolling windows")
    roll = stage("rolling", lambda: rolling(md))
    roll.to_csv(OUT / "rolling_windows.csv", index=False)
    roll_sum = summarize_rolling(roll)
    roll_sum.to_csv(OUT / "rolling_summary.csv", index=False)
    spy_only = {
        n: r
        for n, r in results.items()
        if not n.startswith(("swing", "B2", "B3", "sector", "dual"))
    }
    regimes = period_returns(spy_only, REGIMES)
    cal = calendar_returns({n: results[n] for n in ["B1_spy_buy_hold", "dca_monthly", "trend_sma10m",
                                                    "sma_cross_50_200", "vol_target_15_21d", "rsi2_10_70"]})  # fmt: skip
    regimes.to_csv(OUT / "regimes.csv")
    cal.to_csv(OUT / "calendar_years.csv")
    log("Ken French long history")
    kf, kf_reg, kf_roll = stage("ken_french", ken_french)
    kf.to_csv(OUT / "ken_french.csv", index=False)
    kf_reg.to_csv(OUT / "ken_french_regimes.csv")
    kf_roll.to_csv(OUT / "ken_french_rolling.csv", index=False)
    CACHE.parent.mkdir(exist_ok=True)
    with open(CACHE, "wb") as fh:
        pickle.dump((main, results, nulls, dep, dep_sum, costs, fb, roll, roll_sum, regimes, cal, kf,
                     kf_reg, kf_roll), fh)  # fmt: skip
    finish()


def finish() -> None:
    """Plots and markdown tables from the cached results (``--plots-only`` reruns just this)."""
    with open(CACHE, "rb") as fh:
        (main, results, nulls, dep, dep_sum, costs, fb, roll, roll_sum, regimes, cal, kf, kf_reg,
         kf_roll) = pickle.load(fh)  # fmt: skip
    log("plots and tables")
    make_plots(results, nulls, dep, roll)
    write_tables(main, dep_sum, costs, fb, roll_sum, regimes, cal, kf, kf_reg, kf_roll)
    log("done")


def deployment_summary(dep: pd.DataFrame, md: MarketData) -> pd.DataFrame:
    etf = {int(p) for p, e in zip(md.permnos, md.is_etf) if e}
    b1 = dep[dep["strategy"] == "B1_spy_buy_hold"].set_index("permno")["final_value"]
    ls = dep[dep["strategy"] == "lump_sum"].set_index("permno")["xirr"]
    x = dep[dep["strategy"] != "B1_spy_buy_hold"].copy()
    x["vs_lump_pp"] = (x["xirr"] - x["permno"].map(ls)) * 100
    x["beats_lump"] = x["vs_lump_pp"] > 0
    x["beats_spy"] = x["final_value"] > x["permno"].map(b1)
    x["group"] = np.where(x["permno"].isin(etf), "ETF", "stock")
    g = x.groupby(["group", "strategy"], sort=False).agg(
        tickers=("permno", "size"), median_vs_lump_pp=("vs_lump_pp", "median"),
        pct_beat_lump=("beats_lump", "mean"), pct_beat_spy=("beats_spy", "mean"))  # fmt: skip
    return g.reset_index().round(3)


LOCKBOX_START, LOCKBOX_END = "2023-01-03", "2025-12-31"
TIMING_TYPES = {"trend", "sma_cross", "vol_target", "rsi2", "sector", "dual_momentum", "swing"}


def build_strategy(spec: dict):
    """Strategy from a pre-registered config entry, e.g. {type: dip, dip: 0.05, wait: 3}."""
    t = spec["type"]
    makers = {
        "b1": lambda: spy_buy_and_hold(),
        "sixty_forty": lambda: sixty_forty(spec.get("frequency", "monthly")),
        "lump_sum": lambda: LumpSum(SPY),
        "dca": lambda: DCA(SPY, spec["frequency"]),
        "dip": lambda: BuyTheDip(SPY, spec["dip"], spec["wait"]),
        "trend": lambda: TrendSMA(),
        "sma_cross": lambda: SMACross(),
        "vol_target": lambda: VolTarget(),
        "rsi2": lambda: RSI2(),
        "sector": lambda: SectorRotation(),
        "dual_momentum": lambda: DualMomentum(),
        "swing": lambda: SwingModel(k=spec["k"], threshold=spec["threshold"], C=spec["C"]),
    }
    return makers[t]()


def run_lockbox(cfg: dict, force: bool) -> None:
    """Evaluate the pre-registered list once on 2023-2025 (signals may use earlier history)."""
    marker = OUT / "LOCKBOX_RUN"
    if marker.exists() and not force:
        sys.exit(
            f"lockbox already evaluated ({marker.read_text().strip()}); it is evaluated exactly once"
        )
    specs = (cfg.get("lockbox") or {}).get("strategies")
    if not specs:
        sys.exit("no pre-registered lockbox list in configs/default.yaml (lockbox.strategies)")
    md = MarketData.load()
    pairs = []
    b1 = run_parallel(md, [(spy_buy_and_hold(), LOCKBOX_START, LOCKBOX_END)])[0]
    for spec in specs:
        s = build_strategy(spec)
        if spec["type"] in TIMING_TYPES:
            out = evaluate_timing(s, md, LOCKBOX_START, LOCKBOX_END, n_random=100, phase="lockbox")
            extra = {
                k: out[k] for k in ("n1_final", "n2_median_final", "n2_pct_final", "n2_pct_sharpe")
            }
            pairs.append((out["_res"], b1, {"family": "lockbox", **extra}))
        else:
            r = run_parallel(md, [(s, LOCKBOX_START, LOCKBOX_END)])[0]
            pairs.append((r, b1, {"family": "lockbox"}))
        log(f"lockbox {s.name} done")
    table = add_holm(family_table(pairs, 1000))
    table.to_csv(OUT / "lockbox_results.csv", index=False)
    log_trials([{"kind": "lockbox", **r} for r in table.to_dict("records")], "lockbox")
    cols = MAIN_COLS + ["final_value_ratio_lo", "final_value_ratio_hi", "final_value_ratio_p_holm",
                        "n2_pct_final", "n2_pct_sharpe"]  # fmt: skip
    md_txt = ["# Lockbox evaluation 2023-01-03 → 2025-12-31 (evaluated once)", "",
              "Pre-registered list from configs/default.yaml. $5,000 deposited each January.", "",
              fmt_table(table[[c for c in cols if c in table]], pct=PCT, money=MONEY,
                        dec2=("sharpe", "b1_sharpe", "final_value_ratio_p_holm"), ints=("n_trades",))]  # fmt: skip
    (OUT / "lockbox_tables.md").write_text("\n".join(md_txt) + "\n")
    marker.write_text(f"run at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log("lockbox done")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--lockbox", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-validation", action="store_true")
    ap.add_argument("--plots-only", action="store_true", help="redo plots/tables from the cache")
    ap.add_argument("--resume", action="store_true", help="reuse cached stages from an earlier run")
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text())
    OUT.mkdir(exist_ok=True)
    global RESUME
    RESUME = args.resume
    if args.plots_only:
        finish()
        return 0
    if not args.skip_validation:
        sys.path.insert(0, str(Path(__file__).parent))
        from validate_data import main as validate

        log("data validation")
        if validate() != 0:
            sys.exit("data validation failed; see outputs/data_validation.md")
    if args.lockbox:
        run_lockbox(cfg, args.force)
    else:
        run_dev(args.quick, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
