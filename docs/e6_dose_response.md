# E6: fixed risk-aversion dose–response PPO, prespecified methodology (D-090)

> **Status:** written and fixed on 2026-11-03, **before any E6 implementation run or
> training**.
> - **Experiment IDs:** EXP-015 (pipeline check) and EXP-016 (full experiment).
> - **Scope:** authorised by a team member's in-session instruction (R-S).
> - **Criteria:** Provisional (delegated) choices by Claude Code (D-090). They are not
>   team-reviewed.
> - **E6 is a fixed-risk sensitivity experiment.** It does **not** test investor personalisation.
> - **Research only;** not financial advice.

## 1. Research question

Does PPO show a **reproducible, monotonic dose–response** between a fixed risk-aversion
coefficient λ ∈ {0, 3, 9} and portfolio risk, and does it transfer to validation?

## 2. Motivation (E5, EXP-014)

- **λ = 9 vs λ = 0, in every seed:**
  - training split: volatility −3.6 pp, drawdown 6.9 pp shallower, equity −9 pp;
  - validation: volatility −0.52 pp (median reduction 9.7%).
- **But on validation:** allocation differences were below seed-to-seed variation, and drawdowns
  did not improve consistently. The outcome was B.
- **Open questions:** is the response graded (does an intermediate λ give an intermediate
  response), or is it an endpoint effect? And how much of it transfers?

## 3. Audit (repository at `c531911`, clean, level with `origin/main`)

| Item | Value |
| --- | --- |
| Dataset | `8e00568ee2aa4de7` |
| Feature set | `a79347e37e653703` |
| Splits | Train 2007-01-01 → 2016-12-31 (decisions 2007-07-05 → 2016-12-30, 496); validation 2017-01-01 → 2019-12-31 (decisions 2017-01-03 → 2019-12-31, 156); test 2020–2024, **sealed** |
| PPO | Configuration 4 (lr 1e-4, `n_steps` 512, entropy 0; D-074 settings), 56 inputs (E4/E5 architecture) |
| Budget | Configured 100,000 timesteps. SB3 completes whole 512-step rollouts, so 100,352 are realised (as E5) |
| Reward | E5's: `ProfileRewardSpec(acceptance="fixed", fixed_lambda=λ)`, i.e. r = r_base − (λ/2)·Σ net_return² over the step's own ledger rows. λ = 0, 3 and 9 resolve exactly (checked) |
| Profile input | Constant 0.5, every episode (`distribution: constant`) |
| Metrics available | Net Sharpe, net and gross cumulative return, annualised return, annualised volatility, net and gross maximum drawdown, cost drag, traded notional, turnover, held and target weights, exposures, risky HHI, stability, realised variance and reward components |
| Not available | **Downside risk / Sortino.** Excluded from the evaluator (D-076, G3-20) and not added for E6 |

## 4. Arms

| Arm | λ | Configuration |
| --- | --- | --- |
| E6L | 0 | `configs/dose_response_l0.yaml` |
| E6M | 3 | `configs/dose_response_l3.yaml` |
| E6H | 9 | `configs/dose_response_l9.yaml` |

- **The only difference:** the three files differ **only** in `label` and `reward.fixed_lambda`
  (checked by `validate_config` and the comparison).
- **Not changed:** the dataset, features, architecture, reward formulation, accounting, costs,
  action space, budget and evaluation, which are all as E5.
- **Seeds:** 42–46 per arm, giving 15 full runs.
- **Outputs:** written under `data/processed/dose_response_*`. The E5 records are untouched.
- **Reproducibility check (not a hypothesis):** E6L and E6H reuse E5L's and E5H's exact
  settings, so training is expected to reproduce E5's validation metrics. The comparison
  reports the maximum absolute difference against the E5 evaluations.

## 5. Hypotheses and prespecified criteria

**Conventions:**
- **Pairing:** seed s pairs the three arms' policies with the same seed.
- **Volatility** is annualised net volatility (the primary risk metric).
- "≥ 4/5" means at least 4 of 5 seeds.
- **Primary split:** validation, unless stated.
- **Relative reduction:** r(a→b) = 1 − vol_b / vol_a.

