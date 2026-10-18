"""Performance summary of one simulated window, reusing the milestone-1 metrics (D-052).

Always reported (no annualisation needed):

* gross and net cumulative return (``cumulative_return`` on the value paths);
* gross and net maximum drawdown (``max_drawdown``, starting from initial capital);
* per-session volatility of net returns (``annualized_volatility`` with
  ``periods_per_year=1``, i.e. *not* annualised);
* per-session Sharpe ratio of net returns, only when the configured annual risk-free
  rate is 0 (then the periodic rate is 0 whatever the annualisation factor);
* traded notional (cost basis), two-way turnover, number of rebalances, total cost.
  The initial funding trade (ledger row 0, cash -> first target) is also reported on its
  own (``funding_traded_notional``); ``recurring_traded_notional`` excludes it.

Only when ``periods_per_year`` is configured (D-023 is open, so the default is ``null``):
annualised return, volatility, Sharpe and *recurring* traded-notional turnover (the
one-off funding trade is excluded, so it does not inflate a per-year rate). These remain
provisional. Undefined values (e.g. zero volatility) are reported as ``None`` with the
reason, never as infinity.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.evaluation.metrics import (
    UndefinedMetricError,
    annualized_return,
    annualized_turnover,
    annualized_volatility,
    cumulative_return,
    max_drawdown,
    sharpe_ratio,
)


def _maybe(func, *args, **kwargs) -> tuple[float | None, str | None]:
    try:
        return float(func(*args, **kwargs)), None
    except UndefinedMetricError as exc:
        return None, str(exc)


def summarize_window(
    ledger: pd.DataFrame,
    *,
    initial_capital: float,
    annual_risk_free_rate: float,
    periods_per_year: float | None,
) -> dict[str, Any]:
    """Metrics for one strategy over one evaluation window (deterministic)."""
    if len(ledger) < 3:
        raise ValueError("a window needs at least 3 ledger rows (funding + 2 returns)")
    net = ledger["net_return"].to_numpy(dtype=np.float64)
    gross = ledger["gross_return"].to_numpy(dtype=np.float64)
    net_path = np.r_[initial_capital, ledger["value"].to_numpy(dtype=np.float64)]
    gross_path = initial_capital * np.r_[1.0, np.cumprod(1.0 + gross)]
    # Earning rows exclude the funding row (which has no market exposure).
    earning_net = net[1:]
    rebalances = ledger.loc[ledger["rebalanced"], "traded_notional"].to_numpy(dtype=np.float64)
    # Row 0 is always the funding execution (cash -> first target); later executions recur.
    traded = ledger["traded_notional"].to_numpy(dtype=np.float64)
    recurring = traded[1:][ledger["rebalanced"].to_numpy()[1:]]

    net_mdd = max_drawdown(net_path)
    gross_mdd = max_drawdown(gross_path)
    vol_session = float(annualized_volatility(earning_net, 1))
    summary: dict[str, Any] = {
        "first_date": ledger["date"].iloc[0].date().isoformat(),
        "last_date": ledger["date"].iloc[-1].date().isoformat(),
        "ledger_rows": len(ledger),
        "return_periods": len(ledger) - 1,
        "rebalances": int(ledger["rebalanced"].sum()),
        "gross_cumulative_return": cumulative_return(gross_path),
        "net_cumulative_return": cumulative_return(net_path),
        "cost_drag": cumulative_return(gross_path) - cumulative_return(net_path),
        "gross_max_drawdown": gross_mdd.max_drawdown,
        "net_max_drawdown": net_mdd.max_drawdown,
        "net_max_drawdown_peak_date": ledger["date"]
        .iloc[max(net_mdd.peak_index - 1, 0)]
        .date()
        .isoformat(),
        "net_max_drawdown_trough_date": ledger["date"]
        .iloc[max(net_mdd.trough_index - 1, 0)]
        .date()
        .isoformat(),
        "net_volatility_per_session": vol_session,
        "total_traded_notional": float(rebalances.sum()),
        "funding_traded_notional": float(traded[0]),
        "recurring_traded_notional": float(recurring.sum()),
        "mean_traded_notional_per_rebalance": float(rebalances.mean()) if len(rebalances) else 0.0,
        "total_two_way_turnover": float(ledger["turnover_two_way"].sum()),
        "total_cost_fraction": float(ledger["cost_fraction"].sum()),
        "total_cost_value": float(ledger["cost_value"].sum()),
        "final_value": float(net_path[-1]),
    }
    notes = []
    if annual_risk_free_rate == 0:
        value, reason = _maybe(sharpe_ratio, earning_net, 1)
        summary["net_sharpe_per_session_rf0"] = value
        if reason:
            notes.append(f"per-session Sharpe undefined: {reason}")
    else:
        summary["net_sharpe_per_session_rf0"] = None
        notes.append("per-session Sharpe omitted: non-zero risk-free rate needs D-023")

    if periods_per_year is None:
        summary["annualised"] = None
        notes.append("annualised metrics omitted: periods_per_year is not set (D-023 open)")
    else:
        sharpe, reason = _maybe(
            sharpe_ratio,
            earning_net,
            periods_per_year,
            annual_risk_free_rate=annual_risk_free_rate,
        )
        if reason:
            notes.append(f"annualised Sharpe undefined: {reason}")
        summary["annualised"] = {
            "periods_per_year": periods_per_year,
            "status": "provisional (D-023 not accepted)",
            "net_annualised_return": annualized_return(net_path, periods_per_year),
            "gross_annualised_return": annualized_return(gross_path, periods_per_year),
            "net_annualised_volatility": annualized_volatility(earning_net, periods_per_year),
            "net_sharpe": sharpe,
            # Recurring trades only: the one-off funding trade is reported separately.
            "annualised_traded_notional": annualized_turnover(
                recurring, len(ledger) - 1, periods_per_year
            ),
        }
    summary["notes"] = notes
    return summary
