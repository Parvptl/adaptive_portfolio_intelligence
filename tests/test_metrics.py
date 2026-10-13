"""Tests for adaptive_portfolio.evaluation.metrics.

Expected values are derived by hand in the comments next to each case, not
taken from the implementation.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest

from adaptive_portfolio.evaluation import (
    MaxDrawdown,
    UndefinedMetricError,
    annual_to_periodic_rate,
    annualized_return,
    annualized_volatility,
    cumulative_return,
    drawdown_series,
    max_drawdown,
    portfolio_returns,
    sharpe_ratio,
)

TOL = 1e-12  # absolute tolerance for hand-computed decimals

# ==========================================================================
# Shared input validation
# ==========================================================================

VALUE_FUNCTIONS: list[Callable[[Any], Any]] = [
    portfolio_returns,
    drawdown_series,
    max_drawdown,
    cumulative_return,
    lambda v: annualized_return(v, 12),
]
RETURN_FUNCTIONS: list[Callable[[Any], Any]] = [
    lambda r: annualized_volatility(r, 12),
    lambda r: sharpe_ratio(r, 12),
]
ALL_FUNCTIONS = VALUE_FUNCTIONS + RETURN_FUNCTIONS

BAD_TYPES = [
    None,
    "100,110",
    [True, False, True],
    ["a", "b"],
    [1.0, None],  # object dtype: missing value disguised as None
    [1 + 1j, 2 + 0j],
    {},
]

BAD_VALUES_FOR_ALL = [
    [],  # empty
    5.0,  # scalar, not a sequence
    [[0.01, 0.02], [0.03, 0.04]],  # 2-D
    [[0.01], [0.02, 0.03]],  # ragged
    [0.01, math.nan, 0.02],
    [0.01, math.inf, 0.02],
    [0.01, -math.inf, 0.02],
]


@pytest.mark.parametrize("function", ALL_FUNCTIONS)
@pytest.mark.parametrize("bad", BAD_TYPES, ids=repr)
def test_non_numeric_input_raises_type_error(function: Callable[[Any], Any], bad: Any) -> None:
    with pytest.raises(TypeError):
        function(bad)


@pytest.mark.parametrize("function", ALL_FUNCTIONS)
@pytest.mark.parametrize("bad", BAD_VALUES_FOR_ALL, ids=repr)
def test_invalid_shape_or_non_finite_raises_value_error(
    function: Callable[[Any], Any], bad: Any
) -> None:
    with pytest.raises(ValueError):
        function(bad)


@pytest.mark.parametrize("function", ALL_FUNCTIONS)
def test_empty_input_message(function: Callable[[Any], Any]) -> None:
    with pytest.raises(ValueError, match="empty"):
        function([])


@pytest.mark.parametrize("function", ALL_FUNCTIONS)
def test_single_observation_is_insufficient(function: Callable[[Any], Any]) -> None:
    # One value gives no return; one return gives no sample standard deviation.
    with pytest.raises(ValueError, match="at least 2"):
        function([0.5])


@pytest.mark.parametrize("function", VALUE_FUNCTIONS)
@pytest.mark.parametrize("values", [[100.0, 0.0, 110.0], [100.0, -5.0], [0.0, 100.0]])
def test_non_positive_portfolio_values_rejected(
    function: Callable[[Any], Any], values: list[float]
) -> None:
    with pytest.raises(ValueError, match="strictly positive"):
        function(values)


@pytest.mark.parametrize("function", RETURN_FUNCTIONS)
def test_return_below_minus_one_rejected(function: Callable[[Any], Any]) -> None:
    # -1.5 is impossible as a decimal return; most likely a percentage (-1.5 %).
    with pytest.raises(ValueError, match="percentages"):
        function([0.01, -1.5, 0.02])


def test_input_is_not_mutated() -> None:
    values = np.array([100.0, 110.0, 99.0])
    portfolio_returns(values)
    max_drawdown(values)
    np.testing.assert_array_equal(values, [100.0, 110.0, 99.0])


# ==========================================================================
# A. Portfolio returns
# ==========================================================================


def test_portfolio_returns_hand_calculated() -> None:
    # 110/100 - 1 = 0.10;  99/110 - 1 = -0.10;  99/99 - 1 = 0
    result = portfolio_returns([100.0, 110.0, 99.0, 99.0])
    np.testing.assert_allclose(result, [0.10, -0.10, 0.0], rtol=0, atol=TOL)


def test_portfolio_returns_positive_and_negative() -> None:
    # 150/200 - 1 = -0.25;  300/150 - 1 = +1.00 (doubling)
    result = portfolio_returns([200, 150, 300])  # integers accepted
    np.testing.assert_allclose(result, [-0.25, 1.0], rtol=0, atol=TOL)


def test_portfolio_returns_length_and_first_observation() -> None:
    # n + 1 values -> n returns; the first observation has no return (not 0, not NaN).
    result = portfolio_returns(np.array([10.0, 11.0, 12.0, 13.0, 14.0]))
    assert result.shape == (4,)
    assert result.dtype == np.float64
    assert np.isfinite(result).all()


def test_portfolio_returns_constant_values_are_zero() -> None:
    np.testing.assert_array_equal(portfolio_returns([50.0, 50.0, 50.0]), [0.0, 0.0])


def test_compounded_returns_reproduce_total_growth() -> None:
    # prod(1 + r_t) = V_n / V_0 by telescoping.
    values = [100.0, 104.0, 98.0, 101.5, 120.0]
    result = portfolio_returns(values)
    assert np.prod(1.0 + result) == pytest.approx(values[-1] / values[0], rel=1e-12)


def test_portfolio_returns_scale_invariant() -> None:
    # Returns do not depend on the currency unit.
    base = portfolio_returns([100.0, 110.0, 99.0])
    np.testing.assert_allclose(portfolio_returns([1e5, 1.1e5, 0.99e5]), base, atol=TOL)


# ==========================================================================
# B. Annualised volatility
# ==========================================================================


def test_volatility_two_returns_hand_calculated() -> None:
    # r = [0.01, -0.01]: mean 0; sum of squared deviations 2e-4; ddof=1 -> var 2e-4.
    # annualised with N = 4: sqrt(2e-4 * 4) = sqrt(8e-4)
    assert annualized_volatility([0.01, -0.01], 4) == pytest.approx(math.sqrt(8e-4), abs=TOL)


def test_volatility_monthly_hand_calculated() -> None:
    # r = [0.02, 0.04]: mean 0.03, deviations +-0.01, var = 2e-4 / 1.
    # N = 12: sqrt(2e-4 * 12) = sqrt(0.0024)
    assert annualized_volatility([0.02, 0.04], 12) == pytest.approx(math.sqrt(0.0024), abs=TOL)


def test_volatility_four_returns_hand_calculated() -> None:
    # r = [0.01, -0.01, 0.02, 0.00]: mean 0.005; deviations 0.005, -0.015, 0.015, -0.005
    # squared: 2.5e-5 + 2.25e-4 + 2.25e-4 + 2.5e-5 = 5e-4; var = 5e-4 / 3
    # N = 252: sqrt(5e-4 / 3 * 252) = sqrt(0.042)
    result = annualized_volatility([0.01, -0.01, 0.02, 0.00], 252)
    assert result == pytest.approx(math.sqrt(0.042), abs=TOL)


def test_volatility_uses_sample_standard_deviation() -> None:
    # Population std (ddof=0) of [0.01, -0.01] is 0.01; sample std (ddof=1) is 0.01*sqrt(2).
    result = annualized_volatility([0.01, -0.01], 1)
    assert result == pytest.approx(0.01 * math.sqrt(2), abs=TOL)
    assert result != pytest.approx(0.01, abs=1e-6)


def test_volatility_scales_with_square_root_of_periods() -> None:
    returns = [0.01, -0.02, 0.015, 0.003]
    assert annualized_volatility(returns, 48) == pytest.approx(
        2 * annualized_volatility(returns, 12), rel=1e-12
    )


def test_volatility_of_constant_returns_is_exactly_zero() -> None:
    # Mathematically zero; floating-point noise (~1e-18) is snapped to 0.0.
    assert annualized_volatility([0.001] * 10, 252) == 0.0
    assert annualized_volatility([0.0, 0.0], 12) == 0.0


def test_volatility_accepts_total_loss_return() -> None:
    # r = -1 (a 100 % loss) is a valid return. [-1, 0]: mean -0.5, var 0.5.
    assert annualized_volatility([-1.0, 0.0], 1) == pytest.approx(math.sqrt(0.5), abs=TOL)


def test_volatility_accepts_non_integer_periods_per_year() -> None:
    assert annualized_volatility([0.01, -0.01], 365.25) == pytest.approx(
        0.01 * math.sqrt(2) * math.sqrt(365.25), abs=TOL
    )


INVALID_PERIODS_TYPE = [True, np.bool_(True), "252", None, [252]]
INVALID_PERIODS_VALUE = [0, -12, 0.0, math.nan, math.inf, -math.inf]


@pytest.mark.parametrize("periods", INVALID_PERIODS_TYPE, ids=repr)
def test_volatility_rejects_non_numeric_periods(periods: Any) -> None:
    with pytest.raises(TypeError):
        annualized_volatility([0.01, -0.01], periods)


@pytest.mark.parametrize("periods", INVALID_PERIODS_VALUE, ids=repr)
def test_volatility_rejects_invalid_periods(periods: Any) -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        annualized_volatility([0.01, -0.01], periods)


# ==========================================================================
# C. Risk-free conversion and Sharpe ratio
# ==========================================================================

# (1.01)^12 - 1: the annual rate equivalent to exactly 1 % per month.
ANNUAL_RATE_FOR_ONE_PERCENT_MONTHLY = 1.01**12 - 1


def test_annual_to_periodic_rate_hand_calculated() -> None:
    assert annual_to_periodic_rate(ANNUAL_RATE_FOR_ONE_PERCENT_MONTHLY, 12) == pytest.approx(
        0.01, abs=TOL
    )
    assert annual_to_periodic_rate(0.0, 252) == 0.0


@pytest.mark.parametrize("annual", [0.05, -0.03, 0.25])
def test_annual_to_periodic_rate_compounds_back(annual: float) -> None:
    periodic = annual_to_periodic_rate(annual, 252)
    assert (1 + periodic) ** 252 - 1 == pytest.approx(annual, abs=1e-12)


@pytest.mark.parametrize("annual", [-1.0, -2.0, math.nan, math.inf])
def test_annual_to_periodic_rate_rejects_invalid_rates(annual: float) -> None:
    with pytest.raises(ValueError):
        annual_to_periodic_rate(annual, 12)


def test_sharpe_hand_calculated_zero_risk_free() -> None:
    # r = [0.02, 0.04, 0.00]: mean 0.02; deviations 0, 0.02, -0.02
    # var = (0 + 4e-4 + 4e-4) / 2 = 4e-4 -> std 0.02; periodic Sharpe = 1
    # annualised with N = 12: sqrt(12)
    assert sharpe_ratio([0.02, 0.04, 0.00], 12) == pytest.approx(math.sqrt(12), abs=TOL)


def test_sharpe_negative_returns_give_negative_ratio() -> None:
    # Mirror image of the case above: mean -0.02, std 0.02 -> -sqrt(12)
    assert sharpe_ratio([-0.02, -0.04, 0.00], 12) == pytest.approx(-math.sqrt(12), abs=TOL)


def test_sharpe_with_annual_risk_free_rate_uses_geometric_conversion() -> None:
    # Annual rf converts to exactly 0.01 per month.
    # Excess = [0.01, 0.03, -0.01]: mean 0.01, std 0.02 -> periodic 0.5
    # annualised: 0.5 * sqrt(12) = sqrt(3)
    result = sharpe_ratio(
        [0.02, 0.04, 0.00], 12, annual_risk_free_rate=ANNUAL_RATE_FOR_ONE_PERCENT_MONTHLY
    )
    assert result == pytest.approx(math.sqrt(3), abs=TOL)

    # Simple division (annual / 12 = 0.010568...) would give a different answer, ~1.6335.
    simple_periodic = ANNUAL_RATE_FOR_ONE_PERCENT_MONTHLY / 12
    simple_result = math.sqrt(12) * (0.02 - simple_periodic) / 0.02
    assert result != pytest.approx(simple_result, abs=1e-3)


def test_sharpe_with_scalar_periodic_risk_free_rate() -> None:
    # Same as the previous case, with the periodic rate given directly.
    result = sharpe_ratio([0.02, 0.04, 0.00], 12, periodic_risk_free_rate=0.01)
    assert result == pytest.approx(math.sqrt(3), abs=TOL)


def test_sharpe_with_time_varying_periodic_risk_free_rate() -> None:
    # Excess = [0.02, 0.02, 0.00]: mean 0.04/3
    # squared deviations: 2 * (0.02/3)^2 + (0.04/3)^2 = 0.0024/9; var = 0.0012/9
    # std = sqrt(0.0012)/3 -> periodic Sharpe = 0.04/sqrt(0.0012)
    # annualised: sqrt(12) * 0.04 / sqrt(0.0012) = 0.04 * sqrt(10000) = 4
    result = sharpe_ratio([0.02, 0.04, 0.00], 12, periodic_risk_free_rate=[0.0, 0.02, 0.0])
    assert result == pytest.approx(4.0, abs=1e-10)


def test_sharpe_zero_risk_free_equivalents() -> None:
    returns = [0.01, -0.005, 0.02, 0.0]
    base = sharpe_ratio(returns, 52)
    assert sharpe_ratio(returns, 52, annual_risk_free_rate=0.0) == pytest.approx(base, abs=TOL)
    assert sharpe_ratio(returns, 52, periodic_risk_free_rate=0.0) == pytest.approx(base, abs=TOL)


def test_sharpe_zero_volatility_is_undefined() -> None:
    with pytest.raises(UndefinedMetricError, match="undefined"):
        sharpe_ratio([0.01] * 5, 252)


def test_sharpe_constant_excess_return_is_undefined() -> None:
    # Returns vary, but the excess over a matching risk-free series is constant (0.02).
    # Floating-point subtraction leaves ~1e-18 noise, which must not produce a huge ratio.
    with pytest.raises(UndefinedMetricError):
        sharpe_ratio([0.03, 0.05], 12, periodic_risk_free_rate=[0.01, 0.03])


def test_undefined_metric_error_is_a_value_error() -> None:
    assert issubclass(UndefinedMetricError, ValueError)


def test_sharpe_rejects_both_risk_free_forms() -> None:
    with pytest.raises(ValueError, match="not both"):
        sharpe_ratio([0.01, 0.02], 12, annual_risk_free_rate=0.02, periodic_risk_free_rate=0.001)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"annual_risk_free_rate": -1.0},
        {"annual_risk_free_rate": math.nan},
        {"periodic_risk_free_rate": math.inf},
        {"periodic_risk_free_rate": -1.0},
        {"periodic_risk_free_rate": [0.0, 0.0, 0.0]},  # length mismatch (2 returns)
        {"periodic_risk_free_rate": [0.0, math.nan]},
        {"periodic_risk_free_rate": [0.0, -1.0]},
    ],
    ids=repr,
)
def test_sharpe_rejects_invalid_risk_free_values(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        sharpe_ratio([0.01, 0.02], 12, **kwargs)


@pytest.mark.parametrize("rate", [True, "0.02", [0.02]])
def test_sharpe_rejects_non_numeric_annual_risk_free(rate: Any) -> None:
    with pytest.raises(TypeError):
        sharpe_ratio([0.01, 0.02], 12, annual_risk_free_rate=rate)


@pytest.mark.parametrize("periods", INVALID_PERIODS_VALUE, ids=repr)
def test_sharpe_rejects_invalid_periods(periods: Any) -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        sharpe_ratio([0.01, 0.02], periods)


@pytest.mark.parametrize("periods", INVALID_PERIODS_TYPE, ids=repr)
def test_sharpe_rejects_non_numeric_periods(periods: Any) -> None:
    with pytest.raises(TypeError):
        sharpe_ratio([0.01, 0.02], periods)


# ==========================================================================
# D. Drawdown and maximum drawdown
# ==========================================================================

RECOVERY_PATH = [100.0, 120.0, 90.0, 110.0, 130.0, 117.0]
# running peak: 100, 120, 120, 120, 130, 130
# drawdown:     0,   0,   90/120-1 = -0.25,  110/120-1 = -1/12,  0,  117/130-1 = -0.10


def test_drawdown_series_hand_calculated() -> None:
    expected = [0.0, 0.0, -0.25, -1 / 12, 0.0, -0.10]
    np.testing.assert_allclose(drawdown_series(RECOVERY_PATH), expected, rtol=0, atol=TOL)


def test_drawdown_series_first_observation_is_initial_peak() -> None:
    # Starting below some earlier (unseen) high is invisible: D_0 = 0 by definition.
    assert drawdown_series([80.0, 70.0])[0] == 0.0


def test_max_drawdown_followed_by_recovery() -> None:
    result = max_drawdown(RECOVERY_PATH)
    assert isinstance(result, MaxDrawdown)
    assert result.max_drawdown == pytest.approx(-0.25, abs=TOL)
    assert (result.peak_index, result.trough_index) == (1, 2)


def test_max_drawdown_decline_from_start() -> None:
    # 60/100 - 1 = -0.40; the peak is the first observation.
    result = max_drawdown([100.0, 80.0, 60.0])
    assert result.max_drawdown == pytest.approx(-0.40, abs=TOL)
    assert (result.peak_index, result.trough_index) == (0, 2)


@pytest.mark.parametrize("values", [[100.0, 101.0, 105.0], [50.0, 50.0, 50.0]])
def test_max_drawdown_without_decline_is_zero(values: list[float]) -> None:
    result = max_drawdown(values)
    assert result.max_drawdown == 0.0
    assert (result.peak_index, result.trough_index) == (0, 0)
    np.testing.assert_array_equal(drawdown_series(values), np.zeros(len(values)))


def test_max_drawdown_picks_deepest_episode_and_latest_peak() -> None:
    # Drawdowns: 0, -0.10, 0, -0.30, 0. The deepest trough is at index 3 (70/100 - 1).
    # The running peak (100) is reached at indices 0 and 2; the decline began at index 2.
    result = max_drawdown([100.0, 90.0, 100.0, 70.0, 100.0])
    assert result.max_drawdown == pytest.approx(-0.30, abs=TOL)
    assert (result.peak_index, result.trough_index) == (2, 3)


def test_max_drawdown_tied_troughs_use_earliest() -> None:
    # Drawdowns: 0, -0.5, 0, -0.5. The earliest deepest trough is index 1, after peak 0.
    result = max_drawdown([100.0, 50.0, 100.0, 50.0])
    assert result.max_drawdown == pytest.approx(-0.5, abs=TOL)
    assert (result.peak_index, result.trough_index) == (0, 1)


def test_max_drawdown_is_scale_invariant_and_bounded() -> None:
    base = max_drawdown(RECOVERY_PATH)
    scaled = max_drawdown([v * 1000 for v in RECOVERY_PATH])
    assert scaled.max_drawdown == pytest.approx(base.max_drawdown, abs=TOL)
    assert (scaled.peak_index, scaled.trough_index) == (base.peak_index, base.trough_index)
    # With strictly positive values, -1 < MDD <= 0.
    assert -1.0 < base.max_drawdown <= 0.0


def test_max_drawdown_result_types() -> None:
    result = max_drawdown(np.array([100.0, 90.0]))
    assert type(result.max_drawdown) is float
    assert type(result.peak_index) is int
    assert type(result.trough_index) is int


# ==========================================================================
# Review findings: direct conversion validation, tuple and pandas inputs
# ==========================================================================


@pytest.mark.parametrize("periods", INVALID_PERIODS_VALUE, ids=repr)
def test_annual_to_periodic_rate_rejects_invalid_periods(periods: Any) -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        annual_to_periodic_rate(0.02, periods)


@pytest.mark.parametrize("periods", INVALID_PERIODS_TYPE, ids=repr)
def test_annual_to_periodic_rate_rejects_non_numeric_periods(periods: Any) -> None:
    with pytest.raises(TypeError):
        annual_to_periodic_rate(0.02, periods)


def test_tuple_inputs_match_list_inputs() -> None:
    values = (100.0, 120.0, 90.0, 110.0)
    returns = (0.02, 0.04, 0.00)
    np.testing.assert_array_equal(portfolio_returns(values), portfolio_returns(list(values)))
    assert max_drawdown(values) == max_drawdown(list(values))
    assert cumulative_return(values) == cumulative_return(list(values))
    assert annualized_return(values, 12) == annualized_return(list(values), 12)
    assert annualized_volatility(returns, 12) == annualized_volatility(list(returns), 12)
    assert sharpe_ratio(returns, 12) == sharpe_ratio(list(returns), 12)


def test_pandas_series_inputs_match_list_inputs() -> None:
    # pandas is a dev-only dependency (D-032); the index is ignored, positions are returned.
    pd = pytest.importorskip("pandas")
    dates = pd.date_range("2024-01-31", periods=4, freq="ME")
    values = pd.Series([100.0, 120.0, 90.0, 110.0], index=dates)
    returns = pd.Series([0.02, 0.04, 0.00], index=dates[1:])

    np.testing.assert_array_equal(portfolio_returns(values), portfolio_returns(values.tolist()))
    result = max_drawdown(values)
    assert (result.peak_index, result.trough_index) == (1, 2)
    assert values.index[result.trough_index] == dates[2]  # documented position -> date mapping
    assert cumulative_return(values) == pytest.approx(0.10, abs=TOL)
    assert annualized_return(values, 12) == annualized_return(values.tolist(), 12)
    assert sharpe_ratio(returns, 12) == pytest.approx(math.sqrt(12), abs=TOL)
    assert annualized_volatility(returns, 12) == pytest.approx(0.02 * math.sqrt(12), abs=TOL)


@pytest.mark.parametrize("dtype", ["float64", "Float64"])
def test_pandas_missing_values_rejected(dtype: str) -> None:
    # Both NaN and the nullable pd.NA must be rejected, never dropped.
    pd = pytest.importorskip("pandas")
    series = pd.Series([100.0, None, 110.0], dtype=dtype)
    with pytest.raises((ValueError, TypeError)):
        portfolio_returns(series)


# ==========================================================================
# E. Cumulative return
# ==========================================================================


def test_cumulative_return_positive() -> None:
    # 121 / 100 - 1 = 0.21
    assert cumulative_return([100.0, 110.0, 99.0, 121.0]) == pytest.approx(0.21, abs=TOL)


def test_cumulative_return_negative() -> None:
    # 90 / 100 - 1 = -0.10
    assert cumulative_return([100.0, 80.0, 90.0]) == pytest.approx(-0.10, abs=TOL)


def test_cumulative_return_zero_despite_intermediate_moves() -> None:
    # Ends where it started: 100 / 100 - 1 = 0, whatever happened in between.
    assert cumulative_return([100.0, 150.0, 60.0, 100.0]) == 0.0


def test_cumulative_return_matches_compounded_periodic_returns() -> None:
    # V_T / V_0 = prod(V_t / V_{t-1}) = prod(1 + r_t) by telescoping.
    values = [100.0, 104.0, 98.0, 101.5, 120.0, 87.3]
    compounded = float(np.prod(1.0 + portfolio_returns(values))) - 1.0
    assert cumulative_return(values) == pytest.approx(compounded, abs=TOL)


def test_cumulative_return_scale_invariant_and_decimal() -> None:
    base = cumulative_return([100.0, 150.0])
    assert cumulative_return([1e6, 1.5e6]) == pytest.approx(base, abs=TOL)
    assert base == pytest.approx(0.5, abs=TOL)  # a decimal: 0.5, not 50


def test_cumulative_return_validates_intermediate_values() -> None:
    # Only V_0 and V_T enter the formula, but a corrupt path must still be rejected.
    with pytest.raises(ValueError, match="non-finite"):
        cumulative_return([100.0, math.nan, 110.0])
    with pytest.raises(ValueError, match="strictly positive"):
        cumulative_return([100.0, -1.0, 110.0])


# ==========================================================================
# F. Annualised return (geometric, CAGR)
# ==========================================================================


def test_annualized_return_yearly_periods() -> None:
    # T = 2 yearly periods (N = 1): (121/100)^(1/2) - 1 = 1.1 - 1 = 0.10
    assert annualized_return([100.0, 110.0, 121.0], 1) == pytest.approx(0.10, abs=TOL)


def test_annualized_return_single_period_allowed() -> None:
    # T = 1, N = 1: (110/100)^1 - 1 = 0.10
    assert annualized_return([100.0, 110.0], 1) == pytest.approx(0.10, abs=TOL)


def test_annualized_return_monthly_two_years_any_path() -> None:
    # T = 24 monthly periods, N = 12, V_T / V_0 = 1.21: 1.21^(12/24) - 1 = 0.10.
    # Intermediate values do not matter, only the first, the last and T.
    smooth = [100.0 * 1.21 ** (t / 24) for t in range(25)]
    zigzag = [100.0] + [80.0 if t % 2 else 130.0 for t in range(1, 24)] + [121.0]
    assert len(smooth) == len(zigzag) == 25
    assert annualized_return(smooth, 12) == pytest.approx(0.10, abs=1e-12)
    assert annualized_return(zigzag, 12) == pytest.approx(0.10, abs=1e-12)


def test_annualized_return_declining_portfolio() -> None:
    # (81/100)^(1/2) - 1 = 0.9 - 1 = -0.10
    assert annualized_return([100.0, 90.0, 81.0], 1) == pytest.approx(-0.10, abs=TOL)


def test_annualized_return_fractional_periods_per_year() -> None:
    # T = 5 periods with N = 2.5 periods per year (each period is 0.4 years), so the
    # window is 2 years and the exponent N/T = 0.5: (121/100)^0.5 - 1 = 0.10
    values = [100.0, 105.0, 98.0, 110.0, 115.0, 121.0]
    assert annualized_return(values, 2.5) == pytest.approx(0.10, abs=TOL)


def test_annualized_return_equals_cumulative_over_exactly_one_year() -> None:
    # If T = N the window is one year, so CAGR equals the cumulative return.
    values = [100.0, 103.0, 99.0, 104.0, 107.0, 101.0, 109.0, 111.0, 108.0, 112.0, 115.0, 113.0]
    values.append(118.0)
    assert len(values) - 1 == 12
    assert annualized_return(values, 12) == pytest.approx(cumulative_return(values), abs=TOL)


def test_annualized_return_is_geometric_not_arithmetic() -> None:
    # +50 % then -50 %: 100 -> 150 -> 75. Arithmetic mean of returns = 0, so 0 * N = 0.
    # Geometric: (75/100)^(1/2) - 1 = sqrt(0.75) - 1 = -0.13397...
    values = [100.0, 150.0, 75.0]
    assert float(np.mean(portfolio_returns(values))) == pytest.approx(0.0, abs=TOL)
    assert annualized_return(values, 1) == pytest.approx(math.sqrt(0.75) - 1, abs=TOL)


def test_annualized_return_short_period_extrapolates() -> None:
    # Documents the limitation; it does not fix it. One month of +5 % with N = 12
    # annualises to 1.05^12 - 1 = 0.79586 (about +79.6 % per year).
    assert annualized_return([100.0, 105.0], 12) == pytest.approx(1.05**12 - 1, abs=TOL)


def test_annualized_return_constant_values_is_zero() -> None:
    assert annualized_return([100.0, 100.0, 100.0], 252) == 0.0


def test_annualized_return_overflow_raises() -> None:
    # 1e6-fold growth in one period with N = 252 is (1e6)^252 = 1e1512, beyond float range.
    with pytest.raises(ValueError, match="too large"):
        annualized_return([1.0, 1e6], 252)


def test_annualized_return_extreme_short_loss_rounds_to_minus_one() -> None:
    # (1e-5)^252 underflows; the true value is just above -1 and rounds to -1.0.
    assert annualized_return([100.0, 1e-3], 252) == -1.0


@pytest.mark.parametrize("periods", INVALID_PERIODS_VALUE, ids=repr)
def test_annualized_return_rejects_invalid_periods(periods: Any) -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        annualized_return([100.0, 110.0], periods)


@pytest.mark.parametrize("periods", INVALID_PERIODS_TYPE, ids=repr)
def test_annualized_return_rejects_non_numeric_periods(periods: Any) -> None:
    with pytest.raises(TypeError):
        annualized_return([100.0, 110.0], periods)
