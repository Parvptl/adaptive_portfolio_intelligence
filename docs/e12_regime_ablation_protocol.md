# E12: market-regime observation ablation under walk-forward validation, prespecified protocol (D-096)

> **Status:** written and fixed on 2026-11-05, **before any E12 implementation or training**, and
> committed on its own before the implementation.
> - **Experiment IDs:** EXP-027 (pipeline check) and EXP-028 (full experiment).
> - **Scope:** authorised by a team member's in-session instruction ("Claude Code Master Prompt —
>   E12: Market-Regime Observation Ablation"), under rule R-S (D-061: a decision communicated by
>   either teammate counts for both).
>   - **Policy:** the D-084 policy (§4) lists D-081 (regime-input ablation) as *not covered* and
>     says "a later instruction can add them". This instruction does.
> - **D-062 exception:** D-081 requires "a decision amending D-062 for this experiment only". The
>   instruction specifies that intervention, so for **E12 only** the observation omits the 9
>   regime inputs. **D-062 itself is unchanged** and stays the default observation.
> - **Design, criteria and decision rule:** Provisional (delegated) choices by Claude Code (D-096).
> - **Unchanged:** D-009, D-018 (open), D-094 and D-095 (provisional), and the D-066 budget.
> - **Amendments:** any later change is appended in §13 with a timestamp and reason.
> - **Research only;** simulated backtests on one market history; not financial advice.

## 1. Question

**Primary:** does removing the market-regime observation inputs improve PPO's walk-forward
validation net Sharpe, or do they carry useful information for its decisions?

**What E12 is:** one intervention, the regime inputs of the observation. It is not a reward,
environment, action-space, cost, κ, λ, budget, regularisation or feature-construction change, and
not a test-period experiment.

## 2. Audit (repository at `64e0ada`, clean, level with `origin/main`)

