"""E10 walk-forward fold inputs (D-094): fold datasets and feature sets without 2020+ rows.

A non-reference fold gets its own processed dataset, derived from the parent dataset (e.g.
``8e00568ee2aa4de7``):

* ``returns.csv`` is the **byte-exact prefix** of the parent's file up to the fold's last
  holdout date. It is read with the bounded line reader, which stops before the project's test
  start, so no test-period line is decoded;
* ``splits.csv`` labels each date with the **fold's** partitions;
* ``metadata.json`` is the parent's, with the fold's id, splits and provenance.

The fold feature set is then built by the unchanged :func:`build_feature_dataset` in ``fit``
mode, so regime thresholds are fitted on the fold's training rows only. Feature values are
past-only, so they must equal the parent's for every common row; :func:`verify_fold` checks this
and the other leakage conditions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.config import (
    FeatureConfig,
    ProjectConfig,
    WalkForwardFold,
    apply_walk_forward_fold,
)
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.splits import assign_temporal_splits

FOLD_SCHEMA_VERSION = 1
FOLD_DATASET_ROOT = Path("data/processed/walk_forward_datasets")


class WalkForwardError(ValueError):
    """Raised when a walk-forward fold cannot be built or does not verify."""


def _parent_dates(parent_dir: Path, base: ProjectConfig) -> pd.DatetimeIndex:
    """Dates of the parent's rows before the project's test start (bounded read; no values)."""
    from adaptive_portfolio.features.pipeline import _read_splits_before

    frame = _read_splits_before(Path(parent_dir) / "splits.csv", base, "test")
    return pd.DatetimeIndex(frame["date"])


def fold_dataset_id(parent_id: str, fold: WalkForwardFold) -> str:
    return cache.short_hash({"schema": FOLD_SCHEMA_VERSION, "parent": parent_id,
                             "fold": fold.to_dict()})  # fmt: skip


def fold_dataset_dir(root: Path, parent_dir: Path, fold: WalkForwardFold) -> Path:
    meta = json.loads((Path(parent_dir) / "metadata.json").read_text(encoding="utf-8"))
    return Path(root) / FOLD_DATASET_ROOT / fold_dataset_id(meta["processed_dataset_id"], fold)


def _fold_rows(parent_dir: Path, base: ProjectConfig, fold: WalkForwardFold) -> int:
    dates = _parent_dates(parent_dir, base)
    rows = int((dates <= pd.Timestamp(fold.splits.test.end)).sum())
    if rows == 0 or dates[rows - 1] >= pd.Timestamp(base.experiment.splits.test.start):
        raise WalkForwardError(f"fold {fold.id}: no rows, or rows in the sealed test period")
    return rows


def build_fold_dataset(root: Path, parent_dir: Path, base: ProjectConfig,
                       fold: WalkForwardFold) -> Path:  # fmt: skip
    """Write the fold dataset once (or return it if it already exists and verifies)."""
    fold_config, reference = apply_walk_forward_fold(base, fold)
    if reference:
        raise WalkForwardError("the reference fold uses the parent dataset itself")
    target = fold_dataset_dir(root, parent_dir, fold)
    if target.exists():
        problems = verify_fold_dataset(target, parent_dir, base, fold)
        if problems:
            raise WalkForwardError(f"{target} exists but does not verify: {problems}")
        return target
    rows = _fold_rows(parent_dir, base, fold)
    lines = cache._head_lines(Path(parent_dir) / "returns.csv", rows)
    dates = _parent_dates(parent_dir, base)[:rows]
    labels = assign_temporal_splits(dates, fold_config.experiment.splits).labels
    parent_meta = json.loads((Path(parent_dir) / "metadata.json").read_text(encoding="utf-8"))
    meta = dict(parent_meta)
    meta["processed_dataset_id"] = target.name
    periods = fold.to_dict()
    fold_splits = {"train": periods["train"], "validation": periods["validation"],
                   "test": periods["holdout"]}  # fmt: skip
    meta["processing"] = {**parent_meta.get("processing", {}), "splits": fold_splits}
    meta["walk_forward"] = {
        "schema_version": FOLD_SCHEMA_VERSION, "decision": "D-094", "fold": fold.to_dict(),
        "parent_processed_dataset_id": parent_meta["processed_dataset_id"], "rows": rows,
        "first_date": dates[0].date().isoformat(), "last_date": dates[-1].date().isoformat(),
        "parent_returns_prefix_sha256": cache.head_sha256(
            Path(parent_dir) / "returns.csv", rows),
        "read": f"bounded: parent rows before {base.experiment.splits.test.start} only",
    }  # fmt: skip
    staging = cache.staging_directory(target)
    try:
        (staging / "returns.csv").write_bytes(b"".join(lines))
        cache.write_csv(pd.DataFrame({"date": dates, "split": labels.to_numpy()}),
                        staging / "splits.csv")  # fmt: skip
        cache.write_json(meta, staging / "metadata.json")
        cache.replace_directory(staging, target)
    except BaseException:
        import shutil

        shutil.rmtree(staging, ignore_errors=True)
        raise
    problems = verify_fold_dataset(target, parent_dir, base, fold)
    if problems:
        raise WalkForwardError(f"{target} does not verify: {problems}")
    return target


def build_fold_features(root: Path, fold_dir: Path, base: ProjectConfig,
                        fold: WalkForwardFold, features: FeatureConfig) -> Path:  # fmt: skip
    """The fold's feature set (``fit`` mode: regime thresholds from the fold's training rows)."""
    from adaptive_portfolio.features.pipeline import build_feature_dataset, feature_output_dir

    fold_config, _ = apply_walk_forward_fold(base, fold)
    meta = json.loads((Path(fold_dir) / "metadata.json").read_text(encoding="utf-8"))
    target, _ = feature_output_dir(features, root, meta["processed_dataset_id"], None)
    if target.exists():  # write-once: never rebuilt over an existing feature set
        return target
    result = build_feature_dataset(fold_config, features, root, dataset_dir=Path(fold_dir))
    return Path(result.output_dir)


def verify_fold_dataset(fold_dir: Path, parent_dir: Path, base: ProjectConfig,
                        fold: WalkForwardFold) -> list[str]:  # fmt: skip
    fold_dir, parent_dir = Path(fold_dir), Path(parent_dir)
    problems = []
    meta = json.loads((fold_dir / "metadata.json").read_text(encoding="utf-8"))
    info = meta.get("walk_forward") or {}
    parent_meta = json.loads((parent_dir / "metadata.json").read_text("utf-8"))
    parent_id = parent_meta["processed_dataset_id"]
    if fold_dir.name != fold_dataset_id(parent_id, fold) or meta.get("processed_dataset_id") != (
            fold_dir.name):  # fmt: skip
        problems.append("fold dataset id != hash(parent, fold)")
    if info.get("fold") != fold.to_dict() or info.get("parent_processed_dataset_id") != parent_id:
        problems.append("metadata does not name this fold and parent")
    rows = _fold_rows(parent_dir, base, fold)
    if info.get("rows") != rows:
        problems.append(f"rows {info.get('rows')} != {rows}")
    parent_head = b"".join(cache._head_lines(parent_dir / "returns.csv", rows))
    if (fold_dir / "returns.csv").read_bytes() != parent_head:
        problems.append("returns.csv is not the byte-exact parent prefix")
    splits = cache.read_csv(fold_dir / "splits.csv")
    fold_config, _ = apply_walk_forward_fold(base, fold)
    expected = assign_temporal_splits(pd.DatetimeIndex(splits["date"]),
                                      fold_config.experiment.splits).labels  # fmt: skip
    if splits["split"].tolist() != expected.tolist():
        problems.append("splits.csv labels do not follow the fold boundaries")
    if pd.Timestamp(splits["date"].iloc[-1]) >= pd.Timestamp(base.experiment.splits.test.start):
        problems.append("the fold dataset contains a test-period row")
    return problems


def verify_fold(root: Path, fold_dir: Path, feature_dir: Path, parent_dir: Path,
                parent_feature_dir: Path, base: ProjectConfig,
                fold: WalkForwardFold) -> dict[str, Any]:  # fmt: skip
    """Every leakage and integrity check of a non-reference fold (H9 of D-094)."""
    from adaptive_portfolio.features.pipeline import load_feature_outputs

    fold_config, _ = apply_walk_forward_fold(base, fold)
    checks: dict[str, bool] = {}
    dataset_problems = verify_fold_dataset(fold_dir, parent_dir, base, fold)
    checks["fold dataset verifies (byte-exact parent prefix, fold labels, no test row)"] = (
        not dataset_problems)  # fmt: skip
    fmeta = json.loads((Path(feature_dir) / "feature_metadata.json").read_text(encoding="utf-8"))
    dmeta = json.loads((Path(fold_dir) / "metadata.json").read_text(encoding="utf-8"))
    checks["feature set built from the fold dataset"] = (fmeta.get("input") or {}).get(
        "processed_dataset_id"
    ) == dmeta["processed_dataset_id"]
    checks["regime thresholds fitted on the fold's training rows"] = (
        fmeta.get("thresholds_mode") == "fitted_on_train"
    )
    thresholds = json.loads((Path(feature_dir) / "regime_thresholds.json").read_text("utf-8"))
    calibration = json.dumps(thresholds)
    checks["thresholds name the fold dataset"] = dmeta["processed_dataset_id"] in calibration
    ours = load_feature_outputs(feature_dir, fold_dir, fold_config, exclude_test=False)
    parent = load_feature_outputs(parent_feature_dir, parent_dir, base, exclude_test=True)
    common = parent.features.loc[ours.features.index]
    a = ours.features[common.columns].to_numpy(float)
    b = common.to_numpy(float)
    checks["feature values equal the parent's exactly (past-only)"] = bool(
        a.shape == b.shape and np.array_equal(np.isnan(a), np.isnan(b))
        and np.array_equal(np.nan_to_num(a), np.nan_to_num(b)))  # fmt: skip
    checks["last fold row before the project's test start"] = bool(
        ours.features.index[-1] < pd.Timestamp(base.experiment.splits.test.start)
    )
    return {"fold": fold.id, "dataset_id": dmeta["processed_dataset_id"],
            "feature_set_id": fmeta.get("feature_set_id"), "rows": len(ours.features),
            "first_date": ours.features.index[0].date().isoformat(),
            "last_date": ours.features.index[-1].date().isoformat(),
            "labels": ours.split_labels.value_counts().to_dict(),
            "checks": checks, "dataset_problems": dataset_problems,
            "verified": all(checks.values())}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    """``build-fold`` / ``verify-fold`` for one walk-forward experiment config (D-094)."""
    import argparse
    import sys

    from adaptive_portfolio.config import (
        ConfigError,
        load_feature_config,
        load_profile_experiment_config,
        load_project_config,
    )
    from adaptive_portfolio.data.pipeline import project_root_for
    from adaptive_portfolio.features.pipeline import feature_output_dir, locate_dataset_dir

    parser = argparse.ArgumentParser(description="E10 walk-forward fold inputs (D-094)")
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument("--dataset-dir", type=Path, help="the parent (D-009) processed dataset")
    parser.add_argument("--experiment-config", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-fold", help="write the fold dataset and feature set once")
    build.add_argument("--execute", action="store_true", help="required to write")
    sub.add_parser("verify-fold", help="run every leakage and integrity check of the fold")
    args = parser.parse_args(argv)
    try:
        base = load_project_config(args.config_dir)
        root = project_root_for(args.config_dir)
        experiment = load_profile_experiment_config(args.experiment_config)
        fold = experiment.walk_forward_fold
        if fold is None:
            raise WalkForwardError("the experiment config has no walk_forward_fold block")
        if apply_walk_forward_fold(base, fold)[1]:
            print(f"fold {fold.id} is the reference (D-009) split: nothing to build")
            return 0
        parent = Path(args.dataset_dir or locate_dataset_dir(base, root))
        features = load_feature_config(args.config_dir / "features.yaml")
        if args.command == "build-fold":
            if not args.execute:
                print(f"fold {fold.id}: would write {fold_dataset_dir(root, parent, fold)}")
                return 0
            fold_dir = build_fold_dataset(root, parent, base, fold)
            feature_dir = build_fold_features(root, fold_dir, base, fold, features)
            print(f"fold {fold.id}: dataset {fold_dir}\n  features {feature_dir}")
        fold_dir = fold_dataset_dir(root, parent, fold)
        parent_meta = json.loads((parent / "metadata.json").read_text(encoding="utf-8"))
        fold_meta = json.loads((fold_dir / "metadata.json").read_text(encoding="utf-8"))
        feature_dir, _ = feature_output_dir(features, root, fold_meta["processed_dataset_id"], None)
        parent_features, _ = feature_output_dir(
            features, root, parent_meta["processed_dataset_id"], None
        )
        report = verify_fold(root, fold_dir, feature_dir, parent, parent_features, base, fold)
        for name, ok in report["checks"].items():
            print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        status = "VERIFIED" if report["verified"] else "FAILED"
        print(f"fold {fold.id}: {report['rows']} rows {report['first_date']}.."
              f"{report['last_date']} labels {report['labels']}: {status}")  # fmt: skip
        return 0 if report["verified"] else 1
    except (WalkForwardError, ConfigError, FileNotFoundError, ValueError) as exc:
        print(f"WALK-FORWARD FAILED: {exc}", file=sys.stderr)
        return 1
