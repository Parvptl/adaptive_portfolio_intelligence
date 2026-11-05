# Adaptive Portfolio Intelligence: Explainable Reinforcement Learning for Regime-Aware Portfolio Allocation and Risk Management

**Parv Patel (142301041), Mandar Patil (112401021)** · Research report, **final version prepared
2026-11-05** (supersedes the draft of 2026-10-21, kept in Git history)

> **Status:** every number below is taken from a saved, verified artifact named in §12.
> - **Prepared for the team's review before submission.** The team reviews and verifies the
>   report (roadmap D6); this file does not record that review.
> - **Periods:** development, selection and experiments E0–E12 used training (2007–2016) and
>   validation (2017–2019) data only. The test period (2020–2024) was evaluated **once**, on
>   2026-11-05, under a frozen pre-registration (§9). Validation and test results are reported
>   separately and must not be mixed.
> - **Research and decision support only. Simulated backtests; not financial advice.**

## Abstract

We formulated allocation across seven ETFs as a sequential decision problem with transaction
costs and long-only, capped weights, and trained Proximal Policy Optimisation (PPO) agents on
2007–2016 daily data. Of 40 trained policies, configuration 4 was selected on 2017–2019
validation data; no policy reached the validation net Sharpe of any of three simple baselines.
Twelve prespecified follow-up experiments (E0–E12, training and validation only) studied investor
profiles, risk-aware rewards, a turnover penalty, walk-forward validation, the training budget and
the regime inputs. A turnover penalty reliably reduced trading costs and raised validation net
Sharpe in three walk-forward folds, but every PPO arm stayed below the baselines. On the sealed
2020–2024 test period, evaluated once, the selected policy's median net Sharpe was −0.068 against
0.253 for inverse volatility (difference −0.322; 95% moving-block bootstrap interval −0.818 to
0.192); every seed was below every baseline, even with zero trading costs. Explainability
analyses show decisions driven mainly by momentum inputs, little use of current holdings or regime
labels, and allocations that vary with market regime but not in a risk-reducing direction. In this
setting PPO did not improve on simple, untuned allocation rules.

## 1. Motivation and research question

Portfolio allocation is a sequential decision problem under uncertainty, transaction costs and
changing market conditions. Fixed allocation rules do not adapt to these conditions; a learned
policy might.

**Research question (from the submitted abstract):** can a reinforcement-learning policy,
specifically PPO [1] as a candidate algorithm, allocate across a small ETF universe in a way that
responds to market conditions (rising, falling and high-volatility periods)? How does it compare
with conventional allocation benchmarks, after transaction costs, on cumulative return, Sharpe
ratio, maximum drawdown and turnover, and on risk control, adaptability and interpretability?

**No performance improvement was assumed in advance.**

## 2. Related work and references

- **PPO** [1] is a clipped policy-gradient actor–critic method. **Reinforcement learning
  foundations:** [2]. **Direct reinforcement for trading:** [3].
- **Naive diversification:** equal weighting (1/N) is a demanding benchmark for optimised
  portfolios [6], which motivates the untuned conventional baselines used here.
- **Software:** Stable-Baselines3 [4] and Gymnasium [5].
- **Bootstrap:** the test uses the moving-block bootstrap [8]; the stationary bootstrap [7] was
  considered and not chosen (D-083).

*References [1]–[3] are those of the submitted abstract. [4]–[8] were checked against the
publishers' or indexers' records on 2026-11-05 (JMLR, arXiv, Oxford University Press / RePEc,
JSTOR, Project Euclid).*

1. J. Schulman, F. Wolski, P. Dhariwal, A. Radford, O. Klimov, "Proximal Policy Optimization
   Algorithms," arXiv:1707.06347, 2017.
2. R. S. Sutton, A. G. Barto, *Reinforcement Learning: An Introduction*, 2nd ed., MIT Press,
   2018.
