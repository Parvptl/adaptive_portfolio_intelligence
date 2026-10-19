"""Milestone 5.3: PPO training wrapper (needs the ``rl`` extra).

No test calls ``learn()``: training is not run until the team approves the throughput smoke
test. Models here are untrained and used only for construction, inference and saving.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import warnings
from pathlib import Path

import numpy as np
import pytest
import yaml

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

import torch  # noqa: E402
from stable_baselines3 import PPO  # noqa: E402
from stable_baselines3.common.env_checker import check_env as sb3_check_env  # noqa: E402

from adaptive_portfolio.agents import ppo, run_safety  # noqa: E402
from adaptive_portfolio.config import (  # noqa: E402
    load_agent_config,
    load_backtest_config,
    load_feature_config,
    load_project_config,
)
from adaptive_portfolio.data import cache  # noqa: E402
from adaptive_portfolio.data.pipeline import build_dataset, project_root_for  # noqa: E402
from adaptive_portfolio.environment.observation import FeatureScaler  # noqa: E402
from adaptive_portfolio.environment.portfolio_env import make_training_env  # noqa: E402
from adaptive_portfolio.features.pipeline import build_feature_dataset  # noqa: E402
from conftest import CONFIG_DIR, write_feature_config, write_tiny_project  # noqa: E402
from test_portfolio_env import _env  # noqa: E402

AGENT = load_agent_config(CONFIG_DIR / "agent.yaml")
SPEC = AGENT.run_specs()[13]  # configuration 2 (lr 3e-4, n_steps 1024, ent 0), seed 45
# A clean, committed code state for identity unit tests (D-075).
CODE = {"git_available": True, "commit": "0" * 40, "dirty": False, "changed_paths": 0}
GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
       "-c", "commit.gpgsign=false"]  # fmt: skip
SPLITS = {
    "train": {"start": "2024-01-01", "end": "2024-03-29"},
    "validation": {"start": "2024-04-01", "end": "2024-05-31"},
    "test": {"start": "2024-06-01", "end": "2024-06-28"},
}


def test_build_model_sets_every_hyperparameter_explicitly() -> None:
    model = ppo.build_model(_env(), AGENT, SPEC)
    assert (model.learning_rate, model.n_steps, model.ent_coef) == (3e-4, 1024, 0.0)
    assert model.seed == 45 and model.batch_size == 64 and model.n_epochs == 10
    assert (model.gamma, model.gae_lambda, model.vf_coef, model.max_grad_norm) == (
        0.99,
        0.95,
        0.5,
        0.5,
    )
    assert model.clip_range(1.0) == 0.2 and model.clip_range_vf is None
    assert model.device.type == "cpu" and model.num_timesteps == 0
    layers = [m for m in model.policy.mlp_extractor.policy_net if isinstance(m, torch.nn.Linear)]
    assert [m.out_features for m in layers] == [64, 64]
    assert isinstance(model.policy.mlp_extractor.policy_net[1], torch.nn.Tanh)
    assert torch.all(model.policy.log_std == 0.0)


def test_same_seed_gives_identical_initial_models_and_different_seeds_differ() -> None:
    # Determinism at construction (D-075); no training. Full-run reproducibility is not
    # verified here (that would need training).
    first = ppo.build_model(_env(), AGENT, SPEC).policy.state_dict()
    again = ppo.build_model(_env(), AGENT, SPEC).policy.state_dict()
    other = ppo.build_model(_env(), AGENT, AGENT.run_specs()[14]).policy.state_dict()
    assert all(torch.equal(first[k], again[k]) for k in first)
    assert not all(torch.equal(first[k], other[k]) for k in first)


def test_environment_passes_the_stable_baselines3_checker_and_untrained_inference() -> None:
    env = _env()
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # D-072: no action-space (or any other) warning
        sb3_check_env(env, warn=True)
    model = ppo.build_model(env, AGENT, SPEC)
    observation, _ = env.reset(seed=0)
    action, _ = model.predict(observation, deterministic=True)
    assert action.shape == (5,) and np.abs(action).max() <= 1.0
    again, _ = model.predict(observation, deterministic=True)
    assert np.array_equal(action, again)
    _, reward, _, _, info = env.step(action)  # inference only: the policy is not updated
    assert np.isfinite(reward)
    assert np.array_equal(info["logits"], 5.0 * action.astype(np.float64))  # exact (D-072)


def test_run_identity_rules_and_output_dir(tmp_path: Path) -> None:
    env = _env()
    env.provenance = {"processed_dataset_id": "x", "train_prefix_sha256": {}}
    full = ppo.run_identity(env, AGENT, SPEC, total_timesteps=100_000, run_kind="full", code=CODE)
    assert full == ppo.run_identity(
        env, AGENT, SPEC, total_timesteps=100_000, run_kind="full", code=CODE
    )
    json.dumps(full)  # serialisable
    smoke = ppo.run_identity(env, AGENT, SPEC, total_timesteps=2048, run_kind="smoke", code=CODE)
    other_seed = ppo.run_identity(
        env, AGENT, AGENT.run_specs()[14], total_timesteps=100_000, run_kind="full", code=CODE
    )
    other_commit = ppo.run_identity(
        env,
        AGENT,
        SPEC,
        total_timesteps=100_000,
        run_kind="full",
        code={**CODE, "commit": "1" * 40},
    )
    dirty = {**CODE, "dirty": True, "diff_sha256": "f" * 64}
    smoke_dirty = ppo.run_identity(
        env, AGENT, SPEC, total_timesteps=2048, run_kind="smoke", code=dirty
    )
    ids = {cache.short_hash(x) for x in (full, smoke, other_seed, other_commit, smoke_dirty)}
    assert len(ids) == 5  # seed, budget, run kind and exact code state all change the id
    assert full["code"] == {k: CODE.get(k) for k in ("git_available", "commit", "dirty",
                                                     "diff_sha256")}  # fmt: skip
    assert smoke_dirty["code"]["diff_sha256"] == "f" * 64
    assert full["determinism"]["torch_use_deterministic_algorithms"] is True
    assert full["split"] == "train" and full["environment"]["action_space"] == [-1.0, 1.0]
    assert set(full["versions"]) >= {"stable_baselines3", "torch", "gymnasium", "numpy"}
    directory = ppo.run_output_dir(AGENT, full, tmp_path)
    assert directory.parent == tmp_path / "data" / "processed" / "experiments"
    with pytest.raises(ppo.TrainingError, match="smoke run"):
        ppo.run_identity(env, AGENT, SPEC, total_timesteps=2048, run_kind="full", code=CODE)
    with pytest.raises(ppo.TrainingError, match="fewer timesteps"):
        ppo.run_identity(env, AGENT, SPEC, total_timesteps=100_000, run_kind="smoke", code=CODE)
    with pytest.raises(ppo.TrainingError, match="not one of the configured"):
        bad = ppo.PPORunSpec(0, 0.5, 512, 0.0, 42)
        ppo.run_identity(env, AGENT, bad, total_timesteps=100_000, run_kind="full", code=CODE)


def test_run_outputs_are_complete_and_reloadable(tmp_path: Path) -> None:
    env = _env()
    env.provenance = {"processed_dataset_id": "x", "train_prefix_sha256": {}}
    identity = ppo.run_identity(env, AGENT, SPEC, total_timesteps=2048, run_kind="smoke", code=CODE)
    model = ppo.build_model(env, AGENT, SPEC)  # untrained
    metadata = ppo.write_run_outputs(tmp_path, model, env, identity, {"status": "test"})
    assert {p.name for p in tmp_path.iterdir()} == {
        "model.zip",
        "scaler.json",
        "run_config.json",
        "metadata.json",
    }
    assert json.loads((tmp_path / "run_config.json").read_text(encoding="utf-8")) == identity
    assert metadata["run_id"] == cache.short_hash(identity)
    assert metadata["files_sha256"]["model.zip"] == cache.file_sha256(tmp_path / "model.zip")
    assert FeatureScaler.load(tmp_path / "scaler.json") == env.scaler
    loaded = PPO.load(tmp_path / "model.zip", device="cpu")
    for name, tensor in model.policy.state_dict().items():
        assert torch.equal(tensor, loaded.policy.state_dict()[name])


def _tiny_project(root: Path) -> tuple[Path, Path, Path]:
    config_dir = write_tiny_project(
        root, universe=["AAA", "BBB", "CCC"], start="2024-01-01", end="2024-06-28", splits=SPLITS
    )
    backtest = {
        "execution_lag_sessions": 1,
        "common_start_history_sessions": 15,
        "strategies": [
            {"name": "equal_weight_monthly", "type": "equal_weight", "rebalance": "monthly"}
        ],
    }
    (config_dir / "backtest.yaml").write_text(yaml.safe_dump(backtest), encoding="utf-8")
    write_feature_config(config_dir)
    shutil.copy(CONFIG_DIR / "agent.yaml", config_dir / "agent.yaml")
    config = load_project_config(config_dir)
    root_dir = project_root_for(config_dir)
    dataset = build_dataset(config, root_dir, provider_name="synthetic")
    features = load_feature_config(config_dir / "features.yaml")
    feature_set = build_feature_dataset(config, features, root_dir, provider_name="synthetic")
    # Commit the synthetic project (data ignored) so that full runs pass the code policy.
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    (root_dir / ".gitignore").write_text("data/\n", encoding="utf-8")
    for command in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "synthetic project"]):
        subprocess.run([*GIT, "-C", str(root_dir), *command], check=True, capture_output=True)
    return config_dir, dataset.processed_dir, feature_set.output_dir


def test_training_env_provenance_and_cli_dry_run(tmp_path: Path, capsys) -> None:
    config_dir, dataset_dir, feature_dir = _tiny_project(tmp_path)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    env = make_training_env(config, backtest, dataset_dir, feature_dir)
    rows = env.provenance["loaded_rows"]
    assert env.provenance["last_date"] < SPLITS["validation"]["start"]
    assert env.provenance["train_prefix_sha256"]["returns.csv"] == cache.head_sha256(
        dataset_dir / "returns.csv", rows
    )
    args = ["--config-dir", str(config_dir), "--dataset-dir", str(dataset_dir)]
    args += ["--feature-dir", str(feature_dir), "--configuration", "0", "--seed", "42"]
    assert ppo.main([*args, "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN (no training, nothing written)" in out and "100000 timesteps" in out
    assert not (tmp_path / "data" / "processed" / "experiments").exists()
    assert ppo.main([*args, "--dry-run", "--smoke", "--timesteps", "2048"]) == 0
    assert "run kind smoke, 2048 timesteps" in capsys.readouterr().out
    assert ppo.main([*args, "--dry-run", "--smoke"]) == 2  # --smoke needs --timesteps
    # Only --dataset-dir: the feature set is derived from that dataset (features.yaml).
    derived = ["--config-dir", str(config_dir), "--dataset-dir", str(dataset_dir)]
    assert ppo.main([*derived, "--configuration", "0", "--seed", "42", "--dry-run"]) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert ppo.main([*args[:-2], "--seed", "7", "--dry-run"]) == 2  # not a configured seed


def test_existing_run_directory_is_never_overwritten(tmp_path: Path) -> None:
    config_dir, dataset_dir, feature_dir = _tiny_project(tmp_path)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    agent = load_agent_config(config_dir / "agent.yaml")
    env = make_training_env(config, backtest, dataset_dir, feature_dir)
    code = run_safety.code_provenance(project_root_for(config_dir))
    identity = ppo.run_identity(env, agent, SPEC, total_timesteps=2048, run_kind="smoke", code=code)
    existing = ppo.run_output_dir(agent, identity, project_root_for(config_dir))
    existing.mkdir(parents=True)
    with pytest.raises(ppo.TrainingError, match="never overwritten"):  # raised before training
        ppo.train_ppo_run(
            config, backtest, agent, SPEC, project_root_for(config_dir), dataset_dir,
            feature_dir, total_timesteps=2048, run_kind="smoke",
        )  # fmt: skip
    assert list(existing.iterdir()) == []
