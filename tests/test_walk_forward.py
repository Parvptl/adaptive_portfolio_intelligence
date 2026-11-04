"""E10 walk-forward folds: config, fold inputs, leakage checks, analysis (D-094; no ``rl``)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import (
    ConfigError,
    WalkForwardFold,
    apply_walk_forward_fold,
    load_feature_config,
    load_profile_experiment_config,
    load_project_config,
)
from adaptive_portfolio.data import walk_forward as wf
from adaptive_portfolio.data.pipeline import build_dataset, project_root_for
from adaptive_portfolio.explainability import walk_forward_comparison as wc
from adaptive_portfolio.features.pipeline import build_feature_dataset, feature_output_dir
from conftest import CONFIG_DIR, write_feature_config, write_tiny_project

PROJECT_SPLITS = {
    "train": {"start": "2024-01-01", "end": "2024-03-29"},
    "validation": {"start": "2024-04-01", "end": "2024-05-31"},
    "test": {"start": "2024-06-01", "end": "2024-06-28"},
}
EARLY = {"id": "A", "train": {"start": "2024-01-01", "end": "2024-02-29"},
         "validation": {"start": "2024-03-01", "end": "2024-03-29"},
         "holdout": {"start": "2024-04-01", "end": "2024-05-31"}}  # fmt: skip


# --------------------------------------------------------------------------
# Fold configuration and temporal boundaries
# --------------------------------------------------------------------------


def test_e10_configs_are_three_valid_folds_and_differ_only_as_prespecified() -> None:
    base = load_project_config(CONFIG_DIR)
    e8 = [load_profile_experiment_config(CONFIG_DIR / f"turnover_refine_k{k}.yaml").to_dict()
          for k in (0, 1)]  # fmt: skip
    seen = {}
    for f, reference in (("a", False), ("b", False), ("c", True)):
        pair = [load_profile_experiment_config(CONFIG_DIR / f"walk_forward_{f}_k{k}.yaml")
                for k in (0, 1)]  # fmt: skip
        assert [p.reward.turnover_penalty for p in pair] == [0.0, 0.0015]
        assert all(p.reward.fixed_lambda == 0.0 and p.seeds == (42, 43, 44, 45, 46) for p in pair)
        for p, old in zip(pair, e8, strict=True):
            new = p.to_dict()
            assert {k for k in set(new) | set(old) if new.get(k) != old.get(k)} == {
                "label", "walk_forward_fold"}  # fmt: skip
        fold = pair[0].walk_forward_fold
        assert fold == pair[1].walk_forward_fold
        _, is_reference = apply_walk_forward_fold(base, fold)
        assert is_reference is reference
        if not reference:  # every boundary before the sealed test period
            assert fold.splits.test.end < base.experiment.splits.test.start
        seen[fold.id] = fold.splits
    assert seen["C"] == base.experiment.splits  # the D-009 split
    v = [seen[k].validation for k in "ABC"]
    assert v[0].end < v[1].start and v[1].end < v[2].start  # disjoint validation windows
    assert all(seen[k].train.start == seen["A"].train.start for k in "ABC")  # expanding


def test_invalid_fold_boundaries_are_rejected(tmp_path: Path) -> None:
    config = load_project_config(write_tiny_project(tmp_path, universe=["AAA", "BBB", "CCC"],
                                                    start="2024-01-01", end="2024-06-28",
                                                    splits=PROJECT_SPLITS))  # fmt: skip
    fold = WalkForwardFold.from_dict(EARLY)
    assert apply_walk_forward_fold(config, fold)[1] is False
    into_test = WalkForwardFold.from_dict({**EARLY, "holdout": {"start": "2024-04-01",
                                                                "end": "2024-06-14"}})  # fmt: skip
    with pytest.raises(ConfigError, match="sealed"):
        apply_walk_forward_fold(config, into_test)
    before = WalkForwardFold.from_dict({**EARLY, "train": {"start": "2023-12-01",
                                                           "end": "2024-02-29"}})  # fmt: skip
    with pytest.raises(ConfigError, match="before the project's train"):
        apply_walk_forward_fold(config, before)
    with pytest.raises(ConfigError, match="train must end before validation"):
        WalkForwardFold.from_dict({**EARLY, "validation": {"start": "2024-02-01",
                                                           "end": "2024-03-29"}})  # fmt: skip
    with pytest.raises(ConfigError):
        WalkForwardFold.from_dict({**EARLY, "id": "too long id"})
    assert WalkForwardFold.from_dict(EARLY).to_dict() == EARLY


def test_earlier_experiment_identities_are_unchanged() -> None:
    names = (
        "confirmation_k0.yaml",
        "turnover_refine_k1.yaml",
        "turnover_k2.yaml",
        "dose_response_l3.yaml",
        "fixed_risk_high.yaml",
        "profile_experiment.yaml",
    )
    for name in names:
        config = load_profile_experiment_config(CONFIG_DIR / name)
        assert "walk_forward_fold" not in config.to_dict()


# --------------------------------------------------------------------------
# Fold inputs and leakage checks (synthetic dataset)
# --------------------------------------------------------------------------


@pytest.fixture
def parent(tmp_path: Path):
    config_dir = write_tiny_project(tmp_path, universe=["AAA", "BBB", "CCC"], start="2024-01-01",
                                    end="2024-06-28", splits=PROJECT_SPLITS)  # fmt: skip
    write_feature_config(config_dir)
    config = load_project_config(config_dir)
    root = project_root_for(config_dir)
    build_dataset(config, root, provider_name="synthetic")
    features = load_feature_config(config_dir / "features.yaml")
    result = build_feature_dataset(config, features, root, provider_name="synthetic")
    dataset_dir = Path(json.loads((result.output_dir / "feature_metadata.json").read_text(
        encoding="utf-8"))["input"]["processed_dataset_id"])  # fmt: skip
    dataset_dir = root / "data/processed" / dataset_dir.name
    return {"root": root, "config": config, "features": features, "dataset": dataset_dir,
            "feature_dir": result.output_dir}  # fmt: skip


def test_fold_dataset_is_an_exact_prefix_with_fold_labels_and_no_test_row(parent) -> None:
    fold = WalkForwardFold.from_dict(EARLY)
    root, config = parent["root"], parent["config"]
    fold_dir = wf.build_fold_dataset(root, parent["dataset"], config, fold)
    assert fold_dir == wf.fold_dataset_dir(root, parent["dataset"], fold)
    assert wf.build_fold_dataset(root, parent["dataset"], config, fold) == fold_dir  # idempotent
    head = (parent["dataset"] / "returns.csv").read_bytes()
    assert head.startswith((fold_dir / "returns.csv").read_bytes())
    splits = pd.read_csv(fold_dir / "splits.csv")
    assert splits["date"].iloc[-1] <= "2024-05-31" < str(config.experiment.splits.test.start)
    assert splits.groupby("split")["date"].agg(["min", "max"]).to_dict() == {
        "min": {"test": "2024-04-01", "train": "2024-01-02", "validation": "2024-03-01"},
        "max": {"test": "2024-05-31", "train": "2024-02-29", "validation": "2024-03-29"},
    }
    feature_dir = wf.build_fold_features(root, fold_dir, config, fold, parent["features"])
    report = wf.verify_fold(root, fold_dir, feature_dir, parent["dataset"], parent["feature_dir"],
                            config, fold)  # fmt: skip
    assert report["verified"], report["checks"]
    meta = json.loads((Path(feature_dir) / "feature_metadata.json").read_text(encoding="utf-8"))
    assert meta["thresholds_mode"] == "fitted_on_train"
    ours = json.loads((Path(feature_dir) / "regime_thresholds.json").read_text(encoding="utf-8"))
    theirs = json.loads((parent["feature_dir"] / "regime_thresholds.json").read_text("utf-8"))
    assert ours != theirs  # calibrated on the fold's training rows, not the project's


def test_tampered_fold_inputs_fail_verification(parent) -> None:
    fold = WalkForwardFold.from_dict(EARLY)
    root, config = parent["root"], parent["config"]
    fold_dir = wf.build_fold_dataset(root, parent["dataset"], config, fold)
    feature_dir = wf.build_fold_features(root, fold_dir, config, fold, parent["features"])
    path = fold_dir / "returns.csv"
    original = path.read_bytes()
    path.write_bytes(original.replace(b"2024-01-0", b"2024-01-1", 1))
    assert wf.verify_fold_dataset(fold_dir, parent["dataset"], config, fold)
    path.write_bytes(original)
    labels = pd.read_csv(fold_dir / "splits.csv")
    labels.loc[labels.index[-1], "split"] = "validation"
    labels.to_csv(fold_dir / "splits.csv", index=False, lineterminator="\n")
    assert "labels" in " ".join(wf.verify_fold_dataset(fold_dir, parent["dataset"], config, fold))
    assert feature_output_dir(parent["features"], root, fold_dir.name, None)[0] == Path(feature_dir)
    other = WalkForwardFold.from_dict({**EARLY, "id": "B"})
    assert wf.fold_dataset_dir(root, parent["dataset"], other) != fold_dir  # distinct identity


# --------------------------------------------------------------------------
# Analysis: fold synthesis, hypotheses and outcome (synthetic tables)
# --------------------------------------------------------------------------


def _table(effects: dict[str, float], *, noise: float = 0.02, cash: float = 0.3, seed: int = 0):
    rng = np.random.default_rng(seed)
    rows = []
    for fold, effect in effects.items():
        for split in ("train", "validation"):
            for s in wc.SEEDS:
                base = 0.5 + rng.normal(0, 0.2)
                turnover = 17 + rng.normal(0, 2)
                for role, kappa in (("control", 0.0), ("treatment", 0.0015)):
                    t = role == "treatment"
                    sharpe = base + (effect + rng.normal(0, noise)) * t
                    turn = turnover * (0.6 if t else 1.0)
                    drag = 0.0055 * turn
                    rows.append({"fold": fold, "split": split, "role": role, "seed": s,
                                 "turnover_penalty": kappa, "net_sharpe": sharpe,
                                 "net_annualised_return": sharpe / 20,
                                 "gross_cumulative_return": 0.17, "cost_drag": drag,
                                 "net_cumulative_return": 0.17 - drag, "turnover": turn,
                                 "net_volatility": 0.055, "net_max_drawdown": -0.08,
                                 "target_cash": cash if t else 0.25, "target_risky_hhi": 0.5,
                                 "allocation_dispersion": 0.1, "share_meaningful_changes": 0.6,
                                 "allocation_stability_dw": 0.05, "target_equity": 0.15,
                                 "target_bonds": 0.5,
                                 "share_target_cash_above_95": 0.0})  # fmt: skip
    return pd.DataFrame(rows)


OK_REPRO = {"fold C control = E8B (validation)": {"identical": True}}
OK_INTEGRITY = {f: {"verified": True} for f in wc.FOLDS}
COMPLETE = {f: 5 for f in wc.FOLDS}


def _run(effects, repro=OK_REPRO, integrity=OK_INTEGRITY, complete=COMPLETE, **kwargs):
    table = _table(effects, **kwargs)
    diffs = wc.paired_differences(table)
    summary = wc.fold_summary(diffs)
    return wc.hypotheses(table, diffs, summary, repro, integrity, complete), summary, diffs


def test_outcome_classes_follow_the_fold_rule() -> None:
    hyp, summary, _ = _run({"A": 0.3, "B": 0.3, "C": 0.3})
    assert summary["positive_folds"] == ["A", "B", "C"]
    assert hyp["outcome"]["class"] == "Walk-forward confirmation"
    assert hyp["H3"]["verdict"] == "supported" and hyp["H10"]["verdict"] == "supported"
    assert _run({"A": 0.3, "B": 0.3, "C": 0.0}, noise=0.0)[0]["outcome"]["class"] == (
        "Partial confirmation")  # fmt: skip
    one = _run({"A": 0.0, "B": 0.0, "C": 0.3}, noise=0.0)[0]
    assert one["outcome"]["class"] == "No reliable improvement"  # one fold is not confirmation
    assert one["H3"]["verdict"] == "partially supported"
    assert _run({"A": -0.3, "B": -0.3, "C": 0.3})[0]["outcome"]["class"] == "Deterioration"
    assert _run({"A": 0.3, "B": -0.3, "C": 0.3})[0]["outcome"]["class"] == (
        "No reliable improvement")  # a negative fold blocks partial confirmation  # fmt: skip


def test_guard_rails_failures_and_missing_pairs() -> None:
    cash_heavy = _run({"A": 0.3, "B": 0.3, "C": 0.3}, cash=0.6)[0]
    assert cash_heavy["outcome"]["class"] == "Walk-forward confirmation"
    assert cash_heavy["H7"]["verdict"] == "not supported"
    assert cash_heavy["H10"]["verdict"] == "partially supported"
    failed = _run({"A": 0.3, "B": 0.3, "C": 0.3}, repro={"x": {"identical": False}})[0]
    assert failed["H9"]["verdict"] == "not supported" and failed["outcome"]["class"] == (
        "Inconclusive")  # fmt: skip
    bad = {**OK_INTEGRITY, "A": {"verified": False}}
    leaky = _run({"A": 0.3, "B": 0.3, "C": 0.3}, integrity=bad)[0]
    assert leaky["outcome"]["class"] == "Inconclusive"
    short = _run({"A": 0.3, "B": 0.3, "C": 0.3}, complete={**COMPLETE, "B": 4})[0]
    assert short["outcome"]["class"] == "Inconclusive"
    table = _table({"A": 0.3, "B": 0.3, "C": 0.3})
    with pytest.raises(wc.WalkForwardComparisonError, match="missing seeds"):
        wc.paired_differences(table[~((table["fold"] == "B") & (table["seed"] == 44)
                                      & (table["role"] == "treatment"))])  # fmt: skip
    with pytest.raises(wc.WalkForwardComparisonError, match="duplicate"):
        wc.paired_differences(pd.concat([table, table.iloc[[0]]]))


def test_statistics_use_the_fold_seed_unit_and_keep_folds_apart() -> None:
    _, summary, diffs = _run({"A": 0.4, "B": -0.2, "C": 0.1}, noise=0.0)
    sharpe = diffs[(diffs["metric"] == "net_sharpe") & (diffs["split"] == "validation")]
    assert sorted(sharpe["fold"]) == ["A", "B", "C"] and set(sharpe["n"]) == {5}
    assert sharpe.set_index("fold")["mean"].round(12).to_dict() == {"A": 0.4, "B": -0.2, "C": 0.1}
    assert summary["mean_of_fold_means"] == pytest.approx(0.1)
    assert summary["folds"]["A"]["share_of_absolute_effect"] == pytest.approx(0.4 / 0.7)
    assert all(row["permutation_p"] >= 2 / 32 for _, row in sharpe.iterrows())  # 5 pairs
    observed, p = wc.stratified_permutation_p([np.full(5, 0.3), np.full(5, 0.3), np.full(5, 0.3)])
    assert observed == pytest.approx(0.3) and p == pytest.approx(2 / 2**15)
    zero, p_zero = wc.stratified_permutation_p([np.zeros(5)] * 3)
    assert zero == 0.0 and p_zero == 1.0
    identical = _run({"A": 0.0, "B": 0.0, "C": 0.0}, noise=0.0)[2]
    assert (identical[identical["metric"] == "net_sharpe"]["n_ties"] == 5).all()
