"""Static dashboard from saved, verified results (milestone F; needs the ``viz`` extra).

The dashboard is one self-contained HTML page (figures embedded) plus a manifest of every source
file and its SHA-256. It **reads saved artifacts only**: it never trains, evaluates, loads data
rows or opens the test period. Each section is built from a named artifact; when an artifact is
missing, fails its integrity check or is not authorised, the section says so instead of showing
numbers. No metric is hard-coded.

Builds go to ``<dashboard_dir>/<build_id>/`` where ``build_id`` hashes the source files, so the
same inputs give the same folder and an existing build is never overwritten.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from adaptive_portfolio.agents.provenance import verify_checkpoint
from adaptive_portfolio.config import (
    FORBIDDEN_ARTIFACT_IDS,
    WorkflowConfig,
    load_agent_config,
    load_backtest_config,
    load_preregistration,
    load_project_config,
)
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import project_root_for, resolve_path

LABEL = (
    "Simulated historical backtests on 2007-2019 data (training and validation splits). Not live "
    "trading, not a forecast of future returns and not financial advice. The test period "
    "(2020-2024) is sealed and is not shown."
)
LABEL_TESTED = (
    "Simulated historical backtests. Development, selection and experiments E0-E12 use 2007-2019 "
    "data (training and validation splits). The test period (2020-2024) was evaluated once under "
    "a frozen pre-registration and is shown only in its own section, after verification. Not live "
    "trading, not a forecast of future returns and not financial advice."
)
# Experiments E0-E12 (training and validation only): artifact identifiers, never numbers. Every
# value shown is read from these verified outputs. Paths are relative to the repository root.
EXPERIMENTS = (
    ("E0-E3", "EXP-009, EXP-010", "D-085-D-087", "docs/profile_conditioned_ppo.md", "evaluation",
     ("data/processed/profile_evaluations/93cdfece7bca1f77",
      "data/processed/profile_evaluations/6be9dce1b006008b")),
    ("E4", "EXP-011, EXP-012", "D-088", "docs/e4_results.md", "comparison",
     ("data/processed/profile_reward_comparisons/7982b02a83f54dcf",
      "data/processed/profile_reward_comparisons/2b55a054fcf0a51f")),
    ("E5", "EXP-013, EXP-014", "D-089", "docs/e5_results.md", "comparison",
     ("data/processed/fixed_risk_comparisons/36c60c635effca26",)),
    ("E6", "EXP-015, EXP-016", "D-090", "docs/e6_results.md", "comparison",
     ("data/processed/dose_response_comparisons/0b1860cf0497e504",)),
    ("E7", "EXP-017, EXP-018", "D-091", "docs/e7_results.md", "comparison",
     ("data/processed/turnover_comparisons/9ddf7284e9c26661",)),
    ("E8", "EXP-019, EXP-020", "D-092", "docs/e8_results.md", "comparison",
     ("data/processed/turnover_refine_comparisons/2a4d574cd9c95bbc",)),
    ("E9", "EXP-021, EXP-022", "D-093", "docs/e9_results.md", "comparison",
     ("data/processed/confirmation_comparisons/0e88c06aefaeec31",)),
    ("E10", "EXP-023, EXP-024", "D-094", "docs/e10_results.md", "comparison",
     ("data/processed/walk_forward_comparisons/fb8de80f69600763",)),
    ("E11", "EXP-025, EXP-026", "D-095", "docs/e11_results.md", "comparison",
     ("data/processed/budget_comparisons/a978c872ca38b740",)),
    ("E12", "EXP-027, EXP-028", "D-096", "docs/e12_results.md", "comparison",
     ("data/processed/ablation_comparisons/c3ab3341b6287fa7",)),
)  # fmt: skip
FOLD_FIGURES = ("reports/figures/e10/e10_fold_effects.png",
                "reports/figures/e11/e11_fold_effects.png",
                "reports/figures/e12/e12_fold_effects.png")  # fmt: skip
# The one verification failure documented for EXP-030 (docs/test_results.md section 7): the
# evaluator counted the cash target at the ETF cap. Any other failure hides the test results.
KNOWN_TEST_DEFECT = "concentration does not recompute"
DEFINITIONS = [
    ("Net return", "(1 + gross)(1 - cost fraction) - 1 per session; costs on ETF traded notional."),
    ("Net Sharpe (annualised)", "√252 x mean / std (ddof 1) of daily net returns, rf = 0, "
     "funding row excluded (D-076)."),
    ("Max drawdown", "Largest peak-to-trough fall of the net value path, from initial capital."),
    ("Cost drag", "Gross minus net cumulative return over the window."),
    ("Annualised traded notional", "Recurring ETF traded notional (funding trade and cash leg "
     "excluded) / return periods x 252 (D-059)."),
    ("Regime", "Trend x volatility label from training-calibrated thresholds (D-045, Proposed); "
     "a description, not a verified market state."),
]  # fmt: skip


class DashboardError(RuntimeError):
    """Raised when a dashboard cannot be built safely."""


def _refuse(path: Path) -> None:
    if any(part in FORBIDDEN_ARTIFACT_IDS for part in Path(path).parts):
        raise DashboardError(f"{path} holds test-period results and is never read")


def _verified(directory: Path) -> dict[str, Any]:
    _refuse(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    files = meta.get("files_sha256") or {}
    bad = [n for n, h in files.items() if cache.file_sha256(directory / n) != h]
    if not files or bad:
        raise DashboardError(f"{directory}: integrity check failed for {bad or 'metadata'}")
    return meta


def _img(path: Path) -> str:
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f'<img alt="{html.escape(Path(path).stem)}" src="data:image/png;base64,{data}">'


def _table(frame: pd.DataFrame, digits: int = 4) -> str:
    return frame.to_html(index=False, float_format=lambda v: f"{v:.{digits}f}", border=0,
                         classes="t", na_rep="—")  # fmt: skip


def _missing(reason: str) -> str:
    return f'<p class="missing"><b>Not available.</b> {html.escape(reason)}</p>'


class _Build:
    def __init__(self, workdir: Path, root: Path) -> None:
        self.workdir = workdir
        self.root = Path(root).resolve()
        self.sources: dict[str, str] = {}
        self.sections: list[tuple[str, str]] = []

    def source(self, path: Path) -> Path:
        _refuse(path)
        full = Path(path).resolve()
        # Keys relative to the repository, so identical inputs give the same build id anywhere.
        key = full.relative_to(self.root) if full.is_relative_to(self.root) else full
        self.sources[key.as_posix()] = cache.file_sha256(full)
        return Path(path)

    def section(self, title: str, build: Callable[[], str]) -> None:
        try:
            body = build()
        except (DashboardError, FileNotFoundError, KeyError, ValueError) as exc:
            body = _missing(f"{type(exc).__name__}: {exc}")
        self.sections.append((title, body))


def _assumptions(root: Path, config_dir: Path) -> str:
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    env, splits = config.environment, config.experiment.splits
    rows = pd.DataFrame([
        ("Universe", ", ".join(config.data.universe)),
        ("Splits", f"train {splits.train.start}-{splits.train.end}; validation "
                   f"{splits.validation.start}-{splits.validation.end}; test "
                   f"{splits.test.start}-{splits.test.end} "
                   + ("(evaluated once, EXP-030)" if _test_outputs(root) else "(sealed)")),
        ("Costs", f"{env.transaction_cost_bps} + {env.slippage_bps} bps slippage on traded "
                  "notional (provisional, D-007/D-049)"),
        ("Timing", f"decide at close, execute {backtest.execution_lag_sessions} session later "
                   "(D-055); PPO decides weekly (D-065)"),
        ("Constraints", f"long-only, cash allowed, target cap {env.constraints.max_weight} per "
                        "ETF (D-057)"),
        ("Initial capital", f"{env.initial_capital:,.0f} (scale only)"),
    ], columns=["Assumption", "Value"])  # fmt: skip
    defs = pd.DataFrame(DEFINITIONS, columns=["Metric", "Definition"])
    return _table(rows) + "<h3>Metric definitions</h3>" + _table(defs)


def _validation(b: _Build, wf: WorkflowConfig, root: Path, plots) -> str:
    directory = resolve_path(wf.validation_evaluation_dir, root)
    meta = _verified(directory)
    if meta.get("protocol", {}).get("split") != "validation":
        raise DashboardError("the configured evaluation is not a validation evaluation")
    doc = json.loads(b.source(directory / "evaluation.json").read_text(encoding="utf-8"))
    pol = pd.read_csv(b.source(directory / "policy_metrics.csv"), float_precision="round_trip")
    base = pd.read_csv(b.source(directory / "baseline_metrics.csv"), float_precision="round_trip")
    conf = pd.read_csv(b.source(directory / "configuration_summary.csv"))
    alloc = pd.read_csv(b.source(directory / "allocations.csv"))
    ledgers = pd.read_csv(b.source(directory / "ledgers.csv"), float_precision="round_trip")
    selected = doc["selection"]["selected_configuration"]
    chosen = pol[pol["configuration"] == selected]
    columns = {"strategy": "Strategy", "annualised.net_sharpe": "Net Sharpe",
               "net_cumulative_return": "Net cum. return", "annualised.net_annualised_return":
               "Net CAGR", "annualised.net_annualised_volatility": "Net vol",
               "net_max_drawdown": "Net max DD", "gross_cumulative_return": "Gross cum. return",
               "cost_drag": "Cost drag", "annualised.annualised_traded_notional":
               "Ann. traded notional", "total_cost_value": "Total cost"}  # fmt: skip
    table = pd.concat([chosen, base])[list(columns)].rename(columns=columns)
    names = [*chosen["strategy"], *base["strategy"]]
    capital = float(ledgers["value"].iloc[0] / (1 + ledgers["net_return"].iloc[0]))
    figures = b.workdir / "figures"
    prov = {"source": {"evaluation_id": meta["evaluation_id"],
                       "ledgers_sha256": meta["files_sha256"]["ledgers.csv"]},
            "scope": "validation 2017-2019, simulated"}  # fmt: skip
    paths = plots.plot_value_paths(
        ledgers, names, figures / "validation_value_drawdown.png", initial_capital=capital,
        title=f"Validation (2017-2019): configuration {selected} seeds and baselines, net of costs",
        provenance={**prov, "method": "value / initial capital; drawdown from running peak"},
    )  # fmt: skip
    mean_alloc = plots.plot_mean_allocation(
        alloc[alloc["strategy"].isin(names)].set_index("strategy").loc[names].reset_index(),
        [c.removeprefix("mean_weight_") for c in alloc.columns
         if c.startswith("mean_weight_") and c != "mean_weight_CASH"],
        figures / "validation_mean_allocation.png", title="Time-averaged allocation (validation)",
        provenance={**prov, "method": "allocations.csv mean_weight_*"},
    )  # fmt: skip
    seeds = conf.drop(columns=[c for c in conf.columns if c in ("values_by_seed",)])
    return (
        f"<p>Evaluation <code>{meta['evaluation_id']}</code>, protocol hash "
        f"<code>{meta['protocol_hash']}</code> (D-076), commit "
        f"<code>{meta['code']['commit'][:7]}</code>. Output hashes verified. "
        f"<b>Configuration {selected} was selected on validation; every PPO policy had a lower "
        "validation net Sharpe than each of the three untuned baselines.</b> These are validation "
        "results used for selection, not out-of-sample (test) results.</p>"
        + _table(table)
        + _img(paths)
        + _img(mean_alloc)
        + "<h3>All configurations (median validation net Sharpe over seeds 42-46)</h3>"
        + _table(seeds)
    )


def _provenance(b: _Build, wf: WorkflowConfig, root: Path, config_dir: Path) -> str:
    directory = resolve_path(wf.validation_evaluation_dir, root)
    meta = _verified(directory)
    doc = json.loads((directory / "evaluation.json").read_text(encoding="utf-8"))
    selected = doc["selection"]["selected_configuration"]
    config = load_project_config(config_dir)
    backtest = load_backtest_config(config_dir / "backtest.yaml")
    experiments = resolve_path(load_agent_config(config_dir / "agent.yaml").output_dir, root)
    rows = []
    for c in meta["checkpoints"]:
        if c["configuration"] != selected:
            continue
        problems = verify_checkpoint(
            experiments / c["run_id"], config, backtest, expected_model_sha256=c["model_sha256"],
            dataset_dir=resolve_path(wf.dataset_dir, root),
            feature_dir=resolve_path(wf.feature_dir, root),
        )  # fmt: skip
        rows.append({"seed": c["seed"], "run id": c["run_id"],
                     "model.zip SHA-256": c["model_sha256"][:16] + "…",
                     "status": "verified" if not problems else "; ".join(problems)})  # fmt: skip
    return _table(pd.DataFrame(rows))


def _baselines(b: _Build, wf: WorkflowConfig, root: Path) -> str:
    directory = resolve_path(wf.baseline_backtest_dir, root)
    _refuse(directory)
    meta = json.loads(b.source(directory / "metadata.json").read_text(encoding="utf-8"))
    if "test" in meta.get("evaluated_splits", ["test"]):
        raise DashboardError("the configured backtest includes the test split; not shown")
    metrics = json.loads(b.source(directory / "metrics.json").read_text(encoding="utf-8"))
    rows = []
    for split in ("train", "validation"):
        for name, m in metrics["metrics"][split].items():
            a = m.get("annualised") or {}
            rows.append({"split": split, "strategy": name, "Net Sharpe": a.get("net_sharpe"),
                         "Net cum. return": m["net_cumulative_return"],
                         "Net max DD": m["net_max_drawdown"], "Cost drag": m["cost_drag"],
                         "Ann. traded notional": a.get("annualised_traded_notional")})  # fmt: skip
    return (
        f"<p>Backtest <code>{meta['backtest_id']}</code> (EXP-002): untuned conventional "
        "baselines.</p>" + _table(pd.DataFrame(rows))
    )


def _analyses(b: _Build, wf: WorkflowConfig, root: Path, mode: str) -> str:
    base = resolve_path(wf.explainability_root, root)
    found = []
    for directory in sorted(base.glob("*/")) if base.is_dir() else []:
        if directory.name.startswith("_") or not (directory / "analysis.json").is_file():
            continue
        meta = _verified(directory)
        if meta.get("mode") == mode:
            found.append((meta.get("started_at", ""), directory, meta))
    if not found:
        raise DashboardError(
            "no saved analysis of this kind. The policy analysis on validation decisions (D-068) "
            "needs an explicit authorisation before it may be run."
            if mode == "policy-validation"
            else "run: python scripts/workflow.py explain"
        )
    found.sort(key=lambda item: item[0])
    _, directory, meta = found[-1]
    superseded = [d.name for _, d, _ in found[:-1]]
    analysis = json.loads(b.source(directory / "analysis.json").read_text(encoding="utf-8"))
    summary = pd.read_csv(b.source(directory / "regime_summary.csv"))
    counts = summary[summary["regime"] != "all"].pivot_table(
        index="regime", columns="strategy", values="sessions", aggfunc="first", sort=False
    )
    if mode == "policy-validation":  # identical for every strategy: one column
        counts = counts.iloc[:, :1].set_axis(["sessions"], axis=1)
    parts = [
        f"<p>Analysis <code>{directory.name}</code> ({html.escape(analysis['status'])})"
        + (" <b>Run from uncommitted code.</b>" if analysis.get("uncommitted_code") else "")
        + "</p>"
        + (
            '<p class="missing">Earlier analyses of this kind are <b>superseded</b> by '
            f"<code>{directory.name}</code> and are kept but not shown: "
            + ", ".join(f"<code>{s}</code>" for s in superseded)
            + " (see the experiment log).</p>"
            if superseded
            else ""
        )
        + "<h3>Sessions per regime</h3>"
        + _table(counts.reset_index(), 0)
    ]
    figures = analysis.get("figures", [])
    if mode == "policy-validation":  # D-097: only the selected configuration and the baselines
        selected = analysis["parameters"]["selected_configuration"]
        keep = (f"ppo_c{selected}_", "equal_weight", "inverse_volatility", "sensitivity_")
        figures = [f for f in figures if any(k in Path(f).name for k in keep)]
        shown = summary[~summary["strategy"].str.startswith("ppo_")
                        | summary["strategy"].str.startswith(f"ppo_c{selected}_")]  # fmt: skip
        cols = ["strategy", "regime", "sessions", "mean_weight_CASH", "mean_risky_hhi",
                "annualised_turnover", "annualised_volatility"]  # fmt: skip
        parts.append(
            f"<p>Configuration {selected} (seeds 42-46) and the three baselines only; other "
            "configurations are not compared (D-097). Regimes with at least the minimum number "
            "of sessions:</p>"
            + _table(shown[shown["sufficient"].astype(bool) & (shown["regime"] != "all")][cols], 3)
        )
    for figure in figures:
        parts.append(_img(b.source(directory / figure)))
    if (directory / "sensitivity_summary.csv").is_file():
        parts.append(
            "<h3>Sensitivity of decided targets (median over seeds)</h3>"
            + _table(pd.read_csv(b.source(directory / "sensitivity_summary.csv")))
        )
    parts.append(
        "<h3>Limitations</h3><ul>"
        + "".join(f"<li>{html.escape(x)}</li>" for x in analysis.get("limitations", []))
        + "</ul>"
    )
    del meta
    return "".join(parts)


def _verify_saved(directory: Path, meta: dict[str, Any]) -> list[str]:
    """The repository's verification for a saved comparison (same routing as the CLI)."""
    from adaptive_portfolio.explainability import (
        ablation_comparison,
        budget_comparison,
        confirmation_comparison,
        dose_response_comparison,
        fixed_risk_comparison,
        profile_comparison,
        turnover_comparison,
        turnover_refine_comparison,
        walk_forward_comparison,
    )

    routes = {
        "ablation": ablation_comparison.verify_ablation_comparison,
        "budget": budget_comparison.verify_budget_comparison,
        "walk_forward": walk_forward_comparison.verify_walk_forward_comparison,
        "confirmation": confirmation_comparison.verify_confirmation,
        "turnover_refine": turnover_refine_comparison.verify_refine_comparison,
        "turnover": turnover_comparison.verify_turnover_comparison,
        "dose_response": dose_response_comparison.verify_dose_comparison,
    }
    if meta.get("kind") in routes:
        return routes[meta["kind"]](directory)
    if "evaluations" in meta:
        return fixed_risk_comparison.verify_fixed_comparison(directory)
    return profile_comparison.verify_comparison(directory)


