"""E11 end to end on the tiny synthetic project (D-095; ``rl`` extra).

Folds A (derived, no E0) and C (the reference split). The synthetic agent budget is 128 with
n_steps 64, so E11H declares 64. Trains E10T1, E11R and E11H in both folds (2 seeds), evaluates
both splits, runs ``compare-budget`` through the CLI and checks the budget rules, the exact E10T1
reproduction and the write-once rule. No market data; the synthetic test split is never read.
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

from adaptive_portfolio.agents import ppo  # noqa: E402
from adaptive_portfolio.agents import profile_experiment as pe  # noqa: E402
from adaptive_portfolio.config import load_yaml  # noqa: E402
from adaptive_portfolio.data import walk_forward as wf  # noqa: E402
from adaptive_portfolio.explainability import budget_comparison as bc  # noqa: E402
from adaptive_portfolio.explainability import walk_forward_comparison as wc  # noqa: E402
from conftest import CONFIG_DIR  # noqa: E402
from test_ppo_wrapper import GIT  # noqa: E402
from test_profile_experiment import _project, _train_e0  # noqa: E402
from test_walk_forward_e2e import FOLD_A, FOLD_C  # noqa: E402


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> pe.Context:
    context = _project(tmp_path_factory.mktemp("budget"))
    groups = load_yaml(context.config_dir / "turnover_k0.yaml")["evaluation"]["exposure_groups"]
    names = {}
    for f, fold in (("a", FOLD_A), ("c", FOLD_C)):
        names[f"walk_forward_{f}_k1.yaml"] = (fold, None)
        names[f"budget_{f}_ref.yaml"] = (fold, None)
        names[f"budget_{f}_half.yaml"] = (fold, 64)
    for name, (fold, budget) in names.items():
        raw = copy.deepcopy(load_yaml(CONFIG_DIR / name))
        raw.update(base_configuration=0, seeds=[42, 43], walk_forward_fold=fold)
        if budget is not None:
            raw["total_timesteps"] = budget
        raw["evaluation"].update(sweep_points=3, exposure_groups=groups)
        (context.config_dir / name).write_text(yaml.safe_dump(raw), encoding="utf-8")
    for command in (["add", "-A"], ["commit", "-q", "-m", "E10/E11 configs"]):
        subprocess.run([*GIT, "-C", str(context.root), *command], check=True, capture_output=True)
    context = pe.load_context(context.config_dir)
    _train_e0(context)
    args = ["--config-dir", str(context.config_dir), "--dataset-dir", str(context.dataset_dir),
            "--experiment-config", str(context.config_dir / "budget_a_ref.yaml")]  # fmt: skip
    assert wf.main([*args, "build-fold", "--execute"]) == 0
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


def test_budget_rules(project) -> None:
    cfg = project.config_dir
    half = pe.load_context(cfg, experiment_path=cfg / "budget_a_half.yaml")
    profile = pe.profile_training(half, "main")
    assert ppo.configured_budget(half.agent, profile) == 64
    assert ppo.configured_budget(half.agent, None) == half.agent.total_timesteps == 128
    ref = pe.load_context(cfg, experiment_path=cfg / "budget_a_ref.yaml")
    assert ppo.configured_budget(ref.agent, pe.profile_training(ref, "main")) == 128
    with pytest.raises(ppo.TrainingError, match="smoke run must use fewer"):
        pe.train_arm(half, "main", [42], total_timesteps=64, run_kind="smoke")
    with pytest.raises(ppo.TrainingError, match="configured budget 64"):
        pe.train_arm(half, "main", [42], total_timesteps=128, run_kind="full")
    raw = load_yaml(cfg / "budget_a_half.yaml")
    bad = cfg / "bad_budget.yaml"
    bad.write_text(yaml.safe_dump({**raw, "total_timesteps": 100}), encoding="utf-8")
    with pytest.raises(pe.ProfileExperimentError, match="multiple of n_steps"):
        pe.load_context(cfg, experiment_path=bad)
    bad.unlink()


def test_budget_end_to_end(project, monkeypatch) -> None:
    monkeypatch.setattr(wc, "FOLDS", ("A", "C"))
    monkeypatch.setattr(wc, "SEEDS", (42, 43))
    monkeypatch.setattr(bc, "REFERENCE_DONE", 128)
    monkeypatch.setattr(bc, "HALF_BUDGET", 64)
    cfg = project.config_dir
    e10 = {f: _arm(project, f"walk_forward_{f}_k1.yaml")[1] for f in ("a", "c")}
    reference = project.root / "data/processed/evaluations/reference"
    if not reference.exists():  # the synthetic stand-in for EXP-006, from E10T1_C's E0 rows
        e0 = pd.read_csv(e10["c"]["validation"] / "episode_metrics.csv")
        e0 = e0[e0["experiment"] == "E0"].assign(configuration=0)
        reference.mkdir(parents=True)
        e0[["configuration", "seed", "annualised.net_sharpe"]].to_csv(
            reference / "policy_metrics.csv", index=False)  # fmt: skip
    arms = {(f, a): _arm(project, f"budget_{f}_{a}.yaml")[1] for f in ("a", "c")
            for a in ("ref", "half")}  # fmt: skip
    walk = ["--config-dir", str(cfg), "--experiment-config", str(cfg / "budget_c_ref.yaml"),
            "compare-budget"]  # fmt: skip
    for f in ("a", "c"):
        walk += ["--fold", f.upper(), str(arms[(f, "ref")]["validation"]),
                 str(arms[(f, "half")]["validation"]), str(arms[(f, "ref")]["train"]),
                 str(arms[(f, "half")]["train"])]  # fmt: skip
    walk += ["--reproduce-validation", str(e10["a"]["validation"]), "x",
             str(e10["c"]["validation"]), "--reproduce-train", str(e10["a"]["train"]), "x",
             str(e10["c"]["train"])]  # fmt: skip
    # Only folds A and C exist here: map the CLI's (A, B, C) reproduction slots by hand instead.
    folds = {f.upper(): {"validation": [arms[(f, "ref")]["validation"],
                                        arms[(f, "half")]["validation"]],
                         "train": [arms[(f, "ref")]["train"], arms[(f, "half")]["train"]]}
             for f in ("a", "c")}  # fmt: skip
    repro = {f.upper(): [e10[f]["validation"], e10[f]["train"]] for f in ("a", "c")}
    context = pe.load_context(cfg, experiment_path=cfg / "budget_c_ref.yaml")
    comparison = bc.run_budget_comparison(context, folds, repro)
    assert bc.verify_budget_comparison(comparison) == []
    assert pe.main(["--config-dir", str(cfg), "verify", str(comparison)]) == 0
    assert pe.main([*walk, "--execute"]) == 1  # CLI needs three folds: refused, nothing written

    hyp = json.loads((comparison / "hypotheses.json").read_text(encoding="utf-8"))
    assert hyp["H9"]["verdict"] == "supported", hyp["H9"]["parts"]
    budgets = json.loads((comparison / "budgets.json").read_text(encoding="utf-8"))
    done = {(r["arm"], r["timesteps_done"]) for r in budgets["runs"].values()}
    assert done == {("reference", 128), ("half", 64)} and len(budgets["runs"]) == 8
    repro_out = json.loads((comparison / "reproduction.json").read_text(encoding="utf-8"))
    assert len(repro_out) == 4 and all(r["identical"] for r in repro_out.values())
    gap = pd.read_csv(comparison / "gap.csv")
    assert set(gap["kind"]) == {"run", "paired"} and set(gap["fold"]) == {"A", "C"}
    assert hyp["outcome"]["class"] in ("Generalisation improvement", "Partial improvement",
                                       "No reliable improvement", "Deterioration")  # fmt: skip
    with pytest.raises(bc.BudgetComparisonError, match="written once"):
        bc.run_budget_comparison(context, folds, repro)
    swapped = {**folds, "A": {k: v[::-1] for k, v in folds["A"].items()}}
    with pytest.raises(bc.BudgetComparisonError, match="not comparable"):
        bc.run_budget_comparison(context, swapped, repro)
    with pytest.raises(bc.BudgetComparisonError, match="not the E10T1"):
        bc.run_budget_comparison(context, folds, {"A": repro["C"], "C": repro["A"]})

    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.profile_figures import make_budget_figures

    written = make_budget_figures(comparison, project.root / "data" / "e11_figures")
    assert len(written) == 5 and all(w.with_suffix(".json").is_file() for w in written)
