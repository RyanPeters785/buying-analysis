"""ML stock selection: walk-forward models -> top-N portfolios -> comparison with SPY and the universe.

    uv run scripts/ml_select.py --phase dev        # predictions and portfolios 1998-2015 (model comparison)
    uv run scripts/ml_select.py --phase holdout    # 2016-2025, once, for configs/ml_holdout.yaml only

Universe: point-in-time top-1000 US common stocks (ml/panel.py). Models (ml/models.py): simple factor score,
ridge, random forest, LightGBM, XGBoost; refit each January on realized targets only. Portfolios: equal-weight
top 50 / top 100; monthly rebalancing with 1-month-horizon models, quarterly with 3-month-horizon models;
10 bps per side (20 bps sensitivity). $5,000 deposited each December month-end (invested for January).
Benchmarks: SPY, equal- and cap-weighted top-1000 universe. Outputs: outputs/ml/.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

for _v in ("OMP_NUM_THREADS",):
    os.environ.setdefault(_v, "8")

import numpy as np
import pandas as pd
import yaml

from buying_analysis import plots
from buying_analysis.data import DATA_DIR, RAW_DIR, ROOT
from buying_analysis.experiments import log_trials
from buying_analysis.ml.models import MODEL_NAMES, information_coefficient, walk_forward
from buying_analysis.ml.panel import PANEL
from buying_analysis.ml.portfolio import (
    return_matrix,
    simulate,
    spy_targets,
    summary,
    top_n_targets,
    universe_targets,
)
from buying_analysis.report import fmt_table
from buying_analysis.stats import deflated_sharpe

OUT = ROOT / "outputs" / "ml"
PRED_DIR = DATA_DIR / "derived" / "ml_preds"
PHASES = {"dev": (1998, 2015), "holdout": (2016, 2025)}
HOLDOUT_CFG = ROOT / "configs" / "ml_holdout.yaml"
TOP_NS = (50, 100)
COSTS = (10.0, 20.0)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def predictions(panel, model, horizon, y0, y1) -> pd.DataFrame:
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    path = PRED_DIR / f"{model}_h{horizon}_{y0}_{y1}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    t = time.time()
    p = walk_forward(panel, model, horizon, y0, y1)
    p.to_parquet(path, index=False)
    log(f"{model} h={horizon}: {time.time() - t:.0f}s")
    return p


def rf_monthly() -> pd.Series:
    kf = pd.read_parquet(RAW_DIR / "ff_factors_daily.parquet").set_index("date")
    return (1 + kf["rf"]).resample("ME").prod() - 1


def run(phase: str, configs: list[dict] | None) -> None:
    y0, y1 = PHASES[phase]
    start, end = pd.Timestamp(f"{y0}-01-31"), pd.Timestamp(f"{y1}-12-31")
    panel = pd.read_parquet(PANEL)
    rets = return_matrix()
    rf = rf_monthly()
    OUT.mkdir(parents=True, exist_ok=True)

    # benchmarks
    runs = {"SPY": simulate(spy_targets(rets.index[rets.index >= start]), rets, start, end, cost_bps=2.0),
            "universe equal-weight": simulate(universe_targets(panel, start, "equal"), rets, start, end, 10.0),
            "universe cap-weight": simulate(universe_targets(panel, start, "cap"), rets, start, end, 10.0)}  # fmt: skip
    log("benchmarks done")
    ic_rows, rows = [], []
    combos = [(m, h) for m in MODEL_NAMES for h in (1, 3)]
    if configs:
        combos = sorted({(c["model"], c["horizon"]) for c in configs})
    for model, horizon in combos:
        pr = predictions(panel, model, horizon, y0, y1)
        ic = information_coefficient(pr, panel, horizon)
        ic_rows.append({"model": model, "horizon": horizon, "mean_ic": ic.mean(),
                        "ic_t": ic.mean() / ic.std() * np.sqrt(len(ic)), "pct_months_positive": (ic > 0).mean()})  # fmt: skip
        every = 1 if horizon == 1 else 3
        for n in TOP_NS:
            for cost in COSTS:
                if configs and not any(c["model"] == model and c["horizon"] == horizon and c["top_n"] == n
                                       and c["cost_bps"] == cost for c in configs):  # fmt: skip
                    continue
                name = f"{model} | {'monthly' if horizon == 1 else 'quarterly'} | top {n} | {cost:g} bps"
                runs[name] = simulate(
                    top_n_targets(pr, n, every, start), rets, start, end, cost_bps=cost
                )
        log(f"{model} h={horizon} portfolios done")

    spy = runs["SPY"]
    n_trials = len(runs) - 3
    srs = []
    for name, a in runs.items():
        ex = a["ret"] - spy["ret"].reindex(a.index)
        srs.append(ex.mean() / ex.std() if ex.std() > 0 else 0.0)
    sr_var = float(np.var(srs[3:], ddof=1)) if n_trials > 1 else 0.0
    for name, a in runs.items():
        s = summary(a, rf)
        ex = a["ret"] - spy["ret"].reindex(a.index)
        rel = (1 + a["ret"]).cumprod() / (1 + spy["ret"]).cumprod()
        rows.append({"strategy": name, **s,
                     "vs_spy": a["equity"].iloc[-1] / spy["equity"].iloc[-1] - 1,
                     "excess_t": ex.mean() / ex.std() * np.sqrt(len(ex)) if ex.std() > 0 else np.nan,
                     "dsr_vs_spy": deflated_sharpe(ex, max(n_trials, 1), sr_var) if ex.std() > 0 else np.nan,
                     "worst_3y_vs_spy": (rel / rel.shift(36) - 1).min(),
                     "pct_3y_windows_beat_spy": ((rel / rel.shift(36) - 1).dropna() > 0).mean()})  # fmt: skip
    table = pd.DataFrame(rows).sort_values("final_value", ascending=False)
    ic_tbl = pd.DataFrame(ic_rows)
    log_trials(
        [{"kind": f"ml_{phase}", **r} for r in table.to_dict("records")],
        phase="dev" if phase == "dev" else "ml_holdout",
    )

    best = [n for n in table["strategy"] if "|" in n and "10 bps" in n][:3]
    rel = {n: (1 + runs[n]["ret"]).cumprod() / (1 + spy["ret"]).cumprod() for n in best}
    rel["universe equal-weight"] = (1 + runs["universe equal-weight"]["ret"]).cumprod() / (
        1 + spy["ret"]
    ).cumprod()
    plots.line_chart(rel, f"Growth relative to SPY, {y0}-{y1} (time-weighted, after costs)", "ratio to SPY (log)",
                     OUT / f"{phase}_relative_to_spy.png", log=True, fmt=lambda v: f"{v:.2f}x")  # fmt: skip
    table.to_csv(OUT / f"{phase}_results.csv", index=False)
    ic_tbl.to_csv(OUT / f"{phase}_ic.csv", index=False)
    pct = ("xirr", "cagr", "volatility", "max_drawdown", "vs_spy", "worst_3y_vs_spy", "pct_3y_windows_beat_spy",
           "mean_ic", "pct_months_positive", "turnover_per_yr")  # fmt: skip
    txt = [f"# ML stock selection, {phase} phase ({y0}-{y1})", "",
           ("Top-1000 point-in-time universe; walk-forward (refit each January on realized targets); $5,000 each "
           "December month-end; equal-weight top-N; costs per side as labelled (SPY 2 bps)."), "",
           "## Portfolios (sorted by ending value)", "",
           fmt_table(table[["strategy", "final_value", "vs_spy", "xirr", "sharpe", "volatility", "max_drawdown",
                            "worst_3y_vs_spy", "pct_3y_windows_beat_spy", "excess_t", "dsr_vs_spy",
                            "turnover_per_yr", "avg_holdings"]],
                     pct=pct, money=("final_value",), dec2=("sharpe", "excess_t", "dsr_vs_spy", "turnover_per_yr"),
                     ints=("avg_holdings",)), "",
           f"DSR = probability the monthly excess over SPY has a positive Sharpe after {n_trials} configurations.", "",
           "## Ranking skill: information coefficient (monthly rank correlation of score vs realized return)", "",
           fmt_table(ic_tbl.assign(mean_ic=ic_tbl["mean_ic"].round(4)), pct=("pct_months_positive",),
                     dec2=("ic_t",)), ""]  # fmt: skip
    (OUT / f"{phase}_report.md").write_text("\n".join(txt))
    print("\n".join(txt))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=list(PHASES), default="dev")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.phase == "holdout":
        marker = OUT / "HOLDOUT_RUN"
        if marker.exists() and not args.force:
            sys.exit(
                f"holdout already evaluated ({marker.read_text().strip()}); it runs exactly once"
            )
        if not HOLDOUT_CFG.exists():
            sys.exit(f"pre-register the holdout configs in {HOLDOUT_CFG} first")
        configs = yaml.safe_load(HOLDOUT_CFG.read_text())["configs"]
        run("holdout", configs)
        marker.write_text(f"run at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    else:
        run("dev", None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
