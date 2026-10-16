"""Pull CRSP daily history (1993-01-29 .. 2009-12-31) for the same permnos, plus DGS3MO from FRED.

Run manually (WRDS login needs a Duo push; wrds needs Python 3.11):

    uv run --python 3.11 --group wrds scripts/fetch_crsp_history.py --wrds-username YOUR_USER

Writes data/raw/prices_daily_1993_2009.parquet and data/raw/dgs3mo_1993_2009.parquet (same columns and
conventions as the 2010+ files), checks the stitch against the existing 2010 rows, and updates the manifest.
"""

from __future__ import annotations

import argparse
import io
import urllib.request

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from buying_analysis.data import (
    HISTORY_FILE,
    PRICES_FILE,
    RAW_DIR,
    RF_HISTORY_FILE,
    write_manifest,
)

START, END = "1993-01-29", "2009-12-31"
OVERLAP_END = "2010-01-29"  # pulled only to compute ret_oo_next on 2009-12-31 and check the stitch

DSF_COLUMNS = [
    "permno", "permco", "dlycaldt", "ticker", "dlyopen", "dlyhigh", "dlylow", "dlyclose", "dlyprc", "dlyprcflg",
    "dlyret", "dlyretx", "dlyretmissflg", "dlyvol", "dlycumfacpr", "dlycumfacshr", "shrout", "dlydelflg",
    "tradingstatusflg", "securitytype",
]  # fmt: skip
RENAME = {
    "dlycaldt": "session", "dlyopen": "open", "dlyhigh": "high", "dlylow": "low", "dlyclose": "close",
    "dlyprc": "prc", "dlyret": "ret", "dlyretx": "retx", "dlyvol": "volume", "dlycumfacpr": "cumfacpr",
    "dlycumfacshr": "cumfacshr", "dlydelflg": "delist_flag",
}  # fmt: skip
RAW_CACHE = RAW_DIR.parent / "cache" / "dsf_v2_1993_2010_raw.parquet"  # untouched WRDS rows
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO&cosd={}&coed={}"


def fetch_crsp(username: str, permnos: list[int]) -> pd.DataFrame:
    import wrds

    db = wrds.Connection(wrds_username=username)
    try:
        sql = (
            f"select {', '.join(DSF_COLUMNS)} from crsp.dsf_v2 "
            "where permno in %(permnos)s and dlycaldt between %(start)s and %(end)s order by permno, dlycaldt"
        )
        params = {"permnos": tuple(permnos), "start": START, "end": OVERLAP_END}
        return db.raw_sql(sql, params=params, date_cols=["dlycaldt"])
    finally:
        db.close()


def tidy(raw: pd.DataFrame, template: pd.DataFrame) -> pd.DataFrame:
    """Match the processed 2010+ panel: renamed columns, abs prices, available_at = session close (UTC)."""
    df = raw.rename(columns=RENAME)
    df["session"] = pd.to_datetime(df["session"]).dt.normalize()
    for col in ("open", "high", "low", "close", "prc"):
        df[col] = pd.to_numeric(df[col], errors="coerce").abs()
    sched = mcal.get_calendar("NYSE").schedule(START, OVERLAP_END)
    closes = sched["market_close"].dt.tz_convert("UTC")
    closes.index = pd.DatetimeIndex(sched.index).normalize()
    df["available_at"] = df["session"].map(closes)
    if df["available_at"].isna().any():
        bad = df.loc[df["available_at"].isna(), "session"].unique()[:5]
        raise SystemExit(f"CRSP rows on non-NYSE sessions: {bad}")
    df = df.sort_values(["permno", "session"]).reset_index(drop=True)
    df["ret_oo_next"] = open_to_open_returns(df)
    for c in template.columns:  # same dtypes as the 2010+ file
        df[c] = df[c].astype(template[c].dtype)
    return df[template.columns]


def open_to_open_returns(p: pd.DataFrame) -> pd.Series:
    """Same definition as the 2010+ file: (C_t/O_t) * (1 + ret_{t+1}) / (C_{t+1}/O_{t+1}) - 1, per permno."""
    intraday = p["close"].astype(float) / p["open"].astype(float)
    g = p.groupby("permno", sort=False)
    out = (
        intraday
        * (1.0 + g["ret"].shift(-1).astype(float))
        / intraday.groupby(p["permno"]).shift(-1)
        - 1.0
    )
    out[~np.isfinite(out)] = np.nan
    return out


