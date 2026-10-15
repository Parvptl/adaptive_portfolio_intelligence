"""Tests for training-calibrated rule-based regimes and their diagnostics."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.config import FeatureConfig, RegimeConfig
from adaptive_portfolio.features import build_features
from adaptive_portfolio.regimes import (
    UNAVAILABLE,
    RegimeCalibrationError,
    RegimeThresholds,
    assign_regimes,
    check_compatibility,
    fit_regime_thresholds,
    load_thresholds,
    save_thresholds,
)
from adaptive_portfolio.regimes.diagnostics import _transitions, build_regime_report
from conftest import SMALL_FEATURES

FEATURES = FeatureConfig.from_dict(copy.deepcopy(SMALL_FEATURES))
TREND, VOL = FEATURES.trend_feature, FEATURES.volatility_feature  # equity_mom_5, market_vol_3
SMALL = RegimeConfig(
    trend_neutral_quantile=0.5, volatility_quantiles=(0.25, 0.75), min_calibration_observations=5
)


def _frame(
    trend: list[float], vol: list[float], labels: list[str]
) -> tuple[pd.DataFrame, pd.Series]:
    index = pd.DatetimeIndex(pd.bdate_range("2024-01-02", periods=len(trend)), name="date")
    return (
        pd.DataFrame({TREND: trend, VOL: vol}, index=index),
        pd.Series(labels, index=index, name="split"),
    )


def _fit(frame: pd.DataFrame, labels: pd.Series, config: RegimeConfig = SMALL) -> RegimeThresholds:
    return fit_regime_thresholds(frame, labels, config, trend_feature=TREND, volatility_feature=VOL)


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------


def test_thresholds_hand_calculated_from_train_only() -> None:
    # Train |m| = 0.1..0.5 -> median (q=0.5, linear) 0.3. Train v = 1..5 -> q0.25 = 2, q0.75 = 4.
    # Validation/test rows carry extreme values that must be ignored.
    frame, labels = _frame(
        [-0.1, 0.2, -0.3, 0.4, 0.5, 9.0, -9.0],
        [1.0, 2.0, 3.0, 4.0, 5.0, 100.0, 100.0],
        ["train"] * 5 + ["validation", "test"],
    )
    th = _fit(frame, labels)
    assert th.trend_band == pytest.approx(0.3, abs=1e-12)
    assert (th.volatility_low, th.volatility_high) == pytest.approx((2.0, 4.0), abs=1e-12)
    assert th.calibration["rows_used"] == 5
    assert th.calibration["last_date_used"] == frame.index[4].date().isoformat()


def test_validation_and_test_values_cannot_change_thresholds() -> None:
    base, labels = _frame(
        [-0.1, 0.2, -0.3, 0.4, 0.5, 0.0, 0.0],
        [1.0, 2.0, 3.0, 4.0, 5.0, 1.0, 1.0],
        ["train"] * 5 + ["validation", "test"],
    )
    altered = base.copy()
    altered.iloc[5:] = [[5.0, 50.0], [-5.0, 70.0]]
    assert _fit(base, labels).to_dict() == _fit(altered, labels).to_dict()
    changed_train = base.copy()
    changed_train.iloc[0] = [-0.9, 9.0]
    assert _fit(changed_train, labels).to_dict() != _fit(base, labels).to_dict()


def test_missing_training_features_are_excluded_and_counted() -> None:
    frame, labels = _frame(
        [np.nan, -0.1, 0.2, -0.3, 0.4, 0.5], [np.nan, 1.0, 2.0, 3.0, 4.0, 5.0], ["train"] * 6
    )
    th = _fit(frame, labels)
    assert th.calibration["rows_excluded_missing_features"] == 1
    assert th.trend_band == pytest.approx(0.3, abs=1e-12)


def test_insufficient_training_history_raises() -> None:
    frame, labels = _frame([0.1, 0.2], [1.0, 2.0], ["train", "train"])
    with pytest.raises(RegimeCalibrationError, match="only 2 training row"):
        _fit(frame, labels)


def test_fit_requires_aligned_inputs_and_features() -> None:
    frame, labels = _frame([0.1] * 5, [1.0] * 5, ["train"] * 5)
    with pytest.raises(RegimeCalibrationError, match="same dates"):
        _fit(frame, labels.iloc[1:])
    with pytest.raises(RegimeCalibrationError, match="not in the feature set"):
        _fit(frame.drop(columns=VOL), labels)


# --------------------------------------------------------------------------
# Assignment rules, boundaries, ties, missing values
# --------------------------------------------------------------------------

FROZEN = RegimeThresholds(
    trend_feature=TREND,
    volatility_feature=VOL,
    trend_neutral_quantile=0.5,
    volatility_quantiles=(0.25, 0.75),
    trend_band=0.05,
    volatility_low=0.01,
    volatility_high=0.02,
)


def test_boundaries_are_inclusive_for_the_middle_category() -> None:
    frame, _ = _frame(
        [-0.0501, -0.05, 0.05, 0.0501, 0.0, np.nan, 0.0],
        [0.0099, 0.01, 0.02, 0.0201, np.nan, 0.015, 0.015],
        ["train"] * 7,
    )
    out = assign_regimes(frame, FROZEN)
    assert out["trend_label"].tolist() == [
        "negative",
        "neutral",
        "neutral",
        "positive",
        "neutral",
        UNAVAILABLE,
        "neutral",
    ]
    assert out["volatility_label"].tolist() == [
        "low",
        "normal",
        "normal",
        "high",
        UNAVAILABLE,
        "normal",
        "normal",
    ]
    assert out["regime"].tolist() == [
        "negative_low",
        "neutral_normal",
        "neutral_normal",
        "positive_high",
        UNAVAILABLE,
        UNAVAILABLE,
        "neutral_normal",
    ]
    assert out["regime_status"].tolist() == [
        "ok",
        "ok",
        "ok",
        "ok",
        "missing_volatility_feature",
        "missing_trend_feature",
        "ok",
    ]


def test_assignment_is_deterministic_and_does_not_mutate() -> None:
    frame, _ = _frame([0.1, -0.1], [0.015, 0.03], ["train", "train"])
    before = frame.copy()
    pd.testing.assert_frame_equal(assign_regimes(frame, FROZEN), assign_regimes(frame, FROZEN))
    pd.testing.assert_frame_equal(frame, before)


def test_constant_volatility_gives_degenerate_but_valid_thresholds() -> None:
    frame, labels = _frame([-0.1, 0.2, -0.3, 0.4, 0.5], [0.01] * 5, ["train"] * 5)
    th = _fit(frame, labels)
    assert th.volatility_low == th.volatility_high == 0.01
    assert set(assign_regimes(frame, th)["volatility_label"]) == {"normal"}  # never low/high


# --------------------------------------------------------------------------
# Frozen artifact: serialisation, reload, compatibility
# --------------------------------------------------------------------------


def test_artifact_round_trip_is_deterministic(tmp_path: Path) -> None:
    frame, labels = _frame([-0.1, 0.2, -0.3, 0.4, 0.5], [1.0, 2.0, 3.0, 4.0, 5.0], ["train"] * 5)
    th = _fit(frame, labels)
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    save_thresholds(th, first)
    save_thresholds(load_thresholds(first), second)
    assert first.read_bytes() == second.read_bytes()
    assert load_thresholds(first) == th
    pd.testing.assert_frame_equal(
        assign_regimes(frame, load_thresholds(first)), assign_regimes(frame, th)
    )


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda d: d.update(artifact_schema_version=99), "unsupported artifact schema"),
        (lambda d: d.update(method="kmeans"), "unknown calibration method"),
        (lambda d: d["thresholds"].update(trend_band=-1.0), "inconsistent"),
        (lambda d: d["thresholds"].update(volatility_low=5.0), "inconsistent"),
        (lambda d: d["thresholds"].pop("volatility_high"), "malformed"),
    ],
)
def test_invalid_artifacts_rejected(tmp_path: Path, edit, message: str) -> None:
    data = FROZEN.to_dict()
    edit(data)
    path = tmp_path / "t.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RegimeCalibrationError, match=message):
        load_thresholds(path)


def test_unparsable_and_missing_artifacts(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(RegimeCalibrationError, match="cannot parse"):
        load_thresholds(bad)
    with pytest.raises(FileNotFoundError):
        load_thresholds(tmp_path / "absent.json")


def test_incompatible_artifact_rejected() -> None:
    check_compatibility(FROZEN, trend_feature=TREND, volatility_feature=VOL, config=SMALL)
    with pytest.raises(RegimeCalibrationError, match="does not match"):
        check_compatibility(
            FROZEN, trend_feature="equity_mom_2", volatility_feature=VOL, config=SMALL
        )


# --------------------------------------------------------------------------
# Leakage under the real pipeline contract (features -> fit on train -> assign)
# --------------------------------------------------------------------------


def _returns(n: int, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        rng.normal(0.0003, 0.01, size=(n, 3)),
        columns=["AAA", "BBB", "CCC"],
        index=pd.DatetimeIndex(pd.bdate_range("2024-01-02", periods=n), name="date"),
    )


def _labels(index: pd.DatetimeIndex, train: int, validation: int) -> pd.Series:
    values = ["train"] * train + ["validation"] * validation
    values += ["test"] * (len(index) - len(values))
    return pd.Series(values, index=index)


def test_frozen_thresholds_give_prefix_invariant_labels() -> None:
    returns = _returns(80)
    labels = _labels(returns.index, 40, 20)
    config = FEATURES.regime
    th = fit_regime_thresholds(
        build_features(returns, FEATURES).frame,
        labels,
        config,
        trend_feature=TREND,
        volatility_feature=VOL,
    )
    full = assign_regimes(build_features(returns, FEATURES).frame, th)
    prefix = assign_regimes(build_features(returns.iloc[:50], FEATURES).frame, th)
    pd.testing.assert_frame_equal(full.iloc[:50], prefix)


def test_refitting_after_appending_future_data_reproduces_thresholds() -> None:
    returns = _returns(80)
    short = returns.iloc[:60]
    fit_short = fit_regime_thresholds(
        build_features(short, FEATURES).frame,
        _labels(short.index, 40, 20),
        FEATURES.regime,
        trend_feature=TREND,
        volatility_feature=VOL,
    )
    # 20 later rows appended (labelled test); the training partition is unchanged.
    fit_long = fit_regime_thresholds(
        build_features(returns, FEATURES).frame,
        _labels(returns.index, 40, 20),
        FEATURES.regime,
        trend_feature=TREND,
        volatility_feature=VOL,
    )
    assert fit_short.to_dict() == fit_long.to_dict()


def test_altering_validation_and_test_returns_leaves_thresholds_unchanged() -> None:
    returns = _returns(80)
    labels = _labels(returns.index, 40, 20)
    altered = returns.copy()
    altered.iloc[40:] = altered.iloc[40:] * 5 - 0.01  # every validation/test return changed

    def fit(r: pd.DataFrame) -> dict:
        return fit_regime_thresholds(
            build_features(r, FEATURES).frame,
            labels,
            FEATURES.regime,
            trend_feature=TREND,
            volatility_feature=VOL,
        ).to_dict()

    assert fit(returns) == fit(altered)


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------


def test_transitions_hand_counted() -> None:
    labels = pd.Series(["neutral_low", "neutral_low", "positive_low", UNAVAILABLE, "neutral_low"])
    result = _transitions(labels)
    # Pairs: low->low, low->positive; pairs touching "unavailable" are skipped.
    assert result["counts"] == {"neutral_low": {"neutral_low": 1, "positive_low": 1}}
    assert result["proportions"]["neutral_low"]["positive_low"] == 0.5
    assert (result["regime_changes"], result["consecutive_pairs"]) == (1, 2)


def test_report_counts_and_warnings_for_imbalanced_regimes() -> None:
    returns = _returns(60)
    labels = _labels(returns.index, 40, 10)
    feature_set = build_features(returns, FEATURES)
    th = fit_regime_thresholds(
        feature_set.frame, labels, FEATURES.regime, trend_feature=TREND, volatility_feature=VOL
    )
    regimes = assign_regimes(feature_set.frame, th)
    report = build_regime_report(
        feature_set=feature_set,
        regimes=regimes,
        split_labels=labels,
        thresholds=th,
        thresholds_mode="fitted_on_train",
        config=FEATURES.regime,
        summary_features=[TREND, VOL],
        dataset={"data_origin": "synthetic", "processed_dataset_id": "x"},
    )
    train = report["splits"]["train"]
    assert train["rows"] == 40 and train["unavailable_rows"] == 4  # trend window 5 -> 4 warm-up
    assert sum(r["count"] for r in train["regimes"].values()) == 36
    assert report["warnings"][0].startswith("Input data origin is 'synthetic'")
    # With 10 validation rows, any regime that occurs is >= 10 % and any absent one is flagged.
    absent = [n for n, r in report["splits"]["validation"]["regimes"].items() if r["count"] == 0]
    assert all(f"validation: regime {n} is absent." in report["warnings"] for n in absent)
    assert "not objectively verified" in report["disclaimer"]
