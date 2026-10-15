"""End-to-end tests for the feature and regime pipeline (offline, synthetic data)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from adaptive_portfolio.config import load_feature_config, load_project_config
from adaptive_portfolio.data.cache import read_csv
from adaptive_portfolio.data.cli import main
from adaptive_portfolio.data.pipeline import build_dataset, project_root_for
from adaptive_portfolio.data.providers import InMemoryProvider
from adaptive_portfolio.features.engineering import FeatureDataError
from adaptive_portfolio.features.pipeline import FEATURE_FILES, build_feature_dataset
from adaptive_portfolio.regimes.rules import RegimeCalibrationError
from conftest import write_feature_config, write_tiny_project

SPLITS = {
    "train": {"start": "2024-01-01", "end": "2024-01-31"},
    "validation": {"start": "2024-02-01", "end": "2024-02-14"},
    "test": {"start": "2024-02-15", "end": "2024-02-29"},
}


def _project(root: Path, end: str = "2024-02-29") -> Path:
    config_dir = write_tiny_project(
        root, universe=["AAA", "BBB", "CCC"], start="2024-01-01", end=end, splits=SPLITS
    )
    write_feature_config(config_dir)
    return config_dir


def _build_all(config_dir: Path, **kwargs):
    config = load_project_config(config_dir)
    root = project_root_for(config_dir)
    dataset = build_dataset(config, root, provider_name="synthetic")
    features = load_feature_config(config_dir / "features.yaml")
    result = build_feature_dataset(config, features, root, provider_name="synthetic", **kwargs)
    return dataset, result


def _hashes(directory: Path) -> dict[str, str]:
    return {n: hashlib.sha256((directory / n).read_bytes()).hexdigest() for n in FEATURE_FILES}


def test_end_to_end_outputs_and_schema(tmp_path: Path) -> None:
    dataset, result = _build_all(_project(tmp_path))
    assert sorted(p.name for p in result.output_dir.iterdir()) == sorted(FEATURE_FILES)
    assert result.output_dir.parent == tmp_path / "data" / "processed" / "features"

    features = read_csv(result.output_dir / "features.csv")
    returns = read_csv(dataset.processed_dir / "returns.csv")
    splits = read_csv(dataset.processed_dir / "splits.csv")
    assert list(features.columns[:2]) == ["date", "split"]
    assert features["date"].equals(returns["date"])  # one feature row per return row
    assert features["split"].tolist() == splits["split"].tolist()  # split membership preserved

    regimes = read_csv(result.output_dir / "regimes.csv")
    assert list(regimes.columns[:4]) == ["date", "split", "equity_mom_5", "market_vol_3"]
    assert list(regimes.columns[-4:]) == [
        "trend_label",
        "volatility_label",
        "regime",
        "regime_status",
    ]
    # Trend window 5 -> 4 warm-up rows, all at the start of the training period.
    unavailable = regimes[regimes["regime"] == "unavailable"]
    assert len(unavailable) == 4 and set(unavailable["split"]) == {"train"}

    artifact = json.loads(
        (result.output_dir / "regime_thresholds.json").read_text(encoding="utf-8")
    )
    assert artifact["calibration"]["split"] == "train"
    assert artifact["calibration"]["last_date_used"] <= "2024-01-31"
    assert artifact["source"]["data_origin"] == "synthetic"
    metadata = json.loads((result.output_dir / "feature_metadata.json").read_text(encoding="utf-8"))
    assert metadata["thresholds_mode"] == "fitted_on_train"
    assert len(metadata["feature_definitions"]) == 21
    assert str(tmp_path) not in json.dumps(metadata)  # no absolute paths
    report_md = (result.output_dir / "regime_report.md").read_text(encoding="utf-8")
    assert "NOT market data" in report_md and "heuristic" in report_md


def test_rerun_is_byte_identical(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    _, first = _build_all(config_dir)
    before = _hashes(first.output_dir)
    _, second = _build_all(config_dir)
    assert second.output_dir == first.output_dir
    assert _hashes(second.output_dir) == before


def test_frozen_artifact_reproduces_labels_without_refitting(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    _, fitted = _build_all(config_dir)
    artifact = tmp_path / "frozen.json"
    shutil.copy(fitted.output_dir / "regime_thresholds.json", artifact)
    _, applied = _build_all(config_dir, thresholds_path=artifact)
    assert applied.thresholds_mode == "loaded_frozen_artifact"
    assert applied.output_dir != fitted.output_dir  # different id: artifact hash is part of it
    pd.testing.assert_frame_equal(applied.regimes, fitted.regimes)
    assert applied.thresholds == fitted.thresholds


def test_frozen_artifact_on_longer_dataset_keeps_historical_labels(tmp_path: Path) -> None:
    _, short = _build_all(_project(tmp_path / "short"))
    artifact = short.output_dir / "regime_thresholds.json"
    # Same configuration, one more month of data (labelled 'excluded' after the test period).
    _, extended = _build_all(
        _project(tmp_path / "long", end="2024-03-29"), thresholds_path=artifact
    )
    shared = short.regimes.index
    pd.testing.assert_frame_equal(extended.regimes.loc[shared], short.regimes)
    # Refitting on the longer dataset gives the same thresholds: training rows are unchanged.
    _, refit = _build_all(_project(tmp_path / "long2", end="2024-03-29"))
    assert (refit.thresholds.trend_band, refit.thresholds.volatility_low) == (
        short.thresholds.trend_band,
        short.thresholds.volatility_low,
    )
    assert refit.thresholds.calibration == short.thresholds.calibration


def test_works_offline_without_raw_snapshot(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    dataset, _ = _build_all(config_dir)
    shutil.rmtree(dataset.acquisition.snapshot_dir)  # no raw data; no provider is contacted
    config = load_project_config(config_dir)
    result = build_feature_dataset(
        config,
        load_feature_config(config_dir / "features.yaml"),
        project_root_for(config_dir),
        provider_name="synthetic",
    )
    assert result.thresholds_mode == "fitted_on_train"


def test_missing_dataset_is_actionable(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    config = load_project_config(config_dir)
    with pytest.raises(FileNotFoundError, match="build the dataset first"):
        build_feature_dataset(
            config,
            load_feature_config(config_dir / "features.yaml"),
            project_root_for(config_dir),
            provider_name="synthetic",
        )


def test_split_mismatch_is_rejected(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    dataset, _ = _build_all(config_dir)
    path = config_dir / "experiment.yaml"
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    content["splits"]["validation"]["start"] = "2024-02-02"
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    config = load_project_config(config_dir)
    with pytest.raises(FeatureDataError, match="does not match the split boundaries"):
        build_feature_dataset(
            config,
            load_feature_config(config_dir / "features.yaml"),
            project_root_for(config_dir),
            dataset_dir=dataset.processed_dir,
        )


def test_asset_order_mismatch_is_rejected(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    dataset, _ = _build_all(config_dir)
    path = config_dir / "data.yaml"
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    content["universe"] = ["BBB", "AAA", "CCC"]  # same assets, different order
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    config = load_project_config(config_dir)
    with pytest.raises(FeatureDataError, match="same instruments, same order"):
        build_feature_dataset(
            config,
            load_feature_config(config_dir / "features.yaml"),
            project_root_for(config_dir),
            dataset_dir=dataset.processed_dir,
        )


def test_multi_session_returns_need_explicit_permission(fixture_project, fixture_frames) -> None:
    # The milestone-2 fixture drops 2024-01-05, so one return spans two sessions.
    config = load_project_config(fixture_project)
    root = project_root_for(fixture_project)
    dataset = build_dataset(config, root, provider=InMemoryProvider(fixture_frames))
    groups = {"asset_groups": {"equity": ["AAA"], "bond": ["BBB"]}}
    write_feature_config(fixture_project, groups)
    features = load_feature_config(fixture_project / "features.yaml")
    with pytest.raises(FeatureDataError, match="1 return"):
        build_feature_dataset(config, features, root, dataset_dir=dataset.processed_dir)
    write_feature_config(fixture_project, {**groups, "allow_multi_session_returns": True})
    allowed = load_feature_config(fixture_project / "features.yaml")
    # Accepted now; it then fails honestly because 3 rows cannot calibrate regimes.
    with pytest.raises(RegimeCalibrationError, match="training row"):
        build_feature_dataset(config, allowed, root, dataset_dir=dataset.processed_dir)


def test_incompatible_artifact_is_rejected(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    _, fitted = _build_all(config_dir)
    artifact = tmp_path / "frozen.json"
    shutil.copy(fitted.output_dir / "regime_thresholds.json", artifact)
    write_feature_config(config_dir, {"regime": {"trend_window": 2, "volatility_window": 3}})
    config = load_project_config(config_dir)
    with pytest.raises(RegimeCalibrationError, match="does not match"):
        build_feature_dataset(
            config,
            load_feature_config(config_dir / "features.yaml"),
            project_root_for(config_dir),
            provider_name="synthetic",
            thresholds_path=artifact,
        )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cli(config_dir: Path, *args: str) -> int:
    return main(["-q", "--config-dir", str(config_dir), *args])


def test_cli_feature_workflow(tmp_path: Path, capsys) -> None:
    config_dir = _project(tmp_path)
    assert _cli(config_dir, "validate") == 0
    assert "regime inputs  : equity_mom_5, market_vol_3" in capsys.readouterr().out
    assert _cli(config_dir, "regime-report", "--provider", "synthetic") == 1
    assert "run the 'build' command first" in capsys.readouterr().err
    assert _cli(config_dir, "build", "--provider", "synthetic") == 0
    capsys.readouterr()
    assert _cli(config_dir, "features", "--provider", "synthetic") == 0
    out = capsys.readouterr().out
    assert "NOT MARKET DATA" in out and "fitted_on_train" in out and "21 columns" in out
    assert _cli(config_dir, "regime-report", "--provider", "synthetic") == 0
    assert "# Regime report" in capsys.readouterr().out


def test_cli_without_features_yaml(tmp_path: Path, capsys) -> None:
    config_dir = write_tiny_project(
        tmp_path,
        universe=["AAA", "BBB", "CCC"],
        start="2024-01-01",
        end="2024-02-29",
        splits=SPLITS,
    )
    assert _cli(config_dir, "validate") == 0
    assert "no features.yaml" in capsys.readouterr().out
    assert _cli(config_dir, "features", "--provider", "synthetic") == 1
    assert "features.yaml" in capsys.readouterr().err


def test_cli_invalid_feature_config(tmp_path: Path, capsys) -> None:
    config_dir = _project(tmp_path)
    write_feature_config(config_dir, {"market_group": "credit"})
    assert _cli(config_dir, "validate") == 1
    assert "features.market_group" in capsys.readouterr().err
