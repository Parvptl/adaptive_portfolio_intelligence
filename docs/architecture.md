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
| `environment` | Sequential portfolio simulation: observation, action → weights, costs, constraints, reward | Returns, features, regimes, `EnvironmentConfig` | Transitions, portfolio value and weight history |
| `agents` | RL policies (PPO as the candidate algorithm; others optional); training, checkpointing, inference | Environment, `ExperimentConfig` | Trained policies, weight decisions |
| `baselines` | Traditional strategies producing target weights from past data | Returns (history up to *t*) | Weight decisions |
| `evaluation` | Metrics (`metrics.py`: returns, cumulative and annualised return, volatility, Sharpe, max drawdown, turnover; implemented); planned: backtesting, out-of-sample split protocol; walk-forward and stress tests where feasible; market-condition breakdowns | Weight decisions, returns, costs | Metric tables, result records |
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

## Timing convention (to be fixed in milestone 4)

The environment must document exactly when information becomes available and when trades execute.
Default intention: observe features computed from data up to the close of day *t*, choose weights,
execute at the close of *t* (or the open of *t+1*) with costs applied to the traded notional, and
earn returns from *t* to *t+1*. Whatever is chosen is recorded here and enforced in tests.

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
- **Transaction costs** must be computed from the same weight changes. The proposed direction
  (D-031, open; to implement and validate in milestone 4) is to charge
  κ × `portfolio_turnover(pre, post, cash_column=j)` × V_pre: traded notional, excluding the cash
  leg.

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
  pairs as `boundary`.
- **Interface for milestones 4–5:** the environment and baselines read `features.csv` and
  `regimes.csv` by date. They may use the frozen thresholds artifact, and they must not refit
  anything on validation or test rows.
- Details: technical handbook §12.

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
| 4 | gymnasium | Environment interface | Likely |
| 6 | stable-baselines3 + torch | PPO implementation | Likely (library choice pending) |
| 9 | shap | Attribution | Optional |
| 10 | streamlit | Dashboard | Optional |
| 5+ | matplotlib | Plots | Likely |

Scope labels follow [`roadmap.md`](roadmap.md): only the abstract's commitments are required.
