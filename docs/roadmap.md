# Roadmap

Milestones are sequential: each builds on tested code from the previous one. Every milestone ends
with passing tests, updated docs (journal, handbook, decision log, glossary as relevant), and (from
milestone 5 onward) entries in [`experiment_log.md`](experiment_log.md).

**Status:** ✅ done · ◐ partly done · ⏳ next · ▫️ planned
**Scope:** **[R]** required by the submitted abstract · **[F]** required "where feasible" by the
abstract · **[O]** optional extension, not committed; pursue only with team approval
(record in [`decision_log.md`](decision_log.md)).

All dates, assets, costs and constraints mentioned here are provisional (see
[`decision_log.md`](decision_log.md)).

## 0. Repository scaffold ✅

Complete. Committed as `412d620` and pushed; the GitHub Actions CI workflow passed on that commit.

- `src/` package layout, `pyproject.toml`, Ruff, pytest, Makefile, CI workflow.
- Provisional YAML configs with validated loader (`adaptive_portfolio.config`).
- README, CLAUDE.md, documentation set under `docs/`.

## 1. Financial metrics: ✅ complete

All conventions for this milestone (D-011, D-021, D-022, D-024 to D-030, D-032, D-033) were
accepted on 2026-10-13. Committed as `94e6f74`; GitHub Actions CI passed on that commit
(Python 3.11–3.13).

Implement and unit-test metrics on synthetic return series *before* any real data or models, so that
everything later is measured with trusted tools.

Implemented, documented and tested (2026-10-13; uncommitted, pending team review):

- ✅ [R] Portfolio (simple) returns from portfolio values: `portfolio_returns` (D-021).
- ✅ [R] Cumulative return: `cumulative_return` (D-028).
- ✅ [R] Annualised return, geometric / CAGR: `annualized_return` (D-029).
- ✅ [R] Annualised volatility: `annualized_volatility` (D-022, D-023).
- ✅ [R] Sharpe ratio, with explicit risk-free conversion: `sharpe_ratio`, `annual_to_periodic_rate`
  (D-024, D-025).
- ✅ [R] Maximum drawdown, with peak and trough positions: `max_drawdown`, `drawdown_series` (D-026).
- ✅ [R] Two-way portfolio turnover from drift-adjusted weights: `portfolio_turnover`, plus
  `annualized_turnover` (D-011, D-030). An optional `cash_column` gives traded notional
  (extension approved 2026-10-13; the default is unchanged).
- ✅ Pre-commit review fixes (2026-10-13):
  - pandas dev minimum raised to 2.2 (D-032, Accepted). That day's minimum-version run used
    Python 3.12.1 on Windows with numpy 1.26.0, pandas 2.2.0, pytest 8.0.0 and ruff 0.6.0. PyYAML
    was 6.0.1, because the then-declared minimum 6.0 could not be installed on 3.12.
  - PyYAML minimum raised to 6.0.2 (D-033, Accepted). The final local runs (all on Windows) were:
    - **Python 3.12.1** at the declared minimums (numpy 1.26.0, pandas 2.2.0, PyYAML 6.0.2,
      pytest 8.0.0, ruff 0.6.0): all tests pass, lint and format clean.
    - **Python 3.13.7** at the lowest versions with 3.13 wheels (numpy 2.1.0, pandas 2.2.3,
      PyYAML 6.0.2, pytest 8.0.0, ruff 0.6.0): all tests pass. The declared numpy 1.26 and pandas
      2.2.0 minimums have no 3.13 wheels.
    - **Python 3.11:** not tested locally (not installed). Only Windows was tested.
  - handbook rules table; module docstring;
  - `annualized_turnover` always returns a `float`;
  - journal CI wording corrected; mutation counts corrected.
- ✅ Review fixes:
  - direct validation tests for `annual_to_periodic_rate`;
  - tuple and pandas inputs tested (pandas dev-only, D-032);
  - `ddof` wording clarified (D-022);
  - zero-volatility tolerance reviewed with evidence and kept (D-025).
- ✅ Tests: hand-computed values, edge cases, input validation, drift demonstrations, consistency
  with the config `max_turnover` bound, plus hand-picked injected-error checks. These are a
  selected set of deliberate bugs, not systematic mutation testing.
- ✅ Dependencies: `numpy` (runtime), `pandas` (dev-only).

