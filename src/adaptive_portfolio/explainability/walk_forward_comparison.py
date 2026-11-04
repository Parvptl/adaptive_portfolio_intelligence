"""E10 walk-forward analysis: kappa = 0 vs 0.0015 across three folds (D-094; no ``rl``).

Reads twelve **verified** evaluations (three folds x two arms x training and validation) and
writes once, under ``<evaluation root>/../walk_forward_comparisons/<id>/``:

* ``seed_table.csv``: per fold, split, arm and seed;
* ``paired_differences.csv``: per fold, split and metric: E10T1 - E10B per seed with mean,
  median, SD, SE, sign counts, the bootstrap CI, the exact permutation p and the t-interval;
* ``fold_summary.json``: the fold classification, the across-fold synthesis and the secondary
  stratified permutation test;
* ``hypotheses.json``: H1-H10 and the outcome (``docs/e10_walk_forward_protocol.md`` §7-§9);
* ``reproduction.json``: the reference fold C against E8 and E7, exactly (H9);
* ``integrity.json``: every leakage and boundary check of every fold (H9);
* ``baselines.json``: each fold's baselines (comparable within a fold only);
* ``e9_reference.json``: the verified E9 result, shown separately (never pooled);
* ``training_components.json``: reward components of the training episodes, per run.

Seeds within a fold share one market history and folds share training rows: the statistics are
paired and fold-level; nothing treats the fold-seed pairs as independent markets.
"""

from __future__ import annotations

import itertools
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.config import (
    WalkForwardFold,
    apply_walk_forward_fold,
    load_feature_config,
    load_project_config,
)
from adaptive_portfolio.data import cache, walk_forward
from adaptive_portfolio.data.pipeline import resolve_path
from adaptive_portfolio.explainability import confirmation_comparison as cc
from adaptive_portfolio.explainability.fixed_risk_comparison import _read, training_components
from adaptive_portfolio.explainability.turnover_comparison import _core, kappa_of
from adaptive_portfolio.explainability.turnover_refine_comparison import arm_table, compare_exact

SCHEMA_VERSION = 1
CRITERIA_VERSION = "D-094 v1 (docs/e10_walk_forward_protocol.md §7-§9, fixed before E10 training)"
FILES = ("seed_table.csv", "paired_differences.csv", "fold_summary.json", "hypotheses.json",
         "reproduction.json", "integrity.json", "baselines.json", "e9_reference.json",
         "training_components.json")  # fmt: skip
FOLDS = ("A", "B", "C")
REFERENCE_FOLD = "C"
SEEDS = (42, 43, 44, 45, 46)
TIE = cc.TIE
ENDPOINTS = cc.ENDPOINTS


class WalkForwardComparisonError(ValueError):
    """Raised when the E10 evaluations cannot be analysed as prespecified."""


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


def _fold_of(meta: Mapping[str, Any]) -> WalkForwardFold:
    raw = meta["experiment"].get("walk_forward_fold")
    if raw is None:
        raise WalkForwardComparisonError(f"{meta['evaluation_id']}: not a walk-forward evaluation")
    return WalkForwardFold.from_dict(raw)


def _without_fold(experiment: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in _core(experiment).items() if k != "walk_forward_fold"}


def window_checks(
    run: Mapping[str, Any], fold: WalkForwardFold, test_start: str
) -> dict[str, bool]:
    """The evaluation window lies inside the fold's declared split, and rows stop on time."""
    meta, window = run["meta"], run["summary"]["window"]
    split = meta["split"]
    period = getattr(fold.splits, "validation" if split == "validation" else "train")
    stop = fold.splits.test.start if split == "validation" else fold.splits.validation.start
    first, last = window["split_first_date"], window["last_return_date"]
    return {
        f"{split}: first row on or after {period.start}": first >= period.start.isoformat(),
        f"{split}: last return on or before {period.end}": last <= period.end.isoformat(),
        f"{split}: rows read only before {stop}": meta["rows_read_before"] == stop.isoformat(),
        f"{split}: no row on or after the test start {test_start}": last < test_start,
    }


