# Approval Checklist — DRAFT — FOR TEAM REVIEW

> **DRAFT — FOR TEAM REVIEW. Nothing in this document is approved.**
> - Prepared 2026-10-18 at commit `a03c4b7`, which has two local commits not yet pushed or run
>   through CI, plus uncommitted edits to `ppo_design_proposal.md` and `research_protocol.md`.
> - It lists the decisions the team must take, one by one. No box below is ticked, no name is
>   signed and no date is filled in; only Parv Patel and Mandar Patil may do that, each for
>   themselves.
> - An approval counts only when it is recorded in [`decision_log.md`](decision_log.md) as
>   **Accepted**, with approver and date (decision log, "How to add or update a decision").
>   This checklist is a working aid, not the record.
> - **Parent decisions D-010 and D-013** and **test-row handling:** see the governance items
>   in §1.5. Both are needed before EXP-002.
> - **Prepared command and verification plan:** [`exp002_runbook.md`](exp002_runbook.md)
>   (PREPARED — NOT EXECUTED).
> - **Recording approvals honestly:** each teammate fills in their own lines. Given the
>   unresolved commit-identity question (project journal, 2026-10-18), record approvals in a
>   way that identifies the person: for example, each person commits their own lines from their
>   own account, or confirms in writing.

**Gates:**
- **Gate 1 — Baseline protocol (EXP-002).** **EXP-002 cannot run until every Gate 1 decision
  marked *required* is explicitly approved.**
- **Gate 2 — PPO design.** Only after Gate 1 and EXP-002. No PPO code before Gate 2 is
  approved.
- **Gate 3 — Final test run.** Separate and later (`research_protocol.md` §13).

**Test split:** **No test-split row (2020–2024) may be read, evaluated or used during EXP-002,**
and `--include-test` must not be used. The backtest excludes the test split by default (D-056).
EXP-002 covers training and validation only.

**How to respond:** decisions can be approved individually; no blanket approval is needed.
For each item, each teammate ticks one box, writes the date and adds notes or requested changes.
A rejected item or one with changes requested stays **unresolved**.

---

## Gate 1 — Baseline protocol for EXP-002

### 1.1 Required decisions

#### D-053 — Conventional baselines (proposal for D-010)
- **Proposed decision (decision log):**
  - `equal_weight_monthly`: 1/N, rebalanced at the first session of each month;
  - `buy_and_hold_equal_weight`: 1/N at the start, then drift;
  - `inverse_volatility_monthly`: weights ∝ 1/σ over the last 63 returns, capped at
    `max_weight`, rebalanced monthly.

  No tuning and no regime information.
- **Why it matters:** this is the comparison set for every later result.
- **Caveat:** no optimisation-based baselines (minimum variance, risk parity). The baselines are
  untuned, while the agent would be tuned; that asymmetry is reported.
- **Affects:** `configs/backtest.yaml` `strategies`; `baselines/strategies.py`; handbook §13.6.
  Approving it also resolves D-010.

| Teammate | Approve | Reject | Changes requested | Date | Notes |
| --- | --- | --- | --- | --- | --- |
| Parv Patel | [ ] | [ ] | [ ] | | |
| Mandar Patil | [ ] | [ ] | [ ] | | |

#### D-007 — Transaction-cost rates
- **Proposed decision:** 10 bps proportional cost plus 5 bps slippage, i.e. 15 bps of traded
  notional.
- **Why it matters:** sets the level of every net result.
- **Caveat:** round-number placeholders, not estimated from execution data. Cost sensitivity
  runs (e.g. 0 and 30 bps) are an optional extension needing separate approval.
- **Affects:** `configs/environment.yaml` (`transaction_cost_bps`, `slippage_bps`); handbook §4
  and §13.3.

| Teammate | Approve | Reject | Changes requested | Date | Notes |
| --- | --- | --- | --- | --- | --- |
| Parv Patel | [ ] | [ ] | [ ] | | |
| Mandar Patil | [ ] | [ ] | [ ] | | |

