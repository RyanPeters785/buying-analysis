"""Pull US-listed country / region equity ETFs from WRDS (crsp.dsf_v2), 1996-2025, for the country study.

Run manually (Duo push; wrds needs Python 3.11):

    uv run --python 3.11 --group wrds scripts/fetch_country_etfs.py --wrds-username YOUR_USER

Tickers resolve to every fund PERMNO they used in the window (crsp.stocknames_v2); successive PERMNOs
of one ticker are chained into a single series. Writes data/raw/country_etfs.parquet (same columns as the main
panel), caches the raw pull in data/cache/, runs basic checks, and updates the manifest.
"""

from __future__ import annotations

import argparse
import sys
from itertools import pairwise
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from fetch_crsp_history import DSF_COLUMNS, tidy

from buying_analysis.data import PRICES_FILE, RAW_DIR, write_manifest

START, END = "1996-01-02", "2025-12-31"
OUT = "country_etfs.parquet"
RAW_CACHE = RAW_DIR.parent / "cache" / "country_etfs_raw.parquet"
NAMES_CACHE = RAW_DIR.parent / "cache" / "country_etfs_names.parquet"
TICKERS = {
    # developed (iShares, March 1996 unless noted)
    "EWA": "Australia", "EWC": "Canada", "EWD": "Sweden", "EWG": "Germany", "EWH": "Hong Kong",
    "EWI": "Italy", "EWJ": "Japan", "EWK": "Belgium", "EWL": "Switzerland", "EWN": "Netherlands",
    "EWO": "Austria", "EWP": "Spain", "EWQ": "France", "EWS": "Singapore", "EWU": "United Kingdom",
    # emerging
    "EWW": "Mexico", "EWY": "South Korea", "EWT": "Taiwan", "EWZ": "Brazil", "EZA": "South Africa",
    "FXI": "China", "INDA": "India",
    # regions
    "EFA": "Developed ex-US", "EEM": "Emerging markets",
}  # fmt: skip


def resolve(db) -> pd.DataFrame:
    """Every fund PERMNO each ticker used during [START, END] (funds can get a new PERMNO on reorganization)."""
    sql = (
        "select permno, ticker, issuernm, namedt, nameenddt, securitytype from crsp.stocknames_v2 "
        "where ticker in %(t)s and nameenddt >= %(s)s and namedt <= %(e)s"
    )
    names = db.raw_sql(
        sql, params={"t": tuple(TICKERS), "s": START, "e": END}, date_cols=["namedt", "nameenddt"]
    )
    names = names[names["securitytype"] == "FUND"]
    missing = set(TICKERS) - set(names["ticker"])
    if missing:
        raise SystemExit(f"missing tickers: {missing}")
    return names.drop_duplicates(["ticker", "permno"]).sort_values(["ticker", "namedt"])