def check_pair(
    runs: Sequence[Mapping[str, Any]], test_start: str = "2020-01-01"
) -> tuple[str, list[float], dict[str, bool]]:
    """E10B and E10T1 of one fold and split: kappa 0 < kappa 1, lambda 0, identical otherwise."""
    if len(runs) != 2:
        raise WalkForwardComparisonError("each fold needs exactly two arms (E10B, E10T1)")
    metas = [r["meta"] for r in runs]
    folds = [_fold_of(m) for m in metas]
    kappa = [kappa_of(m) for m in metas]
    first = metas[0]
    reference = folds[0].id == REFERENCE_FOLD
    checks = {
        "kappa 0 then kappa > 0": kappa[0] == 0.0 and kappa[1] > 0.0,
        "same fold": folds[0] == folds[1],
        "same split": metas[0]["split"] == metas[1]["split"],
        "not pipeline checks": not any(m["pipeline_check"] for m in metas),
        "identical except kappa and label": _core(metas[1]["experiment"]) == _core(
            first["experiment"]),
        "lambda = 0 in both arms": all(
            float((m["experiment"].get("reward") or {}).get("fixed_lambda", -1)) == 0.0
            for m in metas),
        "seeds are 42-46 in both arms": all(tuple(m["experiment"]["seeds"]) == SEEDS
                                            for m in metas),
        "same data": metas[1]["data"] == first["data"],
        "same rows boundary": metas[1]["rows_read_before"] == first["rows_read_before"],
        "same E0 checkpoints": metas[1]["e0_checkpoints"] == first["e0_checkpoints"],
        "E0 only in the reference fold": bool(first["e0_checkpoints"]) == reference,
    }  # fmt: skip
    for run, fold in zip(runs, folds, strict=True):
        label = run["meta"]["experiment"]["label"]
        for name, ok in window_checks(run, fold, test_start).items():
            checks[f"{label} {name}"] = ok
    if first["split"] == "validation" and reference:
        for run in runs:
            checks[f"{run['meta']['experiment']['label']}: E0 reproduces EXP-006"] = bool(
                run["summary"]["e0_reproduction"].get("reproduced"))  # fmt: skip
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise WalkForwardComparisonError(f"fold {folds[0].id} is not comparable: "
                                         + "; ".join(failed))  # fmt: skip
    return folds[0].id, kappa, checks


def seed_table(runs: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]]) -> pd.DataFrame:
    rows = []
    for (fold, split), pair in runs.items():
        for role, run in zip(("control", "treatment"), pair, strict=True):
            m = run["metrics"]
            label = run["meta"]["experiment"]["label"]
            part = m[(m["experiment"] == label) & (m["profile_set"] == "centre")]
            if part["seed"].duplicated().any():
                raise WalkForwardComparisonError(f"{label}: duplicate seed rows")
            for seed, row in arm_table(run).iterrows():
                rows.append(
                    {
                        "fold": fold,
                        "split": split,
                        "role": role,
                        "seed": int(seed),
                        "turnover_penalty": kappa_of(run["meta"]),
                        **row.to_dict(),
                    }
                )
    return pd.DataFrame(rows)


def _arm(table: pd.DataFrame, fold: str, split: str, role: str) -> pd.DataFrame:
    part = table[(table["fold"] == fold) & (table["split"] == split) & (table["role"] == role)]
    return part.set_index("seed").sort_index()


