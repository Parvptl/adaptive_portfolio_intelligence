"""Sequential runner for the D-066 PPO grid with a resumable manifest (D-075; ``rl`` extra).

The grid is the 40 ``full`` runs of ``configs/agent.yaml`` (8 configurations x 5 seeds). Its
state lives in ``<agent.output_dir>/grids/<grid_id>/manifest.json`` (written atomically):
every configuration and seed with its expected ``run_id``, status (``pending``, ``running``,
``completed``, ``failed``) and every attempt (times, outcome, log file). ``grid_id`` hashes the
agent settings, the Git commit and the training data, so a resumed grid always continues
with the same code and data.

Execution policy (``agent.execution``):
- **sequential** only: one run at a time, guarded by ``runner.lock``;
- each run is a child process (``python -m adaptive_portfolio.agents.ppo``) killed after
  ``run_timeout_seconds``; a kill is a hard termination, so stale locks and staging
  directories are recovered (quarantined, never deleted) right after it;
- **stop on the first failure** (non-zero exit, timeout, or an output that fails
  verification); failed and interrupted runs are retried only with ``retry_failed=True``;
- resuming adopts completed run directories that verify, refuses directories that do not
  (they are left for a human), and never re-runs or replaces a completed run.

Only training-split data are loaded (``make_training_env``). Nothing here evaluates a policy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adaptive_portfolio.agents import ppo, run_safety
from adaptive_portfolio.config import (
    AgentConfig,
    load_agent_config,
    load_backtest_config,
    load_project_config,
)
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import project_root_for, resolve_path
from adaptive_portfolio.environment.portfolio_env import make_training_env
from adaptive_portfolio.features.pipeline import locate_dataset_dir

GRID_SCHEMA_VERSION = 1
STATUSES = ("pending", "running", "completed", "failed")


class GridError(RuntimeError):
    """Raised when the grid cannot proceed safely; the manifest records why."""


@dataclass(frozen=True)
class GridPlan:
    config_dir: Path
    project_root: Path
    dataset_dir: Path
    feature_dir: Path
    agent: AgentConfig
    code: dict[str, Any]
    grid_id: str
    runs: tuple[dict[str, Any], ...]  # spec fields plus expected run_id

    @property
    def output_dir(self) -> Path:
        return resolve_path(self.agent.output_dir, self.project_root)

    @property
    def grid_dir(self) -> Path:
        return self.output_dir / "grids" / self.grid_id

    @property
    def manifest_path(self) -> Path:
        return self.grid_dir / "manifest.json"


def plan_grid(
    config_dir: Path, dataset_dir: Path | None = None, feature_dir: Path | None = None
) -> GridPlan:
    """Expected run ids and grid identity for the current code and data (writes nothing)."""
    config_dir = Path(config_dir)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    agent = load_agent_config(config_dir / "agent.yaml")
    root = project_root_for(config_dir)
    dataset_dir = Path(dataset_dir or locate_dataset_dir(config, root))
    feature_dir = Path(feature_dir or ppo._default_feature_dir(config_dir, root, dataset_dir))
    code = run_safety.code_provenance(root)
    env = make_training_env(config, backtest, dataset_dir, feature_dir)
    runs = []
    for spec in agent.run_specs():
        identity = ppo.run_identity(
            env, agent, spec, total_timesteps=agent.total_timesteps, run_kind="full", code=code
        )
        runs.append({**spec.to_dict(), "run_id": cache.short_hash(identity)})
    identity = {
        "schema_version": GRID_SCHEMA_VERSION,
        "pipeline_version": ppo.PPO_PIPELINE_VERSION,
        "agent": {
            "seeds": list(agent.seeds),
            "learning_rates": list(agent.learning_rates),
            "n_steps": list(agent.n_steps),
            "ent_coefs": list(agent.ent_coefs),
            "total_timesteps": agent.total_timesteps,
            "fixed": agent.fixed_hyperparameters(),
        },
        "code_commit": code.get("commit"),
        "data": env.provenance,
    }
    return GridPlan(
        config_dir,
        root,
        dataset_dir,
        feature_dir,
        agent,
        code,
        cache.short_hash(identity),
        tuple(runs),
    )


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Atomic write: a temporary file in the same directory, then ``os.replace``."""
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _event(manifest: dict[str, Any], kind: str, **details: Any) -> None:
    manifest["events"].append({"at": run_safety.utc_now(), "event": kind, **details})


def load_or_create_manifest(plan: GridPlan) -> dict[str, Any]:
    if plan.manifest_path.is_file():
        manifest = json.loads(plan.manifest_path.read_text(encoding="utf-8"))
        expected = [(r["configuration"], r["seed"], r["run_id"]) for r in plan.runs]
        found = [(r["configuration"], r["seed"], r["run_id"]) for r in manifest["runs"]]
        if manifest.get("grid_id") != plan.grid_id or found != expected:
            raise GridError(f"{plan.manifest_path} does not match the planned grid")
        return manifest
    agent = plan.agent
    return {
        "schema_version": GRID_SCHEMA_VERSION,
        "grid_id": plan.grid_id,
        "created_at": run_safety.utc_now(),
        "code": plan.code,
        "data_dirs": {"dataset": str(plan.dataset_dir), "features": str(plan.feature_dir)},
        "execution": {
            "mode": agent.execution_mode,
            "on_failure": agent.on_failure,
            "run_timeout_seconds": agent.run_timeout_seconds,
        },
        "runs": [{**run, "status": "pending", "attempts": []} for run in plan.runs],
        "events": [],
    }


