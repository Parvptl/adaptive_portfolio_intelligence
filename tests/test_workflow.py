"""Milestone F (core, no ``rl`` extra): workflow configuration, read-only status, and the
dashboard's handling of missing artifacts. Synthetic paths only."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from adaptive_portfolio import workflow
from adaptive_portfolio.config import ConfigError, WorkflowConfig, load_workflow_config
from conftest import CONFIG_DIR

PATHS = {
    "dataset_dir": "data/processed/ds", "feature_dir": "data/processed/features/fs",
    "baseline_backtest_dir": "data/processed/backtests/bt",
    "validation_evaluation_dir": "data/processed/evaluations/ev",
    "explainability_root": "data/processed/explainability",
    "dashboard_dir": "reports/figures/dashboard",
}  # fmt: skip


def test_repository_workflow_config_loads() -> None:
    config = load_workflow_config(CONFIG_DIR / "workflow.yaml")
    assert config.validation_evaluation_dir.name == "1ce9c490ed03c8c9"


@pytest.mark.parametrize("key", list(PATHS))
def test_test_result_artifacts_are_refused_in_every_path(key: str) -> None:
    with pytest.raises(ConfigError, match="test-period results"):
        WorkflowConfig.from_dict({**PATHS, key: "data/processed/backtests/ac2d6b163d4f5e4b"})


def test_missing_and_unknown_keys_are_rejected() -> None:
    with pytest.raises(ConfigError, match="missing"):
        WorkflowConfig.from_dict({k: v for k, v in PATHS.items() if k != "dashboard_dir"})
    with pytest.raises(ConfigError, match="unknown"):
        WorkflowConfig.from_dict({**PATHS, "test_evaluation_dir": "x"})


@pytest.fixture
def tiny(tmp_path: Path) -> Path:
    config_dir = tmp_path / "configs"
    shutil.copytree(CONFIG_DIR, config_dir)
    (config_dir / "workflow.yaml").write_text(yaml.safe_dump(PATHS), encoding="utf-8")
    return config_dir


def test_status_is_read_only_and_lists_gated_operations(tiny: Path, capsys) -> None:
    before = sorted(p for p in tiny.parent.rglob("*"))
    assert workflow.main(["--config-dir", str(tiny)]) == 0
    out = capsys.readouterr().out
    assert "MISSING" in out and "none (test sealed)" in out and "Gate 3" in out
    assert sorted(p for p in tiny.parent.rglob("*")) == before  # nothing written


def test_verify_fails_cleanly_when_artifacts_are_missing(tiny: Path, capsys) -> None:
    assert workflow.main(["verify", "--config-dir", str(tiny)]) == 1
    assert "WORKFLOW FAILED (verify)" in capsys.readouterr().err


def test_dashboard_shows_missing_sections_instead_of_numbers(tiny: Path) -> None:
    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.dashboard import build_dashboard

    target = build_dashboard(tiny, load_workflow_config(tiny / "workflow.yaml"))
    page = (target / "index.html").read_text(encoding="utf-8")
    assert page.count("Not available.") >= 6  # every artifact-backed section, stress, test
    assert "Simulated historical backtests" in page and "test period (2020-2024) is sealed" in page
    manifest = json.loads((target / "dashboard_manifest.json").read_text(encoding="utf-8"))
    # no result was read: the only hashed source is the (draft) pre-registration config
    assert set(manifest["sources_sha256"]) == {"configs/preregistration.yaml"}
    assert target.parent == tiny.parent / "reports" / "figures" / "dashboard"
