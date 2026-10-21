# EXP-006 turnover and cost diagnostic, and follow-up proposal

- **Date:** 2026-10-21.
- **Scope:** analysis of existing artifacts only. No training, no new evaluation run, no
  protocol change.
- **Test period:** 2020–2024 is **sealed**. No test row or metric was loaded, inspected or
  reported.

**Sources:**
- evaluation `1ce9c490ed03c8c9` (protocol hash `e652adec1095c95a`): `ledgers.csv`,
  `policy_metrics.csv`, `baseline_metrics.csv`, `allocations.csv`, `metadata.json`;
- the training artifacts of the 40 EXP-005 runs (`monitor.csv`, `run_config.json`, `model.zip`);
- EXP-002's saved training metrics;
- regime labels from the feature set, read with the bounded loader (rows before 2020-01-01,
  checked).

**Reproducibility:** the script and its outputs are in
`data/processed/diagnostics/turnover_1ce9c490ed03c8c9/`: `turnover_diagnostic.py`,
`report.json`, `strategy_summary.csv`, `executions_reconstructed.csv`,
`policy_turnover_by_regime.csv` and `training_vs_validation.csv`. These are git-ignored.

**Labels:**
- **[O] observed:** read directly from an artifact.
- **[D] derived:** computed from observed values.
- **[H] hypothesis:** an interpretation not tested by a controlled experiment. Nothing here
  establishes causality.

## 1. Consistency of the saved outputs

- **[D] Asset returns:** the daily validation returns of the 7 ETFs were recovered from the 43
  saved ledgers alone. Each strategy's gross return is its previous end-of-row weights times
  the asset returns, with cash at 0. The weight matrix had full rank (7) on every date, and the
  fit residual was at most 8.8e-17. The dataset files were not re-read.
- **[D] Reconstructed trades:** pre-trade (drifted) weights rebuilt from those returns reproduce
  the ledger's traded notional at every execution, to 1.1e-16.
- **[D] Accounting identities:** for all 43 strategies, net = g − c(1 + g) on every row, and
  100,000 × Π(1 + net) equals the final value, both to rounding (0.0 at the printed precision).
- **[D] Annualised turnover** equals the recurring traded notional (excluding the funding
  trade) / 752 return periods × 252, matching `annualised.annualised_traded_notional` to 7e-15.

## 2. Findings

### 2.1 How turnover is measured

- **[O]** Traded notional = Σ |target − drifted weight| over the 7 ETFs. The cash leg is
  excluded, and this is the cost base. Two-way turnover also includes the cash leg.
- **[O]** Cost = 15 bps × traded notional × value before cost.
- **[O]** Annualised turnover uses recurring trades only (D-052, D-059). The funding trade is
  reported separately.

### 2.2 How much is traded, and how it splits (accounting decomposition)

- **[D] The policies trade at almost every weekly decision.** The 155 recurring executions per
  run move a mean of 0.26–0.54 of the portfolio (median across runs 0.39). For the baselines
  this is 0.019 (equal weight monthly) and 0.067 (inverse volatility).
- **[D] Annualised recurring turnover:** 13.3–27.9× per year across the 40 runs (median
  20.1×), against 0.22× and 0.78× for the rebalancing baselines.
- **[D] Almost all traded notional coincides with target changes, not drift correction.**
  This is an accounting split of each trade, not a causal attribution:
  - 99.3–99.9% of policy traded notional matches the *change in target*, i.e. the sum of
    |target_k − target_(k−1)| over the trades is 0.993–0.999 of the total traded;
  - the drift correction (back to the previous target) is only 0.7–1.9%;
  - for equal weight monthly, by construction, 100% of trading is drift correction.
- **[D] Large reallocations are common.** Per run, 14–49% of weekly target changes exceed 0.5
  of the portfolio. The median weekly target change per run is 0.05–0.46.

### 2.3 Costs and returns

- **[O] The gap between gross and net:**
  - across the 40 policies, gross cumulative return was 6.8–40.8% and cost drag was 7.0–15.0
    percentage points over the window;
  - for the baselines, cost drag was 0.19–0.63 percentage points;
  - recurring costs per policy were 6,540–13,446 per 100,000 initial value (median 9,231).
- **[O] Funding cost** was 61–150 per policy, against 150 for each baseline. Policies start
  with partial cash, so their first trade is smaller.
