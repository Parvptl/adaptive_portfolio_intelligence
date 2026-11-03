"""E8 turnover-penalty refinement: kappa = 0, 0.0015, 0.003, 0.0045 (D-092; no ``rl``).

Reads eight **verified** evaluations (four arms x training and validation splits). It checks
that the arms differ only in ``reward.turnover_penalty`` (strictly increasing from 0) and the
label, and that E0 reproduces EXP-006 on validation. It writes once, under
``<evaluation root>/../turnover_refine_comparisons/<id>/``:

* ``seed_table.csv``: per split, seed and arm, including the E8 responsiveness measures;
* ``paired_differences.csv``: every arm vs B, the refined arms vs T1, and T3 vs T2;
* ``hypotheses.json``: H1-H9 and the outcome class (``docs/e8_turnover_refinement.md`` §5-§6);
* ``reproduction.json``: E8B against E7B and E6L, E8T1 against E7T1, on both splits (H8);
* ``historical.json``: the E7T2 (kappa = 0.0075) evaluations, a labelled prior experiment;
* ``training_components.json``: reward components of the training episodes, per run, and the
  check that the logged penalty equals kappa x the logged traded notional;
* ``references.json``: medians of verified reference evaluations.

Descriptive only: the five seeds share one market history.
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

from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import resolve_path
from adaptive_portfolio.explainability.fixed_risk_comparison import (
    _arm_table,
    _read,
    references,
    training_components,
)
from adaptive_portfolio.explainability.profile_comparison import _stats, _verdict
from adaptive_portfolio.explainability.turnover_comparison import _core, kappa_of

SCHEMA_VERSION = 1
CRITERIA_VERSION = "D-092 v1 (docs/e8_turnover_refinement.md §5-§6, fixed before E8 training)"
FILES = ("seed_table.csv", "paired_differences.csv", "hypotheses.json", "reproduction.json",
         "historical.json", "training_components.json", "references.json")  # fmt: skip
N_ARMS = 4
PAIRS = ((1, 0), (2, 0), (3, 0), (2, 1), (3, 1), (3, 2))
REFINED = (("T2", 2), ("T3", 3))
EXTRA = ("allocation_stability_dw", "share_target_cash_above_95", "allocation_dispersion",
         "share_meaningful_changes")  # fmt: skip
TOLERANCE = 1e-12
# Prespecified thresholds (docs/e8_turnover_refinement.md §5).
DW_RATIO, DISPERSION_RATIO, MEANINGFUL_RATIO = 0.25, 0.50, 0.50
HHI_MAX, CASH_MAX, NEAR_ALL_CASH_MAX = 2 / 3, 0.40, 0.05
VOL_MAX, DRAWDOWN_MAX, COST_DRAG_MIN = 0.005, 0.02, 0.01


class RefineComparisonError(ValueError):
    """Raised when the E8 evaluations cannot be compared as prespecified."""


def check_arms(runs: Sequence[Mapping[str, Any]]) -> list[float]:
    """Four arms of one split, kappa strictly increasing from 0, identical otherwise."""
    if len(runs) != N_ARMS:
        raise RefineComparisonError(f"the comparison needs exactly {N_ARMS} arms")
    metas = [r["meta"] for r in runs]
    kappa = [kappa_of(m) for m in metas]
    first = metas[0]
    checks = {
        "kappa strictly increasing from 0": kappa[0] == 0.0
        and all(a < b for a, b in itertools.pairwise(kappa)),
        "same split": len({m["split"] for m in metas}) == 1,
        "not pipeline checks": not any(m["pipeline_check"] for m in metas),
        "identical except kappa and label": all(_core(m["experiment"]) == _core(
            first["experiment"]) for m in metas),
        "lambda = 0 in every arm": all(
            float((m["experiment"].get("reward") or {}).get("fixed_lambda", -1)) == 0.0
            for m in metas),
        "same E0 checkpoints": all(m["e0_checkpoints"] == first["e0_checkpoints"] for m in metas),
        "same data": all(m["data"] == first["data"] for m in metas),
        "same rows boundary": len({m["rows_read_before"] for m in metas}) == 1,
        "distinct labels": len({m["experiment"]["label"] for m in metas}) == N_ARMS,
    }  # fmt: skip
    if first["split"] == "validation":
        for run in runs:
            checks[f"{run['meta']['experiment']['label']}: E0 reproduces EXP-006"] = bool(
                run["summary"]["e0_reproduction"].get("reproduced"))  # fmt: skip
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise RefineComparisonError("E8 arms are not comparable: " + "; ".join(failed))
    return kappa


def arm_table(run: Mapping[str, Any]) -> pd.DataFrame:
    """Per-seed centre-profile metrics of one evaluation, with the allocation extras."""
    label = run["meta"]["experiment"]["label"]
    table = _arm_table(run, label)
    m = run["metrics"]
    part = m[(m["experiment"] == label) & (m["profile_set"] == "centre")].set_index("seed")
    for column in EXTRA:
        if column in part:
            table[column] = part[column]
    return table


def seed_table(splits: Mapping[str, Sequence[Mapping[str, Any]]], kappa: Sequence[float]):
    rows = []
    for split, runs in splits.items():
        for i, run in enumerate(runs):
            for seed, row in arm_table(run).assign(turnover_penalty=kappa[i]).iterrows():
                rows.append({"split": split, "seed": int(seed), **row.to_dict()})
    return pd.DataFrame(rows)


def _arms(table: pd.DataFrame, split: str, labels: Sequence[str]) -> list[pd.DataFrame]:
    part = table[table["split"] == split]
    return [part[part["arm"] == label].set_index("seed").sort_index() for label in labels]


def paired_differences(table: pd.DataFrame, labels: Sequence[str]) -> pd.DataFrame:
    rows = []
    for split in sorted(table["split"].unique()):
        arms = _arms(table, split, labels)
        for hi, lo in PAIRS:
            seeds = sorted(set(arms[hi].index) & set(arms[lo].index))
            for metric in [c for c in arms[lo].columns
                           if c not in ("arm", "split", "turnover_penalty")]:  # fmt: skip
                a = arms[hi].loc[seeds, metric].to_numpy(float)
                b = arms[lo].loc[seeds, metric].to_numpy(float)
                diff = a - b
                if not len(diff) or not np.isfinite(diff).all():
                    continue
                stats = _stats(diff)
                rel = np.divide(diff, np.abs(b), out=np.full_like(diff, np.nan), where=b != 0)
                rows.append({"split": split, "comparison": f"{labels[hi]} - {labels[lo]}",
                             "metric": metric, **{f"seed_{s}": float(d) for s, d in
                                                  zip(seeds, diff, strict=True)},
                             **stats, "effect_size_d": stats["mean"] / stats["sd"]
                             if stats["sd"] > 0 else float("nan"),
                             "median_relative_difference": float(np.nanmedian(rel))
                             if np.isfinite(rel).any() else float("nan")})  # fmt: skip
    return pd.DataFrame(rows)


def _decreasing(values: Sequence[float]) -> bool:
    return all(a > b for a, b in itertools.pairwise(values))


def _fewer(x: pd.DataFrame, y: pd.DataFrame, metric: str) -> bool:
    return int((x[metric] < y[metric]).sum()) >= 4


def hypotheses(
    table: pd.DataFrame,
    labels: Sequence[str],
    reproduction: Mapping[str, Any],
    penalty_logged: Mapping[str, bool],
) -> dict[str, Any]:
    """H1-H9 and the outcome class (docs/e8_turnover_refinement.md §5-§6)."""
    val = _arms(table, "validation", labels)
    tr = _arms(table, "train", labels)
    b, t1 = val[0], val[1]
    out: dict[str, Any] = {"criteria_version": CRITERIA_VERSION}

    def medians(arms: Sequence[pd.DataFrame], metric: str) -> dict[str, float]:
        return {lab: float(a[metric].median()) for lab, a in zip(labels, arms, strict=True)}

    turn_tr, turn_val = medians(tr, "turnover"), medians(val, "turnover")
    h1 = {"training median turnover strictly decreasing in kappa": _decreasing(
              list(turn_tr.values())),
          "validation median turnover strictly decreasing in kappa": _decreasing(
              list(turn_val.values())),
          "training turnover T2 < T1 in >= 4/5": _fewer(tr[2], tr[1], "turnover"),
          "training turnover T3 < T2 in >= 4/5": _fewer(tr[3], tr[2], "turnover")}  # fmt: skip
    out["H1"] = {"parts": h1, "verdict": _verdict(h1), "median_turnover": {
        "train": turn_tr, "validation": turn_val}}  # fmt: skip

    drag_val = medians(val, "cost_drag")
    h2 = {"validation median cost drag strictly decreasing in kappa": _decreasing(
              list(drag_val.values())),
          "validation cost drag T2 < T1 in >= 4/5": _fewer(val[2], val[1], "cost_drag"),
          "validation cost drag T3 < T2 in >= 4/5": _fewer(val[3], val[2], "cost_drag"),
          "logged penalty = kappa x logged traded notional in every training episode":
              bool(penalty_logged) and all(penalty_logged.values())}  # fmt: skip
    out["H2"] = {"parts": h2, "verdict": _verdict(h2), "median_cost_drag": drag_val,
                 "penalty_logged": dict(penalty_logged)}  # fmt: skip

    h3, rel = {}, {}
    for name, i in REFINED:
        rel[name] = {
            "validation": float((1 - val[i]["turnover"] / b["turnover"]).median()),
            "train": float((1 - tr[i]["turnover"] / tr[0]["turnover"]).median()),
        }
        h3[f"{name}: validation turnover < T1 in >= 4/5"] = _fewer(val[i], t1, "turnover")
        h3[f"{name}: validation cost drag < T1 in >= 4/5"] = _fewer(val[i], t1, "cost_drag")
        h3[f"{name}: validation reduction vs B >= 50% of training reduction"] = (
            rel[name]["train"] > 0 and rel[name]["validation"] >= 0.5 * rel[name]["train"]
        )
    out["H3"] = {"parts": h3, "verdict": _verdict(h3), "median_relative_reduction_vs_B": rel}

    h4, h5, h6, h7, detail = {}, {}, {}, {}, {}
    base = {m: float(b[m].median()) for m in ("allocation_stability_dw", "allocation_dispersion",
                                               "share_meaningful_changes")}  # fmt: skip
    for name, i in REFINED:
        arm = val[i]
        d = {
            "sharpe_diff_vs_T1_median": float((arm["net_sharpe"] - t1["net_sharpe"]).median()),
            "return_diff_vs_T1_median": float(
                (arm["net_annualised_return"] - t1["net_annualised_return"]).median()),
            "vol_diff_vs_T1_median": float((arm["net_volatility"] - t1["net_volatility"]).median()),
            "drawdown_deepening_vs_T1_median": float(
                (t1["net_max_drawdown"] - arm["net_max_drawdown"]).median()),
            **{f"{m}_median": float(arm[m].median()) for m in base},
            **{f"{m}_ratio_to_B": float(arm[m].median()) / v if v > 0 else float("nan")
               for m, v in base.items()},
            "target_risky_hhi_median": float(arm["target_risky_hhi"].median()),
            "target_cash_median": float(arm["target_cash"].median()),
            "near_all_cash_share_median": float(arm["share_target_cash_above_95"].median()),
        }  # fmt: skip
        detail[name] = d
        h4[f"{name}: median Sharpe diff vs T1 >= 0"] = d["sharpe_diff_vs_T1_median"] >= 0
        h4[f"{name}: median annualised return diff vs T1 >= 0"] = d["return_diff_vs_T1_median"] >= 0
        h5[f"{name}: median vol increase vs T1 <= 0.5 pp"] = d["vol_diff_vs_T1_median"] <= VOL_MAX
        h5[f"{name}: median drawdown deepening vs T1 <= 2 pp"] = (
            d["drawdown_deepening_vs_T1_median"] <= DRAWDOWN_MAX
        )
        h6[f"{name}: D_w >= 25% of B"] = (
            d["allocation_stability_dw_median"] >= DW_RATIO * base["allocation_stability_dw"]
        )
        h6[f"{name}: allocation dispersion >= 50% of B"] = (
            d["allocation_dispersion_median"] >= DISPERSION_RATIO * base["allocation_dispersion"]
        )
        h6[f"{name}: share of meaningful changes >= 50% of B"] = (
            d["share_meaningful_changes_median"]
            >= MEANINGFUL_RATIO * base["share_meaningful_changes"]
        )
        h7[f"{name}: risky HHI <= 2/3"] = d["target_risky_hhi_median"] <= HHI_MAX
        h7[f"{name}: target cash <= 0.40"] = d["target_cash_median"] <= CASH_MAX
        h7[f"{name}: near-all-cash share <= 0.05"] = (
            d["near_all_cash_share_median"] <= NEAR_ALL_CASH_MAX
        )
    out["H4"] = {"parts": h4, "verdict": _verdict(h4), "detail": detail}
    out["H5"] = {"parts": h5, "verdict": _verdict(h5), "detail": detail,
                 "downside_risk": "not available from the evaluator (D-076)"}  # fmt: skip
    out["H6"] = {"parts": h6, "verdict": _verdict(h6), "control_medians": base, "detail": detail}
    out["H7"] = {"parts": h7, "verdict": _verdict(h7), "detail": detail}

    h8 = {f"{name} reproduces exactly": bool(r.get("identical"))
          for name, r in reproduction.items()}  # fmt: skip
    out["H8"] = {"parts": h8, "verdict": _verdict(h8) if h8 else "not supported",
                 "reproduction": dict(reproduction)}  # fmt: skip

    seed_sd = float(np.median([a["turnover"].std(ddof=1) for a in val]))
    arm_flags, h9_detail = {}, {}
    for name, i in REFINED:
        arm = val[i]
        drag = float((t1["cost_drag"] - arm["cost_drag"]).median())
        turn = float((t1["turnover"] - arm["turnover"]).mean())
        flags = {
            "cost_efficient": _fewer(arm, t1, "turnover") and _fewer(arm, t1, "cost_drag"),
            "activity_kept": all(v for k, v in {**h6, **h7}.items() if k.startswith(f"{name}:")),
            "performance_kept": all(v for k, v in {**h4, **h5}.items()
                                    if k.startswith(f"{name}:")),
        }  # fmt: skip
        arm_flags[name] = flags
        h9_detail[name] = {"cost_drag_reduction_vs_T1_median": drag,
                           "turnover_reduction_vs_T1_mean": turn,
                           "passes": drag >= COST_DRAG_MIN and turn > seed_sd
                           and flags["activity_kept"]}  # fmt: skip
    h9 = {"at least one refined arm: cost-drag reduction vs T1 >= 1 pp, turnover reduction > "
          "seed SD, and H6 and H7 kept": any(d["passes"] for d in h9_detail.values())}  # fmt: skip
    out["H9"] = {"parts": h9, "verdict": _verdict(h9), "within_arm_turnover_seed_sd": seed_sd,
                 "detail": h9_detail}  # fmt: skip

    verdict = {k: out[k]["verdict"] for k in out if k.startswith("H")}
    balanced = [n for n, f in arm_flags.items() if all(f.values())]
    partial = [
        n
        for n, f in arm_flags.items()
        if f["cost_efficient"] and (f["activity_kept"] or f["performance_kept"])
    ]
    if verdict["H8"] != "supported":
        outcome = "Unresolved: a reproduction failed"
    elif balanced:
        outcome = "A: balanced improvement"
    elif partial:
        outcome = "B: partial improvement"
    else:
        outcome = "C: no reliable improvement"
    out["outcome"] = {"class": outcome, "verdicts": verdict, "arms": arm_flags,
                      "balanced_arms": balanced, "partial_arms": partial}  # fmt: skip
    return out


def compare_exact(ours: pd.DataFrame, run: Mapping[str, Any]) -> dict[str, Any]:
    """Max absolute per-seed difference over every shared numeric metric."""
    ref = arm_table(run)
    seeds = sorted(set(ours.index) & set(ref.index))
    shared = [c for c in ours.columns if c in ref.columns and c not in ("arm", "split",
              "turnover_penalty") and pd.api.types.is_numeric_dtype(ours[c])]  # fmt: skip
    diffs = {c: float((ours.loc[seeds, c] - ref.loc[seeds, c]).abs().max()) for c in shared}
    return {"reference": f"{run['meta']['experiment']['label']} ({run['meta']['evaluation_id']}, "
                         f"{run['meta']['split']})",
            "seeds": seeds, "metrics_compared": len(shared),
            "max_abs_difference": max(diffs.values()) if diffs else float("nan"),
            "per_metric": diffs,
            "identical": len(seeds) == len(ours) and bool(diffs)
            and all(v <= TOLERANCE for v in diffs.values())}  # fmt: skip


def reproduction(
    table: pd.DataFrame, labels: Sequence[str], targets: Mapping[str, Sequence[Path]]
) -> dict[str, Any]:
    """H8: E8B vs E7B and E6L, E8T1 vs E7T1 (``targets`` maps a check name to evaluation dirs).

    Names are ``"<E8 arm index>:<check name>"`` -> directories (one per split).
    """
    out = {}
    for key, dirs in targets.items():
        index, name = key.split(":", 1)
        for d in dirs:
            run = _read(Path(d))
            split = run["meta"]["split"]
            ours = _arms(table, split, labels)[int(index)]
            out[f"{name} ({split})"] = compare_exact(ours, run)
    return out


def historical(dirs: Sequence[Path]) -> dict[str, Any]:
    """The E7T2 evaluations, as a labelled prior experiment (not part of any hypothesis)."""
    out = {}
    for d in dirs:
        run = _read(Path(d))
        table = arm_table(run)
        numeric = table.drop(columns=["arm"]).apply(pd.to_numeric, errors="coerce")
        out[run["meta"]["split"]] = {
            "label": f"{run['meta']['experiment']['label']} (prior experiment EXP-018; "
                     "not trained in E8)",
            "evaluation_id": run["meta"]["evaluation_id"],
            "turnover_penalty": kappa_of(run["meta"]),
            "per_seed": {str(s): row.dropna().to_dict() for s, row in numeric.iterrows()},
            "median": numeric.median().dropna().to_dict(),
            "missing": [c for c in EXTRA if c not in table.columns],
        }  # fmt: skip
    return out


def penalty_check(context_root: Path, output_dir: Path, run: Mapping[str, Any]) -> dict:
    """Per run: does every logged episode penalty equal kappa x the logged traded notional?"""
    root = resolve_path(output_dir, context_root)
    kappa = kappa_of(run["meta"])
    out = {}
    for checkpoint in run["meta"]["checkpoints"]:
        meta = json.loads((root / checkpoint["run_id"] / "metadata.json").read_text("utf-8"))
        episodes = [e for e in meta.get("episode_reward_components", []) if e["steps"] > 0]
        if kappa == 0:
            ok = bool(episodes) and all("turnover_penalty" not in e for e in episodes)
        else:
            ok = bool(episodes) and all(
                abs(e["turnover_penalty"] - kappa * e["traded_notional"]) <= 1e-9 for e in episodes
            )
        out[checkpoint["run_id"]] = ok
    return out


def run_refine_comparison(
    context: Any,
    validation_dirs: Sequence[Path],
    train_dirs: Sequence[Path],
    reproduction_dirs: Mapping[str, Sequence[Path]],
    historical_dirs: Sequence[Path] = (),
    reference_dirs: Sequence[Path] = (),
) -> Path:
    """Compute and write the E8 comparison once; returns its directory."""
    splits = {"validation": [_read(Path(d)) for d in validation_dirs],
              "train": [_read(Path(d)) for d in train_dirs]}  # fmt: skip
    kappa = {split: check_arms(runs) for split, runs in splits.items()}
    if {r["meta"]["split"] for r in splits["validation"]} != {"validation"} or {
            r["meta"]["split"] for r in splits["train"]} != {"train"}:  # fmt: skip
        raise RefineComparisonError("pass the validation and the train evaluations in order")
    if kappa["validation"] != kappa["train"]:
        raise RefineComparisonError("kappa values differ between splits")
    for v, t in zip(splits["validation"], splits["train"], strict=True):
        if v["meta"]["checkpoints"] != t["meta"]["checkpoints"]:
            raise RefineComparisonError("train and validation evaluate different runs")
    labels = [r["meta"]["experiment"]["label"] for r in splits["validation"]]
    identity = {"schema_version": SCHEMA_VERSION, "criteria": CRITERIA_VERSION,
                "evaluations": {f"{lab}_{split}": runs[i]["meta"]["evaluation_id"]
                                for split, runs in splits.items()
                                for i, lab in enumerate(labels)},
                "reproduction": {k: sorted(Path(d).name for d in v)
                                 for k, v in sorted(reproduction_dirs.items())},
                "historical": sorted(Path(d).name for d in historical_dirs),
                "references": sorted(Path(d).name for d in reference_dirs)}  # fmt: skip
    root = resolve_path(context.experiment.evaluation_output_dir, context.root).parent
    target = root / "turnover_refine_comparisons" / cache.short_hash(identity)
    if target.exists():
        raise RefineComparisonError(f"{target} already exists; comparisons are written once")
    table = seed_table(splits, kappa["validation"])
    repro = reproduction(table, labels, reproduction_dirs)
    out_dir = context.experiment.output_dir
    training = {lab: {str(s): v for s, v in training_components(
        context.root, out_dir, splits["train"][i]).items()}
        for i, lab in enumerate(labels)}  # fmt: skip
    logged = {}
    for run in splits["train"]:
        logged.update(penalty_check(context.root, out_dir, run))
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f"{target.name}.staging-{os.getpid()}"
    staging.mkdir()
    table.to_csv(staging / "seed_table.csv", index=False)
    paired_differences(table, labels).to_csv(staging / "paired_differences.csv", index=False)
    cache.write_json(hypotheses(table, labels, repro, logged), staging / "hypotheses.json")
    cache.write_json(repro, staging / "reproduction.json")
    cache.write_json(historical(historical_dirs), staging / "historical.json")
    cache.write_json({"turnover_penalty": kappa["validation"], **training,
                      "penalty_logged": logged}, staging / "training_components.json")  # fmt: skip
    cache.write_json(references(reference_dirs), staging / "references.json")
    metadata = {"comparison_id": target.name, "kind": "turnover_refine", **identity,
                "statistics": "descriptive; t-intervals are not significance tests",
                "files_sha256": {n: cache.file_sha256(staging / n) for n in FILES}}  # fmt: skip
    cache.write_json(metadata, staging / "metadata.json")
    staging.rename(target)
    return target


def verify_refine_comparison(directory: Path) -> list[str]:
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    problems = [f"{n}: hash differs" for n, h in meta["files_sha256"].items()
                if cache.file_sha256(directory / n) != h]  # fmt: skip
    identity = {k: meta[k] for k in ("schema_version", "criteria", "evaluations", "reproduction",
                                     "historical", "references")}  # fmt: skip
    if cache.short_hash(identity) != directory.name:
        problems.append("identity hash != comparison id")
    return problems
