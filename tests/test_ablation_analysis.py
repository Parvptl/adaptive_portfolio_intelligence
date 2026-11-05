"""E12 regime ablation: configs, the ablation key, H1-H9 and outcomes (D-096; no ``rl``)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import ConfigError, load_profile_experiment_config, load_yaml
from adaptive_portfolio.config import ProfileExperimentConfig as PEC
from adaptive_portfolio.explainability import ablation_comparison as ac
from adaptive_portfolio.explainability import budget_comparison as bc
from adaptive_portfolio.explainability import walk_forward_comparison as wc
from conftest import CONFIG_DIR


def test_e12_configs_differ_only_in_the_ablation_and_reproduce_e10t1() -> None:
    for f in "abc":
        full, ablated = (load_profile_experiment_config(CONFIG_DIR / f"ablation_{f}_{a}.yaml")
                         for a in ("full", "noregime"))  # fmt: skip
        e10t1 = load_profile_experiment_config(CONFIG_DIR / f"walk_forward_{f}_k1.yaml")
        assert full.observation_ablation is None and ablated.observation_ablation == "regime"
        for x in (full, ablated):
            assert x.reward.turnover_penalty == 0.0015 and x.reward.fixed_lambda == 0.0
            assert x.total_timesteps is None and x.seeds == (42, 43, 44, 45, 46)
            assert x.walk_forward_fold == e10t1.walk_forward_fold
        a, b, c = full.to_dict(), ablated.to_dict(), e10t1.to_dict()
        assert {k for k in set(a) | set(b) if a.get(k) != b.get(k)} == {
            "label", "observation_ablation"}  # fmt: skip
        assert {k for k in set(a) | set(c) if a.get(k) != c.get(k)} == {"label"}
        assert full.output_dir.as_posix() == "data/processed/ablation_experiments"


def test_ablation_key_is_validated_and_absent_from_earlier_identities() -> None:
    raw = load_yaml(CONFIG_DIR / "ablation_a_noregime.yaml")
    for bad in ("features", "", 1, True):
        with pytest.raises(ConfigError):
            PEC.from_dict({**raw, "observation_ablation": bad})
    names = ("budget_a_half.yaml", "walk_forward_c_k1.yaml", "confirmation_k0.yaml",
             "turnover_refine_k1.yaml", "dose_response_l0.yaml",
             "profile_experiment.yaml")  # fmt: skip
    for name in names:
        d = load_profile_experiment_config(CONFIG_DIR / name).to_dict()
        assert "observation_ablation" not in d


def _table(effects, *, cost_shift=0.0, turnover_ratio=1.0, cash=0.3, seed=0, noise=0.02):
    rng = np.random.default_rng(seed)
    rows = []
    for fold, effect in effects.items():
        for s in wc.SEEDS:
            base = {"train": 2.5 + rng.normal(0, 0.2), "validation": 0.1 + rng.normal(0, 0.2)}
            for split in ("train", "validation"):
                for role in ("control", "treatment"):
                    t = role == "treatment"
                    shift = effect * t if split == "validation" else 0.0
                    sharpe = base[split] + shift + t * rng.normal(0, noise)
                    turnover = 20.0 * (turnover_ratio if t else 1.0)
                    drag = 0.09 + cost_shift * t
                    rows.append({"fold": fold, "split": split, "role": role, "seed": s,
                                 "turnover_penalty": 0.0015, "net_sharpe": sharpe,
                                 "net_annualised_return": sharpe / 25,
                                 "gross_cumulative_return": 0.2, "cost_drag": drag,
                                 "net_cumulative_return": 0.2 - drag, "turnover": turnover,
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
GOOD = {"repro": {"fold A E12F = E10T1 (validation)": {"identical": True}},
        "records": {"all_match": True}, "integrity": {f: {"verified": True} for f in wc.FOLDS},
        "complete": {f: 5 for f in wc.FOLDS}}  # fmt: skip


def _run(effects, **kwargs):
    checks = {**GOOD, **{k: kwargs.pop(k) for k in list(kwargs) if k in GOOD}}
    table = _table(effects, **kwargs)
    diffs = wc.paired_differences(table)
    _, gaps = bc.gap_table(table)
    summary = wc.fold_summary(diffs)
    return ac.hypotheses(table, diffs, gaps, summary, BASELINES, checks["repro"],
                         checks["records"], checks["integrity"], checks["complete"])  # fmt: skip


def test_outcome_classes() -> None:
    good = _run({"A": 0.2, "B": 0.2, "C": 0.2})
    assert good["outcome"]["class"] == "Generalisation improvement"
    assert good["H1"]["verdict"] == good["H2"]["verdict"] == good["H8"]["verdict"] == "supported"
    assert _run({"A": 0.2, "B": 0.2, "C": 0.0}, noise=0.0)["outcome"]["class"] == (
        "Partial improvement")  # fmt: skip
    worse = _run({"A": -0.2, "B": -0.2, "C": 0.1})
    assert worse["outcome"]["class"] == "Deterioration"  # the regime inputs then look useful
    assert worse["H3"]["verdict"] != "supported"
    assert _run({"A": 0.2, "B": 0.0, "C": -0.2}, noise=0.0)["outcome"]["class"] == (
        "No reliable improvement")  # fmt: skip


def test_integrity_and_guard_rails() -> None:
    bad = _run({"A": 0.2, "B": 0.2, "C": 0.2}, records={"all_match": False})
    assert bad["H9"]["verdict"] == "not supported" and bad["outcome"]["class"] == "Inconclusive"
    short = _run({"A": 0.2, "B": 0.2, "C": 0.2}, complete={"A": 5, "B": 5, "C": 4})
    assert short["outcome"]["class"] == "Inconclusive"
    costly = _run({"A": 0.2, "B": 0.2, "C": 0.2}, cost_shift=0.02)
    assert costly["H4"]["verdict"] == "not supported"  # +2 pp cost drag > +1 pp tolerance
    idle = _run({"A": 0.2, "B": 0.2, "C": 0.2}, turnover_ratio=0.3)
    assert idle["H4"]["verdict"] == "not supported"
    cashy = _run({"A": 0.2, "B": 0.2, "C": 0.2}, cash=0.6)
    assert cashy["H6"]["verdict"] == "not supported"
    assert set(_run({"A": 0.1, "B": 0.1, "C": 0.1})["gap"]["attribution"]) == {"A", "B", "C"}
