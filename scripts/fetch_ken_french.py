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
URL25 = BASE + "25_Portfolios_BEME_OP_5x5_CSV.zip"
OUT25 = (
    "ff_25_bm_op_monthly.parquet"  # value-weighted returns, firm counts, average market cap (long)
)
BLOCKS25 = {"Average Value Weighted Returns -- Monthly": "ret", "Number of Firms in Portfolios": "n_firms",
            "Average Market Cap": "avg_cap"}  # fmt: skip
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


def fetch_25() -> pd.DataFrame:
    """5x5 book-to-market x operating-profitability portfolios (monthly, from 1963-07), long format:
    date, bm (1 = lowest/growth .. 5 = highest/value), op (1 = least .. 5 = most profitable), and the
    requested blocks (returns in decimal)."""
    lines = _csv_text(URL25)
    frames = []
    for title, field in BLOCKS25.items():
        start = next(i for i, ln in enumerate(lines) if ln.strip() == title) + 1
        cols = [c.strip() for c in lines[start].split(",")[1:]]
        rows = []
        for ln in lines[start + 1 :]:
            parts = [p.strip() for p in ln.split(",")]
            if len(parts) < 26 or not parts[0].isdigit():
                break
            rows.append(parts[:26])
        df = pd.DataFrame(rows, columns=["yyyymm", *cols])
        df["date"] = pd.to_datetime(df["yyyymm"], format="%Y%m") + pd.offsets.MonthEnd(0)
        long = df.drop(columns="yyyymm").melt(id_vars="date", var_name="cell", value_name=field)
        long[field] = long[field].astype(float)
        if (long[field] <= -99).any():
            raise SystemExit(f"missing values in {title}")
        if field == "ret":
            long[field] /= 100
        frames.append(long.set_index(["date", "cell"]))
    out = pd.concat(frames, axis=1).reset_index()
    order = list(dict.fromkeys(out["cell"]))  # file order: BM1 OP1..OP5, BM2 OP1.., ..
    pos = {c: i for i, c in enumerate(order)}
    out["bm"] = out["cell"].map(lambda c: pos[c] // 5 + 1)
    out["op"] = out["cell"].map(lambda c: pos[c] % 5 + 1)
    return out[out["date"] <= "2025-12-31"].sort_values(["date", "bm", "op"]).reset_index(drop=True)


URL_MOM10 = BASE + "10_Portfolios_Prior_12_2_CSV.zip"
OUT_MOM10 = "ff_10_momentum_monthly.parquet"
URL_MOM6 = BASE + "6_Portfolios_ME_Prior_12_2_CSV.zip"
OUT_MOM6 = "ff_6_size_momentum_monthly.parquet"


URL_VAR = BASE + "Portfolios_Formed_on_VAR_CSV.zip"
OUT_VAR = "ff_variance_monthly.parquet"  # sorted on 60-day return variance, re-formed monthly
URL_BETA = BASE + "Portfolios_Formed_on_BETA_CSV.zip"
OUT_BETA = "ff_beta_monthly.parquet"  # sorted on 60-month beta, re-formed each June


def fetch_blocks(url: str, blocks: dict[str, str]) -> pd.DataFrame:
    """Generic reader for Ken French monthly block files: {block title: field} -> long frame
    (date, cell, col_index (1-based, file order), fields...). Returns are converted to decimal."""
    lines = _csv_text(url)
    frames = []
    for title, field in blocks.items():
        start = next(i for i, ln in enumerate(lines) if ln.strip() == title) + 1
        cols = [c.strip() for c in lines[start].split(",")[1:]]
        rows = []
        for ln in lines[start + 1 :]:
            parts = [p.strip() for p in ln.split(",")]
            if len(parts) < len(cols) + 1 or not parts[0].isdigit() or len(parts[0]) != 6:
                break
            rows.append(parts[: len(cols) + 1])
        df = pd.DataFrame(rows, columns=["yyyymm", *cols])
        df["date"] = pd.to_datetime(df["yyyymm"], format="%Y%m") + pd.offsets.MonthEnd(0)
        long = df.drop(columns="yyyymm").melt(id_vars="date", var_name="cell", value_name=field)
        long[field] = long[field].astype(float)
        if (long[field] <= -99).any():
            raise SystemExit(f"missing values in {title}")
        if field == "ret":
            long[field] /= 100
        long["col"] = long["cell"].map({c: i + 1 for i, c in enumerate(cols)})
        frames.append(long.set_index(["date", "cell", "col"]))
    out = pd.concat(frames, axis=1).reset_index()
    return out[out["date"] <= "2025-12-31"].sort_values(["date", "col"]).reset_index(drop=True)


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
    mom10 = fetch_blocks(
        URL_MOM10,
        {
            "Value Weight Returns -- Monthly": "ret",
            "Number of Firms in Portfolios": "n_firms",
            "Average Firm Size": "avg_size",
        },
    )
    mom10.to_parquet(RAW_DIR / OUT_MOM10, index=False)
    mom6 = fetch_blocks(
        URL_MOM6,
        {
            "Average Value Weighted Returns -- Monthly": "ret",
            "Number of Firms in Portfolios": "n_firms",
            "Average Firm Size": "avg_size",
        },
    )
    mom6.to_parquet(RAW_DIR / OUT_MOM6, index=False)
    print(
        f"momentum: 10 deciles {mom10['date'].min():%Y-%m} → {mom10['date'].max():%Y-%m}; "
        f"6 size x momentum {mom6['date'].min():%Y-%m} → {mom6['date'].max():%Y-%m}"
    )
    for url, out_name in ((URL_VAR, OUT_VAR), (URL_BETA, OUT_BETA)):
        d = fetch_blocks(
            url,
            {
                "Value Weighted Returns -- Monthly": "ret",
                "Number of Firms in Portfolios": "n_firms",
            },
        )
        d.to_parquet(RAW_DIR / out_name, index=False)
        print(
            f"{out_name}: {d['date'].min():%Y-%m} → {d['date'].max():%Y-%m}, cells {d['cell'].nunique()}"
        )
    p25 = fetch_25()
    p25.to_parquet(RAW_DIR / OUT25, index=False)
    print(
        f"25 BM x OP portfolios: {p25['date'].nunique()} months {p25['date'].min():%Y-%m} → {p25['date'].max():%Y-%m}"
    )
    write_manifest({OUT_VAR: f"Ken French Data Library ({URL_VAR.rsplit('/', 1)[-1]}, value-weighted, monthly)",
                    OUT_BETA: f"Ken French Data Library ({URL_BETA.rsplit('/', 1)[-1]}, value-weighted, monthly)",
                    OUT_MOM10: f"Ken French Data Library ({URL_MOM10.rsplit('/', 1)[-1]}, value-weighted, monthly)",
                    OUT_MOM6: f"Ken French Data Library ({URL_MOM6.rsplit('/', 1)[-1]}, value-weighted, monthly)",
                    OUT25: f"Ken French Data Library ({URL25.rsplit('/', 1)[-1]}, value-weighted, monthly)",
                    OUT: f"Ken French Data Library ({URL.rsplit('/', 1)[-1]})",
                    OUT6: f"Ken French Data Library ({URL6.rsplit('/', 1)[-1]}, value-weighted)"})  # fmt: skip


if __name__ == "__main__":
    main()
