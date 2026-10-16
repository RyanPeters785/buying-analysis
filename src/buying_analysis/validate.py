"""Data validation checks. Each check returns Check(name, status, detail); FAIL is a hard stop.

API data (yfinance, FRED) is used here for comparison only and never written into the primary series.
"""

from __future__ import annotations

import io
import urllib.request
from dataclasses import dataclass, field
from functools import cache

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from buying_analysis import data

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
SPY = 84398
BIG_MOVE = 0.25

# S&P 500 total returns (%), published (S&P Dow Jones Indices). SPY should trail by ~expense ratio + tracking.
SP500_TR = {
    1994: 1.32, 1995: 37.58, 1996: 22.96, 1997: 33.36, 1998: 28.58, 1999: 21.04, 2000: -9.10,
    2001: -11.89, 2002: -22.10, 2003: 28.68, 2004: 10.88, 2005: 4.91, 2006: 15.79, 2007: 5.49,
    2008: -37.00, 2009: 26.46, 2010: 15.06, 2011: 2.11, 2012: 16.00, 2013: 32.39, 2014: 13.69,
    2015: 1.38, 2016: 11.96, 2017: 21.83, 2018: -4.38, 2019: 31.49, 2020: 18.40, 2021: 28.71,
    2022: -18.11, 2023: 26.29, 2024: 25.02, 2025: 17.88,
}  # fmt: skip
SP500_TOL_PP = 0.4

# |ret| > 25% days that were reviewed by hand: (permno, session) -> explanation.
KNOWN_BIG_MOVES = {
    (17830, "2001-09-17"): "UTX first session after 9/11 (aerospace)",
    (19502, "2025-01-10"): "WBA earnings beat (+27.5%)",
    (24643, "2020-03-24"): "ARNC COVID-crash rebound (+26%)",
    (59328, "2024-08-02"): "INTC Q2-2024 earnings / dividend suspension (-26%)",
    (86580, "2016-11-11"): "NVDA Q3-FY17 earnings (+30%)",
    (90215, "2020-08-26"): "CRM Q2-FY21 earnings (+26%)",
    (91208, "2020-03-09"): "USO oil-price crash (Saudi/Russia)",
    (91208, "2020-04-21"): "USO negative WTI front-month aftermath",
}

# Corporate actions in the 2010+ universe: (permno, ex-date, description).
CORPORATE_ACTIONS = [
    (89006, "2012-10-02", "KFT -> MDLZ, Kraft Foods Group spinoff"),
    (27828, "2015-11-02", "HPQ, Hewlett Packard Enterprise spinoff"),
    (24643, "2016-11-01", "AA -> ARNC, Alcoa Corp spinoff"),
    (11703, "2017-09-01", "DD merged into DWDP (delisted)"),
    (16851, "2019-04-02", "DWDP, Dow Inc spinoff"),
    (16851, "2019-06-03", "DWDP -> DD, Corteva spinoff + 1:3 reverse split"),
    (24643, "2020-04-01", "ARNC -> HWM, Arconic Corp spinoff"),
    (17830, "2020-04-03", "UTX -> RTX, Carrier/Otis spinoffs + Raytheon merger"),
    (21936, "2020-11-17", "PFE, Upjohn/Viatris spinoff"),
    (22752, "2021-06-03", "MRK, Organon spinoff"),
    (12490, "2021-11-04", "IBM, Kyndryl spinoff"),
    (66093, "2022-04-11", "T, WarnerMedia/WBD spinoff"),
    (12060, "2023-01-04", "GE, GE HealthCare spinoff"),
    (22592, "2024-04-01", "MMM, Solventum spinoff"),
    (12060, "2024-04-02", "GE, GE Vernova spinoff"),
    (19502, "2025-08-28", "WBA taken private (Sycamore, $11.45 cash; DAP right not valued)"),
]
# Distribution apparently not captured in CRSP ret (excess vs SPY too large and no cumfacpr change).
ACTION_EXCESS_TOL = 0.10

# Accepted primary-data issues (kept as-is; CRSP is never patched with API data).
KNOWN_DATA_ISSUES = [
    (
        "SPY 2000-04-04: CRSP close 145.75 (−3.6%) vs index −0.75% and yfinance 150.125; reverses next day. "
        "Likely bad print. Also possible: 2000-04-14, 2001-04-30. Long-run returns unaffected; timing-strategy "
        "trades on these dates are reported (SUSPECT_SPY_DATES)."
    ),
    "Single-stock spinoff returns that look too low: HWM 2020-04-01, DD 2019-06-03, ARNC 2016-11-01.",
    "WBA 2025-08-28 delisting return reflects the $11.45 cash only (DAP right not valued).",
]
SUSPECT_SPY_DATES = ["2000-04-04", "2000-04-14", "2001-04-30"]

