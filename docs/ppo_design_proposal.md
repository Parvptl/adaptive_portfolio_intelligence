# PPO Agent Design — PROPOSED — NOT APPROVED

> **Status: PROPOSED — NOT APPROVED.** This is a design for team review (Parv Patel, Mandar
> Patil).
> - Nothing here is implemented, and no dependency has been added.
> - No decision in [`decision_log.md`](decision_log.md) is changed by this document.
> - Approval must be recorded there, with approver and date, before implementation starts.
> - PPO is a **candidate** algorithm (abstract; D-014). No outcome is assumed.
>
> Prepared 2026-10-18, at commit `817f8b8` plus local, uncommitted Phase C changes. It extends
> the agent-design table in [`research_protocol.md`](research_protocol.md) §8–§13, which is
> also a draft.

Notation: row `d` is a decision row, `L` the execution lag (`timing.py`), and rows are observed
sessions.

## 0. Preconditions (none met yet)

1. Approval of the EXP-002 decisions, and EXP-002 itself (the lag-1 baseline record), on
   train and validation.
2. Approval of every item below that is marked **[decide]**.
3. Resolution of the authorship and repository-identity question (project journal,
   2026-10-18).

## 1. Simulator integration (single source of truth)

- **Fact:**
  - `evaluation.simulator.simulate(returns, targets, lag, window, settings)` runs a whole window
    from a dict of decision row → target weights;
  - `timing.py` holds the timing arithmetic;
  - there is no step-by-step interface.
- **Proposal:** add the smallest step interface **inside** `evaluation/simulator.py`:
  - a `PortfolioState` (value, held weights, row) and a `step(state, target | None) -> (state,
    record)` function;
  - `simulate` is refactored to loop over `step`, so there is exactly one accounting
    implementation;
  - a regression test asserts byte-identical ledgers before and after the refactor.
  - The RL environment adapter (`agents/environment.py`) calls only `step` and `timing.py`. It
    never computes costs, drift, cash or constraints itself.
- **Episode:** one episode covers the evaluation window of one split, from the common start
  (`k0`, the 126-session warm-up, D-058) to the last decision `last_evaluable_decision(e, L)`.
  It starts from cash, and the first action is the funding trade, charged as for the baselines.
  The terminal step is the one whose earned return is row `e`. Episodes never cross a split
  boundary.

## 2. Observation [decide: D-012]

At decision row `d` the observation contains, in a fixed documented order:
1. the causal features dated `d` (`features.csv`; 34 columns by default, D-044);
2. the one-hot regime label dated `d`, using the **frozen** training thresholds (D-045), as
   9 columns (3 trend × 3 volatility);
3. the current pre-trade (drifted) portfolio weights at `d`, for 7 assets plus cash.

- **Leakage:** every element is dated `<= d`. A test perturbs rows `> d` and asserts the
  observation at `d` is unchanged, following the pattern of the existing future-invariance tests.
- **Regime-agnostic ablation** (item 3 without item 2): an optional extension. It is run only
  if approved, with a declared, equal tuning budget.

## 3. Feature scaling [decide]

- Standardise each feature with a mean and standard deviation fitted on **training rows from
  `k0` to the last training decision only**. Freeze them in a JSON artifact, like
  `regime_thresholds.json`, and apply them unchanged to validation and test.
- One-hot and weight inputs are not scaled.
- **Missing values:** none after `k0` (verified for train and validation). Any NaN raises an
  error rather than being filled.
- **Extremes:** clip standardised values to ±10 and log every clipping count. This is a
  numerical safeguard, not a tuning knob.
- **Test:** changing validation or test rows leaves the fitted parameters byte-identical.

## 4. Action and projection [decide]

- The policy outputs `a ∈ R^8` (7 assets + cash). Proposals are `p = softmax(a)`, so `p ≥ 0` and
  `Σp = 1`.
- **Projection:** for each asset, `w_i = min(p_i, 0.40)`, and the capped excess goes **to
  cash**: `w_cash = 1 − Σ_i w_i`. This is deterministic, satisfies `0 ≤ w_i ≤ 0.40` and
  `Σ_i w_i ≤ 1`, and never moves weight to an asset the policy did not choose.
  - It differs from the baselines' `cap_and_redistribute`, which assumes full investment.
    Recommended because the agent may hold cash.
  - Tests cover all-in-one-asset (→ 0.40 asset + 0.60 cash), all-cash, the uniform case, a
    proposal exactly at the cap, and float edge cases. Every projected target must pass the
    simulator's own `validate_target`.
- Logged per decision: raw action, proposal `p`, projected target, and post-trade weights.
- **Cap semantics:** D-057 applies. The cap holds at execution; holdings may drift above it.

## 5. Reward [decide]

- **Primary candidate R1: log net growth.** For a decision at `d` with lag `L`, the step covers
  the simulator rows from the execution `x = d + L` to the row before the next execution:
  `r_step = log(V_end / V_before_trade)`. Here `V_before_trade` is the value at the close of
  `x` before the trade cost, and `V_end` is the value after the last return of the step.
  - It includes that execution's cost (the funding cost on the first step) and every earned
    return, and nothing outside the step.
  - The sum over an episode equals `log(V_final / V_initial)`, with no gaps or double counting.
    A test checks this identity.
- **No reward scaling** is planned. Any scaling must be a fixed constant, declared before
  tuning.
- **Invalid actions** cannot occur after projection. A simulator error, e.g. a non-finite
  value, ends the run with an error, never with a silent penalty.
