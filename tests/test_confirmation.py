"""E9 confirmation: paired-seed statistics, input checks, configs and H1-H10 (D-093; no ``rl``)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import ConfigError, load_profile_experiment_config, load_yaml
from adaptive_portfolio.config import ProfileExperimentConfig as PEC
from adaptive_portfolio.explainability import confirmation_comparison as cc
from adaptive_portfolio.explainability.turnover_comparison import _core
from conftest import CONFIG_DIR

SEEDS = list(cc.PRIMARY_SEEDS)
LABELS = ("E9B", "E9T1")


# --------------------------------------------------------------------------
# Paired statistics with known outcomes
# --------------------------------------------------------------------------


def test_positive_effect_is_detected() -> None:
    rng = np.random.default_rng(1)
    control = pd.Series(rng.normal(0.5, 0.3, 10), index=SEEDS)
    diff = cc.paired(control, control + 0.4, SEEDS)
    s = cc.paired_stats(diff.to_numpy())
    assert s["mean"] == pytest.approx(0.4) and s["n_positive"] == 10 and s["n_ties"] == 0
    assert s["bootstrap_low"] == pytest.approx(0.4) and s["bootstrap_high"] == pytest.approx(0.4)
    assert s["permutation_p"] == pytest.approx(2 / 1024)  # only all-plus and all-minus


def test_negative_effect_is_reported_as_negative() -> None:
    d = np.array([-0.30, -0.10, -0.25, -0.40, -0.05, -0.20, -0.35, -0.15, 0.02, -0.22])
    s = cc.paired_stats(d)
    assert s["mean"] < 0 and s["bootstrap_high"] < 0 and s["t_high"] < 0
    assert (s["n_positive"], s["n_negative"]) == (1, 9) and s["permutation_p"] < 0.05


def test_identical_arms_give_zero_differences() -> None:
    control = pd.Series(np.linspace(0.1, 1.0, 10), index=SEEDS)
    s = cc.paired_stats(cc.paired(control, control.copy(), SEEDS).to_numpy())
    assert s["mean"] == 0.0 and s["n_ties"] == 10 and s["n_positive"] == s["n_negative"] == 0
    assert (s["bootstrap_low"], s["bootstrap_high"]) == (0.0, 0.0)
    assert s["permutation_p"] == 1.0


def test_duplicate_and_missing_seeds_are_rejected() -> None:
    control = pd.Series(np.ones(10), index=SEEDS)
    duplicated = pd.Series(np.ones(10), index=[*SEEDS[:9], SEEDS[0]])
    with pytest.raises(cc.ConfirmationError, match="duplicate seeds"):
        cc.paired(control, duplicated, SEEDS)
    with pytest.raises(cc.ConfirmationError, match=r"missing seeds \[56\]"):
        cc.paired(control, control.drop(56), SEEDS)
    with pytest.raises(cc.ConfirmationError, match="non-finite"):
        cc.paired(control, control.where(control.index != 47, np.nan), SEEDS)


def test_intervals_and_exact_permutation_are_computed_correctly() -> None:
    assert cc.permutation_p(np.array([1.0, 2.0, 3.0])) == pytest.approx(2 / 8)
    d = np.array([0.3, -0.1, 0.2, 0.5, 0.0, 0.4, -0.2, 0.1, 0.25, 0.15])
    s = cc.paired_stats(d)
    se = d.std(ddof=1) / math.sqrt(10)
    assert s["se"] == pytest.approx(se)
    assert (s["t_low"], s["t_high"]) == pytest.approx((d.mean() - 2.262 * se,
                                                       d.mean() + 2.262 * se))  # fmt: skip
    assert s["t_statistic"] == pytest.approx(d.mean() / se)
    rng = np.random.default_rng(cc.BOOTSTRAP_SEED)
    means = d[rng.integers(0, 10, size=(cc.BOOTSTRAP_RESAMPLES, 10))].mean(axis=1)
    assert (s["bootstrap_low"], s["bootstrap_high"]) == pytest.approx(
        tuple(np.quantile(means, [0.025, 0.975])))  # fmt: skip
    assert cc.paired_stats(d) == s  # deterministic (fixed bootstrap seed)
    assert s["n_ties"] == 1 and s["n_positive"] == 7 and s["n_negative"] == 2
    assert cc.BOOTSTRAP_RESAMPLES >= 10_000


# --------------------------------------------------------------------------
# Configurations
# --------------------------------------------------------------------------


def test_e9_configs_differ_only_in_kappa_and_equal_e8() -> None:
    b, t = (load_profile_experiment_config(CONFIG_DIR / f"confirmation_k{k}.yaml")
            for k in (0, 1))  # fmt: skip
    assert (b.label, t.label) == LABELS
    assert (b.reward.turnover_penalty, t.reward.turnover_penalty) == (0.0, 0.0015)
    assert b.reward.fixed_lambda == t.reward.fixed_lambda == 0.0
    assert _core(b.to_dict()) == _core(t.to_dict())
    assert b.seeds == tuple(range(42, 57)) and b.extension_seeds == cc.PRIMARY_SEEDS
    for e9, e8 in ((b, "turnover_refine_k0.yaml"), (t, "turnover_refine_k1.yaml")):
        old = load_profile_experiment_config(CONFIG_DIR / e8).to_dict()
        new = e9.to_dict()
        assert {k for k in set(old) | set(new) if old.get(k) != new.get(k)} == {
            "label", "seeds", "extension_seeds"}  # fmt: skip
        assert "extension_seeds" not in old  # E1-E8 identities are unchanged
    assert b.output_dir.as_posix() == "data/processed/confirmation_experiments"


def test_extension_seeds_must_be_declared_seeds() -> None:
    raw = load_yaml(CONFIG_DIR / "confirmation_k0.yaml")
    with pytest.raises(ConfigError, match="subset of seeds"):
        PEC.from_dict({**raw, "extension_seeds": [47, 99]})
    with pytest.raises(ConfigError):
        PEC.from_dict({**raw, "extension_seeds": [47, 47]})
    assert "extension_seeds" not in PEC.from_dict(
        {k: v for k, v in raw.items() if k != "extension_seeds"}).to_dict()  # fmt: skip


# --------------------------------------------------------------------------
# Hypotheses and outcome
# --------------------------------------------------------------------------


def _table(effect: float, *, noise: float = 0.05, cash: float = 0.27, seed: int = 0):
    rng = np.random.default_rng(seed)
    rows = []
    for split in ("train", "validation"):
        for s in range(42, 57):
            base = {"net_sharpe": 0.5 + rng.normal(0, 0.2), "turnover": 17 + rng.normal(0, 3),
                    "gross_cumulative_return": 0.17}  # fmt: skip
            for label, kappa in zip(LABELS, (0.0, 0.0015), strict=True):
                treated = label == "E9T1"
                sharpe = base["net_sharpe"] + (effect + rng.normal(0, noise)) * treated
                turnover = base["turnover"] * (0.6 if treated else 1.0)
                drag = 0.0055 * turnover
                gross = base["gross_cumulative_return"]
                rows.append({"split": split, "seed": s, "arm": label, "turnover_penalty": kappa,
                             "population": "primary" if s >= 47 else "reproduction",
                             "net_sharpe": sharpe, "net_annualised_return": sharpe / 20,
                             "gross_cumulative_return": gross, "cost_drag": drag,
                             "net_cumulative_return": gross - drag, "turnover": turnover,
                             "net_volatility": 0.055, "net_max_drawdown": -0.08,
                             "target_cash": cash if treated else 0.25,
                             "target_risky_hhi": 0.5, "allocation_dispersion": 0.1,
                             "share_meaningful_changes": 0.6, "allocation_stability_dw": 0.05,
                             "target_equity": 0.15, "target_bonds": 0.5,
                             "share_target_cash_above_95": 0.0})  # fmt: skip
    return pd.DataFrame(rows)


SAME = {"E9B = E8B (validation)": {"identical": True}}


def _run(effect: float, repro=SAME, complete: int = 10, **kwargs) -> dict:
    table = _table(effect, **kwargs)
    return cc.hypotheses(table, cc.paired_differences(table, LABELS), LABELS, repro, complete)


def test_confirmation_partial_none_and_deterioration() -> None:
    strong = _run(0.3)
    assert strong["H3"]["verdict"] == strong["H4"]["verdict"] == "supported"
    assert strong["H1"]["verdict"] == strong["H2"]["verdict"] == "supported"
    assert strong["H5"]["verdict"] == "supported"  # saved costs, no gross change
    assert strong["H10"]["verdict"] == "supported"
    assert strong["outcome"]["class"] == "Confirmation"
    assert _run(0.0, noise=0.0)["outcome"]["class"] == "No reliable improvement"
    assert _run(-0.3)["outcome"]["class"] == "Deterioration"
    weak = _run(0.03, noise=0.08, seed=3)
    assert weak["H3"]["verdict"] != "supported"
    assert weak["outcome"]["class"] in ("Partial confirmation", "No reliable improvement")


def test_guard_rails_and_failures() -> None:
    cash_heavy = _run(0.3, cash=0.6)
    assert cash_heavy["outcome"]["class"] == "Confirmation"  # reported as such ...
    assert cash_heavy["H7"]["verdict"] != "supported"
    assert cash_heavy["H10"]["verdict"] != "supported"  # ... but not practical utility
    failed = _run(0.3, repro={"x": {"identical": False}})
    assert failed["H9"]["verdict"] == "not supported"
    assert failed["outcome"]["class"].startswith("Inconclusive")
    missing = _run(0.3, complete=9)
    assert missing["outcome"]["class"].startswith("Inconclusive")


def test_paired_differences_keep_populations_separate() -> None:
    table = _table(0.2)
    diffs = cc.paired_differences(table, LABELS)
    sizes = diffs.groupby("population")["n"].first().to_dict()
    assert sizes == {"primary": 10, "reproduction": 5, "pooled": 15}
    primary = diffs[(diffs["population"] == "primary") & (diffs["metric"] == "net_sharpe")
                    & (diffs["split"] == "validation")].iloc[0]  # fmt: skip
    assert sorted(c for c in primary.index if c.startswith("seed_") and pd.notna(primary[c])) == (
        sorted(f"seed_{s}" for s in SEEDS))  # fmt: skip
