"""Tests for configs/features.yaml and FeatureConfig validation."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from adaptive_portfolio.config import (
    ConfigError,
    FeatureConfig,
    load_feature_config,
    load_project_config,
)
from conftest import CONFIG_DIR, SMALL_FEATURES


def _config(**overrides: Any) -> FeatureConfig:
    raw = copy.deepcopy(SMALL_FEATURES)
    raw.update(overrides)
    return FeatureConfig.from_dict(raw)


def test_default_feature_config_is_valid_for_the_universe() -> None:
    features = load_feature_config(CONFIG_DIR / "features.yaml")
    features.check_universe(load_project_config(CONFIG_DIR).data.universe)
    assert features.market_group == "equity"
    assert features.trend_feature == "equity_mom_63"
    assert features.volatility_feature == "market_vol_21"
    assert features.group("bond") == ("IEF", "TLT", "LQD")
    assert features.output_dir == Path("data/processed/features")
    assert features.allow_multi_session_returns is False
    assert features.windows.max_window() == 126


def test_windows_are_sorted_and_defaults_apply() -> None:
    raw = copy.deepcopy(SMALL_FEATURES)
    raw["windows"] = {"group_momentum": [5, 2], "market_volatility": [3]}
    config = FeatureConfig.from_dict(raw)
    assert config.windows.group_momentum == (2, 5)
    assert config.windows.correlation == 63  # default for an omitted key


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("asset_groups", {}, "non-empty mapping"),
        ("asset_groups", {"Equity": ["AAA"]}, "invalid group name"),
        ("asset_groups", {"market": ["AAA"]}, "reserved"),
        ("asset_groups", {"equity": ["AAA"], "bond": ["AAA"]}, "disjoint"),
        ("asset_groups", {"equity": ["A B"]}, "invalid identifier"),
        ("market_group", "credit", "not one of"),
        ("correlation_groups", ["equity", "equity"], "two different"),
        ("correlation_groups", ["equity"], "two different"),
        ("allow_multi_session_returns", "yes", "true/false"),
        ("unknown_key", 1, "unknown"),
    ],
)
def test_invalid_top_level_values(key: str, value: Any, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        _config(**{key: value})


@pytest.mark.parametrize(
    ("windows", "message"),
    [
        ({"group_momentum": []}, "non-empty list"),
        ({"group_momentum": [5, 5]}, "duplicate"),
        ({"asset_volatility": [1]}, ">= 2"),
        ({"market_volatility": [0]}, ">= 2"),
        ({"correlation": 2}, ">= 3"),
        ({"market_drawdown": 5000}, "<= 2000"),
        ({"asset_momentum": [2.5]}, "integer"),
        ({"typo": [3]}, "unknown"),
    ],
)
def test_invalid_windows(windows: dict[str, Any], message: str) -> None:
    raw = copy.deepcopy(SMALL_FEATURES)
    raw["windows"].update(windows)
    with pytest.raises(ConfigError, match=message):
        FeatureConfig.from_dict(raw)


@pytest.mark.parametrize(
    ("regime", "message"),
    [
        ({"trend_window": 7}, "must be one of"),  # not in group_momentum
        ({"volatility_window": 4}, "must be one of"),  # not in market_volatility
        ({"trend_neutral_quantile": 1.0}, "strictly between"),
        ({"volatility_quantiles": [0.7, 0.3]}, "low must be < high"),
        ({"volatility_quantiles": [0.5]}, r"\[low, high\]"),
        ({"min_calibration_observations": 5}, ">= 10"),
        ({"sparse_regime_fraction": 0.6}, "sparse_regime_fraction"),
        ({"concentration_warning_fraction": 0}, "concentration_warning_fraction"),
    ],
)
def test_invalid_regime_settings(regime: dict[str, Any], message: str) -> None:
    raw = copy.deepcopy(SMALL_FEATURES)
    raw["regime"].update(regime)
    with pytest.raises(ConfigError, match=message):
        FeatureConfig.from_dict(raw)


def test_group_members_must_be_in_universe() -> None:
    config = _config()
    with pytest.raises(ConfigError, match=r"\['CCC'\] not in data.universe"):
        config.check_universe(("AAA", "BBB"))


def test_correlation_can_be_disabled() -> None:
    assert _config(correlation_groups=None).correlation_groups is None
