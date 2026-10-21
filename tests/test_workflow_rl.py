"""Milestone F with real (untrained) synthetic checkpoints (``rl``): checkpoint provenance and
compatibility, workflow verify, and a dashboard built from a real evaluator output."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

from adaptive_portfolio import workflow  # noqa: E402
from adaptive_portfolio.agents import evaluate as ev  # noqa: E402
from adaptive_portfolio.agents.provenance import verify_checkpoint  # noqa: E402
from adaptive_portfolio.config import (  # noqa: E402
    load_backtest_config,
    load_project_config,
    load_workflow_config,
)
from test_validation_evaluator import project  # noqa: E402, F401  (module-scoped fixture)


@pytest.fixture(scope="module")
def evaluated(project):  # noqa: F811
    plan = ev.plan_evaluation(project["config_dir"], project["dataset_dir"],
                              project["feature_dir"])  # fmt: skip
    target = plan.output_dir if plan.output_dir.exists() else ev.run_evaluation(plan)
    root = project["root"]
    paths = {
        "dataset_dir": project["dataset_dir"].relative_to(root).as_posix(),
        "feature_dir": project["feature_dir"].relative_to(root).as_posix(),
        "baseline_backtest_dir": "data/processed/backtests/none",
        "validation_evaluation_dir": target.relative_to(root).as_posix(),
        "explainability_root": "data/processed/explainability",
        "dashboard_dir": "reports/figures/dashboard",
    }  # fmt: skip
    (project["config_dir"] / "workflow.yaml").write_text(yaml.safe_dump(paths), encoding="utf-8")
    return {**project, "evaluation_dir": target, "plan": plan}


def _checkpoint(evaluated) -> tuple[Path, str]:
    meta = json.loads((evaluated["evaluation_dir"] / "metadata.json").read_text(encoding="utf-8"))
    first = meta["checkpoints"][0]
    return evaluated["root"] / "data/processed/experiments" / first["run_id"], first["model_sha256"]


def test_selected_checkpoints_verify_and_incompatibilities_are_reported(evaluated, tmp_path):
    config = load_project_config(evaluated["config_dir"])
    backtest = load_backtest_config(evaluated["config_dir"] / "backtest.yaml")
    run_dir, sha = _checkpoint(evaluated)
    assert verify_checkpoint(run_dir, config, backtest, expected_model_sha256=sha,
                             dataset_dir=evaluated["dataset_dir"],
                             feature_dir=evaluated["feature_dir"]) == []  # fmt: skip
    assert any(
        "expected" in p
        for p in verify_checkpoint(run_dir, config, backtest, expected_model_sha256="0" * 64)
    )
    other = tmp_path / "configs"
    shutil.copytree(evaluated["config_dir"], other)
    env = yaml.safe_load((other / "environment.yaml").read_text(encoding="utf-8"))
    env["transaction_cost_bps"] = 20.0
    (other / "environment.yaml").write_text(yaml.safe_dump(env), encoding="utf-8")
    problems = verify_checkpoint(run_dir, load_project_config(other), backtest)
    assert any("incompatible cost_rate" in p for p in problems)
    copy = tmp_path / run_dir.name
    shutil.copytree(run_dir, copy)
    (copy / "model.zip").write_bytes(b"tampered")
    assert any(
        "sha256 mismatch for model.zip" in p for p in verify_checkpoint(copy, config, backtest)
    )
    assert verify_checkpoint(tmp_path / "nothing", config, backtest)


def test_workflow_verify_passes_on_a_real_evaluation(evaluated, capsys):
    assert workflow.main(["verify", "--config-dir", str(evaluated["config_dir"])]) == 0
    assert "verify: all checks passed" in capsys.readouterr().out


def test_dashboard_numbers_come_from_the_saved_evaluation(evaluated):
    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.dashboard import build_dashboard

    config = load_workflow_config(evaluated["config_dir"] / "workflow.yaml")
    first = build_dashboard(evaluated["config_dir"], config)
    page = (first / "index.html").read_text(encoding="utf-8")
    meta = json.loads((evaluated["evaluation_dir"] / "metadata.json").read_text(encoding="utf-8"))
    assert meta["evaluation_id"] in page and "verified" in page
    policies = pd.read_csv(evaluated["evaluation_dir"] / "policy_metrics.csv")
    selected = json.loads(
        (evaluated["evaluation_dir"] / "evaluation.json").read_text(encoding="utf-8")
    )["selection"]["selected_configuration"]
    for value in policies.loc[policies["configuration"] == selected, "annualised.net_sharpe"]:
        assert f"{value:.4f}" in page
    assert "Out-of-sample test results" in page and "sealed" in page
    manifest = json.loads((first / "dashboard_manifest.json").read_text(encoding="utf-8"))
    assert any(k.endswith("ledgers.csv") for k in manifest["sources_sha256"])
    assert build_dashboard(evaluated["config_dir"], config) == first  # same sources: reused
    sidecars = list((first / "figures").glob("*.json"))
    assert sidecars and all(
        re.fullmatch(r"[0-9a-f]{64}", json.loads(s.read_text(encoding="utf-8"))["figure_sha256"])
        for s in sidecars
    )


def test_dashboard_refuses_tampered_results(evaluated, tmp_path):
    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.dashboard import build_dashboard

    copy = tmp_path / "evaluation"
    shutil.copytree(evaluated["evaluation_dir"], copy)
    with (copy / "policy_metrics.csv").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    config = load_workflow_config(evaluated["config_dir"] / "workflow.yaml")
    tampered = type(config)(**{**vars(config), "validation_evaluation_dir": copy,
                               "dashboard_dir": tmp_path / "dash"})  # fmt: skip
    page = (build_dashboard(evaluated["config_dir"], tampered) / "index.html").read_text(
        encoding="utf-8"
    )
    assert "integrity check failed" in page and "policy_metrics.csv" in page