def stitch(df: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """Chain a ticker's successive PERMNOs into one series under its latest PERMNO.

    The first row of a new PERMNO has no CRSP return; it is bridged from the old PERMNO's last close
    (flag 'BR'). Raises if the spells overlap or leave a gap in the NYSE calendar.
    """
    out = []
    sessions = pd.DatetimeIndex(sorted(df["session"].unique()))
    for tk, g in names.groupby("ticker"):
        permnos = list(dict.fromkeys(g.sort_values("namedt")["permno"].astype(int)))
        parts = [df[df["permno"] == p].sort_values("session") for p in permnos]
        parts = [p for p in parts if len(p)]
        for prev, nxt in pairwise(parts):
            a, b = prev["session"].max(), nxt["session"].min()
            last = prev.index[-1]
            if (
                a == b
                and prev.at[last, "tradingstatusflg"] == "D"
                and pd.notna(prev.at[last, "ret"])
            ):
                # handover day: the old PERMNO's delisting return is that day's return for the new one
                i = nxt.index[0]
                nxt.loc[i, ["ret", "retx"]] = prev.loc[last, ["ret", "retx"]].to_numpy()
                nxt.loc[i, "dlyretmissflg"] = "BR"
                print(
                    f"{tk}: PERMNO {int(prev.at[last, 'permno'])} -> {int(nxt.at[i, 'permno'])} on "
                    f"{b.date()} uses the delisting return {float(prev.at[last, 'ret']):+.4f}"
                )
                parts[parts.index(prev)] = prev = prev.drop(index=last)
                continue
            if sessions.get_loc(b) != sessions.get_loc(a) + 1:
                raise SystemExit(f"{tk}: gap/overlap between PERMNOs ({a.date()} -> {b.date()})")
            i = nxt.index[0]
            if pd.isna(nxt.at[i, "ret"]):
                r = float(nxt.at[i, "prc"]) / float(prev["prc"].iloc[-1]) - 1
                nxt.loc[i, ["ret", "retx"]] = r
                nxt.loc[i, "dlyretmissflg"] = "BR"
                print(
                    f"{tk}: bridged PERMNO {int(prev['permno'].iloc[0])} -> {int(nxt['permno'].iloc[0])} "
                    f"on {b.date()} (ret {r:+.4f})"
                )
        merged = pd.concat(parts)
        merged["permno"] = merged["permno"].iloc[-1]
        merged["ticker"] = tk
        out.append(merged)
    res = (
        pd.concat(out, ignore_index=True).sort_values(["permno", "session"]).reset_index(drop=True)
    )
    for c in df.columns:
        res[c] = res[c].astype(df[c].dtype)
    return res


def pull(username: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    import wrds

    db = wrds.Connection(wrds_username=username)
    try:
        names = resolve(db)
        sql = (
            f"select {', '.join(DSF_COLUMNS)} from crsp.dsf_v2 "
            "where permno in %(p)s and dlycaldt between %(s)s and %(e)s order by permno, dlycaldt"
        )
        params = {"p": tuple(int(p) for p in names["permno"]), "s": START, "e": END}
        raw = db.raw_sql(sql, params=params, date_cols=["dlycaldt"])
    finally:
        db.close()
    return raw, names


def checks(df: pd.DataFrame, names: pd.DataFrame) -> None:
    from buying_analysis.validate import check_calendar, check_missing_returns

    for c in (check_calendar(df), check_missing_returns(df)):
        print(f"[{c.status}] {c.name}: {c.detail}")
    big = df[df["ret"].astype(float).abs() > 0.25][["ticker", "session", "ret"]]
    print(f"{len(big)} days with |ret| > 25% (review):")
    print(big.to_string(index=False) if len(big) else "  none")
    span = df.groupby("permno")["session"].agg(["min", "max", "size"])
    span["ticker"] = span.index.map(names.set_index("permno")["ticker"])
    print(span.sort_values("min").to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrds-username", required=not RAW_CACHE.exists())
    args = ap.parse_args()
    if RAW_CACHE.exists() and NAMES_CACHE.exists():
        print(f"using cached raw pull {RAW_CACHE}")
        raw, names = pd.read_parquet(RAW_CACHE), pd.read_parquet(NAMES_CACHE)
    else:
        print(
            f"resolving {len(TICKERS)} tickers and pulling {START} .. {END} (approve the Duo push)"
        )
        raw, names = pull(args.wrds_username)
        RAW_CACHE.parent.mkdir(parents=True, exist_ok=True)
        raw.to_parquet(RAW_CACHE, index=False)
        names.to_parquet(NAMES_CACHE, index=False)
    template = pd.read_parquet(RAW_DIR / PRICES_FILE)
    df = stitch(tidy(raw, template, cal_start=START, cal_end=END), names)
    df.to_parquet(RAW_DIR / OUT, index=False)
    print(f"wrote {OUT}: {len(df):,} rows, {df['permno'].nunique()} funds")
    checks(df, names)
    write_manifest(
        {OUT: f"WRDS `crsp.dsf_v2` country/region ETFs ({', '.join(TICKERS)}), {START} → {END}"}
    )


if __name__ == "__main__":
    main()
