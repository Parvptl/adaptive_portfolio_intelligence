"""Pre-grid hardening (D-075): run safety in ``train_ppo_run`` and the sequential grid runner.

No PPO training: ``train_ppo_run`` gets a stub model whose ``learn`` only records settings, and
the grid runner gets fake launchers (success, failure, hard-killed child). The synthetic
project is a committed Git repository, so ``full`` runs pass the code policy.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

import torch  # noqa: E402

from adaptive_portfolio.agents import grid, ppo, run_safety  # noqa: E402
from adaptive_portfolio.config import (  # noqa: E402
    load_agent_config,
    load_backtest_config,
    load_project_config,
)
from adaptive_portfolio.data.pipeline import project_root_for  # noqa: E402
from test_ppo_wrapper import _tiny_project  # noqa: E402


class StubModel:
    """Stands in for PPO: no training. Records the torch settings seen inside ``learn``."""

    seen: dict = {}  # noqa: RUF012

    def __init__(self, env, agent, spec, fail=False, side_effect=None):
        self.num_timesteps, self.fail, self.side_effect = 0, fail, side_effect

    def learn(self, total_timesteps, progress_bar=False):
        StubModel.seen = {
            "deterministic": torch.are_deterministic_algorithms_enabled(),
            "threads": torch.get_num_threads(),
        }
        if self.side_effect:
            self.side_effect()
        if self.fail:
            raise RuntimeError("stub failure")
        self.num_timesteps = total_timesteps

    def save(self, path):
        Path(path).write_bytes(b"stub checkpoint")


def _dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


@pytest.fixture
def project(tmp_path: Path) -> dict:
    config_dir, dataset_dir, feature_dir = _tiny_project(tmp_path)
    return {
        "config_dir": config_dir,
        "root": project_root_for(config_dir),
        "dataset_dir": dataset_dir,
        "feature_dir": feature_dir,
        "config": load_project_config(config_dir),
        "backtest": load_backtest_config(config_dir / "backtest.yaml"),
        "agent": load_agent_config(config_dir / "agent.yaml"),
    }


def _train(p: dict, spec_index: int = 0, **kwargs) -> ppo.TrainingRunResult:
    kwargs.setdefault("model_factory", StubModel)
    return ppo.train_ppo_run(
        p["config"], p["backtest"], p["agent"], p["agent"].run_specs()[spec_index], p["root"],
        p["dataset_dir"], p["feature_dir"], **kwargs,
    )  # fmt: skip


def _output(p: dict) -> Path:
    return p["root"] / "data" / "processed" / "experiments"


# --------------------------------------------------------------------------
# train_ppo_run: provenance, determinism, duplicates, locks, failures
# --------------------------------------------------------------------------


def test_completed_run_records_code_and_determinism(project: dict) -> None:
    threads, deterministic = torch.get_num_threads(), torch.are_deterministic_algorithms_enabled()
    result = _train(project)
    assert StubModel.seen == {"deterministic": True, "threads": 1}  # inside learn
    assert torch.get_num_threads() == threads  # restored afterwards
    assert torch.are_deterministic_algorithms_enabled() == deterministic
    meta = result.metadata
    assert meta["code"]["dirty"] is False and len(meta["code"]["commit"]) == 40
    assert meta["determinism"]["torch_use_deterministic_algorithms"] is True
    assert run_safety.verify_run_dir(result.output_dir, result.run_id, 100_000) == []
    assert sorted(p.name for p in _output(project).iterdir()) == [result.run_id]  # no lock left


def test_full_runs_refuse_uncommitted_code_and_smoke_runs_record_it(project: dict) -> None:
    (project["config_dir"] / "agent.yaml").write_text(
        (project["config_dir"] / "agent.yaml").read_text(encoding="utf-8") + "\n# edit\n",
        encoding="utf-8",
    )
    with pytest.raises(ppo.TrainingError, match="clean, committed"):
        _train(project)
    assert not _output(project).exists()
    smoke = _train(project, total_timesteps=2048, run_kind="smoke")
    assert smoke.metadata["code"]["dirty"] is True and smoke.metadata["code"]["diff_sha256"]


def test_duplicate_runs_are_refused_and_completed_results_untouched(project: dict) -> None:
    first = _train(project)
    before = {p.name: p.read_bytes() for p in first.output_dir.iterdir()}
    with pytest.raises(ppo.TrainingError, match="never overwritten"):
        _train(project)
    assert {p.name: p.read_bytes() for p in first.output_dir.iterdir()} == before


def test_held_and_stale_locks(project: dict) -> None:
    out = _output(project)
    out.mkdir(parents=True)
    run_id = grid.plan_grid(project["config_dir"]).runs[0]["run_id"]
    lock = out / f"{run_id}.lock"
    info = {"host": socket.gethostname(), "created_at": "x", "purpose": "test"}
    lock.write_text(json.dumps({**info, "pid": os.getpid()}), encoding="utf-8")
    with pytest.raises(ppo.TrainingError, match=r"locked \(alive\)"):
        _train(project)
    lock.write_text(json.dumps({**info, "pid": _dead_pid()}), encoding="utf-8")
    with pytest.raises(ppo.TrainingError, match=r"locked \(stale\).*recover"):
        _train(project)  # never silently taken over
    assert [a["action"] for a in run_safety.recover_stale(out)] == ["quarantined"]
    assert _train(project).run_id == run_id


def test_failed_run_is_quarantined_not_deleted(project: dict) -> None:
    def failing(env, agent, spec):
        return StubModel(env, agent, spec, fail=True)

    with pytest.raises(RuntimeError, match="stub failure"):
        _train(project, model_factory=failing)
    out = _output(project)
    assert [p.name for p in out.iterdir()] == [run_safety.QUARANTINE_DIR]  # no run, no lock
    (event,) = list((out / run_safety.QUARANTINE_DIR).iterdir())
    reason = json.loads((event / "reason.json").read_text(encoding="utf-8"))
    assert "RuntimeError: stub failure" in reason["reason"]
    assert any(p.name.endswith(f"staging-{os.getpid()}") for p in event.iterdir())
    assert torch.get_num_threads() >= 1


def test_finalise_refuses_a_destination_created_during_training(project: dict) -> None:
    run_id = grid.plan_grid(project["config_dir"]).runs[0]["run_id"]
    target = _output(project) / run_id

    def racing(env, agent, spec):
        def create():  # another writer appears while this run trains
            target.mkdir()
            (target / "model.zip").write_bytes(b"other result")

        return StubModel(env, agent, spec, side_effect=create)

    with pytest.raises(ppo.TrainingError, match="could not finalise"):
        _train(project, model_factory=racing)
    assert (target / "model.zip").read_bytes() == b"other result"  # not replaced
    assert list((_output(project) / run_safety.QUARANTINE_DIR).iterdir())  # staging kept


# --------------------------------------------------------------------------
# Grid runner: manifest, resume, failure policy, recovery
# --------------------------------------------------------------------------


def _ok_launcher(p: dict, calls: list):
    def launch(plan, run, timeout, log):
        calls.append((run["configuration"], run["seed"], timeout))
        result = _train(p, spec_index=[(s.configuration, s.seed) for s in
                                       p["agent"].run_specs()].index(
            (run["configuration"], run["seed"])))  # fmt: skip
        assert result.run_id == run["run_id"]
        return run_safety.LaunchOutcome(0, False, 0.1)

    return launch


def test_grid_manifest_runs_sequentially_and_resumes(project: dict) -> None:
    plan = grid.plan_grid(project["config_dir"])
    assert len(plan.runs) == 40 and len({r["run_id"] for r in plan.runs}) == 40
    calls: list = []
    first = grid.run_grid(plan, launcher=_ok_launcher(project, calls), max_runs=3)
    assert (first["completed"], first["pending"], first["launched"]) == (3, 37, 3)
    assert [c[:2] for c in calls] == [(0, 42), (0, 43), (0, 44)] and calls[0][2] == 900
    second = grid.run_grid(plan, launcher=_ok_launcher(project, calls), max_runs=2)
    assert second["completed"] == 5 and [c[:2] for c in calls[3:]] == [(0, 45), (0, 46)]
    manifest = json.loads(plan.manifest_path.read_text(encoding="utf-8"))
    assert [r["status"] for r in manifest["runs"][:6]] == ["completed"] * 5 + ["pending"]
    assert manifest["code"]["dirty"] is False and manifest["execution"]["mode"] == "sequential"
    assert not (plan.grid_dir / "runner.lock").exists()


def test_grid_stops_at_first_failure_and_retries_only_on_request(project: dict) -> None:
    plan = grid.plan_grid(project["config_dir"])
    calls: list = []
    ok = _ok_launcher(project, calls)

    def fail_second(plan_, run, timeout, log):
        if run["seed"] == 43:
            return run_safety.LaunchOutcome(1, False, 0.1)
        return ok(plan_, run, timeout, log)

    summary = grid.run_grid(plan, launcher=fail_second)
    assert (summary["completed"], summary["failed"], summary["pending"]) == (1, 1, 38)
    assert "exit code 1" in summary["stopped"]
    with pytest.raises(grid.GridError, match="--retry-failed"):
        grid.run_grid(plan, launcher=ok)
    retried = grid.run_grid(plan, launcher=ok, retry_failed=True, max_runs=1)
    assert retried["failed"] == 0 and retried["completed"] == 2
    manifest = json.loads(plan.manifest_path.read_text(encoding="utf-8"))
    assert [a["outcome"] for a in manifest["runs"][1]["attempts"]] == ["failed", "completed"]


def test_hard_killed_run_is_recovered_and_recorded(project: dict) -> None:
    plan = grid.plan_grid(project["config_dir"])
    out = plan.output_dir

    def killed(plan_, run, timeout, log):  # what a timeout kill leaves behind
        dead = _dead_pid()
        (out / f"{run['run_id']}.lock").write_text(
            json.dumps({"pid": dead, "host": socket.gethostname(), "created_at": "x",
                        "purpose": "t"}), encoding="utf-8")  # fmt: skip
        (out / f"{run['run_id']}.staging-{dead}").mkdir()
        return run_safety.LaunchOutcome(None, True, float(timeout))

    summary = grid.run_grid(plan, launcher=killed)
    assert summary["failed"] == 1 and "timeout after 900 s" in summary["stopped"]
    attempt = json.loads(plan.manifest_path.read_text(encoding="utf-8"))["runs"][0]["attempts"][0]
    assert [a["action"] for a in attempt["recovery"]] == ["quarantined"]
    assert not list(out.glob("*.lock")) and not list(out.glob("*.staging-*"))
    assert len(list((out / run_safety.QUARANTINE_DIR).iterdir())) == 1


def test_stale_runner_lock_marks_interrupted_runs_failed(project: dict) -> None:
    plan = grid.plan_grid(project["config_dir"])
    calls: list = []
    grid.run_grid(plan, launcher=_ok_launcher(project, calls), max_runs=1)
    manifest = json.loads(plan.manifest_path.read_text(encoding="utf-8"))
    manifest["runs"][1]["status"] = "running"  # a runner died mid-run
    manifest["runs"][1]["attempts"].append({"attempt": 1, "started_at": "x"})
    grid.save_manifest(plan.manifest_path, manifest)
    (plan.grid_dir / "runner.lock").write_text(
        json.dumps({"pid": _dead_pid(), "host": socket.gethostname(), "created_at": "x",
                    "purpose": "t"}), encoding="utf-8")  # fmt: skip
    with pytest.raises(grid.GridError, match="--retry-failed"):
        grid.run_grid(plan, launcher=_ok_launcher(project, calls))
    manifest = json.loads(plan.manifest_path.read_text(encoding="utf-8"))
    assert manifest["runs"][1]["status"] == "failed"
    assert manifest["runs"][1]["attempts"][-1]["outcome"] == "interrupted"
    events = [e["event"] for e in manifest["events"]]
    assert "stale_runner_lock_recovered" in events and "interrupted_run_marked_failed" in events
    (plan.grid_dir / "runner.lock").write_text(
        json.dumps({"pid": os.getpid(), "host": socket.gethostname(), "created_at": "x",
                    "purpose": "t"}), encoding="utf-8")  # fmt: skip
    with pytest.raises(grid.GridError, match="another grid runner"):  # a live runner
        grid.run_grid(plan, launcher=_ok_launcher(project, calls), retry_failed=True)


def test_invalid_existing_run_directory_stops_the_grid_untouched(project: dict) -> None:
    plan = grid.plan_grid(project["config_dir"])
    broken = plan.output_dir / plan.runs[2]["run_id"]
    broken.mkdir(parents=True)
    (broken / "model.zip").write_bytes(b"partial")
    with pytest.raises(grid.GridError, match="fails verification"):
        grid.run_grid(plan, launcher=_ok_launcher(project, []))
    assert [p.name for p in broken.iterdir()] == ["model.zip"]


def test_grid_refuses_uncommitted_code_and_default_launcher_command(
    project: dict, monkeypatch
) -> None:
    plan = grid.plan_grid(project["config_dir"])
    seen = {}

    def capture(command, timeout, log, env=None):
        seen.update(command=command, timeout=timeout, env=env)
        return run_safety.LaunchOutcome(0, False, 0.0)

    monkeypatch.setattr(run_safety, "run_with_timeout", capture)
    grid.default_launcher(plan, plan.runs[7], 900, Path("log"))
    assert seen["command"][1:3] == ["-m", "adaptive_portfolio.agents.ppo"]
    assert seen["command"][-4:] == ["--configuration", "1", "--seed", "44"]
    assert seen["timeout"] == 900 and seen["env"]["PYTHONHASHSEED"] == "0"
    (project["root"] / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    dirty = grid.plan_grid(project["config_dir"])
    with pytest.raises(grid.GridError, match="clean, committed"):
        grid.run_grid(dirty, launcher=_ok_launcher(project, []))
    assert grid.main(["--config-dir", str(project["config_dir"]), "--execute"]) == 2
