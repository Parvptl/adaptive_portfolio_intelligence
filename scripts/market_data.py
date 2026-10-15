"""Run the market-data pipeline: validate, fetch, build, report, split.

Usage::

    python scripts/market_data.py --help
    python scripts/market_data.py build --provider synthetic

See ``adaptive_portfolio.data.cli`` and the README section "Market-data pipeline".
"""

from __future__ import annotations

from adaptive_portfolio.data.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