| | Hypothesis | Criterion (supported if all parts hold) |
| --- | --- | --- |
| H1 | Monotonic risk response | Validation: vol(0) > vol(3) > vol(9) within seed in ≥ 4/5 seeds, and the arm medians are strictly decreasing |
| H2 | Informative intermediate arm | Validation: vol(3) strictly between vol(0) and vol(9) in ≥ 4/5 seeds, and the median fraction f = (vol0 − vol3)/(vol0 − vol9) lies in [0.1, 0.9] |
| H3 | Reproducible direction | Each of vol(3) < vol(0), vol(9) < vol(3) and vol(9) < vol(0) holds in ≥ 4/5 seeds on **both** splits |
| H4 | Transfer to validation | The median validation r(0→9) is > 0 and ≥ 50% of the median training r(0→9), and vol(9) < vol(0) in ≥ 4/5 validation seeds |
| H5 | Allocation response | The median paired allocation D_w between λ = 0 and λ = 9 (mean held weights, 7 ETFs + cash) exceeds the median within-arm seed-to-seed D_w (pooled over the three arms), and target equity is lower at λ = 9 than at λ = 0 in ≥ 4/5 seeds |
| H6 | No excess trading or cost | Median turnover at λ = 3 and at λ = 9 each ≤ 1.25 × λ = 0, and median cost drag each ≤ λ = 0 + 1 pp |
| H7 | No risk-adjusted cost | The median paired net Sharpe difference is ≥ 0 for λ = 3 − 0 and for λ = 9 − 0 |
| H8 | Practically meaningful | The median validation reduction in volatility from λ = 0 to λ = 9 is ≥ 0.5 pp a year **and** ≥ 10% (the E5 thresholds), and the mean paired reduction exceeds the median within-arm seed SD of volatility |

**Drawdown and realised variance:**
- Both are reported for each comparison.
- They are not required to be monotone, because a maximum drawdown is a single-path extreme;
  E5 already showed that it need not follow volatility.

**Downside risk:** not available (see §3).

**Return and Sharpe:** reported descriptively, with no assumed direction.

**Outcome classification** (mechanical; applied to the verdicts above):
- **A, strong dose response:** H1, H2, H3, H4 and H6 supported, and at least one of H5 and H8
  supported.
- **C, no convincing dose response:** H1 not supported **and** H4 not supported. ("Not
  supported" means that no part holds; "partially supported" does not count as not supported.)
- **B, weak or partial dose response:** otherwise.

## 6. Statistics

- **Paired seed differences:** λ = 3 − 0, λ = 9 − 3 and λ = 9 − 0, on both splits.
- **Reported:** seed values, mean, SD (ddof 1), median, range, sign count, a descriptive
  t-interval (t₀.₉₇₅,₄ = 2.776), and an effect size d = mean / SD of the paired differences.
- **Variation measures:** the within-arm seed SD and the between-arm allocation D_w.
- **Caveats:**
  - the five seeds share **one** market history. They measure reproducibility across random
    initialisation, **not** generalisation across market regimes;
  - no p-values and no significance claims.

## 7. Procedure

```text
python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/dose_response_l{0,3,9}.yaml train --arm main --execute
python scripts/profile_experiment.py ... --experiment-config configs/dose_response_l{0,3,9}.yaml evaluate --split {train,validation} --execute
python scripts/profile_experiment.py ... compare-dose --validation <l0> <l3> <l9> --train <l0> <l3> <l9> --e5-validation <E5L> <E5H> --execute
```

**Reproducibility requirements:**
- full runs only from a clean commit;
- write-once outputs;
- every output verified;
- E0 must reproduce EXP-006 in every validation evaluation;
- no working-tree edits while training runs.

## 8. Test-period boundary

- No test-period row is read: training uses `train_only`, and validation uses `exclude_test`
  with explicit boundary checks.
- No test evaluation; no coefficient is chosen from any result.
- Test performance remains **unmeasured**.

## 9. Limitations known in advance

- **Coverage:** three λ values on one market history, so the shape of the curve is only coarsely
  resolved.
- **Seeds:** five; they test robustness to initialisation only.
- **Validation:** a mostly low-volatility period.
- **Design:** the constant profile carries no information, so the policies are not
  investor-specific.
- **Inherited:** E0's over-trading.
- **Downside risk:** unavailable.
