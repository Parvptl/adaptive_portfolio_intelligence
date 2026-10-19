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

- **Primary candidate R1: log net growth.** *(Interval corrected in the 2026-10-18 review, §12:
  "to the row before the next execution" left the next execution row's return unassigned.)*
  For a decision at `d` with lag `L`, the step covers the cost at the execution `x = d + L`
  and the returns of rows `x + 1` **through the next execution row `x'`** (inclusive):
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
  - *Status note (2026-10-19):* the training-side settings are implemented and recorded in D-075
    (Proposed). A "deterministic policy at evaluation" is **not decided**: it belongs to the
    separate validation-evaluation decision.
  - *Update (2026-10-19):* D-075 was accepted. Evaluation determinism remains undecided.

## 8. Seeds, tuning budget and selection [decide: D-016]

> **Superseded (2026-10-19):** decided by D-066 (accepted 2026-10-19), using the refined grid of
> §13 item 9: `n_steps` {512, 1024}, not "episode length, 2×"; tie-break lower learning rate →
> smaller `n_steps` → no entropy bonus, not "simpler configuration". The text below is the
> original draft.

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

> **Superseded (2026-10-19):** approval used the §14 matrix and the §15 defaults (D-062 to
> D-069, accepted 2026-10-19). The "OPEN" statuses below are historical.

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

## 12. Technical review notes (2026-10-18; the design remains PROPOSED — NOT APPROVED)

The proposal was checked against the code and the train and validation data. No test-split rows
were read.

1. **Reward interval (corrected in §5).** The original text ended a step at "the row before the
   next execution". That leaves the return of row `x'` (earned by the old holdings before the
   trade at the close of `x'`) in no step, and breaks the claimed identity. The correction makes
   steps `(x_k, x_{k+1}]` plus the cost at `x_k`. Then
   `Σ log(V_before_trade(x_{k+1}) / V_before_trade(x_k)) = log(V_final / V_initial)`.
2. **Reward alignment: [decide].** Two telescoping definitions exist:
   - **(R1a) execution-aligned**, as in §5: the step for a decision at `d_k` ends at
     `x_{k+1} = d_{k+1} + L`. With `L = 1`, its reward includes the return of row
     `d_{k+1} + 1`, which comes **after** the next observation at `d_{k+1}`. This is not
     leakage, since the reward is never an observation input. But the environment must
     simulate `L` rows past the next observation before it can return the reward.
   - **(R1b) decision-aligned:** the step is `(d_k, d_{k+1}]`. The reward is fully known when
     the next observation is emitted, which is the standard environment contract. The first
     `L` rows of each step are earned by the previous holdings, while the current weights are
     part of the observation.

   **Recommendation: R1b**, for clean environment semantics. Both satisfy the telescoping
   identity, and that identity must be tested.
3. **Weekly calendar.**
   - `baselines.decision_rows` supports `daily`, `monthly` and `never` only
     (`REBALANCE_SCHEDULES`). A `weekly` schedule is not implemented, although
     `environment.rebalance_frequency` accepts `weekly`.
   - If weekly is approved, add it following the `monthly` pattern: the first session of the
     window (`k0`, the funding decision), then the first observed session of each new ISO week,
     with tests.
4. **Regime label `unavailable`.** `regimes.csv` uses a tenth label, `unavailable`, during
   warm-up (62 training rows). From the common start (row 125) only the 9 trend × volatility
   labels occur in train and validation. The environment must **raise** if it meets
   `unavailable` or any unknown label, rather than encode it.
5. **Pending orders.** With `L = 1` and weekly decisions, the previous order has always executed
   before the next observation, since consecutive decisions are at least 2 rows apart. With
   daily decisions an order would still be pending at the next observation, and the observation
   would need to include it. This is another reason not to use daily decisions without changing
   the design.
   *Correction (§13, item 5): this daily-decision statement is wrong. With `L = 1` the order
   from `d` executes at the close of `d + 1`, which is the next observation row. It is
   executed, not pending.*
6. **Action space for Stable-Baselines3.**
   - PPO samples Gaussian actions that the library clips to the `Box` bounds before the
     environment sees them. Declare finite bounds (e.g. `[-5, 5]^8`); the softmax is
     shift-invariant.
   - The projection is applied inside the environment, so no gradient through it is needed.
   - `Σ min(p_i, 0.40) ≤ Σ p_i = 1` holds by construction.
