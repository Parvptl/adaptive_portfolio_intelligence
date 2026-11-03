"""E8 turnover-penalty refinement: responsiveness measures, configs, H1-H9 and outcomes (D-092).

No ``rl`` extra: synthetic target paths and seed tables only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import load_profile_experiment_config
from adaptive_portfolio.environment.profile_reward import ProfileRewardSpec
from adaptive_portfolio.environment.profiles import neutral_profile
from adaptive_portfolio.explainability import profile_analysis as pa
from adaptive_portfolio.explainability import turnover_refine_comparison as rc
from conftest import CONFIG_DIR

LABELS = ("E8B", "E8T1", "E8T2", "E8T3")
KAPPAS = (0.0, 0.0015, 0.003, 0.0045)
RETURNS = [0.01, -0.02, 0.005]


# --------------------------------------------------------------------------
# Responsiveness measures
# --------------------------------------------------------------------------


def test_static_and_alternating_paths() -> None:
    static = np.tile([0.3, 0.2, 0.5], (6, 1))
    out = pa.responsiveness(static)
    assert out["allocation_dispersion"] == pytest.approx(0.0, abs=1e-15)
    assert out["share_meaningful_changes"] == 0.0
    flip = np.array([[1.0, 0.0], [0.0, 1.0]] * 3)
    out = pa.responsiveness(flip)
    assert out["share_meaningful_changes"] == 1.0  # every change moves the whole portfolio
    assert out["allocation_dispersion"] == pytest.approx(0.5)
    one = pa.responsiveness(static[:1])
    assert np.isnan(one["allocation_dispersion"]) and np.isnan(one["share_meaningful_changes"])


def test_meaningful_change_threshold_is_five_percent_of_the_portfolio() -> None:
    assert pa.MEANINGFUL_CHANGE == 0.05
    at = np.array([[0.5, 0.5], [0.55, 0.45]])  # 0.5 * (0.05 + 0.05) = 0.05: counts
    below = np.array([[0.5, 0.5], [0.54, 0.46]])  # 0.04: does not count
    assert pa.responsiveness(at)["share_meaningful_changes"] == 1.0
    assert pa.responsiveness(below)["share_meaningful_changes"] == 0.0


def test_measures_separate_jitter_from_a_real_reallocation() -> None:
    n = 50
    jitter = np.array([[0.5 + 0.01 * (-1) ** i, 0.5 - 0.01 * (-1) ** i] for i in range(n)])
    shift = np.array([[0.3, 0.7]] * (n // 2) + [[0.7, 0.3]] * (n // 2))
    dw_jitter = pa.mean_abs_difference(jitter[1:], jitter[:-1])
    dw_shift = pa.mean_abs_difference(shift[1:], shift[:-1])
    assert dw_jitter > dw_shift  # D_w (path length) ranks the jitter as more "active"
    j, s = pa.responsiveness(jitter), pa.responsiveness(shift)
    assert s["allocation_dispersion"] > 10 * j["allocation_dispersion"]
    assert j["share_meaningful_changes"] == 0.0
    assert s["share_meaningful_changes"] == pytest.approx(1 / (n - 1))


def test_behaviour_metrics_adds_the_measures_without_changing_existing_ones() -> None:
    rng = np.random.default_rng(0)
    raw = rng.random((8, 4))
    targets = raw / raw.sum(axis=1, keepdims=True)
    ledger = pd.DataFrame({f"weight_{c}": targets[:, i]
                           for i, c in enumerate(["AAA", "BBB", "CCC", "CASH"])})  # fmt: skip
    groups = {"equity": ["AAA", "BBB"], "bonds": ["CCC"]}
    out = pa.behaviour_metrics(ledger, targets, ["AAA", "BBB", "CCC"], groups)
    assert out["allocation_stability_dw"] == pa.mean_abs_difference(targets[1:], targets[:-1])
    for key, value in pa.exposures(targets, ["AAA", "BBB", "CCC"], groups).items():
        assert out[key] == value
    assert {k: out[k] for k in ("allocation_dispersion", "share_meaningful_changes")} == (
        pa.responsiveness(targets))  # fmt: skip


# --------------------------------------------------------------------------
# Configurations and reward
# --------------------------------------------------------------------------


def test_e8_configs_differ_only_in_kappa_and_reproduce_e7() -> None:
    arms = [load_profile_experiment_config(CONFIG_DIR / f"turnover_refine_k{k}.yaml")
            for k in range(4)]  # fmt: skip
    assert [a.label for a in arms] == list(LABELS)
    assert [a.reward.turnover_penalty for a in arms] == list(KAPPAS)
    assert all(a.reward.fixed_lambda == 0.0 and a.reward.acceptance == "fixed" for a in arms)
    assert all(rc._core(a.to_dict()) == rc._core(arms[0].to_dict()) for a in arms)
    assert all(a.seeds == (42, 43, 44, 45, 46) or list(a.seeds) == [42, 43, 44, 45, 46]
               for a in arms)  # fmt: skip
    assert all(a.base_configuration == 4 and a.arms["main"].constant == 0.5 for a in arms)

    def without_label(x) -> dict:
        return {k: v for k, v in x.to_dict().items() if k != "label"}

    for e8, e7 in ((0, "turnover_k0.yaml"), (1, "turnover_k1.yaml")):
        assert without_label(arms[e8]) == without_label(
            load_profile_experiment_config(CONFIG_DIR / e7))  # fmt: skip
    e6l = load_profile_experiment_config(CONFIG_DIR / "dose_response_l0.yaml")
    assert without_label(arms[0]) == without_label(e6l)
    assert {a.output_dir.as_posix() for a in arms} == {"data/processed/turnover_refine_experiments"}
    assert {a.evaluation_output_dir.as_posix() for a in arms} == {
        "data/processed/turnover_refine_evaluations"}  # fmt: skip


def test_reward_is_unchanged_at_zero_and_the_penalty_is_applied_once() -> None:
    old = ProfileRewardSpec(acceptance="fixed", fixed_lambda=0.0)
    arms = [load_profile_experiment_config(CONFIG_DIR / f"turnover_refine_k{k}.yaml").reward
            for k in range(4)]  # fmt: skip
    assert arms[0].to_dict() == old.to_dict()
    assert arms[0].components(0.003, RETURNS, neutral_profile(), 0.7) == old.components(
        0.003, RETURNS, neutral_profile())  # fmt: skip
    for spec, kappa in zip(arms[1:], KAPPAS[1:], strict=True):
        parts = spec.components(0.003, RETURNS, neutral_profile(), 0.4)
        assert parts["reward_base"] == 0.003 and parts["risk_penalty"] == 0.0
        assert parts["turnover_penalty"] == pytest.approx(kappa * 0.4)
        assert parts["reward"] == pytest.approx(0.003 - kappa * 0.4)


# --------------------------------------------------------------------------
# Hypotheses and outcome classes
# --------------------------------------------------------------------------

BASE_TURNOVER = np.array([20.0, 22.0, 18.0, 19.0, 21.0])


def _table(turnovers, *, sharpe=(0.5, 0.6, 0.7, 0.8), dispersion=(0.05,) * 4,
           meaningful=(0.9,) * 4, hhi=(0.5,) * 4, cash=(0.25,) * 4):  # fmt: skip
    rows = []
    for split in ("train", "validation"):
        for i, label in enumerate(LABELS):
            for j, turnover in enumerate(turnovers[i]):
                rows.append({"split": split, "seed": 42 + j, "arm": label,
                             "turnover_penalty": KAPPAS[i], "turnover": turnover,
                             "cost_drag": 0.004 * turnover, "net_sharpe": sharpe[i],
                             "net_annualised_return": sharpe[i] / 10, "net_volatility": 0.05,
                             "net_max_drawdown": -0.08,
                             "allocation_stability_dw": 0.003 * turnover,
                             "allocation_dispersion": dispersion[i],
                             "share_meaningful_changes": meaningful[i],
                             "target_risky_hhi": hhi[i], "target_cash": cash[i],
                             "share_target_cash_above_95": 0.0})  # fmt: skip
    return pd.DataFrame(rows)


GRADED = [BASE_TURNOVER, BASE_TURNOVER / 2, BASE_TURNOVER / 2 - 3, BASE_TURNOVER / 2 - 5]
SAME = {"E8B = E7B (validation)": {"identical": True}}
LOGGED = {"run": True}


def test_balanced_arm_gives_outcome_a() -> None:
    out = rc.hypotheses(_table(GRADED), LABELS, SAME, LOGGED)
    assert all(out[f"H{i}"]["verdict"] == "supported" for i in range(1, 10)), {
        k: out[k]["verdict"] for k in out if k.startswith("H")}  # fmt: skip
    assert out["outcome"]["class"].startswith("A")
    assert out["outcome"]["balanced_arms"] == ["T2", "T3"]


def test_static_cash_heavy_arm_is_not_a_success() -> None:
    table = _table(GRADED, dispersion=(0.05, 0.05, 0.005, 0.002), meaningful=(0.9, 0.9, 0.1, 0.0),
                   hhi=(0.5, 0.5, 0.9, 0.95), cash=(0.25, 0.27, 0.6, 0.7))  # fmt: skip
    out = rc.hypotheses(table, LABELS, SAME, LOGGED)
    # D_w and the near-all-cash share still pass, so H6 and H7 are partial, but every new
    # responsiveness, concentration and cash part fails for both refined arms.
    assert out["H6"]["verdict"] == "partially supported"
    assert out["H7"]["verdict"] == "partially supported"
    for arm in ("T2", "T3"):
        assert not out["H6"]["parts"][f"{arm}: allocation dispersion >= 50% of B"]
        assert not out["H7"]["parts"][f"{arm}: target cash <= 0.40"]
        assert not out["outcome"]["arms"][arm]["activity_kept"]
    assert out["H9"]["verdict"] == "not supported"  # the saving comes with suppressed activity
    assert out["H4"]["verdict"] == "supported"  # higher Sharpe does not rescue the arm
    assert out["outcome"]["class"].startswith("B") and not out["outcome"]["balanced_arms"]


def test_no_reduction_gives_c_and_failed_reproduction_is_unresolved() -> None:
    flat = [BASE_TURNOVER, BASE_TURNOVER / 2, BASE_TURNOVER / 2, BASE_TURNOVER / 2]
    worse = rc.hypotheses(_table(flat, sharpe=(0.5, 0.6, 0.4, 0.3)), LABELS, SAME, LOGGED)
    assert not any(v for k, v in worse["H3"]["parts"].items() if "< T1" in k)
    assert not any(f["cost_efficient"] for f in worse["outcome"]["arms"].values())
    assert worse["outcome"]["class"].startswith("C")
    failed = rc.hypotheses(_table(GRADED), LABELS, {"x": {"identical": False}}, LOGGED)
    assert failed["H8"]["verdict"] == "not supported"
    assert failed["outcome"]["class"].startswith("Unresolved")
    unlogged = rc.hypotheses(_table(GRADED), LABELS, SAME, {"run": False})
    assert unlogged["H2"]["verdict"] == "partially supported"
