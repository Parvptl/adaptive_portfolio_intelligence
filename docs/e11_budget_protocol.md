# E11: PPO training-budget reduction under walk-forward validation, prespecified protocol (D-095)

> **Status:** written and fixed on 2026-11-04, **before any E11 implementation or training**, and
> committed on its own before the implementation.
> - **Experiment IDs:** EXP-025 (pipeline check) and EXP-026 (full experiment).
> - **Scope:** authorised by a team member's in-session instruction ("Claude Code Master Prompt —
>   E11: PPO Training-Budget Reduction"; R-S).
> - **Design, criteria and decision rule:** Provisional (delegated) choices by Claude Code (D-095).
> - **Labelled exploratory experiment** (D-084 §4: a validation-prompted change is a new experiment
>   and never replaces the original). The D-066 per-run budget in `configs/agent.yaml` (100,000) is
>   **not** revised. Adopting another budget would need a team decision.
> - **Unchanged:** D-009 (split), D-018 (open) and D-094 (provisional).
> - **Amendments:** any later change is appended in §13 with a timestamp and reason. Nothing above
>   §13 is edited after full training starts.
> - **Research only;** simulated backtests on one market history; not financial advice.

## 1. Question

**Primary:** does halving PPO's training budget improve walk-forward validation net Sharpe, and
reduce the in-sample versus validation gap, while keeping the E10 moderate-penalty behaviour?

**What E11 is:** one intervention, the total training timesteps. It is not a κ or λ search, early
stopping, validation-based checkpoint selection, new regularisation, new features, folds, costs or
windows, and not a test-period experiment.

## 2. Audit (repository at `9911cab`, clean, level with `origin/main`)

| Item | Verified fact |
| --- | --- |
| E10 | Protocol `3019f46`, implementation `5939c17`, results `9911cab`. Comparison `fb8de80f69600763` VERIFIED: outcome "Walk-forward confirmation". The E10T1 (κ = 0.0015) validation evaluations are A `418f2fcf3c01cb9a`, B `f89f3649d82a41a8`, C `24626392a5a36572`; training A `7611fafcba4afa42`, B `854253dd8c688803`, C `7d83179bd45ef46d` |
| Overfitting (E10T1 medians) | In-sample net Sharpe 2.95 / 2.00 / 1.31 against validation −0.06 / 0.005 / 0.79 (folds A / B / C) |
| Budget | `agent.yaml` `total_timesteps: 100000` (D-066). `ppo.run_identity` requires `full` runs to use it, so it is realised as 100,352 = 196 rollouts × 512 (configuration 4, n_steps 512) |
| Schedules | Learning rate 1e-4 and clip range 0.2 are **constants** (no linear schedule), so the training budget only sets the number of rollout and update cycles |
| Checkpoint | Only the **final** checkpoint is saved (`model.zip`). No early stopping, no intermediate checkpoints, no validation-based selection (D-076) |
| Folds | E10's `walk_forward_fold` blocks. The A and B fold datasets and feature sets are already built and verified (`f7625695086aee81` / `61236f217f987d35`; `f3499a79c3a186c8` / `072593754556eced`); C = D-009 |

## 3. Design

**Arms** (κ = 0.0015 and λ = 0 in both; everything else as E10T1):

| Arm | Budget | Configs |
| --- | --- | --- |
| **E11R** (reference, E10 budget) | the D-066 default, 100,000 configured → **100,352** realised | `configs/budget_{a,b,c}_ref.yaml` |
| **E11H** (half budget) | `total_timesteps: 50176` → **50,176** realised (98 × 512 = exactly half of 100,352) | `configs/budget_{a,b,c}_half.yaml` |

**Configuration rules:**
- **Generated from one template.** Within a fold the two configs differ only in `label` and the
  new optional `total_timesteps`.
- **E11R** equals E10T1 (`walk_forward_{a,b,c}_k1.yaml`) except `label` and the output roots.
- These rules are checked programmatically.

**Folds:** exactly E10's (training expands from 2007):

| Fold | Training | Validation |
| --- | --- | --- |
| A | → 2010-12-31 | 2011–2013 |
| B | → 2013-12-31 | 2014–2016 |
| C | → 2016-12-31 | 2017–2019 (= D-009) |

