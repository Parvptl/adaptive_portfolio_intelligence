# Experiment Log

Every experiment whose results are discussed, plotted or reported must have an entry here. Record
negative and inconclusive results as well as positive ones. Do not edit past entries except to add
corrections, marked as such.

## How to add an entry

1. Copy the template below to the top of the **Entries** section.
2. Use the next ID (`EXP-001`, `EXP-002`, …).
3. Commit the config files used, and fill in the commit hash.
4. State which period the reported numbers come from. Test-period results are reported only for
   final, pre-registered evaluations.

---

## Template

```markdown
### EXP-XXX: <short title>

- **Date:** YYYY-MM-DD
- **Author(s):**
- **Milestone:** (see docs/roadmap.md)
- **Git commit:** `<hash>` (clean working tree? yes/no)
- **Config files:** `configs/...` (or an inline diff from defaults)
- **Random seed(s):**
- **Data:** provider, universe, date range, frequency, data snapshot/version
- **Periods used:** train YYYY-MM-DD → YYYY-MM-DD; validation …; test … (used? yes/no)

**Hypothesis / question**
What is being tested, and what result would count as support or refutation?

**Method**
Strategy / agent, key hyperparameters, cost assumptions (bps), constraints, rebalancing frequency.

**Assumptions and known limitations**
Anything provisional (costs, universe, survivorship, timing convention).

**Results** (state period; include baselines under identical conditions)

| Strategy | Ann. return | Ann. vol | Sharpe | Sortino | Max DD | Turnover | Cost drag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

Variation across seeds:
Figures: `reports/figures/...`

**Interpretation**
What the evidence does and does not support. No claims of profitability without evidence.

**Next steps**
```

---

## Entries

### EXP-019: E8 turnover-penalty refinement, real-data pipeline check (smoke; training split; NOT a result)

- **Date:** 2026-11-04. **Author(s):** run by Claude Code under D-084, at a team member's
  instruction (E8 master prompt; author not named; R-S).
- **Git commit:** uncommitted working tree on top of `a5d0f0f` (`dirty: true` recorded).
- **Config:** `configs/turnover_refine_k{0,1,2,3}.yaml` (κ = 0, 0.0015, 0.003, 0.0045; λ = 0;
  D-092), seeds 42–46.
- **Data:** dataset `8e00568ee2aa4de7`, training split only; the rows read end before
  2017-01-01.
- **Method:**
  - 4 × 5 smoke runs of 2,048 timesteps each (1.7–2.0 s each);
  - then `evaluate --split train --pipeline-check --execute`, giving `fd4471b114fd2117` (E8B),
    `555a0924d1f686fb` (E8T1), `0b63794277388908` (E8T2) and `ce32854532a2cac9` (E8T3), all
    VERIFIED (20 of 20 comparability checks; the budget check is skipped for pipeline checks).
- **Checks:**
  - **E8B:** no turnover-penalty keys in any training episode.
  - **E8T1–E8T3:** the logged `turnover_penalty` = κ × the logged `traded_notional` in every
    training episode (all 15 runs) and every evaluation episode.
  - **New measures:** `allocation_dispersion` and `share_meaningful_changes` are populated for
    every seed and arm.
- **Observation:** the near-random smoke policies trade about 0.99 of the portfolio per step, so
  their mean episode penalty is 0.61 / 1.22 / 1.82 at κ = 0.0015 / 0.003 / 0.0045, against a
  mean episode base reward of −0.35.
- **Results:** none (smoke checkpoints).

---

### EXP-018: E7 turnover-aware PPO, κ = 0, 0.0015, 0.0075 (training and validation; descriptive; simulated)

- **Date:** 2026-11-03, 20:11–20:37 UTC (2026-11-04 IST; training and evaluations); analysed
  2026-11-04.
- **Author(s):** run by Claude Code under D-084, at a team member's instruction (E7 master
  prompt; author not named; R-S).
- **Git commit:** `c682e32` (clean working tree) for training and evaluations.
- **Config files:** `configs/turnover_k{0,1,2}.yaml`. They differ only in `label` and
  `turnover_penalty` (D-091; fixed before training).
- **Random seeds:** 42–46 per arm. λ = 0; constant profile input 0.5.
- **Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`.
- **Periods used:** training 2007-07-05 → 2016-12-30; validation 2017-01-03 → 2019-12-31.
  **Test not used:** the rows read end before 2020-01-01.

**Method:**
- **Reward:** r = r_base − κ·TN_k (TN_k = the step's recurring traded notional; funding step 0).
  Shaping only; the real 15 bps cost is charged once, by the unchanged ledger.
- **Training:** 15 of 15 `full` runs: 100,352 timesteps and 202 episodes each; 89–155 s each;
  0 failures, 0 retries.
  - E7B: cfd7ca4cdebd29c7, 21440b40672308cf, d20341e993bfc9df, 11d2d91fb9cade86,
    7c7fcc911080ffd8;
  - E7T1: 5aa8f4a944781cea, 532bf2990857b828, 4084e8c86e688270, eaa6b323401f3199,
    50489bf5cc838d12;
  - E7T2: 30a0c2708397778f, 336353126f61842f, 3e8b29d17d826043, 4aaa66dcca7b5837,
    b74fd3eb4d8cdb0a.
- **Evaluations (VERIFIED; 25 of 25 comparability checks each):**

  | Arm | Train | Validation |
  | --- | --- | --- |
  | E7B | `300fc313f83f26ed` | `853856814f0d9687` |
  | E7T1 | `00b9cde548df6173` | `a9529bf9b69c6052` |
  | E7T2 | `a99a9a7ee29bc750` | `27223e4c92aa897e` |

  - E0 reproduces EXP-006 exactly in every validation evaluation.
- **Comparison:** `9ddf7284e9c26661`, VERIFIED, D-091 v1.
- **Reproduction:** E7B equals E6L (`01bfb1a2643f2e38`) exactly (maximum difference 0.0).

**Results (validation medians over seeds unless stated):**

| | E7B (κ 0) | E7T1 (κ 0.0015) | E7T2 (κ 0.0075) |
| --- | --- | --- | --- |
| Turnover / yr | 17.5 | 15.3 | 2.6 |
| Cost drag (3 years) | 9.64 pp | 7.63 pp | 1.36 pp |
| Net Sharpe | 0.512 | 0.788 | 0.691 |
| Net volatility | 5.55% | 5.57% | 4.55% |
| Net max drawdown | −8.51% | −7.83% | −5.18% |
| Gross cumulative return | 17.33% | 17.62% | 13.28% |
| Target cash / risky HHI | 25.0% / 0.47 | 27.0% / 0.51 | 57.1% / 0.93 |
| Training net Sharpe | 1.267 | 1.310 | 1.026 |

- **Paired turnover (validation):** T1 − B −8.0 a year, T2 − B −19.0; lower in 5/5 seeds for
  both arms (training: 5/5 as well).
- **Paired cost drag (validation):** −3.90 pp and −9.60 pp; lower in 5/5 seeds.
- **Paired net Sharpe (validation):** +0.232 [−0.148, 0.613] and +0.341 [−0.083, 0.765]; 4/5
  seeds each (seed 44 worse for both). **Training:** T1 +0.016 (3/5), T2 −0.304 (0/5).
- **Gross return:** unchanged for T1 (−0.05 pp) and lower for T2 (−5.37 pp, 0/5) on validation.
- **Every arm is below every baseline** (validation Sharpe 1.355 / 1.470 / 1.754).

**Hypotheses:**

| Verdict | Hypotheses |
| --- | --- |
| Supported | H1, H2, H3, H4, H5, H7, H8 |
| Partially supported | H6 (T2's allocation stability D_w is 17% of the control's, below 25%) |

**Outcome A (strong support, mechanical rule).**

**Interpretation:**
- The penalty cuts trading and cost drag robustly, and the cut transfers to validation.
- The validation gain comes from saved costs, not better allocation.
- The strong penalty is worse in-sample in every seed and becomes static, concentrated and
  cash-heavy. The moderate penalty is the balanced setting.
- No significance, no personalisation, and no claim of beating the baselines.

**Full report:** `docs/e7_results.md`. **Figures:** `reports/figures/e7/` (git-ignored).

---

### EXP-017: E7 turnover-aware PPO, real-data pipeline check (smoke; training split; NOT a result)

- **Date:** 2026-11-04. **Author(s):** run by Claude Code under D-084, at a team member's
  instruction (E7 master prompt; author not named; R-S).
- **Git commit:** uncommitted working tree on top of `3483b0f` (`dirty: true` recorded).
- **Config:** `configs/turnover_k{0,1,2}.yaml` (κ = 0, 0.0015, 0.0075; λ = 0; D-091), seeds
  42–46.
- **Data:** dataset `8e00568ee2aa4de7`, training split only; the rows read end before
  2017-01-01.
- **Method:**
  - 3 × 5 smoke runs of 2,048 timesteps each (1.8–1.9 s each);
  - then `evaluate --split train --pipeline-check --execute`, giving `148d05d7a8a69c0b` (E7B),
    `4480c07e86fab2cc` (E7T1) and `71ab2ac63e294b3e` (E7T2), all VERIFIED.
- **Checks:**
  - **E7B:** no turnover-penalty columns or episode keys.
  - **E7T1 and E7T2:** the logged `turnover_penalty` = κ × the logged `traded_notional` in
    every training episode and evaluation episode. The evaluation traded notional equals the
    ledger's recurring traded notional.
- **Observation:** the near-random smoke policies trade about 0.8 of the portfolio per step, so
  their mean episode penalty (0.60 at κ1, 3.0 at κ2) exceeds the magnitude of the base reward.
  This is consistent with the prespecified scale (§3 of the protocol).
- **Results:** none (smoke checkpoints).

---

### EXP-016: E6 fixed risk-aversion dose response, λ = 0, 3, 9 (training and validation; descriptive; simulated)

- **Date:** 2026-11-03, 17:56–19:05 UTC (training and evaluations); analysed 2026-11-04.
- **Author(s):** run by Claude Code under D-084, at a team member's instruction (E6 master
  prompt; author not named; R-S).
- **Git commit:** `698152b` (clean working tree) for training and evaluations.
- **Config files:** `configs/dose_response_l{0,3,9}.yaml`. They differ only in `label` and
  `fixed_lambda` (D-090; fixed before training).
- **Random seeds:** 42–46 per arm. Constant profile input 0.5.
- **Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`.
- **Periods used:** training 2007-07-05 → 2016-12-30; validation 2017-01-03 → 2019-12-31.
  **Test not used:** the rows read end before 2020-01-01.

**Method:**
- **Reward:** r = r_base − (λ/2)·Σ net_return², the E5 implementation.
- **Training:** 15 of 15 `full` runs: 100,352 timesteps and 202 episodes each; 92–402 s each
  (CPU contention from an unrelated process); 0 failures, 0 retries.
  - E6L: ef7ba01aa36b33bc, d2eb7014b3a15b2c, 091b84c67396568a, dbe1de95f7dd6dab,
    d4b5237ddaac4d4f;
  - E6M: 11fc189b5c166e2f, 09e7c05ca7db6adf, c6887b8262367bac, 0fcff8c557e3328c,
    aa8c14e4df2ed907;
  - E6H: 497daee0e33f029e, f0be2a72c80a5107, 45a8d1b124e53d4a, fc9b933d6f18bcf2,
    ede0d617c0cc9d76.
