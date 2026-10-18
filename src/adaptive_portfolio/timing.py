"""Shared decision / execution / earned-return timing (decisions D-043, D-048, D-055).

Row positions refer to the processed return table, where row ``t`` holds the
close-to-close return ``P_t / P_{t-1} - 1``. With an execution lag of ``L``
observed sessions (rows, not calendar days):

* a decision at row ``d`` uses information dated ``<= d``;
* it is executed at the close of row ``x = d + L``;
* the new weights first earn the return of row ``x + 1 = d + L + 1``.

A decision belongs to a partition only if its decision row and its first earned
row lie in the same partition (partitions are contiguous, so the execution row
then does too). Otherwise it crosses a split boundary and is excluded.

The simulator, the backtest runner and ``features.next_period_targets`` all use
these functions, so the timing is defined in one place.
"""

from __future__ import annotations

from numbers import Integral

MAX_EXECUTION_LAG_SESSIONS = 5


def validate_execution_lag(lag: object) -> int:
    """Return ``lag`` as an int if it is a valid execution lag, else raise ``ValueError``."""
    if isinstance(lag, bool) or not isinstance(lag, Integral):
        raise ValueError(f"execution lag must be an integer number of sessions, got {lag!r}")
    if not 0 <= int(lag) <= MAX_EXECUTION_LAG_SESSIONS:
        raise ValueError(
            f"execution lag must be in [0, {MAX_EXECUTION_LAG_SESSIONS}] sessions, got {lag}"
        )
    return int(lag)


def execution_row(decision: int, lag: int) -> int:
    """Row at whose close a decision taken at row ``decision`` is executed."""
    return decision + validate_execution_lag(lag)


def first_earned_row(decision: int, lag: int) -> int:
    """First return row earned by the weights executed for ``decision``."""
    return execution_row(decision, lag) + 1


def last_evaluable_decision(last_row: int, lag: int) -> int:
    """Latest decision row whose first earned return is still at or before ``last_row``."""
    return last_row - validate_execution_lag(lag) - 1