def check_stitch(hist_full: pd.DataFrame, new: pd.DataFrame) -> None:
    """Overlap rows (2010-01) must have identical ret; 2009-12-31 -> 2010-01-04 must have no gap."""
    ov = hist_full[hist_full["session"] > END].merge(
        new[new["session"] <= OVERLAP_END], on=["permno", "session"], suffixes=("_h", "_n")
    )
    diff = (ov["ret_h"].astype(float) - ov["ret_n"].astype(float)).abs().max()
    print(f"stitch: {len(ov)} overlapping rows, max |ret diff| = {diff:.2e}")
    if len(ov) == 0 or diff > 1e-9:
        raise SystemExit("stitch check failed: overlap rows missing or ret differs")
    last = hist_full[hist_full["session"] <= END].groupby("permno")["session"].max()
    first_new = new.groupby("permno")["session"].min()
    both = last.index.intersection(first_new.index)
    gap = last[both][last[both] < pd.Timestamp(END)]
    if not gap.empty:  # a permno that traded in 2010 should also trade on 2009-12-31
        live_2010 = first_new[both] == pd.Timestamp("2010-01-04")
        gap = gap[live_2010[gap.index]]
        if not gap.empty:
            raise SystemExit(f"stitch gap: permnos ending before {END}: {gap.to_dict()}")


def fetch_dgs3mo() -> pd.DataFrame:
    """FRED DGS3MO 1993..2009. available_at = end of the 2nd business day after the observation (ET).

    The 2010+ file uses ALFRED first-release dates (median lag ~2 days); this fixed lag is the same or more
    conservative for H.15 releases, and Treasury constant-maturity yields are not revised.
    """
    with urllib.request.urlopen(FRED_URL.format(START, END), timeout=60) as r:
        df = pd.read_csv(io.BytesIO(r.read()))
    df.columns = ["observation_date", "value"]
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).reset_index(drop=True)
    avail = (df["observation_date"] + pd.offsets.BDay(2)).dt.tz_localize("America/New_York")
    df["available_at"] = (avail + pd.Timedelta(hours=23, minutes=59, seconds=59)).dt.tz_convert(
        "UTC"
    )
    df["series_id"] = "DGS3MO"
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrds-username", required=not RAW_CACHE.exists())
    args = ap.parse_args()

    new = pd.read_parquet(RAW_DIR / PRICES_FILE)
    permnos = sorted(int(p) for p in new["permno"].unique())
    if RAW_CACHE.exists():  # a previous pull succeeded; no second WRDS login needed
        print(f"using cached raw pull {RAW_CACHE}")
        raw = pd.read_parquet(RAW_CACHE)
    else:
        print(f"pulling {len(permnos)} permnos {START} .. {OVERLAP_END} (approve the Duo push)")
        raw = fetch_crsp(args.wrds_username, permnos)
        RAW_CACHE.parent.mkdir(parents=True, exist_ok=True)
        raw.to_parquet(RAW_CACHE, index=False)
    hist_full = tidy(raw, new)
    check_stitch(hist_full, new)
    hist = hist_full[hist_full["session"] <= END].reset_index(drop=True)
    hist.to_parquet(RAW_DIR / HISTORY_FILE, index=False)
    starts = hist.groupby("permno")["session"].min().dt.date
    print(f"wrote {HISTORY_FILE}: {len(hist):,} rows, {hist['permno'].nunique()} permnos")
    print(starts.sort_values().to_string())

    rf = fetch_dgs3mo()
    rf.to_parquet(RAW_DIR / RF_HISTORY_FILE, index=False)
    print(f"wrote {RF_HISTORY_FILE}: {len(rf):,} rows")

    write_manifest(
        {
            HISTORY_FILE: f"WRDS `crsp.dsf_v2`, {START} → {END}, same permnos",
            RF_HISTORY_FILE: "FRED DGS3MO (fredgraph.csv), available_at = obs + 2 BDays EOD ET",
        }
    )


if __name__ == "__main__":
    main()
