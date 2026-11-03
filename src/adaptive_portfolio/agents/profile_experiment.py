"""Profile-conditioned PPO experiment: training arms and evaluation E0-E3 (D-085; ``rl`` extra).

Design (``configs/profile_experiment.yaml``; ``docs/profile_conditioned_ppo.md``):

* **E0, existing PPO:** the configuration-4 checkpoints of the EXP-005 grid (51 inputs), verified
  by :func:`adaptive_portfolio.agents.evaluate.discover_checkpoints`, re-evaluated in the same run
  under identical conditions. They are not retrained.
* **E1, profile-conditioned PPO (arm ``main``):** configuration 4's settings, seeds and budget;
  one Uniform(0, 1)^5 profile per training episode, appended to the observation (56 inputs).
* **E2, profile intervention (no retraining):** on the trajectory each ``main`` policy produced
  with profile ``u``, the decided targets are recomputed with the profile input replaced by the
  neutral profile or by another profile of the set (a deterministic derangement). Because the
  profiles are synthetic, an on-path "shuffled" episode would only relabel another profile's
  episode, so the intervention is state-matched.
* **E3, unseen profile combinations (arm ``heldout``):** trained without the excluded joint box
  (risk tolerance >= 0.6 and risk capacity <= 0.4) and evaluated inside and outside it. The
  training and validation splits are both evaluated, so **unseen profiles** and **unseen market
  periods** are reported separately.
* **E4, a profile-sensitive reward, is not implemented** (future work).

Rules: the reward, actions, accounting, costs, features, regimes and splits are the existing
ones; the test split is never loaded (bounded loaders, explicit row checks); outputs are written
once under their own roots; deterministic actions; descriptive statistics only. ``--execute``
on validation needs ``full`` runs from one clean commit and a clean committed tree. A
``--pipeline-check`` (training split only) accepts smoke runs and uncommitted code and labels
every output as not a result.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from stable_baselines3 import PPO

from adaptive_portfolio.agents import evaluate as validation
from adaptive_portfolio.agents import ppo, run_safety
from adaptive_portfolio.config import (
    AgentConfig,
    BacktestConfig,
    ConfigError,
    ProfileExperimentConfig,
    ProjectConfig,
    load_agent_config,
    load_backtest_config,
    load_evaluation_config,
    load_profile_experiment_config,
    load_project_config,
    load_workflow_config,
)
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.boundaries import (
    DataBoundaryError,
    assert_before_split,
    assert_training_only,
)
from adaptive_portfolio.data.pipeline import project_root_for, resolve_path
from adaptive_portfolio.environment.observation import FeatureScaler
from adaptive_portfolio.environment.portfolio_env import PortfolioEnv
from adaptive_portfolio.environment.profile_env import ProfileConditionedEnv
from adaptive_portfolio.environment.profiles import (
    PROFILE_DIMENSIONS,
    PROFILE_SIZE,
    neutral_profile,
    profile_set,
)
from adaptive_portfolio.evaluation.backtest import (
    _environment_dict,
    backtest_config_to_dict,
    simulation_settings,
    split_window,
    strategy_targets,
)
from adaptive_portfolio.evaluation.performance import summarize_window
from adaptive_portfolio.evaluation.simulator import simulate
from adaptive_portfolio.explainability import profile_analysis as pa
from adaptive_portfolio.explainability.sensitivity import decided_targets
from adaptive_portfolio.features.engineering import FeatureDataError
from adaptive_portfolio.features.pipeline import (
    load_feature_outputs,
    load_processed_inputs,
    locate_dataset_dir,
)

SCHEMA_VERSION = 1
CENTRE = "centre"
FIDELITY_TOLERANCE = 1e-6  # batched vs one-at-a-time float32 inference (D-080 saw ~1e-9)
OUTPUT_FILES = (
    "episode_metrics.csv", "state_matched.csv", "dimension_effects.csv", "sweeps.csv",
    "interventions.csv", "seed_scale.csv", "summary.json", "metadata.json",
)  # fmt: skip
OPTIONAL_TABLES = ("interactions", "contrasts")  # written when an interaction grid is set
STATUS = (
    "PROFILE-CONDITIONED PPO EVALUATION (D-085; details Provisional (delegated), D-086/D-087). "
    "Simulated backtest on the {split} split; descriptive only; not a test result, not evidence "
    "of personalisation or suitability (the reward does not use the profile), not financial "
    "advice."
)
PIPELINE_STATUS = (
    "PIPELINE CHECK ONLY: smoke checkpoints and/or uncommitted code on the training split. "
    "These numbers verify the code path and are NOT experimental results."
)


class ProfileExperimentError(RuntimeError):
    """Raised when training or evaluation cannot proceed exactly as specified."""


EXPECTED_FAILURES = (
    ProfileExperimentError,
    validation.EvaluationError,
    DataBoundaryError,
    FeatureDataError,
    ConfigError,
    ppo.TrainingError,
    run_safety.RunSafetyError,
)


@dataclass(frozen=True)
class Context:
    config_dir: Path
    root: Path
    config: ProjectConfig
    backtest: BacktestConfig
    agent: AgentConfig
    experiment: ProfileExperimentConfig
    dataset_dir: Path
    feature_dir: Path


def load_context(
    config_dir: Path,
    dataset_dir: Path | None = None,
    feature_dir: Path | None = None,
    experiment_path: Path | None = None,
) -> Context:
    """Configs for one profile experiment: E1 (``profile_experiment.yaml``, the default) or E4
    (``profile_reward_experiment.yaml``, passed as ``experiment_path``)."""
    config_dir = Path(config_dir)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    agent = load_agent_config(config_dir / "agent.yaml")
    experiment = load_profile_experiment_config(
        experiment_path or config_dir / "profile_experiment.yaml"
    )
    root = project_root_for(config_dir)
    dataset_dir = Path(dataset_dir or locate_dataset_dir(config, root))
    feature_dir = Path(feature_dir or ppo._default_feature_dir(config_dir, root, dataset_dir))
    specs = {(s.configuration, s.seed) for s in agent.run_specs()}
    missing = [s for s in experiment.seeds if (experiment.base_configuration, s) not in specs]
    if missing:
        raise ProfileExperimentError(f"configuration {experiment.base_configuration} seeds "
                                     f"{missing} are not agent.yaml grid runs")  # fmt: skip
    return Context(config_dir, root, config, backtest, agent, experiment, dataset_dir, feature_dir)


def run_spec(context: Context, seed: int) -> ppo.PPORunSpec:
    for spec in context.agent.run_specs():
        if (spec.configuration, spec.seed) == (context.experiment.base_configuration, seed):
            return spec
    raise ProfileExperimentError(f"no grid run for seed {seed}")


def profile_training(context: Context, arm: str) -> ppo.ProfileTraining:
    experiment = context.experiment
    if arm not in experiment.arms:
        raise ProfileExperimentError(f"unknown arm {arm!r}; expected {list(experiment.arms)}")
    return ppo.ProfileTraining(
        arm=arm,
        sampling=experiment.arms[arm],
        stream=experiment.profile_stream,
        experiment=experiment.to_dict(),
        output_dir=experiment.output_dir,
        reward=experiment.reward,
    )


# --------------------------------------------------------------------------
# Training (training split only; reuses ppo.train_ppo_run)
# --------------------------------------------------------------------------


def train_arm(
    context: Context,
    arm: str,
    seeds: Sequence[int] | None = None,
    *,
    total_timesteps: int | None = None,
    run_kind: str = "full",
) -> list[dict[str, Any]]:
    """Train the arm's runs sequentially; stop at the first failure.

    A run whose output directory already exists and verifies is skipped (resume); an existing
    directory that does not verify stops the arm (it is never replaced).
    """
    from adaptive_portfolio.environment.portfolio_env import make_training_env

    profile = profile_training(context, arm)
    budget = context.agent.total_timesteps if total_timesteps is None else total_timesteps
    results = []
    for seed in seeds or context.experiment.seeds:
        spec = run_spec(context, seed)
        code = run_safety.code_provenance(context.root)
        env = make_training_env(context.config, context.backtest, context.dataset_dir,
                                context.feature_dir)  # fmt: skip
        identity = ppo.run_identity(env, context.agent, spec, total_timesteps=budget,
                                    run_kind=run_kind, code=code, profile=profile)  # fmt: skip
        target = ppo.run_output_dir(context.agent, identity, context.root, profile.output_dir)
        if target.exists():
            problems = run_safety.verify_run_dir(target, target.name, budget)
            if problems:
                raise ProfileExperimentError(f"{target} exists but does not verify: {problems}")
            results.append({"arm": arm, "seed": seed, "run_id": target.name, "status": "existing"})
            continue
        result = ppo.train_ppo_run(
            context.config, context.backtest, context.agent, spec, context.root,
            context.dataset_dir, context.feature_dir, total_timesteps=budget,
            run_kind=run_kind, profile=profile,
        )  # fmt: skip
        m = result.metadata
        results.append({"arm": arm, "seed": seed, "run_id": result.run_id, "status": "trained",
                        "timesteps_done": m["timesteps_done"], "wall_seconds": m["wall_seconds"],
                        "episodes_completed": m["episodes_completed"]})  # fmt: skip
    return results


# --------------------------------------------------------------------------
# Checkpoint discovery and comparability (no data rows read)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfileCheckpoint:
    arm: str
    seed: int
    run_id: str
    directory: Path
    model_sha256: str
    run_kind: str
    commit: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"arm": self.arm, "seed": self.seed, "run_id": self.run_id,
                "model_sha256": self.model_sha256, "run_kind": self.run_kind,
                "commit": self.commit}  # fmt: skip


def discover_profile_checkpoints(
    context: Context, *, pipeline_check: bool, commit: str | None = None
) -> tuple[list[ProfileCheckpoint], list[dict[str, Any]]]:
    """Exactly one verified run per (arm, seed); returns checkpoints and their run configs."""
    root = resolve_path(context.experiment.output_dir, context.root)
    wanted = context.experiment.to_dict()
    found: dict[tuple[str, int], list[tuple[ProfileCheckpoint, dict]]] = {}
    for config_path in sorted(root.glob("*/run_config.json")) if root.is_dir() else []:
        directory = config_path.parent
        run = json.loads(config_path.read_text(encoding="utf-8"))
        conditioning = run.get("profile_conditioning") or {}
        kind = run.get("run_kind")
        if conditioning.get("experiment") != wanted or (kind != "full" and not pipeline_check):
            continue
        code = run.get("code") or {}
        if commit and not str(code.get("commit", "")).startswith(commit):
            continue
        key = (conditioning.get("arm"), run.get("run", {}).get("seed"))
        problems = run_safety.verify_run_dir(directory, directory.name, run["total_timesteps"])
        if cache.short_hash(run) != directory.name:
            problems.append("identity hash != run id")
        if problems:
            raise ProfileExperimentError(f"{directory}: {problems}")
        meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        checkpoint = ProfileCheckpoint(key[0], key[1], directory.name, directory,
                                       meta["files_sha256"]["model.zip"], kind,
                                       code.get("commit"))  # fmt: skip
        found.setdefault(key, []).append((checkpoint, run))
    checkpoints, configs, problems = [], [], []
    for arm in context.experiment.arms:
        for seed in context.experiment.seeds:
            matches = found.get((arm, seed), [])
            if len(matches) != 1:
                problems.append(f"{arm} seed {seed}: {len(matches)} matching runs "
                                f"{[c.run_id for c, _ in matches]}")  # fmt: skip
                continue
            checkpoints.append(matches[0][0])
            configs.append(matches[0][1])
    if problems:
        raise ProfileExperimentError(
            "profile checkpoints are missing or ambiguous (pass --commit to choose):\n  - "
            + "\n  - ".join(problems)
        )
    if not pipeline_check:
        commits = {(c.get("code") or {}).get("commit") for c in configs}
        dirty = [c["run"]["seed"] for c in configs if (c.get("code") or {}).get("dirty")]
        if len(commits) != 1 or dirty:
            raise ProfileExperimentError(f"runs must share one clean commit: {commits}, dirty "
                                         f"seeds {dirty}")  # fmt: skip
    return checkpoints, configs


def comparability(
    profile_configs: Sequence[Mapping[str, Any]],
    e0_configs: Sequence[Mapping[str, Any]],
    *,
    pipeline_check: bool,
) -> dict[str, Any]:
    """E0 vs profile runs: identical everything except the five profile inputs.

    Checks the environment block (except the observation size, which must differ by 5), PPO
    hyperparameters, SB3 constants, the frozen scaler, data identity and, for full runs, the
    budget. Raises on any difference; returns the checks for the record.
    """

    def env_without_size(run: Mapping[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in run["environment"].items() if k != "observation_size"}

    reference = e0_configs[0]
    checks: dict[str, bool] = {}
    for run in profile_configs:
        label = f"{run['profile_conditioning']['arm']} s{run['run']['seed']}"
        size = run["environment"]["observation_size"]
        checks[f"{label}: environment identical except observation size"] = env_without_size(
            run
        ) == env_without_size(reference)
        checks[f"{label}: observation size = E0 + {PROFILE_SIZE}"] = (
            size == reference["environment"]["observation_size"] + PROFILE_SIZE
        )
        checks[f"{label}: hyperparameters, SB3 constants, scaler and data identical"] = all(
            run[k] == reference[k] for k in ("hyperparameters", "sb3_constants", "scaler")
        ) and all(
            run["data"].get(k) == reference["data"].get(k)
            for k in ("processed_dataset_id", "feature_set_id", "train_prefix_sha256")
        )
        checks[f"{label}: same grid run spec as E0"] = any(
            run["run"] == e0["run"] for e0 in e0_configs
        )  # fmt: skip
        if not pipeline_check:
            checks[f"{label}: same budget as E0"] = (
                run["total_timesteps"] == reference["total_timesteps"]
            )
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ProfileExperimentError("E0 and the profile runs are not comparable:\n  - "
                                     + "\n  - ".join(failed))  # fmt: skip
    return checks


@dataclass(frozen=True)
class ProfilePlan:
    context: Context
    split: str
    pipeline_check: bool
    checkpoints: tuple[ProfileCheckpoint, ...]
    e0: tuple[validation.Checkpoint, ...]
    profile_sets: Mapping[str, np.ndarray]
    identity: dict[str, Any]
    comparability: dict[str, Any] = field(default_factory=dict)

    @property
    def evaluation_id(self) -> str:
        return cache.short_hash(self.identity)

    @property
    def output_dir(self) -> Path:
        root = resolve_path(self.context.experiment.evaluation_output_dir, self.context.root)
        return root / self.evaluation_id


def build_profile_sets(experiment: ProfileExperimentConfig) -> dict[str, np.ndarray]:
    sets = {CENTRE: neutral_profile()[None, :]}
    for name, spec in experiment.profile_sets.items():
        sampling = experiment.arms[spec.arm] if spec.arm else None
        sets[name] = profile_set(spec.count, spec.seed, spec.region, sampling)
    return sets


def plan_profile_evaluation(
    context: Context, split: str, *, pipeline_check: bool = False, commit: str | None = None
) -> ProfilePlan:
    """Verify every checkpoint and comparability, and fix the evaluation identity. No data rows."""
    if split not in context.experiment.splits:
        raise ProfileExperimentError(f"split {split!r} is not in {context.experiment.splits}")
    if pipeline_check and split != "train":
        raise ProfileExperimentError("a pipeline check runs on the training split only")
    validation._check_conventions(context.config, context.backtest)
    data_ids = validation._data_ids(context.dataset_dir, context.feature_dir)
    checkpoints, profile_configs = discover_profile_checkpoints(
        context, pipeline_check=pipeline_check, commit=commit
    )
    evaluation_cfg = load_evaluation_config(context.config_dir / "evaluation.yaml")
    experiments = resolve_path(context.agent.output_dir, context.root)
    grid, _ = validation.discover_checkpoints(
        context.agent, evaluation_cfg, experiments, data_ids,
        str(context.config.experiment.splits.validation.start),
    )  # fmt: skip
    e0 = tuple(c for c in grid if c.configuration == context.experiment.base_configuration
               and c.seed in context.experiment.seeds)  # fmt: skip
    e0_configs = [json.loads((c.directory / "run_config.json").read_text(encoding="utf-8"))
                  for c in e0]  # fmt: skip
    for run in profile_configs:
        if any(run["data"].get(k) != v for k, v in data_ids.items()):
            raise ProfileExperimentError(f"run {run['run']} was trained on other data")
    checks = comparability(profile_configs, e0_configs, pipeline_check=pipeline_check)
    sets = build_profile_sets(context.experiment)
    provenance = run_safety.code_provenance(context.root)
    code = {k: provenance.get(k) for k in ("git_available", "commit", "dirty", "diff_sha256")}
    splits = context.config.experiment.splits
    identity = {
        "schema_version": SCHEMA_VERSION,
        "split": split,
        "pipeline_check": pipeline_check,
        "experiment": context.experiment.to_dict(),
        "profile_sets": {name: values.tolist() for name, values in sets.items()},
        "checkpoints": [c.to_dict() for c in checkpoints],
        "e0_checkpoints": [c.to_dict() for c in e0],
        "data": data_ids,
        "rows_read_before": str(splits.test.start) if split == "validation"
        else str(splits.validation.start),
        "backtest": backtest_config_to_dict(context.backtest),
        "environment": _environment_dict(context.config),
        "code": code,
        "versions": ppo.package_versions(),
        "determinism": {"torch_use_deterministic_algorithms": True, "torch_num_threads": 1},
    }  # fmt: skip
    return ProfilePlan(context, split, pipeline_check, tuple(checkpoints), e0,
                       sets, identity, checks)  # fmt: skip


# --------------------------------------------------------------------------
# Episodes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Episode:
    targets: np.ndarray  # (decisions, n_assets + 1), cash last
    observations: np.ndarray  # decision observations, (decisions, observation size)
    ledger: pd.DataFrame
    executions: pd.DataFrame


def run_episode(
    model: Any,
    env: Any,
    returns: pd.DataFrame,
    window: tuple[int, int],
    settings: Any,
    lag: int,
    profile: np.ndarray | None = None,
) -> Episode:
    """One deterministic episode; the decided targets are re-simulated and must match exactly."""
    dates = returns.index
    observation, _ = env.reset(seed=0, options=None if profile is None else {"profile": profile})
    targets: dict[int, np.ndarray] = {}
    rows, observations, finished = [], [], False
    while not finished:
        observations.append(observation)
        action, _ = model.predict(observation, deterministic=True)
        observation, _, finished, truncated, info = env.step(action)
        if truncated:
            raise ProfileExperimentError("unexpected truncation")
        targets[int(dates.get_loc(info["decision_date"]))] = info["target"][:-1]
        rows.append(info["target"])
    result = simulate(returns, targets, lag=lag, window=window, settings=settings)
    own = env.unwrapped.ledger_frame()
    if not (np.array_equal(own["value"].to_numpy(), result.ledger["value"].to_numpy())
            and np.array_equal(own.filter(like="weight_").to_numpy(),
                               result.ledger.filter(like="weight_").to_numpy())):  # fmt: skip
        raise ProfileExperimentError("environment and simulator ledgers differ")
    return Episode(np.vstack(rows), np.vstack(observations), result.ledger, result.executions)


def _flatten(summary: Mapping[str, Any]) -> dict[str, Any]:
    return validation._flatten(dict(summary))


def _metrics(episode: Episode, assets, groups, settings, context: Context) -> dict[str, Any]:
    summary = summarize_window(
        episode.ledger, initial_capital=settings.initial_capital,
        annual_risk_free_rate=context.config.environment.risk_free_rate,
        periods_per_year=context.backtest.periods_per_year,
    )  # fmt: skip
    return {**_flatten(summary), "decisions": len(episode.targets),
            **pa.behaviour_metrics(episode.ledger, episode.targets, assets, groups)}  # fmt: skip


def _objective(episode: Episode, spec: Any, profile: np.ndarray, capital: float) -> dict:
    """E4 objective components of one evaluation episode, from its ledger (D-088).

    The base term is the episode's log growth (the sum of the D-064 step rewards); the penalty
    uses every ledger row's net return (the funding row included, as in training).
    """
    net = episode.ledger["net_return"].to_numpy(dtype=np.float64)
    base = float(np.log(episode.ledger["value"].iloc[-1] / capital))
    # Recurring traded notional: every execution after the funding row (row 0); E7 only.
    recurring = float(episode.ledger["traded_notional"].to_numpy(dtype=np.float64)[1:].sum())
    parts = spec.components(base, net, profile, traded_notional=recurring)
    return {f"e4_{key}": value for key, value in parts.items()}


def _profile_columns(profile: np.ndarray) -> dict[str, float]:
    return {f"profile_{name}": float(v) for name, v in zip(PROFILE_DIMENSIONS, profile,
                                                            strict=True)}  # fmt: skip


def _replace_profile(observations: np.ndarray, profile: np.ndarray) -> np.ndarray:
    out = np.array(observations, dtype=np.float32, copy=True)
    out[:, -PROFILE_SIZE:] = np.asarray(profile, dtype=np.float32)
    return out


def _policy(model: Any):
    def policy(obs: np.ndarray) -> np.ndarray:
        return model.predict(obs, deterministic=True)[0]

    return policy


# --------------------------------------------------------------------------
# Evaluation (no test rows; descriptive outputs)
# --------------------------------------------------------------------------


def _load_split(context: Context, split: str):
    config, splits = context.config, context.config.experiment.splits
    if split == "train":
        inputs = load_processed_inputs(context.dataset_dir, config, train_only=True)
        outputs = load_feature_outputs(context.feature_dir, context.dataset_dir, config,
                                       train_only=True)  # fmt: skip
        assert_training_only(inputs.asset_returns.index, inputs.split_labels, splits)
        assert_training_only(outputs.features.index, outputs.split_labels, splits)
    else:
        inputs = load_processed_inputs(context.dataset_dir, config, exclude_test=True)
        outputs = load_feature_outputs(context.feature_dir, context.dataset_dir, config,
                                       exclude_test=True)  # fmt: skip
        assert_before_split(inputs.asset_returns.index, inputs.split_labels, splits, "test",
                            "profile evaluation (returns)")  # fmt: skip
        assert_before_split(outputs.features.index, outputs.split_labels, splits, "test",
                            "profile evaluation (features)")  # fmt: skip
    multi = int((inputs.sessions_spanned > 1).sum())
    if multi and not context.backtest.allow_multi_session_returns:
        raise FeatureDataError("multi-session returns present; refused as in the backtest")
    return inputs, outputs


def evaluate_profiles(plan: ProfilePlan) -> dict[str, Any]:
    """Run E0-E3 in memory and return every table. Writes nothing."""
    context, split, experiment = plan.context, plan.split, plan.context.experiment
    if validation._data_ids(context.dataset_dir, context.feature_dir) != plan.identity["data"]:
        raise ProfileExperimentError("dataset or feature set changed since the plan")
    inputs, outputs = _load_split(context, split)
    returns, labels = inputs.asset_returns, inputs.split_labels
    assets = list(returns.columns)
    groups = experiment.exposure_groups
    settings = simulation_settings(context.config, context.backtest)
    lag, required = context.backtest.execution_lag_sessions, context.backtest.required_history
    window = split_window(labels, returns.index, split, required, lag)
    k0, x0, e = window["k0"], window["x0"], window["e"]
    if set(labels.iloc[window["s"] : e + 1]) != {split}:
        raise ProfileExperimentError(f"the window holds rows outside the {split} split")
    max_weight = context.config.environment.constraints.max_weight
    sets = plan.profile_sets

    def base_env(scaler: FeatureScaler) -> PortfolioEnv:
        env = PortfolioEnv(returns, outputs.features, outputs.regimes["regime"], labels,
                           split=split, scaler=scaler, settings=settings, lag=lag,
                           required_history=required)  # fmt: skip
        if (env.first_decision, env.first_execution, env.last_row) != (k0, x0, e):
            raise ProfileExperimentError("environment window differs from the common window")
        return env

    def load(directory: Path, sha: str, size: int) -> Any:
        if cache.file_sha256(directory / "model.zip") != sha:
            raise ProfileExperimentError(f"{directory.name}: model.zip changed since the plan")
        model = PPO.load(directory / "model.zip", device="cpu")
        if model.observation_space.shape != (size,):
            raise ProfileExperimentError(
                f"{directory.name}: observation size {model.observation_space.shape} != ({size},)"
            )
        return model

    episode_rows: list[dict[str, Any]] = []
    for strategy in context.backtest.strategies:
        targets, _ = strategy_targets(strategy, returns, k0, e, lag, max_weight)
        result = simulate(returns, targets, lag=lag, window=(x0, e), settings=settings)
        summary = summarize_window(
            result.ledger, initial_capital=settings.initial_capital,
            annual_risk_free_rate=context.config.environment.risk_free_rate,
            periods_per_year=context.backtest.periods_per_year,
        )  # fmt: skip
        episode_rows.append({"split": split, "experiment": "baseline", "arm": strategy.name,
                             "seed": None, "profile_set": None, "profile_index": None,
                             **_flatten(summary)})  # fmt: skip

    for checkpoint in plan.e0:
        scaler = FeatureScaler.load(checkpoint.directory / "scaler.json")
        env = base_env(scaler)
        model = load(
            checkpoint.directory, checkpoint.model_sha256, int(env.observation_space.shape[0])
        )
        episode = run_episode(model, env, returns, (x0, e), settings, lag)
        episode_rows.append({"split": split, "experiment": "E0", "arm": "existing_ppo",
                             "seed": checkpoint.seed, "run_id": checkpoint.run_id,
                             "profile_set": None, "profile_index": None,
                             **_metrics(episode, assets, groups, settings, context)})  # fmt: skip

    state_rows, effect_rows, sweep_rows, intervention_rows, scale_rows = [], [], [], [], []
    interaction_rows, contrast_rows = [], []
    if experiment.label is not None:  # E5 (D-089) and later labelled experiments
        labels_by_arm = {"main": experiment.label, "heldout": f"{experiment.label}H"}
    elif experiment.reward is not None:
        labels_by_arm = {"main": "E4", "heldout": "E4H"}
    else:
        labels_by_arm = {"main": "E1", "heldout": "E3"}
    centre_obs: dict[tuple[str, int], np.ndarray] = {}
    models: dict[tuple[str, int], Any] = {}
    sweeps = pa.sweep_profiles(experiment.sweep_points)
    for checkpoint in plan.checkpoints:
        arm, seed = checkpoint.arm, checkpoint.seed
        scaler = FeatureScaler.load(checkpoint.directory / "scaler.json")
        sampling = experiment.arms[arm]
        env = ProfileConditionedEnv(base_env(scaler), sampling, seed=seed,
                                    stream=experiment.profile_stream)  # fmt: skip
        model = load(
            checkpoint.directory, checkpoint.model_sha256, int(env.observation_space.shape[0])
        )
        models[(arm, seed)] = model
        policy = _policy(model)
        label = {"split": split, "arm": arm, "seed": seed, "run_id": checkpoint.run_id}
        set_names = [CENTRE, *experiment.arm_profile_sets[arm]]
        episodes: dict[str, list[Episode]] = {}
        for name in set_names:
            episodes[name] = []
            for index, profile in enumerate(sets[name]):
                episode = run_episode(model, env, returns, (x0, e), settings, lag, profile)
                # Fidelity: recomputing the targets from the saved observations reproduces them.
                again = decided_targets(policy, episode.observations, max_weight)
                if np.abs(again - episode.targets).max() > FIDELITY_TOLERANCE:
                    raise ProfileExperimentError(f"{arm} s{seed}: targets do not reproduce")
                episodes[name].append(episode)
                excluded = sampling.in_excluded_region(profile) if sampling.exclude else None
                episode_rows.append(
                    {
                        **label,
                        "experiment": labels_by_arm[arm],
                        "profile_set": name,
                        "profile_index": index,
                        "in_training_region": None if excluded is None else not excluded,
                        **_profile_columns(profile),
                        **_metrics(episode, assets, groups, settings, context),
                        **(
                            _objective(
                                episode, experiment.reward, profile, settings.initial_capital
                            )
                            if experiment.reward is not None
                            else {}
                        ),
                    }
                )
        observations = episodes[CENTRE][0].observations
        centre_obs[(arm, seed)] = observations
        centre_targets = episodes[CENTRE][0].targets
        # State-matched profile sensitivity on the centre trajectory (personalisation analysis).
        for name in set_names[1:]:
            paths = np.stack([decided_targets(policy, _replace_profile(observations, p),
                                              max_weight) for p in sets[name]])  # fmt: skip
            state_rows.append(
                {
                    **label,
                    "profile_set": name,
                    "observations": "centre_path",
                    **pa.pairwise_summary(paths),
                    "dw_vs_centre_mean": float(
                        np.mean([pa.mean_abs_difference(p, centre_targets) for p in paths])
                    ),
                }
            )
            exposure = [pa.exposures(p, assets, groups) for p in paths]
            outcomes = {key: [x[key] for x in exposure] for key in exposure[0]}
            on_path = [_metrics(ep, assets, groups, settings, context) for ep in episodes[name]]
            for key in ("annualised.net_sharpe", "annualised.net_annualised_volatility",
                        "net_max_drawdown", "annualised.annualised_traded_notional",
                        "mean_held_CASH", "allocation_stability_dw"):  # fmt: skip
                if key in on_path[0]:
                    outcomes[f"on_path.{key}"] = [m[key] for m in on_path]
            for row in pa.dimension_correlations(sets[name], outcomes):
                effect_rows.append({**label, "profile_set": name, **row})
        for dimension, value, profile in sweeps:
            path = decided_targets(policy, _replace_profile(observations, profile), max_weight)
            sweep_rows.append({**label, "dimension": dimension, "value": value,
                               "dw_vs_centre": pa.mean_abs_difference(path, centre_targets),
                               **pa.exposures(path, assets, groups)})  # fmt: skip
        # Interaction grids and the risk-acceptance contrast (E4 analysis; state-matched).
        if experiment.interaction_pairs:
            index = {d: i for i, d in enumerate(PROFILE_DIMENSIONS)}
            grid = np.linspace(0.0, 1.0, experiment.interaction_points)
            for first, second in experiment.interaction_pairs:
                for x in grid:
                    for y in grid:
                        profile = neutral_profile()
                        profile[index[first]], profile[index[second]] = x, y
                        path = decided_targets(policy, _replace_profile(observations, profile),
                                               max_weight)  # fmt: skip
                        interaction_rows.append({
                            **label, "first": first, "second": second, "first_value": float(x),
                            "second_value": float(y),
                            "dw_vs_centre": pa.mean_abs_difference(path, centre_targets),
                            **pa.exposures(path, assets, groups)})  # fmt: skip
            low, high = neutral_profile(), neutral_profile()
            low[[index["risk_tolerance"], index["risk_capacity"]]] = 0.0
            high[[index["risk_tolerance"], index["risk_capacity"]]] = 1.0
            low_path, high_path = (decided_targets(policy, _replace_profile(observations, q),
                                                   max_weight) for q in (low, high))  # fmt: skip
            low_x, high_x = (pa.exposures(q, assets, groups) for q in (low_path, high_path))
            contrast_rows.append({
                **label, "contrast": "a=0 (RT=RC=0) vs a=1 (RT=RC=1), others 0.5",
                "dw": pa.mean_abs_difference(low_path, high_path),
                **{f"low_a_{k}": v for k, v in low_x.items()},
                **{f"high_a_{k}": v for k, v in high_x.items()}})  # fmt: skip
        # E2 intervention on each policy's own trajectory (main arm, first profile set).
        if arm == "main" and experiment.arm_profile_sets["main"]:
            name = experiment.arm_profile_sets["main"][0]
            partner = pa.shuffled_partner(len(sets[name]))
            for index, episode in enumerate(episodes[name]):
                for kind, profile in (
                    ("neutral", neutral_profile()),
                    ("shuffled", sets[name][partner[index]]),
                ):
                    path = decided_targets(
                        policy, _replace_profile(episode.observations, profile), max_weight
                    )
                    own = pa.exposures(episode.targets, assets, groups)
                    other = pa.exposures(path, assets, groups)
                    intervention_rows.append({
                        **label, "profile_set": name, "profile_index": index,
                        "intervention": kind, "dw_vs_correct": pa.mean_abs_difference(
                            episode.targets, path),
                        **{f"delta_{k}": other[k] - own[k] for k in own},
                    })  # fmt: skip

    # Seed scale: D_w between seeds at the centre profile, on one shared observation sequence.
    for arm in experiment.arms:
        seeds = [s for a, s in models if a == arm]
        if len(seeds) < 2:
            continue
        shared = centre_obs[(arm, seeds[0])]
        paths = np.stack([decided_targets(_policy(models[(arm, s)]),
                                          _replace_profile(shared, neutral_profile()),
                                          max_weight) for s in seeds])  # fmt: skip
        scale_rows.append({"split": split, "arm": arm, "observations": f"centre_path_s{seeds[0]}",
                           "seeds": len(seeds), **pa.pairwise_summary(paths)})  # fmt: skip

    return {
        "window": window["info"] | {"first_execution_row": x0, "last_row": e},
        "episode_metrics": pd.DataFrame(episode_rows),
        "state_matched": pd.DataFrame(state_rows),
        "dimension_effects": pd.DataFrame(effect_rows),
        "sweeps": pd.DataFrame(sweep_rows),
        "interventions": pd.DataFrame(intervention_rows),
        "seed_scale": pd.DataFrame(scale_rows),
        **(
            {
                "interactions": pd.DataFrame(interaction_rows),
                "contrasts": pd.DataFrame(contrast_rows),
            }
            if experiment.interaction_pairs
            else {}
        ),
    }


def summarise(results: Mapping[str, Any]) -> dict[str, Any]:
    """Seed-level aggregates (mean, std with ddof 1, median, min, max) of the main tables."""
    metrics = results["episode_metrics"]
    keys = ["annualised.net_sharpe", "net_cumulative_return", "annualised.net_annualised_return",
            "annualised.net_annualised_volatility", "net_max_drawdown", "cost_drag",
            "annualised.annualised_traded_notional", "mean_held_CASH", "target_equity",
            "allocation_stability_dw"]  # fmt: skip

    def stats(values: pd.Series) -> dict[str, float]:
        v = pd.to_numeric(values, errors="coerce").dropna()
        if v.empty:
            return {}
        return {
            "n": int(v.size),
            "mean": float(v.mean()),
            "std": float(v.std(ddof=1)) if v.size > 1 else float("nan"),
            "median": float(v.median()),
            "min": float(v.min()),
            "max": float(v.max()),
        }

    groups = []
    for (experiment, arm, set_name), frame in metrics.groupby(
        ["experiment", "arm", metrics["profile_set"].fillna("-")], dropna=False
    ):
        if experiment not in ("baseline", "E0"):  # per seed: mean over the set's profiles
            frame = frame.groupby("seed").mean(numeric_only=True).reset_index()
        groups.append({"experiment": experiment, "arm": arm, "profile_set": set_name,
                       **{k: stats(frame[k]) for k in keys if k in frame}})  # fmt: skip
    state = results["state_matched"]
    dw = (
        [
            {"arm": arm, "profile_set": name, **stats(frame["dw_mean"])}
            for (arm, name), frame in state.groupby(["arm", "profile_set"])
        ]
        if len(state)
        else []
    )
    interventions = results["interventions"]
    e2 = ([{"intervention": kind, **stats(frame.groupby("seed")["dw_vs_correct"].mean())}
           for kind, frame in interventions.groupby("intervention")]
          if len(interventions) else [])  # fmt: skip
    return {"by_group_over_seeds": groups, "state_matched_dw_over_seeds": dw,
            "e2_dw_over_seeds": e2,
            "seed_scale": results["seed_scale"].to_dict(orient="records"),
            "statistics": "descriptive only (no intervals, no p-values; protocol §15.8)",
            "limitations": list(pa.LIMITATIONS)}  # fmt: skip


def e0_reproduction(plan: ProfilePlan, metrics: pd.DataFrame) -> dict[str, Any]:
    """On validation, E0 must reproduce the EXP-006 net Sharpe of every configuration-4 seed."""
    if plan.split != "validation":
        return {"checked": False, "reason": "EXP-006 covers the validation split only"}
    workflow_path = plan.context.config_dir / "workflow.yaml"
    if not workflow_path.is_file():
        return {"checked": False, "reason": "no workflow.yaml naming the EXP-006 artifact"}
    directory = resolve_path(load_workflow_config(workflow_path).validation_evaluation_dir,
                             plan.context.root)  # fmt: skip
    path = directory / "policy_metrics.csv"
    if not path.is_file():
        return {"checked": False, "reason": f"{path} not found"}
    saved = pd.read_csv(path)
    saved = saved[saved["configuration"] == plan.context.experiment.base_configuration]
    ours = metrics[metrics["experiment"] == "E0"].set_index("seed")["annualised.net_sharpe"]
    diffs = {int(r.seed): abs(float(r["annualised.net_sharpe"]) - float(ours.loc[r.seed]))
             for _, r in saved.iterrows() if r.seed in ours.index}  # fmt: skip
    return {"checked": True, "source": str(path), "max_abs_difference": max(diffs.values()),
            "reproduced": max(diffs.values()) <= 1e-12, "per_seed": diffs}  # fmt: skip


def run_profile_evaluation(plan: ProfilePlan) -> Path:
    """Evaluate and write once. Validation needs a clean committed tree (as D-076)."""
    if not plan.pipeline_check and plan.identity["code"].get("dirty") is not False:
        raise ProfileExperimentError("this evaluation needs a clean committed tree "
                                     "(use --pipeline-check on the training split)")  # fmt: skip
    target = plan.output_dir
    if target.exists():
        raise ProfileExperimentError(f"{target} already exists; evaluations are written once")
    started, clock = dt.datetime.now(dt.UTC), time.perf_counter()
    threads, deterministic = torch.get_num_threads(), torch.are_deterministic_algorithms_enabled()
    try:
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        results = evaluate_profiles(plan)
    finally:
        torch.set_num_threads(threads)
        torch.use_deterministic_algorithms(deterministic)
    seconds = time.perf_counter() - clock
    summary = summarise(results) | {"window": results["window"],
                                    "e0_reproduction": e0_reproduction(
                                        plan, results["episode_metrics"]),
                                    "comparability": plan.comparability}  # fmt: skip
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f"{target.name}{run_safety.STAGING_MARK}{os.getpid()}"
    staging.mkdir()
    tables = [name for name in ("episode_metrics", "state_matched", "dimension_effects", "sweeps",
              "interventions", "seed_scale", *OPTIONAL_TABLES) if name in results]  # fmt: skip
    for name in tables:
        results[name].to_csv(staging / f"{name}.csv", index=False)
    cache.write_json(summary, staging / "summary.json")
    status = PIPELINE_STATUS if plan.pipeline_check else STATUS.format(split=plan.split)
    metadata = {
        "evaluation_id": plan.evaluation_id, "status": status, **plan.identity,
        "started_at": started.isoformat(timespec="seconds"), "wall_seconds": round(seconds, 3),
        "files_sha256": {name: cache.file_sha256(staging / name)
                         for name in sorted(p.name for p in staging.iterdir())},
    }  # fmt: skip
    cache.write_json(metadata, staging / "metadata.json")
    run_safety.finalise_exclusive(staging, target)
    return target


def verify_profile_evaluation(directory: Path) -> list[str]:
    """Problems with a written evaluation: file set, file hashes and identity hash."""
    directory = Path(directory)
    names = sorted(p.name for p in directory.iterdir()) if directory.is_dir() else []
    if "metadata.json" not in names:
        return [f"{directory}: no metadata.json"]
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    expected = sorted({*meta.get("files_sha256", {}), "metadata.json"})
    if names != expected or not set(OUTPUT_FILES) <= set(names):
        return [f"files {names} != {expected} (core files {sorted(OUTPUT_FILES)})"]
    problems = [f"{name}: hash differs" for name, digest in meta["files_sha256"].items()
                if cache.file_sha256(directory / name) != digest]  # fmt: skip
    identity = {k: meta[k] for k in ("schema_version", "split", "pipeline_check", "experiment",
                                     "profile_sets", "checkpoints", "e0_checkpoints", "data",
                                     "rows_read_before", "backtest", "environment", "code",
                                     "versions", "determinism")}  # fmt: skip
    if cache.short_hash(identity) != directory.name or meta["evaluation_id"] != directory.name:
        problems.append("identity hash != evaluation id")
    return problems


# --------------------------------------------------------------------------
# Command line: python scripts/profile_experiment.py
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Profile-conditioned PPO (D-085): train arms, "
        "evaluate E0-E3 on train/validation, verify outputs."
    )
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--feature-dir", type=Path)
    parser.add_argument(
        "--experiment-config",
        type=Path,
        help="experiment file (default <config-dir>/profile_experiment.yaml; E4: "
        "configs/profile_reward_experiment.yaml)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="print the runs and profile sets; trains and reads nothing")
    train = sub.add_parser("train", help="train an arm on the training split")
    train.add_argument("--arm", required=True, choices=("main", "heldout"))
    train.add_argument("--seed", type=int, action="append", help="default: every seed")
    train.add_argument("--smoke", action="store_true", help="reduced budget (needs --timesteps)")
    train.add_argument("--timesteps", type=int)
    train.add_argument("--execute", action="store_true", help="required to train")
    ev = sub.add_parser("evaluate", help="evaluate E0-E3 on one split (never the test split)")
    ev.add_argument("--split", required=True, choices=("train", "validation"))
    ev.add_argument(
        "--pipeline-check",
        action="store_true",
        help="training split only: accept smoke runs and uncommitted code",
    )
    ev.add_argument("--commit", help="choose runs trained at this commit (prefix)")
    ev.add_argument("--execute", action="store_true", help="required to evaluate")
    verify = sub.add_parser("verify", help="check a written evaluation's files and identity")
    verify.add_argument("directory", type=Path)
    compare = sub.add_parser(
        "compare", help="E4 vs E1 (and E0) from two verified evaluations; prespecified H1-H7"
    )
    compare.add_argument("--treatment", type=Path, required=True, help="E4 evaluation dir")
    compare.add_argument("--control", type=Path, required=True, help="E1 evaluation dir")
    compare.add_argument("--execute", action="store_true", help="required to write")
    fixed = sub.add_parser(
        "compare-fixed", help="E5: lambda=9 vs lambda=0 from four verified evaluations; H1-H8"
    )
    for name in ("low-validation", "high-validation", "low-train", "high-train"):
        fixed.add_argument(f"--{name}", type=Path, required=True)
    fixed.add_argument("--reference", type=Path, action="append", default=[],
                       help="verified reference evaluation (E1, E4) for medians")  # fmt: skip
    fixed.add_argument("--execute", action="store_true", help="required to write")
    dose = sub.add_parser(
        "compare-dose", help="E6: lambda dose response from six verified evaluations; H1-H8"
    )
    dose.add_argument(
        "--validation",
        type=Path,
        nargs=3,
        required=True,
        metavar=("L0", "L3", "L9"),
        help="validation evaluations, lambda ascending",
    )
    dose.add_argument(
        "--train",
        type=Path,
        nargs=3,
        required=True,
        metavar=("L0", "L3", "L9"),
        help="training evaluations, lambda ascending",
    )
    dose.add_argument(
        "--e5-validation",
        type=Path,
        nargs=2,
        default=[],
        metavar=("E5L", "E5H"),
        help="E5 validation evaluations (reproduction)",
    )
    dose.add_argument("--reference", type=Path, action="append", default=[])
    dose.add_argument("--execute", action="store_true", help="required to write")
    turn = sub.add_parser(
        "compare-turnover", help="E7: turnover penalty kappa 0 / T1 / T2; H1-H8 (D-091)"
    )
    turn.add_argument(
        "--validation",
        type=Path,
        nargs=3,
        required=True,
        metavar=("K0", "K1", "K2"),
        help="validation evaluations, kappa ascending",
    )
    turn.add_argument(
        "--train",
        type=Path,
        nargs=3,
        required=True,
        metavar=("K0", "K1", "K2"),
        help="training evaluations, kappa ascending",
    )
    turn.add_argument("--e6-validation", type=Path, help="E6L validation evaluation (H7)")
    turn.add_argument("--reference", type=Path, action="append", default=[])
    turn.add_argument("--execute", action="store_true", help="required to write")
    refine = sub.add_parser(
        "compare-refine", help="E8: turnover penalty kappa 0 / T1 / T2 / T3; H1-H9 (D-092)"
    )
    for name in ("validation", "train"):
        refine.add_argument(f"--{name}", type=Path, nargs=4, required=True,
                            metavar=("K0", "K1", "K2", "K3"),
                            help=f"{name} evaluations, kappa ascending")  # fmt: skip
    for name, metavar in (("e7-validation", ("E7B", "E7T1")), ("e7-train", ("E7B", "E7T1"))):
        refine.add_argument(f"--{name}", type=Path, nargs=2, required=True, metavar=metavar,
                            help="E7 evaluations for the H8 reproduction")  # fmt: skip
    for name in ("e6-validation", "e6-train"):
        refine.add_argument(f"--{name}", type=Path, required=True, help="E6L evaluation (H8)")
    refine.add_argument(
        "--historical",
        type=Path,
        action="append",
        default=[],
        help="E7T2 evaluation (prior experiment; not in any hypothesis)",
    )
    refine.add_argument("--reference", type=Path, action="append", default=[])
    refine.add_argument("--execute", action="store_true", help="required to write")
    figures = sub.add_parser("figures", help="E4 vs E1 figures from saved outputs (viz extra)")
    figures.add_argument("--treatment", type=Path, required=True)
    figures.add_argument("--control", type=Path, required=True)
    figures.add_argument("--comparison", type=Path, required=True)
    figures.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "verify":
        meta_path = Path(args.directory) / "metadata.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        is_comparison = "comparison_id" in meta
        if is_comparison and meta.get("kind") == "turnover_refine":  # E8
            from adaptive_portfolio.explainability.turnover_refine_comparison import (
                verify_refine_comparison,
            )

            problems = verify_refine_comparison(args.directory)
        elif is_comparison and meta.get("kind") == "turnover":  # E7
            from adaptive_portfolio.explainability.turnover_comparison import (
                verify_turnover_comparison,
            )

            problems = verify_turnover_comparison(args.directory)
        elif is_comparison and meta.get("kind") == "dose_response":  # E6
            from adaptive_portfolio.explainability.dose_response_comparison import (
                verify_dose_comparison,
            )

            problems = verify_dose_comparison(args.directory)
        elif is_comparison and "evaluations" in meta:  # E5 fixed-risk comparison
            from adaptive_portfolio.explainability.fixed_risk_comparison import (
                verify_fixed_comparison,
            )

            problems = verify_fixed_comparison(args.directory)
        elif is_comparison:
            from adaptive_portfolio.explainability.profile_comparison import verify_comparison

            problems = verify_comparison(args.directory)
        else:
            problems = verify_profile_evaluation(args.directory)
        print("VERIFIED" if not problems else "VERIFICATION FAILED:\n  " + "\n  ".join(problems))
        return 0 if not problems else 1
    if args.command == "figures":
        from adaptive_portfolio.visualization.profile_figures import make_figures

        for path in make_figures(args.treatment, args.control, args.comparison, args.out):
            print(f"written: {path}")
        return 0
    try:
        context = load_context(
            args.config_dir, args.dataset_dir, args.feature_dir, args.experiment_config
        )
        if args.command == "compare":
            from adaptive_portfolio.explainability import profile_comparison as pc

            if not args.execute:
                print("nothing written: add --execute")
                return 0
            try:
                target = pc.run_comparison(context, args.treatment, args.control)
            except pc.ComparisonError as exc:
                print(f"COMPARISON FAILED: {exc}", file=sys.stderr)
                return 1
            print(f"written: {target}")
            for name, outcome in pc.load_hypotheses(target).items():
                print(f"  {name}: {outcome['verdict']}")
            return 0
        if args.command == "compare-turnover":
            from adaptive_portfolio.explainability import turnover_comparison as tc

            if not args.execute:
                print("nothing written: add --execute")
                return 0
            try:
                target = tc.run_turnover_comparison(
                    context, args.validation, args.train, args.e6_validation, args.reference
                )
            except tc.TurnoverComparisonError as exc:
                print(f"COMPARISON FAILED: {exc}", file=sys.stderr)
                return 1
            data = json.loads((target / "hypotheses.json").read_text(encoding="utf-8"))
            print(f"written: {target}")
            for name in sorted(k for k in data if k.startswith("H")):
                print(f"  {name}: {data[name]['verdict']}")
            print(f"  outcome: {data['outcome']['class']}")
            return 0
        if args.command == "compare-refine":
            from adaptive_portfolio.explainability import turnover_refine_comparison as rc

            if not args.execute:
                print("nothing written: add --execute")
                return 0
            repro = {"0:E8B = E7B": [args.e7_validation[0], args.e7_train[0]],
                     "0:E8B = E6L": [args.e6_validation, args.e6_train],
                     "1:E8T1 = E7T1": [args.e7_validation[1], args.e7_train[1]]}  # fmt: skip
            try:
                target = rc.run_refine_comparison(
                    context, args.validation, args.train, repro, args.historical, args.reference
                )
            except rc.RefineComparisonError as exc:
                print(f"COMPARISON FAILED: {exc}", file=sys.stderr)
                return 1
            data = json.loads((target / "hypotheses.json").read_text(encoding="utf-8"))
            print(f"written: {target}")
            for name in sorted((k for k in data if k.startswith("H")), key=lambda k: int(k[1:])):
                print(f"  {name}: {data[name]['verdict']}")
            print(f"  outcome: {data['outcome']['class']}")
            return 0
        if args.command == "compare-dose":
            from adaptive_portfolio.explainability import dose_response_comparison as dc

            if not args.execute:
                print("nothing written: add --execute")
                return 0
            try:
                target = dc.run_dose_comparison(
                    context, args.validation, args.train, args.e5_validation, args.reference
                )
            except dc.DoseResponseError as exc:
                print(f"COMPARISON FAILED: {exc}", file=sys.stderr)
                return 1
            data = json.loads((target / "hypotheses.json").read_text(encoding="utf-8"))
            print(f"written: {target}")
            for name in sorted(k for k in data if k.startswith("H")):
                print(f"  {name}: {data[name]['verdict']}")
            print(f"  outcome: {data['outcome']['class']}")
            return 0
        if args.command == "compare-fixed":
            from adaptive_portfolio.explainability import fixed_risk_comparison as fc

            if not args.execute:
                print("nothing written: add --execute")
                return 0
            try:
                target = fc.run_fixed_comparison(
                    context, args.low_validation, args.high_validation, args.low_train,
                    args.high_train, args.reference,
                )  # fmt: skip
            except fc.FixedRiskComparisonError as exc:
                print(f"COMPARISON FAILED: {exc}", file=sys.stderr)
                return 1
            data = json.loads((target / "hypotheses.json").read_text(encoding="utf-8"))
            print(f"written: {target}")
            for name in sorted(k for k in data if k.startswith("H")):
                print(f"  {name}: {data[name]['verdict']}")
            print(f"  outcome: {data['outcome']['class']}")
            return 0
        if args.command == "plan":
            sets = build_profile_sets(context.experiment)
            print(
                f"configuration {context.experiment.base_configuration}, seeds "
                f"{list(context.experiment.seeds)}, budget {context.agent.total_timesteps}"
            )
            for arm, sampling in context.experiment.arms.items():
                print(f"  arm {arm}: {sampling.to_dict()}")
            for name, values in sets.items():
                print(f"  profile set {name}: {len(values)} profiles")
            return 0
        if args.command == "train":
            if args.smoke != (args.timesteps is not None):
                print("--smoke and --timesteps must be given together", file=sys.stderr)
                return 2
            if not args.execute:
                print("nothing trained: add --execute", file=sys.stderr)
                return 2
            results = train_arm(context, args.arm, args.seed, total_timesteps=args.timesteps,
                                run_kind="smoke" if args.smoke else "full")  # fmt: skip
            for row in results:
                print(row)
            return 0
        plan = plan_profile_evaluation(context, args.split, pipeline_check=args.pipeline_check,
                                       commit=args.commit)  # fmt: skip
        print(
            f"evaluation {plan.evaluation_id} ({args.split}; pipeline check "
            f"{plan.pipeline_check}): {len(plan.checkpoints)} profile and {len(plan.e0)} E0 "
            f"checkpoints; comparability checks {len(plan.comparability)} passed"
        )
        if not args.execute:
            print("nothing evaluated: add --execute")
            return 0
        print(f"written: {run_profile_evaluation(plan)}")
        return 0
    except EXPECTED_FAILURES as exc:
        print(f"PROFILE EXPERIMENT FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