**Seeds:** 42–46, paired within a fold. **Runs:** 3 folds × 2 arms × 5 seeds = **30 full runs**.

**Why E11R is retrained:** it is a **reproduction** of E10T1. It must equal E10T1 exactly (H9),
which shows that the E11 code changes leave the reference unchanged. Its runs are not a new
intervention.

**Expected mechanics (stated in advance; not used in any criterion):**
- The schedules are constant and training is deterministic.
- An E11H run is therefore expected to equal its E11R twin's trajectory stopped after 98 of 196
  rollouts.
- The comparison is between two fixed budgets of the same training process, not a validation-
  selected stopping point.

**Outputs:** `data/processed/budget_{experiments,evaluations,comparisons}`; no E0–E10 output is
touched.

**Evaluations:** for every fold and arm, the training and validation splits, giving 12 in total.

## 4. Shared-code change (minimal; backward compatible)

**`ProfileExperimentConfig.total_timesteps`** (optional, a positive integer):
- **Identity:** written to the experiment identity only when set, so E1–E10 identities are
  unchanged.
- **Use:**
  - `train_arm` uses it as the configured budget of `full` runs;
  - `ppo.run_identity` accepts it only for a profile run whose experiment declares it;
  - smoke runs must stay below it.
- **`load_context`:** requires a multiple of the base configuration's `n_steps`, so realised =
  configured.
- **E0 comparability:** "same budget as E0" becomes "budget equals the experiment's declared
  budget" for such experiments.
- **Recording:** `timesteps_done` is recorded per run (unchanged), and the analysis checks it
  against the registered budget.

## 5. Hypotheses and criteria (validation unless stated)

**Definitions:**
- **Paired difference:** d_{f,s} = metric(E11H) − metric(E11R) for fold f and seed s.
- **Positive fold:** mean ΔSharpe > 0 and ≥ 4/5 seeds positive.
- **Negative fold:** mean ΔSharpe < 0 and ≥ 4/5 seeds negative.
- **Gap:** for each run, gap = training-split net Sharpe − validation net Sharpe.

| | Hypothesis | Supported | Partially | Otherwise |
| --- | --- | --- | --- | --- |
| **H1** | **Primary: validation net Sharpe** | mean ΔSharpe > 0 in all three folds | in some folds | not supported |
| H2 | Cross-fold consistency | ≥ 2 positive folds | exactly 1 | not supported |
| H3 | Overfitting reduction | in every fold: mean Δgap < 0 and ≥ 4/5 seeds lower | in some folds | not supported |
| H4 | Return preservation | in every fold: mean Δ annualised net return ≥ −0.5 pp a year | in some folds | not supported |
| H5 | Not via inactivity, cash or concentration | in every fold, E11H medians: risky HHI ≤ 2/3, cash ≤ 0.40, near-all-cash share ≤ 0.05 (E8 limits), and median turnover ≥ 50% of E11R's | in some folds | none |
| H6 | Responsiveness | in every fold: E11H median dispersion and meaningful-change share ≥ 50% of E11R's, D_w ≥ 25% (E8) | in some folds | none |
| H7 | Risk | in every fold: median Δ volatility ≤ +0.5 pp a year and median drawdown deepening ≤ 2 pp | in some folds | none |
| H8 | Baseline gap (separate question) | in every fold the gap between the best baseline's Sharpe and the arm's median Sharpe is smaller for E11H than for E11R | in some folds | none |
| H9 | Reproduction and integrity | E11R = E10T1 exactly in every fold and split (≤ 1e-12, every shared metric); every run's `timesteps_done` equals its registered budget (100,352 / 50,176); E10's fold-integrity checks pass for A and B; E0 reproduces EXP-006 in fold C | — | not supported |

**Attribution of the gap (reported for H3, never decisive):** per fold, Δgap = Δtrain − Δvalidation.
- **"Genuine":** the gap shrinks and validation Sharpe rises (Δvalidation > 0).
- **"Training loss only":** the gap shrinks only because training Sharpe falls (Δvalidation ≤ 0).

