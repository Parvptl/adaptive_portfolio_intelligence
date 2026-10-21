"""Milestone E: regime analysis, permutation sensitivity and the explainability runner.

All data are synthetic. The policy-validation end-to-end test (``rl``) uses real but untrained
PPO checkpoints evaluated by the real D-076 evaluator on a synthetic project.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from adaptive_portfolio.config import load_backtest_config, load_feature_config, load_project_config
from adaptive_portfolio.data.boundaries import DataBoundaryError
from adaptive_portfolio.data.pipeline import build_dataset, project_root_for
from adaptive_portfolio.evaluation.backtest import run_backtest
from adaptive_portfolio.explainability import regime_analysis as ra
from adaptive_portfolio.explainability import run as runner
from adaptive_portfolio.explainability import sensitivity as sens
from adaptive_portfolio.features.pipeline import build_feature_dataset
from adaptive_portfolio.regimes.rules import REGIME_LABELS, UNAVAILABLE
from conftest import write_feature_config, write_tiny_project

ASSETS = ["AAA", "BBB"]


def _ledger(n: int = 6) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame({
        "date": dates,
        "net_return": [-0.0015, 0.01, -0.02, 0.005, 0.0, 0.03][:n],
        "traded_notional": [1.0, 0.0, 0.2, 0.0, 0.1, 0.0][:n],
        "weight_AAA": [0.5, 0.6, 0.3, 0.3, 0.2, 0.4][:n],
        "weight_BBB": [0.5, 0.4, 0.3, 0.2, 0.0, 0.0][:n],
        "weight_CASH": [0.0, 0.0, 0.4, 0.5, 0.8, 0.6][:n],
    })  # fmt: skip


def _regimes(dates: pd.DatetimeIndex, labels: list[str]) -> pd.Series:
    calendar = pd.DatetimeIndex([dates[0] - pd.offsets.BDay(1), *dates])
    return pd.Series(labels, index=calendar)


# --------------------------------------------------------------------------- regime analysis


def test_summary_uses_the_label_known_when_holdings_were_set() -> None:
    ledger = _ledger()
    dates = pd.DatetimeIndex(ledger["date"])
    # calendar: [pre, d0 .. d5]; rows d1..d5 use labels of d0..d4 (lag 1)
    labels = [UNAVAILABLE, "positive_low", "positive_low", "negative_high", "negative_high",
              "positive_low", "neutral_normal"]  # fmt: skip
    summary = ra.regime_conditioned_summary(ledger, _regimes(dates, labels), min_sessions=2)
    rows = summary.set_index("regime")
    assert list(summary["regime"]) == [*REGIME_LABELS, UNAVAILABLE, ra.ALL]
    # d1 <- positive_low(d0), d2 <- positive_low(d1), d3 <- negative_high, d4 <- negative_high,
    # d5 <- positive_low(d4); the label of the last row's own date (neutral_normal) is unused.
    assert rows.loc["positive_low", "sessions"] == 3
    assert rows.loc["positive_low", "episodes"] == 2
    assert rows.loc["negative_high", "sessions"] == 2
    assert rows.loc["neutral_normal", "sessions"] == 0
    assert rows.loc[ra.ALL, "sessions"] == 5  # funding row excluded
    assert rows.loc["negative_high", "mean_weight_CASH"] == pytest.approx((0.5 + 0.8) / 2)
    assert rows.loc["negative_high", "mean_risky_exposure"] == pytest.approx(1 - 0.65)
    assert rows.loc["positive_low", "traded_notional"] == pytest.approx(0.2)  # funding excluded
    assert rows.loc["negative_high", "annualised_turnover"] == pytest.approx(0.05 * 252)
    net = np.array([0.005, 0.0])
    assert rows.loc["negative_high", "annualised_volatility"] == pytest.approx(
        net.std(ddof=1) * np.sqrt(252)
    )
    # risky-sleeve HHI of (0.3, 0.2) rescaled = 0.6^2 + 0.4^2; of (0.2, 0) = 1
    assert rows.loc["negative_high", "mean_risky_hhi"] == pytest.approx((0.52 + 1.0) / 2)
    assert rows.loc["neutral_normal", ["mean_risky_exposure", "annualised_volatility"]].isna().all()
    assert bool(rows.loc["positive_low", "sufficient"]) is True  # 3 >= 2
    assert bool(rows.loc["negative_low", "sufficient"]) is False


def test_unavailable_warm_up_rows_are_reported_not_dropped() -> None:
    ledger = _ledger()
    labels = [UNAVAILABLE] * 3 + ["neutral_low"] * 4
    summary = ra.regime_conditioned_summary(
        ledger, _regimes(pd.DatetimeIndex(ledger["date"]), labels), min_sessions=1
    )
    rows = summary.set_index("regime")
    assert rows.loc[UNAVAILABLE, "sessions"] == 2 and rows.loc["neutral_low", "sessions"] == 3


@pytest.mark.parametrize(("change", "message"), [
    ("unknown_label", "unknown regime"), ("missing_date", "missing from the regime calendar"),
    ("short_calendar", "at least `lag` rows earlier"), ("unsorted", "strictly increasing"),
    ("one_row", "funding row and at least one"),
])  # fmt: skip
def test_inconsistent_inputs_are_rejected(change: str, message: str) -> None:
    ledger = _ledger()
    dates = pd.DatetimeIndex(ledger["date"])
    regimes = _regimes(dates, ["positive_low"] * 7)
    if change == "unknown_label":
        regimes.iloc[2] = "sideways"
    elif change == "missing_date":
        regimes = regimes.drop(dates[3])
    elif change == "short_calendar":
        regimes = regimes.iloc[2:]  # the funding date d0 is needed for row d1
    elif change == "unsorted":
        ledger = ledger.iloc[[0, 2, 1, 3, 4, 5]]
    elif change == "one_row":
        ledger = ledger.iloc[:1]
    with pytest.raises(ra.RegimeAnalysisError, match=message):
        ra.regime_conditioned_summary(ledger, regimes)
    with pytest.raises(ra.RegimeAnalysisError, match="lag must be"):
        ra.label_ledger_rows(dates, regimes, 0)


def test_summarise_strategies_is_deterministic_and_order_independent() -> None:
    a = _ledger().assign(strategy="a")
    b = _ledger().assign(strategy="b", weight_CASH=0.0, weight_BBB=0.5, weight_AAA=0.5)
    regimes = _regimes(pd.DatetimeIndex(a["date"]), ["positive_low"] * 7)
    one = ra.summarise_strategies(pd.concat([a, b]), regimes, min_sessions=1)
    two = ra.summarise_strategies(pd.concat([b, a]).sample(frac=1, random_state=3), regimes,
                                  min_sessions=1)  # fmt: skip
    pd.testing.assert_frame_equal(one, two)
    assert list(one["strategy"].unique()) == ["a", "b"]


# --------------------------------------------------------------------------- sensitivity


def _linear_policy(weights: np.ndarray):
    def policy(obs: np.ndarray) -> np.ndarray:
        return np.clip(obs @ weights, -1.0, 1.0)

    return policy


def test_sensitivity_is_zero_for_ignored_inputs_and_positive_for_used_ones() -> None:
    rng = np.random.default_rng(0)
    obs = rng.normal(size=(40, 4)).astype(np.float32)
    weights = np.zeros((4, 3))
    weights[0, 0] = 0.8  # the policy uses input 0 only
    table = sens.permutation_sensitivity(
        _linear_policy(weights), obs, {"used": [0], "ignored": [1, 2], "also_ignored": [3]},
        max_weight=0.4, asset_names=["AAA", "BBB"], repeats=5, seed=1,
    ).set_index("group")  # fmt: skip
    assert table.loc["ignored", "mean_l1_change"] == 0.0
    assert table.loc["also_ignored", "max_l1_change"] == 0.0
    assert table.loc["used", "mean_l1_change"] > 0.01
    assert 0 <= table.loc["used", "max_l1_change"] <= 2


def test_sensitivity_is_reproducible_and_independent_of_group_order() -> None:
    rng = np.random.default_rng(1)
    obs = rng.normal(size=(30, 4)).astype(np.float32)
    policy = _linear_policy(rng.normal(scale=0.3, size=(4, 3)))
    groups = {"g1": [0, 1], "g2": [2], "g3": [3]}
    one = sens.permutation_sensitivity(
        policy, obs, groups, max_weight=0.4, asset_names=["A", "B"], repeats=4, seed=7
    )
    two = sens.permutation_sensitivity(
        policy,
        obs,
        dict(reversed(groups.items())),
        max_weight=0.4,
        asset_names=["A", "B"],
        repeats=4,
        seed=7,
    )
    pd.testing.assert_frame_equal(one.set_index("group").sort_index(),
                                  two.set_index("group").sort_index())  # fmt: skip
    other = sens.permutation_sensitivity(
        policy, obs, groups, max_weight=0.4, asset_names=["A", "B"], repeats=4, seed=8
    )
    assert not one["mean_l1_change"].equals(other["mean_l1_change"])


def test_sensitivity_rejects_bad_inputs() -> None:
    obs = np.zeros((5, 3), dtype=np.float32)
    policy = _linear_policy(np.zeros((3, 3)))
    with pytest.raises(sens.SensitivityError, match="invalid columns"):
        sens.permutation_sensitivity(policy, obs, {"g": [5]}, max_weight=0.4,
                                     asset_names=["A", "B"])  # fmt: skip
    with pytest.raises(sens.SensitivityError, match="repeats"):
        sens.permutation_sensitivity(policy, obs, {"g": [0]}, max_weight=0.4,
                                     asset_names=["A", "B"], repeats=1)  # fmt: skip
    with pytest.raises(sens.SensitivityError, match="finite"):
        sens.permutation_sensitivity(policy, obs[:1], {"g": [0]}, max_weight=0.4,
                                     asset_names=["A", "B"])  # fmt: skip


def test_observation_groups_follow_the_d062_layout() -> None:
    groups = sens.observation_groups(["f1", "f2", "f3"], {"f1": "a", "f2": "b", "f3": "a"}, 2)
    assert groups == {"a": [0, 2], "b": [1], "regime_inputs": list(range(3, 12)),
                      "portfolio_weights": [12, 13, 14]}  # fmt: skip
    with pytest.raises(sens.SensitivityError, match="no recorded family"):
        sens.observation_groups(["f1"], {}, 2)


# --------------------------------------------------------------------------- runner


@pytest.fixture(scope="module")
def backtested(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("explain")
    config_dir = write_tiny_project(
        root, universe=["AAA", "BBB", "CCC"], start="2024-01-01", end="2024-06-28",
        splits={"train": {"start": "2024-01-01", "end": "2024-03-29"},
                "validation": {"start": "2024-04-01", "end": "2024-05-31"},
                "test": {"start": "2024-06-01", "end": "2024-06-28"}},
    )  # fmt: skip
    strategies = [{"name": "equal_weight_monthly", "type": "equal_weight", "rebalance": "monthly"},
                  {"name": "inverse_volatility_monthly", "type": "inverse_volatility",
                   "rebalance": "monthly", "lookback": 10}]  # fmt: skip
    backtest = {"execution_lag_sessions": 1, "periods_per_year": 252,
                "common_start_history_sessions": 15, "strategies": strategies}  # fmt: skip
    (config_dir / "backtest.yaml").write_text(yaml.safe_dump(backtest), encoding="utf-8")
    write_feature_config(config_dir)
    config = load_project_config(config_dir)
    project = project_root_for(config_dir)
    dataset = build_dataset(config, project, provider_name="synthetic")
    features = build_feature_dataset(config, load_feature_config(config_dir / "features.yaml"),
                                     project, provider_name="synthetic")  # fmt: skip
    result = run_backtest(config, load_backtest_config(config_dir / "backtest.yaml"), project,
                          dataset_dir=dataset.processed_dir)  # fmt: skip
    return {"config_dir": config_dir, "root": project, "dataset_dir": dataset.processed_dir,
            "feature_dir": features.output_dir, "backtest_dir": result.output_dir}  # fmt: skip


def _run_train(p: dict, out: Path, **kw) -> Path:
    return runner.run_baselines_train(p["config_dir"], p["backtest_dir"],
                                      dataset_dir=p["dataset_dir"], feature_dir=p["feature_dir"],
                                      output_root=out, **kw)  # fmt: skip


def _digests(directory: Path) -> dict[str, str]:
    return {
        p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.name != "metadata.json"
    }


def test_baselines_train_reads_training_rows_only_and_is_reproducible(backtested, tmp_path):
    pytest.importorskip("matplotlib")
    first = _run_train(backtested, tmp_path / "a")
    second = _run_train(backtested, tmp_path / "b")
    assert first.name == second.name and _digests(first) == _digests(second)
    summary = pd.read_csv(first / "regime_summary.csv")
    assert set(summary["regime"]) == {*REGIME_LABELS, UNAVAILABLE, ra.ALL}
    analysis = json.loads((first / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["window"]["last_date"] < "2024-04-01"
    assert analysis["checks"]["test_rows_read"] == 0
    metadata = json.loads((first / "metadata.json").read_text(encoding="utf-8"))
    for name, digest in metadata["files_sha256"].items():
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == digest
    figures = [p for p in (first / "figures").glob("*.png")]
    assert figures and all(p.with_suffix(".json").is_file() for p in figures)
    sidecar = json.loads(figures[0].with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["source"]["backtest_id"] == backtested["backtest_dir"].name
    with pytest.raises(runner.ExplainabilityError, match="never overwritten"):
        _run_train(backtested, tmp_path / "a")


def test_baselines_train_ignores_corrupted_validation_and_test_rows(backtested, tmp_path):
    reference = pd.read_csv(_run_train(backtested, tmp_path / "ref", figures=False)
                            / "regime_summary.csv")  # fmt: skip
    copy = {k: v for k, v in backtested.items()}
    for key in ("feature_dir", "dataset_dir", "backtest_dir"):
        target = tmp_path / key
        import shutil

        shutil.copytree(backtested[key], target)
        copy[key] = target
    for name in ("features.csv", "regimes.csv"):
        _corrupt_from(copy["feature_dir"] / name, "2024-04-01")
    _corrupt_from(copy["dataset_dir"] / "returns.csv", "2024-04-01")
    _corrupt_from(copy["dataset_dir"] / "splits.csv", "2024-04-01", keep_first=True)
    ledger = copy["backtest_dir"] / "ledger.csv"
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    ledger.write_text("".join(line if ",train," in line or i == 0 else
                              line.replace("0.", "x.") for i, line in enumerate(lines)),
                      encoding="utf-8")  # fmt: skip
    again = pd.read_csv(_run_train(copy, tmp_path / "corrupt", figures=False)
                        / "regime_summary.csv")  # fmt: skip
    pd.testing.assert_frame_equal(reference, again)


def _corrupt_from(path: Path, start: str, keep_first: bool = False) -> None:
    lines = path.read_bytes().splitlines(keepends=True)
    out, kept = [lines[0]], False
    for line in lines[1:]:
        late = line[:10].decode("ascii") >= start
        out.append(line if not late or (keep_first and not kept) else b"\xff\xfe bad\n")
        kept = kept or late
    path.write_bytes(b"".join(out))


def test_forbidden_and_test_artifacts_are_refused(backtested, tmp_path):
    with pytest.raises(runner.ExplainabilityError, match="never opened"):
        runner.run_baselines_train(backtested["config_dir"],
                                   tmp_path / "ac2d6b163d4f5e4b")  # fmt: skip
    fake = tmp_path / "fake_backtest"
    fake.mkdir()
    (fake / "metadata.json").write_text(json.dumps({"evaluated_splits": ["train", "test"]}),
                                        encoding="utf-8")  # fmt: skip
    with pytest.raises(runner.ExplainabilityError, match="evaluated the test split"):
        _run_train({**backtested, "backtest_dir": fake}, tmp_path / "o")


def test_policy_validation_refuses_without_explicit_authorisation(backtested, tmp_path):
    with pytest.raises(runner.ExplainabilityError, match="explicit recorded authorisation"):
        runner.run_policy_validation(backtested["config_dir"], tmp_path,
                                     confirm_validation_access=False)  # fmt: skip
    assert runner.main(["policy-validation", "--config-dir", str(backtested["config_dir"]),
                        "--evaluation-dir", str(tmp_path)]) == 1  # fmt: skip
    assert not any(tmp_path.iterdir())


def test_read_split_rows_never_parses_other_splits(tmp_path) -> None:
    path = tmp_path / "ledger.csv"
    path.write_text("strategy,split,date,value\nx,train,2024-01-02,1.5\nx,validation,2024-02-01,"
                    "NOT_A_NUMBER\n", encoding="utf-8")  # fmt: skip
    rows = runner.read_split_rows(path, "train")
    assert len(rows) == 1 and rows["value"].iloc[0] == 1.5
    with pytest.raises(runner.ExplainabilityError, match="no rows labelled"):
        runner.read_split_rows(path, "test")
    assert DataBoundaryError  # imported for the boundary tests above


def test_path_drawdown_levels_are_reported_per_regime() -> None:
    ledger = _ledger()
    capital = 100.0
    ledger["value"] = capital * np.cumprod(1 + ledger["net_return"].to_numpy())
    labels = ["positive_low"] * 3 + ["negative_high"] * 4
    summary = ra.regime_conditioned_summary(
        ledger, _regimes(pd.DatetimeIndex(ledger["date"]), labels), min_sessions=1
    ).set_index("regime")
    value = ledger["value"].to_numpy()
    path = value / np.maximum.accumulate(np.r_[capital, value])[1:] - 1
    # rows d1, d2 -> positive_low; d3, d4, d5 -> negative_high (labels at t - 1)
    assert summary.loc["positive_low", "deepest_path_drawdown"] == pytest.approx(path[1:3].min())
    assert summary.loc["negative_high", "mean_path_drawdown"] == pytest.approx(path[3:].mean())
    assert summary.loc[ra.ALL, "deepest_path_drawdown"] == pytest.approx(path[1:].min())
    no_value = ra.regime_conditioned_summary(
        _ledger(), _regimes(pd.DatetimeIndex(ledger["date"]), labels), min_sessions=1
    )
    assert no_value["deepest_path_drawdown"].isna().all()
