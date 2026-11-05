# E12 results: market-regime observation ablation under walk-forward validation (EXP-028)

> **Status (2026-11-05):** complete on training and validation splits inside 2007–2019.
> - **Methodology:** `docs/e12_regime_ablation_protocol.md` (D-096), committed before implementation
>   (`edd3272`); no amendments. **Pipeline check:** EXP-027 (not a result).
> - **D-062 exception for E12 only:** D-062 remains the default observation.
> - **Unchanged:** D-009, D-018 (open), D-094 and D-095 (provisional), and the D-066 budget.
> - **Test period:** sealed and unmeasured.
> - **Research only;** simulated backtests on one market history; not financial advice.
> - **Traceability:** every number comes from the verified comparison `c3ab3341b6287fa7` (§9).

## 1. Executive summary

**Question:** does removing the market-regime observation inputs improve PPO's walk-forward
validation net Sharpe, or do they carry useful information?

**Ablation:**
- **What is removed:** the **9 regime one-hot inputs** (`negative_low` … `positive_high`), giving
  56 → 47 inputs. The 34 features, 8 weights and 5 profile inputs are unchanged.
- **Arms:** E12F (full observation; an exact reproduction of E10T1) and E12N (no regime inputs).
- **Fixed:** κ = 0.0015, λ = 0 and the D-066 budget (100,352 timesteps) in both arms, E10's three
  folds and seeds 42–46.
- **Runs:** 30 full runs and 12 evaluations, all verified, with no failures or retries.

**Prespecified outcome: No reliable improvement.**
- **Supported:** H4, H7 and H9.
- **Partially supported:** H1, H3, H5, H6 and H8.
- **Not supported:** H2.

**Verified results (E12N − E12F, five paired seeds per fold):**

| Fold (validation) | Validation ΔSharpe mean (median) | + / − | Bootstrap 95% CI | Training ΔSharpe | Δ ann. net return |
| --- | --- | --- | --- | --- | --- |
| A (2011–13) | −0.111 (−0.019) | 2 / 3 | [−0.319, 0.078] | −0.275 (1/4) | −1.48 pp |
| B (2014–16) | −0.245 (−0.021) | 2 / 3 | [−0.595, 0.098] | −0.230 (1/4) | −1.75 pp |
| C (2017–19) | +0.180 (+0.066) | 3 / 2 | [−0.098, 0.459] | −0.134 (1/4) | +0.50 pp |

- **Classes:** every fold is "mixed". No fold is positive or negative under the prespecified rule.
- **Across folds:** mean of fold means −0.058; secondary stratified test p = 0.56.
- **Training:** in-sample Sharpe falls slightly without the regime inputs (4 of 5 seeds in every
  fold). The overfitting gap barely changes (median 3.00 → 2.77, 2.01 → 1.78, 0.68 → 0.42).
- **Trading:** turnover and cost drag are essentially unchanged; responsiveness is kept.
- **Guard rails:**
  - **Risk:** drawdowns deepen and volatility rises in A and B (H5 fails there).
  - **Cash:** fold C's median cash rises to 51.8% (> the 40% guard rail).
- **Reproduction:** E12F equals E10T1 exactly in every fold and split (28 metrics). Every run
  recorded its registered observation size (56 / 47) and 100,352 timesteps.
- **Baselines:** **both PPO arms remain below every simple baseline in every fold.** The ablation
  narrows the gap only in B, and only slightly.

**Interpretation:**
- **The regime inputs are neither clearly useful nor clearly harmful.** Removing them does not
  improve walk-forward generalisation, and the validation effect changes sign across folds.
- **In-sample:** the policies fit the training period slightly less well without them, consistent
  with the one-hot being a coarse summary of features the policy already sees
  (`equity_mom_63`, `market_vol_21`).
- **Recommendation:** no reason to change D-062's observation.

**Main limitation:** one market history; five seeds per fold; the large seed-to-seed spread
(paired SD 0.25–0.45) makes small effects undetectable.

## 2. Design

