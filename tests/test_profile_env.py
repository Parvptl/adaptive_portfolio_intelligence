"""Profile-conditioned observations, reward integrity and PPO integration (D-085; ``rl`` extra).

Small synthetic data only. The reward-integrity tests drive the wrapped and the unwrapped
environment with the same action sequence and require identical rewards, ledgers and info.
"""

from __future__ import annotations

import hashlib
import subprocess
import warnings
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

import torch  # noqa: E402
from stable_baselines3.common.env_checker import check_env as sb3_check_env  # noqa: E402
from stable_baselines3.common.monitor import Monitor  # noqa: E402

from adaptive_portfolio.agents import ppo  # noqa: E402
from adaptive_portfolio.config import load_agent_config  # noqa: E402
from adaptive_portfolio.environment import rewards  # noqa: E402
from adaptive_portfolio.environment.profile_env import ProfileConditionedEnv  # noqa: E402
from adaptive_portfolio.environment.profiles import (  # noqa: E402
    ProfileError,
    ProfileSampling,
    neutral_profile,
    profile_stream,
)
from conftest import CONFIG_DIR  # noqa: E402
from test_portfolio_env import N_ASSETS, N_FEATURES, _env  # noqa: E402

AGENT = load_agent_config(CONFIG_DIR / "agent.yaml")
SPEC = AGENT.run_specs()[20]  # configuration 4 (lr 1e-4, n_steps 512, ent 0), seed 42
BASE_SIZE = N_FEATURES + 9 + N_ASSETS + 1
REPO = Path(__file__).resolve().parents[1]


def _wrapped(seed: int = 42, **kwargs) -> ProfileConditionedEnv:
    return ProfileConditionedEnv(_env(), kwargs.pop("sampling", ProfileSampling()), seed=seed,
                                 **kwargs)  # fmt: skip


def _actions(n: int, seed: int = 3) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    return [rng.uniform(-1, 1, N_ASSETS + 1).astype(np.float32) for _ in range(n)]


def test_observation_appends_the_profile_last_with_unit_bounds() -> None:
    env = _wrapped()
    base = env.unwrapped.observation_space
    space = env.observation_space
    assert space.shape == (BASE_SIZE + 5,) and space.dtype == np.float32
    assert np.array_equal(space.low[:-5], base.low) and np.array_equal(space.high[:-5], base.high)
    assert np.array_equal(space.low[-5:], np.zeros(5)) and np.array_equal(space.high[-5:],
                                                                         np.ones(5))  # fmt: skip
    observation, info = env.reset(seed=42)
    expected = ProfileSampling().sample(profile_stream(42, 5))
    assert np.array_equal(info["profile"], expected)
    assert np.array_equal(observation[-5:], expected.astype(np.float32))
    plain, _ = _env().reset(seed=42)
    assert np.array_equal(observation[:-5], plain)  # existing order unchanged, profile last
    assert space.contains(observation) and np.isfinite(observation).all()


def test_profile_is_constant_within_an_episode_and_resampled_between() -> None:
    env = _wrapped()
    env.reset(seed=42)
    profile = env.profile.copy()
    finished = False
    for action in _actions(env.unwrapped.n_steps):
        observation, _, finished, _, info = env.step(action)
        assert np.array_equal(observation[-5:], profile.astype(np.float32))
        assert np.array_equal(info["profile"], profile)
        assert env.observation_space.contains(observation) and np.isfinite(observation).all()
    assert finished
    env.reset()
    assert not np.array_equal(env.profile, profile)  # a new episode draws a new profile
    assert len(env.history) == 2 and env.history[0] == profile.tolist()
    with pytest.raises(ProfileError):
        _wrapped().step(_actions(1)[0])  # reset first


def test_profile_sequence_is_reproducible_and_seed_dependent() -> None:
    def sequence(seed: int) -> list[list[float]]:
        env = _wrapped(seed=0)
        env.reset(seed=seed)
        for _ in range(3):
            env.reset()
        return env.history

    assert sequence(42) == sequence(42)
    assert sequence(42) != sequence(43)
    rng = profile_stream(42, 5)
    assert sequence(42) == [ProfileSampling().sample(rng).tolist() for _ in range(4)]


def test_fixed_and_option_profiles_for_evaluation() -> None:
    fixed = ProfileConditionedEnv(_env(), None, seed=0, fixed_profile=[0.1, 0.2, 0.3, 0.4, 0.5])
    fixed.reset()
    assert np.allclose(fixed.profile, [0.1, 0.2, 0.3, 0.4, 0.5])
    env = _wrapped()
    observation, _ = env.reset(options={"profile": neutral_profile()})
    assert np.array_equal(observation[-5:], np.full(5, 0.5, np.float32))
    with pytest.raises(ProfileError):
        env.reset(options={"profile": [2, 0, 0, 0, 0]})
    with pytest.raises(ProfileError):
        ProfileConditionedEnv(_env(), None, seed=0)


