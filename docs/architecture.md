# Architecture

This document describes the **intended** design. Required vs. optional components follow the
scope table in the README and the labels in [`roadmap.md`](roadmap.md). Only `config.py` and
`evaluation/metrics.py` are implemented; the other modules are placeholders whose responsibilities
are fixed here so that development can proceed incrementally.
Update this document whenever an interface is introduced or changed.

## Design principles

- **Causality first.** Every component that produces data for time *t* uses only information
  available at *t*. Leakage tests accompany each data-producing module.
- **One backtest engine.** Baselines and RL agents are evaluated with the same cost model,
  constraints, data and periods.
- **Configuration over constants.** Assumptions (universe, costs, splits, seeds) live in `configs/`
  and are loaded through `adaptive_portfolio.config`.
- **Small, testable functions.** Pure functions where possible; state is confined to the environment
  and agents.
- **Library code in `src/`, workflows in `scripts/`, exploration in `notebooks/`.**

## Module responsibilities

| Module | Responsibility | Main inputs | Main outputs |
| --- | --- | --- | --- |
| `config` | Load and validate YAML configs; cross-file consistency checks | `configs/*.yaml` | Frozen dataclasses (`ProjectConfig`) |
| `data` | **Implemented (milestone 2).** Provider interface (csv / yfinance / synthetic), raw snapshots with manifests, validation, observed-calendar alignment, missing-data policy, simple returns, chronological split labels, quality report, CLI | Provider or local files, `DataConfig`, `ExperimentConfig.splits` | `prices.csv`, `prices_long.csv`, `returns.csv`, `splits.csv`, `quality_report.{json,md}`, `metadata.json` (date × asset) |
| `features` | **Implemented (milestone 3).** Causal features from returns (momentum, volatility, downside risk, drawdown, dispersion, correlation); decision/next-return alignment; feature+regime pipeline. No normalisation (any future scaler must be fitted on train only) | `returns.csv`, `splits.csv`, `metadata.json`, `features.yaml` | `features.csv`, `feature_metadata.json` (date × feature) |
| `regimes` | **Implemented (milestone 3).** Rule-based trend × volatility labels; thresholds fitted on train only, frozen in a JSON artifact; diagnostics. Statistical models remain optional | Features, split labels | `regimes.csv`, `regime_thresholds.json`, `regime_report.{json,md}` |
| `environment` | **Building blocks implemented (M5.1):** `actions.py` (softmax action → capped targets, excess to cash), `observation.py` (training-only scaler, 51-input observation), `rewards.py` (weekly episode decisions, decision-aligned log-growth reward). Accounting is the simulator's `step`, never re-implemented here. **M5.2:** `portfolio_env.py`, the Gymnasium `PortfolioEnv` (needs the `rl` extra; the only RL-importing module) | Returns, features, regimes, `EnvironmentConfig`, `BacktestConfig` | Observations, target weights, rewards |
| `agents` | **M5.3 preparation:** `ppo.py`, a Stable-Baselines3 PPO training wrapper for one grid run on the training environment (needs the `rl` extra); `grid.py`, a sequential grid runner with a resumable manifest (`rl`); `run_safety.py`, locks, recovery, exclusive finalisation and code provenance (pure Python, D-075). **Milestone B:** `evaluate.py`, the validation evaluator under protocol D-076 (accepted 2026-10-21, protocol only; execution not authorised), reusing the backtest window, `simulate`, `summarize_window` and `evaluation/selection.py`; guarded by `data/boundaries.py`. PPO is the candidate algorithm. Planned: validation evaluation and selection (needs authorisation); other algorithms optional | Training environment, `AgentConfig` (`configs/agent.yaml`) | `data/processed/experiments/<run_id>/`: run config, metadata, scaler, model checkpoint, training monitor |
| `baselines` | **Implemented (milestone 4).** Conventional strategies (equal weight, buy-and-hold, inverse volatility with a weight cap, fixed weights) producing target weights from returns up to the decision row; rebalancing schedules. No regime information | Returns (history up to *t*), `StrategyConfig` | Target-weight vectors |
| `evaluation` | Metrics (`metrics.py`, milestone 1). **Milestone 4:** `simulator.py` (timing, drift, costs, cash, ledger; one-row `step` and `PortfolioState`, M5.1), `performance.py` (gross/net metrics per window via `metrics.py`), `backtest.py` (per-split protocol, outputs). Planned: walk-forward and stress tests where feasible; market-condition breakdowns | Target weights, `returns.csv`, `splits.csv`, `EnvironmentConfig`, `BacktestConfig` | `ledger.csv`, `executions.csv`, `metrics.{json,csv}`, `backtest_report.md` |
| `explainability` | Attribution and behaviour analysis of policies | Policies, features, regimes | Attribution scores, regime-conditional summaries |
| `visualization` | Plots; optional dashboard | Result records | Figures in `reports/figures/` |

## Intended data flow

