"""Download the Ken French daily US market factors (1926+) for long-history robustness checks.

Saves data/raw/ff_factors_daily.parquet with columns date, mkt (total return, decimal), rf (daily, decimal).
Market-level only: there are no opens, so strategies on this series trade at the next day's close.
"""

import io
import urllib.request
import zipfile

import pandas as pd

from buying_analysis.data import RAW_DIR, write_manifest

URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
OUT = "ff_factors_daily.parquet"


def main() -> None:
    with urllib.request.urlopen(URL, timeout=120) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    text = z.read(z.namelist()[0]).decode("latin-1")
    lines = text.splitlines()
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
    write_manifest({OUT: f"Ken French Data Library ({URL.rsplit('/', 1)[-1]})"})


if __name__ == "__main__":
    main()
