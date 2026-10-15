"""Tests for alignment, the missing-data policy and return construction.

Fixture (conftest): sessions 2024-01-02, 03, 04, 05, 08.
AAA = 100, 110, 99, 99, 108.9;  BBB = 50, 50, 55, (missing), 44.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import DataValidationConfig, MissingDataConfig
from adaptive_portfolio.data.processing import (
    align_prices,
    apply_missing_data_policy,
    compute_returns,
    prices_to_long,
)
from adaptive_portfolio.data.validation import DataValidationError
from adaptive_portfolio.evaluation import cumulative_return, portfolio_returns
from conftest import FIXTURE_DATES

RULES = DataValidationConfig(min_sessions=2)
DROP = MissingDataConfig(policy="drop_sessions", max_dropped_sessions=1)
TOL = 1e-12


def test_alignment_uses_observed_calendar_and_universe_order(fixture_frames) -> None:
    wide, calendar = align_prices(fixture_frames, ["BBB", "AAA"], "adj_close")
    assert list(wide.columns) == ["BBB", "AAA"]
    assert calendar.equals(pd.DatetimeIndex(pd.to_datetime(FIXTURE_DATES), name="date"))
    assert np.isnan(wide.loc["2024-01-05", "BBB"])  # missing cell is NaN, never filled
    assert wide.loc["2024-01-05", "AAA"] == 99.0


def test_session_missing_from_one_instrument_appears_in_calendar(fixture_frames) -> None:
    # Remove 2024-01-03 from BBB entirely: the calendar still contains it via AAA.
    frames = dict(fixture_frames)
    frames["BBB"] = frames["BBB"].drop(index=1)
    wide, calendar = align_prices(frames, ["AAA", "BBB"], "adj_close")
    assert pd.Timestamp("2024-01-03") in calendar
    assert np.isnan(wide.loc["2024-01-03", "BBB"])


def test_error_policy_reports_missing_cells(fixture_frames) -> None:
    wide, calendar = align_prices(fixture_frames, ["AAA", "BBB"], "adj_close")
    with pytest.raises(DataValidationError, match=r"1 missing price\(s\).*2024-01-05 \(BBB\)"):
        apply_missing_data_policy(wide, calendar, MissingDataConfig())


def test_drop_policy_drops_whole_session_and_records_it(fixture_frames) -> None:
    wide, calendar = align_prices(fixture_frames, ["AAA", "BBB"], "adj_close")
    result = apply_missing_data_policy(wide, calendar, DROP)
    assert result.missing_cells == 1
    assert [(d.date, d.missing_instruments) for d in result.dropped_sessions] == [
        (pd.Timestamp("2024-01-05"), ("BBB",))
    ]
    assert list(result.prices.index.strftime("%Y-%m-%d")) == [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-08",
    ]
    assert not result.prices.isna().to_numpy().any()
    assert len(result.calendar) == 5  # the calendar keeps the dropped session


def test_drop_policy_limit(fixture_frames) -> None:
    wide, calendar = align_prices(fixture_frames, ["AAA", "BBB"], "adj_close")
    with pytest.raises(DataValidationError, match="max_dropped_sessions=0"):
        apply_missing_data_policy(
            wide, calendar, MissingDataConfig(policy="drop_sessions", max_dropped_sessions=0)
        )


def _fixture_returns(fixture_frames) -> pd.DataFrame:
    wide, calendar = align_prices(fixture_frames, ["AAA", "BBB"], "adj_close")
    processed = apply_missing_data_policy(wide, calendar, DROP)
    return compute_returns(processed.prices, calendar, RULES)


def test_returns_hand_calculated(fixture_frames) -> None:
    returns = _fixture_returns(fixture_frames)
    # First session (2024-01-02) has no return. Retained sessions: 02, 03, 04, 08.
    assert list(returns.index.strftime("%Y-%m-%d")) == ["2024-01-03", "2024-01-04", "2024-01-08"]
    assert list(returns["period_start"].dt.strftime("%Y-%m-%d")) == [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
    ]
    # 01-08 follows the dropped 01-05: calendar positions 4 - 2 = 2 sessions spanned.
    assert returns["sessions_spanned"].tolist() == [1, 1, 2]
    # AAA: 110/100-1 = 0.10; 99/110-1 = -0.10; 108.9/99-1 = 0.10 (over two sessions)
    np.testing.assert_allclose(returns["AAA"], [0.10, -0.10, 0.10], rtol=0, atol=TOL)
    # BBB: 50/50-1 = 0; 55/50-1 = 0.10; 44/55-1 = -0.20 (over two sessions)
    np.testing.assert_allclose(returns["BBB"], [0.0, 0.10, -0.20], rtol=0, atol=TOL)


def test_returns_consistent_with_milestone1_metrics(fixture_frames) -> None:
    wide, calendar = align_prices(fixture_frames, ["AAA", "BBB"], "adj_close")
    prices = apply_missing_data_policy(wide, calendar, DROP).prices
    returns = compute_returns(prices, calendar, RULES)
    for name in prices.columns:
        np.testing.assert_array_equal(returns[name].to_numpy(), portfolio_returns(prices[name]))
        compounded = float(np.prod(1 + returns[name].to_numpy())) - 1
        assert compounded == pytest.approx(cumulative_return(prices[name]), abs=TOL)


def test_returns_are_chronological_and_finite(fixture_frames) -> None:
    returns = _fixture_returns(fixture_frames)
    assert returns.index.is_monotonic_increasing and returns.index.is_unique
    assert (returns["period_start"] < returns.index.to_series()).all()
    assert np.isfinite(returns[["AAA", "BBB"]].to_numpy()).all()


def test_implausible_return_rejected() -> None:
    # 100 -> 50 is -50 %: what an unadjusted 2:1 split looks like.
    prices = pd.DataFrame(
        {"AAA": [100.0, 50.0]}, index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="date")
    )
    with pytest.raises(DataValidationError, match=r"AAA: return -0\.5000 on 2024-01-03"):
        compute_returns(prices, prices.index, RULES)


def test_returns_need_two_sessions() -> None:
    prices = pd.DataFrame({"AAA": [100.0]}, index=pd.DatetimeIndex(["2024-01-02"], name="date"))
    with pytest.raises(DataValidationError, match="at least 2 sessions"):
        compute_returns(prices, prices.index, RULES)


def test_long_format_is_canonical(fixture_frames) -> None:
    wide, calendar = align_prices(fixture_frames, ["AAA", "BBB"], "adj_close")
    prices = apply_missing_data_policy(wide, calendar, DROP).prices
    long = prices_to_long(prices, "adj_close")
    assert list(long.columns) == ["date", "instrument", "adj_close"]
    assert not long.duplicated(["date", "instrument"]).any()
    assert len(long) == 4 * 2
    assert long.iloc[:2][["instrument", "adj_close"]].values.tolist() == [
        ["AAA", 100.0],
        ["BBB", 50.0],
    ]
    assert long["date"].is_monotonic_increasing
