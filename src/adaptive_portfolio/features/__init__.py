"""Causal, interpretable market features (milestone 3).

* ``engineering`` - rolling primitives and the configured feature set
* ``alignment``   - pairing features at t with the next return r_{t+1}, without leakage
* ``pipeline``    - features + regimes on a processed dataset, with diagnostics

Timing convention (D-043): a feature dated t uses only return rows dated <= t. See
docs/technical_handbook.md, section 12.
"""

from adaptive_portfolio.features.alignment import BOUNDARY, next_period_targets
from adaptive_portfolio.features.engineering import (
    FeatureDataError,
    FeatureDefinition,
    FeatureSet,
    availability_summary,
    build_features,
    compound_return,
    cross_sectional_dispersion,
    downside_volatility,
    rolling_correlation,
    rolling_drawdown,
    rolling_volatility,
)

__all__ = [
    "BOUNDARY",
    "FeatureDataError",
    "FeatureDefinition",
    "FeatureSet",
    "availability_summary",
    "build_features",
    "compound_return",
    "cross_sectional_dispersion",
    "downside_volatility",
    "next_period_targets",
    "rolling_correlation",
    "rolling_drawdown",
    "rolling_volatility",
]
