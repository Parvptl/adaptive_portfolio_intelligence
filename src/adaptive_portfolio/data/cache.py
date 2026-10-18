"""Raw-data snapshots ("the cache"): CSV files plus a manifest with checksums.

What the manifest guarantees: the files in a snapshot are byte-for-byte the files
written at retrieval time (SHA-256), and the snapshot was produced for exactly the
recorded request (provider, universe, dates, frequency). What it does **not**
guarantee: that the provider would return the same data today. Remote historical
data (especially adjusted prices) can be revised; a snapshot only freezes *one*
retrieval.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import platform
import shutil
from collections.abc import Mapping
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATE_FORMAT = "%Y-%m-%d"


class CacheError(RuntimeError):
    """Base class for cache problems."""


class CacheMissError(CacheError):
    """No snapshot exists for the request."""


class CacheMismatchError(CacheError):
    """A snapshot exists but does not match the request or fails its checksums."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def short_hash(value: Any) -> str:
    """16-hex-digit SHA-256 prefix of the canonical JSON of ``value``."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:16]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def software_versions() -> dict[str, str]:
    """Versions recorded for traceability (not a guarantee of identical results)."""
    try:
        package_version = importlib_metadata.version("adaptive-portfolio-intelligence")
    except importlib_metadata.PackageNotFoundError:
        package_version = "unknown"
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "adaptive_portfolio": package_version,
    }


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    """Deterministic CSV: ISO dates, shortest round-trip floats, '\\n' line endings."""
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[column]):
            out[column] = out[column].dt.strftime(DATE_FORMAT)
    out.to_csv(path, index=False, lineterminator="\n")


def read_csv(path: Path, date_columns: tuple[str, ...] = ("date",)) -> pd.DataFrame:
    return _parse_csv(path, date_columns)


def read_csv_head(
    path: Path, n_rows: int, date_columns: tuple[str, ...] = ("date",)
) -> pd.DataFrame:
    """Parse the header and the first ``n_rows`` data lines only.

    Lines are taken one at a time from a binary stream and the stream stops after line
    ``n_rows``: later lines are never decoded or parsed (the operating system may still
    buffer bytes beyond that point; they are not inspected). Raises ``ValueError`` if the
    file has fewer data lines.
    """
    if isinstance(n_rows, bool) or not isinstance(n_rows, int) or n_rows < 0:
        raise ValueError(f"n_rows must be a non-negative integer, got {n_rows!r}")
    with Path(path).open("rb") as handle:
        lines = [handle.readline()]
        while len(lines) <= n_rows:
            line = handle.readline()
            if not line:
                break
            lines.append(line)
    if len(lines) - 1 < n_rows:
        raise ValueError(f"{path} has {len(lines) - 1} data row(s); {n_rows} required")
    return _parse_csv(io.BytesIO(b"".join(lines)), date_columns)


def _parse_csv(source: Any, date_columns: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.read_csv(source, float_precision="round_trip")
    for column in date_columns:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], format=DATE_FORMAT)
    return frame


def write_json(value: Any, path: Path) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def replace_directory(staging: Path, target: Path) -> None:
    """Move a fully written staging directory into place, replacing ``target``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_name(f"{target.name}.old-{os.getpid()}")
    if target.exists():
        target.rename(backup)
    staging.rename(target)
    if backup.exists():
        shutil.rmtree(backup)


def staging_directory(target: Path) -> Path:
    staging = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    return staging


def store_snapshot(
    directory: Path, frames: Mapping[str, pd.DataFrame], manifest: dict[str, Any]
) -> dict[str, Any]:
    """Write one CSV per instrument plus ``manifest.json``; returns the full manifest."""
    staging = staging_directory(directory)
    try:
        files = {}
        for instrument, frame in frames.items():
            path = staging / f"{instrument}.csv"
            write_csv(frame, path)
            files[instrument] = {
                "file": path.name,
                "sha256": file_sha256(path),
                "rows": len(frame),
                "columns": list(frame.columns),
            }
        full = {**manifest, "schema_version": SCHEMA_VERSION, "files": files}
        write_json(full, staging / MANIFEST_NAME)
        replace_directory(staging, directory)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return full


def load_snapshot(
    directory: Path, expected_request: Mapping[str, Any]
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Load a snapshot after verifying its manifest and checksums."""
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        raise CacheMissError(f"no raw snapshot at {directory}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CacheMismatchError(f"unreadable manifest {manifest_path}: {exc}") from exc
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise CacheMismatchError(
            f"snapshot schema {manifest.get('schema_version')} != expected {SCHEMA_VERSION}"
        )
    if manifest.get("request") != dict(expected_request):
        raise CacheMismatchError("snapshot was created for a different request")

    frames = {}
    for instrument in expected_request["universe"]:
        entry = manifest.get("files", {}).get(instrument)
        if entry is None:
            raise CacheMismatchError(f"snapshot has no file for {instrument}")
        path = directory / entry["file"]
        if not path.is_file():
            raise CacheMismatchError(f"snapshot file missing: {path}")
        if file_sha256(path) != entry["sha256"]:
            raise CacheMismatchError(f"checksum mismatch for {path} (file was modified)")
        frames[instrument] = read_csv(path)
    return frames, manifest


def utc_timestamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
