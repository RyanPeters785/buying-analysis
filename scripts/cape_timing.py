"""Valuation timing with Shiller CAPE: stocks when the market is cheap, T-bills (or half) when it's expensive.

Signal (no hindsight): real-time CAPE at month-end t = (P_t / CPI_{t-1}) / mean of real earnings over the 120
months ending at t-4 (4-month reporting lag). "Expensive" = above the q-th percentile of CAPE's own history
up to t (expanding window, >= 20 years of history). Decision at the end of month t applies to month t+1.
Returns: US market total return and T-bills from Ken French daily data, compounded month-end to month-end.

Grid (all reported): q in {70, 80, 90} x {out: all T-bills, half: 50% stocks} when expensive.
Period 1927-01 → 2022-12, $5,000 every January, 2 bps spread on traded amounts. Nulls: 1,000 random
monthly in/out schedules with the same months out and number of exits. Rolling 20-year windows.

    uv run scripts/cape_timing.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.data import RAW_DIR, ROOT
from buying_analysis.experiments import log_trials
from buying_analysis.metrics import xirr
from buying_analysis.report import fmt_table
from buying_analysis.strategies.nulls import in_market_spells, random_schedule

OUT = ROOT / "outputs" / "cape"
START, END = "1927-01-31", "2022-12-31"
AMOUNT, SPREAD = 5000.0, 0.0002
GRID = [(q, mode) for q in (70, 80, 90) for mode in ("out", "half")]
ERAS = {"1927-1963": ("1927", "1963"), "1964-1994": ("1964", "1994"), "1995-2022": ("1995", "2022")}


def cape_signal() -> pd.DataFrame:
    s = pd.read_parquet(RAW_DIR / "shiller_monthly.parquet").set_index("date")
    real_e = s["E"] / s["CPI"]
    avg10 = real_e.shift(4).rolling(120, min_periods=120).mean()
    cape = (s["P"] / s["CPI"].shift(1)) / avg10
    pct = cape.expanding(min_periods=240).apply(lambda v: (v <= v[-1]).mean() * 100, raw=True)
    return pd.DataFrame({"cape": cape, "pct": pct})


def monthly_returns() -> pd.DataFrame:
    kf = pd.read_parquet(RAW_DIR / "ff_factors_daily.parquet").set_index("date")
    m = (1 + kf[["mkt", "rf"]]).resample("ME").prod() - 1
    return m


def simulate(w: pd.Series, r: pd.DataFrame, start=START, end=END) -> pd.DataFrame:
    """Monthly account: deposit each January, stock weight w[t] (decided at t-1's close) for month t."""
    idx = r.loc[start:end].index
    eq, prev_w, rows = 0.0, 0.0, []
    for t in idx:
        dep = AMOUNT if (t.month == 1 or t == idx[0]) else 0.0
        wt = float(w.get(t, np.nan))
        wt = 1.0 if np.isnan(wt) else wt
        base = eq + dep
        cost = SPREAD * (abs(wt - prev_w) * eq + wt * dep)
        port = wt * r.at[t, "mkt"] + (1 - wt) * r.at[t, "rf"]
        new = (base - cost) * (1 + port)
        rows.append((t, dep, wt, new, new / base - 1 if base > 0 else 0.0, r.at[t, "rf"], cost))
        eq, prev_w = new, wt
    return pd.DataFrame(
        rows, columns=["date", "deposit", "w", "equity", "twr", "rf", "cost"]
    ).set_index("date")


def stats(a: pd.DataFrame) -> dict:
    idx = (1 + a["twr"]).cumprod()
    yrs = len(a) / 12
    ex = a["twr"] - a["rf"]
    dates = list(a.index[a["deposit"] > 0]) + [a.index[-1]]
    flows = list(-a.loc[a["deposit"] > 0, "deposit"]) + [a["equity"].iloc[-1]]
    w = a["w"]
    return {
        "final_value": a["equity"].iloc[-1],
        "xirr": xirr(dates, flows),
        "cagr_twr": idx.iloc[-1] ** (1 / yrs) - 1,
        "sharpe": ex.mean() / a["twr"].std() * np.sqrt(12),
        "max_drawdown": (idx / idx.cummax() - 1).min(),
        "avg_stock_weight": w.mean(),
        "months_reduced": int((w < 1).sum()),
        "exits": int(((w < 1) & (w.shift(1, fill_value=1) == 1)).sum()),
        "costs": a["cost"].sum(),
    }


def weights(sig: pd.DataFrame, q: int, mode: str, index) -> pd.Series:
    low = 0.0 if mode == "out" else 0.5
    w = np.where(sig["pct"] > q, low, 1.0)
    w = pd.Series(w, index=sig.index).where(sig["pct"].notna())
    return w.shift(1).reindex(index)  # decided at the end of the previous month


def rolling(w_map: dict, r: pd.DataFrame, years: int = 20) -> pd.DataFrame:
    starts = r.loc[START:END].index
    rows = []
    for s in starts:
        e = s + pd.DateOffset(years=years) - pd.offsets.MonthEnd(1)
        if e > pd.Timestamp(END):
            break
        bh = simulate(pd.Series(1.0, index=r.index), r, s, e)["equity"].iloc[-1]
        for name, w in w_map.items():
            v = simulate(w, r, s, e)["equity"].iloc[-1]
            rows.append({"start": s, "strategy": name, "vs_buy_hold": v / bh - 1})
    return pd.DataFrame(rows)


def predictive(sig: pd.DataFrame, r: pd.DataFrame) -> pd.DataFrame:
    """How well real-time CAPE predicts the next 1 and 10 years of market total return (descriptive)."""
    lr = np.log1p(r["mkt"])
    out = []
    for h in (12, 120):
        fwd = lr[::-1].rolling(h).sum()[::-1].shift(-1)  # sum of months t+1..t+h
        df = pd.DataFrame({"cape": np.log(sig["cape"]), "fwd": fwd}).dropna()
        df = df.loc[START:]
        corr = df["cape"].corr(df["fwd"])
        q = pd.qcut(df["cape"], 5, labels=["cheapest", "2", "3", "4", "most expensive"])
        ann = np.exp(df.groupby(q, observed=True)["fwd"].mean() / (h / 12)) - 1
        out.append({"horizon": f"{h // 12}y", "corr_log_cape_vs_fwd_return": corr, "r_squared": corr**2,
                    **{f"ann_return_{k}": v for k, v in ann.items()}})  # fmt: skip
    return pd.DataFrame(out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sig, r = cape_signal(), monthly_returns()
    idx = r.loc[START:END].index
    bh = simulate(pd.Series(1.0, index=idx), r)
    rows = [{"strategy": "buy_and_hold", **stats(bh)}]
    w_map, runs = {}, {"buy_and_hold": bh}
    rng = np.random.default_rng(0)
    for q, mode in GRID:
        name = f"cape_p{q}_{mode}"
        w = weights(sig, q, mode, idx)
        a = simulate(w, r)
        runs[name], w_map[name] = a, w
        st = stats(a)
        # null: random schedules with the same months reduced and number of exits
        spells, n_red, n = in_market_spells(pd.Series((a["w"] < 1).astype(float)))
        low = 0.0 if mode == "out" else 0.5
        finals = [simulate(pd.Series(np.where(random_schedule(n, n_red, spells, rng), low, 1.0), index=idx), r)
                  ["equity"].iloc[-1] for _ in range(1000)]  # fmt: skip
        st["pct_beat_random"] = float((np.array(finals) < st["final_value"]).mean() * 100)
        rows.append({"strategy": name, **st})
    table = pd.DataFrame(rows)
    table["vs_buy_hold"] = table["final_value"] / table.loc[0, "final_value"] - 1
    eras = pd.DataFrame({n: {e: (1 + a.loc[s:t, "twr"]).prod() ** (12 / len(a.loc[s:t])) - 1
                             for e, (s, t) in ERAS.items()} for n, a in runs.items()}).T  # fmt: skip
    roll = rolling(w_map, r)
    rsum = roll.groupby("strategy", sort=False)["vs_buy_hold"].agg(
        windows="size", median="median", pct_beat=lambda v: (v > 0).mean()
    )
    decade = runs["cape_p80_out"]["w"].groupby(runs["cape_p80_out"].index.year // 10 * 10).apply(
        lambda v: (v < 1).mean())  # fmt: skip
    pred = predictive(sig, r)
    log_trials([{"kind": "cape", **row} for row in table.to_dict("records")])

    for n, df in [("results", table), ("eras", eras), ("rolling_20y", roll), ("predictive", pred),
                  ("signal", sig)]:  # fmt: skip
        df.to_csv(OUT / f"{n}.csv")
    pct = (
        "xirr",
        "cagr_twr",
        "max_drawdown",
        "avg_stock_weight",
        "vs_buy_hold",
        "median",
        "pct_beat",
        "corr_log_cape_vs_fwd_return",
        "r_squared",
        *[c for c in pred.columns if c.startswith("ann_")],
    )
    txt = ["# CAPE valuation timing (1927-2022)", "",
           (f"Latest real-time CAPE in the data: {sig['cape'].dropna().iloc[-1]:.1f} "
           f"({sig['pct'].dropna().iloc[-1]:.0f}th percentile of its history), {sig['cape'].dropna().index[-1]:%Y-%m}."),
           "", fmt_table(table[["strategy", "final_value", "vs_buy_hold", "xirr", "sharpe", "max_drawdown",
                                 "avg_stock_weight", "months_reduced", "exits", "pct_beat_random"]],
                         pct=pct, money=("final_value",), dec2=("sharpe",)), "",
           "## Annualized return by era", "", fmt_table(eras.reset_index(names="strategy"), pct=tuple(eras.columns)),
           "", "## Every 20-year window (monthly starts) vs buy-and-hold", "", fmt_table(rsum.reset_index(), pct=pct),
           "", "## Share of months out of stocks, 80th-percentile all-out rule, by decade", "",
           fmt_table(decade.rename_axis("decade").rename("share_out").reset_index(), pct=("share_out",)), "",
           "## Does CAPE predict returns? (descriptive, full-sample quintiles)", "", fmt_table(pred, pct=pct), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
