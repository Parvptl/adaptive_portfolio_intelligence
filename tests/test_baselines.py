"""Tests for backtest configuration and the conventional baseline strategies."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.baselines import (
    StrategyError,
    cap_and_redistribute,
    decision_rows,
    target_weights,
)
from adaptive_portfolio.config import (
    BacktestConfig,
    ConfigError,
    StrategyConfig,
    load_backtest_config,
    load_project_config,
    load_yaml,
)
from conftest import CONFIG_DIR

BASE = load_yaml(CONFIG_DIR / "backtest.yaml")
UNIVERSE = ("AAA", "BBB", "CCC")


def _strategy(**raw: Any) -> StrategyConfig:
    return StrategyConfig.from_dict(
        {"name": "s", "type": "equal_weight", "rebalance": "monthly", **raw}, 0
    )


def _history(n: int = 30, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        rng.normal(0.0005, [0.005, 0.01, 0.02], size=(n, 3)),
        columns=list(UNIVERSE),
        index=pd.DatetimeIndex(pd.bdate_range("2024-01-02", periods=n), name="date"),
    )


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def test_default_backtest_config_is_valid() -> None:
    backtest = load_backtest_config(CONFIG_DIR / "backtest.yaml")
    project = load_project_config(CONFIG_DIR)
    backtest.check_against(project.data, project.environment)
    assert backtest.execution_lag_sessions == 1  # D-055: proposed primary convention
    assert backtest.periods_per_year is None  # D-023 open: no annualisation by default
    assert [s.name for s in backtest.strategies] == [
        "equal_weight_monthly", "buy_and_hold_equal_weight", "inverse_volatility_monthly",
    ]  # fmt: skip
    assert backtest.strategies[2].min_history == 63


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"execution_lag_sessions": -1}, ">= 0"),
        ({"execution_lag_sessions": 6}, "<= 5"),
        ({"periods_per_year": 0}, "periods_per_year"),
        ({"periods_per_year": 1000}, "periods_per_year"),
        ({"strategies": []}, "non-empty list"),
        ({"charge_initial_funding": "yes"}, "true/false"),
        ({"unknown": 1}, "unknown"),
        ({"execution_lag_sessions": True}, "integer"),
        ({"execution_lag_sessions": 1.5}, "integer"),
    ],
)
def test_invalid_backtest_settings(change: dict[str, Any], message: str) -> None:
    raw = copy.deepcopy(BASE)
    raw.update(change)
    with pytest.raises(ConfigError, match=message):
        BacktestConfig.from_dict(raw)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"type": "momentum"}, "type"),
        ({"rebalance": "weekly"}, "rebalance"),
        ({"name": "Bad Name"}, "lowercase"),
        ({"type": "inverse_volatility"}, "needs 'lookback'"),
        ({"type": "inverse_volatility", "lookback": 1}, ">= 2"),
        ({"lookback": 20}, "only applies to inverse_volatility"),
        ({"type": "fixed_weights"}, "non-empty 'weights'"),
        ({"weights": {"AAA": 1.0}}, "only applies to fixed_weights"),
        ({"type": "fixed_weights", "weights": {"A B": 0.5}}, "invalid identifier"),
    ],
)
def test_invalid_strategy_entries(raw: dict[str, Any], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        _strategy(**raw)


def test_execution_lag_is_required_without_default() -> None:
    # The lag is a research choice (D-055): a config must state it explicitly.
    raw = copy.deepcopy(BASE)
    del raw["execution_lag_sessions"]
    with pytest.raises(ConfigError, match="execution_lag_sessions"):
        BacktestConfig.from_dict(raw)


def test_duplicate_strategy_names_rejected() -> None:
    raw = copy.deepcopy(BASE)
    raw["strategies"].append(dict(raw["strategies"][0]))
    with pytest.raises(ConfigError, match="duplicate names"):
        BacktestConfig.from_dict(raw)


def _check(raw_backtest: dict[str, Any], **environment_overrides: Any) -> None:
    project = load_project_config(CONFIG_DIR)
    env_raw = load_yaml(CONFIG_DIR / "environment.yaml")
    env_raw["constraints"].update(environment_overrides.pop("constraints", {}))
    env_raw.update(environment_overrides)
    from adaptive_portfolio.config import EnvironmentConfig

    BacktestConfig.from_dict({"execution_lag_sessions": 1, **raw_backtest}).check_against(
        project.data, EnvironmentConfig.from_dict(env_raw)
    )


@pytest.mark.parametrize(
    ("strategy", "environment", "message"),
    [
        ({"name": "ew", "type": "equal_weight", "rebalance": "monthly"},
         {"constraints": {"max_weight": 0.1}}, "violates weight bounds"),
        ({"name": "ew", "type": "equal_weight", "rebalance": "daily"},
         {"rebalance_frequency": "weekly"}, "finer than"),
        ({"name": "fw", "type": "fixed_weights", "rebalance": "monthly", "weights": {"XYZ": 0.1}},
         {}, "not in data.universe"),
        ({"name": "fw", "type": "fixed_weights", "rebalance": "monthly",
          "weights": {"SPY": 0.4, "TLT": 0.4, "GLD": 0.4}}, {}, "must be <= 1"),
        ({"name": "fw", "type": "fixed_weights", "rebalance": "monthly", "weights": {"SPY": 0.5}},
         {}, "violate the weight bounds"),
        ({"name": "ew", "type": "equal_weight", "rebalance": "monthly"},
         {"constraints": {"long_only": False}}, "long-only"),
    ],
)  # fmt: skip
def test_cross_checks_with_universe_and_constraints(strategy, environment, message) -> None:
    with pytest.raises(ConfigError, match=message):
        _check({"strategies": [strategy]}, **environment)


def test_fixed_weights_with_cash_accepted() -> None:
    _check({"strategies": [{"name": "fw", "type": "fixed_weights", "rebalance": "monthly",
                            "weights": {"SPY": 0.4, "TLT": 0.4}}]})  # fmt: skip


# --------------------------------------------------------------------------
# Strategy weights
# --------------------------------------------------------------------------


def test_equal_weight() -> None:
    np.testing.assert_allclose(target_weights(_strategy(), _history(), UNIVERSE, 0.4), [1 / 3] * 3)


def test_fixed_weights_unlisted_assets_get_zero() -> None:
    strategy = _strategy(type="fixed_weights", weights={"AAA": 0.25, "CCC": 0.5})
    np.testing.assert_allclose(
        target_weights(strategy, _history(), UNIVERSE, 0.5), [0.25, 0.0, 0.5]
    )


def test_inverse_volatility_hand_calculated() -> None:
    # Window of 3 rows. AAA: [0.01, -0.01, 0.0] -> std 0.01; BBB doubles -> 0.02; CCC x4 -> 0.04.
    # 1/vol = 100, 50, 25 -> weights 100/175, 50/175, 25/175 (no cap with max_weight 0.6).
    base = np.array([0.01, -0.01, 0.0])
    history = pd.DataFrame(
        {"AAA": base, "BBB": 2 * base, "CCC": 4 * base},
        index=pd.DatetimeIndex(pd.bdate_range("2024-01-02", periods=3), name="date"),
    )
    strategy = _strategy(type="inverse_volatility", lookback=3)
    np.testing.assert_allclose(
        target_weights(strategy, history, UNIVERSE, 0.6),
        [100 / 175, 50 / 175, 25 / 175],
        atol=1e-12,
    )


def test_inverse_volatility_uses_only_the_last_lookback_rows() -> None:
    history = _history(40)
    strategy = _strategy(type="inverse_volatility", lookback=10)
    altered = history.copy()
    altered.iloc[:30] = altered.iloc[:30] * 7  # rows outside the lookback window
    np.testing.assert_array_equal(
        target_weights(strategy, history, UNIVERSE, 0.6),
        target_weights(strategy, altered, UNIVERSE, 0.6),
    )


@pytest.mark.parametrize(
    ("raw", "cap", "expected"),
    [
        ([1.0, 1.0, 8.0], 0.4, [0.3, 0.3, 0.4]),  # cap 0.8 -> 0.4, excess spread 1:1
        ([1.0, 4.0, 5.0], 0.4, [0.2, 0.4, 0.4]),  # two rounds: 0.5 then 0.48 capped
        ([1.0, 1.0, 1.0], 0.4, [1 / 3] * 3),  # no cap needed
    ],
)
def test_cap_and_redistribute_hand_calculated(raw, cap, expected) -> None:
    weights = cap_and_redistribute(np.array(raw), cap)
    np.testing.assert_allclose(weights, expected, atol=1e-12)
    assert weights.sum() == pytest.approx(1.0, abs=1e-12)


def test_cap_infeasible() -> None:
    with pytest.raises(StrategyError, match="cannot be fully invested"):
        cap_and_redistribute(np.array([1.0, 1.0]), 0.4)


def test_zero_volatility_is_an_error_not_a_guess() -> None:
    history = _history().assign(BBB=0.001)
    with pytest.raises(StrategyError, match=r"zero volatility for \['BBB'\]"):
        target_weights(_strategy(type="inverse_volatility", lookback=5), history, UNIVERSE, 0.6)


def test_insufficient_history_and_column_mismatch() -> None:
    strategy = _strategy(type="inverse_volatility", lookback=50)
    with pytest.raises(StrategyError, match="needs 50 return rows"):
        target_weights(strategy, _history(30), UNIVERSE, 0.6)
    with pytest.raises(StrategyError, match="columns"):
        target_weights(_strategy(), _history()[["BBB", "AAA", "CCC"]], UNIVERSE, 0.6)


def test_weights_at_k_ignore_future_returns() -> None:
    returns = _history(60)
    strategy = _strategy(type="inverse_volatility", lookback=20)
    k = 35
    altered = returns.copy()
    altered.iloc[k + 1 :] = 0.3 * np.sign(altered.iloc[k + 1 :]) - 0.1
    np.testing.assert_array_equal(
        target_weights(strategy, returns.iloc[: k + 1], UNIVERSE, 0.6),
        target_weights(strategy, altered.iloc[: k + 1], UNIVERSE, 0.6),
    )


# --------------------------------------------------------------------------
# Rebalancing schedules
# --------------------------------------------------------------------------

DATES = pd.DatetimeIndex(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02", "2024-03-01"])


def test_schedules() -> None:
    assert decision_rows("never", DATES, 1, 4) == [1]
    assert decision_rows("daily", DATES, 1, 4) == [1, 2, 3, 4]
    # Start at row 1 (Jan 31), then the first session of February (row 2) and of March (row 4).
    assert decision_rows("monthly", DATES, 1, 4) == [1, 2, 4]
    assert decision_rows("monthly", DATES, 3, 2) == []
