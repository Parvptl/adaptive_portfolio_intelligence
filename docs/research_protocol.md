# Research Protocol — DRAFT / NOT APPROVED

> **Status update (2026-10-19):**
> - The **baseline (Gate 1) parts** of this protocol were **accepted on 2026-10-19** by Parv
>   Patel and Mandar Patil, as recorded in `decision_log.md`. Confirmations were self-declared
>   in a shared-device session and arrived in one message; see `approval_checklist.md` §0.1.
> - The **Gate 2 defaults D-062 to D-069** were accepted on 2026-10-19 as the working design for
>   PPO implementation (under R-S, D-061). Where §8–§13 differ from those entries, the decision
>   log governs. Bootstrap settings and the stress-window protocol remain **open for Gate 3**.
> - D-006, D-008, D-034, D-042 and D-044 are acknowledged as provisional, not validated.
> - The status lines below are updated where Gate 1 settled them.
>
> **Original status: DRAFT. Nothing in this document is approved.**
> - It collects the recommendations of the milestone-4.2 read-only audit (2026-10-18), so the
>   team can decide them before any reinforcement-learning (RL) work starts.
> - Only the student team (Parv Patel, Mandar Patil) can approve a decision. Approval is recorded
>   in [`decision_log.md`](decision_log.md) as **Accepted**, with who approved it and when.
> - Until then, every recommendation here is a proposal, and every value marked provisional
>   stays provisional.
> - The submitted abstract (`Abstract.pdf`) is the source of truth for scope. No improvement of
>   any strategy over another is assumed.

Each section separates three kinds of statement:
- **Fact:** what the code and configs do now (verified on 2026-10-18 at commit `817f8b8`,
  which contains the milestone-4.2 changes).
- **Recommendation:** a proposal, not approved.
- **Open:** a question that needs a team decision.

## 1. Scope from the abstract (fact)

- Portfolio management as sequential decision-making, with feedback based on performance and
  risk.
- Investigate rising, falling and high-volatility periods.
- PPO is a **candidate** algorithm, alongside suitable baselines (D-014).
- Compare against conventional allocation benchmarks using cumulative return, Sharpe ratio,
  maximum drawdown and portfolio turnover.
- Out-of-sample testing. Walk-forward validation and stress testing **where feasible**.
  Transaction costs are included.
- Explainability is **explored**. The study also assesses risk control, adaptability and
  interpretability.

## 2. Timing (D-013, D-043, D-048, D-055)

- **Fact:**
  - decide at row `d` using data dated `<= d`; execute at the close of `d + L`; first earned
    return is row `d + L + 1`;
  - `L` is counted in observed sessions, and `execution_lag_sessions` is required (configs: 1);
  - one implementation lives in `adaptive_portfolio/timing.py`, shared by the simulator, the
    backtest and `features.next_period_targets`.
- **Recommendation:**
  - accept lag 1 as the primary convention and lag 0 as an idealised sensitivity case;
  - any RL reward must pair decision `d` with the return the simulator credits, i.e. use
    `next_period_targets(..., execution_lag_sessions=L)` or the simulator itself.

## 3. Costs and turnover (D-007, D-031, D-049)

- **Fact:**
  - cost = (10 + 5) bps × traded notional of non-cash assets (cash leg excluded), charged on the
    value before the cost and deducted pro rata;
  - the initial funding trade is charged;
  - `max_turnover` must be null, and the backtest refuses a value.
- **Fact (milestone 4.2):** metrics report `funding_traded_notional` (the one-off funding trade)
  and `recurring_traded_notional` separately. The opt-in annualised traded notional uses
  recurring trades only (proposed D-059).
- **Recommendation:**
  - accept traded notional as the cost basis;
  - keep **no turnover cap** in the primary protocol. If a cap is ever introduced, it should
    constrain traded notional per rebalance;
  - keep 15 bps as the base rate.
- **Accepted 2026-10-19:** D-007 (15 bps, placeholder rates) and D-031's cost basis with no cap.
- **Open:**
  - D-031: the turnover-cap measure;
  - cost sensitivity at 0 and 30 bps, an optional extension that needs approval.

## 4. Constraints and cash (D-015, D-050, D-057)

- **Fact:**
  - long-only, Σw ≤ 1, fractional weights;
  - `max_weight` 0.40 is checked on **target** weights at execution; holdings may drift above it
    between rebalances;
  - residual cash earns `risk_free_rate` = 0.
- **Recommendation:** keep rf = 0 for both the cash return and the Sharpe ratio, labelled "excess
  over zero". Document the limitation: T-bill yields were about 4–5 % in 2022–2024, so cash is
  understated in part of the test period. The rule is the same for every strategy.
