# E10: walk-forward validation of the moderate turnover penalty, prespecified protocol (D-094)

> **Status:** written and fixed on 2026-11-04, **before any E10 implementation or training**, and
> committed on its own before the implementation.
> - **Experiment IDs:** EXP-023 (pipeline check) and EXP-024 (full walk-forward experiment).
> - **Scope:** authorised by a team member's in-session instruction ("Claude Code Master Prompt —
>   E10: Walk-Forward Validation of the Moderate Turnover Penalty"; R-S).
> - **Fold design, statistics and decision rule:** Provisional (delegated) choices by Claude Code
>   (D-094) under the open D-018. E10 does **not** resolve D-018 and does **not** change the
>   accepted D-009 split, which remains the project's primary evaluation.
> - **Amendments:** any later change is appended in §15 with a timestamp and reason. Nothing above
>   §15 is edited after full training starts.
> - **Research only;** simulated backtests on one market history; not financial advice.

## 1. Question

**Primary:** does κ = 0.0015 improve validation net Sharpe over κ = 0 across several historical
validation periods, or is the E9 result specific to 2017–2019?

**What E10 is:** a walk-forward robustness check with two arms and three expanding folds, all
inside 2007–2019. It is not a κ search, a reward, risk or personalisation experiment, a no-trade
band experiment or a test-period experiment.

## 2. Audit (repository at `1fe9052`, clean, level with `origin/main`)

| Item | Verified fact |
| --- | --- |
| E9 | Protocol `2c714e1`, implementation `43a23a0`, results `1fe9052`. Comparison `0e88c06aefaeec31` VERIFIED: seeds 47–56, ΔSharpe +0.247, bootstrap CI [0.091, 0.422], permutation p = 0.021, outcome "Partial confirmation" |
| Arms to test | `configs/confirmation_k{0,1}.yaml` = E8B/E8T1 settings: λ = 0, configuration 4 (lr 1e-4, n_steps 512, ent_coef 0), constant profile 0.5, budget 100,000 configured → 100,352 realised timesteps |
| Splits | D-009 (**accepted** 2026-10-19): train 2007–2016, validation 2017–2019, test 2020–2024 (sealed) |
| Walk-forward | Not implemented. `experiment.yaml`'s `walk_forward` block is read by no code. **D-018 (scheme) is open.** `research_protocol.md` §6 recommends walk-forward "as a robustness check, with expanding folds inside 2007–2019 only … and no per-fold tuning", with the fixed split as the primary evaluation |
| Data | Processed dataset `8e00568ee2aa4de7`: 3,271 rows before 2020 (2007-01-04 → 2019-12-31); 250–253 rows a year. The first possible decision is 2007-07-05 (126-session warm-up, D-058) |
| Features | `a79347e37e653703` holds features over **all** rows, and its regime report holds test-period statistics, so it is never rebuilt or opened. Feature values are past-only. **Checked:** recomputing them from the returns before 2020 (bounded read) reproduces the stored values exactly (maximum difference 0.0) |
| Fitted on training rows | (a) Regime thresholds (`features.yaml` regime block, fitted on the train partition). The regime one-hot is part of the observation. (b) The observation scaler (fitted by `make_training_env` on the training decisions) |
| E0 | The EXP-005 grid was trained on 2007–2016 with dataset `8e00568ee2aa4de7`. It is in-sample for any earlier validation window and its data ids differ from a fold dataset's, so **E0 cannot serve folds A and B** |
| Baselines | `buy_and_hold_equal_weight`, `equal_weight_monthly`, `inverse_volatility_monthly` (63 sessions), computed inside every evaluation over that evaluation's window and costs |

## 3. Walk-forward window design

**Selection rule (fixed before any E10 result exists):**
1. **Validation windows:** three calendar years (the D-009/E9 validation length), non-overlapping,
   tiled backwards from 2019-12-31.
2. **Training:** expanding from the dataset start (2007-01-01), ending the day before the fold's
   validation start.
3. **Validity:** a fold is kept only if its training period has at least as many calendar years as
   its validation window (≥ 3 years). This gives at least about 2.5 years of decisions after the
   126-session warm-up.
4. **No test-period row:** for every fold, every row read lies before 2020-01-01.

**Candidates:**

