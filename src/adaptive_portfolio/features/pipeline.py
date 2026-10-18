"""Feature and regime pipeline on top of a processed market-data dataset (milestone 3).

Input: a processed dataset directory produced by ``market_data.py build`` (it contains
``returns.csv``, ``splits.csv`` and ``metadata.json``). Nothing is downloaded.

Output: ``<features.output_dir>/<feature_set_id>/`` containing

* ``features.csv``          date, split, then every feature column;
* ``regimes.csv``           date, split, the regime-defining and summary features,
  trend_label, volatility_label, regime, regime_status;
* ``regime_thresholds.json``  the frozen, training-calibrated definition (the artifact);
* ``regime_report.json`` / ``regime_report.md``  diagnostics;
* ``feature_metadata.json`` feature definitions, configuration, input ids, timing rules.

All files are deterministic for identical inputs (no timestamps). The id hashes the
processed-dataset id, the feature configuration, the pipeline version, and either "fit"
or the SHA-256 of a loaded threshold artifact.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from adaptive_portfolio.config import FeatureConfig, ProjectConfig
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import (
    processed_dataset_dir,
    relative_to_root,
    resolve_path,
)
from adaptive_portfolio.data.splits import assign_temporal_splits, label_dates
from adaptive_portfolio.features.engineering import FeatureDataError, FeatureSet, build_features
from adaptive_portfolio.regimes.diagnostics import build_regime_report, render_regime_markdown
from adaptive_portfolio.regimes.rules import (
    RegimeThresholds,
    assign_regimes,
    check_compatibility,
    fit_regime_thresholds,
    load_thresholds,
    save_thresholds,
)

logger = logging.getLogger(__name__)

FEATURE_PIPELINE_VERSION = "1"
FEATURE_FILES = (
    "features.csv",
    "regimes.csv",
    "regime_thresholds.json",
    "regime_report.json",
    "regime_report.md",
    "feature_metadata.json",
)
RETURN_META_COLUMNS = ["date", "period_start", "sessions_spanned"]


@dataclass(frozen=True)
class ProcessedInputs:
    asset_returns: pd.DataFrame  # index "date"; columns = universe order
    sessions_spanned: pd.Series
    split_labels: pd.Series
    metadata: dict[str, Any]


@dataclass(frozen=True)
class FeatureBuildResult:
    output_dir: Path
    feature_set_id: str
    feature_set: FeatureSet
    regimes: pd.DataFrame
    thresholds: RegimeThresholds
    thresholds_mode: str
    report: dict[str, Any]


def feature_config_to_dict(config: FeatureConfig) -> dict[str, Any]:
    """Canonical, JSON-serialisable form of the feature configuration (for ids and metadata)."""
    w = config.windows
    r = config.regime
    return {
        "asset_groups": {name: list(members) for name, members in config.asset_groups},
        "market_group": config.market_group,
        "correlation_groups": list(config.correlation_groups)
        if config.correlation_groups
        else None,
        "allow_multi_session_returns": config.allow_multi_session_returns,
        "windows": {
            "asset_momentum": list(w.asset_momentum),
            "asset_volatility": list(w.asset_volatility),
            "group_momentum": list(w.group_momentum),
            "market_volatility": list(w.market_volatility),
            "market_downside_volatility": list(w.market_downside_volatility),
            "market_drawdown": w.market_drawdown,
            "average_asset_volatility": w.average_asset_volatility,
            "correlation": w.correlation,
        },
        "regime": {
            "trend_window": r.trend_window,
            "volatility_window": r.volatility_window,
            "trend_neutral_quantile": r.trend_neutral_quantile,
            "volatility_quantiles": list(r.volatility_quantiles),
            "min_calibration_observations": r.min_calibration_observations,
            "sparse_regime_fraction": r.sparse_regime_fraction,
            "concentration_warning_fraction": r.concentration_warning_fraction,
        },
    }


def locate_dataset_dir(
    config: ProjectConfig,
    project_root: Path,
    *,
    dataset_dir: Path | None = None,
    provider_name: str | None = None,
) -> Path:
    if dataset_dir is not None:
        return Path(dataset_dir)
    return processed_dataset_dir(config, project_root, provider_name or config.data.provider)


def _read_splits_before_test(path: Path, config: ProjectConfig) -> pd.DataFrame:
    """Rows of ``splits.csv`` dated before the configured test period (dates and labels only).

    Reads line by line and stops at the first row dated on or after ``test.start`` from
    ``experiment.yaml``, so the boundary comes from the configuration, not from the file's
    labels. That row's label must be the one the configuration implies; otherwise the file is
    mislabelled and an error is raised. No later row is read. A row before ``test.start``
    labelled ``test`` is also rejected here. ``splits.csv`` holds no market values.
    """
    splits = config.experiment.splits
    test_start = pd.Timestamp(splits.test.start)
    rows: list[tuple[str, str]] = []
    with path.open("rb") as handle:
        header = handle.readline().decode("utf-8").strip()
        if header != "date,split":
            raise FeatureDataError("splits.csv must have columns [date, split]")
        while True:
            line = handle.readline()
            if not line:
                break
            fields = line.decode("utf-8").strip().split(",")
            if len(fields) != 2:
                raise FeatureDataError(f"malformed splits.csv row {len(rows) + 1}")
            date, label = fields
            when = pd.to_datetime(date, format=cache.DATE_FORMAT)
            if when >= test_start or label == "test":
                expected = label_dates(pd.DatetimeIndex([when]), splits).iloc[0]
                if label != expected:
                    raise FeatureDataError(
                        f"splits.csv labels {date} as {label}, but experiment.yaml implies "
                        f"{expected}; rebuild the dataset instead of mixing configurations"
                    )
                break
            rows.append((date, label))
    frame = pd.DataFrame(rows, columns=["date", "split"])
    frame["date"] = pd.to_datetime(frame["date"], format=cache.DATE_FORMAT)
    return frame


def load_processed_inputs(
    directory: Path, config: ProjectConfig, *, exclude_test: bool = False
) -> ProcessedInputs:
    """Read and verify the processed dataset contract (see the technical handbook §12).

    ``exclude_test=True`` (the baseline backtest's default, D-056) reads only the rows
    before the first test-period row: ``splits.csv`` up to its first ``test`` label, then
    exactly that many ``returns.csv`` rows. Test-period return values are never parsed.
    Every contract check below is applied to the rows that are read.
    """
    for name in ("returns.csv", "splits.csv", "metadata.json"):
        if not (directory / name).is_file():
            raise FileNotFoundError(
                f"missing {directory / name}; build the dataset first, e.g. "
                "python scripts/market_data.py build --provider <provider>"
            )
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if exclude_test:
        splits = _read_splits_before_test(directory / "splits.csv", config)
        try:
            returns = cache.read_csv_head(
                directory / "returns.csv", len(splits), ("date", "period_start")
            )
        except ValueError as exc:
            raise FeatureDataError(f"returns.csv shorter than splits.csv: {exc}") from None
    else:
        returns = cache.read_csv(directory / "returns.csv", ("date", "period_start"))
        splits = cache.read_csv(directory / "splits.csv")

    universe = list(config.data.universe)
    if list(returns.columns[:3]) != RETURN_META_COLUMNS:
        raise FeatureDataError(
            f"returns.csv must start with {RETURN_META_COLUMNS}, got {list(returns.columns[:3])}"
        )
    assets = list(returns.columns[3:])
    if assets != universe or metadata.get("request", {}).get("universe") != universe:
        raise FeatureDataError(
            f"asset columns {assets} / metadata universe "
            f"{metadata.get('request', {}).get('universe')} do not match data.universe "
            f"{universe} (same instruments, same order required)"
        )
    dates = pd.DatetimeIndex(returns["date"], name="date")
    if dates.has_duplicates:
        raise FeatureDataError(
            f"duplicate date {dates[dates.duplicated()][0].date()} in returns.csv"
        )
    if not dates.is_monotonic_increasing:
        raise FeatureDataError("returns.csv dates are not in chronological order")
    if list(splits.columns) != ["date", "split"] or not splits["date"].equals(returns["date"]):
        raise FeatureDataError("splits.csv must have columns [date, split] and the returns' dates")

    if exclude_test:
        # The prefix has no test rows by construction, so the per-date rule is checked
        # directly (assign_temporal_splits requires every partition to be non-empty).
        expected = label_dates(dates, config.experiment.splits)
    else:
        expected = assign_temporal_splits(dates, config.experiment.splits).labels
    if splits["split"].tolist() != expected.tolist():
        raise FeatureDataError(
            "splits.csv does not match the split boundaries in experiment.yaml; rebuild the "
            "dataset (python scripts/market_data.py build) instead of mixing configurations"
        )
    return ProcessedInputs(
        asset_returns=returns.set_index("date")[assets].rename_axis("date"),
        sessions_spanned=pd.Series(returns["sessions_spanned"].to_numpy(), index=dates),
        split_labels=pd.Series(splits["split"].to_numpy(), index=dates, name="split"),
        metadata=metadata,
    )


@dataclass(frozen=True)
class FeatureOutputs:
    """Feature and regime rows of a feature-set artifact, aligned with its processed dataset."""

    features: pd.DataFrame  # index "date"; feature columns in artifact order
    regimes: pd.DataFrame  # index "date"; regime feature, label and status columns
    split_labels: pd.Series
    metadata: dict[str, Any]


def load_feature_outputs(
    feature_dir: Path,
    dataset_dir: Path,
    config: ProjectConfig,
    *,
    exclude_test: bool = True,
) -> FeatureOutputs:
    """Read ``features.csv`` and ``regimes.csv`` of a feature set for later modelling.

    **Safe by default:** with ``exclude_test=True`` the number of permitted rows comes from
    the processed dataset's ``splits.csv``, which is read only up to the first row dated on or
    after the configured ``test.start`` (the same rule as the baseline backtest). Exactly that
    many rows of each feature file are parsed with :func:`cache.read_csv_head`, so test-period
    feature values are never parsed.

    Checks:
    - the feature set was built from this processed dataset (ids in the metadata files);
    - both files start with ``date, split``;
    - their dates and split labels equal those of ``splits.csv``, and the labels follow
      ``experiment.yaml``.

    ``exclude_test=False`` reads every row and is reserved for the final, authorised test
    evaluation.
    """
    feature_dir, dataset_dir = Path(feature_dir), Path(dataset_dir)
    for path in (
        feature_dir / "features.csv",
        feature_dir / "regimes.csv",
        feature_dir / "feature_metadata.json",
        dataset_dir / "metadata.json",
        dataset_dir / "splits.csv",
    ):
        if not path.is_file():
            raise FileNotFoundError(f"missing {path}")
    metadata = json.loads((feature_dir / "feature_metadata.json").read_text(encoding="utf-8"))
    dataset_metadata = json.loads((dataset_dir / "metadata.json").read_text(encoding="utf-8"))
    built_from = (metadata.get("input") or {}).get("processed_dataset_id")
    if built_from != dataset_metadata.get("processed_dataset_id"):
        raise FeatureDataError(
            f"feature set was built from processed dataset {built_from!r}, not "
            f"{dataset_metadata.get('processed_dataset_id')!r}; use the matching dataset"
        )
    for name in ("features.csv", "regimes.csv"):  # header line only: column names, no values
        with (feature_dir / name).open("rb") as handle:
            header = handle.readline().decode("utf-8").strip().split(",")
        if header[:2] != ["date", "split"]:
            raise FeatureDataError(f"{name} must start with columns [date, split]")
    if exclude_test:
        splits = _read_splits_before_test(dataset_dir / "splits.csv", config)
        try:
            features = cache.read_csv_head(feature_dir / "features.csv", len(splits))
            regimes = cache.read_csv_head(feature_dir / "regimes.csv", len(splits))
        except ValueError as exc:
            raise FeatureDataError(f"cannot read the permitted feature rows: {exc}") from None
    else:
        splits = cache.read_csv(dataset_dir / "splits.csv")
        features = cache.read_csv(feature_dir / "features.csv")
        regimes = cache.read_csv(feature_dir / "regimes.csv")
    for name, frame in (("features.csv", features), ("regimes.csv", regimes)):
        if not frame["date"].equals(splits["date"]):
            raise FeatureDataError(f"{name} dates differ from the processed dataset's splits.csv")
        if frame["split"].tolist() != splits["split"].tolist():
            raise FeatureDataError(f"{name} split labels differ from splits.csv")
    dates = pd.DatetimeIndex(splits["date"], name="date")
    expected = label_dates(dates, config.experiment.splits)
    if splits["split"].tolist() != expected.tolist():
        raise FeatureDataError("split labels do not match experiment.yaml; rebuild the dataset")
    return FeatureOutputs(
        features=features.drop(columns=["date", "split"]).set_index(dates),
        regimes=regimes.drop(columns=["date", "split"]).set_index(dates),
        split_labels=pd.Series(splits["split"].to_numpy(), index=dates, name="split"),
        metadata=metadata,
    )


def feature_set_id_for(processed_id: str, config: FeatureConfig, thresholds_tag: str) -> str:
    return cache.short_hash(
        {
            "processed_dataset_id": processed_id,
            "features": feature_config_to_dict(config),
            "pipeline_version": FEATURE_PIPELINE_VERSION,
            "thresholds": thresholds_tag,
        }
    )


def feature_output_dir(
    config: FeatureConfig, project_root: Path, processed_id: str, thresholds_path: Path | None
) -> tuple[Path, str]:
    tag = "fit" if thresholds_path is None else cache.file_sha256(thresholds_path)
    feature_id = feature_set_id_for(processed_id, config, tag)
    return resolve_path(config.output_dir, project_root) / feature_id, feature_id


def build_feature_dataset(
    config: ProjectConfig,
    feature_config: FeatureConfig,
    project_root: Path,
    *,
    dataset_dir: Path | None = None,
    provider_name: str | None = None,
    thresholds_path: Path | None = None,
) -> FeatureBuildResult:
    """Compute features, fit (training only) or load frozen thresholds, label, report, save."""
    feature_config.check_universe(config.data.universe)
    directory = locate_dataset_dir(
        config, project_root, dataset_dir=dataset_dir, provider_name=provider_name
    )
    inputs = load_processed_inputs(directory, config)
    multi = int((inputs.sessions_spanned > 1).sum())
    if multi and not feature_config.allow_multi_session_returns:
        raise FeatureDataError(
            f"{multi} return(s) span more than one session (sessions_spanned > 1); rolling "
            "windows would cover unequal periods. Set features.allow_multi_session_returns: "
            "true to accept this explicitly."
        )

    feature_set = build_features(inputs.asset_returns, feature_config)
    processed_id = inputs.metadata.get("processed_dataset_id", "unknown")
    source = {
        "processed_dataset_id": processed_id,
        "raw_dataset_id": inputs.metadata.get("raw_dataset_id"),
        "data_origin": inputs.metadata.get("data_origin"),
        "feature_config_sha": cache.short_hash(feature_config_to_dict(feature_config)),
    }
    if thresholds_path is None:
        thresholds = fit_regime_thresholds(
            feature_set.frame,
            inputs.split_labels,
            feature_config.regime,
            trend_feature=feature_config.trend_feature,
            volatility_feature=feature_config.volatility_feature,
            source=source,
        )
        mode = "fitted_on_train"
    else:
        thresholds = load_thresholds(thresholds_path)
        check_compatibility(
            thresholds,
            trend_feature=feature_config.trend_feature,
            volatility_feature=feature_config.volatility_feature,
            config=feature_config.regime,
        )
        mode = "loaded_frozen_artifact"

    regimes = assign_regimes(feature_set.frame, thresholds)
    summary = [
        name
        for name in (
            feature_config.trend_feature,
            feature_config.volatility_feature,
            f"market_drawdown_{feature_config.windows.market_drawdown}",
            "xs_dispersion",
            *(
                [
                    f"{feature_config.correlation_groups[0]}_{feature_config.correlation_groups[1]}"
                    f"_corr_{feature_config.windows.correlation}"
                ]
                if feature_config.correlation_groups
                else []
            ),
        )
        if name in feature_set.frame.columns
    ]
    dataset_info = {
        **source,
        "dataset_dir": relative_to_root(directory, project_root),
        "multi_session_returns": multi,
    }
    report = build_regime_report(
        feature_set=feature_set,
        regimes=regimes,
        split_labels=inputs.split_labels,
        thresholds=thresholds,
        thresholds_mode=mode,
        config=feature_config.regime,
        summary_features=summary,
        dataset=dataset_info,
    )
    target, feature_id = feature_output_dir(
        feature_config, project_root, processed_id, thresholds_path
    )
    metadata = {
        "metadata_schema_version": 1,
        "feature_set_id": feature_id,
        "feature_pipeline_version": FEATURE_PIPELINE_VERSION,
        "input": source,
        "thresholds_mode": mode,
        "thresholds_artifact_sha256_loaded": None
        if thresholds_path is None
        else cache.file_sha256(thresholds_path),
        "feature_config": feature_config_to_dict(feature_config),
        "timing_convention": (
            "Row dated t uses only return rows dated <= t (known at the close of t). The "
            "return dated t+1 is the outcome of a decision taken at t and is never a feature "
            "of t. Windows count return observations; no annualisation."
        ),
        "split_rule": "rows take the split of their own date (D-038); calibration uses train only",
        "feature_definitions": [d.as_dict() for d in feature_set.definitions],
        "software": cache.software_versions(),
    }

    staging = cache.staging_directory(target)
    try:
        features_out = feature_set.frame.copy()
        features_out.insert(0, "split", inputs.split_labels.to_numpy())
        cache.write_csv(features_out.reset_index(), staging / "features.csv")
        regimes_out = pd.concat([feature_set.frame[summary], regimes], axis=1)
        regimes_out.insert(0, "split", inputs.split_labels.to_numpy())
        cache.write_csv(regimes_out.reset_index(), staging / "regimes.csv")
        save_thresholds(thresholds, staging / "regime_thresholds.json")
        cache.write_json(report, staging / "regime_report.json")
        (staging / "regime_report.md").write_text(
            render_regime_markdown(report), encoding="utf-8", newline="\n"
        )
        cache.write_json(metadata, staging / "feature_metadata.json")
        cache.replace_directory(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    logger.info("feature set written to %s", target)
    return FeatureBuildResult(target, feature_id, feature_set, regimes, thresholds, mode, report)
