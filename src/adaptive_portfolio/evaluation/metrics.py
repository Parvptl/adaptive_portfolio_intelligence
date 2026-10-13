"""Core financial performance metrics.

All functions are pure and deterministic. Series inputs are 1-D sequences of
real numbers; turnover takes 2-D weight matrices. Supported, tested input types
are lists, tuples, NumPy arrays, and pandas Series / DataFrames (pandas is not
a runtime dependency; anything ``numpy.asarray`` converts to a real-valued array
works). Metric conventions (``docs/decision_log.md``, D-011 and D-021 to D-030;
the transaction-cost basis, D-031, is still open):

* **Units.** Returns and rates are decimals (0.01 = 1 %), never percentages.
  Periodic quantities refer to one observation interval, for example one day.
  Annualised quantities refer to one year.
* **Portfolio values** must be finite and strictly positive.
* **Returns** are simple (arithmetic) period returns, which must be finite and
  at least -1 (a loss of more than 100 % is impossible for a long-only portfolio).
* **Annualisation** uses an explicitly supplied number of periods per year
  ``periods_per_year``. There is no default frequency.
* **Standard deviation** is the sample standard deviation (``ddof=1``).
* **Annualised return** is geometric (CAGR), based on first and last values.
* **Turnover** is two-way, per rebalance event, computed from caller-supplied
  drift-adjusted pre-trade weights and post-trade weights (long-only, rows sum
  to 1 within :data:`WEIGHT_SUM_TOLERANCE`). By default every column is summed;
  with ``cash_column`` the cash column is excluded, giving traded notional.
* **Invalid input raises**; nothing is silently dropped, filled or clipped.
  Undefined results (e.g. a Sharpe ratio with zero volatility) raise
  :class:`UndefinedMetricError` instead of returning ``inf`` or ``nan``.

Outputs are positional: ``returns[i]`` covers the period from observation ``i``
to ``i + 1``, drawdown indices refer to positions in the input, and turnover
``[k]`` refers to row ``k``. Callers holding pandas objects can map positions to
dates with ``series.index[i]``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

ZERO_VOLATILITY_TOLERANCE = 1e-12
"""Periodic standard deviations at or below this value are treated as zero.

Floating-point arithmetic can turn a mathematically constant series into one
with a standard deviation of ~1e-18. Without a tolerance, that would yield a
meaningless Sharpe ratio of ~1e16. Returns are dimensionless decimals, so an
absolute tolerance is appropriate.

Measured on 2026-10-13 (see D-025): the noise std of constant series up to 0.1
in magnitude was at most ~3e-17; the smallest realistic periodic std (daily
T-bill-like returns) is ~1e-5. Limitations: the tolerance is absolute, not
relative, so a genuine std below 1e-12 would be treated as zero, and noise grows
with return magnitude (irrelevant for realistic decimal returns).
"""

WEIGHT_SUM_TOLERANCE = 1e-6
"""Maximum allowed absolute deviation of a weight row's sum from 1.