#### D-031 + D-049 — Cost basis and turnover cap
- **Proposed decision (D-049):** at each execution, cost = 15 bps × traded notional of
  **non-cash** assets (`portfolio_turnover(..., cash_column)`). It is charged on the value
  before the cost and deducted pro rata. The initial funding trade is charged. Net return =
  `g − c(1 + g)`.
- **For D-031:** accept that cost basis, and use **no turnover cap** (`max_turnover: null`).
- **Why it matters:** defines the costs and turnover reported for every strategy.
- **Caveats:**
  - Charging on the pre-cost value is an order-`k²` approximation (handbook §13.3).
  - The D-031 **cap measure** stays **Open** even if "no cap" is approved. It only needs
    deciding if a cap is ever introduced, and the simulator refuses a cap until then.
- **Affects:** `evaluation/simulator.py` (implemented); `configs/environment.yaml`
  (`max_turnover`); handbook §13.3.
- **Two separate decisions:**
  - D-049 is the cost model;
  - D-031 is the cost basis plus "no cap". Its cap-measure part stays Open.

| Teammate | Item | Approve | Reject | Changes requested | Date | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Parv Patel | D-049 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-049 | [ ] | [ ] | [ ] | | |
| Parv Patel | D-031 (cost basis + no cap) | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-031 (cost basis + no cap) | [ ] | [ ] | [ ] | | |

#### D-009 — Split dates and test-set policy
- **Proposed decision:** train 2007-01-01 to 2016-12-31; validation 2017-01-01 to 2019-12-31;
  test 2020-01-01 to 2024-12-31. Splits are chronological and non-overlapping, and the test
  period is used **once**, for the final evaluation.
- **Why it matters:** defines what may be fitted, selected and reported.
- **Caveat:** validation is only 3 years (754 sessions). Walk-forward evaluation (D-018) is not
  implemented.
- **Affects:** `configs/experiment.yaml` `splits`; all pipelines.

| Teammate | Approve | Reject | Changes requested | Date | Notes |
| --- | --- | --- | --- | --- | --- |
| Parv Patel | [ ] | [ ] | [ ] | | |
| Mandar Patil | [ ] | [ ] | [ ] | | |

#### D-015 (with D-050, D-057) — Constraints and cash
- **Proposed decision:**
  - long-only; fractional weights; Σ risky weights ≤ 1; the remainder is cash;
  - per-asset cap **0.40 on target weights at each execution** (D-057): holdings may drift above
    it between rebalances, and no trade is forced;
  - invalid targets are rejected, never clipped (D-050);
  - cash earns **rf = 0**;
  - daily rebalancing is allowed (`rebalance_frequency: daily`; the three baselines use
    monthly or never). This is part of D-015's recorded text.
  - D-015's recorded text also says "no turnover cap", the same choice as the D-031 row.
    Approving one but rejecting the other would be contradictory.
- **Why it matters:** constrains every strategy identically; rf = 0 affects Sharpe and the value
  of holding cash.
- **Caveat:** rf = 0 is a simplification. T-bill yields were about 4–5 % in 2022–2024, so a
  cash-holding strategy is understated in part of the test period. The alternative is a T-bill
  series, which is new scope. The 0.40 cap is provisional.
- **Affects:** `configs/environment.yaml` `constraints`, `risk_free_rate`;
  `evaluation/simulator.py`; handbook §13.4.

| Teammate | Item | Approve | Reject | Changes requested | Date | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Parv Patel | D-015 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-015 | [ ] | [ ] | [ ] | | |
| Parv Patel | D-050 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-050 | [ ] | [ ] | [ ] | | |
| Parv Patel | D-057 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-057 | [ ] | [ ] | [ ] | | |

#### D-048 + D-055 — Execution timing and primary lag (proposal for D-013)
- **Proposed decision:**
  - decide at the close of row `d` from data dated `<= d`; execute at the close of `d + L`;
    earn from row `d + L + 1`;
  - `L` is counted in observed sessions and is required in the config;
  - **L = 1 is the primary convention, and L = 0 an idealised sensitivity case only** (D-055);
  - one shared implementation, `timing.py`.
