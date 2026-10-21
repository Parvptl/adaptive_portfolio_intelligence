"""Milestone D: the separate test evaluator on a synthetic project (``rl``). Nothing real is read.

The checkpoints are real but untrained PPO models from the synthetic grid of
``test_validation_evaluator``; the synthetic "test" split (June 2024) stands in for the sealed
test period. These tests exercise every guard, one complete run and its independent check.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

from adaptive_portfolio.agents import evaluate as ev  # noqa: E402
from adaptive_portfolio.agents import test_evaluate as te  # noqa: E402
from adaptive_portfolio.config import PREREGISTRATION_ITEMS, load_preregistration  # noqa: E402
from adaptive_portfolio.data import cache  # noqa: E402
from conftest import CONFIG_DIR  # noqa: E402
from test_validation_evaluator import _git, project  # noqa: E402, F401  (module-scoped fixture)

DATA_FILES = ("returns.csv", "features.csv", "regimes.csv", "splits.csv")


def _sessions(p: dict, peak: str, trough: str) -> int:
    """Return sessions in (peak, trough] of the *synthetic* calendar (no real data)."""
    dates = pd.read_csv(p["dataset_dir"] / "returns.csv", usecols=["date"])["date"]
    return int(((dates > peak) & (dates <= trough)).sum())


def _prereg(p: dict, evaluation_dir: Path, *, status: str = "frozen") -> dict:
    raw = yaml.safe_load((CONFIG_DIR / "preregistration.yaml").read_text(encoding="utf-8"))
    meta = json.loads((evaluation_dir / "metadata.json").read_text(encoding="utf-8"))
    doc = json.loads((evaluation_dir / "evaluation.json").read_text(encoding="utf-8"))
    selected = doc["selection"]["selected_configuration"]
    raw["candidate"].update(
        configuration=selected, grid_id=meta["grid"]["grid_id"],
        validation_evaluation_id=meta["evaluation_id"],
        checkpoints=[{"seed": c["seed"], "run_id": c["run_id"], "model_sha256": c["model_sha256"]}
                     for c in meta["checkpoints"] if c["configuration"] == selected],
    )  # fmt: skip
    raw["regimes"]["thresholds_sha256"] = cache.file_sha256(
        p["feature_dir"] / "regime_thresholds.json"
    )
    raw["uncertainty"].update(resamples=200, mean_block_length=3, sensitivity_block_lengths=[])
    expected = _sessions(p, "2024-06-07", "2024-06-20")
    raw["stress_windows"].update(
        sources=[{"citation": "synthetic fixture calendar", "url": "https://example.invalid/x"}],
        windows=[{"name": "w1", "peak_close": "2024-06-07", "trough_close": "2024-06-20",
                  "expected_sessions": expected},
                 {"name": "w_mismatch", "peak_close": "2024-06-07", "trough_close": "2024-06-20",
                  "expected_sessions": expected + 1}],
    )  # fmt: skip
    raw["status"] = status
    for name in PREREGISTRATION_ITEMS:
        raw[name]["decision"] = "ACCEPTED" if status == "frozen" else "OPEN"
        raw[name]["record"] = "synthetic test" if status == "frozen" else None
    return raw


@pytest.fixture(scope="module")
def ready(project):  # noqa: F811
    plan = ev.plan_evaluation(project["config_dir"], project["dataset_dir"],
                              project["feature_dir"])  # fmt: skip
    evaluation_dir = plan.output_dir if plan.output_dir.exists() else ev.run_evaluation(plan)
    path = project["config_dir"] / "preregistration.yaml"
    path.write_text(yaml.safe_dump(_prereg(project, evaluation_dir)), encoding="utf-8")
    _git(project["root"], "add", "-A")
    _git(project["root"], "commit", "-q", "-m", "frozen synthetic pre-registration")
    head = (project["root"] / ".git").exists()
    assert head
    return {**project, "evaluation_dir": evaluation_dir, "prereg_path": path}


def _plan(p, path=None, config_dir=None):
    return te.plan_test_evaluation(config_dir or p["config_dir"], path, p["dataset_dir"],
                                   p["feature_dir"])  # fmt: skip


def _commit(p) -> str:
    import subprocess

    return subprocess.run(["git", "-C", str(p["root"]), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()  # fmt: skip


def test_plan_reads_no_data_rows_and_lists_blockers(ready, tmp_path) -> None:
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(_prereg(ready, ready["evaluation_dir"], status="draft")),
                     encoding="utf-8")  # fmt: skip
    opened: list[str] = []

    def hook(event, args):
        if event == "open" and args and isinstance(args[0], str | Path):
            opened.append(Path(args[0]).name)

    sys.addaudithook(hook)
    plan = _plan(ready, draft)
    seen, opened[:] = list(opened), []
    assert not set(seen) & set(DATA_FILES), seen
    assert plan.blockers and "status is 'draft', not 'frozen'" in plan.blockers
    assert not plan.output_root.exists()


def test_execute_refuses_unless_every_guard_holds(ready, tmp_path, capsys) -> None:
    plan = _plan(ready)
    assert not plan.blockers
    sha, commit = plan.preregistration.sha256(), _commit(ready)
    with pytest.raises(te.TestEvaluationError, match="hash differs"):
        te.run_test_evaluation(plan, preregistration_sha256="0" * 64, expected_commit=commit)
    with pytest.raises(te.TestEvaluationError, match="not the authorised commit"):
        te.run_test_evaluation(plan, preregistration_sha256=sha, expected_commit="deadbeef")
    with pytest.raises(te.TestEvaluationError, match="not the authorised commit"):
        te.run_test_evaluation(plan, preregistration_sha256=sha, expected_commit=commit[:12])
    draft = tmp_path / "draft.yaml"
    draft.write_text(yaml.safe_dump(_prereg(ready, ready["evaluation_dir"], status="draft")),
                     encoding="utf-8")  # fmt: skip
    with pytest.raises(te.TestEvaluationError, match="not frozen"):
        te.run_test_evaluation(_plan(ready, draft), preregistration_sha256=sha,
                               expected_commit=commit)  # fmt: skip
    stray = ready["root"] / "stray.txt"
    stray.write_text("uncommitted", encoding="utf-8")
    try:
        with pytest.raises(te.TestEvaluationError, match="clean committed tree"):
            te.run_test_evaluation(_plan(ready), preregistration_sha256=sha, expected_commit=commit)
    finally:
        stray.unlink()
    assert te.main(["--execute", "--config-dir", str(ready["config_dir"])]) == 2
    assert not plan.output_root.exists()


def test_candidate_must_be_the_validation_selection(ready, tmp_path) -> None:
    raw = _prereg(ready, ready["evaluation_dir"])
    raw["candidate"]["configuration"] += 1
    path = tmp_path / "other.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(te.TestEvaluationError, match="selected"):
        _plan(ready, path)


def test_undefined_primary_metric_fails_and_writes_nothing(ready, monkeypatch) -> None:
    plan = _plan(ready)
    real = te._summary
    calls = {"n": 0}

    def undefined_once(ledger, plan_, settings):
        summary = real(ledger, plan_, settings)
        calls["n"] += 1
        if calls["n"] == 1:  # the first primary policy
            summary["annualised"]["net_sharpe"] = None
        return summary

    monkeypatch.setattr(te, "_summary", undefined_once)
    with pytest.raises(te.TestEvaluationError, match="undefined primary metric"):
        te.run_test_evaluation(plan, preregistration_sha256=plan.preregistration.sha256(),
                               expected_commit=_commit(ready))  # fmt: skip
    root = plan.output_root
    assert not root.exists() or not any(p.name == plan.evaluation_id for p in root.iterdir())


def _executed(ledger: pd.DataFrame) -> pd.DataFrame:
    rows = ledger[ledger["rebalanced"].astype(bool)]
    return rows.filter(like="weight_").reset_index(drop=True)


def test_one_frozen_run_is_written_once_and_verifies(ready) -> None:
    plan = _plan(ready)
    sha, commit = plan.preregistration.sha256(), _commit(ready)
    target = te.run_test_evaluation(plan, preregistration_sha256=sha, expected_commit=commit)
    prereg = load_preregistration(ready["prereg_path"])
    assert sorted(p.name for p in target.iterdir()) == sorted(te.TEST_FILES)
    assert te.verify_test_evaluation(target, prereg) == []
    document = json.loads((target / "evaluation.json").read_text(encoding="utf-8"))
    assert document["selection"].startswith("none")
    by_seed = document["primary_endpoint"]["by_seed"]
    assert document["primary_endpoint"]["value"] == pd.Series(by_seed).median()
    ledgers = pd.read_csv(target / "ledgers.csv", float_precision="round_trip")
    assert ledgers["date"].min() >= "2024-06-01" and ledgers["date"].max() <= "2024-06-28"
    scenarios = pd.read_csv(target / "scenarios.csv").set_index("scenario")
    assert set(scenarios.index) == {
        "primary",
        "fixed_action_cost_0bps",
        "fixed_action_cost_15bps",
        "fixed_action_cost_30bps",
    }
    assert (scenarios["status"] == "computed").all()
    # fixed-action accounting: identical targets at every cost; 15 bps equals the primary run
    primary = ledgers[ledgers["scenario"] == "primary"]
    for strategy, base in primary.groupby("strategy"):
        for bps in ("0", "15", "30"):
            other = ledgers[(ledgers["scenario"] == f"fixed_action_cost_{bps}bps")
                            & (ledgers["strategy"] == strategy)]  # fmt: skip
            assert _executed(other).equals(_executed(base))
        same = ledgers[(ledgers["scenario"] == "fixed_action_cost_15bps")
                       & (ledgers["strategy"] == strategy)]  # fmt: skip
        numeric = base.select_dtypes("number").reset_index(drop=True)
        assert same.select_dtypes("number").reset_index(drop=True).equals(numeric)
    comparison = pd.read_csv(target / "primary_comparison.csv", float_precision="round_trip")
    assert len(comparison) == 1 and comparison["role"].iloc[0] == "primary"
    assert comparison["comparator"].iloc[0] == "inverse_volatility_monthly"
    assert comparison["p_value"].iloc[0] == "not reported (D-083)"
    assert not {"outcome", "p_adjusted"} & set(comparison.columns)
    metrics = pd.read_csv(target / "baseline_metrics.csv", float_precision="round_trip")
    iv = metrics[(metrics["scenario"] == "primary")
                 & (metrics["strategy"] == "inverse_volatility_monthly")]  # fmt: skip
    expected = pd.Series(by_seed).median() - iv["annualised.net_sharpe"].iloc[0]
    assert comparison["estimate"].iloc[0] == pytest.approx(expected, rel=1e-12)
    draws = pd.read_csv(target / "bootstrap_draws.csv")
    assert len(draws) == 200 and draws.columns[-1].startswith("delta_median_seed_sharpe_minus_")
    descriptive = pd.read_csv(target / "descriptive_differences.csv")
    assert set(descriptive["baseline"]) == {"equal_weight_monthly", "buy_and_hold_equal_weight"}
    assert not {"ci_low", "ci_high"} & set(descriptive.columns)
    stress = pd.read_csv(target / "stress_windows.csv")
    assert len(stress) == 2 * (len(by_seed) + 3)
    assert (stress.loc[stress["window"] == "w1", "status"] == "computed").all()
    assert (
        stress.loc[stress["window"] == "w_mismatch", "status"].str.startswith("not computed").all()
    )
    evidence = json.loads((target / "boundary_evidence.json").read_text(encoding="utf-8"))
    assert set(evidence["files_sha256"]) == {
        "returns.csv",
        "splits.csv",
        "features.csv",
        "regimes.csv",
    }
    assert len(pd.read_csv(target / "allocations.csv")) == len(by_seed) + 3
    with pytest.raises(te.TestEvaluationError, match=r"exists|once"):
        te.run_test_evaluation(_plan(ready), preregistration_sha256=sha, expected_commit=commit)
    for name, column, message in (
        ("policy_metrics.csv", "annualised.net_sharpe", "does not recompute"),
        ("primary_comparison.csv", "estimate", "primary estimate does not recompute"),
        ("allocations.csv", "mean_risky_exposure", "allocations do not recompute"),
    ):
        copy = target.parent / "tampered_copy"
        shutil.copytree(target, copy)
        try:
            frame = pd.read_csv(copy / name)
            frame.loc[0, column] += 0.1
            frame.to_csv(copy / name, index=False)
            problems = te.verify_test_evaluation(copy, prereg)
            assert any("hash mismatch" in p for p in problems)
            assert any(message in p for p in problems), problems
        finally:
            shutil.rmtree(copy)


def test_rows_after_test_end_are_refused(ready, tmp_path, monkeypatch) -> None:
    import dataclasses

    from adaptive_portfolio.config import load_project_config

    configs = tmp_path / "configs"
    shutil.copytree(ready["config_dir"], configs)
    experiment = yaml.safe_load((configs / "experiment.yaml").read_text(encoding="utf-8"))
    experiment["splits"]["test"]["end"] = "2024-06-21"
    (configs / "experiment.yaml").write_text(yaml.safe_dump(experiment), encoding="utf-8")
    original = _plan(ready)
    plan = dataclasses.replace(original, config=load_project_config(configs))
    with pytest.raises(te.EXPECTED_FAILURES, match="does not match the split boundaries"):
        te.evaluate_test(plan)  # refused by the loader's contract check
    # The evaluator's own guard: rows that do arrive after test.end are refused.
    real_inputs, real_outputs = te.load_processed_inputs, te.load_feature_outputs
    monkeypatch.setattr(
        te, "load_processed_inputs", lambda d, c, **k: real_inputs(d, original.config, **k)
    )
    monkeypatch.setattr(
        te, "load_feature_outputs", lambda f, d, c, **k: real_outputs(f, d, original.config, **k)
    )
    with pytest.raises(te.DataBoundaryError, match=r"after test\.end"):
        te.evaluate_test(plan)