def _verdicts(hypotheses: dict[str, Any]) -> str:
    found = [v.get("verdict") for k, v in hypotheses.items()
             if k.startswith("H") and isinstance(v, dict) and v.get("verdict")]  # fmt: skip
    if not found:
        return "—"
    order = ("supported", "partially supported", "not supported")
    counts = [f"{sum(1 for v in found if v == name)} {name}" for name in order]
    return f"{len(found)} hypotheses: " + ", ".join(counts)


def _experiments(b: _Build, root: Path) -> str:
    rows, missing = [], []
    for name, records, decision, report, kind, paths in EXPERIMENTS:
        directories = [resolve_path(Path(p), root) for p in paths]
        if not all(d.is_dir() for d in directories):
            missing.append(name)
            continue
        status, outcome, verdicts, folds = (
            [],
            "no prespecified outcome class (see the report)",
            "—",
            "—",
        )
        for directory in directories:
            meta = json.loads(b.source(directory / "metadata.json").read_text(encoding="utf-8"))
            if kind == "evaluation":
                _verified(directory)
                status.append(f"{directory.name}: hashes verified")
                continue
            problems = _verify_saved(directory, meta)
            status.append(
                f"{directory.name}: "
                + ("VERIFIED" if not problems else "FAILED (" + "; ".join(problems) + ")")
            )
            hyp = json.loads(b.source(directory / "hypotheses.json").read_text(encoding="utf-8"))
            if isinstance(hyp.get("outcome"), dict):
                outcome = hyp["outcome"]["class"]
            verdicts = _verdicts(hyp)
            if (directory / "fold_summary.json").is_file():
                summary = json.loads(
                    b.source(directory / "fold_summary.json").read_text(encoding="utf-8")
                )
                folds = " · ".join(f"{f} {v['mean']:+.3f} ({v['class']})"
                                   for f, v in summary["folds"].items())  # fmt: skip
        rows.append({"Experiment": name, "Records": records, "Decision": decision,
                     "Verification": "; ".join(status), "Prespecified outcome": outcome,
                     "Hypotheses": verdicts,
                     "Validation mean ΔSharpe by fold (class)": folds,
                     "Report": report})  # fmt: skip
    if not rows:
        raise DashboardError("no saved E0-E12 outputs in this repository")
    parts = [
        "<p>Training and validation only (2007-2019). Each output is re-verified with the "
        "repository's own verification at build time. Outcomes are what each prespecified rule "
        "gave; design choices are Provisional (delegated), not team-reviewed. In every experiment "
        "every PPO arm stays below the simple baselines.</p>",
        _table(pd.DataFrame(rows), 3),
    ]
    if missing:
        parts.append(_missing("outputs not found for: " + ", ".join(missing)))
    for figure in FOLD_FIGURES:
        path = resolve_path(Path(figure), root)
        if path.is_file():
            parts.append(f"<h3>{html.escape(path.stem)}</h3>" + _img(b.source(path)))
    return "".join(parts)


