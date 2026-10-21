"""Explainability and regime-analysis runs from saved artifacts (milestone E; D-068).

Two modes, each reading only what its data boundary allows:

``baselines-train``
    Regime-conditioned description of the conventional baselines on the **training split**,
    from a saved baseline backtest (e.g. EXP-002). Only ledger lines labelled ``train`` are
    parsed; regime labels come from the bounded ``train_only`` loader and are checked with
    :func:`assert_training_only`. No policy is run. Needs no authorisation beyond development
    use of training data.

``policy-validation``
    The D-068 analysis of the selected PPO checkpoints on **validation decisions**: regime-
    conditioned summaries of the saved validation-evaluation ledgers (policies and baselines),
    and permutation sensitivity of the decided targets by input group. Decision observations are
    rebuilt from the saved ledger weights (no rollout); the rebuilt deterministic targets must
    reproduce the evaluator's executed targets exactly, otherwise the run stops. Rows are read
    only before ``test.start``. **It reads validation-period feature and regime rows, so it
    refuses to run without ``--confirm-validation-access``, which must only be passed after an
    explicit, recorded authorisation.**

There is no test-period mode. Outputs go to ``data/processed/explainability/<analysis_id>/``
(git-ignored), are written in staging, finalised exclusively and never overwritten. The code
state is recorded; runs from uncommitted code are labelled as such.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import platform
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.agents import run_safety
from adaptive_portfolio.config import (
    ConfigError,
    load_agent_config,
    load_backtest_config,
    load_feature_config,
    load_project_config,
)
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.boundaries import (
    DataBoundaryError,
    assert_before_split,
    assert_training_only,
)
from adaptive_portfolio.data.pipeline import project_root_for, resolve_path
from adaptive_portfolio.environment.observation import FeatureScaler, build_observation
from adaptive_portfolio.explainability import regime_analysis as ra
from adaptive_portfolio.explainability import sensitivity as sens
from adaptive_portfolio.features.engineering import FeatureDataError
from adaptive_portfolio.features.pipeline import (
    feature_output_dir,
    load_feature_outputs,
    locate_dataset_dir,
)

SCHEMA_VERSION = 1
OUTPUT_ROOT = "data/processed/explainability"
MODES = ("baselines-train", "policy-validation")
# Artifacts that must never be opened: they hold test-period results (research_protocol.md §12).
FORBIDDEN_ARTIFACTS = {
    "ac2d6b163d4f5e4b": "pipeline-v1 backtest output containing test-split results",
}
FIGURE_METRICS = (
    ("mean_risky_exposure", "mean risky exposure (1 - cash)"),
    ("mean_weight_CASH", "mean cash weight"),
    ("annualised_turnover", "annualised recurring traded notional"),
    ("annualised_volatility", "annualised volatility of daily net returns"),
    ("mean_risky_hhi", "Herfindahl index of the risky sleeve"),
)
STATUS = {
    "baselines-train": (
        "DESCRIPTIVE, TRAINING SPLIT ONLY: conventional baselines from a saved backtest, "
        "conditioned on training-calibrated regime labels. Observational associations on one "
        "historical path; simulated, not live trading; not financial advice."
    ),
    "policy-validation": (
        "DESCRIPTIVE, VALIDATION DECISIONS (D-068): regime-conditioned summaries and one-step "
        "permutation sensitivity of the selected PPO checkpoints. Sensitivity of decisions, not "
        "importance for returns and not causal; simulated, not financial advice."
    ),
}


class ExplainabilityError(RuntimeError):
    """Raised when an analysis cannot run exactly as specified (nothing is written)."""


EXPECTED_FAILURES = (
    ExplainabilityError, ra.RegimeAnalysisError, sens.SensitivityError, DataBoundaryError,
    FeatureDataError, ConfigError, run_safety.RunSafetyError, FileNotFoundError,
)  # fmt: skip


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


def refuse_forbidden(path: Path) -> None:
    """Refuse known test-result artifacts by name, before any file in them is opened."""
    for part in Path(path).parts:
        if part in FORBIDDEN_ARTIFACTS:
            raise ExplainabilityError(f"{path}: {FORBIDDEN_ARTIFACTS[part]}; never opened")


def default_feature_dir(config_dir: Path, root: Path, dataset_dir: Path) -> Path:
    """The training-calibrated feature set built from ``dataset_dir`` with ``features.yaml``."""
    metadata = json.loads((dataset_dir / "metadata.json").read_text(encoding="utf-8"))
    features = load_feature_config(config_dir / "features.yaml")
    directory, _ = feature_output_dir(features, root, metadata["processed_dataset_id"], None)
    return directory


def read_split_rows(path: Path, split: str) -> pd.DataFrame:
    """Rows of a stacked ledger CSV whose ``split`` field equals ``split``.

    Lines of other splits are recognised by their text field only; their numeric values are
    never parsed.
    """
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        header = handle.readline()
        names = header.rstrip("\r\n").split(",")
        if "split" not in names:
            raise ExplainabilityError(f"{path} has no 'split' column")
        index = names.index("split")
        kept = [line for line in handle if line.split(",", index + 1)[index] == split]
    if not kept:
        raise ExplainabilityError(f"{path} has no rows labelled {split!r}")
    frame = pd.read_csv(io.StringIO(header + "".join(kept)), float_precision="round_trip")
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def _check_decision_lag(ledger: pd.DataFrame, calendar: pd.DatetimeIndex, lag: int) -> int:
    """Executions must lie exactly ``lag`` sessions after their recorded decision date."""
    rows = ledger[ledger["rebalanced"].astype(bool) & ledger["decision_date"].notna()]
    executed = calendar.get_indexer(pd.to_datetime(rows["date"]))
    decided = calendar.get_indexer(pd.to_datetime(rows["decision_date"]))
    if (executed < 0).any() or (decided < 0).any() or not np.all(executed - decided == lag):
        raise ExplainabilityError("ledger decision dates are not `lag` sessions before execution")
    return len(rows)


def _verify_hashes(directory: Path) -> dict[str, Any]:
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    bad = [n for n, h in (metadata.get("files_sha256") or {}).items()
           if cache.file_sha256(directory / n) != h]  # fmt: skip
    if bad or not metadata.get("files_sha256"):
        raise ExplainabilityError(f"{directory}: file hashes do not match its metadata: {bad}")
    return metadata


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def _write_outputs(
    output_root: Path, identity: dict[str, Any], writer: Callable[[Path], None]
) -> Path:
    target = output_root / cache.short_hash(identity)
    if target.exists():
        raise ExplainabilityError(f"{target} already exists; analyses are never overwritten")
    output_root.mkdir(parents=True, exist_ok=True)
    staging = output_root / f"{target.name}{run_safety.STAGING_MARK}{os.getpid()}"
    try:
        staging.mkdir()
        started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        writer(staging)
        files = sorted(p.relative_to(staging).as_posix() for p in staging.rglob("*") if p.is_file())
        cache.write_json({
            "analysis_id": target.name, **identity, "started_at": started,
            "files_sha256": {name: cache.file_sha256(staging / name) for name in files},
        }, staging / "metadata.json")  # fmt: skip
        run_safety.finalise_exclusive(staging, target)
    except BaseException as exc:
        run_safety.quarantine(output_root, [staging], target.name,
                              f"analysis failed: {type(exc).__name__}: {exc}")  # fmt: skip
        raise
    return target


def _versions() -> dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version

    out = {"python": platform.python_version()}
    for name in ("numpy", "pandas", "matplotlib"):
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = "not installed"
    return out


def _figures(summary: pd.DataFrame, assets: list[str], directory: Path, scope: str,
             source: dict[str, Any]) -> list[str]:  # fmt: skip
    from adaptive_portfolio.visualization import plots

    made = []
    figures = directory / "figures"
    method = "regime_analysis.regime_conditioned_summary (label at t - lag; funding row excluded)"
    for strategy, rows in summary.groupby("strategy", sort=True):
        path = figures / f"allocation_by_regime_{strategy}.png"
        plots.plot_regime_allocation(
            rows, assets, path, title=f"{strategy}: mean allocation by regime ({scope})",
            provenance={"source": source, "method": method, "scope": scope, "strategy": strategy},
        )  # fmt: skip
        made.append(path.relative_to(directory).as_posix())
    for metric, label in FIGURE_METRICS:
        path = figures / f"{metric}_by_regime.png"
        plots.plot_regime_metric(
            summary, metric, path, ylabel=label, title=f"{label} by regime ({scope})",
            provenance={"source": source, "method": method, "scope": scope, "metric": metric},
        )  # fmt: skip
        made.append(path.relative_to(directory).as_posix())
    return made


# --------------------------------------------------------------------------
# Mode: baselines-train
# --------------------------------------------------------------------------


def run_baselines_train(
    config_dir: Path, backtest_dir: Path, *, dataset_dir: Path | None = None,
    feature_dir: Path | None = None, output_root: Path | None = None,
    min_sessions: int = ra.DEFAULT_MIN_SESSIONS, figures: bool = True,
) -> Path:  # fmt: skip
    """Regime-conditioned summaries of the baselines on the training split of a saved backtest."""
    backtest_dir = Path(backtest_dir)
    refuse_forbidden(backtest_dir)
    config_dir = Path(config_dir)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    root = project_root_for(config_dir)
    dataset_dir = Path(dataset_dir or locate_dataset_dir(config, root))
    feature_dir = Path(feature_dir or default_feature_dir(config_dir, root, dataset_dir))
    meta = json.loads((backtest_dir / "metadata.json").read_text(encoding="utf-8"))
    if "test" in meta.get("evaluated_splits", ["test"]):
        raise ExplainabilityError(f"{backtest_dir} evaluated the test split; it is not read")
    dataset_id = json.loads((dataset_dir / "metadata.json").read_text(encoding="utf-8"))[
        "processed_dataset_id"
    ]
    if meta.get("processed_dataset_id") != dataset_id:
        raise ExplainabilityError("the backtest was run on a different processed dataset")
    lag = int(meta["backtest"]["execution_lag_sessions"])
    if lag != backtest.execution_lag_sessions:
        raise ExplainabilityError("the backtest's lag differs from configs/backtest.yaml")
    ledger_path = backtest_dir / "ledger.csv"
    ledgers = read_split_rows(ledger_path, "train")
    outputs = load_feature_outputs(feature_dir, dataset_dir, config, train_only=True)
    splits = config.experiment.splits
    assert_training_only(outputs.features.index, outputs.split_labels, splits)
    regimes = outputs.regimes["regime"]
    calendar = pd.DatetimeIndex(regimes.index)
    if ledgers["date"].max() >= pd.Timestamp(splits.validation.start):
        raise DataBoundaryError("training ledger rows reach the validation period")
    executions = _check_decision_lag(ledgers, calendar, lag)
    summary = ra.summarise_strategies(ledgers, regimes, lag=lag, min_sessions=min_sessions)
    assets = [c.removeprefix("weight_") for c in ledgers.columns
              if c.startswith("weight_") and c != "weight_CASH"]  # fmt: skip
    source = {
        "backtest_id": meta.get("backtest_id"), "ledger_sha256": cache.file_sha256(ledger_path),
        "rows_used": "split == train", "processed_dataset_id": dataset_id,
        "feature_set_id": outputs.metadata.get("feature_set_id"),
        "regime_thresholds_sha256": cache.file_sha256(feature_dir / "regime_thresholds.json"),
        "regimes_train_prefix_sha256": cache.head_sha256(feature_dir / "regimes.csv",
                                                         len(regimes)),
    }  # fmt: skip
    code = run_safety.code_provenance(root)
    identity = {
        "schema_version": SCHEMA_VERSION, "mode": "baselines-train", "source": source,
        "parameters": {"lag": lag, "min_sessions": min_sessions, "periods_per_year": 252,
                       "label_convention": "regime at t - lag (decision / information date)"},
        "code": {k: code.get(k) for k in ("git_available", "commit", "dirty", "diff_sha256")},
        "versions": _versions(),
    }  # fmt: skip

    def writer(directory: Path) -> None:
        cache.write_csv(summary, directory / "regime_summary.csv")
        made = (
            _figures(summary, assets, directory, "training split, simulated", source)
            if (figures)
            else []
        )
        cache.write_json({
            "status": STATUS["baselines-train"], **identity,
            "window": {"first_date": str(ledgers["date"].min().date()),
                       "last_date": str(ledgers["date"].max().date())},
            "checks": {"executions_lag_checked": executions,
                       "rows_held_training_only": True, "test_rows_read": 0,
                       "validation_values_parsed": 0},
            "figures": made, "limitations": list(ra.LIMITATIONS),
            "uncommitted_code": bool(identity["code"].get("dirty")),
        }, directory / "analysis.json")  # fmt: skip

    return _write_outputs(
        Path(output_root or resolve_path(Path(OUTPUT_ROOT), root)), identity, writer
    )


# --------------------------------------------------------------------------
# Mode: policy-validation (requires an explicit authorisation flag)
# --------------------------------------------------------------------------


def sb3_policy_loader(model_path: Path) -> sens.Policy:  # pragma: no cover - needs the rl extra
    import torch
    from stable_baselines3 import PPO

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    model = PPO.load(model_path, device="cpu")

    def policy(obs: np.ndarray) -> np.ndarray:
        # One observation at a time, as the environment and the D-076 evaluator call it:
        # batched float32 matrix products round differently (about 1e-9 in the targets).
        return np.vstack([model.predict(row, deterministic=True)[0] for row in obs])

    return policy


def decision_observations(
    ledger: pd.DataFrame, features: pd.DataFrame, regimes: pd.Series, scaler: FeatureScaler,
    lag: int,
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:  # fmt: skip
    """Observations at the policy's decision dates, rebuilt from the saved ledger (no rollout).

    Returns the observations, the executed targets (end-of-row weights on the execution rows,
    assets then cash) and the decision dates. The first decision precedes the funding row, so
    its portfolio input is all cash.
    """
    ledger = ledger.sort_values("date").reset_index(drop=True)
    weights = ledger.filter(like="weight_")
    executed = ledger[ledger["rebalanced"].astype(bool)]
    decisions = pd.DatetimeIndex(pd.to_datetime(executed["decision_date"]))
    calendar = pd.DatetimeIndex(features.index)
    if (calendar.get_indexer(pd.to_datetime(executed["date"]))
            - calendar.get_indexer(decisions) != lag).any():  # fmt: skip
        raise ExplainabilityError("executions are not `lag` sessions after their decisions")
    by_date = weights.set_index(pd.to_datetime(ledger["date"]))
    cash_only = np.r_[np.zeros(weights.shape[1] - 1), 1.0]
    scaled, _ = scaler.transform(features.loc[decisions, list(scaler.columns)])
    rows = []
    for i, date in enumerate(decisions):
        held = by_date.loc[date].to_numpy(float) if date in by_date.index else cash_only
        rows.append(build_observation(scaled[i], regimes.loc[date], held))
    return (np.asarray(rows, dtype=np.float32), executed.filter(like="weight_").to_numpy(float),
            decisions)  # fmt: skip


def run_policy_validation(
    config_dir: Path, evaluation_dir: Path, *, confirm_validation_access: bool,
    dataset_dir: Path | None = None, feature_dir: Path | None = None,
    output_root: Path | None = None, repeats: int = 20, seed: int = 0,
    min_sessions: int = ra.DEFAULT_MIN_SESSIONS,
    load_policy: Callable[[Path], sens.Policy] = sb3_policy_loader, figures: bool = True,
) -> Path:  # fmt: skip
    """The D-068 analysis on validation decisions; refuses without the explicit flag."""
    if not confirm_validation_access:
        raise ExplainabilityError(
            "policy-validation reads validation-period feature and regime rows; it needs an "
            "explicit recorded authorisation and --confirm-validation-access"
        )
    evaluation_dir = Path(evaluation_dir)
    refuse_forbidden(evaluation_dir)
    config_dir = Path(config_dir)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    root = project_root_for(config_dir)
    dataset_dir = Path(dataset_dir or locate_dataset_dir(config, root))
    feature_dir = Path(feature_dir or default_feature_dir(config_dir, root, dataset_dir))
    meta = _verify_hashes(evaluation_dir)
    if meta.get("protocol", {}).get("split") != "validation":
        raise ExplainabilityError("only a validation evaluation can be analysed here")
    document = json.loads((evaluation_dir / "evaluation.json").read_text(encoding="utf-8"))
    lag = backtest.execution_lag_sessions
    splits = config.experiment.splits
    outputs = load_feature_outputs(feature_dir, dataset_dir, config, exclude_test=True)
    assert_before_split(outputs.features.index, outputs.split_labels, splits, "test",
                        "explainability (features)")  # fmt: skip
    if outputs.metadata.get("feature_set_id") != meta["data"]["feature_set_id"]:
        raise ExplainabilityError("the feature set differs from the evaluated one")
    regimes = outputs.regimes["regime"]
    ledgers = pd.read_csv(evaluation_dir / "ledgers.csv", float_precision="round_trip")
    ledgers["date"] = pd.to_datetime(ledgers["date"])
    if ledgers["date"].max() >= pd.Timestamp(splits.test.start):
        raise DataBoundaryError("evaluation ledgers reach the test period")
    summary = ra.summarise_strategies(ledgers, regimes, lag=lag, min_sessions=min_sessions)
    families = {
        d["name"]: d["family"]
        for d in json.loads((feature_dir / "feature_metadata.json").read_text(encoding="utf-8"))[
            "feature_definitions"
        ]
    }
    selected = document["selection"]["selected_configuration"]
    checkpoints = [c for c in meta["checkpoints"] if c["configuration"] == selected]
    experiments = resolve_path(load_agent_config(config_dir / "agent.yaml").output_dir, root)
    max_weight = config.environment.constraints.max_weight
    assets = [c.removeprefix("weight_") for c in ledgers.columns
              if c.startswith("weight_") and c != "weight_CASH"]  # fmt: skip
    tables, fidelity = [], {}
    for checkpoint in checkpoints:
        run_dir = experiments / checkpoint["run_id"]
        if cache.file_sha256(run_dir / "model.zip") != checkpoint["model_sha256"]:
            raise ExplainabilityError(f"{checkpoint['run_id']}: model.zip hash mismatch")
        scaler = FeatureScaler.load(run_dir / "scaler.json")
        name = f"ppo_c{checkpoint['configuration']}_s{checkpoint['seed']}"
        rows = ledgers[ledgers["strategy"] == name]
        obs, executed, _ = decision_observations(rows, outputs.features, regimes, scaler, lag)
        policy = load_policy(run_dir / "model.zip")
        gap = float(np.abs(sens.decided_targets(policy, obs, max_weight) - executed).max())
        if gap > 1e-9:
            raise ExplainabilityError(f"{name}: rebuilt decisions differ from the evaluation "
                                      f"by {gap:.3g}; observations are not faithful")  # fmt: skip
        fidelity[name] = gap
        groups = sens.observation_groups(scaler.columns, families, len(assets))
        table = sens.permutation_sensitivity(
            policy,
            obs,
            groups,
            max_weight=max_weight,
            asset_names=assets,
            repeats=repeats,
            seed=seed,
        )
        tables.append(table.assign(strategy=name, seed=checkpoint["seed"]))
    per_seed = pd.concat(tables, ignore_index=True)
    across = per_seed.groupby("group", sort=False).agg(
        n_inputs=("n_inputs", "first"), seeds=("seed", "nunique"),
        median_l1_change=("mean_l1_change", "median"), min_l1_change=("mean_l1_change", "min"),
        max_l1_change=("mean_l1_change", "max"),
    ).reset_index()  # fmt: skip
    source = {"evaluation_id": meta["evaluation_id"], "protocol_hash": meta["protocol_hash"],
              "ledgers_sha256": meta["files_sha256"]["ledgers.csv"],
              "feature_set_id": outputs.metadata.get("feature_set_id"),
              "regime_thresholds_sha256": cache.file_sha256(feature_dir / "regime_thresholds.json"),
              "checkpoints": checkpoints}  # fmt: skip
    code = run_safety.code_provenance(root)
    identity = {
        "schema_version": SCHEMA_VERSION, "mode": "policy-validation", "source": source,
        "parameters": {"lag": lag, "min_sessions": min_sessions, "repeats": repeats,
                       "seed": seed, "selected_configuration": selected,
                       "label_convention": "regime at t - lag (decision / information date)"},
        "code": {k: code.get(k) for k in ("git_available", "commit", "dirty", "diff_sha256")},
        "versions": _versions(),
    }  # fmt: skip

    def writer(directory: Path) -> None:
        cache.write_csv(summary, directory / "regime_summary.csv")
        cache.write_csv(per_seed, directory / "sensitivity_by_seed.csv")
        cache.write_csv(across, directory / "sensitivity_summary.csv")
        made = []
        if figures:
            from adaptive_portfolio.visualization import plots

            made = _figures(summary, assets, directory, "validation, simulated", source)
            path = directory / "figures" / "sensitivity_selected_configuration.png"
            plots.plot_sensitivity(
                across.rename(columns={"median_l1_change": "mean_l1_change"}), path,
                title=f"Configuration {selected}: sensitivity of decided targets (median of seeds)",
                provenance={"source": source, "method": "sensitivity.permutation_sensitivity",
                            "scope": "validation decisions"},
            )  # fmt: skip
            made.append(path.relative_to(directory).as_posix())
        cache.write_json({
            "status": STATUS["policy-validation"], **identity, "fidelity_max_abs_gap": fidelity,
            "figures": made,
            "limitations": [*ra.LIMITATIONS, *sens.LIMITATIONS],
            "uncommitted_code": bool(identity["code"].get("dirty")),
        }, directory / "analysis.json")  # fmt: skip

    return _write_outputs(
        Path(output_root or resolve_path(Path(OUTPUT_ROOT), root)), identity, writer
    )


# --------------------------------------------------------------------------
# Command line: python scripts/explain.py
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regime analysis and explainability runs.")
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--feature-dir", type=Path)
    parser.add_argument("--backtest-dir", type=Path, help="baselines-train: saved backtest")
    parser.add_argument("--evaluation-dir", type=Path, help="policy-validation: saved evaluation")
    parser.add_argument(
        "--confirm-validation-access",
        action="store_true",
        help="policy-validation only, and only after a recorded authorisation",
    )
    parser.add_argument("--min-sessions", type=int, default=ra.DEFAULT_MIN_SESSIONS)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.mode == "baselines-train":
            if args.backtest_dir is None:
                parser.error("baselines-train needs --backtest-dir")
            target = run_baselines_train(args.config_dir, args.backtest_dir,
                                         dataset_dir=args.dataset_dir, feature_dir=args.feature_dir,
                                         min_sessions=args.min_sessions)  # fmt: skip
        else:
            if args.evaluation_dir is None:
                parser.error("policy-validation needs --evaluation-dir")
            target = run_policy_validation(
                args.config_dir, args.evaluation_dir,
                confirm_validation_access=args.confirm_validation_access,
                dataset_dir=args.dataset_dir, feature_dir=args.feature_dir,
                repeats=args.repeats, seed=args.seed, min_sessions=args.min_sessions,
            )  # fmt: skip
    except EXPECTED_FAILURES as exc:
        print(f"ANALYSIS FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"analysis written to {target}")
    return 0
