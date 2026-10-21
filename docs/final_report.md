# Adaptive Portfolio Intelligence: Explainable Reinforcement Learning for Regime-Aware Portfolio Allocation and Risk Management

**Parv Patel (142301041), Mandar Patil (112401021)** · Research report, **DRAFT, 2026-10-21**

> **Status of this draft: incomplete by design. Do not submit as final.**
> - **The out-of-sample test evaluation (2020–2024) has not been run.** Gate 3 is not approved
>   (`docs/approval_checklist.md`).
> - **The PPO explainability analysis has not been run.** It is implemented, but needs an
>   explicit authorisation to read validation-period inputs (D-068).
> - Stress tests, bootstrap uncertainty, walk-forward validation and ablations have no results.
>   The test evaluator, bootstrap and stress-window code exist and are tested on synthetic data,
>   but the Gate 3 pre-registration is a **DRAFT** with every item open, so nothing has run.
> - *Update 2026-10-22:*
>   - Gate 3 decisions are recorded (D-083; Appendix A), but the pre-registration is still
>     a **DRAFT**: the bootstrap needs independent human review, and the stress-window session
>     counts can only be checked against the dataset at run time.
>   - No real-data bootstrap, stress, cost-sensitivity or test result exists.
> - Every number below is a training- or validation-period backtest result taken from a recorded
>   artifact. **None is an out-of-sample result.**
> - This is research, not financial advice.

## 1. Motivation and research question

Portfolio allocation is a sequential decision problem under uncertainty, transaction costs and
changing market conditions. Fixed allocation rules do not adapt to these conditions; a learned
policy might.

**Research question (from the submitted abstract):** can a reinforcement-learning policy,
specifically Proximal Policy Optimisation (PPO) [1] as a candidate algorithm, allocate across a
small ETF universe in a way that responds to market conditions (rising, falling and
high-volatility periods)? How does it compare with conventional allocation benchmarks, after
transaction costs, on:
- cumulative return, Sharpe ratio, maximum drawdown and turnover;
- risk control, adaptability and interpretability?

**No performance improvement was assumed in advance.**

## 2. Related work and references

- **PPO** [1] is a clipped policy-gradient actor–critic method. **Reinforcement learning
  foundations:** [2]. **Direct reinforcement for trading:** [3].
- **Naive diversification:** equal weighting (1/N) is a demanding benchmark for optimised
  portfolios [6], which motivates the untuned conventional baselines used here.
- **Software:** Stable-Baselines3 [4] and Gymnasium [5].
- **Bootstrap:** the stationary block bootstrap [7] is *proposed*, not yet decided, for the
  Gate 3 uncertainty analysis.

*References [1]–[3] are those of the submitted abstract. The bibliographic details of [4]–[7]
were written from memory by the AI assistant and **must be checked against the publishers'
records before submission**.*

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

## 3. Data, features, regimes and splits

**Data:**
- seven ETFs: SPY, EFA, EEM, IEF, TLT, LQD and GLD;
- daily adjusted prices from yfinance (live retrieval, 2026-10-15), requested for 2007–2024;
- raw dataset `e27437b97742fa43`, processed dataset `8e00568ee2aa4de7`;
- simple returns.

**Known data limitations** (recorded in the dataset metadata):
- the universe was chosen with hindsight (survivorship and selection bias, D-034);
- adjusted prices depend on the provider's method;
- the calendar is observed only.

**Features:** 34 causal features (feature set `a79347e37e653703`) in four families: return and
momentum, volatility and risk, cross-asset, and universe context. A row dated *t* uses returns up
to *t* (D-043, Proposed). Standardisation is fitted on training rows only and clipped at ±10
(D-062).

**Regimes** (D-045, Proposed, provisional):
- **trend** from 63-session equity momentum, with a neutral band of ±*b* (*b* = 0.037974, the
  training 1/3 quantile of |*m*|);
- **volatility** from 21-session market volatility, split at the training terciles (0.008937
  and 0.013051 per session);
- nine labels *trend*_*volatility*, plus `unavailable` during the warm-up;
- the thresholds are fitted on training rows only and frozen. They are descriptions, not
  verified market states.

