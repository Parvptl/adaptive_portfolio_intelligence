"""Milestone B: selection rule, data-boundary guards and the evaluation config (no RL library)."""

from __future__ import annotations

import copy
import itertools
import math
from typing import Any

import pandas as pd
import pytest

from adaptive_portfolio.config import (
    ConfigError,
    EvaluationConfig,
    load_project_config,
    load_yaml,
)
from adaptive_portfolio.data.boundaries import (
    DataBoundaryError,
    assert_before_split,
    assert_training_only,
)
from adaptive_portfolio.evaluation.selection import (
    SelectionError,
    select_configuration,
    summarise_configurations,
)
from conftest import CONFIG_DIR

GRID = [(lr, n, c) for lr in (3e-4, 1e-4) for n in (512, 1024) for c in (0.0, 0.01)]


def _runs(values: dict[int, list[float]]) -> list[dict[str, Any]]:
    out = []
    for configuration, series in values.items():
        lr, n, c = GRID[configuration]
        for seed, value in zip((42, 43, 44, 45, 46), series, strict=True):
            out.append({"configuration": configuration, "learning_rate": lr, "n_steps": n,
                        "ent_coef": c, "seed": seed, "value": value})  # fmt: skip
    return out


# --------------------------------------------------------------------------
# Seed aggregation and selection (D-066, D-076)
# --------------------------------------------------------------------------


def test_median_aggregation_and_reporting() -> None:
    (summary,) = summarise_configurations(_runs({0: [0.5, -1.0, 2.0, 0.1, 0.3]}))
    assert summary.median == 0.3 and summary.minimum == -1.0 and summary.maximum == 2.0
    assert math.isclose(summary.mean, 0.38) and summary.values[44] == 2.0
    assert math.isclose(summary.std, pd.Series([0.5, -1.0, 2.0, 0.1, 0.3]).std(ddof=1))


def test_selection_picks_highest_median_and_is_order_independent() -> None:
    runs = _runs({c: [c / 10 + s / 100 for s in range(5)] for c in range(8)})
    expected = select_configuration(summarise_configurations(runs), 1e-9)
    assert expected["selected_configuration"] == 7 and expected["tied_configurations"] == [7]
    for order in itertools.islice(itertools.permutations(range(len(runs))), 5):
        shuffled = [runs[i] for i in order]
        assert select_configuration(summarise_configurations(shuffled), 1e-9) == expected


def test_ties_within_tolerance_use_the_d066_tie_break() -> None:
    same = [1.0, 1.1, 1.2, 1.3, 1.4]  # median 1.2
    runs = _runs({c: same for c in range(8)})
    picked = select_configuration(summarise_configurations(runs), 1e-9)
    # lower learning rate (1e-4: configurations 4-7) -> smaller n_steps (4, 5) -> lower ent (4)
    assert picked["selected_configuration"] == 4 and picked["tied_configurations"] == list(range(8))
    # Configuration 1 (lr 3e-4) is 5e-10 above configuration 4 (lr 1e-4): tied at 1e-9, so the
    # lower learning rate wins; with tolerance 0 the strictly higher median wins.
    near = _runs({4: same, 1: [v + 5e-10 for v in same]})
    assert select_configuration(summarise_configurations(near), 1e-9)["selected_configuration"] == 4
    assert select_configuration(summarise_configurations(near), 0.0)["selected_configuration"] == 1
    apart = _runs({4: same, 1: [v + 1e-6 for v in same]})  # outside the tolerance
    assert (
        select_configuration(summarise_configurations(apart), 1e-9)["selected_configuration"] == 1
    )


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf")])
def test_undefined_metric_stops_selection(bad: Any) -> None:
    runs = _runs({0: [0.1, 0.2, 0.3, 0.4, 0.5]})
    runs[2]["value"] = bad
    with pytest.raises(SelectionError, match="undefined"):
        summarise_configurations(runs)


def test_incomplete_or_inconsistent_seed_sets_are_refused() -> None:
    runs = _runs({0: [0.1] * 5, 1: [0.2] * 5})
    with pytest.raises(SelectionError, match="seeds"):
        summarise_configurations(runs[:-1])  # configuration 1 lacks seed 46
    mixed = copy.deepcopy(runs)
    mixed[0]["n_steps"] = 1024
    with pytest.raises(SelectionError, match="mixes"):
        summarise_configurations(mixed)
    with pytest.raises(SelectionError):
        summarise_configurations([])


