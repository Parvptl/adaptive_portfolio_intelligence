"""Descriptive risk measures from simulator ledgers (milestone D; NumPy and pandas only).

* :func:`concentration` - **cash convention:** concentration is measured on the risky sleeve
  (ETF weights rescaled to sum to 1; undefined when fully in cash), and the cash weight is
  reported separately. Also: the Herfindahl index of the whole portfolio including cash, the
  largest held ETF weight, and the share of executions with an ETF target at the cap.
* :func:`window_metrics` - a sub-window of a ledger (e.g. a pre-registered stress window):
  compounded net return, volatility, and the maximum drawdown measured from the value at the
  start of the window.
* :func:`gross_sharpe` - Sharpe of the gross returns on the same rows as the net Sharpe.
* :func:`stress_window` - the Gate 3 stress-window rule (D-083): returns of the sessions in
  ``(peak close, trough close]``, drawdown measured from the portfolio value at the peak close,
  and a check that the realised session count equals the pre-registered count. A missing peak
  or trough session, or a count mismatch, gives ``not computed`` with a diagnostic; the dates
  are never moved to force a match.
* :func:`allocation_summary` - time-averaged and maximum end-of-row weights per asset, cash and
  risky exposure, mean executed targets, and trade counts (all executions, and recurring ones
  excluding the funding execution).

Undefined values (e.g. concentration when fully in cash, volatility with fewer than two
sessions) are reported as NaN together with an explicit count or status; they are never
silently replaced by numbers.

Nothing here infers anything; the numbers describe one realised path.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from adaptive_portfolio.evaluation.metrics import UndefinedMetricError, sharpe_ratio

CAP_TOLERANCE = 1e-12


class RiskError(ValueError):
    """Raised for inconsistent ledgers or windows."""


def gross_sharpe(ledger: pd.DataFrame, periods_per_year: float = 252.0) -> float:
    """``sharpe_ratio`` of ``gross_return`` excluding the funding row (rf = 0, ddof 1).

    Returns NaN when the Sharpe ratio is undefined (zero variance); callers must report it
    as undefined, never as a number.
    """
    gross = ledger["gross_return"].to_numpy(dtype=np.float64)[1:]
    try:
        return float(sharpe_ratio(gross, periods_per_year, annual_risk_free_rate=0.0))
    except UndefinedMetricError:
        return float("nan")


def concentration(
    ledger: pd.DataFrame, executions: pd.DataFrame, max_weight: float
) -> dict[str, float]:
    """Concentration of end-of-row holdings and of executed targets (funding row included)."""
    weights = ledger.filter(like="weight_")
    if "weight_CASH" not in weights.columns or weights.shape[1] < 2:
        raise RiskError("ledger needs weight_<asset> columns and weight_CASH")
    cash = weights["weight_CASH"].to_numpy(dtype=np.float64)
    etf = weights.drop(columns="weight_CASH").to_numpy(dtype=np.float64)
    risky = etf.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        hhi = np.where(risky > 1e-12, ((etf / risky[:, None]) ** 2).sum(axis=1), np.nan)
    full = (weights.to_numpy(dtype=np.float64) ** 2).sum(axis=1)
    targets = executions.filter(like="target_").to_numpy(dtype=np.float64)
    at_cap = (targets >= max_weight - CAP_TOLERANCE).any(axis=1) if len(targets) else np.array([])
    defined = np.isfinite(hhi)
    return {
        "rows_without_risky_exposure": int((~defined).sum()),  # HHI undefined on these rows
        "mean_cash": float(cash.mean()),
        "mean_risky_hhi": float(np.nanmean(hhi)) if defined.any() else float("nan"),
        "max_risky_hhi": float(np.nanmax(hhi)) if defined.any() else float("nan"),
        "mean_effective_positions": float(np.nanmean(1.0 / hhi)) if defined.any() else float("nan"),
        "mean_hhi_including_cash": float(full.mean()),
        "max_held_etf_weight": float(etf.max()),
        "share_executions_at_cap": float(at_cap.mean()) if len(at_cap) else float("nan"),
    }


def window_metrics(
    ledger: pd.DataFrame, start: str, end: str, periods_per_year: float = 252.0
) -> dict[str, float]:
    """Metrics of the ledger rows dated in ``[start, end]`` (funding row excluded).

    The drawdown is measured from the portfolio value at the close before the window's first
    row, so it describes losses suffered *inside* the window only.
    """
    dates = pd.to_datetime(ledger["date"])
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if last < first:
        raise RiskError(f"window end {end} is before its start {start}")
    if first <= dates.iloc[0] or last > dates.iloc[-1]:
        raise RiskError(f"window {start}..{end} is not inside the ledger after its funding row")
    inside = ((dates >= first) & (dates <= last)).to_numpy()
    if inside.sum() < 2:
        raise RiskError(f"window {start}..{end} holds fewer than 2 sessions")
    net = ledger["net_return"].to_numpy(dtype=np.float64)[inside]
    value = ledger["value"].to_numpy(dtype=np.float64)
    before = value[np.argmax(inside) - 1]
    path = value[inside] / before
    peak = np.maximum.accumulate(np.r_[1.0, path])[1:]
    return {
        "sessions": int(inside.sum()),
        "first_date": str(dates[inside].iloc[0].date()),
        "last_date": str(dates[inside].iloc[-1].date()),
        "net_return": float(path[-1] - 1.0),
        "max_drawdown": float((path / peak - 1.0).min()),
        "annualised_volatility": float(net.std(ddof=1) * np.sqrt(periods_per_year)),
        "worst_day": float(net.min()),
    }


def stress_window(
    ledger: pd.DataFrame,
    peak_close: str,
    trough_close: str,
    expected_sessions: int,
    periods_per_year: float = 252.0,
) -> dict[str, object]:
    """Metrics of the sessions in ``(peak_close, trough_close]`` (Gate 3 stress rule, D-083).

    The window's value path starts at the portfolio value at the close of ``peak_close``; the
    drawdown is measured from there. Returns ``status`` ``computed`` or ``not computed: ...``.
    """
    peak, trough = pd.Timestamp(peak_close), pd.Timestamp(trough_close)
    if trough <= peak:
        raise RiskError(f"trough {trough_close} must be after peak {peak_close}")
    base: dict[str, object] = {"peak_close": peak_close, "trough_close": trough_close,
                               "expected_sessions": int(expected_sessions)}  # fmt: skip
    dates = pd.DatetimeIndex(pd.to_datetime(ledger["date"]))
    at_peak = np.flatnonzero(dates == peak)
    if len(at_peak) != 1:
        return {**base, "status": f"not computed: the peak close {peak_close} is not a session "
                f"of this ledger (dates are never moved)"}  # fmt: skip
    if not (dates == trough).any():
        return {**base, "status": f"not computed: the trough close {trough_close} is not a "
                f"session of this ledger (dates are never moved)"}  # fmt: skip
    inside = np.asarray((dates > peak) & (dates <= trough))
    sessions = int(inside.sum())
    base["realised_sessions"] = sessions
    if sessions != int(expected_sessions):
        return {**base, "status": f"not computed: {sessions} sessions in (peak, trough], "
                f"pre-registered {expected_sessions}"}  # fmt: skip
    if sessions < 2:
        return {**base, "status": "not computed: fewer than 2 sessions (volatility undefined)"}
    value = ledger["value"].to_numpy(dtype=np.float64)
    net = ledger["net_return"].to_numpy(dtype=np.float64)[inside]
    path = value[inside] / value[at_peak[0]]
    running = np.maximum.accumulate(np.r_[1.0, path])[1:]
    return {
        **base,
        "status": "computed",
        "first_session": str(dates[inside][0].date()),
        "last_session": str(dates[inside][-1].date()),
        "net_return": float(path[-1] - 1.0),
        "max_drawdown": float((path / running - 1.0).min()),
        "annualised_volatility": float(net.std(ddof=1) * np.sqrt(periods_per_year)),
        "worst_day": float(net.min()),
    }


def allocation_summary(ledger: pd.DataFrame, executions: pd.DataFrame) -> dict[str, float]:
    """Time-averaged and maximum end-of-row weights, risky exposure, mean targets, trade counts.

    Weights are end-of-row weights on every ledger row (funding row included). ``executions``
    are the executed targets (``target_<asset>``), funding execution first.
    """
    weights = ledger.filter(like="weight_")
    if "weight_CASH" not in weights.columns:
        raise RiskError("ledger needs weight_CASH")
    out: dict[str, float] = {
        "executions_total": len(executions),
        "executions_recurring": int(max(len(executions) - 1, 0)),
        "mean_risky_exposure": float(1.0 - weights["weight_CASH"].mean()),
    }
    for column in weights.columns:
        asset = column.removeprefix("weight_")
        out[f"mean_weight_{asset}"] = float(weights[column].mean())
        out[f"max_weight_{asset}"] = float(weights[column].max())
        target = executions.get(f"target_{asset}")
        if target is not None:
            out[f"mean_target_{asset}"] = float(target.mean())
    return out
