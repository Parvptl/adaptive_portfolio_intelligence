"""Command-line interface for the market-data pipeline.

Usage (from the project root)::

    python scripts/market_data.py validate
    python scripts/market_data.py build --provider synthetic     # offline demo data
    python scripts/market_data.py build --provider yfinance      # live; needs .[data]
    python scripts/market_data.py build --cache-mode offline     # reuse snapshot only
    python scripts/market_data.py fetch                          # raw snapshot only
    python scripts/market_data.py report                         # print quality report
    python scripts/market_data.py split                          # re-derive the split

Exit status: 0 on success, 1 on configuration/data/provider/cache errors, 2 on
invalid command-line usage.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from adaptive_portfolio.config import (
    ALLOWED_CACHE_MODES,
    ALLOWED_PROVIDERS,
    DEFAULT_CONFIG_DIR,
    ConfigError,
    ProjectConfig,
    load_project_config,
)
from adaptive_portfolio.data.cache import CacheError, read_csv
from adaptive_portfolio.data.pipeline import (
    acquire_raw,
    build_dataset,
    create_provider,
    processed_dataset_dir,
    project_root_for,
)
from adaptive_portfolio.data.providers import ProviderError
from adaptive_portfolio.data.splits import SplitError, assign_temporal_splits
from adaptive_portfolio.data.validation import DataValidationError

logger = logging.getLogger("adaptive_portfolio.data")

HANDLED_ERRORS = (
    ConfigError,
    ProviderError,
    DataValidationError,
    CacheError,
    SplitError,
    FileNotFoundError,
)


def _add_source_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        choices=sorted(ALLOWED_PROVIDERS),
        help="override data.provider for this run",
    )
    parser.add_argument(
        "--cache-mode",
        choices=sorted(ALLOWED_CACHE_MODES),
        help="override data.cache.mode for this run",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market_data", description="Market-data pipeline (milestone 2)."
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="directory with data.yaml, environment.yaml, experiment.yaml "
        "(the project root is its parent)",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="warnings and errors only")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("validate", help="validate the configuration files")
    _add_source_options(commands.add_parser("fetch", help="acquire or verify the raw snapshot"))
    _add_source_options(commands.add_parser("build", help="run the full pipeline"))
    for name, text in (
        ("report", "print the quality report of a built dataset"),
        ("split", "re-derive the temporal split and compare with the saved one"),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--provider", choices=sorted(ALLOWED_PROVIDERS))
        sub.add_argument(
            "--dataset-dir",
            type=Path,
            help="processed dataset directory (default: the one for the current config)",
        )
    return parser


def _dataset_dir(args: argparse.Namespace, config: ProjectConfig, root: Path) -> Path:
    if args.dataset_dir is not None:
        return args.dataset_dir
    return processed_dataset_dir(config, root, args.provider or config.data.provider)


def _cmd_validate(config: ProjectConfig, root: Path) -> int:
    data = config.data
    print(f"Configuration OK (project root: {root})")
    print(f"  provider       : {data.provider}")
    print(f"  universe       : {', '.join(data.universe)}")
    print(f"  range          : {data.start_date} to {data.end_date} ({data.frequency})")
    print(f"  price field    : {data.price_field}")
    print(f"  cache mode     : {data.cache.mode}")
    print(f"  missing data   : {data.missing_data.policy}")
    if data.frequency != "daily":
        print("  NOTE: the market-data pipeline currently supports only daily data.")
    return 0


def _cmd_fetch(args: argparse.Namespace, config: ProjectConfig, root: Path) -> int:
    provider = create_provider(config.data, root, args.provider)
    result = acquire_raw(config.data, provider, root, cache_mode=args.cache_mode)
    origin = result.manifest["provider"]["data_origin"]
    print(f"{'CACHE HIT' if result.cache_status == 'hit' else 'FETCHED'}: {result.snapshot_dir}")
    print(f"  data origin    : {origin}")
    print(f"  retrieved (UTC): {result.manifest['retrieved_at_utc']}")
    return 0


def _cmd_build(args: argparse.Namespace, config: ProjectConfig, root: Path) -> int:
    result = build_dataset(config, root, provider_name=args.provider, cache_mode=args.cache_mode)
    report = result.report
    if report["data_origin"] in ("synthetic", "in_memory"):
        print("*** NOT MARKET DATA: this dataset is synthetic/fixture data. ***")
    status = "CACHE HIT" if result.acquisition.cache_status == "hit" else "FETCHED"
    print(f"{status}: raw snapshot {result.acquisition.snapshot_dir}")
    print(f"Processed dataset: {result.processed_dir}")
    print(f"  data origin    : {report['data_origin']}")
    print(f"  retrieved (UTC): {report['dataset']['retrieved_at_utc']}")
    print(
        f"  sessions       : {report['processed']['sessions']} "
        f"({report['processed']['first_session']} to {report['processed']['last_session']})"
    )
    print(f"  returns        : {report['returns']['rows']} rows")
    print(
        f"  missing data   : {report['missing_data']['missing_cells']} missing cell(s), "
        f"{len(report['missing_data']['dropped_sessions'])} dropped session(s)"
    )
    for name, part in report["splits"]["partitions"].items():
        print(f"  {name:<15}: {part['count']} rows ({part['first_date']} to {part['last_date']})")
    return 0


def _cmd_report(args: argparse.Namespace, config: ProjectConfig, root: Path) -> int:
    path = _dataset_dir(args, config, root) / "quality_report.md"
    if not path.is_file():
        raise FileNotFoundError(f"no quality report at {path}; run the 'build' command first")
    print(path.read_text(encoding="utf-8"))
    return 0


def _cmd_split(args: argparse.Namespace, config: ProjectConfig, root: Path) -> int:
    directory = _dataset_dir(args, config, root)
    returns_path, splits_path = directory / "returns.csv", directory / "splits.csv"
    for path in (returns_path, splits_path):
        if not path.is_file():
            raise FileNotFoundError(f"missing {path}; run the 'build' command first")
    dates = pd.DatetimeIndex(read_csv(returns_path)["date"], name="date")
    assignment = assign_temporal_splits(dates, config.experiment.splits)
    saved = read_csv(splits_path)
    reproduced = saved["date"].equals(pd.Series(dates)) and saved["split"].tolist() == list(
        assignment.labels
    )
    print(json.dumps(assignment.summary(), indent=2))
    if not reproduced:
        print("MISMATCH: saved splits.csv differs from the split derived from the current config")
        return 1
    print(f"Reproduced: {splits_path} matches the current configuration.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    level = logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)
    try:
        config = load_project_config(args.config_dir)
        root = project_root_for(args.config_dir)
        if args.command == "validate":
            return _cmd_validate(config, root)
        if args.command == "fetch":
            return _cmd_fetch(args, config, root)
        if args.command == "build":
            return _cmd_build(args, config, root)
        if args.command == "report":
            return _cmd_report(args, config, root)
        return _cmd_split(args, config, root)
    except HANDLED_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
