"""Milestone 5.1: simulator step interface, action mapping, observation and reward helpers.

Targeted tests of the critical invariants only (D-062 to D-067); small synthetic data.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import ConstraintsConfig
from adaptive_portfolio.environment.actions import (
    LOGIT_HIGH,
    LOGIT_LOW,
    ActionError,
    policy_action_to_logits,
    project_action,
)
from adaptive_portfolio.environment.observation import (
    FEATURE_CLIP,
    FeatureScaler,
    ObservationError,
    build_observation,
    fit_feature_scaler,
    regime_one_hot,
)
from adaptive_portfolio.environment.rewards import (
    RewardError,
    decision_aligned_rewards,
    episode_decisions,
    reward_intervals,
)
from adaptive_portfolio.evaluation.simulator import (
    PortfolioState,
    SimulationError,
    SimulationSettings,
    simulate,
    step,
    validate_target,
)
from adaptive_portfolio.regimes.rules import REGIME_LABELS
from adaptive_portfolio.timing import execution_row

N_ASSETS = 7
CAP = 0.40
CONSTRAINTS = ConstraintsConfig(
    long_only=True, allow_cash=True, min_weight=0.0, max_weight=CAP, max_turnover=None
)
SETTINGS = SimulationSettings(
    initial_capital=100_000.0, cost_rate=0.0015, cash_return=0.0, constraints=CONSTRAINTS
)


def _returns(n_rows: int = 80, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-12-21", periods=n_rows)  # spans an ISO year boundary
    return pd.DataFrame(
        rng.normal(0.0004, 0.01, (n_rows, N_ASSETS)),
        index=dates,
        columns=[f"A{i}" for i in range(N_ASSETS)],
    )


def _random_actions(rng: np.random.Generator, count: int) -> list[np.ndarray]:
    return list(rng.uniform(LOGIT_LOW, LOGIT_HIGH, (count, N_ASSETS + 1)))


# --------------------------------------------------------------------------
# Simulator step interface (D-067)
# --------------------------------------------------------------------------


def test_sequential_steps_reproduce_simulate_exactly() -> None:
    # The RL path drives `step` row by row; it must give the ledger of `simulate` bit for bit.
    returns, lag = _returns(), 1
    rng = np.random.default_rng(1)
    k0, e = 5, len(returns) - 1
    decisions = episode_decisions(returns.index, k0, e, lag)
    actions = _random_actions(rng, len(decisions))
    targets = {d: project_action(a, CAP) for d, a in zip(decisions, actions, strict=True)}
    ledger = simulate(
        returns, targets, lag=lag, window=(execution_row(k0, lag), e), settings=SETTINGS
    ).ledger

    executions = {execution_row(d, lag): w for d, w in targets.items()}
    state = PortfolioState.initial(SETTINGS, N_ASSETS)
    values, weights = [], []
    for t in range(execution_row(k0, lag), e + 1):
        state, record = step(state, returns.to_numpy()[t], executions.get(t), SETTINGS)
        values.append(record.value)
        weights.append(state.weights)
    assert np.array_equal(ledger["value"].to_numpy(), np.array(values))
    assert np.array_equal(ledger.filter(like="weight_").to_numpy(), np.array(weights))


def test_step_rejects_invalid_inputs() -> None:
    state = PortfolioState.initial(SETTINGS, N_ASSETS)
    with pytest.raises(SimulationError, match="funding"):
        step(state, None, None, SETTINGS)  # the first row must buy the portfolio
    funded, _ = step(state, None, np.full(N_ASSETS, 0.1), SETTINGS)
    with pytest.raises(SimulationError, match="non-finite"):
        step(funded, np.full(N_ASSETS, np.nan), None, SETTINGS)
    with pytest.raises(SimulationError, match="shape"):
        step(funded, np.zeros(N_ASSETS + 1), None, SETTINGS)
    with pytest.raises(SimulationError, match="above max_weight"):
        step(funded, np.zeros(N_ASSETS), np.full(N_ASSETS, 0.5), SETTINGS)
    with pytest.raises(ValueError):  # the state is immutable
        funded.weights[0] = 1.0


# --------------------------------------------------------------------------
# Action mapping (D-063)
# --------------------------------------------------------------------------


def test_action_mapping_invariants() -> None:
    edge = [
        np.full(N_ASSETS + 1, LOGIT_LOW),  # uniform
        np.r_[LOGIT_HIGH, np.full(N_ASSETS, LOGIT_LOW)],  # all in one asset
        np.r_[np.full(N_ASSETS, LOGIT_LOW), LOGIT_HIGH],  # all cash
        np.r_[np.full(N_ASSETS, LOGIT_HIGH), LOGIT_LOW],
    ]
    for action in edge + _random_actions(np.random.default_rng(2), 2000):
        target = project_action(action, CAP)
        validate_target(target, tuple(f"A{i}" for i in range(N_ASSETS)), CONSTRAINTS)
        assert (target > 0).all() and target.max() <= CAP and target.sum() <= 1.0
    assert np.allclose(project_action(edge[0], CAP), 1 / 8)
    one = project_action(edge[1], CAP)
    assert one[0] == CAP and one[1:].sum() < 1e-3  # capped excess goes to cash, not assets
    assert project_action(edge[2], CAP).sum() < 1e-3


@pytest.mark.parametrize(
    "action",
    [
        np.full(N_ASSETS + 1, np.nan),
        np.full(N_ASSETS + 1, LOGIT_HIGH + 0.1),
        np.zeros((2, N_ASSETS + 1)),
        np.zeros(1),
    ],
)
def test_action_mapping_rejects_invalid_actions(action: np.ndarray) -> None:
    with pytest.raises(ActionError):
        project_action(action, CAP)


def test_normalised_actions_reproduce_the_d063_mapping() -> None:
    # D-072: the policy acts in [-1, 1]; the environment applies the D-063 mapping to 5u.
    rng = np.random.default_rng(5)
    edges = np.array([[1.0] * 8, [-1.0] * 8, [1.0] + [-1.0] * 7, [-1.0] * 7 + [1.0]])
    u32 = np.vstack([rng.uniform(-1, 1, (5000, 8)), edges]).astype(np.float32)
    for u in u32:  # float32 policy actions (as Stable-Baselines3 emits): 5u is exact
        logits = policy_action_to_logits(u)
        assert np.array_equal(logits / 5.0, u.astype(np.float64))
        assert logits.min() >= LOGIT_LOW and logits.max() <= LOGIT_HIGH
    assert np.array_equal(policy_action_to_logits(edges[2]), np.r_[5.0, [-5.0] * 7])
    # Every old (D-063) action a has the normalised action u = a / 5 with the same target:
    # bit for bit for float32 actions, within rounding for arbitrary float64 actions.
    old32 = np.vstack([rng.uniform(-5, 5, (5000, 8)), 5 * edges]).astype(np.float32)
    for a in old32.astype(np.float64):
        new = project_action(policy_action_to_logits(a / 5.0), CAP)
        assert np.array_equal(new, project_action(a, CAP))
    for a in rng.uniform(-5, 5, (5000, 8)):
        new = project_action(policy_action_to_logits(a / 5.0), CAP)
        np.testing.assert_allclose(new, project_action(a, CAP), rtol=0, atol=1e-15)
    for bad in (np.full(8, 1.0001), np.full(8, -1.5), np.full(8, np.nan), np.zeros((2, 8))):
        with pytest.raises(ActionError):
            policy_action_to_logits(bad)


# --------------------------------------------------------------------------
# Observation and training-only scaling (D-062)
# --------------------------------------------------------------------------


def _features(n_rows: int = 40) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2020-01-01", periods=n_rows)
    features = pd.DataFrame(rng.normal(size=(n_rows, 3)), index=dates, columns=["f1", "f2", "f3"])
    labels = pd.Series(["train"] * 30 + ["validation"] * 10, index=dates)
    return features, labels


def test_scaler_uses_only_the_fit_rows_and_round_trips(tmp_path) -> None:
    features, labels = _features()
    scaler = fit_feature_scaler(features, labels, 5, 29)
    changed = features.copy()
    changed.iloc[30:] = 1e6  # later (validation) rows cannot change the frozen parameters
    changed.iloc[:5] = np.nan  # nor can warm-up rows before the fit range
    assert fit_feature_scaler(changed, labels, 5, 29) == scaler
    assert scaler.fitted_on["rows"] == 25
    scaler.save(tmp_path / "scaler.json")
    assert FeatureScaler.load(tmp_path / "scaler.json") == scaler  # exact float round trip
    scaled, counts = scaler.transform(changed.iloc[25:])
    assert np.abs(scaled).max() == FEATURE_CLIP and counts == {"f1": 10, "f2": 10, "f3": 10}
    with pytest.raises(ObservationError, match="'train' rows"):
        fit_feature_scaler(features, labels, 5, 30)
    with pytest.raises(ObservationError, match="non-finite"):
        fit_feature_scaler(changed, labels, 0, 29)


def test_observation_layout_and_regime_encoding() -> None:
    weights = np.r_[np.full(N_ASSETS, 0.1), 0.3]
    observation = build_observation(np.arange(34) / 10, "positive_high", weights)
    assert observation.shape == (51,)  # 34 features + 9 regimes + 8 weights
    assert np.array_equal(observation[:34], np.arange(34) / 10)
    assert observation[34 + REGIME_LABELS.index("positive_high")] == 1.0
    assert observation[34:43].sum() == 1.0
    assert np.array_equal(observation[43:], weights)
    for bad in ("unavailable", "positive"):
        with pytest.raises(ObservationError, match="cannot be encoded"):
            regime_one_hot(bad)
    with pytest.raises(ObservationError, match="sum to 1"):
        build_observation(np.zeros(34), "neutral_low", np.full(8, 0.1))


# --------------------------------------------------------------------------
# Decision-aligned reward and episode timing (D-064, D-065)
# --------------------------------------------------------------------------


def test_reward_timing_and_telescoping() -> None:
    returns, lag = _returns(), 1
    rng = np.random.default_rng(4)
    k0, e = 5, len(returns) - 1
    decisions = episode_decisions(returns.index, k0, e, lag)
    assert decisions[-1] <= e - lag - 1  # last evaluable decision rule
    actions = _random_actions(rng, len(decisions))
    targets = {d: project_action(a, CAP) for d, a in zip(decisions, actions, strict=True)}
    x0 = execution_row(k0, lag)
    ledger = simulate(returns, targets, lag=lag, window=(x0, e), settings=SETTINGS).ledger
    values = pd.Series(ledger["value"].to_numpy(), index=range(x0, e + 1))
    rewards = decision_aligned_rewards(values, decisions, e, lag, SETTINGS.initial_capital)

    assert len(rewards) == len(decisions)
    # r_0 = log(V_{d_1} / V_0): it includes the funding cost charged at x_0 = d_0 + 1.
    assert rewards[0] == np.log(values[decisions[1]] / SETTINGS.initial_capital)
    assert ledger["cost_fraction"].iloc[0] > 0
    # r_k covers (d_k, d_{k+1}]: the execution of action k (at d_k + 1) lies inside it.
    k = 3
    assert rewards[k] == np.log(values[decisions[k + 1]] / values[decisions[k]])
    assert decisions[k] < execution_row(decisions[k], lag) <= decisions[k + 1]
    assert rewards[-1] == np.log(values[e] / values[decisions[-1]])
    assert rewards.sum() == pytest.approx(np.log(values[e] / SETTINGS.initial_capital), abs=1e-12)


def test_reward_intervals_reject_invalid_timing() -> None:
    with pytest.raises(RewardError, match="at least 1"):
        reward_intervals([0, 5], 20, lag=0)
    with pytest.raises(RewardError, match="earns no return"):
        reward_intervals([0, 19], 20, lag=1)
    with pytest.raises(RewardError, match="pending"):
        reward_intervals([0, 1], 20, lag=2)
    with pytest.raises(RewardError, match="strictly increasing"):
        reward_intervals([5, 5], 20, lag=1)
    values = pd.Series([1.0, 1.1], index=[3, 4])
    with pytest.raises(RewardError, match="funding execution"):
        decision_aligned_rewards(values, [0], 4, 1, 1.0)


# --------------------------------------------------------------------------
# Optional rl extra (M5.2): the core package must not need it
# --------------------------------------------------------------------------


def test_core_package_imports_without_the_rl_extra() -> None:
    # Blocks gymnasium, stable_baselines3 and torch, then imports every non-RL module that the
    # core CI matrix (.[dev] only) relies on. Only portfolio_env, agents.ppo, agents.grid,
    # agents.evaluate and agents.test_evaluate (milestone D)
    # may need them.
    script = textwrap.dedent(
        """
        import importlib, importlib.abc, pkgutil, sys
        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in {"gymnasium", "stable_baselines3", "torch"}:
                    raise ModuleNotFoundError(name, name=name)
        sys.meta_path.insert(0, Block())
        import adaptive_portfolio
        rl_only = {"adaptive_portfolio.environment.portfolio_env", "adaptive_portfolio.agents.ppo",
                   "adaptive_portfolio.agents.grid",
            "adaptive_portfolio.agents.evaluate", "adaptive_portfolio.agents.test_evaluate"}
        for module in pkgutil.walk_packages(adaptive_portfolio.__path__, "adaptive_portfolio."):
            if module.name not in rl_only:
                importlib.import_module(module.name)
        for name in sorted(rl_only):
            try:
                importlib.import_module(name)
            except ModuleNotFoundError:
                print("rl-only module needs the rl extra:", name)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("rl-only module needs the rl extra") == 5
    # agents.run_safety (locks, recovery, provenance) is imported above without the extra.