| Item | Value |
| --- | --- |
| Decision / experiments | D-096 (Provisional (delegated); scope under R-S; D-081 executed in adapted form); EXP-027 pipeline check; EXP-028 full experiment |
| Removed inputs | The 9 regime one-hot inputs (D-062 positions 35–43; labels `negative_low`, `negative_normal`, `negative_high`, `neutral_low`, `neutral_normal`, `neutral_high`, `positive_low`, `positive_normal`, `positive_high`) |
| How | `RegimeAblatedEnv` (`environment/observation_ablation.py`), an observation wrapper below the profile wrapper in training and evaluation. Rewards, info, actions, ledger, costs, the scaler and the feature and regime pipelines are unchanged (tested) |
| Arms | E12F: 56 inputs (= E10T1 except the label). E12N: 47 inputs (`observation_ablation: regime`). Both κ = 0.0015, λ = 0, configuration 4, constant profile 0.5, final checkpoint only |
| Budget | D-066: 100,352 realised timesteps per run (548 / 296 / 202 episodes in A / B / C) |
| Folds | E10's: A train → 2010, validate 2011–2013; B train → 2013, validate 2014–2016; C train → 2016, validate 2017–2019 (= D-009). Folds A and B use the verified pre-2020 fold datasets and fold-fitted thresholds |
| Seeds and runs | 42–46, paired within a fold; 3 × 2 × 5 = 30 full runs |
| Statistics | Within fold (n = 5): mean, median, SD, SE, sign counts, percentile bootstrap (10,000, seed 20261104), t-interval (df 4), exact sign-flip p (≥ 0.0625, descriptive). Across folds: fold classes and one secondary stratified test |

## 3. Results (validation; means over seeds, medians in brackets)

| Metric (better) | Fold A E12F → E12N | Δ (+/−) | Fold B E12F → E12N | Δ (+/−) | Fold C E12F → E12N | Δ (+/−) |
| --- | --- | --- | --- | --- | --- | --- |
| Net Sharpe (higher) | −0.032 → −0.143 [−0.056 → −0.186] | −0.111 (2/3) | 0.180 → −0.064 [0.005 → 0.023] | −0.245 (2/3) | 0.662 → 0.843 [0.788 → 0.753] | +0.180 (3/2) |
| Ann. net return (higher) | −0.95% → −2.43% | −1.48 pp (2/3) | 0.77% → −0.99% | −1.75 pp (3/2) | 3.53% → 4.03% | +0.50 pp (2/3) |
| Gross cumulative, 3 years (higher) | 5.22% → 0.86% | −4.36 pp (1/4) | 13.23% → 6.92% | −6.31 pp (2/3) | 18.16% → 19.44% | +1.28 pp (3/2) |
| Cost drag, pp (lower) | 7.97 → 7.85 | −0.12 | 10.67 → 9.72 | −0.95 | 7.18 → 6.86 | −0.31 |
| Turnover / yr | 17.3 → 18.0 | +0.70 | 22.0 → 21.0 | −1.04 | 13.7 → 13.0 | −0.74 |
| Net volatility (lower) | 11.29% → 12.51% | +1.22 pp (4/1 higher) | 8.36% → 8.42% | +0.06 pp | 5.61% → 4.78% | −0.84 pp (1/4) |
| Net max drawdown (shallower) | −15.4% → −18.2% | −2.75 pp deeper | −13.4% → −16.3% | −2.92 pp deeper | −7.5% → −5.4% | +2.06 pp (5/0) |
| Mean target cash | 30.3% → 33.8% [median 38.0%] | +3.6 pp | 32.9% → 38.0% [39.9%] | +5.1 pp | 34.9% → 50.2% [**51.8%**] | +15.3 pp |
| Risky HHI | 0.569 → 0.609 | +0.040 | 0.578 → 0.617 | +0.040 | 0.618 → 0.668 | +0.050 |
| Turnover / dispersion / meaningful-change ratio to E12F | 0.95 / 1.19 / 0.85 | — | 1.00 / 1.13 / 1.00 | — | 0.74 / 0.93 / 1.20 | — |

**Additional intervals:**
- **Sharpe t-intervals:** A [−0.422, 0.201]; B [−0.807, 0.318]; C [−0.265, 0.626].
- **Permutation p:** A 0.44; B 0.38; C 0.38.
- **Downside risk:** not available (D-076).

**Seed-level validation net Sharpe (E12F → E12N):**
- **A:** 42 0.066 → 0.141; 43 0.202 → −0.263; 44 −0.207 → −0.078; 45 −0.056 → −0.329; 46 −0.167 →
  −0.186.
- **B:** 42 0.005 → 0.023; 43 0.261 → −0.508; 44 −0.171 → −0.192; 45 0.850 → 0.163; 46 −0.043 →
  0.194.
- **C:** 42 0.117 → 0.699; 43 0.831 → 0.612; 44 0.763 → 1.296; 45 0.812 → 0.753; 46 0.788 → 0.854.
- **Reading:** large, opposite-signed seed changes (from −0.77 to +0.58) dominate the fold means.