3. J. Moody, M. Saffell, "Learning to trade via direct reinforcement," *IEEE Transactions on
   Neural Networks*, 12(4), 875–889, 2001.
4. A. Raffin, A. Hill, A. Gleave, A. Kanervisto, M. Ernestus, N. Dormann,
   "Stable-Baselines3: Reliable Reinforcement Learning Implementations," *Journal of Machine
   Learning Research*, 22(268), 1–8, 2021.
5. M. Towers et al., "Gymnasium: A Standard Interface for Reinforcement Learning
   Environments," arXiv:2407.17032, 2024.
6. V. DeMiguel, L. Garlappi, R. Uppal, "Optimal Versus Naive Diversification: How Inefficient
   is the 1/N Portfolio Strategy?" *Review of Financial Studies*, 22(5), 1915–1953, 2009.
7. D. N. Politis, J. P. Romano, "The Stationary Bootstrap," *Journal of the American
   Statistical Association*, 89(428), 1303–1313, 1994.
8. H. R. Künsch, "The Jackknife and the Bootstrap for General Stationary Observations," *The
   Annals of Statistics*, 17(3), 1217–1241, 1989.

## 3. Data, features, regimes and splits

**Data:** seven ETFs (SPY, EFA, EEM, IEF, TLT, LQD, GLD); daily adjusted prices from yfinance
(live retrieval, 2026-10-15), 2007–2024; raw dataset `e27437b97742fa43`, processed dataset
`8e00568ee2aa4de7`; simple returns.

**Known data limitations:** the universe was chosen with hindsight (survivorship and selection
bias, D-034); adjusted prices depend on the provider's method; the calendar is the observed one.

**Features:** 34 causal features (feature set `a79347e37e653703`) in four families: return and
momentum, volatility and risk, cross-asset, and universe context. A row dated *t* uses returns up
to *t* (D-043). Standardisation is fitted on training rows only and clipped at ±10 (D-062).

**Regimes** (D-045, provisional): trend from 63-session equity momentum with a neutral band
(*b* = 0.037974, the training 1/3 quantile of |*m*|) × volatility from 21-session market
volatility at the training terciles (0.008937 and 0.013051 per session); nine labels plus
`unavailable`. Thresholds are fitted on training rows only and frozen; they are descriptions,
not verified market states.

**Splits** (D-009): train 2007–2016, validation 2017–2019, test 2020–2024. The test period was
read only by the single pre-registered run (§9); development code never parses test-period values
(D-060). E10–E12 used three expanding walk-forward folds **inside** 2007–2019 (validation
2011–13, 2014–16 and 2017–19; D-094).

## 4. Portfolio environment, costs and constraints

- **Timing:** decide at the close of *d*, execute at the close of *d* + 1 (lag 1, D-055). PPO
  decides weekly, on the first session of each ISO week (D-065). An episode is one split's window,
  starting from cash.
- **Actions:** 8 values in [−1, 1], scaled ×5 to logits (D-072), softmax over 7 ETFs and cash;
  each ETF target is capped at 0.40, the excess going to cash (D-063, D-057). Long-only,
  unlevered.
- **Observation (51 inputs):** 34 scaled features, a 9-way regime one-hot and the 8 current
  weights (D-062).
- **Reward:** decision-aligned log growth of portfolio value **after costs** (D-064). E4–E12
  varied this reward in prespecified experiments (§7); the selected test candidate uses D-064.
- **Costs (Requirement 7):** (10 + 5) bps × traded notional of ETFs (cash leg excluded),
  including the initial funding trade, deducted from the net return by one shared simulator for
  PPO and baselines alike (D-007, D-049; provisional rates). Cash earns 0.
- **Constraints enforced in code:** long-only, no leverage, the 0.40 ETF target cap and implicit
  cash. Holdings may drift above the cap between rebalances (D-057). No turnover cap (D-031).

## 5. Agents, baselines and protocol

