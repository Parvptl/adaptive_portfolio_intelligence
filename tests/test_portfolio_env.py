"""Milestone 5.2: the Gymnasium portfolio environment (needs the optional ``rl`` extra).

Skipped cleanly when Gymnasium is not installed (the core CI matrix installs ``.[dev]`` only).
Small synthetic data; no market data or RL training.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.rl
gym = pytest.importorskip("gymnasium")

from gymnasium.utils.env_checker import check_env  # noqa: E402

from adaptive_portfolio.config import ConstraintsConfig  # noqa: E402
from adaptive_portfolio.environment.actions import ActionError, project_action  # noqa: E402
from adaptive_portfolio.environment.observation import (  # noqa: E402
    ObservationError,
    fit_feature_scaler,
)
from adaptive_portfolio.environment.portfolio_env import (  # noqa: E402
    PortfolioEnv,
    PortfolioEnvError,
)
from adaptive_portfolio.environment.rewards import (  # noqa: E402
    RewardError,
    decision_aligned_rewards,
    episode_decisions,
)
from adaptive_portfolio.evaluation.simulator import SimulationSettings, simulate  # noqa: E402
from adaptive_portfolio.regimes.rules import REGIME_LABELS, UNAVAILABLE  # noqa: E402

N_ASSETS, N_FEATURES, N_TRAIN, N_VALIDATION, HISTORY = 4, 3, 80, 40, 10
# The only check_env warnings accepted (see docs/technical_handbook.md §15):
# The action space is normalised since D-072, so only the render-spec notice remains.
KNOWN_WARNINGS = ("not having a spec",)


def _settings(allow_cash: bool = True) -> SimulationSettings:
    constraints = ConstraintsConfig(
        long_only=True, allow_cash=allow_cash, min_weight=0.0, max_weight=0.4, max_turnover=None
    )
    return SimulationSettings(
        initial_capital=100_000.0, cost_rate=0.0015, cash_return=0.0, constraints=constraints
    )


def _data(seed: int = 0) -> dict[str, pd.DataFrame | pd.Series]:
    rng = np.random.default_rng(seed)
    n = N_TRAIN + N_VALIDATION
    dates = pd.bdate_range("2015-12-01", periods=n, name="date")
    returns = pd.DataFrame(
        rng.normal(0.0004, 0.01, (n, N_ASSETS)),
        index=dates,
        columns=[f"A{i}" for i in range(N_ASSETS)],
    )
    features = pd.DataFrame(
        rng.normal(size=(n, N_FEATURES)), index=dates, columns=["f1", "f2", "f3"]
    )
    features.iloc[: HISTORY - 1] = np.nan  # feature warm-up before the common start
    regimes = pd.Series(rng.choice(REGIME_LABELS, n), index=dates, dtype=object)
    regimes.iloc[: HISTORY - 1] = UNAVAILABLE
    labels = pd.Series(["train"] * N_TRAIN + ["validation"] * N_VALIDATION, index=dates)
    return {"returns": returns, "features": features, "regimes": regimes, "labels": labels}


def _env(data=None, split: str = "train", **overrides) -> PortfolioEnv:
    data = data or _data()
    first = HISTORY - 1
    last_train = N_TRAIN - 1
    decisions = episode_decisions(data["returns"].index, first, last_train, 1)
    scaler = fit_feature_scaler(data["features"], data["labels"], first, decisions[-1])
    kwargs = {"split": split, "scaler": scaler, "settings": _settings(), "lag": 1}
    kwargs.update(overrides)
    return PortfolioEnv(
        data["returns"],
        data["features"],
        data["regimes"],
        data["labels"],
        required_history=HISTORY,
        **kwargs,
    )


def _run_episode(env: PortfolioEnv, seed: int) -> tuple[list, list, list]:
    env.action_space.seed(seed)
    observation, info = env.reset(seed=seed)
    observations, rewards, infos = [observation], [], [info]
    terminated = False
    while not terminated:
        observation, reward, terminated, truncated, info = env.step(env.action_space.sample())
        assert truncated is False
        observations.append(observation)
        rewards.append(reward)
        infos.append(info)
    return observations, rewards, infos


def test_gymnasium_env_checker_passes() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        check_env(_env())
    unexpected = [
        str(w.message) for w in caught if not any(k in str(w.message) for k in KNOWN_WARNINGS)
    ]
    assert unexpected == []


def test_reset_and_step_follow_the_gymnasium_api() -> None:
    env = _env()
    with pytest.raises(PortfolioEnvError, match="reset"):
        env.step(np.zeros(N_ASSETS + 1, dtype=np.float32))
    observations, rewards, infos = _run_episode(env, seed=7)
    size = N_FEATURES + len(REGIME_LABELS) + N_ASSETS + 1
    assert env.observation_space.shape == (size,) and env.action_space.shape == (N_ASSETS + 1,)
    for observation in observations:
        assert observation.dtype == np.float32 and observation.shape == (size,)
        assert np.isfinite(observation).all() and env.observation_space.contains(observation)
    assert np.array_equal(observations[0][-(N_ASSETS + 1) :], np.r_[np.zeros(N_ASSETS), 1.0])
    assert len(rewards) == env.n_steps == len(env.decisions)
    assert all(isinstance(r, float) and np.isfinite(r) for r in rewards)
    assert all(isinstance(i, dict) for i in infos)
    first = infos[1]  # the funding step
    assert first["target"].sum() == pytest.approx(1.0)
    # Executed weights are the simulator's renormalised target (post / post.sum()): equal to the
    # requested target up to one rounding unit.
    np.testing.assert_allclose(first["post_trade_weights"], first["target"], rtol=0, atol=1e-15)
    with pytest.raises(PortfolioEnvError, match="terminated"):
        env.step(np.zeros(N_ASSETS + 1, dtype=np.float32))


def test_episode_reuses_simulator_accounting_and_reward_timing() -> None:
    env = _env()
    _, rewards, infos = _run_episode(env, seed=3)
    ledger = env.ledger_frame()
    targets = {env.decisions[k]: infos[k + 1]["target"][:-1] for k in range(env.n_steps)}
    expected = simulate(
        pd.DataFrame(env._returns, index=env.dates, columns=env.assets),
        targets,
        lag=1,
        window=(env.first_execution, env.last_row),
        settings=env.settings,
    ).ledger
    assert np.array_equal(ledger["value"].to_numpy(), expected["value"].to_numpy())
    assert np.array_equal(
        ledger.filter(like="weight_").to_numpy(), expected.filter(like="weight_").to_numpy()
    )
    values = pd.Series(
        expected["value"].to_numpy(), index=range(env.first_execution, env.last_row + 1)
    )
    reference = decision_aligned_rewards(values, env.decisions, env.last_row, 1, 100_000.0)
    assert np.array_equal(np.array(rewards), reference)
    # Each step's execution happens inside its own reward interval, one row after the decision.
    for k, info in enumerate(infos[1:]):
        assert info["decision_date"] < info["execution_date"] <= info["interval_end_date"]
        assert env.dates.get_loc(info["execution_date"]) == env.decisions[k] + 1
    # Deterministic: the same seed and actions reproduce the episode exactly.
    assert _run_episode(env, seed=3)[1] == rewards


def test_episodes_stay_inside_their_split() -> None:
    data = _data()
    clean_rewards = _run_episode(_env(data), seed=5)[1]
    # Corrupt every row after the training split: the training episode must not read them.
    corrupt = {k: v.copy() for k, v in data.items()}
    corrupt["returns"].iloc[N_TRAIN:] = np.nan
    corrupt["features"].iloc[N_TRAIN:] = np.nan
    corrupt["regimes"].iloc[N_TRAIN:] = UNAVAILABLE
    env = _env(corrupt)
    _, rewards, infos = _run_episode(env, seed=5)
    assert rewards == clean_rewards
    assert infos[-1]["interval_end_date"] == data["returns"].index[N_TRAIN - 1]
    # A validation episode reuses the training scaler and starts at the split's first row.
    validation = _env(data, split="validation")
    assert validation.first_decision == N_TRAIN
    assert validation.last_row == N_TRAIN + N_VALIDATION - 1
    _, _, infos = _run_episode(validation, seed=5)
    dates = [i["decision_date"] for i in infos[1:]] + [infos[-1]["interval_end_date"]]
    assert min(dates) >= data["returns"].index[N_TRAIN]


def test_invalid_actions_and_inputs_are_rejected() -> None:
    env = _env()
    env.reset(seed=0)
    for action in (np.full(N_ASSETS + 1, 1.5), np.full(N_ASSETS + 1, np.nan), np.zeros(2)):
        with pytest.raises(ActionError):
            env.step(action)
    with pytest.raises(PortfolioEnvError, match="allow_cash"):
        _env(settings=_settings(allow_cash=False))
    with pytest.raises(RewardError, match="lag of at least 1"):
        _env(lag=0)
    data = _data()
    # `unavailable` at an observed row (a decision row) is refused at construction, before any
    # episode starts. Rows that are never observed (between decisions) are not encoded.
    data["regimes"].iloc[env.decisions[3]] = UNAVAILABLE
    with pytest.raises(ObservationError, match="cannot be encoded"):
        _env(data)


def test_normalised_action_episode_equals_the_d063_episode() -> None:
    # D-072: driving the environment with u = a / 5 reproduces, bit for bit, the ledger and
    # rewards of the D-063 targets of the old actions a (accounting and timing unchanged).
    env = _env()
    rng = np.random.default_rng(11)
    old_actions = rng.uniform(-5, 5, (env.n_steps, N_ASSETS + 1)).astype(np.float32)
    env.reset(seed=0)
    rewards = []
    for k, a in enumerate(old_actions):
        u = a.astype(np.float64) / 5.0  # the exact normalised counterpart of a
        _, reward, terminated, _, info = env.step(u)
        rewards.append(reward)
        assert np.array_equal(info["logits"], a.astype(np.float64))
        # Rounding u to float32 (SB3's dtype) moves the logits by at most one float32 rounding
        # of a/5, times 5: the float32 grids of old and new actions differ, the mapping does not.
        u32 = u.astype(np.float32).astype(np.float64)
        assert np.abs(5.0 * u32 - a).max() <= 5.0 * np.spacing(np.float32(1.0))
        assert terminated == (k == env.n_steps - 1)
    assert env.action_space.low.min() == -1.0 and env.action_space.high.max() == 1.0
    targets = {
        d: project_action(a.astype(np.float64), 0.4)
        for d, a in zip(env.decisions, old_actions, strict=True)
    }
    expected = simulate(
        pd.DataFrame(env._returns, index=env.dates, columns=env.assets),
        targets,
        lag=1,
        window=(env.first_execution, env.last_row),
        settings=env.settings,
    ).ledger
    assert np.array_equal(env.ledger_frame()["value"].to_numpy(), expected["value"].to_numpy())
    values = pd.Series(
        expected["value"].to_numpy(), index=range(env.first_execution, env.last_row + 1)
    )
    reference = decision_aligned_rewards(values, env.decisions, env.last_row, 1, 100_000.0)
    assert np.array_equal(np.array(rewards), reference)
