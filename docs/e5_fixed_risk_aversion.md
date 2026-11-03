# E5: fixed risk-aversion PPO, prespecified methodology (D-089)

> **Status:** written and fixed on 2026-11-03, **before any E5 training**.
> - **Scope:** authorised by a team member's in-session instruction (R-S).
> - **Design and criteria:** Provisional (delegated) choices by Claude Code (D-089). They are not
>   team-reviewed.
> - **Research only;** not financial advice.

## 1. Question and why E5

**Question:** can PPO learn materially different, financially interpretable risk behaviour
when the risk-aversion coefficient λ is **fixed** at different levels, rather than set by an
investor profile?

**Why this experiment (from EXP-012):**
- E4's profile-dependent reward lowered average in-sample risk relative to E1, but did not
  produce profile-dependent behaviour.
- E5 separates two explanations:
  1. the reward and budget cannot move PPO's risk level;
  2. the risk level can move, but conditioning on the profile failed.

## 2. Audit of the E4 reward (repository at `89ebe75`)

- **Implementation:** `ProfileRewardSpec.components` in `environment/profile_reward.py`:

  ```text
  r = r_base − (λ/2) · RV
  RV = Σ net_return_t² over the step's own ledger rows (d_k, d_{k+1}]
  ```

  - r_base is the D-064 log growth after costs.
  - RV uses only the current step's realised rows, so it carries no future information.
- **Coefficient in E4:** λ(U) = γ(U) − 1 = 9·(1 − min(RT, RC)), with numerical range [0, 9].
- **Validity of the values:** λ = 0 (the base reward exactly) and λ = 9 (relative risk
  aversion 10) are E4's own endpoints, so both lie inside the implemented range.
- **Scale:** the training-split diagnostic (D-088 §4) found that at λ = 9 the mean penalty is
  0.4–1.1 × the mean weekly reward and about 1/14 of its SD. It is numerically stable: RV ≥ 0
  and bounded by realised returns.
- **Logging:** the step info and the per-episode training records carry the components.

## 3. Design

| Arm | Reward | Profile input | Configuration |
| --- | --- | --- | --- |
| **E5L** | λ = 0, fixed: r = r_base exactly | Constant (0.5, …, 0.5) every episode | `configs/fixed_risk_low.yaml` |
| **E5H** | λ = 9, fixed: r = r_base − 4.5·RV | Constant (0.5, …, 0.5) every episode | `configs/fixed_risk_high.yaml` |

**Decoupling λ from the profile:**
- In E4, λ = 9 needs RT = RC = 0, and λ = 0 needs RT = RC = 1. Fixing λ through the profile
  would therefore change the observation between the arms, a confound.
- E5 adds `acceptance: fixed` with `fixed_lambda` to the **same** `ProfileRewardSpec`.
  `components()` is unchanged; only `penalty_coefficient()` returns the constant.
- **Profile input:** the profile stays in the observation (56 inputs, the E4 architecture
  unchanged) and is held at the repository's neutral convention 0.5. The new `constant`
  sampling distribution is used in training, and the centre profile in evaluation.
- **Result:** the observation, architecture and every input distribution are identical in
  both arms.
- **No profile sampling:** none in either arm.

**Held fixed (identical to E4 and E1):**
- the dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`;
- the splits: train 2007–2016, validation 2017–2019;
- PPO configuration 4 (lr 1e-4, `n_steps` 512, entropy 0, other settings D-074);
- seeds 42–46; 100,000 timesteps per run;
- the action mapping, accounting, 15 bps costs, 0.40 cap and lag 1;
- deterministic evaluation.

**Runs:** 10 (2 arms × 5 seeds).

**Fixed during training:** λ is a constant in the run identity (`profile_conditioning.reward.
fixed_lambda`). It is never sampled, scheduled or profile-dependent (tested).

**Comparators:**
- E0: configuration 4, re-evaluated in each E5 evaluation; it must reproduce EXP-006.
- From saved, verified outputs: E1 (EXP-010 `6be9dce1b006008b`), E4 (EXP-012
  `948eb21380278b03`) and the baselines.

## 4. Prespecified hypotheses and criteria

**Notation:**
- **Primary split:** validation.
- **Pairing:** seed s pairs E5H_s with E5L_s, each evaluated at its (only) profile.
- "≥ 4/5" means at least 4 of the 5 seeds.

| | Hypothesis | Criterion (supported if all parts hold) |
| --- | --- | --- |
| **H1 (primary)** | λ = 9 gives lower realised risk than λ = 0 | Net volatility E5H < E5L in ≥ 4/5 seeds, and median relative reduction 1 − vol_H/vol_L ≥ 10% |
| H2 | Allocation differences exceed seed variation | Median paired D_w between arms (mean held weights, 7 ETFs + cash, same seed) > median within-arm between-seed D_w (both arms pooled) |
| H3 | More conservative exposure under λ = 9 | Mean target equity E5H < E5L in ≥ 4/5 seeds, and mean target (cash + bonds) E5H > E5L in ≥ 4/5 |
| H4 | Not explained by turnover or costs | Median turnover E5H ≤ 1.25 × E5L, and median cost drag E5H ≤ E5L + 1 pp |
| H5 | Distinguishable reward components | In the training records, the mean realised variance of the last 50 episodes is E5H < E5L in ≥ 4/5 seeds, and its median ratio is ≤ 0.9 |
| H6 | Reproducible | Volatility E5H < E5L in ≥ 4/5 seeds on **both** the training and validation splits |
| H7 | Stable on validation | The validation median relative volatility reduction is > 0 and ≥ 50% of the training-split median reduction |
| H8 | Interpretable | \|net max drawdown\| E5H < E5L in ≥ 4/5 seeds, and the H3 equity part holds |

**Outcome classification (prespecified):**
- **A, sensitivity demonstrated:** H1, H2 and H6 all supported.
- **C, no meaningful sensitivity:** H1 not supported (neither part) **and** H2 not supported.
- **B, weak or partial sensitivity:** otherwise.
- Outcome A would show that λ can control risk. It would **not** establish investor
  personalisation.

**Performance (descriptive; no hypothesis):**
- Paired seed differences E5H − E5L for net Sharpe, net return, annualised return, volatility,
  maximum drawdown, turnover, cost drag and exposures.
- Reported as seed values, mean, SD (ddof 1), median, range and a descriptive t-interval
  (t₀.₉₇₅,₄ = 2.776).
- The five seeds share one market history, so there are no p-values and no significance
  claims.
- Practical significance: a volatility difference below 0.5 pp a year, or a Sharpe difference
  below the E0 seed range (0.9), is not treated as meaningful.

**Candidate and test:** there is no candidate selection, and no test-period evaluation.
Coefficients are never changed after validation is seen; a change would be a new experiment.

## 5. Procedure (commands)

```text
python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/fixed_risk_{low,high}.yaml train --arm main --execute
python scripts/profile_experiment.py ... evaluate --split {train,validation} --execute
python scripts/profile_experiment.py ... compare-fixed --low-validation … --high-validation … --low-train … --high-train … --execute
```

The comparison code (`explainability/fixed_risk_comparison.py`, `CRITERIA_VERSION` "D-089
v1") implements §4 exactly, and is written before training.

## 6. Known limitations

- **Constant profile input:** acts as a bias term. The E5 policies are not personalised, by
  design.
- **One λ pair:** {0, 9}, so the result says nothing about intermediate values or the shape of
  the λ–risk relationship.
- **Data and statistics:** one market history; five seeds; validation-only evidence, mostly a
  low-volatility period.
- **Inherited behaviour:** E0's over-trading is inherited, and the reward does not target
  turnover.
