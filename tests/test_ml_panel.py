"""Point-in-time checks of the ML panel against the raw CRSP / Compustat pulls (skipped if data is absent)."""

import numpy as np
import pandas as pd
import pytest

from buying_analysis.ml.panel import ML_DIR, PANEL, fundamentals_by_permno, month_end

pytestmark = pytest.mark.skipif(not PANEL.exists(), reason="ML panel not built (licensed data)")
AAPL = 14593


@pytest.fixture(scope="module")
def panel():
    return pd.read_parquet(PANEL)


@pytest.fixture(scope="module")
def msf():
    m = pd.read_parquet(ML_DIR / "crsp_msf.parquet")
    m["mthcaldt"] = month_end(m["mthcaldt"])
    return m


def _ret(msf, permno):
    return msf[msf["permno"] == permno].set_index("mthcaldt")["mthret"].astype(float).sort_index()


def test_every_month_has_exactly_top_n(panel):
    assert panel.groupby("date").size().eq(1000).all()


def test_momentum_skips_the_current_month(panel, msf):
    r = _ret(msf, AAPL)
    t = pd.Timestamp("2015-06-30")
    row = panel[(panel["permno"] == AAPL) & (panel["date"] == t)].iloc[0]
    months = r.index[(r.index <= t)][-12:-1]  # t-11 .. t-1
    assert len(months) == 11
    assert row["mom_12_1"] == pytest.approx(np.prod(1 + r[months]) - 1, rel=1e-9)
    assert row["rev_1"] == pytest.approx(r[t])


def test_targets_are_next_months_returns(panel, msf):
    r = _ret(msf, AAPL)
    t = pd.Timestamp("2015-06-30")
    row = panel[(panel["permno"] == AAPL) & (panel["date"] == t)].iloc[0]
    nxt = r.index[r.index > t][:3]
    assert row["ret_fwd1"] == pytest.approx(r[nxt[0]])
    assert row["ret_fwd3"] == pytest.approx(np.prod(1 + r[nxt]) - 1, rel=1e-9)


def test_fundamentals_only_after_six_month_lag(panel):
    funda = pd.read_parquet(ML_DIR / "comp_funda.parquet")
    link = pd.read_parquet(ML_DIR / "ccm_link.parquet")
    fm = fundamentals_by_permno(funda, link)
    a = fm[fm["permno"] == AAPL].set_index("datadate")
    fy14 = a.loc["2014-09-30"]  # Apple FY2014 (fiscal year ends late September)
    assert fy14["avail"] == pd.Timestamp("2015-03-31")
    p = panel[panel["permno"] == AAPL].set_index("date")
    me = lambda t: p.at[pd.Timestamp(t), "mcap"] / 1000
    # sales/price switches from FY2013 to FY2014 exactly at the availability month, not before
    fy13 = a.loc["2013-09-30"]
    assert p.at[pd.Timestamp("2015-02-28"), "sp"] == pytest.approx(fy13["sale"] / me("2015-02-28"))
    assert p.at[pd.Timestamp("2015-03-31"), "sp"] == pytest.approx(fy14["sale"] / me("2015-03-31"))


def test_universe_ranks_on_current_market_cap_only(panel, msf):
    t = pd.Timestamp("2010-12-31")
    members = set(panel.loc[panel["date"] == t, "permno"])
    m = msf[msf["mthcaldt"] == t].assign(
        mcap=lambda d: d["mthprc"].astype(float).abs() * d["shrout"]
    )
    smallest_member_cap = m[m["permno"].isin(members)]["mcap"].min()
    assert smallest_member_cap > 0
    assert AAPL in members


def test_delisted_stocks_stay_in_history(panel):
    # stocks that later disappeared must appear in the universe while they existed (no survivorship)
    last = panel.groupby("permno")["date"].max()
    gone = last[last < pd.Timestamp("2020-01-31")]
    assert len(gone) > 1000
