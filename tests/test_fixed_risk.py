"""E5 fixed risk aversion: reward option, constant profile, configs and H1-H8 logic (D-089).

No ``rl`` extra and no market data.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import (
    ConfigError,
    ProfileExperimentConfig,
    load_profile_experiment_config,
    load_yaml,
)
from adaptive_portfolio.environment.profile_reward import ProfileRewardError, ProfileRewardSpec
from adaptive_portfolio.environment.profiles import ProfileError, ProfileSampling, profile_stream
from adaptive_portfolio.explainability import fixed_risk_comparison as fc
from conftest import CONFIG_DIR

LOW = ProfileRewardSpec(acceptance="fixed", fixed_lambda=0.0)
HIGH = ProfileRewardSpec(acceptance="fixed", fixed_lambda=9.0)
RETURNS = [0.01, -0.02, 0.005]
RV = 0.01**2 + 0.02**2 + 0.005**2


def test_fixed_lambda_rewards_and_profile_independence() -> None:
    profiles = [np.zeros(5), np.ones(5), np.full(5, 0.5), np.array([0.9, 0.1, 0.3, 0.7, 0.2])]
    for profile in profiles:
        low, high = LOW.components(0.004, RETURNS, profile), HIGH.components(0.004, RETURNS,
                                                                             profile)  # fmt: skip
        assert low["reward"] == 0.004 and low["risk_penalty"] == 0.0 and low["lambda"] == 0.0
        assert high["lambda"] == 9.0 and high["reward"] == pytest.approx(0.004 - 4.5 * RV)
        assert high["realised_variance"] == low["realised_variance"] == pytest.approx(RV)
    assert HIGH.risk_aversion(np.zeros(5)) == 10.0 and LOW.risk_aversion(np.ones(5)) == 1.0
    # The same components() implementation as E4: at a(U)=0 the E4 spec gives the same reward.
    e4 = ProfileRewardSpec()
    assert e4.components(0.004, RETURNS, np.zeros(5)) == HIGH.components(0.004, RETURNS,
                                                                           np.zeros(5))  # fmt: skip
    assert e4.components(0.004, RETURNS, np.ones(5)) == LOW.components(0.004, RETURNS,
                                                                         np.ones(5))  # fmt: skip


def test_fixed_spec_validation_and_e4_dict_unchanged() -> None:
    for bad in ({"acceptance": "fixed"}, {"acceptance": "fixed", "fixed_lambda": -1.0},
                {"acceptance": "fixed", "fixed_lambda": np.nan},
                {"acceptance": "fixed", "fixed_lambda": 60.0},
                {"fixed_lambda": 3.0}):  # fmt: skip
        with pytest.raises(ProfileRewardError):
            ProfileRewardSpec(**bad)
    parsed = ProfileRewardSpec.from_dict({"acceptance": "fixed", "fixed_lambda": 9,
                                          "risk_measure": "realised_variance"})  # fmt: skip
    assert parsed == HIGH and parsed.to_dict()["fixed_lambda"] == 9.0
    with pytest.raises(ProfileRewardError):  # gamma keys are not allowed for a fixed reward
        ProfileRewardSpec.from_dict({"acceptance": "fixed", "fixed_lambda": 9, "gamma_min": 1,
                                     "risk_measure": "realised_variance"})  # fmt: skip
    assert "fixed_lambda" not in ProfileRewardSpec().to_dict()  # E4 identity unchanged


def test_constant_profile_sampling() -> None:
    sampling = ProfileSampling(distribution="constant", constant=0.5)
    rng = profile_stream(42, 5)
    assert all(np.array_equal(sampling.sample(rng), np.full(5, 0.5)) for _ in range(20))
    assert sampling.to_dict()["constant"] == 0.5
    assert "constant" not in ProfileSampling().to_dict()  # E1/E4 identities unchanged
    for bad in ({"distribution": "constant"}, {"distribution": "constant", "constant": 1.5},
                {"constant": 0.5}):  # fmt: skip
        with pytest.raises(ProfileError):
            ProfileSampling(**bad)


def test_e5_arm_configs_differ_only_in_lambda_and_label() -> None:
    low = load_profile_experiment_config(CONFIG_DIR / "fixed_risk_low.yaml")
    high = load_profile_experiment_config(CONFIG_DIR / "fixed_risk_high.yaml")
    assert (low.label, high.label) == ("E5L", "E5H")
    assert (low.reward.fixed_lambda, high.reward.fixed_lambda) == (0.0, 9.0)
    assert fc._without(low.to_dict()) == fc._without(high.to_dict())
    assert set(low.arms) == {"main"} and low.arms["main"].constant == 0.5
    assert low.arm_profile_sets["main"] == () and low.seeds == (42, 43, 44, 45, 46)
    assert low.base_configuration == 4 and low.output_dir == high.output_dir


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r["arms"].pop("main"), "main"),
        (lambda r: r["evaluation"]["arm_profile_sets"].update(heldout=[]), "name exactly"),
        (lambda r: r.update(label="not a label!"), "label"),
        (lambda r: r["reward"].pop("fixed_lambda"), "reward"),
    ],
)
def test_e5_config_rejects_invalid_settings(change, message) -> None:
    raw = copy.deepcopy(load_yaml(CONFIG_DIR / "fixed_risk_high.yaml"))
    change(raw)
    with pytest.raises(ConfigError, match=message):
        ProfileExperimentConfig.from_dict(raw)


def _table(vol_low, vol_high, eq_low, eq_high, scale=1.0) -> pd.DataFrame:
    rows = []
    for split in ("train", "validation"):
        for seed, (vl, vh, el, eh) in enumerate(zip(vol_low, vol_high, eq_low, eq_high,
                                                    strict=True)):  # fmt: skip
            for arm, vol, eq in (("E5L", vl, el), ("E5H", vh * scale, eh)):
                rows.append({"split": split, "seed": 42 + seed, "arm": arm, "net_volatility": vol,
                             "target_equity": eq, "target_bonds": 0.3, "target_cash": 0.6 - eq,
                             "turnover": 10.0, "cost_drag": 0.05, "net_max_drawdown": -vol,
                             "mean_held_SPY": eq, "mean_held_CASH": 1 - eq})  # fmt: skip
    return pd.DataFrame(rows)


def _training(low_rv, high_rv):
    return {
        "low": {42 + i: {"last50_realised_variance": v} for i, v in enumerate(low_rv)},
        "high": {42 + i: {"last50_realised_variance": v} for i, v in enumerate(high_rv)},
    }


def test_hypotheses_detect_a_clear_effect_and_its_absence() -> None:
    clear = fc.hypotheses(
        _table(
            [0.10] * 5,
            [0.06, 0.07, 0.06, 0.07, 0.065],
            [0.5, 0.52, 0.48, 0.5, 0.51],
            [0.2, 0.22, 0.18, 0.2, 0.21],
        ),
        _training([0.1] * 5, [0.05] * 5),
    )
    assert all(clear[h]["verdict"] == "supported" for h in ("H1", "H2", "H3", "H5", "H6", "H8"))
    assert clear["outcome"]["class"].startswith("A")
    same = [0.10, 0.11, 0.09, 0.10, 0.105]
    none = fc.hypotheses(_table(same, same, [0.5, 0.2, 0.4, 0.3, 0.6], [0.5, 0.2, 0.4, 0.3, 0.6]),
                         _training([0.1] * 5, [0.1] * 5))  # fmt: skip
    assert none["H1"]["verdict"] == "not supported" and none["H2"]["verdict"] == "not supported"
    assert none["outcome"]["class"].startswith("C")
    weak = fc.hypotheses(_table(same, [v * 0.98 for v in same], [0.5] * 5, [0.49] * 5),
                         _training([0.1] * 5, [0.099] * 5))  # fmt: skip
    assert weak["H1"]["verdict"] == "partially supported"  # direction holds, size < 10%
    assert weak["outcome"]["class"].startswith("B")
