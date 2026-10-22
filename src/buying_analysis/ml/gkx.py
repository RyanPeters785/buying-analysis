"""Long-only replication of Gu, Kelly & Xiu (2020), "Empirical Asset Pricing via Machine Learning".

Design (paper -> ours, departures noted):
  inputs     42 firm characteristics ranked to [-1, 1] each month (missing -> 0), 10 sector dummies, 7 macro
             predictors (standardized on training data) and all characteristic x macro interactions
             (paper: 94 characteristics, 74 SIC2 dummies, 8 macro)
  target     next-month excess return (ret_fwd1 - rf); winsorized at 1%/99% within training data only
  scheme     test year Y: train on months 1993-01 .. (Y-6)-12, validate on (Y-5)-01 .. (Y-1)-11 (the last month
             before Y whose target is realized by the end of Y-1), choose hyperparameters / early stopping on
             validation MSE, predict every stock in each month of Y; repeat for Y = 2003 .. 2025
  sampling   training and validation use up to 1,000 random stocks per month (compute limit; the paper uses all)
  models     OLS-3+H (size, book-to-market, momentum; Huber), ENet+H (SGD, Huber loss, elastic net),
             GBRT+H (LightGBM, Huber loss), NN3 (32-16-8 ReLU, Adam, L2, early stopping, 3-seed ensemble;
             paper: L1 + batch norm, 10 seeds)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from buying_analysis.ml.panel import GKX_FEATURES, SIC_GROUPS

SECTORS = [g[2] for g in SIC_GROUPS]
SEED = 0
TRAIN_START = pd.Timestamp("1993-01-31")
SAMPLE_PER_MONTH = 1000
MODELS = ["ols3", "enet", "gbrt", "nn3"]


def characteristics(panel: pd.DataFrame) -> np.ndarray:
    ranks = panel.groupby("date")[GKX_FEATURES].rank(pct=True)
    return ((ranks * 2 - 1).fillna(0.0)).to_numpy(np.float32)


def sector_dummies(panel: pd.DataFrame) -> np.ndarray:
    return np.stack([(panel["sector"] == s).to_numpy() for s in SECTORS], axis=1).astype(np.float32)


def design(
    chars: np.ndarray, sect: np.ndarray, macro: np.ndarray, with_interactions: bool
) -> np.ndarray:
    parts = [chars, sect, macro]
    if with_interactions:
        parts.append((chars[:, :, None] * macro[:, None, :]).reshape(len(chars), -1))
    return np.concatenate(parts, axis=1).astype(np.float32)


def sample_rows(
    dates: pd.Series, mask: np.ndarray, rng: np.random.Generator, per_month: int
) -> np.ndarray:
    idx = np.flatnonzero(mask)
    d = dates.to_numpy()[idx]
    keep = []
    for m in np.unique(d):
        rows = idx[d == m]
        keep.append(rows if len(rows) <= per_month else rng.choice(rows, per_month, replace=False))
    return np.sort(np.concatenate(keep)) if keep else idx


def fit_predict(name: str, Xtr, ytr, Xva, yva, Xte, seed: int = SEED) -> tuple[np.ndarray, dict]:
    """Fit on train, choose hyperparameters / stopping on validation MSE, predict test."""
    if name == "ols3":
        from sklearn.linear_model import HuberRegressor

        m = HuberRegressor(epsilon=1.35, max_iter=500).fit(Xtr, ytr)
        return m.predict(Xte), {}
    if name == "enet":
        from sklearn.linear_model import SGDRegressor

        best = None
        for alpha in (1e-5, 1e-4, 1e-3):
            m = SGDRegressor(loss="huber", epsilon=0.05, penalty="elasticnet", l1_ratio=0.5, alpha=alpha,
                             max_iter=20, tol=None, random_state=seed).fit(Xtr, ytr)  # fmt: skip
            mse = float(np.mean((m.predict(Xva) - yva) ** 2))
            if best is None or mse < best[0]:
                best = (mse, alpha, m)
        return best[2].predict(Xte), {"alpha": best[1]}
    if name == "gbrt":
        import lightgbm as lgb

        best = None
        for leaves in (3, 7):
            m = lgb.LGBMRegressor(objective="huber", alpha=0.05, n_estimators=1000, learning_rate=0.05,
                                  num_leaves=leaves, min_child_samples=200, subsample=0.8, subsample_freq=1,
                                  colsample_bytree=0.8, random_state=seed, n_jobs=1, verbose=-1)  # fmt: skip
            m.fit(Xtr, ytr, eval_set=[(Xva, yva)], eval_metric="l2",
                  callbacks=[lgb.early_stopping(50, verbose=False)])  # fmt: skip
            mse = float(np.mean((m.predict(Xva) - yva) ** 2))
            if best is None or mse < best[0]:
                best = (mse, leaves, m)
        return best[2].predict(Xte), {"num_leaves": best[1], "trees": best[2].best_iteration_}
    if name == "nn3":
        from sklearn.neural_network import MLPRegressor

        best = None
        for alpha in (1e-5, 1e-3):
            preds_va, preds_te = [], []
            for s in range(3):
                m = MLPRegressor(hidden_layer_sizes=(32, 16, 8), activation="relu", solver="adam", alpha=alpha,
                                 learning_rate_init=1e-3, batch_size=10000, random_state=seed + s)  # fmt: skip
                best_mse, best_state, bad = np.inf, None, 0
                for _ in range(60):  # epochs with early stopping on validation MSE
                    m.partial_fit(Xtr, ytr)
                    mse = float(np.mean((m.predict(Xva) - yva) ** 2))
                    if mse < best_mse - 1e-9:
                        best_mse, bad = mse, 0
                        best_state = (
                            [w.copy() for w in m.coefs_],
                            [b.copy() for b in m.intercepts_],
                        )
                    else:
                        bad += 1
                        if bad >= 5:
                            break
                m.coefs_, m.intercepts_ = best_state
                preds_va.append(m.predict(Xva))
                preds_te.append(m.predict(Xte))
            mse = float(np.mean((np.mean(preds_va, axis=0) - yva) ** 2))
            if best is None or mse < best[0]:
                best = (mse, alpha, np.mean(preds_te, axis=0))
        return best[2], {"alpha": best[1]}
    raise ValueError(name)


def r2_oos(pred: np.ndarray, actual: np.ndarray) -> float:
    """GKX out-of-sample R^2 (benchmark = zero excess return)."""
    return float(1 - np.sum((actual - pred) ** 2) / np.sum(actual**2))
