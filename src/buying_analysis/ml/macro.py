"""Monthly macro predictors in the spirit of Welch & Goyal (2008), as used by Gu, Kelly & Xiu (2020).

Built from data already on disk plus Treasury yields from yfinance (^IRX, ^TNX; FRED blocks scripted access
here). Every value at month-end t uses information available at t:
  dp    aggregate dividends over the last 12 months / total market cap (CRSP, all common stocks)
  ep    aggregate earnings (Compustat ib, 6-month lag) / total market cap of firms with earnings data
  bm    aggregate book equity (6-month lag) / total market cap of firms with book data
  ntis  12-month net equity issuance / total market cap (CRSP: cap change not explained by price return)
  svar  sum of squared daily market returns in the month (Ken French)
  tbl   3-month T-bill yield (monthly average of ^IRX, decimal)
  tms   term spread: 10-year Treasury yield (^TNX) minus tbl
The Welch-Goyal default spread (BAA - AAA) is omitted: it is not available without FRED.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.data import DATA_DIR, RAW_DIR
from buying_analysis.ml.panel import ML_DIR, SPY, month_end

MACRO = DATA_DIR / "derived" / "ml_macro.parquet"
MACRO_FEATURES = ["dp", "ep", "bm", "ntis", "svar", "tbl", "tms"]


def yields() -> pd.DataFrame:
    import yfinance as yf

    out = {}
    for name, tk in (("tbl", "^IRX"), ("tnx", "^TNX")):
        h = yf.Ticker(tk).history(start="1985-01-01", end="2026-01-01")["Close"]
        h.index = h.index.tz_localize(None)
        out[name] = h.resample("ME").mean() / 100
    return pd.DataFrame(out)


def build_macro(panel: pd.DataFrame) -> pd.DataFrame:
    msf = pd.read_parquet(ML_DIR / "crsp_msf.parquet")
    msf = msf[msf["permno"] != SPY].assign(date=lambda d: month_end(d["mthcaldt"]))
    msf = msf.drop_duplicates(["permno", "date"], keep="last").sort_values(["permno", "date"])
    msf["mcap"] = msf["mthprc"].astype(float).abs() * msf["shrout"].astype(float)
    msf["mcap_lag"] = msf.groupby("permno")["mcap"].shift(1)
    msf["div"] = (msf["mthret"].astype(float) - msf["mthretx"].astype(float)) * msf["mcap_lag"]
    msf["issue"] = msf["mcap"] - msf["mcap_lag"] * (1 + msf["mthretx"].astype(float))
    agg = msf.groupby("date")[["mcap", "div", "issue"]].sum()
    out = pd.DataFrame(index=agg.index)
    out["dp"] = agg["div"].rolling(12, min_periods=12).sum() / agg["mcap"]
    out["ntis"] = agg["issue"].rolling(12, min_periods=12).sum() / agg["mcap"]

    p = panel.assign(me=panel["mcap"] / 1000.0)
    for col in ("ep", "bm"):
        ok = p[col].notna()
        num = (p.loc[ok, col] * p.loc[ok, "me"]).groupby(p.loc[ok, "date"]).sum()
        den = p.loc[ok, "me"].groupby(p.loc[ok, "date"]).sum()
        out[col] = num / den

    kf = pd.read_parquet(RAW_DIR / "ff_factors_daily.parquet").set_index("date")
    out["svar"] = (kf["mkt"] ** 2).resample("ME").sum()
    y = yields()
    out["tbl"] = y["tbl"]
    out["tms"] = y["tnx"] - y["tbl"]
    return out[MACRO_FEATURES].replace([np.inf, -np.inf], np.nan)
