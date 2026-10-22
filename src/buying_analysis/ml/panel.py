"""Point-in-time monthly panel for ML stock selection (CRSP + Compustat, from data/raw/ml/).

At each month-end t:
  universe   US common stock per the CRSP name record valid at t (sharetype NS, EQTY/COM, US-incorporated,
             ACOR/CORP, NYSE/AMEX/Nasdaq), |price| >= $5, valid return at t, and among the largest
             ``top_n`` by market cap at t
  features   use returns / prices / volume through t, daily-volatility aggregates through t, and annual
             fundamentals only from 6 months after the fiscal year-end (stale after 18 months)
  targets    ret_fwd1 = return of t+1, ret_fwd3 = compounded t+1..t+3 (delisting returns included; months
             after a delisting count as 0, i.e. cash)
Wide (month x permno) matrices keep rolling windows aligned even when a stock has missing months.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.data import DATA_DIR, RAW_DIR

ML_DIR = RAW_DIR / "ml"
PANEL = DATA_DIR / "derived" / "ml_panel.parquet"
SPY = 84398
FUND_LAG_MONTHS = 6
FUND_STALE_MONTHS = 18
SIC_GROUPS = [(100, 999, "agri"), (1000, 1499, "mining"), (1500, 1799, "construction"), (2000, 3999, "manufacturing"),
              (4000, 4899, "transport"), (4900, 4999, "utilities"), (5000, 5999, "trade"),
              (6000, 6999, "finance"), (7000, 8999, "services"), (9000, 9999, "public")]  # fmt: skip
PRICE_FEATURES = ["mom_12_1", "mom_6_1", "mom_3_1", "rev_1", "ltrev_36_12", "vol_d1", "vol_d3", "maxret_1",
                  "vol_m12", "beta_36", "size", "turnover", "dist_52w_high", "ma10_gap"]  # fmt: skip
FUND_FEATURES = ["bm", "ep", "sp", "cfp", "dy", "op", "roa", "gp_at", "asset_growth", "accruals", "leverage",
                 "rd_sale"]  # fmt: skip
FEATURES = PRICE_FEATURES + FUND_FEATURES


def month_end(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s) + pd.offsets.MonthEnd(0)


def common_stock_mask(msf: pd.DataFrame, names: pd.DataFrame) -> pd.Series:
    """True where the name record valid at the row's month-end marks a US common stock on NYSE/AMEX/Nasdaq."""
    n = names.dropna(subset=["namedt"]).sort_values("namedt")
    left = msf[["permno", "mthcaldt"]].reset_index().sort_values("mthcaldt")
    m = pd.merge_asof(
        left, n, left_on="mthcaldt", right_on="namedt", by="permno", direction="backward"
    )
    ok = (m["mthcaldt"] <= m["nameenddt"]) & m["sharetype"].eq("NS") & m["securitytype"].eq("EQTY") \
        & m["securitysubtype"].eq("COM") & m["usincflg"].eq("Y") & m["issuertype"].isin(["ACOR", "CORP"]) \
        & m["primaryexch"].isin(["N", "A", "Q"])  # fmt: skip
    out = pd.Series(ok.fillna(False).to_numpy(bool), index=m["index"]).sort_index()
    sic = pd.Series(m["siccd"].to_numpy(), index=m["index"]).sort_index()
    return out, sic


def sic_group(sic: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=sic.index, dtype="object")
    for lo, hi, name in SIC_GROUPS:
        out[(sic >= lo) & (sic <= hi)] = name
    return out