- **Evaluations (VERIFIED):**

  | Arm | Train | Validation |
  | --- | --- | --- |
  | E6L | `b85bc3753249fc83` | `01bfb1a2643f2e38` |
  | E6M | `8203ece24ef46d66` | `4abfb0b026bb2ec5` |
  | E6H | `e20c10e1882d28fb` | `5bb66c096879caaa` |

  - E0 reproduces EXP-006 exactly in every validation evaluation.
- **Comparison:** `0b1860cf0497e504`, VERIFIED, D-090 v1.
- **Reproduction:** E6L and E6H equal E5L and E5H exactly (maximum difference 0.0).

**Results:**

| | Validation (median over seeds) | Training |
| --- | --- | --- |
| Net volatility, λ 0 / 3 / 9 | 5.55% / 5.51% / 4.99% | 13.38% / 11.05% / 9.88% |
| Paired volatility, λ 3 − 0 | −0.20 pp | −1.51 pp |
| Paired volatility, λ 9 − 3 | −0.33 pp | −2.08 pp |
| Paired volatility, λ 9 − 0 | −0.52 pp (median reduction 9.7%) | −3.60 pp (29.2%) |

- **Monotone volatility:** in 4/5 validation seeds and 5/5 training seeds.
- **Validation net Sharpe:** λ 9 − 0 = +0.282 (5/5 seeds); every arm is below the baselines.
- **Allocation:** D_w (λ 0 vs 9) 0.052, below the seed D_w of 0.094.

**Hypotheses:**

| Verdict | Hypotheses |
| --- | --- |
| Supported | H1, H2, H3, H6, H7 |
| Partially supported | H4, H8 |
| Not supported | H5 |

**Outcome B (weak or partial dose response).**

**Interpretation:**
- **In-sample,** λ is a reproducible, graded risk control.
- **Out of sample,** it is monotone in volatility but small, with no consistent allocation
  change.
- **Personalisation:** not tested and not established.

**Full report:** `docs/e6_results.md`. **Figures:** `reports/figures/e6/` (git-ignored).

---

### EXP-015: E6 λ dose response, real-data pipeline check (smoke; training split; NOT a result)

- **Date:** 2026-11-03. **Author(s):** run by Claude Code under D-084, at a team member's
  instruction (E6 master prompt; author not named; R-S).
- **Git commit:** uncommitted working tree on top of `c531911` (`dirty: true` recorded).
- **Config:** `configs/dose_response_l{0,3,9}.yaml` (D-090), seeds 42–46.
- **Data:** dataset `8e00568ee2aa4de7`, training split only; the rows read end before
  2017-01-01.
- **Method:**
  - 3 × 5 smoke runs of 2,048 timesteps each;
  - then `evaluate --split train --pipeline-check --execute`, giving `9e08bdee2bc49431` (E6L),
    `3fc526c1b1b92b13` (E6M) and `e8bb0f64a69318cc` (E6H), all VERIFIED.
- **Checks:**
  - λ is exactly 0, 3 and 9 in every evaluated episode;
  - only centre-profile (0.5) episodes; E0 and the baselines are included.
- **Note:** smoke training took 7.6–8.0 s per run, against 1.7 s in EXP-013. This is consistent
  with CPU contention from an unrelated process on the machine; no code path changed.
- **Results:** none (smoke checkpoints).

---

### EXP-014: E5 fixed risk-aversion PPO, λ = 0 vs λ = 9 (training and validation; descriptive; simulated)

- **Date:** 2026-11-03; training 08:01:24–08:16:16 UTC; evaluations up to 08:16:49 UTC.
- **Author(s):** run by Claude Code under D-084, at a team member's instruction (E5 master
  execution prompt; author not named; R-S).
- **Git commit:** `addcf7b` (clean working tree) for training and evaluations. The comparison
  ran on saved outputs afterwards.
- **Config files:** `configs/fixed_risk_low.yaml` (λ = 0) and `fixed_risk_high.yaml` (λ = 9).
  They differ only in `label` and `fixed_lambda` (checked by `validate_config` and the
  comparison). D-089, fixed before training.
- **Random seeds:** 42–46 per arm. Constant profile input 0.5; no profile sampling.
- **Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`.
- **Periods used:** training 2007-07-05 → 2016-12-30; validation 2017-01-03 → 2019-12-31.
  **Test not used:** the rows read end before 2020-01-01.

**Question and hypotheses:** `docs/e5_fixed_risk_aversion.md` §1 and §4.

**Method:**
- **Reward:** r = r_base − (λ/2)·Σ net_return² (the E4 implementation), λ fixed.
- **Training:** 10 `full` runs, all completed: 100,352 timesteps and 202 episodes each,
  85.9–88.8 s each.
  - E5L: 7a393d5f1cceed1a, 1abfccd67254832b, 1fbbfa5856a35807, a5e06bb681959f4a,
    ff7519f36021c7cb;
  - E5H: 2b36cc3df2033b9a, 5f6454cdbbe2e0b5, b10c77e09537ba5a, 35914f921e295b03,
    9c51b857f83b9971.
- **Evaluations (VERIFIED):** E5L train `771b962770f17efe` and validation `d9067e393b0b26d4`;
  E5H train `3d05b0aefeba01d6` and validation `6a505ae16055c427`.
  - 25 of 25 comparability checks each;
  - **E0 reproduces EXP-006 exactly.**
- **Comparison:** `36c60c635effca26`, VERIFIED, criteria D-089 v1.

**Results (paired E5H − E5L over seeds 42–46; mean ± SD):**

| Metric | Validation | Training |
| --- | --- | --- |
| Net volatility | −0.52 pp ± 0.06; lower in 5/5 (median reduction 9.7%) | −3.60 pp ± 1.35; lower in 5/5 (median reduction 29.2%) |
| Net max drawdown | +0.18 pp, shallower in 2/5 | +6.85 pp, shallower in 5/5 |
| Net Sharpe | +0.282 ± 0.106; higher in 5/5 (median 0.682 vs 0.512) | +0.266 ± 0.127; higher in 5/5 |
| Target equity | −1.17 pp (2/5 higher) | −8.95 pp (0/5 higher) |

- **Allocation:** the cross-arm D_w (0.052) is below the seed-to-seed D_w (0.095).
- **Training records:** the last-50-episode realised-variance ratio E5H/E5L was 0.61–0.66.
- **Against the baselines:** no E5 policy reached any baseline on validation (best 1.223).

**Hypotheses:**

| Verdict | Hypotheses |
| --- | --- |
| Supported | H4, H5, H6 |
| Partially supported | H1, H7 |
| Not supported | H2, H3, H8 |

**Outcome B:** reward sensitivity exists, but is weak out of sample.

**Interpretation:**
- **In-sample,** λ controls risk, reproducibly and interpretably.
- **On validation,** the effect is consistent in sign but small, and not reflected in a stable
  conservative allocation.
- **For E4:** its non-personalisation is mainly a conditioning failure.
- **Personalisation:** not demonstrated.

**Full report:** `docs/e5_results.md`. **Figure:** `reports/figures/e5/` (git-ignored).

---

### EXP-013: E5 fixed risk aversion, real-data pipeline check (smoke; training split; NOT a result)

- **Date:** 2026-11-03. **Author(s):** run by Claude Code under D-084, at a team member's
  instruction (E5 master execution prompt; author not named; R-S).
- **Git commit:** uncommitted working tree on top of `89ebe75` (`dirty: true` recorded).
- **Config:** `configs/fixed_risk_low.yaml` (λ = 0) and `fixed_risk_high.yaml` (λ = 9), seeds
  42–46.
- **Data:** dataset `8e00568ee2aa4de7`, training split only; the rows read end before
  2017-01-01.
- **Method:**
  - 2 × 5 smoke runs of 2,048 timesteps each (`train --arm main --smoke --timesteps 2048
    --execute`);
  - then `evaluate --split train --pipeline-check --execute`, giving `a83f6133c2dcd656` (E5L)
    and `6eaf9db0c17d1d21` (E5H), both VERIFIED.
- **Checks:**
  - λ is exactly 0 (E5L) and 9 (E5H) in every evaluated episode;
  - only centre-profile (0.5) episodes; E0 and the baselines are included;
  - every output verifies.
- **Results:** none (smoke checkpoints).

---

### EXP-012: E4 profile-dependent reward PPO (training and validation; descriptive; simulated)

- **Date:** 2026-11-03.
  - Training: 06:58:54–07:13:57 UTC.
  - Evaluations: up to 07:19:35 UTC.
  - Comparisons: after commit `7903f6c`.
- **Author(s):** run by Claude Code under D-084, at a team member's instruction (E4 master
  execution prompt; author not named; R-S).
- **Git commit:** `82bca2e` (`82bca2e…`, clean working tree) for training and evaluations.
  Comparisons and figures were run from saved outputs at `7903f6c`.
  - Process note: an edit made during training dirtied the tree for a few seconds. It was
    stashed at 06:59:53, before the second run's provenance check. Every run and evaluation
    records `dirty: false`.
- **Config files:** `configs/profile_reward_experiment.yaml` (D-088; fixed before training),
  with `agent.yaml` (configuration 4), `backtest.yaml`, `environment.yaml` and `evaluation.yaml`
  unchanged.
- **Random seeds:** 42–46. Profile stream `default_rng([seed, 5])`. Evaluation profile sets with
  seeds 20261103–20261105, the same as E1.
- **Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`.
- **Periods used:** training 2007-07-05 → 2016-12-30 (496 decisions); validation 2017-01-03 →
  2019-12-31 (156 decisions). **Test not used:** the rows read end before 2020-01-01.

**Question and hypotheses:** see `docs/e4_profile_reward.md` §1 and §6, fixed before training.

**Method**
- **Reward:** r_E4 = r_base − (λ(U)/2)·Σ net_return², with λ = 9·(1 − min(RT, RC)).
- **Training:** 10 `full` runs, all completed: 100,352 timesteps and 202 episodes each,
  87.0–89.6 s each.
  - main: 7897e4dbc0b75d35, ef0471726f4796b3, e318b70ae6f64a16, 7c1a9c28b4c9561a,
    35f1a7760f9aaf33;
  - held-out: 66df7dc70477edba, eac21893088eef47, 1239366219c2124e, ca3d5abb5214be89,
    b78c9c9236689f31.
- **Evaluations:** train `9470b1719f6f9ec7` and validation `948eb21380278b03`, both VERIFIED.
  - 50 of 50 comparability checks against E0 on each split;
  - **E0 reproduces EXP-006 exactly** (maximum absolute Sharpe difference 0.0).
- **Comparisons against E1 (EXP-010):** validation `2b55a054fcf0a51f` and train
  `7982b02a83f54dcf`, both VERIFIED. The criteria are D-088 v1.

**Results, validation (median over seeds, centre profile):**

| Arm | Net Sharpe (range) | Net vol | Net max DD | Turnover / yr | Cost drag |
| --- | --- | --- | --- | --- | --- |
| Baselines | 1.355 / 1.470 / 1.754 | 4.56–6.28% | −7.58% to −11.49% | 0–0.78 | 0.2–0.6 pp |
| E0 | 0.635 (0.253 to 1.149) | 5.61% | −9.24% | 15.9 | 8.4 pp |
| E1 | 0.534 (−0.149 to 1.007) | 5.22% | −7.52% | 19.4 | 10.9 pp |
| **E4** | **0.601 (−0.166 to 1.026)** | 5.16% | −7.49% | 19.9 | 11.2 pp |
| E4H | 0.184 (−0.044 to 1.442) | 4.92% | −9.43% | 19.9 | 10.0 pp |