**Splits** (D-009): train 2007–2016, validation 2017–2019, test 2020–2024. The test period is
sealed: development code never parses test-period values (D-060).

## 4. Portfolio environment

- **Timing:** decide at the close of *d*, execute at the close of *d* + 1 (lag 1, D-055). PPO
  decides weekly, on the first session of each ISO week (D-065). An episode is one split's
  window, starting from cash; a training episode has 496 steps.
- **Actions:**
  - 8 values in [−1, 1], scaled ×5 to logits (D-072);
  - a softmax over the 7 ETFs and cash;
  - each ETF target is capped at 0.40, with the excess going to cash (D-063, D-057).
  - Long-only, unlevered.
- **Observation (51 inputs):** the 34 scaled features, a 9-way regime one-hot and the 8 current
  weights (D-062).
- **Reward:** the decision-aligned log growth of portfolio value **after costs** (D-064). There
  is no explicit turnover or risk penalty.
- **Costs:** 10 + 5 bps on ETF traded notional (cash leg excluded), including the initial
  funding trade (D-007, D-049; provisional values). No terminal liquidation. Cash earns 0.

## 5. Agents, baselines and protocol

**PPO** (Stable-Baselines3 2.9; D-066, D-074):
- separate 64×64 tanh policy and value networks;
- `batch_size` 64; other settings are pinned library defaults;
- a grid of learning rate {3e-4, 1e-4} × `n_steps` {512, 1024} × entropy coefficient {0, 0.01};
- seeds 42–46, 100,000 timesteps each;
- 40 runs on the training split only (EXP-005, commit `cc9784b`).

**Baselines** (D-053, untuned): equal weight monthly, equal-weight buy-and-hold, and inverse
volatility (63 sessions) monthly. They use the same simulator, costs, timing and windows.

**Selection** (D-076, accepted before evaluation):
- deterministic actions (the policy mean);
- the configuration with the highest median validation net Sharpe over seeds 42–46;
- annualised Sharpe = √252·mean/std (ddof 1), rf 0, funding row excluded;
- tie tolerance 1e-9 with a fixed tie-break.

## 6. Results (training and validation only)

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

- **Run:** evaluation `1ce9c490ed03c8c9`, protocol hash `e652adec1095c95a`, at commit
  `0f8341b`.
- **Selection:** configuration 4 (learning rate 1e-4, `n_steps` 512, entropy coefficient 0),
  median validation net Sharpe 0.635. The next best is configuration 5 at 0.498.
- **Per seed:**

  | Seed | Net Sharpe | Net cumulative return | Cost drag | Annualised traded notional |
  | --- | --- | --- | --- | --- |
  | 42 | 1.149 | 21.14% | 7.54 pp | 13.34 |
  | 43 | 0.486 | 9.90% | 9.65 pp | 18.61 |
  | 44 | 0.635 | 10.60% | 10.92 pp | 20.85 |
  | 45 | 0.253 | 3.57% | 7.18 pp | 14.82 |
  | 46 | 0.731 | 12.24% | 8.40 pp | 15.89 |

- **Across all 40 policies:**
  - net Sharpe −0.063 to 1.227;
  - **no policy reached the net Sharpe of any baseline** (1.355 to 1.754);
  - gross cumulative return 6.77% to 40.82%; only 5 of 40 policies exceeded the lowest
    baseline's 27.01% before costs.

**These are validation results used for selection.** With 40 policies on one window, the
selected configuration's validation figures are likely optimistic.

### 6.3 Turnover and cost diagnostic (descriptive; `docs/exp006_turnover_diagnostic.md`)

- **[D] Turnover:** the policies traded 13.3–27.9× the portfolio per year (recurring ETF trades),
  against at most 0.78× for the baselines. 99.3–99.9% of their traded notional coincides with
  changes in the target, not drift correction.
- **[O] Cost drag:** 7.0–15.0 percentage points per policy over the window.
- **[D] Training fit vs validation:**
  - the higher learning rate fitted the training episodes far better (last-10-episode log
    growth 1.74–2.09, against 0.74–0.79);
  - but it had lower validation net Sharpe;
  - across the 40 runs, training log growth and validation Sharpe correlate at −0.25.
