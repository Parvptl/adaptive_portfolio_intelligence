"""Tests for the milestone-2 extensions of the data configuration."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from adaptive_portfolio.config import ConfigError, DataConfig, load_project_config


def test_default_config_has_pipeline_sections(config_dir: Path) -> None:
    data = load_project_config(config_dir).data
    assert data.provider == "csv"  # default runs never need network access
    assert data.universe == ("SPY", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD")
    assert data.price_field == "adj_close"
    assert data.cache.mode == "use"
    assert (data.missing_data.policy, data.missing_data.max_dropped_sessions) == ("error", 0)
    assert data.validation.max_abs_return == 0.4
    assert data.provider_options.max_retries == 3


def test_optional_sections_default_when_absent(data_raw: dict[str, Any]) -> None:
    for key in ("provider_options", "cache", "missing_data", "validation"):
        data_raw.pop(key, None)
    data = DataConfig.from_dict(data_raw)
    assert data.cache.mode == "use"
    assert data.missing_data.policy == "error"
    assert data.validation.min_sessions == 1000
    assert data.provider_options.input_dir == Path("data/raw/csv_input")


def test_empty_yaml_section_means_defaults(data_raw: dict[str, Any]) -> None:
    data_raw["cache"] = None  # "cache:" with nothing under it in YAML
    assert DataConfig.from_dict(data_raw).cache.mode == "use"


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("cache", {"mod": "use"}),  # typo in a nested key
        ("missing_data", {"policy": "error", "fill": "ffill"}),
        ("validation", {"max_abs_ret": 0.4}),
        ("provider_options", {"api_key": "x"}),
    ],
    ids=["cache", "missing_data", "validation", "provider_options"],
)
def test_unknown_nested_key_rejected(data_raw: dict[str, Any], section: str, value: Any) -> None:
    data_raw[section] = value
    with pytest.raises(ConfigError, match="unknown"):
        DataConfig.from_dict(data_raw)


@pytest.mark.parametrize("section", ["cache", "missing_data", "validation", "provider_options"])
def test_section_must_be_a_mapping(data_raw: dict[str, Any], section: str) -> None:
    data_raw[section] = ["use"]
    with pytest.raises(ConfigError, match="mapping"):
        DataConfig.from_dict(data_raw)


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("cache", "mode", "sometimes", "data.cache.mode"),
        ("missing_data", "policy", "forward_fill", "data.missing_data.policy"),
        ("missing_data", "max_dropped_sessions", -1, ">= 0"),
        ("missing_data", "max_dropped_sessions", 2.5, "integer"),
        ("missing_data", "max_dropped_sessions", True, "integer"),
        ("validation", "max_abs_return", 0, "max_abs_return"),
        ("validation", "max_abs_return", math.nan, "finite"),
        ("validation", "min_sessions", 1, ">= 2"),
        ("validation", "max_calendar_gap_days", 0, ">= 1"),
        ("validation", "max_start_lag_days", -3, ">= 0"),
        ("provider_options", "timeout_seconds", 0, "timeout_seconds"),
        ("provider_options", "max_retries", 11, "<= 10"),
        ("provider_options", "retry_delay_seconds", -1, "retry_delay_seconds"),
        ("provider_options", "input_dir", "", "non-empty"),
    ],
)
def test_invalid_nested_values_rejected(
    data_raw: dict[str, Any], section: str, key: str, value: Any, message: str
) -> None:
    data_raw[section] = {**(data_raw.get(section) or {}), key: value}
    if section == "missing_data" and key == "max_dropped_sessions":
        data_raw[section]["policy"] = "drop_sessions"
    with pytest.raises(ConfigError, match=message):
        DataConfig.from_dict(data_raw)


def test_max_dropped_sessions_requires_drop_policy(data_raw: dict[str, Any]) -> None:
    data_raw["missing_data"] = {"policy": "error", "max_dropped_sessions": 3}
    with pytest.raises(ConfigError, match="drop_sessions"):
        DataConfig.from_dict(data_raw)


@pytest.mark.parametrize("field", ["open", "Adj Close", "total_return"])
def test_unsupported_price_field_rejected(data_raw: dict[str, Any], field: str) -> None:
    data_raw["price_field"] = field
    with pytest.raises(ConfigError, match="price_field"):
        DataConfig.from_dict(data_raw)


def test_synthetic_provider_accepted(data_raw: dict[str, Any]) -> None:
    data_raw["provider"] = "synthetic"
    assert DataConfig.from_dict(data_raw).provider == "synthetic"


@pytest.mark.parametrize(
    "ticker", ["SP Y", "../SPY", "A/B", "A\\B", "TOO-LONG-IDENTIFIER-XX", "$X"]
)
def test_invalid_identifiers_rejected(data_raw: dict[str, Any], ticker: str) -> None:
    data_raw["universe"] = ["SPY", ticker]
    with pytest.raises(ConfigError, match="invalid identifier"):
        DataConfig.from_dict(data_raw)


def test_valid_identifier_forms_accepted(data_raw: dict[str, Any]) -> None:
    data_raw["universe"] = ["brk-b", "^GSPC", "EURUSD=X", "BF.B"]
    assert DataConfig.from_dict(data_raw).universe == ("BRK-B", "^GSPC", "EURUSD=X", "BF.B")


def test_raw_and_processed_dirs_must_differ(data_raw: dict[str, Any]) -> None:
    data_raw["processed_data_dir"] = data_raw["raw_data_dir"]
    with pytest.raises(ConfigError, match="must differ"):
        DataConfig.from_dict(data_raw)


@pytest.mark.parametrize("value", [123, None, ""])
def test_invalid_path_values_rejected(data_raw: dict[str, Any], value: Any) -> None:
    data_raw["raw_data_dir"] = value
    with pytest.raises(ConfigError, match="raw_data_dir"):
        DataConfig.from_dict(data_raw)
