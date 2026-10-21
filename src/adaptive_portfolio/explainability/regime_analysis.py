"""Regime-conditioned description of a strategy's ledger (milestone E; observational only).

Every ledger row after the funding row is assigned the regime label that was **known when its
holdings were set**: the label of the session ``lag`` rows earlier in the regime calendar. With
lag 1 this is the decision date of a trade executed on that row, and the close at which the
holdings earning that row's return were fixed. No label from the row's own close is used.

For each of the nine trend/volatility regimes and the warm-up label ``unavailable`` (always
reported, also when absent), the summary gives:

* sample size: sessions, share of sessions, number of contiguous episodes, and a flag
  ``sufficient`` (``sessions >= min_sessions``);
* allocation: mean end-of-row weight per asset and cash, mean risky exposure (1 - cash), mean
  concentration of the risky sleeve (Herfindahl index of the ETF weights rescaled to sum to 1)
  and mean largest ETF weight;
* trading: recurring traded notional (ETF legs, funding excluded) in total, per session and
  annualised (x ``periods_per_year``), and the number of executions;
* realised risk: mean daily net return, annualised volatility (``ddof=1``), share of negative
  days and worst day;
* path drawdown (when the ledger has ``value``): the mean and the deepest level of the whole
  window's net drawdown (value / running peak - 1, peak starting at the initial capital) on the
  rows in the regime. This is the drawdown **level observed while in the regime**, not a loss
  caused by, or confined to, that regime.

Dates: a row's label is the label of its *decision / information* date (``t - lag``); its
return accrues on ``t``; a trade on an execution row ``t`` was decided at ``t - lag``.

These are **associations between labels and outcomes on one historical path**. They are not
effects of the regime, they carry no confidence intervals, and comparisons between regimes are
not statistically supported. Volatility regimes are defined from trailing market volatility, so
realised volatility by volatility regime is partly mechanical (confounded by construction).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from adaptive_portfolio.regimes.rules import REGIME_LABELS, UNAVAILABLE

REGIME_ORDER: tuple[str, ...] = (*REGIME_LABELS, UNAVAILABLE)
ALL = "all"
DEFAULT_MIN_SESSIONS = 63  # about one quarter of sessions; below it a summary is flagged
LIMITATIONS = (
    "Observational: labels and outcomes are associated on one historical path; no causal claim.",
    "No confidence intervals; differences between regimes are not statistically tested.",
    "Regimes with few sessions or few episodes are dominated by a handful of market events.",
    "Volatility regimes come from trailing market volatility, so realised volatility by "
    "volatility regime is partly mechanical.",
    "Regime thresholds are relative to the training period (D-045, Proposed/provisional).",
)


class RegimeAnalysisError(ValueError):
    """Raised for inconsistent ledgers or regime labels."""


def regime_episodes(labels: Sequence[str]) -> dict[str, int]:
    """Number of contiguous runs of each label, in :data:`REGIME_ORDER` (zero if absent)."""
    counts = dict.fromkeys(REGIME_ORDER, 0)
    previous = None
    for label in labels:
        if label not in counts:
            raise RegimeAnalysisError(f"unknown regime label {label!r}")
        if label != previous:
            counts[label] += 1
        previous = label
    return counts


def label_ledger_rows(dates: pd.DatetimeIndex, regimes: pd.Series, lag: int) -> pd.Series:
    """Regime label known when each row's holdings were set: the label ``lag`` sessions earlier.

    ``regimes`` is indexed by the full session calendar (dates before the ledger included).
    """
    if lag < 1:
        raise RegimeAnalysisError("lag must be >= 1 so that labels precede the returns they label")
    calendar = pd.DatetimeIndex(regimes.index)
    if not calendar.is_monotonic_increasing or calendar.has_duplicates:
        raise RegimeAnalysisError("regime dates must be strictly increasing")
    positions = calendar.get_indexer(pd.DatetimeIndex(dates))
    if (positions < 0).any():
        missing = pd.DatetimeIndex(dates)[positions < 0][:3]
        raise RegimeAnalysisError(f"ledger dates missing from the regime calendar: {list(missing)}")
    if (positions - lag < 0).any():
        raise RegimeAnalysisError("the regime calendar must start at least `lag` rows earlier")
    labels = regimes.to_numpy(dtype=object)[positions - lag]
    unknown = sorted(set(labels) - set(REGIME_ORDER))
    if unknown:
        raise RegimeAnalysisError(f"unknown regime labels {unknown}")
    return pd.Series(labels, index=pd.DatetimeIndex(dates), name="regime")


def _risky_hhi(weights: np.ndarray) -> np.ndarray:
    """Herfindahl index of the ETF weights rescaled to sum to 1 (NaN when fully in cash)."""
    total = weights.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        shares = weights / total[:, None]
        hhi = (shares**2).sum(axis=1)
    return np.where(total > 1e-12, hhi, np.nan)


def _path_drawdown(ledger: pd.DataFrame) -> np.ndarray:
    """Net drawdown of the window's value path from the initial capital (NaN without value)."""
    if "value" not in ledger.columns:
        return np.full(len(ledger), np.nan)
    value = ledger["value"].to_numpy(dtype=np.float64)
    initial = value[0] / (1.0 + float(ledger["net_return"].iloc[0]))  # before the funding cost
    peak = np.maximum.accumulate(np.r_[initial, value])[1:]
    return value / peak - 1.0