Large enough to accept floating-point (including float32) rounding in weights
computed elsewhere; small enough to catch real allocation errors such as an
omitted cash column (a 0.0001 % allocation error is the largest accepted).
"""

__all__ = [
    "WEIGHT_SUM_TOLERANCE",
    "ZERO_VOLATILITY_TOLERANCE",
    "MaxDrawdown",
    "UndefinedMetricError",
    "annual_to_periodic_rate",
    "annualized_return",
    "annualized_turnover",
    "annualized_volatility",
    "cumulative_return",
    "drawdown_series",
    "max_drawdown",
    "portfolio_returns",
    "portfolio_turnover",
    "sharpe_ratio",
]


class UndefinedMetricError(ValueError):
    """Raised when a metric is mathematically undefined for valid input.

    Example: the Sharpe ratio of a series whose excess returns have zero
    volatility. Callers decide how to record this (e.g. as "undefined" in a table).
    """


@dataclass(frozen=True)
class MaxDrawdown:
    """Result of :func:`max_drawdown`.

    Attributes:
        max_drawdown: Largest peak-to-trough decline as a non-positive decimal
            fraction (e.g. -0.25 for a 25 % decline; 0.0 if there is no decline).
        peak_index: Position of the running peak from which the maximum
            drawdown is measured.
        trough_index: Position of the lowest point of the maximum drawdown.
            Equal to ``peak_index`` when ``max_drawdown == 0``.
    """

    max_drawdown: float
    peak_index: int
    trough_index: int


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------


def _as_real_array(values: ArrayLike, name: str, kind: str) -> NDArray[np.generic]:
    """Convert ``values`` to a NumPy array of real numbers (int or float), any shape."""
    if values is None or isinstance(values, str | bytes):
        raise TypeError(f"{name} must be a {kind}, got {type(values).__name__}")
    try:
        array = np.asarray(values)
    except ValueError as exc:  # e.g. ragged nested lists
        raise ValueError(f"{name} must be a {kind}: {exc}") from exc

    if array.dtype == np.bool_ or not (
        np.issubdtype(array.dtype, np.integer) or np.issubdtype(array.dtype, np.floating)
    ):
        raise TypeError(f"{name} must contain real numbers, got dtype {array.dtype}")
    return array


def _as_1d_float_array(values: ArrayLike, name: str, min_length: int) -> NDArray[np.float64]:
    """Convert ``values`` to a 1-D float64 array, rejecting anything ambiguous."""
    array = _as_real_array(values, name, kind="1-D numeric sequence")
    if array.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got an array with shape {array.shape}")
    if array.size == 0:
        raise ValueError(f"{name} is empty")
    if array.size < min_length:
        raise ValueError(f"{name} needs at least {min_length} observations, got {array.size}")

    array = array.astype(np.float64)
    non_finite = ~np.isfinite(array)
    if non_finite.any():
        position = int(np.argmax(non_finite))
        raise ValueError(
            f"{name} contains a non-finite value ({array[position]}) at position {position}; "
            "handle missing data explicitly before computing metrics"
        )
    return array


def _validate_portfolio_values(values: ArrayLike) -> NDArray[np.float64]:
    array = _as_1d_float_array(values, "portfolio_values", min_length=2)
    non_positive = array <= 0
    if non_positive.any():
        position = int(np.argmax(non_positive))
        raise ValueError(
            f"portfolio_values must be strictly positive; got {array[position]} at "
            f"position {position}"
        )
    return array


def _validate_returns(returns: ArrayLike, min_length: int) -> NDArray[np.float64]:
    array = _as_1d_float_array(returns, "returns", min_length=min_length)
    below_total_loss = array < -1
    if below_total_loss.any():
        position = int(np.argmax(below_total_loss))
        raise ValueError(
            f"returns must be decimal returns >= -1 (a loss of at most 100 %); got "
            f"{array[position]} at position {position}. Were percentages passed instead "
            "of decimals?"
        )
    return array


def _validate_real_scalar(value: object, name: str) -> float:
    if isinstance(value, bool | np.bool_) or not isinstance(
        value, int | float | np.integer | np.floating
    ):
        raise TypeError(f"{name} must be a real number, got {type(value).__name__}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")
    return value


def _validate_periods_per_year(periods_per_year: object) -> float:
    value = _validate_real_scalar(periods_per_year, "periods_per_year")
    if value <= 0:
        raise ValueError(f"periods_per_year must be positive, got {value}")
    return value


def _validate_rate(rate: object, name: str) -> float:
    value = _validate_real_scalar(rate, name)
    if value <= -1:
        raise ValueError(f"{name} must be a decimal rate greater than -1, got {value}")
    return value


def _validate_weight_matrix(weights: ArrayLike, name: str) -> NDArray[np.float64]:
    """Validate a long-only weight matrix of shape (events, assets)."""
    array = _as_real_array(weights, name, kind="2-D numeric matrix of shape (events, assets)")
    if array.size == 0:
        raise ValueError(f"{name} is empty; it needs at least one event and one asset")
    if array.ndim != 2:
        raise ValueError(
            f"{name} must be 2-D with shape (events, assets), got shape {array.shape}; "
            "a single event must have shape (1, assets)"
        )

    array = array.astype(np.float64)
    non_finite = np.argwhere(~np.isfinite(array))
    if non_finite.size:
        row, col = (int(i) for i in non_finite[0])
        raise ValueError(f"{name} has a non-finite weight ({array[row, col]}) at [{row}, {col}]")

    negative = np.argwhere(array < 0)
    if negative.size:
        row, col = (int(i) for i in negative[0])
        raise ValueError(
            f"{name} has a negative weight ({array[row, col]}) at [{row}, {col}]; only "
            "long-only weights are supported"
        )

    row_sum_error = np.abs(array.sum(axis=1) - 1.0)
    bad_rows = np.flatnonzero(row_sum_error > WEIGHT_SUM_TOLERANCE)
    if bad_rows.size:
        row = int(bad_rows[0])
        raise ValueError(
            f"{name} row {row} sums to {array[row].sum()!r}, not 1 (tolerance "
            f"{WEIGHT_SUM_TOLERANCE}); include cash as a column if part of the portfolio is "
            "held in cash"
        )
    return array


def _sample_std(array: NDArray[np.float64]) -> float:
    """Sample standard deviation (ddof=1), snapped to 0.0 within tolerance."""
    std = float(np.std(array, ddof=1))
    return 0.0 if std <= ZERO_VOLATILITY_TOLERANCE else std


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def portfolio_returns(portfolio_values: ArrayLike) -> NDArray[np.float64]:
    """Simple period returns from a series of portfolio values.

    ``r_t = V_t / V_{t-1} - 1`` for ``t = 1, ..., n``.

    Args:
        portfolio_values: Portfolio values ``V_0, ..., V_n`` in chronological
            order, in any currency unit. Must be 1-D, finite, strictly positive,
            and have at least 2 observations.

    Returns:
        Array of ``n`` decimal returns. ``returns[i]`` is the return from
        observation ``i`` to ``i + 1``. The first observation has no preceding
        value, so it produces no return; it is omitted rather than filled with
        0 or NaN.

    Raises:
        TypeError: Non-numeric or boolean input.
        ValueError: Empty, fewer than 2 observations, not 1-D, NaN/inf, or a
            value <= 0.
    """
    values = _validate_portfolio_values(portfolio_values)
    return values[1:] / values[:-1] - 1.0


def annualized_volatility(returns: ArrayLike, periods_per_year: float) -> float:
    """Annualised volatility: sample standard deviation of returns times sqrt(N).

    ``sigma_ann = std(r, ddof=1) * sqrt(periods_per_year)``

    Square-root-of-time scaling assumes returns are independent and identically
    distributed across periods; autocorrelation makes it inexact.

    Args:
        returns: Periodic decimal returns (at least 2; finite; each >= -1).
        periods_per_year: Number of return periods per year, ``N`` (e.g. 252 or
            365 for daily data, 52 weekly, 12 monthly; the choice of convention
            is the caller's). Must be a positive finite number.

    Returns:
        Annualised volatility as a non-negative decimal. Exactly 0.0 when the
        sample standard deviation is within :data:`ZERO_VOLATILITY_TOLERANCE`.

    Raises:
        TypeError, ValueError: Invalid returns or ``periods_per_year``.
    """
    array = _validate_returns(returns, min_length=2)
    factor = _validate_periods_per_year(periods_per_year)
    return _sample_std(array) * math.sqrt(factor)


def annual_to_periodic_rate(annual_rate: float, periods_per_year: float) -> float:
    """Convert an annual rate to the equivalent compounded periodic rate.

    ``r_period = (1 + r_annual) ** (1 / N) - 1``

    Compounding the periodic rate over ``N`` periods reproduces the annual
    rate exactly. Example: an annual rate of 0.12682503 with N = 12 gives
    0.01 per month.

    Args:
        annual_rate: Annual decimal rate, greater than -1.
        periods_per_year: Positive finite number of periods per year.

    Returns:
        Periodic decimal rate.
    """
    rate = _validate_rate(annual_rate, "annual_rate")
    factor = _validate_periods_per_year(periods_per_year)
    # expm1/log1p keep precision for the small rates typical of daily periods.
    return math.expm1(math.log1p(rate) / factor)


def _periodic_risk_free(
    n_returns: int,
    periods_per_year: float,
    annual_risk_free_rate: float | None,
    periodic_risk_free_rate: ArrayLike | float | None,
) -> NDArray[np.float64] | float:
    if annual_risk_free_rate is not None and periodic_risk_free_rate is not None:
        raise ValueError("Pass either annual_risk_free_rate or periodic_risk_free_rate, not both")
    if annual_risk_free_rate is not None:
        return annual_to_periodic_rate(annual_risk_free_rate, periods_per_year)
    if periodic_risk_free_rate is None:
        return 0.0
    if np.ndim(periodic_risk_free_rate) == 0:
        return _validate_rate(periodic_risk_free_rate, "periodic_risk_free_rate")

    rates = _as_1d_float_array(periodic_risk_free_rate, "periodic_risk_free_rate", min_length=1)
    if rates.size != n_returns:
        raise ValueError(
            f"periodic_risk_free_rate has {rates.size} values but returns has {n_returns}"
        )
    if (rates <= -1).any():
        raise ValueError("periodic_risk_free_rate values must be greater than -1")
    return rates


def sharpe_ratio(
    returns: ArrayLike,
    periods_per_year: float,
    *,
    annual_risk_free_rate: float | None = None,
    periodic_risk_free_rate: ArrayLike | float | None = None,
) -> float:
    """Annualised Sharpe ratio of periodic returns.

    ``S_ann = sqrt(N) * mean(r_t - rf_t) / std(r_t - rf_t, ddof=1)``

    The risk-free rate must match the return frequency. Supply **at most one** of:

    * ``annual_risk_free_rate``: a constant annual decimal rate, converted to a
      periodic rate with :func:`annual_to_periodic_rate` (geometric compounding).
    * ``periodic_risk_free_rate``: a periodic decimal rate, either a scalar or
      one value per return (same length as ``returns``).

    If neither is supplied, the risk-free rate is 0.

    Uses the arithmetic mean and the sample standard deviation of excess
    returns. Annualising by sqrt(N) assumes i.i.d. returns.

    Args:
        returns: Periodic decimal returns (at least 2; finite; each >= -1).
        periods_per_year: Positive finite number of return periods per year.
        annual_risk_free_rate: Optional annual risk-free rate (decimal, > -1).
        periodic_risk_free_rate: Optional periodic risk-free rate(s) (decimal, > -1).

    Returns:
        Annualised Sharpe ratio (dimensionless; may be negative).

    Raises:
        UndefinedMetricError: The standard deviation of excess returns is zero
            (within :data:`ZERO_VOLATILITY_TOLERANCE`), so the ratio is undefined.
        TypeError, ValueError: Invalid inputs, or both risk-free arguments given.
    """
    array = _validate_returns(returns, min_length=2)
    factor = _validate_periods_per_year(periods_per_year)
    risk_free = _periodic_risk_free(
        array.size, factor, annual_risk_free_rate, periodic_risk_free_rate
    )

    excess = array - risk_free
    excess_std = _sample_std(excess)
    if excess_std == 0.0:
        raise UndefinedMetricError(
            "Sharpe ratio is undefined: excess returns have zero standard deviation"
        )
    return math.sqrt(factor) * float(np.mean(excess)) / excess_std


def drawdown_series(portfolio_values: ArrayLike) -> NDArray[np.float64]:
    """Drawdown from the running peak at every observation.

    ``P_t = max_{s <= t} V_s`` and ``D_t = V_t / P_t - 1``.

    The first observation is the initial peak, so ``D_0 = 0``. Any decline that
    began before the series starts is not visible.

    Args:
        portfolio_values: Portfolio values (1-D, finite, strictly positive, at
            least 2 observations).

    Returns:
        Array of non-positive decimal drawdowns, the same length as the input.
    """
    values = _validate_portfolio_values(portfolio_values)
    running_peak = np.maximum.accumulate(values)
    return values / running_peak - 1.0


def max_drawdown(portfolio_values: ArrayLike) -> MaxDrawdown:
    """Maximum peak-to-trough decline of a portfolio-value series.

    ``MDD = min_t D_t`` with ``D_t`` as in :func:`drawdown_series`.

    Tie-breaking rules:

    * If several observations share the deepest drawdown, the **earliest** is
      the trough.
    * The peak is the **latest** observation, at or before the trough, whose
      value equals the running peak. This is where the decline actually began.

    Args:
        portfolio_values: Portfolio values (1-D, finite, strictly positive, at
            least 2 observations).

    Returns:
        :class:`MaxDrawdown` with a non-positive ``max_drawdown`` and positional
        ``peak_index`` / ``trough_index``. With no decline, ``max_drawdown`` is
        0.0 and both indices are 0.
    """
    values = _validate_portfolio_values(portfolio_values)
    drawdowns = values / np.maximum.accumulate(values) - 1.0
    trough_index = int(np.argmin(drawdowns))
    # Search backwards from the trough so that argmax finds the latest peak.
    peak_index = trough_index - int(np.argmax(values[trough_index::-1]))
    return MaxDrawdown(
        max_drawdown=float(drawdowns[trough_index]),
        peak_index=peak_index,
        trough_index=trough_index,
    )


# --------------------------------------------------------------------------
# Whole-period return
# --------------------------------------------------------------------------


def cumulative_return(portfolio_values: ArrayLike) -> float:
    """Total return over the whole series: ``V_T / V_0 - 1``.

    Equal to compounding the periodic simple returns: ``prod(1 + r_t) - 1``.
    Only the first and last values enter the formula, but every value is
    validated, so a corrupt path (NaN, non-positive value) is still rejected.

    Args:
        portfolio_values: Portfolio values ``V_0, ..., V_T`` (1-D, finite,
            strictly positive, at least 2 observations).

    Returns:
        Cumulative return as a decimal, greater than -1 (e.g. 0.21 = +21 %).
    """
    values = _validate_portfolio_values(portfolio_values)
    return float(values[-1] / values[0] - 1.0)


def annualized_return(portfolio_values: ArrayLike, periods_per_year: float) -> float:
    """Geometric annualised return (CAGR): ``(V_T / V_0) ** (N / T) - 1``.

    ``T`` is the number of return periods observed (number of values minus 1)
    and ``N`` is ``periods_per_year``. This is the constant per-year growth rate
    that turns ``V_0`` into ``V_T`` over ``T / N`` years.

    It differs from the arithmetic ``mean(r_t) * N``: volatility drags the
    compounded growth below the arithmetic mean (e.g. +50 % then -50 % has an
    arithmetic mean of 0 but loses 25 % overall).

    **Short samples:** annualising a short period extrapolates it; one month of
    +5 % annualises to about +79.6 %. The formula does not correct for this; no
    minimum length is enforced here, so reports must state ``T`` and the period.

    Args:
        portfolio_values: Portfolio values ``V_0, ..., V_T`` (1-D, finite,
            strictly positive, at least 2 observations, i.e. ``T >= 1``).
        periods_per_year: Positive finite number of periods per year ``N``.

    Returns:
        Annualised return as a decimal, greater than -1 (may round to -1.0 for
        extreme short-period losses).

    Raises:
        ValueError: Invalid inputs, or a result too large to represent as a
            float (an extreme gain over a very short period).
    """
    values = _validate_portfolio_values(portfolio_values)
    factor = _validate_periods_per_year(periods_per_year)
    n_periods = values.size - 1
    log_growth = math.log(values[-1] / values[0])
    try:
        # expm1 keeps precision when the annualised return is close to 0.
        return math.expm1(log_growth * factor / n_periods)
    except OverflowError as exc:
        raise ValueError(
            f"annualized return is too large to represent: growth {values[-1] / values[0]!r} "
            f"over T={n_periods} periods with N={factor} periods per year. The observation "
            "period is too short to annualise meaningfully."
        ) from exc


# --------------------------------------------------------------------------
# Turnover
# --------------------------------------------------------------------------


def portfolio_turnover(
    pre_trade_weights: ArrayLike,
    post_trade_weights: ArrayLike,
    *,
    cash_column: int | None = None,
) -> NDArray[np.float64]:
    """Two-way turnover of each rebalance event.

    Two measures, selected by ``cash_column``:

    * ``cash_column=None`` (default, unchanged behaviour): sum over **every**
      column, ``tau_k = sum_i |w_post[k, i] - w_pre[k, i]|``. If a cash column is
      present, a cash-funded purchase counts twice (the asset leg and the cash
      leg). For a fully invested portfolio without a cash column, this equals the
      traded notional exactly.
    * ``cash_column=j``: **traded notional**, the sum over non-cash columns only,
      ``n_k = sum_{i != j} |w_post[k, i] - w_pre[k, i]|``. Cash is the settlement
      account, not a traded security, so its change is excluded. Rows are still
      validated in full, cash included (each row must sum to 1).

    With a cash column, writing B and S for the total non-cash weight bought and
    sold, the default gives ``2 * max(B, S)`` and ``cash_column`` gives ``B + S``.
    One-way turnover (half the default) is ``max(B, S)``. In general
    ``one-way <= traded notional <= default two-way``.

    Each row ``k`` is one rebalance event:

    * ``pre_trade_weights[k]``: the **actual** weights immediately before
      trading, i.e. after market movements since the previous rebalance have
      made the weights drift. They must be computed by the caller; this
      function does not infer drift, dates or asset returns.
    * ``post_trade_weights[k]``: the target weights immediately after trading.

    Comparing consecutive *target* allocations is not a substitute: returning
    to an unchanged target after drift still requires trading.

    Both matrices must use the same asset ordering and must both include or
    both exclude a cash column. If the portfolio can hold cash, include it as a
    column so that each row sums to 1. With the default, moving weight into or
    out of cash then counts on both legs (asset -> cash of 0.10 gives 0.20); with
    ``cash_column`` set, the same trade gives 0.10.

    Initial funding (from all cash into the first allocation) is counted only
    if the caller includes it as a row.

    This function computes no transaction costs; how costs use these measures
    is open (decision D-031).

    Args:
        pre_trade_weights: Matrix of shape (events, assets).
        post_trade_weights: Matrix of the same shape.
        cash_column: ``None`` (default) to sum over all columns, or the
            0-based, non-negative index of the cash column to exclude it and
            measure traded notional. Negative indices are rejected to avoid
            ambiguity.

    Returns:
        Array of length ``events`` with values in [0, 2]: 0 means no trading,
        2 means the entire portfolio was replaced (sell everything, buy something
        else). With ``cash_column`` set, a purely cash-funded purchase or sale
        of the whole portfolio gives 1.

    Raises:
        TypeError: Non-numeric or boolean weights, or a non-integer
            ``cash_column`` (including booleans).
        ValueError: Empty, not 2-D, shape mismatch, non-finite or negative
            weights, a row not summing to 1 within :data:`WEIGHT_SUM_TOLERANCE`,
            or ``cash_column`` outside ``[0, assets - 1]``.
    """
    pre = _validate_weight_matrix(pre_trade_weights, "pre_trade_weights")
    post = _validate_weight_matrix(post_trade_weights, "post_trade_weights")
    if pre.shape != post.shape:
        raise ValueError(
            f"pre_trade_weights has shape {pre.shape} but post_trade_weights has shape "
            f"{post.shape}; both must be (events, assets) with the same asset ordering"
        )
    weight_changes = np.abs(post - pre)
    if cash_column is None:
        return weight_changes.sum(axis=1)

    if isinstance(cash_column, bool | np.bool_) or not isinstance(cash_column, int | np.integer):
        raise TypeError(
            f"cash_column must be an integer column index or None, got {type(cash_column).__name__}"
        )
    n_assets = pre.shape[1]
    if not 0 <= cash_column < n_assets:
        raise ValueError(
            f"cash_column must be in [0, {n_assets - 1}] for {n_assets} columns, got "
            f"{cash_column}; negative indices are not accepted"
        )
    return np.delete(weight_changes, int(cash_column), axis=1).sum(axis=1)


def annualized_turnover(
    event_turnover: ArrayLike, observation_periods: int, periods_per_year: float
) -> float:
    """Average two-way turnover per year over an evaluation window.

    ``annual_turnover = sum_k tau_k * N / T_obs``

    The aggregate inherits the measure of its input: pass per-event values from
    one consistent :func:`portfolio_turnover` call (default or ``cash_column``)
    and report which measure was used.

    Args:
        event_turnover: Per-event turnover from :func:`portfolio_turnover`, for
            all rebalance events inside the window (1-D; values in [0, 2]). An
            empty sequence means no rebalancing and gives 0.0.
        observation_periods: ``T_obs``, the number of return periods in the
            evaluation window (positive integer), independent of how many
            events occurred. E.g. 252 daily periods with 12 monthly rebalances.
        periods_per_year: Positive finite number of periods per year ``N``.

    Returns:
        Annual turnover per year as a Python ``float`` decimal, in the same
        measure as the input events. For default (all-column) events, 1.5 means
        weight changes summing to 150 % of portfolio value per year, counting
        both legs, including any cash leg. For ``cash_column`` events, it is
        annual traded notional, where only non-cash legs are counted.
    """
    factor = _validate_periods_per_year(periods_per_year)
    if isinstance(observation_periods, bool | np.bool_) or not isinstance(
        observation_periods, int | np.integer
    ):
        raise TypeError(
            f"observation_periods must be an integer, got {type(observation_periods).__name__}"
        )
    if observation_periods <= 0:
        raise ValueError(f"observation_periods must be positive, got {observation_periods}")

    array = _as_real_array(event_turnover, "event_turnover", kind="1-D numeric sequence")
    if array.ndim != 1:
        raise ValueError(f"event_turnover must be 1-D, got an array with shape {array.shape}")
    if array.size == 0:
        return 0.0  # no rebalance events: nothing was traded

    array = _as_1d_float_array(array, "event_turnover", min_length=1)
    max_turnover = 2.0 + 2.0 * WEIGHT_SUM_TOLERANCE
    out_of_range = (array < 0) | (array > max_turnover)
    if out_of_range.any():
        position = int(np.argmax(out_of_range))
        raise ValueError(
            f"event_turnover values must be in [0, 2] (two-way turnover); got "
            f"{array[position]} at position {position}"
        )
    # int(...) so that a NumPy integer cannot turn the result into np.float64.
    return float(array.sum()) * factor / int(observation_periods)
