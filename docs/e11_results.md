# E11 results: PPO training-budget reduction under walk-forward validation (EXP-026)

> **Status (2026-11-04):** complete on training and validation splits inside 2007–2019.
> - **Methodology:** `docs/e11_budget_protocol.md` (D-095), committed before implementation
>   (`bf39e29`); no amendments. **Pipeline check:** EXP-025 (not a result).
> - **Labelled exploratory experiment:** the D-066 budget (100,000 in `agent.yaml`) is **not**
>   revised.
> - **Unchanged:** D-009, D-018 (open) and D-094 (provisional).
> - **Test period:** sealed and unmeasured.
> - **Research only;** simulated backtests on one market history; not financial advice.
> - **Traceability:** every number comes from the verified comparison `a978c872ca38b740` (§9).

## 1. Executive summary

**Question:** does halving PPO's training budget improve walk-forward validation net Sharpe and
reduce overfitting, while keeping the E10 moderate-penalty behaviour?

**Intervention:**
- **Budgets:** 50,176 timesteps (E11H) against 100,352 (E11R, the D-066 budget; an exact
  reproduction of E10T1).
- **Fixed:** κ = 0.0015 and λ = 0 in both arms, E10's three folds and seeds 42–46.
- **Runs:** 30 full runs and 12 evaluations, all verified, with no failures or retries.

**Prespecified outcome: No reliable improvement.**
- **Supported:** H3, H6, H7 and H9.
- **Partially supported:** H1, H2, H4, H5 and H8.

**Verified results (E11H − E11R, five paired seeds per fold):**

| Fold (validation) | Validation ΔSharpe mean (median) | + / − | Bootstrap 95% CI | Training ΔSharpe | Δ gap (training − validation) |
| --- | --- | --- | --- | --- | --- |
| A (2011–13) | +0.107 (+0.114) | 4 / 1 | [−0.027, 0.250] | −0.879 (0/5 higher) | −0.987 (5/5 lower) |
| B (2014–16) | +0.055 (+0.031) | 3 / 2 | [−0.193, 0.304] | −0.544 (0/5) | −0.600 (5/5) |
| C (2017–19) | −0.088 (−0.047) | 2 / 3 | [−0.352, 0.171] | −0.421 (0/5) | −0.334 (4/5) |

- **Validation:** only fold A is "positive" under the rule. Folds B and C are mixed.
  - Mean of fold means +0.025; secondary stratified sign-flip test p = 0.73.
- **The overfitting gap shrinks in every fold, almost entirely because training fit falls.**
  - **A:** training Sharpe −0.88, validation +0.11.
  - **B:** training −0.54, validation +0.06.
  - **C:** training −0.42, and validation **also** falls (−0.09).
- **Risk:** volatility is lower in every fold (−0.6 to −1.5 pp), and drawdowns are shallower in
  A and B.
- **Composition:** responsiveness is kept. Cash rises in A and B (about +6–7 pp; fold B's median
  cash, 41.6%, exceeds the 40% guard rail).
- **Reproduction:** E11R equals E10T1 exactly (28 metrics, all folds and splits), and every run
  realised its registered timesteps.
- **Baselines:** **PPO remains below every simple baseline in every fold** (arm medians). The
  half budget narrows the gap in A and B and widens it in C.

**Interpretation:**
- A shorter budget is a strong regulariser of the **in-sample** fit, but it does not reliably
  improve **out-of-sample** performance.
- The smaller gap is mostly a lower training score, not better generalisation.
- The budget is not the lever that makes PPO competitive.

**Main limitation:** one market history; two budgets only; five seeds per fold.

## 2. Experiment design

| Item | Value |
| --- | --- |
| Decision / experiments | D-095 (Provisional (delegated)); EXP-025 pipeline check; EXP-026 full experiment |
| Arms | E11R: D-066 budget (100,000 configured → 100,352 realised; 548 / 296 / 202 episodes in A / B / C). E11H: `total_timesteps: 50176` (98 × 512; 274 / 148 / 101 episodes) |
| Fixed | κ = 0.0015, λ = 0, configuration 4 (lr 1e-4 and clip 0.2 constant, n_steps 512, batch 64), constant profile 0.5, final checkpoint only (no early stopping, no validation-based selection) |
| Folds | E10's: A train → 2010, validate 2011–2013; B train → 2013, validate 2014–2016; C train → 2016, validate 2017–2019 (= D-009). Folds A and B use the verified pre-2020 fold datasets and fold-fitted regime thresholds |
| Seeds and runs | 42–46, paired within a fold; 3 × 2 × 5 = 30 full runs |
| Configs | `configs/budget_{a,b,c}_{ref,half}.yaml`. Within a fold they differ only in `label` and `total_timesteps`; E11R = E10T1 except `label` (checked by tests and `validate_config`) |
| Statistics | Within fold (n = 5): mean, median, SD, SE, sign counts, percentile bootstrap (10,000, seed 20261104), t-interval (df 4), exact sign-flip p (≥ 0.0625, descriptive). Across folds: fold classes and one secondary stratified test. Seeds share one history; folds share training rows |