- **[O] Even before costs only 5 of 40 policies** exceeded the lowest baseline's gross
  cumulative return (27.0%). In this accounting sense the shortfall is not only a cost effect.
- **[D] Turnover and Sharpe across the 40 runs:** correlation −0.18. This is a weak association
  (r² ≈ 0.03) between runs, not an estimate of the effect of turnover.

### 2.4 Constraints, cash and timing

- **[O] Targets:** every executed target respects the 0.40 cap (maximum 0.40000). In a median
  87% of executions (17–98% per run) at least one ETF is at the cap.
- **[O] Drift above the cap:** between executions, held weights drift above 0.40 on 65–380 of
  753 rows per run, with a maximum of 0.415. This is allowed: the cap applies to targets
  (D-057).
- **[O] Cash:** mean target cash per run was 0.11–0.50 (median 0.36). The baselines hold no
  cash.
- **[D] Timing:** every policy execution is exactly 1 session after its decision (lag 1,
  D-055). Every decision is on the first session of an ISO week (D-065), with 156 executions
  per run.
- **[O] Ledger consistency:** EXP-006 completed, so the evaluator's in-run check that the
  environment and simulator ledgers agree passed for every policy. That check stops the run if
  they differ.
- **What was not checked:** the diagnostic did not recompute targets from the policies' raw
  actions through the D-063 mapping, because actions are not saved. It checked that targets
  respect the cap and that traded notional reconciles.

### 2.5 Where the trading is concentrated

- **[D] By ETF:** the share of policy recurring traded notional (funding trade excluded) was
  SPY 21.8%, TLT 18.6%, IEF 17.3%, EEM 14.8%, EFA 14.2%, LQD 7.0% and GLD 6.3%. For configuration 4 it was similar: SPY 22.0%,
  IEF 18.2%, EEM 17.2%, TLT 15.8%, EFA 14.9%, LQD 8.3% and GLD 3.7%.
- **[D] By year:** the mean traded per execution across all policies rose from 0.278 (2017)
  to 0.390 (2018) to 0.513 (2019).
- **[D] By regime at the decision date** (all policies):
  - highest per execution in `neutral_high` (0.64) and `neutral_normal` (0.61);
  - lowest in `positive_low` (0.31), which is also the most frequent validation regime (2,760
    of 6,200 policy executions).
- **[D] By seed:** the spread is wide within configurations. For configuration 4 it runs from
  13.3× (seed 42, the best Sharpe 1.149) to 20.8× (seed 44).

### 2.6 Training objective vs evaluation objective

- **[O] Reward:** the training reward (D-064) is the per-step log growth of portfolio value
  **after the same 15 bps costs** (run configs: `cost_rate` 0.0015). Costs are therefore
  already in the training objective.
- **[O] What the reward lacks:** it has no explicit turnover penalty and no volatility or
  drawdown term. The evaluation objective is annualised net Sharpe.
- **[D] Training fit vs validation:** the last-10-episode mean training log growth was:
  - 1.74–2.09 per configuration for the higher learning rate (configurations 0–3);
  - 0.74–0.79 for the lower learning rate (configurations 4–7);
  - versus 0.42–0.54 for the three baselines on the same training window (EXP-002, net).

  The higher-learning-rate configurations had *lower* validation net Sharpe (means 0.31–0.53)
  than the lower-learning-rate ones (0.45–0.65). Across the 40 runs the correlation between
  training log growth and validation Sharpe is −0.25.
- **[O] Exploration noise:** the final policy action noise (std of the Gaussian on `[−1, 1]`)
  was still 0.69–1.02 (configuration means). Training rewards were collected with **sampled**
  actions; evaluation uses the **deterministic** mean action (D-076).

### 2.7 Hypotheses (not tested)

- **[H1] Overfitting to the single training path.** Training-episode log growth (sampled
  actions, after costs) was far above the baselines' training log growth, while validation
  net Sharpe trailed every baseline (2.6). One possible explanation is that the policies
  learned path-specific, frequent reallocations whose in-sample gains exceeded costs. The
  negative train-to-validation relationship is consistent with this, but does not
  establish it.
- **[H2] Costs did not deter trading.** Because the reward already includes costs, high
  turnover may persist because, in-sample, the learned reallocations *paid*. A stronger turnover
  deterrent would then be needed to change behaviour out of sample.
