"""Checkpoint provenance and configuration compatibility (milestone F; no ``rl`` extra needed).

:func:`verify_checkpoint` reads only a run directory's metadata, configuration, scaler and file
hashes (never a model's weights and never data rows) and reports every problem found:

* run integrity (:func:`run_safety.verify_run_dir`): files, status, budget, split, file hashes;
* identity: ``run_config.json`` hashes to the run id; an expected ``model.zip`` hash matches;
* data boundary: trained on the training split, with training data ending before
  ``validation.start``; the saved scaler equals the one recorded in the identity;
* compatibility with the **current** configuration: cost rate, cap, initial capital, cash return,
  funding charge, execution lag, decision schedule, action scale and observation size;
* optionally, the processed-dataset and feature-set ids of the data it would be used with;
* the code it was trained from was committed and clean.

An empty list means the checkpoint may be used with the current configuration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adaptive_portfolio.agents import run_safety
from adaptive_portfolio.config import BacktestConfig, ProjectConfig
from adaptive_portfolio.data import cache
from adaptive_portfolio.environment.actions import ACTION_SCALE
from adaptive_portfolio.environment.rewards import DECISION_SCHEDULE
from adaptive_portfolio.evaluation.backtest import simulation_settings
from adaptive_portfolio.regimes.rules import REGIME_LABELS


def _read(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_checkpoint(
    run_dir: Path,
    config: ProjectConfig,
    backtest: BacktestConfig,
    *,
    expected_model_sha256: str | None = None,
    dataset_dir: Path | None = None,
    feature_dir: Path | None = None,
) -> list[str]:
    """Problems that make ``run_dir`` unsafe to load with the current configuration."""
    run_dir = Path(run_dir)
    if not (run_dir / "run_config.json").is_file():
        return [f"{run_dir}: not a training run directory (no run_config.json)"]
    identity = _read(run_dir / "run_config.json")
    problems = list(run_safety.verify_run_dir(run_dir, run_dir.name,
                                              int(identity.get("total_timesteps", 0))))  # fmt: skip
    if problems and "files" in problems[0]:
        return problems
    meta = _read(run_dir / "metadata.json")
    if cache.short_hash(identity) != run_dir.name:
        problems.append("run_config.json does not hash to the run id")
    model_sha = meta.get("files_sha256", {}).get("model.zip")
    if expected_model_sha256 is not None and model_sha != expected_model_sha256:
        problems.append("model.zip hash differs from the expected (selected) checkpoint")
    if identity.get("split") != "train":
        problems.append(f"trained on split {identity.get('split')!r}, not train")
    validation_start = str(config.experiment.splits.validation.start)
    if not str(identity.get("data", {}).get("last_date", "9999")) < validation_start:
        problems.append("training data do not end before validation.start")
    if _read(run_dir / "scaler.json") != identity.get("scaler"):
        problems.append("scaler.json differs from the scaler recorded in the identity")
    settings = simulation_settings(config, backtest)
    env = identity.get("environment", {})
    n_features = len(identity.get("scaler", {}).get("columns", []))
    expected = {
        "cost_rate": settings.cost_rate,
        "max_weight": settings.constraints.max_weight,
        "initial_capital": settings.initial_capital,
        "cash_return": settings.cash_return,
        "charge_initial_funding": settings.charge_initial_funding,
        "execution_lag_sessions": backtest.execution_lag_sessions,
        "decision_schedule": DECISION_SCHEDULE,
        "action_scale": ACTION_SCALE,
        "observation_size": n_features + len(REGIME_LABELS) + len(config.data.universe) + 1,
    }
    for key, value in expected.items():
        if env.get(key) != value:
            problems.append(f"incompatible {key}: checkpoint {env.get(key)!r}, current {value!r}")
    for directory, file, key in (
        (dataset_dir, "metadata.json", "processed_dataset_id"),
        (feature_dir, "feature_metadata.json", "feature_set_id"),
    ):
        if directory is not None:
            found = _read(Path(directory) / file).get(key)
            if found != identity.get("data", {}).get(key):
                problems.append(f"{key} {found} differs from the training data")
    code = identity.get("code", {})
    if not code.get("commit") or code.get("dirty") is not False:
        problems.append("not trained from a clean committed tree")
    return problems