- **Why:** the abstract asks about investment performance and risk under costs. Log growth is
  cost-aware and additive. Risk is assessed through the evaluation metrics (Sharpe, drawdown)
  rather than shaped into the reward.
- **Optional secondary R2:** the differential Sharpe ratio (Moody & Saffell, the abstract's
  reference [3]). It is compared **on validation only**, with the same tuning budget, and only
  if approved. It must never be selected by test performance.

## 6. Decision frequency [decide]

Decision dates available, counted on the live dataset from the common start (row 125), train
and validation only. The last `L + 1` decisions of each split are then dropped:

| Frequency | Train (2007-07-05 – 2016-12-30) | Validation (2017-01-03 – 2019-12-31) |
| --- | --- | --- |
| Daily | 2,392 | 754 |
| Weekly (first session of each ISO week) | 496 | 157 |
| Monthly (first session of each month) | 114 | 36 |

- **Recommendation: weekly** decisions.
  - Monthly gives too few training decisions for PPO.
  - Daily risks cost-driven churn and noisy rewards.
  - Weekly is a provisional compromise, not an established optimum.
- On non-decision sessions the portfolio drifts, and no trade or cost occurs.
- Orders follow `timing.py`: observation at `d`, execution at `d + L`, earning from `d + L + 1`.
- The agent is evaluated on the **same dates** as the baselines: the common window, the same
  splits and the same drop rule. Baselines keep their own monthly or buy-and-hold schedules.
  This difference in schedule is part of what is compared, and it is reported.
- The frequency is fixed before any tuning and never chosen by test performance.

## 7. Library and versions [decide: D-014]

- **Candidate:** Stable-Baselines3 (PPO) with PyTorch on CPU, added as an optional extra (e.g.
  `.[rl]`). The core package stays free of them, and CI runs the non-RL suite unchanged.
- **Before adding:** check that the chosen versions publish wheels for Python 3.11–3.13 on
  Windows and Linux. Pin version ranges in `pyproject.toml` and record exact installed versions
  in every run's metadata. **Not verified yet**: no installation has been attempted.
- **Determinism:** fixed seeds (Python, NumPy, PyTorch, environment), CPU only,
  `torch.use_deterministic_algorithms(True)`, single-threaded, and a deterministic policy at
  evaluation. Bitwise reproducibility across machines and library versions is **not**
  guaranteed, and that will be stated.

## 8. Seeds, tuning budget and selection [decide: D-016]

- **Seeds:** 42, 43, 44, 45, 46 for every configuration.
- **Search space:** at most 8 configurations, declared before tuning:
  - learning rate {3e-4, 1e-4};
  - `n_steps` {weekly-episode length, 2×};
  - entropy coefficient {0, 0.01};
  - all other PPO settings at library defaults, recorded.

  Training length is a fixed number of timesteps, declared before tuning.
- **Selection:** the configuration with the highest **median over seeds** of validation net
  Sharpe (per session, or annualised with N = 252 if D-023 is approved). Ties go to the simpler
  configuration.
- **Model checkpoint:** the final checkpoint. Validation-based early stopping is used only if
  declared beforehand.
- **Reporting:** for every configuration and seed, train and validation metrics, mean,
  standard deviation, median, minimum and maximum, runtime and hardware. No best-seed
  reporting.
- Baselines stay untuned (fixed 63-session lookback). This asymmetry is reported as a
  limitation that favours the agent.

## 9. Evaluation, statistics and explainability (from the draft protocol)

- **Primary endpoint (proposed):** test-split net annualised Sharpe of the selected
  configuration, as the median over the 5 seeds, at lag 1 and 15 bps.
- **Secondary:** cumulative return, maximum drawdown, recurring turnover, cost drag, per-session
  metrics, regime-conditional metrics with the frozen thresholds, the seed distribution, and
  differences against each baseline.
- **Statistics:** stationary block-bootstrap confidence intervals for Sharpe differences, with
  the block length declared beforehand, plus a multiple-comparison caveat.
- **Explainability:**
  - permutation sensitivity of actions to observation features, with the observation
    perturbed at `d` only so that the timing stays intact;
  - regime-conditional allocation and risk summaries.

  Sensitivity is not causality. SHAP is not planned.

## 10. Test-run pre-registration

Before any `--include-test`, the following must be recorded in the experiment log:
- the frozen configs and their hashes;
- the data and feature ids, and the scaler and threshold artifacts;
- the selected configuration and seeds;
- the primary and secondary metrics;
- the bootstrap settings;
- the named stress windows inside 2020–2024 and their economic motivation.

Then the team authorises the run in writing, and it is run once. Later analyses are labelled
exploratory.

## 11. Approval checklist for this design

| Item | Proposed choice | Status |
| --- | --- | --- |
| Step interface inside the simulator (§1) | `PortfolioState` + `step`, `simulate` refactored | PROPOSED |
| Observation (D-012, §2) | features + one-hot regime + drifted weights | OPEN |
| Scaling (§3) | train-only standardisation, frozen artifact | PROPOSED |
| Projection (§4) | cap with excess to cash | PROPOSED |
| Reward (§5) | R1 log net growth; R2 optional | PROPOSED |
| Frequency (§6) | weekly | PROPOSED |
| Library (D-014, §7) | SB3 + PyTorch, optional extra | OPEN |
| Seeds and budget (D-016, §8) | 5 seeds, ≤ 8 configurations, median selection | OPEN |
| Evaluation (§9–§10) | as above | PROPOSED |
