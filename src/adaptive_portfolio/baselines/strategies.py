"""Conventional allocation baselines (decision D-053).

Each strategy is a pure function of the return history available at the decision
date (rows dated <= t) and returns long-only target weights over the universe, in
universe order. Any weight not allocated is implicit cash. No strategy uses regime
labels or features: the baselines must stay distinct from later regime-aware methods.

* ``equal_weight``      - 1/N in every asset.
* ``fixed_weights``     - configured weights (assets not listed get 0).
* ``inverse_volatility``- w_i ∝ 1 / sample std (ddof=1) of the last ``lookback``
  returns of asset i, then capped at ``max_weight`` with the excess redistributed
  proportionally among uncapped assets (water-filling). Zero volatility is an error,
  never silently replaced.

Rebalancing schedules (decision dates within an evaluation window):

* ``daily``   - every session;
* ``weekly``  - the first session of the window, then the first observed session of
  each new ISO week (ISO year and week, so a week spanning 31 December stays one week);
  the schedule of the PPO agent (D-065);
* ``monthly`` - the first session of the window, then the first observed session of
  each new calendar month (decided from past dates only);
* ``never``   - the first session of the window only (buy-and-hold).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from adaptive_portfolio.config import StrategyConfig
from adaptive_portfolio.evaluation.metrics import ZERO_VOLATILITY_TOLERANCE


class StrategyError(ValueError):
    """Raised when a strategy cannot produce valid weights."""


def cap_and_redistribute(raw: np.ndarray, max_weight: float) -> np.ndarray:
    """Scale ``raw`` to sum to 1, then cap at ``max_weight``, redistributing the excess.

    Iteratively fixes capped assets at ``max_weight`` and rescales the remaining ones
    in proportion to their raw weights. Requires ``max_weight * n >= 1``.
    """
    n = len(raw)
    if max_weight * n < 1 - 1e-12:
        raise StrategyError(f"max_weight {max_weight} x {n} assets < 1: cannot be fully invested")
    weights = raw / raw.sum()
    capped = np.zeros(n, dtype=bool)
    for _ in range(n):
        over = (weights > max_weight + 1e-15) & ~capped
        if not over.any():
            break
        capped |= over
        free = ~capped
        remaining = 1.0 - max_weight * capped.sum()
        weights = np.where(capped, max_weight, 0.0)
        if free.any():
            weights[free] = remaining * raw[free] / raw[free].sum()
    return weights


def target_weights(
    strategy: StrategyConfig,
    history: pd.DataFrame,
    universe: tuple[str, ...],
    max_weight: float,
) -> np.ndarray:
    """Target weights at a decision date from ``history`` (all rows dated <= that date)."""
    if list(history.columns) != list(universe):
        raise StrategyError(f"history columns {list(history.columns)} != universe {list(universe)}")
    if len(history) < strategy.min_history:
        raise StrategyError(
            f"{strategy.name}: needs {strategy.min_history} return rows of history, "
            f"got {len(history)}"
        )
    n = len(universe)
    if strategy.type == "equal_weight":
        return np.full(n, 1.0 / n)
    if strategy.type == "fixed_weights":
        configured = dict(strategy.weights or ())
        return np.array([configured.get(asset, 0.0) for asset in universe], dtype=np.float64)
    if strategy.type == "inverse_volatility":
        window = history.to_numpy(dtype=np.float64)[-strategy.lookback :]
        vols = np.std(window, axis=0, ddof=1)
        if (vols <= ZERO_VOLATILITY_TOLERANCE).any():
            zero = [universe[i] for i in np.flatnonzero(vols <= ZERO_VOLATILITY_TOLERANCE)]
            raise StrategyError(
                f"{strategy.name}: zero volatility for {zero} at {history.index[-1].date()}; "
                "inverse-volatility weights are undefined"
            )
        return cap_and_redistribute(1.0 / vols, max_weight)
    raise StrategyError(f"unknown strategy type {strategy.type!r}")


def decision_rows(schedule: str, dates: pd.DatetimeIndex, start: int, end: int) -> list[int]:
    """Positions in ``dates`` (within [start, end]) at which the strategy decides."""
    if start > end:
        return []
    if schedule == "never":
        return [start]
    if schedule == "daily":
        return list(range(start, end + 1))
    if schedule == "weekly":
        weeks = dates.isocalendar()
        keys = list(zip(weeks["year"].to_numpy(), weeks["week"].to_numpy(), strict=True))
        return [start] + [k for k in range(start + 1, end + 1) if keys[k] != keys[k - 1]]
    if schedule == "monthly":
        rows = [start]
        for k in range(start + 1, end + 1):
            if (dates[k].year, dates[k].month) != (dates[k - 1].year, dates[k - 1].month):
                rows.append(k)
        return rows
    raise StrategyError(f"unknown rebalance schedule {schedule!r}")
