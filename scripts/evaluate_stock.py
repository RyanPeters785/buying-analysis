"""Place one stock in this project's factor buckets and show how stocks in those buckets historically did.

    uv run scripts/evaluate_stock.py RIVN

Signals (Fama-French definitions, NYSE breakpoints from the Ken French Data Library):
  momentum      return from 12 months ago to 1 month ago (latest complete months) -> decile
  cheapness     book equity (last fiscal year) / market cap at the prior December -> quintile
  profitability (revenue - COGS - SG&A - interest expense) / book equity (last fiscal year) -> quintile
  trend         price vs its 200-day average; worst drawdown; volatility vs SPY
History for each bucket comes from the Ken French portfolios used in stock_momentum.py and
value_profitability.py. Current prices and financials come from yfinance (descriptive only, not part of
any backtest). Output: outputs/stock_eval/<TICKER>.md. Not investment advice.
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile

import numpy as np
import pandas as pd

from buying_analysis.data import RAW_DIR, ROOT

OUT = ROOT / "outputs" / "stock_eval"
CACHE = RAW_DIR.parent / "cache" / "kf_breakpoints"
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
PCTS = np.arange(5, 101, 5)


def breakpoints(name: str, skip: int) -> pd.DataFrame:
    """Rows = period, columns = 5th..100th NYSE percentiles. ``skip`` = count columns after the period."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.csv"
    if not path.exists():
        with urllib.request.urlopen(BASE + f"{name}_CSV.zip", timeout=120) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        path.write_bytes(z.read(z.namelist()[0]))
    rows = []
    for ln in path.read_text(encoding="latin-1").splitlines():
        parts = [p.strip() for p in ln.split(",")]
        if parts and parts[0].isdigit() and len(parts) >= 1 + skip + 20:
            rows.append([parts[0], *map(float, parts[1 + skip : 1 + skip + 20])])
    df = pd.DataFrame(rows, columns=["period", *PCTS]).set_index("period")
    return df


def percentile(value: float, bp: pd.Series) -> float:
    """Approximate NYSE percentile of ``value`` by interpolating the 5%-step breakpoints."""
    xs, ys = bp.to_numpy(), PCTS.astype(float)
    if value <= xs[0]:
        return float(ys[0] * value / xs[0]) if xs[0] > 0 and value > 0 else 0.0
    return float(np.interp(value, xs, ys))


def bucket(pct: float, n: int) -> int:
    return int(min(n, max(1, np.ceil(pct / (100 / n)))))


def fundamentals(tk: str) -> dict:
    import yfinance as yf

    t = yf.Ticker(tk)
    px = t.history(period="max", auto_adjust=True)["Close"]
    px.index = px.index.tz_localize(None)
    inc, bs = t.income_stmt, t.balance_sheet
    fy = inc.columns[0]
    g = lambda df, row, col=fy: (
        float(df.at[row, col]) if row in df.index and pd.notna(df.at[row, col]) else 0.0
    )
    be = g(bs, "Stockholders Equity", bs.columns[0])
    shares = t.fast_info.get("shares")
    dec = px.loc[: f"{fy.year}-12-31"]
    me_dec = float(dec.iloc[-1]) * shares if len(dec) else np.nan
    op_num = g(inc, "Total Revenue") - g(inc, "Cost Of Revenue") - g(inc, "Selling General And Administration") \
        - g(inc, "Interest Expense")  # fmt: skip
    q = t.quarterly_income_stmt.iloc[:, :4]
    ttm = lambda row: float(q.loc[row].sum()) if row in q.index else np.nan
    return {
        "ticker": tk, "prices": px, "fiscal_year": fy.year, "book_equity": be, "shares": shares,
        "market_cap_now": float(px.iloc[-1]) * shares, "market_cap_dec": me_dec,
        "revenue": g(inc, "Total Revenue"), "gross_profit": g(inc, "Gross Profit"),
        "operating_income": g(inc, "Operating Income"), "net_income": g(inc, "Net Income"),
        "op_numerator": op_num, "ttm_revenue": ttm("Total Revenue"), "ttm_operating_income": ttm("Operating Income"),
        "ttm_quarters": [c.strftime("%Y-%m") for c in q.columns],
    }  # fmt: skip


