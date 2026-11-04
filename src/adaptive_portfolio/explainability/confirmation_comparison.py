"""E9 turnover-penalty confirmation: kappa = 0 vs 0.0015 on new seeds (D-093; no ``rl``).

Reads four **verified** evaluations (E9B and E9T1 x training and validation; each covers seeds
42-56). The primary population is the extension seeds 47-56; seeds 42-46 are only the H9
reproduction check against E8 (and E7); 42-56 together is a labelled secondary analysis. Writes
once, under ``<evaluation root>/../confirmation_comparisons/<id>/``:

* ``seed_table.csv``: per split, seed and arm (with the seed's population);
* ``paired_differences.csv``: per split, population and metric: E9T1 - E9B per seed, mean,
  median, SD, SE, sign counts, the bootstrap CI, the exact permutation p and the t-interval;
* ``hypotheses.json``: H1-H10 and the outcome (``docs/e9_confirmation_protocol.md`` §5-§7);
* ``reproduction.json``: seeds 42-46 against the E8 and E7 evaluations, exactly (H9);
* ``baselines.json``: the baselines of the same validation evaluation (separate from the test);
* ``training_components.json``: reward components of the training episodes, per run.

The statistics describe seed-to-seed variability on **one** market history.
"""

from __future__ import annotations

import itertools
import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import resolve_path
from adaptive_portfolio.explainability.fixed_risk_comparison import _read, training_components
from adaptive_portfolio.explainability.profile_comparison import METRICS, _verdict
from adaptive_portfolio.explainability.turnover_comparison import _core, kappa_of
from adaptive_portfolio.explainability.turnover_refine_comparison import arm_table, compare_exact

SCHEMA_VERSION = 1
CRITERIA_VERSION = "D-093 v1 (docs/e9_confirmation_protocol.md §5-§7, fixed before E9 training)"
FILES = ("seed_table.csv", "paired_differences.csv", "hypotheses.json", "reproduction.json",
         "baselines.json", "training_components.json")  # fmt: skip
PRIMARY_SEEDS = tuple(range(47, 57))
REPRODUCTION_SEEDS = tuple(range(42, 47))
POPULATIONS = {"primary": PRIMARY_SEEDS, "reproduction": REPRODUCTION_SEEDS,
               "pooled": REPRODUCTION_SEEDS + PRIMARY_SEEDS}  # fmt: skip
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261104
T_975 = {4: 2.776, 9: 2.262, 14: 2.145}
TIE = 1e-12
ENDPOINTS = ("net_sharpe", "net_annualised_return", "gross_cumulative_return",
             "net_cumulative_return", "cost_drag", "turnover", "net_volatility",
             "net_max_drawdown", "target_cash", "target_risky_hhi", "allocation_dispersion",
             "share_meaningful_changes", "allocation_stability_dw", "target_equity",
             "target_bonds", "share_target_cash_above_95")  # fmt: skip
# Guard rails from E7/E8 (D-091, D-092), unchanged.
VOL_MAX, DRAWDOWN_MAX = 0.005, 0.02
HHI_MAX, CASH_MAX, NEAR_ALL_CASH_MAX = 2 / 3, 0.40, 0.05
DISPERSION_RATIO, MEANINGFUL_RATIO, DW_RATIO = 0.50, 0.50, 0.25


class ConfirmationError(ValueError):
    """Raised when the E9 evaluations cannot be analysed as prespecified."""


# --------------------------------------------------------------------------
# Paired-seed statistics
# --------------------------------------------------------------------------


def paired(control: pd.Series, treatment: pd.Series, seeds: Sequence[int]) -> pd.Series:
    """Treatment - control per seed; every seed must appear exactly once in both arms."""
    for name, series in (("control", control), ("treatment", treatment)):
        if series.index.has_duplicates:
            dup = sorted(set(series.index[series.index.duplicated()]))
            raise ConfirmationError(f"{name}: duplicate seeds {dup}")
        missing = sorted(set(seeds) - set(series.index))
        if missing:
            raise ConfirmationError(f"{name}: missing seeds {missing} (no silent pair dropping)")
    seeds = list(seeds)
    diff = treatment.loc[seeds].astype(float) - control.loc[seeds].astype(float)
    if not np.isfinite(diff.to_numpy()).all():
        raise ConfirmationError("non-finite paired difference")
    return diff


