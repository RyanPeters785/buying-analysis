"""Experiment helpers: run a strategy with its null baselines and log every configuration tried."""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import numpy as np
import pandas as pd

from buying_analysis.backtest import Engine, MarketData, Strategy, contribution_schedule
from buying_analysis.data import ROOT
from buying_analysis.metrics import summarize
from buying_analysis.strategies.benchmarks import spy_buy_and_hold
from buying_analysis.strategies.nulls import (
    RandomSectors,
    RandomTiming,
    exposure_matched,
    in_market_spells,
    random_schedule,
)
from buying_analysis.strategies.timing import SPY, SectorRotation
from buying_analysis.validate import SUSPECT_SPY_DATES

TRIALS = ROOT / "outputs" / "trials.csv"
LOCKBOX_START = pd.Timestamp("2023-01-01")


def check_dev_window(end, phase: str = "dev") -> None:
    """Dev runs must end before the lockbox; lockbox runs only come from ``run_all.py --lockbox``."""
    if phase == "lockbox":
        return
    if pd.Timestamp(end) >= LOCKBOX_START:
        raise RuntimeError(
            "development runs must end before 2023-01-01 (lockbox); use the lockbox runner"
        )


def log_trials(rows: list[dict], phase: str = "dev") -> None:
    """Append configurations to outputs/trials.csv (rewritten so columns stay consistent across kinds)."""
    TRIALS.parent.mkdir(exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    new = pd.DataFrame([{"logged_at": stamp, "phase": phase, **r} for r in rows])
    old = pd.read_csv(TRIALS) if TRIALS.exists() else None
    pd.concat([old, new], ignore_index=True).to_csv(TRIALS, index=False)


def run_one(engine: Engine, strategy: Strategy, start, end, amount: float, frequency: str):
    dep = contribution_schedule(engine.md.sessions, amount, frequency, start=start, end=end)
    return engine.run(strategy, dep, start=start, end=end)


# --- parallel null runs (module-level so they pickle) ------------------------------------------------------

_G: dict = {}


def _init(md, costs, start, end, amount, frequency):
    _G.update(md=md, costs=costs, start=start, end=end, amount=amount, frequency=frequency)


def _run_null(strategy):
    eng = Engine(_G["md"], costs=_G["costs"])
    res = run_one(eng, strategy, _G["start"], _G["end"], _G["amount"], _G["frequency"])
    return summarize(res)


def evaluate_timing(
    strategy: Strategy,
    md: MarketData,
    start,
    end,
    *,
    amount: float = 5000.0,
    frequency: str = "annual",
    n_random: int = 100,
    costs=None,
    log: bool = True,
    phase: str = "dev",
    res=None,
) -> dict:
    """Strategy vs B1, N1 (exposure-matched) and N2 (random timing) on the same window and deposits.

    Returns summary metrics plus ``_res`` / ``_b1`` (engine results) and ``_n2`` (null summaries) for
    statistics and plots; underscore keys are not written to trials.csv.
    """
    check_dev_window(end, phase)
    eng = Engine(md) if costs is None else Engine(md, costs=costs)
    if res is None:
        res = run_one(eng, strategy, start, end, amount, frequency)
    m = summarize(res)
    b1_res = run_one(eng, spy_buy_and_hold(), start, end, amount, frequency)
    b1 = summarize(b1_res)
    w = (
        res.weights.get(SPY, pd.Series(0.0, index=res.daily.index))
        .reindex(res.daily.index)
        .fillna(0)
    )
    exposure = float(w.mean()) if SPY in strategy.assets else m["time_in_market"]
    n1 = summarize(run_one(eng, exposure_matched(SPY, exposure), start, end, amount, frequency))

    seeds = range(n_random)
    if isinstance(strategy, SectorRotation):
        nulls = [RandomSectors(strategy.k, s, strategy.assets) for s in seeds]
    else:
        spells, n_in, n = in_market_spells(w)
        sess = res.daily.index
        nulls = []
        for s in seeds:
            rng = np.random.default_rng(s)
            sched = pd.Series(random_schedule(n, n_in, spells, rng), index=sess)
            nulls.append(RandomTiming(SPY, sched, s))
    workers = min(len(nulls), os.cpu_count() or 1)
    with ProcessPoolExecutor(workers, initializer=_init,
                             initargs=(md, eng.costs, start, end, amount, frequency)) as ex:  # fmt: skip
        n2 = pd.DataFrame(list(ex.map(_run_null, nulls, chunksize=4)))

    def pct(col):
        return float((n2[col] < m[col]).mean() * 100)

    suspect = res.trades[res.trades["session"].isin(_next_sessions(md, SUSPECT_SPY_DATES))]
    out = {
        **m,
        "b1_final": b1["final_value"],
        "b1_xirr": b1["xirr"],
        "b1_sharpe": b1["sharpe"],
        "n1_exposure": exposure,
        "n1_final": n1["final_value"],
        "n1_sharpe": n1["sharpe"],
        "n2_runs": len(n2),
        "n2_median_final": n2["final_value"].median(),
        "n2_pct_final": pct("final_value"),
        "n2_pct_sharpe": pct("sharpe"),
        "trades_after_suspect_spy_dates": len(suspect),
    }
    if log:
        log_trials([{"kind": "timing", **out}], phase)
    return {**out, "_res": res, "_b1": b1_res, "_n2": n2}


def _next_sessions(md: MarketData, dates) -> list[pd.Timestamp]:
    out = []
    for d in pd.to_datetime(dates):
        i = md.sessions.searchsorted(d, "right")
        if 0 < i < len(md.sessions) and md.sessions[i - 1] == d:
            out.append(md.sessions[i])
    return out


# --- deployment (lump sum / DCA / buy-the-dip) per ticker ---------------------------------------------------

DIP_GRID = [(x, n) for x in (0.05, 0.10, 0.15, 0.20) for n in (3, 6, 12)]


def deployment_strategies(asset: int) -> list[Strategy]:
    from buying_analysis.strategies.deployment import DCA, LumpSum
    from buying_analysis.strategies.dip import BuyTheDip

    return [LumpSum(asset), DCA(asset, "monthly"), DCA(asset, "weekly")] + [
        BuyTheDip(asset, x, n) for x, n in DIP_GRID
    ]


def _run_deployment(args):
    asset, start, end, amount, frequency = args
    eng = Engine(_G["md"], costs=_G["costs"])
    rows = []
    for s in [*deployment_strategies(asset), spy_buy_and_hold()]:
        m = summarize(run_one(eng, s, start, end, amount, frequency))
        rows.append({"permno": asset, "ticker": _G["md"].tickers.get(asset, str(asset)), **m})
    return rows


def evaluate_deployment(md: MarketData, assets, end, *, warmup_days: int = 365, amount=5000.0,
                        frequency="annual", costs=None, log=True, phase="dev", start=None) -> pd.DataFrame:  # fmt: skip
    """Every deployment strategy on every asset, from one year after listing (or the data start) to ``end``.

    Each asset's window also gets a SPY buy-and-hold (B1) run with the same deposits.
    """
    check_dev_window(end, phase)
    eng = Engine(md) if costs is None else Engine(md, costs=costs)
    jobs = []
    for a in assets:
        first = md.first_session([a, SPY])
        s0 = first + pd.Timedelta(days=warmup_days)
        if start is not None:
            s0 = max(s0, pd.Timestamp(start))
        live = md.sessions[(md.sessions >= s0) & (md.sessions <= pd.Timestamp(end))]
        if len(live) < 2 or not md.tradable[md.sessions.get_loc(live[0]), md.col(a)]:
            continue
        jobs.append((a, live[0], end, amount, frequency))
    with ProcessPoolExecutor(min(len(jobs), os.cpu_count() or 1), initializer=_init,
                             initargs=(md, eng.costs, None, None, amount, frequency)) as ex:  # fmt: skip
        rows = [r for chunk in ex.map(_run_deployment, jobs) for r in chunk]
    df = pd.DataFrame(rows)
    if log:
        log_trials([{"kind": "deployment", **r} for r in rows], phase)
    return df


# --- rolling start dates --------------------------------------------------------------------------------


def _run_window(args):
    strategy, start, end = args
    eng = Engine(_G["md"], costs=_G["costs"])
    m = summarize(run_one(eng, strategy, start, end, _G["amount"], _G["frequency"]))
    return {"window_start": start, "window_end": end, **m}


def rolling_windows(md: MarketData, strategies: list[Strategy], years: int, end, *, step_months: int = 1,
                    warmup_days: int = 400, amount=5000.0, frequency="annual", costs=None,
                    benchmark: Strategy | None = None) -> pd.DataFrame:  # fmt: skip
    """Fresh portfolios started on the first session of every ``step_months`` month, each run ``years`` years.

    Each strategy only gets windows that start ``warmup_days`` after all its assets trade; every window also
    runs the benchmark (default SPY buy-and-hold) so results are paired by start date.
    """
    bench = spy_buy_and_hold() if benchmark is None else benchmark
    check_dev_window(end)
    end = pd.Timestamp(end)
    eng = Engine(md) if costs is None else Engine(md, costs=costs)
    months = pd.date_range(md.sessions[0], end, freq=f"{step_months}MS")
    jobs = []
    for s in [bench, *strategies]:
        ok_from = md.first_session(s.assets) + pd.Timedelta(days=warmup_days)
        for m in months:
            st = md.sessions[md.sessions.searchsorted(m)]
            w_end = st + pd.DateOffset(years=years) - pd.Timedelta(days=1)
            if st >= ok_from and w_end <= end:
                jobs.append((s, st, w_end))
    with ProcessPoolExecutor(os.cpu_count() or 1, initializer=_init,
                             initargs=(md, eng.costs, None, None, amount, frequency)) as ex:  # fmt: skip
        rows = list(ex.map(_run_window, jobs, chunksize=8))
    df = pd.DataFrame(rows)
    b1 = df[df["strategy"] == bench.name].set_index("window_start")
    df["b1_final"] = df["window_start"].map(b1["final_value"])
    df["b1_xirr"] = df["window_start"].map(b1["xirr"])
    df["final_vs_b1"] = df["final_value"] / df["b1_final"] - 1
    df["years_window"] = years
    return df


def _run_full(args):
    strategy, start, end = args
    return run_one(
        Engine(_G["md"], costs=_G["costs"]), strategy, start, end, _G["amount"], _G["frequency"]
    )


def run_parallel(md: MarketData, jobs: list[tuple], costs=None, amount=5000.0, frequency="annual"):
    """Run [(strategy, start, end)] in parallel; returns engine Results in order."""
    costs = Engine(md).costs if costs is None else costs
    with ProcessPoolExecutor(min(len(jobs), os.cpu_count() or 1), initializer=_init,
                             initargs=(md, costs, None, None, amount, frequency)) as ex:  # fmt: skip
        return list(ex.map(_run_full, jobs))