VALIDATION_TICKERS = {84398: "SPY", 85765: "DIA", 89469: "IEF", 89468: "TLT", 90448: "GLD",
                      86457: "XLK", 14593: "AAPL", 10107: "MSFT", 47896: "JPM"}  # fmt: skip
CORR_MIN, ANNUAL_TOL_PP = 0.999, 0.10


@dataclass
class Check:
    name: str
    status: str
    detail: str
    table: pd.DataFrame | None = field(default=None, repr=False)


def nyse_sessions(start, end) -> pd.DatetimeIndex:
    return mcal.get_calendar("NYSE").valid_days(start, end).tz_localize(None).normalize()


# --- Structure -----------------------------------------------------------------------------------------


def check_calendar(p: pd.DataFrame) -> Check:
    cal = nyse_sessions(p["session"].min(), p["session"].max())
    calset = set(cal)
    problems = []
    dup = p.duplicated(["permno", "session"]).sum()
    if dup:
        problems.append(f"{dup} duplicate (permno, session) rows")
    wkend = (p["session"].dt.dayofweek >= 5).sum()
    if wkend:
        problems.append(f"{wkend} weekend rows")
    non_nyse = sorted(set(p["session"].unique()) - calset)
    if non_nyse:
        problems.append(f"{len(non_nyse)} non-NYSE sessions, e.g. {non_nyse[:3]}")
    missing_all = sorted(calset - set(p["session"].unique()))
    if missing_all:
        problems.append(f"{len(missing_all)} NYSE sessions with no rows, e.g. {missing_all[:3]}")
    for permno, s in p.groupby("permno")["session"]:
        span = cal[(cal >= s.min()) & (cal <= s.max())]
        gaps = len(span) - s.nunique()
        if gaps:
            problems.append(f"permno {permno}: {gaps} missing sessions inside its history")
    ok = not problems
    detail = (
        f"{len(cal):,} NYSE sessions {cal[0]:%Y-%m-%d} → {cal[-1]:%Y-%m-%d}; every permno continuous"
        if ok
        else "; ".join(problems[:10])
    )
    return Check("NYSE calendar: no gaps/duplicates/weekends", PASS if ok else FAIL, detail)


def check_partial_histories(p: pd.DataFrame) -> Check:
    g = p.groupby("permno").agg(
        ticker=("ticker", lambda s: "/".join(s.dropna().unique())),
        first=("session", "min"),
        last=("session", "max"),
        rows=("session", "size"),
    )
    lo, hi = g["first"].min(), g["last"].max()
    partial = g[(g["first"] > lo) | (g["last"] < hi)].sort_values("first")
    partial = partial.assign(first=partial["first"].dt.date, last=partial["last"].dt.date)
    return Check(
        "Partial histories (listed, not errors)",
        WARN if len(partial) else PASS,
        f"{len(g)} permnos; {len(partial)} start after {lo:%Y-%m-%d} or end before {hi:%Y-%m-%d}",
        partial.reset_index(),
    )


def check_missing_returns(p: pd.DataFrame) -> Check:
    p = p.sort_values(["permno", "session"])
    first = ~p["permno"].duplicated()
    delist = p["tradingstatusflg"].eq("D")
    bad = p[p["ret"].isna() & ~first & ~delist]
    excused = p[p["ret"].isna() & (first | delist)]
    detail = (
        f"{len(excused)} NaN ret on first-listing or delisting rows only"
        if bad.empty
        else f"{len(bad)} NaN ret on regular rows"
    )
    tbl = (excused if bad.empty else bad)[
        ["permno", "session", "ticker", "dlyretmissflg", "tradingstatusflg"]
    ]
    return Check("Missing returns", FAIL if len(bad) else PASS, detail, tbl.reset_index(drop=True))


