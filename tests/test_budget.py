"""E11 training-budget reduction: configs, budget rules, gap attribution, outcomes (no ``rl``)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import ConfigError, load_profile_experiment_config, load_yaml
from adaptive_portfolio.config import ProfileExperimentConfig as PEC
from adaptive_portfolio.explainability import budget_comparison as bc
from adaptive_portfolio.explainability import walk_forward_comparison as wc
from conftest import CONFIG_DIR


def test_e11_configs_differ_only_in_the_budget_and_reproduce_e10t1() -> None:
    for f in "abc":
        ref, half = (load_profile_experiment_config(CONFIG_DIR / f"budget_{f}_{a}.yaml")
                     for a in ("ref", "half"))  # fmt: skip
        e10t1 = load_profile_experiment_config(CONFIG_DIR / f"walk_forward_{f}_k1.yaml")
        assert ref.total_timesteps is None and half.total_timesteps == bc.HALF_BUDGET
        assert half.total_timesteps % 512 == 0 and 2 * half.total_timesteps == bc.REFERENCE_DONE
        for x in (ref, half):
            assert x.reward.turnover_penalty == 0.0015 and x.reward.fixed_lambda == 0.0
            assert x.seeds == (42, 43, 44, 45, 46)
            assert x.walk_forward_fold == e10t1.walk_forward_fold
        a, b, c = ref.to_dict(), half.to_dict(), e10t1.to_dict()
        assert {k for k in set(a) | set(b) if a.get(k) != b.get(k)} == {"label", "total_timesteps"}
        assert {k for k in set(a) | set(c) if a.get(k) != c.get(k)} == {"label"}  # reproduction
        assert ref.output_dir.as_posix() == "data/processed/budget_experiments"


def test_budget_key_is_validated_and_absent_from_earlier_identities() -> None:
    raw = load_yaml(CONFIG_DIR / "budget_a_half.yaml")
    for bad in (0, -512, "50176", 1.5, True):
        with pytest.raises(ConfigError):
            PEC.from_dict({**raw, "total_timesteps": bad})
    names = ("walk_forward_c_k1.yaml", "confirmation_k0.yaml", "turnover_refine_k1.yaml",
             "turnover_k1.yaml", "dose_response_l0.yaml", "profile_experiment.yaml")  # fmt: skip
    for name in names:
        assert "total_timesteps" not in load_profile_experiment_config(CONFIG_DIR / name).to_dict()


# --------------------------------------------------------------------------
# Hypotheses, gap attribution and outcomes (synthetic tables)
# --------------------------------------------------------------------------


def _table(effects, *, train_shift=0.0, cash=0.3, turnover_ratio=0.9, seed=0, noise=0.02):
    """``effects``: per fold, the E11H - E11R validation Sharpe effect; ``train_shift``: the
    E11H - E11R training Sharpe effect (negative = a lower in-sample fit)."""
    rng = np.random.default_rng(seed)
    rows = []
    for fold, effect in effects.items():
        for s in wc.SEEDS:
            base = {"train": 2.5 + rng.normal(0, 0.2), "validation": 0.1 + rng.normal(0, 0.2)}
            for split in ("train", "validation"):
                for role in ("control", "treatment"):
                    t = role == "treatment"
                    shift = (effect if split == "validation" else train_shift) * t
                    sharpe = base[split] + shift + t * rng.normal(0, noise)
                    turnover = 20.0 * (turnover_ratio if t else 1.0)
                    drag = 0.0045 * turnover
                    rows.append({"fold": fold, "split": split, "role": role, "seed": s,
                                 "turnover_penalty": 0.0015, "net_sharpe": sharpe,
                                 "net_annualised_return": sharpe / 25,
                                 "gross_cumulative_return": 0.1, "cost_drag": drag,
                                 "net_cumulative_return": 0.1 - drag, "turnover": turnover,
                                 "net_volatility": 0.08, "net_max_drawdown": -0.15,
                                 "target_cash": cash if t else 0.3, "target_risky_hhi": 0.55,
                                 "allocation_dispersion": 0.11,
                                 "share_meaningful_changes": 0.75,
                                 "allocation_stability_dw": 0.06, "target_equity": 0.2,
                                 "target_bonds": 0.4,
                                 "share_target_cash_above_95": 0.0})  # fmt: skip
    return pd.DataFrame(rows)


BASELINES = {f: {"strategies": {"buy_and_hold_equal_weight": {"net_sharpe": 0.7},
                                "inverse_volatility_monthly": {"net_sharpe": 0.9}}}
             for f in wc.FOLDS}  # fmt: skip
GOOD = {"repro": {"fold A E11R = E10T1 (validation)": {"identical": True}},
        "budget": {"all_match": True}, "integrity": {f: {"verified": True} for f in wc.FOLDS},
        "complete": {f: 5 for f in wc.FOLDS}}  # fmt: skip


def _run(effects, **kwargs):
    checks = {**GOOD, **{k: kwargs.pop(k) for k in list(kwargs) if k in GOOD}}
    table = _table(effects, **kwargs)
    diffs = wc.paired_differences(table)
    _, gaps = bc.gap_table(table)
    summary = wc.fold_summary(diffs)
    return bc.hypotheses(table, diffs, gaps, summary, BASELINES, checks["repro"],
                         checks["budget"], checks["integrity"], checks["complete"])  # fmt: skip


def test_genuine_generalisation_improvement() -> None:
    out = _run({"A": 0.2, "B": 0.2, "C": 0.2}, train_shift=-0.3)
    assert out["outcome"]["class"] == "Generalisation improvement"
    assert all(v["attribution"] == "genuine" for v in out["H3"]["attribution"].values())
    assert out["H1"]["verdict"] == out["H3"]["verdict"] == out["H8"]["verdict"] == "supported"


def test_a_smaller_gap_from_a_lower_training_fit_is_not_generalisation() -> None:
    out = _run({"A": 0.0, "B": 0.0, "C": 0.0}, train_shift=-0.5, noise=0.0)
    assert out["H3"]["verdict"] == "supported"  # the gap shrinks ...
    assert {v["attribution"] for v in out["H3"]["attribution"].values()} == {"training loss only"}
    assert out["outcome"]["class"] == "No reliable improvement"  # ... but validation does not rise


def test_partial_deterioration_and_inconclusive() -> None:
    partial = _run({"A": 0.2, "B": 0.2, "C": 0.0}, train_shift=-0.3, noise=0.0)
    assert partial["outcome"]["class"] == "Partial improvement"
    assert _run({"A": -0.3, "B": -0.3, "C": 0.2})["outcome"]["class"] == "Deterioration"
    wrong = _run({"A": 0.2, "B": 0.2, "C": 0.2}, budget={"all_match": False})
    assert wrong["H9"]["verdict"] == "not supported" and wrong["outcome"]["class"] == "Inconclusive"
    short = _run({"A": 0.2, "B": 0.2, "C": 0.2}, complete={"A": 5, "B": 4, "C": 5})
    assert short["outcome"]["class"] == "Inconclusive"


def test_inactivity_cash_and_return_guards() -> None:
    idle = _run({"A": 0.2, "B": 0.2, "C": 0.2}, train_shift=-0.3, turnover_ratio=0.3)
    assert idle["H5"]["verdict"] == "not supported"  # turnover collapses below 50% of E11R
    cashy = _run({"A": 0.2, "B": 0.2, "C": 0.2}, train_shift=-0.3, cash=0.6)
    assert cashy["H5"]["verdict"] == "not supported"
    worse = _run({"A": -0.2, "B": -0.2, "C": -0.2}, train_shift=-0.3, noise=0.0)
    assert worse["H4"]["verdict"] == "not supported"  # -0.2 / 25 = -0.8 pp < -0.5 pp
    assert worse["H8"]["verdict"] == "not supported"


def test_gap_statistics_are_paired_within_folds() -> None:
    table = _table({"A": 0.1, "B": 0.0, "C": -0.1}, train_shift=-0.2, noise=0.0)
    runs, stats = bc.gap_table(table)
    assert len(runs) == 3 * 2 * 5 and set(stats["n"]) == {5}
    assert stats.set_index("fold")["mean"].round(12).to_dict() == {"A": -0.3, "B": -0.2, "C": -0.1}
    assert (runs["gap"] == runs["train_sharpe"] - runs["validation_sharpe"]).all()
