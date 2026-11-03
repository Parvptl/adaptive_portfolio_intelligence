# E8: turnover-penalty refinement and allocation responsiveness, prespecified methodology (D-092)

> **Status:** written and fixed on 2026-11-04, **before any E8 implementation or training**.
> - **Experiment IDs:** EXP-019 (pipeline check) and EXP-020 (full experiment).
> - **Scope:** authorised by a team member's in-session instruction ("E8 Master Prompt — Turnover
>   Penalty Refinement & Allocation Responsiveness"; R-S).
> - **Coefficients, metrics and criteria:** Provisional (delegated) choices by Claude Code
>   (D-092). They are not team-reviewed.
> - **Research only;** not financial advice.
> - **Results (appended 2026-11-04):** EXP-020 completed under this protocol unchanged;
>   outcome C. See `docs/e8_results.md`.

## 1. Question and motivation

**Question:** can a refined turnover penalty improve the trade-off between transaction-cost
reduction and portfolio responsiveness?

**Motivation (EXP-018, `docs/e7_results.md`):**
- **κ = 0.0015 (E7T1)** cut validation cost drag by about 4 pp while keeping gross return and
  responsiveness.
- **κ = 0.0075 (E7T2)** cut it by about 10 pp, but became near-static: 57% cash, one dominant
  risky fund (HHI 0.93), reallocation activity 17% of the control's, and worse in-sample in every
  seed.
- **Between the two:** the curve is unknown, and E7's outcome rule did not use responsiveness.
- **Unchanged:** every PPO arm is below the simple baselines, and five seeds leave the Sharpe
  effects uncertain.

**Principle:** lower turnover is not automatically better. An arm that saves costs by sitting
in cash or in one position is not counted as a successful result (H6, H7 and the outcome rule).

## 2. Audit (repository at `a5d0f0f`, clean, level with `origin/main`)