def bootstrap_ci(diff: np.ndarray, resamples: int = BOOTSTRAP_RESAMPLES,
                 seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:  # fmt: skip
    """Percentile bootstrap 95% CI of the mean paired difference (resampling seeds)."""
    d = np.asarray(diff, dtype=np.float64)
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, len(d), size=(resamples, len(d)))].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def permutation_p(diff: np.ndarray) -> float:
    """Exact two-sided sign-flip permutation p-value of the mean paired difference."""
    d = np.asarray(diff, dtype=np.float64)
    if len(d) > 20:
        raise ConfirmationError("the exact permutation test is limited to 20 pairs")
    signs = np.array(list(itertools.product((1.0, -1.0), repeat=len(d))))
    means = (signs * d).mean(axis=1)
    observed = abs(d.mean())
    return float((np.abs(means) >= observed - TIE).mean())


def paired_stats(diff: np.ndarray) -> dict[str, Any]:
    d = np.asarray(diff, dtype=np.float64)
    n = len(d)
    mean, sd = float(d.mean()), float(d.std(ddof=1)) if n > 1 else float("nan")
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    t = T_975.get(n - 1)
    low, high = bootstrap_ci(d) if n > 1 else (float("nan"), float("nan"))
    return {
        "n": n, "mean": mean, "median": float(np.median(d)), "sd": sd, "se": se,
        "min": float(d.min()), "max": float(d.max()),
        "n_positive": int((d > TIE).sum()), "n_negative": int((d < -TIE).sum()),
        "n_ties": int((np.abs(d) <= TIE).sum()),
        "bootstrap_low": low, "bootstrap_high": high,
        "permutation_p": permutation_p(d) if n > 1 else float("nan"),
        "t_statistic": mean / se if se and se > 0 else float("nan"),
        "t_low": mean - t * se if t and se == se else float("nan"),
        "t_high": mean + t * se if t and se == se else float("nan"),
    }  # fmt: skip


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


def check_arms(runs: Sequence[Mapping[str, Any]]) -> list[float]:
    """E9B and E9T1 of one split: kappa 0 < kappa 1, lambda 0, identical otherwise."""
    if len(runs) != 2:
        raise ConfirmationError("the confirmation needs exactly two arms (E9B, E9T1)")
    metas = [r["meta"] for r in runs]
    kappa = [kappa_of(m) for m in metas]
    first = metas[0]
    seeds = [tuple(m["experiment"]["seeds"]) for m in metas]
    checks = {
        "kappa 0 then kappa > 0": kappa[0] == 0.0 and kappa[1] > 0.0,
        "same split": len({m["split"] for m in metas}) == 1,
        "not pipeline checks": not any(m["pipeline_check"] for m in metas),
        "identical except kappa and label": _core(metas[1]["experiment"]) == _core(
            first["experiment"]),
        "lambda = 0 in both arms": all(
            float((m["experiment"].get("reward") or {}).get("fixed_lambda", -1)) == 0.0
            for m in metas),
        "seeds cover the primary and reproduction populations": all(
            set(POPULATIONS["pooled"]) <= set(s) for s in seeds),
        "extension seeds are the primary seeds": all(
            tuple(m["experiment"].get("extension_seeds") or ()) == PRIMARY_SEEDS for m in metas),
        "same E0 checkpoints": metas[1]["e0_checkpoints"] == first["e0_checkpoints"],
        "same data": metas[1]["data"] == first["data"],
        "same rows boundary": metas[1]["rows_read_before"] == first["rows_read_before"],
        "distinct labels": metas[0]["experiment"]["label"] != metas[1]["experiment"]["label"],
    }  # fmt: skip
    if first["split"] == "validation":
        for run in runs:
            checks[f"{run['meta']['experiment']['label']}: E0 reproduces EXP-006"] = bool(
                run["summary"]["e0_reproduction"].get("reproduced"))  # fmt: skip
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise ConfirmationError("E9 arms are not comparable: " + "; ".join(failed))
    return kappa


def _table(run: Mapping[str, Any]) -> pd.DataFrame:
    table = arm_table(run)
    m = run["metrics"]
    label = run["meta"]["experiment"]["label"]
    part = m[(m["experiment"] == label) & (m["profile_set"] == "centre")]
    if part["seed"].duplicated().any():
        raise ConfirmationError(f"{label}: duplicate seed rows in the evaluation")
    return table


def seed_table(splits: Mapping[str, Sequence[Mapping[str, Any]]], kappa: Sequence[float]):
    population = {s: p for p in ("reproduction", "primary") for s in POPULATIONS[p]}
    rows = []
    for split, runs in splits.items():
        for i, run in enumerate(runs):
            for seed, row in _table(run).assign(turnover_penalty=kappa[i]).iterrows():
                pop = population.get(int(seed), "other")
                rows.append({"split": split, "seed": int(seed), "population": pop,
                             **row.to_dict()})  # fmt: skip
    return pd.DataFrame(rows)