def check_price_internals(p: pd.DataFrame) -> Check:
    """Prices positive, open/close sane, and ret_oo_next matches its definition."""
    a = p[p["tradingstatusflg"].ne("D")].sort_values(["permno", "session"])
    problems = []
    for c in ("open", "close", "prc"):
        n = (a[c].astype(float) <= 0).sum()
        if n:
            problems.append(f"{n} non-positive {c}")
    nan_open = a["open"].isna().sum()
    ratio = (a["open"] / a["prc"]).astype(float)
    wild = a[(ratio < 0.5) | (ratio > 2.0)]
    if len(wild):
        problems.append(f"{len(wild)} rows with open/close outside [0.5, 2]")
    intraday = (a["close"] / a["open"]).astype(float)
    g = a.groupby("permno", sort=False)
    nxt = g["ret"].shift(-1).astype(float)
    recon = intraday * (1 + nxt) / intraday.groupby(a["permno"]).shift(-1) - 1
    d = (recon - a["ret_oo_next"].astype(float)).abs().max()
    if d > 1e-8:
        problems.append(f"ret_oo_next differs from its definition by up to {d:.2e}")
    status = FAIL if problems else (WARN if nan_open else PASS)
    detail = (
        "; ".join(problems)
        if problems
        else (
            f"prices positive; open/close in [0.5, 2]; ret_oo_next reproduces (max diff {d:.1e}); "
            f"{nan_open} rows with missing open (engine falls back to close for those fills)"
        )
    )
    return Check("Price internals and open-to-open returns", status, detail)


def check_big_moves(p: pd.DataFrame) -> Check:
    big = p[p["ret"].abs() > BIG_MOVE][["permno", "session", "ticker", "ret"]].copy()
    keys = list(zip(big["permno"].astype(int), big["session"].dt.strftime("%Y-%m-%d")))
    big["explanation"] = [KNOWN_BIG_MOVES.get(k, "") for k in keys]
    unexplained = big[big["explanation"] == ""]
    if not unexplained.empty:  # confirmed if an independent source shows the same move
        conf = _confirm_with_yfinance(unexplained)
        big.loc[unexplained.index, "explanation"] = conf
        unexplained = big[big["explanation"].str.startswith("UNCONFIRMED")]
    big["ret"] = big["ret"].astype(float).round(4)
    return Check(
        f"|daily ret| > {BIG_MOVE:.0%} reviewed",
        FAIL if len(unexplained) else PASS,
        f"{len(big)} flagged, {len(unexplained)} unexplained",
        big.reset_index(drop=True),
    )


def _confirm_with_yfinance(rows: pd.DataFrame) -> list[str]:
    out = []
    for _, r in rows.iterrows():
        try:
            s = _yf_returns(
                r["ticker"],
                r["session"] - pd.Timedelta(days=10),
                r["session"] + pd.Timedelta(days=3),
            )
            yr = s.get(r["session"], np.nan)
        except Exception as e:  # noqa: BLE001
            out.append(f"UNCONFIRMED (yfinance error: {e})")
            continue
        if np.isfinite(yr) and abs(yr - float(r["ret"])) < 0.02:
            out.append(f"confirmed by yfinance ({yr:+.1%})")
        else:
            out.append(f"UNCONFIRMED (yfinance {yr:+.1%})")
    return out


def check_corporate_actions(p: pd.DataFrame) -> Check:
    """On each known action date: ret vs SPY, and whether CRSP changed the price factor."""
    spy = p[p["permno"] == SPY].set_index("session")["ret"].astype(float)
    rows = []
    for permno, d, desc in CORPORATE_ACTIONS:
        d = pd.Timestamp(d)
        s = p[p["permno"] == permno].set_index("session")
        if d not in s.index:
            continue
        prev = s.index[s.index.get_loc(d) - 1]
        ret = float(s.at[d, "ret"]) if pd.notna(s.at[d, "ret"]) else np.nan
        fac_changed = (
            bool(s.at[prev, "cumfacpr"] != s.at[d, "cumfacpr"])
            if pd.notna(s.at[d, "cumfacpr"])
            else None
        )
        excess = ret - spy.get(d, np.nan)
        delisted = s.at[d, "tradingstatusflg"] == "D"
        if delisted:
            verdict = "delisting row" + (
                "; ret missing (engine: cash at last price)" if np.isnan(ret) else ""
            )
        elif abs(excess) > ACTION_EXCESS_TOL:
            verdict = "SUSPECT: distribution may be missing from ret"
        else:
            verdict = "ok"
        rows.append(
            {"permno": permno, "date": d.date(), "action": desc, "ret": round(ret, 4),
             "spy_ret": round(spy.get(d, np.nan), 4), "cumfacpr_changed": fac_changed, "verdict": verdict}
        )  # fmt: skip
    t = pd.DataFrame(rows)
    suspect = t[t["verdict"].str.startswith("SUSPECT")] if len(t) else t
    detail = f"{len(t)} actions checked; {len(suspect)} suspect"
    if len(suspect):
        detail += " (" + ", ".join(f"{r.permno} {r.date}" for r in suspect.itertuples()) + ")"
        detail += ". Single-stock only; ETF/SPY results unaffected"
    return Check(
        "Corporate actions (spinoffs, mergers, delistings)",
        WARN if len(suspect) else PASS,
        detail,
        t,
    )