def _verified_test(root: Path, config_dir: Path) -> tuple[Path, Any, list[str]] | None:
    """The single test evaluation of the frozen pre-registration, with its verification."""
    prereg = load_preregistration(config_dir / "preregistration.yaml")
    outputs = _test_outputs(root)
    if not outputs or prereg.status != "frozen":
        return None
    base = resolve_path(Path("data/processed/test_evaluations"), root)
    matches = [base / name for name in outputs if json.loads(
        (base / name / "metadata.json").read_text(encoding="utf-8")
    ).get("preregistration_sha256") == prereg.sha256()]  # fmt: skip
    if len(matches) != 1:
        raise DashboardError(f"expected one test evaluation of the frozen pre-registration, "
                             f"found {len(matches)}")  # fmt: skip
    from adaptive_portfolio.agents.test_evaluate import verify_test_evaluation

    return matches[0], prereg, verify_test_evaluation(matches[0], prereg)


def _test_results(b: _Build, root: Path, config_dir: Path, plots) -> str:
    found = _verified_test(root, config_dir)
    if found is None:
        return _missing(
            "The test period is sealed. Gate 3 is not approved and no test evaluation exists."
            if not _test_outputs(root)
            else "A test evaluation folder exists but the pre-registration is not frozen."
        )
    directory, prereg, problems = found
    other = [p for p in problems if KNOWN_TEST_DEFECT not in p]
    if other:
        raise DashboardError("test verification failed: " + "; ".join(other))
    from adaptive_portfolio.agents.test_evaluate import _executions_from_ledger
    from adaptive_portfolio.evaluation import risk

    rt = {"float_precision": "round_trip"}
    meta = json.loads(b.source(directory / "metadata.json").read_text(encoding="utf-8"))
    doc = json.loads(b.source(directory / "evaluation.json").read_text(encoding="utf-8"))
    comparison = pd.read_csv(b.source(directory / "primary_comparison.csv"), **rt)
    descriptive = pd.read_csv(b.source(directory / "descriptive_differences.csv"), **rt)
    metrics = pd.concat(
        [
            pd.read_csv(b.source(directory / "policy_metrics.csv"), **rt),
            pd.read_csv(b.source(directory / "baseline_metrics.csv"), **rt),
        ]
    )
    stress = pd.read_csv(b.source(directory / "stress_windows.csv"), **rt)
    conc = pd.read_csv(b.source(directory / "concentration.csv"), **rt)
    ledgers = pd.read_csv(b.source(directory / "ledgers.csv"), **rt)
    primary = ledgers[ledgers["scenario"] == "primary"]
    endpoint = doc["primary_endpoint"]
    columns = {"strategy": "Strategy", "annualised.net_sharpe": "Net Sharpe",
               "gross_sharpe_annualised": "Gross Sharpe",
               "net_cumulative_return": "Net cum. return",
               "annualised.net_annualised_return": "Net CAGR",
               "annualised.net_annualised_volatility": "Net vol",
               "net_max_drawdown": "Net max DD", "cost_drag": "Cost drag",
               "annualised.annualised_traded_notional": "Ann. traded notional"}  # fmt: skip
    table = metrics[metrics["scenario"] == "primary"][list(columns)].rename(columns=columns)
    costs = metrics.pivot_table(
        index="strategy", columns="scenario", values="annualised.net_sharpe", sort=False
    ).reset_index()
    cap = float(meta["environment"]["constraints"]["max_weight"])
    conc["share_executions_at_cap (corrected, ETF targets only)"] = [
        risk.concentration(primary[primary["strategy"] == s],
                           _executions_from_ledger(primary[primary["strategy"] == s]),
                           cap)["share_executions_at_cap"]
        for s in conc["strategy"]]  # fmt: skip
    names = list(table["Strategy"])
    capital = float(primary["value"].iloc[0] / (1 + primary["net_return"].iloc[0]))
    figure = plots.plot_value_paths(
        primary, names, b.workdir / "figures" / "test_value_drawdown.png",
        initial_capital=capital,
        title="Test (2020-2024): configuration 4 seeds and baselines, net of costs",
        provenance={"source": {"evaluation_id": meta["evaluation_id"],
                               "ledgers_sha256": meta["files_sha256"]["ledgers.csv"]},
                    "scope": "test 2020-2024, simulated, single pre-registered run",
                    "method": "value / initial capital; drawdown from running peak"},
    )  # fmt: skip
    note = (
        "<p><b>Verification:</b> every pre-registered quantity recomputes"
        + (" except: " + "; ".join(html.escape(p) for p in problems)
           + ". This is the documented evaluator defect (cash counted at the ETF cap); the "
           "corrected column below is recomputed from the saved ledgers (ETF targets only)."
           if problems else ".")
        + "</p>"
    )  # fmt: skip
    return (
        f"<p>Evaluation <code>{meta['evaluation_id']}</code> (EXP-030), pre-registration "
        f"<code>{prereg.sha256()[:16]}…</code>, protocol hash <code>{prereg.protocol_hash()}"
        f"</code>, commit <code>{meta['code']['commit'][:7]}</code>. Executed once; the candidate "
        "was fixed before the test period was read. No result here is used to select, tune or "
        "retrain anything.</p>"
        + note
        + f"<p><b>Primary endpoint</b> ({html.escape(endpoint['seed_aggregation'])} over seeds of "
        f"the annualised net Sharpe): <b>{endpoint['value']:.4f}</b>.</p>"
        + _table(
            comparison[
                [
                    "comparator",
                    "estimate",
                    "ci_low",
                    "ci_high",
                    "block_length",
                    "resamples",
                    "p_value",
                ]
            ]
        )
        + "<h3>Descriptive differences (no interval)</h3>"
        + _table(descriptive[["baseline", "difference"]])
        + "<h3>Primary accounting</h3>"
        + _table(table)
        + _img(figure)
        + "<h3>Net Sharpe by cost scenario (fixed-action accounting)</h3>"
        + _table(costs)
        + "<h3>Stress windows (descriptive slices of one history)</h3>"
        + _table(
            stress[
                [
                    "window",
                    "strategy",
                    "realised_sessions",
                    "status",
                    "net_return",
                    "max_drawdown",
                    "annualised_volatility",
                ]
            ]
        )
        + "<h3>Concentration</h3>"
        + _table(conc)
    )