def _arm(table: pd.DataFrame, split: str, label: str) -> pd.DataFrame:
    part = table[(table["split"] == split) & (table["arm"] == label)]
    return part.set_index("seed").sort_index()


def paired_differences(table: pd.DataFrame, labels: Sequence[str]) -> pd.DataFrame:
    rows = []
    for split in sorted(table["split"].unique()):
        b, t = _arm(table, split, labels[0]), _arm(table, split, labels[1])
        for population, seeds in POPULATIONS.items():
            for metric in ENDPOINTS:
                if metric not in b or metric not in t:
                    continue
                diff = paired(b[metric], t[metric], seeds)
                rows.append({"split": split, "population": population, "metric": metric,
                             "control_median": float(b.loc[list(seeds), metric].median()),
                             "treatment_median": float(t.loc[list(seeds), metric].median()),
                             "control_mean": float(b.loc[list(seeds), metric].mean()),
                             "treatment_mean": float(t.loc[list(seeds), metric].mean()),
                             **{f"seed_{s}": float(v) for s, v in diff.items()},
                             **paired_stats(diff.to_numpy())})  # fmt: skip
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Hypotheses and outcome (primary population, validation)
# --------------------------------------------------------------------------


def _get(diffs: pd.DataFrame, metric: str, split: str = "validation",
         population: str = "primary") -> Mapping[str, Any]:  # fmt: skip
    row = diffs[(diffs["split"] == split) & (diffs["population"] == population)
                & (diffs["metric"] == metric)]  # fmt: skip
    if len(row) != 1:
        raise ConfirmationError(f"no unique paired row for {metric} ({split}, {population})")
    return row.iloc[0].to_dict()


def _reduction(s: Mapping[str, Any]) -> dict[str, bool]:
    return {"mean difference < 0": s["mean"] < 0,
            "bootstrap CI upper < 0": s["bootstrap_high"] < 0,
            ">= 8/10 seeds lower": s["n_negative"] >= 8}  # fmt: skip


def _graded(parts: Mapping[str, bool], partial: bool) -> str:
    return "supported" if all(parts.values()) else "partially supported" if partial else (
        "not supported")  # fmt: skip


def _improvement(s: Mapping[str, Any]) -> tuple[dict[str, bool], bool]:
    parts = {"mean difference > 0": s["mean"] > 0,
             "bootstrap CI lower > 0": s["bootstrap_low"] > 0,
             "permutation p < 0.05": s["permutation_p"] < 0.05,
             ">= 7/10 seeds positive": s["n_positive"] >= 7}  # fmt: skip
    return parts, s["mean"] > 0 and s["n_positive"] >= 6


