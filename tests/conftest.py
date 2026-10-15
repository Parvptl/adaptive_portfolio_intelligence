"""Shared pytest fixtures."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from adaptive_portfolio.config import load_yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "configs"


@pytest.fixture
def config_dir() -> Path:
    return CONFIG_DIR


@pytest.fixture
def data_raw() -> dict[str, Any]:
    """A fresh, mutable copy of the default data config."""
    return copy.deepcopy(load_yaml(CONFIG_DIR / "data.yaml"))


@pytest.fixture
def environment_raw() -> dict[str, Any]:
    return copy.deepcopy(load_yaml(CONFIG_DIR / "environment.yaml"))


@pytest.fixture
def experiment_raw() -> dict[str, Any]:
    return copy.deepcopy(load_yaml(CONFIG_DIR / "experiment.yaml"))


# --------------------------------------------------------------------------
# Market-data fixtures (milestone 2). Everything is offline and deterministic.
# --------------------------------------------------------------------------

FIXTURE_DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
FIXTURE_PRICES = {
    # Hand-calculable paths; BBB has no price on 2024-01-05 (a missing cell).
    "AAA": [100.0, 110.0, 99.0, 99.0, 108.9],
    "BBB": [50.0, 50.0, 55.0, None, 44.0],
}


def fixture_frame(ticker: str) -> pd.DataFrame:
    """Raw frame for the hand-calculated fixture (dates plus close and adj_close)."""
    prices = FIXTURE_PRICES[ticker]
    return pd.DataFrame(
        {
            "date": pd.to_datetime(FIXTURE_DATES),
            "close": prices,
            "adj_close": prices,
            "volume": 1000.0,
        }
    )


@pytest.fixture
def fixture_frames() -> dict[str, pd.DataFrame]:
    return {ticker: fixture_frame(ticker) for ticker in FIXTURE_PRICES}


def write_tiny_project(
    root: Path,
    *,
    universe: list[str],
    start: str,
    end: str,
    splits: dict[str, dict[str, str]],
    provider: str = "synthetic",
    data_overrides: dict[str, Any] | None = None,
) -> Path:
    """Create ``root/configs`` with small, valid config files; return the config dir."""
    configs = root / "configs"
    configs.mkdir(parents=True, exist_ok=True)
    data = copy.deepcopy(load_yaml(CONFIG_DIR / "data.yaml"))
    data.update(provider=provider, universe=universe, start_date=start, end_date=end)
    data["validation"] = {**data.get("validation", {}), "min_sessions": 2}
    data.update(data_overrides or {})
    experiment = copy.deepcopy(load_yaml(CONFIG_DIR / "experiment.yaml"))
    experiment["splits"] = splits
    environment = copy.deepcopy(load_yaml(CONFIG_DIR / "environment.yaml"))
    for name, content in (
        ("data.yaml", data),
        ("experiment.yaml", experiment),
        ("environment.yaml", environment),
    ):
        (configs / name).write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")
    return configs


FIXTURE_SPLITS = {
    "train": {"start": "2024-01-01", "end": "2024-01-03"},
    "validation": {"start": "2024-01-04", "end": "2024-01-05"},
    "test": {"start": "2024-01-06", "end": "2024-01-10"},
}


@pytest.fixture
def fixture_project(tmp_path: Path) -> Path:
    """Config dir for the hand-calculated fixture, with the drop_sessions policy."""
    return write_tiny_project(
        tmp_path,
        universe=["AAA", "BBB"],
        start="2024-01-01",
        end="2024-01-10",
        splits=FIXTURE_SPLITS,
        provider="csv",
        data_overrides={"missing_data": {"policy": "drop_sessions", "max_dropped_sessions": 1}},
    )


@pytest.fixture
def synthetic_project(tmp_path: Path) -> Path:
    """Config dir for a two-month synthetic dataset (weekday sessions)."""
    return write_tiny_project(
        tmp_path,
        universe=["AAA", "BBB", "CCC"],
        start="2024-01-01",
        end="2024-02-29",
        splits={
            "train": {"start": "2024-01-01", "end": "2024-01-31"},
            "validation": {"start": "2024-02-01", "end": "2024-02-14"},
            "test": {"start": "2024-02-15", "end": "2024-02-29"},
        },
    )