- **Why it matters:** this is the realism of execution. Lag 0 trades at a price the signal has
  already used.
- **Caveat:** EXP-001 used lag 0, so it is the sensitivity case, not the primary record.
- **Affects:** `configs/backtest.yaml` (`execution_lag_sessions: 1`); `timing.py`; handbook
  §13.2. Approving both resolves D-013.

| Teammate | Item | Approve | Reject | Changes requested | Date | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Parv Patel | D-048 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-048 | [ ] | [ ] | [ ] | | |
| Parv Patel | D-055 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-055 | [ ] | [ ] | [ ] | | |

#### D-051 + D-056 + D-058 — Evaluation protocol, test opt-in, common window
- **Proposed decisions:**
  - **D-051:** each split is simulated independently from cash, with a common start for all
    strategies; decisions whose earned return falls in the next split are dropped.
  - **D-056:** the test split is evaluated only with `--include-test`; train and validation are
    the default.
  - **D-058:** `common_start_history_sessions: 126`, the longest feature window. On the live
    data, the first training decision is 2007-07-05 (row 125). Validation and test windows are
    unchanged.
- **Why it matters:** comparable dates for every strategy and for a later agent, and a sealed
  test split.
- **Caveat:** independent splits are not one continuous track record. D-058 depends on the
  feature windows of D-044.
- **Affects:** `evaluation/backtest.py`; `configs/backtest.yaml`; CLI; handbook §13.5.

| Teammate | Item | Approve | Reject | Changes requested | Date | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Parv Patel | D-051 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-051 | [ ] | [ ] | [ ] | | |
| Parv Patel | D-056 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-056 | [ ] | [ ] | [ ] | | |
| Parv Patel | D-058 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-058 | [ ] | [ ] | [ ] | | |

#### D-052 + D-059 + D-054 — Metrics and outputs
- **Proposed decisions:**
  - **D-052:** report gross and net cumulative return, maximum drawdown, per-session volatility
    and Sharpe (rf 0), traded notional, turnover and costs. Annualised metrics only when
    `periods_per_year` is set.
  - **D-059:** report funding traded notional separately; annualised turnover uses recurring
    trades only, while the funding cost stays in net results.
  - **D-054:** `configs/backtest.yaml`, plus deterministic, content-addressed outputs in
    `data/processed/backtests/<id>/` (git-ignored).
- **Why it matters:** the definitions of the reported numbers.
- **Caveat:** Sortino is not implemented, and the abstract does not require it.
- **Affects:** `evaluation/performance.py`, `evaluation/backtest.py`; handbook §13.7–§13.9.

| Teammate | Item | Approve | Reject | Changes requested | Date | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Parv Patel | D-052 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-052 | [ ] | [ ] | [ ] | | |
| Parv Patel | D-059 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-059 | [ ] | [ ] | [ ] | | |
| Parv Patel | D-054 | [ ] | [ ] | [ ] | | |
| Mandar Patil | D-054 | [ ] | [ ] | [ ] | | |

### 1.2 Optional for EXP-002 (it can run without it)

#### D-023 — Annualisation factor
- **Proposed decision:** N = **252** for daily data. Annualised Sharpe = √252 × per-session
  mean/std; CAGR over return periods.
- **Evidence:** training years 2008–2016 average 251.9 observed sessions per year.
- **Why it matters:** the abstract names the Sharpe ratio; annualised values are the usual way
  to report it.
- **If not approved:** EXP-002 runs with **per-session metrics only** (`periods_per_year: null`).
- **Caveat:** √N scaling assumes independent returns.
- **Affects:** `configs/backtest.yaml` `periods_per_year`. Approval means setting it to 252
  **before** EXP-002.

| Teammate | Approve | Reject | Changes requested | Date | Notes |
| --- | --- | --- | --- | --- | --- |
| Parv Patel | [ ] | [ ] | [ ] | | |
| Mandar Patil | [ ] | [ ] | [ ] | | |

### 1.3 Related data and feature decisions (also Proposed)

