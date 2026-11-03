"""E6 lambda dose response: configs and the H1-H8 / outcome logic (D-090; no ``rl``)."""

from __future__ import annotations

import pandas as pd
import pytest

from adaptive_portfolio.config import load_profile_experiment_config
from adaptive_portfolio.environment.profile_reward import ProfileRewardSpec
from adaptive_portfolio.environment.profiles import neutral_profile
from adaptive_portfolio.explainability import dose_response_comparison as dc
from adaptive_portfolio.explainability.fixed_risk_comparison import _without
from conftest import CONFIG_DIR

LABELS = ("E6L", "E6M", "E6H")


def _configs():
    return [load_profile_experiment_config(CONFIG_DIR / f"dose_response_l{x}.yaml")
            for x in (0, 3, 9)]  # fmt: skip


def test_e6_arms_differ_only_in_lambda_and_match_e5_settings() -> None:
    arms = _configs()
    assert [a.label for a in arms] == list(LABELS)
    assert [a.reward.fixed_lambda for a in arms] == [0.0, 3.0, 9.0]
    assert [a.reward.penalty_coefficient(neutral_profile()) for a in arms] == [0.0, 3.0, 9.0]
    assert all(_without(a.to_dict()) == _without(arms[0].to_dict()) for a in arms)
    e5 = load_profile_experiment_config(CONFIG_DIR / "fixed_risk_low.yaml")
    assert _without(e5.to_dict()) == _without(arms[0].to_dict())  # same settings as E5
    assert all(a.arms["main"].constant == 0.5 and set(a.arms) == {"main"} for a in arms)
    assert all(a.output_dir != e5.output_dir for a in arms)  # E5 outputs never touched
    assert arms[0].seeds == (42, 43, 44, 45, 46) and arms[0].base_configuration == 4


def test_lambda_three_resolves_exactly_and_uses_the_e4_components() -> None:
    spec = ProfileRewardSpec(acceptance="fixed", fixed_lambda=3.0)
    parts = spec.components(0.002, [0.01, -0.01], neutral_profile())
    assert parts["lambda"] == 3.0 and parts["reward"] == pytest.approx(0.002 - 1.5 * 2e-4)


def _table(vols: dict[str, list[float]], equity: dict[str, list[float]], train_scale=1.0,
           sharpe: dict[str, list[float]] | None = None) -> pd.DataFrame:  # fmt: skip
    rows = []
    for split, scale in (("train", train_scale), ("validation", 1.0)):
        for label, lam in zip(LABELS, (0.0, 3.0, 9.0), strict=True):
            for i, vol in enumerate(vols[label]):
                eq = equity[label][i]
                rows.append({"split": split, "seed": 42 + i, "arm": label, "fixed_lambda": lam,
                             "net_volatility": vol * (scale if label != "E6L" else 1.0),
                             "target_equity": eq, "turnover": 10.0, "cost_drag": 0.05,
                             "net_sharpe": (sharpe or {}).get(label, [0.5] * 5)[i],
                             "mean_held_SPY": eq, "mean_held_CASH": 1 - eq})  # fmt: skip
    return pd.DataFrame(rows)


def test_outcome_a_for_a_clear_graded_response() -> None:
    vols = {"E6L": [0.10, 0.11, 0.10, 0.105, 0.10], "E6M": [0.085, 0.095, 0.086, 0.09, 0.087],
            "E6H": [0.07, 0.08, 0.071, 0.075, 0.072]}  # fmt: skip
    equity = {"E6L": [0.5, 0.52, 0.49, 0.5, 0.51], "E6M": [0.35, 0.37, 0.34, 0.36, 0.35],
              "E6H": [0.2, 0.22, 0.19, 0.2, 0.21]}  # fmt: skip
    hyp = dc.hypotheses(_table(vols, equity, sharpe={"E6L": [0.5] * 5, "E6M": [0.6] * 5,
                                                     "E6H": [0.7] * 5}), LABELS)  # fmt: skip
    assert all(hyp[f"H{i}"]["verdict"] == "supported" for i in range(1, 9))
    assert hyp["outcome"]["class"].startswith("A")
    assert 0.1 <= hyp["H2"]["fraction_median"] <= 0.9


def test_outcome_b_for_an_endpoint_only_response_and_c_for_none() -> None:
    base = [0.10, 0.11, 0.10, 0.105, 0.10]
    flat_eq = {k: [0.4, 0.2, 0.5, 0.3, 0.45] for k in LABELS}
    endpoint = dc.hypotheses(
        _table({"E6L": base, "E6M": base, "E6H": [v * 0.8 for v in base]}, flat_eq), LABELS
    )
    assert endpoint["H2"]["verdict"] != "supported"  # the intermediate arm adds nothing
    assert endpoint["outcome"]["class"].startswith("B")
    none = dc.hypotheses(_table({k: base for k in LABELS}, flat_eq), LABELS)
    assert none["H1"]["verdict"] == "not supported" and none["H4"]["verdict"] == "not supported"
    assert none["outcome"]["class"].startswith("C")
