"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import METRICS, PROCESSED, TARGET, TRAIN_END, VALID_END
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


# --- Exercise 4: target transformations (off by default) -------------------
# A tree predicts a constant per leaf, bounded by the 2011 targets it saw, so
# it cannot reach 2012 levels. Rescaling the target by a *lagged* level turns
# "how many rides" (non-stationary) into "how far from recent demand"
# (roughly stationary), which a tree can learn. The level is a feature known
# at prediction time, so this is not leakage. The committed metrics.json
# uses no transform; these exist only behind --target-transform.


class RelativeTarget(BaseEstimator, RegressorMixin):
    """Fit `estimator` on a transform of y relative to a lagged column, and
    invert the transform at predict time."""

    def __init__(self, estimator=None, base: str = "cnt_roll_28", kind: str = "log_ratio"):
        self.estimator = estimator
        self.base = base
        self.kind = kind

    def _fwd(self, y, b):
        if self.kind == "log_ratio":
            return np.log(y) - np.log(b)
        if self.kind == "diff":
            return y - b
        if self.kind == "log":
            return np.log(y)
        raise ValueError(f"unknown kind {self.kind!r}")

    def _inv(self, z, b):
        if self.kind == "log_ratio":
            return np.exp(z) * b
        if self.kind == "diff":
            return z + b
        return np.exp(z)

    def fit(self, X, y):
        b = X[self.base].to_numpy(dtype=float)
        self.estimator_ = clone(self.estimator).fit(X, self._fwd(np.asarray(y, dtype=float), b))
        return self

    def predict(self, X):
        b = X[self.base].to_numpy(dtype=float)
        return self._inv(self.estimator_.predict(X), b)


TARGET_TRANSFORMS = {
    "log": dict(kind="log", base="cnt_lag_1"),
    "log_ratio28": dict(kind="log_ratio", base="cnt_roll_28"),
    "log_ratio7": dict(kind="log_ratio", base="cnt_roll_7"),
    "diff28": dict(kind="diff", base="cnt_roll_28"),
}


def build_models(target_transform: str | None = None) -> dict:
    models = {name: clone(m) for name, m in MODELS.items()}
    if target_transform:
        spec = TARGET_TRANSFORMS[target_transform]
        for name in ("ridge", "hgb"):
            models[name] = RelativeTarget(models[name], **spec)
    return models


def fit_and_score(target_transform: str | None = None, splits=("valid", "test")) -> dict:
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)
    parts = {"valid": valid, "test": test}

    results = {
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test": len(test),
    }
    if target_transform:
        results["target_transform"] = target_transform
    for name, model in build_models(target_transform).items():
        model.fit(train[cols], train[TARGET])
        results[name] = {
            split: {
                "r2": round(float(r2_score(parts[split][TARGET], model.predict(parts[split][cols]))), 4),
                "mae": round(float(mean_absolute_error(parts[split][TARGET], model.predict(parts[split][cols]))), 1),
            }
            for split in splits
        }
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-transform", choices=sorted(TARGET_TRANSFORMS))
    ap.add_argument("--valid-only", action="store_true",
                    help="score validation only; use while iterating")
    ns = ap.parse_args()
    splits = ("valid",) if ns.valid_only else ("valid", "test")
    res = fit_and_score(ns.target_transform, splits)
    if ns.target_transform is None and not ns.valid_only:
        # Only the untransformed, fully scored run is the headline artefact.
        METRICS.parent.mkdir(parents=True, exist_ok=True)
        METRICS.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