EXP-002's numbers depend on these too. Either approve them, or tick "acknowledge as
provisional", meaning EXP-002 is reported as conditional on them.

| ID | Proposed decision (decision log) | Parv: approve / reject / provisional, date | Mandar: approve / reject / provisional, date |
| --- | --- | --- | --- |
| D-006 | Data range 2007-01-01 to 2024-12-31, daily (provisional) | | |
| D-034 | Universe SPY, EFA, EEM, IEF, TLT, LQD, GLD (provisional) | | |
| D-036 | Missing data: `error` by default, never fill | | |
| D-037 | Price field `adj_close` (total-return approximation) | | |
| D-038 | Rows labelled by their own date; split boundary semantics | | |
| D-044 | Feature set and windows (longest 126, which fixes D-058) | | |
| D-008 | Provider: `csv` is the config default, `yfinance` the opt-in live source. EXP-002 would use the existing yfinance snapshot (see below), including the provider's terms of use | | |
| D-035 | Daily data on the observed session calendar (no exchange calendar) | | |
| D-039 | Raw snapshots with manifest and checksums; content-hashed dataset ids (reproducibility) | | |
| D-042 | Data-validation sanity thresholds (provisional) | | |

**Dataset EXP-002 would use** (from `metadata.json` and the raw manifest only; no data rows
read):
- processed dataset `8e00568ee2aa4de7`;
- raw snapshot `e27437b97742fa43`;
- provider yfinance 1.7.0, retrieved 2026-10-15T10:21:14Z.

**How the run finds it (verified from configuration, 2026-10-18):**
- The processed id is a hash of the data request (universe, start, end, frequency, provider)
  and the processing settings (missing-data policy, price field, splits, validation
  thresholds, pipeline version).
- With the current configs, `--provider yfinance` resolves exactly to `8e00568ee2aa4de7`
  without importing yfinance and without network access. Without that flag, the `csv`
  default resolves to a different id (`a0b557b83c1c99cb`) that does not exist, so the run
  would fail rather than use other data.
- `--dataset-dir data/processed/8e00568ee2aa4de7` names the same dataset explicitly.

**Consequence for approvals:** this snapshot matches the **current** values of D-006, D-008,
D-009, D-034, D-035, D-036, D-037 and D-042.
- If any of them is approved **with changes**, the dataset id changes and this snapshot no
  longer applies.
- A rebuild would then be needed, and for a new date range or universe that means a new
  download, which needs separate authorisation.
- EXP-002 could not run offline until then.

**Is provisional acknowledgment enough?** For running EXP-002, yes: it is a baseline record
conditional on these data choices. Its report must then say the results depend on provisional
data decisions, and must not describe those decisions as validated (`CLAUDE.md`).

### 1.4 Not required for EXP-002 (they stay Proposed or Open)

| ID | Why EXP-002 does not depend on it |
| --- | --- |
| D-012, D-043, D-045, D-046, D-047 | Agent observations, feature timing, regimes and feature outputs. The baselines use no features or regimes; only the window length (D-044, D-058) matters |
| D-016 | Seeds: the baseline backtest is deterministic |
| D-017 | RL output location: backtest outputs follow D-054 (`data/processed/backtests/`) |
| D-018 | Walk-forward is not implemented and not part of EXP-002 |
| D-019 | Embargo: baselines make one-step decisions, and D-051 drops decisions whose earned return crosses a split boundary |
| *Already Accepted:* D-011, D-021, D-022, D-024–D-030 | Metric and turnover conventions used by EXP-002, accepted 2026-10-13. Listed for completeness; no new approval needed |
| D-001–D-004, D-020, D-040, D-041 | Project structure, licence, shorting bound and dependencies; no effect on results. D-041 (yfinance extra) is not needed to *read* the existing snapshot |

### 1.5 Governance items for Gate 1 (team choices; not research results)