def default_launcher(
    plan: GridPlan, run: dict[str, Any], timeout_seconds: float, log_path: Path
) -> run_safety.LaunchOutcome:
    """Run one full grid run in a child process (fresh interpreter, ``PYTHONHASHSEED=0``)."""
    command = [
        sys.executable,
        "-m",
        "adaptive_portfolio.agents.ppo",
        "--config-dir",
        str(plan.config_dir),
        "--dataset-dir",
        str(plan.dataset_dir),
        "--feature-dir",
        str(plan.feature_dir),
        "--configuration",
        str(run["configuration"]),
        "--seed",
        str(run["seed"]),
    ]
    environment = {**os.environ, "PYTHONHASHSEED": "0"}
    return run_safety.run_with_timeout(command, timeout_seconds, log_path, env=environment)


def _acquire_runner_lock(plan: GridPlan, manifest_holder: list) -> dict[str, Any]:
    lock_path = plan.grid_dir / "runner.lock"
    try:
        return run_safety.acquire_lock(lock_path, f"grid runner {plan.grid_id}")
    except run_safety.LockHeldError as exc:
        if exc.state != "stale":
            raise GridError(
                f"another grid runner holds {lock_path} ({exc.state}): {exc.info}"
            ) from None
        event = run_safety.quarantine(
            plan.output_dir,
            [lock_path],
            f"grid-{plan.grid_id}-runner",
            f"stale grid runner lock: owner {exc.info} is no longer running",
        )
        manifest_holder.append({"quarantined_runner_lock": str(event), "owner": exc.info})
        return run_safety.acquire_lock(lock_path, f"grid runner {plan.grid_id}")


def _reconcile(plan: GridPlan, manifest: dict[str, Any]) -> None:
    """Bring the manifest in line with the run directories on disk (never touches them)."""
    for run in manifest["runs"]:
        directory = plan.output_dir / run["run_id"]
        if run["status"] == "running":  # the previous runner ended without recording
            run["status"] = "failed"
            if run["attempts"]:
                run["attempts"][-1].update(outcome="interrupted", finished_at=run_safety.utc_now())
            _event(manifest, "interrupted_run_marked_failed", run_id=run["run_id"])
        if directory.exists():
            problems = run_safety.verify_run_dir(
                directory, run["run_id"], plan.agent.total_timesteps
            )
            if problems:
                raise GridError(
                    f"run directory {directory} exists but fails verification {problems}; it is "
                    "left untouched for manual inspection"
                )
            if run["status"] != "completed":
                _event(manifest, "completed_run_adopted", run_id=run["run_id"], was=run["status"])
                run["status"] = "completed"
        elif run["status"] == "completed":
            raise GridError(
                f"manifest says {run['run_id']} is completed but {directory} is missing"
            )