def test_reward_ledger_and_info_are_identical_to_the_unwrapped_environment() -> None:
    wrapped, plain = _wrapped(), _env()
    wrapped.reset(seed=42)
    plain.reset(seed=42)
    rewards_wrapped, rewards_plain = [], []
    for action in _actions(plain.n_steps):
        _, r_w, done_w, trunc_w, info_w = wrapped.step(action)
        _, r_p, done_p, trunc_p, info_p = plain.step(action)
        rewards_wrapped.append(r_w)
        rewards_plain.append(r_p)
        assert (done_w, trunc_w) == (done_p, trunc_p)
        for key, value in info_p.items():
            assert np.array_equal(np.asarray(info_w[key]), np.asarray(value)), key
    assert rewards_wrapped == rewards_plain  # bit-for-bit
    assert wrapped.unwrapped.ledger_frame().equals(plain.ledger_frame())
    # The D-064 definition from the ledger reproduces the step rewards exactly.
    ledger = wrapped.unwrapped.ledger_frame()
    values = ledger.set_index(wrapped.unwrapped.dates.get_indexer(ledger["date"]))["value"]
    expected = rewards.decision_aligned_rewards(
        values, plain.decisions, plain.last_row, plain.lag, plain.settings.initial_capital
    )
    assert np.allclose(rewards_wrapped, expected, rtol=0, atol=1e-15)


def test_reward_and_accounting_modules_are_unchanged_in_this_extension() -> None:
    # The extension must not edit the reward, environment, action or simulator code: compare
    # each file with the last commit (skipped outside a Git checkout).
    files = ["src/adaptive_portfolio/environment/rewards.py",
             "src/adaptive_portfolio/environment/portfolio_env.py",
             "src/adaptive_portfolio/environment/actions.py",
             "src/adaptive_portfolio/environment/observation.py",
             "src/adaptive_portfolio/evaluation/simulator.py"]  # fmt: skip
    for name in files:
        result = subprocess.run(["git", "-C", str(REPO), "show", f"26a2abd:{name}"],
                                capture_output=True, check=False)  # fmt: skip
        if result.returncode != 0:
            pytest.skip("the baseline commit is not available in this checkout")
        current = (REPO / name).read_bytes().replace(b"\r\n", b"\n")
        assert (
            hashlib.sha256(current).digest()
            == hashlib.sha256(result.stdout.replace(b"\r\n", b"\n")).digest()
        ), name


def test_sb3_checker_ppo_dimensions_training_and_prediction() -> None:
    env = _wrapped()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sb3_check_env(env, warn=True)
    model = ppo.build_model(Monitor(_wrapped()), AGENT, SPEC)
    assert model.observation_space.shape == (BASE_SIZE + 5,)
    assert model.action_space.shape == (N_ASSETS + 1,)
    first = [m for m in model.policy.mlp_extractor.policy_net if isinstance(m, torch.nn.Linear)]
    value = [m for m in model.policy.mlp_extractor.value_net if isinstance(m, torch.nn.Linear)]
    assert [m.in_features for m in first] == [BASE_SIZE + 5, 64]  # only the input grows
    assert [m.out_features for m in first] == [64, 64] == [m.out_features for m in value]
    assert model.policy.action_net.out_features == N_ASSETS + 1
    assert model.policy.value_net.out_features == 1
    observation, _ = env.reset(seed=0)
    with torch.no_grad():
        tensor = torch.as_tensor(observation[None])
        actions, values, _ = model.policy(tensor, deterministic=True)
    assert actions.shape == (1, N_ASSETS + 1) and values.shape == (1, 1)
    small = ppo.PPORunSpec(SPEC.configuration, SPEC.learning_rate, 64, 0.0, 42)
    trained = ppo.build_model(Monitor(_wrapped()), AGENT, small)
    trained.learn(total_timesteps=128)  # a short real training run on synthetic data
    assert trained.num_timesteps >= 128
    action, _ = trained.predict(observation, deterministic=True)
    assert action.shape == (N_ASSETS + 1,) and np.abs(action).max() <= 1.0
    again, _ = trained.predict(observation, deterministic=True)
    assert np.array_equal(action, again)


def test_profile_identity_differs_from_the_plain_run_identity() -> None:
    env = _env()
    env.provenance = {"processed_dataset_id": "x", "train_prefix_sha256": {}}
    code = {"git_available": True, "commit": "0" * 40, "dirty": False}
    plain = ppo.run_identity(env, AGENT, SPEC, total_timesteps=100_000, run_kind="full",
                             code=code)  # fmt: skip
    profile = ppo.ProfileTraining("main", ProfileSampling(), 5, {"v": 1}, Path("p"))
    conditioned = ppo.run_identity(env, AGENT, SPEC, total_timesteps=100_000, run_kind="full",
                                   code=code, profile=profile)  # fmt: skip
    assert "profile_conditioning" not in plain  # existing identities are unchanged
    assert conditioned["environment"]["observation_size"] == BASE_SIZE + 5
    assert plain["environment"]["observation_size"] == BASE_SIZE
    assert {
        k: v for k, v in conditioned.items() if k not in ("environment", "profile_conditioning")
    } == {k: v for k, v in plain.items() if k != "environment"}
    assert ppo.run_output_dir(AGENT, conditioned, Path("/r"), Path("p")).parent == Path("/r/p")
