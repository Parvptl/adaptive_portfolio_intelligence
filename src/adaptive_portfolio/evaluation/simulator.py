"""Transparent daily portfolio simulator (decisions D-048 to D-051, D-055, D-057).

Timing (execution lag ``L`` in observed sessions; returns as in the processed dataset,
row ``t`` = ``P_t / P_{t-1} - 1``; arithmetic shared via :mod:`adaptive_portfolio.timing`):

1. A target is *decided* at the close of decision row ``d`` from information dated <= ``d``.
2. It is *executed* at the close of row ``x = d + L``.
3. It earns returns from row ``x + 1`` onward (the interval ``(x, x+1]``), drifting with
   prices until the next execution. A weight can never earn a return dated <= ``x``.

Accounting for each ledger row ``t`` of an evaluation window (value before any trade = V):

* gross return ``g_t = sum_i w_i r_{i,t} + w_cash * rf`` using the weights held over
  ``(t-1, t]``, i.e. the weights recorded on the previous ledger row; then the weights
  drift: ``w_i <- w_i (1 + r_{i,t}) / (1 + g_t)`` (the pre-trade, drifted weights);
* if an execution happens at the close of ``t``: traded notional
  ``n_t = sum over non-cash assets |w_target - w_drifted|`` (milestone-1
  ``portfolio_turnover`` with ``cash_column``), cost fraction ``c_t = k * n_t`` with
  ``k = (transaction_cost_bps + slippage_bps) / 10^4``, deducted pro rata so that the
  post-trade weights equal the target;
* net return ``(1 + g_t)(1 - c_t) - 1``; value ``V_t = V_{t-1} (1 + net)``. The charge
  ``c_t * V_{t-1} (1 + g_t)`` is computed on the value *before* the cost; the value
  actually purchased is smaller by a factor ``(1 - c_t)``, a difference of order ``k^2``.

Ledger ``weight_*`` columns are the weights at the *end* of row ``t``: post-trade (equal
to the target) on execution rows, otherwise the drifted weights. They are the weights
that earn row ``t + 1``, not row ``t``.

``max_weight`` constrains *target* weights at execution (D-057). Between executions,
holdings drift with prices and may exceed it; no trade is triggered.

The first ledger row is the funding row ``x_0``: the portfolio starts as cash worth
``initial_capital``; its gross return is 0 and its net return is minus the funding cost
(if ``charge_initial_funding``). Hence ``prod(1 + net) = V_end / initial_capital``.

Weights are fractional, long-only and unlevered (``sum <= 1``); the remainder is cash.
Invalid settings (:class:`SimulationSettings` validates itself), invalid targets or lags,
non-finite returns, or a portfolio value that is not a finite positive number raise
:class:`SimulationError`; nothing is clipped, filled or dropped silently.

The accounting of one ledger row is implemented once, in :func:`step` (D-067).
:func:`simulate` runs a whole window by looping over it; a sequential caller (the planned
RL environment) calls it row by row with a :class:`PortfolioState`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from adaptive_portfolio.config import ConstraintsConfig
from adaptive_portfolio.evaluation.metrics import WEIGHT_SUM_TOLERANCE, portfolio_turnover
from adaptive_portfolio.timing import execution_row, first_earned_row, validate_execution_lag

CASH = "CASH"
# A full replacement of the portfolio trades a notional of 2; a cost rate of 0.5 would
# then consume the whole value. Rates must stay below this bound.
MAX_COST_RATE = 0.5


class SimulationError(ValueError):
    """Raised for invalid simulator inputs or portfolio states."""


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise SimulationError(f"{name} must be a real number, got {value!r}")
    number = float(value)
    if not np.isfinite(number):
        raise SimulationError(f"{name} must be finite, got {number}")
    return number


@dataclass(frozen=True)
class SimulationSettings:
    """Validated simulator settings (direct callers get the same checks as the config path)."""

    initial_capital: float
    cost_rate: float  # (transaction_cost_bps + slippage_bps) / 10_000
    cash_return: float  # periodic risk-free return earned by the cash weight
    constraints: ConstraintsConfig
    charge_initial_funding: bool = True

    def __post_init__(self) -> None:
        if _finite_number(self.initial_capital, "initial_capital") <= 0:
            raise SimulationError(f"initial_capital must be > 0, got {self.initial_capital}")
        cost = _finite_number(self.cost_rate, "cost_rate")
        if not 0 <= cost < MAX_COST_RATE:
            raise SimulationError(
                f"cost_rate must be in [0, {MAX_COST_RATE}) as a fraction of traded notional "
                f"(e.g. 15 bps = 0.0015), got {cost}"
            )
        if _finite_number(self.cash_return, "cash_return") <= -1:
            raise SimulationError(
                f"cash_return is a periodic rate and must be > -1, got {self.cash_return}"
            )
        if not isinstance(self.charge_initial_funding, bool):
            raise SimulationError("charge_initial_funding must be true or false")
        c = self.constraints
        if not isinstance(c, ConstraintsConfig):
            raise SimulationError("constraints must be a ConstraintsConfig")
        if not c.long_only:
            raise SimulationError("the simulator supports long-only portfolios only (D-050)")
        low = _finite_number(c.min_weight, "constraints.min_weight")
        high = _finite_number(c.max_weight, "constraints.max_weight")
        if not 0 <= low <= high <= 1 or high == 0:
            raise SimulationError(
                f"constraints need 0 <= min_weight <= max_weight <= 1 and max_weight > 0, "
                f"got min_weight {low}, max_weight {high}"
            )
        if c.max_turnover is not None:
            raise SimulationError(
                "constraints.max_turnover is not enforced by the simulator (D-031 open); "
                "pass None rather than a cap that would be silently ignored"
            )


@dataclass(frozen=True)
class SimulationResult:
    ledger: pd.DataFrame  # one row per ledger date (funding row first)
    executions: pd.DataFrame  # one row per executed target


def validate_target(
    weights: np.ndarray, assets: tuple[str, ...], constraints: ConstraintsConfig
) -> None:
    """Check one target vector against the documented constraints (D-050)."""
    _check_target(weights, len(assets), constraints)


def _check_target(weights: np.ndarray, n_assets: int, constraints: ConstraintsConfig) -> None:
    if weights.shape != (n_assets,):
        raise SimulationError(f"target has shape {weights.shape}, expected ({n_assets},)")
    if not np.isfinite(weights).all():
        raise SimulationError("target weights must be finite")
    if (weights < constraints.min_weight - WEIGHT_SUM_TOLERANCE).any():
        raise SimulationError(f"target weight below min_weight {constraints.min_weight}: {weights}")
    if (weights > constraints.max_weight + WEIGHT_SUM_TOLERANCE).any():
        raise SimulationError(f"target weight above max_weight {constraints.max_weight}: {weights}")
    total = float(weights.sum())
    if total > 1 + WEIGHT_SUM_TOLERANCE:
        raise SimulationError(f"target weights sum to {total} > 1: leverage is not permitted")
    if not constraints.allow_cash and abs(total - 1) > WEIGHT_SUM_TOLERANCE:
        raise SimulationError(f"target weights sum to {total}; cash is not allowed")


def _frozen(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array


@dataclass(frozen=True)
class PortfolioState:
    """Portfolio at the close of the last processed ledger row.

    ``weights`` are the end-of-row weights (assets in universe order, then cash; read-only).
    Before the funding row (``funded`` False) the portfolio is cash worth ``initial_capital``.
    """

    value: float
    weights: np.ndarray
    funded: bool

    @classmethod
    def initial(cls, settings: SimulationSettings, n_assets: int) -> PortfolioState:
        weights = np.zeros(n_assets + 1)
        weights[n_assets] = 1.0  # start fully in cash
        return cls(value=settings.initial_capital, weights=_frozen(weights), funded=False)


@dataclass(frozen=True)
class StepRecord:
    """Accounting of one ledger row (see the module docstring for the definitions)."""

    gross_return: float
    rebalanced: bool
    turnover_two_way: float
    traded_notional: float
    cost_fraction: float
    cost_value: float
    net_return: float
    value: float
    weights: np.ndarray  # end-of-row weights, equal to the new state's weights


def step(
    state: PortfolioState,
    asset_returns: np.ndarray | None,
    target: np.ndarray | None,
    settings: SimulationSettings,
    *,
    date: pd.Timestamp | None = None,
) -> tuple[PortfolioState, StepRecord]:
    """Advance the portfolio by one ledger row ``t``.

    Args:
        state: the portfolio at the close of row ``t - 1`` (or the unfunded initial state).
        asset_returns: the returns of row ``t`` in universe order. Ignored on the funding row
            (an unfunded state), whose gross return is 0 by convention.
        target: risky target weights executed at the close of ``t``, or None for no trade.
            The funding row requires a target.
        settings: capital, cost rate, cash return and constraints.
        date: the date of row ``t``, used in error messages only.
    """
    held = state.weights
    cash_index = len(held) - 1
    when = f" on {date.date()}" if date is not None else ""
    if not state.funded:
        if target is None:
            raise SimulationError("the first row of the window must be an execution (funding) row")
        gross = 0.0
    else:
        values = np.asarray(asset_returns, dtype=np.float64)
        if values.shape != (cash_index,):
            raise SimulationError(f"returns have shape {values.shape}, expected ({cash_index},)")
        if not np.isfinite(values).all():
            raise SimulationError(f"returns contain non-finite values{when}")
        gross = float(held[:cash_index] @ values + held[cash_index] * settings.cash_return)
        growth = 1.0 + gross
        if not growth > 0:  # also rejects NaN
            raise SimulationError(f"portfolio value would be <= 0{when} (gross {gross})")
        drifted = held.copy()
        drifted[:cash_index] *= 1.0 + values
        drifted[cash_index] *= 1.0 + settings.cash_return
        held = drifted / growth

    traded = two_way = cost = 0.0
    if target is not None:
        target = np.asarray(target, dtype=np.float64)
        _check_target(target, cash_index, settings.constraints)
        post = np.append(target, 1.0 - target.sum())
        post[cash_index] = max(post[cash_index], 0.0)  # remove -1e-16 rounding noise
        post = post / post.sum()
        pre_row, post_row = held[np.newaxis, :], post[np.newaxis, :]
        traded = float(portfolio_turnover(pre_row, post_row, cash_column=cash_index)[0])
        two_way = float(portfolio_turnover(pre_row, post_row)[0])
        charge = settings.charge_initial_funding or state.funded
        cost = settings.cost_rate * traded if charge else 0.0
        held = post

    # Same as (1 + g)(1 - c) - 1, but without adding and subtracting 1 (exact when c = 0).
    net = gross - cost * (1.0 + gross)
    value_before_cost = state.value * (1.0 + gross)
    value = state.value * (1.0 + net)
    if not (np.isfinite(value) and value > 0):  # rejects NaN, inf and <= 0
        raise SimulationError(f"portfolio value is not a finite positive number{when}: {value}")
    held = _frozen(held)
    record = StepRecord(
        gross_return=gross,
        rebalanced=target is not None,
        turnover_two_way=two_way,
        traded_notional=traded,
        cost_fraction=cost,
        cost_value=value_before_cost * cost,
        net_return=net,
        value=value,
        weights=held,
    )
    return PortfolioState(value=value, weights=held, funded=True), record


def simulate(
    returns: pd.DataFrame,
    targets: Mapping[int, np.ndarray],
    *,
    lag: int,
    window: tuple[int, int],
    settings: SimulationSettings,
) -> SimulationResult:
    """Simulate one evaluation window.

    Args:
        returns: asset returns (index: dates, columns: assets), complete and finite.
        targets: decision row position -> target weights (universe order).
        lag: execution lag in sessions (``x = d + lag``).
        window: inclusive positions ``(first, last)`` of the evaluation window. Executions
            must satisfy ``first <= x < last`` so that each earns at least one return inside
            the window; returns after ``last`` are never used.
        settings: capital, cost rate, cash return and constraints.
    """
    if not returns.index.is_monotonic_increasing or returns.index.has_duplicates:
        raise SimulationError("return dates must be unique and increasing")
    values = returns.to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        raise SimulationError("returns contain non-finite values")
    assets = tuple(returns.columns)
    first, last = window
    if not 0 <= first < last < len(returns):
        raise SimulationError(f"invalid evaluation window {window} for {len(returns)} rows")
    if not isinstance(settings, SimulationSettings):
        raise SimulationError("settings must be a SimulationSettings instance")
    try:
        lag = validate_execution_lag(lag)
    except ValueError as exc:
        raise SimulationError(str(exc)) from None

    executions: dict[int, tuple[int, np.ndarray]] = {}
    for decision, weights in sorted(targets.items()):
        execution = execution_row(decision, lag)
        if not (first <= execution and first_earned_row(decision, lag) <= last):
            raise SimulationError(
                f"decision at row {decision} executes at row {execution}, outside "
                f"[{first}, {last}) of the evaluation window"
            )
        target = np.asarray(weights, dtype=np.float64)
        validate_target(target, assets, settings.constraints)
        executions[execution] = (decision, target)
    if first not in executions:
        raise SimulationError("the first row of the window must be an execution (funding) row")

    columns = [*assets, CASH]
    state = PortfolioState.initial(settings, len(assets))
    records: list[dict[str, object]] = []
    execution_records: list[dict[str, object]] = []

    for t in range(first, last + 1):
        decision, target = executions.get(t, (None, None))
        state, row = step(state, values[t], target, settings, date=returns.index[t])
        held = row.weights
        decision_date = pd.NaT
        if decision is not None:
            decision_date = returns.index[decision]
            execution_records.append(
                {
                    "decision_date": decision_date,
                    "execution_date": returns.index[t],
                    **{f"target_{c}": held[i] for i, c in enumerate(columns)},
                }
            )
        records.append(
            {
                "date": returns.index[t],
                "gross_return": row.gross_return,
                "rebalanced": row.rebalanced,
                "decision_date": decision_date,
                "turnover_two_way": row.turnover_two_way,
                "traded_notional": row.traded_notional,
                "cost_fraction": row.cost_fraction,
                "cost_value": row.cost_value,
                "net_return": row.net_return,
                "value": row.value,
                **{f"weight_{c}": held[i] for i, c in enumerate(columns)},
            }
        )

    ledger = pd.DataFrame.from_records(records)
    peak = np.maximum.accumulate(np.r_[settings.initial_capital, ledger["value"].to_numpy()])[1:]
    ledger.insert(ledger.columns.get_loc("value") + 1, "drawdown", ledger["value"] / peak - 1.0)
    return SimulationResult(ledger=ledger, executions=pd.DataFrame.from_records(execution_records))