7. **Selection metric independent of D-023.** Annualised Sharpe is the per-session Sharpe
   multiplied by `√N`, a positive constant. So "median validation net Sharpe" ranks
   configurations identically per session or annualised, and model selection does not wait
   for D-023. Reported values still do.
8. **Primary endpoint wording.** §9 here specifies "median over the 5 seeds". The draft
   `research_protocol.md` §10 does not say how seeds are aggregated. Align both before approval.
   The annualised form needs D-023.
9. **Training length:** the fixed timestep budget in §8 is not yet a number. It must be declared
   before tuning.
10. **CI and optional dependencies.** CI installs `.[dev]` only, on Python 3.11, 3.12 and 3.13.
    RL tests must skip cleanly (`pytest.importorskip`) when the `rl` extra is absent, or CI must
    install it. **[decide]**
11. **Observation size:** 34 features + 9 one-hot regime columns + 8 weights = **51** inputs
    (34 features verified in the live feature set).

## 13. Decision memo (2026-10-18) — every choice here is PROPOSED, nothing is approved

**Verification:**
- Read against `timing.py` and `evaluation/simulator.py` at `a03c4b7`.
- Numeric checks used the actual `simulate` and `validate_target` on synthetic data, in a
  script outside the repository. No test-split rows were read, and nothing was installed.

**Notation:**
- `V_t` is the ledger `value` at the close of row `t`, after any trade at that close.
- `V^pre_t = V_{t−1}(1 + g_t)` is the value at the close of `t` before that row's cost.
- The simulator's recursion is `V_t = V_{t−1}(1 + g_t − c_t(1 + g_t)) = V^pre_t (1 − c_t)`.
- Before the funding row `x_0`, the portfolio is cash worth `V_0` (`initial_capital`).

### Classification of the review items

| # | Item | Classification | Status after this memo |
| --- | --- | --- | --- |
| 1 | Reward window and log-growth identity | Confirmed defect in the original §5 | Already resolved (corrected in `a03c4b7`); identity verified numerically |
| 2 | Decision- vs execution-aligned reward | Unresolved research decision | Both verified; R1b recommended (below) |
| 3 | Weekly schedule missing | Implementation requirement (if weekly is approved) | Minimum implementation specified (below) |
| 4 | `unavailable` regime label in warm-up | Implementation requirement | Verified: absent in train and validation from row 125 |
| 5 | Pending orders, daily, lag 1 | **Confirmed defect in §12 item 5**, which was wrong. §2 says "pre-trade weights", which is ambiguous on execution rows (a documentation inconsistency). | Corrected below; observation definition proposed |
| 6 | Finite action bounds | Implementation requirement | Bounds and projection specified; 25,006 actions validated |
| 7 | Selection Sharpe vs annualisation | Already resolved (holds while rf = 0) | Verified from `sharpe_ratio` |
| 8 | Seed aggregation inconsistent | Documentation inconsistency | One rule proposed for the protocol and this design |
| 9 | Timestep budget missing | Unresolved research decision | Concrete budget proposed |
| 10 | Optional RL dependencies and CI | Implementation requirement + decision | CI layout proposed |
| — | 51-dimensional observation | Already resolved (counts) | 34 features verified; 9 labels from row 125; 8 weights, defined as end-of-row (item 5) |

### Items 1–2: reward timing (verified derivation)

Decisions `d_0 < d_1 < … < d_K`, with `d_0 = k0`, `d_K <= last_evaluable_decision(e, L) = e − L − 1`,
execution rows `x_k = d_k + L`, and split end `e`.

- **R1b, decision-aligned (recommended):** `r_k = log(V_{d_{k+1}} / V_{d_k})` for `k < K`, and
  `r_K = log(V_e / V_{d_K})`. Use `V_{d_0} := V_0` when `d_0 < x_0` (still in cash).
  - **Telescoping:** `Σ_k r_k = log(V_e / V_0)`, exactly the net log growth of the ledger. The
    intervals `(d_k, d_{k+1}]` are disjoint and cover `(d_0, e]`, so there are no gaps and no
    double counting.
  - Each interval contains the cost of executing action `k` (at `x_k = d_k + L <= d_{k+1}`,
    because decisions are at least `L` rows apart) and the returns of rows `d_k + 1 … d_{k+1}`.
    The first `L` of those rows are earned by the previous holdings.
  - The reward is fully known when the observation at `d_{k+1}` is produced.
