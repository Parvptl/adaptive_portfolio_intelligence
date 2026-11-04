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
| `explainability` | **Milestone E:** `regime_analysis.py` (strategy behaviour by regime label, label at t − lag), `sensitivity.py` (permutation sensitivity of decided targets by input group), `run.py` (modes `baselines-train`, `policy-validation`; the latter authorisation-gated). Observational and sensitivity analyses only; ablations need retraining (D-081, planned) | Saved ledgers, regime labels, checkpoints (policy mode) | `data/processed/explainability/<id>/` summaries, figures, provenance |
| `visualization` | **Milestones E–F:** `plots.py` (figures with provenance sidecars), `dashboard.py` (static HTML from saved, hash-verified artifacts; D-079) | Saved results named in `configs/workflow.yaml` | `reports/figures/dashboard/<build_id>/` |
| `agents/test_evaluate`, `evaluation/uncertainty`, `evaluation/risk` | **Milestone D (D-082, Proposed):** a separate, pre-registered test evaluator (plan, execute once, verify), a paired block bootstrap and risk measures. Execution is refused unless the pre-registration is frozen, its hash matches, and the code is clean at the named commit | `configs/preregistration.yaml` (DRAFT), the validation selection, checkpoints | `data/processed/test_evaluations/<id>/` (none exist) |
| `environment/profiles`, `environment/profile_env`, `agents/profile_experiment`, `explainability/profile_analysis` | **Profile-conditioned PPO extension [O] (D-085; details D-086/D-087 Provisional (delegated)):** five-dimensional investor profiles and seeded sampling (no `rl`); `ProfileConditionedEnv`, a Gymnasium wrapper that appends a constant-per-episode profile to the unchanged 51-input observation (56 inputs) and passes reward, actions and accounting through unchanged; the arm trainer (reusing `ppo.train_ppo_run` with `profile=`) and the E0–E3 evaluator (train and validation only, write-once, comparability checks against E0); descriptive allocation analysis (D_w, sweeps, rank correlations; no `rl`) | `configs/profile_experiment.yaml`, the existing configs and EXP-005 checkpoints | `data/processed/profile_experiments/<run_id>/`, `data/processed/profile_evaluations/<id>/` |
| `environment/profile_reward`, `ProfileRewardEnv` (in `environment/profile_env`), `explainability/profile_comparison` | **E4 profile-dependent reward (D-088; Provisional (delegated)):** `ProfileRewardSpec` maps a profile to relative risk aversion γ = 1 + 9·(1 − min(RT, RC)) and computes r_base − (λ/2)·Σ net_return² per step (no `rl`). `ProfileRewardEnv` wraps `ProfileConditionedEnv` and changes only the returned reward, from the step's own ledger rows, logging every component. The comparison module checks two verified evaluations (E4 vs E1) for comparability and evaluates the prespecified H1–H7 (no `rl`) | `configs/profile_reward_experiment.yaml`; E1 evaluations | `data/processed/profile_reward_experiments/`, `profile_reward_evaluations/`, `profile_reward_comparisons/` |
| `explainability/fixed_risk_comparison` (plus the `fixed` option of `ProfileRewardSpec` and the `constant` option of `ProfileSampling`) | **E5 fixed risk aversion (D-089; Provisional (delegated)):** two single-arm experiments, λ = 0 and λ = 9, with the E4 reward implementation and a constant neutral profile input. The comparison verifies four evaluations, checks that the arms differ only in λ and the label, and evaluates the prespecified H1–H8 and outcome class (no `rl`) | `configs/fixed_risk_low.yaml`, `fixed_risk_high.yaml` | `data/processed/fixed_risk_experiments/`, `fixed_risk_evaluations/`, `fixed_risk_comparisons/` |
| `explainability/dose_response_comparison` | **E6 λ dose response (D-090; Provisional (delegated)):** verifies six evaluations (λ = 0, 3, 9 × train/validation), checks that the arms differ only in λ (strictly increasing), evaluates the prespecified H1–H8 and outcome class, the paired seed differences (with effect sizes), and the reproduction of E5 (no `rl`) | `configs/dose_response_l{0,3,9}.yaml` | `data/processed/dose_response_{experiments,evaluations,comparisons}/` |
| `explainability/turnover_comparison` (plus `ProfileRewardSpec.turnover_penalty`) | **E7 turnover-aware reward (D-091; Provisional (delegated)):** an optional reward-shaping term κ × the step's recurring traded notional (the funding step excluded), applied by `ProfileRewardEnv` after the unchanged ledger. The comparison verifies six evaluations (κ = 0, T1, T2 × train/validation), checks that the arms differ only in κ, evaluates H1–H8 and the outcome class, and checks that the control reproduces E6L (no `rl`) | `configs/turnover_k{0,1,2}.yaml` | `data/processed/turnover_{experiments,evaluations,comparisons}/` |
| `explainability/turnover_refine_comparison` (plus `profile_analysis.responsiveness`) | **E8 turnover-penalty refinement (D-092; Provisional (delegated)):** two responsiveness measures computed from the decision targets of every evaluation episode (`allocation_dispersion`, `share_meaningful_changes`; additive columns). The comparison verifies eight evaluations (κ = 0, 0.0015, 0.003, 0.0045 × train/validation), checks that the arms differ only in κ (λ = 0), evaluates H1–H9 and the outcome class, checks exact reproduction of E7B, E6L and E7T1, and records E7T2 as a labelled prior experiment (no `rl`) | `configs/turnover_refine_k{0,1,2,3}.yaml` | `data/processed/turnover_refine_{experiments,evaluations,comparisons}/` |
| `explainability/confirmation_comparison` (plus the opt-in `extension_seeds`) | **E9 turnover-penalty confirmation (D-093; Provisional (delegated)):** profile experiments may declare `extension_seeds` outside the D-066 grid. They are trained with the base configuration's spec with only the seed replaced (`profile_experiment.run_spec`, `ppo.is_extension_spec`) and checked against E0 without the seed. The comparison reads four evaluations (E9B/E9T1 × train/validation), keeps the primary (47–56), reproduction (42–46) and pooled populations separate, computes paired-seed statistics (bootstrap CI, exact sign-flip permutation test, t-interval), evaluates H1–H10 and the outcome, and checks exact reproduction of E8 and E7 (no `rl`) | `configs/confirmation_k{0,1}.yaml` | `data/processed/confirmation_{experiments,evaluations,comparisons}/` |
| `data/walk_forward`, `explainability/walk_forward_comparison` (plus the optional `walk_forward_fold`) | **E10 walk-forward validation (D-094; Provisional (delegated); D-018 open):** a profile experiment may declare a fold, whose splits replace the project's in `load_context`. A non-reference fold's dataset is derived from the parent by the bounded reader (byte-exact prefix before the test start, fold labels). Its feature set is built in `fit` mode (regime thresholds from the fold's training rows), and E0 is not used. The reference fold (= D-009) uses the parent dataset unchanged. The comparison reads twelve evaluations (3 folds × 2 arms × 2 splits), verifies each fold's leakage checks and windows, computes within-fold paired statistics and the fold-level synthesis, evaluates H1–H10 and the outcome, and checks exact reproduction of E8/E7 in the reference fold (no `rl`) | `configs/walk_forward_{a,b,c}_k{0,1}.yaml` | `data/processed/walk_forward_{datasets,experiments,evaluations,comparisons}/`, fold feature sets under `data/processed/features/` |
| `workflow` and `agents/provenance` | **Milestone F:** entry point (`status`, `verify`, `explain`, `dashboard`), never training or evaluating; checkpoint integrity and configuration compatibility | `configs/workflow.yaml`, run directories | Console reports, analyses, dashboard |

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
