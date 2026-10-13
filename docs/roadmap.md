# Roadmap

Milestones are sequential: each builds on tested code from the previous one. Every milestone ends
with passing tests, updated docs (journal, handbook, decision log, glossary as relevant), and (from
milestone 5 onward) entries in [`experiment_log.md`](experiment_log.md).

**Status:** ✅ done · ⏳ next · ▫️ planned
**Scope:** **[R]** required by the submitted abstract · **[F]** required "where feasible" by the
abstract · **[O]** optional extension, not committed; pursue only with team approval
(record in [`decision_log.md`](decision_log.md)).

All dates, assets, costs and constraints mentioned here are provisional (see
[`decision_log.md`](decision_log.md)).

## 0. Repository scaffold ✅

Scaffold complete; not yet committed, and the CI workflow has not yet run on GitHub.

- `src/` package layout, `pyproject.toml`, Ruff, pytest, Makefile, CI workflow.
- Provisional YAML configs with validated loader (`adaptive_portfolio.config`).
- README, CLAUDE.md, documentation set under `docs/`.

## 1. Financial metrics ⏳

Implement and unit-test metrics on synthetic return series *before* any real data or models, so that
everything later is measured with trusted tools.

- [R] Cumulative return, Sharpe ratio, maximum drawdown, portfolio turnover (named in the abstract).
- [R] Supporting quantities: simple/log returns, annualised return and volatility.
- [O] Sortino, Calmar, drawdown duration, transaction-cost drag.
- Tests with hand-computed expected values and edge cases (constant returns, all-negative series, NaNs).
- Decisions needed first: annualisation factor, Sharpe convention (risk-free handling), turnover
  definition (D-011).
- Likely dependencies: `numpy`, `pandas`.

## 2. Data pipeline ▫️

- [R] Load historical prices from local CSV; reproducible preprocessing.
- [R] Calendar alignment, missing-data policy, adjusted prices, return computation.
- [R] Data-quality report (gaps, outliers, inception dates); processed cache in `data/processed/`.
- [O] Provider adapter (e.g. yfinance), only once a provider is chosen and justified (D-008).
- Tests using small synthetic fixtures; no network access in CI.

## 3. Market conditions and regime detection ▫️

- [R] Causal features (rolling volatility, trend, drawdown) in `features/`.
- [R] Transparent rule-based labels for rising / falling / high-volatility periods, used at least for
  evaluation by market condition.
- [R/decision] Whether regime signals are also given to the agent as observations (D-012).
- [O] Statistical regime models (e.g. hidden Markov model or clustering), fitted on training data only.
- Leakage tests: labels at *t* must be unchanged when future data is appended.

## 4. Portfolio environment ▫️

- [R] Sequential environment: observations, weight actions, risk-aware reward, episode boundaries.
- [R] Explicit timing convention (decide at close *t*, trade at close *t* or open *t+1*) (D-013).
- [R] Transaction costs on traded notional; long-only weights with cash handling.
- Deterministic tests on toy price paths.
- Likely dependency: `gymnasium`.

## 5. Baseline strategies ▫️

- [R] Conventional allocation benchmarks; minimum set to be agreed (D-010). Candidates: equal weight,
  buy-and-hold, reference portfolio, minimum variance, mean-variance, risk parity / inverse volatility.
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
