"""Tests for raw-frame validation."""

from __future__ import annotations

import datetime as dt
import math

import pandas as pd
import pytest

from adaptive_portfolio.config import DataValidationConfig
from adaptive_portfolio.data.validation import DataValidationError, validate_raw_frame

RULES = DataValidationConfig(
    min_sessions=2,
    max_abs_return=0.4,
    max_calendar_gap_days=7,
    max_start_lag_days=7,
    max_end_lag_days=7,
)
START, END = dt.date(2024, 1, 1), dt.date(2024, 1, 10)


def frame(dates: list[str], prices: list[float | None], **extra: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(dates), "adj_close": prices, **extra})


def validate(df: pd.DataFrame, **kwargs: object) -> object:
    params = {"start": START, "end": END, "rules": RULES, **kwargs}
    return validate_raw_frame(df, "AAA", "adj_close", **params)  # type: ignore[arg-type]


GOOD = frame(["2024-01-02", "2024-01-03", "2024-01-08"], [10.0, 11.0, 12.0])


def test_valid_frame_summary() -> None:
    summary = validate(
        frame(
            ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-08"],
            [10.0, None, 11.0, 12.0],
            dividends=[0.0, 0.0, 0.25, 0.0],
            stock_splits=[0.0, 2.0, 0.0, 0.0],
        )
    )
    assert summary.rows == 4
    assert (summary.first_date, summary.last_date) == (dt.date(2024, 1, 2), dt.date(2024, 1, 8))
    assert summary.missing_price_rows == 1  # NaN is "missing", not an error
    assert summary.max_calendar_gap_days == 4  # 2024-01-04 -> 2024-01-08
    assert (summary.dividend_events, summary.split_events) == (1, 1)


def test_corporate_action_counts_absent_when_columns_missing() -> None:
    summary = validate(GOOD)
    assert summary.dividend_events is None and summary.split_events is None


@pytest.mark.parametrize(
    ("df", "message"),
    [
        (frame(["2024-01-02", "2024-01-02"], [1.0, 2.0]), "duplicate date 2024-01-02"),
        (frame(["2024-01-03", "2024-01-02"], [1.0, 2.0]), "not in increasing order"),
        (pd.DataFrame({"date": pd.to_datetime(["2024-01-02"])}), "missing column"),
        (frame([], []), "no observations"),
        (frame(["2023-12-29", "2024-01-02"], [1.0, 2.0]), "outside"),
        (frame(["2024-01-02", "2024-01-03"], [1.0, math.inf]), "infinite"),
        (frame(["2024-01-02", "2024-01-03"], [1.0, 0.0]), "non-positive"),
        (frame(["2024-01-02", "2024-01-03"], [1.0, -5.0]), "non-positive"),
        (frame(["2024-01-02", "2024-01-03"], [None, None]), "every adj_close value is missing"),
    ],
    ids=[
        "duplicate",
        "unsorted",
        "schema",
        "empty",
        "out-of-range",
        "inf",
        "zero",
        "negative",
        "all-missing",
    ],
)
def test_invalid_frames_rejected(df: pd.DataFrame, message: str) -> None:
    with pytest.raises(DataValidationError, match=message):
        validate(df)


def test_non_numeric_price_rejected() -> None:
    df = pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-02", "2024-01-03"]), "adj_close": [1.0, "n/a"]}
    )
    with pytest.raises(DataValidationError, match="non-numeric"):
        validate(df)


def test_late_start_is_insufficient_coverage() -> None:
    with pytest.raises(DataValidationError, match="insufficient coverage - first"):
        validate(GOOD, start=dt.date(2023, 12, 1))


def test_early_end_is_insufficient_coverage() -> None:
    with pytest.raises(DataValidationError, match="insufficient coverage - last"):
        validate(GOOD, end=dt.date(2024, 1, 31))


def test_large_gap_rejected() -> None:
    # 2024-01-02 -> 2024-01-12 is a 10-day gap (> 7): a missing block or non-daily data.
    df = frame(["2024-01-02", "2024-01-12"], [1.0, 2.0])
    with pytest.raises(DataValidationError, match="10-day gap"):
        validate(df, end=dt.date(2024, 1, 12))
