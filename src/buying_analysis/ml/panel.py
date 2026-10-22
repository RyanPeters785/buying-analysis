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
EXTRA_FEATURES = ["chmom", "dolvol", "ill", "std_turn", "chcsho", "betasq", "idiovol", "age", "rd_mve", "sgr",
                  "cash", "currat", "egr", "roe", "invest"]  # fmt: skip
GKX_FEATURES = (
    FEATURES + EXTRA_FEATURES + ["indmom"]
)  # indmom is added cross-sectionally (see add_indmom)


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
    exch = pd.Series(m["primaryexch"].to_numpy(), index=m["index"]).sort_index()
    return out, sic, exch


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
    g = f.groupby("gvkey")
    f["at_lag"] = g["at"].shift(1)
    f["sale_lag"] = g["sale"].shift(1)
    f["be_lag"] = g["be"].shift(1)
    f["ppinv"] = f["ppent"].fillna(0) + f["invt"].fillna(0)
    f["ppinv_lag"] = g["ppinv"].shift(1)
    lk = link.dropna(subset=["lpermno"]).copy()
    lk["linkenddt"] = lk["linkenddt"].fillna(pd.Timestamp("2100-01-01"))
    lk["permno"] = lk["lpermno"].astype("int64")
    m = f.merge(lk[["gvkey", "permno", "linkdt", "linkenddt", "linkprim"]], on="gvkey")
    m = m[(m["avail"] >= m["linkdt"]) & (m["avail"] <= m["linkenddt"])]
    m = m.sort_values(
        ["permno", "avail", "linkprim", "datadate"]
    )  # 'C' sorts before 'P': keep P last
    return m.drop_duplicates(["permno", "avail"], keep="last")


def build(top_n: int | None = 1000, min_price: float = 5.0, extra: bool = False) -> pd.DataFrame:
    """Panel rows for the universe at each month-end. ``top_n=None`` keeps every eligible common stock;
    ``extra=True`` adds the GKX-style characteristics (EXTRA_FEATURES) and NYSE size buckets."""
    msf = pd.read_parquet(ML_DIR / "crsp_msf.parquet")
    names = pd.read_parquet(ML_DIR / "crsp_names.parquet")
    dvol = pd.read_parquet(ML_DIR / "crsp_dvol.parquet")
    funda = pd.read_parquet(ML_DIR / "comp_funda.parquet")
    link = pd.read_parquet(ML_DIR / "ccm_link.parquet")

    msf["mthcaldt"] = month_end(msf["mthcaldt"])
    msf = msf.drop_duplicates(["permno", "mthcaldt"], keep="last").reset_index(drop=True)
    common, sic, exch = common_stock_mask(msf, names)
    msf["common"], msf["sic"] = common, sic
    msf["nyse"] = (exch == "N").astype(float)
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
    if extra:
        feats |= extra_features(
            ret, retx, mcap, prc, vol, shr, mkt, feats, fwide, fm, me, be_pos, at
        )
    fwd1 = nxt[0].copy()
    fwd3 = (1 + nxt[0]) * (1 + nxt[1]) * (1 + nxt[2]) - 1
    fwd1.iloc[-1:] = np.nan
    fwd3.iloc[-3:] = np.nan

    # universe at t
    eligible = (wide("common").reindex_like(ret) > 0) & ret.notna() & (prc.reindex_like(ret) >= min_price) \
        & mcap.notna()  # fmt: skip
    if top_n is None:
        in_univ = eligible
    else:
        in_univ = mcap.where(eligible).rank(axis=1, ascending=False) <= top_n

    long = in_univ.stack()
    long = long[long].index.to_frame(index=False)
    long.columns = ["date", "permno"]
    cols = {"mcap": mcap, "ret": ret, "ret_fwd1": fwd1, "ret_fwd3": fwd3, **feats}
    if extra:  # NYSE breakpoints of market cap at t (eligible NYSE stocks only)
        nyse_cap = mcap.where(eligible & (wide("nyse").reindex_like(ret) > 0))
        bps = {q: nyse_cap.quantile(q, axis=1) for q in (0.2, 0.5, 0.8)}
        bucket = 1 + (mcap.ge(bps[0.2], axis=0)).astype(float) + (mcap.ge(bps[0.5], axis=0)).astype(float) \
            + (mcap.ge(bps[0.8], axis=0)).astype(float)  # fmt: skip
        cols["size_bucket"] = bucket.where(
            mcap.notna()
        )  # 1 micro (<20th), 2 small, 3 mid, 4 large (>80th)
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


def extra_features(ret, retx, mcap, prc, vol, shr, mkt, feats, fwide, fm, me, be_pos, at) -> dict:
    """GKX-style characteristics beyond the base set; all use data through t (fundamentals lagged)."""
    lr = np.log1p(ret)
    prior = np.expm1(lr.shift(7).rolling(6, min_periods=6).sum())  # t-12 .. t-7
    dollar = vol.reindex_like(ret) * prc.reindex_like(ret)
    turn = vol.reindex_like(ret) / shr
    resid_var = (
        ret.rolling(36, min_periods=24).var()
        - feats["beta_36"] ** 2 * mkt.rolling(36, min_periods=24).var().values[:, None]
    )
    return {
        "chmom": feats["mom_6_1"] - prior,
        "dolvol": np.log(dollar.where(dollar > 0)),
        "ill": (ret.abs() / dollar.where(dollar > 0)).rolling(3, min_periods=2).mean(),
        "std_turn": turn.rolling(12, min_periods=6).std(),
        "chcsho": shr / shr.shift(12) - 1,
        "betasq": feats["beta_36"] ** 2,
        "idiovol": np.sqrt(resid_var.clip(lower=0)),
        "age": ret.notna().cumsum().where(ret.notna()),
        "rd_mve": fwide(fm["xrd"].fillna(0)) / me,
        "sgr": fwide(fm["sale"] / fm["sale_lag"] - 1),
        "cash": fwide(fm["che"]) / at.where(at > 0),
        "currat": fwide(fm["act"] / fm["lct"].where(fm["lct"] > 0)),
        "egr": fwide(fm["be"] / fm["be_lag"].where(fm["be_lag"] > 0) - 1),
        "roe": fwide(fm["ib"]) / be_pos,
        "invest": fwide((fm["ppinv"] - fm["ppinv_lag"]) / fm["at_lag"].where(fm["at_lag"] > 0)),
    }  # fmt: skip


def add_indmom(panel: pd.DataFrame) -> pd.DataFrame:
    """Industry momentum: average 12-1 momentum of the stock's sector that month (cross-sectional, at t)."""
    panel = panel.copy()
    panel["indmom"] = panel.groupby(["date", "sector"])["mom_12_1"].transform("mean")
    return panel