def check_stitch(p: pd.DataFrame) -> Check:
    hist = data.RAW_DIR / data.HISTORY_FILE
    if not hist.exists():
        return Check(
            "1993-2009 history stitch",
            SKIP,
            "history file not fetched yet (scripts/fetch_crsp_history.py)",
        )
    h = pd.read_parquet(hist, columns=["permno", "session"])
    if h["session"].max() >= pd.Timestamp("2010-01-01"):
        return Check("1993-2009 history stitch", FAIL, "history file overlaps 2010+ sessions")
    return Check(
        "1993-2009 history stitch",
        PASS,
        f"{len(h):,} history rows end {h['session'].max():%Y-%m-%d}; "
        "continuity across 2009→2010 covered by the calendar check",
    )


# --- Cross-source --------------------------------------------------------------------------------------


def _crsp_ret(p: pd.DataFrame, permno: int) -> pd.Series:
    return p[p["permno"] == permno].set_index("session")["ret"].astype(float).rename("ret")


def _crsp_px(p: pd.DataFrame, permno: int) -> pd.Series:
    """Close-to-close price return from split-adjusted CRSP close (prc / cumfacpr), no dividends."""
    s = p[p["permno"] == permno].set_index("session")
    return (s["prc"] / s["cumfacpr"]).astype(float).pct_change()


@cache
def _yf_daily(ticker: str) -> pd.DataFrame:
    """yfinance daily returns 1993..2025: ``px`` from split-adjusted Close, ``tr`` from dividend-adjusted Close."""
    import yfinance as yf

    d = yf.download(ticker, start="1993-01-01", end="2026-01-01", auto_adjust=False, progress=False)
    if d.empty:
        raise RuntimeError(f"no yfinance data for {ticker}")
    d.columns = d.columns.get_level_values(0)
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    return pd.DataFrame({"px": d["Close"].pct_change(), "tr": d["Adj Close"].pct_change()}).iloc[1:]


def _yf_returns(ticker: str, start, end) -> pd.Series:
    tr = _yf_daily(ticker)["tr"]
    return tr[(tr.index >= start) & (tr.index <= end)]


def _annual(j: pd.DataFrame) -> pd.DataFrame:
    """Calendar-year compounded returns, full years only (>= 240 sessions)."""
    ann = (1 + j).groupby(j.index.year).prod() - 1
    return ann[j.groupby(j.index.year).size() >= 240]


