# Adaptive Portfolio Intelligence: a complete walkthrough for new readers

**Explainable Reinforcement Learning for Regime-Aware Portfolio Allocation and Risk Management**
· Parv Patel, Mandar Patil · Walkthrough written 2026-10-22 · Repository state: commit `26a2abd`
on `main`

> **How to read this document**
> - It explains the whole project from the ground up: the idea, the finance, the reinforcement
>   learning, what was built, what was measured, and what is still open. It assumes no prior
>   knowledge of the project.
> - Every important statement carries a label:
>   - **[Verified]**: checked against the repository's code, configuration, saved outputs or
>     decision records.
>   - **[Example]**: an illustration with made-up numbers, to explain a concept. *It is not a
>     project result.*
>   - **[Not done]**: planned, proposed or blocked. *There is no result for it.*
> - The authoritative records are `docs/decision_log.md` (decisions D-001 to D-083),
>   `docs/experiment_log.md` (experiments EXP-001 to EXP-008), `docs/approval_checklist.md`
>   (approvals) and `docs/technical_handbook.md` (commands and interfaces). When this document
>   and those records disagree, the records win.
> - **This is research and decision support, not financial advice.** All performance numbers
>   are simulated historical backtests on training or validation data. **No out-of-sample
>   (test) result exists yet.**

---

## The project in one page

**The question.** Can a reinforcement-learning (RL) agent learn to move money between seven
exchange-traded funds (ETFs) as market conditions change? And can it do better, *after
trading costs and taking risk into account*, than simple rules that any investor could follow?

**What was built** [Verified]:
1. a reproducible data pipeline for seven ETFs, 2007–2024;
2. 34 "causal" market features (each uses only information available at the time);
3. rule-based labels describing nine market conditions ("regimes");
4. a portfolio simulator with realistic timing, transaction costs and weight limits;
5. three simple benchmark strategies;
6. an RL environment and a PPO training pipeline;
7. a validation evaluator that picked one PPO configuration by a rule fixed in advance;
8. analysis, explainability and dashboard tools;
9. a separate, heavily guarded evaluator for the final test, which has **not** been run.

**What was found so far** [Verified]:
- PPO trained successfully: 40 runs (8 settings × 5 random seeds) on 2007–2016 data.
- On 2017–2019 validation data, **every** PPO policy had a **lower** risk-adjusted return (net
  Sharpe ratio) than **each** of the three simple benchmarks.
- The PPO policies traded far more: about 13–28 times the portfolio per year, against at most
  0.78 for the benchmarks. That cost them 7–15 percentage points of return over three years.
- Even before costs, most PPO policies earned less than the benchmarks.

**What is still open** [Not done]:
- the final test on 2020–2024 data, which stays deliberately **sealed** until a strict
  pre-registration and approval process is complete;
- the explanation of the PPO policy's decisions;
- stress tests and statistical intervals on real data;
- the planned ablation experiment.

**Honest bottom line.** The project has a complete, carefully controlled research pipeline.
So far, the evidence does **not** show that the RL approach beats simple allocation rules. The
next steps are about finishing the evaluation honestly, not about assuming success.

---

## Stage 1 — Define the research problem

### 1.1 The problem in everyday terms

Imagine you have 100,000 dollars to invest and seven funds to choose from: US stocks,
international stocks, emerging-market stocks, two kinds of US government bonds, corporate bonds
and gold. Every week you may change how much you hold in each. Three things make this hard:

- **Markets change character.** Sometimes stocks rise steadily with little volatility;
  sometimes they fall sharply and everything is volatile. An allocation that works in one
  condition may fail in another.
- **Trading costs money.** Every time you rebalance, you pay costs (commissions, bid–ask
  spreads, price impact). A strategy that trades constantly can lose its gains to costs.
- **Return is not everything.** A strategy that earns a lot but sometimes loses 30% of its
  value is riskier than one that earns a little less with smaller swings.

### 1.2 What the project is trying to find out

The project investigates whether an RL agent can learn a **sequential allocation policy**: a
rule that, at each decision point, looks at recent market conditions and the current portfolio,
and decides how the money should be split. Success is judged on:

- performance **after transaction costs** (net of costs);
- **risk-adjusted** performance (mainly the Sharpe ratio, explained in Stage 6);
- **drawdowns** (the worst peak-to-trough losses) and **volatility**;
- **turnover** (how much is traded);
- **interpretability** (can we understand what the policy does?).

**The research question** (from the submitted abstract) [Verified]: can a PPO-based agent learn
allocations with competitive risk-adjusted performance after transaction costs, compared with
conventional benchmark strategies? The abstract states explicitly that *no improvement is
assumed in advance*.

### 1.3 Why reinforcement learning, and why caution

