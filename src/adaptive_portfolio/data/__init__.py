"""Market-data pipeline: acquisition, validation, alignment, returns, splits, reporting.

Implemented in milestone 2 (see docs/technical_handbook.md, section 11):

* ``providers``  - provider interface; csv, synthetic, in-memory and yfinance sources
* ``cache``      - raw snapshots with manifests and checksums
* ``validation`` - raw-frame checks (dates, prices, coverage, gaps)
* ``processing`` - observed calendar, missing-data policy, simple returns
* ``splits``     - chronological train / validation / test assignment
* ``report``     - dataset-quality report (JSON and Markdown)
* ``pipeline``   - end-to-end build; ``cli`` - command-line interface

Not implemented here: exchange calendars, intraday data, total-return
reconstruction from dividends, survivorship-free universes.
"""

from adaptive_portfolio.data.pipeline import BuildResult, build_dataset, project_root_for
from adaptive_portfolio.data.processing import ProcessedPrices
from adaptive_portfolio.data.providers import (
    CsvProvider,
    InMemoryProvider,
    MarketDataProvider,
    PriceRequest,
    SyntheticProvider,
    YFinanceProvider,
)
from adaptive_portfolio.data.splits import SplitAssignment, assign_temporal_splits, split_frame
from adaptive_portfolio.data.validation import DataValidationError

__all__ = [
    "BuildResult",
    "CsvProvider",
    "DataValidationError",
    "InMemoryProvider",
    "MarketDataProvider",
    "PriceRequest",
    "ProcessedPrices",
    "SplitAssignment",
    "SyntheticProvider",
    "YFinanceProvider",
    "assign_temporal_splits",
    "build_dataset",
    "project_root_for",
    "split_frame",
]
