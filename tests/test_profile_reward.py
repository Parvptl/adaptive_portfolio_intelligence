"""E4 profile-dependent reward: formula, boundaries, configuration and statistics (D-088).

No ``rl`` extra and no market data; hand-checked values only.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from adaptive_portfolio.config import (
    ConfigError,
    ProfileExperimentConfig,
    load_profile_experiment_config,
    load_yaml,
)
from adaptive_portfolio.environment.profile_reward import ProfileRewardError, ProfileRewardSpec
from adaptive_portfolio.environment.profiles import ProfileError, neutral_profile
from adaptive_portfolio.explainability import profile_comparison as pc
from conftest import CONFIG_DIR

SPEC = ProfileRewardSpec()


def _profile(rt=0.5, rc=0.5, h=0.5, liq=0.5, g=0.5) -> np.ndarray:
    return np.array([rt, rc, h, liq, g])


def test_risk_acceptance_is_the_lower_of_tolerance_and_capacity() -> None:
    assert SPEC.risk_acceptance(_profile(0.9, 0.2)) == 0.2
    assert SPEC.risk_acceptance(_profile(0.2, 0.9)) == 0.2  # not interchangeable with a mean
    assert SPEC.risk_acceptance(_profile(0.7, 0.7)) == 0.7


@pytest.mark.parametrize(
    ("rt", "rc", "gamma", "lam"),
    [(1.0, 1.0, 1.0, 0.0), (0.0, 0.0, 10.0, 9.0), (0.5, 0.5, 5.5, 4.5), (1.0, 0.0, 10.0, 9.0),
     (0.0, 1.0, 10.0, 9.0), (0.8, 0.6, 4.6, 3.6)],
)  # fmt: skip
def test_risk_aversion_mapping_boundaries(rt, rc, gamma, lam) -> None:
    assert SPEC.risk_aversion(_profile(rt, rc)) == pytest.approx(gamma)
    assert SPEC.penalty_coefficient(_profile(rt, rc)) == pytest.approx(lam)


def test_reward_components_by_hand_and_nesting_of_the_base_reward() -> None:
    returns = [0.01, -0.02, 0.005]
    rv = 0.01**2 + 0.02**2 + 0.005**2  # 0.000525
    parts = SPEC.components(0.0042, returns, _profile(0.5, 0.5))
    assert parts["realised_variance"] == pytest.approx(rv)
    assert parts["lambda"] == pytest.approx(4.5)
    assert parts["risk_penalty"] == pytest.approx(0.5 * 4.5 * rv)
    assert parts["reward"] == pytest.approx(0.0042 - 0.5 * 4.5 * rv)
    # a(U) = 1: exactly the D-064 reward (E1's objective), bit for bit.
    full = SPEC.components(0.0042, returns, _profile(1.0, 1.0))
    assert full["reward"] == 0.0042 and full["risk_penalty"] == 0.0
    # No returns (no rows) or all-cash rows: no penalty.
    assert SPEC.components(0.0, [0.0, 0.0], _profile(0, 0))["reward"] == 0.0
    assert SPEC.components(0.001, [], _profile(0, 0))["reward"] == 0.001


def test_profile_sensitivity_follows_the_formula() -> None:
    returns = np.full(5, 0.01)
    reward = {name: SPEC.components(0.002, returns, p)["reward"] for name, p in {
        "low_risk": _profile(0.1, 0.1), "high_risk": _profile(0.9, 0.9),
        "tolerant_but_fragile": _profile(0.9, 0.1), "capable_but_averse": _profile(0.1, 0.9),
    }.items()}  # fmt: skip
    assert reward["low_risk"] < reward["high_risk"]
    assert reward["tolerant_but_fragile"] == reward["low_risk"]  # min rule
    assert reward["capable_but_averse"] == reward["low_risk"]
    # Monotone in RT below RC, flat above it.
    values = [SPEC.components(0.002, returns, _profile(rt, 0.5))["reward"]
              for rt in (0.0, 0.25, 0.5, 0.75, 1.0)]  # fmt: skip
    assert values[0] < values[1] < values[2] == values[3] == values[4]
    # Horizon, liquidity and growth preference do not enter the reward (negative controls).
    for dims in ({"h": 0.0}, {"h": 1.0}, {"liq": 0.0}, {"liq": 1.0}, {"g": 0.0}, {"g": 1.0}):
        assert SPEC.components(0.002, returns, _profile(**dims))["reward"] == SPEC.components(
            0.002, returns, neutral_profile())["reward"]  # fmt: skip
    # Deterministic.
    assert SPEC.components(0.002, returns, _profile(0.3, 0.6)) == SPEC.components(
        0.002, returns, _profile(0.3, 0.6))  # fmt: skip


def test_invalid_specs_and_inputs_fail_safely() -> None:
    for bad in ({"gamma_min": 0.5}, {"gamma_min": 5.0, "gamma_max": 2.0},
                {"gamma_max": np.inf}, {"risk_measure": "drawdown"},
                {"acceptance": "mean"}, {"gamma_max": 100.0}):  # fmt: skip
        with pytest.raises(ProfileRewardError):
            ProfileRewardSpec(**bad)
    with pytest.raises(ProfileRewardError):
        SPEC.components(np.nan, [0.01], neutral_profile())
    with pytest.raises(ProfileRewardError):
        SPEC.components(0.0, [np.nan], neutral_profile())
    with pytest.raises(ProfileError):
        SPEC.components(0.0, [0.01], [0.5, 0.5])  # missing dimensions
    with pytest.raises(ProfileError):
        SPEC.components(0.0, [0.01], _profile(1.2, 0.5))
    with pytest.raises(ProfileRewardError):
        ProfileRewardSpec.from_dict({"gamma_min": 1.0})


def test_e4_config_adds_only_the_reward_and_grid_and_e1_is_unchanged() -> None:
    e4 = load_profile_experiment_config(CONFIG_DIR / "profile_reward_experiment.yaml")
    e1 = load_profile_experiment_config(CONFIG_DIR / "profile_experiment.yaml")
    assert e4.reward == ProfileRewardSpec() and e1.reward is None
    d4, d1 = e4.to_dict(), e1.to_dict()
    assert "reward" not in d1 and "interaction_grid" not in d1  # EXP-010 identities unchanged
    assert {k: v for k, v in d4.items() if k not in ("reward", "interaction_grid")} == d1
    assert d4["interaction_grid"]["points"] == 5 and len(d4["interaction_grid"]["pairs"]) == 3
    assert e4.output_dir != e1.output_dir and e4.evaluation_output_dir != e1.evaluation_output_dir


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r["reward"].update(gamma_max=0.5), "reward"),
        (lambda r: r["reward"].pop("acceptance"), "reward"),
        (lambda r: r["evaluation"]["interaction_grid"].update(pairs=[["risk_tolerance"] * 2]),
         "invalid pair"),
        (lambda r: r["evaluation"]["interaction_grid"].update(pairs=[["age", "risk_tolerance"]]),
         "invalid pair"),
        (lambda r: r["evaluation"]["interaction_grid"].update(points=1), "points"),
    ],
)  # fmt: skip
def test_e4_config_rejects_invalid_reward_or_grid(change, message) -> None:
    raw = copy.deepcopy(load_yaml(CONFIG_DIR / "profile_reward_experiment.yaml"))
    change(raw)
    with pytest.raises(ConfigError, match=message):
        ProfileExperimentConfig.from_dict(raw)


def test_descriptive_paired_statistics_and_verdicts() -> None:
    stats = pc._stats(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
    assert stats["mean"] == 3.0 and stats["median"] == 3.0
    assert stats["sd"] == pytest.approx(np.sqrt(2.5))
    half = 2.776 * np.sqrt(2.5) / np.sqrt(5)  # t_{0.975, 4} for five seeds
    assert stats["t_low"] == pytest.approx(3 - half) and stats["t_high"] == pytest.approx(3 + half)
    assert stats["n_positive"] == 5
    assert pc.T_975[4] == 2.776 and pc.T_975[1] == 12.706
    assert pc._verdict({"a": True, "b": True}) == "supported"
    assert pc._verdict({"a": True, "b": False}) == "partially supported"
    assert pc._verdict({"a": False}) == "not supported"
