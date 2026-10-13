# Architecture

This document describes the **intended** design. Required vs. optional components follow the
scope table in the README and the labels in [`roadmap.md`](roadmap.md). Only `config.py` is implemented; the other modules
are placeholders whose responsibilities are fixed here so that development can proceed incrementally.
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
| `data` | Load raw prices, align calendars, handle missing data, compute returns, cache | Raw files / provider, `DataConfig` | Clean price and return tables (date × asset) |
| `features` | Causal features (rolling returns, volatility, drawdown, momentum); training-only normalisation | Prices / returns | Feature table indexed by date |
| `regimes` | Market-condition labels (rule-based required; statistical models optional), fitted on training data only | Features | Regime series indexed by date |
| `environment` | Sequential portfolio simulation: observation, action → weights, costs, constraints, reward | Returns, features, regimes, `EnvironmentConfig` | Transitions, portfolio value and weight history |
| `agents` | RL policies (PPO as the candidate algorithm; others optional); training, checkpointing, inference | Environment, `ExperimentConfig` | Trained policies, weight decisions |
| `baselines` | Traditional strategies producing target weights from past data | Returns (history up to *t*) | Weight decisions |
| `evaluation` | Backtesting, metrics, out-of-sample split protocol; walk-forward and stress tests where feasible; market-condition breakdowns | Weight decisions, returns, costs | Metric tables, result records |
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
| 1 | numpy, pandas | Metrics on return series | Required |
| 2 | yfinance or similar | Data acquisition, if a provider is adopted | Decision pending (D-008) |
| 3 | scikit-learn / hmmlearn | Statistical regime models | Optional |
| 4 | gymnasium | Environment interface | Likely |
| 6 | stable-baselines3 + torch | PPO implementation | Likely (library choice pending) |
| 9 | shap | Attribution | Optional |
| 10 | streamlit | Dashboard | Optional |
| 5+ | matplotlib | Plots | Likely |

Scope labels follow [`roadmap.md`](roadmap.md): only the abstract's commitments are required.
