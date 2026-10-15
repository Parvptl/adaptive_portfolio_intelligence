"""Transparent, training-calibrated rule-based market regimes (decision D-045).

Two components, each from one causal feature (see ``configs/features.yaml``):

* **Trend** from market momentum ``m``: ``negative`` if ``m < -b``, ``positive`` if
  ``m > +b``, ``neutral`` if ``-b <= m <= +b``. The band half-width ``b`` is the
  ``trend_neutral_quantile`` of ``|m|`` over the training partition. Labels therefore
  keep their sign meaning: "negative" always means the trailing return was below zero.
* **Volatility** from market volatility ``v``: ``low`` if ``v < q_low``, ``high`` if
  ``v > q_high``, ``normal`` if ``q_low <= v <= q_high``. ``q_low`` and ``q_high`` are
  training-partition quantiles (terciles by default), so the labels are *relative to
  the training period*.

The regime is ``"<trend>_<volatility>"`` (up to 9 combinations; none is forced to
occur). Rows with a missing regime feature are ``unavailable``, never guessed.

Thresholds are fitted once, on training rows only (``fit_regime_thresholds``), stored
as JSON (``save_thresholds``), and applied unchanged to every partition
(``assign_regimes``). Validation and test values cannot influence them.
Quantiles use NumPy's default ``linear`` interpolation.

These labels are a heuristic, interpretable baseline. They are not verified economic
states.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.config import RegimeConfig

TREND_LABELS = ("negative", "neutral", "positive")
VOLATILITY_LABELS = ("low", "normal", "high")
UNAVAILABLE = "unavailable"
REGIME_LABELS = tuple(f"{t}_{v}" for t in TREND_LABELS for v in VOLATILITY_LABELS)
ARTIFACT_SCHEMA_VERSION = 1
METHOD = "trend: zero-centred band b = quantile(|m|); volatility: quantiles of v"
CALIBRATION_SPLIT = "train"


class RegimeCalibrationError(ValueError):
    """Raised when thresholds cannot be fitted or an artifact is invalid or incompatible."""


@dataclass(frozen=True)
class RegimeThresholds:
    """Frozen, serialisable regime definition fitted on the training partition."""

    trend_feature: str
    volatility_feature: str
    trend_neutral_quantile: float
    volatility_quantiles: tuple[float, float]
    trend_band: float
    volatility_low: float
    volatility_high: float
    calibration: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "method": METHOD,
            "trend_feature": self.trend_feature,
            "volatility_feature": self.volatility_feature,
            "trend_neutral_quantile": self.trend_neutral_quantile,
            "volatility_quantiles": list(self.volatility_quantiles),
            "thresholds": {
                "trend_band": self.trend_band,
                "volatility_low": self.volatility_low,
                "volatility_high": self.volatility_high,
            },
            "rules": {
                "trend": "negative if m < -trend_band; positive if m > trend_band; else neutral",
                "volatility": "low if v < volatility_low; high if v > volatility_high; else normal",
                "regime": "<trend>_<volatility>; unavailable if a feature is missing",
            },
            "calibration": self.calibration,
            "source": self.source,
            "disclaimer": "Heuristic labels, not verified market states.",
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> RegimeThresholds:
        try:
            if raw["artifact_schema_version"] != ARTIFACT_SCHEMA_VERSION:
                raise RegimeCalibrationError(
                    f"unsupported artifact schema {raw['artifact_schema_version']!r}"
                )
            if raw["method"] != METHOD:
                raise RegimeCalibrationError(f"unknown calibration method {raw['method']!r}")
            values = raw["thresholds"]
            thresholds = cls(
                trend_feature=str(raw["trend_feature"]),
                volatility_feature=str(raw["volatility_feature"]),
                trend_neutral_quantile=float(raw["trend_neutral_quantile"]),
                volatility_quantiles=(
                    float(raw["volatility_quantiles"][0]),
                    float(raw["volatility_quantiles"][1]),
                ),
                trend_band=float(values["trend_band"]),
                volatility_low=float(values["volatility_low"]),
                volatility_high=float(values["volatility_high"]),
                calibration=dict(raw.get("calibration", {})),
                source=dict(raw.get("source", {})),
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            if isinstance(exc, RegimeCalibrationError):
                raise
            raise RegimeCalibrationError(f"malformed regime-threshold artifact: {exc}") from exc
        numbers = (thresholds.trend_band, thresholds.volatility_low, thresholds.volatility_high)
        if not all(math.isfinite(x) for x in numbers):
            raise RegimeCalibrationError("artifact thresholds must be finite")
        if thresholds.trend_band < 0 or thresholds.volatility_low > thresholds.volatility_high:
            raise RegimeCalibrationError(
                "artifact thresholds are inconsistent (need trend_band >= 0 and "
                "volatility_low <= volatility_high)"
            )
        return thresholds


def fit_regime_thresholds(
    features: pd.DataFrame,
    split_labels: pd.Series,
    config: RegimeConfig,
    *,
    trend_feature: str,
    volatility_feature: str,
    source: Mapping[str, Any] | None = None,
) -> RegimeThresholds:
    """Fit thresholds on rows labelled ``train`` whose two regime features are available."""
    if not features.index.equals(split_labels.index):
        raise RegimeCalibrationError("features and split labels must share the same dates")
    for name in (trend_feature, volatility_feature):
        if name not in features.columns:
            raise RegimeCalibrationError(f"regime feature {name!r} not in the feature set")
    in_train = (split_labels == CALIBRATION_SPLIT).to_numpy()
    trend = features[trend_feature].to_numpy(dtype=np.float64)
    vol = features[volatility_feature].to_numpy(dtype=np.float64)
    usable = in_train & np.isfinite(trend) & np.isfinite(vol)
    count = int(usable.sum())
    if count < config.min_calibration_observations:
        raise RegimeCalibrationError(
            f"only {count} training row(s) have both regime features; "
            f"min_calibration_observations={config.min_calibration_observations}. "
            "The training period is too short for the configured windows."
        )
    dates = features.index[usable]
    low_q, high_q = config.volatility_quantiles
    vol_low, vol_high = np.quantile(vol[usable], [low_q, high_q], method="linear")
    return RegimeThresholds(
        trend_feature=trend_feature,
        volatility_feature=volatility_feature,
        trend_neutral_quantile=config.trend_neutral_quantile,
        volatility_quantiles=(low_q, high_q),
        trend_band=float(
            np.quantile(np.abs(trend[usable]), config.trend_neutral_quantile, method="linear")
        ),
        volatility_low=float(vol_low),
        volatility_high=float(vol_high),
        calibration={
            "split": CALIBRATION_SPLIT,
            "rows_in_split": int(in_train.sum()),
            "rows_used": count,
            "rows_excluded_missing_features": int(in_train.sum()) - count,
            "first_date_used": dates[0].date().isoformat(),
            "last_date_used": dates[-1].date().isoformat(),
            "quantile_method": "numpy linear interpolation",
        },
        source=dict(source or {}),
    )


def check_compatibility(
    thresholds: RegimeThresholds,
    *,
    trend_feature: str,
    volatility_feature: str,
    config: RegimeConfig,
) -> None:
    """Refuse to apply an artifact fitted for different features or quantile settings."""
    expected = (
        trend_feature,
        volatility_feature,
        config.trend_neutral_quantile,
        tuple(config.volatility_quantiles),
    )
    actual = (
        thresholds.trend_feature,
        thresholds.volatility_feature,
        thresholds.trend_neutral_quantile,
        tuple(thresholds.volatility_quantiles),
    )
    if expected != actual:
        raise RegimeCalibrationError(
            f"threshold artifact does not match the current feature configuration: artifact "
            f"(trend, volatility, trend quantile, volatility quantiles) = {actual}, "
            f"config = {expected}"
        )


def assign_regimes(features: pd.DataFrame, thresholds: RegimeThresholds) -> pd.DataFrame:
    """Apply frozen thresholds row by row; the input frame is not modified."""
    for name in (thresholds.trend_feature, thresholds.volatility_feature):
        if name not in features.columns:
            raise RegimeCalibrationError(f"regime feature {name!r} not in the feature set")
    m = features[thresholds.trend_feature].to_numpy(dtype=np.float64)
    v = features[thresholds.volatility_feature].to_numpy(dtype=np.float64)
    has_m, has_v = np.isfinite(m), np.isfinite(v)
    b = thresholds.trend_band

    trend = np.full(len(m), UNAVAILABLE, dtype=object)
    trend[has_m] = "neutral"
    trend[has_m & (m < -b)] = "negative"
    trend[has_m & (m > b)] = "positive"

    vol = np.full(len(v), UNAVAILABLE, dtype=object)
    vol[has_v] = "normal"
    vol[has_v & (v < thresholds.volatility_low)] = "low"
    vol[has_v & (v > thresholds.volatility_high)] = "high"

    both = has_m & has_v
    regime = np.where(
        both, np.char.add(np.char.add(trend.astype(str), "_"), vol.astype(str)), UNAVAILABLE
    )
    status = np.select(
        [both, ~has_m & ~has_v, ~has_m],
        ["ok", "missing_both_features", "missing_trend_feature"],
        default="missing_volatility_feature",
    )
    return pd.DataFrame(
        {
            "trend_label": trend,
            "volatility_label": vol,
            "regime": regime.astype(object),
            "regime_status": status.astype(object),
        },
        index=features.index,
    )


def save_thresholds(thresholds: RegimeThresholds, path: Path) -> None:
    """Deterministic JSON (stable key order, shortest round-trip floats)."""
    path.write_text(json.dumps(thresholds.to_dict(), indent=2) + "\n", encoding="utf-8")


def load_thresholds(path: Path) -> RegimeThresholds:
    if not path.is_file():
        raise FileNotFoundError(f"no regime-threshold artifact at {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegimeCalibrationError(f"cannot parse {path}: {exc}") from exc
    return RegimeThresholds.from_dict(raw)
