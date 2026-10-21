"""Download the Ken French daily US market factors (1926+) for long-history robustness checks.

Saves data/raw/ff_factors_daily.parquet with columns date, mkt (total return, decimal), rf (daily, decimal).
Market-level only: there are no opens, so strategies on this series trade at the next day's close.
"""

import io
import urllib.request
import zipfile

import pandas as pd

from buying_analysis.data import RAW_DIR, write_manifest

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
URL = BASE + "F-F_Research_Data_Factors_daily_CSV.zip"
OUT = "ff_factors_daily.parquet"
URL6 = BASE + "6_Portfolios_2x3_daily_CSV.zip"
OUT6 = "ff_6_portfolios_daily.parquet"  # value-weighted size x book-to-market portfolios
PORTFOLIOS = ["small_growth", "small_blend", "small_value", "big_growth", "big_blend", "big_value"]


def _csv_text(url: str) -> list[str]:
    with urllib.request.urlopen(url, timeout=120) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    return z.read(z.namelist()[0]).decode("latin-1").splitlines()


def fetch_six() -> pd.DataFrame:
    """First block of the file: average value-weighted daily returns (decimal)."""
    lines = _csv_text(URL6)
    start = next(i for i, ln in enumerate(lines) if "Value Weighted Returns" in ln) + 2
    rows = []
    for ln in lines[start:]:
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 7 or not parts[0].isdigit():
            break
        rows.append(parts[:7])
    df = pd.DataFrame(rows, columns=["date", *PORTFOLIOS])
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    for c in PORTFOLIOS:
        df[c] = df[c].astype(float)
        if (df[c] <= -99).any():
            raise SystemExit(f"missing values in {c}")
        df[c] /= 100
    return df[df["date"] <= "2025-12-31"]


def main() -> None:
    lines = _csv_text(URL)
    start = next(i for i, ln in enumerate(lines) if ln.strip().startswith(",Mkt-RF"))
    rows = []
    for ln in lines[start + 1 :]:
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 5 or not parts[0].isdigit() or len(parts[0]) != 8:
            break
        rows.append(parts[:5])
    df = pd.DataFrame(rows, columns=["date", "mkt_rf", "smb", "hml", "rf"])
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    for c in ("mkt_rf", "rf"):
        df[c] = df[c].astype(float) / 100
    df["mkt"] = df["mkt_rf"] + df["rf"]
    df = df[df["date"] <= "2025-12-31"][["date", "mkt", "rf"]]
    df.to_parquet(RAW_DIR / OUT, index=False)
    print(f"{len(df):,} days {df['date'].min():%Y-%m-%d} → {df['date'].max():%Y-%m-%d}")
    six = fetch_six()
    six.to_parquet(RAW_DIR / OUT6, index=False)
    print(
        f"6 portfolios: {len(six):,} days {six['date'].min():%Y-%m-%d} → {six['date'].max():%Y-%m-%d}"
    )
    write_manifest({OUT: f"Ken French Data Library ({URL.rsplit('/', 1)[-1]})",
                    OUT6: f"Ken French Data Library ({URL6.rsplit('/', 1)[-1]}, value-weighted)"})  # fmt: skip


if __name__ == "__main__":
    main()
