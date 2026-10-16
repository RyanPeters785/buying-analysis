"""Does the weekday / time of a weekly DCA purchase matter? (SPY, 1993-2022; 2023-2025 descriptive only)

Each week a fixed amount buys SPY on weekday d at the open (9:30 ET) or close (16:00 ET); if d is a
holiday, the next session that week (or the following one) is used. Prices are total-return indexes, so
dividends are included. Outputs:
  outputs/day_of_week.csv          ending value and price advantage per slot
  outputs/day_of_week_weekly.csv   per-week price of each slot vs that week's average of all 10 slots
  outputs/day_of_week.png          distribution of the weekly price advantage
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis import plots
from buying_analysis.backtest import MarketData
from buying_analysis.data import ROOT
from buying_analysis.strategies.timing import SPY

OUT = ROOT / "outputs"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
AMOUNT = 5000 / 52
SPREAD = 0.0002
PERIODS = {"1993-2022 (development)": ("1993-02-01", "2022-12-30"),
           "2023-2025 (descriptive only)": ("2023-01-02", "2025-12-31")}  # fmt: skip


def slot_prices(md: MarketData) -> pd.DataFrame:
    """Rows = weeks; columns = 'Mon open', 'Mon close', ...: total-return price paid in that slot."""
    c = md.col(SPY)
    s = md.sessions
    px = pd.DataFrame({"open": md.open_idx[:, c], "close": md.close_idx[:, c]}, index=s).dropna()
    week = px.index.to_period("W")
    rows = {}
    for w in week.unique():
        days = px.index[week == w]
        nxt = px.index[px.index > days[-1]]
        row = {}
        for k, name in enumerate(DAYS):
            target = days[0] - pd.Timedelta(days=days[0].weekday()) + pd.Timedelta(days=k)
            pick = days[days >= target]
            d = pick[0] if len(pick) else (nxt[0] if len(nxt) else None)
            if d is None:
                continue
            row[f"{name} open"] = px.at[d, "open"]
            row[f"{name} close"] = px.at[d, "close"]
        rows[w.start_time] = row
    return pd.DataFrame(rows).T.dropna()


def evaluate(prices: pd.DataFrame, end_price: float) -> pd.DataFrame:
    units = (AMOUNT / (prices * (1 + SPREAD))).sum()
    final = units * end_price
    rel = prices.div(prices.mean(axis=1), axis=0) - 1  # + = paid more than the week's average slot
    return pd.DataFrame({
        "final_value": final,
        "vs_best_pct": (final / final.max() - 1) * 100,
        "avg_price_vs_week_mean_bps": rel.mean() * 1e4,
        "pct_weeks_cheapest": (prices.idxmin(axis=1).value_counts(normalize=True) * 100).reindex(prices.columns).fillna(0),
        "ci_lo_bps": [_boot(rel[c]) [0] for c in prices.columns],
        "ci_hi_bps": [_boot(rel[c])[1] for c in prices.columns],
    })  # fmt: skip


def _boot(x: pd.Series, n: int = 2000, block: int = 4, seed: int = 0) -> tuple[float, float]:
    """95% CI of the mean weekly price difference (bps), circular block bootstrap over weeks."""
    v = x.to_numpy()
    t = len(v)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, t, (n, t // block + 1))
    ii = ((starts[:, :, None] + np.arange(block)) % t).reshape(n, -1)[:, :t]
    m = v[ii].mean(axis=1) * 1e4
    return tuple(np.percentile(m, [2.5, 97.5]))


def main() -> None:
    md = MarketData.load([SPY])
    all_prices = slot_prices(md)
    tables = []
    for label, (a, b) in PERIODS.items():
        p = all_prices[(all_prices.index >= a) & (all_prices.index <= b)]
        end = md.close_idx[md.sessions.searchsorted(pd.Timestamp(b), "right") - 1, md.col(SPY)]
        t = evaluate(p, end).assign(period=label, weeks=len(p))
        tables.append(t.reset_index(names="slot"))
        if label.startswith("1993"):
            rel = p.div(p.mean(axis=1), axis=0) - 1
            rel.to_csv(OUT / "day_of_week_weekly.csv")
            dist = {c: rel[c].to_numpy() * 1e4 for c in p.columns}
            plots.hist_panels(dist, {c: rel[c].mean() * 1e4 for c in p.columns},
                              "Price paid vs that week's average of all 10 slots (SPY, 1993-2022)",
                              "basis points (negative = cheaper)", OUT / "day_of_week.png", ncols=5,
                              marker_label="mean", xlim=(-300, 300))  # fmt: skip
    df = pd.concat(tables, ignore_index=True)
    df.to_csv(OUT / "day_of_week.csv", index=False)
    pd.set_option("display.width", 200)
    for label, g in df.groupby("period", sort=False):
        print(f"\n{label}: {g['weeks'].iloc[0]} weeks, ${AMOUNT:.2f}/week")
        print(g.drop(columns=["period", "weeks"]).sort_values("final_value", ascending=False)
              .round(2).to_string(index=False))  # fmt: skip


if __name__ == "__main__":
    main()
