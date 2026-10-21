"""Milestone B: the PPO validation evaluator on a synthetic project (needs the ``rl`` extra).

No training: checkpoints are real but *untrained* PPO models (``learn`` is a no-op), produced
through the real grid runner and run safety, for a reduced 2 x 2 grid. All data are synthetic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import yaml

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

from adaptive_portfolio.agents import evaluate as ev  # noqa: E402
from adaptive_portfolio.agents import grid, ppo, run_safety  # noqa: E402
from adaptive_portfolio.config import (  # noqa: E402
    load_agent_config,
    load_backtest_config,
    load_feature_config,
    load_project_config,
    load_yaml,
)
from adaptive_portfolio.data.pipeline import build_dataset, project_root_for  # noqa: E402
from adaptive_portfolio.evaluation.backtest import run_backtest  # noqa: E402
from adaptive_portfolio.features.pipeline import build_feature_dataset  # noqa: E402
from conftest import CONFIG_DIR, write_feature_config, write_tiny_project  # noqa: E402

GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
       "-c", "commit.gpgsign=false"]  # fmt: skip
SPLITS = {
    "train": {"start": "2024-01-01", "end": "2024-03-29"},
    "validation": {"start": "2024-04-01", "end": "2024-05-31"},
    "test": {"start": "2024-06-01", "end": "2024-06-28"},
}
STRATEGIES = [
    {"name": "equal_weight_monthly", "type": "equal_weight", "rebalance": "monthly"},
    {"name": "buy_and_hold_equal_weight", "type": "equal_weight", "rebalance": "never"},
    {"name": "inverse_volatility_monthly", "type": "inverse_volatility", "rebalance": "monthly",
     "lookback": 10},
]  # fmt: skip


class NoLearn:
    """A real, untrained PPO model: ``learn`` only records the budget (no training)."""

    def __init__(self, env, agent, spec):
        self.model = ppo.build_model(env, agent, spec)
        self.num_timesteps = 0

    def learn(self, total_timesteps, progress_bar=False):
        self.num_timesteps = self.model.num_timesteps = total_timesteps

    def save(self, path):
        self.model.save(path)


def _git(root: Path, *args: str) -> None:
    subprocess.run([*GIT, "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> dict:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    root_dir = tmp_path_factory.mktemp("evaluator")
    config_dir = write_tiny_project(
        root_dir, universe=["AAA", "BBB", "CCC"], start="2024-01-01", end="2024-06-28",
        splits=SPLITS,
    )  # fmt: skip
    backtest = {"execution_lag_sessions": 1, "periods_per_year": 252,
                "common_start_history_sessions": 15, "strategies": STRATEGIES}  # fmt: skip
    (config_dir / "backtest.yaml").write_text(yaml.safe_dump(backtest), encoding="utf-8")
    write_feature_config(config_dir)
    agent = load_yaml(CONFIG_DIR / "agent.yaml")
    agent.update(seeds=[42, 43])
    agent["grid"] = {"learning_rate": [0.0003], "n_steps": [512], "ent_coef": [0.0, 0.01]}
    (config_dir / "agent.yaml").write_text(yaml.safe_dump(agent), encoding="utf-8")
    config = load_project_config(config_dir)
    root = project_root_for(config_dir)
    dataset = build_dataset(config, root, provider_name="synthetic")
    features = build_feature_dataset(config, load_feature_config(config_dir / "features.yaml"),
                                     root, provider_name="synthetic")  # fmt: skip
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    for command in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "project"]):
        _git(root, *command)
    plan = grid.plan_grid(config_dir, dataset.processed_dir, features.output_dir)
    backtest_config = load_backtest_config(config_dir / "backtest.yaml")
    agent_config = load_agent_config(config_dir / "agent.yaml")
    specs = {(s.configuration, s.seed): s for s in agent_config.run_specs()}

    def launch(plan_, run, timeout, log):
        spec = specs[(run["configuration"], run["seed"])]
        ppo.train_ppo_run(
            config, backtest_config, agent_config, spec, root, dataset.processed_dir,
            features.output_dir, model_factory=NoLearn,
        )  # fmt: skip
        return run_safety.LaunchOutcome(0, False, 0.0)

    assert grid.run_grid(plan, launcher=launch)["completed"] == 4
    evaluation = load_yaml(CONFIG_DIR / "evaluation.yaml")
    evaluation["grid_id"] = plan.grid_id
    (config_dir / "evaluation.yaml").write_text(yaml.safe_dump(evaluation), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "evaluation config")
    return {"config_dir": config_dir, "root": root, "dataset_dir": dataset.processed_dir,
            "feature_dir": features.output_dir, "grid_id": plan.grid_id}  # fmt: skip


def _plan(p: dict, dataset_dir=None, feature_dir=None) -> ev.EvaluationPlan:
    return ev.plan_evaluation(p["config_dir"], dataset_dir or p["dataset_dir"],
                              feature_dir or p["feature_dir"])  # fmt: skip


def _corrupt_from(path: Path, start: str, keep_first: bool = False) -> None:
    lines = path.read_bytes().splitlines(keepends=True)
    out, kept = [lines[0]], False
    for line in lines[1:]:
        late = line[:10].decode("ascii") >= start
        out.append(line if not late or (keep_first and not kept) else b"\xff\xfe bad\n")
        kept = kept or late
    path.write_bytes(b"".join(out))


def test_plan_verifies_every_checkpoint_and_reads_no_data_rows(project: dict, tmp_path) -> None:
    # Every data row (train, validation, test) is replaced by undecodable bytes: a plan that
    # read any row would fail. The plan must still verify all checkpoints and write nothing.
    data, feats = tmp_path / "data", tmp_path / "features"
    shutil.copytree(project["dataset_dir"], data)
    shutil.copytree(project["feature_dir"], feats)
    for path in (data / "returns.csv", feats / "features.csv", feats / "regimes.csv"):
        _corrupt_from(path, "2000-01-01")
    plan = _plan(project, data, feats)
    assert len(plan.checkpoints) == 4
    assert {(c.configuration, c.seed) for c in plan.checkpoints} == {(0, 42), (0, 43), (1, 42),
                                                                     (1, 43)}  # fmt: skip
    assert plan.identity["code"]["dirty"] is False
    assert plan.evaluation_id == _plan(project, data, feats).evaluation_id  # deterministic
    assert not (project["root"] / "data" / "processed" / "evaluations").exists()


def test_policies_and_baselines_share_dates_and_conventions(project: dict) -> None:
    plan = _plan(project)
    results = ev.evaluate(plan)
    ledgers = results["ledgers"]
    by_strategy = {name: frame["date"].to_numpy() for name, frame in ledgers.groupby("strategy")}
    assert len(by_strategy) == 3 + 4
    reference = next(iter(by_strategy.values()))
    assert all(np.array_equal(dates, reference) for dates in by_strategy.values())
    assert str(ledgers["date"].max().date()) <= SPLITS["validation"]["end"]
    assert str(ledgers["date"].min().date()) >= SPLITS["validation"]["start"]
    # The baselines equal the baseline backtest's validation results exactly.
    config = load_project_config(project["config_dir"])
    backtest = load_backtest_config(project["config_dir"] / "backtest.yaml")
    reference_run = run_backtest(config, backtest, project["root"],
                                 dataset_dir=project["dataset_dir"])  # fmt: skip
    for row in results["baselines"]:
        expected = ev._flatten(reference_run.metrics["metrics"]["validation"][row["strategy"]])
        expected.pop("decisions_dropped_at_split_end")
        assert {k: row[k] for k in expected} == expected
    # Selection follows the configuration summaries; every seed is reported.
    assert len(results["configurations"]) == 2 and len(results["policies"]) == 4
    medians = {c["configuration"]: c["median"] for c in results["configurations"]}
    assert results["selection"]["best_median"] == max(medians.values())
    assert all(len(c["values_by_seed"]) == 2 for c in results["configurations"])
    # Deterministic: a second evaluation gives identical results.
    again = ev.evaluate(plan)
    assert again["policies"] == results["policies"] and again["selection"] == results["selection"]


def test_evaluation_never_parses_test_rows(project: dict, tmp_path) -> None:
    clean = ev.evaluate(_plan(project))
    data, feats = tmp_path / "data", tmp_path / "features"
    shutil.copytree(project["dataset_dir"], data)
    shutil.copytree(project["feature_dir"], feats)
    test_start = SPLITS["test"]["start"]
    for path in (data / "returns.csv", feats / "features.csv", feats / "regimes.csv"):
        _corrupt_from(path, test_start)
    _corrupt_from(data / "splits.csv", test_start, keep_first=True)
    bounded = ev.evaluate(_plan(project, data, feats))
    assert bounded["policies"] == clean["policies"] and bounded["baselines"] == clean["baselines"]


@pytest.mark.parametrize("damage", ["model_bytes", "missing_run", "manifest_run", "scaler"])
def test_any_checkpoint_problem_aborts_without_skipping(project: dict, tmp_path, damage) -> None:
    copy = tmp_path / "project"
    shutil.copytree(project["root"], copy)
    out = copy / "data" / "processed" / "experiments"
    manifest_path = out / "grids" / project["grid_id"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    victim = out / manifest["runs"][1]["run_id"]
    if damage == "model_bytes":
        (victim / "model.zip").write_bytes(b"tampered")
    elif damage == "missing_run":
        shutil.rmtree(victim)
    elif damage == "manifest_run":
        manifest["runs"] = manifest["runs"][:-1]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        scaler = json.loads((victim / "scaler.json").read_text(encoding="utf-8"))
        scaler["mean"][0] += 1.0
        (victim / "scaler.json").write_text(json.dumps(scaler), encoding="utf-8")
    dataset = copy / project["dataset_dir"].relative_to(project["root"])
    features = copy / project["feature_dir"].relative_to(project["root"])
    with pytest.raises(ev.EvaluationError, match="nothing is evaluated"):
        ev.plan_evaluation(copy / "configs", dataset, features)


def test_run_writes_outputs_once_and_refuses_uncommitted_code(project: dict, tmp_path) -> None:
    copy = tmp_path / "project"
    shutil.copytree(project["root"], copy)
    dataset = copy / project["dataset_dir"].relative_to(project["root"])
    features = copy / project["feature_dir"].relative_to(project["root"])
    plan = ev.plan_evaluation(copy / "configs", dataset, features)
    target = ev.run_evaluation(plan)
    assert sorted(p.name for p in target.iterdir()) == sorted(ev.EVALUATION_FILES)
    meta = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    assert meta["evaluation_id"] == target.name == plan.evaluation_id
    assert meta["protocol"]["policy_actions"] == "deterministic"
    with pytest.raises(ev.EvaluationError, match="never overwritten"):
        ev.run_evaluation(plan)
    (copy / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    dirty = ev.plan_evaluation(copy / "configs", dataset, features)
    with pytest.raises(ev.EvaluationError, match="clean committed tree"):
        ev.run_evaluation(dirty)


def test_cli_plan_and_execute_guard(project: dict, capsys) -> None:
    args = ["--config-dir", str(project["config_dir"]), "--dataset-dir",
            str(project["dataset_dir"]), "--feature-dir", str(project["feature_dir"])]  # fmt: skip
    assert ev.main([*args, "--plan"]) == 0
    assert "PLAN (no data rows loaded, nothing written)" in capsys.readouterr().out
    assert ev.main([*args, "--execute"]) == 2  # needs --confirm-validation-evaluation


def _copy(project: dict, tmp_path: Path) -> list[str]:
    copy = tmp_path / "project"
    shutil.copytree(project["root"], copy)
    dataset = copy / project["dataset_dir"].relative_to(project["root"])
    features = copy / project["feature_dir"].relative_to(project["root"])
    return ["--config-dir", str(copy / "configs"), "--dataset-dir", str(dataset),
            "--feature-dir", str(features)]  # fmt: skip


def _no_evaluation_files(args: list[str]) -> bool:
    evaluations = Path(args[1]).parent / "data" / "processed" / "evaluations"
    return not evaluations.exists() or not [p for p in evaluations.rglob("*") if p.is_file()]


@pytest.mark.parametrize("failure", ["undefined_metric", "data_boundary"])
def test_expected_failures_exit_cleanly_and_write_nothing(
    project: dict, tmp_path, monkeypatch, capsys, failure
) -> None:
    args = _copy(project, tmp_path)
    if failure == "undefined_metric":
        original = ev.summarize_window

        def undefined(ledger, **kwargs):  # every Sharpe undefined, as for zero volatility
            summary = original(ledger, **kwargs)
            summary["annualised"]["net_sharpe"] = None
            return summary

        monkeypatch.setattr(ev, "summarize_window", undefined)
        expected = "EVALUATION FAILED (execute): SelectionError"
    else:

        def boundary(*a, **k):
            raise ev.DataBoundaryError("validation evaluation: holds rows labelled ['test']")

        monkeypatch.setattr(ev, "assert_before_split", boundary)
        expected = "EVALUATION FAILED (execute): DataBoundaryError"
    assert ev.main([*args, "--execute", "--confirm-validation-evaluation"]) == 1
    err = capsys.readouterr().err
    assert err.startswith(expected) and "Traceback" not in err
    assert _no_evaluation_files(args)  # no output, selection, lock, staging or quarantine


def test_plan_failures_are_reported_cleanly(project: dict, tmp_path, capsys) -> None:
    args = _copy(project, tmp_path)
    (Path(args[1]) / "evaluation.yaml").write_text("split: test\n", encoding="utf-8")
    assert ev.main([*args, "--plan"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("EVALUATION FAILED (plan): ConfigError") and "Traceback" not in err


def test_unexpected_programming_errors_are_not_suppressed(
    project: dict, tmp_path, monkeypatch
) -> None:
    args = _copy(project, tmp_path)

    def broken(plan):
        raise ZeroDivisionError("a programming error")

    monkeypatch.setattr(ev, "evaluate", broken)
    with pytest.raises(ZeroDivisionError):
        ev.main([*args, "--execute", "--confirm-validation-evaluation"])
    assert _no_evaluation_files(args)  # the lock is still released


def test_one_code_provenance_snapshot_per_operation(project: dict, tmp_path, monkeypatch) -> None:
    args = _copy(project, tmp_path)
    calls = []

    def provenance(root):
        calls.append(root)
        dirty = len(calls) > 1  # any later call would see a different state
        return {"git_available": True, "commit": f"{len(calls):040d}", "dirty": dirty,
                "changed_paths": 0, **({"diff_sha256": "f" * 64} if dirty else {})}  # fmt: skip

    monkeypatch.setattr(run_safety, "code_provenance", provenance)
    plan = ev.plan_evaluation(Path(args[1]), Path(args[3]), Path(args[5]))
    snapshot = {"git_available": True, "commit": f"{1:040d}", "dirty": False, "diff_sha256": None}
    assert len(calls) == 1 and dict(plan.code) == snapshot and plan.identity["code"] == snapshot
    with pytest.raises(TypeError):
        plan.code["dirty"] = True  # read-only
    target = ev.run_evaluation(plan)  # reuses the snapshot; no second capture
    assert len(calls) == 1
    meta = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    assert meta["code"] == snapshot and meta["protocol_hash"] == plan.protocol_hash


def test_plan_shows_the_protocol_hash(project: dict, capsys) -> None:
    args = ["--config-dir", str(project["config_dir"]), "--dataset-dir",
            str(project["dataset_dir"]), "--feature-dir", str(project["feature_dir"])]  # fmt: skip
    assert ev.main([*args, "--plan"]) == 0
    plan = _plan(project)
    assert f"protocol hash {plan.protocol_hash}" in capsys.readouterr().out
    assert plan.protocol_hash == plan.evaluation.protocol_hash()