## 3. Results (validation; means over seeds, medians in brackets)

| Metric (better) | Fold A E11R → E11H | Δ (+/−) | Fold B E11R → E11H | Δ (+/−) | Fold C E11R → E11H | Δ (+/−) |
| --- | --- | --- | --- | --- | --- | --- |
| Net Sharpe (higher) | −0.032 → 0.075 [−0.056 → 0.146] | +0.107 (4/1) | 0.180 → 0.236 [0.005 → 0.301] | +0.055 (3/2) | 0.662 → 0.575 [0.788 → 0.468] | −0.088 (2/3) |
| Ann. net return (higher) | −0.95% → 0.20% | +1.15 pp (4/1) | 0.77% → 0.87% | +0.10 pp (3/2) | 3.53% → 2.77% | −0.76 pp (2/3) |
| Gross cumulative, 3 years (higher) | 5.22% → 9.10% | +3.88 pp (4/1) | 13.23% → 13.21% | −0.03 pp (3/2) | 18.16% → 17.13% | −1.03 pp (2/3) |
| Cost drag, pp (lower) | 7.97 → 8.40 | +0.43 (3/2 higher) | 10.67 → 10.35 | −0.32 (2/3) | 7.18 → 8.58 | +1.40 (4/1 higher) |
| Turnover / yr (lower) | 17.3 → 17.6 | +0.35 | 22.0 → 21.2 | −0.77 | 13.7 → 16.8 | +3.06 |
| Net volatility (lower) | 11.29% → 9.84% | −1.45 pp (0/5 higher) | 8.36% → 7.18% | −1.18 pp (0/5) | 5.61% → 5.01% | −0.61 pp (1/4) |
| Net max drawdown (shallower) | −15.4% → −14.2% | +1.17 pp (5/0) | −13.4% → −11.3% | +2.07 pp (5/0) | −7.5% → −7.7% | −0.20 pp (4/1) |
| Mean target cash (limit 40% median) | 30.3% → 37.2% [median 39.7%] | +6.9 pp (5/0) | 32.9% → 39.1% [41.6%] | +6.2 pp (4/1) | 34.9% → 35.9% [35.0%] | +0.9 pp (3/2) |
| Risky HHI (limit 2/3) | 0.569 → 0.587 | +0.018 | 0.578 → 0.597 | +0.020 | 0.618 → 0.513 | −0.105 |
| Dispersion / meaningful changes, ratio to E11R | 0.93 / 1.09 | — | 0.88 / 0.93 | — | 0.99 / 1.60 | — |

**Additional intervals:**
- **Sharpe t-intervals:** A [−0.107, 0.322]; B [−0.337, 0.448]; C [−0.512, 0.337].
- **Permutation p:** A 0.25; B 0.69; C 0.63.
- **Downside risk:** not available (D-076).

**Seed-level validation net Sharpe (E11R → E11H):**
- **A:** 42 0.066 → 0.221; 43 0.202 → 0.317; 44 −0.207 → 0.146; 45 −0.056 → −0.177; 46 −0.167 →
  −0.131.
- **B:** 42 0.005 → 0.301; 43 0.261 → 0.709; 44 −0.171 → −0.140; 45 0.850 → 0.630; 46 −0.043 →
  −0.322.
- **C:** 42 0.117 → 0.468; 43 0.831 → 0.784; 44 0.763 → 0.429; 45 0.812 → 0.303; 46 0.788 → 0.890.

## 4. Overfitting analysis

