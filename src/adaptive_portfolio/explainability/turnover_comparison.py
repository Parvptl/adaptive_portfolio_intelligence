"""E7 turnover-aware comparison: kappa = 0 (E7B), 0.0015 (E7T1), 0.0075 (E7T2) (D-091; no ``rl``).

Reads six **verified** evaluations (three arms x training and validation splits). It checks
that the arms differ only in ``reward.turnover_penalty`` (strictly increasing) and the label,
and that E0 reproduces EXP-006 on validation. It writes once, under
``<evaluation root>/../turnover_comparisons/<id>/``:

* ``seed_table.csv``: per split, seed and arm;
* ``paired_differences.csv``: T1 - B, T2 - B and T2 - T1, with mean, SD, median, range, sign
  count, a descriptive t-interval, the effect size d and the median relative difference;
* ``hypotheses.json``: H1-H8 and the outcome class (``docs/e7_turnover_aware.md`` §4);
* ``reproduction.json``: E7B against the E6L validation evaluation (H7);
* ``training_components.json``: reward components of the training episodes, per run;
* ``references.json``: medians of verified reference evaluations.

Descriptive only: the five seeds share one market history.
"""

from __future__ import annotations

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

SCHEMA_VERSION = 1
CRITERIA_VERSION = "D-091 v1 (docs/e7_turnover_aware.md §4, fixed before E7 training)"
FILES = ("seed_table.csv", "paired_differences.csv", "hypotheses.json", "reproduction.json",
         "training_components.json", "references.json")  # fmt: skip
PAIRS = ((1, 0), (2, 0), (2, 1))  # T1 - B, T2 - B, T2 - T1
EXTRA = {"allocation_stability_dw": "allocation_stability_dw",
         "share_target_cash_above_95": "share_target_cash_above_95"}  # fmt: skip


class TurnoverComparisonError(ValueError):
    """Raised when the E7 evaluations cannot be compared as prespecified."""


