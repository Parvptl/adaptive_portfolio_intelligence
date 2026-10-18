# Glossary

Terms used in this project's code and documentation. Where a precise definition is still a pending
decision, the entry says so and links to [`decision_log.md`](decision_log.md). Add terms as they
appear.

## Finance and portfolio management

**Adjusted close.** A closing price rewritten backwards in time so that splits and dividends do not
appear as price jumps: past prices are scaled down when a dividend is paid or a split happens. Simple
returns from adjusted closes approximate **total returns**. Yahoo's adjusted close is back-adjusted
for splits and dividends; its plain `Close` is split-adjusted only. Adjusted histories are
**revised** whenever a new dividend is paid, so two downloads can differ (D-037).

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

## Market data (milestone 2)

**Back-adjustment.** Rewriting *earlier* prices after a corporate action, so that the latest
price stays as quoted. This is how adjusted closes are built, and why they change over time.

**Cache (raw snapshot).** A saved copy of one provider download, with a manifest. Later runs can
reuse it instead of downloading again. It freezes one retrieval; it does not make the provider's
data permanent.

**Checksum (SHA-256).** A fingerprint of a file's exact bytes. If even one byte changes, the
checksum changes. The pipeline uses checksums to detect edited or corrupted snapshot files.

**Corporate action.** An event by the issuer that changes the share price without changing the
holder's wealth in the same way: a dividend, a stock split, or a capital-gain distribution.

**Data origin.** Where a dataset came from: `live` (downloaded from a provider), `local_csv`
(files you supplied), `synthetic` (generated) or `in_memory` (a test fixture). The quality report
always states it, so test data are never mistaken for market data.

**Dividend.** Cash paid to fund holders. On the ex-dividend date the price drops by about the
dividend amount. That drop is not a loss for the holder, which is why total returns need adjusted
prices.

**Forward-fill.** Copying the last known price into a later date that has no price. This project
never does it, because it invents a price and a 0 % return that did not happen (D-036).

**Manifest.** A JSON file stored with a snapshot. It records what was requested, from which
provider (and version), when (UTC), with which software versions, and the checksum of each file.

**Missing cell.** A session on which one instrument has no price while at least one other does.
The missing-data policy decides what happens: stop with an error, or drop the session for every
instrument.

**Observed calendar (session).** The list of dates on which at least one instrument has a price.
A **trading session** in this project is a date on that list. A **calendar day** is any date. No
exchange calendar is assumed (D-035).

**Point-in-time data.** Data exactly as they were known on each historical date, without later
revisions. Free sources such as Yahoo are *not* point-in-time.

**Price return vs. total return.** A price return uses price changes only. A total return also
counts dividends (as if reinvested). `close` gives price returns; `adj_close` approximates total
returns.

**Provider.** The source of market data (here `csv`, `yfinance` or `synthetic`). All providers
implement the same small interface, so the rest of the pipeline does not depend on any one of
them.

**Selection bias.** Bias from choosing instruments, dates or settings with knowledge of how they
turned out. For example, choosing a universe after seeing that it did well. The universe must not
be changed in response to test-period results.

**Sessions spanned.** For a return row, the number of observed sessions between its start price
and its end price. Normally 1; more than 1 if sessions in between were dropped, so the return
covers a longer period.

**Stock split.** Dividing each share into several. A 2:1 split halves the price without changing
the holder's wealth. Unadjusted prices show a fake −50 % return on the split date, which the
`max_abs_return` check is designed to catch.

**Temporal (chronological) split.** Dividing time-ordered data into training, validation and test
periods by date, never at random, so that a model is never trained on data that come after the
data it is evaluated on.

## Features and regimes (milestone 3)

**Boundary pair.** A decision at the last date of one split paired with an outcome (the next
return) in the following split. It belongs to neither split and is excluded, so that, for
example, validation outcomes never enter training (D-043).

**Calibration (training-only).** Estimating thresholds from the training period only, then
freezing them. Validation and test data are labelled with the frozen thresholds, never used to
re-estimate them.

**Causal feature.** A feature dated *t* computed only from information available at the close
of *t* (returns dated *t* or earlier). It never uses future data, centred windows or full-sample
averages.

**Composite (equal-weight).** The average of a group's daily returns, e.g. the equity composite
= mean of SPY, EFA and EEM returns each day. It is a summary, not a portfolio anyone traded.

**Cross-sectional dispersion.** How differently the assets moved on one day: the standard
deviation of that day's returns across assets.

**Decision time.** The close of day *t*, when features and labels dated *t* are known and a
portfolio decision could be made. Its outcome is the return of day *t+1*.

