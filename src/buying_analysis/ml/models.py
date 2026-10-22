"""Walk-forward ranking models for the ML stock-selection study.

Inputs are the point-in-time panel (ml/panel.py). Each month, features are converted to cross-sectional
ranks in [-0.5, 0.5] (missing -> 0, the median) plus sector dummies, and the target is the cross-sectional
rank of the forward return. Models are refit every January on all rows whose target was fully observed
before that January (horizon-month purge); hyperparameters are fixed in advance (no tuning on returns).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.ml.panel import FEATURES, SIC_GROUPS

SECTORS = [g[2] for g in SIC_GROUPS]
# signs for the simple factor score: momentum, short-term reversal, value, profitability, investment,
# accruals, low volatility / lottery
FACTOR_SIGNS = {"mom_12_1": 1, "rev_1": -1, "bm": 1, "ep": 1, "cfp": 1, "op": 1, "gp_at": 1, "asset_growth": -1,
                "accruals": -1, "vol_d3": -1, "maxret_1": -1}  # fmt: skip
MODEL_NAMES = ["factor_score", "ridge", "random_forest", "lightgbm", "xgboost"]
SEED = 0


def prepare(panel: pd.DataFrame) -> pd.DataFrame:
    """Rank-transform features within each month; add sector dummies."""
    x = panel.groupby("date")[FEATURES].rank(pct=True) - 0.5
    x = x.fillna(0.0)
    for s in SECTORS:
        x[f"sec_{s}"] = (panel["sector"] == s).astype(float)
    return x


def target(panel: pd.DataFrame, horizon: int) -> pd.Series:
    col = "ret_fwd1" if horizon == 1 else "ret_fwd3"
    return panel.groupby("date")[col].rank(pct=True) - 0.5


def make_model(name: str):
    if name == "ridge":
        from sklearn.linear_model import Ridge

        return Ridge(alpha=1.0)
    if name == "random_forest":
        from sklearn.ensemble import RandomForestRegressor

        return RandomForestRegressor(n_estimators=200, max_depth=6, min_samples_leaf=500, max_features=0.33,
                                     max_samples=0.3, n_jobs=-1, random_state=SEED)  # fmt: skip
    if name == "lightgbm":
        import lightgbm as lgb

        return lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=31, min_child_samples=500,
                                 subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                                 random_state=SEED, n_jobs=8, verbose=-1)  # fmt: skip
    if name == "xgboost":
        import xgboost as xgb

        return xgb.XGBRegressor(n_estimators=400, learning_rate=0.03, max_depth=4, min_child_weight=200,
                                subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, tree_method="hist",
                                random_state=SEED, n_jobs=8)  # fmt: skip
    raise ValueError(name)


def factor_score(x: pd.DataFrame) -> np.ndarray:
    return sum(sign * x[f].to_numpy() for f, sign in FACTOR_SIGNS.items()) / len(FACTOR_SIGNS)


def walk_forward(panel: pd.DataFrame, model: str, horizon: int, first_year: int, last_year: int,
                 train_start: str = "1991-01-31") -> pd.DataFrame:  # fmt: skip
    """Predicted scores for every universe row dated in [first_year, last_year].

    For prediction year Y, training uses rows dated <= Dec 31 of Y-1 minus ``horizon`` months, so every
    training target was realized before the first prediction of Y.
    """
    x = prepare(panel)
    y = target(panel, horizon)
    dates = panel["date"]
    out = []
    for year in range(first_year, last_year + 1):
        test = (dates.dt.year == year).to_numpy()
        if not test.any():
            continue
        if model == "factor_score":
            score = factor_score(x[test])
        else:
            cutoff = pd.Timestamp(f"{year - 1}-12-31") - pd.offsets.MonthEnd(horizon)
            train = ((dates >= train_start) & (dates <= cutoff) & y.notna()).to_numpy()
            m = make_model(model)
            m.fit(x[train].to_numpy(), y[train].to_numpy())
            score = m.predict(x[test].to_numpy())
        out.append(pd.DataFrame({"date": dates[test].to_numpy(), "permno": panel.loc[test, "permno"].to_numpy(),
                                 "score": score}))  # fmt: skip
    return pd.concat(out, ignore_index=True)


def information_coefficient(preds: pd.DataFrame, panel: pd.DataFrame, horizon: int) -> pd.Series:
    """Monthly Spearman correlation between predicted score and the realized forward return."""
    col = "ret_fwd1" if horizon == 1 else "ret_fwd3"
    m = preds.merge(panel[["date", "permno", col]], on=["date", "permno"]).dropna()
    return m.groupby("date").apply(
        lambda g: g["score"].rank().corr(g[col].rank()), include_groups=False
    )
