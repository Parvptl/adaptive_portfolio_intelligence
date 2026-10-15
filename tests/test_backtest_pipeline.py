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

from adaptive_portfolio.config import ConfigError, load_backtest_config, load_project_config
from adaptive_portfolio.data.cache import read_csv, write_csv
from adaptive_portfolio.data.cli import main
from adaptive_portfolio.data.pipeline import build_dataset, project_root_for
from adaptive_portfolio.data.providers import InMemoryProvider
from adaptive_portfolio.evaluation.backtest import BACKTEST_FILES, run_backtest
from adaptive_portfolio.features.engineering import FeatureDataError
from conftest import write_tiny_project

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
    config_dir = write_tiny_project(
        root, universe=["AAA", "BBB", "CCC"], start="2024-01-01", end="2024-06-28", splits=SPLITS
    )
    content = {"strategies": STRATEGIES, **backtest}
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


def _hashes(directory: Path) -> dict[str, str]:
    return {n: hashlib.sha256((directory / n).read_bytes()).hexdigest() for n in BACKTEST_FILES}


def test_outputs_and_split_containment(tmp_path: Path) -> None:
    dataset, result = _run(_project(tmp_path))
    assert sorted(p.name for p in result.output_dir.iterdir()) == sorted(BACKTEST_FILES)
    ledger = read_csv(result.output_dir / "ledger.csv", ("date", "decision_date"))
    splits = read_csv(dataset.processed_dir / "splits.csv").set_index("date")["split"]
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


def test_common_start_and_boundary_drops(tmp_path: Path) -> None:
    _, result = _run(_project(tmp_path))
    for split, by_strategy in result.metrics["metrics"].items():
        firsts = {m["first_date"] for m in by_strategy.values()}
        assert len(firsts) == 1, split  # identical evaluation window for every strategy
        # A daily strategy's decision on the split's last row would earn the next split's
        # first return; it is dropped (lag 0 -> exactly one).
        assert by_strategy["equal_weight_daily"]["decisions_dropped_at_split_end"] == 1
        assert by_strategy["buy_and_hold_equal_weight"]["rebalances"] == 1


def test_buy_and_hold_matches_closed_form(tmp_path: Path) -> None:
    dataset, result = _run(_project(tmp_path))
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
    dataset, original = _run(config_dir)
    altered_dir = tmp_path / "altered_dataset"
    shutil.copytree(dataset.processed_dir, altered_dir)
    returns = read_csv(altered_dir / "returns.csv", ("date", "period_start"))
    splits = read_csv(altered_dir / "splits.csv")["split"]
    later = (splits != "train").to_numpy()
    returns.loc[later, ["AAA", "BBB", "CCC"]] = -returns.loc[later, ["AAA", "BBB", "CCC"]] * 3
    write_csv(returns, altered_dir / "returns.csv")
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    altered = run_backtest(config, backtest, project_root_for(config_dir), dataset_dir=altered_dir)
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
    dataset, lag0 = _run(_project(tmp_path / "a"))
    _, lag1 = _run(_project(tmp_path / "b", execution_lag_sessions=1))
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
    assert default.metrics["metrics"]["test"]["equal_weight_monthly"]["annualised"] is None
    _, annual = _run(_project(tmp_path / "b", periods_per_year=252))
    assert annual.metrics["metrics"]["test"]["equal_weight_monthly"]["annualised"][
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
                "strategies": [
                    {
                        "name": "fw",
                        "type": "fixed_weights",
                        "rebalance": "never",
                        "weights": {"AAA": 0.4, "BBB": 0.4},
                    }
                ]
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
