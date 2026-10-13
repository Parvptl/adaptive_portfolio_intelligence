# Glossary

Terms used in this project's code and documentation. Where a precise definition is still a pending
decision, the entry says so and links to [`decision_log.md`](decision_log.md). Add terms as they
appear.

## Finance and portfolio management

**Adjusted close.** Closing price adjusted for dividends and splits, so that price changes reflect
total return. Adjustment methods differ between data providers.

**Asset universe.** The set of assets the strategy may hold. Here: 7 US-listed ETFs, provisionally
(D-005).

**Basis point (bp, bps).** One hundredth of a percent: 1 bp = 0.01 % = 0.0001.

**Buy-and-hold.** Benchmark that buys an initial allocation and never rebalances.

**Calmar ratio.** Annualised return divided by the absolute value of maximum drawdown.

**Cash position.** Portfolio weight not allocated to any asset. Assumed to earn the risk-free rate
(currently 0, provisional).

**Cumulative return.** Total growth of portfolio value over a period: V_end / V_start − 1.

**Drawdown.** Percentage decline of portfolio value from its running peak.

**Equal weight (1/N).** Benchmark allocating the same weight to every asset, rebalanced periodically.

**ETF (exchange-traded fund).** A fund traded on an exchange like a stock, often tracking an index.

**Long-only.** No negative (short) weights are allowed.

**Maximum drawdown (MDD).** The largest peak-to-trough decline over a period. A core risk metric in
the abstract.

**Mean-variance optimisation (Markowitz).** Choosing weights that trade off expected return against
variance.

**Minimum variance portfolio.** Weights that minimise estimated portfolio variance, ignoring expected
returns.

**Rebalancing.** Trading to move current weights to target weights.

**Risk-free rate.** Return on a riskless asset (e.g. T-bills), used in Sharpe-type ratios. Provisional
constant: 0.0.

**Risk parity / inverse volatility.** Allocations that equalise each asset's risk contribution, or
weight assets in inverse proportion to their volatility.

**Sharpe ratio.** (Mean return − risk-free rate) / standard deviation of returns, usually annualised.
A core metric in the abstract. The exact convention is to be fixed in milestone 1.

**Slippage.** The difference between the expected and the actual execution price. Modelled here as
an extra cost in bps (provisional; optional extension).

**Sortino ratio.** Like Sharpe, but divides by downside deviation only.

**Transaction cost.** Cost of trading, modelled as a proportion (in bps) of traded notional.
Provisional value: 10 bps (D-007).

**Turnover.** How much the portfolio trades. Provisional definition: sum over assets of
|w_new − w_old| per rebalance, ranging from 0 to 2 (D-011). A core metric in the abstract.

**Volatility.** Standard deviation of returns, usually annualised.

**Weight (portfolio weight).** Fraction of portfolio value held in an asset.

## Reinforcement learning

**Action.** The agent's decision at each step; here, target portfolio weights.

**Actor–critic.** RL methods that learn both a policy (actor) and a value function (critic).

**Agent.** The learner that chooses actions to maximise expected cumulative reward.

**DQN (Deep Q-Network).** Value-based RL algorithm for discrete actions. Optional extension; not in
the abstract.

**Environment.** The simulated market the agent interacts with: it provides observations and rewards
and applies costs and constraints.

**Episode.** One run of the environment from start to end of a period.

**Observation (state).** Information available to the agent at decision time, e.g. recent returns,
volatility, current weights and possibly regime signals (D-012).

**Policy.** A mapping from observations to actions.

**PPO (Proximal Policy Optimization).** An actor–critic policy-gradient algorithm (Schulman et al.,
2017). The candidate algorithm named in the abstract (D-014).

**Reward.** Scalar feedback after each action. Here it will be based on investment performance and
risk, net of costs. Design still to be decided.

**Seed.** Initial value for random number generators. Recorded so that runs can be reproduced
(D-016).

## Evaluation and research methodology

**Backtest.** Simulation of a strategy on historical data. Backtest results are not evidence of
future performance.

**Baseline / benchmark.** A simple, credible strategy that learned policies are compared against.

**Data leakage.** Using information during training or decision-making that would not have been
available at that time, including information from validation or test periods.

**Embargo / purge.** A gap between adjacent data periods so that forward-looking labels or rewards do
not leak across the boundary (D-019).

**Look-ahead bias.** Using data from time > *t* to make a decision at time *t*.

**Out-of-sample.** Data not used for training or tuning; here, the test period.

**Regime (market condition).** A period with distinctive behaviour, e.g. rising, falling or
high-volatility markets.

**Stress testing.** Evaluating performance in adverse historical episodes or scenarios. Committed
"where feasible".

**Survivorship bias.** Bias from including only assets that still exist today.

**Train / validation / test split.** Chronological, non-overlapping periods used for fitting, model
selection, and final evaluation respectively (D-009).

**Walk-forward evaluation.** Repeatedly re-training on a window of past data and evaluating on the
following period, moving forward in time. Committed "where feasible" (D-018).

## Explainability

**Feature attribution.** Assigning to each input feature a share of responsibility for a model output.

**Permutation importance.** Measuring the drop in performance when one feature's values are shuffled.
For time series this must be interpreted carefully.

**SHAP.** A feature-attribution method based on Shapley values. Optional extension.

**Sensitivity analysis.** Measuring how actions change when inputs are perturbed.
