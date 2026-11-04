# E9: turnover-penalty confirmation study, prespecified protocol (D-093)

> **Status:** written and fixed on 2026-11-04, **before any E9 implementation or training**, and
> committed on its own before the implementation.
> - **Experiment IDs:** EXP-021 (pipeline check) and EXP-022 (full confirmation experiment).
> - **Scope:** authorised by a team member's in-session instruction ("Claude Code Master Prompt —
>   E9: Turnover Penalty Confirmation Study"; R-S).
> - **Design, decision rule and thresholds:** Provisional (delegated) choices by Claude Code
>   (D-093). They are not team-reviewed.
> - **Amendments:** any later change is appended in §13 with a timestamp and reason. Nothing above
>   §13 is edited after full training starts.
> - **Research only;** simulated backtests on one market history; not financial advice.

## 1. Question

**Primary:** does the moderate turnover penalty κ = 0.0015 produce a reproducible improvement in
validation net Sharpe over κ = 0, or was the E7/E8 result primarily seed variation?

**What E9 is:** a confirmation study with **two arms and new seeds**. It is not a new κ search, a
reward or risk experiment, a personalisation experiment, a walk-forward experiment or a test-period
experiment.

**Historical evidence (verified, not re-derived):**
- In E7/E8 (seeds 42–46), validation net Sharpe was 0.512 (κ = 0) vs 0.788 (κ = 0.0015), a
  median of 0.51 vs 0.79.
- The paired mean was +0.232 (t-interval −0.148 to 0.613), positive in 4 of 5 seeds.
- Sources: comparisons `9ddf7284e9c26661` and `2a4d574cd9c95bbc`.

## 2. Audit (repository at `1f8195e`, clean, level with `origin/main`)

| Item | Verified implementation |
| --- | --- |
| E8 commits | Implementation `d4732b0`, results `1f8195e`; comparison `2a4d574cd9c95bbc` VERIFIED; E8B = E7B = E6L and E8T1 = E7T1 exactly (26 metrics, both splits, maximum difference 0.0) |
| Arms to confirm | `configs/turnover_refine_k0.yaml` (E8B, κ = 0) and `_k1.yaml` (E8T1, κ = 0.0015): λ = 0, configuration 4 (lr 1e-4, n_steps 512, ent_coef 0), constant profile 0.5, profile stream 5, budget 100,000 configured → 100,352 realised timesteps |
| Reward | r = r_base − κ·TN_k; TN_k = recurring ETF traded notional (funding step 0); the 0.0015·TN cost is charged once, in r_base, by the unchanged ledger |
| Metrics | Annualised net Sharpe = √252 × mean / SD (ddof 1) of daily net returns, rf 0; turnover = recurring traded notional × 252 / return periods; cost drag = gross cumulative − net cumulative return; E8 allocation and responsiveness columns (`target_cash`, `target_risky_hhi`, `allocation_dispersion`, `share_meaningful_changes`, `allocation_stability_dw`) |
| Baselines | In every evaluation, on the same window and costs (`configs/backtest.yaml`): `buy_and_hold_equal_weight` (never rebalanced; 1.355 on validation), `equal_weight_monthly` (1.470) and `inverse_volatility_monthly` (63-session lookback; 1.754). Initial funding is charged |
| **Seed constraint** | `configs/agent.yaml` (D-066, accepted) defines the grid seeds 42–46. `load_context`, `ppo.run_identity` and the evaluator's E0 comparability accept **only grid seeds**, and E0 (the EXP-005 grid) exists only for 42–46. **Seeds 47–56 cannot run without a code change** |
| Statistics | The repository uses descriptive paired seed statistics (t-interval, sign counts). No practical-significance threshold for Sharpe has ever been established. scipy is not a dependency |

## 3. Design

**Arms:**

| Arm | κ | λ | Config |
| --- | --- | --- | --- |
| **E9B** (control) | 0 | 0 | `configs/confirmation_k0.yaml` |
| **E9T1** (moderate) | 0.0015 | 0 | `configs/confirmation_k1.yaml` |

- **Identical otherwise:** both configs equal E8B/E8T1 except `label`, `seeds`, the new
  `extension_seeds` and the output directories. This is checked programmatically (tests and
  `validate_config`).

**Seeds:** each arm trains seeds **42–56**, split into fixed populations:

