# E4: profile-dependent reward PPO, prespecified methodology (D-088)

> **Status:** written and fixed on 2026-11-03, **before any E4 training**.
> **Results (appended after the run; the text below is unchanged):** EXP-012,
> `docs/e4_results.md`.
> - The reward, parameters, comparisons, hypotheses and decision criteria below were set from
>   the existing protocol and a training-split scale diagnostic only (§4). No E4 result had been
>   seen.
> - **Scope:** authorised by a team member's in-session instruction (R-S).
> - **Formulation and criteria:** Provisional (delegated) choices by Claude Code (D-088). They are
>   not team-reviewed.
> - **Research only;** not financial advice. The profiles are synthetic, not validated
>   suitability assessments.

## 1. Question and context

**Question:** does making the PPO reward depend on the investor profile produce meaningful,
reproducible and financially interpretable personalisation, with acceptable performance, risk,
turnover and costs?

**Context (EXP-010, historical):**
- with the profile in the observation only (E1), allocations changed by D_w ≈ 0.01, about 10×
  less than between seeds;
- the reward ignored the profile;
- the validation median net Sharpe was 0.534 for E1 against 0.635 for E0; all three baselines
  scored 1.355–1.754.

## 2. Repository facts the design uses (audited 2026-11-03 at `7033618`)

- **Base reward (D-064)**, computed in `PortfolioEnv.step`:

  ```text
  r_base,k = log(V_{d_{k+1}} / V_{d_k})
  ```

  This is the log growth of the ledger value after costs over the interval (d_k, d_{k+1}]. It
  contains the execution cost of decision k (15 bps on ETF traded notional) and the returns of
  rows d_k + 1 … d_{k+1}.
- **Simulator rows:** each row of the interval is a `StepRecord` with `net_return` =
  (1 + gross)(1 − cost) − 1, the actual daily net return of the portfolio.
- **Observation:** the profile U = [RT, RC, H, L, G] is appended to the 51 inputs (56 in
  total) by `ProfileConditionedEnv`, drawn once per episode.

## 3. Reward formulation

```text
r_E4,k(U) = r_base,k − (λ(U) / 2) · RV_k
RV_k      = Σ_{t ∈ (d_k, d_{k+1}]} (net_return_t)²        (realised variance of the step)
a(U)      = min(RT, RC)                                    (effective risk acceptance)
γ(U)      = γ_min + (γ_max − γ_min) · (1 − a(U)),   γ_min = 1, γ_max = 10
λ(U)      = γ(U) − 1 ∈ [0, 9]
```

**Why this form:**
- **It is a CRRA objective.** To second order, Σ log(1 + r_t) ≈ Σ r_t − ½ Σ r_t². The base
  log-growth reward is therefore already a mean-variance objective with relative risk aversion
  γ = 1 (the Kelly investor). Subtracting (λ/2)·RV raises the effective relative risk aversion
  to γ = 1 + λ. The reward is a second-order CRRA certainty-equivalent growth rate, with the
  profile setting the investor's risk aversion.
- **Nesting:** at a(U) = 1, λ = 0 and the reward is exactly D-064. E1's objective is the
  special case of a fully risk-accepting investor.
- **Range:** γ from 1 to 10 spans the range usually treated as plausible for relative risk
  aversion. Mehra and Prescott (1985) took 10 as an upper bound. It is fixed in advance, not
  tuned.
- **Risk measure:** the realised variance of daily net returns inside the step. It uses only
  the step's own realised rows, the same information as r_base, and no later rows. It needs no
  extra state, is never negative, and is computed from the existing accounting (net of costs).
  Drawdown and downside deviation were rejected:
  - drawdown is path-dependent across steps (episode-length effects);
  - downside deviation needs a target return and a choice of threshold;
  - neither is needed to test whether risk aversion personalises behaviour.

**Which profile dimensions enter, and why:**

