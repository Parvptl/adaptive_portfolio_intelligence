# Presentation Guide

How to present Adaptive Portfolio Intelligence honestly at reviews, demos and the final
presentation. Update this guide whenever the project's demonstrable status changes.

## Current status (as of 2026-10-19)

- **Available:** the abstract; repository scaffold; validated configuration loader with tests;
  documentation (architecture, roadmap, decision log, glossary); **all seven tested financial
  metrics of milestone 1**: portfolio returns, cumulative return, annualised return (CAGR),
  annualised volatility, Sharpe ratio, maximum drawdown and two-way turnover.
- **Milestone 2 (pushed; data methods D-035–D-039 accepted 2026-10-19; data values
  provisional):** a reproducible
  market-data pipeline with a quality report, chronological split labels and a cache. One live
  download of the proposed 7-ETF universe (2007–2024) has been processed.
- **Milestone 3 (pushed; decisions Proposed; feature windows D-044 acknowledged as
  provisional):** causal market
  features and rule-based regime labels, with thresholds fitted on the training period only and
  a regime report.
- **Milestone 4 (commit `66f9ed7`, originally `a7134b7`; conventions accepted 2026-10-19):** a
  transparent
  portfolio simulator (timing, costs, cash, constraints) and three conventional baselines
  (equal weight monthly, equal-weight buy-and-hold, inverse volatility monthly). One
  descriptive baseline run on train and validation is recorded as EXP-001. It used lag 0,
  now the idealised sensitivity case.
- **Milestone 4.1 (commit `880d82c`, CI passed; decisions D-055 to D-057 accepted
  2026-10-19):** hardening after an audit:
  - lag 1 as the primary timing;
  - the test split is evaluated only on explicit request;
  - simulator settings are validated;
  - cap and ledger semantics are documented.
- **Milestone 4.2 (commit `817f8b8`, CI passed):** a draft research protocol (**not approved**, so do not
  present it as final), a common evaluation window covering the feature warm-up, and
  funding turnover reported separately.
- **Milestone 5.1 (2026-10-19, uncommitted):** RL environment building blocks: observation,
  action mapping, reward and a step-by-step simulator interface. They are checked on the real
  training split only. There is no trained agent, and no RL results exist.
- **Milestone 5.2 (2026-10-19, uncommitted):** a Gymnasium environment that passes
  Gymnasium's own checker. It is validated on the training split only. It has not been used for
  training.
- **M5.3 preparation (2026-10-19, uncommitted):** a PPO training wrapper that records every
  setting, seed, package version and data hash. It is tested without training.
- **Pre-grid hardening (2026-10-19, uncommitted):** the training pipeline cannot replace
  completed results, records the exact code version, and runs the grid sequentially with
  recovery. It is tested without training. Two throughput smoke runs (EXP-003) are execution
  checks only.
- **Not available yet:** trained agents (no full PPO training has run), RL results,
  explainability. Regime labels
  are descriptions of market conditions, not results. Baseline numbers are backtest output
  under provisional conventions, not findings.
- **Decided:** the metric conventions were accepted by the team on 2026-10-13 (D-011, D-021,
  D-022, D-024 to D-030). **Still open:** the daily annualisation factor (D-023). Trade timing
  (D-013) and the cost basis (D-031) now have proposals (D-048, D-049) awaiting approval.
- **What can honestly be shown today:** the research question, planned methodology, evaluation
  safeguards, architecture, the reproducible engineering setup, and how the metrics are defined and
  tested, and how the simulator accounts for timing and costs. Baseline figures from EXP-001
  may be shown only with their caveats (below). **Do not show test-period numbers** and do not
  rank strategies.
- **Data facts that may be shown:** coverage, number of sessions, missing data and other
  data-quality facts about the downloaded dataset. **Do not** present per-asset returns from the
  quality report as findings. They describe the data, not any strategy, and they include the test
  period.

## Explaining the simulator and baselines

### In one sentence

"Given the weights a strategy wants, the simulator applies them a day at a time: it trades only
on information already known, charges costs on what is actually bought and sold, lets weights
drift with prices, and keeps a full ledger, with identical rules for every strategy."

### Key points to explain