- **Supervised learning** learns to predict a label from examples (e.g. "will SPY rise
  tomorrow?").
- **Reinforcement learning** learns to *act*: an agent takes actions in an environment,
  receives feedback (a "reward") and gradually improves its decision rule (its "policy").

Portfolio management fits RL naturally, because today's decision changes tomorrow's holdings,
and therefore tomorrow's costs and risks.

**Caution:** RL is flexible enough to "memorise" one historical path. A policy can look
excellent on the data it was trained on and fail on new data. This project therefore puts most
of its effort into **fair, leak-free evaluation** (Stages 2, 9 and 10).

---

## Stage 2 — Select financial data and assets

### 2.1 The seven ETFs [Verified]

| Ticker | What it holds | Role in the portfolio |
| --- | --- | --- |
| SPY | Large US companies (S&P 500) | US equity growth |
| EFA | Developed markets outside North America | International equity |
| EEM | Emerging-market companies | Higher-risk equity |
| IEF | US Treasury bonds, 7–10 years | Safer government bonds |
| TLT | US Treasury bonds, 20+ years | Long-duration bonds, sensitive to interest rates |
| LQD | Investment-grade corporate bonds | Corporate credit |
| GLD | Gold | A non-financial store of value |

The portfolio can also hold **cash**, which earns 0% in this project.

### 2.2 Where the data come from [Verified]

- **Source:** daily adjusted prices from the public *yfinance* provider, retrieved on
  2026-10-15 for 2007–2024. They were turned into daily simple returns by a reproducible
  pipeline.
- **Identity:** every processed dataset has a content-based identifier. The one used throughout
  is `8e00568ee2aa4de7` (raw data `e27437b97742fa43`).
- **Known limitations, recorded in the dataset metadata:**
  - the seven funds were chosen *today*, with hindsight. Funds that closed or performed badly
    are not in the list (**survivorship and selection bias**, D-034);
  - "adjusted" prices depend on how the provider adjusts for dividends;
  - only days on which data exist are seen.

### 2.3 Chronological splits: the most important safeguard [Verified]

| Split | Dates | Used for |
| --- | --- | --- |
| Training | 2007–2016 | Fitting feature scalers and regime thresholds; training PPO |
| Validation | 2017–2019 | Choosing one PPO configuration by a fixed rule (done once) |
| Test | 2020–2024 | The single final evaluation. **Sealed: not yet read by any evaluation** |

**Why the splits are chronological** [Example]: suppose a model were tuned using 2022 data and
then "evaluated" on 2015. It would have been helped by information nobody had in 2015. In real
trading you never know the future, so evaluation must mimic that. The project therefore:

- never shuffles dates;
- fits every statistic (scalers, thresholds) on training data only;
- reads the test period only after a formal, recorded authorisation (decisions D-056, D-060,
  D-076, D-083).

Default code paths physically stop reading files at the test boundary.

---

## Stage 3 — Formulate the problem as a Markov Decision Process (MDP)

### 3.1 The five ingredients

An MDP is the standard mathematical frame for RL problems: (S, A, P, R, γ).

| Ingredient | General meaning | In this project [Verified] |
| --- | --- | --- |
| State *S* | What the agent sees | 51 numbers: 34 scaled market features, 9 regime indicators, 8 current portfolio weights (Stage 4) |
| Action *A* | What the agent decides | 8 numbers in [−1, 1], turned into target weights for the 7 ETFs plus cash (Stage 5) |
| Transition *P* | How the world moves on | The simulator executes the trade one session later, charges costs, and applies the actual market returns until the next decision |
| Reward *R* | Feedback | The logarithmic growth of portfolio value **after costs** between two decisions (Stage 6) |
| Discount γ | How much future rewards count | γ = 0.99 |

### 3.2 One decision cycle [Verified]

1. **Observe:** on the first trading day of each calendar week (ISO week), at the close, the
   agent receives the 51-number state.
2. **Act:** the PPO policy outputs 8 numbers, which are converted into target weights.
3. **Execute:** the trade happens at the **next** session's close (a one-session lag), and
   transaction costs are charged.
4. **Earn:** the portfolio earns the actual market returns, and its weights drift with prices
   until the next weekly decision.
5. **Feedback:** the reward is the log growth of value over the week; then the next state.

### 3.3 Episodes [Verified]

- **One episode = one whole data split.** A training episode starts in cash on 2007-07-05 (the
  first date with 126 sessions of history for every feature) and runs to 2016-12-30: **496
  weekly decisions**.
- Every episode starts the same way (no random start dates). It ends after the last decision
  that can still earn a return inside the split.
- The final evaluations run one deterministic episode per split.

### 3.4 The Markov property: an approximation

An MDP assumes that the current state contains what is needed to predict what happens next.
Real markets do not obey this exactly; the features are an *attempt* to summarise relevant
recent history. This is a modelling assumption, not a guarantee.

---

## Stage 4 — Define the state space (what the agent sees)

### 4.1 Why prices alone are not enough

A single price says little. The agent needs to know:
- whether prices have been rising or falling;
- how volatile the market is;
- whether stocks and bonds are moving together;
- what it currently holds.

### 4.2 The 34 causal features [Verified]

"Causal" means that a feature dated *t* uses only returns up to and including day *t*.

| Family (as recorded) | Count | Features |
| --- | --- | --- |
| Return / momentum | 14 | For each of the 7 ETFs: the latest daily return (`ret_1`) and the 63-session return (`mom_63`) |
| Volatility / risk | 11 | For each ETF: the 21-session volatility (`vol_21`); for the equity "market": 21- and 63-session volatility, 63-session downside volatility, 126-session drawdown |
| Universe context | 6 | Equity group and bond group: latest, 21- and 63-session returns |
| Cross-asset | 3 | Cross-sectional dispersion, average asset volatility, 63-session equity–bond correlation |

- **Scaling:** each feature is standardised using the mean and standard deviation of the
  **training** rows only, then clipped to ±10. The same frozen scaler is reused unchanged on
  validation and test data.
- **What is *not* in the implemented state** (contrary to some early design notes): trading
  volume, portfolio drawdown, recent P&L and turnover. The design notes considered them; the
  implemented observation is exactly 34 features + 9 regime indicators + 8 weights = **51
  numbers** (D-062).

### 4.3 Market regimes: describing "what kind of market this is" [Verified]

Each day gets one of nine labels, combining **trend** and **volatility** (D-045):

- **Trend**, from the 63-session equity momentum *m*:
  - *negative* if m < −b;
  - *neutral* if −b ≤ m ≤ b;
  - *positive* if m > b.

  The band b = 0.037974 is the one-third quantile of |m| on training rows.
- **Volatility**, from the 21-session market volatility *v*:
  - *low* below 0.008937 per session;
  - *normal* up to 0.013051;
  - *high* above that.

  These are the training-period terciles.
- **Labels:** 3 × 3 = **9 regimes** (e.g. `positive_low`, `negative_high`), plus
  `unavailable` for the warm-up days when there is not yet enough history.

**[Example]** If, on some day, the 63-session equity return is +6% (above the band of 3.8%) and
the 21-session volatility is 0.0095 (between 0.008937 and 0.013051), the label is
`positive_normal`.

**Provenance** (checked 2026-10-22, decision D-083):
- the thresholds were fitted on 2,455 training rows (2007-04-04 to 2016-12-30);
- their file hash is recorded;
- they have never been changed.

**Recorded caveat:** an early diagnostic report also counted labels in the test period. That
report is never opened or used.

**Important:** regimes are *descriptions*, not proven economic states. Because the thresholds
come from the training period (which includes 2008), most of 2017–2019 is labelled
"low volatility".

---

## Stage 5 — Define the action space (what the agent decides)

### 5.1 From buy/hold/sell to portfolio weights

A simple trading agent might say "buy" or "sell" one asset. A portfolio agent instead says
**how the whole portfolio should be split**. This agent outputs eight numbers between −1 and +1
(one per ETF, plus one for cash). The environment turns them into valid target weights.

### 5.2 The mapping, step by step [Verified: D-063, D-072]

1. **Scale:** multiply each number by 5, giving "logits" between −5 and +5.
2. **Softmax:** convert the 8 logits into 8 positive proportions that sum to 1:
   pᵢ = e^(logitᵢ) / Σ e^(logitⱼ).
3. **Cap:** no ETF may receive more than **40%** of the portfolio (target cap 0.40).
4. **Cash:** whatever is cut by the cap, plus the cash proportion, is held in cash.

The result is always **long-only** (no short selling), **unlevered** (weights sum to 1) and
**capped**.

**[Example, computed with the project's own functions]** The action
u = (0.6, 0.2, −0.4, 0.4, 0.0, −0.6, −0.2, 0.0) for (SPY, EFA, EEM, IEF, TLT, LQD, GLD, cash):

| | SPY | EFA | EEM | IEF | TLT | LQD | GLD | Cash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Logits (×5) | 3 | 1 | −2 | 2 | 0 | −3 | −1 | 0 |
| Softmax | 0.6134 | 0.0830 | 0.0041 | 0.2256 | 0.0305 | 0.0015 | 0.0112 | 0.0305 |
| After the 0.40 cap | **0.4000** | 0.0830 | 0.0041 | 0.2256 | 0.0305 | 0.0015 | 0.0112 | **0.2439** |

SPY wanted 61%, was capped at 40%, and the remaining 21% went to cash.

### 5.3 Why the cap matters

- **Holdings drift:** the 40% cap applies to *targets*. Between weekly trades, holdings drift
  with prices and may exceed 40% (in validation, up to 41.5%). No forced trade happens (D-057).
- **The cap shapes behaviour:** in validation, a median 87% of PPO executions had at least one
  ETF at the cap, and PPO held a lot of cash (median target cash 36%). The baselines hold no
  cash.

---

## Stage 6 — Design the reward and the portfolio accounting

### 6.1 Reward versus evaluation metric

- **The training reward** [Verified, D-064]: at each weekly step, the reward is
  `log(value at the next decision / value at this decision)`, **after** transaction costs.
  Summed over an episode, it equals the log of final value over initial value.

  It is "risk-neutral": it does not penalise volatility, drawdown or turnover beyond the actual
  costs paid.
- **The evaluation metric** [Verified, D-076]: the **net Sharpe ratio**, which does account for
  volatility.

  This mismatch (training on growth, judging on risk-adjusted growth) is a recorded limitation
  and a possible reason for the results (Stage 9).

### 6.2 Gross returns, costs and net returns [Verified, D-049]

- **Gross return:** what the holdings earned from market moves.
- **Transaction cost:** (10 + 5) = **15 basis points** (0.15%) of the **traded notional of the
  ETFs**, i.e. the sum of absolute weight changes across ETFs. The cash leg is not charged. The
  first purchase from cash (the "funding trade") is charged too. Both values are provisional
  placeholders, not calibrated estimates.
- **Net return:** `(1 + gross) × (1 − cost fraction) − 1`.

**[Example]** The portfolio is worth 100,000 and the weekly rebalance moves 30% of it between
ETFs. The cost is 0.15% × 30% = 0.045% of value, i.e. **45 dollars**. If the market return that
day is +1%, the net return is (1.01 × 0.99955) − 1 = **+0.9545%**.

**[Example] Why turnover matters:** trading about 39% of the portfolio every week (roughly what
the PPO policies did) is 0.39 × 52 ≈ **20 portfolios per year**. At 0.15% per unit traded, that
is about **3% of value lost to costs every year**, before any gain or loss from markets.

### 6.3 Execution timing: no peeking at the future [Verified, D-055]

- The decision is made at the close of day *d*, using information up to *d*.
- The trade executes at the close of day *d + 1* (a lag of one session).
- The first return earned by the new portfolio is that of day *d + 2*.

**[Example]** A decision on Monday's close is executed at Tuesday's close and starts earning on
Wednesday. The agent can never profit from price moves that happened before its trade could
have been made.

### 6.4 Risk metrics used in evaluation [Verified]

| Metric | Meaning |
| --- | --- |
| **Net Sharpe ratio** | √252 × mean / standard deviation of daily net returns (risk-free rate 0; sample standard deviation; the funding day excluded). Return per unit of volatility, annualised. [Example] 8% a year with 5% volatility gives about 1.6 |
| Cumulative and annualised return (CAGR) | Total and per-year growth |
| Annualised volatility | How much daily returns swing, scaled to a year |
| **Maximum drawdown** | The largest fall from a previous peak, from the starting capital |
| Cost drag | Gross minus net cumulative return: what costs took away |
| **Annualised turnover** | Recurring ETF traded notional per year (the funding trade and the cash leg excluded). 1.0 means trading the whole portfolio once a year |
| Concentration | How concentrated the risky holdings are (Herfindahl index; Stage 10) |

---

## Stage 7 — Implement the environment and the training pipeline

### 7.1 Software building blocks [Verified]

| Component | What it does | Where |
| --- | --- | --- |
| Data pipeline | Download, validate and store prices and returns, with content hashes | `src/adaptive_portfolio/data/` |
| Features and regimes | 34 causal features; regime labels with frozen training thresholds | `features/`, `regimes/` |
| Simulator | One accounting engine for timing, costs, cash, caps and drift; used by baselines and RL alike | `evaluation/simulator.py` |
| Gymnasium environment | Wraps the simulator for RL: `reset`, `step`, observation, reward | `environment/portfolio_env.py` |
| PPO wrapper and grid runner | Trains runs with pinned settings; records everything | `agents/ppo.py`, `agents/grid.py` |
| Run safety | Never overwrites results; requires committed code; locks; quarantine | `agents/run_safety.py` |

**Key design choice:** the RL environment and the benchmark backtest use **the same
simulator**. Tests check that the environment's ledger equals the simulator's ledger *exactly*.
Any difference between PPO and the benchmarks therefore comes from the decisions, not from
different bookkeeping.

### 7.2 Reproducibility [Verified]

Every training run records:
- its configuration, random seed and code commit;
- the package versions;
- the dataset and feature-set identifiers, and a hash of the exact training rows read;
- the frozen scaler and a hash of the saved model.

Runs from uncommitted code are refused. Outputs are written once and never overwritten.

---

## Stage 8 — Train PPO and compare configurations

### 8.1 What PPO is, in plain words

**Proximal Policy Optimization** (Schulman et al., 2017) is a popular policy-gradient RL
algorithm.
- The agent tries its current policy for a while and collects experience.
- It then nudges the policy towards actions that turned out better than expected.
- It *clips* each update, so the policy cannot change too much at once.

The clipping makes training more stable; it does not guarantee a good or profitable policy.

During training, PPO *samples* actions with random noise, to explore. For evaluation, the
project uses the policy's **average (deterministic) action** (D-076).

### 8.2 The training grid: EXP-005 [Verified]

| Item | Value |
| --- | --- |
| Library | Stable-Baselines3 2.9 (CPU) |
| Network | Separate policy and value networks, 2 layers × 64 units, tanh |
| Grid (8 configurations) | Learning rate {0.0003, 0.0001} × rollout length `n_steps` {512, 1024} × entropy bonus {0, 0.01} |
| Fixed settings | Batch 64, 10 epochs per update, γ 0.99, GAE λ 0.95, clip 0.2 |
| Seeds | 42, 43, 44, 45, 46 for each configuration |
| Budget | 100,000 timesteps configured. The library rounds up to whole rollouts, so **100,352** were done, about **202 episodes** |
| Runs | **40 of 40 completed**, one at a time on one torch thread: median training time 79 s per run; 3,470 s (about 58 minutes) of total process time |
| Data | Training split only, ending 2016-12-30 |
| Code | Commit `cc9784b` (clean) |

**Why five seeds?** RL results vary strongly with random initialisation. Judging a setting by
one lucky run would be misleading, so each configuration is summarised by the **median** over
five seeds.

---

## Stage 9 — Baselines and the validation evaluation

### 9.1 The three benchmark strategies [Verified, D-053]

| Baseline | Rule |
| --- | --- |
| Equal weight, monthly | 1/7 in each ETF; rebalanced back to 1/7 on the first trading day of each month |
| Equal weight, buy and hold | 1/7 in each ETF at the start, then never traded |
| Inverse volatility, monthly | Each ETF weighted by 1 / (its 63-session volatility), capped at 40%; rebalanced monthly |

They are deliberately **untuned** and simple: if a complex RL agent cannot beat them, its extra
complexity is not justified. They use exactly the same simulator, costs, timing and dates as
PPO.

### 9.2 How the PPO configuration was chosen [Verified, D-066, D-076]

- **The rule was fixed and accepted *before* any validation data were used:** pick the
  configuration with the highest **median validation net Sharpe** across its five seeds.
  Ties go to the lower learning rate, then the smaller `n_steps`, then the lower entropy bonus.
- **The run (EXP-006, evaluation `1ce9c490ed03c8c9`, protocol hash `e652adec1095c95a`):** one
  run over 2017-01-03 to 2019-12-31 (753 trading days), 156 weekly trades per policy.

### 9.3 Results (validation 2017–2019, net of costs) [Verified]

**Median net Sharpe by configuration:**

| Configuration | Learning rate | n_steps | Entropy | Median | Range over seeds |
| --- | --- | --- | --- | --- | --- |
| 0 | 3e-4 | 512 | 0 | 0.462 | −0.063 to 0.626 |
| 1 | 3e-4 | 512 | 0.01 | 0.356 | −0.006 to 1.227 |
| 2 | 3e-4 | 1024 | 0 | 0.338 | 0.111 to 0.678 |
| 3 | 3e-4 | 1024 | 0.01 | 0.269 | 0.091 to 0.604 |
| **4** | **1e-4** | **512** | **0** | **0.635** | **0.253 to 1.149** |
| 5 | 1e-4 | 512 | 0.01 | 0.498 | 0.228 to 1.094 |
| 6 | 1e-4 | 1024 | 0 | 0.446 | 0.019 to 0.926 |
| 7 | 1e-4 | 1024 | 0.01 | 0.484 | 0.034 to 0.975 |

**Configuration 4 was selected** (median 0.6351).

**Compared with the baselines on the same dates:**

| Strategy | Net Sharpe | Net cum. return | Net volatility | Net max drawdown | Gross cum. return | Cost drag | Turnover per year |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Equal weight, monthly | 1.470 | 28.81% | 5.93% | −10.42% | 29.13% | 0.32 pp | 0.22 |
| Equal weight, buy and hold | 1.355 | 27.96% | 6.28% | −11.49% | 28.15% | 0.19 pp | 0.00 |
| Inverse volatility, monthly | **1.754** | 26.37% | **4.56%** | **−7.58%** | 27.01% | 0.63 pp | 0.78 |
| PPO configuration 4, seed 42 | 1.149 | 21.14% | 5.76% | −8.62% | 28.68% | 7.54 pp | 13.34 |
| PPO configuration 4, seed 43 | 0.486 | 9.90% | 7.07% | −10.71% | 19.54% | 9.65 pp | 18.61 |
| PPO configuration 4, seed 44 | 0.635 | 10.60% | 5.61% | −11.05% | 21.52% | 10.92 pp | 20.85 |
| PPO configuration 4, seed 45 | 0.253 | 3.57% | 5.28% | −6.99% | 10.74% | 7.18 pp | 14.82 |
| PPO configuration 4, seed 46 | 0.731 | 12.24% | 5.55% | −9.24% | 20.64% | 8.40 pp | 15.89 |

### 9.4 What these numbers say [Verified]

1. **No PPO policy, out of all 40, reached the net Sharpe of any baseline.** The best single
   policy scored 1.227; the weakest baseline scored 1.355.
2. **Configuration 4 was selected because it was the best PPO setting, not because it beat
   anything.** It is a *research candidate*, not a demonstrated strategy.
3. **The PPO policies traded heavily:** 13–28× the portfolio per year, against at most 0.78×
   for the baselines, losing 7–15 percentage points to costs over three years.
4. **Costs are not the whole story:** even *before* costs, only 5 of 40 policies earned more
   than the weakest baseline's gross return (27.0%).

### 9.5 The follow-up diagnostic (from saved results only) [Verified, with hypotheses labelled]

- **What drives the trading:** 99.3–99.9% of PPO trading came from the policy **changing its
  target**, not from routine rebalancing back to a target after prices drift.
- **Training fit versus validation:** settings that fitted the training years best (the higher
  learning rate) did *worse* on validation. Across the 40 runs, the correlation between
  training fit and validation Sharpe is −0.25.
- **Exploration noise:** the noise in the trained policies was still large at the end of
  training.
- **Possible explanations (hypotheses, not tested):**
  - overfitting to the single training history;
  - a reward that does not discourage trading enough in-sample;
  - a difference between noisy training behaviour and deterministic evaluation.

  Proposed follow-ups are recorded as D-077 and D-078. **None is approved or run.**

### 9.6 What the benchmarks look like across regimes: EXP-008 [Verified]

Run on the **training** years and for the **baselines only** (it says nothing about PPO).
- **Volatility:** every baseline's volatility was highest in the `negative_high` regime
  (annualised 0.140 buy and hold, 0.183 equal weight monthly, 0.104 inverse volatility, against
  0.091, 0.109 and 0.071 over all sessions). This is partly mechanical, because that label is
  itself defined by high volatility.
- **Allocation:** inverse volatility held less SPY in `negative_high` (0.089) than in
  `negative_low` (0.121), with IEF at 0.279 and TLT at 0.144 in `negative_high`. This follows
  directly from its own rule.
- **Drawdown:** each baseline's deepest drawdown level fell on `negative_high` days. Drawdown
  levels are path-dependent: a level reached while a label holds is not a loss *caused* by that
  regime.
- **Sample size:** some regimes have few days (e.g. `negative_low`: 38 sessions), so these are
  descriptions, not statistical evidence.

---

## Stage 10 — Rigorous evaluation and risk safeguards (the "Gate 3" work)

The final test on 2020–2024 can be run **once**. To stop anyone, consciously or not, adjusting
the method after seeing results, every choice is fixed in advance in a **pre-registration**
(`configs/preregistration.yaml`) and approved step by step (decision D-083).

### 10.1 What has been decided (D-083) [Verified as recorded decisions]

- **The candidate:** configuration 4, seeds 42–46, with each model file identified by its
  cryptographic hash.
- **The primary measure:** the **median of the five seeds' net Sharpe ratios** on the test
  period.
- **The primary comparison:** that median minus the **inverse-volatility** baseline's net
  Sharpe (the strongest validation baseline). The two equal-weight baselines get **descriptive
  differences only** (no statistical interval).
- **No success threshold:** the result is reported as an **effect size with an uncertainty
  interval**, whatever it is.
- **Secondary measures:** returns, volatility, drawdowns with dates, costs, turnover, trade
  counts, allocation, cash and concentration, and regime summaries (at least 63 days per
  regime).
- **Cost sensitivity:** 0, 15 and 30 basis points.
- **Excluded from this protocol:** lag and cap sensitivities, Sortino ratio, walk-forward
  evaluation. No embargo period is applied.

### 10.2 Moving-block bootstrap: how uncertain is the difference? [Verified as implemented on synthetic data; Not done on real data]

A single number such as "median Sharpe minus baseline Sharpe" could be luck. The bootstrap
estimates how much it would vary:
1. Cut the daily return history into blocks of **21 consecutive trading days** (about a month).
   Keeping days together preserves short-term patterns.
2. Build a new history of the same length by picking blocks at random, *without wrapping
   around the end*.
3. On that resampled history, recompute every Sharpe ratio and the difference. Every strategy
   uses **the same resampled dates** ("paired").
4. Repeat **10,000 times** (random seed 20261021). The middle 95% of the differences forms the
   **95% percentile interval**.

**Not reported:** p-values or "significance". The five seeds share one market history; they are
*not* five independent samples.

**Status:**
- the code passes hand-calculated and synthetic tests;
- a second, independently structured implementation agrees with it;
- **both were written by the same author, so an independent human review is still required.**

The item stays OPEN.

### 10.3 Stress windows [Verified sources; Not done on data]

| Window | From (market peak close) | To (market low close) | Trading days in (peak, low] |
| --- | --- | --- | --- |
| COVID crash | 2020-02-19 | 2020-03-23 | 23 |
| 2022 bear market | 2022-01-03 | 2022-10-12 | 195 |

- **Why these windows:** they are the two S&P 500 declines of 20% or more (closing basis) in
  2020–2024, chosen from **public market history, not from any strategy result**.
- **Sources:** Wikipedia's S&P 500 closing milestones; CNBC's report citing S&P Dow Jones
  Indices; the official NYSE holiday calendars (Intercontinental Exchange). There is no
  official bear-market definition; the 20% closing-basis convention is used.
- **Day counts:** match the exchange calendar but can only be checked against the dataset when
  the test is run. A mismatch will be reported as "not computed"; the dates will never be
  moved. The item stays OPEN.
- **Interpretation:** these are descriptive slices of one history, not independent tests.

### 10.4 Fixed-action cost sensitivity [Verified on synthetic data]

- The trades decided in the main run are **replayed** at 0, 15 and 30 basis points.
- The 15 bps replay must equal the main run exactly.
- This shows how cost assumptions change the outcome **of the same decisions**. It does *not*
  show how a policy trained or adapting under different costs would behave.

### 10.5 The separate test evaluator and its guards [Verified on synthetic data]

`scripts/evaluate_test.py` is deliberately independent of the validation evaluator, which is
untouched and keeps its hash. It refuses to run unless **all** of these hold:
- the pre-registration is **frozen**, with no open item;
- the pre-registration's SHA-256 hash equals the one named in a written authorisation;
- the code is **committed and clean**, at the exact 40-character commit named in that
  authorisation;
- the candidate equals the validation selection, and every model hash matches;
- no earlier test evaluation exists for this pre-registration (**one run only**).

It also refuses data after the test end date, never selects or tunes, writes nothing if the
main measure is undefined, and has a `--verify` mode that recomputes every reported number
independently. Its `--plan` mode reads no data at all.

### 10.6 Software checks [Verified, 2026-10-22]

- **964 automated tests** pass (52 of them need the RL extra).
- A fresh environment reproducing the CI setup (Python 3.12, without the RL and plotting
  extras) also passes: 910 tests, 9 skipped.
- Lint, formatting and configuration validation pass.
- Integrity checks pass 16/16; the EXP-006 output fingerprint is `2d69c405a8e5a764`.
- Everything is committed and pushed as `26a2abd` on `main`.

---

## Stage 11 — Explainability and product integration

### 11.1 What explainability means here

- **Not a goal:** proving *why* markets moved.
- **The goal:** describing **which inputs the policy's decisions are sensitive to**, and **how
  its allocations differ across market regimes** (D-068).
- **Method, permutation sensitivity:** shuffle one group of inputs (say, the regime
  indicators) across many decision dates. Then measure how much the policy's chosen weights
  change. A big change means the decisions are *sensitive* to that group.
- **What it is not:** a measure of how much that group *contributes to returns*, or a causal
  effect.

### 11.2 Status

| Item | Status |
| --- | --- |
| Regime analysis and sensitivity tools | [Verified] built and tested; checks that saved decisions are reproduced exactly before anything is computed |
| Regime analysis of the baselines (training years, EXP-008) | [Verified] done (Stage 9.6) |
| **Explainability of the PPO policy on validation decisions** | **[Not done]** plan written (`docs/explainability_validation_plan.md`); needs review and an explicit authorisation |
| Regime-input ablation (retrain PPO without regime inputs) | **[Not done]** planned only (D-081); needs a training authorisation |
| Training-period diagnostic (D-078 / EXP-007) | **[Not done]** proposed only |

### 11.3 Workflow and dashboard [Verified]

- **Workflow:** `python scripts/workflow.py` shows a read-only status by default. It can verify
  all artifacts and checkpoints, run the permitted analyses and build a dashboard. It never
  trains, evaluates or touches test data.
- **Dashboard:** a single HTML page built only from hash-verified saved results. Every number
  traces to a source file. Anything missing or unauthorised is shown as "Not available", with
  the reason.
- **Caveat:** the dashboard was last built before the latest Gate 3 changes, so its Gate 3
  section shows an older draft until it is rebuilt.

---

## Stage 12 — Final evaluation and presentation: where things stand

### 12.1 Completed [Verified]

- **Data, features and regimes:** the data pipeline, features, regimes, simulator and
  baselines; the RL environment and PPO pipeline.
- **Training and validation:**
  - 40 PPO runs (EXP-005);
  - the validation evaluation and selection (EXP-006);
  - the turnover and cost diagnostic;
  - the baseline regime analysis (EXP-008).
- **Tools:** the analysis, workflow and dashboard tools; the guarded test evaluator.
- **Records:** the Gate 3 decisions (D-083); all documentation; committed and pushed
  (`26a2abd`).

### 12.2 Remaining, in order [Not done]

1. **Independent human review** of the bootstrap (G3-5).
2. A team decision on how the stress-window day counts are verified (G3-6).
3. **Team review** of the test evaluator, then a commit instruction with stated authorship.
4. **Freeze** the pre-registration, commit it, and run the evaluator's plan mode to record the
   final hashes and evaluation identifier.
5. A **separate, explicit authorisation to unseal** the test period, naming the commit, the
   hashes, the evaluation id, the dataset, the model hashes and the exact command. Then the
   **single** test run, independently verified and reported whatever the outcome.
6. Optional, each needing its own approval:
   - PPO explainability on validation decisions;
   - the D-077 and D-078 follow-ups;
   - the regime-input ablation.

### 12.3 Messages for the mid-term presentation

- **Do say:**
  - we built a leak-free, reproducible RL research pipeline;
  - PPO trained successfully;
  - on validation, the selected PPO configuration **underperformed** simple benchmarks,
    largely through excessive trading;
  - a strict, pre-registered final test is prepared but not yet run.
- **Do not say:**
  - that PPO outperforms;
  - anything about 2020–2024 performance;
  - that explanations of the policy exist.

---

## Glossary (short)

| Term | Meaning |
| --- | --- |
| **Basis point (bp)** | 0.01%. 15 bp = 0.15% |
| **Bootstrap** | Re-sampling the data many times to estimate how much a result could vary |
| **Causal feature** | A feature that uses only information available at the time it is dated |
| **CAGR** | Compound annual growth rate |
| **Cost drag** | Gross minus net return: what transaction costs took |
| **Deterministic policy evaluation** | Using the policy's average action, without random noise |
| **Drawdown** | A fall from a previous peak value; *maximum* drawdown is the largest such fall |
| **Episode** | One complete run of the agent through a data split |
| **ETF** | Exchange-traded fund: a fund traded like a stock, holding a basket of assets |
| **Herfindahl index (HHI)** | The sum of squared weights; 1 = one asset, 1/7 = equal across seven |
| **Look-ahead bias** | Accidentally using future information in a past decision |
| **MDP** | Markov decision process: state, action, transition, reward, discount |
| **Policy** | The agent's decision rule: state → action |
| **PPO** | Proximal Policy Optimization, the RL algorithm used |
| **Pre-registration** | Writing down and freezing the analysis plan before seeing the data it is tested on |
| **Regime** | A label for market conditions (trend × volatility) |
| **Seed** | A number that fixes random choices so that runs can be reproduced |
| **Sharpe ratio** | Return per unit of volatility, annualised |
| **Turnover** | How much of the portfolio is traded |
| **Validation / test split** | Data held out from training: validation to choose, test for the single final check |

A longer glossary is in `docs/glossary.md`.

---

## Appendix A. Corrections to earlier informal summaries

Earlier informal summaries (not repository records) contained these inaccuracies:

| Earlier statement | Correct, per the repository |
| --- | --- |
| Features include trading volume | **No volume feature.** The four families are return/momentum, volatility/risk, universe context and cross-asset |
| The state includes drawdown, portfolio volatility, recent P&L and turnover | **No.** The state is 34 market features + 9 regime indicators + 8 portfolio weights (51 numbers). Those items were early design ideas, not implemented |
| "100,352 timesteps per run" as the configured budget | The **configured** budget is 100,000. The library completed **100,352** (whole rollouts), about 202 episodes |
| The reward formula is unknown | The reward is the **log growth of portfolio value after costs** between weekly decisions (D-064), with γ = 0.99 |
| The action mapping is unknown | Actions in [−1, 1] → ×5 → softmax over 7 ETFs + cash → each ETF capped at 0.40 → the excess to cash (D-063, D-072) |
| Commit and push still outstanding | **Done:** `26a2abd` pushed to `origin/main` on 2026-10-22 |
| Decisions are daily | **Weekly** (first session of each ISO week), executed one session later |

## Appendix B. Where to find things

| Need | File |
| --- | --- |
| All decisions and their status | `docs/decision_log.md` |
| All experiments with numbers | `docs/experiment_log.md` |
| Approvals and Gate 3 status | `docs/approval_checklist.md` |
| Commands, interfaces and conventions | `docs/technical_handbook.md` |
| Draft academic report | `docs/final_report.md` |
| Turnover and cost diagnostic | `docs/exp006_turnover_diagnostic.md` |
| Explainability notes and plan | `docs/explainability.md`, `docs/explainability_validation_plan.md` |
| Test pre-registration (draft) | `configs/preregistration.yaml` |
| Session-by-session history, including AI assistance | `docs/project_journal.md` |

## Appendix C. AI-use disclosure

- **Abstract:** ChatGPT (OpenAI) helped with language refinement and LaTeX preparation of the
  submitted abstract.
- **Repository:** Claude Code (Anthropic) wrote a substantial part of the code, tests and
  documentation at the team's direction, ran the recorded checks and experiments, and drafted
  this walkthrough. The journal records this session by session.
- **The student team** directs the work, makes the research decisions and is responsible for
  reviewing, verifying and interpreting every result.
