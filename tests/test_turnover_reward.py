"""E7 turnover-aware reward: penalty, configs and the H1-H8 / outcome logic (D-091; no ``rl``)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import load_profile_experiment_config
from adaptive_portfolio.environment.profile_reward import ProfileRewardError, ProfileRewardSpec
from adaptive_portfolio.environment.profiles import neutral_profile
from adaptive_portfolio.explainability import turnover_comparison as tc
from conftest import CONFIG_DIR

LABELS = ("E7B", "E7T1", "E7T2")
RETURNS = [0.01, -0.02, 0.005]


def _spec(kappa: float) -> ProfileRewardSpec:
    return ProfileRewardSpec(acceptance="fixed", fixed_lambda=0.0, turnover_penalty=kappa)


def test_zero_kappa_is_exactly_the_existing_reward() -> None:
    old = ProfileRewardSpec(acceptance="fixed", fixed_lambda=0.0)
    for traded in (0.0, 0.5, 2.0):
        assert _spec(0.0).components(0.003, RETURNS, neutral_profile(), traded) == old.components(
            0.003, RETURNS, neutral_profile())  # fmt: skip
    assert _spec(0.0).to_dict() == old.to_dict()  # E5/E6 identities unchanged
    assert "turnover_penalty" not in _spec(0.0).components(0.003, RETURNS, neutral_profile(), 1.0)


def test_penalty_is_zero_without_trading_and_applied_once() -> None:
    spec = _spec(0.0075)
    none = spec.components(0.003, RETURNS, neutral_profile(), 0.0)
    assert none["turnover_penalty"] == 0.0 and none["reward"] == 0.003
    some = spec.components(0.003, RETURNS, neutral_profile(), 0.4)
    assert some["turnover_penalty"] == pytest.approx(0.0075 * 0.4)
    assert some["reward"] == pytest.approx(0.003 - 0.0075 * 0.4)  # once, nothing else changes
    assert some["reward_base"] == 0.003 and some["risk_penalty"] == 0.0
    rewards = [spec.components(0.003, RETURNS, neutral_profile(), x)["reward"]
               for x in (0.0, 0.2, 0.4, 0.8)]  # fmt: skip
    assert rewards == sorted(rewards, reverse=True) and len(set(rewards)) == 4
    with_risk = ProfileRewardSpec(acceptance="fixed", fixed_lambda=9.0, turnover_penalty=0.0015)
    parts = with_risk.components(0.003, RETURNS, neutral_profile(), 0.4)
    assert parts["reward"] == pytest.approx(0.003 - parts["risk_penalty"] - 0.0015 * 0.4)


def test_invalid_penalties_are_rejected() -> None:
    for bad in (-0.001, np.nan, np.inf, 0.2):
        with pytest.raises(ProfileRewardError):
            _spec(bad)
    with pytest.raises(ProfileRewardError, match="only allowed"):
        ProfileRewardSpec(turnover_penalty=0.001)  # the E4 profile rule does not take kappa
    with pytest.raises(ProfileRewardError):
        _spec(0.001).components(0.0, RETURNS, neutral_profile(), -0.1)
    parsed = ProfileRewardSpec.from_dict({"acceptance": "fixed", "fixed_lambda": 0,
                                          "risk_measure": "realised_variance",
                                          "turnover_penalty": 0.0015})  # fmt: skip
    assert parsed == _spec(0.0015) and parsed.to_dict()["turnover_penalty"] == 0.0015
    with pytest.raises(ProfileRewardError):
        ProfileRewardSpec.from_dict(
            {
                "acceptance": "fixed",
                "fixed_lambda": 0,
                "risk_measure": "realised_variance",
                "kappa": 0.1,
            }
        )


def test_e7_configs_differ_only_in_kappa_and_the_control_equals_e6l() -> None:
    arms = [load_profile_experiment_config(CONFIG_DIR / f"turnover_k{k}.yaml") for k in (0, 1, 2)]
    assert [a.label for a in arms] == list(LABELS)
    assert [a.reward.turnover_penalty for a in arms] == [0.0, 0.0015, 0.0075]
    assert all(tc._core(a.to_dict()) == tc._core(arms[0].to_dict()) for a in arms)
    e6l = load_profile_experiment_config(CONFIG_DIR / "dose_response_l0.yaml").to_dict()
    control = arms[0].to_dict()
    assert {k: v for k, v in control.items() if k != "label"} == {
        k: v for k, v in e6l.items() if k != "label"}  # fmt: skip
    assert all(a.reward.fixed_lambda == 0.0 and a.arms["main"].constant == 0.5 for a in arms)
    assert arms[0].output_dir.as_posix() == "data/processed/turnover_experiments"


def _table(turn_b, turn_t1, turn_t2, *, sharpe=(0.5, 0.5, 0.5), train_scale=1.0):
    rows = []
    for split, scale in (("train", train_scale), ("validation", 1.0)):
        for label, kappa, turns, sh in zip(
            LABELS, (0.0, 0.0015, 0.0075), (turn_b, turn_t1, turn_t2), sharpe, strict=True
        ):
            for i, turnover in enumerate(turns):
                rows.append({"split": split, "seed": 42 + i, "arm": label,
                             "turnover_penalty": kappa, "turnover": turnover * scale,
                             "cost_drag": 0.004 * turnover, "net_sharpe": sh,
                             "net_annualised_return": sh / 10, "net_volatility": 0.05,
                             "net_max_drawdown": -0.08, "allocation_stability_dw": 0.05,
                             "share_target_cash_above_95": 0.0})  # fmt: skip
    return pd.DataFrame(rows)


def test_hypotheses_and_outcome_classes() -> None:
    same = {"identical": True}
    clear = tc.hypotheses(_table([20, 22, 18, 19, 21], [10, 11, 9, 9, 10], [4, 5, 4, 3, 4],
                                 sharpe=(0.5, 0.6, 0.7)), LABELS, same)  # fmt: skip
    assert all(clear[f"H{i}"]["verdict"] == "supported" for i in range(1, 9))
    assert clear["outcome"]["class"].startswith("A")
    flat = [20, 22, 18, 19, 21]
    none = tc.hypotheses(_table(flat, flat, flat), LABELS, same)
    # Equal medians satisfy "T2 <= T1", so H1 is only partial; H3 fails entirely, giving C.
    assert none["H1"]["verdict"] == "partially supported"
    assert none["H3"]["verdict"] == "not supported"
    assert none["outcome"]["class"].startswith("C")
    worse = tc.hypotheses(_table(flat, [10] * 5, [4] * 5, sharpe=(0.5, 0.3, 0.2)), LABELS, same)
    assert worse["H4"]["verdict"] == "not supported" and worse["outcome"]["class"].startswith("B")
    unresolved = tc.hypotheses(_table(flat, [10] * 5, [4] * 5), LABELS, {"identical": False})
    assert unresolved["outcome"]["class"].startswith("Unresolved")
