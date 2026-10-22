"""Value + momentum: split money between cheap stocks and recent winners (50/50, rebalanced each January).

Two pre-declared versions (Ken French value-weighted portfolios, monthly):
  large-cap, 1927-2022:  large-company value (big_value, 2x3 size x B/M) + large-company winners
                         (BIG HiPRIOR, 2x3 size x 12-1 momentum)
  quality, 1964-2022:    cheap + profitable (top 2 x top 2 of the 5x5 B/M x OP sort) + top 20% momentum
Cost drag: value 0.25%/yr, momentum 1%/yr, market 0.03%/yr. $5,000 each January; the 50/50 mix rebalances
to target when each deposit lands. Reported: full period, eras, worst relative stretches, correlation of the
two sleeves' excess returns, every 20-year window, 2023-2025 descriptive.

    uv run scripts/value_momentum.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from stock_momentum import portfolios as momentum_portfolios
from value_profitability import combo_returns, load, stats

from buying_analysis import plots
from buying_analysis.data import RAW_DIR, ROOT
from buying_analysis.experiments import log_trials
from buying_analysis.report import fmt_table

OUT = ROOT / "outputs" / "value_momentum"
FEE_VALUE, FEE_MOM, FEE_MKT = 0.0025, 0.01, 0.0003
VERSIONS = {
    "large-cap (1927-2022)": ("1927-02-28", "2022-12-31"),
    "quality (1964-2022)": ("1964-01-31", "2022-12-31"),
}
ERAS = {"to 1963": ("1927", "1963"), "1964-1993": ("1964", "1993"), "1994-2006": ("1994", "2006"),
        "2007-2022": ("2007", "2022")}  # fmt: skip


def sleeves_sim(rets: pd.DataFrame, weights: dict[str, float], fees: dict[str, float], rf: pd.Series,
                start, end, amount: float = 5000.0) -> pd.DataFrame:  # fmt: skip
    """Monthly account with sleeves: deposit each January (and first month), rebalance to ``weights`` then."""
    r = rets.loc[start:end, list(weights)]
    hold = dict.fromkeys(weights, 0.0)
    rows = []
    for t, row in r.iterrows():
        dep = amount if (t.month == 1 or t == r.index[0]) else 0.0
        total = sum(hold.values()) + dep
        if dep:
            hold = {k: total * w for k, w in weights.items()}
        before = sum(hold.values())
        hold = {k: v * (1 + row[k] - fees[k] / 12) for k, v in hold.items()}
        after = sum(hold.values())
        rows.append((t, dep, after, after / before - 1 if before > 0 else 0.0, rf.get(t, 0.0)))
    return pd.DataFrame(rows, columns=["date", "deposit", "equity", "ret", "rf"]).set_index("date")


def series() -> tuple[pd.DataFrame, pd.Series]:
    p25, m = load()
    c = combo_returns(p25)
    mom, _, _ = momentum_portfolios()
    six = pd.read_parquet(RAW_DIR / "ff_6_portfolios_daily.parquet").set_index("date")
    big_value = (1 + six["big_value"]).resample("ME").prod() - 1
    df = pd.DataFrame({
        "market": m["mkt"],
        "large value": big_value,
        "large winners": mom["big-company winners (top 30% of large caps)"],
        "cheap + profitable": c["cheap + profitable (top 2 x top 2)"],
        "top 20% momentum": mom["top 20% (deciles 9-10)"],
    })  # fmt: skip
    return df, m["rf"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    r, rf = series()
    fees = {"market": FEE_MKT, "large value": FEE_VALUE, "cheap + profitable": FEE_VALUE,
            "large winners": FEE_MOM, "top 20% momentum": FEE_MOM}  # fmt: skip
    plans = {
        "large-cap (1927-2022)": {"market": {"market": 1.0}, "value only": {"large value": 1.0},
                                  "momentum only": {"large winners": 1.0},
                                  "50/50 value + momentum": {"large value": 0.5, "large winners": 0.5}},
        "quality (1964-2022)": {"market": {"market": 1.0}, "value only": {"cheap + profitable": 1.0},
                                "momentum only": {"top 20% momentum": 1.0},
                                "50/50 value + momentum": {"cheap + profitable": 0.5, "top 20% momentum": 0.5}},
    }  # fmt: skip
    rows, eras_rows, _worst_rows, roll_rows, recent_rows, rel = [], [], [], [], [], {}
    for version, (start, end) in VERSIONS.items():
        runs = {name: sleeves_sim(r, w, fees, rf, start, end) for name, w in plans[version].items()}
        base = runs["market"]
        vk, mk = (next(iter(plans[version]["value only"])), next(iter(plans[version]["momentum only"])))
        exv = (r[vk] - r["market"]).loc[start:end]
        exm = (r[mk] - r["market"]).loc[start:end]
        corr = exv.corr(exm)
        for name, a in runs.items():
            s = stats(a)
            rel_idx = (1 + a["ret"]).cumprod() / (1 + base["ret"]).cumprod()
            worst = {
                f"worst_{k}y_vs_market": (rel_idx / rel_idx.shift(12 * k) - 1).min()
                for k in (3, 5, 10)
            }
            rows.append({"version": version, "plan": name, **s,
                         "vs_market": a["equity"].iloc[-1] / base["equity"].iloc[-1] - 1, **worst})  # fmt: skip
            for e, (s0, s1) in ERAS.items():
                x = a.loc[s0:s1, "ret"]
                if len(x) >= 24:
                    eras_rows.append({"version": version, "plan": name, "era": e,
                                      "ann_return": (1 + x).prod() ** (12 / len(x)) - 1})  # fmt: skip
            if version.startswith("large") and name != "market":
                rel[name] = rel_idx
        rows.append(
            {"version": version, "plan": "corr(value excess, momentum excess)", "sharpe": corr}
        )
        for s0 in r.loc[start:end].index:
            e1 = s0 + pd.DateOffset(years=20) - pd.offsets.MonthEnd(1)
            if e1 > pd.Timestamp(end):
                break
            b = sleeves_sim(r, {"market": 1.0}, fees, rf, s0, e1)["equity"].iloc[-1]
            for name, w in plans[version].items():
                if name == "market":
                    continue
                v = sleeves_sim(r, w, fees, rf, s0, e1)["equity"].iloc[-1]
                roll_rows.append({"version": version, "plan": name, "vs_market": v / b - 1})
        for name, w in plans[version].items():
            recent_rows.append({"version": version, "plan": name,
                                **stats(sleeves_sim(r, w, fees, rf, "2023-01-31", "2025-12-31"))})  # fmt: skip
    table = pd.DataFrame(rows)
    eras = pd.DataFrame(eras_rows).pivot_table(index=["version", "plan"], columns="era", values="ann_return",
                                               sort=False)  # fmt: skip
    roll = (
        pd.DataFrame(roll_rows)
        .groupby(["version", "plan"], sort=False)["vs_market"]
        .agg(windows="size", median="median", pct_beat=lambda v: (v > 0).mean(), worst="min")
    )
    recent = pd.DataFrame(recent_rows)
    plots.line_chart(rel, "Large-cap: growth of $1 relative to the market (time-weighted, after costs)",
                     "ratio to market (log)", OUT / "relative_to_market.png", log=True,
                     fmt=lambda v: f"{v:.2f}x")  # fmt: skip
    log_trials([{"kind": "value_momentum", "strategy": f"{x['version']} | {x['plan']}", **x}
                for x in table.to_dict("records") if "corr" not in x["plan"]])  # fmt: skip
    for n, d in [
        ("results", table),
        ("eras", eras),
        ("rolling_20y", roll),
        ("recent_2023_2025", recent),
    ]:
        d.to_csv(OUT / f"{n}.csv")
    pct = ("xirr", "max_drawdown", "vs_market", "worst_3y_vs_market", "worst_5y_vs_market", "worst_10y_vs_market",
           "median", "pct_beat", "worst", *eras.columns)  # fmt: skip
    main_tbl = table[~table["plan"].str.startswith("corr")]
    corr_tbl = table[table["plan"].str.startswith("corr")][["version", "sharpe"]].rename(
        columns={"sharpe": "corr"}
    )
    txt = ["# Value + momentum (50/50, rebalanced each January)", "",
           f"Costs: value {FEE_VALUE:.2%}/yr, momentum {FEE_MOM:.1%}/yr, market {FEE_MKT:.2%}/yr; $5,000 each January.", "",
           fmt_table(main_tbl[["version", "plan", "final_value", "vs_market", "xirr", "sharpe", "max_drawdown",
                               "worst_3y_vs_market", "worst_5y_vs_market", "worst_10y_vs_market"]],
                     pct=pct, money=("final_value",), dec2=("sharpe",)), "",
           "## Correlation of the two sleeves' monthly returns in excess of the market", "",
           fmt_table(corr_tbl, dec2=("corr",)), "",
           "## Annualized return by era (after costs)", "", fmt_table(eras.reset_index(), pct=tuple(eras.columns)), "",
           "## Every 20-year window (monthly starts), ending value vs market", "", fmt_table(roll.reset_index(), pct=pct),
           "", "## 2023-2025 (descriptive)", "",
           fmt_table(recent[["version", "plan", "final_value", "xirr", "max_drawdown"]], pct=pct,
                     money=("final_value",)), ""]  # fmt: skip
    (OUT / "report.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main()