#### G-T — Test-period rows during EXP-002
- **Fact (code, 2026-10-19; local, uncommitted):** the default backtest now loads bounded
  data.
  - `splits.csv` (dates and labels only) is read up to the first row dated on or after the
    configured `test.start`. That row's label is checked. The boundary comes from
    `experiment.yaml`, not from the file's labels.
  - `returns.csv` rows are read only up to that point. **Test-period return values are never
    parsed.**
  - All contract checks still run on the rows read.
  - Synthetic tests prove it: corrupted or removed test rows leave results byte-identical.
  - Details: `exp002_runbook.md` §4.
  - Before 2026-10-19 the whole files were loaded for checks only.
- **Options:**
  - **(a)** accept the bounded loading as satisfying test isolation for EXP-002;
  - **(b)** require stricter handling, e.g. not even reading the first test row's date. That
    needs row counts in dataset metadata, i.e. a rebuild, which needs separate
    authorisation.
- **Consequence:** EXP-002 cannot run until both teammates choose the same option. Details
  are in `exp002_runbook.md` §4.

| Teammate | Choice (a / b) | Date | Notes |
| --- | --- | --- | --- |
| Parv Patel | | | |
| Mandar Patil | | | |

#### G-P — Recording parent decisions D-010 and D-013
- **Fact (decision log):**
  - Rule 3 of "How to add or update a decision" covers changing an **accepted**
    decision only. No rule covers an Open or Proposed question that a later decision
    answers.
  - The only precedent: D-005, a proposal, is marked "Superseded by D-034" while D-034 is
    itself only Proposed.
  - **Documentary mismatch (not fixed, because the decision log stays unchanged until
    approvals exist):** the summary table records D-010 and D-013 as "Proposed (see D-053)"
    and "Proposed (see D-048)", but their entries say "Status: Open".
- **Options**, applying once D-053 (for D-010), and D-048 + D-055 (for D-013), are accepted:
  - **(a)** mark D-010 and D-013 **Accepted**, "resolved by D-053" or "resolved by D-048 +
    D-055", with the same approvers and dates as those decisions;
  - **(b)** mark them **Superseded by** those decisions, following the D-005 precedent;
  - **(c)** leave them unchanged and record the resolution only in the successors.
- Whichever option is chosen, the mismatch between the table and the entries is corrected in
  the same change.

| Teammate | Choice (a / b / c) | Date | Notes |
| --- | --- | --- | --- |
| Parv Patel | | | |
| Mandar Patil | | | |

### 1.6 Gate 1 summary

EXP-002 may run only when **both teammates** have approved D-053, D-007, D-049, D-031 (cost
basis and no cap), D-009, D-015, D-048, D-050, D-051, D-052, D-054, D-055, D-056, D-057, D-058
and D-059 (16 decisions), and those approvals are recorded as Accepted in the decision log.

- Both teammates have chosen the same option for G-T and G-P (§1.5). The bounded-loading
  code must be reviewed and committed by the team before the run. For G-T, option (b) also
  requires its further change to be completed and tested.
- D-023 is optional.
- Every row of §1.3 must be approved or acknowledged as provisional by both teammates.
- §1.4 lists decisions that are **not** needed for EXP-002.

EXP-002 will then use: lag 1; common window 126; train and validation only; the three
baselines; 15 bps on traded notional, funding charged; long-only with a 0.40 target cap and
cash at 0; and N = 252 only if D-023 is approved.

---

## Gate 2 — PPO design (later; nothing here applies to EXP-002)

Source: [`ppo_design_proposal.md`](ppo_design_proposal.md), **PROPOSED — NOT APPROVED**,
especially the §13 decision memo. Each line needs approval from both teammates.

