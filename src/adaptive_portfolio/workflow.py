"""End-to-end entry point over saved artifacts (milestone F): ``python scripts/workflow.py``.

Modes (default ``status``):

``status``     read-only inventory: configured artifacts, whether they exist, and the separate,
               gated operations that this entry point never runs.
``verify``     integrity of the validation evaluation outputs and provenance and configuration
               compatibility of the selected checkpoints (:mod:`agents.provenance`).
``explain``    the training-split baseline regime analysis (milestone E). The policy analysis on
               validation decisions is **not** run here; it needs a recorded authorisation and
               ``scripts/explain.py policy-validation --confirm-validation-access``.
``dashboard``  build the static dashboard from saved, verified artifacts.

Training (``scripts/run_grid.py``), the validation evaluation (``scripts/evaluate_validation.py``)
and any test evaluation (none exists; Gate 3) are separate operations with their own approvals;
this entry point never triggers them and never reads test-period data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from adaptive_portfolio.config import (
    ConfigError,
    load_agent_config,
    load_backtest_config,
    load_preregistration,
    load_project_config,
    load_workflow_config,
)
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import project_root_for, resolve_path

GATED_OPERATIONS = (
    ("train the PPO grid (done: EXP-005)", "python scripts/run_grid.py --plan",
     "a training authorisation; full runs need a clean commit (D-075)"),
    ("validation evaluation (done: EXP-006)", "python scripts/evaluate_validation.py --plan",
     "protocol D-076 accepted; execution authorised separately"),
    ("policy explainability on validation decisions (D-068)",
     "python scripts/explain.py policy-validation --evaluation-dir <dir> "
     "--confirm-validation-access", "an explicit, recorded execution authorisation"),
    ("test evaluation (2020-2024)",
     "python scripts/evaluate_test.py --plan (execution refused until frozen and authorised)",
     "Gate 3: every item in docs/approval_checklist.md, then a separate unsealing authorisation"),
)  # fmt: skip


def _paths(config_dir: Path):
    workflow = load_workflow_config(config_dir / "workflow.yaml")
    root = project_root_for(config_dir)
    return workflow, root


def status(config_dir: Path) -> int:
    workflow, root = _paths(config_dir)
    print("STATUS (read-only; nothing is trained, evaluated or written)")
    for key, path in vars(workflow).items():
        full = resolve_path(path, root)
        print(f"  {key:26s} {'present' if full.exists() else 'MISSING'}  {path.as_posix()}")
    analyses = resolve_path(workflow.explainability_root, root)
    found = (
        sorted(p.name for p in analyses.glob("*") if (p / "analysis.json").is_file())
        if (analyses.is_dir())
        else []
    )
    print(f"  saved analyses             {found or 'none'}")
    prereg_path = config_dir / "preregistration.yaml"
    if prereg_path.is_file():
        prereg = load_preregistration(prereg_path)
        print(
            f"  pre-registration           {prereg.status.upper()} "
            f"({len(prereg.open_items())} blocking item(s)); sha256 {prereg.sha256()[:16]}..."
        )
    tests = resolve_path(Path("data/processed/test_evaluations"), root)
    print(f"  test evaluations           {'PRESENT' if tests.exists() else 'none (test sealed)'}")
    print("Separate, gated operations (never run by this entry point):")
    for what, command, gate in GATED_OPERATIONS:
        print(f"  - {what}: {command}\n      requires {gate}")
    return 0


def verify(config_dir: Path) -> int:
    from adaptive_portfolio.agents.provenance import verify_checkpoint

    workflow, root = _paths(config_dir)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    directory = resolve_path(workflow.validation_evaluation_dir, root)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    problems = [f"{n}: hash mismatch" for n, h in meta["files_sha256"].items()
                if cache.file_sha256(directory / n) != h]  # fmt: skip
    if cache.short_hash({k: v for k, v in meta.items() if k not in (
            "evaluation_id", "protocol_hash", "started_at", "wall_seconds", "files_sha256")}) != (
            meta["evaluation_id"]):  # fmt: skip
        problems.append("evaluation identity does not hash to its id")
    document = json.loads((directory / "evaluation.json").read_text(encoding="utf-8"))
    selected = document["selection"]["selected_configuration"]
    experiments = resolve_path(load_agent_config(config_dir / "agent.yaml").output_dir, root)
    manifest = experiments / "grids" / meta["grid"]["grid_id"] / "manifest.json"
    if cache.file_sha256(manifest) != meta["grid"]["manifest_sha256"]:
        problems.append("grid manifest hash differs from the evaluation record")
    print(f"evaluation {meta['evaluation_id']} (protocol {meta['protocol_hash']}); "
          f"selected configuration {selected}")  # fmt: skip
    for c in meta["checkpoints"]:
        if c["configuration"] != selected:
            continue
        found = verify_checkpoint(
            experiments / c["run_id"], config, backtest, expected_model_sha256=c["model_sha256"],
            dataset_dir=resolve_path(workflow.dataset_dir, root),
            feature_dir=resolve_path(workflow.feature_dir, root),
        )  # fmt: skip
        print(f"  seed {c['seed']} {c['run_id']}: {found if found else 'verified'}")
        problems += [f"{c['run_id']}: {p}" for p in found]
    if problems:
        print("VERIFY FAILED:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return 1
    print("verify: all checks passed")
    return 0


def explain(config_dir: Path) -> int:
    from adaptive_portfolio.explainability import run as runner

    workflow, root = _paths(config_dir)
    try:
        target = runner.run_baselines_train(
            config_dir, resolve_path(workflow.baseline_backtest_dir, root),
            dataset_dir=resolve_path(workflow.dataset_dir, root),
            feature_dir=resolve_path(workflow.feature_dir, root),
            output_root=resolve_path(workflow.explainability_root, root),
        )  # fmt: skip
    except runner.ExplainabilityError as exc:
        if "never overwritten" in str(exc):
            print(f"explain: an identical analysis already exists ({exc})")
            return 0
        raise
    print(f"explain: baselines-train analysis written to {target}")
    print("explain: the policy analysis on validation decisions was NOT run (needs authorisation)")
    return 0


def dashboard(config_dir: Path) -> int:
    from adaptive_portfolio.visualization.dashboard import build_dashboard

    workflow, _ = _paths(config_dir)
    target = build_dashboard(config_dir, workflow)
    print(f"dashboard: {target / 'index.html'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow over saved artifacts (read-mostly).")
    parser.add_argument("mode", nargs="?", default="status",
                        choices=("status", "verify", "explain", "dashboard"))  # fmt: skip
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    args = parser.parse_args(argv)
    try:
        return {"status": status, "verify": verify, "explain": explain,
                "dashboard": dashboard}[args.mode](args.config_dir)  # fmt: skip
    except (ConfigError, FileNotFoundError, KeyError, RuntimeError, ValueError) as exc:
        print(f"WORKFLOW FAILED ({args.mode}): {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