| Population | Seeds | Role |
| --- | --- | --- |
| **Primary (confirmation)** | 47–56 (10 seeds) | The only population used for the primary endpoint, the hypotheses and the outcome |
| **Reproduction** | 42–46 (5 seeds) | H9 only: must equal E8B/E8T1 (and E7B/E7T1) exactly. They are retrained because E9 changes shared code (§4), so reproduction must be re-shown at the E9 commit. **Not** part of the confirmation sample |
| **Pooled (secondary)** | 42–56 (15 seeds, E9's own runs, each seed once) | Descriptive secondary analysis only, clearly labelled. It never decides the outcome |

- **Run count:** 2 arms × 15 seeds = **30 full runs**: 20 confirmation runs, the requested
  structure, plus 10 reproduction runs.
- **Seed validity:** 47–56 are not used by any earlier experiment or grid run. Each (arm, seed)
  has exactly one run, and training is deterministic (`torch` deterministic algorithms, one
  thread).
- **Budget:** 100,352 timesteps per run, identical for both arms, as E8.

**Output directories:** `data/processed/confirmation_{experiments,evaluations,comparisons}`. No
E0–E8 output is touched.

**Evaluations:** one per arm and split (training, validation), each covering all 15 seeds, giving
4 in total.
- They include E0 for seeds 42–46 and the three baselines.
- E0 must reproduce EXP-006 on validation.

## 4. Required shared-code change (seed extension)

**Change:** a new optional experiment key **`extension_seeds`**.
- It must be a subset of `seeds`, and must not include any `agent.yaml` grid seed.
- For an extension seed, the run spec is the base configuration's grid spec with only the seed
  replaced (same learning rate, n_steps, ent_coef and budget).

**Where it applies:**
- **`load_context` and `run_spec`:** extension seeds are accepted.
- **`ppo.run_identity`:** accepts such a spec only for a profile run whose experiment declares
  the seed.
- **Evaluator comparability:** for extension seeds, the check "same grid run spec as E0" compares
  the spec **without the seed**. Every other check (environment, hyperparameters, SB3 constants,
  scaler, data, budget) is unchanged.
- **E0:** evaluated only for the grid seeds that exist.

**Backward compatibility:**
- The key is written to the experiment identity only when non-empty, so E1–E8 identities are
  unchanged (tested).
- Grid training and every existing experiment follow the unchanged path.
- `configs/agent.yaml` (D-066) is **not** modified.

**Verification:** the 42–46 reproduction runs (H9) show empirically that training and evaluation
are unchanged at the E9 commit.

## 5. Hypotheses and criteria (primary population, 10 paired seeds, validation split)

**Paired difference:** d_i = metric(E9T1, seed i) − metric(E9B, seed i), computed from the saved
per-seed metrics (unrounded).

**Statistics (§6):** "CI" is the bootstrap 95% CI of the mean; "p" is the exact permutation
p-value.

| | Hypothesis | Supported | Partially | Otherwise |
| --- | --- | --- | --- | --- |
| H1 | Turnover response | mean d < 0, CI upper < 0, and ≥ 8/10 seeds lower | mean d < 0 | not supported |
| H2 | Cost-drag reduction | as H1, on `cost_drag` | mean d < 0 | not supported |
| **H3** | **Net Sharpe (primary)** | mean d > 0, CI lower > 0, p < 0.05, and ≥ 7/10 seeds positive | mean d > 0 and ≥ 6/10 positive | not supported |
| H4 | Annualised net return | as H3, on `net_annualised_return` | mean d > 0 and ≥ 6/10 positive | not supported |
| H5 | Gross vs cost decomposition | (a) `cost_drag` = gross cumulative − net cumulative for every seed and arm (≤ 1e-12), **and** (b) mean cost-drag saving ≥ mean gross cumulative-return loss, i.e. saved costs compensate the gross change | (a) holds, (b) fails | (a) fails |
| H6 | Risk stability | median paired volatility increase ≤ 0.5 pp a year **and** median paired max-drawdown deepening ≤ 2 pp (E7/E8 convention) | one part | neither |
| H7 | Allocation composition | E9T1 validation medians: risky HHI ≤ 2/3, mean target cash ≤ 0.40, near-all-cash share ≤ 0.05 (E8 limits, D-092) | some parts | none |
| H8 | Allocation responsiveness | E9T1 medians ≥ 50% of E9B's for `allocation_dispersion` and `share_meaningful_changes`, and ≥ 25% for D_w (E8 convention). Turnover is never used as a substitute | some parts | none |
| H9 | Reproduction | Seeds 42–46: E9B = E8B and E7B, and E9T1 = E8T1 and E7T1, on both splits, with maximum absolute difference ≤ 1e-12 on every shared per-seed metric; and E0 reproduces EXP-006 | — | not supported |
| H10 | Practical utility | H3 and H4 supported, **and** H6, H7 and H8 supported | H3 at least partially supported, and H7 and H8 at least partially | not supported |

**Not decisive:** H1 and H2 alone never make H10 or the outcome positive.

## 6. Statistical analysis plan

**Unit:** the seed. The 10 primary paired differences are the observations. Dates, steps and
trades are never treated as samples.

**Reported for every endpoint:**
- control, treatment and paired differences per seed;
- mean, median, SD (ddof 1), SE;
- counts of positive, negative and tied differences (tie: |d| ≤ 1e-12);
- the intervals below.

**Primary interval:** a percentile bootstrap of the mean paired difference.
- 10,000 resamples of the 10 seed-level differences, with replacement;
- `numpy.random.default_rng(20261104)`;
- the 2.5th and 97.5th percentiles.

**Primary test:** an exact two-sided paired sign-flip permutation test of the mean difference.
- All 2¹⁰ = 1,024 sign assignments.
- p = share with |mean| ≥ |observed mean| (with a 1e-12 tolerance).
- This is the only formal test, chosen before training.

**Sensitivity analysis:**
- a paired t-interval (t₀.₉₇₅,₉ = 2.262; 14 df = 2.145 for the pooled sample) and the
  t-statistic;
- no t p-value (scipy is not a dependency, and the t-test is not the prespecified test).

**Validation of inputs (the analysis fails instead of guessing):**
- each seed appears exactly once per arm;
- both arms have the same seeds;
- the primary population is exactly 47–56;
- the arms differ only in κ and the label;
- the splits and data are identical.

**Secondary endpoints**, all with the same statistics:
- annualised net return; gross cumulative return; cost drag; turnover a year;
- net volatility; net max drawdown;
- mean target cash; risky HHI; allocation dispersion; share of meaningful changes; D_w.
- Training-split results are also reported, descriptively.

**Pooled secondary analysis:** 15 seeds with the same statistics (2¹⁵ sign flips, the same
bootstrap seed). It is labelled secondary.

**Interpretation limits:**
- Ten seeds from **one market history** are not ten markets. The intervals describe seed-to-seed
  (training) variability on this history, not generalisation.
- **No practical Sharpe threshold exists** in the repository, so the effect size is interpreted
  descriptively and none is invented after the results.

## 7. Outcome rule (mechanical; validation; primary population)

| Outcome | Rule |
| --- | --- |
| **Inconclusive (technical or methodological failure)** | H9 not supported, or fewer than 10 complete primary pairs after the failure policy (§9). Takes precedence |
| **Confirmation** | H3 supported **and** H4 supported |
| **Partial confirmation** | Not confirmation, and mean ΔSharpe > 0 with ≥ 6/10 seeds positive |
| **Deterioration** | Mean ΔSharpe < 0 and the CI upper bound < 0 |
| **No reliable improvement** | Otherwise |

- **Reporting:** H6–H8 and H10 are reported alongside. A confirmation with failed guard rails is
  reported as such, and H10 then stays unsupported.
- **Excluded from the decision:** baselines and the historical five seeds.
- **Test period:** no test-period result exists or is used.

## 8. Baseline comparison

The three baselines are read from the same verified E9 validation evaluation (same window, costs
and accounting) and reported **separately** from the paired test. They are not retrained.

## 9. Technical-failure policy

**Definitions:**
- **Valid run:** `status: completed`, the full budget, verified.
- **Failed:** an exception or a non-zero exit.
- **Interrupted:** the process stopped.
- **Evaluation or verification failure:** `verify` does not pass.

**Retry rule:**
- A failed or interrupted run is preserved (never deleted) and retried **once** with the same
  seed and configuration, only for an infrastructure cause (process crash, lock, out of memory),
  and recorded.
- No retry after a completed run, whatever its result.
- No choice between successful attempts: discovery accepts exactly one run per (arm, seed).
- A run failing twice leaves its pair missing. Then the outcome is "Inconclusive", and the
  available pairs are reported descriptively only.
- No seed is dropped or replaced, and the seed count never changes after results are seen.

**Slow runs:** a slow run is never killed. The process status is checked, the budget is never
changed, and no other experiment runs concurrently.

## 10. Procedure

```text
python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/confirmation_k{0,1}.yaml train --arm main --execute
python scripts/profile_experiment.py ... --experiment-config configs/confirmation_k{0,1}.yaml evaluate --split {train,validation} --execute
python scripts/profile_experiment.py ... --experiment-config configs/confirmation_k0.yaml compare-confirm --validation <B> <T1> --train <B> <T1> --reproduce-validation <E8B> <E8T1> <E7B> <E7T1> --reproduce-train <E8B> <E8T1> <E7B> <E7T1> --execute
```

**Rules:**
- **Commit order:** protocol, then implementation, then full runs from that clean commit, then
  the results commit.
- **Outputs:** write-once; every output verified.
- **During training:** no working-tree edits.
- **Pipeline check (EXP-021):** smoke runs and a training-split pipeline-check evaluation for both
  arms. It is excluded from every result.

## 11. Test-period boundary

- No test-period row is read, and there is no test evaluation.
- Test results influence nothing.
- Test performance stays **unmeasured**.

## 12. Limitations known in advance

- One market history and a calm validation period.
- Ten primary seeds share that history.
- Validation-only inference; no test or walk-forward evidence.
- The guard-rail thresholds are E8's judgement calls.
- Downside risk is unavailable (D-076).
- The constant profile input; no personalisation.

## 13. Amendments

None.