| Fold | Training rows (dates) | Validation rows (dates) | Holdout (labelled `test` in the fold; never evaluated) | Training rows | Validation rows | Decision span after warm-up | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **A** | 2007-01-01 → 2010-12-31 | 2011-01-01 → 2013-12-31 | 2014-01-01 → 2019-12-31 | 1,007 | 754 | about 3.5 years | **valid** |
| **B** | 2007-01-01 → 2013-12-31 | 2014-01-01 → 2016-12-31 | 2017-01-01 → 2019-12-31 | 1,761 | 756 | about 6.5 years | **valid** |
| **C** | 2007-01-01 → 2016-12-31 | 2017-01-01 → 2019-12-31 | 2020-01-01 → 2024-12-31 (sealed D-009 test) | 2,517 | 754 | about 9.5 years | **valid**; identical to D-009 (the E9 window) |
| (excluded) | 2007 | 2008 → 2010 | — | 250 | 757 | about 0.5 years | training shorter than validation |

**Fold C is the reference fold.**
- It is the D-009 split, using the existing dataset and feature set unchanged.
- With seeds 42–46 its runs must equal E8B/E8T1 exactly, which is how H9 checks the walk-forward
  machinery.
- Its values are therefore already known: E8, +0.232.
- **Folds A and B are the new temporal evidence.**

**Shared observations:**
- The folds share training rows (expanding scheme).
- The validation windows are disjoint.
- They are **not** independent markets.

## 4. Fold inputs and leakage controls

**Folds A and B (derived inputs; implementation `data/walk_forward.py`):**
1. **Fold dataset:**
   - Read the parent dataset `8e00568ee2aa4de7` with the existing **bounded** reader, which
     stops before the D-009 test start, so no 2020+ row is parsed.
   - Keep the rows up to the fold's holdout end (2019-12-31), relabel each row with the fold's
     split, and write a write-once fold dataset.
   - Its metadata records the parent id, the row count and the SHA-256 of the parent prefix.
2. **Fold feature set:** the existing `build_feature_dataset`, applied to the fold dataset, which
   holds no 2020+ row, in `fit` mode.
   - Regime thresholds are fitted on the **fold's** training rows only.
   - The observation scaler is fitted on the fold's training decisions (unchanged
     `make_training_env`).
3. **Checks (part of H9):**
   - fold returns equal the parent rows exactly;
   - fold feature values equal the parent's exactly (past-only);
   - labels follow the fold boundaries;
   - the last row is before 2020-01-01;
   - thresholds are fitted on train.

**Bounded reading in every fold:**
- **Training:** reads rows before the fold's validation start.
- **Validation evaluation:** reads rows before the fold's holdout start, using the existing
  `rows_read_before` logic with the fold's boundaries.

**E0 per fold:**
- **Folds A and B:** no E0 (§2). The profile runs are checked against each other for an
  identical environment, hyperparameters, SB3 constants, data and budget.
- **Fold C:** E0 is evaluated as before and must reproduce EXP-006.

**Embargo:** one-step decisions. D-043 already drops a decision whose earned return lies in the
next partition (D-019 note), so no extra gap is used.

## 5. Arms, seeds, runs and budget

| Arm | κ | λ | Configs |
| --- | --- | --- | --- |
| **E10B** (control) | 0 | 0 | `configs/walk_forward_{a,b,c}_k0.yaml` |
| **E10T1** (moderate) | 0.0015 | 0 | `configs/walk_forward_{a,b,c}_k1.yaml` |

**Configurations:**
- **Generated from one template.** Within a fold the two configs differ only in `label` and
  `reward.turnover_penalty`.