1. **Timing (D-048, D-055).** Decide at the close of day *d* and trade at the next close
   (proposed primary convention). Trading at the same close is shown only as an idealised
   sensitivity case. The new weights earn from the day after the trade. A test puts a +50 %
   return on the trade day itself and checks that the newly bought asset does not earn it.
2. **Costs (D-049).** 15 bps (provisional) on traded notional, including the first purchase.
   *Illustration:* moving 10 % of the portfolio from one ETF to another trades 20 % notional and
   costs 0.03 % of value.
3. **Same rules for all.** Strategies only produce weights; one simulator does all the
   accounting. The future RL agent must use the same simulator.
4. **Splits are kept apart (D-051).** Each period starts from cash. A rebalance that would only
   earn next-period returns is dropped.
5. **Gross and net.** Both are reported, so the cost of trading is visible.
6. **The test set stays sealed (D-056).** Exploratory runs cover training and validation only;
   the test period needs an explicit `--include-test` and is reserved for the final evaluation.
7. **The cap is a rebalancing rule (D-057).** A 0.40 cap limits what is bought at each
   rebalance. Between rebalances an asset can grow above 0.40; no trade is forced.

### What can be said about EXP-001

- "The pipeline reproduces its results exactly and matches independent recomputations."
- "Inverse volatility traded about twice as much as monthly equal weight, so costs took more of
  its return. It also had smaller drawdowns in both training and validation."
- **Do not say** that a strategy "wins", "beats" or "is better". These are single historical
  paths under provisional costs, per-session metrics, and no significance testing.
- **Do not show** test-period numbers. Since milestone 4.1 the command no longer computes them
  unless asked (D-056). Earlier test outputs from the milestone-4 run exist only in a local,
  git-ignored folder and must not be reported.
- EXP-001 used lag 0, which is now the idealised case. Say so if it is shown.

### Questions to expect

- *Why trade one day after the signal?* A signal computed from today's close cannot be filled at
  that same close. Lag 1 is the proposed primary convention; lag 0 is shown only as an
  idealised sensitivity case.
- *Isn't the 0.40 cap violated?* Holdings can drift above it between monthly rebalances; the
  cap applies when trading. Forcing extra trades would change the strategy and its costs.
- *Why no annualised Sharpe?* The annualisation factor (252 vs. observed sessions per year) is an
  open decision (D-023). The metric is shown per session until the team decides.
- *Why only three baselines?* They are the simplest credible set and need no fitted parameters.
  Optimisation-based baselines need further choices (covariance estimation, solver) and team
  approval.

## Explaining features and regimes

All numbers below are descriptive facts about the data or illustrations. None is a result, and
none says anything about any strategy.

### In one sentence

"Every trading day, we describe the market using only information available that evening (recent
trend, volatility, losses, how assets moved together), and we label the day with a simple,
explainable regime such as 'positive trend, low volatility', using thresholds learned from the
training years only."

### Key points to explain

1. **No peeking (D-043).** A feature for day *t* uses returns up to *t*. Tomorrow's return is what
   a decision today would earn, so it is never an input. *Illustration:* a 21-day volatility on
   15 March uses 15 March and the 20 sessions before it, never 16 March.
2. **Boundary days.** The last training day's "tomorrow" is the first validation day. That pair is
   excluded so validation outcomes never leak into training.
3. **Simple, explainable regimes (D-045).**
   - **Trend:** negative / neutral / positive, according to whether the equity composite's
     3-month return is below −b, between, or above +b.
   - **Volatility:** low / normal / high, compared with the training period's terciles.
4. **Training-only thresholds.** The thresholds come only from 2007–2016, are saved in a file,
   and are applied unchanged to 2017–2024. Changing validation or test data cannot move them; a
   test checks this.
5. **Honest diagnostics.** The report shows how often each regime occurs per period, how often
   labels change, and warnings. For example, some regimes are rare in the validation years, which
   were calm compared with a training period that includes 2008.

### Descriptive facts from the first run on the live snapshot

- Thresholds: trend band ±3.8 % over 63 sessions; volatility terciles 0.89 % / 1.31 % per
  session (training only, 2,455 rows).
- All 9 trend × volatility combinations occur.
- About 46 % of validation days are "positive trend, low volatility". This describes 2017–2019
  relative to 2007–2016; it is not a finding.
- The report warns about sparse regimes and that 62 % of training "positive, high volatility"
  days fall in 2009.

### Questions to expect