- **E4 − E1, validation:** Sharpe +0.004 ± 0.043, and the t-interval covers 0 for every metric.
- **E4 − E1, training split:** Sharpe +0.215 ± 0.136, volatility −2.60 pp, maximum drawdown
  +8.9 pp, all in 5 of 5 seeds.
- **Against the baselines:** no E4 main-arm episode beat any baseline. Held-out seed 44 beat
  buy-and-hold in all 65 of its profile episodes and equal-weight in 8 (maximum 1.499).

**Personalisation (validation):**
- **Size:** within-set D_w 0.0109 for E4 vs 0.0115 for E1 (medians); the a = 0 vs 1 contrast
  0.009–0.046, against a seed scale of 0.118.
- **Direction:** ρ(a, equity) was negative in every seed; ρ(a, volatility) was negative in 4 of
  5.
- **Specificity:** the negative controls H, L and G moved the allocation as much as RT and RC.
- **Training diagnostic:** an episode's realised variance was not related to a. The average
  variance fell in 9 of 10 runs.

**Hypotheses:**

| Verdict | Hypotheses |
| --- | --- |
| Supported | H4, H5 |
| Partially supported | H1, H6 |
| Not supported | H2, H3, H7 |

**Exploitation:** none found. Cash > 95% in 2.7% of decisions; maximum weight 0.423; turnover
19.75 vs 19.38; penalty/|base| 0.88–1.02 in training.

**Interpretation:**
- **What changed:** the reward made the policies less risky on average **in-sample**, but did
  not produce profile-dependent, financially aligned behaviour.
- **Validation:** no performance or risk difference from E1 beyond seed noise.
- **Overall:** a negative result for personalisation.

**Limitations:** see `docs/e4_results.md` §10.

**Full report:** `docs/e4_results.md`. **Figures:** `reports/figures/e4_validation/`
(git-ignored).

---

### EXP-011: E4 profile-dependent reward, real-data pipeline check (smoke; training split; NOT a result)

- **Date:** 2026-11-03, 06:44–06:58 UTC. **Author(s):** run by Claude Code under D-084, at a
  team member's instruction (E4 master execution prompt; author not named; R-S).
- **Git commit:** uncommitted working tree on top of `7033618`. `dirty: true` is recorded in the
  outputs.
- **Config:** `configs/profile_reward_experiment.yaml` (D-088), seeds 42–46.
- **Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`. Training split only;
  the rows read end before 2017-01-01.

**Method:**
- 10 smoke runs (2 arms × 5 seeds), 2,048 timesteps each:
  `scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7
  --experiment-config configs/profile_reward_experiment.yaml train --arm {main,heldout}
  --smoke --timesteps 2048 --execute`.
- Then `... evaluate --split train --pipeline-check --execute`, giving evaluation
  `60e2b46f4f2eb286` (803.7 s), VERIFIED.

**Checks (passed):**
- 40 of 40 comparability checks against E0;
- identical environment and simulator ledgers; target recomputation within 1e-6;
- `e4_reward = e4_reward_base − e4_risk_penalty` for every profile episode;
- λ spans 0.54–8.99 across the evaluation profiles;
- `interactions.csv` and `contrasts.csv` written;
- the smoke training records hold per-episode reward components. The mean penalty over mean
  |base reward| was 0.66–1.04 (two runs inspected), consistent with the scale diagnostic (no
  defect).

**Results:** none. The smoke checkpoints (about 2% of the budget) are not reported.

---

### EXP-010: Profile-conditioned PPO E0–E3 (training and validation splits; descriptive; simulated)

- **Date:** 2026-11-03.
  - Training: 05:15–05:33 UTC.
  - Evaluations: 05:33–05:39 UTC; training split 242.6 s, validation 81.4 s.
- **Author(s):** run by Claude Code under D-084, at a team member's instruction ("You may commit
  locally as mandar, then run the profile workflow"; author not named; R-S).
- **Milestone:** Phase P (D-085), steps P2–P5.
- **Git commit:** `d4ad950` (`d4ad9505cfda43e104c92e8a26fcf78eeffbb1f8`), a local commit with a
  **clean working tree**, not pushed.
- **Config files:** `configs/profile_experiment.yaml`, with `agent.yaml` (configuration 4),
  `backtest.yaml`, `environment.yaml` and `evaluation.yaml` unchanged.
- **Random seeds:** 42–46. Profile stream `default_rng([seed, 5])`. Evaluation profile sets with
  seeds 20261103–20261105.
- **Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`.
- **Periods used:**
  - training: decisions 2007-07-05 → 2016-12-30, 496 decisions;
  - validation: decisions 2017-01-03 → 2019-12-31, 156 decisions;
  - **test not used:** rows read end before 2020-01-01.

**Question:** does appending a constant-per-episode investor profile to the observation change
PPO's allocations (behavioural sensitivity), its performance and its risk? Does any such
sensitivity extend to profile combinations not seen in training? Stated in advance: the reward
does not use the profile, so little systematic dependence was expected (D-085).

**Method**
- **Training:** `scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7
  train --arm {main,heldout} --execute`.
  - 10 `full` runs (configuration 4: lr 1e-4, `n_steps` 512, entropy 0, other settings D-074);
  - each 100,352 timesteps and 202 episodes; 84.7–86.9 s each, except main s42 at 254.4 s, the
    first run;
  - main arm: Uniform(0, 1)^5 profiles; held-out arm: the box RT ≥ 0.6 and RC ≤ 0.4 rejected.
  - Run ids:
    - main: e8fb0f9ead93fb35, e317ea6bbe59be5b, 8e71dc2f3e746b3c, bd8d1b4b036c3970,
      8e164387853b7656;
    - heldout: 16faf9c0fbcb4c8e, 7843afca745a4e3f, 4395e6bccd211637, 887d30cf4823b9e4,
      68ad410bc77631f2.
- **Evaluation:** `... evaluate --split train --execute` gives `93cdfece7bca1f77`; `...
  evaluate --split validation --execute` gives `6be9dce1b006008b`.
  - Both VERIFIED (`verify`); one prespecified look each.
  - Deterministic actions; D-076 metrics; profile sets and analyses as in
    `docs/profile_conditioned_ppo.md` §8–§11.
- **Checks:**
  - 50 of 50 comparability checks against E0 on each split;
  - environment and simulator ledgers identical for every episode;
  - batched target recomputation within 1e-6;
  - on validation, **E0 reproduces EXP-006 exactly** (maximum absolute Sharpe difference 0.0,
    every seed);
  - on the training split, the baselines equal EXP-002.

**Results, validation 2017–2019 (unseen market period; net of 15 bps costs):**

| Strategy | Net Sharpe, median over seeds (range) | Turnover / yr, median | Cost drag, median | Net max DD, median | Net vol, median |
| --- | --- | --- | --- | --- | --- |
| Equal weight monthly | 1.470 | 0.22 | 0.32 pp | −10.42% | 5.93% |
| Buy and hold | 1.355 | 0.00 | 0.19 pp | −11.49% | 6.28% |
| Inverse volatility monthly | 1.754 | 0.78 | 0.63 pp | −7.58% | 4.56% |
| **E0** existing PPO, configuration 4 | 0.635 (0.253 to 1.149) | 15.9 | 8.4 pp | −9.24% | 5.61% |
| **E1** profile PPO, centre profile | 0.534 (−0.149 to 1.007) | 19.4 | 10.9 pp | −7.52% | 5.22% |
| **E3** held-out arm, centre profile | 0.311 (−0.007 to 1.157) | 19.6 | 9.3 pp | −9.34% | 5.08% |

Per seed (42–46), validation net Sharpe at the centre profile:
- E1: −0.149, 0.686, 1.007, 0.534, 0.341;
- E3: 0.035, −0.007, 1.157, 0.311, 0.573.

**None of the 650 profile episodes reached any baseline.** The highest was 1.195.

**Behavioural sensitivity (validation, state-matched on each policy's centre trajectory):**
- **Within a set of 32 profiles (`in_distribution`):** median D_w over seeds 0.0115
  (0.0065–0.0165).
- **Between seeds at the same profile:** D_w 0.122 (main) and 0.149 (held-out). Profile-induced
  differences are about **10× smaller** than seed-to-seed differences.
- **Within-seed spread of net Sharpe across the 32 profiles:** SD 0.014–0.036, against a
  between-seed range of −0.149 to 1.007.
- **E2 intervention** on each policy's own trajectory:
  - D_w against the correct profile: neutral 0.005–0.012, shuffled 0.007–0.018;
  - mean equity exposure changes ≤ 0.011 (absolute), mean cash changes ≤ 0.008.
- **One-at-a-time sweeps (0 → 1):** mean over seeds of the change in mean target exposure:
  - RT: equity −0.020, bonds +0.029;
  - RC: equity −0.015;
  - H: equity −0.010;
  - L: cash −0.007;
  - G: equity −0.006.
  - The maximum D_w against the centre profile was ≤ 0.014 in every seed.
- **Rank correlations across the 32 profiles** (median over seeds; seeds with |ρ| > 0.35):

  | Dimension | Correlation with | Median ρ | Seeds with \|ρ\| > 0.35 |
  | --- | --- | --- | --- |
  | RT | bonds | +0.75 | 5 of 5 positive |
  | RT | equity | −0.56 | 4 of 5 negative |
  | RT | cash | −0.65 | 3 negative, 2 positive (mixed) |
  | L | cash | −0.11 | no consistent sign |
  | G | equity | −0.22 | — |
  | L | turnover | −0.56 | 4 of 5 negative |
  | RT | turnover | −0.62 | 3 of 5 negative |

  - The ranks are consistent in places, but the magnitudes are tiny.
  - The RT direction (more bonds, less equity) is the opposite of the conventional reading of
    "risk tolerance".

**Generalisation:**
- **Unseen profile combinations (E3):** the held-out arm's mean net Sharpe over 32 profiles:

  | Split | Unseen box | Training-distribution profiles |
  | --- | --- | --- |
  | Validation (median over seeds) | 0.322 | 0.329 |
  | Training split | 1.156 | 1.164 |

  No gap beyond the within-seed profile spread. (Within-set D_w is lower in the box because the
  box restricts two dimensions; it is not comparable.)
- **Unseen market period:** median net Sharpe falls from the training split to validation:

  | | Training split | Validation |
  | --- | --- | --- |
  | E0 | 1.114 | 0.635 |
  | E1 centre | 1.200 | 0.534 |
  | E3 centre | 1.172 | 0.311 |

  The training-split values are in-sample; the baselines there are 0.516–0.843. The
  market-period gap dominates every profile effect.

**Interpretation:**
1. **Allocations change with the profile, but very little.** The effect is about an order of
   magnitude below seed-to-seed variation, so the policies are nearly profile-invariant. This
   matches the expectation for a task-irrelevant input.
2. **Some rank associations are consistent across seeds** (RT ↔ bonds +). Their size is
   negligible and their direction has no financial meaning. They are learned artefacts, **not
   personalisation**.
3. **Performance:** profile conditioning did not improve validation performance. Median net
   Sharpe was lower than E0 (0.534 vs 0.635), with higher turnover (19.4 vs 15.9) and cost drag
   (10.9 vs 8.4 pp). With five seeds and a seed range wider than 1 Sharpe unit, this difference
   is not distinguishable from seed variation. No inferential test was run.
4. **Against the baselines:** every profile-conditioned policy, like E0, underperformed all
   three baselines on validation net Sharpe.
5. **Generalisation to unseen profile combinations:** shows no degradation. Because the policy
   barely uses the profile, this is uninformative about generalisation as such.

**Limitations:**
- the reward is profile-independent (D-085);
- the profiles are synthetic and uniform;
- one market history and five seeds; descriptive only;
- the 2017–2019 validation period is mostly low-volatility;
- costs, the cap and the universe are provisional;
- D-086 and D-087 choices are not team-reviewed;
- no test-period evaluation of the profile arms (D-086 item 11).

**Next steps (not authorised by this entry):**
- a profile-dependent objective or constraint (E4, or profile-specific risk limits) is required
  for the profile to matter;
- the E0 over-trading problem (D-077) is unaffected and remains the larger issue.

---

### EXP-009: Profile-conditioned PPO, real-data pipeline check (smoke runs; training split only; NOT a result)

- **Date:** 2026-11-03. **Author(s):** run by Claude Code under the standing authority D-084, at
  a team member's instruction ("Master Execution Prompt — Profile-Conditioned PPO"; author not
  named; R-S).
