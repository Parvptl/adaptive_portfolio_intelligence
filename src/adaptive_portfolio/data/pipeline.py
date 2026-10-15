"""End-to-end market-data pipeline: acquire -> validate -> process -> returns -> split -> report.

Directory layout (paths relative to the project root, both git-ignored):

* raw snapshot: ``<raw_data_dir>/<provider>/<raw_dataset_id>/`` with one CSV per
  instrument and ``manifest.json`` (see :mod:`adaptive_portfolio.data.cache`);
* processed dataset: ``<processed_data_dir>/<processed_dataset_id>/`` with
  ``prices.csv``, ``prices_long.csv``, ``returns.csv``, ``splits.csv``,
  ``quality_report.json``, ``quality_report.md``, ``metadata.json`` and
  ``run_info.json``.

All processed files except ``run_info.json`` are deterministic functions of the raw
snapshot and the configuration. ``run_info.json`` records run-specific facts (cache
hit or fetch, run time) and is excluded from that guarantee.
"""

from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from adaptive_portfolio.config import DataConfig, ProjectConfig
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.processing import (
    align_prices,
    apply_missing_data_policy,
    compute_returns,
    prices_to_long,
)
from adaptive_portfolio.data.providers import (
    CsvProvider,
    MarketDataProvider,
    PriceRequest,
    fetch_with_retry,
    make_provider,
)
from adaptive_portfolio.data.report import build_quality_report, render_markdown
from adaptive_portfolio.data.splits import assign_temporal_splits
from adaptive_portfolio.data.validation import DataValidationError, validate_raw_frame

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "1"
PROCESSED_FILES = (
    "prices.csv",
    "prices_long.csv",
    "returns.csv",
    "splits.csv",
    "quality_report.json",
    "quality_report.md",
    "metadata.json",
)
"""Deterministic outputs (``run_info.json`` is written too but is run-specific)."""


@dataclass(frozen=True)
class AcquisitionResult:
    frames: dict[str, pd.DataFrame]
    manifest: dict[str, Any]
    cache_status: str  # "hit" or "fetched"
    snapshot_dir: Path
    dataset_id: str


@dataclass(frozen=True)
class BuildResult:
    acquisition: AcquisitionResult
    processed_dir: Path
    processed_id: str
    report: dict[str, Any]


def project_root_for(config_dir: Path) -> Path:
    """The project root is the parent of the configuration directory."""
    return Path(config_dir).resolve().parent


