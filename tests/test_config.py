"""Tests for configuration loading and validation."""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from typing import Any

import pytest

from adaptive_portfolio.config import (
    DEFAULT_CONFIG_DIR,
    ConfigError,
    DataConfig,
    EnvironmentConfig,
    ExperimentConfig,
    ProjectConfig,
    load_project_config,
    load_yaml,
)

# --------------------------------------------------------------- defaults ----


def test_default_configs_load(config_dir: Path) -> None:
    config = load_project_config(config_dir)
    assert isinstance(config, ProjectConfig)
    assert config.data.universe
    assert config.environment.initial_capital > 0
    assert isinstance(config.experiment.seed, int)


def test_default_config_dir_points_at_repo_configs(config_dir: Path) -> None:
    assert DEFAULT_CONFIG_DIR.resolve() == config_dir.resolve()
    load_project_config()  # uses the default directory


def test_default_splits_are_chronological(config_dir: Path) -> None:
    splits = load_project_config(config_dir).experiment.splits
    assert splits.train.end < splits.validation.start
    assert splits.validation.end < splits.test.start


def test_default_data_provider_needs_no_network(config_dir: Path) -> None:
    # CI must not depend on external market data or credentials.
    assert load_project_config(config_dir).data.provider == "csv"


def test_dates_are_parsed(config_dir: Path) -> None:
    data = load_project_config(config_dir).data
    assert isinstance(data.start_date, dt.date)
    assert isinstance(data.end_date, dt.date)


# ------------------------------------------------------------ file errors ----


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_yaml(tmp_path / "missing.yaml")


def test_non_mapping_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_yaml(path)


def test_malformed_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("key: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="parse"):
        load_yaml(path)


# ------------------------------------------------------- data validation ----


def test_unknown_key_rejected(data_raw: dict[str, Any]) -> None:
    data_raw["frequncy"] = "daily"  # typo
    with pytest.raises(ConfigError, match="unknown"):
        DataConfig.from_dict(data_raw)


def test_missing_key_rejected(data_raw: dict[str, Any]) -> None:
    del data_raw["universe"]
    with pytest.raises(ConfigError, match="missing"):
        DataConfig.from_dict(data_raw)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("provider", "bloomberg"),
        ("frequency", "hourly"),
        ("universe", []),
        ("universe", ["SPY", "spy"]),
        ("start_date", "2007-13-01"),
        ("end_date", "2000-01-01"),
    ],
)
def test_invalid_data_values_rejected(data_raw: dict[str, Any], key: str, value: Any) -> None:
    data_raw[key] = value
    with pytest.raises(ConfigError):
        DataConfig.from_dict(data_raw)


# ------------------------------------------------ environment validation ----


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("initial_capital", math.nan),
        ("initial_capital", math.inf),
        ("initial_capital", 0),
        ("initial_capital", -1000),
        ("initial_capital", "lots"),
        ("transaction_cost_bps", -1),
        ("transaction_cost_bps", 5000),
        ("transaction_cost_bps", True),
        ("slippage_bps", -0.5),
        ("rebalance_frequency", "hourly"),
        ("risk_free_rate", 5.0),  # percent instead of decimal
    ],
)
def test_invalid_environment_values_rejected(
    environment_raw: dict[str, Any], key: str, value: Any
) -> None:
    environment_raw[key] = value
    with pytest.raises(ConfigError):
        EnvironmentConfig.from_dict(environment_raw)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("max_weight", 0),
        ("max_weight", 1.5),
        ("min_weight", -0.1),  # short weight while long_only
        ("min_weight", 0.5),  # exceeds default max_weight of 0.4
        ("min_weight", math.nan),
        ("max_weight", math.inf),
        ("max_turnover", 0),
        ("max_turnover", 3),
        ("long_only", "yes"),
    ],
)
def test_invalid_constraints_rejected(
    environment_raw: dict[str, Any], key: str, value: Any
) -> None:
    environment_raw["constraints"][key] = value
    with pytest.raises(ConfigError):
        EnvironmentConfig.from_dict(environment_raw)


