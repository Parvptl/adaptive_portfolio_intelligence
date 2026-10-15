"""Causal, interpretable market features computed from processed simple returns.

Timing convention (decision D-043; docs/technical_handbook.md section 12):

* Input rows are the processed ``returns.csv`` rows. The row dated ``t`` holds
  ``r_t = P_t / P_prev - 1``, which is known at the close of ``t``.
* A feature dated ``t`` uses only rows dated ``<= t`` (a trailing window that ends at
  ``t``). It never uses ``r_{t+1}``, the outcome of a decision taken at the close of ``t``.
* Windows are counted in return observations (rows), not calendar days. A feature with
  window ``w`` needs ``w`` rows of history *including* ``t``; earlier rows are ``NaN``
  (warm-up). Nothing is filled, back-filled or normalised with full-sample statistics.
* Only returns and ratios of returns are used, never adjusted price *levels*.
  Back-adjusted levels depend on dividends paid after ``t``; return ratios do not.
* Volatilities are sample standard deviations (``ddof=1``) of per-session returns and
  are **not annualised** (D-023 is open). Values at or below
  :data:`~adaptive_portfolio.evaluation.metrics.ZERO_VOLATILITY_TOLERANCE` are snapped
  to exactly 0, as in milestone 1.

Every rolling statistic is computed independently for each window with NumPy (two-pass,
no running sums). A window ending at ``t`` therefore cannot be affected by any row after
``t``, which the leakage tests check directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from adaptive_portfolio.config import FeatureConfig
from adaptive_portfolio.evaluation.metrics import ZERO_VOLATILITY_TOLERANCE

FAMILIES = ("return_momentum", "volatility_risk", "cross_asset", "universe_context")


class FeatureDataError(ValueError):
    """Raised when the input returns violate the feature pipeline's data contract."""


@dataclass(frozen=True)
class FeatureDefinition:
    """Self-describing metadata for one feature column."""

    name: str
    family: str
    formula: str
    inputs: tuple[str, ...]
    window: int
    min_history: int  # return rows needed, including the row at t
    interpretation: str

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["inputs"] = list(self.inputs)
        data["timestamp"] = "known at the close of the row date t; uses rows dated <= t"
        data["missing_values"] = (
            f"NaN for the first {self.min_history - 1} row(s) (warm-up); never filled"
            if self.min_history > 1
            else "never missing for valid input"
        )
        return data


@dataclass(frozen=True)
class FeatureSet:
    frame: pd.DataFrame  # index: DatetimeIndex "date"; columns: feature names
    definitions: tuple[FeatureDefinition, ...]


# --------------------------------------------------------------------------
# Rolling primitives (1-D arrays in chronological order; NaN during warm-up)
# --------------------------------------------------------------------------


def _rolling(
    values: np.ndarray, window: int, func: Callable[[np.ndarray], np.ndarray]
) -> np.ndarray:
    """Apply ``func`` to every trailing window (shape (n_windows, window)), row-wise."""
    out = np.full(len(values), np.nan)
    if len(values) >= window:
        out[window - 1 :] = func(sliding_window_view(values, window))
    return out


def _snap_zero(values: np.ndarray) -> np.ndarray:
    return np.where(np.abs(values) <= ZERO_VOLATILITY_TOLERANCE, 0.0, values)


def compound_return(returns: np.ndarray, window: int) -> np.ndarray:
    """``prod(1 + r_{t-w+1..t}) - 1`` (momentum), via expm1(sum(log1p)) for precision."""
    return _rolling(returns, window, lambda w: np.expm1(np.log1p(w).sum(axis=1)))


def rolling_volatility(returns: np.ndarray, window: int) -> np.ndarray:
    """Sample standard deviation (ddof=1) of the last ``window`` returns; not annualised."""
    return _rolling(returns, window, lambda w: _snap_zero(np.std(w, axis=1, ddof=1)))


def downside_volatility(returns: np.ndarray, window: int) -> np.ndarray:
    """``sqrt(mean(min(r, 0)^2))`` over the window: root-mean-square of losses (target 0)."""
    return _rolling(
        returns, window, lambda w: _snap_zero(np.sqrt(np.mean(np.minimum(w, 0.0) ** 2, axis=1)))
    )


def rolling_drawdown(returns: np.ndarray, window: int) -> np.ndarray:
    """Drawdown at ``t`` from the highest level reached within the last ``window`` returns.

    The window's wealth path starts at 1 (the level just before its first return):
    ``W_k = prod_{j<=k}(1 + r_j)``; ``D_t = W_end / max(1, max_k W_k) - 1`` (<= 0).
    """

    def drawdown(windows: np.ndarray) -> np.ndarray:
        wealth = np.cumprod(1.0 + windows, axis=1)
        peak = np.maximum(1.0, wealth.max(axis=1))
        return np.minimum(wealth[:, -1] / peak - 1.0, 0.0)

    return _rolling(returns, window, drawdown)