**PPO** (Stable-Baselines3 2.9; D-066, D-074): separate 64×64 tanh policy and value networks;
`batch_size` 64; a grid of learning rate {3e-4, 1e-4} × `n_steps` {512, 1024} × entropy
coefficient {0, 0.01}; seeds 42–46; 100,000 timesteps each; 40 runs on the training split
(EXP-005, commit `cc9784b`).

**Baselines** (D-053, untuned): equal weight monthly, equal-weight buy-and-hold, and inverse
volatility (63 sessions) monthly, under the same simulator, costs, timing and windows.

**Selection** (D-076, accepted before evaluation): deterministic actions; the configuration with
the highest median validation net Sharpe over seeds 42–46; annualised Sharpe = √252·mean/std
(ddof 1), rf 0, funding row excluded.

## 6. Training and validation results of the original grid

### 6.1 Baselines (EXP-002, net of costs)

| Split | Strategy | Net Sharpe | Net cumulative return | Net max drawdown | Annualised traded notional |
| --- | --- | --- | --- | --- | --- |
| train | Equal weight monthly | 0.516 | 61.06% | −28.51% | 0.37 |
| train | Equal-weight buy and hold | 0.534 | 52.49% | −24.44% | 0.00 |
| train | Inverse volatility monthly | 0.843 | 71.55% | −18.64% | 0.84 |
| validation | Equal weight monthly | 1.470 | 28.81% | −10.42% | 0.22 |
| validation | Equal-weight buy and hold | 1.355 | 27.96% | −11.49% | 0.00 |
| validation | Inverse volatility monthly | 1.754 | 26.37% | −7.58% | 0.78 |

### 6.2 Validation evaluation and selection (EXP-006)

- **Run:** evaluation `1ce9c490ed03c8c9`, protocol hash `e652adec1095c95a`, commit `0f8341b`.
- **Selection:** configuration 4 (learning rate 1e-4, `n_steps` 512, entropy 0), median
  validation net Sharpe 0.635; next best configuration 5 at 0.498.

  | Seed | Net Sharpe | Net cumulative return | Cost drag | Annualised traded notional |
  | --- | --- | --- | --- | --- |
  | 42 | 1.149 | 21.14% | 7.54 pp | 13.34 |
  | 43 | 0.486 | 9.90% | 9.65 pp | 18.61 |
  | 44 | 0.635 | 10.60% | 10.92 pp | 20.85 |
  | 45 | 0.253 | 3.57% | 7.18 pp | 14.82 |
  | 46 | 0.731 | 12.24% | 8.40 pp | 15.89 |

- **Across all 40 policies:** net Sharpe −0.063 to 1.227; **no policy reached the net Sharpe of
  any baseline** (1.355 to 1.754); gross cumulative return 6.77% to 40.82%.
- With 40 policies on one window, the selected configuration's validation figures were expected
  to be optimistic (confirmed in §9).

### 6.3 Turnover and cost diagnostic (descriptive)

The policies traded 13.3–27.9× the portfolio per year against at most 0.78× for the baselines;
cost drag was 7.0–15.0 percentage points per policy. The higher learning rate fitted the training
episodes far better but had lower validation net Sharpe (`docs/exp006_turnover_diagnostic.md`).

### 6.4 Regime-conditioned behaviour of the baselines (EXP-008, training split)

2,390 sessions in 369 regime episodes; realised volatility highest in `negative_high` for all
three baselines (partly mechanical); each baseline's deepest training drawdown falls on
`negative_high` rows. Descriptive associations only.

## 7. Follow-up experiments E0–E12 (training and validation only)

Each experiment was prespecified (hypotheses and a mechanical outcome rule committed before
training), run with seeds 42–46 unless stated, and recorded in `docs/experiment_log.md`. Design
choices are Provisional (delegated) under D-084, not team-reviewed. **No result in this section is
a test result.**