def test_unbounded_short_weight_rejected(environment_raw: dict[str, Any]) -> None:
    environment_raw["constraints"]["long_only"] = False
    environment_raw["constraints"]["min_weight"] = -5
    with pytest.raises(ConfigError, match=">= -1"):
        EnvironmentConfig.from_dict(environment_raw)


def test_short_weight_allowed_when_not_long_only(environment_raw: dict[str, Any]) -> None:
    environment_raw["constraints"]["long_only"] = False
    environment_raw["constraints"]["min_weight"] = -0.2
    config = EnvironmentConfig.from_dict(environment_raw)
    assert config.constraints.min_weight == -0.2


# ------------------------------------------------- experiment validation ----


@pytest.mark.parametrize("seed", [-1, 2**32, 1.5, "42", True])
def test_invalid_seed_rejected(experiment_raw: dict[str, Any], seed: Any) -> None:
    experiment_raw["seed"] = seed
    with pytest.raises(ConfigError, match="seed"):
        ExperimentConfig.from_dict(experiment_raw)


def test_overlapping_train_validation_rejected(experiment_raw: dict[str, Any]) -> None:
    experiment_raw["splits"]["validation"]["start"] = "2016-06-01"
    with pytest.raises(ConfigError, match="train must end before validation"):
        ExperimentConfig.from_dict(experiment_raw)


def test_test_before_validation_rejected(experiment_raw: dict[str, Any]) -> None:
    experiment_raw["splits"]["test"] = {"start": "2010-01-01", "end": "2012-12-31"}
    with pytest.raises(ConfigError, match="validation must end before test"):
        ExperimentConfig.from_dict(experiment_raw)


def test_inverted_split_period_rejected(experiment_raw: dict[str, Any]) -> None:
    experiment_raw["splits"]["train"] = {"start": "2016-12-31", "end": "2007-01-01"}
    with pytest.raises(ConfigError, match="start must be before end"):
        ExperimentConfig.from_dict(experiment_raw)


def test_invalid_walk_forward_scheme_rejected(experiment_raw: dict[str, Any]) -> None:
    experiment_raw["walk_forward"]["scheme"] = "random"
    with pytest.raises(ConfigError, match="scheme"):
        ExperimentConfig.from_dict(experiment_raw)


# ------------------------------------------------- cross-file validation ----


def _build(
    data_raw: dict[str, Any], environment_raw: dict[str, Any], experiment_raw: dict[str, Any]
) -> ProjectConfig:
    return ProjectConfig(
        data=DataConfig.from_dict(data_raw),
        environment=EnvironmentConfig.from_dict(environment_raw),
        experiment=ExperimentConfig.from_dict(experiment_raw),
    )


def test_splits_outside_data_window_rejected(
    data_raw: dict[str, Any], environment_raw: dict[str, Any], experiment_raw: dict[str, Any]
) -> None:
    data_raw["end_date"] = "2022-12-31"  # test period ends in 2024
    with pytest.raises(ConfigError, match="within data"):
        _build(data_raw, environment_raw, experiment_raw)


def test_rebalance_finer_than_data_rejected(
    data_raw: dict[str, Any], environment_raw: dict[str, Any], experiment_raw: dict[str, Any]
) -> None:
    data_raw["frequency"] = "monthly"
    environment_raw["rebalance_frequency"] = "daily"
    with pytest.raises(ConfigError, match="finer"):
        _build(data_raw, environment_raw, experiment_raw)


def test_infeasible_weights_without_cash_rejected(
    data_raw: dict[str, Any], environment_raw: dict[str, Any], experiment_raw: dict[str, Any]
) -> None:
    data_raw["universe"] = ["SPY", "TLT"]
    environment_raw["constraints"]["allow_cash"] = False
    environment_raw["constraints"]["max_weight"] = 0.4  # 2 * 0.4 < 1
    with pytest.raises(ConfigError, match="Infeasible"):
        _build(data_raw, environment_raw, experiment_raw)