## 4. Observation analysis

| Fold | Training Sharpe (median) E12F → E12N | Validation Sharpe (median) | Gap (median) | Paired Δgap (bootstrap 95% CI) | Attribution |
| --- | --- | --- | --- | --- | --- |
| A | 2.953 → 2.618 | −0.056 → −0.186 | 3.00 → 2.77 | −0.164 [−0.559, 0.318], 3/5 lower | training loss only |
| B | 2.002 → 1.735 | 0.005 → 0.023 | 2.01 → 1.78 | +0.015 [−0.376, 0.406], 2/5 | gap not reduced |
| C | 1.310 → 1.187 | 0.788 → 0.753 | 0.68 → 0.42 | −0.315 [−0.654, 0.024], 3/5 | "genuine" in mean (validation +0.18), but mixed by seed |

**Answers to the protocol's questions:**
1. **Validation performance:** not improved. The effect is negative in A and B and positive in C,
   all within seed noise.
2. **Training performance:** slightly lower (−0.13 to −0.27 Sharpe; 4/5 seeds in every fold). The
   regime inputs help the in-sample fit a little.
3. **Gap:** it changes little. The modest reductions in A and C come mostly from the lower training
   fit.
4. **Trading:** unchanged (turnover ratios 0.74–1.00; cost drag −0.1 to −1.0 pp). The penalty's
   cost behaviour is kept.
