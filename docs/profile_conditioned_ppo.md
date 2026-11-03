# Profile-conditioned PPO: methodology (D-085; details D-086/D-087)

> **Status (2026-11-03):** **implemented, tested and run.**
> - **Run:** E1/E3 fully trained (10 runs) at local commit `d4ad950`; E0–E3 evaluated on the
>   training and validation splits. This is **EXP-010**: evaluations `93cdfece7bca1f77` (train)
>   and `6be9dce1b006008b` (validation), both verified.
> - **Earlier:** the pipeline check EXP-009 is not a result.
> - **Headline (validation):**
>   - allocations change with the profile by D_w ≈ 0.01, about 10× less than between seeds;
>   - median net Sharpe 0.534 (E1) vs 0.635 (E0);
>   - no profile episode reached any baseline;
>   - no degradation on unseen profile combinations, which is uninformative, because the
>     profile is barely used.
>   - This is behavioural insensitivity, as expected for a task-irrelevant input. It is not
>     personalisation.
> - **Approval status:**
>   - scope and fixed design: D-085, accepted under R-S;
>   - every other choice: **Provisional (delegated)** (D-086, D-087), not team-reviewed.
> - **Research only.** This is not financial advice, and the profiles are not validated
>   investor assessments.

---

## 1. Research objective

**Question:** can a single PPO policy, conditioned on an investor profile, produce different
portfolio allocations for different investor characteristics, while keeping reasonable
performance and risk behaviour?

This first experiment changes **only the observation**: the reward, the actions and all
accounting are unchanged. Its purpose is to isolate the effect of giving the policy profile
information, before any profile-sensitive objective is tried.

## 2. Why profile conditioning is investigated

- **The motivation:** a deployed allocation system would serve investors with different
  risk appetites, horizons and liquidity needs. Conditioning one policy on a profile is the
  simplest way to let the profile influence decisions.
- **What it does not do:** it does not *make* the policy respect the profile.

**Stated in advance (D-085):** in this MDP the profile cannot matter for the objective.
- The D-064 reward, the costs and the constraints are the same for every profile.
- The best policy is therefore the same for every profile, and the profile is a
  task-irrelevant input.
- **What PPO may do:** ignore the profile, or react to it in arbitrary ways. Neither is
  personalisation.
- **What the experiment tests:** whether PPO's decisions are **sensitive** to an input that
  carries no reward information, and whether adding that input changes performance. This is a
  useful control before E4 (§13).

## 3. Profile dimensions

| Symbol | Name in code | Meaning (research representation) | Range |
| --- | --- | --- | --- |
| RT | `risk_tolerance` | Willingness to accept risk | [0, 1] |
| RC | `risk_capacity` | Ability to bear losses | [0, 1] |
| H | `investment_horizon` | Length of the investment horizon (0 short, 1 long) | [0, 1] |
| L | `liquidity_preference` | Preference for liquid or cash holdings | [0, 1] |
| G | `growth_preference` | Preference for growth-oriented assets | [0, 1] |

- **Representation:** U = [RT, RC, H, L, G], as float values.
- **What the values are:** numbers with names. They are not calibrated to any questionnaire
  or regulation, and nothing in the environment interprets them.

**Code:** `src/adaptive_portfolio/environment/profiles.py`:
- `validate_profile`: shape (5,), finite, in [0, 1];
- `neutral_profile`: (0.5, 0.5, 0.5, 0.5, 0.5);
- `ProfileSampling`: the sampling description;
- `profile_set`: seeded evaluation sets.

## 4. Profile sampling

**Training:**
- **When:** one profile per episode, drawn at `reset` and constant for the whole episode
  (496 weekly steps on the training split).
- **Distribution:** each dimension i.i.d. Uniform(0, 1). This is a provisional design choice,
  not a claim about real investors (D-086 item 2).
- **Generator:** a dedicated `numpy.random.default_rng([seed, 5])`. It is re-created when
  Stable-Baselines3 seeds the first reset, so the market path and PPO's own random streams are
  unchanged.
- **Recording:** every sampled profile is stored in the run's `metadata.json`
  (`episode_profiles`).
- **Configuration:** `configs/profile_experiment.yaml` (`arms`). Other distributions can be
  added to `ProfileSampling` without touching the environment.

**Held-out arm (E3):**
- profiles with **both** RT ≥ 0.6 **and** RC ≤ 0.4 are rejected and redrawn (D-087 item 2);
- each marginal range still occurs separately in training, so only the *combination* is
  unseen.

## 5. Extended state

| Block | Inputs | Source |
| --- | --- | --- |
| M_t: scaled causal features | 34 | D-044 features, training-fitted scaler, ±10 clip (D-062) |
| R_t: regime one-hot | 9 | D-045 labels |
| P_t: end-of-row weights | 8 | 7 ETFs + cash |
| U: investor profile | 5 | appended last, **unscaled** (already in [0, 1]) |