- **Milestone:** Phase P (D-085), step P1 verification.
- **Git commit:** uncommitted working tree on top of `26a2abd`. The `dirty: true` state and diff
  hash are recorded in each output.
- **Config files:** `configs/profile_experiment.yaml` (new), with `agent.yaml`, `backtest.yaml`
  and `environment.yaml` unchanged.
- **Random seeds:** 42–46. Profile stream `default_rng([seed, 5])`.
- **Data:**
  - dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`;
  - the training split only (`train_only=True`). The rows read end before 2017-01-01.
- **Periods used:** training window 2007-07-05 to 2016-12-30 (496 decisions). Validation not
  used. Test not used.

**Question:** does the profile-conditioning code path run end to end on the real data, with
the real EXP-005 checkpoints, without breaking comparability or the data boundaries? This is
a software check, **not** an experiment.

**Method**
1. **Smoke training:**
   - command: `python scripts/profile_experiment.py --dataset-dir
     data/processed/8e00568ee2aa4de7 train --arm {main,heldout} --smoke --timesteps 2048
     --execute`;
   - 10 runs (2 arms × seeds 42–46), 2,048 timesteps each (4 episodes), configuration-4 PPO
     settings, 1.6–1.7 s of training each;
   - output under `data/processed/profile_experiments/` (git-ignored).
   - Run ids:
     - main: 5e9f27cf8b50c9e9, 3842f11fd7e3c118, 998587a338b5a7c6, 1899352c4ec8d552,
       56c061dbc7d9f0df;
     - heldout: 51736fe4ec596051, 2d567f6b73510481, a7d28eea0bce315c, 48d734a5bc78f382,
       a5c5de9fcbc8266e.
2. **Pipeline-check evaluation:**
   - command: `... evaluate --split train --pipeline-check --execute`;
   - evaluation `f9851a8190ae0e5e`, 255.5 s;
   - it re-evaluates the 5 configuration-4 E0 checkpoints (EXP-005), the 3 baselines and the
     10 smoke checkpoints on the training window. Each smoke checkpoint covers the centre
     profile plus 64 profiles.
3. **Verification:** `python scripts/profile_experiment.py verify
   data/processed/profile_evaluations/f9851a8190ae0e5e` → `VERIFIED`.

**Checks (passed):**
- 40 of 40 E0-vs-profile comparability checks. They cover the environment block apart from
  the observation size (+5), the hyperparameters, SB3 constants, scaler, data identity and run
  spec. The budget is not compared in a pipeline check.
- E0 discovery passes the D-076 checkpoint integrity checks for the whole EXP-005 grid.
- For every episode:
  - the environment and simulator ledgers are identical;
  - the batched recomputation of the targets matches within 1e-6.
- 658 episode rows: 3 baselines + 5 E0 + 650 profile episodes; 496 decisions each; dates
  2007-07-06 to 2016-12-30.
- **Integrity only:** the three baselines reproduce EXP-002's training values exactly (net
  Sharpe 0.516 / 0.534 / 0.843; net cumulative return 61.06% / 52.49% / 71.55%; net maximum
  drawdown −28.51% / −24.44% / −18.64%).

**Results:** **none.**
- The checkpoints have about 2% of the configured budget. Their numbers describe nearly
  untrained policies and must not be reported, plotted or compared.
- The E0 rows are a training-period evaluation of configuration 4, produced only as part of
  this check. They are not reported here; D-078 stays Proposed.

**Limitations:**
- uncommitted code;
- smoke checkpoints only;
- no validation look (validation is refused for pipeline checks by design).

**Next steps** (blocked: full training needs a clean committed tree, D-075):
1. Commit, with permission and authorship (D-070).
2. Train full runs:
   `train --arm main --execute`, then `train --arm heldout --execute` (about 14 minutes in
   total).
3. Evaluate on the training split, then on validation (one prespecified look each).
4. Verify both evaluations.

---

### EXP-008: Regime-conditioned description of the conventional baselines (training split only)

- **Date:** 2026-10-21. **Author(s):** run by Claude Code at a team member's request
  (milestone E). No authorisation was needed beyond development use of training data; no
  validation or test values were read.
- **Numbering:** EXP-007 is reserved for the D-078 diagnostic (Proposed, not run).
- **Code:** uncommitted working tree on top of `0f8341b`; the state is recorded in each
  analysis's `metadata.json` (`dirty: true` with a diff hash).
- **Command:** `python scripts/explain.py baselines-train --backtest-dir
  data/processed/backtests/c6d8c473258e3194 --dataset-dir data/processed/8e00568ee2aa4de7`.
  It was also run via `python scripts/workflow.py explain`, including once from a clean virtual
  environment.
- **Data:**
  - EXP-002 backtest `c6d8c473258e3194`: only lines labelled `train` are parsed;
  - feature set `a79347e37e653703`: regime labels through the `train_only` bounded loader with
    `assert_training_only`;
  - dataset `8e00568ee2aa4de7`;
  - window 2007-07-06 to 2016-12-30.
- **Method:** `docs/explainability.md` §2.1 (D-080, Proposed): the label at *t* − 1; the
  funding row excluded; all 9 regimes and `unavailable` reported; small-sample flag below 63
  sessions.
- **Outputs:** `data/processed/explainability/1d0548a0ca7857c4/` (git-ignored):
  `regime_summary.csv`, `analysis.json`, `metadata.json`, and 8 figures with provenance
  sidecars.
  - The same numbers (identical `regime_summary.csv`, SHA-256 prefix `cec980c0aaa45559`) are
    also in `1d162803d2c77633`, `b527bb03e40ec9e8` and `6de3011ab784feee`.
  - `1d162803d2c77633` was produced before a legend-only figure fix and is superseded.
  - The others differ only in the recorded uncommitted-code state or environment. None was
    deleted.
- **Checks:**
  - 229 executions lie exactly 1 session after their decision dates;
  - 0 test rows read; 0 validation values parsed;
  - the "all" rows equal EXP-002's training annualised traded notional, annualised volatility
    and return periods exactly;
  - the regime rows partition the totals.

**Results (observed; descriptive; training split; simulated):**
- **Sessions per regime:**

  | Regime | Sessions | Episodes |
  | --- | --- | --- |
  | `negative_low` | 38 | 12 (small) |
  | `negative_normal` | 113 | 29 |
  | `negative_high` | 435 | 43 |
  | `neutral_low` | 332 | 48 |
  | `neutral_normal` | 303 | 58 |
  | `neutral_high` | 182 | 51 |
  | `positive_low` | 409 | 47 |
  | `positive_normal` | 377 | 57 |
  | `positive_high` | 201 | 24 |
  | `unavailable` | 0 | 0 |

  In total there are 2,390 sessions in 369 episodes.
- **Realised annualised volatility in `negative_high`:** buy-and-hold 0.140, equal weight
  monthly 0.183, inverse volatility 0.104. The all-session values are 0.091, 0.109 and 0.071.
- **Inverse volatility allocation:** SPY 0.089 in `negative_high` vs 0.121 in `negative_low`;
  IEF 0.279 and TLT 0.144 in `negative_high`.
- **Turnover in `negative_high`:** annualised 1.27 for inverse volatility and 0.69 for equal
  weight monthly. The all-session values are 0.84 and 0.37; buy-and-hold is 0.
- **Risky exposure:** 1.0 everywhere (the baselines never hold cash).

**Interpretation:**
- These are mechanical behaviours of known rules on one path.
- Volatility by volatility regime is partly mechanical, because the labels come from trailing
  market volatility.
- No confidence intervals; differences between regimes are not tested.
- **They say nothing about the PPO policy.** The PPO analysis on validation decisions (D-068)
  is implemented but not authorised.

**Limitations:**
- one path; few episodes in some regimes;
- the regime thresholds are relative to the training period (D-045, Proposed);
- run from uncommitted code.

**Next steps (not authorised):** re-run after a commit, for clean provenance. The policy
analysis needs an explicit authorisation (see `docs/explainability.md` §5).

*Re-run (2026-10-21, appended):* `data/processed/explainability/b89e6b0c03289d34/`, using
the same command (training rows only, 0 validation values parsed, 0 test rows). It adds:
- **path drawdown per regime:** the mean and deepest level of the window's net drawdown on
  the rows in the regime;
- the regime-threshold artifact SHA-256 (`5fc00522…16d7`) in its identity.

**Checks:**
- every earlier column is identical to `1d0548a0ca7857c4`;
- the all-session deepest drawdown equals EXP-002's training net maximum drawdown exactly:
  −0.2851 (equal weight monthly), −0.2444 (buy-and-hold), −0.1864 (inverse volatility).

**Observed:**
- that deepest level falls on `negative_high`-labelled rows for all three baselines;
- mean path drawdown in `negative_high`: −0.087, −0.071 and −0.047 respectively.

Drawdown levels are **path-dependent**: a level reached while a label holds is not a loss
caused by that regime. The run was from uncommitted code. It supersedes the earlier
analyses for display; all are kept.

---

### EXP-006: PPO validation evaluation and configuration selection (validation 2017–2019 only)

- **Date:** run on 2026-10-21 (UTC): command 10:48:31Z–10:48:41Z, evaluation 4.9 s.
- **Author(s):** run by Claude Code at the request of a team member. The member explicitly
  authorised execution in the session, naming the evaluation id, protocol hash, commit, grid
  and dataset. The message does not name its author; it was recorded under R-S (D-061), and the
  other teammate's confirmation was not sought.
- **Milestone:** C, validation evaluation and selection under the accepted protocol D-076.
- **Git commit:** `0f8341b` (`0f8341bb1c5026e6fef6939a0326c1bf30668541`), **clean working
  tree**, recorded in the evaluation identity.
- **Evaluation:**
  - id `1ce9c490ed03c8c9`, protocol hash `e652adec1095c95a` (protocol version 1). Both match
    the approved read-only plan;
  - checkpoints: the 40 final checkpoints of grid `0f1c47502dc30d84` (EXP-005), all verified
    before and after.
- **Command:** `python scripts/evaluate_validation.py --execute --confirm-validation-evaluation
  --dataset-dir data/processed/8e00568ee2aa4de7`. Exit 0.
- **Data:** processed dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`.
  - Rows read only before 2020-01-01, checked against the configured dates and labels.
  - Evaluation window: first decision 2017-01-03, funding execution 2017-01-04, last return
    2019-12-31 (753 ledger rows), identical for all 43 strategies.