- **[H] Hypotheses, none tested:** overfitting to the single training path; costs not deterring
  trading in-sample; deterministic evaluation differing from the noisy trained policy.

### 6.4 Regime-conditioned behaviour of the baselines (EXP-008, training split)

- **Sample sizes:** 2,390 sessions in 369 regime episodes. `negative_low` has only 38 sessions
  (flagged small); `unavailable` has 0.
- **Volatility:** realised volatility is highest in `negative_high` for all three baselines.
  This is partly mechanical, because the labels come from trailing market volatility.
- **Allocation:** inverse volatility holds less equity and more Treasuries in high-volatility
  regimes, a direct consequence of its rule.
- **Drawdown:** each baseline's deepest training drawdown (−28.51%, −24.44% and −18.64% for equal
  weight monthly, buy-and-hold and inverse volatility) falls on `negative_high`-labelled rows.
  Drawdown levels are path-dependent, so this is not a loss caused by the regime.
- **Not inferential:** these figures are descriptive associations with no confidence intervals.
  **They do not describe the PPO policy.**

### 6.5 Out-of-sample test results

**Not available.** The test period (2020–2024) is sealed. Before it is opened, the Gate 3
pre-registration needs decisions on:
- the candidate checkpoints and the primary endpoint;
- the bootstrap settings and stress windows;
- multiple comparisons, success criteria, and the regime, walk-forward and embargo treatment.

It then needs a reviewed, separate test evaluator and an explicit unsealing authorisation
(`docs/approval_checklist.md`, G3-1 to G3-27).

**Status of the evaluator (2026-10-21):**
- A separate evaluator now exists (`scripts/evaluate_test.py`; D-082, Proposed). Its plan
  mode reads no data rows.
- Execution is refused unless the pre-registration is frozen, its SHA-256 matches the
  authorised one, and the code is clean at the authorised commit.
- The pre-registration `configs/preregistration.yaml` is a **DRAFT** in which every item is
  open, so **no test result exists or can yet be produced.**

## 7. Risk, robustness, explainability and ablation

- **Risk (validation):**
  - drawdowns: configuration 4's net maximum drawdowns were −6.99% to −11.05%, against −7.58%
    to −11.49% for the baselines;
  - cost drag was 7.2–10.9 percentage points for configuration 4. It exceeds the shortfall in
    net cumulative return to the lowest-return baseline (inverse volatility, 26.37%) only for
    seed 42. Seeds 43–46 also trail that baseline before costs, so costs are not the whole
    explanation.
- **No inference:** no bootstrap intervals or significance tests exist.
- **Robustness:** seed variation is large (configuration 4: net Sharpe 0.25 to 1.15). Cost,
  lag and constraint sensitivities are proposed for Gate 3 (G3-23 to G3-25) but not run.
  Walk-forward (D-018) and stress tests (G3-6) do not exist.
- **Explainability (D-068):** regime-conditioned summaries and one-step permutation sensitivity
  of the decided targets are implemented and verified on synthetic checkpoints. That includes a
  fidelity check that rebuilt decisions reproduce the evaluator's recorded decisions.
  **They have not been run on the PPO policy** (authorisation pending).
- **Ablation:** removing the regime inputs requires retraining. It is planned (D-081,
  Proposed), not run.

## 8. Limitations and threats to validity

- **One market path.** A single validation window (2017–2019, mostly low-volatility regimes) and
  one dataset. The selection used validation, so the validation figures are optimistic.
- **Universe chosen with hindsight**, so survivorship and selection bias. Provider-adjusted
  prices.
- **Provisional assumptions.** Costs (15 bps), the 0.40 cap, the weekly frequency and the
  regime thresholds are provisional, not calibrated.
- **The reward ignores risk.** It is risk-neutral log growth after costs, with no turnover or
  volatility term, while evaluation uses Sharpe.
- **Training–evaluation mismatch.** Training used sampled actions with large noise (final std
  0.69–1.02); evaluation uses the mean action.
- **Descriptive analyses only.** Regime summaries and sensitivity analyses are associations or
  sensitivities, not causal effects.
- **Untuned baselines**, which is conservative for the baselines.

## 9. Reproducibility