- **R1a, execution-aligned:** `r_k = log(V^pre_{x_{k+1}} / V^pre_{x_k})`, and
  `r_K = log(V_e / V^pre_{x_K})`, with `V^pre_{x_0} = V_0`. It also telescopes to
  `log(V_e / V_0)`. It attributes returns exactly to each action's holdings, but its value
  needs `L` rows after the next observation.
- **Numeric check:** on 30 weekly and 148 daily lag-1 decisions with random projected actions,
  `|Σ r − log(V_e / V_0)|` was at most 4.5e-16 for both definitions.
- **Terminal handling (proposed):** the episode ends after `r_K`, with `terminated = True`. The
  split end is a fixed, finite horizon; nothing is bootstrapped past `e`. Decisions after
  `e − L − 1` are never offered: the same rule as the baselines and as the `boundary` pairs of
  `next_period_targets`.

### Item 3: weekly schedule (minimum implementation, if weekly is approved)

- Add `"weekly"` to `REBALANCE_SCHEDULES` (order `daily, weekly, monthly, never`). In
  `decision_rows`, use the window's first row `start`, then every row whose ISO
  `(year, week)` differs from the previous row's. Use the ISO year so that a week spanning
  31 December stays one week.
- **Tests:**
  - a mid-week start;
  - a week whose Monday is a holiday;
  - the ISO year boundary (e.g. 2015-12-31 / 2016-01-04);
  - a one-session week;
  - equivalence with the counts in §6 (train and validation dates only);
  - `check_against` ordering (weekly is not finer than `rebalance_frequency: daily`).
- Baselines keep their schedules. This code only makes weekly available.

### Item 5: what happens to an action chosen at `d` (lag 1)

1. At the close of `d` the policy observes data dated `<= d` and chooses a target.
2. The order executes at the close of `d + 1` (`execution_row`), against the weights drifted
   through row `d + 1`. The return of row `d + 1` is earned by the **previous** holdings.
3. The new weights earn from row `d + 2`.
4. Next observation:
   - **weekly** (decisions at least 2 rows apart): the order executed before the next
     decision row, so there is no pending order and no execution at that row;
   - **daily**: the next observation row *is* `d + 1`. The order executes at that close, before
     the observation is formed, so it is not pending (147 of 147 daily cases checked; the
     ledger weights at `d + 1` equal the executed target).
   - A pending order would only arise if decisions were fewer than `L` rows apart, e.g. daily
     with `L >= 2`. That is not part of this design.
5. **Proposed observation definition:** the weights are the **end-of-row ledger weights at `d`**
   (`weight_*` of row `d`: post-trade if an execution happened at that close, otherwise
   drifted). This replaces the ambiguous "pre-trade (drifted) weights" in §2. At most one order
   is ever outstanding, and there are no simultaneous orders.

### Item 6: action bounds and projection

- **Action space:** `Box(low=−5, high=5, shape=(8,))`. Stable-Baselines3 clips sampled actions
  to these bounds.
- **Projection:** `p = softmax(a)`, then `w_i = min(p_i, 0.40)` for the 7 assets, and
  `w_cash = 1 − Σ w_i`. The simulator receives the 7 risky targets; cash is implicit. Requires
  `allow_cash: true` (D-015).
- **Validation:**
  - 25,006 actions (edge cases, uniform in the bounds, and values far outside, which are
    clipped) all passed `validate_target`;
  - maximum risky sum 0.999994;
  - all-in-one-asset gives 0.40 asset + 0.60 cash.
- **Consequence to approve:** the bounds keep every risky weight above zero (minimum
  `≈ 6.5e-6`), so exact zeros never occur. Each rebalance makes negligible residual trades.
  Wider bounds lower the minimum but make exploration harder.

### Item 7: selection metric

`sharpe_ratio` computes `√N · mean / std`. With rf = 0 the ranking is identical per session or
annualised, so **model selection does not depend on D-023**. If a non-zero rf were adopted,
this would no longer hold exactly.

### Item 8: one seed-aggregation rule (proposed, for the protocol and this design)

- **Validation selection:** for each configuration, compute the validation net Sharpe of each
  seed (42–46) and take the **median of the 5**. Select the highest median. Ties go to the lower
  learning rate, then the smaller `n_steps`, then no entropy bonus. All configurations and seeds
  are reported.