- **Periods used:** **validation only** (2017-01-03 to 2019-12-31). **The test period
  (2020–2024) was not loaded, evaluated or inspected.**
- **Protocol (D-076, accepted 2026-10-21):**
  - deterministic actions; start in cash with the funding trade charged; 15 bps; mark to market
    at 2019-12-31;
  - annualised net Sharpe with N = 252 and rf = 0, excluding the funding row;
  - median over seeds 42–46; tie tolerance 1e-9, then lower learning rate → smaller `n_steps`
    → lower entropy coefficient;
  - stop on any undefined metric.
  - **The protocol was not changed after the results were seen.**

**Question.** Under the frozen D-076 rule, which D-066 configuration has the highest median
validation net Sharpe? How do the policies compare with the three baselines on identical dates
and conventions?

**Results (observed; validation split, net of costs)**

Per configuration: annualised net Sharpe for each seed, and the summary.

| Configuration | Learning rate | `n_steps` | Entropy coefficient | Seed 42 | Seed 43 | Seed 44 | Seed 45 | Seed 46 | **Median** | Mean | Std (ddof=1) | Min | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 3e-4 | 512 | 0 | 0.626 | 0.362 | 0.587 | −0.063 | 0.462 | **0.462** | 0.395 | 0.276 | −0.063 | 0.626 |
| 1 | 3e-4 | 512 | 0.01 | 0.727 | −0.006 | 1.227 | 0.356 | 0.351 | **0.356** | 0.531 | 0.468 | −0.006 | 1.227 |
| 2 | 3e-4 | 1024 | 0 | 0.678 | 0.421 | 0.293 | 0.111 | 0.338 | **0.338** | 0.368 | 0.207 | 0.111 | 0.678 |
| 3 | 3e-4 | 1024 | 0.01 | 0.604 | 0.149 | 0.269 | 0.091 | 0.417 | **0.269** | 0.306 | 0.208 | 0.091 | 0.604 |
| **4** | **1e-4** | **512** | **0** | 1.149 | 0.486 | 0.635 | 0.253 | 0.731 | **0.635** | 0.651 | 0.332 | 0.253 | 1.149 |
| 5 | 1e-4 | 512 | 0.01 | 1.094 | 0.498 | 0.489 | 0.228 | 0.728 | **0.498** | 0.607 | 0.325 | 0.228 | 1.094 |
| 6 | 1e-4 | 1024 | 0 | 0.926 | 0.019 | 0.796 | 0.085 | 0.446 | **0.446** | 0.454 | 0.408 | 0.019 | 0.926 |
| 7 | 1e-4 | 1024 | 0.01 | 0.975 | 0.081 | 0.844 | 0.034 | 0.484 | **0.484** | 0.484 | 0.429 | 0.034 | 0.975 |

**Selection:**
- **configuration 4** (learning rate 1e-4, `n_steps` 512, entropy coefficient 0), median
  0.6351 (0.635095);
- no tie: the next median is 0.4979 (configuration 5);
- selected checkpoints, configuration 4: seed 42 `c12145d46246e1c7`, 43 `4f9be9680a6334bd`,
  44 `e9819a04ccc36567`, 45 `9f585486f8b4ce4b`, 46 `8d929082251f7c7f`. Model SHA-256 values are
  in `metadata.json`.

Baselines and the selected configuration, on the same window:

| Strategy | Net Sharpe | Net cumulative return | Net CAGR | Net annualised volatility | Net max drawdown | Gross cumulative return | Cost drag | Annualised traded notional | Executions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Equal weight monthly | 1.470 | 28.81% | 8.84% | 5.93% | −10.42% | 29.13% | 0.32 pp | 0.22 | 36 |
| Equal-weight buy and hold | 1.355 | 27.96% | 8.60% | 6.28% | −11.49% | 28.15% | 0.19 pp | 0.00 | 1 |
| Inverse volatility monthly | 1.754 | 26.37% | 8.15% | 4.56% | −7.58% | 27.01% | 0.63 pp | 0.78 | 36 |
| PPO c4, seed 42 | 1.149 | 21.14% | 6.63% | 5.76% | −8.62% | 28.68% | 7.54 pp | 13.34 | 156 |
| PPO c4, seed 43 | 0.486 | 9.90% | 3.21% | 7.07% | −10.71% | 19.54% | 9.65 pp | 18.61 | 156 |
| PPO c4, seed 44 | 0.635 | 10.60% | 3.43% | 5.61% | −11.05% | 21.52% | 10.92 pp | 20.85 | 156 |
| PPO c4, seed 45 | 0.253 | 3.57% | 1.18% | 5.28% | −6.99% | 10.74% | 7.18 pp | 14.82 | 156 |
| PPO c4, seed 46 | 0.731 | 12.24% | 3.94% | 5.55% | −9.24% | 20.64% | 8.40 pp | 15.89 | 156 |

- The baseline values equal EXP-002's validation results exactly (same conventions).
- **Across all 40 policies:**
  - net Sharpe −0.063 to 1.227 (median 0.454);
  - net cumulative return −2.07% to 25.80%;
  - gross cumulative return 6.77% to 40.82%;
  - cost drag 6.99 to 15.03 pp;
  - net max drawdown −5.99% to −17.33%;
  - annualised traded notional 13.3 to 27.9;
  - 156 weekly executions each.
- **Allocation of all 40 policies** (mean end-of-row weight): SPY 0.206, EFA 0.058, EEM 0.067,
  IEF 0.107, TLT 0.143, LQD 0.036, GLD 0.032, **cash 0.351**.
- **Configuration 4 seeds:** mean cash 0.28–0.49. Holdings drifted up to 0.41 per asset between
  executions (the 0.40 cap applies to targets, D-057).

**Observations (facts from the outputs).**
1. **No policy reached the net Sharpe of any baseline.** The highest single policy (c1 s44,
   1.227) is below the lowest baseline (buy and hold, 1.355). The selected configuration's
   median (0.635) is below all three.
2. **Before costs the gap is smaller but remains.** Only 5 of 40 policies had a gross cumulative
   return above the lowest baseline's gross return (27.01%).
3. **The policies traded heavily.** Their annualised traded notional was 13–28× the portfolio,
   against at most 0.78× for the baselines, and their cost drag was 7–15 percentage points over
   the window.
4. **Seed variation is large.** Within a configuration, net Sharpe ranges up to 1.23 (c1);
   configuration 4 ranges from 0.25 to 1.15.

**Interpretation (tentative, not tested).**
- The turnover and cost figures suggest that weekly rebalancing with near-full reallocation
  is a major contributor to the shortfall. The gross figures show it is not the only one.
- This is consistent with a policy that is noisy and over-fitted to one training path.
- None of these causes has been isolated. No sensitivity analysis or ablation was run, and
  none is authorised.

**Limitations.**
- One validation period (2017–2019), one dataset, deterministic actions only, and selection by
  a single metric. There is no statistical test (Gate 3 bootstrap settings are still open).
- The baselines are untuned.
- With 40 policies on one window, the best policies and the selected configuration's median are
  likely to be optimistic estimates of how the policy would perform on new data (a selection
  effect).
- **These are validation results used for selection. They are not test results, not evidence
  of out-of-sample performance, and not financial advice.**

**Verification (independent, read-only).** 25 checks passed:
- the 7 output files, with hashes matching the metadata;
- evaluation id = hash(identity) = folder name;
- protocol hash reproduced; clean commit;
- 40 checkpoints = the manifest, with the model hashes unchanged and the manifest hash
  unchanged;
- every value finite, and the `notes` empty (no undefined metric);
- 43 ledgers with identical dates, all inside validation, none from 2020 or later;
- every Sharpe recomputed from its ledger: bit-identical with `sharpe_ratio` on the rows after
  funding;
- the selection recomputed independently;
- baselines equal to EXP-002;
- an in-memory rerun with **every 2020+ row replaced by undecodable bytes** reproduced every
  policy Sharpe and the selection exactly. No test row was used.

**Outputs:**
- `data/processed/evaluations/1ce9c490ed03c8c9/`: `evaluation.json`, `policy_metrics.csv`,
  `baseline_metrics.csv`, `configuration_summary.csv`, `allocations.csv`, `ledgers.csv`,
  `metadata.json` (folder fingerprint `2d69c405a8e5a764`);
- execution log: `data/processed/evaluation_logs/1ce9c490ed03c8c9-execute.log`;
- all git-ignored.

**Next steps (team decisions; none authorised).**
- Whether and how to proceed to the sealed test evaluation (Gate 3: bootstrap settings, stress
  windows, pre-registration), given that configuration 4 is selected but trails all three
  baselines on validation.
- *Follow-up analysis (2026-10-21, appended):*
  - The entry was reconciled against the saved artifacts: 166 values, no discrepancy beyond
    display rounding.
  - A turnover and cost diagnostic from the saved artifacts only (no new run, no test data) is
    in `docs/exp006_turnover_diagnostic.md`. Its outputs are in
    `data/processed/diagnostics/turnover_1ce9c490ed03c8c9/` (git-ignored).
  - Follow-up experiments are proposed as D-077 (not approved).
- *Clarification (2026-10-21, appended, Phase D audit):*
  - In this entry, "annualised traded notional" (policies 13.3–27.9; baselines 0.22 and
    0.78) is recurring ETF traded notional per year: the initial funding trade and the cash leg are excluded. This is checked from the saved metrics: annualised = recurring /
    752 × 252, and total = funding + recurring.
  - The integrity of the evaluation outputs, the 40 checkpoints and the grid manifest was
    re-verified without rerunning the evaluation (project journal, same date).
- Any cost or turnover sensitivity or redesign would be new work, needing its own decisions.
  It must not be tuned on the test period.

---

### EXP-005: Full D-066 PPO training grid, 40 runs (training split only; trained, not evaluated)

- **Date:** run on 2026-10-20 (UTC): 22:13:44Z–23:11:38Z (57 min 54 s). Recorded on 2026-10-21.
- **Author(s):** run by Claude Code at the request of a team member. In the session, the member
  answered "Launch the full grid" to an explicit approval question naming the grid, commit and
  settings. The message does not name its author; it was recorded under R-S (D-061), and the
  other teammate's confirmation was not sought.
- **Milestone:** M5.3: the D-066 training grid. **Training only**: no policy was evaluated and
  no configuration was selected.
- **Git commit:** `cc9784b` (`cc9784b98a8c4ec2b3ac88ce797d15dc4f6621b3`), **clean working tree**.
  The commit is in every run identity and in the grid id. It was not yet pushed when the grid
  ran.
- **Grid:** `0f1c47502dc30d84`; manifest at
  `data/processed/experiments/grids/0f1c47502dc30d84/manifest.json`.
- **Config files (SHA-256 prefixes of the working copies at run time):**
  - `agent.yaml` `cf3d767a1b222389`;
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb`.

  These are identical to EXP-004. The line-ending note there applies.
- **Random seeds:** 42, 43, 44, 45, 46 for every configuration (D-066).
- **Data:** processed dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`, loaded with
  `train_only=True`; 2,517 rows, 2007-01-04 to 2016-12-30.
