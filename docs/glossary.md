# Glossary

Terms used in this project's code and documentation. Where a precise definition is still a pending
decision, the entry says so and links to [`decision_log.md`](decision_log.md). Add terms as they
appear.

## Finance and portfolio management

**Adjusted close.** Closing price adjusted for dividends and splits, so that price changes reflect
total return. Adjustment methods differ between data providers.

**Annualisation.** Converting a per-period figure into a per-year figure, so that results from
daily, weekly and monthly data can be compared. N is the number of periods per year
(`periods_per_year`), e.g. 12 for monthly data. Volatility is annualised by multiplying by √N, not
N, because variances (not standard deviations) add up over independent periods. Example: a monthly
volatility of 2 % becomes 2 % × √12 ≈ 6.9 % per year. Returns are annualised by compounding (see
*Annualised return*), not by multiplying by N. The value of N for daily data (252 or 365) is still
an open decision (D-023).

**Annualised return (CAGR, compound annual growth rate).** The constant yearly growth rate that
would turn the starting value into the final value over the same time: (V_T / V_0)^(N/T) − 1, where
T is the number of periods observed. Example: 100 growing to 121 over two years is 10 % per year,
because 1.1 × 1.1 = 1.21. It is *not* the average return × N: +50 % then −50 % averages 0 %, but
the portfolio falls from 100 to 75, which is −13.4 % per year over two years. **Caution:**
annualising a short period exaggerates. One good month of +5 % annualises to about +80 % per year,
which says little about a real year (D-029).

**Arithmetic vs. geometric average.** The arithmetic average adds returns and divides by their
count. The geometric average reflects compounding: what you actually ended up with. When returns
vary, the geometric average is lower ("volatility drag"). The Sharpe ratio uses the arithmetic
mean; annualised return (CAGR) uses the geometric one.

**Asset universe.** The set of assets the strategy may hold. Here: 7 US-listed ETFs, provisionally
(D-005).

**Basis point (bp, bps).** One hundredth of a percent: 1 bp = 0.01 % = 0.0001.

**Buy-and-hold.** Benchmark that buys an initial allocation and never rebalances.

**Calmar ratio.** Annualised return divided by the absolute value of maximum drawdown.

**Cash position.** Portfolio weight not allocated to any asset. Assumed to earn the risk-free rate
(currently 0, provisional). When computing turnover, cash is written as its own column so that all
weights add up to 1.

**Cumulative return.** How much the portfolio gained or lost over the whole period, as a decimal:
V_T / V_0 − 1. Example: from 100 to 121 is 0.21 (+21 %). It is the same as compounding all period
returns. It says nothing about how long the period was or how much risk was taken, so it is always
reported together with other metrics (D-028).

**Drift (weight drift).** Changes in portfolio weights caused by price moves, without any trading.
Example: start at 50/50; if asset A rises 10 % and B is flat, the weights become about 52.4 % /
47.6 %. Rebalancing back to 50/50 then requires a trade.

**Decimal vs. percentage.** All returns and rates in code are decimals: 0.05 means 5 %. A value
of −1.5 passed as a return is rejected, because it would mean a loss of 150 %; it is probably a
percentage written by mistake.

**Drawdown.** How far the portfolio currently sits below its best value so far, as a fraction:
D_t = V_t / P_t − 1, where P_t is the peak. It is 0 at a new high and negative otherwise. Example:
if the portfolio peaked at 120 and is now 90, the drawdown is 90 / 120 − 1 = −0.25 (25 % below the
peak).

**Equal weight (1/N).** Benchmark allocating the same weight to every asset, rebalanced periodically.

**ETF (exchange-traded fund).** A fund traded on an exchange like a stock, often tracking an index.

**Long-only.** No negative (short) weights are allowed.

**Maximum drawdown (MDD).** The worst drawdown over the whole period: the largest fall from a peak
to a later trough. It is reported as a non-positive decimal (e.g. −0.25), and answers the question
"what was the biggest loss an investor could have suffered?" A core risk metric in the abstract.
Here, the first observation counts as the initial peak (D-026).

**Mean-variance optimisation (Markowitz).** Choosing weights that trade off expected return against
variance.

**Minimum variance portfolio.** Weights that minimise estimated portfolio variance, ignoring expected
returns.

**Peak (running peak, high-water mark).** The highest portfolio value reached so far:
P_t = max of V_s for all s ≤ t. It never decreases. In this project the first observation is the
starting peak.

