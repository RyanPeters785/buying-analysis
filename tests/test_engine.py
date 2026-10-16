import numpy as np
import pandas as pd
import pytest

from buying_analysis.backtest import Context, Engine, MarketData, Strategy, contribution_schedule
from buying_analysis.costs import CostModel
from buying_analysis.metrics import summarize, xirr
from buying_analysis.strategies.benchmarks import SPY, sixty_forty, spy_buy_and_hold
from buying_analysis.strategies.deployment import DCA, LumpSum

ZERO = CostModel(
    spread_bps_etf=0, spread_bps_stock=0, sec_fee_rate=0, finra_taf_per_share=0, mmf_expense=0
)
A, B = 1, 2


def run(prices, strategy, deposits=None, costs=ZERO, **kw):
    md = MarketData.load(prices=prices)
    dep = deposits if deposits is not None else contribution_schedule(md.sessions, 1000.0, "once")
    return Engine(md, costs=costs, **kw).run(strategy, dep)


# --- accounting ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("costs", [ZERO, CostModel()])
def test_cash_plus_holdings_equals_equity(panel, costs):
    rng = np.random.default_rng(0)
    c = 100 * np.cumprod(1 + rng.normal(0, 0.01, 300))
    p = panel({A: c, B: c[::-1]})
    md = MarketData.load(prices=p)
    dep = contribution_schedule(md.sessions, 1000.0, "monthly")
    res = Engine(md, costs=costs).run(sixty_forty_like(), dep)
    d = res.daily
    assert np.allclose(d["cash"] + d["invested"], d["equity"])
    assert d["deposit"].sum() == pytest.approx(dep.sum())
    assert (d["cash"] >= -1e-9).all()


def sixty_forty_like():
    s = sixty_forty()
    s.target, s.assets = {A: 0.6, B: 0.4}, (A, B)
    return s


def test_costs_reduce_equity_by_exactly_the_charge(panel):
    p = panel({A: [100.0] * 10})
    costs = CostModel(spread_bps_etf=10, sec_fee_rate=0, finra_taf_per_share=0, mmf_expense=0)
    res = run(p, LumpSum(A), costs=costs)
    charged = res.daily["costs"].sum()
    assert charged == pytest.approx(1000 / 1.001 * 0.001)  # buy as much as cash allows incl. spread
    assert res.daily["equity"].iloc[-1] == pytest.approx(1000 - charged)


def test_sell_fees_charged(panel):
    p = panel({A: [100.0] * 6})

    class InOut(Strategy):
        name = "in_out"

        def decide(self, ctx):
            return {A: 1.0} if ctx.i == 0 else ({} if ctx.i == 2 else None)

    cm = CostModel(spread_bps_etf=0, sec_fee_rate=0.001, finra_taf_per_share=0, mmf_expense=0)
    res = run(p, InOut(), costs=cm)
    assert res.daily["equity"].iloc[-1] == pytest.approx(1000 - 1.0)  # 0.1% of the $1000 sold


# --- prices and returns ----------------------------------------------------------------------------------


def test_zero_cost_lump_sum_reproduces_cumulative_ret():
    md = MarketData.load([SPY], start="2010-01-04", end="2012-12-31")
    dep = contribution_schedule(md.sessions, 5000.0, "once")
    res = Engine(md, costs=ZERO).run(spy_buy_and_hold(), dep)
    c = md.col(SPY)
    # bought at the 2nd session's open, held to the end: growth = close_idx[end] / open_idx[1]
    growth_cash = 1 + max(md.rf[0], 0) * md.days[1] / 365 if not np.isnan(md.rf[0]) else 1.0
    expected = 5000 * growth_cash * md.close_idx[-1, c] / md.open_idx[1, c]
    assert res.daily["equity"].iloc[-1] == pytest.approx(expected, rel=1e-9)
    # and close-to-close equity growth after day 1 equals CRSP (1 + ret)
    ret = (1 + pd.Series(md.close_idx[:, c], index=md.sessions).pct_change()).iloc[2:]
    eq = res.daily["equity"]
    assert np.allclose((eq / eq.shift(1)).iloc[2:], ret, rtol=1e-12)