def history_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Annualized return by momentum decile (1927-2022, 2007-2022) and by BM x OP cell minus market."""
    kf = pd.read_parquet(RAW_DIR / "ff_factors_daily.parquet").set_index("date")
    mkt = (1 + kf["mkt"]).resample("ME").prod() - 1
    mom = pd.read_parquet(RAW_DIR / "ff_10_momentum_monthly.parquet").pivot(
        index="date", columns="col", values="ret"
    )

    def ann(x, a, b):
        x = x.loc[a:b]
        return (1 + x).prod() ** (12 / len(x)) - 1

    md = pd.DataFrame({"1927-2022": {d: ann(mom[d], "1927", "2022") for d in mom},
                       "2007-2022": {d: ann(mom[d], "2007", "2022") for d in mom}})  # fmt: skip
    md.loc["market"] = [ann(mkt, "1927", "2022"), ann(mkt, "2007", "2022")]
    p = pd.read_parquet(RAW_DIR / "ff_25_bm_op_monthly.parquet").pivot(
        index="date", columns=["bm", "op"], values="ret"
    )
    cells = pd.DataFrame({"1964-2022": {c: ann(p[c], "1964", "2022") - ann(mkt, "1964", "2022") for c in p},
                          "2007-2022": {c: ann(p[c], "2007", "2022") - ann(mkt, "2007", "2022") for c in p}})  # fmt: skip
    return md, cells


def main(tk: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    f = fundamentals(tk)
    px = f["prices"]
    me = px.resample("ME").last()
    me = me[me.index < pd.Timestamp.today().normalize().replace(day=1)]  # completed months only
    mom_ret = me.iloc[-2] / me.iloc[-13] - 1 if len(me) >= 13 else np.nan
    mom_window = f"{me.index[-13]:%Y-%m} → {me.index[-2]:%Y-%m}" if len(me) >= 13 else "n/a"

    bm_bp = breakpoints("BE-ME_Breakpoints", 2)
    op_bp = breakpoints("OP_Breakpoints", 1)
    pr_bp = breakpoints("Prior_2-12_Breakpoints", 1)
    bm_year = (
        str(f["fiscal_year"] + 1) if str(f["fiscal_year"] + 1) in bm_bp.index else bm_bp.index[-1]
    )
    op_year = bm_year if bm_year in op_bp.index else op_bp.index[-1]
    pr_month = pr_bp.index[-1]

    bm = f["book_equity"] / f["market_cap_dec"] if f["book_equity"] > 0 else np.nan
    op = f["op_numerator"] / f["book_equity"] * 100 if f["book_equity"] > 0 else np.nan
    bm_pct = percentile(bm, bm_bp.loc[bm_year]) if pd.notna(bm) else np.nan
    op_pct = percentile(op, op_bp.loc[op_year]) if pd.notna(op) else 0.0
    mom_pct = percentile(mom_ret * 100, pr_bp.loc[pr_month]) if pd.notna(mom_ret) else np.nan
    mom_dec, bm_q, op_q = bucket(mom_pct, 10), bucket(bm_pct, 5), bucket(op_pct, 5)

    md, cells = history_tables()
    sma200 = px.rolling(200).mean().iloc[-1]
    dd = px / px.cummax() - 1
    import yfinance as yf

    spy = yf.Ticker("SPY").history(start=px.index[0], auto_adjust=True)["Close"]
    spy.index = spy.index.tz_localize(None)
    vol = np.log(px).diff().std() * np.sqrt(252)
    spy_vol = np.log(spy).diff().std() * np.sqrt(252)
    years = (px.index[-1] - px.index[0]).days / 365.25
    cagr = (px.iloc[-1] / px.iloc[0]) ** (1 / years) - 1
    spy_cagr = (spy.iloc[-1] / spy.iloc[0]) ** (1 / years) - 1

    B = 1e9
    txt = [f"# {tk}: where it lands in this project's factor buckets", "",
           (f"Data: yfinance prices through {px.index[-1]:%Y-%m-%d}; fiscal year {f['fiscal_year']} financials; "
           f"Ken French NYSE breakpoints (BM/OP {bm_year}, momentum {pr_month}). Descriptive only; not advice."), "",
           "## Inputs", "",
           (f"- Price {px.iloc[-1]:.2f}; market cap now ${f['market_cap_now'] / B:,.1f}B "
           f"(Dec {f['fiscal_year']}: ${f['market_cap_dec'] / B:,.1f}B); book equity ${f['book_equity'] / B:,.2f}B"),
           (f"- FY{f['fiscal_year']}: revenue ${f['revenue'] / B:,.2f}B, gross profit ${f['gross_profit'] / B:,.2f}B, "
           f"operating income ${f['operating_income'] / B:,.2f}B, net income ${f['net_income'] / B:,.2f}B"),
           (f"- Last 4 quarters ({', '.join(f['ttm_quarters'])}): revenue ${f['ttm_revenue'] / B:,.2f}B, "
           f"operating income ${f['ttm_operating_income'] / B:,.2f}B"), "",
           "## Signals", "",
           "| Signal | Value | NYSE percentile | Bucket |", "|---|---|---|---|",
           f"| Momentum (12-1), {mom_window} | {mom_ret:+.1%} | {mom_pct:.0f} | decile {mom_dec} of 10 |",
           f"| Book-to-market (cheapness) | {bm:.2f} | {bm_pct:.0f} | quintile {bm_q} of 5 (5 = cheapest) |",
           f"| Operating profitability | {op:.0f}% of book | {op_pct:.0f} | quintile {op_q} of 5 (5 = most profitable) |",
           f"| Price vs 200-day average | {px.iloc[-1] / sma200 - 1:+.1%} | | {'above' if px.iloc[-1] > sma200 else 'below'} |",
           "", "## What stocks in the same buckets historically did (value-weighted portfolios)", "",
           "| Bucket | Annual return 1927/1964-2022 | 2007-2022 |", "|---|---|---|",
           (f"| Momentum decile {mom_dec} | {md.at[mom_dec, '1927-2022']:.1%} (market {md.at['market', '1927-2022']:.1%}) "
           f"| {md.at[mom_dec, '2007-2022']:.1%} (market {md.at['market', '2007-2022']:.1%}) |"),
           (f"| Cheapness {bm_q} × profitability {op_q} cell, vs market | {cells.at[(bm_q, op_q), '1964-2022']:+.1%}/yr "
           f"| {cells.at[(bm_q, op_q), '2007-2022']:+.1%}/yr |"),
           "", "## Single-stock risk", "",
           (f"- Since listing ({px.index[0]:%Y-%m-%d}): {cagr:+.1%}/yr vs SPY {spy_cagr:+.1%}/yr; worst drawdown "
           f"{dd.min():.0%} (now {-dd.iloc[-1]:.0%} below its peak)"),
           f"- Volatility {vol:.0%}/yr vs SPY {spy_vol:.0%}/yr", ""]  # fmt: skip
    (OUT / f"{tk}.md").write_text("\n".join(txt))
    print("\n".join(txt))


if __name__ == "__main__":
    main(sys.argv[1].upper() if len(sys.argv) > 1 else "RIVN")
