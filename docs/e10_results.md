# E10 results: walk-forward validation of the moderate turnover penalty (EXP-024)

> **Status (2026-11-04):** complete on training and validation splits inside 2007–2019.
> - **Methodology:** `docs/e10_walk_forward_protocol.md` (D-094), committed before implementation
>   (`3019f46`); no amendments. **Pipeline check:** EXP-023 (not a result).
> - **Test period:** sealed. Test performance is **unmeasured**.
> - **D-018** (walk-forward scheme) **stays open**, and D-009 is unchanged.
> - **Research only;** simulated backtests on one market history; not financial advice.
> - **Traceability:** every number comes from the verified comparison `fb8de80f69600763` (§10).

## 1. Executive summary

**Question:** does κ = 0.0015 improve validation net performance over κ = 0 in several historical
periods, or is the E9 result specific to 2017–2019?

**Design:**
- **Folds:** three expanding walk-forward folds inside 2007–2019, with three-year validation
  windows:
  - **A:** 2011–2013;
  - **B:** 2014–2016;
  - **C:** 2017–2019 (= D-009).
- **Arms and seeds:** E10B (κ = 0) and E10T1 (κ = 0.0015), λ = 0; seeds 42–46, paired within each
  fold.
- **Runs:** **30 full runs** of 100,352 timesteps and 12 evaluations, all verified, with no
  failures or retries.
- **Fold inputs:** folds A and B use fold-specific datasets and regime thresholds, with no row on
  or after 2020-01-01. Fold C is the existing D-009 setup.

**Prespecified outcome: Walk-forward confirmation.** H1–H10 are all supported.

**Verified results (validation, E10T1 − E10B, five paired seeds per fold):**

| Fold (validation) | Control mean Sharpe | Treatment mean Sharpe | Mean ΔSharpe (median) | Seeds + / − | Bootstrap 95% CI | Mean Δ ann. net return |
| --- | --- | --- | --- | --- | --- | --- |
| A (2011–2013) | −0.114 | −0.032 | **+0.082** (+0.040) | 5 / 0 | [0.016, 0.148] | +1.12 pp (5 / 0) |
| B (2014–2016) | −0.041 | +0.180 | **+0.221** (+0.169) | 5 / 0 | [0.112, 0.330] | +1.78 pp (5 / 0) |
| C (2017–2019; = E8) | 0.430 | 0.662 | **+0.232** (+0.211) | 4 / 1 | [−0.016, 0.484] | +1.23 pp (4 / 1) |

- **Direction:** the effect has the same sign in every fold, and **14 of 15** pairs are
  positive. The fold means are +0.08 / +0.22 / +0.23 (range 0.15). No fold dominates (shares 15%
  / 41% / 43%).
- **Secondary stratified sign-flip test** (2¹⁵ assignments): p = 0.002. This carries the
  dependence caveat.
- **Fold-level permutation p:** ≥ 0.0625 by construction, so it is descriptive.
- **Mechanism:**
  - **Costs:** cost drag falls by 2.8–3.9 pp in every seed of every fold.
  - **Turnover:** falls by about 6.5–8 a year.
  - **Volatility and drawdowns:** both fall.
  - **Gross return:** does not fall (+0.5 / +2.5 / −0.05 pp).