def rolling_correlation(a: np.ndarray, b: np.ndarray, window: int) -> np.ndarray:
    """Pearson correlation over the window; NaN where either series has zero variance."""
    out = np.full(len(a), np.nan)
    if len(a) < window:
        return out
    wa = sliding_window_view(a, window)
    wb = sliding_window_view(b, window)
    da = wa - wa.mean(axis=1, keepdims=True)
    db = wb - wb.mean(axis=1, keepdims=True)
    var_a = (da**2).sum(axis=1)
    var_b = (db**2).sum(axis=1)
    std_floor = ZERO_VOLATILITY_TOLERANCE**2 * (window - 1)
    defined = (var_a > std_floor) & (var_b > std_floor)
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = (da * db).sum(axis=1) / np.sqrt(var_a * var_b)
    out[window - 1 :] = np.where(defined, np.clip(corr, -1.0, 1.0), np.nan)
    return out


def cross_sectional_dispersion(returns: np.ndarray) -> np.ndarray:
    """Population std (ddof=0) of the assets' returns on each row (the whole cross-section)."""
    return _snap_zero(np.std(returns, axis=1, ddof=0))


# --------------------------------------------------------------------------
# Input contract and feature construction
# --------------------------------------------------------------------------


def validate_returns_frame(returns: pd.DataFrame, required: tuple[str, ...]) -> None:
    """Check the date index and asset columns before computing features."""
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise FeatureDataError("returns must be indexed by a DatetimeIndex of dates")
    if returns.index.has_duplicates:
        duplicate = returns.index[returns.index.duplicated()][0]
        raise FeatureDataError(f"duplicate return date {duplicate.date()}")
    if not returns.index.is_monotonic_increasing:
        raise FeatureDataError("return dates are not in chronological order")
    if returns.columns.has_duplicates:
        raise FeatureDataError(f"duplicate asset columns: {list(returns.columns)}")
    missing = [c for c in required if c not in returns.columns]
    if missing:
        raise FeatureDataError(f"returns are missing asset column(s) {missing}")
    if returns.empty:
        raise FeatureDataError("returns are empty")
    values = returns.to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        row, col = (int(i) for i in np.argwhere(~np.isfinite(values))[0])
        raise FeatureDataError(
            f"non-finite return for {returns.columns[col]} on {returns.index[row].date()}; "
            "features require complete processed returns"
        )


def _composite(returns: pd.DataFrame, members: tuple[str, ...]) -> np.ndarray:
    """Equal-weight, daily-rebalanced composite return: mean of the members' returns."""
    return returns[list(members)].to_numpy(dtype=np.float64).mean(axis=1)