- **Alternative (new scope, needs approval):** a daily T-bill series, with its own timing and
  leakage rules.
- **Accepted 2026-10-19:** D-015 (cap 0.40 on targets, rf = 0).

## 5. Annualisation and metrics (D-023, D-052)

- **Fact:**
  - metrics are per session by default (`periods_per_year: null`);
  - annualised values appear only when `periods_per_year` is set, and are labelled provisional;
  - volatility and Sharpe exclude the funding row; cumulative return and drawdown include it.
- **Evidence (not a decision):** training years 2008–2016 average 251.9 observed sessions per
  year (range 250–253).
- **Recommendation:**
  - N = 252 for daily data;
  - report the annualised Sharpe (√252 × per-session mean/std) alongside the per-session value;
  - CAGR over the return periods.

  The limitation of √N scaling (it assumes independent returns) must be stated.
- **Accepted 2026-10-19:** D-023, N = 252 (`periods_per_year: 252`).

## 6. Splits, evaluation window and test isolation (D-009, D-018, D-019, D-051, D-056, D-058)

- **Fact:**
  - train 2007–2016 (2,517 rows), validation 2017–2019 (754), test 2020–2024 (1,258);
  - each split is simulated independently from cash;
  - decisions whose earned return falls in the next split are dropped;
  - test is evaluated only with `--include-test`.
- **Fact (milestone 4.2, proposed D-058):** `backtest.common_start_history_sessions: 126` makes
  every strategy's first training decision wait for the longest feature window (126 sessions).
  The CLI refuses a value below the longest window in `features.yaml`. Validation and test
  windows are unchanged.
- **Fact:** walk-forward evaluation is **not implemented**. The `walk_forward` settings in
  `experiment.yaml` are not read by any code.
- **Recommendation:**
  - the fixed split is the primary evaluation;
  - walk-forward as a robustness check, with expanding folds **inside 2007–2019 only** (e.g.
    validate on each of 2015–2019) and no per-fold tuning;
  - no embargo is needed for one-step rewards; revisit if a multi-step reward is adopted.
- **Accepted 2026-10-19:** D-009, D-051, D-056, D-058.
- **Open:** D-018 (walk-forward scheme), D-019 (embargo).

## 7. Baselines (D-010, D-053)

- **Fact:** equal weight monthly, equal-weight buy-and-hold, inverse volatility (63) monthly.
  None has fitted parameters, and none uses regime information.
- **Recommendation:** keep this set. Do not add strategies without a stated reason. Baselines
  stay untuned, and that asymmetry with a tuned agent is reported.
- **Accepted 2026-10-19:** D-053; EXP-002 is the primary baseline record.
- **Missing record:** EXP-001 used lag 0. A primary-convention baseline run (lag 1, common
  window 126) on train and validation has not been made yet.

## 8. Agent design (needed before PPO; new decisions, none recorded yet)

> **Superseded (2026-10-19):** the agent design was decided as D-062 to D-069 (accepted
> 2026-10-19) and amended by D-072 (normalised actions, accepted). The table below is kept as
> the original draft.

A more detailed design, also **PROPOSED — NOT APPROVED**, is in
[`ppo_design_proposal.md`](ppo_design_proposal.md).

| Item | Options | Recommendation |
| --- | --- | --- |
| Algorithm and library (D-014) | Stable-Baselines3 + PyTorch; other libraries | Choose before implementation; add version-bounded dependencies then |
| Observation (D-012) | (a) causal features only; (b) features + one-hot regime label; (c) both, as an ablation [O] | (b) primary, because the title says "regime-aware"; plus the current drifted weights |
| Feature scaling | none; train-only fitted scaler | Fit on train only, then freeze (like the regime thresholds) |
| Action mapping | softmax over assets + cash, then a projection | A deterministic projection onto 0 ≤ w ≤ 0.40, Σw ≤ 1, with capped excess going **to cash** and logged |
| Decision frequency | daily; weekly; monthly (114 training decisions from the 126-session common start, too few; 117 under the earlier milestone-4 start) | Daily or weekly, fixed before tuning; costs and turnover always reported |
| Reward | (a) log net growth per step; (b) differential Sharpe ratio (Moody & Saffell, cited in the abstract); (c) (a) minus a risk penalty | (a) primary, (b) the only alternative compared, on validation. **Not chosen; must not be chosen by looking at test results.** |
| Accounting | Separate environment code; the existing simulator | Reuse `simulate` and `timing.py` exactly, so that agent and baselines share costs, timing and constraints |

## 9. Tuning, seeds and selection (D-016)

