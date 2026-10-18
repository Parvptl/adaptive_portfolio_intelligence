"""Shared timing: the feature/target alignment and the simulator agree (lag 0 and lag 1).

Row ``t`` of a return table is the return from the close of ``t - 1`` to the close of
``t``. A decision at row ``d`` with lag ``L`` executes at the close of ``d + L`` and
first earns row ``d + L + 1`` (D-048, D-055).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import ConstraintsConfig
from adaptive_portfolio.evaluation.simulator import SimulationSettings, simulate
from adaptive_portfolio.features import BOUNDARY, next_period_targets
from adaptive_portfolio.timing import (
    execution_row,
    first_earned_row,
    last_evaluable_decision,
    validate_execution_lag,
)

OPEN = ConstraintsConfig(
    long_only=True, allow_cash=True, min_weight=0.0, max_weight=1.0, max_turnover=None
)
SETTINGS = SimulationSettings(
    initial_capital=100.0, cost_rate=0.0, cash_return=0.0, constraints=OPEN
)
# Distinct, recognisable returns: A's return on row t is (t + 1) / 100; B never moves.
N = 10
RETURNS = pd.DataFrame(
    {"A": [(t + 1) / 100 for t in range(N)], "B": [0.0] * N},
    index=pd.DatetimeIndex(pd.bdate_range("2024-01-01", periods=N), name="date"),
)
LABELS = pd.Series(["train"] * 4 + ["validation"] * 3 + ["test"] * 3, index=RETURNS.index)


def test_timing_arithmetic() -> None:
    assert (execution_row(3, 0), first_earned_row(3, 0)) == (3, 4)
    assert (execution_row(3, 1), first_earned_row(3, 1)) == (4, 5)
    # Last decision of a split ending at row 9 that still earns a row <= 9.
    assert last_evaluable_decision(9, 0) == 8
    assert last_evaluable_decision(9, 1) == 7


@pytest.mark.parametrize("lag", [-1, 6, 1.0, True, "1", None])
def test_invalid_lags_rejected(lag) -> None:
    with pytest.raises(ValueError, match="execution lag"):
        validate_execution_lag(lag)


@pytest.mark.parametrize("lag", [0, 1])
def test_targets_are_exactly_the_returns_the_simulator_credits(lag: int) -> None:
    targets = next_period_targets(RETURNS, LABELS, execution_lag_sessions=lag)
    assert len(targets) == N - (lag + 1)
    for d, (decision_date, row) in enumerate(targets.iterrows()):
        x = execution_row(d, lag)
        assert row["execution_date"] == RETURNS.index[x]
        # Simulate: decide at d to hold 100 % A, executed at x (the funding row), held to the end.
        ledger = simulate(
            RETURNS, {d: np.array([1.0, 0.0])}, lag=lag, window=(x, N - 1), settings=SETTINGS
        ).ledger
        assert ledger["date"].iloc[0] == RETURNS.index[x]
        assert ledger["decision_date"].iloc[0] == decision_date
        assert ledger["gross_return"].iloc[0] == 0.0  # the execution-day return is not earned
        # The first return the new weights earn is exactly the alignment target.
        assert ledger["date"].iloc[1] == row["target_date"]
        assert ledger["gross_return"].iloc[1] == pytest.approx(row["target_A"], abs=1e-15)


@pytest.mark.parametrize("lag", [0, 1])
def test_boundary_labels_match_the_backtest_drop_rule(lag: int) -> None:
    targets = next_period_targets(RETURNS, LABELS, execution_lag_sessions=lag)
    for split in ("train", "validation", "test"):
        rows = np.flatnonzero(LABELS.to_numpy() == split)
        s, e = int(rows[0]), int(rows[-1])
        kept = [d for d in range(s, e + 1) if d <= last_evaluable_decision(e, lag)]
        paired = [
            d
            for d in range(s, e + 1)
            if d < len(targets) and targets["pair_split"].iloc[d] == split
        ]
        assert kept == paired, (split, lag)
        # Every other decision row of the split is labelled boundary (or has no target).
        for d in range(s, e + 1):
            if d not in kept and d < len(targets):
                assert targets["pair_split"].iloc[d] == BOUNDARY


def test_lag_zero_keeps_the_milestone3_pairing() -> None:
    default = next_period_targets(RETURNS, LABELS)
    explicit = next_period_targets(RETURNS, LABELS, execution_lag_sessions=0)
    pd.testing.assert_frame_equal(default, explicit)
    assert (default["target_date"].to_numpy() == RETURNS.index[1:].to_numpy()).all()
    assert (default["execution_date"] == default.index).all()


def test_lag_one_marks_two_boundary_decisions_per_split_change() -> None:
    labels = next_period_targets(RETURNS, LABELS, execution_lag_sessions=1)["pair_split"]
    # Rows 2 and 3 (train) earn rows 4 and 5 (validation); rows 5 and 6 earn test rows.
    assert labels.tolist() == [
        "train", "train", BOUNDARY, BOUNDARY, "validation", BOUNDARY, BOUNDARY, "test",
    ]  # fmt: skip


def test_a_gap_inside_the_holding_interval_is_a_boundary() -> None:
    # Lag 1: decision row 0 earns row 2 via execution row 1. If row 1 carries another label,
    # the pair is not attributed to "train" even though rows 0 and 2 are both "train".
    labels = pd.Series(["train", "excluded"] + ["train"] * (N - 2), index=RETURNS.index)
    pairs = next_period_targets(RETURNS, labels, execution_lag_sessions=1)["pair_split"]
    assert pairs.iloc[0] == BOUNDARY
    assert pairs.iloc[2] == "train"
