"""Tests for causal feature engineering and decision/target alignment.

Expected values are derived by hand in the comments.
"""

from __future__ import annotations

import copy
import math

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import FeatureConfig
from adaptive_portfolio.features import (
    BOUNDARY,
    FeatureDataError,
    availability_summary,
    build_features,
    compound_return,
    cross_sectional_dispersion,
    downside_volatility,
    next_period_targets,
    rolling_correlation,
    rolling_drawdown,
    rolling_volatility,
)
from conftest import SMALL_FEATURES

TOL = 1e-12
CONFIG = FeatureConfig.from_dict(copy.deepcopy(SMALL_FEATURES))


def _returns(n: int = 40, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)  # fixed seed: deterministic synthetic returns
    return pd.DataFrame(
        rng.normal(0.0005, 0.01, size=(n, 3)),
        columns=["AAA", "BBB", "CCC"],
        index=pd.DatetimeIndex(pd.bdate_range("2024-01-02", periods=n), name="date"),
    )


# --------------------------------------------------------------------------
# Hand-calculated primitives
# --------------------------------------------------------------------------

R = np.array([0.10, -0.10, 0.20, 0.0])


def test_compound_return_hand_calculated() -> None:
    # w=2: 1.1*0.9-1 = -0.01; 0.9*1.2-1 = 0.08; 1.2*1.0-1 = 0.20; first row warm-up.
    np.testing.assert_allclose(compound_return(R, 2), [np.nan, -0.01, 0.08, 0.20], atol=TOL)


def test_rolling_volatility_is_sample_std_not_annualised() -> None:
    # [0.1, -0.1]: deviations +-0.1, var = 0.02/1 -> sqrt(0.02)
    # [-0.1, 0.2]: mean 0.05, deviations -+0.15, var = 0.045 -> sqrt(0.045)
    # [0.2, 0.0]: deviations +-0.1 -> sqrt(0.02)
    expected = [np.nan, math.sqrt(0.02), math.sqrt(0.045), math.sqrt(0.02)]
    np.testing.assert_allclose(rolling_volatility(R, 2), expected, atol=TOL)


def test_downside_volatility_counts_only_losses() -> None:
    # [0.1, -0.1] -> sqrt((0 + 0.01)/2); [-0.1, 0.2] -> same; [0.2, 0.0] -> 0
    expected = [np.nan, math.sqrt(0.005), math.sqrt(0.005), 0.0]
    np.testing.assert_allclose(downside_volatility(R, 2), expected, atol=TOL)


def test_drawdown_from_peak_within_window() -> None:
    # Window [0.10, -0.20, 0.05]: wealth 1.1, 0.88, 0.924; peak 1.1 -> 0.924/1.1 - 1 = -0.16
    np.testing.assert_allclose(
        rolling_drawdown(np.array([0.10, -0.20, 0.05]), 3)[-1], -0.16, atol=TOL
    )
    # Window [-0.10, 0.05]: wealth 0.9, 0.945; the peak is the starting level 1 -> -0.055
    np.testing.assert_allclose(rolling_drawdown(np.array([-0.10, 0.05]), 2)[-1], -0.055, atol=TOL)
    # A rising window has no drawdown.
    assert rolling_drawdown(np.array([0.01, 0.02]), 2)[-1] == 0.0


def test_correlation_hand_calculated_and_undefined() -> None:
    a = np.array([0.01, 0.02, 0.03])
    np.testing.assert_allclose(rolling_correlation(a, 2 * a, 3)[-1], 1.0, atol=TOL)
    np.testing.assert_allclose(rolling_correlation(a, a[::-1].copy(), 3)[-1], -1.0, atol=TOL)
    # Zero variance: correlation is undefined -> NaN (never a fabricated 0).
    assert np.isnan(rolling_correlation(a, np.full(3, 0.01), 3)[-1])