- **Recommendation:**
  - a fixed hyperparameter budget and search space, declared before tuning;
  - at least 5 training seeds (e.g. 42–46);
  - select by the median over seeds of validation net Sharpe. Annualising does not change the
    ranking while rf = 0 (see `ppo_design_proposal.md` §13, items 7–8, including the
    tie-break);
  - early stopping, if used, on validation only;
  - report every seed: mean, standard deviation, median and range. Never report only the best
    seed.
- **Open:** D-016. *(Superseded on 2026-10-19: D-016 was resolved by D-066, accepted. The
  selection metric's operational definition and evaluation policy are still to be decided
  separately.)*

## 10. Primary endpoint, statistics and stress tests

- **Recommendation (pre-registration):**
  - **Primary:** test-split net Sharpe at lag 1 and 15 bps of the selected configuration,
    as the **median over the same 5 seeds** (annualised with N if D-023 is approved,
    otherwise per session). Every seed is reported. Inference uses a joint block bootstrap
    over time (`ppo_design_proposal.md` §13, item 8). *(Seed aggregation added
    2026-10-18 for consistency with the PPO proposal; still a proposal.)*
  - **Secondary:** cumulative return, maximum drawdown, recurring turnover, cost drag, and
    regime-conditional metrics using the frozen thresholds (D-045).
  - **Statistics:** block-bootstrap confidence intervals for Sharpe differences against each
    baseline, plus the across-seed distribution, with a multiple-comparison caveat.
  - **Stress windows** inside the test period (e.g. the 2020 drawdown and the 2022 rate shock)
    must be named **before** the test run.

## 11. Explainability

- **Recommendation:**
  - permutation sensitivity of actions to observation features;
  - regime-conditional allocation and risk summaries;
  - SHAP is optional and needs approval plus a new dependency.

## 12. Reproducibility and outputs (D-017)

- **Fact:**
  - backtest and feature outputs live under `data/processed/` (git-ignored) with content-hashed
    ids, and reruns are byte-identical;
  - `experiment.yaml` `output_dir: reports` is not used by any code, and only `reports/figures/`
    is git-ignored;
  - an old pipeline-version-1 output folder containing test-split results
    (`data/processed/backtests/ac2d6b163d4f5e4b/`) is kept locally and must not be reported.
- **Recommendation:**
  - a git-ignored results root for RL experiments;
  - commit only configs and experiment-log entries;
  - record seeds, configs, data ids and software versions for every run.
- **Open:** D-017.

## 13. Test-run rule

The test split is evaluated **once**, after the team has:
1. approved this protocol (as decision-log entries);
2. frozen all configs; record their hashes in the experiment log;
3. recorded the selected agent configuration and seeds from validation only.

No result from that run may be used to change anything afterwards. Any later change must be
reported as a new, explicitly labelled exploratory analysis.

*Update (2026-11-03, appended; the rule above is unchanged):* the conditions and command for
the single test run are now in `docs/autonomous_execution_policy.md` §7 (D-084). The run stays
blocked until G3-5 has a real human review (or a written waiver), the pre-registration is frozen
and committed, and a commit is permitted.

## 14. Approvals required before PPO

D-007, D-009, D-012, D-014 (library), D-015, D-016, D-017, D-018, D-019, D-023, D-031,
D-048–D-059, and the agent-design items in §8–§10.

## 15. Profile-conditioned PPO extension [O] (D-085; details Provisional (delegated), D-086)

> **Status:**
> - **Scope and fixed design:** authorised 2026-11-03 under R-S (D-085).
> - **Every detail marked (P):** a Provisional (delegated) choice by Claude Code under D-084.
>   It is not reviewed or approved by the team.
> - **Implementation:** nothing in this section is implemented or run yet.
> - **Abstract:** investor profiles are **not** in the submitted abstract. This is an optional
>   extension; the abstract's research question is unchanged.

*Update (2026-11-03, appended; the text below is kept):* implemented under the 2026-11-03
execution instruction. **D-087 revises §15.5–§15.7:**
- the ablation is an inference-time intervention (correct, neutral and shuffled profiles),
  with no retrained constant arm;
- the held-out region is the joint box RT ≥ 0.6 **and** RC ≤ 0.4, not RT ≥ 0.8;
- both the training and validation splits are evaluated.

The methodology is in `docs/profile_conditioned_ppo.md`, the configuration in
`configs/profile_experiment.yaml`. Status: implemented and tested; real-data pipeline check
only (EXP-009); experiment not run.

### 15.1 Question

Does conditioning the PPO policy on a constant-per-episode investor profile change its training
and validation behaviour, and do its allocations vary with the profile?

