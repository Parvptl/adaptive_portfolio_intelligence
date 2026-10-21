"""Paired block-bootstrap uncertainty for Sharpe-ratio differences (milestone D; NumPy only).

All settings (method, block length, resamples, seed, confidence level, multiple-comparison
rule) are arguments; the values used for the test evaluation come from the frozen
pre-registration (Gate 3), not from this module.

* **Paired resampling:** one index sequence per resample is applied to *every* strategy's
  aligned daily return series, so cross-sectional dependence between strategies is kept.
* **Methods:** the stationary bootstrap (Politis and Romano, 1994; random block lengths with mean
  ``L``) and the circular block bootstrap (fixed length ``L``), both wrapping around the end; and
  the **moving-block bootstrap** (Kunsch, 1989; fixed length ``L``, **no wrapping**), the method
  of the Gate 3 protocol (D-083):

  - ``K = ceil(n / L)`` block starts ``s_1 .. s_K`` are drawn independently and uniformly from
    ``{0, 1, ..., n - L}`` (``rng.integers(0, n - L + 1)``), so every block lies inside the
    series;
  - the replicate's indices are ``s_1, s_1 + 1, ..., s_1 + L - 1, s_2, ..., s_K + L - 1``,
    truncated to the first ``n``; the replicate has exactly ``n`` rows;
  - one index vector per replicate is applied to every series (paired resampling).
* **Statistic:** ``delta_j = agg_s SR(policy_s) - SR(baseline_j)`` per resample, with
  ``SR = sqrt(N) * mean / std(ddof=1)`` (rf = 0) and ``agg`` the median (or mean) over seeds.
* **Intervals and tests:** percentile intervals; a two-sided bootstrap p-value
  ``min(1, (2 * min(#{d <= 0}, #{d >= 0}) + 1) / (B + 1))``; Holm or Bonferroni adjustment.

Limitations: the realised return series are resampled with the strategies' realised actions
fixed (the policy is not re-run); percentile intervals and bootstrap p-values are approximate,
especially for short series.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

METHODS = ("stationary_block_bootstrap", "circular_block_bootstrap", "moving_block_bootstrap")
AGGREGATIONS = ("median", "mean")
ADJUSTMENTS = ("holm", "bonferroni", "none")
CHUNK = 500


class UncertaintyError(ValueError):
    """Raised for invalid bootstrap inputs or undefined resampled statistics."""


def bootstrap_indices(
    n: int, block_length: int, size: int, method: str, rng: np.random.Generator
) -> np.ndarray:
    """``(size, n)`` resampled row indices for one method (wrapping circularly)."""
    if n < 2 or block_length < 1 or size < 1:
        raise UncertaintyError("need n >= 2, block_length >= 1 and size >= 1")
    positions = np.arange(n)
    if method == "stationary_block_bootstrap":
        starts = rng.integers(0, n, size=(size, n))
        new_block = rng.random((size, n)) < 1.0 / block_length
        new_block[:, 0] = True
        last_start = np.maximum.accumulate(np.where(new_block, positions, 0), axis=1)
        anchor = np.take_along_axis(starts, last_start, axis=1)
        return (anchor + positions - last_start) % n
    if method == "moving_block_bootstrap":
        if block_length > n:
            raise UncertaintyError("the moving-block bootstrap needs block_length <= n")
        blocks = -(-n // block_length)
        starts = rng.integers(0, n - block_length + 1, size=(size, blocks))
        return moving_block_indices_from_starts(starts, n, block_length)
    if method == "circular_block_bootstrap":
        blocks = -(-n // block_length)
        starts = rng.integers(0, n, size=(size, blocks))
        offsets = np.arange(block_length)
        rows = (starts[:, :, None] + offsets[None, None, :]).reshape(size, -1)[:, :n]
        return rows % n
    raise UncertaintyError(f"unknown method {method!r}; expected one of {METHODS}")


def moving_block_indices_from_starts(starts: np.ndarray, n: int, block_length: int) -> np.ndarray:
    """Indices of moving-block replicates from given block starts (no wrapping; length ``n``).

    ``starts`` is ``(replicates, ceil(n / block_length))`` with values in ``{0, ..., n - L}``.
    Separated from the random draw so that a hand-written example can check it exactly.
    """
    starts = np.asarray(starts)
    if starts.ndim != 2 or starts.shape[1] != -(-n // block_length):
        raise UncertaintyError("starts must be (replicates, ceil(n / block_length))")
    if starts.min(initial=0) < 0 or starts.max(initial=0) > n - block_length:
        raise UncertaintyError("block starts must lie in {0, ..., n - block_length}")
    offsets = np.arange(block_length)
    rows = (starts[:, :, None] + offsets[None, None, :]).reshape(len(starts), -1)
    return rows[:, :n]


def percentile_interval(
    point: float, draws: np.ndarray, confidence_level: float
) -> dict[str, float | str | int]:
    """Percentile interval of one bootstrap statistic. No p-value, no significance claim."""
    sample = np.asarray(draws, dtype=np.float64)
    if sample.ndim != 1 or len(sample) < 2 or not np.isfinite(sample).all():
        raise UncertaintyError("draws must be a finite vector of at least two replicates")
    if not np.isfinite(point):
        raise UncertaintyError("the point estimate is undefined")
    if not 0.5 < confidence_level < 1:
        raise UncertaintyError("confidence_level must be in (0.5, 1)")
    tail = (1 - confidence_level) / 2
    low, high = np.quantile(sample, [tail, 1 - tail])
    return {"estimate": float(point), "ci_low": float(low), "ci_high": float(high),
            "confidence_level": float(confidence_level),
            "interval_method": "percentile (numpy linear interpolation)",
            "replicates": len(sample)}  # fmt: skip


def annualised_sharpe(returns: np.ndarray, periods_per_year: float = 252.0) -> np.ndarray:
    """Sharpe along axis -2 (time) for arrays shaped ``(..., T, k)``; rf = 0, ddof 1."""
    std = returns.std(axis=-2, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.sqrt(periods_per_year) * returns.mean(axis=-2) / std


def sharpe_differences(
    returns: np.ndarray, n_policies: int, aggregation: str, periods_per_year: float = 252.0
) -> np.ndarray:
    """``agg`` of the policies' Sharpe minus each baseline's Sharpe; columns: policies first."""
    if aggregation not in AGGREGATIONS:
        raise UncertaintyError(f"aggregation must be one of {AGGREGATIONS}")
    sharpe = annualised_sharpe(returns, periods_per_year)
    policies, baselines = sharpe[..., :n_policies], sharpe[..., n_policies:]
    agg = np.median(policies, axis=-1) if aggregation == "median" else policies.mean(axis=-1)
    return agg[..., None] - baselines


def paired_bootstrap(
    returns: np.ndarray, n_policies: int, *, method: str, block_length: int, resamples: int,
    seed: int, aggregation: str = "median", periods_per_year: float = 252.0,
) -> tuple[np.ndarray, np.ndarray]:  # fmt: skip
    """Point estimates ``(m,)`` and resampled differences ``(resamples, m)``.

    ``returns`` is ``(T, k)``: the aligned daily net returns (funding row excluded) of
    ``n_policies`` policies followed by ``m = k - n_policies`` baselines. Deterministic in
    ``seed`` (NumPy PCG64) for the fixed :data:`CHUNK` size, which is part of the method:
    indices are drawn chunk by chunk, so a different chunk size gives different draws.
    """
    data = np.asarray(returns, dtype=np.float64)
    if data.ndim != 2 or not np.isfinite(data).all():
        raise UncertaintyError("returns must be a finite (T, k) matrix")
    if not 1 <= n_policies < data.shape[1]:
        raise UncertaintyError("need at least one policy and one baseline column")
    point = sharpe_differences(data, n_policies, aggregation, periods_per_year)
    if not np.isfinite(point).all():
        raise UncertaintyError("a point Sharpe is undefined (zero volatility)")
    rng = np.random.default_rng(seed)
    draws = []
    for start in range(0, resamples, CHUNK):
        size = min(CHUNK, resamples - start)
        index = bootstrap_indices(len(data), block_length, size, method, rng)
        draws.append(sharpe_differences(data[index], n_policies, aggregation, periods_per_year))
    out = np.concatenate(draws, axis=0)
    if not np.isfinite(out).all():
        raise UncertaintyError("a resampled Sharpe is undefined; the statistic is unstable")
    return point, out


def bootstrap_p_values(draws: np.ndarray) -> np.ndarray:
    """Two-sided bootstrap p-values for ``delta = 0`` per column."""
    below = (draws <= 0).sum(axis=0)
    above = (draws >= 0).sum(axis=0)
    return np.minimum(1.0, (2 * np.minimum(below, above) + 1) / (len(draws) + 1))


def adjust_p_values(p_values: Sequence[float], method: str) -> np.ndarray:
    """Holm (step-down) or Bonferroni adjusted p-values, or unadjusted for ``none``."""
    p = np.asarray(p_values, dtype=np.float64)
    if method == "none":
        return p.copy()
    if method == "bonferroni":
        return np.minimum(1.0, p * len(p))
    if method != "holm":
        raise UncertaintyError(f"unknown adjustment {method!r}")
    order = np.argsort(p, kind="stable")
    scaled = (len(p) - np.arange(len(p))) * p[order]
    adjusted = np.minimum(1.0, np.maximum.accumulate(scaled))
    out = np.empty_like(p)
    out[order] = adjusted
    return out


def summarise_comparisons(
    point: np.ndarray, draws: np.ndarray, baselines: Sequence[str], *, confidence_level: float,
    adjustment: str, familywise_alpha: float, minimum_difference: float | None = None,
) -> pd.DataFrame:  # fmt: skip
    """One row per baseline: estimate, percentile interval, p-values and the outcome label.

    Outcome: ``higher`` / ``lower`` when the adjusted p-value is at most ``familywise_alpha``
    (and, if given, ``|estimate| >= minimum_difference``), otherwise ``inconclusive``.
    ``inconclusive`` is not evidence of equality.
    """
    if not 0.5 < confidence_level < 1:
        raise UncertaintyError("confidence_level must be in (0.5, 1)")
    tail = (1 - confidence_level) / 2
    low, high = np.quantile(draws, [tail, 1 - tail], axis=0)
    raw = bootstrap_p_values(draws)
    adjusted = adjust_p_values(raw, adjustment)
    rows = []
    for j, name in enumerate(baselines):
        significant = adjusted[j] <= familywise_alpha
        large = minimum_difference is None or abs(point[j]) >= minimum_difference
        outcome = "inconclusive"
        if significant and large:
            outcome = "higher" if point[j] > 0 else "lower"
        rows.append({"baseline": name, "estimate": float(point[j]), "ci_low": float(low[j]),
                     "ci_high": float(high[j]), "confidence_level": confidence_level,
                     "p_value": float(raw[j]), "p_adjusted": float(adjusted[j]),
                     "adjustment": adjustment, "outcome": outcome})  # fmt: skip
    return pd.DataFrame.from_records(rows)