- **Periods used:** **train only.** Each episode runs from decision 2007-07-05 to 2016-12-30.
  Validation and test values were not loaded or parsed.

**Question.** Train every D-066 configuration and seed on the training split under the accepted
execution policy (D-075). This is a training step; the results needed for selection (median
validation net Sharpe, D-066) are not part of it.

**Method.**
- **Command:** `python scripts/run_grid.py --execute --confirm-full-grid --dataset-dir
  data/processed/8e00568ee2aa4de7`.
- **Execution:** sequential; each run in a child process with `PYTHONHASHSEED=0` and a 900 s
  hard limit; stop at the first failure (none occurred).
- **Runs:** 8 configurations (learning rate {3e-4, 1e-4} × `n_steps` {512, 1024} × entropy
  coefficient {0, 0.01}, `batch_size` 64) × 5 seeds = 40 `full` runs with a 100,000-timestep
  budget each.
- **Settings:** the pinned settings (D-074), one torch thread,
  `torch.use_deterministic_algorithms(True)`.
- **Environment:** weekly decisions, lag 1, 15 bps, actions in `[−1, 1]` scaled ×5 (D-072).
- **Versions:** Stable-Baselines3 2.9.0, torch 2.14.1+cpu, Gymnasium 1.4.0, Python 3.13.7,
  Windows 11.

**Results (execution diagnostics only)**

| Item | Value |
| --- | --- |
| Runs completed / failed / attempts | **40 / 0 / 40** (no retries; runner exit 0; nothing quarantined) |
| Timesteps per run | **100,352** for all 40 runs (see the note below) |
| Training episodes per run | 202 completed (496 steps each) |
| Child-process time per run | min 80.4 s, median 83.0 s, max 235.5 s (c0 s42, the first run); total 3,470 s |
| Training wall time per run | min 76.5 s, median 79.1 s, max 229.3 s; total 3,311 s |
| Environment steps per second | min 437.6 (c0 s42), median 1,268.6, max 1,311.3 |
| Independent verification (`verify_grid.py`) | **40/40 runs passed; no problems** |
| Storage | about 11 MB for `data/processed/experiments/` (all runs) |

- **The independent verification checked, for every run:**
  - manifest status `completed` with a single completed attempt;
  - `run_safety.verify_run_dir` valid;
  - `run_id` equal to the identity hash and the folder name;
  - run spec equal to the D-066 configuration and seed, run kind `full`, budget 100,000;
  - code provenance equal to the clean `cc9784b`;
  - the deterministic-algorithms setting recorded;
  - pinned settings equal to `agent.yaml`;
  - data 2007-01-04 to 2016-12-30 (2,517 rows), with the training-line hashes of the four input
    files reproducing;
  - the scaler equal to the run config and fitted on training rows only (2,389 rows). It is one
    identical scaler for all 40 runs;
  - the checkpoint reloads with matching learning rate, `n_steps`, entropy coefficient and
    seed, finite weights and the `[−1, 1]` action space;
  - monitor rewards finite, every episode 496 steps, and episode counts matching the metadata.
- **Timestep note.** Stable-Baselines3 stops only after a complete rollout, so every run did
  100,352 timesteps: 196 × 512 or 98 × 1024. That is 352 more than the 100,000 budget (+0.35%),
  identical for all configurations and seeds. It is recorded here for the team, not changed.
- **Earlier outputs:** EXP-003 folders unchanged (`da738d8728a41f4e`); EXP-004 folder unchanged
  (`dd79f9e5dd837946`).
- **Logs:**
  - runner log at `data/processed/grid_logs/0f1c47502dc30d84-runner.log`;
  - one child log per run under `data/processed/experiments/grids/0f1c47502dc30d84/logs/`;
  - all git-ignored.
- **Run ids** (configuration: seed and run id):
  - c0: s42 `0f0e3865f322bb50`; s43 `50c87a250e26d231`; s44 `6fb9a9fd05e90a9b`;
    s45 `3bb1373b092bcd41`; s46 `be9599d9ff60cee0`
  - c1: s42 `ab299094121dbe7f`; s43 `f4cebc59c0b09255`; s44 `49939c7aa87413ac`;
    s45 `635096bc56deec6e`; s46 `f628c54f5b5b3693`
  - c2: s42 `5e95542366a5c2e6`; s43 `d9c972997ad6ecc0`; s44 `fed57b758969289a`;
    s45 `df59b44fa6f66948`; s46 `46a71af10378f1a4`
  - c3: s42 `bb95040edb112d30`; s43 `4c0b18c370d7bac6`; s44 `64bcf8642643a08a`;
    s45 `057b43075f480ab0`; s46 `dfd93db6f445172c`
  - c4: s42 `c12145d46246e1c7`; s43 `4f9be9680a6334bd`; s44 `e9819a04ccc36567`;
    s45 `9f585486f8b4ce4b`; s46 `8d929082251f7c7f`
  - c5: s42 `05ae6384c7f46fe0`; s43 `466aeeeb8b133e7b`; s44 `2ddeed5b510cf4eb`;
    s45 `7b75d47261a98e93`; s46 `26d128a131c83a63`
  - c6: s42 `183b5c0bf02a2f5e`; s43 `60f4d9e08713949c`; s44 `e6136843d31a5c18`;
    s45 `cd53a0bf1fba1eb6`; s46 `ebbde71cbdb55568`
  - c7: s42 `e2bc9a0387a8caee`; s43 `90cbda70224c331d`; s44 `06d56cf4abb2a559`;
    s45 `cfca6f8a07857b93`; s46 `13bb90916c3afbcb`

**Observations (not explained).**
- The grid took about 0.96 h, at the low end of the approximate 0.9–3.5 h estimate.
- The first run (c0 s42) was about three times slower than the other 39 (229 s of training
  versus about 77–81 s). Its cause, e.g. warm-up or machine load, is not established.
  - *Correction (2026-10-21, Milestone A close-out audit):* the other 39 runs took 76.5–79.7 s
    of training wall time and 80.4–83.7 s of child-process time, not "about 77–81 s". The
    comparison is unchanged: c0 s42 took 229.3 s of training, against a median of 79.1 s for
    all 40 runs.

**Interpretation.**
- The grid trained to completion under the accepted safeguards, and every output verifies.
- No policy has been evaluated. Training-episode rewards were checked only for being finite.
  They are training-split diagnostics and are **not** reported or interpreted as investment
  performance.
- These checkpoints are not results until evaluated under an approved protocol.

**Next steps.** Each needs a separate team decision or authorisation:
1. The operational definition of the selection metric and the evaluation policy: deterministic
   or stochastic actions, the validation window and funding, ties.
2. Authorisation to load validation data and run validation evaluation and selection (D-066).
3. Gate 3 items: bootstrap settings and stress windows.
4. Whether the 100,352-timestep note needs any record beyond this entry.

The test period stays sealed.

---

### EXP-004: Post-commit PPO smoke run on committed code (training split only; execution check, not a result)

- **Date:** run on 2026-10-19 (UTC): driver 17:29:03Z–17:29:12Z; training 17:29:08Z–17:29:11Z.
  Recorded on 2026-10-20.
- **Author(s):** run by Claude Code at the request of a team member, who approved this single run
  in the session. The message does not name its author; it was recorded under R-S (D-061), and
  the other teammate's confirmation was not sought.
- **Milestone:** M5.3. This is the final pre-grid check of the committed pipeline. It is **not**
  a grid run, and the 40-run grid was not started.
- **Git commit:** `20fe0b0` (`20fe0b021490de171c90849520b5906baa81553a`), **clean working tree**,
  checked before the run and recorded in the run identity:
  `code = {git_available: true, commit: 20fe0b0…, dirty: false}`.
- **Config files (SHA-256 prefixes of the working copies at run time):**
  - `agent.yaml` `cf3d767a1b222389`;
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb`.

  `backtest.yaml` and `environment.yaml` differ from their committed blobs only in line endings
  (CRLF in the Windows working copy): their LF-normalised hashes are identical, and
  `git diff HEAD -- configs` is empty. `agent.yaml` differs from EXP-003's `fb5cac2b0491bcb8`
  only through the later `execution` section and approval comments (D-074, D-075). Its grid,
  seeds, budget and pinned training settings are unchanged.
- **Random seed:** 42.
- **Data:** processed dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`, loaded with
  `train_only=True`; 2,517 rows, 2007-01-04 to 2016-12-30.
- **Periods used:** **train only.** The episode runs from decision 2007-07-05 to 2016-12-30.
  Validation and test values were not loaded or parsed.

**Question.** Does the committed pipeline (`20fe0b0`) complete a short training run end to end,
including the paths EXP-003 did not exercise?
- `torch.use_deterministic_algorithms(True)`;
- the per-run lock and exclusive finalisation;
- the grid runner's child-process launcher;
- code provenance in the run identity.

**Method.**
- **Driver:** a one-off script outside the repository launched **one** child process with the
  grid runner's launcher command, `python -m adaptive_portfolio.agents.ppo` with
  `PYTHONHASHSEED=0`, plus `--smoke --timesteps 4096`.
- **Timeout:** 600 s hard limit through the repository's `run_safety.run_with_timeout`.
- **Failure policy:** quarantine through `recover_stale` if the run failed, with no retry; it was
  not needed.
- **Watching:** while the child ran, the driver recorded whether the run's lock and staging
  directory existed.
- **Settings:** configuration 0 (learning rate 3e-4, `n_steps` 512, entropy coefficient 0), seed
  42, 4,096 timesteps, one torch thread. Other settings as in `agent.yaml` (D-074).
- **Environment:** weekly decisions, lag 1, 15 bps, actions in `[−1, 1]` scaled ×5 (D-072).
- **Versions:** Stable-Baselines3 2.9.0, torch 2.14.1+cpu, Gymnasium 1.4.0, Python 3.13.7,
  Windows 11.

**Results (execution diagnostics only)**

| Item | Value |
| --- | --- |
| Run id | `7d49ee0f53d6165e` (run kind `smoke`) |
| Status / child exit code / timed out | completed / 0 / no |
| Timesteps / training episodes | exactly 4,096 / 8 completed (496 steps each) |
| Total child-process time / training wall time | 7.6 s (7.632 s) / 3.4 s (3.414 s) |
| Environment steps per second (training) | 1,199.8 |
| Output checks (`verify_run.py`) | **28/28 passed** |
| Safety checks (`smoke_extra_checks.py`) | **12/12 passed** |

- **The 28 output checks** confirmed:
  - exactly the five run files, with no staging directory left;
  - `run_id` equals the folder name and the hash of the run config;
  - metadata matching the run identity, and output file hashes reproducing;
  - 4,096 timesteps;
  - data ending on 2016-12-30, with the training-line hashes reproducing (2,517 rows; later rows
    not read);
  - a training-only scaler (2,389 rows) matching the run config;
  - the checkpoint reloads with 4,096 timesteps, matching settings, finite weights and the
    `[−1, 1]` action space;
  - all logged training-episode rewards finite.
- **The 12 safety checks** confirmed:
  - child exit 0 within 600 s, and `run_safety.verify_run_dir` valid;
  - code provenance equal to the clean `HEAD` commit;
  - the deterministic-algorithms setting recorded in the run identity;
  - the per-run lock observed during the run and held by the child process (pid 20336), not
    the driver (pid 24336);
  - the staging directory `7d49ee0f53d6165e.staging-20336` observed;
  - after the run, the finalised folder present with no lock or staging directory (exclusive
    finalisation into an absent destination);
  - nothing quarantined;
  - no error in the child log;
  - the working tree still clean.
