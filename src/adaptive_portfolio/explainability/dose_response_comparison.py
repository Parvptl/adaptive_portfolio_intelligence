"""E6 dose-response comparison: lambda = 0, 3, 9 (D-090; no ``rl`` extra).

Reads six **verified** evaluations (three arms x training and validation splits). It checks
that the arms differ only in ``reward.fixed_lambda`` and the label, with lambda strictly
increasing, and that E0 reproduces EXP-006 on validation. It writes once, under
``<evaluation root>/../dose_response_comparisons/<id>/``:

* ``seed_table.csv``: per split, seed and arm (E0 and the three lambda arms);
* ``paired_differences.csv``: lambda 3 - 0, 9 - 3 and 9 - 0 per seed and split, with mean, SD,
  median, range, sign count, a descriptive t-interval and the effect size d = mean / SD;
* ``hypotheses.json``: H1-H8 and the outcome class (``docs/e6_dose_response.md`` §5);
* ``training_components.json``: reward components of the training episodes, per run;
* ``reproduction.json``: E6L and E6H against the E5L and E5H evaluations, if given;
* ``references.json``: centre-profile medians of verified reference evaluations.

Descriptive only: the five seeds share one market history.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import resolve_path
from adaptive_portfolio.explainability.fixed_risk_comparison import (
    _arm_table,
    _held,
    _read,
    _without,
    references,
    training_components,
)
from adaptive_portfolio.explainability.profile_analysis import mean_abs_difference
from adaptive_portfolio.explainability.profile_comparison import METRICS, _stats, _verdict

SCHEMA_VERSION = 1
CRITERIA_VERSION = "D-090 v1 (docs/e6_dose_response.md §5, fixed before E6 training)"
FILES = ("seed_table.csv", "paired_differences.csv", "hypotheses.json",
         "training_components.json", "reproduction.json", "references.json")  # fmt: skip
VOL = "net_volatility"
PAIRS = ((1, 0), (2, 1), (2, 0))  # arm indices: lambda 3 - 0, 9 - 3, 9 - 0


class DoseResponseError(ValueError):
    """Raised when the E6 evaluations cannot be compared as prespecified."""


def check_arms(runs: Sequence[Mapping[str, Any]]) -> list[float]:
    """Three arms of one split, fixed lambda strictly increasing, identical otherwise."""
    if len(runs) != 3:
        raise DoseResponseError("the dose response needs exactly three arms")
    metas = [r["meta"] for r in runs]
    lam = []
    for meta in metas:
        reward = meta["experiment"].get("reward") or {}
        if reward.get("acceptance") != "fixed":
            raise DoseResponseError(f"{meta['evaluation_id']}: not a fixed-lambda evaluation")
        lam.append(float(reward["fixed_lambda"]))
    first = metas[0]
    checks = {
        "lambda strictly increasing": lam[0] < lam[1] < lam[2],
        "same split": len({m["split"] for m in metas}) == 1,
        "not pipeline checks": not any(m["pipeline_check"] for m in metas),
        "identical except lambda and label": all(
            _without(m["experiment"]) == _without(first["experiment"]) for m in metas),
        "same E0 checkpoints": all(m["e0_checkpoints"] == first["e0_checkpoints"] for m in metas),
        "same data": all(m["data"] == first["data"] for m in metas),
        "same rows boundary": len({m["rows_read_before"] for m in metas}) == 1,
        "same profile sets": all(m["profile_sets"] == first["profile_sets"] for m in metas),
        "distinct labels": len({m["experiment"]["label"] for m in metas}) == 3,
    }  # fmt: skip
    if first["split"] == "validation":
        for run in runs:
            checks[f"{run['meta']['experiment']['label']}: E0 reproduces EXP-006"] = bool(
                run["summary"]["e0_reproduction"].get("reproduced"))  # fmt: skip
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise DoseResponseError("E6 arms are not comparable: " + "; ".join(failed))
    return lam


def seed_table(splits: Mapping[str, Sequence[Mapping[str, Any]]], lam: Sequence[float]):
    rows = []
    for split, runs in splits.items():
        metrics = runs[0]["metrics"]
        e0 = metrics[metrics["experiment"] == "E0"].set_index("seed")
        e0 = e0[[c for c in METRICS if c in e0]].rename(columns=METRICS).assign(
            arm="E0", fixed_lambda=np.nan)  # fmt: skip
        tables = [e0] + [_arm_table(run, run["meta"]["experiment"]["label"]).assign(
            fixed_lambda=lam[i]) for i, run in enumerate(runs)]  # fmt: skip
        for table in tables:
            for seed, row in table.iterrows():
                rows.append({"split": split, "seed": int(seed), **row.to_dict()})
    return pd.DataFrame(rows)


def _arms(table: pd.DataFrame, split: str, labels: Sequence[str]) -> list[pd.DataFrame]:
    part = table[table["split"] == split]
    return [part[part["arm"] == label].set_index("seed").sort_index() for label in labels]


def paired_differences(table: pd.DataFrame, labels: Sequence[str], lam: Sequence[float]):
    rows = []
    for split in sorted(table["split"].unique()):
        arms = _arms(table, split, labels)
        for hi, lo in PAIRS:
            seeds = sorted(set(arms[hi].index) & set(arms[lo].index))
            for metric in [
                c for c in arms[lo].columns if c not in ("arm", "split", "fixed_lambda")
            ]:
                diff = (arms[hi].loc[seeds, metric] - arms[lo].loc[seeds, metric]).to_numpy(float)
                if not len(diff) or not np.isfinite(diff).all():
                    continue
                stats = _stats(diff)
                effect = stats["mean"] / stats["sd"] if stats["sd"] > 0 else float("nan")
                rows.append({"split": split, "comparison": f"lambda {lam[hi]:g} - {lam[lo]:g}",
                             "metric": metric, **{f"seed_{s}": float(d) for s, d in
                                                  zip(seeds, diff, strict=True)},
                             **stats, "effect_size_d": effect})  # fmt: skip
    return pd.DataFrame(rows)


def hypotheses(table: pd.DataFrame, labels: Sequence[str]) -> dict[str, Any]:
    """H1-H8 and the outcome class (docs/e6_dose_response.md §5)."""
    val = _arms(table, "validation", labels)
    tr = _arms(table, "train", labels)
    v0, v3, v9 = (a[VOL] for a in val)
    t0, t3, t9 = (a[VOL] for a in tr)
    out: dict[str, Any] = {"criteria_version": CRITERIA_VERSION}

    def n(mask: pd.Series) -> int:
        return int(mask.sum())

    medians = [float(x.median()) for x in (v0, v3, v9)]
    h1 = {
        "vol(0) > vol(3) > vol(9) in >= 4/5 validation seeds": n((v0 > v3) & (v3 > v9)) >= 4,
        "validation arm medians strictly decreasing": medians[0] > medians[1] > medians[2],
    }
    out["H1"] = {
        "parts": h1,
        "verdict": _verdict(h1),
        "medians_validation": medians,
        "vol_validation": {lab: a[VOL].to_dict() for lab, a in zip(labels, val, strict=True)},
    }
    between = (v3 < v0) & (v3 > v9)
    fraction = (v0 - v3) / (v0 - v9)
    h2 = {
        "vol(3) strictly between endpoints in >= 4/5": n(between) >= 4,
        "median fraction f in [0.1, 0.9]": 0.1 <= float(fraction.median()) <= 0.9,
    }
    out["H2"] = {
        "parts": h2,
        "verdict": _verdict(h2),
        "fraction": fraction.to_dict(),
        "fraction_median": float(fraction.median()),
    }
    h3 = {}
    for name, (a, b) in {"vol(3) < vol(0)": ((v3, v0), (t3, t0)),
                         "vol(9) < vol(3)": ((v9, v3), (t9, t3)),
                         "vol(9) < vol(0)": ((v9, v0), (t9, t0))}.items():  # fmt: skip
        h3[f"{name} in >= 4/5 on validation"] = n(a[0] < a[1]) >= 4
        h3[f"{name} in >= 4/5 on training"] = n(b[0] < b[1]) >= 4
    out["H3"] = {"parts": h3, "verdict": _verdict(h3)}
    red_v, red_t = 1 - v9 / v0, 1 - t9 / t0
    med_v, med_t = float(red_v.median()), float(red_t.median())
    h4 = {
        "validation median r(0->9) > 0": med_v > 0,
        "validation median >= 50% of training median": med_t > 0 and med_v >= 0.5 * med_t,
        "vol(9) < vol(0) in >= 4/5 validation seeds": n(v9 < v0) >= 4,
    }
    out["H4"] = {"parts": h4, "verdict": _verdict(h4), "reduction_validation": red_v.to_dict(),
                 "reduction_train": red_t.to_dict(), "median_validation": med_v,
                 "median_train": med_t}  # fmt: skip
    held = [_held(a) for a in val]
    cross = {int(s): mean_abs_difference(held[2].loc[[s]].to_numpy(), held[0].loc[[s]].to_numpy())
             for s in held[0].index}  # fmt: skip
    within = [mean_abs_difference(h.loc[[a]].to_numpy(), h.loc[[b]].to_numpy())
              for h in held for a, b in combinations(h.index, 2)]  # fmt: skip
    h5 = {
        "median D_w(0 vs 9) > median within-arm seed D_w": float(np.median(list(cross.values())))
        > float(np.median(within)),
        "target equity lower at 9 than 0 in >= 4/5": n(
            val[2]["target_equity"] < val[0]["target_equity"]
        )
        >= 4,
    }
    out["H5"] = {"parts": h5, "verdict": _verdict(h5), "cross_dw_0_vs_9": cross,
                 "cross_dw_median": float(np.median(list(cross.values()))),
                 "within_arm_seed_dw_median": float(np.median(within)),
                 "target_equity": {lab: a["target_equity"].to_dict()
                                   for lab, a in zip(labels, val, strict=True)}}  # fmt: skip
    turn = [float(a["turnover"].median()) for a in val]
    drag = [float(a["cost_drag"].median()) for a in val]
    h6 = {"median turnover at 3 and 9 <= 1.25 x at 0": all(x <= 1.25 * turn[0] for x in turn[1:]),
          "median cost drag at 3 and 9 <= at 0 + 1 pp": all(x <= drag[0] + 0.01
                                                            for x in drag[1:])}  # fmt: skip
    out["H6"] = {
        "parts": h6,
        "verdict": _verdict(h6),
        "turnover_medians": turn,
        "cost_drag_medians": drag,
    }
    sharpe = [a["net_sharpe"] for a in val]
    d30, d90 = float((sharpe[1] - sharpe[0]).median()), float((sharpe[2] - sharpe[0]).median())
    h7 = {"median Sharpe(3) - Sharpe(0) >= 0": d30 >= 0, "median Sharpe(9) - Sharpe(0) >= 0":
          d90 >= 0}  # fmt: skip
    out["H7"] = {
        "parts": h7,
        "verdict": _verdict(h7),
        "median_sharpe_diff_3_0": d30,
        "median_sharpe_diff_9_0": d90,
    }
    abs_red = v0 - v9
    seed_sd = float(np.median([a[VOL].std(ddof=1) for a in val]))
    h8 = {
        "median validation vol reduction 0->9 >= 0.5 pp": float(abs_red.median()) >= 0.005,
        "median relative reduction >= 10%": med_v >= 0.10,
        "mean paired reduction > median within-arm seed SD": float(abs_red.mean()) > seed_sd,
    }
    out["H8"] = {
        "parts": h8,
        "verdict": _verdict(h8),
        "median_abs_reduction": float(abs_red.median()),
        "mean_abs_reduction": float(abs_red.mean()),
        "within_arm_seed_sd": seed_sd,
    }
    verdict = {k: out[k]["verdict"] for k in out if k.startswith("H")}
    core = all(verdict[k] == "supported" for k in ("H1", "H2", "H3", "H4", "H6"))
    if core and "supported" in (verdict["H5"], verdict["H8"]):
        outcome = "A: strong dose response"
    elif verdict["H1"] == "not supported" and verdict["H4"] == "not supported":
        outcome = "C: no convincing dose response"
    else:
        outcome = "B: weak or partial dose response"
    out["outcome"] = {"class": outcome, "verdicts": verdict}
    return out


def reproduction(table: pd.DataFrame, labels: Sequence[str], e5_dirs: Sequence[Path]) -> dict:
    """E6L/E6H vs E5L/E5H on validation (same settings, expected to reproduce)."""
    if not e5_dirs:
        return {"checked": False, "reason": "no E5 evaluations given"}
    if len(e5_dirs) != 2:
        raise DoseResponseError("pass the E5L and E5H validation evaluations")
    val = _arms(table, "validation", labels)
    out: dict[str, Any] = {"checked": True}
    for e6, directory in ((val[0], e5_dirs[0]), (val[2], e5_dirs[1])):
        run = _read(Path(directory))
        label = run["meta"]["experiment"]["label"]
        e5 = _arm_table(run, label)
        diffs = {m: float((e6[m] - e5.loc[e6.index, m]).abs().max())
                 for m in ("net_sharpe", VOL, "net_max_drawdown", "turnover")}  # fmt: skip
        out[f"{e6['arm'].iloc[0]} vs {label} ({run['meta']['evaluation_id']})"] = {
            "max_abs_difference": diffs,
            "identical": all(v == 0.0 for v in diffs.values()),
        }
    return out


def run_dose_comparison(
    context: Any,
    validation_dirs: Sequence[Path],
    train_dirs: Sequence[Path],
    e5_validation_dirs: Sequence[Path] = (),
    reference_dirs: Sequence[Path] = (),
) -> Path:
    """Compute and write the E6 comparison once; returns its directory."""
    splits = {"validation": [_read(Path(d)) for d in validation_dirs],
              "train": [_read(Path(d)) for d in train_dirs]}  # fmt: skip
    lam = {split: check_arms(runs) for split, runs in splits.items()}
    if {r["meta"]["split"] for r in splits["validation"]} != {"validation"} or {
            r["meta"]["split"] for r in splits["train"]} != {"train"}:  # fmt: skip
        raise DoseResponseError("pass the validation and the train evaluations in order")
    if lam["validation"] != lam["train"]:
        raise DoseResponseError("lambda values differ between splits")
    for v, t in zip(splits["validation"], splits["train"], strict=True):
        if v["meta"]["checkpoints"] != t["meta"]["checkpoints"]:
            raise DoseResponseError("train and validation evaluate different runs")
    labels = [r["meta"]["experiment"]["label"] for r in splits["validation"]]
    identity = {"schema_version": SCHEMA_VERSION, "criteria": CRITERIA_VERSION,
                "evaluations": {f"{lab}_{split}": runs[i]["meta"]["evaluation_id"]
                                for split, runs in splits.items()
                                for i, lab in enumerate(labels)},
                "e5": sorted(Path(d).name for d in e5_validation_dirs),
                "references": sorted(Path(d).name for d in reference_dirs)}  # fmt: skip
    root = resolve_path(context.experiment.evaluation_output_dir, context.root).parent
    target = root / "dose_response_comparisons" / cache.short_hash(identity)
    if target.exists():
        raise DoseResponseError(f"{target} already exists; comparisons are written once")
    table = seed_table(splits, lam["validation"])
    training = {lab: {str(s): v for s, v in training_components(
        context.root, context.experiment.output_dir, splits["train"][i]).items()}
        for i, lab in enumerate(labels)}  # fmt: skip
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f"{target.name}.staging-{os.getpid()}"
    staging.mkdir()
    table.to_csv(staging / "seed_table.csv", index=False)
    paired_differences(table, labels, lam["validation"]).to_csv(
        staging / "paired_differences.csv", index=False)  # fmt: skip
    cache.write_json(hypotheses(table, labels), staging / "hypotheses.json")
    cache.write_json({"lambda": lam["validation"], **training},
                     staging / "training_components.json")  # fmt: skip
    cache.write_json(reproduction(table, labels, e5_validation_dirs),
                     staging / "reproduction.json")  # fmt: skip
    cache.write_json(references(reference_dirs), staging / "references.json")
    metadata = {"comparison_id": target.name, "kind": "dose_response", **identity,
                "statistics": "descriptive; t-intervals are not significance tests",
                "files_sha256": {n: cache.file_sha256(staging / n) for n in FILES}}  # fmt: skip
    cache.write_json(metadata, staging / "metadata.json")
    staging.rename(target)
    return target


def verify_dose_comparison(directory: Path) -> list[str]:
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    problems = [f"{n}: hash differs" for n, h in meta["files_sha256"].items()
                if cache.file_sha256(directory / n) != h]  # fmt: skip
    identity = {k: meta[k] for k in ("schema_version", "criteria", "evaluations", "e5",
                                     "references")}  # fmt: skip
    if cache.short_hash(identity) != directory.name:
        problems.append("identity hash != comparison id")
    return problems