def check_cross_source(p: pd.DataFrame) -> Check:
    """CRSP vs yfinance, split into price-only returns (split-adjusted close) and total returns (ret).

    Price disagreement on annual returns is a FAIL. Total-return disagreement with matching prices is a
    dividend-data difference: yfinance's early dividend history has known errors (e.g. IEF 2003 doubled,
    TLT 2012-11 missing), so it is a WARN with the years listed. CRSP total returns are converted to
    yfinance's back-adjustment convention, ret' = (1 + px) / (1 − (ret − px)) − 1, which only matters
    for large special dividends (MSFT 2004-11-15).
    """
    rows, problems = [], []
    for permno, tk in VALIDATION_TICKERS.items():
        s = pd.concat([_crsp_ret(p, permno), _crsp_px(p, permno).rename("cpx")], axis=1).dropna()
        if s.empty:
            continue
        try:
            y = _yf_daily(tk)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{tk}: {e}")
            continue
        j = s.join(y, how="inner").iloc[1:]
        j["ret_conv"] = (1 + j["cpx"]) / (1 - (j["ret"] - j["cpx"])) - 1
        px = _annual(j[["cpx", "px"]])
        tr = _annual(j[["ret_conv", "tr"]])
        px_diff = (px["cpx"] - px["px"]).abs() * 100
        tr_diff = (tr["ret_conv"] - tr["tr"]).abs() * 100
        bad_days = ((j["cpx"] - j["px"]).abs() > 0.01).sum()
        rows.append({
            "ticker": tk, "days": len(j), "corr_px": round(j["cpx"].corr(j["px"]), 5),
            "days_px_diff_gt_1pp": int(bad_days),
            "max_annual_px_diff_pp": round(px_diff.max(), 3), "worst_px_year": int(px_diff.idxmax()),
            "max_annual_tr_diff_pp": round(tr_diff.max(), 3),
            "tr_years_gt_tol": ", ".join(str(y) for y in tr_diff.index[tr_diff > ANNUAL_TOL_PP]),
        })  # fmt: skip
    t = pd.DataFrame(rows)
    if t.empty:
        return Check("Cross-source vs yfinance", FAIL, "no yfinance data: " + "; ".join(problems))
    px_bad = t[t["max_annual_px_diff_pp"] > ANNUAL_TOL_PP]
    low_corr = t[t["corr_px"] <= CORR_MIN]
    div_diff = t[t["tr_years_gt_tol"] != ""]
    parts = [f"{len(t)} tickers; annual price returns within {ANNUAL_TOL_PP}pp"
             + ("" if px_bad.empty else f" EXCEPT {', '.join(px_bad['ticker'])}")]  # fmt: skip
    if len(low_corr):
        parts.append(f"daily corr ≤ {CORR_MIN} for {', '.join(low_corr['ticker'])} (isolated bad prints, "
                     "see SPY vs index check)")  # fmt: skip
    if len(div_diff):
        parts.append(
            f"dividend-data differences (total return only) for {', '.join(div_diff['ticker'])}"
        )
    if problems:
        parts.append("download errors: " + "; ".join(problems))
    status = FAIL if len(px_bad) else (WARN if len(low_corr) or len(div_diff) or problems else PASS)
    return Check("Cross-source vs yfinance (validation only)", status, "; ".join(parts), t)


def check_spy_published(p: pd.DataFrame) -> Check:
    """Annualized SPY − S&P 500 TR over all full years must sit in [-0.4, +0.1]pp (expense ratio + tracking).

    Single years can differ more before ~2005: SPY closed at 4:15pm on AMEX (index at 4:00) and, as a UIT,
    held dividends in cash until quarterly payout. Those years are listed as WARN.
    """
    s = p[p["permno"] == SPY].set_index("session")["ret"].astype(float).dropna()
    ann = ((1 + s).groupby(s.index.year).prod() - 1) * 100
    n = s.groupby(s.index.year).size()
    rows = [
        {"year": y, "spy_crsp_pct": round(ann[y], 2), "sp500_tr_pct": SP500_TR[y],
         "diff_pp": round(ann[y] - SP500_TR[y], 2)}
        for y in ann.index if y in SP500_TR and n[y] >= 240
    ]  # fmt: skip
    t = pd.DataFrame(rows)
    yrs = len(t)
    cagr = lambda col: ((1 + t[col] / 100).prod() ** (1 / yrs) - 1) * 100
    gap = cagr("spy_crsp_pct") - cagr("sp500_tr_pct")
    loud = t[t["diff_pp"].abs() > SP500_TOL_PP]
    ok = -0.4 <= gap <= 0.1
    detail = (
        f"{t['year'].min()}–{t['year'].max()}: SPY {cagr('spy_crsp_pct'):.2f}%/yr vs index "
        f"{cagr('sp500_tr_pct'):.2f}%/yr (gap {gap:+.2f}pp/yr)"
    )
    if len(loud):
        detail += f"; single years beyond {SP500_TOL_PP}pp: {loud['year'].tolist()}"
    return Check("SPY total return vs published S&P 500 TR", FAIL if not ok else (WARN if len(loud) else PASS),
                 detail, t)  # fmt: skip


def check_spy_vs_index(p: pd.DataFrame) -> Check:
    """Daily SPY price return vs S&P 500 index (^GSPC): candidate bad prints in either source.

    A day where |SPY − index| > 1pp and the gap reverses next session is a one-day bad print (net effect on
    long-run returns ~0, but it can trigger daily signals).
    """
    s = _crsp_px(p, SPY)
    ix = _yf_daily("^GSPC")["px"]
    j = pd.concat([s.rename("spy"), ix.rename("index")], axis=1, join="inner").dropna()
    j["gap"] = j["spy"] - j["index"]
    nxt = j["gap"].shift(-1)
    flagged = j[j["gap"].abs() > 0.01].copy()
    flagged["reverses_next_day"] = (np.sign(nxt[flagged.index]) == -np.sign(flagged["gap"])) & (
        nxt[flagged.index].abs() > 0.5 * flagged["gap"].abs()
    )
    flagged = flagged.round(4).reset_index(names="session")
    flagged["session"] = flagged["session"].dt.date
    rev = int(flagged["reverses_next_day"].sum())
    return Check(
        "SPY daily vs S&P 500 index (bad prints)",
        WARN if len(flagged) else PASS,
        f"{len(flagged)} days with |SPY − index| > 1pp ({rev} reverse next day = likely one-day bad prints); "
        f"by year: {flagged.groupby(pd.to_datetime(flagged['session']).dt.year).size().to_dict()}",
        flagged,
    )