```text
                 configs/*.yaml
                       │
                       ▼
                   config (validated dataclasses)
                       │
       ┌───────────────┼──────────────────────────────┐
       ▼               ▼                              ▼
     data ──► features ──► regimes            experiment settings
       │          │           │               (seed, splits, walk-forward)
       │          └─────┬─────┘                        │
       ▼                ▼                              │
   returns ───► environment ◄──────────────────────────┤
                 │      ▲                              │
          obs/   │      │ weights                      │
          reward ▼      │                              │
                agents ─┘    baselines ─► weights      │
                  │                          │         │
                  └──────────► evaluation ◄──┴─────────┘
                                   │
                     ┌─────────────┴──────────────┐
                     ▼                            ▼
              explainability               visualization ──► reports/figures/
                     │                            │
                     └──────► docs/experiment_log.md ◄──┘
```

## Timing convention (implemented in milestone 4; Proposed, D-048 and D-055)

- Decide at the close of row *d* using data dated ≤ *d*.
- Execute at the close of *x* = *d* + *L*, where *L* is `execution_lag_sessions`, required in
  the config and counted in observed sessions. *L* = 1 is the proposed primary convention;
  *L* = 0 is an idealised sensitivity case.
- Earn returns from row *x* + 1 onward. Costs are charged on the traded notional at *x*
  (D-049).

The arithmetic lives in one module, `adaptive_portfolio/timing.py`, used by
`evaluation/simulator.py`, the backtest drop rule and `features.next_period_targets(...,
execution_lag_sessions=L)`. Tests show these agree for *L* = 0 and *L* = 1 (technical handbook
§13.2). The later RL environment must use the same module, so that rewards, agents and
baselines share one timing.

## Metric interfaces the backtest and environment must satisfy

The metrics in `evaluation/metrics.py` are pure functions. The future backtest or environment
(milestones 4 and 5) must produce inputs in these forms:

- **Portfolio-value path** V_0…V_T: strictly positive, with no missing values. It is used for
  returns, cumulative and annualised return, and drawdown.
- **Pre- and post-trade weight matrices** (events × assets) for turnover:
  - pre-trade rows are the *drift-adjusted* weights at the execution time set by D-013;
  - cash is an explicit column when `allow_cash` is true;
  - the asset order is identical in both matrices.
- **Number of observed periods** T_obs and `periods_per_year`, for annualisation.
- **Transaction costs** must be computed from the same weight changes. Milestone 4 implements
  κ × `portfolio_turnover(pre, post, cash_column=j)` × V_pre: traded notional, excluding the cash
  leg (D-049, Proposed). The measure a turnover cap would constrain is still open (D-031).

## Market-data pipeline (milestone 2)

```text
provider ──► raw snapshot (data/raw/<provider>/<raw_id>/: CSVs + manifest.json with SHA-256)
   │              ▲  cache: use / refresh / offline
   ▼              │
validate ──► align (observed calendar) ──► missing-data policy ──► simple returns
                                                                     │
                     experiment.yaml splits ──► split labels ◄────────┘
                                                     │
              data/processed/<processed_id>/: prices, returns, splits, quality report, metadata
```

- **Boundaries:** acquisition (`providers`), storage (`cache`), checks (`validation`),
  transformation (`processing`), partitioning (`splits`), description (`report`), orchestration
  (`pipeline`) and the command line (`cli`).
- **Interface for later milestones:** baselines, the environment and evaluation read
  `returns.csv` and `prices.csv`, and use `splits.csv` or `assign_temporal_splits` / `split_frame`
  to obtain partitions. They must not refit anything on validation or test rows.
- Details: technical handbook §11.

## Features and regimes (milestone 3)

```text
data/processed/<processed_id>/ returns.csv + splits.csv + metadata.json
        │  contract checks (columns, order, dates, splits == experiment.yaml)
        ▼
features.engineering.build_features      (trailing windows ending at t; NaN warm-up)
        │
        ├──► regimes.rules.fit_regime_thresholds   (train rows only) ──► regime_thresholds.json
        │                                                                      │ frozen
        ▼                                                                      ▼
regimes.rules.assign_regimes  (all partitions, same thresholds) ──► regimes.csv
        ▼
regimes.diagnostics ──► regime_report.{json,md}      data/processed/features/<feature_set_id>/
```

- **Timing (D-043):** rows dated *t* use returns dated ≤ *t*. Later milestones that pair
  features with outcomes must use `features.next_period_targets`, which marks boundary-crossing
  pairs as `boundary`. Pass the backtest's `execution_lag_sessions` (default 0 ≠ the proposed
  primary lag 1, D-055), so that outcomes match the returns the simulator credits.
- **Interface for milestones 4–5:** the environment and baselines read `features.csv` and
  `regimes.csv` by date. They may use the frozen thresholds artifact, and they must not refit
  anything on validation or test rows.
- **Since 2026-10-19 (commit `8e52693`):** they read these through
  `features.pipeline.load_feature_outputs(feature_dir, dataset_dir, config)`. It is bounded by
  default: only rows dated before the configured `test.start` are parsed. The feature artifact
  on disk contains test-period rows (built in milestone 3), so reading the CSVs directly would
  bypass the test boundary.
