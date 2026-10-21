"""Validation evaluator for the PPO grid (milestone B; protocol D-076; ``rl`` extra).

Protocol D-076 was accepted on 2026-10-21 (protocol only). Executing the evaluation needs a
separate authorisation; see docs/decision_log.md and docs/approval_checklist.md.

Evaluates the final checkpoint of every run of the configured grid (``evaluation.yaml``
``grid_id``) and the conventional baselines (``backtest.yaml``) on the **validation** split,
under one set of conventions, then summarises seeds and applies the D-066 selection rule.

Protocol (D-076):

* **Checkpoints:** exactly the runs of ``agent.yaml``'s grid (8 x 5 = 40 for D-066). Each must
  pass the integrity checks of :func:`discover_checkpoints`. Any failure aborts the whole
  evaluation; no checkpoint is ever skipped or substituted.
* **Window (identical for all):** the validation split's common window of the baseline backtest
  (:func:`~adaptive_portfolio.evaluation.backtest.split_window`). First decision ``k0`` (the
  first validation row), funding execution ``x0 = k0 + lag``, last return row ``e`` (the last
  validation row). Every policy and baseline ledger must have identical dates.
* **Policies:** :class:`PortfolioEnv` on the validation split with the checkpoint's frozen
  training scaler. Actions are deterministic (``predict(deterministic=True)``: the Gaussian
  mean, clipped to ``[-1, 1]``), then the D-072/D-063 mapping. Weekly decisions (D-065), lag 1.
  The decided targets are re-simulated with :func:`simulate` (the baselines' path), and the
  ledger must equal the environment's own ledger exactly.
* **Baselines:** the ``backtest.yaml`` strategies with their own schedules, through
  :func:`strategy_targets` and :func:`simulate`.
* **Accounting:** start in cash at ``initial_capital``; the funding trade at ``x0`` is charged;
  15 bps on traded notional; the final value is marked to market at the close of ``e``, with no
  liquidation and no terminal cost. Metrics come from :func:`summarize_window` (shared with the
  baseline backtest): annualised with N = 252, rf = 0, net Sharpe excluding the funding row.
* **Selection:** :mod:`adaptive_portfolio.evaluation.selection`.
* **Data boundary:** rows are read only up to the day before ``test.start`` (bounded loaders);
  the rows held are checked by :func:`assert_before_split`; there is no test option.

``--plan`` reads only configuration, the grid manifest, run directories and the dataset and
feature-set metadata (ids). It loads no data rows. ``--execute`` additionally needs
``--confirm-validation-evaluation`` and a clean, committed working tree.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd
import torch
from stable_baselines3 import PPO

from adaptive_portfolio.agents import ppo, run_safety
from adaptive_portfolio.config import (
    AgentConfig,
    BacktestConfig,
    ConfigError,
    EvaluationConfig,
    ProjectConfig,
    load_agent_config,
    load_backtest_config,
    load_evaluation_config,
    load_project_config,
)
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.boundaries import DataBoundaryError, assert_before_split
from adaptive_portfolio.data.pipeline import project_root_for, resolve_path
from adaptive_portfolio.environment.observation import FeatureScaler
from adaptive_portfolio.environment.portfolio_env import PortfolioEnv
from adaptive_portfolio.evaluation.backtest import (
    _environment_dict,
    backtest_config_to_dict,
    simulation_settings,
    split_window,
    strategy_targets,
)
from adaptive_portfolio.evaluation.performance import summarize_window
from adaptive_portfolio.evaluation.selection import (
    SelectionError,
    select_configuration,
    summarise_configurations,
)
from adaptive_portfolio.evaluation.simulator import simulate
from adaptive_portfolio.features.engineering import FeatureDataError
from adaptive_portfolio.features.pipeline import (
    load_feature_outputs,
    load_processed_inputs,
    locate_dataset_dir,
)

EVALUATION_SCHEMA_VERSION = 1
EVALUATION_FILES = (
    "evaluation.json",
    "policy_metrics.csv",
    "baseline_metrics.csv",
    "configuration_summary.csv",
    "allocations.csv",
    "ledgers.csv",
    "metadata.json",
)
STATUS = (
    "VALIDATION EVALUATION under protocol D-076 (approval status in docs/decision_log.md). "
    "Validation metrics are used for configuration selection only; they are not test results, "
    "not evidence of out-of-sample performance and not financial advice."
)


class EvaluationError(RuntimeError):
    """Raised when the evaluation cannot proceed exactly as the protocol requires."""


# Expected, reportable failures: the CLI prints them as ``EVALUATION FAILED`` and exits 1.
# Anything else (a programming error) is not caught and keeps its traceback.
EXPECTED_FAILURES = (
    EvaluationError,
    SelectionError,
    DataBoundaryError,
    FeatureDataError,
    ConfigError,
    run_safety.RunSafetyError,
)


def protocol_hash(evaluation: EvaluationConfig) -> str:
    """Deterministic hash of the normalised protocol settings (canonical JSON, sorted keys).

    Independent of YAML formatting, key order and numeric spelling (e.g. ``1.0e-9`` and
    ``0.000000001``); it changes whenever a protocol setting changes.
    """
    return evaluation.protocol_hash()


@dataclass(frozen=True)
class Checkpoint:
    configuration: int
    seed: int
    learning_rate: float
    n_steps: int
    ent_coef: float
    run_id: str
    directory: Path
    model_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "configuration": self.configuration,
            "seed": self.seed,
            "learning_rate": self.learning_rate,
            "n_steps": self.n_steps,
            "ent_coef": self.ent_coef,
            "run_id": self.run_id,
            "model_sha256": self.model_sha256,
        }


# --------------------------------------------------------------------------
# Checkpoint discovery and integrity (no data rows read)
# --------------------------------------------------------------------------


def _data_ids(dataset_dir: Path, feature_dir: Path) -> dict[str, str]:
    dataset = json.loads((dataset_dir / "metadata.json").read_text(encoding="utf-8"))
    features = json.loads((feature_dir / "feature_metadata.json").read_text(encoding="utf-8"))
    return {
        "processed_dataset_id": dataset.get("processed_dataset_id"),
        "feature_set_id": features.get("feature_set_id"),
    }


def discover_checkpoints(
    agent: AgentConfig,
    evaluation: EvaluationConfig,
    experiments_dir: Path,
    data_ids: dict[str, str],
    validation_start: str,
) -> tuple[list[Checkpoint], dict[str, Any]]:
    """Every run of the grid, verified; raises :class:`EvaluationError` listing all problems."""
    manifest_path = experiments_dir / "grids" / evaluation.grid_id / "manifest.json"
    if not manifest_path.is_file():
        raise EvaluationError(f"grid manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    specs = {(s.configuration, s.seed): s for s in agent.run_specs()}
    runs = {(r["configuration"], r["seed"]): r for r in manifest.get("runs", [])}
    problems: list[str] = []
    if manifest.get("grid_id") != evaluation.grid_id:
        problems.append(f"manifest grid_id {manifest.get('grid_id')} != {evaluation.grid_id}")
    if set(runs) != set(specs) or len(manifest.get("runs", [])) != len(specs):
        problems.append(
            f"manifest runs {sorted(runs)} differ from the {len(specs)} configured grid runs"
        )
    grid_code = manifest.get("code") or {}
    if grid_code.get("dirty") is not False or not grid_code.get("commit"):
        problems.append(f"grid was not trained from a clean commit: {grid_code}")
    checkpoints, scalers = [], set()
    for key in sorted(specs):
        spec, run = specs[key], runs.get(key)
        label = f"c{key[0]} s{key[1]}"
        if run is None:
            problems.append(f"{label}: missing from the manifest")
            continue
        run_id, directory = run["run_id"], experiments_dir / run["run_id"]
        if run.get("status") != "completed":
            problems.append(f"{label} {run_id}: manifest status {run.get('status')!r}")
        found = run_safety.verify_run_dir(directory, run_id, agent.total_timesteps)
        if found:
            problems.append(f"{label} {run_id}: {found}")
            continue
        config = json.loads((directory / "run_config.json").read_text(encoding="utf-8"))
        meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        checks = {
            "identity hash == run_id": cache.short_hash(config) == run_id,
            "run spec == configured grid run": config.get("run") == spec.to_dict(),
            "run kind full": config.get("run_kind") == "full",
            "trained on the training split": config.get("split") == "train",
            "code == grid commit, clean": config.get("code", {}).get("commit")
            == grid_code.get("commit")
            and config.get("code", {}).get("dirty") is False,
            "data ids match the dataset to evaluate": all(
                config.get("data", {}).get(k) == v for k, v in data_ids.items()
            ),
            "training data ends before validation.start": str(
                config.get("data", {}).get("last_date", "9999")
            )
            < validation_start,
            "scaler.json == run config scaler": json.loads(
                (directory / "scaler.json").read_text(encoding="utf-8")
            )
            == config.get("scaler"),
            "model.zip hash recorded": bool(meta.get("files_sha256", {}).get("model.zip")),
        }
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            problems.append(f"{label} {run_id}: failed {failed}")
            continue
        scalers.add(json.dumps(config["scaler"], sort_keys=True))
        checkpoints.append(
            Checkpoint(
                configuration=spec.configuration,
                seed=spec.seed,
                learning_rate=spec.learning_rate,
                n_steps=spec.n_steps,
                ent_coef=spec.ent_coef,
                run_id=run_id,
                directory=directory,
                model_sha256=meta["files_sha256"]["model.zip"],
            )
        )
    if len(scalers) > 1:
        problems.append(f"{len(scalers)} different scalers across runs; expected one")
    if problems:
        raise EvaluationError(
            f"{len(problems)} checkpoint integrity problem(s); nothing is evaluated:\n  - "
            + "\n  - ".join(problems)
        )
    info = {
        "grid_id": evaluation.grid_id,
        "manifest_sha256": cache.file_sha256(manifest_path),
        "grid_code": grid_code,
        "runs": len(checkpoints),
    }
    return checkpoints, info


# --------------------------------------------------------------------------
# Identity and plan
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationPlan:
    config: ProjectConfig
    backtest: BacktestConfig
    agent: AgentConfig
    evaluation: EvaluationConfig
    project_root: Path
    dataset_dir: Path
    feature_dir: Path
    checkpoints: tuple[Checkpoint, ...]
    identity: dict[str, Any]
    code: Mapping[str, Any]  # read-only snapshot, captured once per plan

    @property
    def evaluation_id(self) -> str:
        return cache.short_hash(self.identity)

    @property
    def protocol_hash(self) -> str:
        return protocol_hash(self.evaluation)

    @property
    def output_dir(self) -> Path:
        return resolve_path(self.evaluation.output_dir, self.project_root) / self.evaluation_id


def _check_conventions(config: ProjectConfig, backtest: BacktestConfig) -> None:
    if backtest.periods_per_year != 252 or config.environment.risk_free_rate != 0:
        raise EvaluationError(
            "the protocol uses N = 252 and rf = 0; found periods_per_year "
            f"{backtest.periods_per_year} and risk_free_rate {config.environment.risk_free_rate}"
        )
    if backtest.execution_lag_sessions != 1:
        raise EvaluationError("the protocol uses execution lag 1 (D-055)")


def plan_evaluation(
    config_dir: Path, dataset_dir: Path | None = None, feature_dir: Path | None = None
) -> EvaluationPlan:
    """Verify every checkpoint and compute the evaluation identity. Reads no data rows."""
    config_dir = Path(config_dir)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    agent = load_agent_config(config_dir / "agent.yaml")
    evaluation = load_evaluation_config(config_dir / "evaluation.yaml")
    _check_conventions(config, backtest)
    root = project_root_for(config_dir)
    dataset_dir = Path(dataset_dir or locate_dataset_dir(config, root))
    feature_dir = Path(feature_dir or ppo._default_feature_dir(config_dir, root, dataset_dir))
    data_ids = _data_ids(dataset_dir, feature_dir)
    experiments = resolve_path(agent.output_dir, root)
    splits = config.experiment.splits
    checkpoints, grid = discover_checkpoints(
        agent, evaluation, experiments, data_ids, str(splits.validation.start)
    )
    # One code-provenance snapshot per operation, reused everywhere (identity and policy).
    provenance = run_safety.code_provenance(root)
    code = {k: provenance.get(k) for k in ("git_available", "commit", "dirty", "diff_sha256")}
    identity = {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "protocol": evaluation.to_dict(),
        "grid": grid,
        "checkpoints": [c.to_dict() for c in checkpoints],
        "data": data_ids,
        "splits": {
            "validation": [str(splits.validation.start), str(splits.validation.end)],
            "rows_read_before": str(splits.test.start),
        },
        "backtest": backtest_config_to_dict(backtest),
        "environment": _environment_dict(config),
        "code": dict(code),
        "versions": ppo.package_versions(),
        "determinism": {"torch_use_deterministic_algorithms": True, "torch_num_threads": 1},
    }
    return EvaluationPlan(config, backtest, agent, evaluation, root, dataset_dir, feature_dir,
                          tuple(checkpoints), identity, MappingProxyType(dict(code)))  # fmt: skip


# --------------------------------------------------------------------------
# Evaluation (loads rows dated before test.start only)
# --------------------------------------------------------------------------


def _allocation(ledger: pd.DataFrame, executions: pd.DataFrame, name: str) -> dict[str, Any]:
    weights = ledger.filter(like="weight_")
    targets = executions.filter(like="target_")
    row: dict[str, Any] = {"strategy": name, "executions": len(executions)}
    for column in weights.columns:
        asset = column.removeprefix("weight_")
        row[f"mean_weight_{asset}"] = float(weights[column].mean())
        row[f"max_weight_{asset}"] = float(weights[column].max())
        row[f"mean_target_{asset}"] = float(targets[f"target_{asset}"].mean())
    return row


def _summary(ledger: pd.DataFrame, plan: EvaluationPlan, settings) -> dict[str, Any]:
    return summarize_window(
        ledger,
        initial_capital=settings.initial_capital,
        annual_risk_free_rate=plan.config.environment.risk_free_rate,
        periods_per_year=plan.backtest.periods_per_year,
    )


def evaluate(plan: EvaluationPlan) -> dict[str, Any]:
    """Run the protocol in memory; returns every result. Writes nothing."""
    config, backtest = plan.config, plan.backtest
    splits = config.experiment.splits
    inputs = load_processed_inputs(plan.dataset_dir, config, exclude_test=True)
    outputs = load_feature_outputs(plan.feature_dir, plan.dataset_dir, config, exclude_test=True)
    assert_before_split(inputs.asset_returns.index, inputs.split_labels, splits, "test",
                        "validation evaluation (returns)")  # fmt: skip
    assert_before_split(outputs.features.index, outputs.split_labels, splits, "test",
                        "validation evaluation (features)")  # fmt: skip
    if int((inputs.sessions_spanned > 1).sum()) and not backtest.allow_multi_session_returns:
        raise FeatureDataError("multi-session returns present; refused as in the backtest")
    if _data_ids(plan.dataset_dir, plan.feature_dir) != plan.identity["data"]:
        raise EvaluationError("dataset or feature set changed since the plan")
    returns, dates, labels = inputs.asset_returns, inputs.asset_returns.index, inputs.split_labels
    settings = simulation_settings(config, backtest)
    lag, required = backtest.execution_lag_sessions, backtest.required_history
    window = split_window(labels, dates, "validation", required, lag)
    k0, x0, e = window["k0"], window["x0"], window["e"]
    if set(labels.iloc[window["s"] : e + 1]) != {"validation"}:
        raise EvaluationError("the evaluation window holds rows outside the validation split")
    max_weight = config.environment.constraints.max_weight

    ledgers, baseline_rows, policy_rows, allocations = [], [], [], []
    for strategy in backtest.strategies:
        targets, dropped = strategy_targets(strategy, returns, k0, e, lag, max_weight)
        result = simulate(returns, targets, lag=lag, window=(x0, e), settings=settings)
        summary = _summary(result.ledger, plan, settings)
        baseline_rows.append({"strategy": strategy.name, "rebalance": strategy.rebalance,
                              "decisions": len(targets), "decisions_dropped": dropped,
                              **_flatten(summary)})  # fmt: skip
        ledgers.append(result.ledger.assign(kind="baseline", strategy=strategy.name))
        allocations.append(_allocation(result.ledger, result.executions, strategy.name))

    for checkpoint in plan.checkpoints:
        name = f"ppo_c{checkpoint.configuration}_s{checkpoint.seed}"
        model_path = checkpoint.directory / "model.zip"
        if cache.file_sha256(model_path) != checkpoint.model_sha256:
            raise EvaluationError(f"{name}: model.zip changed since the plan")
        scaler = FeatureScaler.load(checkpoint.directory / "scaler.json")
        env = PortfolioEnv(returns, outputs.features, outputs.regimes["regime"], labels,
                           split="validation", scaler=scaler, settings=settings, lag=lag,
                           required_history=required)  # fmt: skip
        if (env.first_decision, env.first_execution, env.last_row) != (k0, x0, e):
            raise EvaluationError(f"{name}: environment window differs from the common window")
        model = PPO.load(model_path, device="cpu")
        if model.action_space.shape != env.action_space.shape:
            raise EvaluationError(f"{name}: checkpoint action space {model.action_space}")
        observation, _ = env.reset(seed=0)
        targets, finished = {}, False
        while not finished:
            action, _ = model.predict(observation, deterministic=True)
            observation, _, finished, truncated, info = env.step(action)
            if truncated:
                raise EvaluationError(f"{name}: unexpected truncation")
            targets[int(dates.get_loc(info["decision_date"]))] = info["target"][:-1]
        result = simulate(returns, targets, lag=lag, window=(x0, e), settings=settings)
        own = env.ledger_frame()
        if not (np.array_equal(own["value"].to_numpy(), result.ledger["value"].to_numpy())
                and np.array_equal(own.filter(like="weight_").to_numpy(),
                                   result.ledger.filter(like="weight_").to_numpy())):  # fmt: skip
            raise EvaluationError(f"{name}: environment and simulator ledgers differ")
        summary = _summary(result.ledger, plan, settings)
        policy_rows.append({**checkpoint.to_dict(), "strategy": name, "decisions": len(targets),
                            **_flatten(summary)})  # fmt: skip
        ledgers.append(result.ledger.assign(kind="policy", strategy=name))
        allocations.append(_allocation(result.ledger, result.executions, name))

    reference = ledgers[0]["date"].to_numpy()
    if any(not np.array_equal(ledger["date"].to_numpy(), reference) for ledger in ledgers):
        raise EvaluationError("policies and baselines do not share identical evaluation dates")
    summaries = summarise_configurations(
        [{"configuration": r["configuration"], "learning_rate": r["learning_rate"],
          "n_steps": r["n_steps"], "ent_coef": r["ent_coef"], "seed": r["seed"],
          "value": r["annualised.net_sharpe"]} for r in policy_rows]
    )  # fmt: skip
    selection = select_configuration(summaries, plan.evaluation.tie_tolerance)
    return {
        "window": window["info"] | {"first_execution_row": x0, "last_row": e},
        "baselines": baseline_rows,
        "policies": policy_rows,
        "configurations": [s.to_dict() for s in summaries],
        "selection": selection,
        "allocations": allocations,
        "ledgers": pd.concat(ledgers, ignore_index=True),
    }


def _flatten(summary: dict[str, Any]) -> dict[str, Any]:
    flat = {k: v for k, v in summary.items() if k not in ("annualised", "notes")}
    for key, value in (summary.get("annualised") or {}).items():
        if key != "status":
            flat[f"annualised.{key}"] = value
    flat["notes"] = "; ".join(summary.get("notes") or [])
    return flat


def run_evaluation(plan: EvaluationPlan) -> Path:
    """Execute the protocol and write the outputs; never overwrites; clean code required."""
    try:
        run_safety.check_code_policy(dict(plan.code), "full")  # the plan's snapshot
    except run_safety.RunSafetyError as exc:
        raise EvaluationError(f"evaluation needs a clean committed tree: {exc}") from None
    target = plan.output_dir
    if target.exists():
        raise EvaluationError(f"{target} already exists; evaluations are never overwritten")
    lock_path = target.parent / f"{target.name}{run_safety.LOCK_SUFFIX}"
    lock = run_safety.acquire_lock(lock_path, f"validation evaluation {target.name}")
    threads, deterministic = torch.get_num_threads(), torch.are_deterministic_algorithms_enabled()
    staging = target.parent / f"{target.name}{run_safety.STAGING_MARK}{os.getpid()}"
    try:
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        started, clock = dt.datetime.now(dt.UTC), time.perf_counter()
        results = evaluate(plan)
        staging.mkdir(parents=True)
        _write(staging, plan, results, started, time.perf_counter() - clock)
        run_safety.finalise_exclusive(staging, target)
    except BaseException as exc:
        run_safety.quarantine(target.parent, [staging], target.name,
                              f"evaluation failed: {type(exc).__name__}: {exc}")  # fmt: skip
        raise
    finally:
        torch.set_num_threads(threads)
        torch.use_deterministic_algorithms(deterministic)
        run_safety.release_lock(lock_path, lock)
    return target


def _write(directory: Path, plan, results, started, seconds) -> None:
    pd.DataFrame(results["policies"]).to_csv(directory / "policy_metrics.csv", index=False)
    pd.DataFrame(results["baselines"]).to_csv(directory / "baseline_metrics.csv", index=False)
    pd.DataFrame(
        [{k: v for k, v in c.items() if k != "values_by_seed"} | {
            f"seed_{s}": v for s, v in c["values_by_seed"].items()}
         for c in results["configurations"]]
    ).to_csv(directory / "configuration_summary.csv", index=False)  # fmt: skip
    pd.DataFrame(results["allocations"]).to_csv(directory / "allocations.csv", index=False)
    cache.write_csv(results["ledgers"], directory / "ledgers.csv")
    document = {
        "status": STATUS,
        "evaluation_id": plan.evaluation_id,
        "protocol_hash": plan.protocol_hash,
        "window": results["window"],
        "selection": results["selection"],
        "configurations": results["configurations"],
        "baselines": results["baselines"],
        "policies": results["policies"],
    }
    cache.write_json(json.loads(json.dumps(document, default=str)), directory / "evaluation.json")
    cache.write_json(
        {"evaluation_id": plan.evaluation_id, "protocol_hash": plan.protocol_hash,
         **plan.identity,
         "started_at": started.isoformat(timespec="seconds"), "wall_seconds": round(seconds, 3),
         "files_sha256": {n: cache.file_sha256(directory / n) for n in EVALUATION_FILES
                          if n != "metadata.json"}},
        directory / "metadata.json",
    )  # fmt: skip


# --------------------------------------------------------------------------
# Command line: python scripts/evaluate_validation.py
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or run the PPO validation evaluation.")
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--feature-dir", type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true", help="verify checkpoints; no data rows")
    action.add_argument("--execute", action="store_true", help="LOADS VALIDATION ROWS")
    parser.add_argument("--confirm-validation-evaluation", action="store_true",
                        help="required with --execute: the evaluation is authorised")  # fmt: skip
    args = parser.parse_args(argv)
    if args.execute and not args.confirm_validation_evaluation:
        print("--execute needs --confirm-validation-evaluation", file=sys.stderr)
        return 2
    try:
        plan = plan_evaluation(args.config_dir, args.dataset_dir, args.feature_dir)
    except EXPECTED_FAILURES as exc:
        print(f"EVALUATION FAILED (plan): {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.plan:
        e = plan.evaluation
        splits = plan.config.experiment.splits
        code = plan.code
        print(f"PLAN (no data rows loaded, nothing written): evaluation {plan.evaluation_id}")
        print(f"  protocol hash {plan.protocol_hash} (protocol_version {e.protocol_version})")
        print(
            f"  grid {e.grid_id}: {len(plan.checkpoints)} checkpoints verified "
            f"(trained at {plan.identity['grid']['grid_code'].get('commit', '')[:7]})"
        )
        print(
            f"  split validation {splits.validation.start}..{splits.validation.end}; rows read "
            f"only before {splits.test.start}; test split sealed"
        )
        print(f"  baselines: {[s.name for s in plan.backtest.strategies]}")
        print(
            f"  actions {e.policy_actions}; selection {e.selection_metric} "
            f"{e.seed_aggregation} over seeds; tie tolerance {e.tie_tolerance:g}"
        )
        print(f"  code {code.get('commit')} dirty {code.get('dirty')}; output {plan.output_dir}")
        return 0
    try:
        target = run_evaluation(plan)
    except EXPECTED_FAILURES as exc:
        print(f"EVALUATION FAILED (execute): {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"evaluation written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
