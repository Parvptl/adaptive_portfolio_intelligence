"""E10 end to end on the tiny synthetic project (D-094; ``rl`` extra).

Folds: A (earlier; a derived dataset, no E0) and C (the project's own split, the reference).
Trains E7B/E7T1, E8B/E8T1 and both E10 arms of both folds (2 seeds), evaluates both splits,
runs ``compare-walk-forward`` through the CLI and checks leakage, reproduction, unique run
identities and the write-once rule. No market data; the synthetic test split is never read.
"""

from __future__ import annotations

import copy
import json
import subprocess

import pandas as pd
import pytest
import yaml

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

from adaptive_portfolio.agents import profile_experiment as pe  # noqa: E402
from adaptive_portfolio.config import load_yaml  # noqa: E402
from adaptive_portfolio.data import walk_forward as wf  # noqa: E402
from adaptive_portfolio.explainability import walk_forward_comparison as wc  # noqa: E402
from conftest import CONFIG_DIR  # noqa: E402
from test_ppo_wrapper import GIT, SPLITS  # noqa: E402
from test_profile_experiment import _project, _train_e0  # noqa: E402

FOLD_A = {"id": "A", "train": {"start": "2024-01-01", "end": "2024-02-29"},
          "validation": {"start": "2024-03-01", "end": "2024-03-29"},
          "holdout": {"start": "2024-04-01", "end": "2024-05-31"}}  # fmt: skip
FOLD_C = {"id": "C", "train": SPLITS["train"], "validation": SPLITS["validation"],
          "holdout": SPLITS["test"]}  # fmt: skip


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> pe.Context:
    context = _project(tmp_path_factory.mktemp("walkforward"))
    groups = load_yaml(context.config_dir / "turnover_k0.yaml")["evaluation"]["exposure_groups"]
    names = {f"turnover_refine_k{k}.yaml": None for k in (0, 1)}
    names |= {f"walk_forward_{f}_k{k}.yaml": fold for f, fold in (("a", FOLD_A), ("c", FOLD_C))
              for k in (0, 1)}  # fmt: skip
    for name, fold in names.items():
        raw = copy.deepcopy(load_yaml(CONFIG_DIR / name))
        raw.update(base_configuration=0, seeds=[42, 43])
        if fold is not None:
            raw["walk_forward_fold"] = fold
        raw["evaluation"].update(sweep_points=3, exposure_groups=groups)
        (context.config_dir / name).write_text(yaml.safe_dump(raw), encoding="utf-8")
    for command in (["add", "-A"], ["commit", "-q", "-m", "E8/E10 configs"]):
        subprocess.run([*GIT, "-C", str(context.root), *command], check=True, capture_output=True)
    context = pe.load_context(context.config_dir)
    _train_e0(context)
    return context


def _arm(project: pe.Context, name: str) -> tuple[pe.Context, dict]:
    context = pe.load_context(project.config_dir, experiment_path=project.config_dir / name)
    assert {r["status"] for r in pe.train_arm(context, "main")} <= {"trained", "existing"}
    dirs = {}
    for split in ("train", "validation"):
        plan = pe.plan_profile_evaluation(context, split)
        target = plan.output_dir if plan.output_dir.exists() else pe.run_profile_evaluation(plan)
        assert pe.verify_profile_evaluation(target) == []
        dirs[split] = target
    return context, dirs