def hypotheses(table: pd.DataFrame, diffs: pd.DataFrame, labels: Sequence[str],
               reproduction: Mapping[str, Any], complete_pairs: int) -> dict[str, Any]:  # fmt: skip
    """H1-H10 and the outcome (docs/e9_confirmation_protocol.md §5-§7)."""
    out: dict[str, Any] = {"criteria_version": CRITERIA_VERSION, "population": "seeds 47-56",
                           "split": "validation"}  # fmt: skip
    stats = {m: _get(diffs, m) for m in ENDPOINTS if not diffs[diffs["metric"] == m].empty}
    for name, metric in (("H1", "turnover"), ("H2", "cost_drag")):
        parts = _reduction(stats[metric])
        out[name] = {"parts": parts, "verdict": _graded(parts, stats[metric]["mean"] < 0),
                     "statistics": stats[metric]}  # fmt: skip
    for name, metric in (("H3", "net_sharpe"), ("H4", "net_annualised_return")):
        parts, partial = _improvement(stats[metric])
        out[name] = {"parts": parts, "verdict": _graded(parts, partial),
                     "statistics": stats[metric]}  # fmt: skip

    b = _arm(table, "validation", labels[0]).loc[list(PRIMARY_SEEDS)]
    t = _arm(table, "validation", labels[1]).loc[list(PRIMARY_SEEDS)]
    identity = max(float((a["gross_cumulative_return"] - a["net_cumulative_return"]
                          - a["cost_drag"]).abs().max()) for a in (b, t))  # fmt: skip
    saving = -stats["cost_drag"]["mean"]
    gross_loss = -stats["gross_cumulative_return"]["mean"]
    exact = "cost drag = gross - net cumulative (<= 1e-12)"
    h5 = {
        exact: identity <= TIE,
        "mean cost saving >= mean gross cumulative-return loss": saving >= gross_loss,
    }
    out["H5"] = {"parts": h5, "verdict": "supported" if all(h5.values()) else (
        "partially supported" if h5[exact] else "not supported"),
        "max_identity_error": identity, "mean_cost_saving": saving,
        "mean_gross_change": stats["gross_cumulative_return"]["mean"],
        "mean_net_cumulative_change": stats["net_cumulative_return"]["mean"]}  # fmt: skip

    h6 = {"median vol increase <= 0.5 pp": stats["net_volatility"]["median"] <= VOL_MAX,
          "median drawdown deepening <= 2 pp": -stats["net_max_drawdown"]["median"]
          <= DRAWDOWN_MAX}  # fmt: skip
    out["H6"] = {"parts": h6, "verdict": _verdict(h6),
                 "downside_risk": "not available from the evaluator (D-076)"}  # fmt: skip
    medians = {m: float(t[m].median()) for m in ("target_risky_hhi", "target_cash",
                                                  "share_target_cash_above_95")}  # fmt: skip
    h7 = {"E9T1 risky HHI <= 2/3": medians["target_risky_hhi"] <= HHI_MAX,
          "E9T1 target cash <= 0.40": medians["target_cash"] <= CASH_MAX,
          "E9T1 near-all-cash share <= 0.05": medians["share_target_cash_above_95"]
          <= NEAR_ALL_CASH_MAX}  # fmt: skip
    out["H7"] = {"parts": h7, "verdict": _verdict(h7), "treatment_medians": medians,
                 "control_medians": {m: float(b[m].median()) for m in medians}}  # fmt: skip
    ratios = {m: float(t[m].median()) / float(b[m].median()) if float(b[m].median()) > 0
              else float("nan") for m in ("allocation_dispersion", "share_meaningful_changes",
                                          "allocation_stability_dw")}  # fmt: skip
    h8 = {"dispersion >= 50% of E9B": ratios["allocation_dispersion"] >= DISPERSION_RATIO,
          "meaningful-change share >= 50% of E9B": ratios["share_meaningful_changes"]
          >= MEANINGFUL_RATIO,
          "D_w >= 25% of E9B": ratios["allocation_stability_dw"] >= DW_RATIO}  # fmt: skip
    out["H8"] = {"parts": h8, "verdict": _verdict(h8), "ratios_to_control": ratios}
    h9 = {f"{k} reproduces exactly": bool(v.get("identical")) for k, v in reproduction.items()}
    out["H9"] = {"parts": h9, "verdict": "supported" if h9 and all(h9.values())
                 else "not supported", "reproduction": dict(reproduction)}  # fmt: skip
    v = {k: out[k]["verdict"] for k in ("H3", "H4", "H6", "H7", "H8")}
    if all(v[k] == "supported" for k in v):
        h10 = "supported"
    elif v["H3"] != "not supported" and v["H7"] != "not supported" and v["H8"] != "not supported":
        h10 = "partially supported"
    else:
        h10 = "not supported"
    out["H10"] = {"verdict": h10, "inputs": v}

    sharpe = stats["net_sharpe"]
    if out["H9"]["verdict"] != "supported" or complete_pairs < len(PRIMARY_SEEDS):
        outcome = "Inconclusive: technical or methodological failure"
    elif out["H3"]["verdict"] == "supported" and out["H4"]["verdict"] == "supported":
        outcome = "Confirmation"
    elif sharpe["mean"] > 0 and sharpe["n_positive"] >= 6:
        outcome = "Partial confirmation"
    elif sharpe["mean"] < 0 and sharpe["bootstrap_high"] < 0:
        outcome = "Deterioration"
    else:
        outcome = "No reliable improvement"
    verdicts = {k: out[k]["verdict"] for k in out if k.startswith("H")}
    out["outcome"] = {"class": outcome, "complete_primary_pairs": complete_pairs,
                      "verdicts": verdicts}  # fmt: skip
    return out


# --------------------------------------------------------------------------
# Reproduction, baselines and the run
# --------------------------------------------------------------------------


def reproduction(table: pd.DataFrame, labels: Sequence[str],
                 targets: Mapping[str, Sequence[Path]]) -> dict[str, Any]:  # fmt: skip
    """H9: seeds 42-46 of an E9 arm vs earlier evaluations. Keys ``"<arm index>:<name>"``."""
    out = {}
    for key, dirs in targets.items():
        index, name = key.split(":", 1)
        for d in dirs:
            run = _read(Path(d))
            split = run["meta"]["split"]
            ours = _arm(table, split, labels[int(index)]).loc[list(REPRODUCTION_SEEDS)]
            ours = ours.drop(columns=["population", "split"], errors="ignore")
            out[f"{name} ({split})"] = compare_exact(ours, run)
    return out