# --------------------------------------------------------------------------
# Data boundaries
# --------------------------------------------------------------------------

SPLITS = load_project_config(CONFIG_DIR).experiment.splits


def _frame(dates: list[str], labels: list[str]) -> tuple[pd.DatetimeIndex, pd.Series]:
    index = pd.DatetimeIndex(dates)
    return index, pd.Series(labels, index=index)


def test_training_may_hold_training_rows_only() -> None:
    assert_training_only(*_frame(["2016-12-29", "2016-12-30"], ["train", "train"]), SPLITS)
    for dates, labels in (
        (["2016-12-30", "2017-01-03"], ["train", "validation"]),  # a validation row
        (["2016-12-30", "2017-01-03"], ["train", "train"]),  # mislabelled: dates decide too
        (["2016-12-29", "2016-12-30"], ["train", "validation"]),  # labels decide too
    ):
        with pytest.raises(DataBoundaryError, match="training"):
            assert_training_only(*_frame(dates, labels), SPLITS)


def test_validation_evaluation_may_not_hold_test_rows() -> None:
    held = _frame(["2019-12-30", "2019-12-31"], ["validation", "validation"])
    assert_before_split(*held, SPLITS, "test", "evaluation")
    for dates, labels in (
        (["2019-12-31", "2020-01-02"], ["validation", "test"]),
        (["2019-12-31", "2020-01-02"], ["validation", "validation"]),
        (["2019-12-30", "2019-12-31"], ["validation", "test"]),
    ):
        with pytest.raises(DataBoundaryError, match="evaluation"):
            assert_before_split(*_frame(dates, labels), SPLITS, "test", "evaluation")
    with pytest.raises(ValueError, match="validation' or 'test"):
        assert_before_split(*held, SPLITS, "train", "evaluation")


# --------------------------------------------------------------------------
# configs/evaluation.yaml
# --------------------------------------------------------------------------

RAW = load_yaml(CONFIG_DIR / "evaluation.yaml")


def test_default_evaluation_config_is_the_proposed_protocol() -> None:
    config = EvaluationConfig.from_dict(RAW)
    assert config.grid_id == "0f1c47502dc30d84" and config.split == "validation"
    assert config.policy_actions == "deterministic" and config.tie_tolerance == 1e-9
    assert config.tie_break == ("lower_learning_rate", "smaller_n_steps", "lower_ent_coef")
    assert (config.selection_metric, config.seed_aggregation, config.undefined_metric) == (
        "net_sharpe_annualised", "median", "fail")  # fmt: skip


def _with(path: str, value: Any) -> dict[str, Any]:
    raw = copy.deepcopy(RAW)
    *parents, key = path.split(".")
    target = raw
    for name in parents:
        target = target[name]
    target[key] = value
    return raw


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("split", "test", "sealed"),
        ("policy_actions", "sampled", "not one of"),
        ("grid_id", "not-a-grid", "16-hex"),
        ("selection.tie_tolerance", 0.5, r"\[0, 1e-3\]"),
        ("selection.tie_break", ["smaller_n_steps", "lower_learning_rate", "lower_ent_coef"],
         "D-066 order"),
        ("selection.seed_aggregation", "mean", "not one of"),
        ("selection.undefined_metric", "skip", "not one of"),
        ("baselines", "custom", "from_backtest_config"),
    ],
)  # fmt: skip
def test_invalid_evaluation_config_is_rejected(path: str, value: Any, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        EvaluationConfig.from_dict(_with(path, value))


def test_protocol_hash_is_stable_normalised_and_sensitive() -> None:
    base = EvaluationConfig.from_dict(RAW)
    assert base.protocol_hash() == EvaluationConfig.from_dict(copy.deepcopy(RAW)).protocol_hash()
    assert len(base.protocol_hash()) == 16
    # Normalised: numeric spelling, key order and the output location do not matter.
    spelled = _with("selection.tie_tolerance", 0.000000001)
    reordered = dict(reversed(list(_with("output_dir", "elsewhere/evaluations").items())))
    for variant in (spelled, reordered):
        assert EvaluationConfig.from_dict(variant).protocol_hash() == base.protocol_hash()
    # Sensitive: any protocol setting changes it.
    changed = [
        _with("selection.tie_tolerance", 2e-9),
        _with("grid_id", "0123456789abcdef"),
        _with("protocol_version", 2),
    ]
    hashes = {EvaluationConfig.from_dict(raw).protocol_hash() for raw in changed}
    assert len(hashes) == 3 and base.protocol_hash() not in hashes
