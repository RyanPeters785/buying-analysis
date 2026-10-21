"""Download Robert Shiller's monthly S&P data (1871+): price (monthly average), dividends, earnings, CPI.

Saves data/raw/shiller_monthly.parquet. Used only for the CAPE valuation signal; returns come from CRSP /
Ken French. The Yale-hosted file was last updated September 2023.
"""

import io
import urllib.request

import pandas as pd

from buying_analysis.data import RAW_DIR, write_manifest

URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
OUT = "shiller_monthly.parquet"


def main() -> None:
    with urllib.request.urlopen(URL, timeout=120) as r:
        raw = pd.read_excel(io.BytesIO(r.read()), sheet_name="Data", header=None, skiprows=8)
    df = raw.iloc[:, :5].copy()
    df.columns = ["yyyymm", "P", "D", "E", "CPI"]
    df = df[pd.to_numeric(df["yyyymm"], errors="coerce").notna()]
    ym = df["yyyymm"].astype(float).map(lambda v: f"{int(v)}-{round((v - int(v)) * 100):02d}")
    df["date"] = pd.to_datetime(ym, format="%Y-%m") + pd.offsets.MonthEnd(0)
    for c in ("P", "D", "E", "CPI"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[["date", "P", "D", "E", "CPI"]].reset_index(drop=True)
    df.to_parquet(RAW_DIR / OUT, index=False)
    print(f"{len(df):,} months {df['date'].min():%Y-%m} → {df['date'].max():%Y-%m}; "
          f"earnings through {df.dropna(subset=['E'])['date'].max():%Y-%m}")  # fmt: skip
    write_manifest({OUT: "Shiller ie_data.xls (econ.yale.edu, last updated 2023-09)"})


if __name__ == "__main__":
    main()
