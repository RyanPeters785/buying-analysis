import numpy as np
import pandas as pd
import pytest

from buying_analysis.stats import block_bootstrap, deflated_sharpe, holm


def _daily(r, dep0=1000.0):
    idx = pd.bdate_range("2000-01-03", periods=len(r) + 1)
    twr = np.r_[0.0, r]
    eq = dep0 * np.cumprod(1 + twr)
    dep = np.zeros(len(idx))
    dep[0] = dep0
    return pd.DataFrame({"equity": eq, "twr_ret": twr, "deposit": dep, "rf": 0.0}, index=idx)


def test_bootstrap_identical_series_has_zero_difference():
    r = np.random.default_rng(0).normal(0.0003, 0.01, 1000)
    out = block_bootstrap(_daily(r), _daily(r), n_boot=200)
    assert out["cagr_diff_lo"] == pytest.approx(0) and out["cagr_diff_hi"] == pytest.approx(0)
    assert out["final_value_ratio_p"] == 1.0  # never strictly better


def test_bootstrap_detects_a_clear_edge():
    rng = np.random.default_rng(1)
    b = rng.normal(0.0003, 0.01, 2000)
    a = b + 0.0004  # +10%/yr, same noise
    out = block_bootstrap(_daily(a), _daily(b), n_boot=300)
    assert out["cagr_diff_lo"] > 0.08 and out["final_value_ratio_p"] == 0.0


def test_deflated_sharpe_falls_with_more_trials():
    r = pd.Series(np.random.default_rng(2).normal(0.0005, 0.01, 2500))
    one = deflated_sharpe(r, 1, 0.0)
    many = deflated_sharpe(r, 1000, (0.02) ** 2)
    assert 0 <= many < one <= 1


def test_holm():
    p = pd.Series([0.01, 0.04, 0.03], index=list("abc"))
    assert holm(p).round(4).to_dict() == {"a": 0.03, "b": 0.06, "c": 0.06}