def run_grid(
    plan: GridPlan,
    *,
    launcher: Any = default_launcher,
    retry_failed: bool = False,
    max_runs: int | None = None,
) -> dict[str, Any]:
    """Run the pending grid runs sequentially; returns a summary. Stops at the first failure."""
    agent = plan.agent
    if agent.execution_mode != "sequential" or agent.on_failure != "stop":
        raise GridError("only sequential execution with stop-on-failure is approved (D-075)")
    try:
        run_safety.check_code_policy(plan.code, "full")
    except run_safety.RunSafetyError as exc:
        raise GridError(str(exc)) from None
    plan.grid_dir.mkdir(parents=True, exist_ok=True)
    notes: list[dict[str, Any]] = []
    lock = _acquire_runner_lock(plan, notes)
    try:
        manifest = load_or_create_manifest(plan)
        for note in notes:
            _event(manifest, "stale_runner_lock_recovered", **note)
        recovered = run_safety.recover_stale(plan.output_dir)
        if any(a["action"] == "quarantined" for a in recovered):
            _event(manifest, "stale_run_state_recovered", actions=recovered)
        try:
            _reconcile(plan, manifest)
        finally:
            save_manifest(plan.manifest_path, manifest)
        failed = [r["run_id"] for r in manifest["runs"] if r["status"] == "failed"]
        if failed and not retry_failed:
            raise GridError(
                f"failed or interrupted runs {failed} must be reviewed first; rerun with "
                "--retry-failed to retry them"
            )
        launched, stopped = 0, None
        for run in manifest["runs"]:
            if run["status"] == "completed":
                continue
            if max_runs is not None and launched >= max_runs:
                stopped = f"max_runs={max_runs} reached"
                break
            number = len(run["attempts"]) + 1
            log = plan.grid_dir / "logs" / f"c{run['configuration']}-s{run['seed']}-a{number}.log"
            attempt = {
                "attempt": number,
                "started_at": run_safety.utc_now(),
                "runner_pid": os.getpid(),
                "log": str(log),
            }
            run["attempts"].append(attempt)
            run["status"] = "running"
            save_manifest(plan.manifest_path, manifest)
            try:
                outcome = launcher(plan, run, agent.run_timeout_seconds, log)
            except BaseException as exc:
                attempt.update(
                    outcome="interrupted",
                    reason=f"{type(exc).__name__}: {exc}",
                    finished_at=run_safety.utc_now(),
                )
                run["status"] = "failed"
                _event(
                    manifest,
                    "runner_interrupted",
                    run_id=run["run_id"],
                    recovery=run_safety.recover_stale(plan.output_dir),
                )
                save_manifest(plan.manifest_path, manifest)
                raise
            launched += 1
            attempt.update(
                finished_at=run_safety.utc_now(),
                seconds=outcome.seconds,
                returncode=outcome.returncode,
                timed_out=outcome.timed_out,
            )
            if outcome.timed_out or outcome.returncode != 0:
                reason = (
                    f"timeout after {agent.run_timeout_seconds} s (child killed)"
                    if outcome.timed_out
                    else f"exit code {outcome.returncode}"
                )
                attempt["recovery"] = run_safety.recover_stale(plan.output_dir)
            else:
                problems = run_safety.verify_run_dir(
                    plan.output_dir / run["run_id"], run["run_id"], agent.total_timesteps
                )
                reason = f"verification failed: {problems}" if problems else None
            if reason is None:
                attempt["outcome"] = "completed"
                run["status"] = "completed"
            else:
                attempt.update(outcome="failed", reason=reason)
                run["status"] = "failed"
                stopped = f"stopped after failure of {run['run_id']}: {reason}"
            save_manifest(plan.manifest_path, manifest)
            if stopped:
                break
        _event(manifest, "runner_finished", launched=launched, stopped=stopped)
        save_manifest(plan.manifest_path, manifest)
        return summarise(manifest) | {"launched": launched, "stopped": stopped}
    finally:
        run_safety.release_lock(plan.grid_dir / "runner.lock", lock)


def summarise(manifest: dict[str, Any]) -> dict[str, Any]:
    counts = {status: 0 for status in STATUSES}
    for run in manifest["runs"]:
        counts[run["status"]] += 1
    return {"grid_id": manifest["grid_id"], "runs": len(manifest["runs"]), **counts}


# --------------------------------------------------------------------------
# Command line: python scripts/run_grid.py
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan, inspect, recover or run the PPO grid.")
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--feature-dir", type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true", help="show the plan; writes nothing")
    action.add_argument("--status", action="store_true", help="show the manifest; read-only")
    action.add_argument("--recover", action="store_true", help="quarantine stale run state")
    action.add_argument("--execute", action="store_true", help="run pending runs (training!)")
    parser.add_argument(
        "--confirm-full-grid",
        action="store_true",
        help="required with --execute: confirms the grid run is approved",
    )
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--max-runs", type=int)
    args = parser.parse_args(argv)
    if args.recover:
        agent = load_agent_config(args.config_dir / "agent.yaml")
        output = resolve_path(agent.output_dir, project_root_for(args.config_dir))
        for action_taken in run_safety.recover_stale(output):
            print(action_taken)
        return 0
    plan = plan_grid(args.config_dir, args.dataset_dir, args.feature_dir)
    try:
        run_safety.check_code_policy(plan.code, "full")
        verdict = "allowed"
    except run_safety.RunSafetyError:
        verdict = "REFUSED (uncommitted code: commit first)"
    if args.plan or args.status:
        manifest = (
            json.loads(plan.manifest_path.read_text(encoding="utf-8"))
            if plan.manifest_path.is_file()
            else None
        )
        statuses = {r["run_id"]: r["status"] for r in manifest["runs"]} if manifest else {}
        print(
            f"grid {plan.grid_id}: {len(plan.runs)} runs, {plan.agent.total_timesteps} timesteps "
            f"each; code commit {plan.code.get('commit')}, dirty {plan.code.get('dirty')} -> "
            f"execution {verdict}"
        )
        print(f"  manifest: {plan.manifest_path} ({'exists' if manifest else 'not created'})")
        print(
            f"  execution: {plan.agent.execution_mode}, timeout "
            f"{plan.agent.run_timeout_seconds} s per run, on failure {plan.agent.on_failure}"
        )
        for run in plan.runs:
            status = statuses.get(run["run_id"], "pending")
            print(f"  c{run['configuration']} s{run['seed']} {run['run_id']} {status}")
        return 0
    if not args.confirm_full_grid:
        print(
            "--execute needs --confirm-full-grid (explicit approval of the grid run)",
            file=sys.stderr,
        )
        return 2
    summary = run_grid(plan, retry_failed=args.retry_failed, max_runs=args.max_runs)
    print(summary)
    return 0 if summary["failed"] == 0 else 1