def _fred_dgs3mo(start, end) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO&cosd={start:%Y-%m-%d}&coed={end:%Y-%m-%d}"
    with urllib.request.urlopen(url, timeout=60) as r:
        df = pd.read_csv(io.BytesIO(r.read()))
    df.columns = ["observation_date", "value"]
    s = pd.to_numeric(df["value"], errors="coerce")
    s.index = pd.to_datetime(df["observation_date"])
    return s.dropna()


def check_rf(p: pd.DataFrame) -> Check:
    obs = data.load_dgs3mo()
    problems = []
    lag = obs["available_at"] - obs["observation_date"].dt.tz_localize(
        "America/New_York"
    ).dt.tz_convert("UTC")
    if (lag < pd.Timedelta(hours=16)).any():
        problems.append(
            f"{(lag < pd.Timedelta(hours=16)).sum()} values available before the observation day's close"
        )
    try:
        fred = _fred_dgs3mo(obs["observation_date"].min(), obs["observation_date"].max())
        j = (
            obs.set_index("observation_date")["value"]
            .to_frame("local")
            .join(fred.rename("fred"), how="inner")
        )
        maxdiff = (j["local"] - j["fred"]).abs().max()
        if maxdiff > 0.005:
            problems.append(f"local vs FRED differ by up to {maxdiff:.3f}pp")
        fred_note = f"{len(j):,} obs match FRED (max diff {maxdiff:.3f})"
    except Exception as e:  # noqa: BLE001
        problems.append(f"FRED download failed: {e}")
        fred_note = ""
    rf = data.rf_daily(p)
    lead = rf.isna().cumprod().sum()
    gaps = rf.iloc[lead:].isna().sum()
    if gaps:
        problems.append(f"{gaps} NaN rf after the first value")
    detail = (
        "; ".join(problems)
        if problems
        else (
            f"{fred_note}; point-in-time (all values available ≥ next day); daily series forward-filled from past "
            f"releases only; {lead} leading sessions before the first release ({rf.index[0]:%Y-%m-%d} …)"
        )
    )
    status = FAIL if problems else (WARN if lead else PASS)
    return Check("DGS3MO risk-free (point-in-time, vs FRED)", status, detail)


def run_all() -> list[Check]:
    p = data.load_prices()
    checks = [
        check_calendar, check_partial_histories, check_missing_returns, check_price_internals,
        check_big_moves, check_corporate_actions, check_stitch, check_spy_published, check_spy_vs_index,
        check_cross_source, check_rf,
    ]  # fmt: skip
    out = []
    for f in checks:
        try:
            out.append(f(p))
        except Exception as e:  # noqa: BLE001
            out.append(Check(f.__name__, FAIL, f"check crashed: {type(e).__name__}: {e}"))
        print(f"[{out[-1].status}] {out[-1].name}: {out[-1].detail}")
    return out


def to_markdown(checks: list[Check]) -> str:
    p = data.load_prices()
    lines = [
        "# Data validation",
        "",
        (
            f"Primary data: CRSP daily, {p['session'].min():%Y-%m-%d} → {p['session'].max():%Y-%m-%d}, "
            f"{p['permno'].nunique()} permnos, {len(p):,} rows. Generated by `scripts/validate_data.py`."
        ),
        "",
        "| check | status | detail |",
        "|---|---|---|",
    ]
    lines += [f"| {c.name} | **{c.status}** | {c.detail} |" for c in checks]
    lines += ["", "## Known data issues (accepted, not patched)", ""] + [
        f"- {s}" for s in KNOWN_DATA_ISSUES
    ]
    for c in checks:
        if c.table is not None and len(c.table):
            lines += ["", f"## {c.name}", "", c.table.to_markdown(index=False)]
    return "\n".join(lines) + "\n"