| # | Decision | Proposed choice | Parv: decision, date | Mandar: decision, date |
| --- | --- | --- | --- | --- |
| 2.1 | Simulator step interface | `PortfolioState` + `step` inside the simulator; `simulate` refactored; ledgers byte-identical (regression tests) | | |
| 2.2 | Observation (D-012) | 51 inputs: 34 features + 9 one-hot regimes (frozen thresholds; raise on `unavailable`) + 8 end-of-row weights | | |
| 2.3 | Feature scaling | Standardise on training rows only, frozen artifact; clip to ±10, counts logged | | |
| 2.4 | Action and projection | `Box[−5, 5]^8` → softmax → cap 0.40 → excess to cash. Risky weights are never exactly 0 (minimum ≈ 6.5e-6). | | |
| 2.5 | Reward | Log net growth, **decision-aligned** (R1b); `terminated` at the split end | | |
| 2.6 | Decision frequency | Weekly (ISO-week first session); add a `weekly` schedule with tests | | |
| 2.7 | Library (D-014) | Stable-Baselines3 + PyTorch, CPU, optional extra `rl`, after a wheel check for Python 3.11–3.13 | | |
| 2.8 | CI | Core matrix unchanged; RL tests marked `rl` with `importorskip`; one extra CI job | | |
| 2.9 | Seeds and selection (D-016) | Seeds 42–46; median validation net Sharpe; tie-break lower learning rate → smaller `n_steps` → no entropy | | |
| 2.10 | Budget | 100,000 timesteps per run; 8 configurations (learning rate × `n_steps` {512, 1024} × entropy); final checkpoint; throughput smoke test first | | |
| 2.11 | Primary endpoint and statistics | Median over the 5 seeds of test net Sharpe (annualised only if D-023 is approved); joint time-block bootstrap; block length declared before the test | | |
| 2.12 | Explainability | Permutation sensitivity plus regime-conditional summaries; no SHAP | | |
| 2.13 | Governance | Resolve the authorship and commit-identity question before further commits | | |

A decision-ready matrix with options, consequences and recommendations is in
`ppo_design_proposal.md` §14.

**Unresolved Gate 2 points and their consequences** (checked 2026-10-18; none decided here):

| # | Point | Where it conflicts or is missing | Consequence if left open |
| --- | --- | --- | --- |
| 1 | Portfolio weights in the observation | Proposal §2 and `research_protocol.md` §8 say pre-trade or drifted weights; proposal §13 item 5 proposes end-of-row weights. They are identical for weekly decisions and differ only on execution rows. | Observation schema undefined, so no environment code |
| 2 | Reward alignment | Proposal §5 describes the execution-aligned R1; §13 recommends the decision-aligned R1b. Both partition growth exactly (verified). | Reward undefined, so no training |
| 3 | Terminal handling | Only in §13 (`terminated` at the split end) | Episode semantics undefined |
| 4 | Decision frequency | Protocol §8: "daily or weekly"; proposal: weekly. Weekly needs new `decision_rows` code and tests. | Calendar and episode length undefined |
| 5 | `n_steps` values | Proposal §8: {episode length, 2×}; §13: {512, 1024} | Tuning grid undefined |
| 6 | Timestep budget | 100,000 per run is proposed; throughput not yet measured | Compute plan unapproved |
| 7 | Seed aggregation and tie-break | Consistent in the proposal (§13) and protocol (§9–§10); still Proposed | Selection rule unapproved |
| 8 | Bootstrap block length | Not specified anywhere | Gate 3 cannot be pre-registered |
| 9 | Named stress windows | Not specified anywhere | Gate 3 cannot be pre-registered |
| 10 | D-017 RL output location | Open | No agreed artifact location |
| 11 | Optional RL dependencies and CI | Proposed only; wheels not checked | Dependencies cannot be added |
| 12 | Explainability scope | Proposed (permutation sensitivity plus regime summaries); SHAP excluded | Analysis plan unapproved |
| 13 | Authorship and commit identity | Unresolved since 2026-10-18 | Further commits are open to dispute |
| 14 | Proposal §11 checklist | Lacks points 2–4 and 11 | Approve from this table instead |

---

## Not decided by either gate

Walk-forward evaluation (D-018) and embargo (D-019) remain open, and walk-forward is not
implemented. Each optional extension needs its own approval:
- cost sensitivity;
- the regime-agnostic ablation;
- the differential-Sharpe reward R2;
- SHAP;
- a T-bill cash rate;
- the lag-0 sensitivity re-run under the new window.