| Dimension | In the reward? | Reason |
| --- | --- | --- |
| RT risk tolerance | Yes, through a(U) | Willingness to bear risk |
| RC risk capacity | Yes, through a(U) | Ability to bear losses. Suitability practice treats the **lower** of willingness and ability as binding: an investor with high tolerance but low capacity should not take high risk. Hence `min`, not an average; they are not interchangeable |
| H horizon | **No** | With CRRA utility and i.i.d. returns, the optimal risky share does not depend on horizon (Samuelson 1969; Merton 1969). Adding a horizon term would need a model of return predictability that this project does not have |
| L liquidity preference | **No** | All seven ETFs are exchange-traded and liquid, and cash is already an asset. A cash bonus would be an arbitrary preference parameter. Turnover is already penalised by the real 15 bps cost |
| G growth preference | **No** | Capital appreciation is what the log-growth term already rewards. A growth bonus would reward risk-taking directly, which the instruction warns against |

H, L and G therefore remain in the **observation** but not in the reward. They act as built-in
**negative controls**: any systematic E4 response to them is spurious.

**Logging:**
- every step's info carries `reward_base`, `realised_variance`, `risk_penalty`, `lambda` and the
  final `reward`;
- every training episode's sums are stored in the run metadata (`episode_reward_components`);
- evaluation episodes record the E4 objective components from the ledger.

## 4. Scale diagnostic (training split only, baselines; before any E4 run)

Weekly steps 2007-07-05 → 2016-12-30, 496 decisions; rows read through 2016-12-30:

| Portfolio | mean r_base | sd r_base | mean RV | (9/2)·mean RV | ratio to \|mean r_base\| |
| --- | --- | --- | --- | --- | --- |
| Equal weight monthly | 0.00096 | 0.01458 | 0.000229 | 0.00103 | 1.07 |
| Buy and hold | 0.00085 | 0.01236 | 0.000160 | 0.00072 | 0.85 |
| Inverse volatility monthly | 0.00109 | 0.00985 | 0.000096 | 0.00043 | 0.40 |
| All cash | 0 | 0 | 0 | 0 | — |

**What this shows:**
- at the maximum λ = 9, the penalty is of the same order as the mean reward, so it can change
  which portfolios are preferred;
- it stays about 14× smaller than the reward's per-step standard deviation, so it does not
  dominate the learning signal;
- at λ = 0 nothing changes.

**No coefficient was changed after this diagnostic.**

## 5. Experiment design (EXP-012; pipeline check EXP-011)

| Arm | Definition | Trained? |
| --- | --- | --- |
| E0 | Existing PPO, configuration 4 (EXP-005 checkpoints); re-evaluated; must reproduce EXP-006 exactly | No |
| E1 | Profile-conditioned, base reward (EXP-010 runs and evaluations, reused after hash verification) | No |
| **E4 main** | Same as E1 `main` (Uniform(0, 1)^5 profiles, 56 inputs, configuration 4, seeds 42–46, 100,000 timesteps), with r_E4 | Yes |
| **E4 held-out** | Same as E1 `heldout` (the box RT ≥ 0.6 ∧ RC ≤ 0.4 excluded in training), with r_E4 | Yes |

