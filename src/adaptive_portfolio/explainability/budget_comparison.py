"""E11 training-budget reduction: 50,176 vs 100,352 timesteps across E10's folds (D-095).

Reads twelve **verified** evaluations (three folds x E11R / E11H x training and validation; both
arms kappa = 0.0015, lambda = 0) and writes once, under
``<evaluation root>/../budget_comparisons/<id>/``:

* ``seed_table.csv`` and ``paired_differences.csv`` (E11H - E11R per fold, split and metric);
* ``gap.csv``: per run, training-split minus validation net Sharpe, and its paired differences;
* ``fold_summary.json``: fold classes, the across-fold synthesis and the secondary test;
* ``hypotheses.json``: H1-H9 and the outcome (``docs/e11_budget_protocol.md`` §5-§7);
* ``reproduction.json``: E11R against E10T1 in every fold and split, exactly (H9);
* ``budgets.json``: the registered and realised timesteps of every run (H9);
* ``integrity.json``: E10's fold-input leakage checks (H9);
* ``baselines.json``, ``e10_reference.json`` and ``training_components.json``.

The statistics are paired seed-level within folds. Seeds share one market history and folds share
training rows.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from adaptive_portfolio.config import load_project_config
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import resolve_path
from adaptive_portfolio.explainability import confirmation_comparison as cc
from adaptive_portfolio.explainability import walk_forward_comparison as wc
from adaptive_portfolio.explainability.fixed_risk_comparison import _read, training_components
from adaptive_portfolio.explainability.turnover_comparison import kappa_of
from adaptive_portfolio.explainability.turnover_refine_comparison import compare_exact

SCHEMA_VERSION = 1
CRITERIA_VERSION = "D-095 v1 (docs/e11_budget_protocol.md §5-§7, fixed before E11 training)"
FILES = (
    "seed_table.csv",
    "paired_differences.csv",
    "gap.csv",
    "fold_summary.json",
    "hypotheses.json",
    "reproduction.json",
    "budgets.json",
    "integrity.json",
    "baselines.json",
    "e10_reference.json",
    "training_components.json",
)
KAPPA = 0.0015
REFERENCE_DONE, HALF_BUDGET = 100_352, 50_176
RETURN_TOLERANCE = -0.005  # H4: mean Δ annualised net return >= -0.5 pp a year
TURNOVER_RATIO = 0.50  # H5: E11H median turnover >= 50% of E11R's


class BudgetComparisonError(ValueError):
    """Raised when the E11 evaluations cannot be analysed as prespecified."""


def _without_budget(experiment: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in experiment.items() if k not in ("label", "total_timesteps")}


def check_pair(runs: Sequence[Mapping[str, Any]], test_start: str) -> tuple[str, dict[str, bool]]:
    """E11R and E11H of one fold and split: identical except the label and the budget."""
    if len(runs) != 2:
        raise BudgetComparisonError("each fold needs exactly two arms (E11R, E11H)")
    metas = [r["meta"] for r in runs]
    folds = [wc._fold_of(m) for m in metas]
    exps = [m["experiment"] for m in metas]
    reference = folds[0].id == wc.REFERENCE_FOLD
    checks = {
        "same fold": folds[0] == folds[1],
        "same split": metas[0]["split"] == metas[1]["split"],
        "not pipeline checks": not any(m["pipeline_check"] for m in metas),
        "identical except label and total_timesteps": _without_budget(exps[0])
        == _without_budget(exps[1]),
        "reference arm uses the D-066 budget": exps[0].get("total_timesteps") is None,
        f"half arm declares {HALF_BUDGET}": exps[1].get("total_timesteps") == HALF_BUDGET,
        f"kappa = {KAPPA} in both arms": all(kappa_of(m) == KAPPA for m in metas),
        "lambda = 0 in both arms": all(
            float((e.get("reward") or {}).get("fixed_lambda", -1)) == 0.0 for e in exps
        ),
        "seeds are 42-46 in both arms": all(tuple(e["seeds"]) == wc.SEEDS for e in exps),
        "same data": metas[1]["data"] == metas[0]["data"],
        "same rows boundary": metas[1]["rows_read_before"] == metas[0]["rows_read_before"],
        "same E0 checkpoints": metas[1]["e0_checkpoints"] == metas[0]["e0_checkpoints"],
        "E0 only in the reference fold": bool(metas[0]["e0_checkpoints"]) == reference,
    }
    for run, fold in zip(runs, folds, strict=True):
        for name, ok in wc.window_checks(run, fold, test_start).items():
            checks[f"{run['meta']['experiment']['label']} {name}"] = ok
    if metas[0]["split"] == "validation" and reference:
        for run in runs:
            checks[f"{run['meta']['experiment']['label']}: E0 reproduces EXP-006"] = bool(
                run["summary"]["e0_reproduction"].get("reproduced")
            )
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise BudgetComparisonError(f"fold {folds[0].id} is not comparable: " + "; ".join(failed))
    return folds[0].id, checks


def budgets(context: Any, runs: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]]) -> dict:
    """Registered and realised timesteps of every training run (from the run directories)."""
    root = resolve_path(context.experiment.output_dir, context.root)
    out: dict[str, Any] = {"runs": {}, "all_match": True}
    for (fold, split), pair in sorted(runs.items()):
        if split != "train":
            continue
        for role, run, expected in zip(
            ("reference", "half"), pair, (REFERENCE_DONE, HALF_BUDGET), strict=True
        ):
            for checkpoint in run["meta"]["checkpoints"]:
                directory = root / checkpoint["run_id"]
                config = json.loads((directory / "run_config.json").read_text(encoding="utf-8"))
                meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
                ok = (
                    meta.get("timesteps_done") == expected
                    and meta.get("status") == "completed"
                    and config["run_kind"] == "full"
                )
                out["runs"][checkpoint["run_id"]] = {
                    "fold": fold,
                    "arm": role,
                    "seed": checkpoint["seed"],
                    "configured": config["total_timesteps"],
                    "timesteps_done": meta.get("timesteps_done"),
                    "episodes": meta.get("episodes_completed"),
                    "expected_done": expected,
                    "commit": (config.get("code") or {}).get("commit"),
                    "ok": ok,
                }
                out["all_match"] = out["all_match"] and ok
    return out


def gap_table(table: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per run: training minus validation net Sharpe; and the paired E11H - E11R statistics."""
    rows, stats = [], []
    for fold in wc.FOLDS:
        series = {}
        for role in ("control", "treatment"):
            tr = wc._arm(table, fold, "train", role)["net_sharpe"]
            va = wc._arm(table, fold, "validation", role)["net_sharpe"]
            gap = (tr - va).loc[list(wc.SEEDS)]
            series[role] = gap
            for seed in wc.SEEDS:
                rows.append(
                    {
                        "fold": fold,
                        "role": role,
                        "seed": seed,
                        "train_sharpe": float(tr.loc[seed]),
                        "validation_sharpe": float(va.loc[seed]),
                        "gap": float(gap.loc[seed]),
                    }
                )
        diff = cc.paired(series["control"], series["treatment"], wc.SEEDS)
        stats.append(
            {
                "fold": fold,
                "metric": "gap",
                **{f"seed_{s}": float(v) for s, v in diff.items()},
                **cc.paired_stats(diff.to_numpy()),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(stats)


def _stats(diffs: pd.DataFrame, fold: str, metric: str, split: str = "validation") -> dict:
    return wc._row(diffs, fold, metric, split)


def _graded(flags: Mapping[str, bool], partial: bool) -> str:
    if flags and all(flags.values()):
        return "supported"
    return "partially supported" if partial else "not supported"


def hypotheses(
    table: pd.DataFrame,
    diffs: pd.DataFrame,
    gaps: pd.DataFrame,
    summary: Mapping[str, Any],
    baselines: Mapping[str, Any],
    reproduction: Mapping[str, Any],
    budget: Mapping[str, Any],
    integrity: Mapping[str, Any],
    complete: Mapping[str, int],
) -> dict:
    """H1-H9 and the outcome (docs/e11_budget_protocol.md §5-§7)."""
    out: dict[str, Any] = {
        "criteria_version": CRITERIA_VERSION,
        "split": "validation",
        "contrast": "E11H (50,176) - E11R (100,352)",
    }
    folds = wc.FOLDS
    sharpe = {f: _stats(diffs, f, "net_sharpe") for f in folds}
    h1 = {f"fold {f}: mean ΔSharpe > 0": sharpe[f]["mean"] > 0 for f in folds}
    out["H1"] = {
        "parts": h1,
        "verdict": _graded(h1, any(h1.values())),
        "fold_means": {f: sharpe[f]["mean"] for f in folds},
    }
    positives, negatives = summary["positive_folds"], summary["negative_folds"]
    out["H2"] = {
        "verdict": "supported"
        if len(positives) >= 2
        else ("partially supported" if len(positives) == 1 else "not supported"),
        "positive_folds": positives,
        "classes": {f: v["class"] for f, v in summary["folds"].items()},
    }
    gap = {f: gaps[gaps["fold"] == f].iloc[0].to_dict() for f in folds}
    attribution = {}
    for f in folds:
        d_train = _stats(diffs, f, "net_sharpe", "train")["mean"]
        d_val = sharpe[f]["mean"]
        attribution[f] = {
            "delta_gap": gap[f]["mean"],
            "delta_train": d_train,
            "delta_validation": d_val,
            "attribution": "genuine"
            if gap[f]["mean"] < 0 and d_val > 0
            else ("training loss only" if gap[f]["mean"] < 0 else "gap not reduced"),
        }
    h3 = {
        f"fold {f}: mean Δgap < 0 and >= 4/5 lower": gap[f]["mean"] < 0
        and gap[f]["n_negative"] >= 4
        for f in folds
    }
    out["H3"] = {"parts": h3, "verdict": _graded(h3, any(h3.values())), "attribution": attribution}
    ret = {f: _stats(diffs, f, "net_annualised_return") for f in folds}
    h4 = {f"fold {f}: mean Δ return >= -0.5 pp": ret[f]["mean"] >= RETURN_TOLERANCE for f in folds}
    out["H4"] = {
        "parts": h4,
        "verdict": _graded(h4, any(h4.values())),
        "fold_means": {f: ret[f]["mean"] for f in folds},
    }
    h5, h6, h7, detail = {}, {}, {}, {}
    for f in folds:
        b = wc._arm(table, f, "validation", "control").loc[list(wc.SEEDS)]
        t = wc._arm(table, f, "validation", "treatment").loc[list(wc.SEEDS)]
        med = {
            m: float(t[m].median())
            for m in ("target_risky_hhi", "target_cash", "share_target_cash_above_95", "turnover")
        }
        ratio = {
            m: float(t[m].median()) / float(b[m].median())
            if float(b[m].median()) > 0
            else float("nan")
            for m in (
                "turnover",
                "allocation_dispersion",
                "share_meaningful_changes",
                "allocation_stability_dw",
            )
        }
        detail[f] = {"treatment_medians": med, "ratios_to_reference": ratio}
        h5[f"fold {f}"] = (
            med["target_risky_hhi"] <= cc.HHI_MAX
            and med["target_cash"] <= cc.CASH_MAX
            and med["share_target_cash_above_95"] <= cc.NEAR_ALL_CASH_MAX
            and ratio["turnover"] >= TURNOVER_RATIO
        )
        h6[f"fold {f}"] = (
            ratio["allocation_dispersion"] >= cc.DISPERSION_RATIO
            and ratio["share_meaningful_changes"] >= cc.MEANINGFUL_RATIO
            and ratio["allocation_stability_dw"] >= cc.DW_RATIO
        )
        h7[f"fold {f}"] = (
            _stats(diffs, f, "net_volatility")["median"] <= cc.VOL_MAX
            and -_stats(diffs, f, "net_max_drawdown")["median"] <= cc.DRAWDOWN_MAX
        )
    for name, flags in (("H5", h5), ("H6", h6), ("H7", h7)):
        out[name] = {
            "parts": flags,
            "verdict": _graded(flags, any(flags.values())),
            "detail": detail,
        }
    h8, gaps_to_baseline = {}, {}
    for f in folds:
        best = max(s["net_sharpe"] for s in baselines[f]["strategies"].values())
        names = baselines[f]["strategies"]
        ref_med = float(wc._arm(table, f, "validation", "control")["net_sharpe"].median())
        half_med = float(wc._arm(table, f, "validation", "treatment")["net_sharpe"].median())
        gaps_to_baseline[f] = {
            "best_baseline_sharpe": best,
            "reference_gap": best - ref_med,
            "half_gap": best - half_med,
            "reference_exceeds_any": any(ref_med >= s["net_sharpe"] for s in names.values()),
            "half_exceeds_any": any(half_med >= s["net_sharpe"] for s in names.values()),
        }
        h8[f"fold {f}: gap to the best baseline smaller for E11H"] = (
            gaps_to_baseline[f]["half_gap"] < gaps_to_baseline[f]["reference_gap"]
        )
    out["H8"] = {"parts": h8, "verdict": _graded(h8, any(h8.values())), "detail": gaps_to_baseline}
    h9 = {
        **{f"{k} reproduces exactly": bool(v.get("identical")) for k, v in reproduction.items()},
        "every run's timesteps_done equals its registered budget": bool(budget["all_match"]),
        **{f"fold {k} integrity": bool(v.get("verified")) for k, v in integrity.items()},
    }
    out["H9"] = {
        "parts": h9,
        "verdict": "supported" if h9 and all(h9.values()) else "not supported",
    }

    genuine = all(attribution[f]["attribution"] == "genuine" for f in folds)
    if out["H9"]["verdict"] != "supported" or any(n < len(wc.SEEDS) for n in complete.values()):
        outcome = "Inconclusive"
    elif len(positives) == len(folds) and out["H4"]["verdict"] == "supported" and genuine:
        outcome = "Generalisation improvement"
    elif len(positives) >= 2 and not negatives:
        outcome = "Partial improvement"
    elif len(negatives) >= 2:
        outcome = "Deterioration"
    else:
        outcome = "No reliable improvement"
    out["outcome"] = {
        "class": outcome,
        "complete_pairs": dict(complete),
        "positive_folds": positives,
        "negative_folds": negatives,
        "gap_attribution_genuine_in_every_fold": genuine,
        "verdicts": {k: out[k]["verdict"] for k in out if k.startswith("H")},
    }
    return out


def reproduction(table: pd.DataFrame, targets: Mapping[str, Sequence[Path]]) -> dict[str, Any]:
    """H9: E11R vs E10T1. ``targets`` maps a fold id to its E10T1 evaluation directories."""
    out = {}
    for fold, dirs in targets.items():
        for d in dirs:
            run = _read(Path(d))
            split = run["meta"]["split"]
            if wc._fold_of(run["meta"]).id != fold or kappa_of(run["meta"]) != KAPPA:
                raise BudgetComparisonError(f"{d}: not the E10T1 evaluation of fold {fold}")
            ours = wc._arm(table, fold, split, "control").loc[list(wc.SEEDS)]
            ours = ours.drop(columns=["fold", "split", "role"], errors="ignore")
            out[f"fold {fold} E11R = E10T1 ({split})"] = compare_exact(ours, run)
    return out


def e10_reference(directory: Path | None) -> dict[str, Any]:
    if directory is None:
        return {"available": False}
    if wc.verify_walk_forward_comparison(Path(directory)):
        raise BudgetComparisonError(f"{directory}: the E10 comparison does not verify")
    summary = json.loads((Path(directory) / "fold_summary.json").read_text(encoding="utf-8"))
    hyp = json.loads((Path(directory) / "hypotheses.json").read_text(encoding="utf-8"))
    return {
        "available": True,
        "comparison_id": Path(directory).name,
        "label": "E10 (EXP-024): kappa 0.0015 - kappa 0 at the D-066 budget; context only",
        "outcome": hyp["outcome"]["class"],
        "fold_mean_delta_sharpe": {f: v["mean"] for f, v in summary["folds"].items()},
    }


def run_budget_comparison(
    context: Any,
    folds: Mapping[str, Mapping[str, Sequence[Path]]],
    reproduction_dirs: Mapping[str, Sequence[Path]],
    e10_dir: Path | None = None,
) -> Path:
    """Compute and write the E11 analysis once; returns its directory."""
    if sorted(folds) != sorted(wc.FOLDS) or sorted(reproduction_dirs) != sorted(wc.FOLDS):
        raise BudgetComparisonError(f"exactly the folds {wc.FOLDS} are required")
    test_start = str(load_project_config(context.config_dir).experiment.splits.test.start)
    runs, checks = {}, {}
    for fold_id, dirs in folds.items():
        for split in ("validation", "train"):
            pair = [_read(Path(d)) for d in dirs[split]]
            found, pair_checks = check_pair(pair, test_start)
            if found != fold_id or pair[0]["meta"]["split"] != split:
                raise BudgetComparisonError(f"fold {fold_id} {split}: wrong evaluations")
            runs[(fold_id, split)] = pair
            checks[f"{fold_id} {split}"] = pair_checks
        for i in (0, 1):
            if (
                runs[(fold_id, "validation")][i]["meta"]["checkpoints"]
                != runs[(fold_id, "train")][i]["meta"]["checkpoints"]
            ):
                raise BudgetComparisonError(f"fold {fold_id}: splits evaluate different runs")
    identity = {
        "schema_version": SCHEMA_VERSION,
        "criteria": CRITERIA_VERSION,
        "bootstrap": {"resamples": cc.BOOTSTRAP_RESAMPLES, "seed": cc.BOOTSTRAP_SEED},
        "evaluations": {
            f"{fold}_{split}_{role}": run["meta"]["evaluation_id"]
            for (fold, split), pair in sorted(runs.items())
            for role, run in zip(("reference", "half"), pair, strict=True)
        },
        "reproduction": {
            k: sorted(Path(d).name for d in v) for k, v in sorted(reproduction_dirs.items())
        },
        "e10": Path(e10_dir).name if e10_dir else None,
    }
    root = resolve_path(context.experiment.evaluation_output_dir, context.root).parent
    target = root / "budget_comparisons" / cache.short_hash(identity)
    if target.exists():
        raise BudgetComparisonError(f"{target} already exists; comparisons are written once")
    table = wc.seed_table(runs)
    diffs = wc.paired_differences(table)
    gaps_per_run, gap_stats = gap_table(table)
    complete = {
        f: len(
            set(wc._arm(table, f, "validation", "control").index)
            & set(wc._arm(table, f, "validation", "treatment").index)
            & set(wc.SEEDS)
        )
        for f in wc.FOLDS
    }
    summary = wc.fold_summary(diffs)
    repro = reproduction(table, reproduction_dirs)
    budget = budgets(context, runs)
    integrity = wc.integrity(context, runs)
    base = {fold: cc.baselines(runs[(fold, "validation")][0]) for fold in wc.FOLDS}
    hyp = hypotheses(table, diffs, gap_stats, summary, base, repro, budget, integrity, complete)
    out_dir = context.experiment.output_dir
    training = {
        f"{fold} {run['meta']['experiment']['label']}": {
            str(s): v for s, v in training_components(context.root, out_dir, run).items()
        }
        for (fold, split), pair in runs.items()
        if split == "train"
        for run in pair
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f"{target.name}.staging-{os.getpid()}"
    staging.mkdir()
    table.to_csv(staging / "seed_table.csv", index=False)
    diffs.to_csv(staging / "paired_differences.csv", index=False)
    pd.concat([gaps_per_run.assign(kind="run"), gap_stats.assign(kind="paired")]).to_csv(
        staging / "gap.csv", index=False
    )
    cache.write_json({**summary, "pair_checks": checks}, staging / "fold_summary.json")
    cache.write_json(hyp, staging / "hypotheses.json")
    cache.write_json(repro, staging / "reproduction.json")
    cache.write_json(budget, staging / "budgets.json")
    cache.write_json(integrity, staging / "integrity.json")
    cache.write_json(base, staging / "baselines.json")
    cache.write_json(e10_reference(e10_dir), staging / "e10_reference.json")
    cache.write_json(training, staging / "training_components.json")
    metadata = {
        "comparison_id": target.name,
        "kind": "budget",
        **identity,
        "budgets": {"reference": f"D-066 default ({REFERENCE_DONE} realised)", "half": HALF_BUDGET},
        "statistics": "paired seed-level within folds; fold-level synthesis; one secondary "
        "stratified permutation test (one market history)",
        "files_sha256": {n: cache.file_sha256(staging / n) for n in FILES},
    }
    cache.write_json(metadata, staging / "metadata.json")
    staging.rename(target)
    return target


def verify_budget_comparison(directory: Path) -> list[str]:
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    problems = [
        f"{n}: hash differs"
        for n, h in meta["files_sha256"].items()
        if cache.file_sha256(directory / n) != h
    ]
    identity = {
        k: meta[k]
        for k in ("schema_version", "criteria", "bootstrap", "evaluations", "reproduction", "e10")
    }
    if cache.short_hash(identity) != directory.name:
        problems.append("identity hash != comparison id")
    return problems