- **Composition:**
  - **Cash and concentration:** rise in every fold (cash +6–8 pp, risky HHI +0.07–0.11).
  - **Limits:** they stay inside E8's limits.
  - **Responsiveness:** kept (dispersion 86–95%, meaningful changes 78–92% of the control's).
- **Reproduction (H9):** fold C equals E8B/E8T1 (28 metrics) and E7B/E7T1 (26 metrics) exactly.
  The fold A and B leakage checks all pass.

**Essential context (verified):**
- **Losses in A and B:** both arms **lose money** out of sample in folds A and B. In fold A the
  mean annualised net return is −2.1% (control) vs −1.0% (treatment). The penalty mainly makes the
  policy **lose less**.
- **Overfitting:** in-sample the same policies show net Sharpe of about 2.9 (fold A) and 2.0
  (fold B), so the short training histories produce severe overfitting.
- **No in-sample gain:** the penalty does not change in-sample Sharpe in any fold.
- **Baselines:** every fold's simple baselines are far above both PPO arms. Fold A: 0.64–0.94;
  fold B: 0.46–0.61; fold C: 1.36–1.75.

**Interpretation:**
- On this market history the moderate penalty's net-Sharpe advantage **generalises across three
  validation periods**. It is a consistent cost and volatility effect, not better allocation.
- This strengthens the case for κ = 0.0015 as the default PPO setting.
- It does **not** make PPO a viable strategy: PPO underperforms simple baselines in every period
  and loses money in two of three.

**Main limitation:**
- **One market history:** the folds share training rows; five seeds per fold.
- **Fold C:** it repeats E8 by design.
- **Fold A:** its effect is small (median +0.04).
- **No test-period evidence.**

**Recommended next step (§9):** investigate the in-sample/out-of-sample gap (overfitting) rather
than tune κ further.

## 2. Protocol

| Item | Value |
| --- | --- |
| Decision / experiments | D-094 (Provisional (delegated); D-018 open); EXP-023 pipeline check; EXP-024 full experiment |
| Arms | E10B κ = 0, E10T1 κ = 0.0015; λ = 0; configuration 4; constant profile 0.5; `configs/walk_forward_{a,b,c}_k{0,1}.yaml` (equal to E8B/E8T1 except `label` and `walk_forward_fold`) |
| Seeds | 42–46 in every fold and arm; paired within a fold; run ids unique across folds |
| Budget | 100,352 timesteps per run (548 / 296 / 202 episodes in folds A / B / C) |
| Statistics | Within fold: mean, median, SD, SE, sign counts, percentile bootstrap (10,000, seed 20261104), t-interval (df 4), exact permutation p (2⁵). Across folds: fold classes and range; one secondary stratified sign-flip test (2¹⁵). No practical Sharpe threshold exists |
| Outcome rule | Confirmation: all three folds positive (mean ΔSharpe > 0 and ≥ 4/5 seeds positive) **and** mean Δ return > 0 in all folds |

## 3. Folds, boundaries and verification

| Fold | Training rows (dates; rows) | Validation (dates; rows) | Holdout (never evaluated) | Dataset / features | Decisions per episode | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| A | 2007-01-04 → 2010-12-31; 1,007 | 2011-01-03 → 2013-12-31; 754 | 2014–2019 | `f7625695086aee81` / `61236f217f987d35` (thresholds fitted 2007–2010) | 183 | byte-exact parent prefix; fold labels; features equal parent exactly; no 2020+ row |
| B | 2007-01-04 → 2013-12-31; 1,761 | 2014-01-02 → 2016-12-30; 756 | 2017–2019 | `f3499a79c3a186c8` / `072593754556eced` (thresholds fitted 2007–2013) | 339 | as A |
| C | 2007-01-04 → 2016-12-30; 2,517 | 2017-01-03 → 2019-12-31; 754 | sealed test (not read) | `8e00568ee2aa4de7` / `a79347e37e653703` (D-009) | 496 | reference: equals D-009; reproduces E8 and E7 exactly |

**Window checks:**
- Every evaluation's window lies inside its fold's split.
- **Rows read:**
  - training reads only rows before the fold's validation start;
  - validation reads only rows before the holdout start (A: 2014-01-01; B: 2017-01-01; C:
    2020-01-01).
- **E0:** used only in fold C, where it reproduces EXP-006. Fold A and B runs pass the
  within-fold comparability checks (35 of 35 each).

## 4. Fold-level results (validation; means over seeds, medians in brackets)

| Metric (unit; better) | Fold A control → treatment | Δ mean (+ / −) | Fold B control → treatment | Δ mean (+ / −) | Fold C control → treatment | Δ mean (+ / −) |
| --- | --- | --- | --- | --- | --- | --- |
| Net Sharpe (higher) | −0.114 → −0.032 [−0.103 → −0.056] | +0.082 (5/0) | −0.041 → 0.180 [−0.212 → 0.005] | +0.221 (5/0) | 0.430 → 0.662 [0.511 → 0.788] | +0.232 (4/1) |
| Ann. net return (higher) | −2.08% → −0.95% | +1.12 pp (5/0) | −1.01% → +0.77% | +1.78 pp (5/0) | 2.29% → 3.53% | +1.23 pp (4/1) |
| Gross cumulative return, 3 years (higher) | 4.68% → 5.22% | +0.54 pp (3/2) | 10.70% → 13.23% | +2.54 pp (4/1) | 18.21% → 18.16% | −0.05 pp (2/3) |
| Net cumulative return, 3 years (higher) | −6.05% → −2.75% | +3.30 pp (5/0) | −2.75% → +2.56% | +5.31 pp (5/0) | 7.13% → 10.99% | +3.86 pp (4/1) |
| Cost drag, pp over 3 years (lower) | 10.73 → 7.97 | −2.76 (0/5) | 13.45 → 10.67 | −2.77 (0/5) | 11.08 → 7.18 | −3.90 (0/5) |
| Turnover / yr (lower) | 23.8 → 17.3 | −6.53 (0/5) | 28.6 → 22.0 | −6.63 (0/5) | 21.7 → 13.7 | −8.00 (0/5) |
| Net volatility, p.a. (lower) | 12.00% → 11.29% | −0.70 pp (0/5) | 9.06% → 8.36% | −0.71 pp (0/5) | 5.84% → 5.61% | −0.22 pp (1/4) |
| Net max drawdown (shallower) | −18.9% → −15.4% | +3.51 pp (5/0) | −16.1% → −13.4% | +2.71 pp (5/0) | −8.5% → −7.5% | +1.06 pp (4/1) |
| Mean target cash (limit 40%) | 22.5% → 30.3% [22.8% → 32.9%] | +7.7 pp (5/0) | 26.9% → 32.9% [29.1% → 35.0%] | +6.0 pp (5/0) | 26.8% → 34.9% [25.0% → 27.0%] | +8.1 pp (4/1) |
| Risky HHI (limit 2/3) | 0.481 → 0.569 [0.471 → 0.570] | +0.089 (5/0) | 0.512 → 0.578 [0.533 → 0.608] | +0.065 (5/0) | 0.503 → 0.618 [0.466 → 0.511] | +0.115 (5/0) |
| Dispersion, ratio to control (≥ 0.5) | 0.95 | −0.010 (0/5) | 0.90 | −0.013 (0/5) | 0.86 | −0.019 (0/5) |
| Meaningful-change share, ratio to control (≥ 0.5) | 0.92 | −0.105 (0/5) | 0.92 | −0.082 (0/5) | 0.78 | −0.221 (0/5) |

**Intervals (bootstrap 95%, mean Δ):**

| | Fold A | Fold B | Fold C |
| --- | --- | --- | --- |
| Sharpe | [0.016, 0.148] | [0.112, 0.330] | [−0.016, 0.484] |
| Ann. return | [0.38, 1.87] pp | [1.01, 2.49] pp | [−0.13, 2.52] pp |
| Cost drag | [−3.11, −2.19] pp | [−4.11, −1.32] pp | [−5.18, −2.57] pp |

- **t-intervals (sensitivity) for Sharpe:** A [−0.025, 0.188]; B [0.044, 0.398]; C [−0.148,
  0.613].
- **Downside risk:** not available (D-076).

**Seed-level net Sharpe, validation (control → treatment):**
- **A:** 42 −0.103 → 0.066; 43 0.023 → 0.202; 44 −0.247 → −0.207; 45 −0.058 → −0.056; 46
  −0.185 → −0.167.
- **B:** 42 −0.360 → 0.005; 43 0.203 → 0.261; 44 −0.308 → −0.171; 45 0.474 → 0.850; 46 −0.212 →
  −0.043.
- **C:** 42 −0.031 → 0.117; 43 0.512 → 0.831; 44 0.946 → 0.763; 45 0.147 → 0.812; 46 0.577 →
  0.788.
- **The only negative pair is seed 44 in fold C,** the same seed as in E7/E8.
- **In fold A,** two seeds gain less than 0.02.

**Training split (in-sample, descriptive; medians control → treatment):**

| Fold | Net Sharpe | Annualised net return | Mean Δ Sharpe | Mean Δ return | Turnover Δ |
| --- | --- | --- | --- | --- | --- |
| A | 2.895 → 2.953 | about 68% → 64% | +0.012 (3/2) | −3.1 pp (1/4) | −5.8 (0/5) |
| B | 2.044 → 2.002 | 33% → 30% | −0.011 (2/3) | −2.0 pp (0/5) | −5.7 (0/5) |
| C | 1.267 → 1.310 | 17% → 16% | +0.016 (3/2) | −1.1 pp (2/3) | −8.0 (0/5) |

## 5. Across-fold synthesis

- **Same direction everywhere:**
  - every fold is "positive" under the prespecified rule;
  - 14 of 15 pairs improve;
  - the mean Δ return is positive in all folds.
- **Magnitude varies by period:**
  - **fold A** is small (+0.08; median +0.04);
  - **folds B and C** are about +0.22–0.23.
  - No fold dominates: the largest share of the summed effect is 43%.
- **Gross vs cost:**
  - cost savings (2.8–3.9 pp) are consistent across folds;
  - gross return does not fall: it rises in B, is flat in A and C;
  - the net gain is therefore cost savings plus, in B, some gross gain.
  - **Volatility:** lower in A and B (−0.7 pp), which raises Sharpe further.
- **Cash and concentration:** they rise in every fold, by a similar amount, and stay within limits.
- **Responsiveness:** it is preserved.
- **Gap to baselines:** the penalty narrows PPO's losses, but the gap is about 0.6–1.7 Sharpe in
  every fold.

## 6. Historical comparison with E9 (not pooled)

| | Population | Window | Mean ΔSharpe | + / − | Bootstrap 95% CI | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| E9 (EXP-022) | seeds 47–56 | 2017–2019 | +0.247 | 8 / 2 | [0.091, 0.422] | Partial confirmation |
| E10 fold C | seeds 42–46 (= E8) | 2017–2019 | +0.232 | 4 / 1 | [−0.016, 0.484] | — |
| E10 folds A / B | seeds 42–46 | 2011–13 / 2014–16 | +0.082 / +0.221 | 5 / 0, 5 / 0 | [0.016, 0.148] / [0.112, 0.330] | — |

**Reading:**
- **2017–2019 is not exceptional:** a similar Sharpe gain appears in 2014–2016, and a smaller one
  in 2011–2013.
- **Absolute levels are exceptional:** 2017–2019 is the only window in which either PPO arm earns
  a clearly positive net Sharpe.

## 7. Baselines (each fold's own validation evaluation; comparable within a fold only)

| Fold | `buy_and_hold_equal_weight` | `equal_weight_monthly` | `inverse_volatility_monthly` | E10B / E10T1 median Sharpe |
| --- | --- | --- | --- | --- |
| A (2011–13) | 0.658 (4.9% p.a.) | 0.641 (5.2%) | 0.936 (5.5%) | −0.103 / −0.056 |
| B (2014–16) | 0.461 (2.8%) | 0.477 (3.0%) | 0.605 (3.1%) | −0.212 / 0.005 |
| C (2017–19) | 1.355 (8.6%) | 1.470 (8.8%) | 1.754 (8.1%) | 0.511 / 0.788 |

**What they share:** the same window, 15 bps costs (funding charged), metric definitions and
universe as PPO.
- **Turnover:** baselines trade 0–0.8 a year; PPO trades 14–29.
- **Result:** no PPO run beats any baseline in folds A and B.

## 8. Limitations

- **One market history:**
  - expanding folds share training rows (2007–2010 is in every fold);
  - the three validation windows are not independent markets;
  - the stratified p-value assumes exchangeable pair signs, not independent periods.
- **Folds and seeds:**
  - three folds and five seeds per fold;
  - fold-level permutation p cannot be below 0.0625;
  - fold C repeats E8 exactly.
- **Fold A:** a short training history (about 3.5 years, dominated by 2008–2010), and the
  smallest effect.
- **Overfitting:** in-sample Sharpe is about 2–3, against negative validation Sharpe in A and B.
  The validation results describe overfitted policies.
- **Guard rails:** E8's judgement calls.
- **Unchanged limits:** downside risk is unavailable; the profile input is constant (no
  personalisation); validation-only inference; test performance unmeasured.

## 9. Conclusion and recommendation

**Conclusion (prespecified rule): Walk-forward confirmation.**
- The moderate penalty generalised across all three validation periods in direction. It reduced
  turnover and costs, and improved net Sharpe and return in 14 of 15 paired runs, without
  harming risk or responsiveness.
- **Effect size by period:** small in 2011–2013, and similar in 2014–2016 and 2017–2019.
- **What it is:** an improvement in cost efficiency and in the risk-adjusted performance *of
  PPO*.
- **What it is not:** evidence that PPO is a good portfolio strategy. It remains far below simple
  baselines in every fold and loses money in two of three.

**Recommended next step (not started; needs its own protocol):**
- **Primary: diagnose and reduce PPO's overfitting,** keeping κ = 0.0015 fixed as the default.
  - **Why:** in-sample Sharpe is about 2–3 against −0.1–0.7 out of sample. That gap, not
    trading costs, now limits the approach.
  - **Options:**
    - early stopping on a pre-validation slice of the training period;
    - a shorter training budget per fold;
    - stronger regularisation.
  - **Each option needs a team decision,** because it changes the training methodology.
- **Not recommended:** further κ tuning; E8 and E10 already cover it.
- **Test period:** stays sealed. A single pre-registered test run (D-084 §7) would need a fixed
  candidate and a written rule first.

## 10. Reproducibility

| Item | Identifier |
| --- | --- |
| Commits | Protocol `3019f46`; implementation `5939c17` (clean; fold builds, all runs and evaluations); results: this report's commit |
| Fold A runs (κ 0; κ 0.0015), seeds 42–46 | a1987fe9a9420e88, b613799bd599961a, 3bb95ec1a8f75740, b4362ac510db7b95, 6f4bc0057184aa41; 49880d287e1a6454, 1edd50c148a5c4fb, a7cd76ad58e16f2a, a98c22361efd2e45, 6edfb9c667924e8d |
| Fold B runs | ee43e96c1d4f0163, 3dd52ce0644f1a19, df2ea0565b3aff6a, c3ea753e3b3eefdc, 1de4d38510dfbf64; af44cb0be7d8a720, 088dc61ea6d0139e, 66df7779731f398c, a1820b87c2796d39, 63d40d08fad3e8c2 |
| Fold C runs | e9b05a7fcf50a8b5, bdf35ba71d8dd9ef, 4ca515716606df12, 2271d97442a47808, a5c59af899a1bd37; 76a36b87b4ea6607, 2299651687162723, c22997bd04069410, 62f1dd21539c2988, 0db3cfb8836e05c4 |
| Training | 30 of 30 `full` runs, 100,352 timesteps each; 87–350 s each (several slow runs from CPU contention; deterministic, fold C reproduced exactly); 2026-11-04 08:58–10:15 UTC; 0 failures, 0 retries, 0 exclusions |
| Evaluations (all VERIFIED) | A: train `cd9d0d473f53ba05`/`7611fafcba4afa42`, validation `0e249b70baa00c70`/`418f2fcf3c01cb9a`; B: train `0ba58ef8a13cb719`/`854253dd8c688803`, validation `2b74d6ba896bfd6e`/`f89f3649d82a41a8`; C: train `f54b704a0601bf2c`/`7d83179bd45ef46d`, validation `db81bea846034477`/`24626392a5a36572` (control/treatment) |
| Comparison (VERIFIED, D-094 v1) | `data/processed/walk_forward_comparisons/fb8de80f69600763` |
| Analysis command | `python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/walk_forward_c_k0.yaml compare-walk-forward --fold A … --fold B … --fold C … --reproduce-validation <E8B> <E8T1> <E7B> <E7T1> --reproduce-train <…> --e9-comparison data/processed/confirmation_comparisons/0e88c06aefaeec31 --execute` |
| Bootstrap | 10,000 resamples, `numpy.random.default_rng(20261104)` |
| Figures (git-ignored; source-hash sidecars) | `reports/figures/e10/e10_fold_effects.png`, `e10_paired_seeds.png`, `e10_costs_decomposition.png`, `e10_composition.png` |
