"""E12 regime observation ablation: 47 vs 56 inputs across E10's folds (D-096; no ``rl``).

Reads twelve **verified** evaluations (three folds x E12F / E12N x training and validation;
both arms kappa = 0.0015, lambda = 0, the D-066 budget) and writes once, under
``<evaluation root>/../ablation_comparisons/<id>/``:

* ``seed_table.csv``, ``paired_differences.csv`` (E12N - E12F) and ``gap.csv``;
* ``fold_summary.json``, ``hypotheses.json`` (H1-H9 and the outcome,
  ``docs/e12_regime_ablation_protocol.md`` §5-§7);
* ``reproduction.json`` (E12F = E10T1 exactly), ``runs.json`` (observation size and realised
  timesteps of every run), ``integrity.json``, ``baselines.json``, ``e10_reference.json`` and
  ``training_components.json``.

Paired seed-level statistics within folds; seeds share one market history and folds share
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
from adaptive_portfolio.explainability import budget_comparison as bc
from adaptive_portfolio.explainability import confirmation_comparison as cc
from adaptive_portfolio.explainability import walk_forward_comparison as wc
from adaptive_portfolio.explainability.fixed_risk_comparison import _read, training_components
from adaptive_portfolio.explainability.turnover_comparison import kappa_of

SCHEMA_VERSION = 1
CRITERIA_VERSION = "D-096 v1 (docs/e12_regime_ablation_protocol.md §5-§7, fixed before training)"
FILES = (
    "seed_table.csv",
    "paired_differences.csv",
    "gap.csv",
    "fold_summary.json",
    "hypotheses.json",
    "reproduction.json",
    "runs.json",
    "integrity.json",
    "baselines.json",
    "e10_reference.json",
    "training_components.json",
)
KAPPA = 0.0015
FULL_SIZE, ABLATED_SIZE = 56, 47
DONE = 100_352
RETURN_TOLERANCE = -0.005  # H3: mean Δ annualised net return >= -0.5 pp a year
TURNOVER_RATIO = 0.50  # H4: E12N median turnover >= 50% of E12F's
COST_TOLERANCE = 0.01  # H4: mean Δ cost drag <= +1.0 pp over the window


class AblationComparisonError(ValueError):
    """Raised when the E12 evaluations cannot be analysed as prespecified."""


def _without_ablation(experiment: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in experiment.items() if k not in ("label", "observation_ablation")}


def check_pair(runs: Sequence[Mapping[str, Any]], test_start: str) -> tuple[str, dict[str, bool]]:
    """E12F and E12N of one fold and split: identical except the label and the ablation."""
    if len(runs) != 2:
        raise AblationComparisonError("each fold needs exactly two arms (E12F, E12N)")
    metas = [r["meta"] for r in runs]
    folds = [wc._fold_of(m) for m in metas]
    exps = [m["experiment"] for m in metas]
    reference = folds[0].id == wc.REFERENCE_FOLD
    checks = {
        "same fold": folds[0] == folds[1],
        "same split": metas[0]["split"] == metas[1]["split"],
        "not pipeline checks": not any(m["pipeline_check"] for m in metas),
        "identical except label and observation_ablation": _without_ablation(exps[0])
        == _without_ablation(exps[1]),
        "control has the full observation": exps[0].get("observation_ablation") is None,
        "treatment removes the regime inputs": exps[1].get("observation_ablation") == "regime",
        "D-066 budget in both arms": all(e.get("total_timesteps") is None for e in exps),
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
        raise AblationComparisonError(f"fold {folds[0].id} is not comparable: " + "; ".join(failed))
    return folds[0].id, checks


def run_records(context: Any, runs: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]]) -> dict:
    """Recorded observation size and realised timesteps of every training run (H9)."""
    root = resolve_path(context.experiment.output_dir, context.root)
    out: dict[str, Any] = {"runs": {}, "all_match": True}
    for (fold, split), pair in sorted(runs.items()):
        if split != "train":
            continue
        for role, run, size in zip(
            ("full", "no_regime"), pair, (FULL_SIZE, ABLATED_SIZE), strict=True
        ):
            for checkpoint in run["meta"]["checkpoints"]:
                directory = root / checkpoint["run_id"]
                config = json.loads((directory / "run_config.json").read_text(encoding="utf-8"))
                meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
                observed = config["environment"]["observation_size"]
                ok = (
                    observed == size
                    and meta.get("timesteps_done") == DONE
                    and meta.get("status") == "completed"
                    and config["run_kind"] == "full"
                )
                out["runs"][checkpoint["run_id"]] = {
                    "fold": fold,
                    "arm": role,
                    "seed": checkpoint["seed"],
                    "observation_size": observed,
                    "expected_size": size,
                    "timesteps_done": meta.get("timesteps_done"),
                    "commit": (config.get("code") or {}).get("commit"),
                    "ok": ok,
                }
                out["all_match"] = out["all_match"] and ok
    return out


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
    records: Mapping[str, Any],
    integrity: Mapping[str, Any],
    complete: Mapping[str, int],
) -> dict:
    """H1-H9 and the outcome (docs/e12_regime_ablation_protocol.md §5-§7)."""
    out: dict[str, Any] = {
        "criteria_version": CRITERIA_VERSION,
        "split": "validation",
        "contrast": "E12N (no regime inputs) - E12F (full observation)",
    }
    folds = wc.FOLDS

    def stat(f: str, m: str, split: str = "validation") -> dict:
        return wc._row(diffs, f, m, split)

    sharpe = {f: stat(f, "net_sharpe") for f in folds}
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
    ret = {f: stat(f, "net_annualised_return") for f in folds}
    h3 = {f"fold {f}: mean Δ return >= -0.5 pp": ret[f]["mean"] >= RETURN_TOLERANCE for f in folds}
    out["H3"] = {
        "parts": h3,
        "verdict": _graded(h3, any(h3.values())),
        "fold_means": {f: ret[f]["mean"] for f in folds},
    }
    h4, h5, h6, h7, detail = {}, {}, {}, {}, {}
    for f in folds:
        b = wc._arm(table, f, "validation", "control").loc[list(wc.SEEDS)]
        t = wc._arm(table, f, "validation", "treatment").loc[list(wc.SEEDS)]
        med = {
            m: float(t[m].median())
            for m in ("target_risky_hhi", "target_cash", "share_target_cash_above_95")
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
        cost = stat(f, "cost_drag")["mean"]
        detail[f] = {
            "treatment_medians": med,
            "ratios_to_control": ratio,
            "mean_delta_cost_drag": cost,
        }
        h4[f"fold {f}"] = ratio["turnover"] >= TURNOVER_RATIO and cost <= COST_TOLERANCE
        h5[f"fold {f}"] = (
            stat(f, "net_volatility")["median"] <= cc.VOL_MAX
            and -stat(f, "net_max_drawdown")["median"] <= cc.DRAWDOWN_MAX
        )
        h6[f"fold {f}"] = (
            med["target_risky_hhi"] <= cc.HHI_MAX
            and med["target_cash"] <= cc.CASH_MAX
            and med["share_target_cash_above_95"] <= cc.NEAR_ALL_CASH_MAX
        )
        h7[f"fold {f}"] = (
            ratio["allocation_dispersion"] >= cc.DISPERSION_RATIO
            and ratio["share_meaningful_changes"] >= cc.MEANINGFUL_RATIO
            and ratio["allocation_stability_dw"] >= cc.DW_RATIO
        )
    for name, flags in (("H4", h4), ("H5", h5), ("H6", h6), ("H7", h7)):
        out[name] = {
            "parts": flags,
            "verdict": _graded(flags, any(flags.values())),
            "detail": detail,
        }
    h8, to_baseline = {}, {}
    for f in folds:
        strategies = baselines[f]["strategies"]
        best = max(s["net_sharpe"] for s in strategies.values())
        meds = {
            role: float(wc._arm(table, f, "validation", role)["net_sharpe"].median())
            for role in ("control", "treatment")
        }
        seeds_above = {
            role: int(
                (
                    wc._arm(table, f, "validation", role)["net_sharpe"]
                    >= min(s["net_sharpe"] for s in strategies.values())
                ).sum()
            )
            for role in meds
        }
        to_baseline[f] = {
            "best_baseline_sharpe": best,
            "control_gap": best - meds["control"],
            "treatment_gap": best - meds["treatment"],
            "control_median_exceeds_any": any(
                meds["control"] >= s["net_sharpe"] for s in strategies.values()
            ),
            "treatment_median_exceeds_any": any(
                meds["treatment"] >= s["net_sharpe"] for s in strategies.values()
            ),
            "seeds_at_or_above_weakest_baseline": seeds_above,
        }
        h8[f"fold {f}: gap to the best baseline smaller for E12N"] = (
            to_baseline[f]["treatment_gap"] < to_baseline[f]["control_gap"]
        )
    out["H8"] = {"parts": h8, "verdict": _graded(h8, any(h8.values())), "detail": to_baseline}
    attribution = {}
    for f in folds:
        g = gaps[gaps["fold"] == f].iloc[0]
        d_val = sharpe[f]["mean"]
        attribution[f] = {
            "delta_gap": float(g["mean"]),
            "delta_train": stat(f, "net_sharpe", "train")["mean"],
            "delta_validation": d_val,
            "attribution": "genuine"
            if g["mean"] < 0 and d_val > 0
            else ("training loss only" if g["mean"] < 0 else "gap not reduced"),
        }
    out["gap"] = {"attribution": attribution, "note": "reported, never decisive (protocol §5)"}
    h9 = {
        **{f"{k} reproduces exactly": bool(v.get("identical")) for k, v in reproduction.items()},
        "every run has its registered observation size and realised 100,352 timesteps": bool(
            records["all_match"]
        ),
        **{f"fold {k} integrity": bool(v.get("verified")) for k, v in integrity.items()},
    }
    out["H9"] = {
        "parts": h9,
        "verdict": "supported" if h9 and all(h9.values()) else "not supported",
    }
    if out["H9"]["verdict"] != "supported" or any(n < len(wc.SEEDS) for n in complete.values()):
        outcome = "Inconclusive"
    elif len(positives) == len(folds) and out["H3"]["verdict"] == "supported":
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
        "verdicts": {k: out[k]["verdict"] for k in out if k.startswith("H")},
    }
    return out


def run_ablation_comparison(
    context: Any,
    folds: Mapping[str, Mapping[str, Sequence[Path]]],
    reproduction_dirs: Mapping[str, Sequence[Path]],
    e10_dir: Path | None = None,
) -> Path:
    """Compute and write the E12 analysis once; returns its directory."""
    if sorted(folds) != sorted(wc.FOLDS) or sorted(reproduction_dirs) != sorted(wc.FOLDS):
        raise AblationComparisonError(f"exactly the folds {wc.FOLDS} are required")
    test_start = str(load_project_config(context.config_dir).experiment.splits.test.start)
    runs, checks = {}, {}
    for fold_id, dirs in folds.items():
        for split in ("validation", "train"):
            pair = [_read(Path(d)) for d in dirs[split]]
            found, pair_checks = check_pair(pair, test_start)
            if found != fold_id or pair[0]["meta"]["split"] != split:
                raise AblationComparisonError(f"fold {fold_id} {split}: wrong evaluations")
            runs[(fold_id, split)] = pair
            checks[f"{fold_id} {split}"] = pair_checks
        for i in (0, 1):
            if (
                runs[(fold_id, "validation")][i]["meta"]["checkpoints"]
                != runs[(fold_id, "train")][i]["meta"]["checkpoints"]
            ):
                raise AblationComparisonError(f"fold {fold_id}: splits evaluate different runs")
    identity = {
        "schema_version": SCHEMA_VERSION,
        "criteria": CRITERIA_VERSION,
        "bootstrap": {"resamples": cc.BOOTSTRAP_RESAMPLES, "seed": cc.BOOTSTRAP_SEED},
        "evaluations": {
            f"{fold}_{split}_{role}": run["meta"]["evaluation_id"]
            for (fold, split), pair in sorted(runs.items())
            for role, run in zip(("full", "no_regime"), pair, strict=True)
        },
        "reproduction": {
            k: sorted(Path(d).name for d in v) for k, v in sorted(reproduction_dirs.items())
        },
        "e10": Path(e10_dir).name if e10_dir else None,
    }
    root = resolve_path(context.experiment.evaluation_output_dir, context.root).parent
    target = root / "ablation_comparisons" / cache.short_hash(identity)
    if target.exists():
        raise AblationComparisonError(f"{target} already exists; comparisons are written once")
    table = wc.seed_table(runs)
    diffs = wc.paired_differences(table)
    gaps_per_run, gap_stats = bc.gap_table(table)
    complete = {
        f: len(
            set(wc._arm(table, f, "validation", "control").index)
            & set(wc._arm(table, f, "validation", "treatment").index)
            & set(wc.SEEDS)
        )
        for f in wc.FOLDS
    }
    summary = wc.fold_summary(diffs)
    try:
        repro = bc.reproduction(table, reproduction_dirs)
    except bc.BudgetComparisonError as exc:
        raise AblationComparisonError(str(exc)) from None
    repro = {k.replace("E11R", "E12F"): v for k, v in repro.items()}
    records = run_records(context, runs)
    integrity = wc.integrity(context, runs)
    base = {fold: cc.baselines(runs[(fold, "validation")][0]) for fold in wc.FOLDS}
    hyp = hypotheses(table, diffs, gap_stats, summary, base, repro, records, integrity, complete)
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
    cache.write_json(records, staging / "runs.json")
    cache.write_json(integrity, staging / "integrity.json")
    cache.write_json(base, staging / "baselines.json")
    cache.write_json(bc.e10_reference(e10_dir), staging / "e10_reference.json")
    cache.write_json(training, staging / "training_components.json")
    metadata = {
        "comparison_id": target.name,
        "kind": "ablation",
        **identity,
        "removed_inputs": "the 9 regime one-hot inputs (D-062 positions 35-43)",
        "observation_sizes": {"full": FULL_SIZE, "no_regime": ABLATED_SIZE},
        "statistics": "paired seed-level within folds; fold-level synthesis; one secondary "
        "stratified permutation test (one market history)",
        "files_sha256": {n: cache.file_sha256(staging / n) for n in FILES},
    }
    cache.write_json(metadata, staging / "metadata.json")
    staging.rename(target)
    return target


def verify_ablation_comparison(directory: Path) -> list[str]:
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
