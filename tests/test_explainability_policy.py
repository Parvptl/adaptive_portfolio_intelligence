"""Milestone E end to end: policy-validation analysis on a synthetic evaluated project (``rl``).

The checkpoints are real but untrained PPO models evaluated by the real D-076 evaluator on
synthetic data (fixture shared with ``test_validation_evaluator``). Nothing real is read.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

from adaptive_portfolio.agents import evaluate as ev  # noqa: E402
from adaptive_portfolio.explainability import run as runner  # noqa: E402
from test_validation_evaluator import project  # noqa: E402, F401  (module-scoped fixture)


@pytest.fixture(scope="module")
def evaluated(project):  # noqa: F811
    plan = ev.plan_evaluation(project["config_dir"], project["dataset_dir"],
                              project["feature_dir"])  # fmt: skip
    target = plan.output_dir
    if not target.exists():
        target = ev.run_evaluation(plan)
    return {**project, "evaluation_dir": target}


def test_rebuilt_decisions_reproduce_the_evaluation_and_outputs_are_complete(evaluated, tmp_path):
    pytest.importorskip("matplotlib")
    out = runner.run_policy_validation(
        evaluated["config_dir"], evaluated["evaluation_dir"], confirm_validation_access=True,
        dataset_dir=evaluated["dataset_dir"], feature_dir=evaluated["feature_dir"],
        output_root=tmp_path, repeats=3, seed=0,
    )  # fmt: skip
    analysis = json.loads((out / "analysis.json").read_text(encoding="utf-8"))
    gaps = analysis["fidelity_max_abs_gap"]
    assert gaps and max(gaps.values()) <= 1e-9
    per_seed = pd.read_csv(out / "sensitivity_by_seed.csv")
    groups = set(per_seed["group"])
    assert {"regime_inputs", "portfolio_weights"} <= groups
    assert ((per_seed["mean_l1_change"] >= 0) & (per_seed["mean_l1_change"] <= 2)).all()
    summary = pd.read_csv(out / "regime_summary.csv")
    assert summary["strategy"].nunique() == 4 + 3  # 2 configurations x 2 seeds + 3 baselines
    assert (out / "figures" / "sensitivity_selected_configuration.png").is_file()
    again = runner.run_policy_validation(
        evaluated["config_dir"], evaluated["evaluation_dir"], confirm_validation_access=True,
        dataset_dir=evaluated["dataset_dir"], feature_dir=evaluated["feature_dir"],
        output_root=tmp_path / "again", repeats=3, seed=0, figures=False,
    )  # fmt: skip
    pd.testing.assert_frame_equal(per_seed, pd.read_csv(again / "sensitivity_by_seed.csv"))


def test_a_wrong_policy_fails_the_fidelity_check(evaluated, tmp_path):
    def contrary(path):
        return lambda obs: np.tile(np.linspace(-1, 1, 4), (len(obs), 1))

    with pytest.raises(runner.ExplainabilityError, match="not faithful"):
        runner.run_policy_validation(
            evaluated["config_dir"], evaluated["evaluation_dir"], confirm_validation_access=True,
            dataset_dir=evaluated["dataset_dir"], feature_dir=evaluated["feature_dir"],
            output_root=tmp_path, repeats=2, load_policy=contrary, figures=False,
        )  # fmt: skip
    assert not any(p for p in tmp_path.iterdir() if not p.name.startswith("_quarantine"))
