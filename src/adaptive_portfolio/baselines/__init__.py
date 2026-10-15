"""Conventional allocation baselines (milestone 4).

Implemented (``strategies``): equal weight, fixed weights and inverse volatility,
with daily / monthly / never (buy-and-hold) rebalancing schedules. Weights use only
returns dated <= the decision date and never use regime information. All baselines
are evaluated by the same simulator (``adaptive_portfolio.evaluation.simulator``).
See docs/technical_handbook.md, section 13.

Not implemented (possible later, with team approval): minimum variance,
mean-variance, risk parity, momentum or volatility targeting.
"""

from adaptive_portfolio.baselines.strategies import (
    StrategyError,
    cap_and_redistribute,
    decision_rows,
    target_weights,
)

__all__ = ["StrategyError", "cap_and_redistribute", "decision_rows", "target_weights"]