| Experiment | Records | Question | Outcome and verified headline |
| --- | --- | --- | --- |
| E0–E3 | EXP-009/010; D-085–D-087 | 5-dimensional investor profile appended to the observation | Allocations barely move with the profile (D_w ≈ 0.01, about 10× below seed differences); the reward ignores the profile, so personalisation cannot be shown |
| E4 | EXP-011/012; D-088 | Profile-dependent risk-aversion reward | No meaningful personalisation (D_w median 0.0109 vs seed variation 0.118) |
| E5 | EXP-013/014; D-089 | Fixed risk aversion λ = 0 vs 9 | Outcome B: large in-sample risk reduction; on validation volatility −0.52 pp, 0 of 5 seeds higher |
| E6 | EXP-015/016; D-090 | λ = 0 / 3 / 9 dose response | Outcome B: monotone in-sample, weak out of sample |
| E7 | EXP-017/018; D-091 | Turnover penalty κ = 0 / 0.0015 / 0.0075 | Outcome A: validation turnover 17.5 → 15.3 / 2.6 a year; median net Sharpe 0.512 → 0.788 / 0.691, through saved costs |
| E8 | EXP-019/020; D-092 | κ = 0 / 0.0015 / 0.003 / 0.0045 | Outcome C: higher κ concentrates (risky-sleeve HHI 0.47 → 0.87) and moves to cash; κ = 0.0015 remains the balanced setting |
| E9 | EXP-021/022; D-093 | κ = 0.0015 vs 0 on new seeds 47–56 | Partial confirmation: ΔSharpe +0.247 (8 of 10 seeds; bootstrap 95% CI 0.091–0.422; exact p = 0.021) |
| E10 | EXP-023/024; D-094 | Walk-forward: κ = 0.0015 vs 0 in three folds | Walk-forward confirmation: ΔSharpe +0.082 / +0.221 / +0.232 (14 of 15 pairs); both arms lose money in 2011–2016 |
| E11 | EXP-025/026; D-095 | Half training budget (50,176 vs 100,352 timesteps) | No reliable improvement: validation ΔSharpe +0.107 / +0.055 / −0.088; training fit falls in every fold |
| E12 | EXP-027/028; D-096 | Remove the 9 regime one-hot inputs | No reliable improvement: validation ΔSharpe −0.111 / −0.245 / +0.180, every fold mixed |

**What E0–E12 show:**
- **Costs are the lever that works.** A modest turnover penalty cut trading and cost drag and
  raised validation net Sharpe consistently across three historical periods (E7, E9, E10), mostly
  by saving costs rather than by better allocation.
- **PPO overfits a single training path.** Training fit is far above validation fit; halving the
  training budget reduced the in-sample fit without improving validation (E11).
- **Profiles and regime labels do not change much.** The profile-conditioned and
  profile-reward policies did not personalise (E0–E4); removing the regime inputs did not
  reliably change performance (E12).
- **No PPO arm reached the simple baselines** in any experiment, fold or period (for example
  E10 fold C: E10T1 mean 0.662 against inverse volatility 1.754).
- **Not established:** any out-of-sample benefit of the turnover penalty. The penalty arms were
  not test arms (§9), so the test says nothing about them.

## 8. Explainability (Requirement 9)

### 8.1 Decision sensitivity and regime behaviour of configuration 4 on validation (EXP-029)

Authorised as D-097 and run **before** the test (policy §7 condition 1); output
`86b75ffd1d00783e`; the rebuilt decisions reproduce the evaluated ones within 1.1e-16; the tables
reproduce byte-for-byte. Full report: `docs/ppo_explainability_results.md`.

| Input group (inputs) | Median L1 change of decided targets (range over seeds) |
| --- | --- |
| Return and momentum (14) | **0.433** (0.373–0.559) |
| Universe context (6) | 0.314 (0.181–0.338) |
| Volatility and risk (11) | 0.212 (0.125–0.353) |
| Cross-asset (3) | 0.150 (0.085–0.312) |
| Regime one-hot (9) | 0.118 (0.083–0.175) |
| Current portfolio weights (8) | **0.032** (0.025–0.050) |

