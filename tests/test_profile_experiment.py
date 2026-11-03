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


def test_validation_evaluation_covers_e0_to_e3_and_is_written_once(trained) -> None:
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
    assert summary["e0_reproduction"]["checked"] is False  # no EXP-006 in a synthetic project
    meta = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    assert meta["rows_read_before"] == SPLITS["test"]["start"] and not meta["pipeline_check"]
    with pytest.raises(pe.ProfileExperimentError, match="written once"):
        pe.run_profile_evaluation(plan)
    (target / "summary.json").write_text("{}", encoding="utf-8")
    assert pe.verify_profile_evaluation(target) == ["summary.json: hash differs"]


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
