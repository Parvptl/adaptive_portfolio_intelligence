"""Validation of raw provider frames before they enter the processed dataset.

Rules (see docs/technical_handbook.md, "Market-data pipeline"):

* the frame has a ``date`` column and the configured price column;
* dates are unique and strictly increasing (unsorted input is rejected, not sorted);
* prices are numeric; ``NaN`` means *missing* (handled later by the missing-data
  policy), while infinite or non-positive prices are *invalid* and raise;
* the instrument covers the requested range within the configured start/end lags;
* consecutive observed dates are never further apart than ``max_calendar_gap_days``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from adaptive_portfolio.config import DataValidationConfig


class DataValidationError(ValueError):
    """Raised when market data violates a validation rule."""


@dataclass(frozen=True)
class RawSummary:
    """Facts about one validated raw frame, used in the quality report."""

    instrument: str
    rows: int
    first_date: dt.date
    last_date: dt.date
    missing_price_rows: int
    max_calendar_gap_days: int
    dividend_events: int | None
    split_events: int | None


def _count_events(frame: pd.DataFrame, column: str) -> int | None:
    if column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return int((values != 0).sum())


def validate_raw_frame(
    frame: pd.DataFrame,
    instrument: str,
    price_field: str,
    start: dt.date,
    end: dt.date,
    rules: DataValidationConfig,
) -> RawSummary:
    """Check one instrument's raw frame; raise :class:`DataValidationError` on violations."""
    if not isinstance(frame, pd.DataFrame):
        raise DataValidationError(f"{instrument}: expected a DataFrame, got {type(frame)}")
    missing_columns = [c for c in ("date", price_field) if c not in frame.columns]
    if missing_columns:
        raise DataValidationError(
            f"{instrument}: missing column(s) {missing_columns}; available: {list(frame.columns)}"
        )
    if frame.empty:
        raise DataValidationError(f"{instrument}: no observations")

    dates = pd.to_datetime(frame["date"])
    duplicated = dates.duplicated()
    if duplicated.any():
        raise DataValidationError(
            f"{instrument}: duplicate date {dates[duplicated].iloc[0].date()} "
            f"({int(duplicated.sum())} duplicate row(s))"
        )
    steps = dates.diff().dropna()
    if (steps <= pd.Timedelta(0)).any():
        position = int(np.argmax((steps <= pd.Timedelta(0)).to_numpy())) + 1
        raise DataValidationError(
            f"{instrument}: dates are not in increasing order at row {position} "
            f"({dates.iloc[position - 1].date()} then {dates.iloc[position].date()})"
        )
    outside = (dates < pd.Timestamp(start)) | (dates > pd.Timestamp(end))
    if outside.any():
        raise DataValidationError(
            f"{instrument}: {int(outside.sum())} observation(s) outside {start}..{end}"
        )

    prices = pd.to_numeric(frame[price_field], errors="coerce")
    unparsable = prices.isna() & frame[price_field].notna()
    if unparsable.any():
        bad = frame[price_field][unparsable].iloc[0]
        raise DataValidationError(f"{instrument}: non-numeric {price_field} value {bad!r}")
    values = prices.to_numpy(dtype=np.float64)
    present = ~np.isnan(values)
    if np.isinf(values).any():
        raise DataValidationError(f"{instrument}: infinite {price_field} value")
    non_positive = present & (values <= 0)
    if non_positive.any():
        position = int(np.argmax(non_positive))
        raise DataValidationError(
            f"{instrument}: non-positive {price_field} {values[position]} on "
            f"{dates.iloc[position].date()}"
        )
    if not present.any():
        raise DataValidationError(f"{instrument}: every {price_field} value is missing")

    observed = dates[present]
    first, last = observed.iloc[0].date(), observed.iloc[-1].date()
    if (first - start).days > rules.max_start_lag_days:
        raise DataValidationError(
            f"{instrument}: insufficient coverage - first {price_field} observation is {first}, "
            f"more than {rules.max_start_lag_days} day(s) after start_date {start}. Use a later "
            "start_date or remove the instrument."
        )
    if (end - last).days > rules.max_end_lag_days:
        raise DataValidationError(
            f"{instrument}: insufficient coverage - last {price_field} observation is {last}, "
            f"more than {rules.max_end_lag_days} day(s) before end_date {end}."
        )

    gaps = observed.diff().dropna().dt.days
    max_gap = int(gaps.max()) if len(gaps) else 0
    if max_gap > rules.max_calendar_gap_days:
        position = int(np.argmax(gaps.to_numpy()))
        raise DataValidationError(
            f"{instrument}: {max_gap}-day gap between observations ending "
            f"{observed.iloc[position + 1].date()} exceeds max_calendar_gap_days="
            f"{rules.max_calendar_gap_days} (missing block of data or non-daily frequency)"
        )

    return RawSummary(
        instrument=instrument,
        rows=len(frame),
        first_date=first,
        last_date=last,
        missing_price_rows=int((~present).sum()),
        max_calendar_gap_days=max_gap,
        dividend_events=_count_events(frame, "dividends"),
        split_events=_count_events(frame, "stock_splits"),
    )
