"""Transparent, training-calibrated market-regime labels (milestone 3).

* ``rules``       - fit thresholds on the training partition, freeze, save/load, apply
* ``diagnostics`` - regime counts, transitions, feature distributions, warnings

Labels combine a trend component (negative / neutral / positive) and a volatility
component (low / normal / high). They are heuristic baseline classifications, not
verified market states. Statistical regime models remain an optional extension.
"""

from adaptive_portfolio.regimes.rules import (
    REGIME_LABELS,
    TREND_LABELS,
    UNAVAILABLE,
    VOLATILITY_LABELS,
    RegimeCalibrationError,
    RegimeThresholds,
    assign_regimes,
    check_compatibility,
    fit_regime_thresholds,
    load_thresholds,
    save_thresholds,
)

__all__ = [
    "REGIME_LABELS",
    "TREND_LABELS",
    "UNAVAILABLE",
    "VOLATILITY_LABELS",
    "RegimeCalibrationError",
    "RegimeThresholds",
    "assign_regimes",
    "check_compatibility",
    "fit_regime_thresholds",
    "load_thresholds",
    "save_thresholds",
]
