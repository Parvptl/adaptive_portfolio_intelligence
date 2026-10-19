"""Observation assembly and training-only feature scaling (decision D-062).

The observation at decision row ``d`` is, in this order:

1. the causal features dated ``d`` (``features.csv`` columns, artifact order), standardised
   with a mean and standard deviation fitted on training rows only, frozen, then clipped to
   ``+-FEATURE_CLIP`` (clipping counts are reported, never hidden);
2. the regime label dated ``d`` (frozen training thresholds) one-hot encoded over the 9
   trend x volatility labels of :data:`REGIME_LABELS`; ``unavailable`` or any other label is
   an error;
3. the end-of-row portfolio weights at ``d`` (assets in universe order, then cash): the
   ledger weights after any execution at the close of ``d``.

Every element is dated ``<= d``. Weights and one-hot inputs are not scaled. Standard
deviations use ``ddof=0``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.evaluation.metrics import WEIGHT_SUM_TOLERANCE
from adaptive_portfolio.regimes.rules import REGIME_LABELS

FEATURE_CLIP = 10.0
SCALER_SCHEMA_VERSION = 1
FIT_SPLIT = "train"


class ObservationError(ValueError):
    """Raised for missing, unknown or inconsistent observation inputs."""


@dataclass(frozen=True)
class FeatureScaler:
    """Per-feature mean and standard deviation, fitted on training rows and then frozen."""

    columns: tuple[str, ...]
    mean: tuple[float, ...]
    std: tuple[float, ...]
    fitted_on: dict[str, Any]  # split, first and last date, number of rows

    def transform(self, features: pd.DataFrame) -> tuple[np.ndarray, dict[str, int]]:
        """Standardised, clipped values and the number of clipped values per column."""
        if tuple(features.columns) != self.columns:
            raise ObservationError("feature columns differ from the fitted scaler's columns")
        values = features.to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            raise ObservationError("features contain missing or non-finite values")
        scaled = (values - np.asarray(self.mean)) / np.asarray(self.std)
        clipped = np.abs(scaled) > FEATURE_CLIP
        counts = dict(zip(self.columns, (int(n) for n in clipped.sum(axis=0)), strict=True))
        return np.clip(scaled, -FEATURE_CLIP, FEATURE_CLIP), counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCALER_SCHEMA_VERSION,
            "method": "standardise (ddof=0), then clip",
            "clip": FEATURE_CLIP,
            "fitted_on": self.fitted_on,
            "columns": list(self.columns),
            "mean": list(self.mean),
            "std": list(self.std),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> FeatureScaler:
        if raw.get("schema_version") != SCALER_SCHEMA_VERSION or raw.get("clip") != FEATURE_CLIP:
            raise ObservationError("unsupported scaler artifact (schema version or clip)")
        return cls(
            columns=tuple(raw["columns"]),
            mean=tuple(float(x) for x in raw["mean"]),
            std=tuple(float(x) for x in raw["std"]),
            fitted_on=dict(raw["fitted_on"]),
        )

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> FeatureScaler:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def fit_feature_scaler(
    features: pd.DataFrame, split_labels: pd.Series, first_row: int, last_row: int
) -> FeatureScaler:
    """Fit on rows ``first_row..last_row`` (inclusive), which must all be training rows.

    The intended range is the common start ``k0`` to the last training decision. Rows outside
    it are not read, so later rows cannot change the fitted values.
    """
    if not features.index.equals(split_labels.index):
        raise ObservationError("features and split labels must share one date index")
    if not 0 <= first_row <= last_row < len(features):
        raise ObservationError(f"invalid fit rows [{first_row}, {last_row}]")
    labels = split_labels.iloc[first_row : last_row + 1]
    if (labels != FIT_SPLIT).any():
        raise ObservationError(f"the scaler may only be fitted on {FIT_SPLIT!r} rows")
    values = features.iloc[first_row : last_row + 1].to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        raise ObservationError("fit rows contain missing or non-finite feature values")
    mean, std = values.mean(axis=0), values.std(axis=0, ddof=0)
    if (std <= 0).any():
        constant = [c for c, s in zip(features.columns, std, strict=True) if s <= 0]
        raise ObservationError(f"constant features on the fit rows cannot be scaled: {constant}")
    dates = labels.index
    return FeatureScaler(
        columns=tuple(features.columns),
        mean=tuple(float(x) for x in mean),
        std=tuple(float(x) for x in std),
        fitted_on={
            "split": FIT_SPLIT,
            "first_date": dates[0].date().isoformat(),
            "last_date": dates[-1].date().isoformat(),
            "rows": len(labels),
        },
    )


def regime_one_hot(label: str) -> np.ndarray:
    """One-hot vector over :data:`REGIME_LABELS`; ``unavailable`` and unknown labels raise."""
    if label not in REGIME_LABELS:
        raise ObservationError(f"regime label {label!r} cannot be encoded (expected one of 9)")
    encoded = np.zeros(len(REGIME_LABELS))
    encoded[REGIME_LABELS.index(label)] = 1.0
    return encoded


def build_observation(
    scaled_features: np.ndarray, regime_label: str, weights: np.ndarray
) -> np.ndarray:
    """Concatenate scaled features, the one-hot regime and the end-of-row weights."""
    features = np.asarray(scaled_features, dtype=np.float64)
    held = np.asarray(weights, dtype=np.float64)
    if features.ndim != 1 or not np.isfinite(features).all():
        raise ObservationError("scaled features must be a finite vector")
    if np.abs(features).max(initial=0.0) > FEATURE_CLIP:
        raise ObservationError("scaled features exceed the clip bound; transform them first")
    if held.ndim != 1 or not np.isfinite(held).all() or (held < -WEIGHT_SUM_TOLERANCE).any():
        raise ObservationError("weights must be a finite, non-negative vector")
    if abs(held.sum() - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise ObservationError(f"weights including cash must sum to 1, got {held.sum()}")
    return np.concatenate([features, regime_one_hot(regime_label), held])