- **Final test reporting:** for the selected configuration, the **primary endpoint is the median
  over the same 5 seeds of test-split net Sharpe**, annualised with N if D-023 is approved,
  otherwise per session. Every seed's value is reported, plus mean, standard deviation, minimum
  and maximum. No other seed or configuration is chosen after the test.
- **Inference:** a stationary block bootstrap of time blocks, applied **jointly** to all
  five seeds' and every baseline's daily net return series, with the block length declared
  before the test run.
  - Each resample gives the median-over-seeds Sharpe difference against each baseline; the
    confidence intervals use the percentiles of those.
  - Per-seed differences are reported too.
- There is no experiment-log entry for an RL run yet. When one exists it must record this rule.

### Item 9: training budget (proposed)

- **Per run: 100,000 environment timesteps.** A weekly training episode has about 494 steps
  (496 decision dates minus `L + 1`), so this is about 200 passes over the training period.
- **Search grid, refining §8:** learning rate {3e-4, 1e-4} × `n_steps` {512, 1024} × entropy
  coefficient {0, 0.01} = **8 configurations** × 5 seeds = **40 runs**, i.e. 4.0 million
  timesteps. `n_steps` changes from "episode length" to powers of two so that
  `batch_size = 64` divides it.
- **Checkpoint:** final checkpoint only, with no early stopping. Validation is used once per run,
  for selection.
- **Feasibility (assumption, not measured):** at an assumed 300–2,000 environment steps per
  second on one CPU core, 4.0 million steps takes about 0.6–4 hours.
  - A smoke test measures real throughput **before** any tuning run.
  - If it shows the budget is infeasible, the team approves a revised number before tuning
    starts. It is never revised after seeing validation results.
- **Risk to state:** about 200 passes over one historical path invites over-fitting to that
  path. Validation selection and the 5 seeds are the guards. Random training start offsets
  would be a different design choice, not proposed here.

### Item 10: optional dependencies and CI (proposed)

- **Package:** RL dependencies (`stable-baselines3`, `torch`, and `gymnasium` as SB3 requires
  it) go in an optional extra, `rl`, with bounded versions chosen after a wheel check for Python
  3.11–3.13. The core package and `.[dev]` stay unchanged.
- **Code:**
  - Projection, reward partition, observation assembly and the weekly schedule are pure NumPy
    and pandas, importable and tested **without** the extra, so the existing CI matrix covers
    them.
  - Only the Gymnasium and SB3 wrappers import the extra.
- **Tests:** RL-library tests carry a new `rl` marker (registered in `pyproject.toml`, since
  `--strict-markers` is on) and call `pytest.importorskip("stable_baselines3")`. The core matrix
  (`.[dev]`, Python 3.11–3.13) runs unchanged and skips them.
- **CI:** one extra job (Ubuntu, Python 3.12, `.[dev,rl]`, CPU-only torch) runs
  `pytest -m rl` with a short smoke budget. A run never trains a real model.

## 14. Gate 2 decision matrix (2026-10-19) — every recommendation is PROPOSED, approval by both teammates required