- Details: technical handbook §12.

## Simulator and baselines (milestone 4)

```text
data/processed/<processed_id>/ returns.csv + splits.csv + metadata.json
        │  features.pipeline.load_processed_inputs (milestone-3 contract checks)
        ▼
for each split [s, e]:  common start k0 = max(s, required_history − 1)
                        (required_history = max(strategy lookbacks,
                         common_start_history_sessions = 126 feature warm-up), D-058)
        │
        ├─ baselines.strategies.decision_rows(schedule)  ──► decision rows k in [k0, e − L)
        ├─ baselines.strategies.target_weights(history = returns[..k])  ──► targets
        ▼
evaluation.simulator.simulate(returns, targets, lag=L, window=(k0 + L, e))
        │  drift, traded notional (metrics.portfolio_turnover), costs, cash, value, drawdown
        ▼
evaluation.performance.summarize_window  (metrics.py functions; gross and net)
        ▼
data/processed/backtests/<backtest_id>/: ledger, executions, metrics, report, metadata
```

- **Separation:** strategies only map past returns to target weights. The simulator only does
  accounting. Every strategy uses the same simulator, timing, costs and constraints, and the
  future RL agents must too.
- **Leakage boundaries:** weights at *k* use rows ≤ *k*. Each split is simulated independently
  from cash. Decisions that would earn the next split's returns are dropped (D-051).
- **Test protection (D-056):** `run_backtest` evaluates train and validation unless
  `include_test=True` (CLI `--include-test`). The evaluated splits are part of the output id.
- **Weight cap (D-057):** `max_weight` is checked on target weights at execution. Holdings
  drift between executions.
- Details: technical handbook §13.

## RL environment building blocks (milestone 5.1)

```text
load_feature_outputs / load_processed_inputs (train_only=True for training inputs)
        │
        ├─ rewards.episode_decisions: weekly rows from k0 to last_evaluable_decision(e, L)
        ├─ observation.fit_feature_scaler: rows k0 .. last training decision only, frozen
        ▼
at each decision d_k:  observation = [scaled features_d (34), one-hot regime_d (9),
                                      end-of-row weights_d (8)]
                       action u ∈ [−1, 1]^8 ──► logits 5u (D-072)
                                            ──► actions.project_action ──► target
        ▼
evaluation.simulator.step (one row at a time; target executed at x_k = d_k + L)
        ▼
reward r_k = log(V_{d_{k+1}} / V_{d_k})   (rewards.log_growth; the last step ends at e)
```

- **Single accounting implementation (D-067):** `simulate` loops over `step`. A sequential
  caller gets exactly the ledger values of `simulate`.
- **Leakage boundaries:** the observation at `d` uses rows ≤ `d` only. The scaler is fitted on
  training rows only. Training inputs can be loaded with `train_only=True`, which never parses
  validation or test values.
- **Gymnasium environment (M5.2):** `PortfolioEnv` sequences the parts above.
  - `reset` gives the observation at `d_0`.
  - Each `step` advances `simulator.step` to the next decision row and returns the reward.
  - The episode terminates at the split's last row.
- **Optional dependencies:** the core package and `.[dev]` stay free of RL libraries.
- Details: technical handbook §14 and §15.

## Split and evaluation protocol

1. **Train** period: fit features' normalisation, regime models and agents.
2. **Validation** period: model selection and hyperparameter tuning.
3. **Test** period: single final evaluation; never used for decisions.
4. **Walk-forward (where feasible):** repeat (1)–(2) over successive windows to measure stability.

The loader enforces `train.end < validation.start` and `validation.end < test.start`, and that all
splits lie inside the data window.

## Planned dependencies (added only when needed)

| Milestone | Likely dependency | Reason | Scope |
| --- | --- | --- | --- |
| 1 | numpy | Metrics on return series | **Added** (D-027) |
| 1 | pandas (dev-only) | Tests of pandas inputs | Added (D-032); moved to runtime in milestone 2 |
| 2 | pandas (runtime) | Dated price / return tables, CSV I/O | **Added** (D-040, Proposed) |
| 2 | yfinance (optional `data` extra) | Live daily prices from Yahoo Finance | **Added** as an optional extra (D-041, Proposed); not used in tests or CI |
| 3 | scikit-learn / hmmlearn | Statistical regime models | Optional |
| 4 | gymnasium | Environment interface | **Added** as part of the optional `rl` extra (`>=1.4,<2`, M5.2); used only by `environment/portfolio_env.py` |
| 6 | stable-baselines3 + torch | PPO implementation | **Declared** in the optional `rl` extra (`>=2.9,<3`, `>=2.8,<3`; CPU-only index); not imported by any module yet |
| 9 | shap | Attribution | Optional |
| 10 | streamlit | Dashboard | Optional |
| 5+ | matplotlib | Plots | Likely |

Scope labels follow [`roadmap.md`](roadmap.md): only the abstract's commitments are required.
