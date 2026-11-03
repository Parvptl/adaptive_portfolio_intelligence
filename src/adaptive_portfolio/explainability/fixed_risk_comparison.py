"""E5 fixed risk-aversion comparison: E5H (lambda = 9) vs E5L (lambda = 0) (D-089; no ``rl``).

Reads four **verified** evaluations (each arm on the training and validation splits) and the
arms' training records. It checks that the arms differ only in ``reward.fixed_lambda`` and the
label, and that E0 reproduces EXP-006 on validation. It writes once, under
``<evaluation root>/../fixed_risk_comparisons/<id>/``:

* ``seed_table.csv``: per split and seed, E0, E5L and E5H metrics;
* ``paired_differences.csv``: E5H - E5L per seed, with mean, SD, median, range, sign count and a
  descriptive t-interval;
* ``hypotheses.json``: H1-H8 and the outcome class, exactly as prespecified in
  ``docs/e5_fixed_risk_aversion.md`` §4;
* ``training_components.json``: per-run reward components of the training episodes;
* ``references.json``: medians of verified reference evaluations (E1, E4), if given.

Descriptive statistics only: the five seeds share one market history.
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
from adaptive_portfolio.explainability.profile_analysis import mean_abs_difference
from adaptive_portfolio.explainability.profile_comparison import METRICS, _stats, _verdict

SCHEMA_VERSION = 1
CRITERIA_VERSION = "D-089 v1 (docs/e5_fixed_risk_aversion.md §4, fixed before E5 training)"
FILES = ("seed_table.csv", "paired_differences.csv", "hypotheses.json",
         "training_components.json", "references.json")  # fmt: skip
VOL = "net_volatility"
LAST_EPISODES = 50


class FixedRiskComparisonError(ValueError):
    """Raised when the E5 evaluations cannot be compared as prespecified."""


def _read(directory: Path) -> dict[str, Any]:
    from adaptive_portfolio.agents.profile_experiment import verify_profile_evaluation

    problems = verify_profile_evaluation(directory)
    if problems:
        raise FixedRiskComparisonError(f"{directory} does not verify: {problems}")
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    return {"dir": Path(directory), "meta": meta, "summary": summary,
            "metrics": pd.read_csv(directory / "episode_metrics.csv")}  # fmt: skip


def _without(experiment: Mapping[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in experiment.items() if k not in ("label", "reward")}
    reward = dict(experiment.get("reward") or {})
    reward.pop("fixed_lambda", None)
    return {**out, "reward": reward}


def check_arms(low: Mapping[str, Any], high: Mapping[str, Any]) -> dict[str, float]:
    """The pair must be one split, fixed-lambda arms differing only in lambda and label."""
    lm, hm = low["meta"], high["meta"]
    lam = {}
    for name, meta in (("low", lm), ("high", hm)):
        reward = meta["experiment"].get("reward") or {}
        if reward.get("acceptance") != "fixed":
            raise FixedRiskComparisonError(f"{name}: not a fixed-lambda (E5) evaluation")
        lam[name] = float(reward["fixed_lambda"])
    checks = {
        "same split": lm["split"] == hm["split"],
        "not pipeline checks": not lm["pipeline_check"] and not hm["pipeline_check"],
        "low lambda < high lambda": lam["low"] < lam["high"],
        "experiments identical except lambda and label": _without(lm["experiment"])
        == _without(hm["experiment"]),
        "same E0 checkpoints": lm["e0_checkpoints"] == hm["e0_checkpoints"],
        "same data": lm["data"] == hm["data"],
        "same rows boundary": lm["rows_read_before"] == hm["rows_read_before"],
        "same profile sets": lm["profile_sets"] == hm["profile_sets"],
    }  # fmt: skip
    if lm["split"] == "validation":
        for name, run in (("low", low), ("high", high)):
            checks[f"{name}: E0 reproduces EXP-006"] = bool(
                run["summary"]["e0_reproduction"].get("reproduced"))  # fmt: skip
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise FixedRiskComparisonError("E5 arms are not comparable: " + "; ".join(failed))
    return lam


def _arm_table(run: Mapping[str, Any], arm: str) -> pd.DataFrame:
    m = run["metrics"]
    label = run["meta"]["experiment"]["label"]
    part = m[(m["experiment"] == label) & (m["profile_set"] == "centre")]
    if part.empty:
        raise FixedRiskComparisonError(f"no centre-profile episodes for {label}")
    keep = {**METRICS, "target_cash": "target_cash", "e4_realised_variance": "realised_variance",
            "e4_risk_penalty": "risk_penalty", "e4_reward": "objective",
            "e4_reward_base": "objective_base",
            **{c: c for c in part.columns if c.startswith("mean_held_")}}  # fmt: skip
    table = part.set_index("seed")[[c for c in keep if c in part]].rename(columns=keep)
    return table.assign(arm=arm)


def seed_table(pairs: Mapping[str, tuple[Mapping, Mapping]]) -> pd.DataFrame:
    rows = []
    for split, (low, high) in pairs.items():
        e0 = low["metrics"][low["metrics"]["experiment"] == "E0"].set_index("seed")
        e0 = e0[[c for c in METRICS if c in e0]].rename(columns=METRICS).assign(arm="E0")
        for table in (e0, _arm_table(low, "E5L"), _arm_table(high, "E5H")):
            for seed, row in table.iterrows():
                rows.append({"split": split, "seed": int(seed), **row.to_dict()})
    return pd.DataFrame(rows)


def paired_differences(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for split, part in table.groupby("split"):
        low = part[part["arm"] == "E5L"].set_index("seed")
        high = part[part["arm"] == "E5H"].set_index("seed")
        seeds = sorted(set(low.index) & set(high.index))
        for metric in [c for c in low.columns if c not in ("arm", "split")]:
            diff = (high.loc[seeds, metric] - low.loc[seeds, metric]).to_numpy(float)
            if len(diff) and np.isfinite(diff).all():
                rows.append({"split": split, "comparison": "E5H - E5L", "metric": metric,
                             **{f"seed_{s}": float(d) for s, d in zip(seeds, diff, strict=True)},
                             **_stats(diff)})  # fmt: skip
    return pd.DataFrame(rows)


def _held(frame: pd.DataFrame) -> pd.DataFrame:
    """Mean held weights per asset and cash (``mean_held_<TICKER>``, ``mean_held_CASH``)."""
    columns = [c for c in frame.columns if c.startswith("mean_held_") and c != "mean_held_cash"]
    return frame[columns].dropna(axis=1, how="all")


def training_components(context_root: Path, output_dir: Path, run: Mapping[str, Any]) -> dict:
    root = resolve_path(output_dir, context_root)
    out = {}
    for checkpoint in run["meta"]["checkpoints"]:
        meta = json.loads((root / checkpoint["run_id"] / "metadata.json").read_text("utf-8"))
        episodes = [e for e in meta.get("episode_reward_components", []) if e["steps"] > 0]
        last = episodes[-LAST_EPISODES:]
        out[int(checkpoint["seed"])] = {
            "run_id": checkpoint["run_id"], "episodes": len(episodes),
            "lambda": sorted({e["lambda"] for e in episodes}),
            "last50_realised_variance": float(np.mean([e["realised_variance"] for e in last])),
            "last50_reward_base": float(np.mean([e["reward_base"] for e in last])),
            "last50_risk_penalty": float(np.mean([e["risk_penalty"] for e in last])),
            "last50_reward": float(np.mean([e["reward"] for e in last])),
            "first50_realised_variance": float(np.mean(
                [e["realised_variance"] for e in episodes[:LAST_EPISODES]])),
        }  # fmt: skip
    return out


def hypotheses(table: pd.DataFrame, training: Mapping[str, Mapping[int, dict]]) -> dict:
    """H1-H8 and the outcome class (docs/e5_fixed_risk_aversion.md §4)."""

    def arms(split: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        part = table[table["split"] == split]
        return (part[part["arm"] == "E5L"].set_index("seed").sort_index(),
                part[part["arm"] == "E5H"].set_index("seed").sort_index())  # fmt: skip

    low, high = arms("validation")
    low_t, high_t = arms("train")
    out: dict[str, Any] = {"criteria_version": CRITERIA_VERSION}
    reduction = 1 - high[VOL] / low[VOL]
    reduction_t = 1 - high_t[VOL] / low_t[VOL]
    h1 = {
        "vol E5H < E5L in >= 4/5 seeds": int((high[VOL] < low[VOL]).sum()) >= 4,
        "median relative reduction >= 10%": float(reduction.median()) >= 0.10,
    }
    out["H1"] = {"parts": h1, "verdict": _verdict(h1), "vol_low": low[VOL].to_dict(),
                 "vol_high": high[VOL].to_dict(), "relative_reduction": reduction.to_dict(),
                 "median_relative_reduction": float(reduction.median())}  # fmt: skip
    cross = {
        int(s): mean_abs_difference(_held(high).loc[[s]].to_numpy(), _held(low).loc[[s]].to_numpy())
        for s in low.index
    }
    within = [mean_abs_difference(_held(arm).loc[[a]].to_numpy(), _held(arm).loc[[b]].to_numpy())
              for arm in (low, high) for a, b in combinations(arm.index, 2)]  # fmt: skip
    h2 = {
        "median cross-arm D_w > median within-arm seed D_w": float(np.median(list(cross.values())))
        > float(np.median(within))
    }
    out["H2"] = {"parts": h2, "verdict": _verdict(h2), "cross_arm_dw": cross,
                 "cross_arm_dw_median": float(np.median(list(cross.values()))),
                 "within_arm_seed_dw_median": float(np.median(within))}  # fmt: skip
    safe_l, safe_h = low["target_cash"] + low["target_bonds"], high["target_cash"] + high[
        "target_bonds"]  # fmt: skip
    h3 = {
        "target equity E5H < E5L in >= 4/5": int(
            (high["target_equity"] < low["target_equity"]).sum()
        )
        >= 4,
        "target cash+bonds E5H > E5L in >= 4/5": int((safe_h > safe_l).sum()) >= 4,
    }
    out["H3"] = {
        "parts": h3,
        "verdict": _verdict(h3),
        "equity_low": low["target_equity"].to_dict(),
        "equity_high": high["target_equity"].to_dict(),
        "cash_plus_bonds_low": safe_l.to_dict(),
        "cash_plus_bonds_high": safe_h.to_dict(),
    }
    h4 = {"median turnover E5H <= 1.25 x E5L": float(high["turnover"].median())
          <= 1.25 * float(low["turnover"].median()),
          "median cost drag E5H <= E5L + 1 pp": float(high["cost_drag"].median())
          <= float(low["cost_drag"].median()) + 0.01}  # fmt: skip
    out["H4"] = {"parts": h4, "verdict": _verdict(h4), "turnover_low": low["turnover"].to_dict(),
                 "turnover_high": high["turnover"].to_dict(),
                 "cost_drag_low": low["cost_drag"].to_dict(),
                 "cost_drag_high": high["cost_drag"].to_dict()}  # fmt: skip
    rv_l = {s: v["last50_realised_variance"] for s, v in training["low"].items()}
    rv_h = {s: v["last50_realised_variance"] for s, v in training["high"].items()}
    ratio = {s: rv_h[s] / rv_l[s] for s in rv_l if s in rv_h}
    h5 = {
        "last-50 RV E5H < E5L in >= 4/5": sum(rv_h[s] < rv_l[s] for s in ratio) >= 4,
        "median RV ratio <= 0.9": float(np.median(list(ratio.values()))) <= 0.9,
    }
    out["H5"] = {
        "parts": h5,
        "verdict": _verdict(h5),
        "rv_low": rv_l,
        "rv_high": rv_h,
        "rv_ratio": ratio,
    }
    h6 = {
        "vol E5H < E5L in >= 4/5 on training": int((high_t[VOL] < low_t[VOL]).sum()) >= 4,
        "vol E5H < E5L in >= 4/5 on validation": int((high[VOL] < low[VOL]).sum()) >= 4,
    }
    out["H6"] = {
        "parts": h6,
        "verdict": _verdict(h6),
        "relative_reduction_train": reduction_t.to_dict(),
    }
    med_v, med_t = float(reduction.median()), float(reduction_t.median())
    h7 = {
        "validation median reduction > 0": med_v > 0,
        "validation median >= 50% of training median": med_t > 0 and med_v >= 0.5 * med_t,
    }
    out["H7"] = {
        "parts": h7,
        "verdict": _verdict(h7),
        "median_reduction_validation": med_v,
        "median_reduction_train": med_t,
    }
    mdd = {"|MDD| E5H < E5L in >= 4/5": int((high["net_max_drawdown"].abs()
                                              < low["net_max_drawdown"].abs()).sum()) >= 4,
           "H3 equity part holds": h3["target equity E5H < E5L in >= 4/5"]}  # fmt: skip
    out["H8"] = {
        "parts": mdd,
        "verdict": _verdict(mdd),
        "mdd_low": low["net_max_drawdown"].to_dict(),
        "mdd_high": high["net_max_drawdown"].to_dict(),
    }
    supported = {k: out[k]["verdict"] for k in ("H1", "H2", "H6")}
    if all(v == "supported" for v in supported.values()):
        outcome = "A: risk-aversion sensitivity demonstrated"
    elif out["H1"]["verdict"] == "not supported" and out["H2"]["verdict"] == "not supported":
        outcome = "C: no meaningful risk sensitivity"
    else:
        outcome = "B: reward sensitivity exists but is weak or partial"
    out["outcome"] = {"class": outcome, "basis": supported}
    return out


def references(directories: Sequence[Path]) -> dict[str, Any]:
    """Median centre-profile validation metrics of verified reference evaluations (E1, E4)."""
    out = {}
    for directory in directories:
        run = _read(Path(directory))
        m = run["metrics"]
        for exp, part in m[m["profile_set"] == "centre"].groupby("experiment"):
            table = part.set_index("seed")[[c for c in METRICS if c in part]].rename(
                columns=METRICS)  # fmt: skip
            out[f"{exp} ({run['meta']['evaluation_id']}, {run['meta']['split']})"] = {
                k: float(v) for k, v in table.median().items()
            }
    return out


def run_fixed_comparison(
    context: Any,
    low_validation: Path,
    high_validation: Path,
    low_train: Path,
    high_train: Path,
    reference_dirs: Sequence[Path] = (),
) -> Path:
    """Compute and write the E5 comparison once; returns its directory."""
    pairs = {"validation": (_read(Path(low_validation)), _read(Path(high_validation))),
             "train": (_read(Path(low_train)), _read(Path(high_train)))}  # fmt: skip
    lam = {split: check_arms(*pair) for split, pair in pairs.items()}
    if pairs["validation"][0]["meta"]["split"] != "validation" or pairs["train"][0][
            "meta"]["split"] != "train":  # fmt: skip
        raise FixedRiskComparisonError("pass the validation and train evaluations in order")
    if lam["validation"] != lam["train"]:
        raise FixedRiskComparisonError("the lambda values differ between splits")
    for arm in (0, 1):
        if pairs["validation"][arm]["meta"]["checkpoints"] != pairs["train"][arm]["meta"][
                "checkpoints"]:  # fmt: skip
            raise FixedRiskComparisonError("train and validation evaluate different runs")
    identity = {"schema_version": SCHEMA_VERSION, "criteria": CRITERIA_VERSION,
                "evaluations": {f"{arm}_{split}": pairs[split][i]["meta"]["evaluation_id"]
                                for split in pairs for i, arm in enumerate(("low", "high"))},
                "references": sorted(Path(d).name for d in reference_dirs)}  # fmt: skip
    root = resolve_path(context.experiment.evaluation_output_dir, context.root).parent
    target = root / "fixed_risk_comparisons" / cache.short_hash(identity)
    if target.exists():
        raise FixedRiskComparisonError(f"{target} already exists; comparisons are written once")
    table = seed_table(pairs)
    training = {name: training_components(context.root, context.experiment.output_dir,
                                          pairs["train"][i]) for i, name in
                enumerate(("low", "high"))}  # fmt: skip
    results = {
        "hypotheses": hypotheses(table, training),
        "training": training,
        "references": references(reference_dirs),
        "lambda": lam["validation"],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f"{target.name}.staging-{os.getpid()}"
    staging.mkdir()
    table.to_csv(staging / "seed_table.csv", index=False)
    paired_differences(table).to_csv(staging / "paired_differences.csv", index=False)
    cache.write_json(results["hypotheses"], staging / "hypotheses.json")
    cache.write_json(
        {
            "lambda": results["lambda"],
            **{k: {str(s): v for s, v in d.items()} for k, d in training.items()},
        },
        staging / "training_components.json",
    )
    cache.write_json(results["references"], staging / "references.json")
    metadata = {"comparison_id": target.name, **identity,
                "statistics": "descriptive; t-intervals are not significance tests",
                "files_sha256": {n: cache.file_sha256(staging / n) for n in FILES}}  # fmt: skip
    cache.write_json(metadata, staging / "metadata.json")
    staging.rename(target)
    return target


def verify_fixed_comparison(directory: Path) -> list[str]:
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    problems = [f"{n}: hash differs" for n, h in meta["files_sha256"].items()
                if cache.file_sha256(directory / n) != h]  # fmt: skip
    identity = {k: meta[k] for k in ("schema_version", "criteria", "evaluations", "references")}
    if cache.short_hash(identity) != directory.name:
        problems.append("identity hash != comparison id")
    return problems