def resolve_path(path: Path, project_root: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def relative_to_root(path: Path, project_root: Path) -> str:
    """Portable (forward-slash) path for metadata; avoids machine-specific absolute paths."""
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def request_parameters(data: DataConfig, provider_name: str) -> dict[str, Any]:
    """Parameters that define a raw snapshot (and its id)."""
    return {
        "provider": provider_name,
        "universe": list(data.universe),
        "start": data.start_date.isoformat(),
        "end": data.end_date.isoformat(),
        "frequency": data.frequency,
    }


def create_provider(data: DataConfig, project_root: Path, name: str | None = None):
    """Provider from configuration (``name`` overrides ``data.provider``)."""
    return make_provider(
        name or data.provider,
        timeout_seconds=data.provider_options.timeout_seconds,
        input_dir=resolve_path(data.provider_options.input_dir, project_root),
    )


def _csv_fingerprints(provider: MarketDataProvider, universe: tuple[str, ...]) -> dict[str, str]:
    if isinstance(provider, CsvProvider):
        return {ticker: provider.fingerprint(ticker) for ticker in universe}
    return {}


def acquire_raw(
    data: DataConfig,
    provider: MarketDataProvider,
    project_root: Path,
    *,
    cache_mode: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> AcquisitionResult:
    """Return raw frames from a verified snapshot, or fetch and store a new snapshot."""
    if data.frequency != "daily":
        raise DataValidationError(
            f"data.frequency={data.frequency!r} is not supported by the market-data pipeline "
            "yet; only 'daily' is implemented (decision D-035)"
        )
    mode = cache_mode or data.cache.mode
    request = request_parameters(data, provider.name)
    dataset_id = cache.short_hash(request)
    snapshot_dir = resolve_path(data.raw_data_dir, project_root) / provider.name / dataset_id

    if mode in ("use", "offline"):
        try:
            frames, manifest = cache.load_snapshot(snapshot_dir, request)
            current = _csv_fingerprints(provider, data.universe)
            if current and current != manifest.get("source_fingerprints"):
                raise cache.CacheMismatchError("local CSV source files changed since the snapshot")
            logger.info("cache hit: %s (retrieved %s)", snapshot_dir, manifest["retrieved_at_utc"])
            return AcquisitionResult(frames, manifest, "hit", snapshot_dir, dataset_id)
        except cache.CacheMissError as exc:
            if mode == "offline":
                raise cache.CacheError(
                    f"cache mode 'offline' but {exc}. Run once with --cache-mode use to fetch."
                ) from exc
            logger.info("cache miss: %s", exc)
        except cache.CacheMismatchError as exc:
            if mode == "offline":
                raise cache.CacheError(f"cache mode 'offline' but snapshot invalid: {exc}") from exc
            logger.warning("cached snapshot rejected (%s); fetching again", exc)

    logger.info(
        "fetching %d instrument(s) from %s (%s to %s)",
        len(data.universe),
        provider.name,
        data.start_date,
        data.end_date,
    )
    frames = {}
    for ticker in data.universe:
        frames[ticker] = fetch_with_retry(
            provider,
            PriceRequest(ticker, data.start_date, data.end_date),
            max_retries=data.provider_options.max_retries,
            retry_delay_seconds=data.provider_options.retry_delay_seconds,
            sleep=sleep,
        )
        logger.info("  %s: %d row(s)", ticker, len(frames[ticker]))
    manifest = cache.store_snapshot(
        snapshot_dir,
        frames,
        {
            "dataset_id": dataset_id,
            "request": request,
            "provider": {
                "name": provider.name,
                "version": provider.version(),
                "data_origin": provider.data_origin,
            },
            "retrieved_at_utc": cache.utc_timestamp(),
            "software": cache.software_versions(),
            "source_fingerprints": _csv_fingerprints(provider, data.universe),
        },
    )
    # Re-read from disk so that fetched and cached runs process byte-identical input.
    frames, manifest = cache.load_snapshot(snapshot_dir, request)
    return AcquisitionResult(frames, manifest, "fetched", snapshot_dir, dataset_id)


def processing_parameters(config: ProjectConfig) -> dict[str, Any]:
    data = config.data
    splits = config.experiment.splits
    return {
        "pipeline_version": PIPELINE_VERSION,
        "price_field": data.price_field,
        "missing_data": {
            "policy": data.missing_data.policy,
            "max_dropped_sessions": data.missing_data.max_dropped_sessions,
        },
        "validation": {
            "min_sessions": data.validation.min_sessions,
            "max_abs_return": data.validation.max_abs_return,
            "max_calendar_gap_days": data.validation.max_calendar_gap_days,
            "max_start_lag_days": data.validation.max_start_lag_days,
            "max_end_lag_days": data.validation.max_end_lag_days,
        },
        "splits": {
            name: {"start": period.start.isoformat(), "end": period.end.isoformat()}
            for name, period in (
                ("train", splits.train),
                ("validation", splits.validation),
                ("test", splits.test),
            )
        },
    }


def processed_dataset_dir(config: ProjectConfig, project_root: Path, provider_name: str) -> Path:
    """Where ``build`` writes for this configuration (computable without fetching)."""
    raw_id = cache.short_hash(request_parameters(config.data, provider_name))
    processed_id = cache.short_hash({"raw": raw_id, **processing_parameters(config)})
    return resolve_path(config.data.processed_data_dir, project_root) / processed_id


SCHEMAS = {
    "prices.csv": "date (YYYY-MM-DD session) + one column per instrument: selected price field",
    "prices_long.csv": "date, instrument, <price_field>: canonical long form, unique (date, "
    "instrument), sorted by date then universe order",
    "returns.csv": "date (period end), period_start, sessions_spanned, + one column per "
    "instrument: simple decimal return",
    "splits.csv": "date (return period end), split in {train, validation, test, excluded}",
}


def build_dataset(
    config: ProjectConfig,
    project_root: Path,
    *,
    provider: MarketDataProvider | None = None,
    provider_name: str | None = None,
    cache_mode: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> BuildResult:
    """Run the full pipeline and write the processed dataset."""
    data = config.data
    provider = provider or create_provider(data, project_root, provider_name)
    acquisition = acquire_raw(data, provider, project_root, cache_mode=cache_mode, sleep=sleep)
    frames = acquisition.frames

    summaries = {
        ticker: validate_raw_frame(
            frames[ticker],
            ticker,
            data.price_field,
            data.start_date,
            data.end_date,
            data.validation,
        )
        for ticker in data.universe
    }
    aligned, calendar = align_prices(frames, data.universe, data.price_field)
    processed = apply_missing_data_policy(aligned, calendar, data.missing_data)
    if len(processed.prices) < data.validation.min_sessions:
        raise DataValidationError(
            f"only {len(processed.prices)} aligned session(s); validation.min_sessions="
            f"{data.validation.min_sessions}"
        )
    returns = compute_returns(processed.prices, calendar, data.validation)
    assignment = assign_temporal_splits(returns.index, config.experiment.splits)

    params = processing_parameters(config)
    processed_id = cache.short_hash({"raw": acquisition.dataset_id, **params})
    report = build_quality_report(
        manifest=acquisition.manifest,
        dataset_id=acquisition.dataset_id,
        processed_id=processed_id,
        price_field=data.price_field,
        universe=data.universe,
        raw_summaries=summaries,
        aligned=aligned,
        processed=processed,
        returns=returns,
        assignment=assignment,
        missing_policy=data.missing_data.policy,
        max_abs_return_threshold=data.validation.max_abs_return,
    )
    metadata = {
        "metadata_schema_version": 1,
        "raw_dataset_id": acquisition.dataset_id,
        "processed_dataset_id": processed_id,
        "data_origin": acquisition.manifest["provider"]["data_origin"],
        "provider": acquisition.manifest["provider"],
        "retrieved_at_utc": acquisition.manifest["retrieved_at_utc"],
        "raw_snapshot_dir": relative_to_root(acquisition.snapshot_dir, project_root),
        "raw_manifest_sha256": cache.file_sha256(acquisition.snapshot_dir / cache.MANIFEST_NAME),
        "request": acquisition.manifest["request"],
        "processing": params,
        "software_at_retrieval": acquisition.manifest["software"],
        "software_at_processing": cache.software_versions(),
        "schemas": SCHEMAS,
        "units": "prices in the instrument's quote currency (USD for the default universe); "
        "returns are simple decimal returns (0.01 = 1 %); no annualisation is applied",
        "limitations": [
            "Instrument universe chosen with hindsight (survivorship/selection bias).",
            "Adjusted prices depend on the provider's adjustment method and may be revised.",
            "Observed calendar only: sessions absent from every instrument are invisible.",
        ],
    }

    target = processed_dataset_dir(config, project_root, provider.name)
    staging = cache.staging_directory(target)
    try:
        cache.write_csv(processed.prices.reset_index(), staging / "prices.csv")
        cache.write_csv(
            prices_to_long(processed.prices, data.price_field), staging / "prices_long.csv"
        )
        cache.write_csv(returns.reset_index(), staging / "returns.csv")
        cache.write_csv(
            assignment.labels.rename("split").rename_axis("date").reset_index(),
            staging / "splits.csv",
        )
        cache.write_json(report, staging / "quality_report.json")
        (staging / "quality_report.md").write_text(
            render_markdown(report), encoding="utf-8", newline="\n"
        )
        cache.write_json(metadata, staging / "metadata.json")
        cache.write_json(
            {
                "note": "run-specific; excluded from the determinism guarantee",
                "cache_status": acquisition.cache_status,
                "run_at_utc": cache.utc_timestamp(),
            },
            staging / "run_info.json",
        )
        cache.replace_directory(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    logger.info("processed dataset written to %s", target)
    return BuildResult(acquisition, target, processed_id, report)