def test_cross_sectional_dispersion_population_std() -> None:
    # Row [0.01, 0.03]: mean 0.02, deviations +-0.01 -> population std 0.01
    np.testing.assert_allclose(
        cross_sectional_dispersion(np.array([[0.01, 0.03]])), [0.01], atol=TOL
    )


def test_constant_returns_give_exact_zero_volatility() -> None:
    constant = np.full(6, 0.001)
    assert (rolling_volatility(constant, 3)[2:] == 0.0).all()
    assert (downside_volatility(constant, 3)[2:] == 0.0).all()


def test_short_series_is_all_warm_up() -> None:
    assert np.isnan(compound_return(np.array([0.01, 0.02]), 3)).all()


# --------------------------------------------------------------------------
# Feature frame: schema, warm-up, aggregates
# --------------------------------------------------------------------------


def test_schema_and_column_order() -> None:
    features = build_features(_returns(), CONFIG).frame
    assert list(features.columns) == [
        "AAA_ret_1", "AAA_mom_3", "AAA_vol_3",
        "BBB_ret_1", "BBB_mom_3", "BBB_vol_3",
        "CCC_ret_1", "CCC_mom_3", "CCC_vol_3",
        "equity_ret_1", "equity_mom_2", "equity_mom_5",
        "bond_ret_1", "bond_mom_2", "bond_mom_5",
        "market_vol_3", "market_downside_vol_3", "market_drawdown_4",
        "xs_dispersion", "avg_asset_vol_3", "equity_bond_corr_4",
    ]  # fmt: skip
    assert features.index.name == "date"


def test_aggregates_match_definitions() -> None:
    returns = _returns()
    features = build_features(returns, CONFIG).frame
    equity = returns[["AAA", "BBB"]].mean(axis=1).to_numpy()  # equal-weight composite
    np.testing.assert_allclose(features["equity_ret_1"], equity, atol=TOL)
    np.testing.assert_allclose(features["market_vol_3"], rolling_volatility(equity, 3), atol=TOL)
    np.testing.assert_allclose(features["bond_ret_1"], returns["CCC"], atol=TOL)
    avg = np.mean([rolling_volatility(returns[c].to_numpy(), 3) for c in returns], axis=0)
    np.testing.assert_allclose(features["avg_asset_vol_3"], avg, atol=TOL)


def test_warm_up_rows_are_nan_and_reported() -> None:
    feature_set = build_features(_returns(), CONFIG)
    frame = feature_set.frame
    # A window of w needs w rows including t: rows 0..w-2 are NaN, row w-1 is the first value.
    assert frame["equity_mom_5"].iloc[:4].isna().all() and pd.notna(frame["equity_mom_5"].iloc[4])
    assert frame["AAA_ret_1"].notna().all()
    summary = availability_summary(feature_set)
    assert summary["equity_mom_5"] == {"warm_up_rows": 4, "other_missing_rows": 0}
    assert summary["market_drawdown_4"] == {"warm_up_rows": 3, "other_missing_rows": 0}
    definitions = {d.name: d for d in feature_set.definitions}
    assert definitions["equity_mom_5"].min_history == 5
    assert "never filled" in definitions["equity_mom_5"].as_dict()["missing_values"]


def test_undefined_correlation_is_distinguished_from_warm_up() -> None:
    returns = _returns()
    returns["CCC"] = 0.002  # constant bond composite -> zero variance
    summary = availability_summary(build_features(returns, CONFIG))
    assert summary["equity_bond_corr_4"]["warm_up_rows"] == 3
    assert summary["equity_bond_corr_4"]["other_missing_rows"] == len(returns) - 3


def test_deterministic_and_input_not_mutated() -> None:
    returns = _returns()
    before = returns.copy()
    first = build_features(returns, CONFIG).frame
    second = build_features(returns, CONFIG).frame
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(returns, before)