- **Deterministic algorithms** (`torch.use_deterministic_algorithms(True)`) were enabled during
  training. Training completed without raising, so no non-deterministic operation was hit.
- **Outputs:** `data/processed/experiments/7d49ee0f53d6165e/`.
- **Evidence:** `data/processed/smoke_checks/20261019T172904Z-c0-s42-7d49ee0f53d6165e.log` and
  `data/processed/smoke_checks/20261019T172904Z-7d49ee0f53d6165e-evidence.json` (git-ignored).
- **EXP-003 output folders** `d06b6c2971f6ff66` and `4ddbffd78cddcb65` were **unchanged**:
  combined SHA-256 `da738d8728a41f4e` before and after, and both re-verified 28/28.
- **Not exercised:**
  - the refusal to finalise into an existing destination (covered by unit tests only);
  - the grid manifest, because the grid runner launches only full runs.

**Reproducibility observation (this machine and configuration only).**
- The final model weights and the training episode-reward sequence of this run were
  **bit-identical** to those of EXP-003 Run A (`d06b6c2971f6ff66`).
- Run A used the same configuration, seed and budget, but a pre-hardening working tree, the
  determinism flag off, a different launch path and no fixed `PYTHONHASHSEED`.
- This is consistent with (a) the hardening not changing the training computation, and (b) a
  seeded run reproducing in a fresh process on this machine.
- It is one comparison on one machine, configuration and library set. It is **not** a general
  guarantee of reproducibility across machines, library versions or other configurations.
- The rewards are training-split execution diagnostics, **not** evidence of investment
  performance.

**Throughput observation (not explained).**
- Training ran at about 1,200 steps/s, versus about 320 in EXP-003, with the same library
  versions and one torch thread.
- Machine load or power state at the time is a plausible factor, but this run does not establish
  the cause.
- The approximate full-grid estimate (4.0 million steps, sequential) therefore ranges from
  about 0.9 h (at ~1,200 steps/s) to about 3.5 h (at ~320 steps/s). It is an extrapolation from
  three short runs. No budget change is proposed.

**Interpretation.** The committed pipeline runs end to end on the training split with its safety
features active. Nothing here evaluates a policy or says anything about portfolio performance.

**Next steps.**
- The team commits this entry; the grid id will change with the commit.
- Then `run_grid.py --plan` must show "allowed".
- The full 40-run grid needs separate explicit approval.

---

### EXP-003: M5.3 PPO throughput smoke test (training split only; execution check, not a result)

- **Date:** 2026-10-19. Run A 2026-10-19T10:39:58Z–10:40:11Z; Run B 10:40:48Z–10:41:01Z.
- **Author(s):** run by Claude Code at the request of a team member. The message approving
  both runs does not name its author; it was recorded under R-S (D-061), and the other
  teammate's confirmation was not sought.
- **Milestone:** M5.3 preparation (roadmap 4/6). It checks the throughput assumption behind the
  D-066 budget **before** any tuning.
- **Git commit:** code at `c1c1925` plus **uncommitted** M5.1–M5.3 working-tree changes. Record
  the commit hash here once the team commits them.
  - *Correction (2026-10-19, after the commit and push):*
    - The exact working-tree state that ran EXP-003 was **never committed as such**.
    - The code was committed later as `71e6333` and `85c40d1`, with documentation in `c387459`
      and `8da032a`, all pushed. Those commits also contain the pre-grid hardening done after
      EXP-003: run locks, exclusive finalisation, quarantine, code provenance in the run
      identity, and `torch.use_deterministic_algorithms(True)` during training.
    - According to the session record in the project journal, the hardening did not change
      the training computation path used here: the environment, simulator, reward and pinned
      PPO settings. This cannot be checked by a commit comparison, because the intermediate
      state was never committed.
    - **EXP-003 predates the deterministic-algorithm setting:**
      `torch.use_deterministic_algorithms(True)` was **not active** during these runs.
    - Separately, the run configs have no code hash, because they predate D-075.
    - The nearest committed code is `85c40d1`.
- **Config files (SHA-256 prefixes at run time):**
  - `agent.yaml` `fb5cac2b0491bcb8`;
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb`.
- **Random seed:** 42, for both runs.
- **Data:**
  - processed dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`, loaded with
    `train_only=True`;
  - 2,517 rows, 2007-01-04 to 2016-12-30;
  - training-line SHA-256 values are recorded in each run's `run_config.json`.
- **Periods used:** **train only.** The episode runs from decision 2007-07-05 to 2016-12-30.
  Validation and test values were not used, and none was loaded or parsed.

**Question.** Does the PPO pipeline run end to end, and what is its throughput (environment
steps per second) on one CPU thread? The answer is used to judge whether the D-066 budget is
feasible: 100,000 steps × 8 configurations × 5 seeds = 4.0 million steps.

**Method.**
- Stable-Baselines3 2.9.0 PPO, torch 2.14.1+cpu, Gymnasium 1.4.0, Python 3.13.7, Windows 11.
  One torch thread; 16 logical CPUs present; one run at a time.
- Settings: `run_kind: smoke`, 4,096 timesteps each, other settings as in `agent.yaml` (D-074
  pinned defaults).
- Weekly decisions, lag 1, 15 bps, actions in `[−1, 1]` scaled ×5 (D-072).
- Each run had a 10-minute hard limit (`timeout 600`). The outputs were then checked
  independently: 28 checks per run.

**Results (execution diagnostics only)**

| Run | Configuration | `n_steps` | Run id | Status | Timesteps | Training wall time | Env steps/s | Episodes | Process time incl. start-up |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0 (lr 3e-4, ent 0) | 512 | `d06b6c2971f6ff66` | completed | 4,096 | 12.802 s | 319.9 | 8 | ≈ 18 s |
| B | 2 (lr 3e-4, ent 0) | 1024 | `4ddbffd78cddcb65` | completed | 4,096 | 12.649 s | 323.8 | 8 | ≈ 17 s |

- **Both runs passed all 28 checks:**
  - exactly the five output files, no staging folder left, the folder name equal to the
    identity hash;
  - metadata containing the identical identity, file hashes reproduced, status `completed`,
    4,096 timesteps;
  - data ending 2016-12-30, with the training-line hashes reproduced;
  - a train-only scaler (2,389 rows) matching the run config;
  - a checkpoint that reloads with 4,096 timesteps, the matching hyperparameters, finite
    weights and the `[−1, 1]` action space;
  - every logged training-episode reward finite, and every completed episode 496 steps long.
- Each run completed 8 training episodes (3,968 steps); the remaining 128 steps were part of an
  unfinished ninth episode. `n_steps` 512 versus 1024 made no material speed difference: Run B
  was 1.2 % faster than Run A.
- Training-episode rewards were checked only for being finite. They are **not** reported or
  interpreted: these are 4,096-step runs, on training data, never evaluated.

**Approximate estimate for the full D-066 budget** (an extrapolation, not a measurement)
- At the mean measured 321.9 steps/s:
  - 4.0 million steps take about 12,400 s, i.e. **about 3.5 hours** of training when run
    sequentially on one thread;
  - plus about 5 s of start-up per run, about 3 minutes in total;
  - one 100,000-step run takes about 5.2 minutes.
- **Caveats:**
  - two short runs only;
  - sustained speed over 100,000 steps can differ (machine load, thermal limits, memory);
  - 16 CPUs could run several single-thread runs in parallel, which is not measured and
    needs approval.
- This lies within the design memo's assumed range (0.6–4 h, item 9). **No budget change is
  proposed.**

*Note (2026-10-19, after the pre-grid hardening): these two run configs predate D-075. They
contain no Git commit or working-tree hash; their code state is the one stated above. Their
folders are preserved unchanged (SHA-256 of all files checked).*

**Interpretation.** The pipeline runs end to end on the training split, and its outputs are
complete and reproducible. Throughput is at the low end of the memo's assumption, but the
D-066 budget stays practical. Nothing here says anything about portfolio performance.

**Next steps.** Any full run, the 40-run grid, tuning or validation evaluation each need separate
approval. Full runs would need a time limit larger than the smoke test's 10 minutes; at about
5.2 minutes per run, 15 minutes per run is a reasonable limit.

---

### EXP-002: Primary-convention conventional baselines, train and validation (Gate 1)

- **Date:** 2026-10-19 (local time; run at 2026-10-18T22:11Z)
- **Author(s):** run by Claude Code at the request of Parv Patel and Mandar Patil, after both
  confirmed Gate 1 on 2026-10-19. That approval evidence is self-declared in a shared-device
  session; see `approval_checklist.md` §0.1.
- **Milestone:** roadmap 4–5 (primary baseline record before any RL work)
- **Approval:** the run used only decisions recorded as Accepted on 2026-10-19:
  - D-007, D-009, D-010, D-013, D-015, D-023, D-031 (cost basis, no cap);
  - D-035–D-039, D-048–D-060.

  D-006, D-008, D-034, D-042 and D-044 are **acknowledged as provisional**, not validated.
- **Git commit:** code at `8e52693` plus **uncommitted** working-tree changes. Those were
  approval-neutral output wording, a test update, `periods_per_year: 252` and documentation;
  none changes computed values. Record the commit hash here once the team commits them.
  - *Correction (2026-10-19, pre-grid hardening): those changes were committed locally as
    `04dc44a` (`feat: record Gate 1 approvals, run EXP-002 baselines and prepare Gate 2
    packet`), which is not yet pushed. The code state of EXP-002 is therefore `04dc44a`.*
  - *Correction (2026-10-19, after the push): `04dc44a` was pushed to `origin/main` on
    2026-10-19, together with the later commits up to `8da032a`.*