**Held fixed:**
- the dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`;
- the splits (train 2007–2016, validation 2017–2019);
- the actions, accounting, costs, cap and lag;
- the PPO settings and seeds;
- the profile sampling and the evaluation profile sets (seeds 20261103–20261105, the same as
  E1);
- deterministic evaluation.

**The only difference from E1 is the reward.** This is also the first arm where the held-out
box is meaningful: high RT with low RC has a = RC ≤ 0.4, so a policy that applies the `min`
rule should treat these profiles as risk-averse.

## 6. Prespecified hypotheses and decision criteria (validation split; descriptive)

Notation:
- ρ_s(x, y) is the Spearman correlation across the 32 `in_distribution` profiles for seed s.
- "≥ 4/5" means at least 4 of the 5 seeds.
- **State-matched** quantities hold each policy's centre-profile observations fixed and replace
  only the profile inputs.

| | Hypothesis | Criterion (supported if all parts hold) |
| --- | --- | --- |
| H1 | Profile reward gives stronger profile sensitivity than E1 | Within-set D_w (`in_distribution`, state-matched) is greater for E4 than for E1 in ≥ 4/5 seeds (paired by seed), and the median E4/E1 ratio is ≥ 2 |
| H2 | The allocation direction matches the intended meaning | ρ_s(a, target equity) > +0.35 and ρ_s(a, target cash + bonds) < −0.35 in ≥ 4/5 seeds. The negative controls H, L, G have \|median ρ\| < 0.35 for every exposure |
| H3 | Risk-sensitive profiles get lower realised risk | ρ_s(a, on-path net volatility) > +0.35 in ≥ 4/5 seeds, and the median over seeds of the volatility ratio (high-a tercile / low-a tercile of the 32 profiles) is > 1.1 |
| H4 | Personalisation is not achieved through more trading | Median turnover of E4 (mean over profiles) ≤ 1.25 × that of E1, and ρ_s(a, turnover) does not exceed ρ_s(a, volatility) in median |
| H5 | Stable across seeds | The H3 correlation has the same sign in ≥ 4/5 seeds, and the E4 seed-scale D_w is not larger than E1's by more than 50% |
| H6 | Unseen combinations behave consistently | Held-out arm on `heldout_region` (a = RC ≤ 0.4): mean on-path volatility below its own `heldout_training` mean in ≥ 4/5 seeds, and a median net Sharpe difference (region − training profiles) within ± the median within-seed profile SD |
| H7 | The profile effect exceeds seed variation | The state-matched D_w between the extreme profiles a = 0 and a = 1 (RT = RC = 0 vs RT = RC = 1, others 0.5) is greater than the E4 seed-scale D_w, in median over seeds |

**Performance (not a hypothesis test):**
- **Comparisons:** paired seed differences E4 − E0 and E4 − E1 at the centre profile (a = 0.5,
  λ = 4.5), and over the mean of the `in_distribution` profiles.
- **Metrics:** net Sharpe, net return, volatility, maximum drawdown, turnover, cost drag.
- **Reported:** seed values, mean, median, SD, range, and a t-interval for the mean difference
  (t₀.₉₇₅,₄ = 2.776).
  - The t-interval is **descriptive only**. Five seeds share one market history, so no p-value
    or significance claim is made.
- **Practical significance:** a Sharpe difference smaller than the E0 seed range (0.9) is not
  treated as meaningful.

**Reward-exploitation checks (descriptive):**
- the share of decisions with target cash > 0.95;
- the maximum held weight; HHI;
- turnover against E1;
- the ratio of the mean penalty to the mean |r_base| in training episodes.

**Candidate:**
- E4 has one prespecified configuration, so no selection takes place.
- There is **no test-period evaluation**. The single pre-registered test (D-083) concerns
  configuration 4 only, and stays sealed.

## 7. Analyses

All are computed by code and written once:
- evaluation (train and validation): `scripts/profile_experiment.py --experiment-config
  configs/profile_reward_experiment.yaml …`;
- the E4-vs-E1 comparison, including the H1–H7 criteria: `scripts/profile_experiment.py
  compare`.

**Analyses included:** the EXP-010 metrics and D_w analyses, plus:
- the E4 objective components per evaluation episode;
- an interaction grid (5 × 5 values for RT × RC, H × L and G × RT, others at 0.5;
  state-matched exposures);
- the risk contrast (H7).

## 8. Limitations known in advance

- **Synthetic profiles:** uniform and independent; their labels have no validated meaning.
- **Fixed formulation:** the γ range and the `min` rule are one defensible choice, not
  calibrated to investors.
- **Data and statistics:** one market history and five seeds; validation-only evidence, mostly
  a low-volatility period.
- **Inherited behaviour:** E0's over-trading is inherited, and the reward does not target
  turnover.
- **Reward vs evaluation:** the risk penalty acts on realised variance per step, while
  evaluation uses annualised Sharpe and volatility. These are related but not identical.