- *Why not a machine-learning regime model?* Interpretability first. A hidden Markov model or
  clustering is an optional later extension and would also be fitted on training data only.
- *Aren't the regimes just hindsight?* The thresholds use training data only, and the labels use
  only past returns. The labels are still heuristics, and we present them as such.
- *Why terciles?* They are a simple, explainable default, not tuned. Changing them after seeing
  test results is not allowed.

## Explaining the market-data pipeline

All numbers below are descriptive facts about the downloaded data, or illustrations. None is a
result.

### What it does, in one sentence

"It downloads, or loads, daily prices for a fixed list of ETFs. It checks them thoroughly, turns
them into daily returns without inventing any data, labels every day as training, validation or
test by date, and writes a report saying exactly what came in and what was dropped."

### Key points to explain

1. **Universe (Proposed, D-034).** Seven liquid ETFs, one per risk driver: US, developed and
   emerging equities (SPY, EFA, EEM); Treasuries of two durations (IEF, TLT); investment-grade
   credit (LQD); gold (GLD). *Be honest:* they were chosen in 2026, with hindsight. That is
   survivorship and selection bias, so the results will not show what an investor could have
   picked in 2007.
2. **Source (Proposed, D-008).** Yahoo Finance through the free `yfinance` package: convenient
   and credential-free, but unofficial and revisable. The pipeline also reads your own CSV files,
   or generates labelled synthetic data for tests.
3. **Adjusted prices (D-037).** We use adjusted closes, so dividends and splits do not look like
   crashes. *Illustration:* without adjustment, a 2:1 split looks like a −50 % day. The pipeline
   rejects any daily move beyond ±40 % as a probable data error.
4. **No invented data (D-036).** A missing price stops the pipeline by default. It is never
   copied forward. If you explicitly allow dropping a day, the next return is marked as covering
   two sessions.
5. **No look-ahead (D-038).** Each row belongs to the period that contains its own date.
   Training never sees a price from after the training period. *Illustration:* the first
   validation return starts from the last training price, which was already known.
6. **Reproducibility (D-039).** Each download is saved with a manifest (what was requested,
   when, by which software) and checksums. Re-running from the saved copy produces byte-identical
   files. *Limit:* re-downloading later can give different adjusted prices, so the saved copy is
   the reference.

### Descriptive facts about the first live snapshot (retrieved 2026-10-15)

- 4,530 sessions from 2007-01-03 to 2024-12-31 for all seven ETFs, with no missing prices.
- 250–253 sessions per calendar year. This is relevant to the open annualisation question
  (D-023), but **does not decide it**.
- The largest gap between sessions is 5 days (the late-October 2012 market closure).
- These describe the dataset only. They say nothing about any strategy.

## Explaining the core metrics

All numbers in this section are **illustrative toy examples** chosen to make the arithmetic easy.
They are not project results and describe no real asset or strategy.

### Why these metrics matter for this project

The research question is whether an adaptive RL policy is *useful*, not just whether it makes
money. A strategy with a higher return can still be worse if it takes far more risk, suffers deep
losses, or trades so much that costs eat the gains. The abstract therefore commits to cumulative
return, the Sharpe ratio, maximum drawdown and turnover. Every strategy is compared on the same
metrics, data, costs and periods.

Think of the metrics as answering four questions:

1. **How much?** Cumulative return and annualised return.
2. **How bumpy?** Volatility.
3. **Worth the risk?** The Sharpe ratio.
4. **How painful, and how costly to run?** Maximum drawdown and turnover.

| Metric | Question it answers | Formula | Better when |
| --- | --- | --- | --- |
| Portfolio return | How much did the portfolio gain or lose each period? | r_t = V_t / V_{t−1} − 1 | — (input to the others) |
| Cumulative return | How much did it gain or lose in total? | V_T / V_0 − 1 | Higher (but see risk) |
| Annualised return (CAGR) | What steady yearly growth would give the same result? | (V_T / V_0)^(N/T) − 1 | Higher (but see risk) |
| Annualised volatility | How bumpy is the ride? | σ_ann = std(r) · √N | Lower, for the same return |
| Sharpe ratio | How much excess return per unit of risk? | √N · mean(r − r_f) / std(r − r_f) | Higher |
| Maximum drawdown | What was the worst fall from a high? | min_t (V_t / max_{s≤t} V_s − 1) | Closer to 0 |
| Turnover (two-way) | How much did a rebalance trade? | Σ_i \|w_post,i − w_pre,i\| | Lower, for the same performance |

