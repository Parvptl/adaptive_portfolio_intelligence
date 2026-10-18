"""Run the conventional baselines through the simulator on a processed dataset (milestone 4).

Evaluated splits (decision D-056): by default only ``train`` and ``validation``. The
``test`` split is reserved for the final pre-registered evaluation and is simulated,
written and reported only when the caller passes ``include_test=True`` (CLI:
``--include-test``). The evaluated splits are part of the backtest id. Nothing is ever
fitted on any split; the baselines have no fitted parameters beyond fixed lookbacks.

Protocol per evaluated split (decision D-051), identical for every strategy:

* Rows are the split's return rows ``[s, e]`` (D-038). A decision at row ``k`` uses the
  return history of rows ``<= k``, which may include earlier splits (historical lookback,
  not leakage). No parameter is fitted on later data.
* Common start: the first decision row is the first row ``k0 >= s`` at which *every*
  strategy has its required history and the configured common history
  (``k0 + 1 >= BacktestConfig.required_history``, e.g. the 126-session feature warm-up),
  so all strategies are evaluated over the same window. Only the start of the dataset
  (training) is affected.
* Each split is an independent simulation that starts in cash at ``initial_capital`` at
  the first execution row ``x0 = k0 + lag``. The last earned return is the split's last
  row ``e``. A decision whose first earned row ``k + lag + 1`` would be ``> e`` belongs to
  the next split's returns, so it is dropped (and counted); this is exactly the
  ``boundary`` rule of ``features.next_period_targets`` (shared ``timing`` module). No
  result for one split ever contains another split's return.

Outputs go to ``<backtest.output_dir>/<backtest_id>/`` and are deterministic.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from adaptive_portfolio.baselines.strategies import decision_rows, target_weights
from adaptive_portfolio.config import BacktestConfig, ConfigError, ProjectConfig
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.pipeline import relative_to_root, resolve_path
from adaptive_portfolio.data.splits import PARTITIONS
from adaptive_portfolio.evaluation.metrics import annual_to_periodic_rate
from adaptive_portfolio.evaluation.performance import summarize_window
from adaptive_portfolio.evaluation.simulator import SimulationError, SimulationSettings, simulate
from adaptive_portfolio.features.engineering import FeatureDataError
from adaptive_portfolio.features.pipeline import load_processed_inputs, locate_dataset_dir
from adaptive_portfolio.timing import execution_row, last_evaluable_decision

logger = logging.getLogger(__name__)

# Version 2 (milestone 4.1): evaluated splits recorded and part of the id; test opt-in.
BACKTEST_PIPELINE_VERSION = "2"
DEFAULT_SPLITS = ("train", "validation")
TEST_SPLIT = "test"
BACKTEST_FILES = (
    "ledger.csv",
    "executions.csv",
    "metrics.json",
    "metrics.csv",
    "backtest_report.md",
    "metadata.json",
)
CONVENTIONS = {
    "timing": "decide at close of d (data <= d); execute at close of d + lag (observed "
    "sessions); earn from the next session (D-048, proposal for D-013); lag 1 is the proposed "
    "primary convention, lag 0 an idealised sensitivity case (D-055)",
    "costs": "cost = (transaction_cost_bps + slippage_bps)/1e4 x traded notional (non-cash "
    "legs) x value at execution; deducted pro rata; initial funding charged if configured "
    "(D-049, proposal for D-031)",
    "constraints": "long-only, no leverage (sum <= 1), fractional weights, implicit cash "
    "earning the periodic risk-free rate (D-050); max_weight applies to target weights at "
    "execution, holdings may drift above it between rebalances (D-057)",
    "protocol": "independent simulation per split from cash; common start; boundary-crossing "
    "decisions dropped (D-051); test split evaluated only on explicit request (D-056)",
    "metrics": "per-session metrics; annualised only if periods_per_year is set (D-052, D-023)",
}


@dataclass(frozen=True)
class BacktestResult:
    output_dir: Path
    backtest_id: str
    metrics: dict[str, Any]


def backtest_config_to_dict(config: BacktestConfig) -> dict[str, Any]:
    return {
        "execution_lag_sessions": config.execution_lag_sessions,
        "charge_initial_funding": config.charge_initial_funding,
        "periods_per_year": config.periods_per_year,
        "allow_multi_session_returns": config.allow_multi_session_returns,
        "common_start_history_sessions": config.common_start_history_sessions,
        "strategies": [
            {
                "name": s.name,
                "type": s.type,
                "rebalance": s.rebalance,
                "lookback": s.lookback,
                "weights": dict(s.weights) if s.weights else None,
            }
            for s in config.strategies
        ],
    }


def _environment_dict(config: ProjectConfig) -> dict[str, Any]:
    env = config.environment
    c = env.constraints
    return {
        "initial_capital": env.initial_capital,
        "transaction_cost_bps": env.transaction_cost_bps,
        "slippage_bps": env.slippage_bps,
        "rebalance_frequency": env.rebalance_frequency,
        "risk_free_rate": env.risk_free_rate,
        "constraints": {
            "long_only": c.long_only,
            "allow_cash": c.allow_cash,
            "min_weight": c.min_weight,
            "max_weight": c.max_weight,
            "max_turnover": c.max_turnover,
        },
    }


def evaluated_splits(include_test: bool) -> tuple[str, ...]:
    """Splits a backtest evaluates: train and validation, plus test only on request (D-056)."""
    if not isinstance(include_test, bool):
        raise ConfigError("include_test must be true or false")
    return (*DEFAULT_SPLITS, TEST_SPLIT) if include_test else DEFAULT_SPLITS


def backtest_identity(
    config: ProjectConfig,
    backtest: BacktestConfig,
    processed_id: str,
    *,
    include_test: bool = False,
) -> dict[str, Any]:
    """Everything that defines a backtest run (hashed into its id)."""
    return {
        "processed_dataset_id": processed_id,
        "backtest": backtest_config_to_dict(backtest),
        "environment": _environment_dict(config),
        "evaluated_splits": list(evaluated_splits(include_test)),
        "pipeline_version": BACKTEST_PIPELINE_VERSION,
    }


def backtest_output_dir(
    config: ProjectConfig,
    backtest: BacktestConfig,
    project_root: Path,
    processed_id: str,
    *,
    include_test: bool = False,
) -> tuple[Path, str]:
    identity = backtest_identity(config, backtest, processed_id, include_test=include_test)
    backtest_id = cache.short_hash(identity)
    return resolve_path(backtest.output_dir, project_root) / backtest_id, backtest_id


def simulation_settings(config: ProjectConfig, backtest: BacktestConfig) -> SimulationSettings:
    env = config.environment
    if env.constraints.max_turnover is not None:
        raise ConfigError(
            "environment.constraints.max_turnover is set, but which turnover measure a cap "
            "constrains is undecided (D-031); the simulator does not enforce caps yet. Set it to "
            "null."
        )
    if env.risk_free_rate == 0:
        cash_return = 0.0
    elif backtest.periods_per_year is None:
        raise ConfigError(
            "a non-zero risk_free_rate needs backtest.periods_per_year to convert it to a "
            "per-session cash return, and D-023 is open"
        )
    else:
        cash_return = annual_to_periodic_rate(env.risk_free_rate, backtest.periods_per_year)
    return SimulationSettings(
        initial_capital=env.initial_capital,
        cost_rate=(env.transaction_cost_bps + env.slippage_bps) / 10_000,
        cash_return=cash_return,
        constraints=env.constraints,
        charge_initial_funding=backtest.charge_initial_funding,
    )


def split_bounds(labels: pd.Series, split: str) -> tuple[int, int]:
    positions = [i for i, label in enumerate(labels.to_numpy()) if label == split]
    if not positions:
        raise SimulationError(f"split {split!r} has no rows")
    if positions != list(range(positions[0], positions[-1] + 1)):
        raise SimulationError(f"split {split!r} rows are not contiguous")
    return positions[0], positions[-1]


def run_backtest(
    config: ProjectConfig,
    backtest: BacktestConfig,
    project_root: Path,
    *,
    dataset_dir: Path | None = None,
    provider_name: str | None = None,
    include_test: bool = False,
) -> BacktestResult:
    """Simulate every strategy on the evaluated splits and write the outputs.

    ``include_test`` (default False) adds the test split, which is reserved for the final
    pre-registered evaluation (D-056). Train and validation results do not depend on it.
    """
    splits = evaluated_splits(include_test)
    backtest.check_against(config.data, config.environment)
    settings = simulation_settings(config, backtest)
    directory = locate_dataset_dir(
        config, project_root, dataset_dir=dataset_dir, provider_name=provider_name
    )
    # Test-period rows are not even read unless the test split is requested (D-056).
    inputs = load_processed_inputs(directory, config, exclude_test=not include_test)
    multi = int((inputs.sessions_spanned > 1).sum())
    if multi and not backtest.allow_multi_session_returns:
        raise FeatureDataError(
            f"{multi} return(s) span more than one session; set "
            "backtest.allow_multi_session_returns: true to accept this explicitly"
        )
    returns = inputs.asset_returns
    dates = returns.index
    universe = tuple(returns.columns)
    lag = backtest.execution_lag_sessions
    required = backtest.required_history

    ledgers, executions, metrics, windows = [], [], {}, {}
    for split in (p for p in PARTITIONS if p in splits):
        s, e = split_bounds(inputs.split_labels, split)
        k0 = max(s, required - 1)
        x0 = execution_row(k0, lag)
        if x0 >= e - 1:
            raise SimulationError(
                f"{split}: not enough rows after warm-up ({required} sessions) and lag {lag} "
                "for at least two returns"
            )
        windows[split] = {
            "split_first_date": dates[s].date().isoformat(),
            "first_decision_date": dates[k0].date().isoformat(),
            "first_execution_date": dates[x0].date().isoformat(),
            "last_return_date": dates[e].date().isoformat(),
            "warm_up_rows_skipped": k0 - s,
            "required_history_sessions": required,
        }
        metrics[split] = {}
        for strategy in backtest.strategies:
            all_decisions = decision_rows(strategy.rebalance, dates, k0, e)
            kept = [k for k in all_decisions if k <= last_evaluable_decision(e, lag)]
            targets = {
                k: target_weights(
                    strategy,
                    returns.iloc[: k + 1],
                    universe,
                    config.environment.constraints.max_weight,
                )
                for k in kept
            }
            result = simulate(returns, targets, lag=lag, window=(x0, e), settings=settings)
            summary = summarize_window(
                result.ledger,
                initial_capital=settings.initial_capital,
                annual_risk_free_rate=config.environment.risk_free_rate,
                periods_per_year=backtest.periods_per_year,
            )
            summary["decisions_dropped_at_split_end"] = len(all_decisions) - len(kept)
            metrics[split][strategy.name] = summary
            ledgers.append(result.ledger.assign(strategy=strategy.name, split=split))
            executions.append(result.executions.assign(strategy=strategy.name, split=split))

    processed_id = inputs.metadata.get("processed_dataset_id", "unknown")
    identity = backtest_identity(config, backtest, processed_id, include_test=include_test)
    target, backtest_id = backtest_output_dir(
        config, backtest, project_root, processed_id, include_test=include_test
    )
    document = {
        "status": "PROVISIONAL: conventions D-048 to D-057 are Proposed; D-007, D-015 are "
        "provisional; not a validated comparison",
        "data_origin": inputs.metadata.get("data_origin"),
        "evaluated_splits": list(splits),
        "test_split": (
            "INCLUDED on explicit request: reserved for the final pre-registered evaluation (D-056)"
            if include_test
            else "excluded (default; D-056)"
        ),
        "windows": windows,
        "metrics": metrics,
    }
    metadata = {
        "metadata_schema_version": 1,
        "backtest_id": backtest_id,
        "input": {
            "processed_dataset_id": processed_id,
            "raw_dataset_id": inputs.metadata.get("raw_dataset_id"),
            "data_origin": inputs.metadata.get("data_origin"),
            "dataset_dir": relative_to_root(directory, project_root),
        },
        **identity,
        "conventions": CONVENTIONS,
        "software": cache.software_versions(),
    }

    staging = cache.staging_directory(target)
    try:
        ledger = pd.concat(ledgers, ignore_index=True)
        ledger = ledger[
            ["strategy", "split", *[c for c in ledger.columns if c not in ("strategy", "split")]]
        ]
        cache.write_csv(ledger, staging / "ledger.csv")
        execs = pd.concat(executions, ignore_index=True)
        execs = execs[
            ["strategy", "split", *[c for c in execs.columns if c not in ("strategy", "split")]]
        ]
        cache.write_csv(execs, staging / "executions.csv")
        cache.write_json(document, staging / "metrics.json")
        cache.write_csv(_flat_metrics(metrics), staging / "metrics.csv")
        (staging / "backtest_report.md").write_text(
            render_backtest_markdown(document, metadata), encoding="utf-8", newline="\n"
        )
        cache.write_json(metadata, staging / "metadata.json")
        cache.replace_directory(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    logger.info("backtest written to %s", target)
    return BacktestResult(target, backtest_id, document)


FLAT_KEYS = (
    "first_date",
    "last_date",
    "return_periods",
    "rebalances",
    "gross_cumulative_return",
    "net_cumulative_return",
    "cost_drag",
    "gross_max_drawdown",
    "net_max_drawdown",
    "net_volatility_per_session",
    "net_sharpe_per_session_rf0",
    "total_traded_notional",
    "total_cost_fraction",
    "total_cost_value",
    "final_value",
    "decisions_dropped_at_split_end",
    "funding_traded_notional",
    "recurring_traded_notional",
)


def _flat_metrics(metrics: dict[str, dict[str, dict[str, Any]]]) -> pd.DataFrame:
    rows = []
    for split, by_strategy in metrics.items():
        for name, summary in by_strategy.items():
            row = {"split": split, "strategy": name, **{k: summary[k] for k in FLAT_KEYS}}
            annual = summary["annualised"] or {}
            for key in ("net_annualised_return", "net_annualised_volatility", "net_sharpe"):
                row[key] = annual.get(key)
            rows.append(row)
    return pd.DataFrame(rows)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2%}"


def render_backtest_markdown(document: dict[str, Any], metadata: dict[str, Any]) -> str:
    lines = [
        "# Baseline backtest report",
        "",
        f"> {document['status']}.",
        "> Backtest results describe historical simulations under stated assumptions; they are "
        "not evidence of future performance.",
    ]
    if document["data_origin"] in ("synthetic", "in_memory"):
        lines.append("> NOT MARKET DATA: synthetic/fixture input.")
    lines += [
        "",
        f"Evaluated splits: {', '.join(document['evaluated_splits'])}. "
        f"Test split: {document['test_split']}.",
    ]
    env = metadata["environment"]
    lines += [
        "",
        "## Conventions",
        "",
        *[f"- **{k}:** {v}" for k, v in metadata["conventions"].items()],
        f"- Execution lag: {metadata['backtest']['execution_lag_sessions']} session(s); cost "
        f"rate {env['transaction_cost_bps'] + env['slippage_bps']} bps of traded notional; "
        f"initial capital {env['initial_capital']}; max weight {env['constraints']['max_weight']}",
        "",
    ]
    for split, by_strategy in document["metrics"].items():
        window = document["windows"][split]
        lines += [
            f"## {split}",
            "",
            f"Window: decisions from {window['first_decision_date']}, first execution "
            f"{window['first_execution_date']}, last return {window['last_return_date']} "
            f"({window['warm_up_rows_skipped']} warm-up row(s) skipped).",
            "",
            "| Strategy | Net cum. | Gross cum. | Cost drag | Net max DD | Vol/session "
            "| Sharpe/session (rf=0) | Traded notional | Rebalances |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for name, m in by_strategy.items():
            sharpe = m["net_sharpe_per_session_rf0"]
            lines.append(
                f"| {name} | {_pct(m['net_cumulative_return'])} | "
                f"{_pct(m['gross_cumulative_return'])} | {_pct(m['cost_drag'])} | "
                f"{_pct(m['net_max_drawdown'])} | {m['net_volatility_per_session']:.4%} | "
                f"{'n/a' if sharpe is None else f'{sharpe:.4f}'} | "
                f"{m['total_traded_notional']:.3f} | {m['rebalances']} |"
            )
        notes = sorted({n for m in by_strategy.values() for n in m["notes"]})
        lines += ["", *[f"- {n}" for n in notes], ""]
    return "\n".join(lines)
