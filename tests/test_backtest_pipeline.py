"""End-to-end tests for the baseline backtest (offline, synthetic data)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yaml

from adaptive_portfolio.config import (
    ConfigError,
    load_backtest_config,
    load_feature_config,
    load_project_config,
)
from adaptive_portfolio.data.cache import read_csv, write_csv
from adaptive_portfolio.data.cli import main
from adaptive_portfolio.data.pipeline import build_dataset, project_root_for
from adaptive_portfolio.data.providers import InMemoryProvider
from adaptive_portfolio.evaluation.backtest import BACKTEST_FILES, run_backtest
from adaptive_portfolio.features import next_period_targets
from adaptive_portfolio.features.engineering import FeatureDataError
from adaptive_portfolio.features.pipeline import build_feature_dataset
from adaptive_portfolio.timing import execution_row, first_earned_row
from conftest import write_feature_config, write_tiny_project

SPLITS = {
    "train": {"start": "2024-01-01", "end": "2024-03-29"},
    "validation": {"start": "2024-04-01", "end": "2024-05-31"},
    "test": {"start": "2024-06-01", "end": "2024-06-28"},
}
STRATEGIES = [
    {"name": "equal_weight_monthly", "type": "equal_weight", "rebalance": "monthly"},
    {"name": "buy_and_hold_equal_weight", "type": "equal_weight", "rebalance": "never"},
    {
        "name": "inverse_volatility_monthly",
        "type": "inverse_volatility",
        "rebalance": "monthly",
        "lookback": 10,
    },
    {"name": "equal_weight_daily", "type": "equal_weight", "rebalance": "daily"},
]


def _project(root: Path, **backtest: Any) -> Path:
    # Lag 1 (the proposed primary convention, D-055) unless a test overrides it.
    config_dir = write_tiny_project(
        root, universe=["AAA", "BBB", "CCC"], start="2024-01-01", end="2024-06-28", splits=SPLITS
    )
    content = {"execution_lag_sessions": 1, "strategies": STRATEGIES, **backtest}
    (config_dir / "backtest.yaml").write_text(
        yaml.safe_dump(content, sort_keys=False), encoding="utf-8"
    )
    return config_dir


def _run(config_dir: Path, **kwargs):
    config = load_project_config(config_dir)
    root = project_root_for(config_dir)
    dataset = build_dataset(config, root, provider_name="synthetic")
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    return dataset, run_backtest(config, backtest, root, provider_name="synthetic", **kwargs)


def _rerun(config_dir: Path, dataset_dir: Path, **kwargs):
    # Re-run on an existing (possibly altered) processed dataset.
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    root = project_root_for(config_dir)
    return run_backtest(config, backtest, root, dataset_dir=dataset_dir, **kwargs)


def _hashes(directory: Path) -> dict[str, str]:
    return {n: hashlib.sha256((directory / n).read_bytes()).hexdigest() for n in BACKTEST_FILES}


@pytest.mark.parametrize("include_test", [False, True])
def test_outputs_and_split_containment(tmp_path: Path, include_test: bool) -> None:
    dataset, result = _run(_project(tmp_path), include_test=include_test)
    assert sorted(p.name for p in result.output_dir.iterdir()) == sorted(BACKTEST_FILES)
    ledger = read_csv(result.output_dir / "ledger.csv", ("date", "decision_date"))
    splits = read_csv(dataset.processed_dir / "splits.csv").set_index("date")["split"]
    expected = {"train", "validation", "test"} if include_test else {"train", "validation"}
    assert set(ledger["split"]) == expected
    for (strategy, split), rows in ledger.groupby(["strategy", "split"]):
        # Every ledger date belongs to the ledger's own split: no return from another split.
        assert set(splits.loc[rows["date"]]) == {split}, (strategy, split)
        assert rows["date"].iloc[-1] == splits.index[splits == split][-1]
    windows = result.metrics["windows"]
    # Lookback 10 -> the first decision is the 10th return row; later splits start immediately.
    assert windows["train"]["warm_up_rows_skipped"] == 9
    assert windows["validation"]["first_decision_date"] == windows["validation"]["split_first_date"]
    executions = read_csv(result.output_dir / "executions.csv", ("decision_date", "execution_date"))
    assert (executions["execution_date"] >= executions["decision_date"]).all()
    metadata = json.loads((result.output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert str(tmp_path) not in json.dumps(metadata)
    assert "D-048" in metadata["conventions"]["timing"]


@pytest.mark.parametrize("lag", [0, 1])
def test_common_start_and_boundary_drops(tmp_path: Path, lag: int) -> None:
    _, result = _run(_project(tmp_path, execution_lag_sessions=lag), include_test=True)
    for split, by_strategy in result.metrics["metrics"].items():
        firsts = {m["first_date"] for m in by_strategy.values()}
        assert len(firsts) == 1, split  # identical evaluation window for every strategy
        # A daily strategy's decisions on the split's last lag + 1 rows would first earn a
        # return of the next split; they are dropped (lag 0 -> one, lag 1 -> two).
        assert by_strategy["equal_weight_daily"]["decisions_dropped_at_split_end"] == lag + 1
        assert by_strategy["buy_and_hold_equal_weight"]["rebalances"] == 1


def test_buy_and_hold_matches_closed_form(tmp_path: Path) -> None:
    dataset, result = _run(_project(tmp_path), include_test=True)
    returns = read_csv(dataset.processed_dir / "returns.csv").set_index("date")[
        ["AAA", "BBB", "CCC"]
    ]
    splits = read_csv(dataset.processed_dir / "splits.csv").set_index("date")["split"]
    cost = (10.0 + 5.0) / 10_000  # environment.yaml defaults
    for split, window in result.metrics["windows"].items():
        rows = returns[(splits == split).to_numpy()]
        earned = rows[rows.index > pd.Timestamp(window["first_execution_date"])]
        # Value = V0 (1 - cost x 1.0) x mean over assets of each asset's compounded growth.
        expected = 100_000 * (1 - cost) * np.mean(np.prod(1 + earned.to_numpy(), axis=0))
        actual = result.metrics["metrics"][split]["buy_and_hold_equal_weight"]["final_value"]
        assert actual == pytest.approx(expected, rel=1e-12)


def test_rerun_is_byte_identical(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    _, first = _run(config_dir)
    before = _hashes(first.output_dir)
    _, second = _run(config_dir)
    assert _hashes(second.output_dir) == before


def test_later_returns_cannot_change_earlier_split_results(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    dataset, original = _run(config_dir, include_test=True)
    altered_dir = tmp_path / "altered_dataset"
    shutil.copytree(dataset.processed_dir, altered_dir)
    returns = read_csv(altered_dir / "returns.csv", ("date", "period_start"))
    splits = read_csv(altered_dir / "splits.csv")["split"]
    later = (splits != "train").to_numpy()
    returns.loc[later, ["AAA", "BBB", "CCC"]] = -returns.loc[later, ["AAA", "BBB", "CCC"]] * 3
    write_csv(returns, altered_dir / "returns.csv")
    altered = _rerun(config_dir, altered_dir, include_test=True)
    assert altered.metrics["metrics"]["train"] == original.metrics["metrics"]["train"]
    assert altered.metrics["metrics"]["test"] != original.metrics["metrics"]["test"]


def test_pipeline_weights_use_row_k_but_never_row_k_plus_1(tmp_path: Path) -> None:
    # Pipeline-level leakage check for inverse-volatility weights decided at row k:
    # changing the return at row k (inside the lookback) must change them, and
    # changing the return at row k+1 (the first future return) must not.
    config_dir = _project(tmp_path)
    dataset, _original = _run(config_dir)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    target_columns = ["target_AAA", "target_BBB", "target_CCC", "target_CASH"]

    def inverse_vol_targets(directory: Path) -> pd.DataFrame:
        result = run_backtest(config, backtest, project_root_for(config_dir), dataset_dir=directory)
        frame = read_csv(result.output_dir / "executions.csv", ("decision_date", "execution_date"))
        selected = (frame["strategy"] == "inverse_volatility_monthly") & (
            frame["split"] == "validation"
        )
        return frame[selected].set_index("decision_date")[target_columns]

    baseline = inverse_vol_targets(dataset.processed_dir)
    decision = baseline.index[1]  # the mid-split monthly decision

    def altered_targets(offset: int, name: str) -> pd.DataFrame:
        directory = tmp_path / name
        shutil.copytree(dataset.processed_dir, directory)
        returns = read_csv(directory / "returns.csv", ("date", "period_start"))
        position = int(np.flatnonzero(returns["date"] == decision)[0]) + offset
        returns.loc[position, ["AAA", "BBB", "CCC"]] = [0.30, -0.25, 0.20]
        write_csv(returns, directory / "returns.csv")
        return inverse_vol_targets(directory)

    future = altered_targets(1, "future_row")
    pd.testing.assert_series_equal(baseline.loc[decision], future.loc[decision])
    present = altered_targets(0, "decision_row")
    assert not np.allclose(baseline.loc[decision].to_numpy(), present.loc[decision].to_numpy())


def test_execution_lag_shifts_the_window(tmp_path: Path) -> None:
    dataset, lag0 = _run(_project(tmp_path / "a", execution_lag_sessions=0), include_test=True)
    _, lag1 = _run(_project(tmp_path / "b", execution_lag_sessions=1), include_test=True)
    returns = read_csv(dataset.processed_dir / "returns.csv")
    dates = list(returns["date"].dt.strftime("%Y-%m-%d"))
    for split in ("train", "validation", "test"):
        w0, w1 = lag0.metrics["windows"][split], lag1.metrics["windows"][split]
        assert w1["first_decision_date"] == w0["first_decision_date"]
        assert (
            dates.index(w1["first_execution_date"]) == dates.index(w0["first_execution_date"]) + 1
        )
        assert (
            lag1.metrics["metrics"][split]["equal_weight_daily"]["decisions_dropped_at_split_end"]
            == 2
        )


def test_annualised_metrics_are_opt_in(tmp_path: Path) -> None:
    _, default = _run(_project(tmp_path / "a"))
    assert default.metrics["metrics"]["validation"]["equal_weight_monthly"]["annualised"] is None
    _, annual = _run(_project(tmp_path / "b", periods_per_year=252))
    assert annual.metrics["metrics"]["validation"]["equal_weight_monthly"]["annualised"][
        "status"
    ].startswith("provisional")


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"constraints": {"max_turnover": 0.5}}, "D-031"),
        ({"risk_free_rate": 0.02}, "D-023"),
    ],
)
def test_unresolved_assumptions_are_refused(tmp_path: Path, environment, message) -> None:
    config_dir = _project(tmp_path)
    path = config_dir / "environment.yaml"
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    content["constraints"].update(environment.pop("constraints", {}))
    content.update(environment)
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        _run(config_dir)


def test_offline_without_raw_snapshot(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    dataset, _ = _run(config_dir)
    shutil.rmtree(dataset.acquisition.snapshot_dir)
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    result = run_backtest(config, backtest, project_root_for(config_dir), provider_name="synthetic")
    assert result.metrics["data_origin"] == "synthetic"


def test_multi_session_returns_refused(fixture_project, fixture_frames) -> None:
    config = load_project_config(fixture_project)
    root = project_root_for(fixture_project)
    dataset = build_dataset(config, root, provider=InMemoryProvider(fixture_frames))
    (fixture_project / "backtest.yaml").write_text(
        # Two assets: equal weight (0.5) would exceed max_weight 0.4, so use 0.4/0.4 + cash.
        yaml.safe_dump(
            {
                "execution_lag_sessions": 1,
                "strategies": [
                    {
                        "name": "fw",
                        "type": "fixed_weights",
                        "rebalance": "never",
                        "weights": {"AAA": 0.4, "BBB": 0.4},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    backtest = load_backtest_config(fixture_project / "backtest.yaml")
    with pytest.raises(FeatureDataError, match="more than one session"):
        run_backtest(config, backtest, root, dataset_dir=dataset.processed_dir)


def _cli(config_dir: Path, *args: str) -> int:
    return main(["-q", "--config-dir", str(config_dir), *args])


def test_cli_backtest_workflow(tmp_path: Path, capsys) -> None:
    config_dir = _project(tmp_path)
    assert _cli(config_dir, "validate") == 0
    assert "backtest.yaml OK" in capsys.readouterr().out
    assert _cli(config_dir, "build", "--provider", "synthetic") == 0
    capsys.readouterr()
    assert _cli(config_dir, "backtest-report", "--provider", "synthetic") == 1
    assert "run the 'backtest' command first" in capsys.readouterr().err
    assert _cli(config_dir, "backtest", "--provider", "synthetic") == 0
    out = capsys.readouterr().out
    assert "NOT MARKET DATA" in out and "PROVISIONAL" in out
    assert _cli(config_dir, "backtest-report", "--provider", "synthetic") == 0
    assert "# Baseline backtest report" in capsys.readouterr().out


def test_cli_without_backtest_yaml(tmp_path: Path, capsys) -> None:
    config_dir = _project(tmp_path)
    (config_dir / "backtest.yaml").unlink()
    assert _cli(config_dir, "validate") == 0
    assert "no backtest.yaml" in capsys.readouterr().out
    assert _cli(config_dir, "backtest", "--provider", "synthetic") == 1
    assert "backtest.yaml" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Milestone 4.1: test split opt-in (D-056), lag-1 timing and alignment (D-055)
# --------------------------------------------------------------------------


def _executions(result) -> pd.DataFrame:
    return read_csv(result.output_dir / "executions.csv", ("decision_date", "execution_date"))


def test_test_split_is_absent_by_default(tmp_path: Path) -> None:
    _, result = _run(_project(tmp_path))
    assert list(result.metrics["metrics"]) == ["train", "validation"]
    assert list(result.metrics["windows"]) == ["train", "validation"]
    assert result.metrics["evaluated_splits"] == ["train", "validation"]
    assert result.metrics["test_split"].startswith("excluded")
    out = result.output_dir
    for name in ("ledger.csv", "executions.csv", "metrics.csv"):
        assert "test" not in set(read_csv(out / name)["split"]), name
    assert "## test" not in (out / "backtest_report.md").read_text(encoding="utf-8")
    metadata = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["evaluated_splits"] == ["train", "validation"]


def test_test_split_requires_explicit_opt_in(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    dataset, default = _run(config_dir)
    included = _rerun(config_dir, dataset.processed_dir, include_test=True)
    assert list(included.metrics["metrics"]) == ["train", "validation", "test"]
    assert included.metrics["test_split"].startswith("INCLUDED")
    # Different evaluated splits -> different backtest id: neither run overwrites the other.
    assert included.backtest_id != default.backtest_id
    assert (default.output_dir / "metrics.json").is_file()
    # Train and validation results are identical with or without the test split.
    for split in ("train", "validation"):
        assert included.metrics["metrics"][split] == default.metrics["metrics"][split]
    with pytest.raises(ConfigError, match="include_test"):
        _rerun(config_dir, dataset.processed_dir, include_test="yes")


def test_test_returns_cannot_change_train_or_validation(tmp_path: Path) -> None:
    config_dir = _project(tmp_path)
    dataset, original = _run(config_dir, include_test=True)
    altered_dir = tmp_path / "altered_test_returns"
    shutil.copytree(dataset.processed_dir, altered_dir)
    returns = read_csv(altered_dir / "returns.csv", ("date", "period_start"))
    splits = read_csv(altered_dir / "splits.csv")["split"]
    test_rows = (splits == "test").to_numpy()
    returns.loc[test_rows, ["AAA", "BBB", "CCC"]] = (
        0.05 - returns.loc[test_rows, ["AAA", "BBB", "CCC"]]
    )
    write_csv(returns, altered_dir / "returns.csv")
    altered = _rerun(config_dir, altered_dir, include_test=True)
    assert altered.metrics["metrics"]["test"] != original.metrics["metrics"]["test"]
    before, after = _executions(original), _executions(altered)
    for split in ("train", "validation"):
        assert altered.metrics["metrics"][split] == original.metrics["metrics"][split]
        # The baselines' decisions and target weights (their only "parameters") are unchanged.
        pd.testing.assert_frame_equal(
            before[before["split"] == split].reset_index(drop=True),
            after[after["split"] == split].reset_index(drop=True),
        )


def test_lag_one_pipeline_timing(tmp_path: Path) -> None:
    dataset, result = _run(_project(tmp_path, execution_lag_sessions=1))
    returns = read_csv(dataset.processed_dir / "returns.csv").set_index("date")[
        ["AAA", "BBB", "CCC"]
    ]
    dates = returns.index
    ledger = read_csv(result.output_dir / "ledger.csv", ("date", "decision_date"))
    executions = _executions(result)
    # Every execution is exactly one observed session after its decision.
    positions = {d: i for i, d in enumerate(dates)}
    for _, row in executions.iterrows():
        assert positions[row["execution_date"]] == positions[row["decision_date"]] + 1
    weight_columns = ["weight_AAA", "weight_BBB", "weight_CCC"]
    for split in ("train", "validation"):
        rows = ledger[(ledger["strategy"] == "equal_weight_monthly") & (ledger["split"] == split)]
        rows = rows.reset_index(drop=True)
        window = result.metrics["windows"][split]
        x0 = positions[pd.Timestamp(window["first_execution_date"])]
        assert x0 == positions[pd.Timestamp(window["first_decision_date"])] + 1
        assert rows.loc[0, "date"] == dates[x0] and rows.loc[0, "gross_return"] == 0.0
        # The first earned return is row x0 + 1, earned with the funding-row weights.
        assert rows.loc[1, "date"] == dates[x0 + 1]
        earned = float(rows.loc[0, weight_columns].to_numpy(dtype=float) @ returns.iloc[x0 + 1])
        assert rows.loc[1, "gross_return"] == pytest.approx(earned, abs=1e-12)
        # On every later execution row, the new weights did not earn that row's return.
        for i in rows.index[rows["rebalanced"]][1:]:
            held = rows.loc[i - 1, weight_columns].to_numpy(dtype=float)
            assert rows.loc[i, "gross_return"] == pytest.approx(
                float(held @ returns.loc[rows.loc[i, "date"]]), abs=1e-12
            )


@pytest.mark.parametrize("lag", [0, 1])
def test_backtest_decisions_match_feature_target_alignment(tmp_path: Path, lag: int) -> None:
    dataset, result = _run(_project(tmp_path, execution_lag_sessions=lag), include_test=True)
    returns = read_csv(dataset.processed_dir / "returns.csv").set_index("date")[
        ["AAA", "BBB", "CCC"]
    ]
    labels = read_csv(dataset.processed_dir / "splits.csv").set_index("date")["split"]
    targets = next_period_targets(returns, labels, execution_lag_sessions=lag)
    executions = _executions(result)
    daily = executions[executions["strategy"] == "equal_weight_daily"]
    for split, rows in daily.groupby("split"):
        first = pd.Timestamp(result.metrics["windows"][split]["first_decision_date"])
        paired = targets[(targets["pair_split"] == split) & (targets.index >= first)]
        # The backtest keeps exactly the decisions the alignment helper assigns to the split,
        # executed on the same dates.
        assert list(rows["decision_date"]) == list(paired.index), (split, lag)
        assert list(rows["execution_date"]) == list(paired["execution_date"]), (split, lag)


def test_cli_test_split_opt_in(tmp_path: Path, capsys) -> None:
    config_dir = _project(tmp_path)
    assert _cli(config_dir, "build", "--provider", "synthetic") == 0
    capsys.readouterr()
    assert _cli(config_dir, "backtest", "--provider", "synthetic") == 0
    out = capsys.readouterr().out
    assert "splits         : train, validation" in out
    assert "test split     : excluded" in out and "  test:" not in out
    assert "TEST SPLIT INCLUDED" not in out
    assert _cli(config_dir, "backtest-report", "--provider", "synthetic", "--include-test") == 1
    assert "backtest --include-test" in capsys.readouterr().err
    assert _cli(config_dir, "backtest", "--provider", "synthetic", "--include-test") == 0
    out = capsys.readouterr().out
    assert "TEST SPLIT INCLUDED" in out and "  test:" in out
    assert _cli(config_dir, "backtest-report", "--provider", "synthetic", "--include-test") == 0
    assert "## test" in capsys.readouterr().out
    assert _cli(config_dir, "backtest-report", "--provider", "synthetic") == 0
    assert "## test" not in capsys.readouterr().out


# --------------------------------------------------------------------------
# Milestone 4.2: common evaluation window and funding turnover
# --------------------------------------------------------------------------


def test_common_start_history_moves_only_the_training_start(tmp_path: Path) -> None:
    dataset, default = _run(_project(tmp_path / "a"))
    _, longer = _run(_project(tmp_path / "b", common_start_history_sessions=20))
    # Default: the 10-session inverse-volatility lookback sets the start (9 warm-up rows).
    assert default.metrics["windows"]["train"]["warm_up_rows_skipped"] == 9
    # 20 rows of history required at the first decision -> first decision at row 19.
    train = longer.metrics["windows"]["train"]
    assert train["warm_up_rows_skipped"] == 19
    assert train["required_history_sessions"] == 20
    dates = list(read_csv(dataset.processed_dir / "returns.csv")["date"].dt.strftime("%Y-%m-%d"))
    assert train["first_decision_date"] == dates[19]
    for name, m in longer.metrics["metrics"]["train"].items():
        assert m["first_date"] == train["first_execution_date"], name  # one shared window
    # Validation starts long after 20 rows: its window is unchanged.
    assert longer.metrics["windows"]["validation"] == {
        **default.metrics["windows"]["validation"],
        "required_history_sessions": 20,
    }
    assert longer.metrics["metrics"]["validation"] == default.metrics["metrics"]["validation"]


def test_cli_refuses_a_common_start_shorter_than_the_feature_warm_up(
    tmp_path: Path, capsys
) -> None:
    config_dir = _project(tmp_path, common_start_history_sessions=1)
    write_feature_config(config_dir)
    longest = load_feature_config(config_dir / "features.yaml").windows.max_window()
    assert _cli(config_dir, "validate") == 1
    assert f"longest feature window in features.yaml is {longest}" in capsys.readouterr().err
    content = yaml.safe_load((config_dir / "backtest.yaml").read_text(encoding="utf-8"))
    content["common_start_history_sessions"] = longest
    (config_dir / "backtest.yaml").write_text(yaml.safe_dump(content), encoding="utf-8")
    assert _cli(config_dir, "validate") == 0
    assert "backtest.yaml OK" in capsys.readouterr().out


def test_metrics_report_funding_and_recurring_turnover(tmp_path: Path) -> None:
    _, result = _run(_project(tmp_path))
    flat = read_csv(result.output_dir / "metrics.csv")
    for _, row in flat.iterrows():
        assert row["funding_traded_notional"] == pytest.approx(1.0)  # all strategies fund fully
        assert row["total_traded_notional"] == pytest.approx(
            row["funding_traded_notional"] + row["recurring_traded_notional"]
        )
    hold = flat[flat["strategy"] == "buy_and_hold_equal_weight"]
    assert (hold["recurring_traded_notional"] == 0.0).all()


def test_feature_warm_up_and_backtest_window_align_end_to_end(tmp_path: Path) -> None:
    # Integration (offline, synthetic): build the processed dataset and the feature set from it,
    # then run the backtest with common_start_history_sessions = the longest feature window. The
    # feature warm-up (15 rows) is longer than every strategy lookback (at most 10), so it alone
    # sets the window.
    config_dir = _project(tmp_path, common_start_history_sessions=15)
    write_feature_config(config_dir)
    feature_path = config_dir / "features.yaml"
    feature_raw = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    feature_raw["windows"]["market_drawdown"] = 15
    feature_path.write_text(yaml.safe_dump(feature_raw, sort_keys=False), encoding="utf-8")
    config = load_project_config(config_dir)
    root = project_root_for(config_dir)
    dataset = build_dataset(config, root, provider_name="synthetic")
    feature_config = load_feature_config(feature_path)
    assert feature_config.windows.max_window() == 15
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    backtest.check_feature_warm_up(feature_config)  # the CLI safeguard accepts this pairing
    feature_set = build_feature_dataset(config, feature_config, root, provider_name="synthetic")
    result = run_backtest(config, backtest, root, provider_name="synthetic")

    features = read_csv(feature_set.output_dir / "features.csv")
    returns = read_csv(dataset.processed_dir / "returns.csv").set_index("date")[
        ["AAA", "BBB", "CCC"]
    ]
    assert list(features["date"]) == list(returns.index)  # same rows, same order
    complete = features.drop(columns=["date", "split"]).notna().all(axis=1).to_numpy()
    first_complete = int(np.argmax(complete))
    assert first_complete == 14 and not complete[:14].any()  # 15 rows incl. the decision row

    dates = returns.index
    lag = backtest.execution_lag_sessions
    assert lag == 1
    train = result.metrics["windows"]["train"]
    k0 = first_complete
    # The first eligible decision is exactly the first row with every feature available.
    assert train["first_decision_date"] == dates[k0].date().isoformat()
    assert train["required_history_sessions"] == 15
    assert train["first_execution_date"] == dates[execution_row(k0, lag)].date().isoformat()

    ledger = read_csv(result.output_dir / "ledger.csv", ("date", "decision_date"))
    executions = _executions(result)
    splits = read_csv(dataset.processed_dir / "splits.csv").set_index("date")["split"]
    assert set(ledger["split"]) == {"train", "validation"}  # no test rows by default
    weight_columns = ["weight_AAA", "weight_BBB", "weight_CCC"]
    for split in ("train", "validation"):
        rows = ledger[ledger["split"] == split]
        assert set(splits.loc[rows["date"]]) == {split}  # split boundaries respected
        # Every strategy uses exactly the same evaluation dates.
        per_strategy = [tuple(g["date"]) for _, g in rows.groupby("strategy")]
        assert len(set(per_strategy)) == 1, split
        first = pd.Timestamp(result.metrics["windows"][split]["first_decision_date"])
        k = dates.get_loc(first)
        assert complete[k], split  # features are available at the first decision
        x = execution_row(k, lag)
        earned = first_earned_row(k, lag)
        for name, g in rows.groupby("strategy"):
            g = g.reset_index(drop=True)
            assert g.loc[0, "date"] == dates[x] and g.loc[0, "gross_return"] == 0.0, name
            assert g.loc[1, "date"] == dates[earned], name
            held = g.loc[0, weight_columns].to_numpy(dtype=float)
            assert g.loc[1, "gross_return"] == pytest.approx(
                float(held @ returns.iloc[earned]), abs=1e-12
            )
            first_exec = executions[
                (executions["strategy"] == name) & (executions["split"] == split)
            ]
            assert first_exec["decision_date"].iloc[0] == dates[k], name
