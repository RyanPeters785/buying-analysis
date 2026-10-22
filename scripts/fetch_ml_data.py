"""Pull the point-in-time stock universe and fundamentals for the ML stock-selection study (WRDS).

    uv run --python 3.11 --group wrds scripts/fetch_ml_data.py --wrds-username YOUR_USER

Saves to data/raw/ml/ (licensed; gitignored):
  crsp_msf.parquet        monthly returns / prices / shares, every common stock (+ SPY), 1990-2025
  crsp_names.parquet      name history with share-type / exchange / SIC filters (point-in-time)
  crsp_dvol.parquet       per stock-month from daily data (aggregated on the server): volatility,
                          max daily return, trading days
  ccm_link.parquet        CRSP-Compustat link history (LU/LC, primary)
  comp_funda.parquet      Compustat annual fundamentals 1985+ (INDL/STD/D/C)
Each table is saved as soon as it is pulled; rerunning skips tables already on disk (delete a file to
re-pull it). Column lists are checked against information_schema first, so a missing column is dropped
with a warning instead of failing after login.
"""

from __future__ import annotations

import argparse

import pandas as pd

from buying_analysis.data import RAW_DIR, write_manifest

OUT = RAW_DIR / "ml"
START, END = "1990-01-01", "2025-12-31"
FUNDA_START = "1985-01-01"
SPY = 84398

MSF_COLS = ["permno", "permco", "mthcaldt", "mthret", "mthretx", "mthprc", "shrout", "mthvol",
            "mthretmissflg", "mthdelflg"]  # fmt: skip
NAMES_COLS = ["permno", "permco", "ticker", "issuernm", "namedt", "nameenddt", "sharetype", "securitytype",
              "securitysubtype", "usincflg", "issuertype", "primaryexch", "conditionaltype", "tradingstatusflg",
              "siccd", "naics"]  # fmt: skip
LINK_COLS = ["gvkey", "lpermno", "lpermco", "linktype", "linkprim", "linkdt", "linkenddt"]
FUNDA_COLS = ["gvkey", "datadate", "fyear", "fyr", "sich", "naicsh", "ceq", "seq", "txditc", "pstk", "pstkrv",
              "pstkl", "at", "lt", "revt", "sale", "cogs", "xsga", "xint", "xrd", "ib", "ni", "oancf", "dp",
              "capx", "che", "dltt", "dlc", "act", "lct", "dvc", "csho", "prcc_f", "invt", "rect", "ppent",
              "emp"]  # fmt: skip


def available(db, schema: str, table: str, wanted: list[str]) -> list[str]:
    have = set(db.raw_sql(
        "select column_name from information_schema.columns where table_schema = %(s)s and table_name = %(t)s",
        params={"s": schema, "t": table})["column_name"])  # fmt: skip
    missing = [c for c in wanted if c not in have]
    if missing:
        print(f"  note: {schema}.{table} lacks {missing}; skipping those columns")
    return [c for c in wanted if c in have]


def save(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT / name, index=False)
    print(f"  saved {name}: {len(df):,} rows")


def pull_names(db) -> pd.DataFrame:
    cols = available(db, "crsp", "stocknames_v2", NAMES_COLS)
    sql = f"select {', '.join(cols)} from crsp.stocknames_v2 where nameenddt >= %(s)s"
    return db.raw_sql(sql, params={"s": START}, date_cols=["namedt", "nameenddt"])


def common_permnos(names: pd.DataFrame) -> list[int]:
    """Any permno that was ever a US-incorporated common stock (filters are re-applied point-in-time later)."""
    m = (names["sharetype"].eq("NS") & names["securitytype"].eq("EQTY") & names["securitysubtype"].eq("COM")
         & names["usincflg"].eq("Y") & names["issuertype"].isin(["ACOR", "CORP"]))  # fmt: skip
    return sorted({int(p) for p in names.loc[m, "permno"]} | {SPY})