5. **Composition:** cash and concentration rise moderately, and markedly for fold C's cash.
6. **Responsiveness:** preserved (dispersion ≥ 0.93, meaningful changes ≥ 0.85 of E12F's).
7. **Useful information?**
   - There is no evidence that removing the one-hot helps.
   - There is weak, inconsistent evidence that it carries some useful signal: the in-sample fit is
     higher, and returns and drawdowns are better with it in A and B.
   - Not established in either direction.

## 5. Baselines (each fold's own validation evaluation; comparable within a fold only)

| Fold | Best baseline (validation Sharpe) | E12F median gap | E12N median gap | Arm median ≥ any baseline? | Seeds at or above the weakest baseline (E12F / E12N) |
| --- | --- | --- | --- | --- | --- |
| A | `inverse_volatility_monthly` 0.936 (others 0.64–0.66) | 0.99 | 1.12 | no | 0 / 0 |
| B | `inverse_volatility_monthly` 0.605 (others 0.46–0.48) | 0.60 | 0.58 | no | 1 / 0 |
| C | `inverse_volatility_monthly` 1.754 (others 1.36–1.47) | 0.97 | 1.00 | no | 0 / 0 |

**Reading:** PPO stays below all simple baselines in every fold, with or without regime inputs.

## 6. Hypotheses

| | Verdict | Evidence |
| --- | --- | --- |
| H1 validation Sharpe | Partially | Mean Δ > 0 only in C |
| H2 cross-fold consistency | **Not supported** | No positive fold; all mixed |
| H3 return preservation | Partially | Δ return −1.48 / −1.75 / +0.50 pp (A and B below −0.5 pp) |
| H4 not via inactivity or costs | **Supported** | Turnover ratios ≥ 0.74; cost drag not higher |
| H5 risk | Partially | A: median drawdown 3.8 pp deeper; B: median volatility +0.7 pp; C fine |
| H6 composition | Partially | C median cash 51.8% > 40% |
| H7 responsiveness | **Supported** | Dispersion and meaningful-change ratios ≥ 0.85, D_w ≥ 0.92 |
| H8 baseline gap | Partially | Smaller only in B (0.60 → 0.58) |
| H9 reproduction and integrity | **Supported** | E12F = E10T1 exactly (6/6); observation sizes 56/47 and 100,352 timesteps in all 30 runs; fold A and B integrity verified; E0 reproduces EXP-006 in fold C (comparability rule E0 + 5 − 9 applied for E12N) |

**Outcome rule:** no positive fold and no two negative folds, so the outcome is **No reliable
improvement**.

## 7. Integrity

- **Test period:** sealed. Every evaluation window lies inside its fold, every row read is before
  2020-01-01, and there is no test evaluation.
- **Protocol:** unchanged since `edd3272`.
- **Configs:** the arms differ only in `label` and `observation_ablation` (tests and
  `validate_config`).
- **Runs:**
  - 30 of 30 `full` runs at the clean commit `b3b44f5`, 0 failures, 0 retries, 0 exclusions.
  - 89–404 s each (CPU contention), 2026-11-05 00:49–02:47 UTC. Training is deterministic, and
    E12F reproduced E10T1 exactly.
- **Earlier work:** the E1–E11 configurations discover exactly their existing runs (identities
  unchanged), and every earlier output verifies.
- **Governance:** D-009, D-018 (open), D-094, D-095 and the D-066 budget are unchanged. D-062 has
  an exception for E12 only.

## 8. Limitations and conclusion

**Limitations:**
- **One market history:** shared expanding training rows; three windows; five seeds per fold,
  with a large seed spread.
- **Redundancy:** the regime one-hot is a function of two observed features. E12 therefore tests
  the value of that discretisation (and its fold-specific calibration), not of the information
  itself. Removing the source features would be a different experiment.
- **Architecture:** the first network layer differs (47 vs 56 inputs), which is inherent to an
  input ablation.
- **Overfitting:** it remains (training Sharpe 1.2–2.6 against −0.2–0.8 on validation).
- **Unchanged limits:** downside risk is unavailable; the profile input is constant; validation
  only.

**Conclusion: No reliable improvement.**
- **Generalisation:** removing the regime inputs does not improve walk-forward validation. The
  effect is small, inconsistent in sign and inside seed noise.
- **What it costs:** a slightly lower in-sample fit, and worse returns and drawdowns in two of
  three folds.
- **Baselines:** PPO remains below the simple baselines in every fold.
- **D-062:** the full observation stays.

**Next recommendation (not started; needs its own protocol and a team decision):**
- **Direction:** E10–E12 show that κ, the budget and the regime inputs do not close the gap. The
  next step should test the **learning setup** rather than the inputs.
- **For example:** compare PPO against a much simpler learned policy, such as a linear or
  long-only mean–variance allocator on the same features and folds.
- **Why:** to establish whether the limitation is PPO's sample efficiency on about 200–550 weekly
  episodes or the information in the features.

## 9. Reproducibility

| Item | Identifier |
| --- | --- |
| Commits | Protocol `edd3272`; implementation `b3b44f5` (clean; all runs and evaluations); results: this report's commit |
| Fold A runs (E12F; E12N), seeds 42–46 | 387d15c97861890a, 09a35c13d2be2ade, cc2613e7313c91d6, 5e9cd525122da1da, 9b6a2e1a0f2f1576; 7f2fcb3f499d84ea, fc360811c2e7f775, dfc70549ef06a1f9, cdced99380df0596, 6a2c1f47fdebfc20 |
| Fold B runs | 733ff7e8f17b716b, daa359e2cf8f89d4, acd411e5cebc8570, 12dae8a81b84045a, c79c47c989df7ba3; 3f5c599676949794, a545f7f042c45ab0, 58b3885583f4ca0d, 6ce6b9bb0649eaf0, b9684be16ceae28f |
| Fold C runs | de122c4df7448154, 1df6199265492830, 6f69dc5ca8aaf714, 4a05a30aeb6180c2, 3ce0a36cae912208; 0d39e4de466612ff, c81311d73f6d6559, a731db97578719ee, 550b713037bbbc35, ea02623c843c12f8 |
| Evaluations (all VERIFIED; E12F / E12N) | A: train `448627f018a0e50b` / `8fe8b00de59a325a`, validation `0bc6b1d837e4f9e6` / `868b1ed3cfb02c40`; B: train `1c754652525ccc84` / `cf09a3512838c459`, validation `f7859205caa2b650` / `1cc43551502a645b`; C: train `923b470501a15918` / `0943e111ce42c865`, validation `1b7f378f5ffd98b5` / `fd0424c6b0591b9a` |
| Comparison (VERIFIED, D-096 v1) | `data/processed/ablation_comparisons/c3ab3341b6287fa7` |
| Analysis command | `python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/ablation_c_full.yaml compare-ablation --fold A … --fold B … --fold C … --reproduce-validation <E10T1 A/B/C val> --reproduce-train <E10T1 A/B/C train> --e10-comparison data/processed/walk_forward_comparisons/fb8de80f69600763 --execute` |
| Bootstrap | 10,000 resamples, `numpy.random.default_rng(20261104)` |
| Figures (git-ignored; source-hash sidecars) | `reports/figures/e12/e12_fold_effects.png`, `e12_train_vs_validation.png`, `e12_costs_turnover.png`, `e12_composition.png`, `e12_baselines.png` |
