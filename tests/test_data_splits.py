"""Tests for chronological splits and for the absence of look-ahead in processing."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import DataValidationConfig, MissingDataConfig, SplitPeriod, Splits
from adaptive_portfolio.data.processing import (
    align_prices,
    apply_missing_data_policy,
    compute_returns,
)
from adaptive_portfolio.data.providers import PriceRequest, SyntheticProvider
from adaptive_portfolio.data.splits import SplitError, assign_temporal_splits, split_frame

SPLITS = Splits(
    train=SplitPeriod(dt.date(2024, 1, 2), dt.date(2024, 1, 4)),
    validation=SplitPeriod(dt.date(2024, 1, 8), dt.date(2024, 1, 9)),
    test=SplitPeriod(dt.date(2024, 1, 11), dt.date(2024, 1, 12)),
)
# 01-01 before train; 01-05 between train and validation; 01-10 between validation
# and test; 01-15 after test.
DATES = pd.DatetimeIndex(
    [
        "2024-01-01",
        "2024-01-02",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
        "2024-01-09",
        "2024-01-10",
        "2024-01-11",
        "2024-01-12",
        "2024-01-15",
    ],
    name="date",
)


def test_labels_follow_inclusive_boundaries() -> None:
    labels = assign_temporal_splits(DATES, SPLITS).labels
    assert labels.tolist() == [
        "excluded",
        "train",
        "train",
        "excluded",
        "validation",
        "validation",
        "excluded",
        "test",
        "test",
        "excluded",
    ]


def test_partitions_are_ordered_and_disjoint() -> None:
    assignment = assign_temporal_splits(DATES, SPLITS)
    by_name = {
        n: set(assignment.labels.index[assignment.labels == n])
        for n in ("train", "validation", "test")
    }
    assert not (by_name["train"] & by_name["validation"]) and not (
        by_name["validation"] & by_name["test"]
    )
    assert max(by_name["train"]) < min(by_name["validation"])
    assert max(by_name["validation"]) < min(by_name["test"])


def test_summary_counts() -> None:
    summary = assign_temporal_splits(DATES, SPLITS).summary()
    assert {n: p["count"] for n, p in summary["partitions"].items()} == {
        "train": 2,
        "validation": 2,
        "test": 2,
    }
    assert summary["partitions"]["train"]["first_date"] == "2024-01-02"
    assert summary["excluded"] == {"before_train": 1, "between_partitions": 2, "after_test": 1}


def test_assignment_is_reproducible() -> None:
    first = assign_temporal_splits(DATES, SPLITS)
    second = assign_temporal_splits(DATES.copy(), SPLITS)
    pd.testing.assert_series_equal(first.labels, second.labels)
    assert first.summary() == second.summary()


def test_insufficient_history_raises() -> None:
    short = DATES[: DATES.searchsorted(pd.Timestamp("2024-01-11"))]  # dates before the test period
    with pytest.raises(SplitError, match="insufficient history: test"):
        assign_temporal_splits(short, SPLITS)


def test_minimum_observations_enforced() -> None:
    with pytest.raises(SplitError, match="at least 3 required"):
        assign_temporal_splits(DATES, SPLITS, min_observations=3)
    with pytest.raises(SplitError, match="min_observations"):
        assign_temporal_splits(DATES, SPLITS, min_observations=0)


@pytest.mark.parametrize(
    ("dates", "message"),
    [
        (DATES[::-1], "chronological"),
        (DATES.append(DATES[:1]).sort_values(), "duplicates"),
    ],
    ids=["unsorted", "duplicates"],
)
def test_invalid_dates_rejected(dates: pd.DatetimeIndex, message: str) -> None:
    with pytest.raises(SplitError, match=message):
        assign_temporal_splits(dates, SPLITS)


def test_overlapping_specification_rejected() -> None:
    overlapping = Splits(
        train=SplitPeriod(dt.date(2024, 1, 2), dt.date(2024, 1, 9)),
        validation=SplitPeriod(dt.date(2024, 1, 8), dt.date(2024, 1, 9)),
        test=SplitPeriod(dt.date(2024, 1, 11), dt.date(2024, 1, 12)),
    )
    with pytest.raises(SplitError, match="without overlap"):
        assign_temporal_splits(DATES, overlapping)


def test_split_frame_partitions_rows() -> None:
    frame = pd.DataFrame({"x": range(len(DATES))}, index=DATES)
    assignment = assign_temporal_splits(DATES, SPLITS)
    parts = split_frame(frame, assignment)
    assert parts["train"]["x"].tolist() == [1, 2]
    assert parts["test"]["x"].tolist() == [7, 8]
    with pytest.raises(SplitError, match="does not match"):
        split_frame(frame.iloc[1:], assignment)


# --------------------------------------------------------------------------
# Leakage: future data must never change past outputs
# --------------------------------------------------------------------------

RULES = DataValidationConfig(min_sessions=2)
UNIVERSE = ["AAA", "BBB"]


def _synthetic(end: dt.date) -> dict[str, pd.DataFrame]:
    provider = SyntheticProvider()
    return {t: provider.fetch(PriceRequest(t, dt.date(2024, 1, 1), end)) for t in UNIVERSE}


def _returns(frames: dict[str, pd.DataFrame], policy: MissingDataConfig) -> pd.DataFrame:
    wide, calendar = align_prices(frames, UNIVERSE, "adj_close")
    return compute_returns(
        apply_missing_data_policy(wide, calendar, policy).prices, calendar, RULES
    )


def test_appending_future_data_does_not_change_past_returns() -> None:
    cutoff = dt.date(2024, 1, 31)
    past = _returns(_synthetic(cutoff), MissingDataConfig())
    full = _returns(_synthetic(dt.date(2024, 3, 29)), MissingDataConfig())
    pd.testing.assert_frame_equal(full.loc[: pd.Timestamp(cutoff)], past)


def test_future_missing_data_does_not_change_past_returns() -> None:
    policy = MissingDataConfig(policy="drop_sessions", max_dropped_sessions=1)
    cutoff = dt.date(2024, 1, 31)
    past = _returns(_synthetic(cutoff), policy)
    future = _synthetic(dt.date(2024, 3, 29))
    gap = future["BBB"]["date"] == pd.Timestamp("2024-02-15")
    future["BBB"] = future["BBB"].loc[~gap].reset_index(drop=True)  # missing after cutoff
    full = _returns(future, policy)
    pd.testing.assert_frame_equal(full.loc[: pd.Timestamp(cutoff)], past)
    assert full.loc["2024-02-16", "sessions_spanned"] == 2  # the gap is flagged, later only


def test_training_rows_use_only_training_period_prices() -> None:
    returns = _returns(_synthetic(dt.date(2024, 3, 29)), MissingDataConfig())
    splits = Splits(
        train=SplitPeriod(dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
        validation=SplitPeriod(dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
        test=SplitPeriod(dt.date(2024, 3, 1), dt.date(2024, 3, 29)),
    )
    assignment = assign_temporal_splits(returns.index, splits)
    train = split_frame(returns, assignment)["train"]
    assert train.index.max() <= pd.Timestamp("2024-01-31")
    assert train["period_start"].max() < pd.Timestamp("2024-01-31")
    # Documented boundary rule: the first validation return starts from the last training
    # price, which was observed before the validation period (not leakage).
    validation = split_frame(returns, assignment)["validation"]
    assert validation["period_start"].iloc[0] == train.index.max()
    assert np.isfinite(validation.iloc[0][UNIVERSE].to_numpy(dtype=float)).all()