| Fold | Training Sharpe (median) E11R → E11H | Validation Sharpe (median) | Gap (median) | Paired Δgap (bootstrap 95% CI) | Attribution |
| --- | --- | --- | --- | --- | --- |
| A | 2.953 → 2.160 | −0.056 → 0.146 | 3.00 → 1.98 | −0.987 [−1.317, −0.616], 5/5 lower | "genuine" (validation rose, by 0.11 against a 0.88 training drop) |
| B | 2.002 → 1.404 | 0.005 → 0.301 | 2.01 → 1.25 | −0.600 [−0.976, −0.280], 5/5 | "genuine" (+0.06 against −0.54) |
| C | 1.310 → 0.916 | 0.788 → 0.468 | 0.68 → 0.45 | −0.334 [−0.558, −0.131], 4/5 | "training loss only" (validation fell) |

**Training-split annualised net return:** 64% → 35% (A), 30% → 18% (B), 16% → 9% (C). It is lower in
every seed.

**Reading:**
- **The gap reduction is real, but it is not a generalisation improvement.**
  - In A and B, about 90% of Δgap is the drop in training performance (0.88 of 0.99; 0.54 of
    0.60).
  - In C the training drop exceeds the whole gap reduction, because validation fell too.
- **Validation:** gains are small and inconsistent in A and B, and there is a loss in C.
- **Variability:** paired validation differences vary widely across seeds (SD 0.17 / 0.32 / 0.34).
- **Instability:** none beyond that. No run failed, and no metric was undefined.

## 5. Across-fold synthesis and baselines

**Synthesis:**
- **Fold means:** +0.107 / +0.055 / −0.088 (range 0.19).
- **Shares:** 43% / 22% / 35% of the summed absolute effect, so no fold dominates.
- **Classes:** one positive fold, two mixed.

| Fold | Best baseline (validation Sharpe) | E11R median gap to it | E11H median gap to it | Any arm median ≥ a baseline? |
| --- | --- | --- | --- | --- |
| A | `inverse_volatility_monthly` 0.936 (others 0.64–0.66) | 0.99 | 0.79 | no |
| B | `inverse_volatility_monthly` 0.605 (others 0.46–0.48) | 0.60 | 0.30 | no; two E11H seeds (0.71, 0.63) and one E11R seed (0.85) individually exceed all three |
| C | `inverse_volatility_monthly` 1.754 (others 1.36–1.47) | 0.97 | 1.29 | no |

**Comparability:** baselines come from each fold's own validation evaluation (same window, costs
and definitions). They are comparable within a fold, not across folds.

**E10 context:** E10's κ effect at the D-066 budget was +0.082 / +0.221 / +0.232. The budget
effect here is smaller and changes sign across folds.

## 6. Hypotheses

| | Verdict | Evidence |
| --- | --- | --- |
| H1 validation Sharpe | Partially | Mean Δ > 0 in A and B, < 0 in C |
| H2 cross-fold consistency | Partially | One positive fold (A); B and C mixed |
| H3 overfitting gap | **Supported** | Δgap < 0 with ≥ 4/5 seeds in every fold. Attribution is genuine in A and B and training loss only in C, so it is driven by lower training fit |
| H4 return preservation | Partially | Δ return +1.15 / +0.10 / **−0.76** pp (C below the −0.5 pp tolerance) |
| H5 not via inactivity, cash or concentration | Partially | Fold B median cash 41.6% > 40%. Turnover ratios 0.90 / 0.81 / 1.13 (no inactivity) |
| H6 responsiveness | **Supported** | Dispersion ≥ 88% and meaningful changes ≥ 93% of E11R's |
| H7 risk | **Supported** | Lower volatility everywhere; drawdown not deeper by more than 0.2 pp |
| H8 baseline gap | Partially | Narrower in A and B, wider in C; below every baseline everywhere |
| H9 reproduction and integrity | **Supported** | E11R = E10T1 exactly (6/6); every run's `timesteps_done` = registered (100,352 / 50,176); fold A and B integrity verified; E0 reproduces EXP-006 in fold C |

**Outcome rule:**
- **What it needs:** "Generalisation improvement" requires all three folds positive.
- **What happened:** with one positive fold and none negative, the outcome is **No reliable
  improvement**.

## 7. Integrity

- **Test period:** sealed. Every evaluation window lies inside its fold, every row read is before
  2020-01-01, and there is no test evaluation.