- The decisions respond mostly to return and momentum inputs and hardly to current holdings,
  consistent with very high turnover (13–21× a year).
- The regime inputs rank fifth of six, consistent with E12 (§8.2).
- In the three regimes with ≥ 63 validation sessions, every seed held the **least cash** in
  `neutral_normal` and the **most** in `positive_low`, and traded most in `neutral_normal`. No
  negative regime reached 63 validation sessions.

### 8.2 Regime-input ablation (E12, EXP-028)

Retraining without the regime one-hot inputs changed validation net Sharpe by −0.111 / −0.245 /
+0.180 across folds with no reliable direction; the labels are a coarse summary of momentum and
volatility features the policy already observes.

### 8.3 Test-period regime behaviour (EXP-030, descriptive)

On the test period five regimes reach 63 sessions, including `negative_high` (167 sessions). There
the policy held **less** cash (0.10–0.38) than in calm uptrends (0.32–0.50) in every seed, and its
volatility (0.20–0.30 annualised) exceeded every baseline's (0.16–0.19).

**Interpretation:** the policy's allocation does vary with market conditions, but not in a
risk-reducing way: it is not more defensive in falling, volatile markets. All of this is
association, not causation; permutation creates out-of-distribution inputs, and group scores
depend on group size.

## 9. Out-of-sample test evaluation, 2020–2024 (Requirement 8; EXP-030)

**Governance:**
- **Pre-registration:** frozen at commit `67618cf` (SHA-256 `3a5e5e82…ae9f`; protocol hash
  `f45b8b35e16d2d3c`, unchanged since 2026-10-22).
- **Review:** the bootstrap (G3-5) and the evaluator (Gate 3c) were reviewed by Parv Patel, a
  person other than the implementer; the review is not independent of the team and no separate
  review document exists.
- **G3-6:** accepted with a delegated record.
- **Execution:** one run (evaluation `57eeefd22d8ae35d`) after the policy §7 condition check.
- **Candidate:** configuration 4, seeds 42–46, fixed before the test was read; no selection,
  tuning or retraining followed.

**Primary result** (median over seeds of the annualised net Sharpe; 1,256 daily returns):

| | Value |
| --- | --- |
| Configuration 4 per seed (42 / 43 / 44 / 45 / 46) | 0.235 / 0.020 / −0.068 / −0.234 / −0.329 |
| Median | **−0.068** |
| Inverse volatility monthly | 0.253 |
| Difference | **−0.322**, 95% paired moving-block bootstrap interval **[−0.818, 0.192]** (L = 21, 10,000 replicates) |
| Equal weight monthly / buy-and-hold (descriptive) | 0.371 / 0.426 (differences −0.439 / −0.494) |

No p-value or threshold was pre-registered. The primary interval includes zero, but the point
estimate is negative and every seed is below every baseline.

**Secondary results (15 bps):**
- **Turnover and costs:** PPO traded 18–24× a year and lost 12.4–19.6 pp to costs, against at
  most 0.8× and 0.8 pp for the baselines.
- **Returns and risk:** net cumulative return −20.6% to +9.5% (baselines 9.9% to 21.7%); net
  maximum drawdown −19.1% to −31.0% (baselines −23.0% to −24.2%); 32–47% average cash.
- **Cost sensitivity (fixed actions):** at 0 bps the PPO median net Sharpe is 0.261, still below
  every baseline (0.266–0.426); at 30 bps it is −0.399.
- **Stress windows:**
  - **COVID crash (23 sessions):** every PPO seed lost more (−17.3% to −28.1%) than every
    baseline (−10.6% to −14.0%).
  - **2022 bear market (195 sessions):** every PPO seed lost less (−11.1% to −20.8%) than every
    baseline (−20.9% to −22.3%), with lower volatility, consistent with its large cash holding.
  - Both windows matched the dataset calendar.