N is the number of periods per year (e.g. 12 for monthly data); T is the number of periods
observed. All values are decimals (0.10 = 10 %).

### Slide-ready explanations

**1. Portfolio return.** "We turn the portfolio's value path into period-by-period percentage
changes." *Illustration:* 100 → 110 → 99 gives returns of +10 % and −10 %. The portfolio ends at
99, not 100, because returns compound.

**2. Annualised volatility.** "Volatility measures how much returns swing around their average. We
annualise it so that daily and monthly results are comparable." *Illustration:* monthly returns of
+2 % and +4 % have a monthly sample standard deviation of 1.41 %. Multiplied by √12, that is about
4.9 % per year. Volatility measures risk as uncertainty: it does not say whether returns were good
or bad.

**3. Sharpe ratio.** "Return above the risk-free rate, per unit of volatility: a fair way to
compare a cautious strategy with an aggressive one." *Illustration:* monthly returns of 2 %, 4 % and
0 % with a 1 %-per-month risk-free rate give excess returns of 1 %, 3 % and −1 %. Their mean is 1 %
and their standard deviation 2 %, so the monthly Sharpe is 0.5 and the annualised Sharpe is
0.5 × √12 ≈ 1.73. *Interpretation:* higher is better; negative means the strategy did worse than the
risk-free rate. If returns never vary, the Sharpe is undefined and we report it as such, not as
infinity.

**4. Maximum drawdown.** "The worst loss an investor could have experienced, buying at a peak and
selling at the following low." *Illustration:* 100 → 120 → 90 → 110 → 130 → 117 has a maximum
drawdown of −25 % (from 120 to 90), even though the path ends higher than it started. The metric
captures pain that the final return hides.

**5. Cumulative return.** "How much the portfolio grew or shrank in total, from start to finish."
*Illustration:* 100 → 110 → 99 → 121 is 121/100 − 1 = **+21 %**. Multiplying the period growth
factors gives the same answer: 1.10 × 0.90 × 1.222 = 1.21. *Caveat:* it ignores how long it took
and how rough the journey was. 100 → 300 → 100 has a cumulative return of 0 %.

**6. Annualised return (CAGR).** "The steady yearly growth rate that would produce the same end
result. It lets us compare a 2-year and a 5-year test fairly." *Illustration:* 100 → 121 over two
years gives (1.21)^(1/2) − 1 = **10 % per year**, because 1.10 × 1.10 = 1.21.
- *Why not just average the returns?* +50 % then −50 % averages 0 %, but 100 → 150 → 75 actually
  lost 25 %. CAGR reports −13.4 % per year, which reflects reality. The gap is called
  *volatility drag*.
- *Big caveat:* annualising a short window exaggerates. One month at +5 % annualises to about
  **+80 % per year**. The formula cannot fix this, so we always state the window length, and we do
  not headline annualised numbers for windows shorter than a year (proposed rule, D-029).

**7. Turnover.** "How much of the portfolio we had to trade at each rebalance. It matters because
every trade costs money." *Illustration:*
- Moving from 60/40 to 50/50 trades 10 % out of one asset and 10 % into the other. Two-way
  turnover counts both sides: **0.20**.
- Selling everything and buying something else is the maximum, **2.0**.
- *The subtle point, which is good to explain in a viva:* even if the target allocation never
  changes, markets move the weights ("drift"). Suppose the target is 50/50, asset A rises 10 % and
  B is flat. The portfolio is now about 52.4 / 47.6, so getting back to 50/50 requires trading
  (turnover ≈ **0.048**). Comparing "target vs. previous target" would wrongly say 0. That is why
  our function takes the *drifted* pre-trade weights.
- *Annualised turnover:* add up the turnover of all rebalances and express it per year. For
  example, 12 monthly rebalances of 0.10 each give **1.2 per year**.
- *Cash, and the question an examiner may ask:* if cash is one of the columns, buying 10 % of an
  asset with cash moves two weights (asset +0.10, cash −0.10). Summing over all columns gives
  0.20, but only 0.10 of a security was actually traded. So the function has two measures:
  - the default sums every column;
  - `cash_column=j` leaves cash out and gives **traded notional**: 0.10 for that purchase, and
    0.20 for a 10 % switch between two assets.

  Rule of thumb: one-way ≤ traded notional ≤ two-way. Which measure transaction costs will use is
  decided in the environment milestone (D-031); traded notional is the proposed choice.