- **Configs:** checked programmatically (§2).
- **Protocol:** unchanged since `bf39e29`.
- **Runs:**
  - 30 of 30 `full` runs at the clean commit `dc7cb36`, 0 failures, 0 retries, 0 exclusions.
  - 42–2,548 s each; several were slow from CPU contention. Training is deterministic, and E11R
    reproduced E10T1 exactly.
- **Earlier work:** the E1–E10 configurations discover exactly their existing runs (identities
  unchanged), and all earlier outputs verify (§9).
- **Governance:** D-009, D-018, D-094 and the D-066 budget are unchanged.

## 8. Limitations and conclusion

**Limitations:**
- **One market history:** shared, expanding training rows; three windows; five seeds per fold.
- **Budgets:** two values only, not a budget curve. E11H is a truncated E11R trajectory, because
  the schedules are constant.
- **Overfitting remains:** training Sharpe is still 0.9–2.2 against −0.1–0.5 on validation.
- **Guard rails:** E8's judgement calls (fold B's cash just exceeds one).
- **Unchanged limits:** downside risk is unavailable; the profile input is constant; validation
  only.

**Conclusion: No reliable improvement.**
- **What halving did:** it reduced in-sample performance a lot and the overfitting gap with it.
- **What it did not do:** improve validation net Sharpe consistently. The gain was small in A and
  B, and there was a loss in 2017–2019.
- **Gap attribution:** the gap reduction comes mainly from a lower training fit, not from better
  generalisation.
- **Baselines:** PPO remains below the simple baselines in every fold.
- **Recommendation:** E11 gives no reason to change the current recommendation or the D-066
  budget.

**Next recommendation (not started; needs its own protocol and a team decision):**
- **What:** test whether PPO's out-of-sample weakness comes from the **policy input** rather than
  the amount of training.
- **How:** an observation ablation, for example removing the regime one-hot or the raw held
  weights, under the E10 walk-forward folds.
- **Why:** the training budget, like κ, changes the fit without lifting validation performance.

## 9. Reproducibility

| Item | Identifier |
| --- | --- |
| Commits | Protocol `bf39e29`; implementation `dc7cb36` (clean; all runs and evaluations); results: this report's commit |
| Fold A runs (E11R; E11H), seeds 42–46 | 3071078f0a280e0e, 89ee06dcdf4e74d6, 5250bec0840b97eb, 3b92242fd4191458, 4995c43af382c283; a35409671cfc7c64, 0eef26723c007e1b, 7534b322350c028a, 0415de1906bc6f3d, 70ad94fc8983df81 |
| Fold B runs | 4f61b1d940359e76, 1ae936c9fda336f5, 8d63f8e29dc46cc8, a3f663354eb1369f, 3a8fa99576f62b10; 37e4f7b4ca043c31, ab84d5a02d41f413, 9e611781020f65e6, 984e2d3599def70c, 921a91860b2dd505 |
| Fold C runs | 357c9814dc05386f, d2bd73efbb3d2009, 665cce5c688e39ab, d9880e0a071955fe, a78130bd1f6f1544; d5c1c6f58726ba87, 0bd63009fedeb7bd, 6b57b569fbcc5c44, 7e399a1a811a1f93, 3f6c9a26bcc673a5 |
| Evaluations (all VERIFIED; E11R / E11H) | A: train `22378b3716b7b598` / `1929277d9cf6196f`, validation `cdcff58f622e1b76` / `f2321a56154e3302`; B: train `3459747164023b1b` / `b2accef50ea52ab8`, validation `cc055311816bcfcb` / `96496d5ca87cb2c2`; C: train `8a9946ee7d4b229b` / `f2161e6656a146b9`, validation `9300fef05dcc78ae` / `eb84f15c642b0bb3` |
| Comparison (VERIFIED, D-095 v1) | `data/processed/budget_comparisons/a978c872ca38b740` |
| Analysis command | `python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/budget_c_ref.yaml compare-budget --fold A … --fold B … --fold C … --reproduce-validation <E10T1 A/B/C val> --reproduce-train <E10T1 A/B/C train> --e10-comparison data/processed/walk_forward_comparisons/fb8de80f69600763 --execute` |
| Bootstrap | 10,000 resamples, `numpy.random.default_rng(20261104)` |
| Figures (git-ignored; source-hash sidecars) | `reports/figures/e11/e11_fold_effects.png`, `e11_train_vs_validation.png`, `e11_costs_turnover.png`, `e11_composition.png`, `e11_baselines.png` |