def _block(rows: pd.DataFrame, assets: Sequence[str], periods_per_year: int) -> dict[str, float]:
    n = len(rows)
    out: dict[str, float] = {}
    etf = rows[[f"weight_{a}" for a in assets]].to_numpy(dtype=np.float64)
    cash = rows["weight_CASH"].to_numpy(dtype=np.float64)
    for asset in (*assets, "CASH"):
        out[f"mean_weight_{asset}"] = float(rows[f"weight_{asset}"].mean()) if n else np.nan
    out["mean_risky_exposure"] = float(1.0 - cash.mean()) if n else np.nan
    hhi = _risky_hhi(etf) if n else np.array([])
    out["mean_risky_hhi"] = float(np.nanmean(hhi)) if n and np.isfinite(hhi).any() else np.nan
    out["mean_max_etf_weight"] = float(etf.max(axis=1).mean()) if n else np.nan
    traded = rows["traded_notional"].to_numpy(dtype=np.float64)
    out["traded_notional"] = float(traded.sum())
    out["traded_per_session"] = float(traded.mean()) if n else np.nan
    out["annualised_turnover"] = out["traded_per_session"] * periods_per_year if n else np.nan
    out["executions"] = int((traded > 0).sum())
    net = rows["net_return"].to_numpy(dtype=np.float64)
    out["mean_daily_net_return"] = float(net.mean()) if n else np.nan
    out["annualised_volatility"] = (
        float(net.std(ddof=1) * np.sqrt(periods_per_year)) if n >= 2 else np.nan
    )
    out["share_negative_days"] = float((net < 0).mean()) if n else np.nan
    out["worst_day"] = float(net.min()) if n else np.nan
    drawdown = rows["path_drawdown"].to_numpy(dtype=np.float64)
    out["mean_path_drawdown"] = float(drawdown.mean()) if n else np.nan
    out["deepest_path_drawdown"] = float(drawdown.min()) if n else np.nan
    return out


def regime_conditioned_summary(
    ledger: pd.DataFrame,
    regimes: pd.Series,
    *,
    lag: int = 1,
    min_sessions: int = DEFAULT_MIN_SESSIONS,
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """One row per regime in :data:`REGIME_ORDER` plus ``all``, for one strategy's ledger.

    ``ledger`` is one strategy's simulator ledger in date order; its first row is the funding
    execution and is excluded (D-059). ``regimes`` maps every calendar session (including the
    ``lag`` sessions before the first analysed row) to its label.
    """
    required = {"date", "net_return", "traded_notional", "weight_CASH"}
    if missing := required - set(ledger.columns):
        raise RegimeAnalysisError(f"ledger lacks columns {sorted(missing)}")
    if len(ledger) < 2:
        raise RegimeAnalysisError("a ledger needs the funding row and at least one more row")
    dates = pd.DatetimeIndex(pd.to_datetime(ledger["date"]))
    if not dates.is_monotonic_increasing or dates.has_duplicates:
        raise RegimeAnalysisError("ledger dates must be strictly increasing (one strategy)")
    if min_sessions < 1:
        raise RegimeAnalysisError("min_sessions must be >= 1")
    assets = [c.removeprefix("weight_") for c in ledger.columns if c.startswith("weight_")]
    assets = [a for a in assets if a != "CASH"]
    rows = ledger.iloc[1:].reset_index(drop=True).copy()
    rows["path_drawdown"] = _path_drawdown(ledger)[1:]
    labels = label_ledger_rows(dates[1:], regimes, lag).to_numpy(dtype=object)
    episodes = regime_episodes(labels)
    total = len(rows)
    records = []
    for regime in (*REGIME_ORDER, ALL):
        mask = np.ones(total, bool) if regime == ALL else labels == regime
        sessions = int(mask.sum())
        records.append({
            "regime": regime,
            "sessions": sessions,
            "share_of_sessions": sessions / total,
            "episodes": sum(episodes.values()) if regime == ALL else episodes[regime],
            "sufficient": sessions >= min_sessions,
            **_block(rows[mask], assets, periods_per_year),
        })  # fmt: skip
    return pd.DataFrame.from_records(records)


def summarise_strategies(
    ledgers: pd.DataFrame,
    regimes: pd.Series,
    *,
    lag: int = 1,
    min_sessions: int = DEFAULT_MIN_SESSIONS,
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """:func:`regime_conditioned_summary` for every ``strategy`` in a stacked ledger table."""
    if "strategy" not in ledgers.columns:
        raise RegimeAnalysisError("stacked ledgers need a 'strategy' column")
    frames = []
    for name, group in ledgers.groupby("strategy", sort=True):
        summary = regime_conditioned_summary(
            group.sort_values("date"), regimes, lag=lag, min_sessions=min_sessions,
            periods_per_year=periods_per_year,
        )  # fmt: skip
        frames.append(summary.assign(strategy=name))
    out = pd.concat(frames, ignore_index=True)
    return out[["strategy", *[c for c in out.columns if c != "strategy"]]]
