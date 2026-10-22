"""Screen today's stocks for the "cheap + profitable" category (and the "expensive + unprofitable" one).

    uv run scripts/screen_cheap_profitable.py               # S&P 500 (SPY holdings)
    uv run scripts/screen_cheap_profitable.py --universe sptm   # S&P Composite 1500 (SPTM holdings)
    uv run scripts/screen_cheap_profitable.py --include-financials

Same definitions and NYSE breakpoints as scripts/evaluate_stock.py (Fama-French):
  cheapness     book equity (last fiscal year) / market cap at that December -> quintile (5 = cheapest)
  profitability (revenue - COGS - SG&A - interest expense) / book equity -> quintile (5 = most profitable)
  momentum      12-1 month return -> decile; trend = price vs 200-day average (context only)
Financials and real estate are excluded by default (the profitability formula does not fit them); negative
book equity is excluded (as in Fama-French). Holdings: State Street daily SPDR files. Fundamentals:
yfinance, cached per ticker per day in data/cache/fundamentals/.

Output: outputs/screen/screen_<date>.csv and .md. A screen is a starting point for research, not a buy
list: the historical edge was for ~200-stock portfolios, and individual names vary widely. Not advice.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from evaluate_stock import breakpoints, bucket, history_tables, percentile

from buying_analysis.data import RAW_DIR, ROOT
from buying_analysis.report import fmt_table

OUT = ROOT / "outputs" / "screen"
CACHE = RAW_DIR.parent / "cache" / "fundamentals"
HOLDINGS = "https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{}.xlsx"
EXCLUDED_SECTORS = {"Financial Services", "Real Estate"}


def universe(name: str) -> pd.DataFrame:
    req = urllib.request.Request(HOLDINGS.format(name), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = pd.read_excel(io.BytesIO(r.read()), header=None)
    asof = str(raw.iat[2, 1]).replace("As of", "").strip()
    hdr = raw.index[raw.iloc[:, 0].eq("Name")][0]
    df = raw.iloc[hdr + 1 :, :5]
    df.columns = ["name", "ticker", "identifier", "sedol", "weight"]
    df = df.dropna(subset=["ticker"])
    df = df[df["ticker"].astype(str).str.fullmatch(r"[A-Z.]+") & (df["ticker"] != "CASH_USD")]
    df["yf"] = df["ticker"].str.replace(".", "-", regex=False)
    df.attrs["asof"] = asof
    return df.reset_index(drop=True)


def fetch(tk: str) -> dict:
    """Fundamentals and price signals for one ticker (cached for the day)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{tk}_{date.today():%Y%m%d}.json"
    if path.exists():
        return json.loads(path.read_text())
    import yfinance as yf

    out = {"yf": tk, "error": None}
    for attempt in range(3):
        try:
            t = yf.Ticker(tk)
            px = t.history(period="2y", auto_adjust=True)["Close"]
            px.index = px.index.tz_localize(None)
            inc, bs = t.income_stmt, t.balance_sheet
            fy = inc.columns[0]

            def g(df, row, col=fy):
                return (
                    float(df.at[row, col])
                    if row in df.index and pd.notna(df.at[row, col])
                    else np.nan
                )

            shares = t.fast_info.get("shares")
            dec = px.loc[: f"{fy.year}-12-31"]
            me = px.resample("ME").last()
            me = me[me.index < pd.Timestamp.today().normalize().replace(day=1)]
            info = t.info
            out["error"] = None
            out |= {
                "sector": info.get("sector"), "industry": info.get("industry"), "fiscal_year": fy.year,
                "book_equity": g(bs, "Stockholders Equity", bs.columns[0]),
                "market_cap_dec": float(dec.iloc[-1]) * shares if len(dec) and shares else np.nan,
                "market_cap_now": float(px.iloc[-1]) * shares if shares else np.nan,
                "revenue": g(inc, "Total Revenue"), "cogs": g(inc, "Cost Of Revenue"),
                "sga": g(inc, "Selling General And Administration"), "interest": g(inc, "Interest Expense"),
                "operating_income": g(inc, "Operating Income"),
                "momentum_12_1": float(me.iloc[-2] / me.iloc[-13] - 1) if len(me) >= 13 else np.nan,
                "vs_200d": float(px.iloc[-1] / px.rolling(200).mean().iloc[-1] - 1) if len(px) >= 200 else np.nan,
                "price": float(px.iloc[-1]),
            }  # fmt: skip
            break
        except Exception as e:  # noqa: BLE001
            out["error"] = f"{type(e).__name__}: {e}"
            time.sleep((15 if "RateLimit" in type(e).__name__ else 2) * (attempt + 1))
    if out["error"] is None:  # never cache failures, so a rerun retries them
        path.write_text(json.dumps(out, default=float))
    return out


