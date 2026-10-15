"""Market-data providers: one small interface, several interchangeable sources.

A provider turns a :class:`PriceRequest` (one instrument, an inclusive date range)
into a *raw frame*: a pandas DataFrame with a ``date`` column (tz-naive, midnight)
and some of the :data:`RAW_COLUMNS`. Providers only acquire data; validation,
alignment, returns and storage happen elsewhere in :mod:`adaptive_portfolio.data`.

Errors are classified so that only *transient* failures are retried
(:func:`fetch_with_retry`); permanent problems (missing files, empty or malformed
responses) fail immediately with an actionable message.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RAW_COLUMNS = (
    "date",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "dividends",
    "stock_splits",
    "capital_gains",
)
"""Standard raw column names. Providers may return a subset; ``date`` is always present."""

MAX_RETRY_DELAY_SECONDS = 60.0


class ProviderError(RuntimeError):
    """Base class for errors raised while acquiring market data."""


class TransientProviderError(ProviderError):
    """Timeouts, connection failures or rate limits: a retry may succeed."""


class ProviderNotAvailableError(ProviderError):
    """The provider cannot be used here (missing optional package or input file)."""


class EmptyResponseError(ProviderError):
    """The provider returned no observations for the requested range."""


class MalformedResponseError(ProviderError):
    """The response lacks required columns or contains unparsable values."""


@dataclass(frozen=True)
class PriceRequest:
    """Daily history for one instrument over an inclusive date range."""

    ticker: str
    start: dt.date
    end: dt.date


class MarketDataProvider(Protocol):
    """Interface implemented by every provider."""

    name: str
    data_origin: str  # "live", "local_csv", "synthetic" or "in_memory"

    def version(self) -> str:
        """Version string of the underlying source, recorded in the manifest."""
        ...

    def fetch(self, request: PriceRequest) -> pd.DataFrame:
        """Return the raw frame for ``request`` or raise a :class:`ProviderError`."""
        ...


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def standardize_column_name(name: object) -> str:
    """'Adj Close' -> 'adj_close', 'Stock Splits' -> 'stock_splits'."""
    return str(name).strip().lower().replace(" ", "_")


def standardize_raw_frame(frame: pd.DataFrame, request: PriceRequest) -> pd.DataFrame:
    """Normalise column names and dates, keep known columns, restrict to the request range.

    Raises :class:`MalformedResponseError` if there is no usable ``date`` column, and
    :class:`EmptyResponseError` if no rows fall inside the requested range. Row order
    and duplicates are *not* changed here; they are checked during validation.
    """
    renamed = frame.rename(columns=standardize_column_name)
    if "date" not in renamed.columns:
        raise MalformedResponseError(
            f"{request.ticker}: response has no 'date' column (columns: {list(frame.columns)})"
        )
    try:
        dates = pd.to_datetime(renamed["date"])
    except (ValueError, TypeError) as exc:
        raise MalformedResponseError(f"{request.ticker}: unparsable dates: {exc}") from exc
    if dates.isna().any():
        raise MalformedResponseError(f"{request.ticker}: response contains empty dates")
    if getattr(dates.dt, "tz", None) is not None:
        dates = dates.dt.tz_localize(None)
    renamed = renamed.assign(date=dates.dt.normalize())

    columns = [c for c in RAW_COLUMNS if c in renamed.columns]
    in_range = (renamed["date"] >= pd.Timestamp(request.start)) & (
        renamed["date"] <= pd.Timestamp(request.end)
    )
    result = renamed.loc[in_range, columns].reset_index(drop=True)
    if result.empty:
        raise EmptyResponseError(
            f"{request.ticker}: no observations between {request.start} and {request.end}"
        )
    return result


def fetch_with_retry(
    provider: MarketDataProvider,
    request: PriceRequest,
    *,
    max_retries: int,
    retry_delay_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> pd.DataFrame:
    """Call ``provider.fetch``; retry only :class:`TransientProviderError`.

    At most ``1 + max_retries`` attempts are made. Delays double after each failed
    attempt, starting at ``retry_delay_seconds`` and capped at 60 s.
    """
    attempts = 1 + max_retries
    for attempt in range(1, attempts + 1):
        try:
            return provider.fetch(request)
        except TransientProviderError as exc:
            if attempt == attempts:
                raise TransientProviderError(
                    f"{request.ticker}: giving up after {attempts} attempt(s): {exc}"
                ) from exc
            delay = min(retry_delay_seconds * 2 ** (attempt - 1), MAX_RETRY_DELAY_SECONDS)
            logger.warning(
                "%s: transient error (attempt %d/%d): %s; retrying in %.1f s",
                request.ticker,
                attempt,
                attempts,
                exc,
                delay,
            )
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


# --------------------------------------------------------------------------
# Synthetic provider (deterministic, offline; NOT market data)
# --------------------------------------------------------------------------

_SYNTHETIC_EPOCH = dt.date(2000, 1, 1)


def _ticker_parameters(ticker: str) -> tuple[float, float, float, float]:
    """Deterministic per-ticker drift and phases derived from a hash of the ticker."""
    digest = hashlib.sha256(ticker.encode("utf-8")).digest()
    unit = [b / 255 for b in digest[:4]]
    drift = 0.0001 + 0.0003 * unit[0]  # log-price drift per calendar day
    return drift, 2 * math.pi * unit[1], 2 * math.pi * unit[2], 0.5 + unit[3]


class SyntheticProvider:
    """Deterministic generated prices for tests and offline demonstrations.

    Sessions are Monday-Friday (no holidays): this is **not** an exchange calendar.
    Each date's price is a closed-form function of the ticker and the date, so any
    sub-range of a request gives identical values for the shared dates. There are no
    corporate actions, so ``close`` equals ``adj_close``.
    """

    name = "synthetic"
    data_origin = "synthetic"

    def version(self) -> str:
        return "synthetic-v1"

    def fetch(self, request: PriceRequest) -> pd.DataFrame:
        dates = pd.bdate_range(request.start, request.end)
        if len(dates) == 0:
            raise EmptyResponseError(f"{request.ticker}: no weekdays in the requested range")
        drift, phase_slow, phase_fast, scale = _ticker_parameters(request.ticker)
        days = (dates - pd.Timestamp(_SYNTHETIC_EPOCH)).days.to_numpy(dtype=np.float64)
        log_price = (
            math.log(100.0)
            + drift * days
            + 0.08 * scale * np.sin(2 * math.pi * days / 365.0 + phase_slow)
            + 0.02 * np.sin(2 * math.pi * days / 9.0 + phase_fast)
        )
        price = np.exp(log_price)
        return standardize_raw_frame(
            pd.DataFrame(
                {"date": dates, "close": price, "adj_close": price, "volume": 1_000_000.0}
            ),
            request,
        )


# --------------------------------------------------------------------------
# In-memory provider (fixtures and tests)
# --------------------------------------------------------------------------


class InMemoryProvider:
    """Serve pre-built raw frames, e.g. hand-made fixtures in tests."""

    def __init__(
        self,
        frames: Mapping[str, pd.DataFrame],
        *,
        name: str = "in_memory",
        data_origin: str = "in_memory",
    ) -> None:
        self._frames = {ticker: frame.copy() for ticker, frame in frames.items()}
        self.name = name
        self.data_origin = data_origin
        self.calls: list[str] = []

    def version(self) -> str:
        return "in-memory-v1"

    def fetch(self, request: PriceRequest) -> pd.DataFrame:
        self.calls.append(request.ticker)
        if request.ticker not in self._frames:
            raise EmptyResponseError(f"{request.ticker}: not available from this provider")
        return standardize_raw_frame(self._frames[request.ticker], request)


# --------------------------------------------------------------------------
# Local CSV provider (offline)
# --------------------------------------------------------------------------


class CsvProvider:
    """Read ``<input_dir>/<TICKER>.csv`` files supplied by the researcher.

    Each file needs a ``date`` column and the configured price column (e.g.
    ``adj_close``; headers such as "Adj Close" are normalised). The files are the
    source of truth; their SHA-256 checksums are recorded so that the cache can
    detect when they change.
    """

    name = "csv"
    data_origin = "local_csv"

    def __init__(self, input_dir: Path) -> None:
        self.input_dir = input_dir

    def version(self) -> str:
        return "local-csv-v1"

    def path_for(self, ticker: str) -> Path:
        return self.input_dir / f"{ticker}.csv"

    def fingerprint(self, ticker: str) -> str:
        """SHA-256 of the source file (raises if it does not exist)."""
        return hashlib.sha256(self._require(ticker).read_bytes()).hexdigest()

    def _require(self, ticker: str) -> Path:
        path = self.path_for(ticker)
        if not path.is_file():
            raise ProviderNotAvailableError(
                f"{ticker}: expected local file {path}. Put one CSV per instrument there "
                "(columns: date plus the configured price field), or use "
                "--provider yfinance (network) or --provider synthetic (demo data)."
            )
        return path

    def fetch(self, request: PriceRequest) -> pd.DataFrame:
        path = self._require(request.ticker)
        try:
            frame = pd.read_csv(path, float_precision="round_trip")
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            raise MalformedResponseError(f"{request.ticker}: cannot parse {path}: {exc}") from exc
        return standardize_raw_frame(frame, request)


# --------------------------------------------------------------------------
# yfinance provider (live, optional dependency)
# --------------------------------------------------------------------------


def _is_transient(exc: BaseException) -> bool:
    """Heuristic: rate limits, timeouts and connection failures are worth retrying."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    transient_markers = ("RateLimit", "Timeout", "Connection", "Temporary")
    return any(marker in name for name in names for marker in transient_markers) or isinstance(
        exc, TimeoutError | ConnectionError
    )


