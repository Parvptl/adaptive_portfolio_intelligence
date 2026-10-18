"""Command-line interface for the market-data pipeline.

Usage (from the project root)::

    python scripts/market_data.py validate
    python scripts/market_data.py build --provider synthetic     # offline demo data
    python scripts/market_data.py build --provider yfinance      # live; needs .[data]
    python scripts/market_data.py build --cache-mode offline     # reuse snapshot only
    python scripts/market_data.py fetch                          # raw snapshot only
    python scripts/market_data.py report                         # print quality report
    python scripts/market_data.py split                          # re-derive the split
    python scripts/market_data.py features --provider yfinance   # features + regimes (M3)
    python scripts/market_data.py features --thresholds FILE     # apply frozen thresholds
    python scripts/market_data.py regime-report --provider yfinance
    python scripts/market_data.py backtest --provider yfinance   # baselines: train + validation
    python scripts/market_data.py backtest-report --provider yfinance
    python scripts/market_data.py backtest --include-test ...    # final evaluation only (D-056)

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

from adaptive_portfolio.baselines.strategies import StrategyError
from adaptive_portfolio.config import (
    ALLOWED_CACHE_MODES,
    ALLOWED_PROVIDERS,
    DEFAULT_CONFIG_DIR,
    BacktestConfig,
    ConfigError,
    FeatureConfig,
    ProjectConfig,
    load_backtest_config,
    load_feature_config,
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
from adaptive_portfolio.evaluation.backtest import backtest_output_dir, run_backtest
from adaptive_portfolio.evaluation.simulator import SimulationError
from adaptive_portfolio.features.engineering import FeatureDataError
from adaptive_portfolio.features.pipeline import (
    build_feature_dataset,
    feature_output_dir,
    locate_dataset_dir,
)
from adaptive_portfolio.regimes.rules import RegimeCalibrationError

logger = logging.getLogger("adaptive_portfolio.data")

HANDLED_ERRORS = (
    ConfigError,
    ProviderError,
    DataValidationError,
    CacheError,
    SplitError,
    FeatureDataError,
    RegimeCalibrationError,
    SimulationError,
    StrategyError,
    FileNotFoundError,
)
BACKTEST_CONFIG_NAME = "backtest.yaml"

FEATURE_CONFIG_NAME = "features.yaml"


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
        prog="market_data", description="Market-data, feature and regime pipeline."
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
    for name, text in (
        ("features", "compute causal features and rule-based regimes (milestone 3)"),
        ("regime-report", "print the regime report of a computed feature set"),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--provider", choices=sorted(ALLOWED_PROVIDERS))
        sub.add_argument(
            "--dataset-dir",
            type=Path,
            help="processed dataset directory (default: the one for the current config)",
        )
        sub.add_argument(
            "--thresholds",
            type=Path,
            help="apply this frozen regime_thresholds.json instead of fitting on train",
        )
    for name, text in (
        ("backtest", "simulate the conventional baselines (milestone 4)"),
        ("backtest-report", "print the report of a computed backtest"),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--provider", choices=sorted(ALLOWED_PROVIDERS))
        sub.add_argument(
            "--dataset-dir",
            type=Path,
            help="processed dataset directory (default: the one for the current config)",
        )
        sub.add_argument(
            "--include-test",
            action="store_true",
            help="also evaluate the test split, which is reserved for the final "
            "pre-registered evaluation (default: train and validation only; D-056)",
        )
    return parser


def _dataset_dir(args: argparse.Namespace, config: ProjectConfig, root: Path) -> Path:
    if args.dataset_dir is not None:
        return args.dataset_dir
    return processed_dataset_dir(config, root, args.provider or config.data.provider)


def _load_features(config_dir: Path, config: ProjectConfig) -> FeatureConfig:
    path = Path(config_dir) / FEATURE_CONFIG_NAME
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}; the feature pipeline needs a features.yaml")
    feature_config = load_feature_config(path)
    feature_config.check_universe(config.data.universe)
    return feature_config


def _load_backtest(config_dir: Path, config: ProjectConfig) -> BacktestConfig:
    path = Path(config_dir) / BACKTEST_CONFIG_NAME
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}; the backtest needs a backtest.yaml")
    backtest = load_backtest_config(path)
    backtest.check_against(config.data, config.environment)
    features_path = Path(config_dir) / FEATURE_CONFIG_NAME
    if features_path.is_file():
        # The common evaluation window must cover the feature warm-up (milestone 4.2).
        backtest.check_feature_warm_up(load_feature_config(features_path))
    return backtest


def _cmd_validate(args: argparse.Namespace, config: ProjectConfig, root: Path) -> int:
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
    if (Path(args.config_dir) / FEATURE_CONFIG_NAME).is_file():
        features = _load_features(args.config_dir, config)
        print(f"  features       : {FEATURE_CONFIG_NAME} OK (market group {features.market_group})")
        print(f"  regime inputs  : {features.trend_feature}, {features.volatility_feature}")
    else:
        print(f"  features       : no {FEATURE_CONFIG_NAME} (feature pipeline unavailable)")
    if (Path(args.config_dir) / BACKTEST_CONFIG_NAME).is_file():
        backtest = _load_backtest(args.config_dir, config)
        names = ", ".join(s.name for s in backtest.strategies)
        print(f"  backtest       : {BACKTEST_CONFIG_NAME} OK ({names})")
        print(
            f"  execution lag  : {backtest.execution_lag_sessions} session(s); periods_per_year "
            f"{'null' if backtest.periods_per_year is None else backtest.periods_per_year} "
            "(null = annualised metrics omitted)"
        )
    else:
        print(f"  backtest       : no {BACKTEST_CONFIG_NAME} (backtest unavailable)")
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


def _cmd_features(args: argparse.Namespace, config: ProjectConfig, root: Path) -> int:
    feature_config = _load_features(args.config_dir, config)
    result = build_feature_dataset(
        config,
        feature_config,
        root,
        dataset_dir=args.dataset_dir,
        provider_name=args.provider,
        thresholds_path=args.thresholds,
    )
    report = result.report
    origin = report["dataset"].get("data_origin")
    if origin in ("synthetic", "in_memory"):
        print("*** NOT MARKET DATA: features computed from synthetic/fixture data. ***")
    th = result.thresholds
    print(f"Feature set: {result.output_dir}")
    print(f"  input dataset  : {report['dataset'].get('processed_dataset_id')} (origin {origin})")
    print(f"  features       : {len(result.feature_set.definitions)} columns")
    print(f"  thresholds     : {result.thresholds_mode}")
    print(
        f"  trend band     : +/-{th.trend_band:.6f} on {th.trend_feature}; volatility "
        f"{th.volatility_low:.6f} / {th.volatility_high:.6f} on {th.volatility_feature}"
    )
    for split, info in report["splits"].items():
        top = max(info["regimes"].items(), key=lambda item: item[1]["count"])
        print(
            f"  {split:<15}: {info['available_rows']} labelled, {info['unavailable_rows']} "
            f"unavailable; most frequent {top[0]} ({top[1]['count']})"
        )
    print(f"  warnings       : {len(report['warnings'])} (see regime_report.md)")
    return 0


def _cmd_regime_report(args: argparse.Namespace, config: ProjectConfig, root: Path) -> int:
    feature_config = _load_features(args.config_dir, config)
    directory = locate_dataset_dir(
        config, root, dataset_dir=args.dataset_dir, provider_name=args.provider
    )
    metadata_path = directory / "metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"missing {metadata_path}; run the 'build' command first")
    processed_id = json.loads(metadata_path.read_text(encoding="utf-8"))["processed_dataset_id"]
    target, _ = feature_output_dir(feature_config, root, processed_id, args.thresholds)
    path = target / "regime_report.md"
    if not path.is_file():
        raise FileNotFoundError(f"no regime report at {path}; run the 'features' command first")
    print(path.read_text(encoding="utf-8"))
    return 0


def _cmd_backtest(args: argparse.Namespace, config: ProjectConfig, root: Path) -> int:
    backtest = _load_backtest(args.config_dir, config)
    result = run_backtest(
        config,
        backtest,
        root,
        dataset_dir=args.dataset_dir,
        provider_name=args.provider,
        include_test=args.include_test,
    )
    document = result.metrics
    if document["data_origin"] in ("synthetic", "in_memory"):
        print("*** NOT MARKET DATA: backtest on synthetic/fixture data. ***")
    if args.include_test:
        print(
            "*** TEST SPLIT INCLUDED (--include-test): reserved for the final pre-registered "
            "evaluation; do not use it to choose or tune anything (D-056). ***"
        )
    print(f"Backtest: {result.output_dir}")
    print(f"  status         : {document['status']}")
    print(f"  splits         : {', '.join(document['evaluated_splits'])}")
    print(f"  test split     : {document['test_split']}")
    print(f"  execution lag  : {backtest.execution_lag_sessions} session(s)")
    for split, by_strategy in document["metrics"].items():
        print(f"  {split}:")
        for name, m in by_strategy.items():
            print(
                f"    {name:<28} net {m['net_cumulative_return']:+.2%}  gross "
                f"{m['gross_cumulative_return']:+.2%}  max DD {m['net_max_drawdown']:+.2%}  "
                f"traded {m['total_traded_notional']:.2f}"
            )
    print("  (descriptive backtest output under provisional conventions; see backtest_report.md)")
    return 0


def _cmd_backtest_report(args: argparse.Namespace, config: ProjectConfig, root: Path) -> int:
    backtest = _load_backtest(args.config_dir, config)
    directory = locate_dataset_dir(
        config, root, dataset_dir=args.dataset_dir, provider_name=args.provider
    )
    metadata_path = directory / "metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"missing {metadata_path}; run the 'build' command first")
    processed_id = json.loads(metadata_path.read_text(encoding="utf-8"))["processed_dataset_id"]
    target, _ = backtest_output_dir(
        config, backtest, root, processed_id, include_test=args.include_test
    )
    path = target / "backtest_report.md"
    if not path.is_file():
        option = " --include-test" if args.include_test else ""
        raise FileNotFoundError(
            f"no backtest report at {path}; run the 'backtest{option}' command first"
        )
    print(path.read_text(encoding="utf-8"))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    level = logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)
    try:
        config = load_project_config(args.config_dir)
        root = project_root_for(args.config_dir)
        if args.command == "validate":
            return _cmd_validate(args, config, root)
        if args.command == "fetch":
            return _cmd_fetch(args, config, root)
        if args.command == "build":
            return _cmd_build(args, config, root)
        if args.command == "report":
            return _cmd_report(args, config, root)
        if args.command == "features":
            return _cmd_features(args, config, root)
        if args.command == "regime-report":
            return _cmd_regime_report(args, config, root)
        if args.command == "backtest":
            return _cmd_backtest(args, config, root)
        if args.command == "backtest-report":
            return _cmd_backtest_report(args, config, root)
        return _cmd_split(args, config, root)
    except HANDLED_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
