"""Descriptive analysis of profile-conditioned allocations (D-085; protocol §15.8; no ``rl``).

Everything here is descriptive: there are no confidence intervals, no p-values and no
significance claims (research_protocol.md §15.8). A change of allocation with the profile is
evidence of **behavioural sensitivity**, not of good performance or suitable advice.

Definitions:

* **Mean absolute allocation difference** between two target paths ``A`` and ``B`` (decisions x
  N weights, assets then cash, N = n_assets + 1)::

      D_w(A, B) = mean over decisions of (1/N) * sum_k |A_k - B_k|

  For one decision this is the prompt's ``D_w(U_i, U_j)``; values lie in ``[0, 2/N]``.
* **State-matched** comparisons evaluate the policy on one fixed sequence of observations and
  replace only the five profile inputs, so path effects (different holdings, costs and values)
  are excluded.
* **Rank correlation** is Spearman's (Pearson correlation of average ranks); ``nan`` when a
  variable is constant.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.environment.profiles import (
    NEUTRAL_VALUE,
    PROFILE_DIMENSIONS,
    PROFILE_SIZE,
    validate_profile,
)

CASH = "CASH"
LIMITATIONS = (
    "Descriptive only: one market history, five seeds, no intervals or significance tests.",
    "The D-064 reward does not depend on the profile, so profile dependence is not "
    "personalisation and says nothing about suitability (D-085).",
    "State-matched differences hold observations fixed; they are one-step sensitivities, "
    "not causal effects on returns or risk (D-068).",
    "Profiles are synthetic research representations, not validated suitability scores.",
)


class ProfileAnalysisError(ValueError):
    """Raised for inconsistent target paths, profiles or outcome arrays."""


def _paths(*paths: np.ndarray) -> list[np.ndarray]:
    arrays = [np.asarray(p, dtype=np.float64) for p in paths]
    shape = arrays[0].shape
    if len(shape) != 2 or any(a.shape != shape for a in arrays):
        raise ProfileAnalysisError(f"target paths need one (decisions, N) shape, got "
                                   f"{[a.shape for a in arrays]}")  # fmt: skip
    if not all(np.isfinite(a).all() for a in arrays):
        raise ProfileAnalysisError("target paths must be finite")
    return arrays


def per_decision_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """``(1/N) * sum_k |a_k - b_k|`` for every decision (row)."""
    a, b = _paths(a, b)
    return np.abs(a - b).mean(axis=1)


def mean_abs_difference(a: np.ndarray, b: np.ndarray) -> float:
    """``D_w``: the per-decision difference averaged over decisions."""
    return float(per_decision_difference(a, b).mean())


def pairwise_differences(paths: np.ndarray) -> np.ndarray:
    """Symmetric ``(P, P)`` matrix of ``D_w`` between ``P`` target paths ``(P, T, N)``."""
    stack = np.asarray(paths, dtype=np.float64)
    if stack.ndim != 3 or stack.shape[0] < 2:
        raise ProfileAnalysisError(f"need (profiles >= 2, decisions, N), got {stack.shape}")
    matrix = np.zeros((stack.shape[0], stack.shape[0]))
    for i, j in combinations(range(stack.shape[0]), 2):
        matrix[i, j] = matrix[j, i] = mean_abs_difference(stack[i], stack[j])
    return matrix


def pairwise_summary(paths: np.ndarray) -> dict[str, float]:
    """Mean, median and maximum ``D_w`` over all profile pairs, and the spread over decisions
    of the per-decision mean pairwise difference (5th, 50th and 95th percentiles)."""
    stack = np.asarray(paths, dtype=np.float64)
    matrix = pairwise_differences(stack)
    upper = matrix[np.triu_indices(stack.shape[0], 1)]
    per_decision = np.mean(
        [per_decision_difference(stack[i], stack[j])
         for i, j in combinations(range(stack.shape[0]), 2)], axis=0,
    )  # fmt: skip
    return {
        "pairs": len(upper),
        "dw_mean": float(upper.mean()),
        "dw_median": float(np.median(upper)),
        "dw_max": float(upper.max()),
        "per_decision_p05": float(np.quantile(per_decision, 0.05)),
        "per_decision_p50": float(np.quantile(per_decision, 0.50)),
        "per_decision_p95": float(np.quantile(per_decision, 0.95)),
    }


def rank_correlation(x: Sequence[float], y: Sequence[float]) -> float:
    """Spearman's rank correlation (average ranks for ties); ``nan`` if either is constant."""
    xs, ys = pd.Series(np.asarray(x, float)), pd.Series(np.asarray(y, float))
    if len(xs) != len(ys) or len(xs) < 3:
        raise ProfileAnalysisError("rank correlation needs two equal-length series (n >= 3)")
    rx, ry = xs.rank().to_numpy(), ys.rank().to_numpy()
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def exposures(
    targets: np.ndarray, assets: Sequence[str], groups: Mapping[str, Sequence[str]]
) -> dict[str, float]:
    """Mean target exposure per group, mean cash and mean risky-sleeve Herfindahl index.

    ``targets`` are decision targets ``(decisions, n_assets + 1)``, cash last.
    """
    (path,) = _paths(targets)
    if path.shape[1] != len(assets) + 1:
        raise ProfileAnalysisError(f"{path.shape[1]} weight columns for {len(assets)} assets")
    index = {asset: i for i, asset in enumerate(assets)}
    unknown = {a for members in groups.values() for a in members} - set(index)
    if unknown:
        raise ProfileAnalysisError(f"exposure groups name unknown assets {sorted(unknown)}")
    out = {f"target_{g}": float(path[:, [index[a] for a in members]].sum(axis=1).mean())
           for g, members in groups.items()}  # fmt: skip
    out["target_cash"] = float(path[:, -1].mean())
    out["share_target_cash_above_95"] = float((path[:, -1] > 0.95).mean())
    risky = path[:, :-1]
    totals = risky.sum(axis=1)
    shares = np.divide(risky, totals[:, None], out=np.zeros_like(risky), where=totals[:, None] > 0)
    out["target_risky_hhi"] = float((shares**2).sum(axis=1)[totals > 0].mean())
    return out