| Item | Verified implementation |
| --- | --- |
| E7 commits | Implementation `c682e32`, results `a5d0f0f`; comparison `9ddf7284e9c26661` VERIFIED (outcome A, H6 partial) |
| E7 configs | `configs/turnover_k{0,1,2}.yaml`: κ = 0 / 0.0015 / 0.0075, λ = 0, constant profile 0.5, configuration 4, seeds 42–46 |
| Reward | `ProfileRewardSpec.components`: r = r_base − (λ/2)·Σ net_return² − κ·TN; `ProfileRewardEnv` passes TN = the step's recurring traded notional, 0 for the funding step |
| Turnover and cost | `simulator.step`: TN = Σ\|Δw\| over the 7 ETFs (cash leg excluded); cost = 0.0015·TN, inside r_base through the ledger. Reported turnover = recurring TN × 252 / return periods (D-059) |
| Allocation metrics | `profile_analysis.behaviour_metrics` on the decision targets (8 columns, cash last): `target_{equity,bonds,gold,cash}`, `share_target_cash_above_95`, `target_risky_hhi` (Herfindahl index of the risky sleeve), `allocation_stability_dw` = mean over decisions of (1/8)·Σ\|w_k − w_{k−1}\| |
| Responsiveness | Only `allocation_stability_dw`. It measures the **path length** of the targets, so it moves with turnover and cannot tell meaningful reallocations from small, noisy ones (§4) |
| Data | dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`; training decisions 2007-07-05 → 2016-12-30 (496); validation 2017-01-03 → 2019-12-31 (156); test 2020– sealed |
| Budget | 100,000 configured (configuration 4) → 100,352 realised timesteps (196 × 512) |
| Tests | 1,041 passing at `a5d0f0f` |

## 3. Design

**Arms** (λ = 0 in all; everything else as E7):

| Arm | κ | Role | Expected penalty at E6L's training turnover (median TN 0.487 per step; mean r_base about 0.0031) |
| --- | --- | --- | --- |
| **E8B** | 0 | Control; must reproduce E6L and E7B | — |
| **E8T1** | 0.0015 | Moderate reference; must reproduce E7T1 | about 0.00073 (24%) |
| **E8T2** | 0.003 | Intermediate (2× the cost rate) | about 0.00146 (47%) |
| **E8T3** | 0.0045 | Upper intermediate (3× the cost rate) | about 0.00219 (71%) |

- **Scale check:** both new values lie between E7's two trained values (24% and 119% of the mean
  base reward), so the reward scale is compatible and no amendment is needed.
- **Fixed in advance:** the values are the 1×, 2× and 3× multiples of the cost rate requested by
  the team, not chosen from any E8 output.
- **Historical reference:** κ = 0.0075 is **not** retrained. The verified E7T2 evaluations
  (`27223e4c92aa897e` validation, `a99a9a7ee29bc750` training) are shown as a labelled prior
  experiment. They are not used in any hypothesis.
- **Configurations:** `configs/turnover_refine_k{0,1,2,3}.yaml` differ **only** in `label` and
  `reward.turnover_penalty`. Outputs go to new directories
  `data/processed/turnover_refine_{experiments,evaluations,comparisons}`, so no E0–E7 output is
  touched.

## 4. Responsiveness and concentration measures

**Existing measures, reused unchanged:** `allocation_stability_dw` (D_w), `target_cash`,
`share_target_cash_above_95`, `target_risky_hhi`, `target_equity`, `target_bonds`, and the mean
held weights.

**Two new measures,** added to `behaviour_metrics` for every evaluation from E8 on:
- They are computed from the same decision targets of the training or validation episode only.
- They are additive: existing columns are unchanged.
- They are unit-tested.

| Metric | Definition | Reading |
| --- | --- | --- |
| `allocation_dispersion` | Mean over the 8 weight columns of the standard deviation (ddof 0) of the decision target weight across the episode's decisions | How **widely** the allocation moves over the period. A static portfolio scores about 0. Small jitter around one allocation scores low even if it trades a lot |
| `share_meaningful_changes` | Share of consecutive decisions whose target change ½·Σ\|w_k − w_{k−1}\| (8 columns) is ≥ 0.05, i.e. at least 5% of the portfolio reallocated | How **often** the policy makes a reallocation large enough to matter. With weekly decisions, 5% is the threshold fixed here |

**Why these two:**
- D_w is path length, which a turnover penalty lowers by construction.
- Dispersion separates real shifts from jitter.
- The meaningful-change share separates a few deliberate moves from many tiny ones.

**Not chosen:** allocation persistence and counts of distinct allocations. They are harder to
interpret and need extra thresholds.

**Not a target:** none of these measures should be maximised. Higher values are not better per
se; they are guard rails against a near-static policy.

## 5. Prespecified hypotheses and criteria

**Conventions:**
- **Pairing:** seed-paired; "≥ 4/5" means at least 4 of the 5 seeds.
- **Medians:** medians over the five seeds.
- **Refined arms:** E8T2 and E8T3; E8T1 is the reference they are judged against.
- **Units:** turnover is annualised recurring traded notional; cost drag is in pp over the
  window.

| | Hypothesis | Criterion (supported if all parts hold; partially if some) |
| --- | --- | --- |
| H1 | Turnover response | Median turnover strictly decreasing B > T1 > T2 > T3 on the training split **and** on validation; and on training, T2 < T1 and T3 < T2 in ≥ 4/5 seeds |
| H2 | Cost reduction | Validation: median cost drag strictly decreasing across the four arms; T2 < T1 and T3 < T2 in ≥ 4/5 seeds. **Accounting:** in every T1–T3 training run, the logged penalty equals κ × the logged traded notional in every episode (the penalty is applied once; the ledger cost is untouched) |
| H3 | Validation transfer | Validation turnover and cost drag both < T1 in ≥ 4/5 seeds for T2 and for T3; and for T2 and T3 the median relative turnover reduction vs B on validation is ≥ 50% of that on training |
| H4 | Net performance | For T2 and for T3, vs T1 (validation): median paired net Sharpe difference ≥ 0 and median paired annualised net return difference ≥ 0 |
| H5 | Risk preservation | For T2 and for T3, vs T1 (validation): median paired volatility increase ≤ 0.5 pp a year, and median paired deepening of the maximum drawdown ≤ 2 pp |
| H6 | Responsiveness | For T2 and for T3 (validation medians): D_w ≥ 25% of E8B's (E7's convention); `allocation_dispersion` ≥ 50% of E8B's; `share_meaningful_changes` ≥ 50% of E8B's |
| H7 | Concentration and cash | For T2 and for T3 (validation medians): `target_risky_hhi` ≤ 2/3 (at least 1.5 effective risky positions; E7B 0.47, E7T1 0.51, E7T2 0.93); `target_cash` ≤ 0.40 (E7B's 0.25 + 15 pp; E7T2 0.57); `share_target_cash_above_95` ≤ 0.05 |
| H8 | Reproducibility | E8B equals E7B and E6L, and E8T1 equals E7T1, on both splits: maximum absolute difference ≤ 1e-12 for every shared per-seed metric |
| H9 | Practical utility | For at least one refined arm: median validation cost-drag reduction vs T1 ≥ 1 pp; mean paired validation turnover reduction vs T1 > the median within-arm seed SD of validation turnover; **and** the arm passes all its H6 and H7 parts (the saving does not come from suppressed activity) |

- **Downside risk:** not available from the evaluator (D-076). It is not computed with a new
  definition.
- **Thresholds:** all are fixed here from E7's conventions and E7's verified values. None can be
  changed after E8 outputs exist.

## 6. Outcome rule (mechanical)

For each refined arm k ∈ {T2, T3}:
- **Cost-efficient:** validation turnover < T1 and cost drag < T1 in ≥ 4/5 seeds.
- **Activity kept:** all H6 and H7 parts for k hold.
- **Performance kept:** all H4 and H5 parts for k hold.

| Outcome | Rule |
| --- | --- |
| **Unresolved** | H8 not supported. Interpretation stops until the drift is explained; it is not attributed to κ |
| **A, balanced improvement** | Some k is cost-efficient, keeps activity **and** keeps performance |
| **B, partial improvement** | Not A, and some k is cost-efficient and keeps either activity or performance |
| **C, no reliable improvement** | Otherwise |

- **Reporting:** the comparison reports which arms meet which conditions. If both meet A, both
  are reported. No arm is selected for the test period here.

## 7. Statistics and descriptive questions

**Paired differences, on both splits:**
- **vs the control:** T1 − B, T2 − B, T3 − B;
- **vs the moderate reference:** T2 − T1, T3 − T1;
- **vs the nearest lower κ:** T3 − T2 (T2's is T1).

**Reported:**
- seed values, mean, SD (ddof 1), median, range and sign count;
- a descriptive t-interval (t₀.₉₇₅,₄ = 2.776), effect size d and the median relative
  difference;
- within-arm seed SDs.

**Caveats:** the five seeds share one market history, so they are not independent market
samples. There are no p-values and no significance claims.

**Descriptive questions, answered in the report (not hypotheses):**
1. Does seed 44 still behave differently?
2. Do the intermediate penalties improve validation performance?
3. Does T3 begin to suppress responsiveness?
4. Do the training effects transfer to validation?
5. Do cost savings explain the net changes (gross vs net returns)?

## 8. Procedure

```text
python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/turnover_refine_k{0,1,2,3}.yaml train --arm main --execute
python scripts/profile_experiment.py ... --experiment-config configs/turnover_refine_k{0,1,2,3}.yaml evaluate --split {train,validation} --execute
python scripts/profile_experiment.py ... --experiment-config configs/turnover_refine_k0.yaml compare-refine --validation <k0..k3> --train <k0..k3> --e7-validation <E7B> <E7T1> --e7-train <E7B> <E7T1> --e6-validation <E6L> --e6-train <E6L> --historical-validation <E7T2> --historical-train <E7T2> --reference ... --execute
```

**Rules:**
- full runs only from a clean commit; write-once outputs; every output verified;
- E0 must reproduce EXP-006;
- no working-tree edits during training; unrelated processes are not touched.
- **Retry rule:** a run that fails for an infrastructure reason (process crash, lock) is retried
  once with the same seed and configuration, and the failure is recorded. Any other failure stops
  the experiment. No seed is dropped.

## 9. Test-period boundary

- No test-period row is read, and there is no test evaluation.
- Test performance stays **unmeasured**.

## 10. Limitations known in advance

- **Coefficients:** four κ values on one linear penalty, so it remains coarse.
- **Data and statistics:** one market history; five seeds; a mostly calm validation period.
- **New measures:** the 5% threshold and the 50% ratios are judgement calls fixed in advance.
  They are guard rails, not validated definitions of good allocation.
- **Historical reference:** E7T2 does not have the two new measures, because its evaluations
  predate them and are not recomputed.
- **Design:** the constant profile input; no personalisation.