def classify(df: pd.DataFrame) -> pd.DataFrame:
    bm_bp, op_bp = breakpoints("BE-ME_Breakpoints", 2), breakpoints("OP_Breakpoints", 1)
    pr_bp = breakpoints("Prior_2-12_Breakpoints", 1)
    df = df.copy()
    df["bm"] = df["book_equity"] / df["market_cap_dec"]
    expenses = df[["cogs", "sga", "interest"]]
    df["op"] = (df["revenue"] - expenses.fillna(0).sum(axis=1)) / df["book_equity"] * 100
    usable = (
        (df["book_equity"] > 0)
        & df["revenue"].notna()
        & expenses.notna().any(axis=1)
        & df["bm"].notna()
    )
    df["usable"] = usable
    df["bp_year"] = (df["fiscal_year"] + 1).astype("Int64").astype(str)
    df.loc[~df["bp_year"].isin(bm_bp.index), "bp_year"] = bm_bp.index[-1]
    df["bm_pct"] = [
        percentile(b, bm_bp.loc[y]) if u else np.nan
        for b, y, u in zip(df["bm"], df["bp_year"], usable)
    ]
    df["op_pct"] = [percentile(o, op_bp.loc[y if y in op_bp.index else op_bp.index[-1]]) if u else np.nan
                    for o, y, u in zip(df["op"], df["bp_year"], usable)]  # fmt: skip
    df["mom_pct"] = [
        percentile(m * 100, pr_bp.iloc[-1]) if pd.notna(m) else np.nan for m in df["momentum_12_1"]
    ]
    df["bm_q"] = df["bm_pct"].map(lambda v: bucket(v, 5) if pd.notna(v) else pd.NA)
    df["op_q"] = df["op_pct"].map(lambda v: bucket(v, 5) if pd.notna(v) else pd.NA)
    df["mom_decile"] = df["mom_pct"].map(lambda v: bucket(v, 10) if pd.notna(v) else pd.NA)
    df["score"] = df["bm_pct"] + df["op_pct"]
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="spy", choices=["spy", "sptm"])
    ap.add_argument("--include-financials", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    u = universe(args.universe)
    print(
        f"{len(u)} holdings ({u.attrs['asof']}); fetching fundamentals (cached per day)...",
        flush=True,
    )
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(fetch, u["yf"]))
    df = u.merge(pd.DataFrame(rows), on="yf", how="left")
    df = classify(df)
    if not args.include_financials:
        df["excluded_sector"] = df["sector"].isin(EXCLUDED_SECTORS)
    else:
        df["excluded_sector"] = False
    ok = df["usable"] & ~df["excluded_sector"]
    # data sanity: OP above 100% of book usually means missing cost lines (e.g. insurers' claims) or tiny book
    df["check"] = np.where(df["op"] > 100, "OP > 100% of book: verify costs / small book", "")
    _md, cells = history_tables()

    def view(mask, n=None, ascending=False):
        cols = ["ticker", "name", "sector", "bm", "bm_q", "op", "op_q", "mom_decile", "momentum_12_1", "vs_200d",
                "market_cap_now", "check"]  # fmt: skip
        out = df[mask].sort_values("score", ascending=ascending)[cols]
        return out.head(n) if n else out

    corner = ok & (df["bm_q"] == 5) & (df["op_q"] == 5)
    broad = ok & df["bm_q"].isin([4, 5]) & df["op_q"].isin([4, 5])
    junk = ok & df["bm_q"].isin([1, 2]) & df["op_q"].isin([1, 2])
    grid = df[ok].groupby(["bm_q", "op_q"]).size().unstack(fill_value=0)
    stamp = f"{date.today():%Y%m%d}"
    df.to_csv(OUT / f"screen_{args.universe}_{stamp}.csv", index=False)

    fmt = {"pct": ("momentum_12_1", "vs_200d"), "dec2": ("bm",), "money": ()}
    show = lambda d: fmt_table(d.assign(op=d["op"].round(0), market_cap_now=(d["market_cap_now"] / 1e9).round(1))
                               .rename(columns={"market_cap_now": "mkt_cap_$B", "op": "op_%_of_book"}),
                               pct=fmt["pct"], dec2=fmt["dec2"])  # fmt: skip
    txt = [f"# Cheap + profitable screen: {args.universe.upper()} holdings as of {u.attrs['asof']}", "",
           (f"Run {date.today():%Y-%m-%d}. {len(df)} holdings; {int(ok.sum())} usable "
           f"({int(df['excluded_sector'].sum())} financials/real estate excluded, "
           f"{int((~df['usable']).sum())} without usable data or with negative book equity). "
           "Buckets use Ken French NYSE breakpoints (quintile 5 = cheapest / most profitable). "
           "Not investment advice; the historical edge was for ~200-stock portfolios, not single names."), "",
           "## How many usable stocks fall in each cell (rows = cheapness quintile, columns = profitability)", "",
           grid.reset_index().to_markdown(index=False), "",
           "## Caveats on the definitions", "",
           ("- Profitability is operating profit / *book equity*. Companies with large goodwill from acquisitions "
           "(big book equity) look less profitable than their margins suggest, and companies with tiny book equity "
           "(heavy buybacks) look more profitable. Rows flagged in `check` deserve a manual look."),
           ("- yfinance maps some industries poorly (e.g. health insurers' medical costs are not 'cost of revenue'), "
           "which inflates their profitability."),
           ("- The S&P 500 is mostly large, expensive, profitable companies, so few land in the cheapest quintile; "
           "`--universe sptm` (S&P 1500) adds mid and small caps, where the value effect was historically stronger."),
           "",
           "## Historical return vs market of each target cell (value-weighted, before fees)", "",
           (f"- Cheapest + most profitable (5,5): {cells.at[(5, 5), '1964-2022']:+.1%}/yr 1964-2022, "
           f"{cells.at[(5, 5), '2007-2022']:+.1%}/yr 2007-2022"),
           (f"- Expensive + unprofitable (1,1): {cells.at[(1, 1), '1964-2022']:+.1%}/yr 1964-2022, "
           f"{cells.at[(1, 1), '2007-2022']:+.1%}/yr 2007-2022"), "",
           f"## Cheapest + most profitable (both quintile 5): {int(corner.sum())} stocks", "", show(view(corner)), "",
           f"## Broader cheap + profitable (quintiles 4-5 on both): {int(broad.sum())} stocks", "",
           show(view(broad)), "",
           f"## Expensive + unprofitable (quintiles 1-2 on both, historically the worst): {int(junk.sum())} stocks",
           "", show(view(junk, ascending=True)), ""]  # fmt: skip
    (OUT / f"screen_{args.universe}_{stamp}.md").write_text("\n".join(txt))
    print("\n".join(txt[:12]))
    print(f"\nwrote {OUT / f'screen_{args.universe}_{stamp}.md'}")


if __name__ == "__main__":
    main()
