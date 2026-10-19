"""Episode decisions and the decision-aligned reward (decisions D-064, D-065).

Decisions ``d_0 < ... < d_K`` are the ``weekly`` decision rows of a split window from the
common start ``k0`` up to ``last_evaluable_decision(e, L)``, the same drop rule as the
baselines. The action chosen at ``d_k`` executes at ``x_k = d_k + L``.

Reward of step ``k`` (log growth after costs over ``(d_k, d_{k+1}]``):

* ``r_k = log(V_{d_{k+1}} / V_{d_k})`` for ``k < K`` and ``r_K = log(V_e / V_{d_K})``;
* ``V_t`` is the ledger value at the close of ``t`` after any trade; ``V_{d_0} = V_0`` (the
  initial capital) because the portfolio is still cash before the funding row ``x_0``.

Each interval contains the cost of executing action ``k`` (``x_k <= d_{k+1}`` is required)
and the returns of rows ``d_k + 1 .. d_{k+1}``; the first ``L`` of them are earned by the
previous holdings. The rewards telescope: ``sum_k r_k = log(V_e / V_0)``. The episode
terminates after ``r_K``; nothing is bootstrapped past ``e``.

The lag must be at least 1. With lag 0 an action executes at the close of its own decision
row, so its cost would fall in the previous step's interval; lag 0 is a backtest sensitivity
case (D-055), not supported by this reward.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import numpy as np
import pandas as pd

from adaptive_portfolio.baselines.strategies import decision_rows
from adaptive_portfolio.timing import (
    execution_row,
    last_evaluable_decision,
    validate_execution_lag,
)

DECISION_SCHEDULE = "weekly"  # D-065


class RewardError(ValueError):
    """Raised for inconsistent decision rows or portfolio values."""


def episode_decisions(
    dates: pd.DatetimeIndex, first_decision: int, last_row: int, lag: int
) -> list[int]:
    """Weekly decision rows from ``first_decision`` to the last evaluable decision."""
    last = last_evaluable_decision(last_row, lag)
    if first_decision > last:
        raise RewardError(f"no evaluable decision in rows [{first_decision}, {last_row}]")
    return [
        k for k in decision_rows(DECISION_SCHEDULE, dates, first_decision, last_row) if k <= last
    ]


def reward_intervals(decisions: Sequence[int], last_row: int, lag: int) -> list[tuple[int, int]]:
    """Row intervals ``(start, end]`` of each step: ``(d_k, d_{k+1}]`` and ``(d_K, e]``."""
    if validate_execution_lag(lag) < 1:
        raise RewardError("the decision-aligned reward needs an execution lag of at least 1")
    rows = [int(d) for d in decisions]
    if not rows:
        raise RewardError("an episode needs at least one decision")
    if rows[-1] > last_evaluable_decision(last_row, lag):
        raise RewardError(f"decision {rows[-1]} earns no return by row {last_row}")
    for current, following in pairwise(rows):
        if following <= current:
            raise RewardError("decision rows must be strictly increasing")
        if execution_row(current, lag) > following:
            raise RewardError(
                f"decision {current} executes at row {execution_row(current, lag)}, after the "
                f"next decision {following}: an order would still be pending"
            )
    return list(zip(rows, [*rows[1:], last_row], strict=True))


def log_growth(value_start: float, value_end: float) -> float:
    """``log(value_end / value_start)`` for finite, positive portfolio values."""
    for name, value in (("start", value_start), ("end", value_end)):
        if not (np.isfinite(value) and value > 0):
            raise RewardError(f"portfolio value at the {name} must be finite and > 0: {value}")
    return float(np.log(value_end / value_start))


def decision_aligned_rewards(
    values: pd.Series, decisions: Sequence[int], last_row: int, lag: int, initial_capital: float
) -> np.ndarray:
    """Rewards from a ledger: ``values`` maps row position -> value at that close.

    The first ledger row must be the funding execution ``x_0 = d_0 + lag``; ``V_{d_0}`` is
    then ``initial_capital``. ``values`` must cover every later interval end.
    """
    intervals = reward_intervals(decisions, last_row, lag)
    first_ledger_row = int(values.index.min())
    if first_ledger_row != execution_row(intervals[0][0], lag):
        raise RewardError(
            f"the ledger starts at row {first_ledger_row}, not at the funding execution "
            f"{execution_row(intervals[0][0], lag)} of the first decision"
        )

    def value_at(row: int) -> float:
        if row < first_ledger_row:
            return initial_capital
        if row not in values.index:
            raise RewardError(f"no ledger value for row {row}")
        return float(values.loc[row])

    return np.array([log_growth(value_at(s), value_at(e)) for s, e in intervals])
