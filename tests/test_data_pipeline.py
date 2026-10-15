"""End-to-end tests: pipeline, cache, outputs, quality report and CLI (all offline)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from adaptive_portfolio.config import load_project_config
from adaptive_portfolio.data.cache import CacheError, read_csv
from adaptive_portfolio.data.cli import main
from adaptive_portfolio.data.pipeline import PROCESSED_FILES, build_dataset, project_root_for
from adaptive_portfolio.data.providers import EmptyResponseError, InMemoryProvider
from adaptive_portfolio.data.validation import DataValidationError
from conftest import REPO_ROOT


def _build(config_dir: Path, provider: InMemoryProvider, **kwargs):
    config = load_project_config(config_dir)
    return build_dataset(config, project_root_for(config_dir), provider=provider, **kwargs)


def _hashes(directory: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in PROCESSED_FILES
    }


# --------------------------------------------------------------------------
# Full build on the hand-calculated fixture
# --------------------------------------------------------------------------


def test_fixture_build_outputs_match_hand_calculation(fixture_project, fixture_frames) -> None:
    result = _build(fixture_project, InMemoryProvider(fixture_frames))
    out = result.processed_dir
    assert sorted(p.name for p in out.iterdir()) == sorted([*PROCESSED_FILES, "run_info.json"])

    assert (out / "prices.csv").read_text(encoding="utf-8") == (
        "date,AAA,BBB\n"
        "2024-01-02,100.0,50.0\n"
        "2024-01-03,110.0,50.0\n"
        "2024-01-04,99.0,55.0\n"
        "2024-01-08,108.9,44.0\n"
    )
    returns = read_csv(out / "returns.csv", ("date", "period_start"))
    assert list(returns.columns) == ["date", "period_start", "sessions_spanned", "AAA", "BBB"]
    assert returns["sessions_spanned"].tolist() == [1, 1, 2]
    np.testing.assert_allclose(returns["AAA"], [0.10, -0.10, 0.10], atol=1e-12)
    np.testing.assert_allclose(returns["BBB"], [0.0, 0.10, -0.20], atol=1e-12)

    splits = read_csv(out / "splits.csv")
    assert splits["split"].tolist() == ["train", "validation", "test"]

    long = read_csv(out / "prices_long.csv")
    assert list(long.columns) == ["date", "instrument", "adj_close"]
    assert len(long) == 8


def test_fixture_quality_report_matches_hand_calculation(fixture_project, fixture_frames) -> None:
    report = _build(fixture_project, InMemoryProvider(fixture_frames)).report
    assert report["data_origin"] == "in_memory"
    assert report["warnings"][0].startswith("FIXTURE DATA")
    assert report["calendar"]["observed_sessions"] == 5
    assert report["calendar"]["max_gap_between_sessions_days"] == 3  # 01-05 -> 01-08
    assert report["calendar"]["sessions_per_calendar_year"] == {"2024": 5}
    assert report["missing_data"]["missing_cells"] == 1
    assert report["missing_data"]["dropped_sessions"] == [
        {"date": "2024-01-05", "missing_instruments": ["BBB"]}
    ]
    assert report["missing_data"]["returns_spanning_multiple_sessions"] == 1
    assert report["processed"]["sessions"] == 4
    assert report["returns"]["rows"] == 3
    assert report["returns"]["max_abs_return_observed"] == pytest.approx(0.20, abs=1e-12)
    per = {item["instrument"]: item for item in report["instruments"]["per_instrument"]}
    assert (per["AAA"]["raw_rows"], per["AAA"]["missing_cells_on_observed_calendar"]) == (5, 0)
    assert (
        per["BBB"]["raw_missing_price_rows"],
        per["BBB"]["missing_cells_on_observed_calendar"],
    ) == (1, 1)
    assert (per["BBB"]["processed_price_min"], per["BBB"]["processed_price_max"]) == (44.0, 55.0)
    assert per["BBB"]["return_min"] == pytest.approx(-0.20, abs=1e-12)
    counts = {name: part["count"] for name, part in report["splits"]["partitions"].items()}
    assert counts == {"train": 1, "validation": 1, "test": 1}

    markdown = (
        _build(fixture_project, InMemoryProvider(fixture_frames)).processed_dir
        / "quality_report.md"
    ).read_text(encoding="utf-8")
    assert "FIXTURE DATA" in markdown and "dropped 2024-01-05: missing BBB" in markdown


def test_metadata_records_provenance_without_absolute_paths(
    fixture_project, fixture_frames
) -> None:
    result = _build(fixture_project, InMemoryProvider(fixture_frames))
    metadata = json.loads((result.processed_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["data_origin"] == "in_memory"
    assert metadata["request"]["universe"] == ["AAA", "BBB"]
    assert metadata["processing"]["missing_data"]["policy"] == "drop_sessions"
    assert metadata["raw_snapshot_dir"].startswith("data/raw/in_memory/")
    assert str(fixture_project.parent) not in json.dumps(metadata)
    manifest = json.loads(
        (result.acquisition.snapshot_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert set(manifest["files"]) == {"AAA", "BBB"}
    assert manifest["retrieved_at_utc"] == metadata["retrieved_at_utc"]
    assert {"python", "numpy", "pandas"} <= set(manifest["software"])


# --------------------------------------------------------------------------
# Cache behaviour
# --------------------------------------------------------------------------


def test_cache_miss_then_hit_and_deterministic_outputs(fixture_project, fixture_frames) -> None:
    first_provider = InMemoryProvider(fixture_frames)
    first = _build(fixture_project, first_provider)
    assert first.acquisition.cache_status == "fetched"
    assert first_provider.calls == ["AAA", "BBB"]
    before = _hashes(first.processed_dir)

    second_provider = InMemoryProvider(fixture_frames)
    second = _build(fixture_project, second_provider)
    assert second.acquisition.cache_status == "hit"
    assert second_provider.calls == []  # no provider request on a cache hit
    assert second.processed_dir == first.processed_dir
    assert _hashes(second.processed_dir) == before  # byte-identical processed files
    run_info = json.loads((second.processed_dir / "run_info.json").read_text(encoding="utf-8"))
    assert run_info["cache_status"] == "hit"


def test_tampered_snapshot_is_refetched_in_use_mode(fixture_project, fixture_frames) -> None:
    first = _build(fixture_project, InMemoryProvider(fixture_frames))
    snapshot = first.acquisition.snapshot_dir / "AAA.csv"
    snapshot.write_text(
        snapshot.read_text(encoding="utf-8").replace("110.0", "111.0"), encoding="utf-8"
    )
    provider = InMemoryProvider(fixture_frames)
    second = _build(fixture_project, provider)
    assert second.acquisition.cache_status == "fetched"
    assert provider.calls == ["AAA", "BBB"]
    assert "2024-01-03,110.0,50.0" in (second.processed_dir / "prices.csv").read_text(
        encoding="utf-8"
    )


def test_tampered_snapshot_fails_in_offline_mode(fixture_project, fixture_frames) -> None:
    first = _build(fixture_project, InMemoryProvider(fixture_frames))
    (first.acquisition.snapshot_dir / "BBB.csv").write_text("date,adj_close\n", encoding="utf-8")
    with pytest.raises(CacheError, match="checksum mismatch"):
        _build(fixture_project, InMemoryProvider(fixture_frames), cache_mode="offline")


def test_manifest_for_other_request_is_rejected(fixture_project, fixture_frames) -> None:
    first = _build(fixture_project, InMemoryProvider(fixture_frames))
    manifest_path = first.acquisition.snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["request"]["end"] = "2030-01-01"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CacheError, match="different request"):
        _build(fixture_project, InMemoryProvider(fixture_frames), cache_mode="offline")


def test_refresh_mode_always_fetches(fixture_project, fixture_frames) -> None:
    _build(fixture_project, InMemoryProvider(fixture_frames))
    provider = InMemoryProvider(fixture_frames)
    assert (
        _build(fixture_project, provider, cache_mode="refresh").acquisition.cache_status
        == "fetched"
    )
    assert provider.calls == ["AAA", "BBB"]


def test_offline_mode_without_snapshot_never_calls_provider(
    fixture_project, fixture_frames
) -> None:
    provider = InMemoryProvider(fixture_frames)
    with pytest.raises(CacheError, match="offline"):
        _build(fixture_project, provider, cache_mode="offline")
    assert provider.calls == []


def test_changed_local_csv_invalidates_cache(fixture_project, fixture_frames) -> None:
    input_dir = fixture_project.parent / "data" / "raw" / "csv_input"
    input_dir.mkdir(parents=True)
    for ticker, frame in fixture_frames.items():
        frame.assign(date=frame["date"].dt.strftime("%Y-%m-%d")).to_csv(
            input_dir / f"{ticker}.csv", index=False
        )
    config = load_project_config(fixture_project)
    root = project_root_for(fixture_project)
    assert build_dataset(config, root).acquisition.cache_status == "fetched"
    assert build_dataset(config, root).acquisition.cache_status == "hit"
    text = (input_dir / "AAA.csv").read_text(encoding="utf-8").replace("108.9", "109.9")
    (input_dir / "AAA.csv").write_text(text, encoding="utf-8")
    rebuilt = build_dataset(config, root)
    assert rebuilt.acquisition.cache_status == "fetched"
    assert "2024-01-08,109.9,44.0" in (rebuilt.processed_dir / "prices.csv").read_text(
        encoding="utf-8"
    )


# --------------------------------------------------------------------------
# Failure handling
# --------------------------------------------------------------------------


def test_provider_error_leaves_no_snapshot(fixture_project, fixture_frames) -> None:
    provider = InMemoryProvider({"AAA": fixture_frames["AAA"]})  # BBB unavailable
    with pytest.raises(EmptyResponseError, match="BBB"):
        _build(fixture_project, provider)
    raw_root = fixture_project.parent / "data" / "raw" / "in_memory"
    assert not raw_root.exists() or not any(raw_root.iterdir())


def test_malformed_frame_is_rejected(fixture_project, fixture_frames) -> None:
    frames = {t: f.drop(columns="adj_close") for t, f in fixture_frames.items()}
    with pytest.raises(DataValidationError, match="missing column"):
        _build(fixture_project, InMemoryProvider(frames))


def test_error_policy_stops_on_missing_cell(tmp_path, fixture_frames) -> None:
    from conftest import FIXTURE_SPLITS, write_tiny_project

    config_dir = write_tiny_project(
        tmp_path,
        universe=["AAA", "BBB"],
        start="2024-01-01",
        end="2024-01-10",
        splits=FIXTURE_SPLITS,
        provider="csv",
    )
    with pytest.raises(DataValidationError, match=r"missing_data\.policy is 'error'"):
        _build(config_dir, InMemoryProvider(fixture_frames))


def test_min_sessions_enforced(fixture_project, fixture_frames) -> None:
    path = fixture_project / "data.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["validation"]["min_sessions"] = 10
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(DataValidationError, match="min_sessions=10"):
        _build(fixture_project, InMemoryProvider(fixture_frames))


def test_non_daily_frequency_not_supported(fixture_project, fixture_frames) -> None:
    for name in ("data.yaml", "environment.yaml"):
        path = fixture_project / name
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        content["frequency" if name == "data.yaml" else "rebalance_frequency"] = "weekly"
        path.write_text(yaml.safe_dump(content), encoding="utf-8")
    with pytest.raises(DataValidationError, match="only 'daily'"):
        _build(fixture_project, InMemoryProvider(fixture_frames))


# --------------------------------------------------------------------------
# Command-line interface
# --------------------------------------------------------------------------


def _cli(config_dir: Path, *args: str) -> int:
    return main(["-q", "--config-dir", str(config_dir), *args])


def test_cli_end_to_end_with_synthetic_data(synthetic_project, capsys) -> None:
    assert _cli(synthetic_project, "validate") == 0
    assert "AAA, BBB, CCC" in capsys.readouterr().out

    assert _cli(synthetic_project, "build", "--provider", "synthetic") == 0
    out = capsys.readouterr().out
    assert "NOT MARKET DATA" in out and "FETCHED" in out

    assert _cli(synthetic_project, "build", "--provider", "synthetic") == 0
    assert "CACHE HIT" in capsys.readouterr().out

    assert (
        _cli(synthetic_project, "fetch", "--provider", "synthetic", "--cache-mode", "offline") == 0
    )
    assert "CACHE HIT" in capsys.readouterr().out

    assert _cli(synthetic_project, "report", "--provider", "synthetic") == 0
    report = capsys.readouterr().out
    assert "# Dataset quality report" in report and "SYNTHETIC DATA" in report

    assert _cli(synthetic_project, "split", "--provider", "synthetic") == 0
    assert "Reproduced" in capsys.readouterr().out


def test_cli_split_detects_modified_assignment(synthetic_project, capsys) -> None:
    assert _cli(synthetic_project, "build", "--provider", "synthetic") == 0
    processed = next((synthetic_project.parent / "data" / "processed").iterdir())
    splits = processed / "splits.csv"
    splits.write_text(
        splits.read_text(encoding="utf-8").replace("validation", "train", 1), encoding="utf-8"
    )
    capsys.readouterr()
    assert _cli(synthetic_project, "split", "--provider", "synthetic") == 1
    assert "MISMATCH" in capsys.readouterr().out


def test_cli_errors_are_actionable(synthetic_project, capsys) -> None:
    assert _cli(synthetic_project, "build", "--provider", "csv") == 1
    assert "expected local file" in capsys.readouterr().err
    assert (
        _cli(synthetic_project, "build", "--provider", "synthetic", "--cache-mode", "offline") == 1
    )
    assert "offline" in capsys.readouterr().err
    assert _cli(synthetic_project, "report") == 1
    assert "run the 'build' command first" in capsys.readouterr().err


def test_cli_invalid_config_and_usage(tmp_path, synthetic_project, capsys) -> None:
    path = synthetic_project / "data.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["cache"] = {"mode": "sometimes"}
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert _cli(synthetic_project, "validate") == 1
    assert "data.cache.mode" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exit_info:
        main(["build", "--provider", "bloomberg"])
    assert exit_info.value.code == 2


def test_script_entry_point_runs(synthetic_project) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "market_data.py"),
            "--config-dir",
            str(synthetic_project),
            "validate",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Configuration OK" in completed.stdout


def test_synthetic_build_rows_are_weekdays(synthetic_project) -> None:
    config = load_project_config(synthetic_project)
    result = build_dataset(config, project_root_for(synthetic_project), provider_name="synthetic")
    prices = read_csv(result.processed_dir / "prices.csv")
    assert (pd.DatetimeIndex(prices["date"]).dayofweek < 5).all()
    # Weekdays: January 2024 has 23, February 2024 (29 days, starting Thursday) has 21.
    assert len(prices) == 23 + 21