### How to interpret them together

- Never present return alone. Pair it with volatility, Sharpe, maximum drawdown and turnover.
- A higher Sharpe with a much deeper drawdown is a trade-off, not a clear win.
- High turnover makes results sensitive to the cost assumption. A strategy that wins only at zero
  cost is not a convincing win.
- Metrics from short periods are noisy; differences between strategies need uncertainty estimates
  (planned) before being called meaningful.
- All results must be stated net of transaction costs, with the period (train / validation / test),
  the window length T and the annualisation factor N.

### Check your understanding (answers below)

1. A portfolio goes 100 → 80 → 100. What are its cumulative return and its maximum drawdown?
2. Why is volatility multiplied by √12, not 12, for monthly data?
3. Why can the Sharpe ratio be "undefined", and what do we report then?
4. Two years of data turn 100 into 81. What is the CAGR?
5. The target weights are the same at every rebalance. Can turnover still be positive?

*Answers:*
1. Cumulative 0 %; maximum drawdown −20 % (80/100 − 1).
2. Variances add over independent periods, so standard deviations grow with the square root of
   time.
3. If returns never vary, the denominator is zero. We report "undefined", never infinity.
4. (0.81)^(1/2) − 1 = 0.9 − 1 = −10 % per year.
5. Yes. Price moves cause the weights to drift away from the target, and rebalancing back requires
   trades.

### Methodological choices to mention if asked

These conventions were accepted by the team on 2026-10-13, except where marked open:

- Sample standard deviation (`ddof=1`). It is unbiased for the variance; the standard deviation
  itself is slightly biased low (D-022). Annualisation by √N, with N given explicitly. Which N to
  use for daily data (252 or 365) is still open (D-023).
- An annual risk-free rate is converted to a periodic rate by compounding, never subtracted from
  daily returns directly (D-024).
- Undefined values raise an error instead of being reported as infinity (D-025). The zero
  threshold (1e-12) was checked against measured floating-point noise.
- Drawdown is measured from the first observation onward (D-026).
- Cumulative return is V_T/V_0 − 1 (D-028). Annualised return is geometric (CAGR), not
  mean × N (D-029).
- Turnover is two-way, from drift-adjusted pre-trade weights, with cash as a column (D-011, D-030).
  By default it sums all columns; `cash_column` gives traded notional. How trading costs use these
  measures is still open (D-031).
- Correctness: each metric is checked against hand-calculated examples. In addition, a hand-picked
  set of deliberate bugs (for example `ddof=0`, simple instead of geometric conversion, one-way
  instead of two-way turnover) was injected into a temporary copy of the code. The tests failed for
  every one of them (technical handbook §10.11). This is evidence that the tests catch those
  specific mistakes. It is **not** systematic mutation testing and does not prove the tests catch
  every possible bug.

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
- *Why these assets / dates / costs?* They are provisional development choices (D-034, D-006,
  D-007, D-009). The universe follows stated criteria (one liquid ETF per risk driver, history
  before 2007), but it was chosen with hindsight. Sensitivity analysis is planned where feasible.
- *Where does the data come from, and can it be reproduced?* From Yahoo Finance via `yfinance`
  (unofficial). Each download is frozen with a manifest and checksums; re-processing a saved
  download is exactly reproducible, but re-downloading may not be.
- *How do you handle missing prices and splits?* Missing prices stop the pipeline or drop the
  whole day explicitly, and are never filled. Adjusted prices absorb splits and dividends, and a
  ±40 % daily-move check catches unadjusted splits.
- *Isn't the ETF list survivorship-biased?* Yes. We state it as a limitation and do not claim the
  results generalise to a historical investable universe.
- *Why PPO?* Named as a candidate in the abstract: suited to continuous actions such as portfolio
  weights, and widely used. Not assumed to be optimal.
- *What if RL does not beat the baselines?* That is a valid, reportable result.
- *Is this financial advice?* No. It is a research and decision-support project.

## Disclosure

Include the AI-use disclosure (see README) in the final presentation and report.