| Item | Verified fact |
| --- | --- |
| Observation (D-062 + D-085) | 56 inputs in this order: (1) 34 causal features, standardised with the training-fitted scaler and clipped ±10; (2) **9 regime one-hot inputs, unscaled** (labels `negative_low` … `positive_high`; indices 34–42); (3) 8 end-of-row weights (7 ETFs + cash), unscaled; (4) 5 profile inputs (constant 0.5) |
| Where regime labels are used | Only in the observation (`build_observation`) and the environment's construction check that every label is valid. The reward, accounting, actions, costs and termination never use them |
| How labels are made | `regimes.rules`: trend = market-group (equity) momentum over 63 sessions; volatility = market volatility over 21 sessions; thresholds fitted on the training partition (fold-specific in E10/E11) |
| Redundancy | **Both source features are already observed**, as `equity_mom_63` and `market_vol_21` among the 34. The one-hot is a coarse, train-calibrated discretisation of two observed inputs, not new information |
| Isolation | The one-hot is a separate, unscaled block. The scaler covers only the 34 features. Removing the block changes no other input, the scaler, the feature or regime pipelines, or any environment behaviour |
| Reference | E10T1 (κ = 0.0015, λ = 0, the D-066 budget of 100,352 realised timesteps, seeds 42–46, E10's folds). E11R reproduced it exactly. Evaluations: validation A `418f2fcf3c01cb9a`, B `f89f3649d82a41a8`, C `24626392a5a36572`; training A `7611fafcba4afa42`, B `854253dd8c688803`, C `7d83179bd45ef46d` |
| Prior attempts | None: D-081 is a plan only (Proposed); no ablation run exists |

## 3. Design

**Arms** (κ = 0.0015, λ = 0 and the D-066 budget in both; everything else as E10T1):

| Arm | Observation | Inputs | Configs |
| --- | --- | --- | --- |
| **E12F** (control, full observation) | unchanged | 56 | `configs/ablation_{a,b,c}_full.yaml` |
| **E12N** (no regime inputs) | the 9 regime one-hot inputs removed; features, weights and profile unchanged and in the same order | **47** | `configs/ablation_{a,b,c}_noregime.yaml` |

**Removed:** the one-hot inputs for the 9 labels `negative_low`, `negative_normal`,
`negative_high`, `neutral_low`, `neutral_normal`, `neutral_high`, `positive_low`,
`positive_normal`, `positive_high`.

**Configuration rules:**
- **Generated from one template.** Within a fold the arms differ only in `label` and the new
  optional `observation_ablation: regime`.
- **E12F** equals E10T1 except `label` and the output roots. It is a **reproduction**, and must
  equal E10T1 exactly (H9).

**Folds:** E10's, with expanding training from 2007:

| Fold | Training | Validation |
| --- | --- | --- |
| A | → 2010 | 2011–2013 |
| B | → 2013 | 2014–2016 |
| C | → 2016 | 2017–2019 (= D-009) |

- **Fold inputs:** folds A and B use the verified pre-2020 fold datasets and fold-fitted
  thresholds.
- **Labels in E12N:** regime labels are still computed and validated (unchanged pipeline). They
  are just not observed.

**Seeds:** 42–46, paired within folds, giving **30 full runs**.

**Evaluations:** training and validation splits for every fold and arm, 12 in total.

**Outputs:** `data/processed/ablation_{experiments,evaluations,comparisons}`.

## 4. Shared-code change (minimal; backward compatible)

**Config:** an optional experiment key `observation_ablation`, whose only allowed value is
`regime`.
- Written to the identity only when set, so E1–E11 identities are unchanged.

**Wrapper:** a thin Gymnasium `ObservationWrapper` (`environment/observation_ablation.py`).
- It deletes exactly the 9 regime positions from `PortfolioEnv`'s observation and observation
  space, and is applied **before** the profile wrapper.
- It is used in both places profile environments are built: training (`ppo.train_ppo_run`) and
  evaluation (`evaluate_profiles`).
- It changes nothing else; rewards, info and actions pass through.

**Identity:** the run identity's `observation_size` becomes 47 for E12N.

**E0 comparability:** for fold C, the check "observation size = E0 + 5" becomes
"E0 + 5 − 9" for an ablated experiment.

## 5. Hypotheses and criteria (validation unless stated)

**Definitions:**
- **Paired difference:** d_{f,s} = metric(E12N) − metric(E12F).
- **Positive fold:** mean ΔSharpe > 0 and ≥ 4/5 seeds positive.
- **Negative fold:** mean ΔSharpe < 0 and ≥ 4/5 seeds negative.
- **Gap:** training-split net Sharpe − validation net Sharpe.

| | Hypothesis | Supported | Partially | Otherwise |
| --- | --- | --- | --- | --- |
| **H1** | **Primary: validation net Sharpe** | mean ΔSharpe > 0 in all three folds | in some folds | not supported |
| H2 | Cross-fold consistency | ≥ 2 positive folds | exactly 1 | not supported |
| H3 | Return preservation | in every fold: mean Δ annualised net return ≥ −0.5 pp a year | in some folds | not supported |
| H4 | Not via inactivity or higher costs | in every fold: E12N median turnover ≥ 50% of E12F's **and** mean Δ cost drag ≤ +1.0 pp over the window | in some folds | none |
| H5 | Risk | in every fold: median Δ volatility ≤ +0.5 pp a year and median drawdown deepening ≤ 2 pp | in some folds | none |
| H6 | Composition | in every fold, E12N medians: risky HHI ≤ 2/3, target cash ≤ 0.40, near-all-cash share ≤ 0.05 (E8 limits) | in some folds | none |
| H7 | Responsiveness | in every fold: E12N median dispersion and meaningful-change share ≥ 50% of E12F's, D_w ≥ 25% | in some folds | none |
| H8 | Baseline gap (separate question) | in every fold the gap from the best baseline to the arm's median Sharpe is smaller for E12N | in some folds | none |
| H9 | Reproduction and integrity | E12F = E10T1 exactly in every fold and split (≤ 1e-12); every run's recorded observation size is 56 (E12F) or 47 (E12N); every run realised 100,352 timesteps; fold A and B integrity verified; E0 reproduces EXP-006 in fold C | — | not supported |

**Reported, never decisive:**
- the gap change and its attribution (validation-driven vs a lower training fit, as in E11);
- whether either arm reaches a baseline;
- individual seeds beating baselines.

## 6. Statistical analysis plan

E10/E11 conventions, applied to E12N − E12F.

**Within each fold (n = 5), for every endpoint:**
- per-seed values and differences;
- mean, median, SD, SE, and counts of positive, negative and tied differences;
- a percentile bootstrap 95% CI (10,000 resamples, `default_rng(20261104)`);
- a t-interval (df 4);
- the exact sign-flip p (2⁵; ≥ 0.0625, descriptive).

**Across folds:** fold classes, the fold-mean range and shares, and one secondary stratified
sign-flip test (2¹⁵).
- **Dependence caveat:** seeds share one history and folds share training rows. Nothing treats the
  15 pairs as independent markets.

**Endpoints:**
- net Sharpe; annualised net return; gross and net cumulative return; cost drag; turnover;
- volatility; maximum drawdown;
- cash; risky HHI; dispersion; meaningful-change share; D_w;
- training values and the gap.

**No practical Sharpe threshold exists.** The thresholds above are fixed here.

## 7. Outcome rule (mechanical)

| Outcome | Rule |
| --- | --- |
| **Inconclusive** | H9 not supported, or any fold has fewer than 5 complete pairs. Takes precedence |
| **Generalisation improvement** | All three folds positive **and** H3 supported |
| **Partial improvement** | Not the above, ≥ 2 folds positive and no fold negative |
| **Deterioration** | ≥ 2 folds negative (the regime inputs then appear useful) |
| **No reliable improvement** | Otherwise (no consistent evidence either way) |

- **Reporting:** H4–H8 are reported alongside.
- **Defaults:** no outcome changes D-062 or the default observation. That needs a separate team
  decision.

## 8. Comparisons reported separately

- **Baselines:** each fold's own baselines, from that fold's E12 validation evaluation.
  Comparable within a fold only.
- **E10 and E11:** shown as context, not pooled.

## 9. Technical-failure policy

As E9–E11:
- A failed or interrupted run is preserved and retried once, for an infrastructure cause only,
  and recorded.
- No retry after completion, and no choice between successful attempts.
- A missing pair makes the outcome "Inconclusive".
- Slow runs are never killed, the registered experiment is never altered, and no other heavy
  experiment runs concurrently.

## 10. Procedure

```text
python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/ablation_<f>_{full,noregime}.yaml train --arm main --execute
python scripts/profile_experiment.py ... --experiment-config configs/ablation_<f>_{full,noregime}.yaml evaluate --split {train,validation} --execute
python scripts/profile_experiment.py ... --experiment-config configs/ablation_c_full.yaml compare-ablation --fold A <F val> <N val> <F train> <N train> --fold B ... --fold C ... --reproduce-validation <E10T1 A> <E10T1 B> <E10T1 C> --reproduce-train <E10T1 A> <E10T1 B> <E10T1 C> --e10-comparison <fb8de80f69600763> --execute
```

**Rules:**
- **Commit order:** protocol, then implementation, then the pipeline check (EXP-027), full runs and
  evaluations from that clean commit, then the results commit.
- **Outputs:** write-once; verified.
- **During training:** no working-tree edits.

## 11. Test-period boundary

- Folds A and B use the pre-2020 fold datasets. Fold C reads rows before 2020-01-01 only.
- There is no test evaluation.

## 12. Limitations known in advance

- **One market history:** shared expanding training rows; three windows; five seeds per fold.
- **Redundancy:** the regime inputs are a function of two observed features, so the ablation tests
  the value of that discretisation (and its fold-specific calibration), not of the information
  itself.
- **Architecture:** the network's first layer has 9 fewer inputs (47 vs 56). The architecture is
  otherwise identical, and this is inherent to an input ablation.
- **Unchanged limits:** downside risk is unavailable; the profile input is constant; validation
  only.

## 13. Amendments

None.
