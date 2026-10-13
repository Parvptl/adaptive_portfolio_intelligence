"""Smoke tests: the package and all planned subpackages import cleanly."""

from __future__ import annotations

import importlib

import pytest

import adaptive_portfolio

SUBPACKAGES = [
    "data",
    "features",
    "regimes",
    "environment",
    "agents",
    "baselines",
    "evaluation",
    "explainability",
    "visualization",
]


def test_version_is_defined() -> None:
    assert isinstance(adaptive_portfolio.__version__, str)
    assert adaptive_portfolio.__version__


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    module = importlib.import_module(f"adaptive_portfolio.{name}")
    assert module.__doc__, f"adaptive_portfolio.{name} should document its responsibility"


def test_config_module_imports() -> None:
    importlib.import_module("adaptive_portfolio.config")