class YFinanceProvider:
    """Daily history from Yahoo Finance through the unofficial ``yfinance`` package.

    Not authoritative: Yahoo can rate-limit, change or revise data without notice, and
    use is subject to Yahoo's terms. ``Adj Close`` is back-adjusted for splits and
    dividends; ``Close`` is split-adjusted only. Corporate-action columns
    (dividends, stock splits, capital gains) are kept in the raw snapshot.
    Requires ``pip install -e ".[data]"``.
    """

    name = "yfinance"
    data_origin = "live"

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._module = None

    def _yfinance(self):
        if self._module is None:
            try:
                import yfinance  # optional dependency, imported lazily
            except ImportError as exc:
                raise ProviderNotAvailableError(
                    'the yfinance package is not installed; run: pip install -e ".[data]"'
                ) from exc
            self._module = yfinance
        return self._module

    def version(self) -> str:
        return f"yfinance {getattr(self._yfinance(), '__version__', 'unknown')}"

    def fetch(self, request: PriceRequest) -> pd.DataFrame:
        yf = self._yfinance()
        try:
            history = yf.Ticker(request.ticker).history(
                start=request.start.isoformat(),
                # yfinance treats ``end`` as exclusive; add one day to include request.end.
                end=(request.end + dt.timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=False,
                actions=True,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:  # the package raises many unrelated exception types
            if _is_transient(exc):
                raise TransientProviderError(f"{request.ticker}: {exc}") from exc
            raise ProviderError(f"{request.ticker}: yfinance request failed: {exc}") from exc

        if history is None or not isinstance(history, pd.DataFrame):
            raise MalformedResponseError(f"{request.ticker}: yfinance returned {type(history)}")
        if history.empty:
            raise EmptyResponseError(
                f"{request.ticker}: yfinance returned no rows for {request.start}..{request.end} "
                "(unknown or delisted ticker, no data in range, or a silently suppressed error)"
            )
        return standardize_raw_frame(history.reset_index(), request)


def make_provider(name: str, *, timeout_seconds: float, input_dir: Path) -> MarketDataProvider:
    """Construct the provider named in the configuration."""
    if name == "csv":
        return CsvProvider(input_dir)
    if name == "synthetic":
        return SyntheticProvider()
    if name == "yfinance":
        return YFinanceProvider(timeout_seconds=timeout_seconds)
    raise ValueError(f"unknown provider {name!r}")
