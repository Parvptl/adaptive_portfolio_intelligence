"""PPO training wrapper (milestone 5.3; needs the ``rl`` extra).

One run = one grid configuration and one seed (D-066), trained with Stable-Baselines3 PPO on the
**training split only** (:func:`make_training_env` loads with ``train_only=True``). Nothing here
loads validation or test data, evaluates a policy or selects a configuration.

Outputs (D-069): ``<agent.output_dir>/<run_id>/``, written to a staging directory and moved into
place only when complete:

* ``run_config.json`` - the run identity (hashed into ``run_id``): grid values and seed, pinned
  hyperparameters, budget and run kind, environment and cost settings, data provenance
  (dataset and feature-set ids, SHA-256 of the training lines read), the frozen scaler, and
  package versions;
* ``metadata.json``   - the identity plus timestamps, wall time, timesteps done, episodes,
  throughput and output-file hashes;
* ``scaler.json``     - the feature scaler fitted on training rows (D-062);
* ``model.zip``       - the final checkpoint (no early stopping, no intermediate checkpoints);
* ``monitor.csv``     - per-episode training reward sums and lengths (training split).

``run_kind`` is ``"full"`` for the configured budget or ``"smoke"`` for a reduced budget used
only to measure throughput; it is part of the identity, so the two never share an id.

Safety (D-075, see :mod:`adaptive_portfolio.agents.run_safety`): the identity includes the Git
commit and working-tree state, and ``full`` runs refuse uncommitted code; each run holds an
exclusive ``<run_id>.lock``; a completed run is finalised only if its directory does not exist
(never replaced); a failed run's staging directory is quarantined, not deleted. Determinism:
one torch thread, ``torch.use_deterministic_algorithms(True)`` during training, seeded SB3.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor

from adaptive_portfolio.agents import run_safety
from adaptive_portfolio.config import (
    AgentConfig,
    BacktestConfig,
    PPORunSpec,
    ProjectConfig,
    load_agent_config,
    load_backtest_config,
    load_feature_config,
    load_project_config,
)
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import project_root_for, resolve_path
from adaptive_portfolio.environment.actions import ACTION_SCALE
from adaptive_portfolio.environment.portfolio_env import PortfolioEnv, make_training_env
from adaptive_portfolio.environment.rewards import DECISION_SCHEDULE
from adaptive_portfolio.features.pipeline import feature_output_dir, locate_dataset_dir

PPO_PIPELINE_VERSION = "1"
RUN_KINDS = ("full", "smoke")
RUN_FILES = run_safety.RUN_FILES
# Determinism settings applied to every run and recorded in its identity (D-075).
DETERMINISM: dict[str, Any] = {
    "torch_use_deterministic_algorithms": True,
    "torch_num_threads": "agent.torch_num_threads",
    "seeding": "Stable-Baselines3 seed= (Python, NumPy, torch, action space)",
    "environment_reset": "deterministic (fixed start, no random offsets)",
    "child_process_PYTHONHASHSEED": "0 (grid runner)",
    "cross_machine_bitwise_reproducibility": "not guaranteed",
}
ACTIVATIONS = {"tanh": torch.nn.Tanh, "relu": torch.nn.ReLU}
# Stable-Baselines3 settings not in agent.yaml, pinned to their 2.9 defaults (D-074).
SB3_CONSTANTS: dict[str, Any] = {
    "normalize_advantage": True,
    "clip_range_vf": None,
    "use_sde": False,
    "target_kl": None,
    "ortho_init": True,
    "share_features_extractor": True,
    "n_envs": 1,
}
VERSIONED_PACKAGES = (
    "numpy", "pandas", "PyYAML", "gymnasium", "stable_baselines3", "torch",
    "adaptive-portfolio-intelligence",
)  # fmt: skip


class TrainingError(ValueError):
    """Raised for an invalid training request or an existing run directory."""


@dataclass(frozen=True)
class TrainingRunResult:
    run_id: str
    output_dir: Path
    metadata: dict[str, Any]


def package_versions() -> dict[str, str]:
    """Interpreter, platform and package versions recorded with every run."""
    versions = {"python": platform.python_version(), "platform": platform.platform()}
    versions.update({name: version(name) for name in VERSIONED_PACKAGES})
    versions["torch_cuda_build"] = str(torch.version.cuda)
    return versions


def run_identity(
    env: PortfolioEnv,
    agent: AgentConfig,
    spec: PPORunSpec,
    *,
    total_timesteps: int,
    run_kind: str,
    code: dict[str, Any],
) -> dict[str, Any]:
    """Everything that defines a training run (hashed into its id), including the code state."""
    code_identity = {k: code.get(k) for k in ("git_available", "commit", "dirty", "diff_sha256")}
    if run_kind not in RUN_KINDS:
        raise TrainingError(f"run_kind must be one of {RUN_KINDS}, got {run_kind!r}")
    if run_kind == "full" and total_timesteps != agent.total_timesteps:
        raise TrainingError(
            f"a full run uses the configured budget {agent.total_timesteps}; a reduced budget "
            f"({total_timesteps}) is a smoke run"
        )
    if run_kind == "smoke" and total_timesteps >= agent.total_timesteps:
        raise TrainingError("a smoke run must use fewer timesteps than the configured budget")
    if spec not in agent.run_specs():
        raise TrainingError(f"{spec} is not one of the configured grid runs")
    settings = env.settings
    return {
        "pipeline_version": PPO_PIPELINE_VERSION,
        "run_kind": run_kind,
        "split": env.split,
        "run": spec.to_dict(),
        "total_timesteps": total_timesteps,
        "hyperparameters": agent.fixed_hyperparameters(),
        "sb3_constants": SB3_CONSTANTS,
        "environment": {
            "decision_schedule": DECISION_SCHEDULE,
            "execution_lag_sessions": env.lag,
            "first_decision_date": env.dates[env.first_decision].date().isoformat(),
            "last_row_date": env.dates[env.last_row].date().isoformat(),
            "steps_per_episode": env.n_steps,
            "observation_size": int(env.observation_space.shape[0]),
            "action_space": [float(env.action_space.low.min()), float(env.action_space.high.max())],
            "action_scale": ACTION_SCALE,
            "initial_capital": settings.initial_capital,
            "cost_rate": settings.cost_rate,
            "cash_return": settings.cash_return,
            "charge_initial_funding": settings.charge_initial_funding,
            "max_weight": settings.constraints.max_weight,
        },
        "data": env.provenance,
        "scaler": env.scaler.to_dict(),
        "versions": package_versions(),
        "code": code_identity,
        "determinism": DETERMINISM,
    }


def run_output_dir(agent: AgentConfig, identity: dict[str, Any], project_root: Path) -> Path:
    return resolve_path(agent.output_dir, project_root) / cache.short_hash(identity)


def build_model(env: Any, agent: AgentConfig, spec: PPORunSpec) -> PPO:
    """An untrained PPO model with every hyperparameter set explicitly."""
    layers = list(agent.net_arch)
    return PPO(
        agent.policy,
        env,
        learning_rate=spec.learning_rate,
        n_steps=spec.n_steps,
        batch_size=agent.batch_size,
        n_epochs=agent.n_epochs,
        gamma=agent.gamma,
        gae_lambda=agent.gae_lambda,
        clip_range=agent.clip_range,
        clip_range_vf=SB3_CONSTANTS["clip_range_vf"],
        normalize_advantage=SB3_CONSTANTS["normalize_advantage"],
        ent_coef=spec.ent_coef,
        vf_coef=agent.vf_coef,
        max_grad_norm=agent.max_grad_norm,
        use_sde=SB3_CONSTANTS["use_sde"],
        target_kl=SB3_CONSTANTS["target_kl"],
        policy_kwargs={
            "net_arch": {"pi": layers, "vf": layers},
            "activation_fn": ACTIVATIONS[agent.activation],
            "log_std_init": agent.log_std_init,
            "ortho_init": SB3_CONSTANTS["ortho_init"],
            "share_features_extractor": SB3_CONSTANTS["share_features_extractor"],
        },
        seed=spec.seed,
        device=agent.device,
        verbose=0,
    )


def write_run_outputs(
    directory: Path, model: PPO, env: PortfolioEnv, identity: dict[str, Any], details: dict
) -> dict[str, Any]:
    """Write the checkpoint, scaler, identity and metadata into ``directory``."""
    model.save(directory / "model.zip")
    env.scaler.save(directory / "scaler.json")
    cache.write_json(identity, directory / "run_config.json")
    metadata = {
        "run_id": cache.short_hash(identity),
        **identity,
        **details,
        "files_sha256": {
            name: cache.file_sha256(directory / name)
            for name in ("model.zip", "scaler.json", "run_config.json")
        },
        "note": (
            "Training split only: no validation or test rows were loaded. This run is not "
            "evaluated and is not a result."
        ),
    }
    cache.write_json(metadata, directory / "metadata.json")
    return metadata


def train_ppo_run(
    config: ProjectConfig,
    backtest: BacktestConfig,
    agent: AgentConfig,
    spec: PPORunSpec,
    project_root: Path,
    dataset_dir: Path,
    feature_dir: Path,
    *,
    total_timesteps: int | None = None,
    run_kind: str = "full",
    model_factory: Callable[[Any, AgentConfig, PPORunSpec], Any] = build_model,
) -> TrainingRunResult:
    """Train one PPO run on the training split and write its outputs.

    Refuses: ``full`` runs from uncommitted code; an existing run directory; a run whose lock
    is held (if the holder is gone, run recovery first). ``model_factory`` exists so tests can
    use a stub model; production code always uses :func:`build_model`.
    """
    budget = agent.total_timesteps if total_timesteps is None else total_timesteps
    code = run_safety.code_provenance(project_root)
    try:
        run_safety.check_code_policy(code, run_kind)
    except run_safety.RunSafetyError as exc:
        raise TrainingError(str(exc)) from None
    env = make_training_env(config, backtest, dataset_dir, feature_dir)
    identity = run_identity(env, agent, spec, total_timesteps=budget, run_kind=run_kind, code=code)
    target = run_output_dir(agent, identity, project_root)
    output_dir, run_id = target.parent, target.name
    if target.exists():
        raise TrainingError(f"run directory {target} already exists; it is never overwritten")
    lock_path = output_dir / f"{run_id}{run_safety.LOCK_SUFFIX}"
    try:
        lock = run_safety.acquire_lock(lock_path, f"training run {run_id}")
    except run_safety.LockHeldError as exc:
        raise TrainingError(
            f"run {run_id} is locked ({exc.state}) by {exc.info}; if its owner is gone, recover "
            "first: python scripts/run_grid.py --recover"
        ) from None
    try:
        if target.exists():  # re-check while holding the lock
            raise TrainingError(f"run directory {target} already exists; it is never overwritten")
        staging = output_dir / f"{run_id}{run_safety.STAGING_MARK}{os.getpid()}"
        staging.mkdir()
        threads = torch.get_num_threads()
        deterministic = torch.are_deterministic_algorithms_enabled()
        monitored = Monitor(env, filename=str(staging / "monitor.csv"))
        try:
            torch.set_num_threads(agent.torch_num_threads)
            torch.use_deterministic_algorithms(True)
            model = model_factory(monitored, agent, spec)
            started = dt.datetime.now(dt.UTC)
            clock = time.perf_counter()
            model.learn(total_timesteps=budget, progress_bar=False)
            seconds = time.perf_counter() - clock
            details = {
                "status": "completed",
                "started_at": started.isoformat(timespec="seconds"),
                "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                "wall_seconds": round(seconds, 3),
                "timesteps_done": int(model.num_timesteps),
                "env_steps_per_second": round(model.num_timesteps / max(seconds, 1e-9), 1),
                "episodes_completed": len(monitored.get_episode_rewards()),
                "code_changed_paths": code.get("changed_paths"),
            }
            monitored.close()
            metadata = write_run_outputs(staging, model, env, identity, details)
            try:
                run_safety.finalise_exclusive(staging, target)
            except (run_safety.RunSafetyError, OSError) as exc:
                raise TrainingError(f"could not finalise {target} safely: {exc}") from exc
        except BaseException as exc:
            monitored.close()
            run_safety.quarantine(
                output_dir, [staging], run_id, f"run failed: {type(exc).__name__}: {exc}"
            )
            raise
        finally:
            torch.set_num_threads(threads)
            torch.use_deterministic_algorithms(deterministic)
    finally:
        run_safety.release_lock(lock_path, lock)
    return TrainingRunResult(run_id=run_id, output_dir=target, metadata=metadata)


# --------------------------------------------------------------------------
# Command line: python scripts/train_ppo.py
# --------------------------------------------------------------------------


def _default_feature_dir(config_dir: Path, root: Path, dataset_dir: Path) -> Path:
    """The train-calibrated feature set built from ``dataset_dir`` with ``features.yaml``."""
    metadata = json.loads((dataset_dir / "metadata.json").read_text(encoding="utf-8"))
    features = load_feature_config(config_dir / "features.yaml")
    feature_dir, _ = feature_output_dir(features, root, metadata["processed_dataset_id"], None)
    return feature_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train one PPO run on the training split (D-066 grid), or inspect it."
    )
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--feature-dir", type=Path)
    parser.add_argument("--list", action="store_true", help="list the grid runs and exit")
    parser.add_argument("--configuration", type=int, help="grid configuration index")
    parser.add_argument("--seed", type=int, help="one of the configured seeds")
    parser.add_argument("--timesteps", type=int, help="reduced budget; requires --smoke")
    parser.add_argument("--smoke", action="store_true", help="throughput smoke run")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build the environment and the untrained model, print the plan; no training",
    )
    args = parser.parse_args(argv)
    config_dir = args.config_dir
    agent = load_agent_config(config_dir / "agent.yaml")
    specs = agent.run_specs()
    if args.list:
        for spec in specs:
            print(spec.to_dict())
        return 0
    chosen = [s for s in specs if (s.configuration, s.seed) == (args.configuration, args.seed)]
    if not chosen:
        print("choose a configured --configuration and --seed (see --list)", file=sys.stderr)
        return 2
    if (args.timesteps is not None) != args.smoke:
        print("--timesteps and --smoke must be given together", file=sys.stderr)
        return 2
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    root = project_root_for(config_dir)
    dataset_dir = args.dataset_dir or locate_dataset_dir(config, root)
    feature_dir = args.feature_dir or _default_feature_dir(config_dir, root, dataset_dir)
    kind = "smoke" if args.smoke else "full"
    budget = args.timesteps if args.smoke else agent.total_timesteps
    if args.dry_run:
        code = run_safety.code_provenance(root)
        env = make_training_env(config, backtest, dataset_dir, feature_dir)
        identity = run_identity(
            env, agent, chosen[0], total_timesteps=budget, run_kind=kind, code=code
        )
        try:
            run_safety.check_code_policy(code, kind)
            policy = "allowed"
        except run_safety.RunSafetyError:
            policy = "REFUSED: full runs need a clean committed tree"
        model = build_model(env, agent, chosen[0])
        parameters = sum(p.numel() for p in model.policy.parameters())
        print(f"DRY RUN (no training, nothing written): {chosen[0].to_dict()}")
        print(f"  run kind {kind}, {budget} timesteps, {env.n_steps} steps per episode")
        print(f"  data: {env.provenance['first_date']} .. {env.provenance['last_date']} (train)")
        print(f"  policy parameters: {parameters}")
        print(f"  code: commit {code['commit']}, dirty {code['dirty']} -> {kind} run {policy}")
        print(f"  output: {run_output_dir(agent, identity, root)}")
        return 0
    result = train_ppo_run(
        config, backtest, agent, chosen[0], root, dataset_dir, feature_dir,
        total_timesteps=budget, run_kind=kind,
    )  # fmt: skip
    m = result.metadata
    print(f"run {result.run_id} ({kind}): {m['timesteps_done']} timesteps in {m['wall_seconds']} s")
    print(f"  {m['env_steps_per_second']} env steps/s; outputs in {result.output_dir}")
    return 0


if __name__ == "__main__":  # the grid runner calls: python -m adaptive_portfolio.agents.ppo
    raise SystemExit(main())