def _core(experiment: Mapping[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in experiment.items() if k not in ("label", "reward")}
    reward = {k: v for k, v in (experiment.get("reward") or {}).items()
              if k not in ("turnover_penalty", "formula")}  # fmt: skip
    return {**out, "reward": reward}


def kappa_of(meta: Mapping[str, Any]) -> float:
    reward = meta["experiment"].get("reward") or {}
    if reward.get("acceptance") != "fixed":
        raise TurnoverComparisonError(f"{meta['evaluation_id']}: not a fixed-lambda evaluation")
    return float(reward.get("turnover_penalty", 0.0))


def check_arms(runs: Sequence[Mapping[str, Any]]) -> list[float]:
    """Three arms of one split, kappa strictly increasing from 0, identical otherwise."""
    if len(runs) != 3:
        raise TurnoverComparisonError("the comparison needs exactly three arms")
    metas = [r["meta"] for r in runs]
    kappa = [kappa_of(m) for m in metas]
    first = metas[0]
    checks = {
        "kappa strictly increasing from 0": kappa[0] == 0.0 and kappa[0] < kappa[1] < kappa[2],
        "same split": len({m["split"] for m in metas}) == 1,
        "not pipeline checks": not any(m["pipeline_check"] for m in metas),
        "identical except kappa and label": all(_core(m["experiment"]) == _core(
            first["experiment"]) for m in metas),
        "same E0 checkpoints": all(m["e0_checkpoints"] == first["e0_checkpoints"] for m in metas),
        "same data": all(m["data"] == first["data"] for m in metas),
        "same rows boundary": len({m["rows_read_before"] for m in metas}) == 1,
        "distinct labels": len({m["experiment"]["label"] for m in metas}) == 3,
    }  # fmt: skip
    if first["split"] == "validation":
        for run in runs:
            checks[f"{run['meta']['experiment']['label']}: E0 reproduces EXP-006"] = bool(
                run["summary"]["e0_reproduction"].get("reproduced"))  # fmt: skip
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise TurnoverComparisonError("E7 arms are not comparable: " + "; ".join(failed))
    return kappa


def _table(run: Mapping[str, Any]) -> pd.DataFrame:
    table = _arm_table(run, run["meta"]["experiment"]["label"])
    m = run["metrics"]
    label = run["meta"]["experiment"]["label"]
    part = m[(m["experiment"] == label) & (m["profile_set"] == "centre")].set_index("seed")
    for column, name in EXTRA.items():
        if column in part:
            table[name] = part[column]
    return table


def seed_table(splits: Mapping[str, Sequence[Mapping[str, Any]]], kappa: Sequence[float]):
    rows = []
    for split, runs in splits.items():
        for i, run in enumerate(runs):
            for seed, row in _table(run).assign(turnover_penalty=kappa[i]).iterrows():
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


def hypotheses(table: pd.DataFrame, labels: Sequence[str], reproduction: Mapping) -> dict:
    """H1-H8 and the outcome class (docs/e7_turnover_aware.md §4)."""
    b, t1, t2 = _arms(table, "validation", labels)
    bt, t1t, t2t = _arms(table, "train", labels)
    out: dict[str, Any] = {"criteria_version": CRITERIA_VERSION}

    def fewer(x: pd.DataFrame, y: pd.DataFrame, metric: str) -> bool:
        return int((x[metric] < y[metric]).sum()) >= 4

    h1 = {"train turnover T1 < B in >= 4/5": fewer(t1t, bt, "turnover"),
          "train turnover T2 < B in >= 4/5": fewer(t2t, bt, "turnover"),
          "median train turnover T2 <= T1": float(t2t["turnover"].median())
          <= float(t1t["turnover"].median())}  # fmt: skip
    out["H1"] = {
        "parts": h1,
        "verdict": _verdict(h1),
        "train_turnover": {
            lab: a["turnover"].to_dict() for lab, a in zip(labels, (bt, t1t, t2t), strict=True)
        },
    }
    h2 = {
        "validation cost drag T1 < B in >= 4/5": fewer(t1, b, "cost_drag"),
        "validation cost drag T2 < B in >= 4/5": fewer(t2, b, "cost_drag"),
    }
    out["H2"] = {
        "parts": h2,
        "verdict": _verdict(h2),
        "validation_cost_drag": {
            lab: a["cost_drag"].to_dict() for lab, a in zip(labels, (b, t1, t2), strict=True)
        },
    }
    rel = {}
    for name, (v, tr) in {"T1": (t1, t1t), "T2": (t2, t2t)}.items():
        rel[name] = {
            "validation": float((1 - v["turnover"] / b["turnover"]).median()),
            "train": float((1 - tr["turnover"] / bt["turnover"]).median()),
        }
    h3 = {
        "validation turnover T1 < B in >= 4/5": fewer(t1, b, "turnover"),
        "validation turnover T2 < B in >= 4/5": fewer(t2, b, "turnover"),
    }
    for name, r in rel.items():
        h3[f"{name}: validation reduction >= 50% of training reduction"] = (
            r["train"] > 0 and r["validation"] >= 0.5 * r["train"]
        )
    out["H3"] = {
        "parts": h3,
        "verdict": _verdict(h3),
        "median_relative_reduction": rel,
        "validation_turnover": {
            lab: a["turnover"].to_dict() for lab, a in zip(labels, (b, t1, t2), strict=True)
        },
    }
    h4, h5, h6 = {}, {}, {}
    detail = {}
    base_stab = float(b["allocation_stability_dw"].median())
    for name, arm in (("T1", t1), ("T2", t2)):
        sharpe = float((arm["net_sharpe"] - b["net_sharpe"]).median())
        ret = float((arm["net_annualised_return"] - b["net_annualised_return"]).median())
        vol = float((arm["net_volatility"] - b["net_volatility"]).median())
        deeper = float((b["net_max_drawdown"] - arm["net_max_drawdown"]).median())
        stab = float(arm["allocation_stability_dw"].median())
        cash = float(arm["share_target_cash_above_95"].median())
        h4[f"{name}: median Sharpe diff >= 0"] = sharpe >= 0
        h4[f"{name}: median annualised return diff >= 0"] = ret >= 0
        h5[f"{name}: median vol increase <= 0.5 pp"] = vol <= 0.005
        h5[f"{name}: median drawdown deepening <= 2 pp"] = deeper <= 0.02
        h6[f"{name}: median stability D_w >= 25% of B"] = stab >= 0.25 * base_stab
        h6[f"{name}: median near-all-cash share <= 0.05"] = cash <= 0.05
        detail[name] = {
            "sharpe_diff_median": sharpe,
            "return_diff_median": ret,
            "vol_diff_median": vol,
            "drawdown_deepening_median": deeper,
            "stability_dw_median": stab,
            "near_all_cash_share_median": cash,
        }
    out["H4"] = {"parts": h4, "verdict": _verdict(h4), "detail": detail}
    out["H5"] = {
        "parts": h5,
        "verdict": _verdict(h5),
        "detail": detail,
        "downside_risk": "not available from the evaluator (D-076)",
    }
    out["H6"] = {
        "parts": h6,
        "verdict": _verdict(h6),
        "baseline_stability_dw_median": base_stab,
        "detail": detail,
    }
    h7 = {"E7B reproduces E6L exactly": bool(reproduction.get("identical"))}
    out["H7"] = {"parts": h7, "verdict": _verdict(h7), "reproduction": dict(reproduction)}
    seed_sd = float(np.median([a["turnover"].std(ddof=1) for a in (b, t1, t2)]))
    h8_any, h8_detail = False, {}
    for name, arm in (("T1", t1), ("T2", t2)):
        drag = float((b["cost_drag"] - arm["cost_drag"]).median())
        turn = float((b["turnover"] - arm["turnover"]).mean())
        ok = drag >= 0.02 and turn > seed_sd
        h8_detail[name] = {
            "cost_drag_reduction_median": drag,
            "turnover_reduction_mean": turn,
            "passes": ok,
        }
        h8_any = h8_any or ok
    h8 = {"at least one arm: cost-drag reduction >= 2 pp and turnover reduction > seed SD": h8_any}
    out["H8"] = {
        "parts": h8,
        "verdict": _verdict(h8),
        "within_arm_turnover_seed_sd": seed_sd,
        "detail": h8_detail,
    }
    verdict = {k: out[k]["verdict"] for k in out if k.startswith("H")}
    if verdict["H7"] != "supported":
        outcome = "Unresolved: the control does not reproduce E6L"
    elif all(verdict[k] == "supported" for k in ("H1", "H2", "H3", "H4", "H5")):
        outcome = "A: strong support"
    elif (
        verdict["H1"] == "not supported"
        or verdict["H3"] == "not supported"
        or (verdict["H4"] == "not supported" and verdict["H5"] == "not supported")
    ):
        outcome = "C: no support"
    else:
        outcome = "B: partial support"
    out["outcome"] = {"class": outcome, "verdicts": verdict}
    return out


def reproduction(table: pd.DataFrame, labels: Sequence[str], e6_dir: Path | None) -> dict:
    if e6_dir is None:
        return {"checked": False, "identical": False, "reason": "no E6L evaluation given"}
    run = _read(Path(e6_dir))
    label = run["meta"]["experiment"]["label"]
    reward = run["meta"]["experiment"].get("reward") or {}
    if reward.get("fixed_lambda") != 0.0 or run["meta"]["split"] != "validation":
        raise TurnoverComparisonError("the E6 reference must be the E6L (lambda 0) validation run")
    ours = _arms(table, "validation", labels)[0]
    ref = _arm_table(run, label)
    diffs = {
        m: float((ours[m] - ref.loc[ours.index, m]).abs().max())
        for m in ("net_sharpe", "net_volatility", "net_max_drawdown", "turnover")
    }
    return {
        "checked": True,
        "reference": f"{label} ({run['meta']['evaluation_id']})",
        "max_abs_difference": diffs,
        "identical": all(v <= 1e-12 for v in diffs.values()),
    }


def run_turnover_comparison(
    context: Any,
    validation_dirs: Sequence[Path],
    train_dirs: Sequence[Path],
    e6_validation_dir: Path | None = None,
    reference_dirs: Sequence[Path] = (),
) -> Path:
    """Compute and write the E7 comparison once; returns its directory."""
    splits = {"validation": [_read(Path(d)) for d in validation_dirs],
              "train": [_read(Path(d)) for d in train_dirs]}  # fmt: skip
    kappa = {split: check_arms(runs) for split, runs in splits.items()}
    if {r["meta"]["split"] for r in splits["validation"]} != {"validation"} or {
            r["meta"]["split"] for r in splits["train"]} != {"train"}:  # fmt: skip
        raise TurnoverComparisonError("pass the validation and the train evaluations in order")
    if kappa["validation"] != kappa["train"]:
        raise TurnoverComparisonError("kappa values differ between splits")
    for v, t in zip(splits["validation"], splits["train"], strict=True):
        if v["meta"]["checkpoints"] != t["meta"]["checkpoints"]:
            raise TurnoverComparisonError("train and validation evaluate different runs")
    labels = [r["meta"]["experiment"]["label"] for r in splits["validation"]]
    identity = {"schema_version": SCHEMA_VERSION, "criteria": CRITERIA_VERSION,
                "evaluations": {f"{lab}_{split}": runs[i]["meta"]["evaluation_id"]
                                for split, runs in splits.items()
                                for i, lab in enumerate(labels)},
                "e6": Path(e6_validation_dir).name if e6_validation_dir else None,
                "references": sorted(Path(d).name for d in reference_dirs)}  # fmt: skip
    root = resolve_path(context.experiment.evaluation_output_dir, context.root).parent
    target = root / "turnover_comparisons" / cache.short_hash(identity)
    if target.exists():
        raise TurnoverComparisonError(f"{target} already exists; comparisons are written once")
    table = seed_table(splits, kappa["validation"])
    repro = reproduction(table, labels, e6_validation_dir)
    training = {lab: {str(s): v for s, v in training_components(
        context.root, context.experiment.output_dir, splits["train"][i]).items()}
        for i, lab in enumerate(labels)}  # fmt: skip
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f"{target.name}.staging-{os.getpid()}"
    staging.mkdir()
    table.to_csv(staging / "seed_table.csv", index=False)
    paired_differences(table, labels).to_csv(staging / "paired_differences.csv", index=False)
    cache.write_json(hypotheses(table, labels, repro), staging / "hypotheses.json")
    cache.write_json(repro, staging / "reproduction.json")
    cache.write_json({"turnover_penalty": kappa["validation"], **training},
                     staging / "training_components.json")  # fmt: skip
    cache.write_json(references(reference_dirs), staging / "references.json")
    metadata = {"comparison_id": target.name, "kind": "turnover", **identity,
                "statistics": "descriptive; t-intervals are not significance tests",
                "files_sha256": {n: cache.file_sha256(staging / n) for n in FILES}}  # fmt: skip
    cache.write_json(metadata, staging / "metadata.json")
    staging.rename(target)
    return target


def verify_turnover_comparison(directory: Path) -> list[str]:
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    problems = [f"{n}: hash differs" for n, h in meta["files_sha256"].items()
                if cache.file_sha256(directory / n) != h]  # fmt: skip
    identity = {k: meta[k] for k in ("schema_version", "criteria", "evaluations", "e6",
                                     "references")}  # fmt: skip
    if cache.short_hash(identity) != directory.name:
        problems.append("identity hash != comparison id")
    return problems
