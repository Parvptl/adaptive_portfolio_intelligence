"""Shared pytest fixtures."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

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
