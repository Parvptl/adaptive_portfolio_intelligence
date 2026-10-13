"""Backtesting, performance metrics and evaluation protocols.

Implemented (``metrics``): portfolio returns, cumulative return, annualised
return (CAGR), annualised volatility, Sharpe ratio, maximum drawdown and
two-way portfolio turnover. See docs/technical_handbook.md, section 10.

Planned: optional further metrics such as Sortino, Calmar and cost drag;
backtesting; chronological splits, out-of-sample testing; walk-forward
evaluation and stress testing where feasible.
See docs/architecture.md and docs/roadmap.md.
"""

from adaptive_portfolio.evaluation.metrics import (
    WEIGHT_SUM_TOLERANCE,
    ZERO_VOLATILITY_TOLERANCE,
    MaxDrawdown,
    UndefinedMetricError,
    annual_to_periodic_rate,
    annualized_return,
    annualized_turnover,
    annualized_volatility,
    cumulative_return,
    drawdown_series,
    max_drawdown,
    portfolio_returns,
    portfolio_turnover,
    sharpe_ratio,
)

__all__ = [
    "WEIGHT_SUM_TOLERANCE",
    "ZERO_VOLATILITY_TOLERANCE",
    "MaxDrawdown",
    "UndefinedMetricError",
    "annual_to_periodic_rate",
    "annualized_return",
    "annualized_turnover",
    "annualized_volatility",
    "cumulative_return",
    "drawdown_series",
    "max_drawdown",
    "portfolio_returns",
    "portfolio_turnover",
    "sharpe_ratio",
]
