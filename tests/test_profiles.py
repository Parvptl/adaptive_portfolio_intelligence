"""Investor profiles, profile sets, the experiment config and the profile analysis (D-085).

No ``rl`` extra and no market data: pure NumPy/pandas with hand-checked values.
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
from adaptive_portfolio.environment.profiles import (
    PROFILE_DIMENSIONS,
    PROFILE_SIZE,
    ProfileError,
    ProfileSampling,
    neutral_profile,
    profile_dict,
    profile_set,
    profile_stream,
    validate_profile,
)
from adaptive_portfolio.explainability import profile_analysis as pa
from conftest import CONFIG_DIR

HELDOUT = ProfileSampling(exclude=(("risk_tolerance", 0.6, 1.0), ("risk_capacity", 0.0, 0.4)))


# ------------------------------------------------------------------ profiles


def test_profile_has_five_named_dimensions_in_unit_interval() -> None:
    assert PROFILE_DIMENSIONS == ("risk_tolerance", "risk_capacity", "investment_horizon",
                                  "liquidity_preference", "growth_preference")  # fmt: skip
    assert PROFILE_SIZE == 5
    assert validate_profile([0, 0.25, 0.5, 0.75, 1]).dtype == np.float64
    assert profile_dict(neutral_profile()) == dict.fromkeys(PROFILE_DIMENSIONS, 0.5)
    for bad in ([0.5] * 4, [0.5] * 6, [0.5, 0.5, 0.5, 0.5, 1.01], [-0.01, 0, 0, 0, 0],
                [np.nan, 0, 0, 0, 0], [[0.5] * 5]):  # fmt: skip
        with pytest.raises(ProfileError):
            validate_profile(bad)


def test_sampling_is_continuous_bounded_and_reproducible() -> None:
    sampling = ProfileSampling()
    first = np.vstack([sampling.sample(profile_stream(42, 5)) for _ in range(3)])
    assert np.array_equal(first[0], first[1])  # a fresh stream with the same seed repeats
    rng = profile_stream(42, 5)
    draws = np.vstack([sampling.sample(rng) for _ in range(2000)])
    assert np.array_equal(draws[0], first[0])
    assert draws.shape == (2000, 5) and (draws >= 0).all() and (draws <= 1).all()
    assert len(np.unique(draws)) == draws.size  # continuous: no repeated values
    assert np.allclose(draws.mean(axis=0), 0.5, atol=0.03)  # Uniform(0, 1) per dimension
    other = ProfileSampling().sample(profile_stream(43, 5))
    assert not np.array_equal(other, first[0])
    # The stream is independent of the market/PPO seed stream default_rng(42).
    assert not np.array_equal(np.random.default_rng(42).uniform(0, 1, 5), first[0])


def test_excluded_joint_region_is_never_sampled_but_its_margins_are() -> None:
    rng = profile_stream(7, 5)
    draws = np.vstack([HELDOUT.sample(rng) for _ in range(5000)])
    assert not any(HELDOUT.in_excluded_region(d) for d in draws)
    # The combination is excluded, not the marginal ranges: both still occur separately.
    assert (draws[:, 0] >= 0.6).any() and (draws[:, 1] <= 0.4).any()
    assert HELDOUT.in_excluded_region(np.array([0.6, 0.4, 0, 0, 0]))  # closed bounds
    assert not HELDOUT.in_excluded_region(neutral_profile())
    assert not ProfileSampling().in_excluded_region(np.ones(5))
    everything = ProfileSampling(exclude=(("risk_tolerance", 0.0, 1.0),))
    with pytest.raises(ProfileError, match="rejection limit"):
        everything.sample(rng)


def test_sampling_description_round_trip_and_validation() -> None:
    raw = {"distribution": "uniform", "low": 0.0, "high": 1.0,
           "exclude": {"risk_capacity": [0.0, 0.4], "risk_tolerance": [0.6, 1.0]}}  # fmt: skip
    parsed = ProfileSampling.from_dict(raw)
    assert parsed == HELDOUT  # dimension order normalised
    assert parsed.to_dict()["exclude"] == {"risk_tolerance": [0.6, 1.0],
                                           "risk_capacity": [0.0, 0.4]}  # fmt: skip
    for bad in ({"distribution": "beta"}, {"distribution": "uniform", "low": 0.5, "high": 0.5},
                {"distribution": "uniform", "exclude": {"age": [0, 1]}},
                {"distribution": "uniform", "exclude": {"risk_tolerance": [0.7, 0.2]}},
                {"low": 0.0}, {"distribution": "uniform", "extra": 1}):  # fmt: skip
        with pytest.raises(ProfileError):
            ProfileSampling.from_dict(bad)


def test_profile_sets_are_seeded_and_in_their_region() -> None:
    full = profile_set(32, 20261103, "full")
    assert full.shape == (32, 5) and np.array_equal(full, profile_set(32, 20261103, "full"))
    assert not np.array_equal(full, profile_set(32, 20261104, "full"))
    inside = profile_set(32, 20261104, "excluded", HELDOUT)
    assert all(HELDOUT.in_excluded_region(p) for p in inside)
    training = profile_set(32, 20261105, "sampling", HELDOUT)
    assert not any(HELDOUT.in_excluded_region(p) for p in training)
    with pytest.raises(ProfileError):
        profile_set(4, 1, "excluded", ProfileSampling())
    with pytest.raises(ProfileError):
        profile_set(0, 1, "full")
    with pytest.raises(ProfileError):
        profile_set(4, 1, "elsewhere")


# ------------------------------------------------------------------ config


def test_repository_profile_config_loads_with_the_fixed_design() -> None:
    config = load_profile_experiment_config(CONFIG_DIR / "profile_experiment.yaml")
    assert config.base_configuration == 4 and config.seeds == (42, 43, 44, 45, 46)
    assert config.profile_stream == 5 and config.policy_actions == "deterministic"
    assert config.arms["main"] == ProfileSampling() and config.arms["heldout"] == HELDOUT
    assert config.splits == ("train", "validation")  # never the test split
    assert set(config.profile_sets) == {"in_distribution", "heldout_region", "heldout_training"}
    assert config.output_dir.as_posix() == "data/processed/profile_experiments"
    assert "output_dir" not in config.to_dict()  # output roots do not enter identities


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("evaluation", "splits"), ["train", "test"], "sealed"),
        (("arms", "main", "exclude"), {"risk_tolerance": [0.6, 1.0]}, "must not exclude"),
        (("arms", "heldout", "exclude"), None, "needs an excluded region"),
        (("evaluation", "policy_actions"), "sampled", "policy_actions"),
        (("evaluation", "arm_profile_sets", "main"), ["nowhere"], "unknown sets"),
        (("evaluation", "profile_sets", "heldout_region", "arm"), "main", "no excluded region"),
        (("seeds",), [42, 42], "unique"),
    ],
)
def test_profile_config_rejects_invalid_settings(path, value, message) -> None:
    raw = copy.deepcopy(load_yaml(CONFIG_DIR / "profile_experiment.yaml"))
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ConfigError, match=message):
        ProfileExperimentConfig.from_dict(raw)


# ------------------------------------------------------------------ analysis


def test_mean_absolute_allocation_difference_by_hand() -> None:
    a = np.array([[0.4, 0.4, 0.2], [0.2, 0.3, 0.5]])
    b = np.array([[0.4, 0.2, 0.4], [0.2, 0.3, 0.5]])
    # Decision 1: (0 + 0.2 + 0.2) / 3; decision 2: 0. D_w is their mean.
    assert np.allclose(pa.per_decision_difference(a, b), [0.4 / 3, 0.0])
    assert pa.mean_abs_difference(a, b) == pytest.approx(0.2 / 3)
    assert pa.mean_abs_difference(a, a) == 0.0
    matrix = pa.pairwise_differences(np.stack([a, b, a]))
    assert np.allclose(matrix, matrix.T) and np.allclose(np.diag(matrix), 0)
    assert matrix[0, 2] == 0.0 and matrix[0, 1] == pytest.approx(0.2 / 3)
    summary = pa.pairwise_summary(np.stack([a, b, a]))
    assert summary["pairs"] == 3 and summary["dw_max"] == pytest.approx(0.2 / 3)
    with pytest.raises(pa.ProfileAnalysisError):
        pa.mean_abs_difference(a, b[:1])
    with pytest.raises(pa.ProfileAnalysisError):
        pa.pairwise_differences(a[None])


def test_rank_correlation_exposures_and_behaviour() -> None:
    assert pa.rank_correlation([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert pa.rank_correlation([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert np.isnan(pa.rank_correlation([1, 2, 3], [5, 5, 5]))
    targets = np.array([[0.4, 0.2, 0.1, 0.3], [0.4, 0.4, 0.0, 0.2]])
    groups = {"equity": ["A", "B"], "bonds": ["C"]}
    out = pa.exposures(targets, ["A", "B", "C"], groups)
    assert out["target_equity"] == pytest.approx(0.7) and out["target_bonds"] == pytest.approx(0.05)
    assert out["target_cash"] == pytest.approx(0.25)
    # Risky-sleeve HHI: (4/7)^2 + (2/7)^2 + (1/7)^2 = 21/49 and 0.5^2 + 0.5^2 = 0.5.
    assert out["target_risky_hhi"] == pytest.approx((21 / 49 + 0.5) / 2)
    with pytest.raises(pa.ProfileAnalysisError, match="unknown assets"):
        pa.exposures(targets, ["A", "B", "C"], {"equity": ["SPY"]})


def test_sweeps_and_shuffled_partner() -> None:
    rows = pa.sweep_profiles(3)
    assert len(rows) == 15
    name, value, profile = rows[2]
    assert (name, value) == ("risk_tolerance", 1.0) and np.allclose(
        profile, [1, 0.5, 0.5, 0.5, 0.5]
    )
    partner = pa.shuffled_partner(4)
    assert partner.tolist() == [1, 2, 3, 0] and (partner != np.arange(4)).all()
    effects = pa.dimension_correlations(profile_set(4, 0, "full"), {"x": [1, 2, 3, 4]})
    assert len(effects) == 5 and {r["dimension"] for r in effects} == set(PROFILE_DIMENSIONS)
