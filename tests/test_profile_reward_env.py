"""E4 reward wrapper: integrity against E1 and the unwrapped environment (D-088; ``rl`` extra).

The same action sequence is replayed through the plain environment (E0 reward), the profile
wrapper (E1 reward) and the E4 wrapper. Everything except the returned reward must be identical,
and the E4 reward must equal ``r_base - (lambda/2) * sum(net_return**2)`` for the step's rows.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

from stable_baselines3.common.env_checker import check_env as sb3_check_env  # noqa: E402
from stable_baselines3.common.monitor import Monitor  # noqa: E402

from adaptive_portfolio.agents import ppo  # noqa: E402
from adaptive_portfolio.config import load_agent_config  # noqa: E402
from adaptive_portfolio.environment.profile_env import (  # noqa: E402
    ProfileConditionedEnv,
    ProfileRewardEnv,
)
from adaptive_portfolio.environment.profile_reward import ProfileRewardSpec  # noqa: E402
from adaptive_portfolio.environment.profiles import ProfileError, ProfileSampling  # noqa: E402
from conftest import CONFIG_DIR  # noqa: E402
from test_portfolio_env import N_ASSETS, _env  # noqa: E402

SPEC = ProfileRewardSpec()
AGENT = load_agent_config(CONFIG_DIR / "agent.yaml")


def _actions(n: int, seed: int = 11) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    return [rng.uniform(-1, 1, N_ASSETS + 1).astype(np.float32) for _ in range(n)]


def _e4(profile=None) -> ProfileRewardEnv:
    inner = ProfileConditionedEnv(_env(), ProfileSampling(), seed=42)
    env = ProfileRewardEnv(inner, SPEC)
    env.reset(seed=42, options=None if profile is None else {"profile": profile})
    return env


def _e1(profile=None) -> ProfileConditionedEnv:
    env = ProfileConditionedEnv(_env(), ProfileSampling(), seed=42)
    env.reset(seed=42, options=None if profile is None else {"profile": profile})
    return env


def test_e4_reward_equals_the_formula_and_everything_else_is_unchanged() -> None:
    profile = np.array([0.3, 0.7, 0.2, 0.9, 0.1])  # a = 0.3, lambda = 6.3
    e4, e1, plain = _e4(profile), _e1(profile), _env()
    plain.reset(seed=42)
    for action in _actions(plain.n_steps):
        n_before = len(e4.unwrapped.ledger)
        o4, r4, d4, t4, i4 = e4.step(action)
        o1, r1, d1, t1, i1 = e1.step(action)
        o0, r0, d0, t0, _ = plain.step(action)
        assert np.array_equal(o4, o1) and np.array_equal(o4[:-5], o0)
        assert (d4, t4) == (d1, t1) == (d0, t0)
        assert r1 == r0 == i4["reward_base"]  # E1 and E0 keep the D-064 reward exactly
        rows = [rec.net_return for _, rec in e4.unwrapped.ledger[n_before:]]
        assert i4["realised_variance"] == pytest.approx(sum(x * x for x in rows), rel=1e-12)
        assert i4["lambda"] == pytest.approx(6.3)
        assert r4 == pytest.approx(r0 - 0.5 * 6.3 * i4["realised_variance"], rel=0, abs=1e-15)
        assert r4 <= r0
        for key in ("target", "value", "cost_value", "post_trade_weights"):
            assert np.array_equal(np.asarray(i4[key]), np.asarray(i1[key])), key
    assert e4.unwrapped.ledger_frame().equals(plain.ledger_frame())  # accounting unchanged
    episode = e4.episodes[-1]
    assert episode["steps"] == plain.n_steps and episode["lambda"] == pytest.approx(6.3)
    assert episode["reward"] == pytest.approx(episode["reward_base"] - episode["risk_penalty"])


def test_fully_risk_accepting_profile_gives_exactly_the_e1_reward() -> None:
    e4, e1 = _e4(np.array([1.0, 1.0, 0.0, 0.0, 0.0])), _e1(np.array([1.0, 1.0, 0.0, 0.0, 0.0]))
    for action in _actions(e1.unwrapped.n_steps):
        assert e4.step(action)[1] == e1.step(action)[1]


def test_lower_risk_acceptance_never_increases_the_reward() -> None:
    actions = _actions(_env().n_steps)
    totals = {}
    for a in (0.0, 0.25, 0.5, 0.75, 1.0):
        env = _e4(np.array([a, a, 0.5, 0.5, 0.5]))
        totals[a] = sum(env.step(x)[1] for x in actions)
    assert totals[0.0] < totals[0.25] < totals[0.5] < totals[0.75] < totals[1.0]
    # The negative controls do not change the reward.
    base = sum(_e4(np.array([0.4, 0.6, 0.5, 0.5, 0.5])).step(x)[1] for x in actions)
    other = sum(_e4(np.array([0.4, 0.6, 1.0, 0.0, 1.0])).step(x)[1] for x in actions)
    assert base == other


def test_wrapper_guards_checker_and_ppo_training() -> None:
    with pytest.raises(ProfileError):
        ProfileRewardEnv(_env(), SPEC)  # needs a profile-conditioned environment
    unreset = ProfileRewardEnv(ProfileConditionedEnv(_env(), ProfileSampling(), seed=0), SPEC)
    with pytest.raises(ProfileError):
        unreset.step(_actions(1)[0])
    sb3_check_env(ProfileRewardEnv(ProfileConditionedEnv(_env(), ProfileSampling(), seed=0),
                                   SPEC), warn=True)  # fmt: skip
    env = ProfileRewardEnv(ProfileConditionedEnv(_env(), ProfileSampling(), seed=42), SPEC)
    spec = ppo.PPORunSpec(4, 1e-4, 64, 0.0, 42)
    model = ppo.build_model(Monitor(env), AGENT, spec)
    model.learn(total_timesteps=128)
    assert model.num_timesteps >= 128 and len(env.episodes) >= 2
    assert all(e["lambda"] == pytest.approx(SPEC.penalty_coefficient(e["profile"]))
               for e in env.episodes)  # fmt: skip


def test_identity_gets_a_reward_block_only_for_e4() -> None:
    env = _env()
    env.provenance = {"processed_dataset_id": "x", "train_prefix_sha256": {}}
    code = {"git_available": True, "commit": "0" * 40, "dirty": False}
    spec = AGENT.run_specs()[20]
    e1 = ppo.ProfileTraining("main", ProfileSampling(), 5, {"v": 1}, Path("p"))
    e4 = ppo.ProfileTraining("main", ProfileSampling(), 5, {"v": 1}, Path("p"), reward=SPEC)
    i1 = ppo.run_identity(env, AGENT, spec, total_timesteps=100_000, run_kind="full",
                          code=code, profile=e1)  # fmt: skip
    i4 = ppo.run_identity(env, AGENT, spec, total_timesteps=100_000, run_kind="full",
                          code=code, profile=e4)  # fmt: skip
    assert "reward" not in i1["profile_conditioning"]
    assert i4["profile_conditioning"]["reward"] == SPEC.to_dict()
    assert {k: v for k, v in i4["profile_conditioning"].items() if k != "reward"} == i1[
        "profile_conditioning"]  # fmt: skip


def test_fixed_lambda_is_constant_across_profiles_episodes_and_steps() -> None:
    """E5 (D-089): lambda never depends on the profile; lambda = 0 equals the base reward."""
    from adaptive_portfolio.environment.profiles import ProfileSampling as Sampling

    for lam in (0.0, 9.0):
        spec = ProfileRewardSpec(acceptance="fixed", fixed_lambda=lam)
        inner = ProfileConditionedEnv(_env(), Sampling(distribution="constant", constant=0.5),
                                      seed=42)  # fmt: skip
        env, plain = ProfileRewardEnv(inner, spec), _env()
        for episode in range(2):
            env.reset(seed=42 if episode == 0 else None)
            plain.reset(seed=42)
            assert np.array_equal(env.unwrapped.ledger_frame().values, plain.ledger_frame().values)
            for action in _actions(plain.n_steps, seed=episode):
                _, reward, _, _, info = env.step(action)
                _, base, _, _, _ = plain.step(action)
                assert info["lambda"] == lam and info["reward_base"] == base
                assert reward == pytest.approx(base - 0.5 * lam * info["realised_variance"],
                                               rel=0, abs=1e-15)  # fmt: skip
                if lam == 0.0:
                    assert reward == base
        assert [e["lambda"] for e in env.episodes] == [lam, lam]
        assert all(e["profile"] == [0.5] * 5 for e in env.episodes)
