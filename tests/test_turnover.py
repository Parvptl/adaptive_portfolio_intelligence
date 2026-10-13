"""Tests for two-way portfolio turnover (portfolio_turnover, annualized_turnover).

Convention (proposed, D-011 / D-030): tau_k = sum_i |w_post[k, i] - w_pre[k, i]|,
where pre-trade weights are the drifted weights immediately before trading.
Expected values are derived by hand in the comments.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from adaptive_portfolio.config import EnvironmentConfig
from adaptive_portfolio.evaluation import (
    WEIGHT_SUM_TOLERANCE,
    annualized_turnover,
    portfolio_turnover,
)

TOL = 1e-12

# ==========================================================================
# Hand-calculated turnover
# ==========================================================================


def test_partial_rebalance() -> None:
    # |0.5 - 0.6| + |0.5 - 0.4| = 0.1 + 0.1 = 0.2 (two-way: both legs counted)
    result = portfolio_turnover([[0.6, 0.4]], [[0.5, 0.5]])
    np.testing.assert_allclose(result, [0.2], rtol=0, atol=TOL)


def test_full_replacement_is_maximum_two() -> None:
    # Sell all of A, buy all of B: |0 - 1| + |1 - 0| = 2
    np.testing.assert_allclose(portfolio_turnover([[1.0, 0.0]], [[0.0, 1.0]]), [2.0], atol=TOL)


def test_zero_trade_event_is_exactly_zero() -> None:
    weights = [[0.3, 0.3, 0.4]]
    np.testing.assert_array_equal(portfolio_turnover(weights, weights), [0.0])


def test_one_value_per_event_in_row_order() -> None:
    pre = [[0.6, 0.4], [0.5, 0.5], [1.0, 0.0]]
    post = [[0.5, 0.5], [0.5, 0.5], [0.0, 1.0]]
    result = portfolio_turnover(pre, post)
    assert result.shape == (3,)
    assert result.dtype == np.float64
    np.testing.assert_allclose(result, [0.2, 0.0, 2.0], rtol=0, atol=TOL)


# ==========================================================================
# Why drift-adjusted pre-trade weights are required
# ==========================================================================


def _drifted_weights(weights: np.ndarray, asset_returns: np.ndarray) -> np.ndarray:
    """Weights after one period of returns (test helper; drift is the caller's job)."""
    grown = weights * (1.0 + asset_returns)
    return grown / grown.sum()


def test_drift_requires_trading_even_when_target_is_unchanged() -> None:
    # Target 50/50 at both rebalances. Asset A returns +10 %, asset B 0 %.
    # Portfolio value 0.5 * 1.1 + 0.5 * 1.0 = 1.05, so the drifted weights are
    # A = 0.55 / 1.05 = 11/21 and B = 0.50 / 1.05 = 10/21.
    # Rebalancing back to 50/50: |1/2 - 11/21| + |1/2 - 10/21| = 1/42 + 1/42 = 1/21.
    target = np.array([[0.5, 0.5]])
    pre_trade = _drifted_weights(target[0], np.array([0.10, 0.0]))[np.newaxis, :]
    np.testing.assert_allclose(pre_trade, [[11 / 21, 10 / 21]], rtol=0, atol=TOL)

    actual = portfolio_turnover(pre_trade, target)
    np.testing.assert_allclose(actual, [1 / 21], rtol=0, atol=TOL)

    # The naive comparison of consecutive targets sees no change at all, so it would
    # report zero turnover (and zero transaction cost) for a trade that really happens.
    naive = np.abs(target - target).sum(axis=1)
    np.testing.assert_array_equal(naive, [0.0])
    assert actual[0] > 0.04


def test_drift_can_also_reduce_required_trading() -> None:
    # Moving from 60/40 to 50/50. If A falls -10 % and B rises +10 % first:
    # A = 0.6 * 0.9 = 0.54, B = 0.4 * 1.1 = 0.44, total 0.98, so the drifted weights
    # are A = 0.54/0.98 and B = 0.44/0.98. Trading to 50/50 needs
    # 2 * (0.54/0.98 - 0.5) = 2 * (0.54 - 0.49)/0.98 = 2 * 0.05/0.98 = 0.10204...,
    # roughly half of the naive 0.2.
    old_target = np.array([0.6, 0.4])
    new_target = np.array([[0.5, 0.5]])
    pre_trade = _drifted_weights(old_target, np.array([-0.10, 0.10]))[np.newaxis, :]
    actual = portfolio_turnover(pre_trade, new_target)
    np.testing.assert_allclose(actual, [2 * 0.05 / 0.98], rtol=0, atol=TOL)
    naive = np.abs(new_target[0] - old_target).sum()
    assert naive == pytest.approx(0.2, abs=TOL)
    assert actual[0] < naive


# ==========================================================================
# Cash and initial funding
# ==========================================================================


def test_cash_column_counts_on_both_legs() -> None:
    # Columns: SPY, TLT, CASH. Selling 0.10 of SPY into cash:
    # |0.4 - 0.5| + |0.5 - 0.5| + |0.1 - 0.0| = 0.2
    pre = [[0.5, 0.5, 0.0]]
    post = [[0.4, 0.5, 0.1]]
    np.testing.assert_allclose(portfolio_turnover(pre, post), [0.2], rtol=0, atol=TOL)


def test_omitted_cash_column_is_detected() -> None:
    # Same trade without the cash column: the post-trade row sums to 0.9, not 1.
    with pytest.raises(ValueError, match="include cash"):
        portfolio_turnover([[0.5, 0.5]], [[0.4, 0.5]])


def test_initial_funding_counted_only_when_supplied_as_an_event() -> None:
    # All cash -> 50/50: |0.5 - 0| + |0.5 - 0| + |0 - 1| = 2.0
    funding = portfolio_turnover([[0.0, 0.0, 1.0]], [[0.5, 0.5, 0.0]])
    np.testing.assert_allclose(funding, [2.0], rtol=0, atol=TOL)
    # Without that row, only the supplied rebalance is measured.
    later = portfolio_turnover([[0.55, 0.45, 0.0]], [[0.5, 0.5, 0.0]])
    assert later.shape == (1,)
    np.testing.assert_allclose(later, [0.1], rtol=0, atol=TOL)


# ==========================================================================
# Mathematical properties
# ==========================================================================


def test_turnover_bounds_and_symmetry_on_random_valid_weights() -> None:
    # For weights that each sum to 1, 0 <= sum|post - pre| <= sum(post) + sum(pre) = 2,
    # and the value is symmetric in (pre, post).
    rng = np.random.default_rng(12345)
    pre = rng.dirichlet(np.ones(6), size=200)
    post = rng.dirichlet(np.ones(6), size=200)
    forward = portfolio_turnover(pre, post)
    assert ((forward >= 0) & (forward <= 2 + 2 * WEIGHT_SUM_TOLERANCE)).all()
    np.testing.assert_allclose(portfolio_turnover(post, pre), forward, rtol=0, atol=TOL)


def test_single_asset_portfolio_never_trades() -> None:
    np.testing.assert_array_equal(portfolio_turnover([[1.0], [1.0]], [[1.0], [1.0]]), [0.0, 0.0])


def test_full_replacement_is_accepted_by_config_turnover_cap(
    environment_raw: dict[str, Any],
) -> None:
    # Consistency with configs/environment.yaml: max_turnover is two-way, in (0, 2],
    # so the largest possible turnover from portfolio_turnover is a valid cap.
    largest = float(portfolio_turnover([[1.0, 0.0]], [[0.0, 1.0]])[0])
    environment_raw["constraints"]["max_turnover"] = largest
    config = EnvironmentConfig.from_dict(environment_raw)
    assert config.constraints.max_turnover == pytest.approx(2.0)


# ==========================================================================
# Weight-sum tolerance
# ==========================================================================


def test_rounding_within_tolerance_accepted() -> None:
    nearly_one = [[0.5, 0.5 + 0.5 * WEIGHT_SUM_TOLERANCE]]
    np.testing.assert_allclose(portfolio_turnover(nearly_one, [[0.5, 0.5]]), [0.0], atol=1e-6)


def test_float32_weights_accepted() -> None:
    # Ten weights of 0.1 in float32 sum to 1 only within ~1e-7.
    weights = np.full((1, 10), 0.1, dtype=np.float32)
    np.testing.assert_allclose(portfolio_turnover(weights, weights), [0.0], atol=TOL)


def test_allocation_error_beyond_tolerance_rejected() -> None:
    with pytest.raises(ValueError, match="sums to"):
        portfolio_turnover([[0.5, 0.5 + 10 * WEIGHT_SUM_TOLERANCE]], [[0.5, 0.5]])


# ==========================================================================
# Input validation
# ==========================================================================

VALID = [[0.5, 0.5]]


@pytest.mark.parametrize("empty", [[], [[]], np.empty((0, 3)), np.empty((2, 0))], ids=repr)
def test_empty_matrices_rejected(empty: Any) -> None:
    with pytest.raises(ValueError, match="empty"):
        portfolio_turnover(empty, empty)


@pytest.mark.parametrize(
    "bad",
    [[0.5, 0.5], np.full((1, 2, 2), 0.25), 1.0],
    ids=["1-D", "3-D", "scalar"],
)
def test_wrong_dimensions_rejected(bad: Any) -> None:
    with pytest.raises(ValueError, match="2-D"):
        portfolio_turnover(bad, bad)


@pytest.mark.parametrize(
    ("pre", "post"),
    [
        ([[0.5, 0.5]], [[0.2, 0.3, 0.5]]),  # different number of assets
        ([[0.5, 0.5], [0.5, 0.5]], [[0.5, 0.5]]),  # different number of events
    ],
)
def test_shape_mismatch_rejected(pre: Any, post: Any) -> None:
    with pytest.raises(ValueError, match="shape"):
        portfolio_turnover(pre, post)


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("side", ["pre", "post"])
def test_non_finite_weights_rejected(bad_value: float, side: str) -> None:
    bad = [[0.5, bad_value]]
    pre, post = (bad, VALID) if side == "pre" else (VALID, bad)
    with pytest.raises(ValueError, match="non-finite"):
        portfolio_turnover(pre, post)


def test_negative_weight_rejected_as_not_long_only() -> None:
    # Sums to 1 but contains a short position.
    with pytest.raises(ValueError, match="long-only"):
        portfolio_turnover([[1.2, -0.2]], VALID)


@pytest.mark.parametrize("row_sum", [0.0, 0.9, 1.1, 2.0])
def test_rows_not_summing_to_one_rejected(row_sum: float) -> None:
    with pytest.raises(ValueError, match="sums to"):
        portfolio_turnover(VALID, [[row_sum / 2, row_sum / 2]])


@pytest.mark.parametrize(
    "bad",
    [None, "0.5,0.5", [[True, False]], [["a", "b"]], [[0.5, None]], [[0.5 + 0j, 0.5 + 0j]]],
    ids=repr,
)
def test_non_numeric_weights_rejected(bad: Any) -> None:
    with pytest.raises(TypeError):
        portfolio_turnover(bad, VALID)


def test_ragged_matrix_rejected() -> None:
    with pytest.raises(ValueError):
        portfolio_turnover([[0.5, 0.5], [1.0]], VALID)


def test_tuple_and_pandas_inputs() -> None:
    expected = portfolio_turnover([[0.6, 0.4]], [[0.5, 0.5]])
    np.testing.assert_array_equal(portfolio_turnover(((0.6, 0.4),), ((0.5, 0.5),)), expected)
    pd = pytest.importorskip("pandas")
    pre = pd.DataFrame([[0.6, 0.4]], columns=["SPY", "CASH"])
    post = pd.DataFrame([[0.5, 0.5]], columns=["SPY", "CASH"])
    np.testing.assert_array_equal(portfolio_turnover(pre, post), expected)


def test_inputs_not_mutated() -> None:
    pre = np.array([[0.6, 0.4]])
    post = np.array([[0.5, 0.5]])
    portfolio_turnover(pre, post)
    np.testing.assert_array_equal(pre, [[0.6, 0.4]])
    np.testing.assert_array_equal(post, [[0.5, 0.5]])


# ==========================================================================
# Annualised turnover (aggregation)
# ==========================================================================


def test_annualized_turnover_monthly_events_daily_data() -> None:
    # 12 monthly events of 0.1 within one year of daily data (T_obs = 252, N = 252):
    # sum = 1.2, times 252 / 252 -> 1.2 per year.
    assert annualized_turnover([0.1] * 12, 252, 252) == pytest.approx(1.2, abs=TOL)


def test_annualized_turnover_over_two_years() -> None:
    # 6 events of 0.2 over 24 monthly periods (N = 12): 1.2 * 12 / 24 = 0.6 per year.
    assert annualized_turnover([0.2] * 6, 24, 12) == pytest.approx(0.6, abs=TOL)


def test_annualized_turnover_from_portfolio_turnover_output() -> None:
    events = portfolio_turnover([[0.6, 0.4], [1.0, 0.0]], [[0.5, 0.5], [0.0, 1.0]])
    # (0.2 + 2.0) * 12 / 12 = 2.2
    assert annualized_turnover(events, 12, 12) == pytest.approx(2.2, abs=TOL)


def test_annualized_turnover_no_events_is_zero() -> None:
    # Buy-and-hold with no rebalance events inside the window trades nothing.
    assert annualized_turnover([], 252, 252) == 0.0
    assert annualized_turnover(np.array([]), 252, 252) == 0.0


@pytest.mark.parametrize("bad", [[-0.1], [2.5], [math.nan], [0.1, math.inf]], ids=repr)
def test_annualized_turnover_rejects_invalid_event_values(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        annualized_turnover(bad, 12, 12)


def test_annualized_turnover_rejects_2d_events() -> None:
    with pytest.raises(ValueError, match="1-D"):
        annualized_turnover([[0.1, 0.2]], 12, 12)


@pytest.mark.parametrize("periods", [0, -12])
def test_annualized_turnover_rejects_non_positive_observation_periods(periods: int) -> None:
    with pytest.raises(ValueError, match="observation_periods"):
        annualized_turnover([0.1], periods, 12)


@pytest.mark.parametrize("periods", [2.5, True, "12", None])
def test_annualized_turnover_rejects_non_integer_observation_periods(periods: Any) -> None:
    with pytest.raises(TypeError, match="observation_periods"):
        annualized_turnover([0.1], periods, 12)


@pytest.mark.parametrize("factor", [0, -1, math.nan, math.inf])
def test_annualized_turnover_rejects_invalid_periods_per_year(factor: float) -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        annualized_turnover([0.1], 12, factor)


@pytest.mark.parametrize(
    "periods", [12, np.int64(12), np.int32(12), np.uint16(12)], ids=lambda p: type(p).__name__
)
def test_annualized_turnover_returns_python_float(periods: Any) -> None:
    # Regression: a NumPy integer observation_periods used to yield np.float64.
    # 0.1 * 12 / 12 = 0.1
    result = annualized_turnover([0.1], periods, 12)
    assert type(result) is float
    assert result == pytest.approx(0.1, abs=TOL)
    assert type(annualized_turnover([0.1], periods, np.float64(12.0))) is float
    assert type(annualized_turnover([], periods, 12)) is float


# ==========================================================================
# Traded notional: cash_column (approved 2026-10-13; D-011, D-030)
# Columns are [A, B, CASH] unless stated otherwise.
# ==========================================================================

PRE = [[0.5, 0.3, 0.2]]


def test_cash_funded_purchase_counts_once_with_cash_column() -> None:
    # Buy 0.10 of A using cash: post = [0.6, 0.3, 0.1].
    # Default (all columns): |0.1| + 0 + |-0.1| = 0.2 (asset leg + cash leg).
    # cash_column=2 (traded notional): |0.1| + 0 = 0.1 (only A was traded).
    post = [[0.6, 0.3, 0.1]]
    np.testing.assert_allclose(portfolio_turnover(PRE, post), [0.2], rtol=0, atol=TOL)
    np.testing.assert_allclose(
        portfolio_turnover(PRE, post, cash_column=2), [0.1], rtol=0, atol=TOL
    )


def test_switch_between_assets_is_unchanged_by_cash_column() -> None:
    # Sell 0.10 of A, buy 0.10 of B, cash unchanged: post = [0.4, 0.4, 0.2].
    # Both measures: |-0.1| + |0.1| (+ 0 for cash) = 0.2.
    post = [[0.4, 0.4, 0.2]]
    np.testing.assert_allclose(portfolio_turnover(PRE, post), [0.2], rtol=0, atol=TOL)
    np.testing.assert_allclose(
        portfolio_turnover(PRE, post, cash_column=2), [0.2], rtol=0, atol=TOL
    )


def test_mixed_trade_ordering_of_measures() -> None:
    # post = [0.4, 0.5, 0.1]: sell 0.1 of A (S = 0.1), buy 0.2 of B (B = 0.2), cash -0.1.
    # Default two-way = 0.1 + 0.2 + 0.1 = 0.4 = 2 * max(B, S)
    # Traded notional = 0.1 + 0.2 = 0.3 = B + S
    # One-way = 0.4 / 2 = 0.2 = max(B, S)
    post = [[0.4, 0.5, 0.1]]
    two_way = portfolio_turnover(PRE, post)[0]
    traded = portfolio_turnover(PRE, post, cash_column=2)[0]
    assert two_way == pytest.approx(0.4, abs=TOL)
    assert traded == pytest.approx(0.3, abs=TOL)
    assert two_way / 2 == pytest.approx(0.2, abs=TOL)
    assert two_way / 2 < traded < two_way


def test_cash_column_in_first_position() -> None:
    # Same 0.10 cash-funded purchase with columns [CASH, A, B].
    pre = [[0.2, 0.5, 0.3]]
    post = [[0.1, 0.6, 0.3]]
    np.testing.assert_allclose(
        portfolio_turnover(pre, post, cash_column=0), [0.1], rtol=0, atol=TOL
    )


def test_initial_funding_with_cash_column_is_one() -> None:
    # All cash -> 50/50: the default counts 0.5 + 0.5 + 1.0 = 2.0;
    # traded notional counts only the purchases, 0.5 + 0.5 = 1.0.
    pre, post = [[0.0, 0.0, 1.0]], [[0.5, 0.5, 0.0]]
    np.testing.assert_allclose(portfolio_turnover(pre, post), [2.0], rtol=0, atol=TOL)
    np.testing.assert_allclose(
        portfolio_turnover(pre, post, cash_column=2), [1.0], rtol=0, atol=TOL
    )


def test_cash_column_identities_on_random_weights() -> None:
    # For rows summing to 1 with cash in column j, the changes sum to 0, so
    # |dw_cash| = |B - S|. Hence default = B + S + |B - S| = 2 max(B, S) and
    # traded = B + S = default - |dw_cash|, with max(B, S) <= B + S <= 2 max(B, S).
    rng = np.random.default_rng(2026)
    pre = rng.dirichlet(np.ones(5), size=300)
    post = rng.dirichlet(np.ones(5), size=300)
    cash = 4
    default = portfolio_turnover(pre, post)
    traded = portfolio_turnover(pre, post, cash_column=cash)

    changes = post - pre
    risky = np.delete(changes, cash, axis=1)
    bought = np.where(risky > 0, risky, 0.0).sum(axis=1)
    sold = np.where(risky < 0, -risky, 0.0).sum(axis=1)
    np.testing.assert_allclose(traded, bought + sold, rtol=0, atol=1e-12)
    np.testing.assert_allclose(default, 2 * np.maximum(bought, sold), rtol=0, atol=1e-12)
    np.testing.assert_allclose(traded, default - np.abs(changes[:, cash]), rtol=0, atol=1e-12)
    assert (default / 2 <= traded + 1e-12).all()
    assert (traded <= default + 1e-12).all()


def test_default_behaviour_preserved() -> None:
    # Omitting cash_column and passing None are identical, and equal the
    # all-column sum used before the parameter existed.
    pre = [[0.6, 0.4], [1.0, 0.0]]
    post = [[0.5, 0.5], [0.0, 1.0]]
    legacy = np.abs(np.array(post) - np.array(pre)).sum(axis=1)
    np.testing.assert_array_equal(portfolio_turnover(pre, post), legacy)
    np.testing.assert_array_equal(portfolio_turnover(pre, post, cash_column=None), legacy)
    np.testing.assert_allclose(legacy, [0.2, 2.0], rtol=0, atol=TOL)


def test_fully_invested_portfolio_without_cash_needs_no_cash_column() -> None:
    # No cash column: buys equal sells, so the default already equals traded notional.
    # 60/40 -> 50/50: |-0.1| + |0.1| = 0.2 = B + S with B = S = 0.1.
    np.testing.assert_allclose(portfolio_turnover([[0.6, 0.4]], [[0.5, 0.5]]), [0.2], atol=TOL)


def test_cash_column_accepts_numpy_integer() -> None:
    post = [[0.6, 0.3, 0.1]]
    np.testing.assert_allclose(
        portfolio_turnover(PRE, post, cash_column=np.int64(2)), [0.1], rtol=0, atol=TOL
    )


def test_single_cash_column_portfolio_trades_nothing() -> None:
    # Only cash: nothing non-cash to trade.
    np.testing.assert_array_equal(portfolio_turnover([[1.0]], [[1.0]], cash_column=0), [0.0])


@pytest.mark.parametrize("index", [-1, -3, 3, 10])
def test_out_of_range_cash_column_rejected(index: int) -> None:
    # Three columns: valid indices are 0, 1, 2. Negative indices are refused, not wrapped.
    with pytest.raises(ValueError, match="cash_column"):
        portfolio_turnover(PRE, PRE, cash_column=index)


@pytest.mark.parametrize("index", [2.0, "2", True, np.bool_(True), [2]], ids=repr)
def test_non_integer_cash_column_rejected(index: Any) -> None:
    with pytest.raises(TypeError, match="cash_column"):
        portfolio_turnover(PRE, PRE, cash_column=index)


def test_full_rows_still_validated_with_cash_column() -> None:
    # The cash column is excluded from the sum, not from validation.
    # Row sums to 1.1 including cash:
    with pytest.raises(ValueError, match="sums to"):
        portfolio_turnover(PRE, [[0.6, 0.3, 0.2]], cash_column=2)
    # Negative cash weight (borrowing) is still rejected as not long-only:
    with pytest.raises(ValueError, match="long-only"):
        portfolio_turnover(PRE, [[0.8, 0.3, -0.1]], cash_column=2)
    # Omitting the cash column entirely still fails the row-sum check:
    with pytest.raises(ValueError, match="sums to"):
        portfolio_turnover([[0.5, 0.3]], [[0.6, 0.3]], cash_column=1)


def test_cash_column_with_multiple_events() -> None:
    # Event 1: cash-funded purchase of 0.1 -> 0.1. Event 2: switch of 0.1 -> 0.2.
    # Event 3: sell 0.3 of B into cash -> 0.3.
    pre = [[0.5, 0.3, 0.2], [0.5, 0.3, 0.2], [0.5, 0.3, 0.2]]
    post = [[0.6, 0.3, 0.1], [0.4, 0.4, 0.2], [0.5, 0.0, 0.5]]
    np.testing.assert_allclose(
        portfolio_turnover(pre, post, cash_column=2), [0.1, 0.2, 0.3], rtol=0, atol=TOL
    )
    np.testing.assert_allclose(portfolio_turnover(pre, post), [0.2, 0.2, 0.6], rtol=0, atol=TOL)