- **Config files (SHA-256 prefixes at run time):**
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb` (used only for the window check).
- **Seeds:** none; the run is deterministic.
- **Data:**
  - processed dataset `8e00568ee2aa4de7`, from raw snapshot `e27437b97742fa43` (yfinance 1.7.0,
    retrieved 2026-10-15T10:21:14Z);
  - SPY, EFA, EEM, IEF, TLT, LQD, GLD; daily adjusted close. Read offline; no download.
- **Periods used:**
  - **train:** decisions from 2007-07-05 (126-session common window), returns earned
    2007-07-06 to 2016-12-30 (2,390 return periods);
  - **validation:** decisions from 2017-01-03, returns earned 2017-01-04 to 2019-12-31 (752);
  - **test: not used.** No `--include-test`; test-period return values were never parsed
    (D-060).
- **Command:**
  `python scripts/market_data.py --config-dir configs backtest --dataset-dir data/processed/8e00568ee2aa4de7`
- **Output:** `data/processed/backtests/c6d8c473258e3194/` (git-ignored). SHA-256 prefixes:
  - `ledger.csv` `ae141edb87a3f524`;
  - `executions.csv` `f604b0340b72d652`;
  - `metrics.json` `d6924a0511e6eee6`;
  - `metrics.csv` `b57f69a701ba27e2`;
  - `backtest_report.md` `951c56f0ce1e7653`;
  - `metadata.json` `30aba7b2885a198b`.
- **Software:** Python 3.13.7, numpy 2.5.4, pandas 3.0.6, adaptive_portfolio 0.1.0 (Windows).

**Question**
What do the three approved conventional baselines achieve on train and validation under the
primary convention (lag 1, 15 bps, 126-session window, N = 252)? This is the reference record
for any later comparison. No hypothesis about which strategy is better is tested, and nothing
was tuned.

**Method**
- **Strategies:** `equal_weight_monthly`, `buy_and_hold_equal_weight`,
  `inverse_volatility_monthly` (63-session lookback, cap 0.40).
- **Rules:** long-only; Σw ≤ 1 with cash at rf = 0; funding trade charged.
- **Protocol:** each split simulated independently from 100,000 in cash.
- **Metrics:**
  - per-session metrics, plus annualised metrics with N = 252, using √252 scaling and CAGR over
    the return periods;
  - Sharpe uses rf = 0 and excludes the funding row;
  - cumulative return and drawdown include the funding cost;
  - turnover is traded notional; annualised turnover counts recurring trades only.

**Results** (net of costs unless stated; descriptive; single historical path; no significance
testing)

| Split | Strategy | Rebal. | Gross cum. | Net cum. | Cost drag | Net max DD | Ann. return | Ann. vol | Ann. Sharpe (rf 0) | Recurring notional | Ann. recurring turnover | Total cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | equal_weight_monthly | 114 | 62.15 % | 61.06 % | 1.09 pp | −28.51 % | 5.15 % | 10.93 % | 0.516 | 3.503 | 0.369 | 0.675 % |
| train | buy_and_hold_equal_weight | 1 | 52.72 % | 52.49 % | 0.23 pp | −24.44 % | 4.55 % | 9.15 % | 0.534 | 0.000 | 0.000 | 0.150 % |
| train | inverse_volatility_monthly | 114 | 73.88 % | 71.55 % | 2.33 pp | −18.64 % | 5.85 % | 7.06 % | 0.843 | 7.979 | 0.841 | 1.347 % |
| validation | equal_weight_monthly | 36 | 29.13 % | 28.81 % | 0.32 pp | −10.42 % | 8.84 % | 5.93 % | 1.470 | 0.662 | 0.222 | 0.249 % |
| validation | buy_and_hold_equal_weight | 1 | 28.15 % | 27.96 % | 0.19 pp | −11.49 % | 8.60 % | 6.28 % | 1.355 | 0.000 | 0.000 | 0.150 % |
| validation | inverse_volatility_monthly | 36 | 27.01 % | 26.37 % | 0.63 pp | −7.58 % | 8.15 % | 4.56 % | 1.754 | 2.334 | 0.782 | 0.500 % |

- **Notes on the table:**
  - "Rebal." counts executions, including the funding trade.
  - Total traded notional = 1.0 (funding) + recurring.
  - Total cost is the sum of cost fractions, funding included.
  - No decision was dropped at split ends.
- **Per-session values** (rf 0), net volatility / net Sharpe:
  - train: 0.689 % / 0.0325, 0.576 % / 0.0336, 0.445 % / 0.0531;
  - validation: 0.373 % / 0.0926, 0.396 % / 0.0853, 0.287 % / 0.1105;

  in the table's strategy order.

**Verification (all passed)**
- outputs contain train and validation only, with every ledger date before 2020;
- all values are finite;
- the three strategies have identical dates in each split;
- each of the 302 executions happens exactly one session after its decision;
- every row's gross return was recomputed as the previous row's weights × that row's returns;
- cost = 15 bps × traded notional, net = g − c(1 + g), and the value path compounds from
  100,000;
- funding: notional 1.0 (within 1e-12), gross 0, cost 0.0015 on the first row;
- recurring turnover is 0 for buy-and-hold;
- cost drag > 0;
- targets are within [0, 0.40] with Σ ≤ 1;
- annualised Sharpe was recomputed as √252 × mean / std;
- metadata ids match;
- the output status text claims no approval state;
- **an identical re-run reproduced all six files byte for byte.**

**Interpretation (descriptive only)**
- **Inverse volatility:**
  - in both splits it had the smallest maximum drawdown and the lowest volatility;
  - it also traded about 2–3.5× the recurring notional of monthly equal weight and had the
    largest cost drag;
  - its annualised Sharpe (rf 0) was the highest of the three in both splits.
- **Cumulative return** ranks differ between splits: inverse volatility first in train, last in
  validation.
- **These are single historical paths** under placeholder costs and rf = 0, with no confidence
  intervals. **They do not show that any strategy is better,** and nothing here concerns PPO,
  which has not been implemented.
- **Compared with EXP-001** (lag 0, 62-row window), the figures differ modestly; the two runs
  use different conventions and windows and are not a controlled comparison.

**Limitations**
- Provisional data values (universe, date range, provider, validation thresholds, feature
  windows).
- Placeholder cost rates; rf = 0 for cash and Sharpe.
- Close-to-close execution, even at lag 1.
- √N annualisation assumes independent returns; untuned baselines; survivorship and selection
  bias in an ETF universe chosen with hindsight.
- Approval evidence self-declared, not technically verified.

**Next steps**
- The team commits the working-tree changes and records the commit hash above.
- Gate 2 (PPO design) decisions and dependency authorisation; then PPO training on train and
  validation only.
- The test split stays sealed until Gate 3.

### EXP-001: Conventional baselines on the training and validation splits (milestone 4)

- **Date:** 2026-10-15
- **Author(s):** project team (run by Claude Code at the team's request; to be checked by the team)
- **Milestone:** roadmap 4–5 (team milestone 4: portfolio simulation and conventional baselines)
- **Git commit:** none. Uncommitted working tree on top of `adffff5`; record the commit hash when
  the team commits.
- **Config files:** `configs/backtest.yaml`, `configs/environment.yaml`, `configs/data.yaml`,
  `configs/experiment.yaml` (defaults, unchanged)
- **Random seed(s):** not applicable (deterministic; no randomness)
- **Data:** yfinance live snapshot, raw id `e27437b97742fa43`, processed id `8e00568ee2aa4de7`.
  Universe SPY, EFA, EEM, IEF, TLT, LQD, GLD (provisional, D-034); daily adjusted close,
  2007–2024.
- **Backtest id:** `ac2d6b163d4f5e4b` (pipeline version 1); outputs in
  `data/processed/backtests/ac2d6b163d4f5e4b/` (git-ignored); reruns byte-identical.
- **Periods used:** train 2007-04-04 → 2016-12-30 (common start after 62 warm-up rows);
  validation 2017-01-03 → 2019-12-31. **Test: computed by the command but not reported here**
  (see D-051 open question).

**Question**
Does the simulator produce consistent, reproducible baseline results under the proposed
conventions? This is a pipeline check and a reference point. It is not a hypothesis about which
strategy is better, and no parameter was tuned.

**Method**
The three baselines of D-053:
- timing D-048 with lag 0;
- costs D-049: 10 + 5 bps on traded notional, including initial funding;
- constraints D-050: long-only, max weight 0.40, cash at rf 0;
- protocol D-051: independent per split, starting from cash.

**Assumptions and known limitations**
- All conventions are Proposed. Costs, cap and universe are provisional.
- Close-to-close execution at lag 0 is optimistic.
- Metrics are per session because D-023 is open: no annualised return, volatility or Sharpe is
  reported.
- Sortino is not implemented.

**Results** (net of costs unless stated; per-session values not annualised; descriptive only)

| Split | Strategy | Rebalances | Gross cum. | Net cum. | Cost drag | Net max DD | Net vol / session | Net Sharpe / session (rf 0) | Traded notional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | equal_weight_monthly | 117 | 66.93 % | 65.78 % | 1.15 pp | −28.56 % | 0.68 % | 0.034 | 4.60 |
| train | buy_and_hold_equal_weight | 1 | 54.39 % | 54.16 % | 0.23 pp | −25.94 % | 0.60 % | 0.032 | 1.00 |
| train | inverse_volatility_monthly | 117 | 73.73 % | 71.38 % | 2.36 pp | −18.15 % | 0.44 % | 0.052 | 9.11 |
| validation | equal_weight_monthly | 36 | 29.81 % | 29.48 % | 0.33 pp | −10.29 % | 0.37 % | 0.095 | 1.69 |
| validation | buy_and_hold_equal_weight | 1 | 28.85 % | 28.65 % | 0.19 pp | −11.51 % | 0.40 % | 0.087 | 1.00 |
| validation | inverse_volatility_monthly | 36 | 27.34 % | 26.71 % | 0.63 pp | −7.54 % | 0.29 % | 0.112 | 3.29 |

"Rebalances" counts executions, including the initial funding. No decisions were dropped at
split ends.

**Independent checks:**
- buy-and-hold matches its closed form;
- equal-weight monthly matches a separately written loop;
- inverse-volatility weights match a hand computation.
All agree to about 1e-8. Figures: none produced.

**Interpretation**
- The pipeline runs offline, deterministically, and agrees with independent recomputation.
- Differences between strategies are single-path historical outcomes under provisional costs
  and timing. They have no significance test, no annualisation and no test-period evidence.
  **They do not show that any strategy is better.**
- Descriptively: inverse volatility traded about twice the notional of equal weight and had
  the largest cost drag, and it had the smallest drawdowns in both splits.
- The ordering of cumulative returns differs between train and validation.

**Next steps**
- Team decisions on D-048 to D-054 and D-023.
- Decide whether test-split evaluation becomes opt-in.
- Lag-1 and cost-sensitivity runs if approved.

**Correction (2026-10-18), added after the milestone-4 audit; the entry above is unchanged:**
- **Git commit:** the code and configs used are those committed as `a7134b7` ("feat: add
  portfolio simulator and conventional baselines"), pushed to `origin/main`. GitHub Actions CI
  passed on that commit.
- The read-only audit (2026-10-18) re-ran the backtest from `a7134b7` in an isolated copy. All
  outputs were byte-identical except the `dataset_dir` path in `metadata.json`.
- **Timing:** this run used `execution_lag_sessions: 0`. Under D-055 (Proposed, 2026-10-18) lag 1
  is the proposed primary convention, and lag 0 an idealised sensitivity case. The figures above
  are therefore the **lag-0 sensitivity case**. No lag-1 run has been made or reported yet.
- **Test split:** this run (pipeline version 1) also computed test-split results, which were
  printed to the console during the milestone-4 session. They exist in a git-ignored local folder
  (`data/processed/backtests/ac2d6b163d4f5e4b/`). They are not recorded here, were not used for any
  choice, and must not be reported. From pipeline version 2 (D-056), test evaluation is opt-in.
- **Weight cap:** inverse-volatility holdings exceeded the 0.40 cap between rebalances (up to
  about 0.4117 on 19 training-split ledger rows; test-split rows are not reported). The cap
  applies to target weights at execution (D-057, Proposed).

**Correction (2026-10-18, milestone 4.2), appended; the entries above are unchanged:**
- **Commit hashes:** the commit cited above as `a7134b7` was rewritten on 2026-10-18 with
  changed author and committer metadata and force-pushed as `66f9ed7`. The file tree is
  identical, so the code and configs used by EXP-001 are unchanged. The original commit remains
  on the local branch `backup/main-before-author-rewrite`. CI passed on `a7134b7` (run #3) and
  on the current head `880d82c` (run #6). No separate run exists for `66f9ed7`.
- **Evaluation window:** EXP-001 used the milestone-4 common start (first training decision
  2007-04-04, 62 warm-up rows). Under the proposed D-058 the training window would start on
  2007-07-05. EXP-001 is not a record of the proposed primary protocol, which uses lag 1 and the
  126-session window.
