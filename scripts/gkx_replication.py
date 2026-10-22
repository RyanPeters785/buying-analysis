"""Long-only Gu-Kelly-Xiu replication: walk-forward predictions (stage "train") and portfolios (stage "portfolio").

    uv run scripts/gkx_replication.py --stage train       # predictions for 2003-2025, cached per model
    uv run scripts/gkx_replication.py --stage portfolio   # long-only top-decile portfolios vs SPY

See src/buying_analysis/ml/gkx.py for the model design and departures from the paper.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from buying_analysis.data import DATA_DIR, RAW_DIR, ROOT
from buying_analysis.ml import gkx
from buying_analysis.ml.macro import MACRO, MACRO_FEATURES, build_macro

PANEL_FULL = DATA_DIR / "derived" / "ml_panel_full.parquet"
PRED_DIR = DATA_DIR / "derived" / "gkx_preds"
OUT = ROOT / "outputs" / "gkx"
YEARS = range(2003, 2026)
_G: dict = {}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rf_monthly() -> pd.Series:
    kf = pd.read_parquet(RAW_DIR / "ff_factors_daily.parquet").set_index("date")
    return (1 + kf["rf"]).resample("ME").prod() - 1


def load_inputs() -> None:
    panel = pd.read_parquet(PANEL_FULL)
    if MACRO.exists():
        macro = pd.read_parquet(MACRO)
    else:
        macro = build_macro(panel)
        macro.to_parquet(MACRO)
    rf = rf_monthly()
    panel = panel.sort_values(["date", "permno"]).reset_index(drop=True)
    nxt = panel["date"] + pd.offsets.MonthEnd(1)
    _G["dates"] = panel["date"]
    _G["permno"] = panel["permno"].to_numpy()
    _G["y"] = (panel["ret_fwd1"] - nxt.map(rf).fillna(0.0)).to_numpy(np.float64)
    _G["chars"] = gkx.characteristics(panel)
    _G["sect"] = gkx.sector_dummies(panel)
    _G["macro_raw"] = macro[MACRO_FEATURES].reindex(panel["date"]).to_numpy(np.float64)
    ols_cols = [gkx.GKX_FEATURES.index(c) for c in ("size", "bm", "mom_12_1")]
    _G["ols_cols"] = ols_cols
    log(f"inputs: {len(panel):,} rows, {len(gkx.GKX_FEATURES)} characteristics")


def job(args):
    model, year = args
    d = _G["dates"]
    y = _G["y"]
    rng = np.random.default_rng(year)
    train_end = pd.Timestamp(f"{year - 6}-12-31")
    val_start, val_end = pd.Timestamp(f"{year - 5}-01-31"), pd.Timestamp(f"{year - 1}-11-30")
    tr = sample_mask(d, (d >= gkx.TRAIN_START) & (d <= train_end) & np.isfinite(y), rng)
    va = sample_mask(d, (d >= val_start) & (d <= val_end) & np.isfinite(y), rng)
    te = np.flatnonzero((d.dt.year == year).to_numpy())
    m_raw = _G["macro_raw"]
    mu, sd = np.nanmean(m_raw[tr], axis=0), np.nanstd(m_raw[tr], axis=0) + 1e-12
    mac = lambda idx: np.nan_to_num((m_raw[idx] - mu) / sd).astype(np.float32)
    lo, hi = np.quantile(y[tr], [0.01, 0.99])
    ytr, yva = np.clip(y[tr], lo, hi), np.clip(y[va], lo, hi)
    if model == "ols3":
        cols = _G["ols_cols"]
        X = lambda idx: _G["chars"][idx][:, cols]
    else:
        X = lambda idx: gkx.design(_G["chars"][idx], _G["sect"][idx], mac(idx), True)
    t = time.time()
    pred, info = gkx.fit_predict(model, X(tr), ytr, X(va), yva, X(te), seed=year)
    return model, year, pd.DataFrame({"date": d.to_numpy()[te], "permno": _G["permno"][te], "pred": pred,
                                      "actual": y[te]}), {**info, "seconds": round(time.time() - t), "n_train": len(tr)}  # fmt: skip


def sample_mask(d: pd.Series, mask, rng) -> np.ndarray:
    return gkx.sample_rows(d, np.asarray(mask), rng, gkx.SAMPLE_PER_MONTH)


def train(models: list[str], workers: int, years=YEARS) -> None:
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    load_inputs()
    todo = [(m, y) for m in models for y in years if not (PRED_DIR / f"{m}_{y}.parquet").exists()]
    log(f"{len(todo)} model-years to fit with {workers} workers")
    infos = []
    with ProcessPoolExecutor(workers) as ex:  # fork: workers share the prepared arrays
        for model, year, df, info in ex.map(job, todo):
            df.to_parquet(PRED_DIR / f"{model}_{year}.parquet", index=False)
            infos.append({"model": model, "year": year, **info})
            log(f"{model} {year}: {info}")
    if infos:
        OUT.mkdir(parents=True, exist_ok=True)
        old = pd.read_csv(OUT / "fit_log.csv") if (OUT / "fit_log.csv").exists() else None
        pd.concat([old, pd.DataFrame(infos)]).to_csv(OUT / "fit_log.csv", index=False)


COST_BPS = {
    1: 75.0,
    2: 30.0,
    3: 15.0,
    4: 10.0,
}  # per side by NYSE size bucket: micro, small, mid, large
PERIODS = {
    "2003-2009": ("2003", "2009"),
    "2010-2015": ("2010", "2015"),
    "2016-2025*": ("2016", "2025"),
}


def portfolios() -> None:
    from buying_analysis import plots
    from buying_analysis.experiments import log_trials
    from buying_analysis.ml.portfolio import return_matrix, simulate, spy_targets, summary
    from buying_analysis.report import fmt_table
    from buying_analysis.stats import deflated_sharpe

    OUT.mkdir(parents=True, exist_ok=True)
    preds = pd.concat([pd.read_parquet(p).assign(model=p.stem.rsplit("_", 1)[0])
                       for p in sorted(PRED_DIR.glob("*.parquet"))], ignore_index=True)  # fmt: skip
    years_per_model = preds.groupby("model")["date"].apply(lambda d: d.dt.year.nunique())
    complete = years_per_model[years_per_model == len(YEARS)].index
    if len(complete) < len(years_per_model):
        log(f"skipping incomplete models: {sorted(set(years_per_model.index) - set(complete))}")
    preds = preds[preds["model"].isin(complete)]
    panel = pd.read_parquet(
        PANEL_FULL, columns=["date", "permno", "mcap", "size_bucket", "ret_fwd1"]
    )
    preds = preds.merge(panel, on=["date", "permno"], how="left")
    rets, rf = return_matrix(), rf_monthly()
    start, end = pd.Timestamp("2003-01-31"), pd.Timestamp("2025-12-31")
    cmap = {
        d: g.set_index("permno")["size_bucket"].map(COST_BPS)
        for d, g in panel[panel["date"] >= start].groupby("date")
    }
    log("inputs loaded")

    # replication checks: out-of-sample R^2 and rank IC, all stocks vs no microcaps
    checks = []
    for (m, uni), g in [((m, u), g[g["size_bucket"] >= (1 if u == "all" else 2)])
                        for m, g in preds.groupby("model") for u in ("all", "no microcaps")]:  # fmt: skip
        ok = np.isfinite(g["actual"]) & np.isfinite(g["pred"])
        ic = (
            g[ok]
            .groupby("date")
            .apply(lambda x: x["pred"].rank().corr(x["actual"].rank()), include_groups=False)
        )
        checks.append({"model": m, "universe": uni, "r2_oos": gkx.r2_oos(g.loc[ok, "pred"].to_numpy(),
                       g.loc[ok, "actual"].to_numpy()), "mean_ic": ic.mean(), "ic_t": ic.mean() / ic.std() * np.sqrt(len(ic))})  # fmt: skip
    checks = pd.DataFrame(checks)

    def targets(g: pd.DataFrame, weighting: str) -> dict:
        out = {}
        for d, x in g.groupby("date"):
            top = x.nlargest(max(1, len(x) // 10), "pred")
            w = pd.Series(1.0, index=top["permno"].to_numpy()) if weighting == "EW" else \
                pd.Series(top["mcap"].to_numpy(), index=top["permno"].to_numpy())  # fmt: skip
            out[pd.Timestamp(d)] = w / w.sum()
        return out

    runs = {}
    runs["SPY (before costs)"] = simulate(
        spy_targets(rets.index[rets.index >= start]), rets, start, end, cost_bps=0.0
    )
    runs["SPY"] = simulate(
        spy_targets(rets.index[rets.index >= start]), rets, start, end, cost_bps=2.0
    )
    uni_all = panel[panel["date"] >= start]
    for label, g, wt in (("market cap-weight (all stocks)", uni_all, "VW"), ("equal-weight all stocks", uni_all, "EW"),
                         ("equal-weight no microcaps", uni_all[uni_all["size_bucket"] >= 2], "EW")):  # fmt: skip
        tg = {d: (pd.Series(1.0, index=x["permno"].to_numpy()) if wt == "EW" else
                  pd.Series(x["mcap"].to_numpy(), index=x["permno"].to_numpy())) for d, x in g.groupby("date")}  # fmt: skip
        tg = {pd.Timestamp(d): w / w.sum() for d, w in tg.items()}
        runs[label] = simulate(tg, rets, start, end, cost_bps=0.0, cost_map=cmap)
    log("benchmarks done")
    for m, g in preds.groupby("model"):
        for uni in ("all stocks", "no microcaps"):
            gg = g if uni == "all stocks" else g[g["size_bucket"] >= 2]
            for wt in ("EW", "VW"):
                tg = targets(gg, wt)
                runs[f"{m} | {uni} | {wt} | before costs"] = simulate(
                    tg, rets, start, end, cost_bps=0.0
                )
                runs[f"{m} | {uni} | {wt} | after costs"] = simulate(
                    tg, rets, start, end, cost_bps=0.0, cost_map=cmap
                )
        log(f"{m} portfolios done")

    spy = runs["SPY"]
    trial_names = [n for n in runs if n.endswith("after costs")]
    ex_sr = [
        ((runs[n]["ret"] - spy["ret"]).mean() / (runs[n]["ret"] - spy["ret"]).std())
        for n in trial_names
    ]
    sr_var = float(np.var(ex_sr, ddof=1))
    rows, per_rows = [], []
    for name, a in runs.items():
        s = summary(a, rf)
        r, sr = a["ret"], spy["ret"]
        sharpe_s = (r - rf.reindex(r.index)).rolling(36).mean() / r.rolling(36).std()
        sharpe_b = (sr - rf.reindex(sr.index)).rolling(36).mean() / sr.rolling(36).std()
        ret_s = (1 + r).rolling(36).apply(np.prod, raw=True)
        ret_b = (1 + sr).rolling(36).apply(np.prod, raw=True)
        yearly = (1 + pd.DataFrame({"s": r, "b": sr})).groupby(r.index.year).prod()
        ex = r - sr
        rows.append({"strategy": name, **s, "vs_spy": a["equity"].iloc[-1] / spy["equity"].iloc[-1] - 1,
                     "pct_36m_sharpe_beats_spy": (sharpe_s > sharpe_b).loc[sharpe_s.notna()].mean(),
                     "pct_36m_return_beats_spy": (ret_s > ret_b).loc[ret_s.notna()].mean(),
                     "pct_years_beat_spy": (yearly["s"] > yearly["b"]).mean(),
                     "excess_t": ex.mean() / ex.std() * np.sqrt(len(ex)) if ex.std() > 0 else np.nan,
                     "dsr_vs_spy": deflated_sharpe(ex, len(trial_names), sr_var) if name in trial_names else np.nan})  # fmt: skip
        for p, (a0, a1) in PERIODS.items():
            x = r.loc[a0:a1]
            dd = (1 + x).cumprod()
            per_rows.append({"strategy": name, "period": p, "ann_return": (1 + x).prod() ** (12 / len(x)) - 1,
                             "sharpe": (x - rf.reindex(x.index)).mean() / x.std() * np.sqrt(12),
                             "max_drawdown": (dd / dd.cummax() - 1).min()})  # fmt: skip
    table = pd.DataFrame(rows)
    per = pd.DataFrame(per_rows)
    log_trials([{"kind": "gkx_long_only", **x} for x in table.to_dict("records")])
    table.to_csv(OUT / "results.csv", index=False)
    per.to_csv(OUT / "periods.csv", index=False)
    checks.to_csv(OUT / "replication_checks.csv", index=False)

    best = (
        table[table["strategy"].str.endswith("after costs")]
        .nlargest(3, "sharpe")["strategy"]
        .tolist()
    )
    rel = {n: (1 + runs[n]["ret"]).cumprod() / (1 + spy["ret"]).cumprod() for n in best}
    plots.line_chart(rel, "Best long-only GKX portfolios (after costs) relative to SPY, 2003-2025",
                     "ratio to SPY (log)", OUT / "relative_to_spy.png", log=True, fmt=lambda v: f"{v:.2f}x")  # fmt: skip
    pct = ("xirr", "cagr", "volatility", "max_drawdown", "vs_spy", "pct_36m_sharpe_beats_spy",
           "pct_36m_return_beats_spy", "pct_years_beat_spy", "ann_return", "turnover_per_yr")  # fmt: skip
    sp = per.pivot_table(index="strategy", columns="period", values="sharpe", sort=False)
    txt = ["# Long-only Gu-Kelly-Xiu replication (2003-2025, walk-forward)", "",
           ("Top decile of predicted next-month excess return, monthly rebalance; $5,000 each December month-end. "
           f"After-cost runs charge per side by NYSE size bucket {COST_BPS} bps (SPY 2 bps). "
           "*2016-2025 was viewed in the earlier ML study."), "",
           "## Replication checks (out-of-sample, 2003-2025)", "",
           fmt_table(checks, dec2=("ic_t",)).replace("r2_oos", "r2_oos (fraction)"), "",
           "## Portfolios", "",
           fmt_table(table[["strategy", "final_value", "vs_spy", "xirr", "cagr", "sharpe", "volatility", "max_drawdown",
                            "pct_years_beat_spy", "pct_36m_sharpe_beats_spy", "pct_36m_return_beats_spy", "excess_t",
                            "dsr_vs_spy", "turnover_per_yr", "avg_holdings"]],
                     pct=pct, money=("final_value",), dec2=("sharpe", "excess_t", "dsr_vs_spy", "turnover_per_yr"),
                     ints=("avg_holdings",)), "",
           "## Sharpe ratio by period", "", fmt_table(sp.reset_index(), dec2=tuple(sp.columns)), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt[:12]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["train", "portfolio"], default="train")
    ap.add_argument("--models", default=",".join(gkx.MODELS))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--years", default=None, help="e.g. 2003-2005 (default 2003-2025)")
    args = ap.parse_args()
    if args.stage == "train":
        years = YEARS
        if args.years:
            a, _, b = args.years.partition("-")
            years = range(int(a), int(b or a) + 1)
        train(args.models.split(","), args.workers, years)
    else:
        portfolios()
    return 0


if __name__ == "__main__":
    sys.exit(main())