def baselines(run: Mapping[str, Any]) -> dict[str, Any]:
    """The baselines of the E9 validation evaluation (same window, costs and accounting)."""
    m = run["metrics"]
    part = m[m["experiment"] == "baseline"]
    keep = [c for c in METRICS if c in part]
    out = {}
    for arm, rows in part.groupby("arm"):
        values = rows[keep].rename(columns=METRICS)
        out[str(arm)] = {"rows": len(rows), **{k: float(v) for k, v in values.median().items()}}
    return {"evaluation_id": run["meta"]["evaluation_id"], "split": run["meta"]["split"],
            "strategies": out}  # fmt: skip


def run_confirmation(
    context: Any,
    validation_dirs: Sequence[Path],
    train_dirs: Sequence[Path],
    reproduction_dirs: Mapping[str, Sequence[Path]],
) -> Path:
    """Compute and write the E9 analysis once; returns its directory."""
    splits = {"validation": [_read(Path(d)) for d in validation_dirs],
              "train": [_read(Path(d)) for d in train_dirs]}  # fmt: skip
    kappa = {split: check_arms(runs) for split, runs in splits.items()}
    if {r["meta"]["split"] for r in splits["validation"]} != {"validation"} or {
            r["meta"]["split"] for r in splits["train"]} != {"train"}:  # fmt: skip
        raise ConfirmationError("pass the validation and the train evaluations in order")
    if kappa["validation"] != kappa["train"]:
        raise ConfirmationError("kappa values differ between splits")
    for v, t in zip(splits["validation"], splits["train"], strict=True):
        if v["meta"]["checkpoints"] != t["meta"]["checkpoints"]:
            raise ConfirmationError("train and validation evaluate different runs")
    labels = [r["meta"]["experiment"]["label"] for r in splits["validation"]]
    identity = {"schema_version": SCHEMA_VERSION, "criteria": CRITERIA_VERSION,
                "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED},
                "evaluations": {f"{lab}_{split}": runs[i]["meta"]["evaluation_id"]
                                for split, runs in splits.items()
                                for i, lab in enumerate(labels)},
                "reproduction": {k: sorted(Path(d).name for d in v)
                                 for k, v in sorted(reproduction_dirs.items())}}  # fmt: skip
    root = resolve_path(context.experiment.evaluation_output_dir, context.root).parent
    target = root / "confirmation_comparisons" / cache.short_hash(identity)
    if target.exists():
        raise ConfirmationError(f"{target} already exists; comparisons are written once")
    table = seed_table(splits, kappa["validation"])
    diffs = paired_differences(table, labels)
    both = set(_arm(table, "validation", labels[0]).index) & set(
        _arm(table, "validation", labels[1]).index)  # fmt: skip
    complete = len(both & set(PRIMARY_SEEDS))
    repro = reproduction(table, labels, reproduction_dirs)
    training = {lab: {str(s): v for s, v in training_components(
        context.root, context.experiment.output_dir, splits["train"][i]).items()}
        for i, lab in enumerate(labels)}  # fmt: skip
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f"{target.name}.staging-{os.getpid()}"
    staging.mkdir()
    table.to_csv(staging / "seed_table.csv", index=False)
    diffs.to_csv(staging / "paired_differences.csv", index=False)
    cache.write_json(hypotheses(table, diffs, labels, repro, complete), staging / "hypotheses.json")
    cache.write_json(repro, staging / "reproduction.json")
    cache.write_json(baselines(splits["validation"][0]), staging / "baselines.json")
    cache.write_json({"turnover_penalty": kappa["validation"], **training},
                     staging / "training_components.json")  # fmt: skip
    metadata = {"comparison_id": target.name, "kind": "confirmation", **identity,
                "populations": {k: list(v) for k, v in POPULATIONS.items()},
                "statistics": "paired seed-level; bootstrap CI and exact permutation test on one "
                              "market history (seed variability, not market generalisation)",
                "files_sha256": {n: cache.file_sha256(staging / n) for n in FILES}}  # fmt: skip
    cache.write_json(metadata, staging / "metadata.json")
    staging.rename(target)
    return target


def verify_confirmation(directory: Path) -> list[str]:
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    problems = [f"{n}: hash differs" for n, h in meta["files_sha256"].items()
                if cache.file_sha256(directory / n) != h]  # fmt: skip
    identity = {k: meta[k] for k in ("schema_version", "criteria", "bootstrap", "evaluations",
                                     "reproduction")}  # fmt: skip
    if cache.short_hash(identity) != directory.name:
        problems.append("identity hash != comparison id")
    return problems