**Expected result, stated in advance:** the D-064 reward, costs and constraints do not depend
on the profile. The profile is therefore task-irrelevant, and the optimal policy is the same for
every profile. Little or no systematic profile dependence is expected. Any dependence found is
reported as learned behaviour, **not** as personalisation or suitability.

### 15.2 Representation

- **Vector:** p = (`risk_tolerance`, `risk_capacity`, `investment_horizon`,
  `liquidity_preference`, `growth_preference`), each value in [0, 1].
- **Placement:** appended after the 51 D-062 inputs, giving 56 inputs, as float32. (P)
- **Scaling:** none. The profile is not passed through the training-feature scaler, because it
  is already in [0, 1] and is not a market statistic. (P)
- **Network:** configuration 4's architecture (D-074, 64×64 tanh, separate policy and value
  networks), with input size 56.

### 15.3 Sampling (training)

- At each `reset`, each dimension is drawn i.i.d. from Uniform(0, 1). The profile stays fixed
  until the next reset. (P)
- It uses a dedicated generator, `numpy.random.default_rng([seed, 5])`, so that market data,
  the environment and the PPO random streams are unchanged by the profile draw. (P)
- The sampled profiles are recorded per episode in the run metadata.

### 15.4 Training

- **Hyperparameters:** those of configuration 4 (learning rate 1e-4, `n_steps` 512, entropy 0;
  other settings as D-074).
- **Runs:** seeds 42–46; a configured budget of 100,000 timesteps; training split only;
  `run_kind: full` (clean committed tree, D-075).
- **No new hyperparameter grid (P):** this avoids tuning on validation and keeps the comparison
  with configuration 4 like-for-like.

### 15.5 Ablation (P)

- **A, constant profile:**
  - the same 56-input architecture, seeds and budget;
  - the profile is fixed at (0.5, 0.5, 0.5, 0.5, 0.5) in training and evaluation.
  - This separates the *information* in the profile from the change in input size.
- **B, reference:** the existing configuration-4 checkpoints (EXP-005, 51 inputs). They are
  not retrained.

### 15.6 Unseen-profile generalisation (P)

- **Separate training arm "held-out":**
  - the same as §15.4, except that during training `risk_tolerance` is drawn from
    Uniform(0, 0.8);
  - the other four dimensions are drawn from Uniform(0, 1).
- **Evaluation:** on the in-region set and on the out-of-region set E-out (§15.7).

### 15.7 Evaluation profiles (validation window of D-076) (P)

- **c, centre:** (0.5, 0.5, 0.5, 0.5, 0.5).
- **E-in:** 32 profiles drawn i.i.d. Uniform(0, 1)^5 with `default_rng(20261103)`.
- **E-out:** 32 profiles with `risk_tolerance` drawn from Uniform(0.8, 1) and the other
  dimensions from Uniform(0, 1), with `default_rng(20261104)`.
- **E-in-train:** 32 profiles drawn from the held-out arm's training distribution, with
  `default_rng(20261105)`.
- **Assignment:**
  - the main and ablation-A arms are evaluated on c and E-in;
  - the held-out arm is evaluated on c, E-in-train and E-out.
- **Evaluation method:** deterministic actions (D-076); one episode per (seed, profile) on the
  D-076 validation window, 2017-01-03 to 2019-12-31.
- **Prespecified:** these sets are fixed before any validation look. Each arm has **one**
  validation evaluation.

### 15.8 Metrics and summaries (P)

- **Per (seed, profile):** the D-076 metric set: net Sharpe, net and gross cumulative return,
  volatility, maximum drawdown, cost drag, annualised traded notional and executions.
- **Per arm:**
  - the median over seeds of net Sharpe at the centre profile;
  - for each seed, the median and range of net Sharpe across the evaluation profiles.
- **Profile sensitivity:**
  - start from the centre-profile validation ledger of each seed;
  - rebuild the observations, replace only the five profile inputs with each evaluation
    profile, and compute the deterministic targets;
  - the score is the mean L1 change in target weights (cash included) against the centre
    targets on the same decision dates.
  - Observations are held fixed, so path effects are excluded. This measures associations,
    not causes (D-068).
- **Statistics:** descriptive only. No bootstrap, no p-values and no significance claims for
  this extension.

### 15.9 Comparison

- **Against:** the three D-053 baselines and configuration 4 on the same validation window,
  with identical data, costs, lag and constraints. Their EXP-006 values are reused, with hashes
  checked; no re-selection.
- **Reporting:** results are reported as backtests, with costs and turnover. No superiority
  claim is made without comparable evidence.

### 15.10 Test period

The profile arms are **not** evaluated on 2020–2024 in this protocol (D-086). The single test run
is the D-083 protocol for configuration 4 (`docs/autonomous_execution_policy.md` §7).