**Periodic vs. annual rate.** A periodic rate applies to one observation interval (e.g. one day or
month); an annual rate applies to a year. They must not be mixed: an annual rate must not be
subtracted from a daily return. Conversion used here (D-024):
r_periodic = (1 + r_annual)^(1/N) − 1. Example: 12.68 % per year ≈ 1 % per month.

**Portfolio return (simple return).** The percentage change in portfolio value over one period,
written as a decimal: r_t = V_t / V_{t−1} − 1. Example: from 100 to 110 is a return of 0.10
(+10 %); from 110 back to 99 is −0.10. Note that +10 % followed by −10 % does not return to the
starting value. A series of n + 1 values gives n returns (D-021).

**Rebalancing.** Trading to move current weights to target weights.

**Risk-free rate.** The return available without taking risk, typically approximated by short-term
government bills. Used as the hurdle in the Sharpe ratio: a strategy should earn more than this to
compensate for its risk. The project's config holds it as an annual decimal (provisional constant
0.0); it is converted to a periodic rate before use.

**Risk parity / inverse volatility.** Allocations that equalise each asset's risk contribution, or
weight assets in inverse proportion to their volatility.

**Sample standard deviation (`ddof=1`).** A measure of spread that divides the sum of squared
deviations by T − 1 rather than T, because the data are a sample. With only one observation it is
undefined. Used for volatility and the Sharpe ratio (D-022).

**Sharpe ratio.** Reward per unit of risk: the average return above the risk-free rate, divided by
the volatility of that excess return, then annualised:
S = √N · mean(r − r_f) / std(r − r_f). Higher is better. A Sharpe of 1 means that, on average,
the excess return equals one standard deviation per year. It can be negative. If returns do not
vary at all, the ratio is undefined (division by zero), and the code raises an error rather than
reporting infinity (D-025). A core metric in the abstract. Limitation: it treats upside and downside
swings the same way.

**Slippage.** The difference between the expected and the actual execution price. Modelled here as
an extra cost in bps (provisional; optional extension).

**Sortino ratio.** Like Sharpe, but divides by downside deviation only.

**Transaction cost.** Cost of trading, modelled as a proportion (in bps) of the value traded.
Provisional value: 10 bps (D-007). Exactly which measure is charged (traded notional, which
excludes the cash leg, or all-column turnover) is not yet decided (D-031).

**Trough.** The lowest point of a drawdown, before the portfolio starts to recover. The maximum
drawdown is measured from a peak to its trough.

**Turnover (two-way).** How much the portfolio trades at a rebalance. It is the sum, over all assets
(including cash if held), of how much each weight changes: Σ |w_post − w_pre|. It ranges from 0 (no
trade) to 2 (sell everything and buy something else). "Two-way" means both the selling and the buying
side are counted: moving 10 % from asset A to asset B gives 0.10 + 0.10 = 0.20. The weights before
trading are the *drifted* weights, not the previous targets. A core metric in the abstract; the
definition is proposed (D-011, D-030). **Annualised turnover** adds up the turnover of all
rebalances and expresses it per year (e.g. 1.2 = 120 % of portfolio value traded per year, counting
both sides).

**Turnover (one-way).** Half of two-way turnover, i.e. only one side of each trade. It is common in
the literature; always state which convention a number uses.

**Traded notional.** The value of securities actually bought plus sold at a rebalance, as a
fraction of portfolio value: the sum of |weight change| over the **non-cash** assets. Cash is
where trades settle; it is not itself traded. Example with a cash column: buying 10 % of an asset
with cash is traded notional 0.10, but two-way turnover over all columns counts it as 0.20 (asset
leg plus cash leg). Switching 10 % between two assets is 0.20 under both. In code:
`portfolio_turnover(pre, post, cash_column=j)`. Ordering: one-way ≤ traded notional ≤ two-way. The
proposed basis for future transaction costs (D-031, still open).

**Volatility.** How much returns fluctuate around their average, measured as the (sample) standard
deviation of returns and usually annualised. Higher volatility means a bumpier, riskier ride. It
says nothing about direction: steady losses can have low volatility. Example: monthly returns of
2 % and 4 % have a monthly volatility of about 1.41 %, or about 4.9 % per year.

**Volatility drag.** The gap between arithmetic and compounded growth caused by ups and downs:
approximately σ²/2 per period. A +10 % gain followed by a −10 % loss leaves you at 0.99, not 1.00.

**Weight (portfolio weight).** Fraction of portfolio value held in an asset. Pre-trade weights are
measured just before a rebalance (after drift); post-trade weights are the targets just after it.

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