def fundamentals_by_permno(funda: pd.DataFrame, link: pd.DataFrame) -> pd.DataFrame:
    """Annual rows mapped to the permno linked at their availability date (datadate + 6 months, month-end)."""
    f = funda.copy()
    f["avail"] = month_end(f["datadate"]) + pd.offsets.MonthEnd(FUND_LAG_MONTHS)
    se = f["seq"].fillna(f["ceq"] + f["pstk"]).fillna(f["at"] - f["lt"])
    ps = f["pstkrv"].fillna(f["pstkl"]).fillna(f["pstk"]).fillna(0)
    f["be"] = se - ps + f["txditc"].fillna(0)
    f = f.sort_values(["gvkey", "datadate"])
    f["at_lag"] = f.groupby("gvkey")["at"].shift(1)
    lk = link.dropna(subset=["lpermno"]).copy()
    lk["linkenddt"] = lk["linkenddt"].fillna(pd.Timestamp("2100-01-01"))
    lk["permno"] = lk["lpermno"].astype("int64")
    m = f.merge(lk[["gvkey", "permno", "linkdt", "linkenddt", "linkprim"]], on="gvkey")
    m = m[(m["avail"] >= m["linkdt"]) & (m["avail"] <= m["linkenddt"])]
    m = m.sort_values(
        ["permno", "avail", "linkprim", "datadate"]
    )  # 'C' sorts before 'P': keep P last
    return m.drop_duplicates(["permno", "avail"], keep="last")