def paired_differences(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (fold, split), _ in table.groupby(["fold", "split"]):
        b, t = _arm(table, fold, split, "control"), _arm(table, fold, split, "treatment")
        for metric in ENDPOINTS:
            if metric not in b or metric not in t:
                continue
            try:
                diff = cc.paired(b[metric], t[metric], SEEDS)
            except cc.ConfirmationError as exc:
                raise WalkForwardComparisonError(f"fold {fold} {split} {metric}: {exc}") from None
            rows.append({"fold": fold, "split": split, "metric": metric,
                         "control_mean": float(b.loc[list(SEEDS), metric].mean()),
                         "treatment_mean": float(t.loc[list(SEEDS), metric].mean()),
                         "control_median": float(b.loc[list(SEEDS), metric].median()),
                         "treatment_median": float(t.loc[list(SEEDS), metric].median()),
                         **{f"seed_{s}": float(v) for s, v in diff.items()},
                         **cc.paired_stats(diff.to_numpy())})  # fmt: skip
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Fold synthesis, hypotheses and outcome
# --------------------------------------------------------------------------


def _row(diffs: pd.DataFrame, fold: str, metric: str, split: str = "validation") -> dict:
    part = diffs[(diffs["fold"] == fold) & (diffs["split"] == split) & (diffs["metric"] == metric)]
    if len(part) != 1:
        raise WalkForwardComparisonError(f"no unique row for fold {fold} {split} {metric}")
    return part.iloc[0].to_dict()


def classify(stats: Mapping[str, Any]) -> str:
    if stats["mean"] > 0 and stats["n_positive"] >= 4:
        return "positive"
    if stats["mean"] < 0 and stats["n_negative"] >= 4:
        return "negative"
    return "mixed"


def stratified_permutation_p(diffs_by_fold: Sequence[np.ndarray]) -> tuple[float, float]:
    """Exact sign-flip test of the average of the fold means (signs flipped within pairs)."""
    stacked = np.concatenate([np.asarray(d, float) for d in diffs_by_fold])
    sizes = [len(d) for d in diffs_by_fold]
    edges = np.cumsum([0, *sizes])
    signs = np.array(list(itertools.product((1.0, -1.0), repeat=len(stacked))))
    flipped = signs * stacked
    means = np.mean([flipped[:, a:b].mean(axis=1) for a, b in itertools.pairwise(edges)], axis=0)
    observed = float(np.mean([d.mean() for d in map(np.asarray, diffs_by_fold)]))
    return observed, float((np.abs(means) >= abs(observed) - TIE).mean())


def fold_summary(diffs: pd.DataFrame) -> dict[str, Any]:
    per_fold = {}
    for fold in FOLDS:
        s = _row(diffs, fold, "net_sharpe")
        per_fold[fold] = {"mean": s["mean"], "median": s["median"], "n_positive": s["n_positive"],
                          "n_negative": s["n_negative"], "bootstrap_low": s["bootstrap_low"],
                          "bootstrap_high": s["bootstrap_high"],
                          "permutation_p": s["permutation_p"], "class": classify(s)}  # fmt: skip
    means = np.array([per_fold[f]["mean"] for f in FOLDS])
    total = float(np.abs(means).sum())
    for fold, value in zip(FOLDS, means, strict=True):
        per_fold[fold]["share_of_absolute_effect"] = float(abs(value) / total) if total else 0.0
    vectors = [np.array([_row(diffs, f, "net_sharpe")[f"seed_{s}"] for s in SEEDS]) for f in FOLDS]
    observed, p = stratified_permutation_p(vectors)
    return {"metric": "net_sharpe", "split": "validation", "folds": per_fold,
            "positive_folds": [f for f in FOLDS if per_fold[f]["class"] == "positive"],
            "negative_folds": [f for f in FOLDS if per_fold[f]["class"] == "negative"],
            "mean_of_fold_means": float(means.mean()), "min_fold_mean": float(means.min()),
            "max_fold_mean": float(means.max()), "range": float(means.max() - means.min()),
            "secondary_stratified_permutation": {
                "statistic": "average of the three fold-mean differences", "observed": observed,
                "p": p, "assignments": 2 ** sum(len(v) for v in vectors),
                "caveat": "seeds share one market history and folds share training rows"},
            "note": "no interval across three folds is computed (protocol §8)"}  # fmt: skip


def _per_fold(diffs: pd.DataFrame, table: pd.DataFrame) -> dict[str, dict[str, Any]]:
    out = {}
    for fold in FOLDS:
        s = {m: _row(diffs, fold, m) for m in ENDPOINTS
             if not diffs[(diffs["fold"] == fold) & (diffs["metric"] == m)].empty}  # fmt: skip
        b = _arm(table, fold, "validation", "control").loc[list(SEEDS)]
        t = _arm(table, fold, "validation", "treatment").loc[list(SEEDS)]
        identity = max(float((a["gross_cumulative_return"] - a["net_cumulative_return"]
                              - a["cost_drag"]).abs().max()) for a in (b, t))  # fmt: skip
        ratios = {m: float(t[m].median()) / float(b[m].median()) if float(b[m].median()) > 0
                  else float("nan") for m in ("allocation_dispersion", "share_meaningful_changes",
                                              "allocation_stability_dw")}  # fmt: skip
        out[fold] = {
            "stats": s, "identity_error": identity,
            "cost_saving": -s["cost_drag"]["mean"],
            "gross_loss": -s["gross_cumulative_return"]["mean"],
            "treatment_medians": {m: float(t[m].median()) for m in (
                "target_risky_hhi", "target_cash", "share_target_cash_above_95")},
            "ratios_to_control": ratios,
        }  # fmt: skip
    return out


def _graded(flags: Mapping[str, bool], partial: bool) -> str:
    if flags and all(flags.values()):
        return "supported"
    return "partially supported" if partial else "not supported"


def hypotheses(table: pd.DataFrame, diffs: pd.DataFrame, summary: Mapping[str, Any],
               reproduction: Mapping[str, Any], integrity: Mapping[str, Any],
               complete: Mapping[str, int]) -> dict[str, Any]:  # fmt: skip
    """H1-H10 and the outcome (docs/e10_walk_forward_protocol.md §7-§9)."""
    f = _per_fold(diffs, table)
    out: dict[str, Any] = {"criteria_version": CRITERIA_VERSION, "split": "validation"}

    def by_fold(test) -> dict[str, bool]:
        return {fold: bool(test(f[fold])) for fold in FOLDS}

    for name, metric in (("H1", "turnover"), ("H2", "cost_drag")):
        flags = by_fold(lambda x, m=metric: x["stats"][m]["mean"] < 0
                        and x["stats"][m]["n_negative"] >= 4)  # fmt: skip
        out[name] = {"parts": {f"fold {k}: mean < 0 and >= 4/5 lower": v for k, v in flags.items()},
                     "verdict": _graded(flags, any(flags.values()))}  # fmt: skip
    classes = {k: v["class"] for k, v in summary["folds"].items()}
    h3 = {f"fold {k} positive": v == "positive" for k, v in classes.items()}
    out["H3"] = {"parts": h3, "verdict": _graded(h3, any(h3.values())), "classes": classes}
    ret = {k: x["stats"]["net_annualised_return"] for k, x in f.items()}
    h4 = {f"fold {k}: mean > 0 and >= 4/5 positive": r["mean"] > 0 and r["n_positive"] >= 4
          for k, r in ret.items()}  # fmt: skip
    out["H4"] = {"parts": h4, "verdict": _graded(h4, sum(r["mean"] > 0 for r in ret.values()) >= 2),
                 "fold_means": {k: r["mean"] for k, r in ret.items()}}  # fmt: skip
    identity_ok = all(x["identity_error"] <= TIE for x in f.values())
    saving = by_fold(lambda x: x["cost_saving"] >= x["gross_loss"])
    h5 = {
        "cost drag = gross - net cumulative in every run": identity_ok,
        **{f"fold {k}: mean cost saving >= mean gross loss": v for k, v in saving.items()},
    }
    out["H5"] = {"parts": h5, "verdict": "supported" if all(h5.values()) else (
        "partially supported" if identity_ok else "not supported"),
        "detail": {k: {"cost_saving": x["cost_saving"], "gross_change": -x["gross_loss"],
                       "net_cumulative_change": x["stats"]["net_cumulative_return"]["mean"]}
                   for k, x in f.items()}}  # fmt: skip
    risk = by_fold(lambda x: x["stats"]["net_volatility"]["median"] <= cc.VOL_MAX
                   and -x["stats"]["net_max_drawdown"]["median"] <= cc.DRAWDOWN_MAX)  # fmt: skip
    out["H6"] = {"parts": {f"fold {k}": v for k, v in risk.items()},
                 "verdict": _graded(risk, any(risk.values())),
                 "downside_risk": "not available from the evaluator (D-076)"}  # fmt: skip
    comp = by_fold(lambda x: x["treatment_medians"]["target_risky_hhi"] <= cc.HHI_MAX
                   and x["treatment_medians"]["target_cash"] <= cc.CASH_MAX
                   and x["treatment_medians"]["share_target_cash_above_95"]
                   <= cc.NEAR_ALL_CASH_MAX)  # fmt: skip
    out["H7"] = {
        "parts": {f"fold {k}": v for k, v in comp.items()},
        "verdict": _graded(comp, any(comp.values())),
        "treatment_medians": {k: x["treatment_medians"] for k, x in f.items()},
    }
    resp = by_fold(
        lambda x: (
            x["ratios_to_control"]["allocation_dispersion"] >= cc.DISPERSION_RATIO
            and x["ratios_to_control"]["share_meaningful_changes"] >= cc.MEANINGFUL_RATIO
            and x["ratios_to_control"]["allocation_stability_dw"] >= cc.DW_RATIO
        )
    )
    out["H8"] = {
        "parts": {f"fold {k}": v for k, v in resp.items()},
        "verdict": _graded(resp, any(resp.values())),
        "ratios_to_control": {k: x["ratios_to_control"] for k, x in f.items()},
    }
    h9 = {
        **{f"{k} reproduces exactly": bool(v.get("identical")) for k, v in reproduction.items()},
        **{f"fold {k} integrity": bool(v.get("verified")) for k, v in integrity.items()},
    }
    out["H9"] = {"parts": h9, "verdict": "supported" if h9 and all(h9.values())
                 else "not supported"}  # fmt: skip

    positives, negatives = summary["positive_folds"], summary["negative_folds"]
    if out["H9"]["verdict"] != "supported" or any(n < len(SEEDS) for n in complete.values()):
        outcome = "Inconclusive"
    elif len(positives) == len(FOLDS) and all(r["mean"] > 0 for r in ret.values()):
        outcome = "Walk-forward confirmation"
    elif len(positives) >= 2 and not negatives:
        outcome = "Partial confirmation"
    elif len(negatives) >= 2:
        outcome = "Deterioration"
    else:
        outcome = "No reliable improvement"
    guards = all(out[k]["verdict"] == "supported" for k in ("H6", "H7", "H8"))
    if outcome == "Walk-forward confirmation" and guards:
        h10 = "supported"
    elif outcome in ("Walk-forward confirmation", "Partial confirmation"):
        h10 = "partially supported"
    else:
        h10 = "not supported"
    out["H10"] = {"verdict": h10, "inputs": {"outcome": outcome, "guard_rails_supported": guards}}
    out["outcome"] = {
        "class": outcome,
        "complete_pairs": dict(complete),
        "positive_folds": positives,
        "negative_folds": negatives,
        "verdicts": {k: out[k]["verdict"] for k in out if k.startswith("H")},
    }
    return out


# --------------------------------------------------------------------------
# Reproduction, integrity, references and the run
# --------------------------------------------------------------------------


def reproduction(table: pd.DataFrame, targets: Mapping[str, Sequence[Path]]) -> dict[str, Any]:
    """H9: the reference fold vs earlier evaluations. Keys ``"<control|treatment>:<name>"``."""
    out = {}
    for key, dirs in targets.items():
        role, name = key.split(":", 1)
        for d in dirs:
            run = _read(Path(d))
            split = run["meta"]["split"]
            ours = _arm(table, REFERENCE_FOLD, split, role).loc[list(SEEDS)]
            ours = ours.drop(columns=["fold", "split", "role"], errors="ignore")
            out[f"{name} ({split})"] = compare_exact(ours, run)
    return out


def integrity(context: Any, runs: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]]) -> dict:
    """Leakage checks: fold inputs (non-reference folds) plus the windows already checked."""
    base = load_project_config(context.config_dir)
    features = load_feature_config(context.config_dir / "features.yaml")
    from adaptive_portfolio.features.pipeline import feature_output_dir

    out = {}
    for fold_id in FOLDS:
        meta = runs[(fold_id, "validation")][0]["meta"]
        fold = _fold_of(meta)
        _, reference = apply_walk_forward_fold(base, fold)
        if reference:
            out[fold_id] = {"reference": True, "dataset_id": meta["data"]["processed_dataset_id"],
                            "verified": fold.splits == base.experiment.splits}  # fmt: skip
            continue
        fold_dir = context.root / walk_forward.FOLD_DATASET_ROOT / meta["data"][
            "processed_dataset_id"]  # fmt: skip
        fold_meta = json.loads((fold_dir / "metadata.json").read_text(encoding="utf-8"))
        parent_id = fold_meta["walk_forward"]["parent_processed_dataset_id"]
        parent_dir = resolve_path(base.data.processed_data_dir, context.root) / parent_id
        feature_dir, _ = feature_output_dir(features, context.root, fold_dir.name, None)
        parent_features, _ = feature_output_dir(features, context.root, parent_id, None)
        report = walk_forward.verify_fold(context.root, fold_dir, feature_dir, parent_dir,
                                          parent_features, base, fold)  # fmt: skip
        report["verified"] = report["verified"] and Path(feature_dir).name == meta["data"][
            "feature_set_id"]  # fmt: skip
        out[fold_id] = {"reference": False, **report}
    return out