def pull_msf(db, permnos: list[int]) -> pd.DataFrame:
    cols = available(db, "crsp", "msf_v2", MSF_COLS)
    frames = []
    for y in range(int(START[:4]), int(END[:4]) + 1):
        sql = (f"select {', '.join(cols)} from crsp.msf_v2 where permno in %(p)s "
               "and mthcaldt between %(a)s and %(b)s")  # fmt: skip
        frames.append(db.raw_sql(sql, params={"p": tuple(permnos), "a": f"{y}-01-01", "b": f"{y}-12-31"},
                                 date_cols=["mthcaldt"]))  # fmt: skip
        print(f"  msf {y}: {len(frames[-1]):,}", flush=True)
    return pd.concat(frames, ignore_index=True)


def pull_dvol(db, permnos: list[int]) -> pd.DataFrame:
    frames = []
    for y in range(int(START[:4]), int(END[:4]) + 1):
        sql = ("select permno, date_trunc('month', dlycaldt)::date as month, stddev_samp(dlyret) as dvol, "
               "max(dlyret) as maxret, count(dlyret) as ndays from crsp.dsf_v2 where permno in %(p)s "
               "and dlycaldt between %(a)s and %(b)s group by 1, 2")  # fmt: skip
        frames.append(db.raw_sql(sql, params={"p": tuple(permnos), "a": f"{y}-01-01", "b": f"{y}-12-31"},
                                 date_cols=["month"]))  # fmt: skip
        print(f"  daily-agg {y}: {len(frames[-1]):,}", flush=True)
    return pd.concat(frames, ignore_index=True)


def pull_link(db) -> pd.DataFrame:
    cols = available(db, "crsp", "ccmxpf_lnkhist", LINK_COLS)
    sql = (f"select {', '.join(cols)} from crsp.ccmxpf_lnkhist where linktype in ('LU', 'LC') "
           "and linkprim in ('P', 'C') and lpermno is not null")  # fmt: skip
    return db.raw_sql(sql, date_cols=["linkdt", "linkenddt"])


def pull_funda(db) -> pd.DataFrame:
    cols = available(db, "comp", "funda", FUNDA_COLS)
    sql = (f"select {', '.join(cols)} from comp.funda where indfmt = 'INDL' and datafmt = 'STD' "
           "and popsrc = 'D' and consol = 'C' and datadate >= %(s)s")  # fmt: skip
    return db.raw_sql(sql, params={"s": FUNDA_START}, date_cols=["datadate"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrds-username", required=True)
    args = ap.parse_args()
    import wrds

    todo = {
        n: not (OUT / n).exists()
        for n in [
            "crsp_names.parquet",
            "crsp_msf.parquet",
            "crsp_dvol.parquet",
            "ccm_link.parquet",
            "comp_funda.parquet",
        ]
    }
    if not any(todo.values()):
        print("all tables already on disk; delete a file to re-pull it")
        return
    print("connecting (approve the Duo push)...", flush=True)
    db = wrds.Connection(wrds_username=args.wrds_username)
    try:
        if todo["crsp_names.parquet"]:
            print("names...", flush=True)
            save(pull_names(db), "crsp_names.parquet")
        permnos = common_permnos(pd.read_parquet(OUT / "crsp_names.parquet"))
        print(f"{len(permnos):,} permnos that were ever US common stocks (+ SPY)")
        if todo["crsp_msf.parquet"]:
            print("monthly stock file...", flush=True)
            save(pull_msf(db, permnos), "crsp_msf.parquet")
        if todo["crsp_dvol.parquet"]:
            print("daily volatility (server-side aggregation)...", flush=True)
            save(pull_dvol(db, permnos), "crsp_dvol.parquet")
        if todo["ccm_link.parquet"]:
            print("link table...", flush=True)
            save(pull_link(db), "ccm_link.parquet")
        if todo["comp_funda.parquet"]:
            print("compustat annual...", flush=True)
            save(pull_funda(db), "comp_funda.parquet")
    finally:
        db.close()
    write_manifest(
        {f"ml/{n}": f"WRDS ({n.split('.')[0]}), pulled by scripts/fetch_ml_data.py" for n in todo}
    )
    print("done")


if __name__ == "__main__":
    main()
