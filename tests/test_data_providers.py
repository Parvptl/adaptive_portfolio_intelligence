"""Tests for market-data providers and the retry policy (all offline)."""

from __future__ import annotations

import datetime as dt
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.data.providers import (
    MAX_RETRY_DELAY_SECONDS,
    CsvProvider,
    EmptyResponseError,
    InMemoryProvider,
    MalformedResponseError,
    PriceRequest,
    ProviderError,
    ProviderNotAvailableError,
    SyntheticProvider,
    TransientProviderError,
    YFinanceProvider,
    fetch_with_retry,
    make_provider,
    standardize_raw_frame,
)

JAN = PriceRequest("AAA", dt.date(2024, 1, 1), dt.date(2024, 1, 31))

# --------------------------------------------------------------------------
# Synthetic provider
# --------------------------------------------------------------------------


def test_synthetic_is_deterministic_and_weekday_only() -> None:
    first = SyntheticProvider().fetch(JAN)
    second = SyntheticProvider().fetch(JAN)
    pd.testing.assert_frame_equal(first, second)
    assert (first["date"].dt.dayofweek < 5).all()
    assert len(first) == 23  # weekdays in January 2024
    assert (first["adj_close"] > 0).all()
    np.testing.assert_array_equal(first["close"], first["adj_close"])  # no corporate actions


def test_synthetic_sub_range_matches_full_range() -> None:
    full = SyntheticProvider().fetch(JAN).set_index("date")
    part = SyntheticProvider().fetch(
        PriceRequest("AAA", dt.date(2024, 1, 10), dt.date(2024, 1, 12))
    )
    np.testing.assert_array_equal(full.loc[part["date"], "adj_close"], part["adj_close"])


def test_synthetic_tickers_differ() -> None:
    a = SyntheticProvider().fetch(JAN)["adj_close"]
    b = SyntheticProvider().fetch(PriceRequest("BBB", JAN.start, JAN.end))["adj_close"]
    assert not np.allclose(a, b)


def test_synthetic_empty_range_raises() -> None:
    weekend = PriceRequest("AAA", dt.date(2024, 1, 6), dt.date(2024, 1, 7))
    with pytest.raises(EmptyResponseError):
        SyntheticProvider().fetch(weekend)


# --------------------------------------------------------------------------
# Standardisation of raw frames
# --------------------------------------------------------------------------


def test_standardize_renames_columns_converts_timezones_and_filters_range() -> None:
    frame = pd.DataFrame(
        {
            "Date": pd.DatetimeIndex(
                ["2023-12-29", "2024-01-02", "2024-01-03"], tz="America/New_York"
            ),
            "Adj Close": [1.0, 2.0, 3.0],
            "Stock Splits": [0.0, 0.0, 2.0],
            "Unrelated": ["x", "y", "z"],
        }
    )
    result = standardize_raw_frame(frame, JAN)
    assert list(result.columns) == ["date", "adj_close", "stock_splits"]
    assert result["date"].dt.tz is None
    assert result["date"].tolist() == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]


def test_standardize_requires_date_column() -> None:
    with pytest.raises(MalformedResponseError, match="date"):
        standardize_raw_frame(pd.DataFrame({"adj_close": [1.0]}), JAN)


def test_standardize_rejects_unparsable_dates() -> None:
    with pytest.raises(MalformedResponseError, match="date"):
        standardize_raw_frame(pd.DataFrame({"date": ["not-a-date"], "adj_close": [1.0]}), JAN)


def test_standardize_empty_range_raises() -> None:
    frame = pd.DataFrame({"date": pd.to_datetime(["2023-06-01"]), "adj_close": [1.0]})
    with pytest.raises(EmptyResponseError, match="no observations"):
        standardize_raw_frame(frame, JAN)


# --------------------------------------------------------------------------
# CSV provider
# --------------------------------------------------------------------------


def test_csv_provider_reads_and_normalises(tmp_path: Path) -> None:
    (tmp_path / "AAA.csv").write_text(
        "Date,Adj Close,Close\n2024-01-02,10.5,11\n2024-01-03,10.25,11.5\n", encoding="utf-8"
    )
    frame = CsvProvider(tmp_path).fetch(JAN)
    assert list(frame.columns) == ["date", "close", "adj_close"]
    assert frame["adj_close"].tolist() == [10.5, 10.25]


def test_csv_provider_missing_file_is_actionable(tmp_path: Path) -> None:
    with pytest.raises(ProviderNotAvailableError, match=r"AAA\.csv"):
        CsvProvider(tmp_path).fetch(JAN)


def test_csv_provider_malformed_file(tmp_path: Path) -> None:
    (tmp_path / "AAA.csv").write_bytes(b"\xff\xfe\x00garbage\x00")
    with pytest.raises(MalformedResponseError):
        CsvProvider(tmp_path).fetch(JAN)


def test_csv_fingerprint_changes_with_content(tmp_path: Path) -> None:
    path = tmp_path / "AAA.csv"
    path.write_text("date,adj_close\n2024-01-02,1\n", encoding="utf-8")
    before = CsvProvider(tmp_path).fingerprint("AAA")
    path.write_text("date,adj_close\n2024-01-02,2\n", encoding="utf-8")
    assert CsvProvider(tmp_path).fingerprint("AAA") != before


def test_in_memory_provider_unknown_ticker() -> None:
    with pytest.raises(EmptyResponseError):
        InMemoryProvider({}).fetch(JAN)


def test_make_provider_unknown_name() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        make_provider("bloomberg", timeout_seconds=1.0, input_dir=Path())


# --------------------------------------------------------------------------
# Retry policy
# --------------------------------------------------------------------------


