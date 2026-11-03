# E7: turnover-aware PPO, prespecified methodology (D-091)

> **Status:** written and fixed on 2026-11-04, **before any E7 training**.
> - **Experiment IDs:** EXP-017 (pipeline check) and EXP-018 (full experiment).
> - **Scope:** authorised by a team member's in-session instruction (R-S). It implements D-077
>   item 3 ("a turnover-aware reward").
> - **Coefficients and criteria:** Provisional (delegated) choices by Claude Code (D-091). They
>   are not team-reviewed.
> - **Research only;** not financial advice.

## 1. Question and motivation

**Question:** can a turnover-aware PPO reward reduce excessive trading and transaction-cost drag
without materially degrading net performance?

**Motivation:**
- **Over-trading:** every PPO arm so far (E0–E6) traded about 13–37 times its portfolio a year,
  against at most 0.78 for the baselines. On validation this cost about 8–11 pp of return over
  three years (EXP-006, EXP-014, EXP-016).
- **Weak risk lever:** E6 showed that a risk-sensitive reward moves risk in-sample but transfers
  weakly. The trading behaviour, which drives the cost drag, was never targeted.

## 2. Audit (repository at `3483b0f`, clean, level with `origin/main`)

| Item | Verified implementation |
| --- | --- |
| Turnover per execution | `simulator.step`: traded notional = Σ \|w_post − w_pre,drifted\| over the 7 ETFs; **the cash leg is excluded** (`portfolio_turnover(..., cash_column)`). The funding trade from cash is the first execution |
| Transaction cost | cost fraction = 0.0015 × traded notional (10 + 5 bps; D-007/D-049), charged on every execution including funding; net_return = gross − cost·(1 + gross) |
| Base reward | D-064: r_base,k = log(V_{d_{k+1}} / V_{d_k}). V is after costs, so **the cost is already in the reward** |
| E6 reward | r = r_base − (λ/2)·Σ net_return² (`ProfileRewardSpec`, `acceptance: fixed`) |
| Reported turnover | `annualised_traded_notional` = recurring traded notional (funding excluded, D-059) × 252 / return periods |
| Cost drag | gross cumulative − net cumulative return |
| Data | dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`; train decisions 2007-07-05 → 2016-12-30; validation 2017-01-03 → 2019-12-31; test 2020– sealed |
| PPO | Configuration 4, seeds 42–46, configured budget 100,000 timesteps (100,352 realised), 56 inputs with a constant profile 0.5 |

## 3. Design

**Control = E6L (λ = 0)**, so that E7 isolates the turnover penalty:
- with λ = 0, the E6 reward is exactly D-064's log growth after costs;
- D-077 item 3 proposed the turnover-aware reward on that base;
- E6L is verified to equal E5L exactly, giving a strong reproduction target;
- **alternative not chosen:** E6H (λ = 9), which would confound the turnover penalty with the
  risk penalty.

**Reward of step k:**

```text
r_k = r_base,k − (λ/2)·Σ net_return_t² − κ·TN_k ,   λ = 0
TN_k = traded notional of step k's execution (Σ|Δw| over the 7 ETFs, cash excluded),
       except TN_0 := 0 for the episode's first step, the funding trade (as D-059's reported turnover)
