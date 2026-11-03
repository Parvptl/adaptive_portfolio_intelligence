"""End-to-end profile experiment on a tiny synthetic project (D-085; ``rl`` extra).

Trains real (tiny-budget) E0 grid runs and profile arms from a committed synthetic Git project,
then evaluates E0-E3 on the training and validation splits. No market data; the test split of
the synthetic project is never loaded.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

from adaptive_portfolio.agents import ppo  # noqa: E402
from adaptive_portfolio.agents import profile_experiment as pe  # noqa: E402
from adaptive_portfolio.config import load_yaml  # noqa: E402
from adaptive_portfolio.data import cache  # noqa: E402
from adaptive_portfolio.data.pipeline import build_dataset, project_root_for  # noqa: E402
from adaptive_portfolio.explainability import profile_comparison as pc  # noqa: E402
from adaptive_portfolio.features.pipeline import build_feature_dataset  # noqa: E402
from conftest import CONFIG_DIR, write_feature_config, write_tiny_project  # noqa: E402
from test_ppo_wrapper import GIT, SPLITS  # noqa: E402

GRID_ID = "0123456789abcdef"


def _project(root: Path) -> pe.Context:
    config_dir = write_tiny_project(root, universe=["AAA", "BBB", "CCC"], start="2024-01-01",
                                    end="2024-06-28", splits=SPLITS)  # fmt: skip
    backtest = {"execution_lag_sessions": 1, "common_start_history_sessions": 15,
                "periods_per_year": 252,
                "strategies": [{"name": "equal_weight_monthly", "type": "equal_weight",
                                "rebalance": "monthly"}]}  # fmt: skip
    (config_dir / "backtest.yaml").write_text(yaml.safe_dump(backtest), encoding="utf-8")
    write_feature_config(config_dir)
    agent = copy.deepcopy(load_yaml(CONFIG_DIR / "agent.yaml"))
    agent.update(
        seeds=[42, 43],
        total_timesteps=128,
        grid={"learning_rate": [0.0001], "n_steps": [64], "ent_coef": [0.0]},
    )
    (config_dir / "agent.yaml").write_text(yaml.safe_dump(agent), encoding="utf-8")
    evaluation = copy.deepcopy(load_yaml(CONFIG_DIR / "evaluation.yaml"))
    evaluation["grid_id"] = GRID_ID
    (config_dir / "evaluation.yaml").write_text(yaml.safe_dump(evaluation), encoding="utf-8")
    profile = copy.deepcopy(load_yaml(CONFIG_DIR / "profile_experiment.yaml"))
    profile.update(base_configuration=0, seeds=[42, 43])
    profile["evaluation"]["sweep_points"] = 3
    profile["evaluation"]["exposure_groups"] = {"equity": ["AAA", "BBB"], "bonds": ["CCC"]}
    for spec in profile["evaluation"]["profile_sets"].values():
        spec["count"] = 4
    (config_dir / "profile_experiment.yaml").write_text(yaml.safe_dump(profile),
                                                        encoding="utf-8")  # fmt: skip
    reward = copy.deepcopy(load_yaml(CONFIG_DIR / "profile_reward_experiment.yaml"))
    reward.update(base_configuration=0, seeds=[42, 43])
    reward["evaluation"].update(sweep_points=3, exposure_groups=profile["evaluation"][
        "exposure_groups"])  # fmt: skip
    reward["evaluation"]["interaction_grid"]["points"] = 3
    for spec in reward["evaluation"]["profile_sets"].values():
        spec["count"] = 4
    (config_dir / "profile_reward_experiment.yaml").write_text(yaml.safe_dump(reward),
                                                               encoding="utf-8")  # fmt: skip
    for arm in ("low", "high"):  # E5 (D-089)
        fixed = copy.deepcopy(load_yaml(CONFIG_DIR / f"fixed_risk_{arm}.yaml"))
        fixed.update(base_configuration=0, seeds=[42, 43])
        fixed["evaluation"].update(sweep_points=3, exposure_groups=profile["evaluation"][
            "exposure_groups"])  # fmt: skip
        (config_dir / f"fixed_risk_{arm}.yaml").write_text(yaml.safe_dump(fixed),
                                                          encoding="utf-8")  # fmt: skip
    workflow = copy.deepcopy(load_yaml(CONFIG_DIR / "workflow.yaml"))
    workflow["validation_evaluation_dir"] = "data/processed/evaluations/reference"
    (config_dir / "workflow.yaml").write_text(yaml.safe_dump(workflow), encoding="utf-8")
    from adaptive_portfolio.config import load_feature_config, load_project_config

    config = load_project_config(config_dir)
    root_dir = project_root_for(config_dir)
    build_dataset(config, root_dir, provider_name="synthetic")
    build_feature_dataset(config, load_feature_config(config_dir / "features.yaml"), root_dir,
                          provider_name="synthetic")  # fmt: skip
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    (root_dir / ".gitignore").write_text("data/\n", encoding="utf-8")
    for command in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "synthetic project"]):
        subprocess.run([*GIT, "-C", str(root_dir), *command], check=True, capture_output=True)
    return pe.load_context(config_dir)


def _train_e0(context: pe.Context) -> None:
    """Full tiny E0 runs and a grid manifest in the format the D-076 discovery expects."""
    runs = []
    for spec in context.agent.run_specs():
        result = ppo.train_ppo_run(
            context.config,
            context.backtest,
            context.agent,
            spec,
            context.root,
            context.dataset_dir,
            context.feature_dir,
        )
        runs.append({"configuration": spec.configuration, "seed": spec.seed,
                     "run_id": result.run_id, "status": "completed"})  # fmt: skip
    commit = result.metadata["code"]["commit"]
    manifest = {"grid_id": GRID_ID, "runs": runs, "code": {"commit": commit, "dirty": False}}
    path = context.root / "data/processed/experiments/grids" / GRID_ID / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture(scope="module")
def trained(tmp_path_factory) -> pe.Context:
    context = _project(tmp_path_factory.mktemp("profile"))
    _train_e0(context)
    for arm in ("main", "heldout"):
        results = pe.train_arm(context, arm)
        assert [r["status"] for r in results] == ["trained", "trained"]
    # Reference E0 validation metrics (the synthetic stand-in for EXP-006), under ignored data/.
    e0 = pe.evaluate_profiles(pe.plan_profile_evaluation(context, "validation"))["episode_metrics"]
    e0 = e0[e0["experiment"] == "E0"].assign(configuration=0)
    reference = context.root / "data/processed/evaluations/reference"
    reference.mkdir(parents=True)
    e0[["configuration", "seed", "annualised.net_sharpe"]].to_csv(
        reference / "policy_metrics.csv", index=False
    )
    return context


@pytest.fixture(scope="module")
def e4_trained(trained) -> pe.Context:
    context = pe.load_context(
        trained.config_dir, experiment_path=trained.config_dir / "profile_reward_experiment.yaml"
    )
    for arm in ("main", "heldout"):
        assert [r["status"] for r in pe.train_arm(context, arm)] == ["trained", "trained"]
    return context


def test_training_records_profiles_and_resumes_without_overwriting(trained) -> None:
    root = trained.root / "data/processed/profile_experiments"
    runs = sorted(root.glob("*/metadata.json"))
    assert len(runs) == 4  # 2 arms x 2 seeds, under their own root
    e0 = list((trained.root / "data/processed/experiments").glob("*/run_config.json"))
    base = json.loads(e0[0].read_text(encoding="utf-8"))["environment"]["observation_size"]
    for path in runs:
        meta = json.loads(path.read_text(encoding="utf-8"))
        assert meta["run_kind"] == "full" and meta["split"] == "train"
        assert meta["environment"]["observation_size"] == base + 5
        profiles = np.array(meta["episode_profiles"])
        assert profiles.shape[1] == 5 and len(profiles) >= meta["episodes_completed"]
        assert ((profiles >= 0) & (profiles <= 1)).all()
        assert len({tuple(p) for p in profiles}) == len(profiles)  # one draw per episode
        arm = meta["profile_conditioning"]["arm"]
        if arm == "heldout":
            sampling = trained.experiment.arms["heldout"]
            assert not any(sampling.in_excluded_region(p) for p in profiles)
    # E0 runs stay in the existing root, with unchanged (profile-free) identities.
    assert len(e0) == 2
    assert all("profile_conditioning" not in json.loads(p.read_text()) for p in e0)
    again = pe.train_arm(trained, "main")
    assert [r["status"] for r in again] == ["existing", "existing"]  # resume, never retrain


def test_validation_evaluation_covers_e0_to_e3_and_is_written_once(trained, tmp_path) -> None:
    plan = pe.plan_profile_evaluation(trained, "validation")
    assert len(plan.checkpoints) == 4 and len(plan.e0) == 2
    assert all(plan.comparability.values()) and len(plan.comparability) == 4 * 5
    target = pe.run_profile_evaluation(plan)
    assert pe.verify_profile_evaluation(target) == []
    metrics = pd.read_csv(target / "episode_metrics.csv")
    assert set(metrics["experiment"]) == {"baseline", "E0", "E1", "E3"}
    # Every ledger lies inside the validation split: no test row is evaluated.
    assert (metrics["first_date"] >= SPLITS["validation"]["start"]).all()
    assert (metrics["last_date"] <= SPLITS["validation"]["end"]).all()
    e1 = metrics[metrics["experiment"] == "E1"]
    assert len(e1) == 2 * (1 + 4 + 4)  # seeds x (centre + two sets)
    assert e1["in_training_region"].isna().all()
    e3 = metrics[metrics["experiment"] == "E3"]
    region = e3[e3["profile_set"] == "heldout_region"]
    assert (region["in_training_region"] == False).all()  # noqa: E712
    assert (e3[e3["profile_set"] == "heldout_training"]["in_training_region"] == True).all()  # noqa: E712
    interventions = pd.read_csv(target / "interventions.csv")
    assert set(interventions["intervention"]) == {"neutral", "shuffled"}
    assert len(interventions) == 2 * 4 * 2 and (interventions["dw_vs_correct"] >= 0).all()
    state = pd.read_csv(target / "state_matched.csv")
    assert set(state["profile_set"]) == {"in_distribution", "heldout_region", "heldout_training"}
    assert ((state["dw_mean"] >= 0) & (state["dw_mean"] <= 2 / 4)).all()
    sweeps = pd.read_csv(target / "sweeps.csv")
    assert len(sweeps) == 4 * 5 * 3  # checkpoints x dimensions x points
    centre_rows = sweeps[np.isclose(sweeps["value"], 0.5)]
    assert np.allclose(centre_rows["dw_vs_centre"], 0.0, atol=1e-6)  # the sweep's midpoint
    summary = json.loads((target / "summary.json").read_text(encoding="utf-8"))
    assert summary["statistics"].startswith("descriptive only")
    assert summary["e0_reproduction"]["reproduced"] is True  # against the reference metrics
    meta = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    assert meta["rows_read_before"] == SPLITS["test"]["start"] and not meta["pipeline_check"]
    with pytest.raises(pe.ProfileExperimentError, match="written once"):
        pe.run_profile_evaluation(plan)
    tampered = tmp_path / target.name  # tamper a copy; the original is the E4 control later
    shutil.copytree(target, tampered)
    (tampered / "summary.json").write_text("{}", encoding="utf-8")
    assert pe.verify_profile_evaluation(tampered) == ["summary.json: hash differs"]


def test_training_split_evaluation_and_reproducibility(trained, tmp_path) -> None:
    plan = pe.plan_profile_evaluation(trained, "train")
    first = pe.evaluate_profiles(plan)
    second = pe.evaluate_profiles(plan)
    for name in ("episode_metrics", "state_matched", "interventions", "sweeps"):
        pd.testing.assert_frame_equal(first[name], second[name])  # deterministic
    metrics = first["episode_metrics"]
    assert (metrics["last_date"] < SPLITS["validation"]["start"]).all()
    assert plan.identity["rows_read_before"] == SPLITS["validation"]["start"]


def test_refusals_pipeline_check_and_dirty_tree(trained) -> None:
    with pytest.raises(pe.ProfileExperimentError, match="training split only"):
        pe.plan_profile_evaluation(trained, "validation", pipeline_check=True)
    with pytest.raises(pe.ProfileExperimentError, match="not in"):
        pe.plan_profile_evaluation(trained, "test")
    with pytest.raises(pe.ProfileExperimentError, match="0 matching runs"):
        pe.plan_profile_evaluation(trained, "validation", commit="ffffffff")
    stray = trained.root / "untracked.txt"
    stray.write_text("dirty", encoding="utf-8")
    try:
        plan = pe.plan_profile_evaluation(trained, "validation")
        with pytest.raises(pe.ProfileExperimentError, match="clean committed tree"):
            pe.run_profile_evaluation(plan)
        assert pe.plan_profile_evaluation(trained, "train", pipeline_check=True).pipeline_check
    finally:
        stray.unlink()


def test_comparability_detects_a_changed_environment(trained) -> None:
    _, configs = pe.discover_profile_checkpoints(trained, pipeline_check=False)
    e0 = [json.loads(p.read_text()) for p in
          (trained.root / "data/processed/experiments").glob("*/run_config.json")]  # fmt: skip
    changed = copy.deepcopy(configs)
    changed[0]["environment"]["cost_rate"] = 0.003
    with pytest.raises(pe.ProfileExperimentError, match="not comparable"):
        pe.comparability(changed, e0, pipeline_check=False)
    resized = copy.deepcopy(configs)
    resized[0]["environment"]["observation_size"] += 1
    with pytest.raises(pe.ProfileExperimentError, match="observation size"):
        pe.comparability(resized, e0, pipeline_check=False)
    assert cache.short_hash(configs[0]) in {c.run_id for c in pe.discover_profile_checkpoints(
        trained, pipeline_check=False)[0]}  # fmt: skip


def test_cli_plan_and_guards(trained, capsys) -> None:
    args = ["--config-dir", str(trained.config_dir)]
    assert pe.main([*args, "plan"]) == 0
    assert "profile set heldout_region: 4 profiles" in capsys.readouterr().out
    assert pe.main([*args, "train", "--arm", "main"]) == 2  # needs --execute
    assert pe.main([*args, "train", "--arm", "main", "--smoke", "--execute"]) == 2
    assert pe.main([*args, "evaluate", "--split", "train"]) == 0  # plan only
    assert "nothing evaluated" in capsys.readouterr().out
    assert pe.main([*args, "evaluate", "--split", "validation", "--pipeline-check"]) == 1


# --------------------------------------------------------------------------
# E4: profile-dependent reward (D-088)
# --------------------------------------------------------------------------


def test_e4_training_records_reward_components(e4_trained) -> None:
    root = e4_trained.root / "data/processed/profile_reward_experiments"
    runs = sorted(root.glob("*/metadata.json"))
    assert len(runs) == 4  # separate root; the E1 runs are untouched
    assert len(list((e4_trained.root / "data/processed/profile_experiments").glob("*/"))) == 4
    for path in runs:
        meta = json.loads(path.read_text(encoding="utf-8"))
        assert meta["profile_conditioning"]["reward"]["gamma_max"] == 10.0
        episodes = [e for e in meta["episode_reward_components"] if e["steps"]]
        assert len(episodes) >= meta["episodes_completed"]
        spec = e4_trained.experiment.reward
        for episode in episodes:
            assert episode["lambda"] == pytest.approx(spec.penalty_coefficient(episode["profile"]))
            assert episode["reward"] == pytest.approx(
                episode["reward_base"] - episode["risk_penalty"]
            )
            assert episode["risk_penalty"] >= 0 and episode["realised_variance"] >= 0


def test_e4_evaluations_and_prespecified_comparison(e4_trained, trained) -> None:
    targets = {}
    for split in ("train", "validation"):
        plan = pe.plan_profile_evaluation(e4_trained, split)
        targets[split] = pe.run_profile_evaluation(plan)
        assert pe.verify_profile_evaluation(targets[split]) == []
        assert "reward" in plan.identity["experiment"]
    metrics = pd.read_csv(targets["validation"] / "episode_metrics.csv")
    assert set(metrics["experiment"]) == {"baseline", "E0", "E4", "E4H"}
    e4 = metrics[metrics["experiment"].isin(["E4", "E4H"])]
    assert np.allclose(e4["e4_reward"], e4["e4_reward_base"] - e4["e4_risk_penalty"])
    acceptance = np.minimum(e4["profile_risk_tolerance"], e4["profile_risk_capacity"])
    assert np.allclose(e4["e4_lambda"], 9 * (1 - acceptance))
    assert (metrics["last_date"] <= SPLITS["validation"]["end"]).all()
    contrasts = pd.read_csv(targets["validation"] / "contrasts.csv")
    interactions = pd.read_csv(targets["validation"] / "interactions.csv")
    assert len(contrasts) == 4 and (contrasts["dw"] >= 0).all()
    assert len(interactions) == 4 * 3 * 3 * 3  # checkpoints x pairs x 3 x 3 points
    summary = json.loads((targets["validation"] / "summary.json").read_text(encoding="utf-8"))
    assert summary["e0_reproduction"]["reproduced"] is True
    control = pe.plan_profile_evaluation(trained, "validation").output_dir
    if not control.exists():
        control = pe.run_profile_evaluation(pe.plan_profile_evaluation(trained, "validation"))
    comparison = pc.run_comparison(e4_trained, targets["validation"], control)
    assert pc.verify_comparison(comparison) == []
    hypotheses = pc.load_hypotheses(comparison)
    assert sorted(hypotheses) == [f"H{i}" for i in range(1, 8)]
    assert all(h["verdict"] in ("supported", "partially supported", "not supported")
               for h in hypotheses.values())  # fmt: skip
    diffs = pd.read_csv(comparison / "paired_differences.csv")
    assert {"E4 - E0", "E4 - E1"} == set(diffs["comparison"])
    assert (diffs["n"] == 2).all()
    exploitation = json.loads((comparison / "exploitation.json").read_text(encoding="utf-8"))
    assert len(exploitation["training_episodes"]) == 4
    with pytest.raises(pc.ComparisonError, match="written once"):
        pc.run_comparison(e4_trained, targets["validation"], control)
    with pytest.raises(pc.ComparisonError, match="not comparable"):
        pc.run_comparison(e4_trained, targets["train"], control)  # different splits
    with pytest.raises(pc.ComparisonError):
        pc.run_comparison(e4_trained, control, targets["validation"])  # swapped roles
    args = ["--config-dir", str(e4_trained.config_dir), "verify", str(comparison)]
    assert pe.main(args) == 0
    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.profile_figures import make_figures

    out = e4_trained.root / "data" / "figures"  # under ignored data/: keeps the tree clean
    written = make_figures(targets["validation"], control, comparison, out)
    assert len(written) == 3 and all(p.is_file() and p.with_suffix(".json").is_file()
                                     for p in written)  # fmt: skip


# --------------------------------------------------------------------------
# E5: fixed risk aversion (D-089)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def e5_trained(trained) -> dict[str, pe.Context]:
    contexts = {}
    for arm in ("low", "high"):
        context = pe.load_context(
            trained.config_dir, experiment_path=trained.config_dir / f"fixed_risk_{arm}.yaml"
        )
        assert [r["status"] for r in pe.train_arm(context, "main")] == ["trained", "trained"]
        contexts[arm] = context
    return contexts


def test_e5_training_evaluation_and_comparison(e5_trained) -> None:
    from adaptive_portfolio.explainability import fixed_risk_comparison as fc

    root = e5_trained["low"].root / "data/processed/fixed_risk_experiments"
    lambdas = []
    for path in sorted(root.glob("*/metadata.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        episodes = [e for e in meta["episode_reward_components"] if e["steps"]]
        lambdas.append(sorted({e["lambda"] for e in episodes}))  # constant within each run
        assert all(e["profile"] == [0.5] * 5 for e in episodes)  # no profile sampling
    assert sorted(lambdas) == [[0.0], [0.0], [9.0], [9.0]]
    dirs = {}
    for arm, context in e5_trained.items():
        for split in ("train", "validation"):
            target = pe.run_profile_evaluation(pe.plan_profile_evaluation(context, split))
            assert pe.verify_profile_evaluation(target) == []
            metrics = pd.read_csv(target / "episode_metrics.csv")
            label = "E5L" if arm == "low" else "E5H"
            assert set(metrics["experiment"]) == {"baseline", "E0", label}
            assert set(metrics.loc[metrics["experiment"] == label, "profile_set"]) == {"centre"}
            dirs[(arm, split)] = target
    comparison = fc.run_fixed_comparison(
        e5_trained["low"], dirs[("low", "validation")], dirs[("high", "validation")],
        dirs[("low", "train")], dirs[("high", "train")],
    )  # fmt: skip
    assert fc.verify_fixed_comparison(comparison) == []
    hyp = json.loads((comparison / "hypotheses.json").read_text(encoding="utf-8"))
    assert sorted(k for k in hyp if k.startswith("H")) == [f"H{i}" for i in range(1, 9)]
    assert hyp["outcome"]["class"][0] in "ABC"
    diffs = pd.read_csv(comparison / "paired_differences.csv")
    assert set(diffs["split"]) == {"train", "validation"} and (diffs["n"] == 2).all()
    with pytest.raises(fc.FixedRiskComparisonError, match="written once"):
        fc.run_fixed_comparison(e5_trained["low"], dirs[("low", "validation")],
                                dirs[("high", "validation")], dirs[("low", "train")],
                                dirs[("high", "train")])  # fmt: skip
    with pytest.raises(fc.FixedRiskComparisonError):  # swapped arms: low lambda must be lower
        fc.run_fixed_comparison(e5_trained["low"], dirs[("high", "validation")],
                                dirs[("low", "validation")], dirs[("high", "train")],
                                dirs[("low", "train")])  # fmt: skip
    args = ["--config-dir", str(e5_trained["low"].config_dir), "verify", str(comparison)]
    assert pe.main(args) == 0
    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.profile_figures import make_fixed_risk_figures

    written = make_fixed_risk_figures(comparison, e5_trained["low"].root / "data" / "e5_figures")
    assert len(written) == 1 and written[0].with_suffix(".json").is_file()
