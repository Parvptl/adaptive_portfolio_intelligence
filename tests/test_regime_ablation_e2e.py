"""E12 end to end on the tiny synthetic project (D-096; ``rl`` extra).

Folds A (derived, no E0) and C (the reference split, with E0). Trains E10T1, E12F and E12N in
both folds (2 seeds), evaluates both splits and runs the comparison. It checks that the ablated
runs record 9 fewer inputs, that fold C passes the E0 comparability rule E0 + 5 - 9, that E12F
reproduces E10T1 exactly, and the write-once rule. No market data; the test split is never read.
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
from adaptive_portfolio.explainability import ablation_comparison as ac  # noqa: E402
from adaptive_portfolio.explainability import walk_forward_comparison as wc  # noqa: E402
from conftest import CONFIG_DIR  # noqa: E402
from test_ppo_wrapper import GIT  # noqa: E402
from test_profile_experiment import _project, _train_e0  # noqa: E402
from test_walk_forward_e2e import FOLD_A, FOLD_C  # noqa: E402


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> pe.Context:
    context = _project(tmp_path_factory.mktemp("ablation"))
    groups = load_yaml(context.config_dir / "turnover_k0.yaml")["evaluation"]["exposure_groups"]
    for f, fold in (("a", FOLD_A), ("c", FOLD_C)):
        for name in (f"walk_forward_{f}_k1.yaml", f"ablation_{f}_full.yaml",
                     f"ablation_{f}_noregime.yaml"):  # fmt: skip
            raw = copy.deepcopy(load_yaml(CONFIG_DIR / name))
            raw.update(base_configuration=0, seeds=[42, 43], walk_forward_fold=fold)
            raw["evaluation"].update(sweep_points=3, exposure_groups=groups)
            (context.config_dir / name).write_text(yaml.safe_dump(raw), encoding="utf-8")
    for command in (["add", "-A"], ["commit", "-q", "-m", "E10/E12 configs"]):
        subprocess.run([*GIT, "-C", str(context.root), *command], check=True, capture_output=True)
    context = pe.load_context(context.config_dir)
    _train_e0(context)
    args = ["--config-dir", str(context.config_dir), "--dataset-dir", str(context.dataset_dir),
            "--experiment-config", str(context.config_dir / "ablation_a_full.yaml")]  # fmt: skip
    assert wf.main([*args, "build-fold", "--execute"]) == 0
    return context


def _arm(project: pe.Context, name: str) -> dict:
    context = pe.load_context(project.config_dir, experiment_path=project.config_dir / name)
    assert {r["status"] for r in pe.train_arm(context, "main")} <= {"trained", "existing"}
    dirs = {}
    for split in ("train", "validation"):
        plan = pe.plan_profile_evaluation(context, split)
        target = plan.output_dir if plan.output_dir.exists() else pe.run_profile_evaluation(plan)
        assert pe.verify_profile_evaluation(target) == []
        dirs[split] = target
    return dirs


def test_ablation_end_to_end(project, monkeypatch) -> None:
    monkeypatch.setattr(wc, "FOLDS", ("A", "C"))
    monkeypatch.setattr(wc, "SEEDS", (42, 43))
    monkeypatch.setattr(ac, "DONE", 128)
    cfg = project.config_dir
    e10 = {f: _arm(project, f"walk_forward_{f}_k1.yaml") for f in ("a", "c")}
    reference = project.root / "data/processed/evaluations/reference"
    if not reference.exists():  # the synthetic stand-in for EXP-006, from E10T1_C's E0 rows
        e0 = pd.read_csv(e10["c"]["validation"] / "episode_metrics.csv")
        e0 = e0[e0["experiment"] == "E0"].assign(configuration=0)
        reference.mkdir(parents=True)
        e0[["configuration", "seed", "annualised.net_sharpe"]].to_csv(
            reference / "policy_metrics.csv", index=False)  # fmt: skip
    arms = {(f, a): _arm(project, f"ablation_{f}_{a}.yaml") for f in ("a", "c")
            for a in ("full", "noregime")}  # fmt: skip
    meta = json.loads((arms[("c", "noregime")]["validation"] / "summary.json").read_text("utf-8"))
    assert any("E0 + 5 - 9" in name for name in meta["comparability"])  # fold C rule applied
    sizes = {}
    root = project.root / "data/processed/ablation_experiments"
    for path in root.glob("*/run_config.json"):
        run = json.loads(path.read_text(encoding="utf-8"))
        ablation = run["profile_conditioning"]["experiment"].get("observation_ablation")
        sizes.setdefault(ablation, set()).add(run["environment"]["observation_size"])
    assert len(sizes[None]) == 1 and sizes["regime"] == {next(iter(sizes[None])) - 9}
    monkeypatch.setattr(ac, "FULL_SIZE", next(iter(sizes[None])))
    monkeypatch.setattr(ac, "ABLATED_SIZE", next(iter(sizes["regime"])))

    folds = {f.upper(): {"validation": [arms[(f, "full")]["validation"],
                                        arms[(f, "noregime")]["validation"]],
                         "train": [arms[(f, "full")]["train"], arms[(f, "noregime")]["train"]]}
             for f in ("a", "c")}  # fmt: skip
    repro = {f.upper(): [e10[f]["validation"], e10[f]["train"]] for f in ("a", "c")}
    context = pe.load_context(cfg, experiment_path=cfg / "ablation_c_full.yaml")
    comparison = ac.run_ablation_comparison(context, folds, repro)
    assert ac.verify_ablation_comparison(comparison) == []
    assert pe.main(["--config-dir", str(cfg), "verify", str(comparison)]) == 0
    hyp = json.loads((comparison / "hypotheses.json").read_text(encoding="utf-8"))
    assert hyp["H9"]["verdict"] == "supported", hyp["H9"]["parts"]
    out = json.loads((comparison / "reproduction.json").read_text(encoding="utf-8"))
    assert len(out) == 4 and all(r["identical"] for r in out.values())
    assert all(k.split()[2] == "E12F" for k in out)
    records = json.loads((comparison / "runs.json").read_text(encoding="utf-8"))
    assert records["all_match"] and len(records["runs"]) == 8
    assert hyp["outcome"]["class"] in ("Generalisation improvement", "Partial improvement",
                                       "No reliable improvement", "Deterioration")  # fmt: skip
    with pytest.raises(ac.AblationComparisonError, match="written once"):
        ac.run_ablation_comparison(context, folds, repro)
    swapped = {**folds, "A": {k: v[::-1] for k, v in folds["A"].items()}}
    with pytest.raises(ac.AblationComparisonError, match="not comparable"):
        ac.run_ablation_comparison(context, swapped, repro)

    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.profile_figures import make_ablation_figures

    written = make_ablation_figures(comparison, project.root / "data" / "e12_figures")
    assert len(written) == 5 and all(w.name.startswith("e12_") for w in written)
