"""Monthly long-only portfolio simulation for ranked stock selections (Roth IRA: no shorting or leverage).

At each rebalance month-end t the portfolio buys the ``top_n`` highest-scored stocks, equal-weighted; between
rebalances weights drift with returns. Returns come from the full CRSP monthly file (not just the top-1000
panel), so a held stock that leaves the universe or delists keeps contributing its actual return (the
delisting return is in its last row; after that its money is cash at 0%). Costs are charged on traded value
(``cost_bps`` per side), including investing each $5,000 January deposit, which is added at the December
month-end so it is invested for January.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.metrics import xirr
from buying_analysis.ml.panel import ML_DIR, SPY, month_end


def return_matrix() -> pd.DataFrame:
    msf = pd.read_parquet(ML_DIR / "crsp_msf.parquet")
    msf["mthcaldt"] = month_end(msf["mthcaldt"])
    msf = msf.drop_duplicates(["permno", "mthcaldt"], keep="last")
    return msf.pivot(index="mthcaldt", columns="permno", values="mthret").astype(float).sort_index()


def simulate(targets: dict[pd.Timestamp, pd.Series], rets: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
             cost_bps: float = 10.0, amount: float = 5000.0,
             cost_map: dict[pd.Timestamp, pd.Series] | None = None, default_bps: float = 75.0) -> pd.DataFrame:  # fmt: skip
    """``targets`` maps rebalance month-end -> target weights (permno -> weight, summing to 1).

    Costs: ``cost_bps`` per side for every stock, or, with ``cost_map``, a per-stock rate (bps per side) at each
    month-end; stocks missing from the map (e.g. holdings that left the universe) are charged ``default_bps``.
    The holding period after month-end t earns the returns of month t+1. Returns one row per holding month.
    """
    months = rets.index[(rets.index >= start) & (rets.index <= end)]
    hold = pd.Series(dtype=float)  # dollars per permno, valued at the latest month-end
    cash = 0.0
    rows = []
    c = cost_bps / 1e4
    for i, t in enumerate(months[:-1]):
        nxt = months[i + 1]
        dep = amount if (t.month == 12 or i == 0) else 0.0
        cash += dep
        value = cash + hold.sum()
        cost, trade = 0.0, 0.0
        if t in targets or dep:
            w = targets.get(t)
            if w is None:  # deposit without a rebalance: keep current mix, add the cash pro rata
                w = hold / hold.sum() if hold.sum() > 0 else None
            if w is not None:
                new = w * value
                traded = new.sub(hold, fill_value=0).abs()
                trade = traded.sum()
                if cost_map is not None:
                    bps = (
                        cost_map.get(t, pd.Series(dtype=float))
                        .reindex(traded.index)
                        .fillna(default_bps)
                    )
                    cost = float((traded * bps).sum()) / 1e4
                else:
                    cost = trade * c
                scale = (value - cost) / value
                hold, cash = new * scale, 0.0
        r = rets.loc[nxt].reindex(hold.index).fillna(0.0)  # missing next month = delisted -> cash
        before = value  # account value after the deposit and *before* costs, so costs reduce the return
        hold = hold * (1 + r)
        hold = hold[hold.abs() > 1e-9]
        after = cash + hold.sum()
        turnover = 0.0 if value <= 0 or not (t in targets or dep) else trade / value
        rows.append(
            (nxt, dep, after, after / before - 1 if before > 0 else 0.0, cost, turnover, len(hold))
        )
    return pd.DataFrame(rows, columns=["date", "deposit", "equity", "ret", "cost", "turnover", "n_holdings"]) \
        .set_index("date")  # fmt: skip


def top_n_targets(preds: pd.DataFrame, top_n: int, every: int, start: pd.Timestamp) -> dict:
    """Equal-weight top-N targets at every ``every``-th month-end from ``start``."""
    out = {}
    dates = sorted(d for d in preds["date"].unique() if d >= start)
    for k, d in enumerate(dates):
        if k % every:
            continue
        g = preds[preds["date"] == d].nlargest(top_n, "score")
        out[pd.Timestamp(d)] = pd.Series(1.0 / len(g), index=g["permno"].to_numpy())
    return out


def universe_targets(panel: pd.DataFrame, start: pd.Timestamp, how: str) -> dict:
    """Equal- or cap-weighted top-1000 universe, rebalanced monthly."""
    out = {}
    for d, g in panel[panel["date"] >= start].groupby("date"):
        w = pd.Series(1.0, index=g["permno"].to_numpy()) if how == "equal" else \
            pd.Series(g["mcap"].to_numpy(), index=g["permno"].to_numpy())  # fmt: skip
        out[pd.Timestamp(d)] = w / w.sum()
    return out


def spy_targets(dates) -> dict:
    return {pd.Timestamp(d): pd.Series({SPY: 1.0}) for d in dates[:1]}


def summary(a: pd.DataFrame, rf: pd.Series) -> dict:
    """Metrics for one simulation. Deposits are dated at the month-end before the holding month they fund."""
    r = a["ret"]
    idx = (1 + r).cumprod()
    deps = a["deposit"][a["deposit"] > 0]
    flows_d = [d - pd.offsets.MonthEnd(1) for d in deps.index] + [a.index[-1]]
    flows = list(-deps) + [a["equity"].iloc[-1]]
    ex = r - rf.reindex(a.index).fillna(0.0)
    return {
        "final_value": a["equity"].iloc[-1], "xirr": xirr(flows_d, flows),
        "cagr": idx.iloc[-1] ** (12 / len(r)) - 1, "volatility": r.std() * np.sqrt(12),
        "sharpe": ex.mean() / r.std() * np.sqrt(12), "max_drawdown": (idx / idx.cummax() - 1).min(),
        "turnover_per_yr": a["turnover"].sum() / (len(r) / 12), "costs": a["cost"].sum(),
        "avg_holdings": a["n_holdings"].mean(),
    }  # fmt: skip