- **Size and bounds:** 56 inputs, float32. The observation-space bounds for U are [0, 1].
- **Wrapper:** `ProfileConditionedEnv` in `src/adaptive_portfolio/environment/profile_env.py`
  wraps the unchanged `PortfolioEnv`.
  - `reset(options={"profile": u})` fixes the profile for evaluation.
  - `step` passes the action straight through.

## 6. PPO architecture

- **Unchanged:** configuration 4's settings and SB3 2.9 `MlpPolicy`:
  - separate 64×64 tanh policy and value networks;
  - learning rate 1e-4, `n_steps` 512, entropy 0, batch 64, 10 epochs;
  - γ 0.99, λ 0.95, clip 0.2, `log_std_init` 0;
  - seeds 42–46, budget 100,000 timesteps.
- **The only difference:** the first layer's input size (56 instead of 51). There is no
  profile encoder, attention, hypernetwork, mixture of experts or extra algorithm.
- **Tests:** `tests/test_profile_env.py` checks the layer sizes, the actor and critic output
  sizes, a short real training run and deterministic prediction.

## 7. Exact reward preservation

The reward is the D-064 decision-aligned log growth after costs:

```text
r_k = log(V_{d_{k+1}} / V_{d_k}),   r_K = log(V_e / V_{d_K})
```

Here V_t is the ledger value after costs at the close of row t. It is computed only by
`PortfolioEnv.step` and `environment/rewards.py`.

**How it is preserved:**
- **The wrapper never touches it.** It returns the inner environment's reward, termination,
  truncation and info unchanged, adding only `info["profile"]`.
- **Tests:**
  - the same action sequence on the wrapped and unwrapped environments gives bit-identical
    rewards, ledgers and info;
  - the rewards equal `decision_aligned_rewards` recomputed from the ledger;
  - `rewards.py`, `portfolio_env.py`, `actions.py`, `observation.py` and `simulator.py` are
    byte-identical to commit `26a2abd`.

## 8. Experimental design

| Id | What | Trained? | Data |
| --- | --- | --- | --- |
| **E0** | Existing PPO: configuration-4 checkpoints of EXP-005 (51 inputs), re-evaluated in the same run | No (reused) | Train, validation |
| **E1** | Profile-conditioned PPO, arm `main` (all profiles) | Yes, 5 seeds | Train only; evaluated on train and validation |
| **E2** | Intervention on E1 policies: correct vs neutral vs shuffled profile | No | Same as E1 |
| **E3** | Arm `heldout` (one joint profile region excluded) | Yes, 5 seeds | Train only; evaluated on train and validation |
| **E4** | Profile-sensitive reward | **Not implemented** (future work, §13) | — |