**H8** also reports, per fold, whether either arm reaches or exceeds any baseline.

## 6. Statistical analysis plan

E10's conventions, applied to E11H − E11R.

**Within each fold (n = 5), for every endpoint:**
- per-seed values and differences;
- mean, median, SD, SE, and counts of positive, negative and tied differences (|d| ≤ 1e-12);
- a percentile bootstrap 95% CI (10,000 resamples, `default_rng(20261104)`);
- a t-interval (df 4);
- the exact sign-flip p (2⁵; smallest attainable 0.0625, so descriptive only).

**Across folds:** fold classes, the fold-mean range, each fold's share of the summed effect, and
one secondary stratified sign-flip test of the average fold mean (2¹⁵).
- **No interval across three folds.**
- **Dependence caveat:** the seeds share one market history, and the folds share training rows.
  Nothing treats the 15 pairs as independent markets, and no small p-value is read as regime
  replication.

**Endpoints** (E10 definitions):
- net Sharpe; annualised net return; gross and net cumulative return; cost drag; turnover;
- volatility; maximum drawdown;
- target cash; risky HHI; dispersion; meaningful-change share; D_w;
- training-split values and the gap.

**No practical Sharpe threshold exists.** The −0.5 pp (H4), 50% (H5, H6) and E8 limits are fixed
here, and no other threshold is added after results.

## 7. Outcome rule (mechanical)

| Outcome | Rule |
| --- | --- |
| **Inconclusive** | H9 not supported, or any fold has fewer than 5 complete pairs. Takes precedence |
| **Generalisation improvement** | All three folds positive, **and** H4 supported, **and** in every fold the gap attribution is "genuine" |
| **Partial improvement** | Not the above, ≥ 2 folds positive and no fold negative |
| **Deterioration** | ≥ 2 folds negative |
| **No reliable improvement** | Otherwise |

- **Reporting:** H5–H8 are reported alongside.
- **Defaults:** no outcome changes the default training budget. That needs a team decision.
- **Test period:** no test-period result exists or is used.

## 8. Comparisons reported separately

- **E10:** the κ effect, fold means +0.082 / +0.221 / +0.232. It is context only: E11 compares
  budgets, not κ.
- **Baselines:** each fold's baselines from that fold's own E11 validation evaluation (comparable
  within a fold only).

## 9. Technical-failure policy

As E9 and E10:
- A failed or interrupted run is preserved and retried once, for an infrastructure cause only,
  and recorded.
- No retry after completion, and no choice between successful attempts.
- A missing pair makes the outcome "Inconclusive".
- Slow runs are never killed, and no other heavy experiment runs concurrently.

## 10. Procedure

```text
python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/budget_<f>_{ref,half}.yaml train --arm main --execute
python scripts/profile_experiment.py ... --experiment-config configs/budget_<f>_{ref,half}.yaml evaluate --split {train,validation} --execute
python scripts/profile_experiment.py ... --experiment-config configs/budget_c_ref.yaml compare-budget --fold A <R val> <H val> <R train> <H train> --fold B ... --fold C ... --reproduce-validation <E10T1 A> <E10T1 B> <E10T1 C> --reproduce-train <E10T1 A> <E10T1 B> <E10T1 C> --e10-comparison <fb8de80f69600763> --execute
```

**Rules:**
- **Commit order:** protocol, then implementation, then the pipeline check, full runs and
  evaluations from that clean commit, then the results commit.
- **Outputs:** write-once; every output verified.
- **During training:** no working-tree edits.
- **Pipeline check (EXP-025):** smoke runs and training-split pipeline-check evaluations for all
  six configs. It is excluded from every result.

## 11. Test-period boundary

- Folds A and B use the verified pre-2020 fold datasets. Fold C reads rows before 2020-01-01
  only.
- There is no test evaluation.

## 12. Limitations known in advance

- **One market history:** shared, expanding training rows; three windows; five seeds per fold.
- **Budgets:** two values only, so this is not a budget curve.
- **Truncation:** E11H is expected to be a truncated E11R trajectory.
- **Unchanged limits:** downside risk is unavailable (D-076); the profile input is constant;
  validation-only evidence.

## 13. Amendments

None.
