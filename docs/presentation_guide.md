# Presentation Guide

How to present Adaptive Portfolio Intelligence honestly at reviews, demos and the final
presentation. Update this guide whenever the project's demonstrable status changes.

## Current status (as of 2026-10-13)

- **Available:** the abstract; repository scaffold; validated configuration loader with tests;
  documentation (architecture, roadmap, decision log, glossary).
- **Not available yet:** data pipeline, metrics, regime detection, environment, baselines, RL agents,
  explainability, or any experimental results.
- **What can honestly be shown today:** the research question, planned methodology, evaluation
  safeguards, architecture, and the reproducible engineering setup. **Do not show or imply any
  performance numbers.**

## Core message

> We study whether a reinforcement learning agent (PPO as the candidate) can adapt portfolio
> allocations to changing market conditions under transaction costs, and we compare it fairly with
> conventional benchmarks using risk-adjusted, out-of-sample evaluation. No improvement is assumed
> in advance; negative results are valid findings.

## Suggested storyline

1. **Problem.** Allocation is sequential and uncertain; fixed rules may not adapt to changing
   conditions, costs and risk.
2. **Question.** Can an adaptive RL policy respond to rising, falling and high-volatility periods,
   and is it useful once costs and risk are accounted for?
3. **Approach.** Sequential decision formulation, PPO as the candidate algorithm, a risk-aware
   reward, transaction costs and portfolio constraints.
4. **Fair comparison.** Conventional benchmarks under identical data, costs, constraints and periods.
5. **Evaluation protocol.** Chronological train/validation/test; out-of-sample testing; walk-forward
   validation and stress testing where feasible; metrics: cumulative return, Sharpe, maximum
   drawdown, turnover.
6. **Explainability.** What factors are associated with allocation and risk-taking decisions.
7. **Results** (once available, from `experiment_log.md`), including limitations.
8. **Conclusions and limitations.**

## Slides by stage

| Stage | What to show |
| --- | --- |
| Proposal / early review (now) | Abstract, research question, architecture diagram, evaluation safeguards, roadmap with required vs. optional scope, open decisions. |
| After metrics + data (milestones 1–2) | Tested metric definitions, data-quality summary, market-condition labelling. |
| After baselines (milestone 5) | Baseline results on train/validation periods, with costs. |
| After agents (milestones 6–8) | Agent vs. baselines on validation; final single test-period evaluation; seed variability; market-condition breakdown. |
| Final | All of the above + explainability findings + limitations + reproducibility appendix + AI-use disclosure. |

## Rules for reporting results

- Every number must trace to an entry in `experiment_log.md` (config, seed, commit).
- Always show baselines next to the agent, under the same costs and periods.
- Always report risk (maximum drawdown, volatility, Sharpe) and turnover, not only cumulative return.
- State which period a number comes from (train / validation / test) and the cost assumption.
- Report variability across seeds, not a single best seed.
- Call backtests backtests.

## Wording to avoid → prefer

| Avoid | Prefer |
| --- | --- |
| "Our agent beats the market." | "In this backtest, under these assumptions, the agent's Sharpe was X vs. Y for equal weight." |
| "PPO is the best algorithm for this." | "PPO was our candidate algorithm; here is how it compared." |
| "The model predicts regimes." | "The labelling rule classifies past periods as …, using only data available at the time." |
| "Profitable strategy." | "Positive backtested return net of the assumed costs; not evidence of future returns." |
| "Validated transaction costs / universe." | "Provisional assumptions (see decision log)." |

## Anticipated questions

- *How do you prevent look-ahead bias?* Chronological splits, causal features, training-only
  fitting, and an explicit timing convention (D-013).
- *Why these assets / dates / costs?* They are provisional development choices (D-005 to D-009);
  sensitivity analysis is planned where feasible.
- *Why PPO?* Named as a candidate in the abstract: suited to continuous actions such as portfolio
  weights, and widely used. Not assumed to be optimal.
- *What if RL does not beat the baselines?* That is a valid, reportable result.
- *Is this financial advice?* No. It is a research and decision-support project.

## Disclosure

Include the AI-use disclosure (see README) in the final presentation and report.
