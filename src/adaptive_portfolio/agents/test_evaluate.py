"""Separate, pre-registered test evaluator (milestone D; Gate 3; ``rl`` extra).

This module is **separate from the D-076 validation evaluator**, which it reuses but never
changes. It evaluates exactly the candidate checkpoints of a **frozen** pre-registration
(``configs/preregistration.yaml``) and the conventional baselines on the **test** split, once.

Guards:

* ``--plan`` reads configuration, the pre-registration, the validation evaluation's metadata,
  run directories and dataset/feature metadata only. **It reads no data rows** and writes
  nothing. It lists every blocker (open items, draft status) and the provisional evaluation id.
* ``--execute`` refuses unless all of these hold:

  - the pre-registration is ``frozen`` with every item ACCEPTED;
  - its content SHA-256 equals ``--preregistration-sha256``;
  - the working tree is clean and HEAD equals ``--expected-commit``;
  - ``--confirm-test-unsealing`` is given;
  - the candidate checkpoints match the validation selection and pass provenance and
    compatibility checks;
  - no test evaluation exists yet for this pre-registration (single-run rule).
* There is **no model selection, tuning or retraining**: the candidate is fixed by the
  pre-registration. Rows after ``test.end`` are refused.

Primary scenario: the D-076 conventions on the test window:
- deterministic actions; start in cash, with the funding trade charged;
- lag 1, 15 bps, the 0.40 target cap;
- mark to market at the last test row;
- annualised Sharpe with N = 252 and rf = 0, funding row excluded.

The environment and simulator ledgers must agree exactly.

Secondary scenarios (pre-registered; descriptive):
- **fixed-action cost levels (D-083):** the primary run's decided targets of every policy and
  baseline are replayed through the simulator at each pre-registered cost level. Actions are
  identical across cost levels; this does **not** model a policy that adapts to costs. The
  level equal to the primary cost must reproduce the primary ledgers exactly;
- **re-simulated execution lags of at least 1** and **baseline target caps** (none are
  pre-registered under D-083; the trained PPO cap is never changed).

A secondary scenario that cannot be computed is recorded as such; it never aborts the primary.
An undefined primary metric (e.g. a zero-variance Sharpe) aborts the run: nothing is written.

Primary comparison (D-083): the median over the candidate seeds of the annualised net Sharpe
minus the primary baseline's annualised net Sharpe, with a paired moving-block bootstrap
percentile interval (no p-values). The other baselines get descriptive point differences only.

Uncertainty, stress windows, regime summaries and concentration follow the pre-registration
(``evaluation.uncertainty``, ``evaluation.risk``, ``explainability.regime_analysis``).
Outputs go to ``data/processed/test_evaluations/<evaluation_id>/``. They are never overwritten,
and :func:`verify_test_evaluation` recomputes them independently.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
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

from adaptive_portfolio.agents import evaluate as ev
from adaptive_portfolio.agents import ppo, run_safety
from adaptive_portfolio.agents.provenance import verify_checkpoint
from adaptive_portfolio.config import (
    BacktestConfig,
    ConfigError,
    PreregistrationConfig,
    ProjectConfig,
    load_agent_config,
    load_backtest_config,
    load_evaluation_config,
    load_preregistration,
    load_project_config,
)
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.boundaries import DataBoundaryError
from adaptive_portfolio.data.pipeline import project_root_for, resolve_path
from adaptive_portfolio.environment.observation import FeatureScaler
from adaptive_portfolio.environment.portfolio_env import PortfolioEnv
from adaptive_portfolio.environment.rewards import RewardError
from adaptive_portfolio.evaluation import risk, uncertainty
from adaptive_portfolio.evaluation.backtest import (
    _environment_dict,
    backtest_config_to_dict,
    simulation_settings,
    split_window,
    strategy_targets,
)
from adaptive_portfolio.evaluation.bootstrap_reference import reference_moving_block_draws
from adaptive_portfolio.evaluation.metrics import sharpe_ratio
from adaptive_portfolio.evaluation.simulator import SimulationError, simulate
from adaptive_portfolio.explainability import regime_analysis
from adaptive_portfolio.features.engineering import FeatureDataError
from adaptive_portfolio.features.pipeline import (
    load_feature_outputs,
    load_processed_inputs,
    locate_dataset_dir,
)

SCHEMA_VERSION = 1
EVALUATOR_VERSION = 1
TEST_FILES = (
    "evaluation.json", "policy_metrics.csv", "baseline_metrics.csv", "primary_comparison.csv",
    "descriptive_differences.csv", "bootstrap_draws.csv", "stress_windows.csv",
    "regime_summary.csv", "regime_labels.csv", "allocations.csv", "concentration.csv",
    "scenarios.csv", "ledgers.csv", "boundary_evidence.json", "log.jsonl", "metadata.json",
)  # fmt: skip
NOTES = (
    "Five seeds of one configuration share one market history; they are not five independent "
    "samples.",
    "The interval reflects time-series resampling under moving-block bootstrap assumptions "
    "(stationarity, dependence shorter than the block); it is not a significance test, not "
    "causal, and says nothing beyond the evaluated period.",
    "Cost sensitivity replays identical decided targets (fixed-action accounting); it does not "
    "model a policy that adapts its actions to costs.",
    "Equal-weight comparisons are descriptive point differences without intervals.",
    "Stress windows are descriptive slices of the single test history, not independent tests.",
)
STATUS = (
    "FINAL TEST EVALUATION (Gate 3) under the frozen pre-registration named in metadata.json. "
    "Every pre-registered result is reported regardless of outcome. Simulated historical backtest; "
    "not live trading and not financial advice."
)


class TestEvaluationError(RuntimeError):
    """Raised when the test evaluation cannot proceed exactly as pre-registered."""

    __test__ = False  # not a pytest test class


EXPECTED_FAILURES = (
    TestEvaluationError, DataBoundaryError, FeatureDataError, ConfigError,
    run_safety.RunSafetyError, uncertainty.UncertaintyError, risk.RiskError,
    regime_analysis.RegimeAnalysisError, FileNotFoundError,
)  # fmt: skip


@dataclass(frozen=True)
class TestPlan:
    __test__ = False

    config: ProjectConfig
    backtest: BacktestConfig
    preregistration: PreregistrationConfig
    project_root: Path
    dataset_dir: Path
    feature_dir: Path
    checkpoints: tuple[Mapping[str, Any], ...]
    identity: Mapping[str, Any]
    code: Mapping[str, Any]
    blockers: tuple[str, ...]

    @property
    def evaluation_id(self) -> str:
        return cache.short_hash(dict(self.identity))

    @property
    def output_root(self) -> Path:
        root = Path(self.preregistration.value("outputs", "root"))
        return resolve_path(root, self.project_root)

    @property
    def output_dir(self) -> Path:
        return self.output_root / self.evaluation_id


# --------------------------------------------------------------------------
# Plan (no data rows)
# --------------------------------------------------------------------------


def _verified_dir(directory: Path) -> dict[str, Any]:
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    files = meta.get("files_sha256") or {}
    bad = [n for n, h in files.items() if cache.file_sha256(directory / n) != h]
    if not files or bad:
        raise TestEvaluationError(f"{directory}: file hashes do not match metadata: {bad}")
    return meta


def plan_test_evaluation(
    config_dir: Path, preregistration_path: Path | None = None,
    dataset_dir: Path | None = None, feature_dir: Path | None = None,
) -> TestPlan:  # fmt: skip
    """Verify the candidate and compute the identity. Reads no data rows; drafts allowed."""
    config_dir = Path(config_dir)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    agent = load_agent_config(config_dir / "agent.yaml")
    evaluation = load_evaluation_config(config_dir / "evaluation.yaml")
    ev._check_conventions(config, backtest)
    prereg = load_preregistration(preregistration_path or config_dir / "preregistration.yaml")
    root = project_root_for(config_dir)
    dataset_dir = Path(dataset_dir or locate_dataset_dir(config, root))
    feature_dir = Path(feature_dir or ppo._default_feature_dir(config_dir, root, dataset_dir))
    data_ids = ev._data_ids(dataset_dir, feature_dir)
    candidate = prereg.items["candidate"]
    problems: list[str] = []
    # Selection provenance: the candidate is exactly the validation selection of D-076.
    validation_dir = (
        resolve_path(evaluation.output_dir, root) / candidate["validation_evaluation_id"]
    )
    vmeta = _verified_dir(validation_dir)
    vdoc = json.loads((validation_dir / "evaluation.json").read_text(encoding="utf-8"))
    selected = vdoc["selection"]["selected_configuration"]
    if selected != candidate["configuration"]:
        problems.append(
            f"candidate configuration {candidate['configuration']} != selected {selected}"
        )
    if vmeta["grid"]["grid_id"] != candidate["grid_id"]:
        problems.append("candidate grid id differs from the validation evaluation")
    recorded = sorted(({"seed": c["seed"], "run_id": c["run_id"], "model_sha256": c["model_sha256"]}
                       for c in vmeta["checkpoints"] if c["configuration"] == selected),
                      key=lambda c: c["seed"])  # fmt: skip
    if recorded != list(candidate["checkpoints"]):
        problems.append("candidate checkpoints differ from the validation selection's checkpoints")
    experiments = resolve_path(agent.output_dir, root)
    checkpoints = []
    for c in candidate["checkpoints"]:
        found = verify_checkpoint(experiments / c["run_id"], config, backtest,
                                  expected_model_sha256=c["model_sha256"],
                                  dataset_dir=dataset_dir, feature_dir=feature_dir)  # fmt: skip
        problems += [f"{c['run_id']}: {p}" for p in found]
        checkpoints.append(MappingProxyType({**c, "directory": experiments / c["run_id"]}))
    regimes = prereg.items["regimes"]
    if cache.file_sha256(feature_dir / "regime_thresholds.json") != regimes["thresholds_sha256"]:
        problems.append("regime_thresholds.json differs from the pre-registered threshold hash")
    test = config.experiment.splits.test
    for w in prereg.items["stress_windows"]["windows"]:
        if not (str(test.start) <= w["peak_close"] and w["trough_close"] <= str(test.end)):
            problems.append(f"stress window {w['name']} lies outside the test split")
    comparator = prereg.value("primary_endpoint", "primary_baseline")
    if comparator not in [s.name for s in backtest.strategies]:
        problems.append(f"primary baseline {comparator!r} is not a configured baseline")
    primary_bps = round(simulation_settings(config, backtest).cost_rate * 10_000, 9)
    if primary_bps not in [round(b, 9) for b in prereg.value("cost_sensitivity", "total_bps")]:
        problems.append(
            f"cost levels must include the primary {primary_bps:g} bps (identity check)"
        )
    if problems:
        raise TestEvaluationError("candidate or protocol checks failed; nothing is evaluated:\n"
                                  "  - " + "\n  - ".join(problems))  # fmt: skip
    provenance = run_safety.code_provenance(root)
    code = {k: provenance.get(k) for k in ("git_available", "commit", "dirty", "diff_sha256")}
    identity = {
        "schema_version": SCHEMA_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "preregistration_sha256": prereg.sha256(),
        "protocol_hash": prereg.protocol_hash(),
        "candidate": {k: v for k, v in candidate.items() if k not in ("decision", "record")},
        "data": data_ids,
        "splits": {"test": [str(test.start), str(test.end)]},
        "backtest": backtest_config_to_dict(backtest),
        "environment": _environment_dict(config),
        "code": dict(code),
        "versions": ppo.package_versions(),
        "determinism": {
            "torch_use_deterministic_algorithms": True,
            "torch_num_threads": 1,
            "bootstrap_chunk": uncertainty.CHUNK,
        },
    }
    blockers = tuple(([f"status is {prereg.status!r}, not 'frozen'"]
                      if prereg.status != "frozen" else []) + prereg.open_items())  # fmt: skip
    return TestPlan(config, backtest, prereg, root, dataset_dir, feature_dir, tuple(checkpoints),
                    MappingProxyType(identity), MappingProxyType(dict(code)), blockers)  # fmt: skip


# --------------------------------------------------------------------------
# Evaluation (reads test rows; only through run_test_evaluation)
# --------------------------------------------------------------------------


def _rows(summary: dict[str, Any], ledger: pd.DataFrame) -> dict[str, Any]:
    return {**ev._flatten(summary), "gross_sharpe_annualised": risk.gross_sharpe(ledger)}


def _summary(ledger: pd.DataFrame, plan: TestPlan, settings) -> dict[str, Any]:
    return ev._summary(ledger, plan, settings)  # same conventions as D-076 (N, rf)


def _run_policy(plan, checkpoint, model, scaler, data, settings, lag, window):
    returns, features, regimes, labels, dates = data
    env = PortfolioEnv(
        returns,
        features,
        regimes,
        labels,
        split="test",
        scaler=scaler,
        settings=settings,
        lag=lag,
        required_history=plan.backtest.required_history,
    )
    if (env.first_decision, env.first_execution, env.last_row) != (window["k0"], window["x0"],
                                                                     window["e"]):  # fmt: skip
        raise TestEvaluationError("environment window differs from the common test window")
    observation, _ = env.reset(seed=0)
    targets, finished = {}, False
    while not finished:
        action, _ = model.predict(observation, deterministic=True)
        observation, _, finished, truncated, info = env.step(action)
        if truncated:
            raise TestEvaluationError("unexpected truncation")
        targets[int(dates.get_loc(info["decision_date"]))] = info["target"][:-1]
    result = simulate(returns, targets, lag=lag, window=(window["x0"], window["e"]),
                      settings=settings)  # fmt: skip
    own = env.ledger_frame()
    if not (np.array_equal(own["value"].to_numpy(), result.ledger["value"].to_numpy())
            and np.array_equal(own.filter(like="weight_").to_numpy(),
                               result.ledger.filter(like="weight_").to_numpy())):  # fmt: skip
        raise TestEvaluationError(f"seed {checkpoint['seed']}: environment and simulator differ")
    return result, targets


def _finite(value: Any) -> bool:
    return isinstance(value, int | float) and bool(np.isfinite(value))


def _metric_row(scenario, strategy, ledger, plan, settings, **extra) -> dict[str, Any]:
    row = {"scenario": scenario, "strategy": strategy, **extra}
    row.update(_rows(_summary(ledger, plan, settings), ledger))
    if not _finite(row["gross_sharpe_annualised"]):
        row["notes"] = "; ".join(filter(None, [row.get("notes"), "gross Sharpe undefined"]))
    return row


def _ledgers_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    numeric = [c for c in a.columns if c in b.columns and pd.api.types.is_numeric_dtype(a[c])]
    return len(a) == len(b) and all(
        np.array_equal(a[c].to_numpy(), b[c].to_numpy(), equal_nan=True) for c in numeric
    )


def _boundary_evidence(plan: TestPlan, labels: pd.Series) -> dict[str, Any]:
    """Rows per split, first and last dates, and the SHA-256 of the files read (execute only)."""
    per_split = {}
    for split in sorted(set(labels.astype(str))):
        dates = labels.index[labels.astype(str) == split]
        per_split[split] = {"rows": len(dates), "first": str(dates.min().date()),
                            "last": str(dates.max().date())}  # fmt: skip
    files = {"returns.csv": plan.dataset_dir / "returns.csv",
             "splits.csv": plan.dataset_dir / "splits.csv",
             "features.csv": plan.feature_dir / "features.csv",
             "regimes.csv": plan.feature_dir / "regimes.csv"}  # fmt: skip
    return {"test_end": str(plan.config.experiment.splits.test.end), "rows_by_split": per_split,
            "files_sha256": {n: cache.file_sha256(f) for n, f in files.items()}}  # fmt: skip


def evaluate_test(plan: TestPlan) -> dict[str, Any]:
    """Run the pre-registered evaluation in memory. **Reads test rows.** Writes nothing."""
    config, backtest, prereg = plan.config, plan.backtest, plan.preregistration
    splits = config.experiment.splits
    inputs = load_processed_inputs(plan.dataset_dir, config)
    outputs = load_feature_outputs(plan.feature_dir, plan.dataset_dir, config, exclude_test=False)
    end = pd.Timestamp(splits.test.end)
    for index in (inputs.asset_returns.index, outputs.features.index):
        if index.max() > end:
            raise DataBoundaryError(f"rows after test.end ({splits.test.end}) are not evaluated")
    if ev._data_ids(plan.dataset_dir, plan.feature_dir) != plan.identity["data"]:
        raise TestEvaluationError("dataset or feature set changed since the plan")
    if int((inputs.sessions_spanned > 1).sum()) and not backtest.allow_multi_session_returns:
        raise FeatureDataError("multi-session returns present; refused as in the backtest")
    returns, dates, labels = inputs.asset_returns, inputs.asset_returns.index, inputs.split_labels
    data = (returns, outputs.features, outputs.regimes["regime"], labels, dates)
    base = simulation_settings(config, backtest)
    lag0, required = backtest.execution_lag_sessions, backtest.required_history
    cap0 = config.environment.constraints.max_weight
    boundary = _boundary_evidence(plan, labels)

    def window_for(lag: int) -> dict[str, Any]:
        window = split_window(labels, dates, "test", required, lag)
        if set(labels.iloc[window["s"] : window["e"] + 1]) != {"test"}:
            raise TestEvaluationError("the test window holds rows outside the test split")
        return window

    models = {c["seed"]: (PPO.load(c["directory"] / "model.zip", device="cpu"),
                          FeatureScaler.load(c["directory"] / "scaler.json"))
              for c in plan.checkpoints}  # fmt: skip
    for c in plan.checkpoints:
        if cache.file_sha256(c["directory"] / "model.zip") != c["model_sha256"]:
            raise TestEvaluationError(f"seed {c['seed']}: model.zip changed since the plan")
    window = window_for(lag0)
    configuration = prereg.value("candidate", "configuration")
    rows, frames, status, decided, executions = [], {}, [], {}, {}

    # Primary scenario: policies through the environment (deterministic), baselines by rule.
    for c in plan.checkpoints:
        model, scaler = models[c["seed"]]
        result, targets = _run_policy(plan, c, model, scaler, data, base, lag0, window)
        label = f"ppo_c{configuration}_s{c['seed']}"
        decided[label] = ("policy", targets)
        rows.append(
            _metric_row(
                "primary",
                label,
                result.ledger,
                plan,
                base,
                kind="policy",
                seed=c["seed"],
                run_id=c["run_id"],
                decisions=len(targets),
            )
        )
        frames[("primary", label)] = result.ledger.assign(scenario="primary", kind="policy",
                                                          strategy=label)  # fmt: skip
        executions[label] = (result.ledger, result.executions)
    for strategy in backtest.strategies:
        targets, dropped = strategy_targets(strategy, returns, window["k0"], window["e"], lag0,
                                            cap0)  # fmt: skip
        result = simulate(returns, targets, lag=lag0, window=(window["x0"], window["e"]),
                          settings=base)  # fmt: skip
        decided[strategy.name] = ("baseline", targets)
        rows.append(_metric_row("primary", strategy.name, result.ledger, plan, base,
                                kind="baseline", decisions=len(targets),
                                decisions_dropped=dropped))  # fmt: skip
        frames[("primary", strategy.name)] = result.ledger.assign(
            scenario="primary", kind="baseline", strategy=strategy.name)  # fmt: skip
        executions[strategy.name] = (result.ledger, result.executions)
    undefined = [r["strategy"] for r in rows if not _finite(r.get("annualised.net_sharpe"))]
    if undefined:
        raise TestEvaluationError(
            f"undefined primary metric (annualised net Sharpe) for "
            f"{undefined}: failed primary evaluation; nothing is written"
        )
    status.append({"scenario": "primary", "kind": "primary", "status": "computed", "lag": lag0,
                   "cost_rate": base.cost_rate, "max_weight": cap0,
                   "first_decision_date": window["info"]["first_decision_date"],
                   "last_return_date": window["info"]["last_return_date"]})  # fmt: skip

    # Fixed-action cost scenarios: replay the primary decided targets (D-083).
    for bps in prereg.value("cost_sensitivity", "total_bps"):
        name = f"fixed_action_cost_{bps:g}bps"
        settings = dataclasses.replace(base, cost_rate=bps / 10_000)
        for label, (kind, targets) in decided.items():
            result = simulate(returns, targets, lag=lag0, window=(window["x0"], window["e"]),
                              settings=settings)  # fmt: skip
            if abs(settings.cost_rate - base.cost_rate) < 1e-15 and not _ledgers_equal(
                    result.ledger, frames[("primary", label)]):  # fmt: skip
                raise TestEvaluationError(
                    f"{label}: the {bps:g} bps replay does not reproduce "
                    "the primary ledger (fixed-action identity failed)"
                )
            rows.append(_metric_row(name, label, result.ledger, plan, settings, kind=kind))
            frames[(name, label)] = result.ledger.assign(scenario=name, kind=kind, strategy=label)
        status.append({"scenario": name, "kind": "fixed_action_accounting", "status": "computed",
                       "lag": lag0, "cost_rate": settings.cost_rate, "max_weight": cap0,
                       "first_decision_date": window["info"]["first_decision_date"],
                       "last_return_date": window["info"]["last_return_date"]})  # fmt: skip

    # Re-simulated scenarios: only if pre-registered (none under D-083).
    for lag in prereg.value("lag_sensitivity", "lags"):
        _resimulate(f"resimulated_lag_{lag}", plan, models, data, base, lag, cap0, True,
                    window_for, rows, frames, status)  # fmt: skip
    for cap in prereg.value("constraint_sensitivity", "baseline_max_weights"):
        settings = dataclasses.replace(
            base, constraints=dataclasses.replace(base.constraints, max_weight=cap)
        )
        _resimulate(f"baseline_cap_{cap:g}", plan, models, data, settings, lag0, cap, False,
                    window_for, rows, frames, status)  # fmt: skip

    stacked = pd.concat(list(frames.values()), ignore_index=True)
    primary = stacked[stacked["scenario"] == "primary"]
    policy_names = [n for n, (k, _) in decided.items() if k == "policy"]
    baseline_names = [s.name for s in backtest.strategies]
    reference = None
    for name in policy_names + baseline_names:
        d = primary.loc[primary["strategy"] == name, "date"].to_numpy()
        if reference is not None and not np.array_equal(d, reference):
            raise TestEvaluationError("primary ledgers do not share identical dates")
        reference = d
    sharpe = {r["strategy"]: r["annualised.net_sharpe"] for r in rows if r["scenario"] == "primary"}
    aggregation = prereg.value("primary_endpoint", "seed_aggregation")
    seeds = [sharpe[n] for n in policy_names]
    endpoint = float(np.median(seeds) if aggregation == "median" else np.mean(seeds))
    comparator = prereg.value("primary_endpoint", "primary_baseline")
    comparison, draws = _primary_comparison(prereg, primary, policy_names, comparator,
                                            endpoint - sharpe[comparator])  # fmt: skip
    descriptive = pd.DataFrame([
        {"baseline": b, "difference": endpoint - sharpe[b],
         "definition": f"{aggregation} seed net Sharpe minus baseline net Sharpe",
         "status": "descriptive point difference; no interval; no inference"}
        for b in baseline_names if b != comparator])  # fmt: skip
    regime, regime_labels = pd.DataFrame(), pd.DataFrame()
    if prereg.value("regimes", "include"):
        calendar = outputs.regimes["regime"]
        regime = regime_analysis.summarise_strategies(
            primary, calendar, lag=lag0, min_sessions=prereg.value("regimes", "min_sessions")
        )
        first = calendar.index.get_loc(pd.Timestamp(primary["date"].min())) - lag0
        last = calendar.index.get_loc(pd.Timestamp(primary["date"].max()))
        regime_labels = calendar.iloc[first : last + 1].rename("regime").reset_index()
    allocations = pd.DataFrame([{"strategy": n, **risk.allocation_summary(led, exe)}
                                for n, (led, exe) in executions.items()])  # fmt: skip
    conc = pd.DataFrame([{"strategy": n, **risk.concentration(led, exe, cap0)}
                         for n, (led, exe) in executions.items()])  # fmt: skip
    return {
        "window": window["info"] | {"first_execution_row": window["x0"], "last_row": window["e"]},
        "primary_endpoint": {
            "metric": "net_sharpe_annualised",
            "seed_aggregation": aggregation,
            "value": endpoint,
            "by_seed": dict(zip(policy_names, seeds, strict=True)),
        },
        "policies": [r for r in rows if r["kind"] == "policy"],
        "baselines": [r for r in rows if r["kind"] == "baseline"],
        "primary_comparison": comparison,
        "descriptive_differences": descriptive,
        "bootstrap_draws": draws,
        "stress_windows": _stress(prereg, primary, policy_names + baseline_names),
        "regime_summary": regime,
        "regime_labels": regime_labels,
        "allocations": allocations,
        "concentration": conc,
        "scenarios": pd.DataFrame(status),
        "ledgers": stacked,
        "boundary_evidence": boundary,
    }


def _resimulate(name, plan, models, data, settings, lag, cap, with_policies, window_for, rows,
                frames, status) -> None:  # fmt: skip
    """A re-simulated secondary scenario; recorded as not computed if it cannot be run."""
    returns = data[0]
    try:
        window = window_for(lag)
        new_rows, new_frames = [], {}
        if with_policies:
            for c in plan.checkpoints:
                model, scaler = models[c["seed"]]
                result, _ = _run_policy(plan, c, model, scaler, data, settings, lag, window)
                label = (
                    f"ppo_c{plan.preregistration.value('candidate', 'configuration')}_s{c['seed']}"
                )
                new_rows.append(_metric_row(name, label, result.ledger, plan, settings,
                                            kind="policy"))  # fmt: skip
                new_frames[(name, label)] = result.ledger.assign(scenario=name, kind="policy",
                                                                 strategy=label)  # fmt: skip
        for strategy in plan.backtest.strategies:
            targets, _ = strategy_targets(strategy, returns, window["k0"], window["e"], lag, cap)
            result = simulate(returns, targets, lag=lag, window=(window["x0"], window["e"]),
                              settings=settings)  # fmt: skip
            new_rows.append(_metric_row(name, strategy.name, result.ledger, plan, settings,
                                        kind="baseline"))  # fmt: skip
            new_frames[(name, strategy.name)] = result.ledger.assign(
                scenario=name, kind="baseline", strategy=strategy.name)  # fmt: skip
    except (RewardError, SimulationError, TestEvaluationError, ValueError) as exc:
        status.append({"scenario": name, "kind": "resimulated",
                       "status": f"not computed: {type(exc).__name__}: {exc}"})  # fmt: skip
        return
    rows += new_rows
    frames.update(new_frames)
    status.append({"scenario": name, "kind": "resimulated", "status": "computed", "lag": lag,
                   "cost_rate": settings.cost_rate, "max_weight": cap,
                   "first_decision_date": window["info"]["first_decision_date"],
                   "last_return_date": window["info"]["last_return_date"]})  # fmt: skip


def _returns_matrix(primary: pd.DataFrame, names: list[str]) -> np.ndarray:
    """Aligned daily net returns after the funding row, one column per strategy."""
    return np.column_stack([
        primary.loc[primary["strategy"] == n, "net_return"].to_numpy(dtype=np.float64)[1:]
        for n in names])  # fmt: skip


def _primary_comparison(prereg, primary, policy_names, comparator, point_from_tables):
    """The D-083 primary comparison: estimate and paired moving-block percentile interval."""
    u = prereg.items["uncertainty"]
    aggregation = prereg.value("primary_endpoint", "seed_aggregation")
    estimand = (f"{aggregation} over seeds {[n.rsplit('_s', 1)[1] for n in policy_names]} of the "
                f"annualised net Sharpe minus the annualised net Sharpe of {comparator}; each "
                "replicate recomputes every Sharpe on the same resampled dates")  # fmt: skip
    base = {"estimand": estimand, "comparator": comparator, "seeds": len(policy_names),
            "p_value": "not reported (D-083)", "notes": " ".join(NOTES)}  # fmt: skip
    if not u["include"]:
        return pd.DataFrame([{**base, "estimate": point_from_tables,
                              "interval": "not pre-registered"}]), pd.DataFrame()  # fmt: skip
    matrix = _returns_matrix(primary, [*policy_names, comparator])
    tables, draws = [], []
    for role, block in [("primary", u["mean_block_length"]),
                        *(("sensitivity", b) for b in u["sensitivity_block_lengths"])]:  # fmt: skip
        point, sample = uncertainty.paired_bootstrap(
            matrix, len(policy_names), method=u["method"], block_length=block,
            resamples=u["resamples"], seed=u["seed"], aggregation=aggregation)  # fmt: skip
        if abs(point[0] - point_from_tables) > 1e-12 * max(1.0, abs(point_from_tables)):
            raise TestEvaluationError("the bootstrap point estimate differs from the metric tables")
        interval = uncertainty.percentile_interval(point[0], sample[:, 0], u["confidence_level"])
        tables.append({**base, **interval, "role": role, "method": u["method"],
                       "block_length": block, "resamples": u["resamples"], "seed": u["seed"],
                       "chunk": uncertainty.CHUNK, "return_periods": len(matrix)})  # fmt: skip
        draws.append(pd.DataFrame({"block_length": block, "draw": np.arange(len(sample)),
                                   f"delta_{aggregation}_seed_sharpe_minus_{comparator}_sharpe":
                                   sample[:, 0]}))  # fmt: skip
    return pd.DataFrame(tables), pd.concat(draws, ignore_index=True)


def _stress(prereg, primary, names):
    s = prereg.items["stress_windows"]
    rows = []
    if s["include"]:
        for w in s["windows"]:
            for n in names:
                ledger = primary[primary["strategy"] == n]
                rows.append({"window": w["name"], "strategy": n,
                             **risk.stress_window(ledger, w["peak_close"], w["trough_close"],
                                                  w["expected_sessions"])})  # fmt: skip
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Execute (all guards) and verify
# --------------------------------------------------------------------------


def run_test_evaluation(
    plan: TestPlan, *, preregistration_sha256: str, expected_commit: str
) -> Path:
    """The single pre-registered test run. Refuses unless every guard holds."""
    if plan.blockers:
        raise TestEvaluationError("the pre-registration is not frozen: " + "; ".join(plan.blockers))
    if preregistration_sha256 != plan.preregistration.sha256():
        raise TestEvaluationError("the pre-registration hash differs from the authorised one")
    try:
        run_safety.check_code_policy(dict(plan.code), "full")
    except run_safety.RunSafetyError as exc:
        raise TestEvaluationError(f"the test run needs a clean committed tree: {exc}") from None
    commit = str(plan.code.get("commit") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") or commit != expected_commit:
        raise TestEvaluationError(
            f"HEAD {commit[:12]} is not the authorised commit {expected_commit}"
        )
    target = plan.output_dir
    root = plan.output_root
    if target.exists():
        raise TestEvaluationError(f"{target} already exists; the test is evaluated once")
    for previous in root.glob("*/metadata.json") if root.is_dir() else []:
        meta = json.loads(previous.read_text(encoding="utf-8"))
        if meta.get("preregistration_sha256") == plan.preregistration.sha256():
            raise TestEvaluationError(f"a test evaluation for this pre-registration exists: "
                                      f"{previous.parent.name}")  # fmt: skip
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / f"{target.name}{run_safety.LOCK_SUFFIX}"
    lock = run_safety.acquire_lock(lock_path, f"test evaluation {target.name}")
    threads, deterministic = torch.get_num_threads(), torch.are_deterministic_algorithms_enabled()
    staging = root / f"{target.name}{run_safety.STAGING_MARK}{os.getpid()}"
    log: list[dict[str, Any]] = []
    try:
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        started, clock = dt.datetime.now(dt.UTC), time.perf_counter()
        log.append({"event": "start", "at": started.isoformat(timespec="seconds")})
        results = evaluate_test(plan)
        log.append({"event": "evaluated", "seconds": round(time.perf_counter() - clock, 3)})
        staging.mkdir(parents=True)
        _write(staging, plan, results, started, time.perf_counter() - clock, log)
        run_safety.finalise_exclusive(staging, target)
    except BaseException as exc:
        run_safety.quarantine(root, [staging], target.name,
                              f"test evaluation failed: {type(exc).__name__}: {exc}")  # fmt: skip
        raise
    finally:
        torch.set_num_threads(threads)
        torch.use_deterministic_algorithms(deterministic)
        run_safety.release_lock(lock_path, lock)
    return target


def _write(directory: Path, plan: TestPlan, results: dict, started, seconds, log) -> None:
    tables = {"policy_metrics.csv": pd.DataFrame(results["policies"]),
              "baseline_metrics.csv": pd.DataFrame(results["baselines"]),
              "primary_comparison.csv": results["primary_comparison"],
              "descriptive_differences.csv": results["descriptive_differences"],
              "bootstrap_draws.csv": results["bootstrap_draws"],
              "stress_windows.csv": results["stress_windows"],
              "regime_summary.csv": results["regime_summary"],
              "regime_labels.csv": results["regime_labels"],
              "allocations.csv": results["allocations"],
              "concentration.csv": results["concentration"],
              "scenarios.csv": results["scenarios"], "ledgers.csv": results["ledgers"]}  # fmt: skip
    for name, frame in tables.items():
        cache.write_csv(frame, directory / name)
    cache.write_json(results["boundary_evidence"], directory / "boundary_evidence.json")
    document = {"status": STATUS, "evaluation_id": plan.evaluation_id,
                "preregistration_sha256": plan.preregistration.sha256(),
                "protocol_hash": plan.preregistration.protocol_hash(),
                "selection": "none (candidate fixed by the pre-registration)",
                "window": results["window"], "primary_endpoint": results["primary_endpoint"],
                "primary_comparison": results["primary_comparison"].to_dict(orient="records"),
                "descriptive_differences":
                    results["descriptive_differences"].to_dict(orient="records"),
                "notes": list(NOTES)}  # fmt: skip
    cache.write_json(json.loads(json.dumps(document, default=str)), directory / "evaluation.json")
    log.append({"event": "written", "files": [*sorted(tables), "boundary_evidence.json",
                                              "evaluation.json"]})  # fmt: skip
    (directory / "log.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in log), encoding="utf-8"
    )
    cache.write_json(
        {"evaluation_id": plan.evaluation_id,
         "preregistration_sha256": plan.preregistration.sha256(),
         "protocol_hash": plan.preregistration.protocol_hash(), **dict(plan.identity),
         "started_at": started.isoformat(timespec="seconds"), "wall_seconds": round(seconds, 3),
         "files_sha256": {n: cache.file_sha256(directory / n) for n in TEST_FILES
                          if n != "metadata.json"}},
        directory / "metadata.json",
    )  # fmt: skip


def _executions_from_ledger(ledger: pd.DataFrame) -> pd.DataFrame:
    """Executed targets rebuilt from post-trade (end-of-row) weights on execution rows."""
    executed = ledger[ledger["rebalanced"].astype(bool)]
    weights = executed.filter(like="weight_").drop(columns="weight_CASH")
    return weights.rename(columns=lambda c: "target_" + c.removeprefix("weight_"))


def _close(a, b, tol=1e-12) -> bool:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    return a.shape == b.shape and bool(np.allclose(a, b, rtol=tol, atol=tol, equal_nan=True))


def verify_test_evaluation(directory: Path, preregistration: PreregistrationConfig) -> list[str]:
    """Independent re-check of a written test evaluation (no data rows beyond its own outputs).

    Recomputes from the saved ledgers: every Sharpe, the endpoint, accounting identities
    (costs, net returns, funding row, execution lag), the fixed-action identity, the primary
    estimate and its bootstrap replicates (main implementation exactly; the loop-based
    reference within 1e-9), the interval, descriptive differences, allocations, concentration,
    stress windows and regime summaries.
    """
    directory = Path(directory)
    problems: list[str] = []
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if sorted(p.name for p in directory.iterdir()) != sorted(TEST_FILES):
        problems.append("unexpected file set")
    problems += [f"{n}: hash mismatch" for n, h in meta["files_sha256"].items()
                 if cache.file_sha256(directory / n) != h]  # fmt: skip
    identity = {k: v for k, v in meta.items() if k not in (
        "evaluation_id", "preregistration_sha256", "protocol_hash", "started_at", "wall_seconds",
        "files_sha256")}  # fmt: skip
    identity = {**identity, "preregistration_sha256": meta["preregistration_sha256"],
                "protocol_hash": meta["protocol_hash"]}  # fmt: skip
    if cache.short_hash(identity) != meta["evaluation_id"] or directory.name != meta[
            "evaluation_id"]:  # fmt: skip
        problems.append("evaluation id is not the hash of the identity")
    if meta["preregistration_sha256"] != preregistration.sha256():
        problems.append("written under a different pre-registration")
    rt = {"float_precision": "round_trip"}
    ledgers = pd.read_csv(directory / "ledgers.csv", **rt)
    start, end = meta["splits"]["test"]
    if ledgers["date"].min() < start or ledgers["date"].max() > end:
        problems.append("ledger dates outside the test split")
    metrics = pd.concat([pd.read_csv(directory / "policy_metrics.csv", **rt),
                         pd.read_csv(directory / "baseline_metrics.csv", **rt)])  # fmt: skip
    for _, row in metrics.iterrows():
        led = ledgers[(ledgers["scenario"] == row["scenario"])
                      & (ledgers["strategy"] == row["strategy"])]  # fmt: skip
        net = sharpe_ratio(led["net_return"].to_numpy()[1:], 252, annual_risk_free_rate=0.0)
        if net != row["annualised.net_sharpe"] or not _close(
            risk.gross_sharpe(led), row["gross_sharpe_annualised"], 0
        ):
            problems.append(f"{row['scenario']}/{row['strategy']}: Sharpe does not recompute")
    scenarios = pd.read_csv(directory / "scenarios.csv", **rt).set_index("scenario")
    primary_rate = scenarios.loc["primary", "cost_rate"]
    primary = ledgers[ledgers["scenario"] == "primary"]
    for (scenario, strategy), led in ledgers.groupby(["scenario", "strategy"], sort=False):
        rate, lag = scenarios.loc[scenario, "cost_rate"], int(scenarios.loc[scenario, "lag"])
        where = f"{scenario}/{strategy}"
        if not _close(led["cost_fraction"], rate * led["traded_notional"], 1e-15):
            problems.append(f"{where}: cost != rate x traded notional")
        net = (1 + led["gross_return"]) * (1 - led["cost_fraction"]) - 1
        if not _close(led["net_return"], net, 1e-14):
            problems.append(f"{where}: net return identity fails")
        if not bool(led["rebalanced"].iloc[0]) or not led["decision_date"].iloc[0] < led[
                "date"].iloc[0]:  # fmt: skip
            problems.append(f"{where}: the first row is not the funding execution")
        dates = list(led["date"])
        for _, r in led[led["rebalanced"].astype(bool)].iloc[1:].iterrows():
            if r["decision_date"] not in dates or (
                dates.index(r["date"]) - dates.index(r["decision_date"]) != lag
            ):
                problems.append(f"{where}: execution {r['date']} is not lag {lag} after its "
                                "decision")  # fmt: skip
                break
        if scenarios.loc[scenario, "kind"] == "fixed_action_accounting":
            base = primary[primary["strategy"] == strategy]
            same_targets = _close(_executions_from_ledger(led), _executions_from_ledger(base), 0)
            if not same_targets:
                problems.append(f"{where}: decided targets differ from the primary run")
            if rate == primary_rate and not _close(
                led.select_dtypes("number"), base.select_dtypes("number"), 0
            ):
                problems.append(f"{where}: the primary-cost replay does not equal the primary")
    document = json.loads((directory / "evaluation.json").read_text(encoding="utf-8"))
    by_seed = document["primary_endpoint"]["by_seed"]
    aggregation = document["primary_endpoint"]["seed_aggregation"]
    values = list(by_seed.values())
    endpoint = float(np.median(values) if aggregation == "median" else np.mean(values))
    if endpoint != document["primary_endpoint"]["value"]:
        problems.append("primary endpoint does not recompute")
    baseline_sharpe = metrics[metrics["scenario"] == "primary"].set_index("strategy")[
        "annualised.net_sharpe"]  # fmt: skip
    comparison = pd.read_csv(directory / "primary_comparison.csv", **rt)
    comparator = preregistration.value("primary_endpoint", "primary_baseline")
    if (comparison["p_value"] != "not reported (D-083)").any():
        problems.append("a p-value is reported")
    expected = endpoint - baseline_sharpe[comparator]
    if not _close(comparison["estimate"].to_numpy(), np.full(len(comparison), expected)):
        problems.append("primary estimate does not recompute")
    descriptive = pd.read_csv(directory / "descriptive_differences.csv", **rt)
    for _, r in descriptive.iterrows():
        if not _close(r["difference"], endpoint - baseline_sharpe[r["baseline"]]):
            problems.append(f"descriptive difference for {r['baseline']} does not recompute")
        if r["baseline"] == comparator:
            problems.append("the primary baseline appears among descriptive differences")
    u = preregistration.items["uncertainty"]
    if u["include"]:
        matrix = _returns_matrix(primary, [*by_seed, comparator])
        saved = pd.read_csv(directory / "bootstrap_draws.csv", **rt)
        for (_, row), (block, frame) in zip(comparison.iterrows(),
                                            saved.groupby("block_length", sort=False),
                                            strict=True):  # fmt: skip
            column = frame.filter(like="delta_").to_numpy()[:, 0]
            _, again = uncertainty.paired_bootstrap(
                matrix, len(by_seed), method=u["method"], block_length=int(block),
                resamples=u["resamples"], seed=u["seed"], aggregation=aggregation)  # fmt: skip
            if not np.array_equal(again[:, 0], column):
                problems.append(f"bootstrap replicates (block {block}) do not reproduce")
            if u["method"] == "moving_block_bootstrap" and aggregation == "median":
                reference = reference_moving_block_draws(
                    matrix[:, :-1].T,
                    matrix[:, -1],
                    block_length=int(block),
                    resamples=u["resamples"],
                    seed=u["seed"],
                    chunk=uncertainty.CHUNK,
                )
                if not _close(reference, column, 1e-9):
                    problems.append(f"reference bootstrap (block {block}) disagrees")
            interval = uncertainty.percentile_interval(row["estimate"], column,
                                                       u["confidence_level"])  # fmt: skip
            if not _close(
                [interval["ci_low"], interval["ci_high"]], [row["ci_low"], row["ci_high"]], 0
            ):
                problems.append(f"interval (block {block}) does not recompute")
    weight_cap = float(meta["environment"]["constraints"]["max_weight"])
    allocations = pd.read_csv(directory / "allocations.csv", **rt).set_index("strategy")
    conc = pd.read_csv(directory / "concentration.csv", **rt).set_index("strategy")
    for strategy, led in primary.groupby("strategy", sort=False):
        executed = _executions_from_ledger(led)
        again = pd.Series(risk.allocation_summary(led, executed))
        if not _close(again.to_numpy(), allocations.loc[strategy, again.index].to_numpy()):
            problems.append(f"{strategy}: allocations do not recompute")
        c = pd.Series(risk.concentration(led, executed, weight_cap))
        if not _close(c.to_numpy(), conc.loc[strategy, c.index].to_numpy()):
            problems.append(f"{strategy}: concentration does not recompute")
    stress = pd.read_csv(directory / "stress_windows.csv", **rt)
    for w in preregistration.items["stress_windows"]["windows"] if len(stress) else []:
        for strategy, led in primary.groupby("strategy", sort=False):
            again = risk.stress_window(led, w["peak_close"], w["trough_close"],
                                       w["expected_sessions"])  # fmt: skip
            saved_row = stress[(stress["window"] == w["name"]) & (stress["strategy"] == strategy)]
            if saved_row.empty or saved_row["status"].iloc[0] != again["status"]:
                problems.append(f"stress {w['name']}/{strategy}: status does not recompute")
            elif again["status"] == "computed" and not _close(
                [again[k] for k in ("net_return", "max_drawdown", "annualised_volatility")],
                saved_row[["net_return", "max_drawdown", "annualised_volatility"]].iloc[0],
            ):
                problems.append(f"stress {w['name']}/{strategy}: metrics do not recompute")
    if preregistration.value("regimes", "include"):
        labels = pd.read_csv(directory / "regime_labels.csv")
        calendar = pd.Series(labels["regime"].to_numpy(), index=pd.to_datetime(labels["date"]))
        primary_dt = primary.assign(date=pd.to_datetime(primary["date"]))
        again = regime_analysis.summarise_strategies(
            primary_dt, calendar, lag=int(scenarios.loc["primary", "lag"]),
            min_sessions=preregistration.value("regimes", "min_sessions"))  # fmt: skip
        saved = pd.read_csv(directory / "regime_summary.csv", **rt)
        numeric = [c for c in again.columns if pd.api.types.is_numeric_dtype(again[c])
                   and c != "sufficient"]  # fmt: skip
        if not _close(again[numeric], saved[numeric]):
            problems.append("regime summaries do not recompute")
    return problems


# --------------------------------------------------------------------------
# Command line: python scripts/evaluate_test.py
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan, run (once) or verify the test evaluation.")
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument("--preregistration", type=Path)
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--feature-dir", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="no data rows; nothing written")
    mode.add_argument("--execute", action="store_true", help="READS THE SEALED TEST PERIOD")
    mode.add_argument("--verify", type=Path, metavar="DIR", help="re-check a written evaluation")
    parser.add_argument("--confirm-test-unsealing", action="store_true")
    parser.add_argument("--preregistration-sha256")
    parser.add_argument("--expected-commit")
    args = parser.parse_args(argv)
    if args.execute and not (args.confirm_test_unsealing and args.preregistration_sha256
                             and args.expected_commit):  # fmt: skip
        print(
            "--execute needs --confirm-test-unsealing, --preregistration-sha256 and "
            "--expected-commit (from the explicit unsealing authorisation)",
            file=sys.stderr,
        )
        return 2
    try:
        if args.verify:
            prereg = load_preregistration(args.preregistration or args.config_dir /
                                          "preregistration.yaml")  # fmt: skip
            problems = verify_test_evaluation(args.verify, prereg)
            print("verify: all checks passed" if not problems else "VERIFY FAILED:\n  - "
                  + "\n  - ".join(problems))  # fmt: skip
            return 0 if not problems else 1
        plan = plan_test_evaluation(args.config_dir, args.preregistration, args.dataset_dir,
                                    args.feature_dir)  # fmt: skip
        if args.plan:
            p = plan.preregistration
            print("PLAN (no data rows loaded, nothing written; the test period stays sealed)")
            print(f"  pre-registration: status {p.status}; sha256 {p.sha256()}")
            print(f"  protocol hash {p.protocol_hash()}; evaluator version {EVALUATOR_VERSION}")
            print(
                f"  candidate: configuration {p.value('candidate', 'configuration')}, "
                f"{len(plan.checkpoints)} checkpoints verified (provenance and compatibility)"
            )
            print(f"  data: {plan.identity['data']}")
            print(f"  code: {plan.code.get('commit')} dirty {plan.code.get('dirty')}")
            print(f"  evaluation id (provisional; changes with code, data or pre-registration): "
                  f"{plan.evaluation_id}")  # fmt: skip
            print(f"  output: {plan.output_dir}")
            if plan.blockers:
                print(f"  EXECUTION REFUSED until resolved ({len(plan.blockers)}):")
                for b in plan.blockers:
                    print(f"    - {b}")
            return 0
        target = run_test_evaluation(plan, preregistration_sha256=args.preregistration_sha256,
                                     expected_commit=args.expected_commit)  # fmt: skip
    except EXPECTED_FAILURES as exc:
        print(f"TEST EVALUATION FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"test evaluation written to {target}")
    return 0