Sign-off: ✅ all milestone conventions were accepted on 2026-10-13 (see the decision log). If any
convention changes later, the code, tests and docs must change together.

Moved to later milestones, because they cannot be decided without them:

- D-023: the project-wide `periods_per_year` per data frequency (252 vs. 365 for daily) belongs to
  milestone 2 (data pipeline). The metric functions already require N explicitly.
- D-031: the transaction-cost basis for cash legs belongs to milestones 4 and 7 (environment, costs).
- D-013: trade timing belongs to milestone 4; turnover is timing-agnostic.

Optional, not started:

- [O] Log returns, Sortino, Calmar, drawdown duration, transaction-cost drag.

## 2. Data pipeline: ✅ implemented and tested · committed (`1a289ab`) and pushed · ⏳ decisions Proposed

Implemented on 2026-10-15 in `src/adaptive_portfolio/data/`, with the CLI
`scripts/market_data.py` (technical handbook §11). Every decision introduced here (D-034 to
D-042, and D-008 moved from Open to Proposed) awaits team approval. GitHub Actions has not run on
this work.

- ✅ [R] Load historical prices from local CSV (`csv` provider); reproducible preprocessing.
- ✅ [R] Observed-calendar alignment, missing-data policy (`error` / `drop_sessions`, never
  fill), adjusted prices (`adj_close`, never mixed with `close`), simple-return construction
  that reuses `portfolio_returns`.
- ✅ [R] Data-quality report (JSON + Markdown: coverage, gaps, missing cells, corporate-action
  counts, return range, split counts); processed datasets in `data/processed/<id>/`.
- ✅ [R] Chronological split assignment (D-038), with leakage/causality tests.
- ✅ [R] Raw snapshots with manifest and checksums; cache modes use / refresh / offline (D-039).
- ✅ [O] Provider adapter (yfinance, optional extra). Started because the team member's
  milestone-2 brief explicitly requested a real-data adapter. The provider choice itself is
  Proposed (D-008, D-041). One live retrieval of the full universe (2007–2024) succeeded on
  2026-10-15.
- ✅ Offline tests with hand-calculated fixtures, synthetic data and a fake yfinance module; no
  network access in tests or CI.
- Still open: D-023 (annualisation), D-019 (embargo), D-018 (walk-forward), and team approval of
  D-008 and D-034 to D-042.

## 3. Market conditions and regime detection: ✅ implemented and tested · committed (`adffff5`) and pushed · ⏳ decisions Proposed

Implemented on 2026-10-15 in `features/` and `regimes/`, with the CLI commands `features` and
`regime-report` (technical handbook §12). Decisions D-043 to D-047 await team approval.

- ✅ [R] Causal features in `features/`: momentum, volatility, downside volatility, drawdown,
  dispersion, equity–bond correlation, and group composites (34 columns by default). Trailing
  windows only; warm-up kept as NaN.
- ✅ [R] Transparent rule-based labels for rising / falling (trend) and high-volatility periods:
  thresholds fitted on the training partition only, frozen in an artifact, re-applicable without
  refitting.
- ✅ Diagnostics: regime counts and proportions by split, transitions, feature medians by regime,
  and sparse, absent and concentrated warnings.
- ✅ Leakage tests: features and frozen-threshold labels unchanged when future data is modified or
  appended; thresholds unaffected by validation/test values; boundary-crossing decision/target
  pairs flagged.
- ✅ Run offline on the existing live processed dataset (2007–2024): all 9 regimes occur; the
  report lists 4 warnings (descriptive, not tuned).
- [R/decision] Whether regime signals are given to the agent as observations: still open (D-012).
- [O] Statistical regime models (e.g. hidden Markov model or clustering): not started.

## 4. Portfolio environment: ◐ simulator (`66f9ed7`) and hardening 4.1 (`880d82c`, CI passed) · 4.2 preparation local · ⏳ decisions Proposed · RL interface not started

Done on 2026-10-15, together with milestone 5, as the team's "milestone 4: portfolio simulation
and conventional baselines" (technical handbook §13). It was originally committed and
pushed as `a7134b7`, and CI passed on it. After a metadata rewrite on 2026-10-18 the same
tree is commit `66f9ed7` (see the project journal). Decisions D-048 to D-054 await team
approval.