def e9_reference(directory: Path | None) -> dict[str, Any]:
    if directory is None:
        return {"available": False}
    if cc.verify_confirmation(Path(directory)):
        raise WalkForwardComparisonError(f"{directory}: the E9 comparison does not verify")
    diffs = pd.read_csv(Path(directory) / "paired_differences.csv")
    part = diffs[(diffs["split"] == "validation") & (diffs["population"] == "primary")]
    hyp = json.loads((Path(directory) / "hypotheses.json").read_text(encoding="utf-8"))
    keep = ("mean", "median", "n_positive", "n_negative", "bootstrap_low", "bootstrap_high",
            "permutation_p", "control_median", "treatment_median")  # fmt: skip
    return {
        "available": True,
        "comparison_id": Path(directory).name,
        "label": "E9 (EXP-022): seeds 47-56, validation 2017-2019; historical, not pooled",
        "outcome": hyp["outcome"]["class"],
        "metrics": {r["metric"]: {k: r[k] for k in keep} for _, r in part.iterrows()},
    }


def run_walk_forward_comparison(
    context: Any,
    folds: Mapping[str, Mapping[str, Sequence[Path]]],
    reproduction_dirs: Mapping[str, Sequence[Path]],
    e9_dir: Path | None = None,
) -> Path:
    """Compute and write the E10 analysis once; returns its directory."""
    if sorted(folds) != sorted(FOLDS):
        raise WalkForwardComparisonError(f"exactly the folds {FOLDS} are required")
    runs, checks = {}, {}
    test_start = str(load_project_config(context.config_dir).experiment.splits.test.start)
    for fold_id, dirs in folds.items():
        for split in ("validation", "train"):
            pair = [_read(Path(d)) for d in dirs[split]]
            found, _, pair_checks = check_pair(pair, test_start)
            if found != fold_id or pair[0]["meta"]["split"] != split:
                raise WalkForwardComparisonError(f"fold {fold_id} {split}: wrong evaluations")
            runs[(fold_id, split)] = pair
            checks[f"{fold_id} {split}"] = pair_checks
        if runs[(fold_id, "validation")][0]["meta"]["checkpoints"] != runs[(fold_id, "train")][0][
                "meta"]["checkpoints"]:  # fmt: skip
            raise WalkForwardComparisonError(f"fold {fold_id}: splits evaluate different runs")
    cores = {_without_fold(p[i]["meta"]["experiment"]) == _without_fold(
        runs[("A", "validation")][i]["meta"]["experiment"])
        for p in runs.values() for i in (0, 1)}  # fmt: skip
    if cores != {True}:
        raise WalkForwardComparisonError("folds differ in more than the fold block and label")
    data_ids = {p[0]["meta"]["data"]["processed_dataset_id"] for k, p in runs.items()}
    if len(data_ids) != len(FOLDS):
        raise WalkForwardComparisonError("each fold must have its own dataset")
    identity = {"schema_version": SCHEMA_VERSION, "criteria": CRITERIA_VERSION,
                "bootstrap": {"resamples": cc.BOOTSTRAP_RESAMPLES, "seed": cc.BOOTSTRAP_SEED},
                "evaluations": {f"{fold}_{split}_{role}": run["meta"]["evaluation_id"]
                                for (fold, split), pair in sorted(runs.items())
                                for role, run in zip(("control", "treatment"), pair,
                                                     strict=True)},
                "reproduction": {k: sorted(Path(d).name for d in v)
                                 for k, v in sorted(reproduction_dirs.items())},
                "e9": Path(e9_dir).name if e9_dir else None}  # fmt: skip
    root = resolve_path(context.experiment.evaluation_output_dir, context.root).parent
    target = root / "walk_forward_comparisons" / cache.short_hash(identity)
    if target.exists():
        raise WalkForwardComparisonError(f"{target} already exists; comparisons are written once")
    table = seed_table(runs)
    diffs = paired_differences(table)
    complete = {}
    for fold in FOLDS:
        both = set(_arm(table, fold, "validation", "control").index) & set(
            _arm(table, fold, "validation", "treatment").index)  # fmt: skip
        complete[fold] = len(both & set(SEEDS))
    summary = fold_summary(diffs)
    repro = reproduction(table, reproduction_dirs)
    checks_integrity = integrity(context, runs)
    hyp = hypotheses(table, diffs, summary, repro, checks_integrity, complete)
    out_dir = context.experiment.output_dir
    training = {f"{fold} {run['meta']['experiment']['label']}": {
        str(s): v for s, v in training_components(context.root, out_dir, run).items()}
        for (fold, split), pair in runs.items() if split == "train" for run in pair}  # fmt: skip
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f"{target.name}.staging-{os.getpid()}"
    staging.mkdir()
    table.to_csv(staging / "seed_table.csv", index=False)
    diffs.to_csv(staging / "paired_differences.csv", index=False)
    cache.write_json({**summary, "pair_checks": checks}, staging / "fold_summary.json")
    cache.write_json(hyp, staging / "hypotheses.json")
    cache.write_json(repro, staging / "reproduction.json")
    cache.write_json(checks_integrity, staging / "integrity.json")
    cache.write_json({fold: cc.baselines(runs[(fold, "validation")][0]) for fold in FOLDS},
                     staging / "baselines.json")  # fmt: skip
    cache.write_json(e9_reference(e9_dir), staging / "e9_reference.json")
    cache.write_json(training, staging / "training_components.json")
    metadata = {"comparison_id": target.name, "kind": "walk_forward", **identity,
                "folds": {fold: _fold_of(runs[(fold, "validation")][0]["meta"]).to_dict()
                          for fold in FOLDS},
                "statistics": "paired seed-level within folds; fold-level synthesis; one "
                              "secondary stratified permutation test (one market history)",
                "files_sha256": {n: cache.file_sha256(staging / n) for n in FILES}}  # fmt: skip
    cache.write_json(metadata, staging / "metadata.json")
    staging.rename(target)
    return target


def verify_walk_forward_comparison(directory: Path) -> list[str]:
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    problems = [f"{n}: hash differs" for n, h in meta["files_sha256"].items()
                if cache.file_sha256(directory / n) != h]  # fmt: skip
    identity = {k: meta[k] for k in ("schema_version", "criteria", "bootstrap", "evaluations",
                                     "reproduction", "e9")}  # fmt: skip
    if cache.short_hash(identity) != directory.name:
        problems.append("identity hash != comparison id")
    return problems