```

**Why this is not a second cost deduction:**
- The real cost (0.0015·TN) stays in r_base through the ledger, and the ledger, cost model and
  accounting are unchanged.
- κ·TN is a **reward-shaping penalty on trading activity**. It never enters the ledger,
  portfolio value or any reported metric.
- Every reported metric remains the unchanged net-of-cost accounting.

| Arm | κ | Rationale | Expected strength at E6L's training turnover (median TN 0.487 per step; mean r_base about 0.0031 per step) |
| --- | --- | --- | --- |
| **E7B** (control) | 0 | The existing reward, exactly E6L | — |
| **E7T1** (moderate) | 0.0015 | Equal to the real cost rate: the agent perceives trading at 2× its true cost | Penalty about 0.00073 per step, about 24% of the mean base reward |
| **E7T2** (strong) | 0.0075 | 5× the cost rate: the agent perceives trading at 6× its true cost | Penalty about 0.0037 per step, about 119% of the mean base reward at today's turnover. It can be avoided by trading less (a baseline-like turnover of 0.8 a year implies about 0.00012 per step) |

- **Coefficient units:** κ is per unit of traded notional, the same unit as the cost rate.
- **Fixed in advance:** both values come from the cost rate and the E6L scale above, never from
  E7 results.
- **Configurations:** `configs/turnover_k0.yaml`, `turnover_k1.yaml` and `turnover_k2.yaml`
  differ **only** in `label` and `reward.turnover_penalty`. Everything else equals E6L,
  including λ = 0, the seeds and the budget.

## 4. Prespecified hypotheses and criteria

**Conventions:**
- **Pairing:** seed-paired; "≥ 4/5" means at least 4 of the 5 seeds.
- **Turnover:** annualised recurring traded notional.
- **Cost drag:** in pp over the window.
- **Primary split:** validation, unless stated.

| | Hypothesis | Criterion (supported if all parts hold) |
| --- | --- | --- |
| H1 | Turnover reduction | Training split: turnover T1 < B and T2 < B in ≥ 4/5 seeds each, and the median T2 ≤ the median T1 |
| H2 | Cost efficiency | Validation: cost drag T1 < B and T2 < B in ≥ 4/5 seeds each |
| H3 | Transfer | Validation: turnover T1 < B and T2 < B in ≥ 4/5 seeds each, and the median relative reduction (1 − T/B) on validation is ≥ 50% of that on training, for both arms |
| H4 | Net performance | For both T1 and T2: median paired validation net Sharpe difference vs B ≥ 0, and median paired annualised net return difference vs B ≥ 0 |
| H5 | Risk preservation | For both T1 and T2: median paired validation volatility increase vs B ≤ +0.5 pp a year, and median paired deepening of the maximum drawdown vs B ≤ 2 pp |
| H6 | Responsiveness | For both T1 and T2 (validation): median `allocation_stability_dw` ≥ 25% of B's (the policy still re-allocates), and the median share of decisions with target cash > 95% ≤ 0.05 (no cash collapse) |
| H7 | Reproduction | E7B validation net Sharpe, volatility, maximum drawdown and turnover equal the E6L evaluation exactly (maximum absolute difference ≤ 1e-12, all seeds) |
| H8 | Practical utility | For at least one penalty arm: the median validation cost-drag reduction vs B ≥ 2 pp over the three years, **and** the mean paired turnover reduction vs B > the median within-arm seed SD of validation turnover |

- **Downside risk:** not available from the evaluator (D-076). It is not computed with a new
  definition.

**Outcome classification** (mechanical):
- **Unresolved:** if H7 is not supported. E7 is not interpreted until the reproduction failure
  is explained.
- **A, strong support:** H1, H2, H3, H4 and H5 supported.
- **C, no support:** H1 not supported (no part holds), **or** H3 not supported, **or** both H4
  and H5 not supported.
- **B, partial support:** otherwise.

## 5. Statistics

- **Paired differences:** T1 − B, T2 − B and T2 − T1 on both splits.
- **Reported:** seed values, mean, SD (ddof 1), median, range, sign count, a descriptive
  t-interval (t₀.₉₇₅,₄ = 2.776), effect size d, and relative differences for turnover and cost
  drag.
- **Seed variation:** within-arm seed SDs.
- **Caveats:** the five seeds share one market history, so these are not independent market
  samples; no p-values and no significance claims.

## 6. Procedure

```text
python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/turnover_k{0,1,2}.yaml train --arm main --execute
python scripts/profile_experiment.py ... --experiment-config configs/turnover_k{0,1,2}.yaml evaluate --split {train,validation} --execute
python scripts/profile_experiment.py ... compare-turnover --validation <k0> <k1> <k2> --train <k0> <k1> <k2> --e6-validation <E6L val> --execute
```

**Rules:**
- full runs only from a clean commit; write-once outputs; every output verified;
- E0 must reproduce EXP-006;
- no working-tree edits during training; unrelated processes are not touched.
- **Retry rule:** a run that fails for an infrastructure reason (process crash, lock) is retried
  once with the same seed and configuration, and the failure is recorded. Any other failure stops
  the experiment.

## 7. Test-period boundary

- No test-period row is read, and there is no test evaluation.
- Test performance stays **unmeasured**.

## 8. Limitations known in advance

- **Coefficients:** two κ values only, so the shape of the curve is coarse.
- **Data and statistics:** one market history; five seeds; validation-only evidence, mostly a
  calm period.
- **Penalty design:** the penalty is linear in traded notional and ignores *which* trades are
  useful, so it may suppress good rebalancing as well as noise.
- **Design:** the constant profile input; no personalisation.
