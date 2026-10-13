"""Validate the project configuration and print a short summary.

Usage::

    python scripts/validate_config.py [--config-dir configs]

Exits with a non-zero status if any configuration file is invalid.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from adaptive_portfolio.config import ConfigError, load_project_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    args = parser.parse_args(argv)

    try:
        config = load_project_config(args.config_dir)
    except ConfigError as exc:
        print(f"Invalid configuration: {exc}", file=sys.stderr)
        return 1

    splits = config.experiment.splits
    print(f"Configuration OK ({args.config_dir})")
    print(f"  provider     : {config.data.provider} (provisional)")
    print(f"  universe     : {', '.join(config.data.universe)}")
    print(f"  frequency    : {config.data.frequency}")
    print(f"  train        : {splits.train.start} -> {splits.train.end}")
    print(f"  validation   : {splits.validation.start} -> {splits.validation.end}")
    print(f"  test         : {splits.test.start} -> {splits.test.end}")
    print(
        f"  costs (bps)  : {config.environment.transaction_cost_bps} + slippage "
        f"{config.environment.slippage_bps} (provisional)"
    )
    print(f"  seed         : {config.experiment.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
