import numpy as np
import pandas as pd
import pytest

from buying_analysis.backtest import Engine, MarketData, contribution_schedule
from buying_analysis.costs import CostModel
from buying_analysis.strategies.dip import BuyTheDip
from buying_analysis.strategies.nulls import in_market_spells, random_schedule
from buying_analysis.strategies.timing import (
    IEF,
    RSI2,
    SECTORS,
    SPY,
    DualMomentum,
    SectorRotation,
    SMACross,
    TrendSMA,
    VolTarget,
    rsi,
)

ZERO = CostModel(
    spread_bps_etf=0, spread_bps_stock=0, sec_fee_rate=0, finra_taf_per_share=0, mmf_expense=0
)
A = 1


def test_rsi_hand_calc():
    # diffs 1, 1, -1: seed avg up 1, down 0; then up 0.5, down 0.5 -> RSI 50
    assert rsi(np.array([1.0, 2, 3, 2]), 2) == pytest.approx(50.0)
    assert rsi(np.array([1.0, 2, 3]), 2) == 100.0


def test_random_schedule_matches_exposure_and_spells():
    rng = np.random.default_rng(0)
    for n_in, k in [(500, 7), (10, 10), (999, 1), (0, 0)]:
        s = random_schedule(1000, n_in, k, rng)
        spells, days, n = in_market_spells(pd.Series(s.astype(float)))
        assert (spells, days, n) == (k, n_in, 1000)


def test_dip_waits_for_drawdown_then_buys(panel):
    c = [100.0] * 20 + [95.0] * 5 + [89.0] * 5  # 11% below the high from day 25
    md = MarketData.load(prices=panel({A: c}))
    dep = contribution_schedule(md.sessions, 1000.0, "once")
    res = Engine(md, costs=ZERO).run(BuyTheDip(A, dip=0.10, max_wait_months=6), dep)
    buy = res.trades[res.trades["side"] == "buy"]
    assert list(buy["session"]) == [md.sessions[26]]  # signal at day-25 close, fill next open


def test_dip_falls_back_after_max_wait(panel):
    md = MarketData.load(prices=panel({A: [100.0] * 80}))
    dep = contribution_schedule(md.sessions, 1000.0, "once")
    res = Engine(md, costs=ZERO).run(BuyTheDip(A, dip=0.10, max_wait_months=2), dep)
    buy = res.trades[res.trades["side"] == "buy"]
    first = md.sessions[0]
    signal = md.sessions[md.sessions >= first + pd.DateOffset(months=2)][0]
    assert buy["session"].iloc[0] == md.sessions[md.sessions.get_loc(signal) + 1]


def test_trend_in_when_above_sma_and_out_when_below(panel):
    up = list(np.linspace(100, 200, 260))
    down = list(np.linspace(200, 100, 260))
    md = MarketData.load(prices=panel({A: up + down}))
    dep = contribution_schedule(md.sessions, 1000.0, "once")
    res = Engine(md, costs=ZERO).run(TrendSMA(A, months=10), dep)
    w = res.weights[A] if A in res.weights else pd.Series(0, index=res.daily.index)
    assert w.loc[md.sessions[259]] > 0.99  # rising: invested
    assert w.iloc[-1] == 0  # falling for a year: out


# --- no look-ahead on real data for every timing strategy -------------------------------------------------


@pytest.fixture(scope="module")
def real_md():
    return MarketData.load([SPY, IEF, *SECTORS], end="2008-12-31")


@pytest.mark.parametrize(
    "make",
    [
        TrendSMA,
        SMACross,
        DualMomentum,
        SectorRotation,
        VolTarget,
        RSI2,
        lambda: BuyTheDip(SPY, 0.1, 6),
    ],
)
def test_truncating_the_future_changes_nothing(real_md, make):
    cut = pd.Timestamp("2006-06-30")
    short = MarketData.load([SPY, IEF, *SECTORS], end=cut)
    start = pd.Timestamp("2003-01-02")
    dep_long = contribution_schedule(real_md.sessions, 5000.0, "annual", start=start)
    r_long = Engine(real_md).run(make(), dep_long, start=start)
    r_short = Engine(short).run(make(), dep_long[dep_long.index <= cut], start=start)
    a = r_long.daily.loc[:cut, ["equity", "cash"]]
    b = r_short.daily.loc[:cut, ["equity", "cash"]]
    pd.testing.assert_frame_equal(a, b)
    ta = r_long.trades[r_long.trades["session"] <= cut].reset_index(drop=True)
    pd.testing.assert_frame_equal(ta, r_short.trades.reset_index(drop=True))