| # | Item | Current proposal | Contradiction or gap | Options | Consequences and risks | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Observation weights | §2: "pre-trade (drifted)" weights; §13 item 5: end-of-row ledger weights | Two definitions; they differ only on execution rows | (a) end-of-row; (b) pre-trade | (b) is ambiguous on an execution row, where the observation would show weights that are about to change | (a) end-of-row |
| 2 | Observation contents | 34 features + 9 one-hot regimes + 8 weights = 51 | `unavailable` regime label in warm-up rows | (a) as proposed; (b) without regimes (that is an ablation, not the primary) | (a) needs the environment to raise on `unavailable`; it never occurs from row 125 (train and validation) | (a) |
| 3 | Reward timing | §5: execution-aligned R1a; §13: decision-aligned R1b | Two definitions | R1a; R1b | Both partition log growth exactly (verified). R1a's reward needs `L` rows after the next observation. R1b is complete at the next observation. | R1b |
| 4 | Terminal handling | §13: `terminated` at the split end after the last evaluable decision | Not in §5 or §11 | terminated; truncated with bootstrapping | Bootstrapping past `e` would value states with no evaluable future | terminated |
| 5 | Decision frequency | weekly (§6); protocol §8: "daily or weekly" | No weekly schedule code exists | daily; weekly; monthly | Daily: 2,392 training steps, churn. Weekly: 496, needs `decision_rows` code. Monthly: 114, too few. | weekly, after the code and tests exist |
| 6 | `n_steps` | §8: {episode length, 2×}; §13: {512, 1024} | Conflict | as §8; as §13 | §8's values do not divide by `batch_size` 64 | {512, 1024} |
| 7 | Learning rate and entropy | {3e-4, 1e-4} × {0, 0.01} | — | as proposed; wider | A wider grid needs more compute and invites over-search | as proposed |
| 8 | Training budget | 100,000 timesteps per run; 40 runs | Throughput not measured | as proposed; smaller; larger | About 200 passes over one path risks over-fitting it; the cost is unknown until a smoke test | as proposed, with a throughput smoke test before tuning; revise only before tuning |
| 9 | Seeds and selection | seeds 42–46; median validation net Sharpe; tie-break lower learning rate → smaller `n_steps` → entropy 0 | Protocol says "at least 5" | as proposed | Ranking is independent of D-023 while rf = 0 | as proposed |
| 10 | Bootstrap | joint stationary block bootstrap over time | **Block length unspecified** | fixed length (e.g. 21 or 63 sessions); data-driven rule (e.g. Politis–White) declared in advance | Must be fixed before the test run, or it can be tuned to the result | fixed 21 sessions, plus 63 as a declared sensitivity |
| 11 | Stress windows | named before the test | **None named** | peak-to-trough windows of a broad index, e.g. S&P 500 2020-02-19 – 2020-03-23 (COVID crash) and 2022-01-03 – 2022-10-12 (rate shock) | Choosing after seeing results biases them; dates must come from public index history, not test results | name windows defined by a public, pre-stated rule (e.g. S&P 500 peak to trough), with dates **confirmed from a cited public source**, before Gate 3 |
| 12 | Output location (D-017) | Open | — | `data/processed/experiments/<id>/` (git-ignored); `reports/results/` (needs a `.gitignore` change) | `reports/` is only partly ignored, so outputs could be committed by mistake | `data/processed/experiments/<id>/` |
| 13 | Dependencies and CI | `rl` extra (SB3 + torch + gymnasium); `rl` test marker; one extra CI job | Wheels for Python 3.11–3.13 not checked | as proposed; CI also installs `rl` everywhere | A heavy CI on every job is slow; the core matrix must stay independent of RL | as proposed, after a wheel check (needs authorisation to install) |
| 14 | Explainability | permutation sensitivity plus regime-conditional summaries; no SHAP | Claims must be limited | as proposed; plus SHAP | Sensitivity shows association, not causation; SHAP adds a dependency | as proposed; state that it is not causal |
| 15 | AI-use disclosure and attribution | README and journal disclose Claude Code; commit identity unresolved | Commit metadata disputed | team resolves | Academic-integrity risk if attribution is inaccurate | each person commits their own work under their own identity; the journal records who did what |
| 16 | Proposal §11 | Lacks items 3, 4, 5 and 13 | — | — | Approval from §11 alone would be incomplete | approve from this matrix |

## 15. Proposed defaults (2026-10-19) — still PROPOSED, not approved

A team member put forward the §14 recommendations as the proposed defaults, recorded as
D-062 to D-069:
- 51 inputs with end-of-row weights;
- training-only standardisation, frozen, clipped at ±10 with counts logged;
- softmax actions with a 0.40 cap and excess to cash;
- decision-aligned log-growth reward after costs, terminating at the last evaluable decision;
- weekly decisions;
- seeds 42–46, median validation Sharpe with the predefined tie-break;
- 100,000 timesteps × 8 configurations × 5 seeds, subject to a throughput check;
- simulator reuse with parity tests;
- outputs in `data/processed/experiments/<id>/`;
- explainability as permutation sensitivity plus regime summaries, which indicate associations,
  not causation.

**Still open until before Gate 3:** the bootstrap details (block length, resamples, seed,
confidence-interval method, statistic) and the stress-window rule and its external source.

**Open:** commit authorship (D-070). The approval channel follows R-S (D-061). No item above is
approved yet.

**Update (2026-10-19):**
- D-062 to D-069 were **accepted** as the working design for PPO implementation. A team member
  communicated the approval under R-S (D-061); the message names no author, and the other
  teammate's confirmation was not sought.
- Still **open for Gate 3:** bootstrap settings and the stress-window protocol. Their values must
  not be invented, and must not be chosen using the sealed test period.
- Still **open:** D-070 (commit authorship).