def _test_outputs(root: Path) -> list[str]:
    base = resolve_path(Path("data/processed/test_evaluations"), root)
    return sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []


def _gate3(b: _Build, config_dir: Path, root: Path) -> str:
    path = b.source(config_dir / "preregistration.yaml")
    prereg = load_preregistration(path)
    open_items = prereg.open_items()
    rows = pd.DataFrame(
        [
            ("Pre-registration status", prereg.status.upper()),
            ("Pre-registration SHA-256", prereg.sha256()),
            ("Protocol hash", prereg.protocol_hash()),
            ("Items blocking execution", f"{len(open_items)}: " + ", ".join(open_items)),
            ("Test evaluator", "implemented (scripts/evaluate_test.py); plan mode reads no data"),
            ("Test evaluation outputs", ", ".join(_test_outputs(root)) or "none"),
        ],
        columns=["Item", "Value"],
    )
    return (
        "<p>The test evaluator refuses to run unless this pre-registration is frozen, its hash "
        "matches an explicit unsealing authorisation, and the code is committed at the named "
        "commit. Values in a draft are proposals, not decisions.</p>" + _table(rows)
    )


def build_dashboard(config_dir: Path, workflow: WorkflowConfig) -> Path:
    """Build the dashboard; returns the build folder (reused if the same sources were built)."""
    from adaptive_portfolio.visualization import plots

    config_dir = Path(config_dir)
    root = project_root_for(config_dir)
    output_root = resolve_path(workflow.dashboard_dir, root)
    staging = output_root / "_staging"
    if staging.exists():
        raise DashboardError(f"{staging} exists (an interrupted build?); inspect and remove it")
    staging.mkdir(parents=True)
    b = _Build(staging, root)
    b.section("Assumptions and definitions", lambda: _assumptions(root, config_dir))
    b.section("Validation evaluation (EXP-006)", lambda: _validation(b, workflow, root, plots))
    b.section("Selected checkpoint provenance", lambda: _provenance(b, workflow, root, config_dir))
    b.section("Baselines, training and validation (EXP-002)", lambda: _baselines(b, workflow, root))
    b.section("Experiments E0-E12 (training and validation)", lambda: _experiments(b, root))
    b.section("Regime analysis: baselines, training split",
              lambda: _analyses(b, workflow, root, "baselines-train"))  # fmt: skip
    b.section("Explainability: selected PPO policy (D-068)",
              lambda: _analyses(b, workflow, root, "policy-validation"))  # fmt: skip
    b.section(
        "Stress tests",
        lambda: (
            _missing(
                "Gate 3 item G3-6 (stress-window rule and source) is undecided; no stress test "
                "exists."
            )
            if not _test_outputs(root)
            else "<p>The pre-registered stress windows lie inside the test period; they are "
            "shown in the out-of-sample test section below.</p>"
        ),
    )
    b.section("Gate 3 pre-registration and test evaluator", lambda: _gate3(b, config_dir, root))
    b.section(
        "Out-of-sample test results (2020-2024)",
        lambda: _test_results(b, root, config_dir, plots),
    )
    body = "".join(f"<h2>{html.escape(t)}</h2>{s}" for t, s in b.sections)
    page = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        "<title>Adaptive Portfolio Intelligence: research dashboard</title><style>"
        "body{font-family:system-ui,sans-serif;max-width:1100px;margin:2em auto;color:#222}"
        ".label{background:#fff4ce;border:1px solid #e0c060;padding:.8em}"
        ".missing{background:#f3f3f3;border-left:4px solid #999;padding:.6em}"
        "table.t{border-collapse:collapse;font-size:.85em;margin:.6em 0}"
        "table.t td,table.t th{border-bottom:1px solid #ddd;padding:.25em .6em;text-align:right}"
        "img{max-width:100%;margin:.6em 0}</style></head><body>"
        "<h1>Adaptive Portfolio Intelligence: research dashboard</h1>"
        f'<p class="label">{html.escape(LABEL_TESTED if _test_outputs(root) else LABEL)}</p>'
        f"{body}</body></html>"
    )
    (staging / "index.html").write_text(page, encoding="utf-8")
    code = {
        Path(m.__file__).name: cache.file_sha256(Path(m.__file__))
        for m in (sys.modules[__name__], plots)
    }  # a code change gives a new build
    build_id = cache.short_hash({"sources": b.sources, "code": code})
    target = output_root / build_id
    cache.write_json({"build_id": build_id, "sources_sha256": b.sources, "code_sha256": code,
                      "built_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                      "sections": [t for t, _ in b.sections]},
                     staging / "dashboard_manifest.json")  # fmt: skip
    if target.exists():
        import shutil

        shutil.rmtree(staging)  # same sources: the existing build is kept unchanged
        return target
    staging.rename(target)
    return target
