"""Permutation sensitivity of a policy's decided targets to observation input groups (D-068).

For a fixed set of decision observations, the inputs of one group (a feature family, the nine
regime one-hot inputs, or the eight portfolio-weight inputs) are permuted **jointly across
decisions**, so each permuted row keeps a realistic within-group combination. The policy's
deterministic action is then mapped to target weights with the project's own action mapping
(D-072 scaling and the D-063 capped softmax), and the change is measured as the L1 distance
between the original and the perturbed targets (cash included; range 0 to 2).

What this measures:

* **sensitivity of decisions**, one step at a time: the portfolio-weight inputs are taken as
  given and no rollout is re-simulated;
* not importance for returns or risk, and **not a causal effect** of the input on outcomes.
  Permuting one group breaks its correlation with the others, so perturbed observations can lie
  outside the training distribution.

Repeats use independent, seeded permutations; the spread across repeats is Monte Carlo noise of
the permutation, not market uncertainty.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from adaptive_portfolio.environment.actions import policy_action_to_logits, project_action
from adaptive_portfolio.regimes.rules import REGIME_LABELS

Policy = Callable[[np.ndarray], np.ndarray]  # (n, d) observations -> (n, n_assets + 1) actions
REGIME_GROUP = "regime_inputs"
WEIGHT_GROUP = "portfolio_weights"
LIMITATIONS = (
    "Sensitivity of the decided targets, not importance for returns or risk; not causal.",
    "One-step: portfolio-weight inputs are held as observed; no rollout is re-simulated.",
    "Permuting a group breaks its correlation with other inputs (out-of-distribution rows).",
    "Repeat spread is permutation noise only; results describe these decisions and checkpoints.",
)


class SensitivityError(ValueError):
    """Raised for inconsistent observations, groups or policy outputs."""


def observation_groups(
    feature_columns: Sequence[str], families: Mapping[str, str], n_assets: int
) -> dict[str, list[int]]:
    """Column indices of each input group in the D-062 observation layout.

    Layout: scaled features (``feature_columns`` order), the nine regime one-hot inputs, then
    ``n_assets + 1`` end-of-row weights (cash last). Feature groups are the recorded families.
    """
    groups: dict[str, list[int]] = {}
    for index, column in enumerate(feature_columns):
        if column not in families:
            raise SensitivityError(f"feature {column!r} has no recorded family")
        groups.setdefault(families[column], []).append(index)
    start = len(feature_columns)
    groups[REGIME_GROUP] = list(range(start, start + len(REGIME_LABELS)))
    start += len(REGIME_LABELS)
    groups[WEIGHT_GROUP] = list(range(start, start + n_assets + 1))
    return groups


def decided_targets(policy: Policy, observations: np.ndarray, max_weight: float) -> np.ndarray:
    """Target weights (assets then cash) from the policy's deterministic actions."""
    actions = np.asarray(policy(observations), dtype=np.float64)
    if actions.ndim != 2 or actions.shape[0] != observations.shape[0]:
        raise SensitivityError(f"policy returned shape {actions.shape} for {observations.shape}")
    rows = []
    for action in actions:
        target = project_action(policy_action_to_logits(action), max_weight)
        rows.append(np.append(target, 1.0 - target.sum()))
    return np.vstack(rows)


def _seed(seed: int, group: str, repeat: int) -> np.random.Generator:
    # A stable per-(group, repeat) stream: results do not depend on the order of the groups.
    return np.random.default_rng([seed, zlib.crc32(group.encode("utf-8")), repeat])


def permutation_sensitivity(
    policy: Policy,
    observations: np.ndarray,
    groups: Mapping[str, Sequence[int]],
    *,
    max_weight: float,
    asset_names: Sequence[str],
    repeats: int = 20,
    seed: int = 0,
) -> pd.DataFrame:
    """Mean L1 change of the decided targets when each group is permuted across decisions."""
    obs = np.asarray(observations, dtype=np.float32)
    if obs.ndim != 2 or len(obs) < 2 or not np.isfinite(obs).all():
        raise SensitivityError("observations must be a finite (n >= 2, d) matrix")
    if repeats < 2:
        raise SensitivityError("repeats must be >= 2 so that the repeat spread is defined")
    width = obs.shape[1]
    for name, columns in groups.items():
        if not columns or min(columns) < 0 or max(columns) >= width:
            raise SensitivityError(f"group {name!r} has invalid columns")
    base = decided_targets(policy, obs, max_weight)
    if base.shape[1] != len(asset_names) + 1:
        raise SensitivityError("asset_names must list the non-cash assets in target order")
    labels = [*asset_names, "CASH"]
    records = []
    for name, columns in groups.items():
        cols = np.asarray(columns, dtype=int)
        scores, per_asset = [], []
        for repeat in range(repeats):
            order = _seed(seed, name, repeat).permutation(len(obs))
            perturbed = obs.copy()
            perturbed[:, cols] = obs[order][:, cols]
            change = np.abs(decided_targets(policy, perturbed, max_weight) - base)
            scores.append(change.sum(axis=1).mean())
            per_asset.append(change.mean(axis=0))
        scores_arr = np.asarray(scores)
        records.append({
            "group": name,
            "n_inputs": len(cols),
            "decisions": len(obs),
            "repeats": repeats,
            "mean_l1_change": float(scores_arr.mean()),
            "std_l1_change": float(scores_arr.std(ddof=1)),
            "min_l1_change": float(scores_arr.min()),
            "max_l1_change": float(scores_arr.max()),
            **{f"mean_abs_change_{a}": float(v)
               for a, v in zip(labels, np.mean(per_asset, axis=0), strict=True)},
        })  # fmt: skip
    return pd.DataFrame.from_records(records)