**Milestone 4.1 (2026-10-18, commit `880d82c`, originally `4b37aae`; CI run #6 passed):**
hardening after the read-only milestone-4 audit. Decisions D-055 to D-057 are Proposed.
- lag 1 as the primary convention, with the lag required in the config;
- shared timing with the feature alignment;
- test split opt-in;
- validated simulator settings;
- documented cap and ledger semantics.

- ✅ [R] Explicit timing convention: decide at close *d*, execute at close *d* + lag, earn from
  the next session (D-048, proposal for D-013). Lag 1 is the proposed primary convention and
  lag 0 an idealised sensitivity case (D-055).
- ✅ [R] Transaction costs on traded notional, cash leg excluded, initial funding charged (D-049,
  proposal for D-031). Long-only, unlevered, fractional weights with implicit cash (D-050).
- ✅ Deterministic tests on toy paths with hand-calculated ledgers.
- [R] Sequential RL environment (observations, weight actions, risk-aware reward, episode
  boundaries): not started. It must reuse the simulator's accounting and timing.
- ✅ Test split opt-in (`--include-test`, D-056, Proposed).
- **Milestone 4.2 (2026-10-18, local, not committed): protocol preparation before PPO.**
  - ✅ draft [`research_protocol.md`](research_protocol.md), **not approved**;
  - ✅ common evaluation window covering the 126-session feature warm-up (D-058, Proposed);
  - ✅ funding turnover reported separately and excluded from annualised turnover (D-059,
    Proposed).
  - Walk-forward evaluation is **not implemented** (D-018 open).
  - A primary-convention (lag 1) baseline record does not exist yet.
- Still open: D-023 (annualisation) and the turnover-cap measure (D-031).
- Likely dependency (RL interface only): `gymnasium`.

## 5. Baseline strategies: ◐ minimum set implemented and tested locally · ⏳ decisions Proposed

- ✅ [R] Conventional allocation benchmarks, proposed minimum set (D-053, proposal for D-010):
  equal weight monthly, equal-weight buy-and-hold, inverse volatility (63) monthly. Fixed weights
  are also supported.
- ✅ Offline run on the live processed dataset (2007–2024); train and validation results
  recorded as EXP-001 (descriptive only). It used lag 0, now the idealised sensitivity case.
  The primary lag-1 run has not been made yet.
- Candidates not implemented: reference portfolio (possible with `fixed_weights`), minimum
  variance, mean-variance, risk parity.
- [O] Momentum / volatility targeting and other rule-based strategies.
- Same backtest engine, costs and constraints as the agents.
- First logged experiments: baselines on train/validation periods.

## 6. RL agents ▫️

- [R] PPO, as the candidate algorithm named in the abstract. If PPO proves unsuitable, record why
  and what replaces it.
- [O] Other algorithms (e.g. DQN on discretised actions), only if justified.
- Library choice decided here (e.g. Stable-Baselines3); add the dependency at this point, not before.
- Hyperparameter search on validation only; multiple seeds.
- [O] Regime-aware vs. regime-agnostic variants (depends on D-012).

## 7. Realistic costs and constraints ▫️

- [R] Transaction costs included in every reported result.
- [O] Cost sensitivity sweeps (e.g. 0–50 bps), slippage model, turnover caps, rebalancing-frequency
  comparison.

## 8. Robust evaluation ▫️

- [R] Single final out-of-sample run on the held-out test period.
- [F] Walk-forward evaluation (expanding / rolling).
- [F] Stress testing across different market conditions.
- [R] Performance by market condition; seed variability.
- [O] Statistical comparison with baselines (e.g. bootstrap confidence intervals).

## 9. Explainability ▫️

- [R] Explore techniques to understand factors associated with allocation decisions and
  risk-taking behaviour (e.g. allocation behaviour by market condition, sensitivity analysis).
- [O] Specific attribution libraries (e.g. SHAP), permutation importance.

## 10. Dashboard ▫️ [O]

- Lightweight interactive view of equity curves, drawdowns, allocations and regimes (e.g. Streamlit),
  reading saved results only. Not mentioned in the abstract.

## 11. Final research report ▫️ [R]

- Methodology, assumptions, results with uncertainty, limitations and negative results.
- Reproducibility appendix: configs, seeds, commit hashes, data provenance.
- AI-use disclosure.
