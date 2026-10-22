import numpy as np
import pandas as pd
import pytest

from buying_analysis.ml.portfolio import simulate, summary, top_n_targets


def _rets():
    idx = pd.date_range("2000-01-31", periods=14, freq="ME")
    return pd.DataFrame(
        {1: [0.01] * 14, 2: [0.02] * 14, 3: [0.0] * 5 + [-0.5] + [np.nan] * 8}, index=idx
    )


def test_zero_cost_single_asset_compounds_exactly():
    r = _rets()
    a = simulate(
        {r.index[0]: pd.Series({1: 1.0})}, r, r.index[0], r.index[-1], cost_bps=0.0, amount=1000.0
    )
    # first deposit at Jan month-end, then 13 months of +1%; second deposit at the December month-end
    dec = r.index[r.index.month == 12][0]
    pre = 1000 * 1.01 ** (r.index.get_loc(dec))
    expect = (pre + 1000) * 1.01 ** (len(r) - 1 - r.index.get_loc(dec))
    assert a["equity"].iloc[-1] == pytest.approx(expect)


def test_delisted_holding_becomes_cash_after_its_last_return():
    r = _rets()
    a = simulate(
        {r.index[0]: pd.Series({3: 1.0})}, r, r.index[0], r.index[6], cost_bps=0.0, amount=1000.0
    )
    assert a["equity"].iloc[-1] == pytest.approx(500.0)  # -50% delisting month, then cash at 0%


def test_costs_charged_on_traded_value():
    r = _rets()
    a = simulate(
        {r.index[0]: pd.Series({1: 1.0})}, r, r.index[0], r.index[1], cost_bps=10.0, amount=1000.0
    )
    assert a["cost"].iloc[0] == pytest.approx(1.0)  # 10 bps of the $1,000 bought
    assert a["equity"].iloc[0] == pytest.approx(999.0 * 1.01)


def test_top_n_equal_weights():
    p = pd.DataFrame(
        {
            "date": [pd.Timestamp("2000-01-31")] * 4,
            "permno": [1, 2, 3, 4],
            "score": [0.1, 0.4, 0.3, 0.2],
        }
    )
    t = top_n_targets(p, 2, 1, pd.Timestamp("2000-01-31"))
    w = t[pd.Timestamp("2000-01-31")]
    assert set(w.index) == {2, 3} and w.sum() == pytest.approx(1.0)


def test_summary_runs():
    r = _rets()
    a = simulate({r.index[0]: pd.Series({2: 1.0})}, r, r.index[0], r.index[-1], cost_bps=0.0)
    s = summary(a, pd.Series(0.0, index=r.index))
    assert s["max_drawdown"] == pytest.approx(0.0) and s["xirr"] > 0.2


# --- walk-forward: training never sees a target that was not yet realized ---------------------------------


def _synthetic_panel(seed=0):
    from buying_analysis.ml.panel import FEATURES

    rng = np.random.default_rng(seed)
    dates = pd.date_range("1995-01-31", "2001-12-31", freq="ME")
    rows = []
    for d in dates:
        for p in range(60):
            rows.append({"date": d, "permno": p, "sector": "manufacturing",
                         **{f: rng.normal() for f in FEATURES},
                         "ret_fwd1": rng.normal(0, 0.05), "ret_fwd3": rng.normal(0, 0.1)})  # fmt: skip
    return pd.DataFrame(rows)


@pytest.mark.parametrize(
    "model,horizon", [("ridge", 1), ("lightgbm", 3), ("random_forest", 1), ("xgboost", 3)]
)
def test_walk_forward_ignores_unrealized_targets(model, horizon):
    from buying_analysis.ml.models import walk_forward

    p = _synthetic_panel()
    base = walk_forward(p, model, horizon, 2000, 2000, train_start="1995-01-31")
    q = p.copy()
    cutoff = pd.Timestamp("1999-12-31") - pd.offsets.MonthEnd(horizon)
    late = q["date"] > cutoff  # targets not yet realized at the start of 2000
    col = "ret_fwd1" if horizon == 1 else "ret_fwd3"
    q.loc[late, col] = np.random.default_rng(9).normal(0, 1, late.sum())
    later_feats = q["date"] > pd.Timestamp("2000-12-31")
    q.loc[later_feats, "mom_12_1"] = 99.0  # the future beyond the prediction year
    again = walk_forward(q, model, horizon, 2000, 2000, train_start="1995-01-31")
    np.testing.assert_allclose(base["score"].to_numpy(), again["score"].to_numpy())


def test_per_stock_cost_map():
    r = _rets()
    t0 = r.index[0]
    cmap = {t0: pd.Series({1: 50.0, 2: 10.0})}
    a = simulate({t0: pd.Series({1: 0.5, 2: 0.5})}, r, t0, r.index[1], cost_bps=0.0, amount=1000.0, cost_map=cmap)
    assert a["cost"].iloc[0] == pytest.approx(500 * 0.005 + 500 * 0.001)


def test_costs_reduce_the_monthly_return_not_just_the_balance():
    r = _rets()
    t0 = r.index[0]
    tg = {t0: pd.Series({1: 1.0})}
    free = simulate(tg, r, t0, r.index[1], cost_bps=0.0, amount=1000.0)
    paid = simulate(tg, r, t0, r.index[1], cost_bps=10.0, amount=1000.0)
    assert free["ret"].iloc[0] == pytest.approx(0.01)
    assert paid["ret"].iloc[0] == pytest.approx(999.0 * 1.01 / 1000.0 - 1)