def build_features(returns: pd.DataFrame, config: FeatureConfig) -> FeatureSet:
    """Compute the configured feature set from asset returns (index: dates, columns: assets).

    The input frame is not modified. Column order is deterministic: per-asset features
    in asset order, then group, market and cross-asset features.
    """
    assets = tuple(returns.columns)
    grouped = tuple(t for _, members in config.asset_groups for t in members)
    validate_returns_frame(returns, grouped)
    windows = config.windows
    columns: dict[str, np.ndarray] = {}
    definitions: list[FeatureDefinition] = []

    def add(values: np.ndarray, definition: FeatureDefinition) -> None:
        columns[definition.name] = values
        definitions.append(definition)

    # A. Return and momentum (per asset)
    for asset in assets:
        r = returns[asset].to_numpy(dtype=np.float64)
        add(
            r.copy(),
            FeatureDefinition(
                f"{asset}_ret_1",
                "return_momentum",
                "r_t (latest simple return)",
                (asset,),
                1,
                1,
                f"Most recent one-session return of {asset}; the return of the period ending at t.",
            ),
        )
        for w in windows.asset_momentum:
            add(
                compound_return(r, w),
                FeatureDefinition(
                    f"{asset}_mom_{w}",
                    "return_momentum",
                    f"prod(1 + r_{{t-{w - 1}..t}}) - 1",
                    (asset,),
                    w,
                    w,
                    f"Compounded return of {asset} over the last {w} sessions (trend).",
                ),
            )
        # B. Volatility (per asset)
        for w in windows.asset_volatility:
            add(
                rolling_volatility(r, w),
                FeatureDefinition(
                    f"{asset}_vol_{w}",
                    "volatility_risk",
                    f"std(r_{{t-{w - 1}..t}}, ddof=1), per session, not annualised",
                    (asset,),
                    w,
                    w,
                    f"Recent variability of {asset} returns over {w} sessions.",
                ),
            )

    # D. Universe context: group composites
    composites = {name: _composite(returns, members) for name, members in config.asset_groups}
    for name, members in config.asset_groups:
        c = composites[name]
        add(
            c.copy(),
            FeatureDefinition(
                f"{name}_ret_1",
                "universe_context",
                f"mean of r_t over {list(members)}",
                members,
                1,
                1,
                f"Equal-weight {name} composite return on t "
                "(descriptive, not a tradable portfolio).",
            ),
        )
        for w in windows.group_momentum:
            add(
                compound_return(c, w),
                FeatureDefinition(
                    f"{name}_mom_{w}",
                    "universe_context",
                    f"prod(1 + {name}_ret_1 over t-{w - 1}..t) - 1",
                    members,
                    w,
                    w,
                    f"Trend of the {name} composite over the last {w} sessions.",
                ),
            )

    # B. Market-level risk (market = configured market group composite)
    market_members = config.group(config.market_group)
    market = composites[config.market_group]
    for w in windows.market_volatility:
        add(
            rolling_volatility(market, w),
            FeatureDefinition(
                f"market_vol_{w}",
                "volatility_risk",
                f"std({config.market_group}_ret_1 over t-{w - 1}..t, ddof=1), not annualised",
                market_members,
                w,
                w,
                f"Volatility of the market ({config.market_group}) composite over {w} sessions.",
            ),
        )
    for w in windows.market_downside_volatility:
        add(
            downside_volatility(market, w),
            FeatureDefinition(
                f"market_downside_vol_{w}",
                "volatility_risk",
                f"sqrt(mean(min({config.market_group}_ret_1, 0)^2) over t-{w - 1}..t)",
                market_members,
                w,
                w,
                f"Size of market losses over {w} sessions (gains count as zero).",
            ),
        )
    w = windows.market_drawdown
    add(
        rolling_drawdown(market, w),
        FeatureDefinition(
            f"market_drawdown_{w}",
            "volatility_risk",
            f"W_t / max(1, max W within window) - 1, W = cumulative {config.market_group} "
            f"composite wealth over the last {w} returns",
            market_members,
            w,
            w,
            f"How far the market composite is below its {w}-session high (stress proxy, <= 0).",
        ),
    )

    # C. Cross-sectional and inter-asset
    if len(assets) >= 2:
        add(
            cross_sectional_dispersion(returns[list(assets)].to_numpy(dtype=np.float64)),
            FeatureDefinition(
                "xs_dispersion",
                "cross_asset",
                "std(r_t across all assets, ddof=0)",
                assets,
                1,
                1,
                "How differently the assets moved on t (cross-sectional spread).",
            ),
        )
    w = windows.average_asset_volatility
    asset_vols = np.column_stack(
        [rolling_volatility(returns[a].to_numpy(dtype=np.float64), w) for a in assets]
    )
    add(
        asset_vols.mean(axis=1),
        FeatureDefinition(
            f"avg_asset_vol_{w}",
            "cross_asset",
            f"mean over assets of std(r over t-{w - 1}..t, ddof=1)",
            assets,
            w,
            w,
            f"Market-wide volatility summary: average {w}-session volatility of all assets.",
        ),
    )
    if config.correlation_groups is not None:
        first, second = config.correlation_groups
        w = windows.correlation
        add(
            rolling_correlation(composites[first], composites[second], w),
            FeatureDefinition(
                f"{first}_{second}_corr_{w}",
                "cross_asset",
                f"Pearson corr({first}_ret_1, {second}_ret_1) over t-{w - 1}..t; NaN if a "
                "series has zero variance",
                config.group(first) + config.group(second),
                w,
                w,
                f"Co-movement of {first} and {second} composites (diversification indicator).",
            ),
        )

    frame = pd.DataFrame(columns, index=pd.DatetimeIndex(returns.index, name="date"))
    return FeatureSet(frame=frame, definitions=tuple(definitions))


def availability_summary(feature_set: FeatureSet) -> dict[str, dict[str, int]]:
    """Per feature: rows missing because of warm-up vs. missing for another reason."""
    summary = {}
    n = len(feature_set.frame)
    for definition in feature_set.definitions:
        missing = feature_set.frame[definition.name].isna().to_numpy()
        warm = min(definition.min_history - 1, n)
        summary[definition.name] = {
            "warm_up_rows": int(missing[:warm].sum()),
            "other_missing_rows": int(missing[warm:].sum()),
        }
    return summary