**Common conditions (checked in code; any difference stops the evaluation):**
- the same dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`;
- the same frozen scaler, environment block, costs, cap, lag, PPO hyperparameters, SB3
  constants, budget and grid run spec as E0;
- E0's observation size + 5.

Each evaluation window is the split's common window (D-058). Actions are deterministic
(D-076), and every decided path is re-simulated and must match the environment's ledger
exactly.

## 9. Baselines and ablations

- **Conventional baselines:** the three D-053 strategies, recomputed in the same run on the
  same window.
- **E0:** the non-personalised PPO comparator.
  - On validation, its net Sharpe must reproduce EXP-006 for every seed (checked within 1e-12
    against `data/processed/evaluations/1ce9c490ed03c8c9/policy_metrics.csv`).
  - On the training split, it is a deterministic training-period evaluation of configuration
    4 only. This overlaps D-078 item 1 in content, and is recorded as part of this instruction
    (D-087 item 4).
- **E2, inference-time intervention (D-087 item 1; no retraining):**
  - for each E1 policy and each profile u_i of `in_distribution`, take the observations of its
    own episode with u_i;
  - recompute the decided targets with the five profile inputs replaced by:
    1. **neutral:** (0.5, …, 0.5);
    2. **shuffled:** u_{(i+1) mod 32}, a deterministic derangement;
  - report D_w against the correct targets, and the change in exposures.
  - **Why not on-path:** with synthetic profiles, a "shuffled" episode would only be another
    profile's own episode under a different label. A state-matched intervention is the
    meaningful comparison.
  - **What it is:** an intervention on the input, not a separately trained policy.
- **Not done:** a retrained constant-profile arm (D-086 item 5 is withdrawn by D-087). E0
  serves as the no-profile reference. A retrained control would separate "learned to use the
  profile" from "larger input layer", and is listed as future work.

## 10. Generalisation methodology

Two kinds of generalisation are reported separately and never pooled:

| | Seen market period (training split, 2007–2016) | Unseen market period (validation, 2017–2019) |
| --- | --- | --- |
| **Seen profile combinations** | `heldout` arm on `heldout_training`; `main` arm on `in_distribution` | same sets |
| **Unseen profile combinations** | `heldout` arm on `heldout_region` | same set |

`main` on `heldout_region` is the reference for the same profiles when they were seen in
training.

**Profile sets** (fixed before any evaluation; `configs/profile_experiment.yaml`):
- the centre profile;
- `in_distribution`: 32 profiles, Uniform(0, 1)^5, seed 20261103;
- `heldout_region`: 32 profiles inside the excluded box, seed 20261104;
- `heldout_training`: 32 profiles from the held-out arm's training distribution, seed
  20261105.

Market data are never shuffled; each split is one chronological episode.

## 11. Evaluation metrics

**Portfolio performance (D-076 definitions, `summarize_window`):**
- net and gross cumulative return; net annualised return;
- net Sharpe (√252·mean/std, ddof 1, rf 0, funding row excluded);
- net annualised volatility; net and gross maximum drawdown;
- cost drag; total cost; traded notional and turnover (D-059).

**Portfolio behaviour (`explainability/profile_analysis.py`):**
- mean held weight per asset and cash; maximum held weight;
- mean target exposure per group: equity (SPY, EFA, EEM), bonds (IEF, TLT, LQD), gold (GLD),
  and cash. The group labels are provisional and descriptive.
- risky-sleeve HHI (concentration);
- **allocation stability:** D_w between consecutive targets;
- executions.

**Personalisation behaviour (state-matched, on each policy's centre-profile trajectory):**
- **D_w:**

  ```text
  D_w(U_i, U_j) = mean over decisions of (1/N) Σ_k |w_k(U_i) − w_k(U_j)|
  ```

  Here N = 8 (7 ETFs + cash), w is the decided target, and values lie in [0, 0.25].
- **Pairwise summary:** the mean, median and maximum D_w over all pairs in a set, and the 5th,
  50th and 95th percentiles over decisions. The percentiles show whether differences are
  consistent across market observations.
- **Dimension effects:** Spearman correlation across profiles between each dimension and:
  - the exposures (equity, bonds, gold, cash, HHI);
  - the on-path net Sharpe, volatility, maximum drawdown, turnover, mean held cash and
    stability.
- **One-at-a-time sweeps:** each dimension at 0, 0.1, …, 1, with the others at 0.5. The output
  is the exposures and D_w against the centre profile.
- **Seed scale:** D_w between the five seeds at the centre profile on one shared observation
  sequence. This is the size of seed-to-seed differences, used to judge whether profile
  differences are large.

**Statistics:**
- **Descriptive only:** across seeds, the mean, standard deviation (ddof 1), median, minimum
  and maximum.
- **Not reported:** confidence intervals, p-values or significance. The moving-block bootstrap
  belongs to the Gate 3 test protocol, and it still awaits review.

**How the five questions are read:**
1. RT and observed risk exposure: equity share, HHI, volatility, drawdown.
2. RC and allocation: all exposures.
3. H and allocation.
4. L and cash or turnover.
5. G and equity exposure.

None of these effects is assumed. A changed allocation is behavioural sensitivity, not
evidence of good performance or suitability.

## 12. Limitations

- **The profile is task-irrelevant** under the unchanged reward (§2). Personalisation cannot
  be shown by this experiment.
- **Synthetic profiles:** uniform and independent; not real investors; dimension labels have no
  validated meaning.
- **Scale:** one market history, five seeds, no inferential statistics. Validation 2017–2019
  is mostly low-volatility (D-045 note).
- **E0 already underperformed** all three baselines on validation (EXP-006). Profile
  conditioning does not address that.
- **State-matched sensitivities** are one-step and not causal (D-068). On-path comparisons mix
  the profile effect with path effects.
- **Provisional settings:** costs, the 0.40 cap and the universe stay provisional; the asset
  groups are labels.
- **No test-period evaluation** of the profile arms (D-086 item 11).

## 13. Future research directions (none implemented)

- **E4, a profile-sensitive reward:** for example, a risk penalty scaled by
  (1 − RT)·(1 − RC), or a cash or liquidity term weighted by L. This makes the profile
  reward-relevant, and is the natural next test, **after** E1–E3 establish the
  observation-only control.
- **Profile-specific constraints:** for example, a maximum equity weight or volatility budget
  as a function of RC.
- **Model variants:** separate profile encoders with late fusion; attention or FiLM-style
  conditioning; contextual or meta-RL; hierarchical policies; constrained or risk-sensitive
  PPO.
- **A retrained constant-profile control** (§9).

The handover in the 2026-11-03 journal entry compares these options and their evidence
requirements.