- **[H3] Deterministic evaluation differs from what was trained.** The policies were trained
  and scored under large action noise. The mean action may behave differently from the trained
  stochastic policy, e.g. being more concentrated: frequent 0.40 caps and high cash. This has
  not been measured.
- **[H4] Rising turnover over 2017–2019** may reflect validation states moving away from the
  training distribution. It is not tested.
- **[H5] A weekly frequency** gives 156 decision points per three years. Each is an opportunity
  for an unproductive reallocation.

### 2.8 Limitations

- One validation window, one dataset, deterministic actions only. No statistical tests: the
  Gate 3 bootstrap is not decided.
- The decomposition splits *traded notional*. It does not attribute *returns* to individual
  trades.
- The regime breakdown pools 40 policies with very different behaviour.
- The asset returns are derived from the ledgers; they agree to 1e-16, but are not read from
  the dataset.
- The training figures come from training-time episodes with sampled actions; they are not
  deterministic training-period evaluations.

## 3. Follow-up proposal (D-077, Proposed; nothing implemented or trained)

### 3.1 Principles that apply to every item

- **Validation reuse:** 2017–2019 has been used once, for the D-066 selection. Each further
  look weakens it as an unbiased selection set. Every follow-up below therefore:
  - fixes all of its parameters using **training data only**: either in-sample, or an inner
    split of the training period, e.g. fitting on 2007–2013 and choosing on 2014–2016;
  - uses validation **at most once**, as a confirmatory comparison;
  - **never touches the test period.**
- **Fairness:**
  - same dataset, window, costs (15 bps), constraints, lag 1, funding treatment and metrics
    (D-076 definitions);
  - the same three untuned baselines;
  - the same seeds (42–46), with every seed reported;
  - an equal or explicitly stated training budget.
- **The configuration-4 selection stands.** No follow-up re-selects among the EXP-005
  configurations. A follow-up produces new, separately labelled candidates.

### 3.2 Prioritised proposals

| Priority | Proposal | Hypothesis tested | Changes needed | Data use | Success / failure, declared before running | Approval needed |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Training-period deterministic evaluation** of the 40 existing checkpoints and the baselines, with deterministic and sampled actions; no training | Informs, but cannot test, H1 (in-sample vs out-of-sample gap) and H3 (deterministic vs sampled) | Allow the evaluator to evaluate the **train** split, as a new protocol version with its own hash; D-076 itself unchanged | Training split only (no validation, no test) | Descriptive only: report the in-sample net Sharpe and turnover of each policy, deterministic vs sampled. No selection or tuning | A new protocol decision (e.g. D-078) plus authorisation to run |
| 2 | **Execution smoothing or a no-trade band on the existing configuration-4 checkpoints**, no retraining. Partial adjustment `w = w_pre + η(a − w_pre)`, or skip trades with L1 change < δ | H2, H5: does damping reallocation reduce turnover and cost drag without destroying gross return? | An execution wrapper applying a rule fixed before running (η and δ chosen from small pre-declared grids, e.g. η ∈ {0.25, 0.5}, δ ∈ {0.1, 0.2}). New evaluator protocol version; D-076 outputs untouched | Choose η or δ on the **training** split only; then **one** validation comparison of configuration 4 (5 seeds) with the frozen rule | Primary: the median validation net Sharpe of configuration 4 with the frozen rule exceeds the unsmoothed 0.635, **and** the median annualised turnover falls by ≥ 50%. Secondary: whether it reaches the lowest baseline (1.355). Otherwise failure. Report all seeds | A decision on the rule, its grids and criteria; authorisation for one validation look |
| 3 | **Retrain configuration 4's hyperparameters with a turnover-aware reward**, e.g. `r = log growth − λ · traded_notional` (λ on top of the true costs), or a training-only cost multiplier | H2: does an explicit turnover deterrent change the learned behaviour? | A reward option in the environment (new decision amending D-064 for this experiment only); a new grid; tests | λ from a declared grid (e.g. {0.0005, 0.002}), chosen on the **inner training split** (2014–2016); then **one** validation comparison | Primary: median validation net Sharpe above 0.635 with turnover at most half of EXP-006's configuration 4; all seeds reported | A reward decision, training authorisation (about 10–15 runs at about 80 s each), one validation look |
| 4 | **Lower decision frequency**, e.g. every 4 weeks, with configuration 4's hyperparameters | H5 | `DECISION_SCHEDULE` option (amends D-065 for this experiment) plus tests; same timestep budget | Training plus one validation comparison | As 3 | A decision amending D-065, training authorisation |
| 5 | **Reduce overfitting:** a smaller budget or training-split early stopping on an inner split, with configuration 4 | H1 | A checkpoint-selection rule on the inner training split (amends D-066 "final checkpoint only") | Inner training split plus one validation comparison | As 3 | A decision, training authorisation |