class ScriptedProvider:
    """Raises the scripted exceptions in order, then returns a frame."""

    name = "scripted"
    data_origin = "in_memory"

    def __init__(self, outcomes: list[Exception | None]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def version(self) -> str:
        return "test"

    def fetch(self, request: PriceRequest) -> pd.DataFrame:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if outcome is not None:
            raise outcome
        return pd.DataFrame({"date": [pd.Timestamp(request.start)], "adj_close": [1.0]})


def test_transient_errors_are_retried_with_backoff() -> None:
    sleeps: list[float] = []
    provider = ScriptedProvider(
        [TransientProviderError("timeout"), TransientProviderError("429"), None]
    )
    frame = fetch_with_retry(
        provider, JAN, max_retries=3, retry_delay_seconds=1.5, sleep=sleeps.append
    )
    assert len(frame) == 1
    assert provider.calls == 3
    assert sleeps == [1.5, 3.0]  # doubling delays


def test_retries_are_bounded() -> None:
    sleeps: list[float] = []
    provider = ScriptedProvider([TransientProviderError("down")] * 3)
    with pytest.raises(TransientProviderError, match="giving up after 3"):
        fetch_with_retry(provider, JAN, max_retries=2, retry_delay_seconds=1.0, sleep=sleeps.append)
    assert provider.calls == 3
    assert sleeps == [1.0, 2.0]


def test_retry_delay_is_capped() -> None:
    sleeps: list[float] = []
    provider = ScriptedProvider([TransientProviderError("x")] * 4 + [None])
    fetch_with_retry(provider, JAN, max_retries=4, retry_delay_seconds=50.0, sleep=sleeps.append)
    assert max(sleeps) == MAX_RETRY_DELAY_SECONDS


@pytest.mark.parametrize(
    "error",
    [EmptyResponseError("empty"), MalformedResponseError("bad"), ProviderNotAvailableError("x")],
)
def test_permanent_errors_are_not_retried(error: ProviderError) -> None:
    sleeps: list[float] = []
    provider = ScriptedProvider([error, None])
    with pytest.raises(type(error)):
        fetch_with_retry(provider, JAN, max_retries=5, retry_delay_seconds=1.0, sleep=sleeps.append)
    assert provider.calls == 1
    assert sleeps == []


def test_zero_retries_means_single_attempt() -> None:
    provider = ScriptedProvider([TransientProviderError("x")])
    with pytest.raises(TransientProviderError):
        fetch_with_retry(
            provider, JAN, max_retries=0, retry_delay_seconds=1.0, sleep=lambda _: None
        )
    assert provider.calls == 1


# --------------------------------------------------------------------------
# yfinance adapter, exercised against a fake module (no network)
# --------------------------------------------------------------------------


class YFRateLimitError(Exception):
    """Same class name as yfinance's rate-limit exception."""


def _install_fake_yfinance(monkeypatch: pytest.MonkeyPatch, behaviour: Any) -> dict[str, Any]:
    recorded: dict[str, Any] = {}

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            recorded["symbol"] = symbol

        def history(self, **kwargs: Any) -> Any:
            recorded["kwargs"] = kwargs
            if isinstance(behaviour, Exception):
                raise behaviour
            return behaviour

    module = types.ModuleType("yfinance")
    module.Ticker = FakeTicker  # type: ignore[attr-defined]
    module.__version__ = "0.0-fake"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", module)
    return recorded


def _yahoo_like_frame() -> pd.DataFrame:
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], tz="America/New_York", name="Date")
    return pd.DataFrame(
        {
            "Open": [1.0, 2.0],
            "Close": [10.0, 11.0],
            "Adj Close": [9.5, 10.6],
            "Volume": [100, 200],
            "Dividends": [0.0, 0.1],
            "Stock Splits": [0.0, 0.0],
        },
        index=index,
    )


def test_yfinance_success_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded = _install_fake_yfinance(monkeypatch, _yahoo_like_frame())
    provider = YFinanceProvider(timeout_seconds=12.0)
    frame = provider.fetch(JAN)
    assert recorded["symbol"] == "AAA"
    assert recorded["kwargs"]["end"] == "2024-02-01"  # exclusive end = request end + 1 day
    assert recorded["kwargs"]["auto_adjust"] is False
    assert recorded["kwargs"]["timeout"] == 12.0
    assert frame["date"].tolist() == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]
    assert frame["adj_close"].tolist() == [9.5, 10.6]
    assert frame["dividends"].tolist() == [0.0, 0.1]
    assert provider.version() == "yfinance 0.0-fake"


def test_yfinance_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_yfinance(monkeypatch, pd.DataFrame())
    with pytest.raises(EmptyResponseError, match="no rows"):
        YFinanceProvider().fetch(JAN)


def test_yfinance_non_frame_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_yfinance(monkeypatch, {"not": "a frame"})
    with pytest.raises(MalformedResponseError):
        YFinanceProvider().fetch(JAN)


@pytest.mark.parametrize("error", [YFRateLimitError("Too Many Requests"), TimeoutError("slow")])
def test_yfinance_transient_errors(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    _install_fake_yfinance(monkeypatch, error)
    with pytest.raises(TransientProviderError):
        YFinanceProvider().fetch(JAN)


def test_yfinance_other_errors_are_permanent(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_yfinance(monkeypatch, ValueError("unexpected payload"))
    with pytest.raises(ProviderError) as info:
        YFinanceProvider().fetch(JAN)
    assert not isinstance(info.value, TransientProviderError)


def test_yfinance_missing_package_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "yfinance", None)  # makes "import yfinance" fail
    with pytest.raises(ProviderNotAvailableError, match=r"\.\[data\]"):
        YFinanceProvider().fetch(JAN)