**Downside volatility.** The size of losses only: the square root of the average squared
negative return, with gains counted as zero.

**Frozen threshold artifact.** The JSON file (`regime_thresholds.json`) holding the
training-calibrated regime thresholds. Re-applying it reproduces labels without refitting.

**Lookback window.** The number of recent sessions a rolling feature uses, e.g. 21 sessions
(roughly a month). Counted in trading sessions, not calendar days.

**Momentum (trend).** The compounded return over a lookback window. Positive momentum means the
asset or market rose over that window.

**Neutral band.** The range of momentum treated as "no clear trend": between −b and +b, where
b is estimated from the training period (D-045).

**Rolling correlation.** The correlation between two return series over the lookback window. For
equity and bond composites it shows whether bonds have been diversifying (negative) or moving
with stocks (positive).

**Transition (regime).** A change of label from one day to the next. Few transitions mean
persistent regimes.

**Warm-up.** The first rows of the dataset where a rolling feature cannot be computed, because
fewer sessions than the window exist. These values stay missing and are never filled with zeros.

## Portfolio simulation and baselines (milestone 4)

**Common start.** The first decision date shared by all strategies in a split: the first day on
which every strategy has enough history (e.g. 63 returns for inverse volatility). Starting
together keeps the comparison on identical periods. Since milestone 4.2 the common start also
waits for `common_start_history_sessions` (126, the longest feature window), so that baselines
and a later feature-based agent share one window (D-058, Proposed).

**Funding vs. recurring turnover.** The funding trade is the one-off purchase from cash at the
start of a simulation. Recurring turnover is every later rebalance. They are reported
separately, and only recurring turnover is annualised (D-059, Proposed).

**Cost drag.** Gross cumulative return minus net cumulative return: how much return the
transaction costs removed over the period.

**Decision date / execution date.** The day whose closing information a target is based on, and
the day the trade happens. They are equal when the execution lag is 0.

**Dropped boundary decision.** A rebalance scheduled so late in a split that its weights would
only earn returns of the next split. It is skipped and counted, so each split's results use only
that split's returns (D-051).

**Execution lag.** The number of observed sessions between a decision and its trade
(`execution_lag_sessions`, required in the config). 1 trades at the next close and is the
proposed primary convention (D-055). 0 trades at the close just observed: an idealised
sensitivity case.

**End-of-row weights.** The `weight_*` columns of the ledger: the weights after that day's
price moves and any trade at its close. They earn the *next* row's return; the weights that
earned a row are on the previous row.

**Idealised sensitivity case.** A run under a deliberately optimistic assumption (here, lag
0), reported to show how much results depend on it, not as the main result.

**Opt-in test evaluation.** The test split is evaluated only when explicitly requested
(`--include-test`), so it stays reserved for the final, pre-registered evaluation (D-056).

**Pre-trade (drifted) weights.** The weights just before a trade: the previous weights moved
by that day's returns. Turnover and costs compare them with the target.

**Funding row.** The first row of a simulated period, when the portfolio converts its starting
cash into the first target weights. Its cost is charged when `charge_initial_funding` is true.

**Gross / net return.** Return before / after transaction costs. Net = gross − cost × (1 + gross).

**Inverse-volatility weighting.** Weights proportional to 1 / (recent volatility), so calmer
assets receive more. Here: the sample standard deviation of the last 63 daily returns, capped at
`max_weight`.

**Ledger.** The day-by-day record of a simulation: returns, trades, costs, value, drawdown and
the weights held.

**Per-session metric.** A metric left in daily units (e.g. daily volatility) because the
annualisation factor (D-023) has not been decided.

**Pro-rata cost deduction.** Paying the transaction cost proportionally out of every holding, so
the weights after the trade equal the target exactly.

**Target weights.** The weights a strategy asks for at a decision, checked against the
constraints (e.g. the 0.40 cap) when executed. Holdings can drift away from them afterwards.

**Water-filling (weight capping).** Setting weights above the cap to the cap and handing the
excess to the uncapped assets in proportion to their weights, repeated until none exceeds the
cap.

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
high-volatility markets. In this project, a regime is a *label* assigned by simple rules to each
day (trend × volatility, D-045). It is a description, not a verified economic state.

**Stress testing.** Evaluating performance in adverse historical episodes or scenarios. Committed
"where feasible".

**Survivorship bias.** Bias from including only assets that still exist today. Funds that closed
(often after doing badly) are missing, so the history looks better than what an investor could
actually have picked at the time. This project's ETF universe was chosen in 2026 and is affected
(D-034).

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