def test_dca_constant_price_buys_equal_tranches(panel):
    n = 260
    p = panel({A: [50.0] * n}, start="2021-01-01")
    md = MarketData.load(prices=p)
    dep = contribution_schedule(md.sessions, 12000.0, "annual")
    res = Engine(md, costs=ZERO).run(DCA(A, "monthly"), dep)
    buys = res.trades[res.trades["side"] == "buy"]
    assert len(buys) == 12
    assert np.allclose(buys["value"], 1000.0)
    assert res.daily["equity"].iloc[-1] == pytest.approx(12000.0)


def test_xirr_known_example():
    # -1000 then +1100 one year later -> 10%
    assert xirr(pd.to_datetime(["2020-01-01", "2020-12-31"]), [-1000, 1100]) == pytest.approx(
        0.10, abs=1e-3
    )
    # two deposits; check against NPV = 0
    d = pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"])
    r = xirr(d, [-1000, -1000, 2300])
    t = (d - d[0]).days / 365
    assert np.sum(np.array([-1000, -1000, 2300]) / (1 + r) ** t) == pytest.approx(0, abs=1e-6)


# --- settlement ------------------------------------------------------------------------------------------


def test_sell_then_buy_cannot_use_unsettled_proceeds(panel):
    p = panel({A: [100.0] * 8, B: [100.0] * 8})

    class Switch(Strategy):
        name = "switch"

        def decide(self, ctx):
            return {A: 1.0} if ctx.i == 0 else ({B: 1.0} if ctx.i == 2 else None)

    res = run(p, Switch())
    t = res.trades.set_index(["session", "permno", "side"])["value"]
    s = res.daily.index
    assert t[(s[3], A, "sell")] == pytest.approx(1000)
    assert (s[3], B, "buy") not in t.index  # proceeds unsettled on the sale day
    assert t[(s[4], B, "buy")] == pytest.approx(1000)  # bought once settled (T+1)


# --- no look-ahead ---------------------------------------------------------------------------------------


class Recorder(Strategy):
    """Momentum-ish toy: hold A when its 5-day return is positive. Records what it saw."""

    name = "recorder"

    def reset(self):
        self.seen = []

    def decide(self, ctx: Context):
        x = ctx.close(A)
        self.seen.append(x.copy())
        if len(x) < 6:
            return None
        return {A: 1.0} if x[-1] / x[-6] > 1 else {}


def test_perturbing_future_prices_changes_nothing_before_t(panel):
    rng = np.random.default_rng(1)
    c = 100 * np.cumprod(1 + rng.normal(0, 0.02, 120))
    cut = 70
    c2 = c.copy()
    c2[cut + 1 :] *= np.cumprod(1 + rng.normal(0, 0.05, len(c) - cut - 1))
    s1, s2 = Recorder(), Recorder()
    r1, r2 = run(panel({A: c}), s1), run(panel({A: c2}), s2)
    for k in range(cut + 1):
        assert np.array_equal(s1.seen[k], s2.seen[k], equal_nan=True)
    pd.testing.assert_frame_equal(r1.weights.iloc[: cut + 1], r2.weights.iloc[: cut + 1])
    t1 = r1.trades[r1.trades["session"] <= r1.daily.index[cut]]
    t2 = r2.trades[r2.trades["session"] <= r2.daily.index[cut]]
    pd.testing.assert_frame_equal(t1, t2)


def test_metrics_run(panel):
    p = panel({A: list(np.linspace(100, 150, 300))})
    res = run(p, LumpSum(A))
    m = summarize(res)
    assert m["final_value"] > 1000 and m["max_drawdown"] == pytest.approx(0, abs=1e-12)