**Recommended order:**
1. **Item 1 first.** It uses no validation data and needs no training. It describes in-sample
   behaviour under deterministic and sampled actions. That bears on H1 and H3 but cannot
   establish either (D-078 §10). Its result may inform which of items 2–5 is worth
   proposing.
2. **Then item 2.** It needs no retraining and tests the turnover mechanism directly.
3. **Items 3–5** only if items 1–2 support them.

## 4. Gate 3 decisions still required before any test evaluation

1. **Whether to proceed to the test period now**, and with which candidate.
   - D-066 and D-076 selected configuration 4 on validation.
   - No test endpoint is accepted yet. Gate 2 item 10 (approval checklist) recommends, but
     leaves open, test net Sharpe as the median over seeds 42–46.
   - Any follow-up candidate must be decided **before** unsealing; otherwise the test is
     used for selection.
2. **Bootstrap settings:** block length (e.g. 21 sessions with 63 as a declared sensitivity),
   number of resamples, random seed, confidence-interval method, statistic (the joint
   stationary block bootstrap of design memo item 8).
3. **Stress-window rule and its public source:** windows defined by a pre-stated rule, with
   dates confirmed from a cited public source, not from test results.
4. **Multiple comparisons:** how the three baseline comparisons, and any extra candidates, are
   reported or adjusted.
5. **A pre-registration document** (hypotheses, primary and secondary endpoints, success
   criteria, reporting plan), committed **before** unsealing.
6. **A reviewed test evaluator.** The current evaluator deliberately has no test option. Adding
   one needs a new protocol decision, tests and review.
7. **An explicit authorisation to unseal**, with the commit identity, recorded under R-S.
8. **A reporting policy for validation results** in presentations, given that the selected
   PPO trails the baselines on validation.

---

*Update (2026-10-21, appended):*
- A standalone protocol for item 1 of §3.2 is drafted as **D-078 (Proposed)** in
  `docs/protocol_d078_training_modes.md`.
- **Correction** (made before this document was first committed): §2.6 previously gave the
  lower-learning-rate training log growth as "0.74–0.80". The configuration means are
  0.737–0.795, so the range is now "0.74–0.79". §2.5 now states that the ETF shares are of
  recurring traded notional, i.e. with the funding trade excluded.

*Second update (2026-10-21, appended, Phase D audit; this document was still uncommitted):*

**Wording corrections.** These statements overstated what a descriptive diagnostic shows, or
misattributed a decision. They were corrected in the body; the original wording is recorded
here:
- §2.2 heading: was "How much is traded and why".
- §2.2 bullet: was "Target changes drive the trades, not drift".
- §2.3: was "Costs do not explain the whole shortfall" and "turnover differences between runs
  explain little of their Sharpe differences".
- §2.7 H1: began "The policies fit 2007–2016 far better than the baselines in-sample,
  including costs, but do not generalise", and said "supported by, but not proven by".
- §3.2 item 1: the hypothesis column read "H1 (…), H3 (…)". The recommended order said item 1
  "tells us whether the problem is overfitting (H1), the evaluation mode (H3), or both".
- §4 item 1: said "D-066 pre-registers the selected configuration 4 (median of seeds 42–46 of
  test net Sharpe as the primary endpoint)". **That was inaccurate.** D-066 covers seeds,
  validation selection and the budget. The test endpoint is a recommendation in Gate 2 item
  10, which is still open.

**Superseded design notes:**
- §3.2 item 1's "Changes needed" (extending the evaluator) is superseded by the D-078 draft. It
  proposes a separate module, leaving the D-076 evaluator unchanged.
- The §4 Gate 3 list is superseded by the Gate 3 pre-registration packet in
  `approval_checklist.md` and the Phase D section of `roadmap.md`.

**Turnover basis:** every "×" turnover figure here is recurring ETF traded notional per year: the initial funding trade and the cash leg are excluded (D-049, D-059). Two-way
turnover, which includes the cash leg, is not used in this document's figures.
