"""E8 end to end on the tiny synthetic project (D-092; ``rl`` extra).

Trains E6L, E7B, E7T1, E7T2 and the four E8 arms (tiny budget, 2 seeds), evaluates them on the
training and validation splits, and runs ``compare-refine`` through the CLI. No market data; the
synthetic test split is never loaded.
"""

from __future__ import annotations

import copy
import json
import subprocess

import pandas as pd
import pytest
import yaml

pytestmark = pytest.mark.rl
pytest.importorskip("stable_baselines3")

from adaptive_portfolio.agents import profile_experiment as pe  # noqa: E402
from adaptive_portfolio.config import load_yaml  # noqa: E402
from adaptive_portfolio.explainability import turnover_refine_comparison as rc  # noqa: E402
from conftest import CONFIG_DIR  # noqa: E402
from test_ppo_wrapper import GIT  # noqa: E402
from test_profile_experiment import _project, _train_e0  # noqa: E402


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> pe.Context:
    context = _project(tmp_path_factory.mktemp("refine"))
    groups = load_yaml(context.config_dir / "turnover_k0.yaml")["evaluation"]["exposure_groups"]
    for k in range(4):
        raw = copy.deepcopy(load_yaml(CONFIG_DIR / f"turnover_refine_k{k}.yaml"))
        raw.update(base_configuration=0, seeds=[42, 43])
        raw["evaluation"].update(sweep_points=3, exposure_groups=groups)
        (context.config_dir / f"turnover_refine_k{k}.yaml").write_text(yaml.safe_dump(raw),
                                                                      encoding="utf-8")  # fmt: skip
    for command in (["add", "-A"], ["commit", "-q", "-m", "E8 configs"]):
        subprocess.run([*GIT, "-C", str(context.root), *command], check=True, capture_output=True)
    context = pe.load_context(context.config_dir)
    _train_e0(context)
    return context


def _arm(project: pe.Context, name: str) -> tuple[pe.Context, dict]:
    context = pe.load_context(project.config_dir, experiment_path=project.config_dir / name)
    assert {r["status"] for r in pe.train_arm(context, "main")} <= {"trained", "exists"}
    dirs = {}
    for split in ("train", "validation"):
        plan = pe.plan_profile_evaluation(context, split)
        target = plan.output_dir if plan.output_dir.exists() else pe.run_profile_evaluation(plan)
        assert pe.verify_profile_evaluation(target) == []
        dirs[split] = target
    return context, dirs


def test_e8_refinement_end_to_end(project) -> None:
    e6 = _arm(project, "dose_response_l0.yaml")[1]
    if not (project.root / "data/processed/evaluations/reference").exists():
        # The synthetic stand-in for EXP-006 (as in test_profile_experiment), from E6L's E0 rows.
        e0 = pd.read_csv(e6["validation"] / "episode_metrics.csv")
        e0 = e0[e0["experiment"] == "E0"].assign(configuration=0)
        reference = project.root / "data/processed/evaluations/reference"
        reference.mkdir(parents=True)
        e0[["configuration", "seed", "annualised.net_sharpe"]].to_csv(
            reference / "policy_metrics.csv", index=False)  # fmt: skip
    e7 = [_arm(project, f"turnover_k{k}.yaml")[1] for k in range(3)]
    arms = [_arm(project, f"turnover_refine_k{k}.yaml") for k in range(4)]
    k0 = project.config_dir / "turnover_refine_k0.yaml"
    args = ["--config-dir", str(project.config_dir), "--experiment-config", str(k0),
            "compare-refine",
            "--validation", *[str(d["validation"]) for _, d in arms],
            "--train", *[str(d["train"]) for _, d in arms],
            "--e7-validation", str(e7[0]["validation"]), str(e7[1]["validation"]),
            "--e7-train", str(e7[0]["train"]), str(e7[1]["train"]),
            "--e6-validation", str(e6["validation"]), "--e6-train", str(e6["train"]),
            "--historical", str(e7[2]["validation"]), "--historical", str(e7[2]["train"]),
            "--execute"]  # fmt: skip
    assert pe.main(args) == 0
    root = project.root / "data/processed/turnover_refine_comparisons"
    (comparison,) = [p for p in root.iterdir() if p.is_dir()]
    assert rc.verify_refine_comparison(comparison) == []
    assert pe.main(["--config-dir", str(project.config_dir), "verify", str(comparison)]) == 0

    hyp = json.loads((comparison / "hypotheses.json").read_text(encoding="utf-8"))
    assert sorted(k for k in hyp if k.startswith("H")) == sorted(f"H{i}" for i in range(1, 10))
    assert hyp["H8"]["verdict"] == "supported"  # E8B = E7B = E6L and E8T1 = E7T1, exactly
    assert hyp["H2"]["parts"][
        "logged penalty = kappa x logged traded notional in every training episode"]  # fmt: skip
    assert hyp["outcome"]["class"][0] in "ABC"
    repro = json.loads((comparison / "reproduction.json").read_text(encoding="utf-8"))
    assert len(repro) == 6 and all(r["identical"] and r["metrics_compared"] > 5
                                   for r in repro.values())  # fmt: skip

    table = pd.read_csv(comparison / "seed_table.csv")
    assert sorted(table["arm"].unique()) == sorted(["E8B", "E8T1", "E8T2", "E8T3"])
    for column in ("allocation_dispersion", "share_meaningful_changes", "target_risky_hhi"):
        assert table[column].notna().all()
    diffs = pd.read_csv(comparison / "paired_differences.csv")
    assert set(diffs["comparison"]) == {"E8T1 - E8B", "E8T2 - E8B", "E8T3 - E8B", "E8T2 - E8T1",
                                        "E8T3 - E8T1", "E8T3 - E8T2"}  # fmt: skip
    hist = json.loads((comparison / "historical.json").read_text(encoding="utf-8"))
    assert set(hist) == {"train", "validation"}
    assert all("prior experiment" in h["label"] and h["turnover_penalty"] == 0.0075
               for h in hist.values())  # fmt: skip

    context = arms[0][0]
    validation = [d["validation"] for _, d in arms]
    train = [d["train"] for _, d in arms]
    repro_dirs = {"0:E8B = E7B": [e7[0]["validation"], e7[0]["train"]],
                  "0:E8B = E6L": [e6["validation"], e6["train"]],
                  "1:E8T1 = E7T1": [e7[1]["validation"], e7[1]["train"]]}  # fmt: skip
    with pytest.raises(rc.RefineComparisonError, match="written once"):
        rc.run_refine_comparison(context, validation, train, repro_dirs,
                                 [e7[2]["validation"], e7[2]["train"]])  # fmt: skip
    with pytest.raises(rc.RefineComparisonError, match="strictly increasing"):
        rc.run_refine_comparison(context, validation[::-1], train[::-1], repro_dirs)
    with pytest.raises(rc.RefineComparisonError, match="exactly 4"):
        rc.run_refine_comparison(context, validation[:3], train[:3], repro_dirs)

    pytest.importorskip("matplotlib")
    from adaptive_portfolio.visualization.profile_figures import make_refine_figures

    written = make_refine_figures(comparison, project.root / "data" / "e8_figures")
    assert len(written) == 3 and all(w.with_suffix(".json").is_file() for w in written)