MEANINGFUL_CHANGE = 0.05  # E8 (D-092): at least 5% of the portfolio reallocated


def responsiveness(targets: np.ndarray) -> dict[str, float]:
    """E8 responsiveness of one target path ``(decisions, N)`` (D-092).

    ``allocation_dispersion`` is the mean over columns of each target weight's standard deviation
    (ddof 0) across decisions: how widely the allocation moves. ``share_meaningful_changes`` is
    the share of consecutive decisions whose target change ``0.5 * sum |w_k - w_{k-1}|`` is at
    least :data:`MEANINGFUL_CHANGE`: how often a reallocation is large enough to matter.
    """
    (path,) = _paths(targets)
    if len(path) < 2:
        return {"allocation_dispersion": float("nan"), "share_meaningful_changes": float("nan")}
    change = 0.5 * np.abs(np.diff(path, axis=0)).sum(axis=1)
    return {
        "allocation_dispersion": float(path.std(axis=0).mean()),
        "share_meaningful_changes": float((change >= MEANINGFUL_CHANGE).mean()),
    }


def behaviour_metrics(
    ledger: pd.DataFrame,
    targets: np.ndarray,
    assets: Sequence[str],
    groups: Mapping[str, Sequence[str]],
) -> dict[str, float]:
    """Allocation behaviour of one episode: held and target weights, exposures, stability.

    ``allocation_stability_dw`` is ``D_w`` between consecutive decision targets (lower means
    more stable); held weights are the ledger's end-of-row weights. The E8 responsiveness
    measures (:func:`responsiveness`) are appended.
    """
    (path,) = _paths(targets)
    out: dict[str, float] = {}
    for column in [*assets, CASH]:
        out[f"mean_held_{column}"] = float(ledger[f"weight_{column}"].mean())
    held = ledger[[f"weight_{a}" for a in assets]].to_numpy(float)
    out["max_held_weight"] = float(held.max())
    out.update(exposures(path, assets, groups))
    out["allocation_stability_dw"] = (
        mean_abs_difference(path[1:], path[:-1]) if len(path) > 1 else float("nan")
    )
    out.update(responsiveness(path))
    return out


def sweep_profiles(points: int) -> list[tuple[str, float, np.ndarray]]:
    """One-at-a-time sweeps: each dimension at ``points`` values in [0, 1], others neutral."""
    if points < 2:
        raise ProfileAnalysisError("a sweep needs at least two points")
    rows = []
    for d, name in enumerate(PROFILE_DIMENSIONS):
        for value in np.linspace(0.0, 1.0, points):
            profile = np.full(PROFILE_SIZE, NEUTRAL_VALUE)
            profile[d] = value
            rows.append((name, float(value), validate_profile(profile)))
    return rows


def dimension_correlations(
    profiles: np.ndarray, outcomes: Mapping[str, Sequence[float]]
) -> list[dict[str, Any]]:
    """Rank correlation of each profile dimension with each outcome across profiles."""
    values = np.asarray(profiles, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != PROFILE_SIZE:
        raise ProfileAnalysisError(f"profiles must be (P, {PROFILE_SIZE}), got {values.shape}")
    rows = []
    for name, outcome in outcomes.items():
        if len(outcome) != len(values):
            raise ProfileAnalysisError(f"outcome {name!r} has {len(outcome)} values")
        for d, dimension in enumerate(PROFILE_DIMENSIONS):
            rows.append({"dimension": dimension, "outcome": name,
                         "spearman": rank_correlation(values[:, d], outcome)})  # fmt: skip
    return rows


def shuffled_partner(count: int) -> np.ndarray:
    """Deterministic derangement ``i -> (i + 1) mod count``: every profile gets another one."""
    if count < 2:
        raise ProfileAnalysisError("shuffling needs at least two profiles")
    return (np.arange(count) + 1) % count
