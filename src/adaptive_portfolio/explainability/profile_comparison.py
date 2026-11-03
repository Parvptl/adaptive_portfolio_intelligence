"""E4 vs E1 (and E0) comparison with the prespecified H1-H7 criteria (D-088; no ``rl`` extra).

Reads two **verified** profile evaluations of the same split: the E4 treatment
(``configs/profile_reward_experiment.yaml``) and the E1 control (``profile_experiment.yaml``,
EXP-010). It checks that they share the data, profile sets, E0 checkpoints and split, and that
E0 reproduces EXP-006 on validation. It then writes once:

* ``seed_table.csv``: seed-level metrics of E0, E1, E3, E4 and E4H (centre profile, and the mean
  over the ``in_distribution`` profiles);
* ``paired_differences.csv``: E4 - E0 and E4 - E1 per seed, with mean, SD (ddof 1), median,
  range, sign count and a descriptive t-interval (t_{0.975,4} = 2.776 for five seeds);
* ``hypotheses.json``: every H1-H7 part with its value and verdict, exactly as prespecified in
  ``docs/e4_profile_reward.md`` §6;
* ``exploitation.json``: reward-exploitation checks (cash collapse, concentration, turnover, and
  penalty/base ratios from the training-episode records).

The statistics are descriptive. The five seeds share one market history, so no p-value or
significance claim is made.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import resolve_path
from adaptive_portfolio.explainability.profile_analysis import rank_correlation

SCHEMA_VERSION = 1
CRITERIA_VERSION = "D-088 v1 (docs/e4_profile_reward.md §6, fixed before E4 training)"
# Student t 0.975 quantiles by degrees of freedom (df = seeds - 1).
T_975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}
RHO = 0.35
FILES = ("seed_table.csv", "paired_differences.csv", "hypotheses.json", "exploitation.json")
METRICS = {
    "annualised.net_sharpe": "net_sharpe",
    "net_cumulative_return": "net_cumulative_return",
    "annualised.net_annualised_return": "net_annualised_return",
    "annualised.net_annualised_volatility": "net_volatility",
    "net_max_drawdown": "net_max_drawdown",
    "gross_cumulative_return": "gross_cumulative_return",
    "cost_drag": "cost_drag",
    "annualised.annualised_traded_notional": "turnover",
    "mean_held_CASH": "mean_held_cash",
    "target_equity": "target_equity",
    "target_bonds": "target_bonds",
    "target_risky_hhi": "target_risky_hhi",
    "allocation_stability_dw": "allocation_stability_dw",
}


class ComparisonError(ValueError):
    """Raised when the two evaluations cannot be compared as prespecified."""


def _read(directory: Path) -> dict[str, Any]:
    from adaptive_portfolio.agents.profile_experiment import verify_profile_evaluation

    problems = verify_profile_evaluation(directory)
    if problems:
        raise ComparisonError(f"{directory} does not verify: {problems}")
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    out = {
        "dir": directory,
        "meta": meta,
        "summary": json.loads((directory / "summary.json").read_text(encoding="utf-8")),
    }
    for name in ("episode_metrics", "state_matched", "seed_scale", "contrasts"):
        path = directory / f"{name}.csv"
        out[name] = pd.read_csv(path) if path.is_file() else None
    return out


def _check_pair(treatment: Mapping[str, Any], control: Mapping[str, Any], wanted: dict) -> None:
    t, c = treatment["meta"], control["meta"]
    checks = {
        "same split": t["split"] == c["split"],
        "neither is a pipeline check": not t["pipeline_check"] and not c["pipeline_check"],
        "treatment has the E4 reward": "reward" in t["experiment"],
        "control has the D-064 reward": "reward" not in c["experiment"],
        "treatment matches the configured E4 experiment": t["experiment"] == wanted,
        "same profile sets": t["profile_sets"] == c["profile_sets"],
        "same E0 checkpoints": t["e0_checkpoints"] == c["e0_checkpoints"],
        "same data": t["data"] == c["data"],
        "same rows boundary": t["rows_read_before"] == c["rows_read_before"],
        "same seeds": t["experiment"]["seeds"] == c["experiment"]["seeds"],
        "same arms and sampling": t["experiment"]["arms"] == c["experiment"]["arms"],
    }
    if t["split"] == "validation":
        for label, run in (("treatment", treatment), ("control", control)):
            checks[f"{label}: E0 reproduces EXP-006"] = bool(
                run["summary"]["e0_reproduction"].get("reproduced")
            )
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ComparisonError("evaluations are not comparable: " + "; ".join(failed))


def _stats(values: np.ndarray) -> dict[str, float]:
    v = np.asarray(values, dtype=np.float64)
    n = len(v)
    mean = float(v.mean())
    sd = float(v.std(ddof=1)) if n > 1 else float("nan")
    half = T_975.get(n - 1, 1.96) * sd / math.sqrt(n) if n > 1 else float("nan")
    return {"n": n, "mean": mean, "sd": sd, "median": float(np.median(v)), "min": float(v.min()),
            "max": float(v.max()), "t_low": mean - half, "t_high": mean + half,
            "n_positive": int((v > 0).sum())}  # fmt: skip


def _acceptance(frame: pd.DataFrame) -> np.ndarray:
    return np.minimum(frame["profile_risk_tolerance"], frame["profile_risk_capacity"]).to_numpy()


def _per_seed(frame: pd.DataFrame) -> pd.DataFrame:
    keep = [k for k in METRICS if k in frame]
    return frame.groupby("seed")[keep].mean().rename(columns=METRICS)


def seed_table(treatment: Mapping[str, Any], control: Mapping[str, Any]) -> pd.DataFrame:
    rows = []
    t, c = treatment["episode_metrics"], control["episode_metrics"]
    arms = [("E0", t[t["experiment"] == "E0"], "-")]
    for exp, frame in (("E1", c), ("E3", c), ("E4", t), ("E4H", t)):
        for name in ("centre", "in_distribution", "heldout_training", "heldout_region"):
            part = frame[(frame["experiment"] == exp) & (frame["profile_set"] == name)]
            if len(part):
                arms.append((exp, part, name))
    for exp, frame, name in arms:
        table = _per_seed(frame)
        for seed, row in table.iterrows():
            rows.append({"arm": exp, "profile_set": name, "seed": int(seed), **row.to_dict()})
    return pd.DataFrame(rows)


def paired_differences(table: pd.DataFrame) -> pd.DataFrame:
    """E4 - E0 and E4 - E1, paired by seed, at the centre profile and the in-distribution mean."""
    rows = []
    metrics = [m for m in METRICS.values() if m in table]
    e0 = table[table["arm"] == "E0"].set_index("seed")
    for reference in ("E0", "E1"):
        for name in ("centre", "in_distribution"):
            e4 = table[(table["arm"] == "E4") & (table["profile_set"] == name)].set_index("seed")
            ref = (e0 if reference == "E0" else table[(table["arm"] == "E1") & (
                table["profile_set"] == name)].set_index("seed"))  # fmt: skip
            seeds = sorted(set(e4.index) & set(ref.index))
            for metric in metrics:
                diff = (e4.loc[seeds, metric] - ref.loc[seeds, metric]).to_numpy(float)
                if not np.isfinite(diff).all():
                    continue
                rows.append({"comparison": f"E4 - {reference}", "e4_profile_set": name,
                             "metric": metric, **{f"seed_{s}": float(d) for s, d in
                                                  zip(seeds, diff, strict=True)},
                             **_stats(diff)})  # fmt: skip
    return pd.DataFrame(rows)


def _rhos(frame: pd.DataFrame, outcome: str, key: str = "a") -> dict[int, float]:
    out = {}
    for seed, part in frame.groupby("seed"):
        x = _acceptance(part) if key == "a" else part[f"profile_{key}"].to_numpy()
        out[int(seed)] = rank_correlation(x, part[outcome].to_numpy())
    return out


def _verdict(parts: Mapping[str, bool]) -> str:
    passed = sum(bool(v) for v in parts.values())
    return ("supported" if passed == len(parts) else
            "partially supported" if passed else "not supported")  # fmt: skip


def hypotheses(treatment: Mapping[str, Any], control: Mapping[str, Any]) -> dict[str, Any]:
    """H1-H7 exactly as prespecified (docs/e4_profile_reward.md §6)."""
    t, c = treatment["episode_metrics"], control["episode_metrics"]
    e4 = t[(t["experiment"] == "E4") & (t["profile_set"] == "in_distribution")].copy()
    e1 = c[(c["experiment"] == "E1") & (c["profile_set"] == "in_distribution")].copy()
    for frame in (e4, e1):
        frame["cash_plus_bonds"] = frame["target_cash"] + frame["target_bonds"]
    vol = "annualised.net_annualised_volatility"
    turnover = "annualised.annualised_traded_notional"
    out: dict[str, Any] = {
        "criteria_version": CRITERIA_VERSION,
        "split": treatment["meta"]["split"],
    }

    def at_least_4(values: Mapping[int, float], sign: int) -> bool:
        return sum((sign * v) > RHO for v in values.values()) >= 4

    # H1: within-set state-matched D_w, E4 vs E1, paired by seed.
    st_t, st_c = treatment["state_matched"], control["state_matched"]

    def pick(s):
        return (s[(s["arm"] == "main") & (s["profile_set"] == "in_distribution")]
                .set_index("seed")["dw_mean"])  # fmt: skip

    dw4, dw1 = pick(st_t), pick(st_c)
    ratio = (dw4 / dw1).dropna()
    h1 = {
        "E4 > E1 in >= 4/5 seeds": int((dw4 > dw1).sum()) >= 4,
        "median E4/E1 ratio >= 2": float(ratio.median()) >= 2,
    }
    out["H1"] = {"parts": h1, "verdict": _verdict(h1), "dw_e4": dw4.to_dict(),
                 "dw_e1": dw1.to_dict(), "ratio_median": float(ratio.median())}  # fmt: skip
    # H2: direction of allocation; negative controls H, L, G.
    rho_eq, rho_safe = _rhos(e4, "target_equity"), _rhos(e4, "cash_plus_bonds")
    controls = {}
    for dim in ("investment_horizon", "liquidity_preference", "growth_preference"):
        for exposure in [
            c for c in ("target_equity", "target_bonds", "target_gold", "target_cash") if c in e4
        ]:  # the configured groups
            controls[f"{dim} vs {exposure}"] = float(np.median(list(
                _rhos(e4, exposure, dim).values())))  # fmt: skip
    h2 = {
        "rho(a, equity) > +0.35 in >= 4/5": at_least_4(rho_eq, +1),
        "rho(a, cash+bonds) < -0.35 in >= 4/5": at_least_4(rho_safe, -1),
        "negative controls |median rho| < 0.35": all(abs(v) < RHO for v in controls.values()),
    }
    out["H2"] = {
        "parts": h2,
        "verdict": _verdict(h2),
        "rho_a_equity": rho_eq,
        "rho_a_cash_plus_bonds": rho_safe,
        "negative_controls_median_rho": controls,
    }
    # H3: realised risk.
    rho_vol = _rhos(e4, vol)
    ratios = {}
    for seed, part in e4.groupby("seed"):
        ordered = part.assign(a=_acceptance(part)).sort_values("a")
        k = len(ordered) // 3
        ratios[int(seed)] = float(ordered[vol].iloc[-k:].mean() / ordered[vol].iloc[:k].mean())
    h3 = {"rho(a, volatility) > +0.35 in >= 4/5": at_least_4(rho_vol, +1),
          "median high/low tercile volatility ratio > 1.1": float(np.median(
              list(ratios.values()))) > 1.1}  # fmt: skip
    out["H3"] = {"parts": h3, "verdict": _verdict(h3), "rho_a_volatility": rho_vol,
                 "tercile_volatility_ratio": ratios}  # fmt: skip
    # H4: not via turnover.
    turn4 = e4.groupby("seed")[turnover].mean()
    turn1 = e1.groupby("seed")[turnover].mean()
    rho_turn = _rhos(e4, turnover)
    h4 = {"median turnover E4 <= 1.25 x E1": float(turn4.median()) <= 1.25 * float(turn1.median()),
          "median rho(a, turnover) <= median rho(a, volatility)": float(np.median(
              list(rho_turn.values()))) <= float(np.median(list(rho_vol.values())))}  # fmt: skip
    out["H4"] = {"parts": h4, "verdict": _verdict(h4), "turnover_e4": turn4.to_dict(),
                 "turnover_e1": turn1.to_dict(), "rho_a_turnover": rho_turn}  # fmt: skip
    # H5: stability.
    signs = [np.sign(v) for v in rho_vol.values() if np.isfinite(v)]

    def scale(s):
        return float(s[s["arm"] == "main"]["dw_mean"].iloc[0])

    scale4, scale1 = scale(treatment["seed_scale"]), scale(control["seed_scale"])
    h5 = {
        "same sign of rho(a, volatility) in >= 4/5": max(signs.count(1), signs.count(-1)) >= 4,
        "E4 seed-scale D_w <= 1.5 x E1": scale4 <= 1.5 * scale1,
    }
    out["H5"] = {
        "parts": h5,
        "verdict": _verdict(h5),
        "seed_scale_e4": scale4,
        "seed_scale_e1": scale1,
    }
    # H6: unseen combinations (held-out arm).
    held = t[t["experiment"] == "E4H"]
    region = held[held["profile_set"] == "heldout_region"].groupby("seed")
    training = held[held["profile_set"] == "heldout_training"].groupby("seed")
    vol_region, vol_training = region[vol].mean(), training[vol].mean()
    sharpe_gap = region["annualised.net_sharpe"].mean() - training["annualised.net_sharpe"].mean()
    spread = float(training["annualised.net_sharpe"].std(ddof=1).median())
    h6 = {"region volatility below training-profile volatility in >= 4/5":
          int((vol_region < vol_training).sum()) >= 4,
          "|median Sharpe gap| <= median within-seed SD": abs(float(sharpe_gap.median()))
          <= spread}  # fmt: skip
    out["H6"] = {
        "parts": h6,
        "verdict": _verdict(h6),
        "volatility_region": vol_region.to_dict(),
        "volatility_training_profiles": vol_training.to_dict(),
        "sharpe_gap": sharpe_gap.to_dict(),
        "within_seed_sd_median": spread,
    }
    # H7: extreme-profile contrast vs seed variation.
    contrasts = treatment["contrasts"]
    main = contrasts[contrasts["arm"] == "main"].set_index("seed")["dw"]
    h7 = {"median a=0 vs a=1 D_w > E4 seed-scale D_w": float(main.median()) > scale4}
    out["H7"] = {
        "parts": h7,
        "verdict": _verdict(h7),
        "contrast_dw": main.to_dict(),
        "seed_scale_e4": scale4,
    }
    return out


def exploitation(context: Any, treatment: Mapping[str, Any], control: Mapping[str, Any]) -> dict:
    t, c = treatment["episode_metrics"], control["episode_metrics"]
    e4 = t[t["experiment"].isin(["E4", "E4H"])]
    e1 = c[c["experiment"].isin(["E1", "E3"])]
    root = resolve_path(context.experiment.output_dir, context.root)
    training = {}
    for checkpoint in treatment["meta"]["checkpoints"]:
        meta = json.loads((root / checkpoint["run_id"] / "metadata.json").read_text("utf-8"))
        episodes = [e for e in meta.get("episode_reward_components", []) if e["steps"] > 0]
        base = np.array([e["reward_base"] for e in episodes])
        penalty = np.array([e["risk_penalty"] for e in episodes])
        training[f"{checkpoint['arm']} s{checkpoint['seed']}"] = {
            "episodes": len(episodes),
            "mean_penalty_over_mean_abs_base": float(penalty.mean() / np.abs(base).mean()),
            "share_episodes_penalty_above_abs_base": float((penalty > np.abs(base)).mean()),
            "last10_reward_base_mean": float(base[-10:].mean()),
            "last10_penalty_mean": float(penalty[-10:].mean()),
        }
    return {
        "share_target_cash_above_95_mean_e4": float(e4["share_target_cash_above_95"].mean()),
        "share_target_cash_above_95_max_e4": float(e4["share_target_cash_above_95"].max()),
        "max_held_weight_e4": float(e4["max_held_weight"].max()),
        "max_held_weight_e1": float(e1["max_held_weight"].max()),
        "target_risky_hhi_mean_e4": float(e4["target_risky_hhi"].mean()),
        "target_risky_hhi_mean_e1": float(e1["target_risky_hhi"].mean()),
        "turnover_median_e4": float(e4["annualised.annualised_traded_notional"].median()),
        "turnover_median_e1": float(e1["annualised.annualised_traded_notional"].median()),
        "training_episodes": training,
    }


def run_comparison(context: Any, treatment_dir: Path, control_dir: Path) -> Path:
    """Compute and write the comparison once; returns its directory."""
    treatment, control = _read(Path(treatment_dir)), _read(Path(control_dir))
    if treatment["contrasts"] is None:
        raise ComparisonError("the treatment evaluation has no interaction grid / contrasts")
    _check_pair(treatment, control, context.experiment.to_dict())
    identity = {"schema_version": SCHEMA_VERSION, "criteria": CRITERIA_VERSION,
                "treatment": treatment["meta"]["evaluation_id"],
                "control": control["meta"]["evaluation_id"],
                "split": treatment["meta"]["split"]}  # fmt: skip
    root = resolve_path(context.experiment.evaluation_output_dir, context.root).parent
    target = root / "profile_reward_comparisons" / cache.short_hash(identity)
    if target.exists():
        raise ComparisonError(f"{target} already exists; comparisons are written once")
    table = seed_table(treatment, control)
    diffs = paired_differences(table)
    results = {
        "hypotheses": hypotheses(treatment, control),
        "exploitation": exploitation(context, treatment, control),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f"{target.name}.staging-{os.getpid()}"
    staging.mkdir()
    table.to_csv(staging / "seed_table.csv", index=False)
    diffs.to_csv(staging / "paired_differences.csv", index=False)
    cache.write_json(results["hypotheses"], staging / "hypotheses.json")
    cache.write_json(results["exploitation"], staging / "exploitation.json")
    metadata = {"comparison_id": target.name, **identity,
                "statistics": "descriptive; t-intervals are not significance tests",
                "files_sha256": {n: cache.file_sha256(staging / n) for n in FILES}}  # fmt: skip
    cache.write_json(metadata, staging / "metadata.json")
    staging.rename(target)
    return target


def load_hypotheses(directory: Path) -> dict[str, Any]:
    data = json.loads((Path(directory) / "hypotheses.json").read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k.startswith("H")}


def verify_comparison(directory: Path) -> list[str]:
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    problems = [f"{n}: hash differs" for n, h in meta["files_sha256"].items()
                if cache.file_sha256(directory / n) != h]  # fmt: skip
    identity = {k: meta[k] for k in ("schema_version", "criteria", "treatment", "control",
                                     "split")}  # fmt: skip
    if cache.short_hash(identity) != directory.name:
        problems.append("identity hash != comparison id")
    return problems