def test_extra_asset_columns_get_per_asset_features_only() -> None:
    returns = _returns().assign(DDD=0.001)  # not in any group
    columns = build_features(returns, CONFIG).frame.columns
    assert "DDD_ret_1" in columns and "DDD_vol_3" in columns


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r.drop(columns="CCC"), r"missing asset column\(s\) \['CCC'\]"),
        (lambda r: pd.concat([r, r.iloc[[0]]]).sort_index(), "duplicate return date"),
        (lambda r: r.iloc[::-1], "chronological"),
        (lambda r: r.assign(AAA=np.r_[np.nan, r["AAA"].to_numpy()[1:]]), "non-finite return"),
        (lambda r: r.iloc[:0], "empty"),
        (lambda r: r.reset_index(drop=True), "DatetimeIndex"),
    ],
    ids=["missing-column", "duplicate-date", "unsorted", "nan", "empty", "no-dates"],
)
def test_invalid_inputs_rejected(mutate, message: str) -> None:
    with pytest.raises(FeatureDataError, match=message):
        build_features(mutate(_returns()), CONFIG)


def test_duplicate_asset_columns_rejected() -> None:
    returns = _returns()
    duplicated = pd.concat([returns, returns[["AAA"]]], axis=1)
    with pytest.raises(FeatureDataError, match="duplicate asset columns"):
        build_features(duplicated, CONFIG)


# --------------------------------------------------------------------------
# Leakage: a feature at t must not depend on anything after t
# --------------------------------------------------------------------------


def test_modifying_future_rows_does_not_change_past_features() -> None:
    returns = _returns()
    cutoff = 25
    altered = returns.copy()
    altered.iloc[cutoff + 1 :] = -2.0 * altered.iloc[cutoff + 1 :] + 0.03
    original = build_features(returns, CONFIG).frame
    changed = build_features(altered, CONFIG).frame
    pd.testing.assert_frame_equal(original.iloc[: cutoff + 1], changed.iloc[: cutoff + 1])
    assert not original.iloc[cutoff + 1 :].equals(changed.iloc[cutoff + 1 :])


def test_appending_rows_does_not_change_existing_features() -> None:
    returns = _returns(60)
    prefix = build_features(returns.iloc[:30], CONFIG).frame
    full = build_features(returns, CONFIG).frame
    pd.testing.assert_frame_equal(full.iloc[:30], prefix)


def test_next_return_never_enters_features_at_t() -> None:
    returns = _returns()
    t = 20
    altered = returns.copy()
    altered.iloc[t + 1] = altered.iloc[t + 1] + 0.05  # change only r_{t+1}
    original = build_features(returns, CONFIG).frame
    changed = build_features(altered, CONFIG).frame
    pd.testing.assert_series_equal(original.iloc[t], changed.iloc[t])
    assert not original.iloc[t + 1].equals(changed.iloc[t + 1])  # it does affect t+1


# --------------------------------------------------------------------------
# Decision/target alignment across split boundaries
# --------------------------------------------------------------------------


def test_next_period_targets_alignment_and_boundaries() -> None:
    returns = _returns(6)
    labels = pd.Series(
        ["train", "train", "validation", "validation", "test", "test"], index=returns.index
    )
    targets = next_period_targets(returns, labels)
    assert len(targets) == 5  # the last row has no next return
    assert targets.index[0] == returns.index[0]
    assert targets["target_date"].iloc[0] == returns.index[1]
    assert targets["target_AAA"].iloc[0] == returns["AAA"].iloc[1]
    # Decision at the last train date -> its outcome is a validation return: boundary.
    assert targets["pair_split"].tolist() == ["train", BOUNDARY, "validation", BOUNDARY, "test"]


def test_next_period_targets_requires_matching_index() -> None:
    returns = _returns(4)
    with pytest.raises(ValueError, match="identical date indexes"):
        next_period_targets(returns, pd.Series(["train"] * 3, index=returns.index[:3]))