def build(top_n: int = 1000, min_price: float = 5.0) -> pd.DataFrame:
    msf = pd.read_parquet(ML_DIR / "crsp_msf.parquet")
    names = pd.read_parquet(ML_DIR / "crsp_names.parquet")
    dvol = pd.read_parquet(ML_DIR / "crsp_dvol.parquet")
    funda = pd.read_parquet(ML_DIR / "comp_funda.parquet")
    link = pd.read_parquet(ML_DIR / "ccm_link.parquet")

    msf["mthcaldt"] = month_end(msf["mthcaldt"])
    msf = msf.drop_duplicates(["permno", "mthcaldt"], keep="last").reset_index(drop=True)
    common, sic = common_stock_mask(msf, names)
    msf["common"], msf["sic"] = common, sic
    msf["prc"] = msf["mthprc"].astype(float).abs()
    msf["mcap"] = msf["prc"] * msf["shrout"].astype(float)  # $ thousands

    def wide(col, df=msf, idx="mthcaldt"):
        return df.pivot(index=idx, columns="permno", values=col).astype(float).sort_index()

    ret, retx, mcap, prc = wide("mthret"), wide("mthretx"), wide("mcap"), wide("prc")
    vol = wide("mthvol").reindex_like(ret)
    shr = wide("shrout").reindex_like(ret)
    months = ret.index
    dv = dvol.assign(month=month_end(dvol["month"]))
    dvw = {c: dv.pivot(index="month", columns="permno", values=c).astype(float).reindex(index=months,
           columns=ret.columns) for c in ("dvol", "maxret", "ndays")}  # fmt: skip

    lr = np.log1p(ret)

    def window(k_from: int, k_to: int):
        """Compounded return from month t-k_from .. t-k_to (inclusive), NaN if any month missing."""
        s = lr.shift(k_to).rolling(k_from - k_to + 1, min_periods=k_from - k_to + 1).sum()
        return np.expm1(s)

    feats = {
        "mom_12_1": window(11, 1), "mom_6_1": window(5, 1), "mom_3_1": window(2, 1), "rev_1": ret,
        "ltrev_36_12": window(35, 12),
        "vol_d1": dvw["dvol"].where(dvw["ndays"] >= 10), "vol_d3": dvw["dvol"].rolling(3, min_periods=2).mean(),
        "maxret_1": dvw["maxret"], "vol_m12": ret.rolling(12, min_periods=10).std(),
        "size": np.log(mcap), "turnover": (vol / shr).rolling(3, min_periods=2).mean(),
    }  # fmt: skip
    mkt = ret[SPY] if SPY in ret else ret.mean(axis=1)
    cov = ret.rolling(36, min_periods=24).cov(mkt)
    feats["beta_36"] = cov.div(mkt.rolling(36, min_periods=24).var(), axis=0)
    pidx = (1 + retx.fillna(0)).cumprod().where(retx.notna() | ret.notna())
    feats["dist_52w_high"] = pidx / pidx.rolling(12, min_periods=10).max() - 1
    feats["ma10_gap"] = pidx / pidx.rolling(10, min_periods=8).mean() - 1

    fm = fundamentals_by_permno(funda, link)
    fm = fm[fm["permno"].isin(ret.columns)]

    def fwide(expr: pd.Series) -> pd.DataFrame:
        w = (
            fm.assign(v=expr.loc[fm.index])
            .pivot(index="avail", columns="permno", values="v")
            .astype(float)
        )
        return w.reindex(index=months.union(w.index)).sort_index().ffill(limit=FUND_STALE_MONTHS - FUND_LAG_MONTHS) \
            .reindex(index=months, columns=ret.columns)  # fmt: skip

    me = mcap / 1000.0  # $ millions, as Compustat
    be, at = fwide(fm["be"]), fwide(fm["at"])
    be_pos = be.where(be > 0)
    feats |= {
        "bm": be_pos / me, "ep": fwide(fm["ib"]) / me, "sp": fwide(fm["sale"]) / me, "cfp": fwide(fm["oancf"]) / me,
        "dy": fwide(fm["dvc"]) / me,
        "op": fwide(fm["revt"] - fm["cogs"].fillna(0) - fm["xsga"].fillna(0) - fm["xint"].fillna(0)) / be_pos,
        "roa": fwide(fm["ib"]) / at.where(at > 0), "gp_at": fwide(fm["revt"] - fm["cogs"]) / at.where(at > 0),
        "asset_growth": fwide(fm["at"] / fm["at_lag"] - 1),
        "accruals": fwide((fm["ib"] - fm["oancf"]) / fm["at"]),
        "leverage": fwide((fm["dltt"].fillna(0) + fm["dlc"].fillna(0)) / fm["at"]),
        "rd_sale": fwide(fm["xrd"].fillna(0) / fm["sale"].where(fm["sale"] > 0)),
    }  # fmt: skip

    # targets: missing future months (delisted with no further rows, or data gaps) count as 0 = cash, so a
    # stock never silently drops out of a portfolio; only the last months of the sample are unknown (NaN)
    nxt = [ret.shift(-k).fillna(0.0) for k in (1, 2, 3)]
    fwd1 = nxt[0].copy()
    fwd3 = (1 + nxt[0]) * (1 + nxt[1]) * (1 + nxt[2]) - 1
    fwd1.iloc[-1:] = np.nan
    fwd3.iloc[-3:] = np.nan

    # universe at t
    eligible = (wide("common").reindex_like(ret) > 0) & ret.notna() & (prc.reindex_like(ret) >= min_price) \
        & mcap.notna()  # fmt: skip
    rank = mcap.where(eligible).rank(axis=1, ascending=False)
    in_univ = rank <= top_n

    long = in_univ.stack()
    long = long[long].index.to_frame(index=False)
    long.columns = ["date", "permno"]
    cols = {"mcap": mcap, "ret": ret, "ret_fwd1": fwd1, "ret_fwd3": fwd3, **feats}
    for name, w in cols.items():
        long[name] = (
            w.stack(future_stack=True)
            .reindex(pd.MultiIndex.from_frame(long[["date", "permno"]]))
            .to_numpy()
        )
    sic_w = msf.pivot(index="mthcaldt", columns="permno", values="sic").reindex_like(ret)
    long["sector"] = sic_group(pd.Series(sic_w.stack(future_stack=True).reindex(
        pd.MultiIndex.from_frame(long[["date", "permno"]])).to_numpy(), index=long.index)).to_numpy()  # fmt: skip
    return long.sort_values(["date", "permno"]).reset_index(drop=True)


def spy_monthly() -> pd.DataFrame:
    msf = pd.read_parquet(ML_DIR / "crsp_msf.parquet")
    s = msf[msf["permno"] == SPY].assign(date=lambda d: month_end(d["mthcaldt"]))
    return s.set_index("date")[["mthret"]].astype(float).rename(columns={"mthret": "spy"})