- **Validation vs test:** the selection median fell from 0.635 (validation) to −0.068 (test).

**Verification:** `evaluate_test.py --verify` recomputes every pre-registered quantity except
one secondary descriptive field. The evaluator counted the cash target at the 0.40 ETF cap in
`share_executions_at_cap` for the PPO policies. Corrected values, from the saved ledgers, are
0.908 / 0.766 / 0.831 / 0.858 / 0.766 (saved 0.943 / 0.839 / 0.847 / 0.927 / 0.770). The code was
fixed afterwards with a regression test; the output was not regenerated and the test was not
re-run. Details: `docs/test_results.md`.

## 10. Discussion: answering the research question

- **Performance:** on the held-out 2020–2024 period, the selected PPO policy did not outperform
  equal weighting, buy-and-hold or inverse volatility on net Sharpe or net return. Even before
  costs its median was below all three. This agrees with the validation evidence and with the
  difficulty of beating naive diversification [6].
- **Risk control:** mixed and not reliable. PPO held much cash and lost less in the 2022 bear
  market, but lost more in the fast COVID crash, and in falling high-volatility regimes it was
  more volatile than the baselines. Its maximum drawdowns spanned the baselines' on both sides.
- **Adaptability:** the policy changes its allocation with conditions (it trades 18–24× a year
  and its cash share varies by regime), but the changes do not reduce risk and their cost
  dominates. A turnover penalty helped on validation, but its test performance is unknown.
- **Interpretability:** permutation sensitivity and regime summaries make the policy's behaviour
  describable (momentum-driven, holdings-agnostic, little use of regime labels); they do not
  make it causal or justify it.
- **Overall:** in this setting (seven ETFs, daily data, one training path, provisional costs), RL
  did not add value over simple rules. The framework, its safeguards and the negative result are
  the contribution.

## 11. Limitations and threats to validity

- **One market history.** One training path, one validation window and one test period; seeds
  share the history and are not independent samples. Walk-forward evaluation (E10–E12) covered
  2007–2019 only; D-018 stays open.
- **Selection on validation.** 40 policies on one window made the validation figures optimistic,
  as the test confirmed.
- **Universe chosen with hindsight** (survivorship and selection bias); provider-adjusted prices.
- **Provisional assumptions.** Costs (15 bps), the 0.40 cap, the weekly frequency and the regime
  thresholds are placeholders, not calibrated.
- **Only configuration 4 was tested.** The better-on-validation turnover-penalty arms were never
  test arms; a new test would need a new pre-registration and is not allowed on this test period.
- **Reward and evaluation mismatch.** The D-064 reward is risk-neutral log growth while evaluation
  uses Sharpe; training used noisy sampled actions while evaluation uses the mean action.
- **Descriptive analyses.** Regime summaries, sensitivities and stress windows are associations
  on one history, not causal effects or independent tests.
- **Governance limits.** The review of the bootstrap and evaluator was by a team member, without
  a written review document; most design choices from E3 on are Provisional (delegated); approvals
  are self-declared in a shared-device session (R-S).
- **One verification defect** in a secondary field of the test output (§9), corrected in the
  report but not in the write-once output.

## 12. Reproducibility

| Item | Identifier |
| --- | --- |
| Data | raw `e27437b97742fa43`; processed `8e00568ee2aa4de7`; features `a79347e37e653703` |
| Baselines | EXP-002, backtest `c6d8c473258e3194` |
| PPO grid and selection | EXP-005 (commit `cc9784b`); EXP-006 evaluation `1ce9c490ed03c8c9` |
| E0–E12 | EXP-009 to EXP-028; comparisons listed in `docs/e*_results.md` and re-verified by the dashboard |
| Explainability | EXP-029, analysis `86b75ffd1d00783e` (commit `bcb99ec`) |
| Test | EXP-030, evaluation `57eeefd22d8ae35d` (commit `67618cf`) |
| Dashboard | build `dadca2c01945447c` (commit `7e6477b`); `python scripts/workflow.py dashboard` |
| Checks | `python scripts/workflow.py verify`; `python scripts/profile_experiment.py … verify <dir>`; `python scripts/evaluate_test.py --verify <dir>` |