def test_walk_forward_end_to_end(project, monkeypatch) -> None:
    monkeypatch.setattr(wc, "FOLDS", ("A", "C"))
    monkeypatch.setattr(wc, "SEEDS", (42, 43))
    cfg = project.config_dir
    with pytest.raises(pe.ProfileExperimentError, match="not built"):
        pe.load_context(cfg, experiment_path=cfg / "walk_forward_a_k0.yaml")
    args = ["--config-dir", str(cfg), "--dataset-dir", str(project.dataset_dir),
            "--experiment-config", str(cfg / "walk_forward_a_k0.yaml")]  # fmt: skip
    assert wf.main([*args, "build-fold", "--execute"]) == 0
    assert wf.main([*args, "verify-fold"]) == 0
    fold_a = pe.load_context(cfg, experiment_path=cfg / "walk_forward_a_k0.yaml")
    assert not fold_a.e0_available and fold_a.dataset_dir != project.dataset_dir
    assert str(fold_a.config.experiment.splits.validation.start) == "2024-03-01"

    e7 = [_arm(project, f"turnover_k{k}.yaml")[1] for k in (0, 1)]
    reference = project.root / "data/processed/evaluations/reference"
    if not reference.exists():  # the synthetic stand-in for EXP-006, from E7B's E0 rows
        e0 = pd.read_csv(e7[0]["validation"] / "episode_metrics.csv")
        e0 = e0[e0["experiment"] == "E0"].assign(configuration=0)
        reference.mkdir(parents=True)
        e0[["configuration", "seed", "annualised.net_sharpe"]].to_csv(
            reference / "policy_metrics.csv", index=False)  # fmt: skip
    e8 = [_arm(project, f"turnover_refine_k{k}.yaml")[1] for k in (0, 1)]
    a = [_arm(project, f"walk_forward_a_k{k}.yaml")[1] for k in (0, 1)]
    c = [_arm(project, f"walk_forward_c_k{k}.yaml")[1] for k in (0, 1)]

    meta_a = json.loads((a[0]["validation"] / "metadata.json").read_text(encoding="utf-8"))
    meta_c = json.loads((c[0]["validation"] / "metadata.json").read_text(encoding="utf-8"))
    assert meta_a["e0_checkpoints"] == [] and meta_c["e0_checkpoints"]  # E0 only in fold C
    assert meta_a["rows_read_before"] == "2024-04-01"  # the fold's holdout start
    summary_a = json.loads((a[0]["validation"] / "summary.json").read_text(encoding="utf-8"))
    assert "no E0" in summary_a["e0_reproduction"]["reason"]
    ids_a = {cp["seed"]: cp["run_id"] for cp in meta_a["checkpoints"]}
    ids_c = {cp["seed"]: cp["run_id"] for cp in meta_c["checkpoints"]}
    assert set(ids_a) == set(ids_c) and not set(ids_a.values()) & set(ids_c.values())

    walk = ["--config-dir", str(cfg), "--experiment-config", str(cfg / "walk_forward_c_k0.yaml"),
            "compare-walk-forward",
            "--fold", "A", str(a[0]["validation"]), str(a[1]["validation"]), str(a[0]["train"]),
            str(a[1]["train"]),
            "--fold", "C", str(c[0]["validation"]), str(c[1]["validation"]), str(c[0]["train"]),
            str(c[1]["train"]),
            "--reproduce-validation", str(e8[0]["validation"]), str(e8[1]["validation"]),
            str(e7[0]["validation"]), str(e7[1]["validation"]),
            "--reproduce-train", str(e8[0]["train"]), str(e8[1]["train"]), str(e7[0]["train"]),
            str(e7[1]["train"]), "--execute"]  # fmt: skip
    assert pe.main(walk) == 0
    root = project.root / "data/processed/walk_forward_comparisons"
    (comparison,) = [p for p in root.iterdir() if p.is_dir()]
    assert wc.verify_walk_forward_comparison(comparison) == []
    assert pe.main(["--config-dir", str(cfg), "verify", str(comparison)]) == 0

    hyp = json.loads((comparison / "hypotheses.json").read_text(encoding="utf-8"))
    assert hyp["H9"]["verdict"] == "supported", hyp["H9"]["parts"]
    integrity = json.loads((comparison / "integrity.json").read_text(encoding="utf-8"))
    assert integrity["A"]["verified"] and not integrity["A"]["reference"]
    assert integrity["A"]["checks"]["feature values equal the parent's exactly (past-only)"]
    assert integrity["C"]["reference"] and integrity["C"]["verified"]
    repro = json.loads((comparison / "reproduction.json").read_text(encoding="utf-8"))
    assert len(repro) == 8 and all(r["identical"] for r in repro.values())
    diffs = pd.read_csv(comparison / "paired_differences.csv")
    assert set(diffs["fold"]) == {"A", "C"} and set(diffs["n"]) == {2}
    assert hyp["outcome"]["class"] in ("Walk-forward confirmation", "Partial confirmation",
                                       "No reliable improvement", "Deterioration")  # fmt: skip
    summary = json.loads((comparison / "fold_summary.json").read_text(encoding="utf-8"))
    assert set(summary["folds"]) == {"A", "C"}
    assert summary["secondary_stratified_permutation"]["assignments"] == 2**4

    folds = {"A": {"validation": [a[0]["validation"], a[1]["validation"]],
                   "train": [a[0]["train"], a[1]["train"]]},
             "C": {"validation": [c[0]["validation"], c[1]["validation"]],
                   "train": [c[0]["train"], c[1]["train"]]}}  # fmt: skip
    repro_dirs = {"control:x = E8B": [e8[0]["validation"], e8[0]["train"]]}
    context = pe.load_context(cfg, experiment_path=cfg / "walk_forward_c_k0.yaml")
    with pytest.raises(wc.WalkForwardComparisonError, match="not comparable"):
        swapped = {**folds, "A": {"validation": folds["A"]["validation"][::-1],
                                  "train": folds["A"]["train"][::-1]}}  # fmt: skip
        wc.run_walk_forward_comparison(context, swapped, repro_dirs)
    with pytest.raises(wc.WalkForwardComparisonError, match="wrong evaluations"):
        wc.run_walk_forward_comparison(context, {"A": folds["C"], "C": folds["A"]}, repro_dirs)
    with pytest.raises(wc.WalkForwardComparisonError, match="exactly the folds"):
        wc.run_walk_forward_comparison(context, {"A": folds["A"]}, repro_dirs)

    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.profile_figures import make_walk_forward_figures

    written = make_walk_forward_figures(comparison, project.root / "data" / "e10_figures")
    assert len(written) == 4 and all(w.with_suffix(".json").is_file() for w in written)
