"""E9 end to end on the tiny synthetic project (D-093; ``rl`` extra).

The synthetic grid has seeds 42-43; the E9 configs add extension seeds 47-48 (the stand-in for
47-56). Trains E7B/E7T1, E8B/E8T1 and E9B/E9T1, evaluates both splits, runs ``compare-confirm``
through the CLI and checks the seed extension, the reproduction and the write-once rule. No market
data; the synthetic test split is never loaded.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import subprocess
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

from adaptive_portfolio.agents import ppo  # noqa: E402
from adaptive_portfolio.agents import profile_experiment as pe  # noqa: E402
from adaptive_portfolio.config import load_yaml  # noqa: E402
from adaptive_portfolio.explainability import confirmation_comparison as cc  # noqa: E402
from conftest import CONFIG_DIR  # noqa: E402
from test_ppo_wrapper import GIT  # noqa: E402
from test_profile_experiment import _project, _train_e0  # noqa: E402


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> pe.Context:
    context = _project(tmp_path_factory.mktemp("confirm"))
    groups = load_yaml(context.config_dir / "turnover_k0.yaml")["evaluation"]["exposure_groups"]
    names = {f"turnover_refine_k{k}.yaml": [42, 43] for k in (0, 1)}
    names |= {f"confirmation_k{k}.yaml": [42, 43, 47, 48] for k in (0, 1)}
    for name, seeds in names.items():
        raw = copy.deepcopy(load_yaml(CONFIG_DIR / name))
        raw.update(base_configuration=0, seeds=seeds)
        if "extension_seeds" in raw:
            raw["extension_seeds"] = [47, 48]
        raw["evaluation"].update(sweep_points=3, exposure_groups=groups)
        (context.config_dir / name).write_text(yaml.safe_dump(raw), encoding="utf-8")
    for command in (["add", "-A"], ["commit", "-q", "-m", "E8/E9 configs"]):
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


def test_extension_seed_rules(project) -> None:
    path = project.config_dir / "confirmation_k1.yaml"
    context = pe.load_context(project.config_dir, experiment_path=path)
    spec = pe.run_spec(context, 47)
    grid = pe.run_spec(context, 42)
    assert spec == dataclasses.replace(grid, seed=47) and spec not in context.agent.run_specs()
    profile = pe.profile_training(context, "main")
    assert ppo.is_extension_spec(context.agent, spec, profile)
    assert not ppo.is_extension_spec(context.agent, spec, None)  # never for E0 grid runs
    undeclared = SimpleNamespace(experiment={"extension_seeds": []})
    assert not ppo.is_extension_spec(context.agent, spec, undeclared)
    other = dataclasses.replace(spec, learning_rate=0.5)  # not a grid spec except the seed
    assert not ppo.is_extension_spec(context.agent, other, profile)
    with pytest.raises(pe.ProfileExperimentError, match="no grid run"):
        pe.run_spec(context, 99)
    raw = load_yaml(project.config_dir / "confirmation_k0.yaml")
    bad = project.config_dir / "bad_confirmation.yaml"
    bad.write_text(yaml.safe_dump({**raw, "extension_seeds": [42, 47]}), encoding="utf-8")
    with pytest.raises(pe.ProfileExperimentError, match="grid seeds"):
        pe.load_context(project.config_dir, experiment_path=bad)
    bad.unlink()


def test_e9_confirmation_end_to_end(project, monkeypatch) -> None:
    monkeypatch.setattr(cc, "PRIMARY_SEEDS", (47, 48))
    monkeypatch.setattr(cc, "REPRODUCTION_SEEDS", (42, 43))
    monkeypatch.setattr(cc, "POPULATIONS", {"primary": (47, 48), "reproduction": (42, 43),
                                            "pooled": (42, 43, 47, 48)})  # fmt: skip
    e7 = [_arm(project, f"turnover_k{k}.yaml")[1] for k in (0, 1)]
    reference = project.root / "data/processed/evaluations/reference"
    if not reference.exists():  # the synthetic stand-in for EXP-006, from E7B's E0 rows
        e0 = pd.read_csv(e7[0]["validation"] / "episode_metrics.csv")
        e0 = e0[e0["experiment"] == "E0"].assign(configuration=0)
        reference.mkdir(parents=True)
        e0[["configuration", "seed", "annualised.net_sharpe"]].to_csv(
            reference / "policy_metrics.csv", index=False)  # fmt: skip
    e8 = [_arm(project, f"turnover_refine_k{k}.yaml")[1] for k in (0, 1)]
    e9 = [_arm(project, f"confirmation_k{k}.yaml") for k in (0, 1)]
    meta = json.loads((e9[1][1]["validation"] / "metadata.json").read_text(encoding="utf-8"))
    assert sorted(c["seed"] for c in meta["checkpoints"]) == [42, 43, 47, 48]
    assert sorted(c["seed"] for c in meta["e0_checkpoints"]) == [42, 43]  # E0 only on the grid
    k0 = project.config_dir / "confirmation_k0.yaml"
    args = ["--config-dir", str(project.config_dir), "--experiment-config", str(k0),
            "compare-confirm",
            "--validation", *[str(d["validation"]) for _, d in e9],
            "--train", *[str(d["train"]) for _, d in e9],
            "--reproduce-validation", str(e8[0]["validation"]), str(e8[1]["validation"]),
            str(e7[0]["validation"]), str(e7[1]["validation"]),
            "--reproduce-train", str(e8[0]["train"]), str(e8[1]["train"]), str(e7[0]["train"]),
            str(e7[1]["train"]), "--execute"]  # fmt: skip
    assert pe.main(args) == 0
    (comparison,) = [p for p in (project.root / "data/processed/confirmation_comparisons")
                     .iterdir() if p.is_dir()]  # fmt: skip
    assert cc.verify_confirmation(comparison) == []
    assert pe.main(["--config-dir", str(project.config_dir), "verify", str(comparison)]) == 0

    hyp = json.loads((comparison / "hypotheses.json").read_text(encoding="utf-8"))
    assert sorted(k for k in hyp if k.startswith("H")) == sorted(f"H{i}" for i in range(1, 11))
    assert hyp["H9"]["verdict"] == "supported"  # seeds 42-43 equal E8 and E7 exactly
    assert hyp["H5"]["parts"]["cost drag = gross - net cumulative (<= 1e-12)"]
    assert hyp["outcome"]["class"] in ("Confirmation", "Partial confirmation",
                                       "No reliable improvement", "Deterioration")  # fmt: skip
    repro = json.loads((comparison / "reproduction.json").read_text(encoding="utf-8"))
    assert len(repro) == 8 and all(r["identical"] for r in repro.values())
    diffs = pd.read_csv(comparison / "paired_differences.csv")
    assert set(diffs["population"]) == {"primary", "reproduction", "pooled"}
    assert set(diffs.groupby("population")["n"].first()) == {2, 4}
    base = json.loads((comparison / "baselines.json").read_text(encoding="utf-8"))
    assert base["split"] == "validation" and base["strategies"]

    context = e9[0][0]
    validation = [d["validation"] for _, d in e9]
    train = [d["train"] for _, d in e9]
    repro_dirs = {"0:E9B = E8B": [e8[0]["validation"], e8[0]["train"]],
                  "1:E9T1 = E8T1": [e8[1]["validation"], e8[1]["train"]],
                  "0:E9B = E7B": [e7[0]["validation"], e7[0]["train"]],
                  "1:E9T1 = E7T1": [e7[1]["validation"], e7[1]["train"]]}  # fmt: skip
    with pytest.raises(cc.ConfirmationError, match="written once"):
        cc.run_confirmation(context, validation, train, repro_dirs)
    with pytest.raises(cc.ConfirmationError, match="not comparable"):
        cc.run_confirmation(context, [e8[0]["validation"], e8[1]["validation"]],
                            [e8[0]["train"], e8[1]["train"]], repro_dirs)  # fmt: skip
    with pytest.raises(cc.ConfirmationError, match="not comparable"):
        cc.run_confirmation(context, validation[::-1], train[::-1], repro_dirs)

    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.profile_figures import make_confirmation_figures

    written = make_confirmation_figures(comparison, project.root / "data" / "e9_figures")
    assert len(written) == 3 and all(w.with_suffix(".json").is_file() for w in written)
