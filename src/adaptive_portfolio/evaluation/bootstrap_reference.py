"""Reference (slow, loop-based) moving-block bootstrap for independent verification (D-083).

This module re-derives the Gate 3 primary bootstrap statistic **without** using the vectorised
code in :mod:`adaptive_portfolio.evaluation.uncertainty`. It shares only the documented random
number convention, which is needed to reproduce the same replicates:

* NumPy ``default_rng(seed)``; replicates drawn in chunks of ``chunk`` (500);
* per chunk, block starts ``rng.integers(0, n - L + 1, size=(chunk_size, ceil(n / L)))``.

Per replicate it builds the index list block by block in plain Python, then computes each
series' Sharpe as ``sqrt(N) * mean / sqrt(sum((x - mean)^2) / (n - 1))`` and the statistic as
``median(policy Sharpes) - Sharpe(comparator)`` with :func:`statistics.median`.

It is a verification path written by the same author as the main implementation: agreement
shows internal consistency, not independent human review.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

import numpy as np


def _sharpe(values: Sequence[float], periods_per_year: float) -> float:
    n = len(values)
    mean = math.fsum(values) / n
    variance = math.fsum((v - mean) ** 2 for v in values) / (n - 1)
    if variance <= 0:
        raise ValueError("zero variance: Sharpe undefined")
    return math.sqrt(periods_per_year) * mean / math.sqrt(variance)


def reference_moving_block_draws(
    policy_returns: Sequence[Sequence[float]],
    comparator_returns: Sequence[float],
    *,
    block_length: int,
    resamples: int,
    seed: int,
    chunk: int = 500,
    periods_per_year: float = 252.0,
) -> list[float]:
    """Replicates of ``median_s SR(policy_s) - SR(comparator)`` under the moving-block rule."""
    series = [list(map(float, s)) for s in policy_returns]
    comparator = list(map(float, comparator_returns))
    n = len(comparator)
    if any(len(s) != n for s in series) or not series:
        raise ValueError("all series must share one length")
    if not 1 <= block_length <= n:
        raise ValueError("block_length must be in [1, n]")
    blocks = -(-n // block_length)
    rng = np.random.default_rng(seed)
    out: list[float] = []
    done = 0
    while done < resamples:
        size = min(chunk, resamples - done)
        starts = rng.integers(0, n - block_length + 1, size=(size, blocks))
        for row in starts:
            index: list[int] = []
            for start in row.tolist():
                index.extend(range(start, start + block_length))
            index = index[:n]
            sharpes = [_sharpe([s[i] for i in index], periods_per_year) for s in series]
            out.append(
                statistics.median(sharpes)
                - _sharpe([comparator[i] for i in index], periods_per_year)
            )
        done += size
    return out