- **Across folds:** they differ only in the `walk_forward_fold` block (the fold's boundaries) and
  the label.
- **Everything else** equals E8B/E8T1 (`turnover_refine_k{0,1}.yaml`) apart from the output
  directories. This is checked programmatically.

**Seeds:** 42–46, the D-066 grid seeds, in every fold and arm, paired within a fold.

**Runs:**
- 3 folds × 2 arms × 5 seeds = **30 full runs** of 100,352 timesteps.
- Fold A's training episodes are shorter (about 3.5 years of decisions), so the same budget
  covers more episodes.

**Unique run identity:** the run id hashes the experiment dict (including the fold block), the
fold's dataset and feature ids, the training-row hashes and the environment's first and last
decision dates. A seed reused in another fold therefore never collides (tested).

**Outputs:**
- **Runs, evaluations and analysis:**
  `data/processed/walk_forward_{experiments,evaluations,comparisons}`.
- **Fold datasets:** `data/processed/walk_forward_datasets/<id>`.
- **Fold feature sets:** under `data/processed/features/<id>`, as new directories.
- No E0–E9 output is touched.

**Evaluations:** for every fold and arm, the training and validation splits, giving 12 in total.

## 6. Shared-code changes (minimal; backward compatible)

1. **`ProfileExperimentConfig.walk_forward_fold`** (optional): `id`, `train`, `validation` and
   `holdout` periods.
   - Written to the experiment identity only when set, so E1–E9 identities are unchanged.
   - **Validation:** strict ordering; every boundary before the project's test start unless the
     fold equals the D-009 split exactly.
2. **`load_context`:** for a fold, the project config's splits are replaced by the fold's
   (validated by the existing `Splits` and `ProjectConfig` checks).
3. **`plan_profile_evaluation`:** for a non-reference fold, E0 is not discovered, and comparability
   is checked among the profile runs instead. `e0_reproduction` reports "not applicable".
4. **New modules:**
   - `data/walk_forward.py`: fold datasets and features, plus verification;
   - `explainability/walk_forward_comparison.py`: the analysis;
   - E10 figures and the `walk-forward` CLI commands.

Every change is tested. The E1–E9 configs must still discover exactly their existing runs.

## 7. Hypotheses and criteria (validation split; all three folds)

**Definitions:**
- **Paired difference:** d_{f,s} = metric(E10T1) − metric(E10B), for fold f and seed s.
- **Positive fold:** mean ΔSharpe > 0 and ≥ 4/5 seeds positive.
- **Negative fold:** mean ΔSharpe < 0 and ≥ 4/5 seeds negative.
- **Mixed fold:** otherwise.

| | Hypothesis | Supported | Partially | Otherwise |
| --- | --- | --- | --- | --- |
| H1 | Turnover | in every fold: mean d < 0 and ≥ 4/5 seeds lower | in some folds | not supported |
| H2 | Cost drag | as H1, on `cost_drag` | in some folds | not supported |
| **H3** | **Net Sharpe (primary)** | all three folds positive | ≥ 1 positive fold | not supported |
| H4 | Annualised net return | in every fold: mean d > 0 and ≥ 4/5 seeds positive | mean d > 0 in ≥ 2 folds | not supported |
| H5 | Gross vs cost decomposition | cost drag = gross − net cumulative (≤ 1e-12) for every run, **and** mean cost saving ≥ mean gross cumulative-return loss in every fold | identity holds, the saving condition in some folds | identity fails |
| H6 | Risk | in every fold: median paired volatility increase ≤ 0.5 pp a year and median drawdown deepening ≤ 2 pp | in some folds | none |
| H7 | Composition | in every fold, E10T1 medians: risky HHI ≤ 2/3, target cash ≤ 0.40, near-all-cash share ≤ 0.05 (E8 limits) | in some folds | none |
| H8 | Responsiveness | in every fold: E10T1 median dispersion and meaningful-change share ≥ 50% of E10B's, and D_w ≥ 25% (E8) | in some folds | none |
| H9 | Reproduction and fold integrity | Fold C seeds 42–46 equal E8B/E8T1 and E7B/E7T1 exactly on both splits (≤ 1e-12, every shared metric); E0 reproduces EXP-006 in fold C; all §4 checks pass for folds A and B | — | not supported |
| H10 | Practical utility | outcome "Walk-forward confirmation" and H6, H7, H8 supported | outcome "Partial confirmation", or confirmation with a guard rail not supported | not supported |

**Not decisive:** H1 and H2 alone never make H10 or the outcome positive.

## 8. Statistical analysis plan

**Unit:** the seed-level paired difference within a fold.
- Seeds within a fold share one market history.
- Folds share training rows.
- **No analysis treats the 15 fold-seed pairs as independent markets, and there is no simple
  pooled test.**

**Within each fold (n = 5), for every endpoint:**
- control and treatment values per seed, means and medians, and paired d per seed;
- mean, median, SD (ddof 1), SE, and counts of positive, negative and tied differences
  (|d| ≤ 1e-12);
- a percentile bootstrap 95% CI of the mean (10,000 resamples, `default_rng(20261104)`);
- a t-interval (t₀.₉₇₅,₄ = 2.776);
- the exact sign-flip permutation p (2⁵ = 32 assignments).
- **Caveat:** with five pairs the smallest attainable p is 0.0625, so fold-level p-values are
  descriptive and cannot reach 0.05.

**Across folds (primary synthesis; descriptive):**
- the three fold-level mean ΔSharpe values and their signs;
- the fold classification (§7);
- their mean, minimum, maximum and range;
- each fold's share of the summed effect, to show whether one fold dominates.
- **No interval across three folds is computed:** three windows of one history cannot estimate
  market-wide effects.

**Secondary (one prespecified test):**
- A stratified exact sign-flip permutation test of the **average of the three fold means**, over
  all 2¹⁵ sign assignments of the 15 pairs.
- It tests "no effect in any pair". Signs are flipped within pairs, so fold structure is kept.
- It is reported as secondary with the dependence caveat. It is the only cross-fold test.

**Multiplicity:**
- Three folds × several endpoints are reported.
- Only the H3 rule (§7) and the outcome rule (§9) are decisional. All other p-values and
  intervals are descriptive.

**Secondary endpoints**, each with the same statistics:
- annualised net return; gross cumulative return; net cumulative return; cost drag; turnover a
  year;
- net volatility; net max drawdown;
- mean target cash; risky HHI; allocation dispersion; share of meaningful changes; D_w.
- The training split is reported descriptively.

**Units and direction:** reported per metric in the results report (higher, lower or context).

**Input validation:** the analysis fails if any of these hold:
- a seed is duplicated, or a pair is missing in any fold;
- the arms differ in anything but κ and the label;
- folds do not match their declared boundaries;
- a fold's evaluation window lies outside its validation boundaries, or any row read is on or
  after 2020-01-01 (except fold C's sealed holdout, which is never read).

**No practical Sharpe threshold exists** in the repository. Effect sizes are described, and none
is invented after the results.

## 9. Outcome rule (mechanical)

| Outcome | Rule |
| --- | --- |
| **Inconclusive** | H9 not supported, or any fold has fewer than 5 complete pairs after the failure policy (§11). Takes precedence |
| **Walk-forward confirmation** | All three folds positive **and** mean Δ annualised net return > 0 in all three folds |
| **Partial confirmation** | Not confirmation, ≥ 2 folds positive and no fold negative |
| **Deterioration** | ≥ 2 folds negative |
| **No reliable improvement** | Otherwise (including a single positive fold) |

- **Reporting:** guard rails (H6–H8), the secondary permutation test and baselines are reported
  alongside and never change the outcome.
- **Test period:** no test-period result exists or is used.

## 10. Comparisons reported separately

- **E9 (historical; seeds 47–56, 2017–2019):** taken from the verified E9 comparison
  `0e88c06aefaeec31` and shown next to the folds. It is never pooled with E10 and never used to
  choose windows.
- **Baselines:** the three baselines of each fold's own validation evaluation (same window, costs
  and accounting). They are comparable **within** a fold, not across folds, because the windows
  differ.

## 11. Technical-failure policy

**Definitions:**
- **Valid run:** `status: completed`, the full budget, verified.
- **Failed:** an exception or a non-zero exit.
- **Interrupted:** the process stopped.
- **Evaluation or verification failure:** `verify` does not pass.

**Retry rule:**
- A failed or interrupted run is preserved and retried **once** with the same configuration, only
  for an infrastructure cause, and recorded.
- No retry after a completed run.
- Discovery accepts exactly one run per (fold, arm, seed).
- A pair still missing makes the outcome "Inconclusive" (the others are reported descriptively).
- No seed, fold or run is dropped or replaced because of its results.

**Slow runs:** never killed, and the budget never changes. No other heavy experiment runs
concurrently.

## 12. Procedure

```text
python scripts/walk_forward.py --experiment-config configs/walk_forward_{a,b}_k0.yaml build-fold --execute
python scripts/profile_experiment.py --dataset-dir <fold dataset> --experiment-config configs/walk_forward_<f>_k{0,1}.yaml train --arm main --execute
python scripts/profile_experiment.py --dataset-dir <fold dataset> --experiment-config configs/walk_forward_<f>_k{0,1}.yaml evaluate --split {train,validation} --execute
python scripts/profile_experiment.py ... compare-walk-forward --fold A <B val> <T1 val> <B train> <T1 train> --fold B ... --fold C ... --reproduce-validation <E8B> <E8T1> <E7B> <E7T1> --reproduce-train <...> --e9-comparison <0e88c06aefaeec31> --execute
```

**Rules:**
- **Commit order:** protocol, then implementation, then fold builds, full runs and evaluations from
  that clean commit, then the results commit.
- **Outputs:** write-once; every output verified.
- **During training:** no working-tree edits.
- **Pipeline check (EXP-023):** smoke runs and training-split pipeline-check evaluations for every
  fold and arm. It is excluded from every result.

## 13. Test-period boundary

- No row dated on or after 2020-01-01 is read for folds A and B: their datasets are derived by
  the bounded reader.
- Fold C reads exactly what E8 and E9 read: rows before 2020-01-01 for validation.
- There is no test evaluation, and test results influence nothing.

## 14. Limitations known in advance

- **One market history:** expanding folds share training rows; three validation windows.
- **Fold A:** a short training history (about 3.5 years, dominated by 2008–2010).
- **Fold C:** it repeats known E8 results by design.
- **Seeds:** five per fold.
- **Guard rails:** E8's judgement calls.
- **Unchanged limits:** downside risk is unavailable (D-076); the profile input is constant (no
  personalisation); validation-only evidence.

## 15. Amendments

None.
