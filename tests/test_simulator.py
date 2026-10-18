"""Tests for the portfolio simulator and per-window performance summary.

Expected values are derived by hand in the comments.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import ConstraintsConfig
from adaptive_portfolio.evaluation.metrics import (
    annualized_return,
    annualized_volatility,
    cumulative_return,
    max_drawdown,
    portfolio_turnover,
    sharpe_ratio,
)
from adaptive_portfolio.evaluation.performance import summarize_window
from adaptive_portfolio.evaluation.simulator import (
    SimulationError,
    SimulationSettings,
    simulate,
)

TOL = 1e-12
OPEN = ConstraintsConfig(
    long_only=True, allow_cash=True, min_weight=0.0, max_weight=1.0, max_turnover=None
)
FIXTURE = pd.DataFrame(
    {"A": [0.0, 0.10, -0.05, 0.02], "B": [0.0, 0.00, 0.10, 0.00]},
    index=pd.DatetimeIndex(pd.bdate_range("2024-01-01", periods=4), name="date"),
)
HALF = np.array([0.5, 0.5])


def _settings(**overrides) -> SimulationSettings:
    values = {"initial_capital": 100.0, "cost_rate": 0.001, "cash_return": 0.0, "constraints": OPEN}
    values.update(overrides)
    return SimulationSettings(**values)


def _run(targets, *, lag=0, window=(0, 3), returns=FIXTURE, **settings):
    return simulate(returns, targets, lag=lag, window=window, settings=_settings(**settings))


# --------------------------------------------------------------------------
# Hand-calculated accounting
# --------------------------------------------------------------------------


def test_ledger_hand_calculated() -> None:
    ledger = _run({0: HALF, 2: HALF}).ledger
    # Row 0 (funding): buy 50/50 from cash -> traded 1.0, cost 0.001, value 99.9.
    # Row 1: gross 0.5*0.10 = 0.05; A drifts to 0.55/1.05 = 11/21.
    # Row 2: gross 11/21*(-0.05) + 10/21*0.10 = 0.45/21. Drifted A = 10.45/21.45; trading back
    #        to 0.5 needs 2*(0.5 - 10.45/21.45) = 0.55/21.45 of traded notional.
    # Row 3: gross 0.5*0.02 = 0.01, no trade.
    g2 = 0.45 / 21
    traded2 = 0.55 / 21.45
    np.testing.assert_allclose(ledger["gross_return"], [0.0, 0.05, g2, 0.01], atol=TOL)
    np.testing.assert_allclose(ledger["traded_notional"], [1.0, 0.0, traded2, 0.0], atol=TOL)
    np.testing.assert_allclose(
        ledger["cost_fraction"], [0.001, 0.0, 0.001 * traded2, 0.0], atol=TOL
    )
    net2 = (1 + g2) * (1 - 0.001 * traded2) - 1
    np.testing.assert_allclose(ledger["net_return"], [-0.001, 0.05, net2, 0.01], atol=TOL)
    expected_values = 100 * np.cumprod([0.999, 1.05, 1 + net2, 1.01])
    np.testing.assert_allclose(ledger["value"], expected_values, atol=1e-9)
    np.testing.assert_allclose(
        ledger.loc[1, ["weight_A", "weight_B"]].to_numpy(dtype=float), [11 / 21, 10 / 21], atol=TOL
    )
    assert ledger["rebalanced"].tolist() == [True, False, True, False]
    # Two-way turnover counts the cash leg on funding (0.5 + 0.5 + 1.0 = 2.0).
    np.testing.assert_allclose(ledger["turnover_two_way"], [2.0, 0.0, traded2, 0.0], atol=TOL)


def test_value_identity_and_drawdown() -> None:
    ledger = _run({0: HALF, 2: HALF}).ledger
    assert np.prod(1 + ledger["net_return"]) == pytest.approx(
        ledger["value"].iloc[-1] / 100, abs=TOL
    )
    # Drawdown is measured from the running peak, starting at initial capital 100.
    assert ledger["drawdown"].iloc[0] == pytest.approx(-0.001, abs=TOL)
    assert (ledger["drawdown"] <= 0).all()


def test_cost_reuses_milestone1_turnover() -> None:
    ledger = _run({0: HALF, 2: np.array([0.8, 0.2])}).ledger
    pre = np.array([[10.45 / 21.45, 11 / 21.45, 0.0]])
    post = np.array([[0.8, 0.2, 0.0]])
    expected = portfolio_turnover(pre, post, cash_column=2)[0]
    assert ledger.loc[2, "traded_notional"] == pytest.approx(expected, abs=TOL)
    assert ledger.loc[2, "cost_fraction"] == pytest.approx(0.001 * expected, abs=TOL)


def test_uncharged_initial_funding() -> None:
    ledger = _run({0: HALF}, charge_initial_funding=False).ledger
    assert ledger.loc[0, "cost_fraction"] == 0.0
    assert ledger.loc[0, "traded_notional"] == 1.0  # still recorded


def test_cash_weight_earns_cash_return_and_costs_ignore_cash_leg() -> None:
    # 50 % A, 50 % cash; cash earns 0.001 per session.
    ledger = _run({0: np.array([0.5, 0.0])}, cash_return=0.001).ledger
    assert ledger.loc[0, "traded_notional"] == 0.5  # only the A purchase is traded notional
    assert ledger.loc[1, "gross_return"] == pytest.approx(0.5 * 0.10 + 0.5 * 0.001, abs=TOL)


def test_zero_cost_gross_equals_net() -> None:
    ledger = _run({0: HALF, 2: HALF}, cost_rate=0.0).ledger
    np.testing.assert_array_equal(ledger["gross_return"], ledger["net_return"])


# --------------------------------------------------------------------------
# Temporal alignment (D-048)
# --------------------------------------------------------------------------

SPIKE = pd.DataFrame(
    {"A": [0.0, 0.0, 0.50, 0.01, 0.02], "B": [0.0] * 5},
    index=pd.DatetimeIndex(pd.bdate_range("2024-01-01", periods=5), name="date"),
)


def test_weight_never_earns_a_return_dated_at_or_before_execution() -> None:
    # Hold B, then decide at row 2 to hold A. Row 2's +50 % A return is already in the past
    # at the close of row 2, so it must not be earned. The first A return earned is row 3.
    ledger = _run(
        {0: np.array([0.0, 1.0]), 2: np.array([1.0, 0.0])}, returns=SPIKE, window=(0, 4)
    ).ledger
    assert ledger.loc[2, "gross_return"] == 0.0
    assert ledger.loc[3, "gross_return"] == pytest.approx(0.01, abs=TOL)


def test_execution_lag_delays_the_effective_weights() -> None:
    # With lag 1, the decision at row 1 executes at row 2 and first earns row 3.
    ledger = _run(
        {0: np.array([0.0, 1.0]), 1: np.array([1.0, 0.0])}, lag=1, returns=SPIKE, window=(1, 4)
    ).ledger
    assert ledger["date"].iloc[0] == SPIKE.index[1]  # funding row = first execution (row 1)
    assert ledger.loc[ledger["date"] == SPIKE.index[2], "gross_return"].item() == 0.0
    assert ledger.loc[ledger["date"] == SPIKE.index[3], "gross_return"].item() == pytest.approx(
        0.01
    )
    assert ledger.loc[ledger["date"] == SPIKE.index[2], "decision_date"].item() == SPIKE.index[1]


def test_returns_outside_the_window_are_never_used() -> None:
    altered = SPIKE.copy()
    altered.iloc[4] = [9.0, 9.0]  # beyond the window's last row 3
    base = _run({0: HALF}, returns=SPIKE, window=(0, 3)).ledger
    other = _run({0: HALF}, returns=altered, window=(0, 3)).ledger
    pd.testing.assert_frame_equal(base, other)


@pytest.mark.parametrize(
    ("targets", "lag", "window", "message"),
    [
        ({0: HALF, 3: HALF}, 0, (0, 3), "outside"),  # executes on the last row: would earn row 4
        ({0: HALF, 2: HALF}, 1, (1, 3), "outside"),  # executes at row 3 = last row
        ({1: HALF}, 0, (0, 3), "funding"),  # nothing executes at the first row
        ({0: HALF}, 0, (2, 2), "invalid evaluation window"),
        ({0: HALF}, -1, (0, 3), "lag"),
    ],
)
def test_invalid_schedules_rejected(targets, lag, window, message) -> None:
    with pytest.raises(SimulationError, match=message):
        _run(targets, lag=lag, window=window)


# --------------------------------------------------------------------------
# Invalid inputs and states
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        (np.array([-0.1, 1.1]), "below min_weight"),
        (np.array([0.7, 0.7]), "leverage"),
        (np.array([np.nan, 0.5]), "finite"),
        (np.array([0.5, 0.25, 0.25]), "shape"),
    ],
)
def test_invalid_targets_rejected(weights, message) -> None:
    with pytest.raises(SimulationError, match=message):
        _run({0: weights})


def test_max_weight_and_no_cash_constraints() -> None:
    capped = ConstraintsConfig(
        long_only=True, allow_cash=False, min_weight=0.0, max_weight=0.6, max_turnover=None
    )
    with pytest.raises(SimulationError, match="above max_weight"):
        _run({0: np.array([0.7, 0.3])}, constraints=capped)
    with pytest.raises(SimulationError, match="cash is not allowed"):
        _run({0: np.array([0.5, 0.4])}, constraints=capped)


def test_invalid_returns_rejected() -> None:
    with pytest.raises(SimulationError, match="non-finite"):
        _run({0: HALF}, returns=FIXTURE.assign(A=[0.0, np.nan, 0.0, 0.0]))
    duplicated = FIXTURE.copy()
    duplicated.index = pd.DatetimeIndex(["2024-01-01", "2024-01-01", "2024-01-03", "2024-01-04"])
    with pytest.raises(SimulationError, match="unique and increasing"):
        _run({0: HALF}, returns=duplicated)


def test_total_loss_is_an_invalid_state() -> None:
    wipeout = FIXTURE.assign(A=[0.0, -1.0, 0.0, 0.0], B=[0.0, -1.0, 0.0, 0.0])
    with pytest.raises(SimulationError, match="<= 0"):
        _run({0: HALF}, returns=wipeout)


def test_deterministic_and_no_mutation() -> None:
    returns = FIXTURE.copy()
    targets = {0: HALF.copy(), 2: HALF.copy()}
    first = _run(targets, returns=returns).ledger
    second = _run(targets, returns=returns).ledger
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(returns, FIXTURE)
    np.testing.assert_array_equal(targets[0], HALF)


# --------------------------------------------------------------------------
# Performance summary reuses milestone-1 metrics
# --------------------------------------------------------------------------


def _long_ledger() -> pd.DataFrame:
    rng = np.random.default_rng(5)
    returns = pd.DataFrame(
        rng.normal(0.0005, 0.01, size=(30, 2)),
        columns=["A", "B"],
        index=pd.DatetimeIndex(pd.bdate_range("2024-01-01", periods=30), name="date"),
    )
    return _run({0: HALF, 10: HALF, 20: HALF}, returns=returns, window=(0, 29)).ledger


def test_summary_matches_milestone1_functions() -> None:
    ledger = _long_ledger()
    summary = summarize_window(
        ledger, initial_capital=100.0, annual_risk_free_rate=0.0, periods_per_year=None
    )
    net_path = np.r_[100.0, ledger["value"]]
    gross_path = 100.0 * np.r_[1.0, np.cumprod(1 + ledger["gross_return"])]
    earning = ledger["net_return"].to_numpy()[1:]
    assert summary["net_cumulative_return"] == cumulative_return(net_path)
    assert summary["gross_cumulative_return"] == cumulative_return(gross_path)
    assert summary["net_max_drawdown"] == max_drawdown(net_path).max_drawdown
    assert summary["net_volatility_per_session"] == annualized_volatility(earning, 1)
    assert summary["net_sharpe_per_session_rf0"] == sharpe_ratio(earning, 1)
    assert summary["rebalances"] == 3
    assert summary["total_traded_notional"] == pytest.approx(
        ledger["traded_notional"].sum(), abs=TOL
    )
    assert summary["cost_drag"] > 0  # costs make net < gross
    assert summary["annualised"] is None
    assert any("D-023" in note for note in summary["notes"])


def test_annualised_metrics_only_when_configured() -> None:
    ledger = _long_ledger()
    summary = summarize_window(
        ledger, initial_capital=100.0, annual_risk_free_rate=0.0, periods_per_year=252
    )
    annual = summary["annualised"]
    assert annual["status"].startswith("provisional")
    net_path = np.r_[100.0, ledger["value"]]
    assert annual["net_annualised_return"] == annualized_return(net_path, 252)
    assert annual["net_sharpe"] == pytest.approx(
        sharpe_ratio(ledger["net_return"].to_numpy()[1:], 252, annual_risk_free_rate=0.0)
    )


def test_nonzero_risk_free_without_annualisation_omits_sharpe() -> None:
    summary = summarize_window(
        _long_ledger(), initial_capital=100.0, annual_risk_free_rate=0.02, periods_per_year=None
    )
    assert summary["net_sharpe_per_session_rf0"] is None


def test_zero_volatility_sharpe_is_undefined_not_infinite() -> None:
    flat = pd.DataFrame(
        {"A": [0.0] * 5, "B": [0.0] * 5},
        index=pd.DatetimeIndex(pd.bdate_range("2024-01-01", periods=5), name="date"),
    )
    ledger = _run({0: HALF}, returns=flat, window=(0, 4), cost_rate=0.0).ledger
    summary = summarize_window(
        ledger, initial_capital=100.0, annual_risk_free_rate=0.0, periods_per_year=None
    )
    assert summary["net_sharpe_per_session_rf0"] is None
    assert summary["net_volatility_per_session"] == 0.0
    assert not any(math.isinf(v) for v in summary.values() if isinstance(v, float))