Every run records its configuration, seeds, Git commit, data identifiers, hashes of the rows read
and package versions; outputs are written once and hash-checked (`docs/technical_handbook.md`).

## 13. Ethical considerations

- This is research and decision support, **not financial advice**. Backtests are simulations,
  not evidence of future returns.
- **Negative results are reported** in full, including the test underperformance.
- **Data:** public market data retrieved for research; raw data are not redistributed.
- **Misuse risk:** a high-turnover policy that underperformed simple rules out of sample should
  not be deployed. The investor-profile experiments do not establish suitability for any investor.

## 14. AI-use disclosure and attribution

- **Abstract:** ChatGPT (OpenAI) assisted with language and the LaTeX preparation of the
  abstract.
- **Repository:** Claude Code (Anthropic) wrote a substantial part of the implementation, the
  tests and the documentation at the team's direction; it ran the recorded checks, experiments and
  the single test evaluation, and drafted this report. Details are in `README.md` "AI tools
  disclosure" and in `docs/project_journal.md`, session by session.
- **The student team** directs the work, makes and records the research decisions, and is
  responsible for reviewing, verifying and interpreting every result.
- **Approvals:** recorded under rule R-S; messages in the shared-device session are
  self-declared.

## 15. Future work

1. Pre-register and evaluate the turnover-penalised policy on **new** out-of-sample data (a later
   period or another universe); this test period may not be reused.
2. Compare PPO with a simpler learned allocator (for example a linear or mean–variance model)
   under the same folds, costs and constraints.
3. Calibrate costs and the cap, and decide the walk-forward scheme (D-018) and embargo (D-019).
4. Make risk part of the training objective in a way that transfers out of sample (E5–E6 showed
   only in-sample effects).

## Appendix A. The pre-registered test protocol (frozen 2026-11-05; D-083)

- **Candidate:** configuration 4, seeds 42–46, fixed by the validation procedure.
- **Primary endpoint:** median over seeds of the test annualised net Sharpe (D-076 definition);
  primary comparison against inverse volatility monthly with a paired moving-block bootstrap
  (21-session blocks, 10,000 replicates, seed 20261021), 95% percentile interval; no p-values and
  no pass/fail threshold.
- **Other baselines:** descriptive point differences. **Secondary:** returns, CAGR, volatility,
  drawdowns, cost drag, turnover, allocation, concentration, regime summaries (≥ 63 sessions).
- **Cost sensitivity:** 0, 15 and 30 bps as fixed-action accounting.
- **Stress windows:** S&P 500 closing-basis bear markets 2020-02-19 → 2020-03-23 (23 sessions) and
  2022-01-03 → 2022-10-12 (195 sessions), (peak close, trough close].
- **Omitted:** lag and cap sensitivities, Sortino, walk-forward and embargo.
- **Status:** frozen and executed once (EXP-030).

## Appendix B. Governance summary

| Gate | Status |
| --- | --- |
| G3-1 to G3-27 (except G3-5, G3-6) | Accepted 2026-10-21/22 (D-083; R-S) |
| G3-5 bootstrap, Gate 3c evaluator | Reviewed by Parv Patel (2026-11-05; not independent of the team; no document) |
| G3-6 stress windows | Accepted at freeze with a delegated record (D-086, policy §7.1) |
| Commit permission | Given 2026-11-05 (Parvptl) |
| Test execution | Once, after the policy §7 condition check (journal, 2026-11-05) |
| PPO explainability | Authorised as D-097; settings Provisional (delegated) |
| Dashboard | Required for submission (D-098) |
| D-009 | Accepted, unchanged · D-018, D-019 Open · D-094–D-096 Provisional (delegated) |