- **Recorded for every run:** configuration, seeds, Git commit, dataset and feature ids, the
  hashes of the training lines read, and package versions.
- **Outputs:** written once, never overwritten, and hash-checked.
- **Commands:** `README.md` and `docs/technical_handbook.md` §1 and §18. The read-only
  `python scripts/workflow.py verify` re-checks the evaluation outputs and the selected
  checkpoints.
- **Clean environment:** the core, dev and viz extras were installed in a fresh virtual
  environment on 2026-10-21. The non-RL tests passed and the workflow ran; the RL extra was not
  reinstalled there.

## 10. Ethical considerations

- This is research and decision support, **not financial advice**. Backtests are simulations,
  not evidence of future returns.
- **Negative results are reported:** the learned policy trailed simple benchmarks on
  validation. Presenting selective results would mislead.
- **Data:** market data were retrieved from a public provider for research. Raw data are not
  redistributed in the repository.
- **Misuse risk:** a policy with high turnover and an untested out-of-sample record should not
  be deployed.

## 11. AI-use disclosure and attribution

- **Abstract:** ChatGPT (OpenAI) assisted with language and the LaTeX preparation of the
  abstract.
- **Repository:** Claude Code (Anthropic) wrote a substantial part of the implementation, the
  tests and the documentation at the team's direction. It ran the recorded checks and
  experiments, and drafted this report. Details are in `README.md` "AI tools disclosure" and in
  `docs/project_journal.md`, session by session.
- **The student team** directs the work, makes and records the research decisions, and is
  responsible for reviewing, verifying and interpreting every result.
- **Approvals:** recorded under rule R-S. Messages in the shared-device session do not name
  their author; this attribution limitation is recorded with each approval.

## 12. Future work

1. **Gate 3:** decide the pre-registration items. Then implement and review a separate test
   evaluator, and run the single test evaluation, reporting it whatever the outcome.
2. **Explainability:** authorise and run the D-068 analysis of the selected policy on validation
   decisions.
3. **Follow-ups (D-077, D-078, D-081):**
   - a training-period deterministic-vs-sampled diagnostic;
   - execution smoothing;
   - a turnover-aware reward;
   - a lower decision frequency;
   - a regime-input ablation.

   Each must be decided on training data, with at most one further validation look and no test
   access.

## Appendix A. Pre-registered test protocol (DRAFT, not frozen; D-083, 2026-10-22)

- **Candidate:** configuration 4, seeds 42–46, fixed by the validation procedure. It is a
  research candidate that **underperformed all three baselines on validation net Sharpe**, not
  a demonstrated strategy.
- **Primary endpoint:** the median over the five seeds of the test annualised net Sharpe (D-076
  definition).
- **Primary comparison:** that median minus the inverse-volatility baseline's net Sharpe.
  - Interval: a paired moving-block bootstrap (21-session blocks, 10,000 replicates, seed
    20261021), 95% percentile interval.
  - **No p-values and no pass/fail threshold.**
  - The five seeds share one market history and are not independent samples.
- **Other baselines:** equal-weight monthly and buy-and-hold get descriptive point differences
  only.
- **Secondary:**
  - net and gross returns, CAGR, volatility and drawdowns (net with dates);
  - cost drag, recurring ETF turnover and trade counts;
  - allocation, cash and concentration;
  - regime summaries with a minimum of 63 sessions (D-045 thresholds).
- **Cost sensitivity:** 0, 15 and 30 bps as fixed-action accounting (the policy does not adapt).
- **Omitted from this protocol:** lag sensitivity, baseline-cap sensitivity, Sortino and
  walk-forward evaluation. No embargo is applied.
- **Stress windows:** S&P 500 closing-basis bear markets.
  - 2020-02-19 → 2020-03-23 (23 sessions); 2022-01-03 → 2022-10-12 (195 sessions).
  - Boundary (peak close, trough close].
  - Sources: Wikipedia, CNBC/S&P Dow Jones Indices, and the ICE holiday calendars.
  - The counts are provisional against the dataset calendar.
  - These are descriptive slices of one history, not independent tests.
- **Status:** not frozen and not executed. The evaluator is verified on synthetic data only; no
  human has reviewed it. Running it needs a separate unsealing authorisation.
