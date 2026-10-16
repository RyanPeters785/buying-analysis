import numpy as np
import pandas as pd
import pytest


def make_panel(closes: dict[int, list[float]], opens: dict[int, list[float]] | None = None, start="2020-01-02",
               rf: float = 0.0, etf=True) -> pd.DataFrame:  # fmt: skip
    """Synthetic CRSP-like panel: ret from closes, open defaults to close, all assets listed every day."""
    n = len(next(iter(closes.values())))
    sessions = pd.bdate_range(start, periods=n)
    rows = []
    for p, c in closes.items():
        c = np.asarray(c, float)
        o = np.asarray(opens[p], float) if opens and p in opens else c
        ret = np.r_[np.nan, c[1:] / c[:-1] - 1]
        rows.append(pd.DataFrame({
            "permno": p, "session": sessions, "ticker": f"T{p}", "prc": c, "close": c, "open": o, "ret": ret,
            "securitytype": "FUND" if etf else "EQTY", "tradingstatusflg": "A", "rf": rf,
        }))  # fmt: skip
    return pd.concat(rows, ignore_index=True)


@pytest.fixture
def panel():
    return make_panel
