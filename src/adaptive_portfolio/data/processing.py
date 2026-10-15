"""Turn validated raw frames into the canonical price table and simple returns.

Definitions (see docs/technical_handbook.md, "Market-data pipeline"):

* **Observed calendar**: the sorted union of dates on which *any* instrument has a
  price. No exchange calendar is assumed; a session exists only if data show it.
* **Missing cell**: an instrument without a price on an observed session.
* **Missing-data policy**: ``error`` (default) stops; ``drop_sessions`` removes the
  affected sessions for *all* instruments and records them. Prices are never
  forward-filled or interpolated.
* **Returns**: simple returns ``r_t = P_t / P_prev - 1`` between consecutive
  *retained* sessions, computed with
  :func:`adaptive_portfolio.evaluation.portfolio_returns` (convention D-021). Each
  return row records ``period_start`` and ``sessions_spanned`` (1 normally; more
  than 1 if sessions in between were dropped), so a multi-session return is never
  mistaken for an ordinary one-session return.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from adaptive_portfolio.config import DataValidationConfig, MissingDataConfig
from adaptive_portfolio.data.validation import DataValidationError
from adaptive_portfolio.evaluation import portfolio_returns


@dataclass(frozen=True)
class DroppedSession:
    """A session removed by the ``drop_sessions`` policy, and why."""

    date: pd.Timestamp
    missing_instruments: tuple[str, ...]


@dataclass(frozen=True)
class ProcessedPrices:
    """Aligned prices after the missing-data policy."""

    prices: pd.DataFrame  # index: DatetimeIndex "date"; columns: instruments (config order)
    calendar: pd.DatetimeIndex  # all observed sessions, before any were dropped
    missing_cells: int
    dropped_sessions: tuple[DroppedSession, ...]


def align_prices(
    raw_frames: Mapping[str, pd.DataFrame], universe: Sequence[str], price_field: str
) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """Wide table on the observed calendar; NaN marks a missing cell."""
    columns = {}
    for instrument in universe:
        frame = raw_frames[instrument]
        series = pd.Series(
            pd.to_numeric(frame[price_field], errors="raise").to_numpy(dtype=np.float64),
            index=pd.DatetimeIndex(pd.to_datetime(frame["date"]), name="date"),
        ).dropna()
        columns[instrument] = series
    wide = pd.DataFrame(columns).sort_index()
    wide.index.name = "date"
    wide.columns.name = None
    return wide[list(universe)], pd.DatetimeIndex(wide.index, name="date")


def apply_missing_data_policy(
    wide: pd.DataFrame, calendar: pd.DatetimeIndex, policy: MissingDataConfig
) -> ProcessedPrices:
    """Apply the configured policy; never fills values."""
    missing_mask = wide.isna()
    missing_cells = int(missing_mask.to_numpy().sum())
    affected = missing_mask.any(axis=1)
    if not affected.any():
        return ProcessedPrices(wide.copy(), calendar, 0, ())

    dropped = tuple(
        DroppedSession(
            date=date, missing_instruments=tuple(wide.columns[missing_mask.loc[date].to_numpy()])
        )
        for date in wide.index[affected.to_numpy()]
    )
    if policy.policy == "error":
        preview = ", ".join(
            f"{d.date.date()} ({'/'.join(d.missing_instruments)})" for d in dropped[:5]
        )
        raise DataValidationError(
            f"{missing_cells} missing price(s) on {len(dropped)} session(s), e.g. {preview}. "
            "missing_data.policy is 'error'; inspect the raw data, or set policy "
            "'drop_sessions' with an explicit max_dropped_sessions."
        )
    if len(dropped) > policy.max_dropped_sessions:
        raise DataValidationError(
            f"{len(dropped)} session(s) would be dropped for missing prices, more than "
            f"missing_data.max_dropped_sessions={policy.max_dropped_sessions}; first: "
            f"{dropped[0].date.date()} ({'/'.join(dropped[0].missing_instruments)})"
        )
    return ProcessedPrices(wide.loc[~affected].copy(), calendar, missing_cells, dropped)


def compute_returns(
    prices: pd.DataFrame, calendar: pd.DatetimeIndex, rules: DataValidationConfig
) -> pd.DataFrame:
    """Simple returns between consecutive retained sessions.

    Output columns: ``period_start`` (previous retained session), ``sessions_spanned``
    (number of observed sessions from ``period_start`` to the row date), then one
    column per instrument. The first retained session has no return and is omitted.
    """
    if len(prices) < 2:
        raise DataValidationError("at least 2 sessions are needed to compute returns")
    returns = {
        instrument: portfolio_returns(prices[instrument].to_numpy())
        for instrument in prices.columns
    }
    positions = calendar.get_indexer(prices.index)
    if (positions < 0).any():
        raise DataValidationError("internal error: retained session missing from calendar")
    frame = pd.DataFrame(
        {
            "period_start": prices.index[:-1],
            "sessions_spanned": np.diff(positions).astype(np.int64),
            **returns,
        },
        index=pd.DatetimeIndex(prices.index[1:], name="date"),
    )

    values = frame[list(prices.columns)].to_numpy()
    too_large = np.abs(values) > rules.max_abs_return
    if too_large.any():
        row, col = (int(i) for i in np.argwhere(too_large)[0])
        raise DataValidationError(
            f"{prices.columns[col]}: return {values[row, col]:+.4f} on "
            f"{frame.index[row].date()} exceeds validation.max_abs_return="
            f"{rules.max_abs_return} - likely a data error such as an unadjusted split"
        )
    return frame


def prices_to_long(prices: pd.DataFrame, price_field: str) -> pd.DataFrame:
    """Canonical long table: one row per (date, instrument), sorted by date then config order."""
    # melt (not stack) behaves identically on pandas 2.2 and 3.x.
    long = (
        prices.rename_axis(index="date")
        .reset_index()
        .melt(id_vars="date", var_name="instrument", value_name=price_field)
    )
    order = {name: i for i, name in enumerate(prices.columns)}
    long["_order"] = long["instrument"].map(order)
    return long.sort_values(["date", "_order"]).drop(columns="_order").reset_index(drop=True)
