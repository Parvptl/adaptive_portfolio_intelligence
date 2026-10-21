# Approval Checklist — DRAFT — FOR TEAM REVIEW

> **Gate 1 CONFIRMED by both teammates on 2026-10-19** (§0.1, amendment A-1; identity
> self-declared, not technically verified) and recorded as Accepted in `decision_log.md`.
> **Gate 2 (PPO design) and Gate 3 (final test) are NOT approved.** The rest of this document
> keeps its original wording for the record.
> - Prepared 2026-10-18 and 2026-10-19. First committed in `8e52693` (pushed; GitHub
>   Actions CI run #8 passed). Later revisions: see `git log -- docs/approval_checklist.md`.
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
>   unresolved commit-identity question (project journal, 2026-10-18), see
>   "Identification" in §0.1: a commit from the shared device does not identify a person.

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

## 0. Gate 1 approval packet (summary; the fill-in fields are in §1)

**Status today (2026-10-19):** no Gate 1 item is approved.
- The only Accepted decisions EXP-002 relies on are the milestone-1 metric conventions:
  D-011, D-021, D-022 and D-024–D-030.
- Everything below is **Proposed** or **Open**, with no approver recorded.
- "Recommended" means a technical recommendation by the AI assistant, **not** an approval.

| Decision | What approving it means in practice | Recommended default (not approved) |
| --- | --- | --- |
| D-053 | EXP-002 compares exactly three untuned baselines | Approve |
| D-007 | Every net result pays 15 bps (10 + 5) on traded value | Approve (placeholder rates; disclosed) |
| D-049 | How the 15 bps is applied: non-cash traded notional, pre-cost value, pro rata, funding charged | Approve |
| D-031 | Same cost basis, and **no** turnover cap; the cap-measure question stays Open | Approve the basis and no cap |
| D-009 | Train 2007–16, validation 2017–19, test 2020–24, with the test split used once | Approve |
| D-015 | Long-only; 0.40 cap on target weights; daily rebalancing allowed; rf = 0; no turnover cap | Approve; disclose the rf = 0 limitation |
| D-048 + D-055 | Trade one session after the decision (lag 1), earn from the following session; lag 0 is a sensitivity case only | Approve both |
| D-050 + D-057 | Σw ≤ 1; invalid targets rejected; the cap binds at rebalancing only | Approve both |
| D-051 + D-056 + D-058 | Separate simulation per split from cash; common start of 126 sessions; test evaluated only with `--include-test` | Approve all three |
| D-052 + D-059 + D-054 | What is reported (gross and net, per-session; funding turnover separate) and where (`data/processed/backtests/<id>/`) | Approve all three |
| §1.3 data decisions | The results hold only for this dataset and these data choices | **Approve** the methods D-035, D-036, D-037, D-038, D-039. **Acknowledge as provisional** the values D-006, D-008, D-034, D-042, D-044, which are chosen for development and not validated. |
| G-T | Test-period return values are never parsed in the default run (committed `8e52693`; tested) | **(a)** accept the bounded loading. It enforces the strict rule (no test-period values parsed) through configured dates, not labels. |
| G-P | How the open questions D-010 and D-013 are closed | **(a)** mark them Accepted, "resolved by D-053" and "resolved by D-048 + D-055". They are questions answered by later decisions, not proposals replaced by them, which was the D-005 case. |
| D-023 (optional) | Annualised Sharpe, volatility, return and turnover appear in EXP-002 | **Approve N = 252**: the standard convention, and training years average 251.9 sessions. Model ranking does not depend on it while rf = 0. If approved, set `periods_per_year: 252` before the run; the output id becomes `c6d8c473258e3194` instead of `ce46d29217983c40`. |

**Dependencies and contradictions to avoid:**
- **D-015 and D-031** both contain "no turnover cap". Approve or reject them consistently.
- **D-007 ↔ D-049:** D-049 applies D-007's rate.
- **D-048 ↔ D-055:** D-055 revises D-048's default lag.
- **D-050 ↔ D-057:** D-057 defines what D-050's cap means.
- **D-058 depends on D-044:** 126 is D-044's longest window.
- **D-052 and D-059 depend on D-023:** D-059's annualised-turnover rule matters only if N is set.
- **The dataset id hashes** D-006, D-008, D-009, D-034–D-037 and D-042. Approving any of them
  *with changes* invalidates the snapshot. A rebuild or download needs separate authorisation.
- **Already true in the decision log:** D-010 and D-013 have an "Open" entry status versus
  "Proposed (see …)" in the summary table (G-P), and D-031's cap measure stays Open whatever is
  decided.

**What the team must hand back:** each teammate's own rows in §1, filled in a way that
identifies the person (their own commit or written confirmation). Then the assistant records
exactly those decisions in the decision log and runs EXP-002 per
[`exp002_runbook.md`](exp002_runbook.md).

### 0.0 Working approval rule R-S (adopted 2026-10-19; applies from now on)

**Rule (as communicated):** a task approval or decision communicated by either teammate is
treated as approved by **both** Parv Patel and Mandar Patil.
- No separate messages, GitHub comments, emails or individual confirmations from the other
  teammate are required.
- It applies to Gate 2, future project decisions and task authorisations, unless a teammate
  explicitly asks for an additional step.
- Approving a task authorises **only** that task's stated scope, never actions that are
  expressly prohibited.

**How it was adopted:** communicated in the Claude Code session on 2026-10-19 by a team member.
The messages do not name their author; identity is self-declared in a shared-device session.
The other teammate's separate confirmation was not sought, which is what the rule provides.
Recorded as D-061.

**How records made under R-S read:**
- they name the teammate who communicated the decision, as self-declared, or "a team member
  (not named)";
- they state that the other teammate's separate confirmation was not sought.

**History preserved:**
- Gate 1 was confirmed **before** R-S, under §0.1 and amendment A-1. Its record, including the
  disclosed deviation (both named confirmations arrived in one message), is unchanged.
- The §0.1 rules (independence, identification, A-1) remain the historical basis of Gate 1. For
  decisions after 2026-10-19 they are superseded by R-S.
- The alternative recommended during review, R1 (each teammate confirms from their own GitHub
  account), was not adopted.

### 0.1 Optional one-step confirmation of the recommended package

Instead of filling in §1 row by row, a teammate may confirm the whole recommended package in
§0 at once.
- The package is the "Recommended default" column above: the 16 required decisions, the §1.3
  approve / provisional split, G-T (a), G-P (a), and the D-023 choice below.
- It takes effect for EXP-002 **only when both teammates have confirmed it**, with the same
  D-023 choice and no conflicting amendments.
- Any amendment sends the affected items back to individual decisions in §1. Until resolved,
  they stay **Proposed** and EXP-002 does not run.
- A recommendation, an AI-generated summary, a commit or a passing CI run is **not** a
  confirmation. Leave these fields blank until the person concerned fills them in.
- **Independence:** each row is filled in only by the person named in it. Neither teammate
  confirms for the other, and one confirmation does not cover both rows.

**Identification must be bound to the person, not to this device.** On the shared
device the repository-local Git identity is `mavp309` for whoever types, and pushes
appear under the `Parvptl` GitHub account, so a commit made there does **not** identify
who confirmed. Use a channel tied to the individual, for example:
- a review or comment from the person's own GitHub account;
- a commit made from their own account on their own device under their own identity;
- a written confirmation the other teammate can verify (e.g. from the person's own email).

**Amendment A-1 to the identification rule — ADOPTED 2026-10-19 by both teammates (named
statements recorded below); not retroactive.** *(Originally proposed the same day.)*

*Purpose:* allow written confirmations in the team's Claude Code conversation as an agreed
channel, in place of separate GitHub comments or emails.

*Rule if adopted:* a confirmation in that conversation counts for a teammate's row when all of
the following hold:
1. it is a **separate message for each teammate**, naming its author (full name) in its text;
2. it states the decision: the whole §0 package, or the items with any amendments, plus the
   D-023 choice and the date;
3. it is recorded **verbatim** in this section, with the date received.

The record must state: *"author identity self-declared in a shared-device session; not
technically verified."* Every decision-log entry approved this way cites this section and
repeats that caveat.

*Adoption:* A-1 takes effect only when **both** teammates adopt it, each in their own named
message. That message may be combined with their confirmation of the package. Messages received
before adoption, including the unnamed confirmation recorded below, do not count
retroactively.

| Teammate | Adopts A-1 (yes / no) | Message recorded (date) |
| --- | --- | --- |
| Parv Patel | yes | 2026-10-19 (verbatim below) |
| Mandar Patil | yes | 2026-10-19 (verbatim below) |

| Teammate | Confirms the whole package in §0 (yes / no) | D-023: N = 252 or null | Amendments or exceptions (item: change) | How identified (channel tied to this person; see above) | Date |
| --- | --- | --- | --- | --- | --- |
| Parv Patel | yes | N = 252 | none | named written confirmation in the Claude Code session under A-1 (verbatim below); identity self-declared, not technically verified | 2026-10-19 |
| Mandar Patil | yes | N = 252 | none | named written confirmation in the Claude Code session under A-1 (verbatim below); identity self-declared, not technically verified | 2026-10-19 |

**Confirmations recorded verbatim (received 2026-10-19).** Both named statements arrived in
**one** conversation message, whereas A-1 condition 1 asks for a separate message per
teammate. They are two individually named, first-person statements with identical content.
This deviation is disclosed here and in the decision log rather than waived silently.

> I, Parv Patel, adopt amendment A-1 proposed in `docs/approval_checklist.md` §0.1. I confirm
> the entire recommended Gate 1 package in §0, including all 16 required decisions, approval of
> data methods D-035–D-039, provisional acknowledgment of D-006, D-008, D-034, D-042 and D-044,
> G-T option (a), G-P option (a), and D-023 with N = 252. Amendments: none. Date: 2026-10-19.
>
> I understand that my identity in this shared-device session is self-declared and has not been
> technically verified.

> I, Mandar Patil, adopt amendment A-1 proposed in `docs/approval_checklist.md` §0.1. I
> confirm the entire recommended Gate 1 package in §0, including all 16 required decisions,
> approval of data methods D-035–D-039, provisional acknowledgment of D-006, D-008, D-034,
> D-042 and D-044, G-T option (a), G-P option (a), and D-023 with N = 252. Amendments: none.
> Date: 2026-10-19.
>
> I understand that my identity in this shared-device session is self-declared and has not been
> technically verified.

The §1 row-by-row fields were not used: Gate 1 was confirmed as a package through this
section. G-T (a) is recorded as D-060.

**Reported, not yet recorded as approval (2026-10-19):**
- In a Claude Code session on the shared device, the session's user stated that Parv Patel and
  Mandar Patil reviewed the changes together. According to that statement, both agree with the
  whole recommended package, including G-T (a), G-P (a) and D-023 N = 252.
- This is a **single report from one session**. Under the rules above it does not yet identify
  each person, so both rows stay blank and nothing is marked Accepted.

**In-session confirmation received (2026-10-19), verbatim, author not named:**

> "I confirm that I have reviewed and approve the recommended Gate 1 decision package in
> `docs/approval_checklist.md` §0, including the required baseline and evaluation decisions, the
> provisional data acknowledgments, G-T option (a), G-P option (a), and D-023 with N = 252. I
> agree that EXP-002 should run on training and validation data only, with the final test period
> excluded. Date: 19/10/26."

It is not entered in either row, for two reasons:
- it does not say which teammate wrote it;
- it arrived through the shared-device session, which the rules above do not accept as
  identifying a person.

At most it is one confirmation; a second, separate one is still required.

**Text each teammate can post through their own channel** (e.g. a comment from their own GitHub
account, or an email the other can verify), then copy into their row above:

> I, <full name>, confirm the whole recommended Gate 1 package in docs/approval_checklist.md §0
> as reviewed on <date>: the 16 required decisions; approve D-035–D-039; acknowledge D-006,
> D-008, D-034, D-042, D-044 as provisional; G-T (a); G-P (a); D-023 N = 252. Amendments: none.

When both rows show a full confirmation with matching D-023 choices, the assistant may record in
`decision_log.md`:
- each covered decision as **Accepted**, approved by Parv Patel and Mandar Patil, with the
  dates given;
- the §1.3 values D-006, D-008, D-034, D-042 and D-044 keep their status **Proposed
  (provisional)**, because the decision log has no "acknowledged" status. Each gets a dated
  note: "acknowledged as provisional for EXP-002 by Parv Patel and Mandar Patil". They
  are not recorded as accepted or validated.
- D-010 and D-013 as resolved through G-P (a), with the summary-table and entry statuses made
  consistent.

The D-031 cap measure stays **Open**.

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

In the decision log, an acknowledged item keeps **Proposed (provisional)** with a dated
acknowledgment note. The log has no "acknowledged" status.

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
- **Fact (code, 2026-10-19; committed in `8e52693`, CI #8 passed):** the default backtest
  now loads bounded data.
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
Approval may be given row by row in §1 or, for the whole recommended package, through §0.1.
Either way, both teammates must each confirm, identifiably.

- Both teammates have chosen the same option for G-T and G-P (§1.5). The bounded-loading
  code is committed (`8e52693`), but choosing G-T (a) means the team accepts it as
  reviewed. For G-T, option (b) also requires its further change to be completed and
  tested.
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

### Gate 2 decision packet (prepared 2026-10-19) — ALL ITEMS PENDING

**Update (2026-10-19):**
- A team member put forward the recommended choices below as the **proposed defaults** for
  items 1–9, 12–15 and 17. They are recorded in the decision log as D-062 to D-069, status
  **Proposed**.
- Items 10 (bootstrap details) and 11 (stress windows) stay **open** until before Gate 3.
- Nothing here is approved. Under R-S (§0.0), a Gate 2 item becomes approved when a teammate
  communicates its approval.

Sources: `ppo_design_proposal.md` §13–§14 and the tables above.
- "Recommended" is a technical recommendation by the AI assistant, not an approval.
- No Gate 2 item is decided, and no PPO code, dependency or training exists.
- "Depends on" names what must exist, or be decided, before the item can be implemented.

| # | Item | Recommended (pending) | Alternatives | Consequences and risks | Depends on |
| --- | --- | --- | --- | --- | --- |
| 1 | Observation contents | 34 causal features + 9 one-hot regime labels (frozen thresholds) + 8 portfolio weights = 51 inputs; raise an error on the `unavailable` label | Drop the regime labels (only as an approved ablation with an equal budget) | Regime inputs reflect the "regime-aware" title; omitting them changes the research question | The bounded `load_feature_outputs` (exists; D-060); #14 for the weights |
| 2 | Weights shown to the agent | End-of-row ledger weights at decision row `d` | Pre-trade (drifted) weights | Identical for weekly decisions; differ only on execution rows, where pre-trade weights are ambiguous | #14 |
| 3 | Feature scaling | Standardise with the mean and std of training rows (`k0` to the last training decision); freeze in an artifact; clip to ±10 and count clipping | No scaling; robust scaling | Fitting on anything but training rows leaks information; clipping hides extremes unless it is counted | #15 for the artifact location |
| 4 | Action and projection | `Box[−5, 5]^8` → softmax → each asset ≤ 0.40 → excess to cash | Wider bounds; Dirichlet actions; redistribution instead of cash | Never exactly 0 weight (minimum ≈ 6.5e-6), so tiny residual trades occur; 25,006 synthetic actions all passed `validate_target` | `validate_target` (exists) |
| 5 | **Reward alignment** | **Unresolved.** Recommended: decision-aligned R1b, log growth over `(d_k, d_{k+1}]` including costs | Execution-aligned R1a, `(x_k, x_{k+1}]`; differential Sharpe R2 (optional) | Both R1 forms add up exactly to total log growth (verified numerically). R1a needs `L` rows after the next observation; R1b assigns one row per step to the previous holdings. **Must be fixed before any training.** | #14, `timing.py` (exists) |
| 6 | Episode termination | `terminated` at the split end after the last evaluable decision (`e − L − 1`) | Truncation with bootstrapped value | Bootstrapping past `e` values states with no evaluable future | `timing.last_evaluable_decision` (exists) |
| 7 | Decision frequency | Weekly (ISO-week first session), 496 training and 157 validation decision dates | Daily (2,392 / 754); monthly (114 / 36) | Daily risks cost-driven churn; monthly has too few samples; the baselines stay monthly or buy-and-hold, and that difference is reported | New `weekly` option in `decision_rows`, with tests |
| 8 | Seeds and selection | Seeds 42–46; select by the median validation net Sharpe; tie-break lower learning rate → smaller `n_steps` → no entropy bonus; report every seed | More seeds; mean instead of median | The ranking does not depend on N while rf = 0; never report only the best seed | #12 |
| 9 | Training budget | 100,000 timesteps per run; 8 configurations (learning rate {3e-4, 1e-4} × `n_steps` {512, 1024} × entropy {0, 0.01}) × 5 seeds = 4.0 million steps; final checkpoint | Larger or smaller budget; early stopping on validation | About 200 passes over one path risks over-fitting it; **throughput is unknown until a smoke test runs**; revise only before tuning | #12, then a smoke test |
| 10 | **Evaluation protocol (bootstrap)** | **Unresolved details.** Primary: test net Sharpe, median over seeds, at lag 1, 15 bps, N = 252. Statistics: stationary block bootstrap applied jointly to all series | Moving-block or circular bootstrap; data-driven block length (Politis–White) | **Must be fixed before Gate 3:** block length (recommended 21, with 63 as a sensitivity), number of resamples (e.g. 10,000), random seed, CI method (e.g. 95 % percentile) and the exact statistic (difference in annualised Sharpe against each baseline). Otherwise it can be tuned to the result. | D-023 (accepted); can be built with NumPy only |
| 11 | **Stress windows** | **Unresolved.** Name windows inside 2020–2024 by a pre-stated public rule, e.g. peak-to-trough of a broad index, with the dates taken from a cited public source | Fixed calendar windows; no stress test | **Deriving the dates from this project's own SPY data would read test-period prices, which D-060 forbids before Gate 3.** The dates must come from an external source, which needs authorisation for web research, or from the team with a citation. | Team decision, plus a source |
| 12 | Dependencies | Optional extra `rl`: stable-baselines3, torch (CPU), gymnasium, with version bounds chosen after a wheel check for Python 3.11–3.13 | Other RL libraries | Adds heavy dependencies; the core package must stay independent | **Authorisation to install**, and network access for the wheel check |
| 13 | CI | RL tests marked `rl` with `pytest.importorskip`; the core matrix is unchanged; one extra CI job (Ubuntu, Python 3.12, CPU) | Install `rl` in every CI job | Slower CI and more failure points if everything installs it | #12; the marker registered in `pyproject.toml` |
| 14 | Simulator step interface | `PortfolioState` + `step` inside `evaluation/simulator.py`; `simulate` reimplemented on top of it; regression tests show byte-identical ledgers | A separate environment accounting engine (not recommended) | A second engine could diverge from the accepted cost and timing conventions (D-048–D-059) | None (engineering only), but it touches accepted accounting, so it needs tests |
| 15 | Output location (D-017) | `data/processed/experiments/<id>/` (git-ignored), with configs, seeds, versions and hashes in metadata | `reports/results/` (not fully git-ignored) | Outputs could be committed by mistake | None |
| 16 | **Attribution and approval channel** | **Approval channel:** settled by R-S (§0.0, D-061). **Commit authorship: unresolved (D-070).** Facts: the repository-local identity is `mavp309 <mandar.avp@gmail.com>`; the global identity on the shared device is `Parvptl <pparv2515@gmail.com>`; pushes appear under the `Parvptl` GitHub account. Git configuration is unchanged; any change awaits a separate decision. | Keep the repo-local identity; remove it (commits would default to `Parvptl`); set an identity per commit | Commit metadata from the shared device cannot show who did the work; academic-integrity risk | Team decision; any Git configuration change needs separate confirmation |
| 17 | **Explainability** | Permutation sensitivity of the policy's actions to each observation feature, on validation decisions only, perturbing at decision row `d` so timing stays intact; plus regime-conditional allocation, risk and performance summaries using the frozen thresholds. **These indicate associations, not causation**, and may be unstable across seeds (report that). No SHAP. Proposed default (D-068). | SHAP or gradient attribution (new dependency, needs approval) | Overclaiming causation; instability across seeds | A trained policy (#8, #9) and the observation layout (#1); NumPy only |

**Explicitly unresolved, and needing a team decision before the related work:**
- **#5 reward alignment:** before any training.
- **#10 bootstrap details:** before Gate 3.
- **#11 stress-window rule and source:** before Gate 3.
- **#16 commit authorship (D-070):** before further commits are attributed. The approval
  channel is settled by R-S.
- **D-017 (#15), D-012 (#1), D-014 library (#12) and D-016 (#8):** still Open or Proposed in the
  decision log.

Under R-S, one teammate's communicated decision suffices. Record it here when it happens:

| Communicated by (as self-declared) | Gate 2 decision (approve all / approve with amendments) | Amendments | Date |
| --- | --- | --- | --- |
| A team member (not named in the message; shared-device session) | Approve the proposed defaults D-062 to D-069 as the working design for PPO implementation | None. Items 10 (bootstrap) and 11 (stress windows) stay open for Gate 3; D-070 (commit authorship) stays open. | 2026-10-19 |

Recorded under R-S (§0.0, D-061). The other teammate's separate confirmation was not sought.

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


---

## Pre-grid decision packet (2026-10-19), for review under R-S (§0.0, D-061)

These decisions are **Proposed**. None is marked Accepted until a team member communicates the
decision. Approving this packet would approve only what it lists.

| # | Decision | What approving it means | Where |
| --- | --- | --- | --- |
| 1 | **D-071** (M5.1 clarifications) | The scaler uses `ddof=0`; out-of-bound actions raise; the reward needs lag ≥ 1; train-only loading; `weekly` is a valid schedule value | `decision_log.md` D-071 |
| 2 | **D-073** (M5.2 environment choices) | Terminal observation at `e`; `float32` observations; observation bounds; deterministic reset; misuse raises; `info` fields | D-073 |
| 3 | **D-074** (wrapper settings not fixed by D-066) | The pinned SB3 2.9 defaults (`n_epochs` 10, `gamma` 0.99, `gae_lambda` 0.95, `clip_range` 0.2, `vf_coef` 0.5, `max_grad_norm` 0.5, `[64, 64]` tanh, `log_std_init` 0, …), one torch thread, the run layout and provenance, run kinds | D-074, `configs/agent.yaml` |
| 4 | **D-075** (pre-grid run safety) | Exclusive finalisation; `full` runs only from a clean committed tree; sequential execution with a 900 s timeout per run and stop-on-first-failure; manifest and resume; quarantine instead of deletion; the determinism settings | D-075 |

**Not in this packet:**
- **D-070** (commit authorship): stays Open until the team decides it explicitly.
  *Update (2026-10-19): decided after the commit and push — Parv Patel directed and reviewed
  the work committed as `71e6333`, `85c40d1`, `c387459` and `8da032a`; see `decision_log.md` D-070.*
- **The validation-selection metric and evaluation policy:** separate decision; validation data
  need separate authorisation.
- **Gate 3 items** (bootstrap settings, stress windows).
- **Approval to run the grid itself:** separate, and it requires committed code (D-075).

| Communicated by (as self-declared) | Decision (approve all / approve with amendments / reject) | Amendments | Date |
| --- | --- | --- | --- |
| A team member (not named in the message; shared-device session) | Approve D-071, D-073, D-074 and D-075 | None. The approval does not authorise a commit, push, repeat smoke run or full-grid training. D-070 stays Open until an explicit decision. | 2026-10-19 |

Recorded under R-S (§0.0, D-061). The other teammate's separate confirmation was not sought.


---

## Milestone B decision packet (2026-10-21), for review under R-S (§0.0, D-061)

These are two separate decisions. Neither is recorded until a team member communicates it.

| # | Item | What approving it means |
| --- | --- | --- |
| 1 | **D-076** (validation evaluation protocol) | The 12 protocol items in `decision_log.md` D-076. The new choices are: deterministic actions; tie tolerance 1e-9; stop on any undefined Sharpe; the allocation summary; no Sortino or Calmar; the clean-commit requirement; the output location. |
| 2 | **Authorisation to execute the validation evaluation** | Running `python scripts/evaluate_validation.py --execute --confirm-validation-evaluation` once, on a clean commit. This loads validation rows (2017–2019) and selects a configuration. It does **not** authorise any test-period access. |

**Also open (not in this packet):**
- Gate 3 items: bootstrap settings and stress windows.
- Whether the 100,352-timestep rollout overshoot of EXP-005 needs any record beyond the
  experiment log.
- Whether validation results may be shown in presentations, and how.

| Communicated by (as self-declared) | Item(s) | Decision (approve / approve with amendments / reject) | Amendments | Date |
| --- | --- | --- | --- | --- |
| A team member (not named in the message; shared-device session) | 1 (D-076) | Approve with amendments | Item 6 wording: "net maximum drawdown with its peak and trough dates, and gross maximum drawdown, both including the funding row". The approval also covered three evaluator implementation fixes, with no protocol change. | 2026-10-21 |

Recorded under R-S (§0.0, D-061). The other teammate's separate confirmation was not sought.
**Item 2 (authorisation to execute the validation evaluation) has not been given.**

*Update (2026-10-21, appended; the line above was true when written):* item 2 was then
authorised and executed.

| Communicated by (as self-declared) | Item(s) | Decision | Scope and conditions | Date |
| --- | --- | --- | --- | --- |
| A team member (not named in the message; shared-device session) | 2 (execute the validation evaluation) | Authorise | Run exactly `python scripts/evaluate_validation.py --execute --confirm-validation-evaluation --dataset-dir data/processed/8e00568ee2aa4de7` for evaluation `1ce9c490ed03c8c9`, protocol hash `e652adec1095c95a`, commit `0f8341b`, grid `0f1c47502dc30d84`. Validation (2017–2019) only. No test-period access, training, tuning or protocol change. | 2026-10-21 |

Recorded under R-S (§0.0, D-061). The other teammate's separate confirmation was not sought.

- **Executed** on 2026-10-21 as **EXP-006**, exit 0. All preconditions passed first. The result:
  **configuration 4** selected under D-076.
- **Outputs:** `data/processed/evaluations/1ce9c490ed03c8c9/` (git-ignored).
- **The test period (2020–2024) stays sealed.** No Gate 3 item has been decided.

---

## D-078 decision packet (2026-10-21), for review under R-S (§0.0, D-061): training-period checkpoint diagnostic

Three separate steps. None is recorded until a team member communicates it. The test period
stays sealed throughout.

| # | Item | What approving it means |
| --- | --- | --- |
| A1 | **D-078** (protocol, `docs/protocol_d078_training_modes.md`) | The window, checkpoints, deterministic and sampled inference, accounting, metrics, summaries, comparisons C1–C5, outputs and boundary checks. Either the proposed defaults for choices U1–U12, or stated amendments. Adopts D-077 item 1 only. |
| A2 | **Authorisation to implement** | Writing the code, configuration, tests and documentation listed in §12 of the protocol. No data rows are loaded. Commit only on an explicit instruction. |
| A3 | **Authorisation to execute** | One run of `python scripts/evaluate_training_modes.py --execute --confirm-training-diagnostic --dataset-dir data/processed/8e00568ee2aa4de7`. It names the diagnostic id, protocol hash and commit (known after A2), the grid `0f1c47502dc30d84` and the dataset. Training rows only (2007–2016): no validation or test rows, no training, no tuning. |

| Communicated by (as self-declared) | Item(s) | Decision | Amendments / scope | Date |
| --- | --- | --- | --- | --- |
| | | | | |

**Status (2026-10-21): A1, A2 and A3 have not been given.**

---

## Gate 3 pre-registration packet (draft 2026-10-21), for review under R-S (§0.0, D-061): ALL ITEMS OPEN

**Status and scope:**
- Nothing in this packet is approved. The "proposed default" column holds technical proposals
  by the AI assistant. It is not a team decision.
- No test row or metric was used to draft it.
- The items extend the open Gate 2 items 10 (bootstrap) and 11 (stress windows) above.
- Planning context: `roadmap.md`, Phase D (D3–D5).

**Candidate as of 2026-10-21 (G3-1):** configuration 4, selected by D-066/D-076 in EXP-006. It
trailed all three baselines on validation net Sharpe. Checkpoint hashes (from evaluation
`1ce9c490ed03c8c9` `metadata.json`, re-verified 2026-10-21):

| Seed | Run id | `model.zip` SHA-256 |
| --- | --- | --- |
| 42 | `c12145d46246e1c7` | `1d335d10c6867d05d151cd26a934b4f7728b4fd30fea701f8155505077b75b24` |
| 43 | `4f9be9680a6334bd` | `2c65fccbe87eaf983ea500dabb3dd84cf91fbadc0e81fc3edeec1d2c4051a636` |
| 44 | `e9819a04ccc36567` | `9745e59e47deaa56e7e2572e3b1e7e4d2c5264c9106d3fe11b03efbadbfaf046` |
| 45 | `9f585486f8b4ce4b` | `88bf40ed8af7b9912415ca5a2bd631a4a76fc12a3808f242480883878419f87f` |
| 46 | `8d929082251f7c7f` | `c0e9e0935b9759010bee14670d4b5c5dd71f5368ccaebd90ac1ce155c78917ce` |

| # | Item | Status | Proposed default (proposal only) | Alternatives / notes |
| --- | --- | --- | --- | --- |
| G3-1 | Candidate and checkpoints | OPEN | Freeze the 5 configuration-4 checkpoints above. Evaluate no other configuration on test | Wait for a D-077 follow-up candidate, which must be produced and frozen **before** unsealing. Evaluating all 40 on test, labelled exploratory, increases multiplicity |
| G3-2 | Primary endpoint | OPEN | Median over seeds 42–46 of test annualised net Sharpe, under the D-076 definitions: √252·mean/std (ddof 1), rf 0, funding row excluded, lag 1, 15 bps, start in cash, mark to market at the last test row, deterministic actions, frozen training scaler | Mean over seeds; per-seed only. Source: Gate 2 item 10 recommendation (not accepted) |
| G3-3 | Secondary metrics | OPEN | Every seed and baseline: net and gross cumulative return; net CAGR and volatility; net max drawdown with dates; gross max drawdown; cost drag; funding cost; annualised recurring ETF traded notional (funding and cash leg excluded); two-way turnover; regime-conditional metrics with the frozen thresholds | Gross Sharpe (defined in D-078 §6). **Sortino:** listed in `CLAUDE.md` but [O] in the README and not implemented; it needs a definition (downside deviation, target 0) and implementation authorisation. **D-045 (regime taxonomy) is Proposed**: accept it or label the regime metrics provisional |
| G3-4 | Baselines and accounting | OPEN | The three D-053 baselines, computed **in the same single test run** on the common test window (`split_window("test")`, D-051/D-058), with identical costs, lag and valuation | A separate `--include-test` backtest (D-056), which would be a second test access |
| G3-5 | Uncertainty | OPEN | Stationary block bootstrap (Politis and Romano, 1994), applied jointly to the aligned daily net returns of the 5 seeds and 3 baselines (the same resampled indices): expected block length 21 sessions (63 as a declared sensitivity); B = 10,000; a fixed recorded seed; 95% percentile intervals. Statistic: Δⱼ = median over seeds of the Sharpe − baseline j's Sharpe, per resample | Moving-block or circular bootstrap; Politis–White block length. **Limitation:** it resamples realised returns and does not re-run the policy. **Scope:** bootstrap CIs are [O] in the README and milestone 8, so making them required is a team decision. Not implemented (NumPy only) |
| G3-6 | Stress windows | OPEN | Rule: S&P 500 price-index peak-to-trough declines of ≥ 20% (closing basis) inside 2020–2024, with dates **taken from a cited public source**. The candidate windows in `ppo_design_proposal.md` are unverified until sourced. Descriptive metrics per window, no inference | No stress windows; they are [F]. **The dates must not come from this project's test data (D-060).** Sourcing needs a team citation or authorised web research |
| G3-7 | Multiple comparisons and selection bias | OPEN | Report all three Δⱼ. Judge them with Holm's step-down adjustment at a familywise 5%. Report every seed. Note that configuration 4 was selected from 8 on validation: its validation figures are optimistic, and the test estimate is the fair one for this fixed candidate | A single pre-specified primary baseline (e.g. equal weight monthly) with no adjustment; Bonferroni intervals |
| G3-8 | Hypotheses and success criteria | OPEN | For each baseline j: H₀ Δⱼ ≤ 0 vs H₁ Δⱼ > 0. "Evidence of higher test net Sharpe than j" only if j's Holm-adjusted bound excludes 0 on the positive side; otherwise "no evidence", which is **not** "equal". Lower values are reported the same way. Results are published whatever the outcome; underperformance is plausible given EXP-006 | Descriptive-only reporting without a success criterion |
| G3-9 | Outputs and verification | OPEN | Output folder `data/processed/test_evaluations/<id>/` (git-ignored, never overwritten): ledgers, per-seed and baseline metrics, bootstrap draws summary, stress and regime tables, metadata (identity, protocol hash, clean commit, checkpoint hashes, data ids, pre-registration SHA-256, file hashes). An independent verification (metrics recomputed from ledgers, bootstrap reproduced from its seed, hashes) passes **before** results are discussed. A second team member reviews | Other output location |
| G3-10 | Single-run rule and failures | OPEN | One run (`research_protocol.md` §13). The evaluator refuses if any test output exists. A **technical** failure before outputs are written may be fixed and rerun with the same protocol hash. The fix and rerun are recorded; no protocol choice may change | Any rerun requires a new authorisation |
| G3-11 | Pre-registration document | OPEN | One document collecting the G3-1 to G3-10 decisions. It is committed before the G3-13 authorisation, and its SHA-256 is recorded in the test identity | — |
| G3-12 | Reporting policy | OPEN | Show the validation (EXP-006) and test results with their labels; never present configuration 4 as a successful strategy unless the pre-registered criteria are met; no financial advice | — |
| G3-13 | **Unsealing and execution authorisation** | OPEN, not given | An explicit message naming the evaluation id, protocol hash, commit, the 5 checkpoint hashes, dataset `8e00568ee2aa4de7`, the pre-registration hash and the exact command. Recorded under R-S with its attribution limits. One run | — |

**Also needed before Gate 3:**
- **Test evaluator (Phase D4):** separate from D-076. Implementation needs its own
  authorisation, then review and commit (D-076 hash regression-tested).
- **Old local test-result folder:** `data/processed/backtests/ac2d6b163d4f5e4b/`
  (pipeline v1, `research_protocol.md` §12). It must stay unopened and unreported. Whether to
  quarantine or delete it is a team decision; deletion is irreversible.
- **D-018 (walk-forward) and D-019 (embargo):** still Open. Schedule them or record them as
  not done.

| Communicated by (as self-declared) | Item(s) | Decision | Amendments / scope | Date |
| --- | --- | --- | --- | --- |
| | | | | |

**Status (2026-10-21): no Gate 3 item has been decided. The test period stays sealed.**

### Gate 3 packet addendum (2026-10-21, dependency review; appended, the packet above is kept)

**Labels and corrections:**
- Every entry in the "Proposed default" column of G3-1 to G3-13 is **PROPOSED**, not approved.
  Every item stays **OPEN** until a team member communicates a decision under R-S.
- **No accepted record establishes a primary test endpoint.** D-066 accepted seeds, validation
  selection and the budget only. D-076 covers validation only. The test endpoint in G3-2 is a
  recommendation (Gate 2 item 10, open).
- **G3-5 is made precise (PROPOSED):**
  - the seed is 42, the project default in `experiment.yaml`;
  - the statistic per resample b is Δⱼ⁽ᵇ⁾ = median over seeds 42–46 of SR(rₛ⁽ᵇ⁾) − SR(rⱼ⁽ᵇ⁾);
  - SR = √252 · mean / std (ddof 1), rf 0, on aligned daily net returns with the funding row
    excluded, resampled with one shared index draw per b;
  - 95% percentile intervals.
- **G3-8 is made quantitative (PROPOSED):**
  - two-sided bootstrap p-values pⱼ = min(1, 2 · min(#{Δⱼ⁽ᵇ⁾ ≤ 0}, #{Δⱼ⁽ᵇ⁾ ≥ 0}) + 1) / (B + 1)
    for the 3 baselines, with Holm at a familywise α = 0.05;
  - the outcome for each baseline is "higher" (rejected, Δ̂ⱼ > 0), "lower" (rejected,
    Δ̂ⱼ < 0) or **"inconclusive"** (not rejected). Inconclusive is not "equal".
  - **OPEN:** whether a minimum practically relevant difference (e.g. ΔSR ≥ 0.2) is also
    required.
- **G3-11 and G3-13 circularity (correction):**
  - the pre-registration document cannot contain the hash of the commit that contains it;
  - the document fixes the decisions and the test configuration hash;
  - the unsealing authorisation names the evaluator commit;
  - the run identity records the commit, the protocol hash and the document's SHA-256 (G3-22).

**Additional items (all OPEN; defaults PROPOSED):**

| # | Item | Status | Proposed default | Alternatives / notes |
| --- | --- | --- | --- | --- |
| G3-14 | Regime analysis and frozen taxonomy | OPEN | Include regime-conditional metrics with the **same** `regime_thresholds.json` that the checkpoints were trained with (hash recorded), applied unchanged to 2020–2024. Accept or acknowledge D-045 as provisional first. Report sparse regimes as sparse | Exclude regime metrics. This would leave the abstract's market-condition study only to explainability and stress windows |
| G3-15 | Walk-forward (D-018) | OPEN | Record D-018 as **not feasible within the remaining scope**, with the reason: it needs retraining per fold and further use of 2017–2019. State this as a limitation | Schedule expanding folds inside 2007–2019 after the freeze, as a robustness study of the training procedure that cannot change the candidate (needs training authorisation) |
| G3-16 | Embargo (D-019) | OPEN | Close D-019: no embargo, because rewards are one-step and decision-aligned (D-064) and boundary-crossing pairs are excluded (D-043, which is itself Proposed) | Specify a gap in sessions |
| G3-17 | Explainability deliverables and boundaries | OPEN | Per D-068, on validation decisions of the frozen checkpoints only: permutation sensitivity by feature group (the groups, permutation count, seeds and sensitivity measure fixed in a protocol decision), plus regime-conditional allocation and risk summaries. Results recorded before unsealing. Test-period regime summaries only from the single test run | Run after S8, disclosed as possibly influenced by test results |
| G3-18 | Frozen artifacts | OPEN | Record before unsealing: the dataset id `8e00568ee2aa4de7`; the feature set id; the hashes of `scaler.json` and the regime thresholds; the hashes of every configuration used; the 5 checkpoint hashes (G3-1) | — |
| G3-19 | Evaluator identity | OPEN | A separate test evaluator with its own `protocol_version` and hash, a clean commit, and a regression test showing that D-076's hash `e652adec1095c95a` is unchanged | — |
| G3-20 | Sortino | OPEN | **Exclude**, consistent with D-076 (accepted). Record the `CLAUDE.md` deviation as a known limitation | Include as a secondary metric with a definition (downside deviation of daily net returns below 0, ddof 1, √252) and implementation authorisation |
| G3-21 | Reporting of underperformance and inconclusive results | OPEN | Report every pre-registered result, every seed and baseline, and the "lower" and "inconclusive" outcomes in the abstract and conclusions. No post-hoc subgroups or new metrics are presented as findings; any later analysis is labelled exploratory (`research_protocol.md` §13) | — |
| G3-22 | Pre-registration amendments and freeze | OPEN | Amendments are allowed only before S6, only for implementation reasons, with no test data seen, each dated and recorded. After S6 nothing changes. The run identity records the document's SHA-256 | — |

**Dependencies:** see `roadmap.md`, "Phase D revision (2026-10-21, dependency review)", stages
S0–S9.

**Status (2026-10-21): no item G3-1 to G3-22 is decided. The test period stays sealed.**

---

## Gate 3 decision sheet (2026-10-21, Milestone D readiness audit): the approvals needed before any test access

**Readiness result (2026-10-21): NOT READY. The test period was not loaded.**
- Configuration 4 is verified: seeds 42–46, the five checkpoint hashes in the packet above,
  trained on training data only at clean commit `cc9784b`, selected by D-066/D-076 in EXP-006.
- **Missing:**
  - every Gate 3 decision (G3-1 to G3-22);
  - the test evaluator (not implemented);
  - a clean committed tree (11 documentation files uncommitted);
  - the unsealing authorisation.

**New items requested for Milestone D (OPEN; defaults PROPOSED).** All are descriptive and
computed inside the same single test run. They carry no inference and do not change the
primary endpoint.

| # | Item | Proposed default | Notes |
| --- | --- | --- | --- |
| G3-23 | Cost sensitivity | Re-run the policies and baselines at 0 bps (gross reference) and 30 bps (2× the provisional 15 bps) | The policy path changes with costs because weights enter the observation, so each setting is a full re-run. Milestone 7 lists cost sweeps as [O] |
| G3-24 | Execution-lag sensitivity | Lag 2 for the policies and baselines | **Lag 0 is impossible for PPO:** the environment requires lag ≥ 1 (D-071). Lag 0 (D-055's idealised case) applies to the baselines only, or is omitted |
| G3-25 | Constraint sensitivity | **None for PPO** (a different cap is outside the training distribution); baselines at caps 0.30 and 1.00, descriptive | Alternatively include PPO at other caps, labelled out-of-distribution |
| G3-26 | Allocation concentration | Per strategy: mean and maximum Herfindahl index of end-of-row ETF weights; effective number of positions (1/HHI); mean cash; share of executions with an ETF at the cap; maximum held weight | Descriptive |
| G3-27 | Regime subsample rule (extends G3-14) | Report session counts for every regime. Metrics only for regimes with ≥ 63 test sessions, with no per-regime inference. Fewer sessions are reported as "too few to summarise" | Small subsamples. The training-relative volatility thresholds may label most of 2020–2024 differently from training |

**The smallest approval path:**

1. **Message 1, decisions and implementation:**
   - accept or amend G3-1 to G3-27, D-045, D-018, D-019 (and D-043) and the explainability
     protocol stance (G3-17);
   - decide whether D-077/EXP-007 happen before the freeze;
   - authorise implementing the separate test evaluator and risk-analysis code (Gate 3b), tested
     on synthetic data only;
   - authorise committing the current docs, with the stated authorship (D-070).
2. Implementation, review and a **commit instruction** (Gate 3c). The pre-registration
   document is then frozen (G3-22, S6).
3. **Message 2, unsealing (Gate 3d, G3-13):**
   - an explicit authorisation naming the evaluator commit, protocol hash, test evaluation id,
     dataset `8e00568ee2aa4de7`, the five checkpoint hashes, the pre-registration SHA-256 and
     the exact command;
   - this cannot be given now, because those identifiers do not exist yet.

| Communicated by (as self-declared) | Item(s) | Decision | Amendments / scope | Date |
| --- | --- | --- | --- | --- |
| | | | | |

**Status (2026-10-21): no item G3-1 to G3-27 is decided; no Gate 3 approval is given. The test
period stays sealed.**

---

## Milestones D-F completion request (2026-10-21): what was and was not authorised

**Recorded facts (from the in-session message; its author is not named; R-S):**
- The message asked to complete milestones D, E and F "using … the explicit decision packet
  supplied with this task".
- **No decision packet was attached.** No Gate 3 item (G3-1 to G3-27) can therefore be recorded
  as accepted, and none is.
- The message said the PPO validation explainability may run "only if the explicit
  validation-access authorization is included in this task". **No such authorisation was
  included**, so it was not run.
- The message instructed the implementation of a separate test evaluator (Gate 3b) and required
  a stop before test access.
  - The evaluator was implemented against the **DRAFT** pre-registration
    `configs/preregistration.yaml` (SHA-256 `6a7d5b713271ee1e3c4211e6ec9927f7dd8ba78fef7b91183603a7443e873fe6`; every item OPEN) and tested on
    synthetic data only.
  - **Gate 3c** (review and commit instruction, with authorship per D-070) has not been given.
  - **Gate 3d** (unsealing) has not been given.

**What freezing requires (no shortcut):**
1. Each team decision on G3-1 to G3-27 recorded (the decision log, this checklist).
2. Each item in `configs/preregistration.yaml` set to `decision: ACCEPTED` with a `record`;
   stress-window dates added from a cited public source; `status: frozen`.
3. A commit of the code and the frozen file (a commit instruction and authorship).
4. `python scripts/evaluate_test.py --plan --dataset-dir data/processed/8e00568ee2aa4de7`,
   which prints the frozen pre-registration SHA-256, the protocol hash and the evaluation id.
5. An explicit unsealing authorisation naming:
   - the evaluator commit, the protocol hash, the pre-registration SHA-256 and the evaluation
     id;
   - dataset `8e00568ee2aa4de7`;
   - the five checkpoint SHA-256 values;
   - the command:

     `python scripts/evaluate_test.py --execute --confirm-test-unsealing --preregistration-sha256 <sha256> --expected-commit <commit> --dataset-dir data/processed/8e00568ee2aa4de7`

| Communicated by (as self-declared) | Item(s) | Decision | Scope | Date |
| --- | --- | --- | --- | --- |
| A team member (not named in the message; shared-device session) | Gate 3b (implement the test evaluator) | Instructed | Implementation only, on a draft pre-registration, with synthetic tests. No Gate 3a decision; no test access | 2026-10-21 |

**Status (2026-10-21): no Gate 3 item is decided. The pre-registration is a DRAFT. The test
period stays sealed.**

---

## Gate 3 decision record (D-083), recorded 2026-10-22

| Communicated by (as self-declared) | Item(s) | Decision | Scope | Date |
| --- | --- | --- | --- | --- |
| A team member (not named in the message; shared-device session) | Gate 3 packet | Approved in principle | Subject to evidence checks and execution gates; no test access | 2026-10-21 |
| A team member (not named in the message; shared-device session) | Decisions 1–6 | Lag 2 omitted; baseline caps omitted; D-045 accepted conditionally (exposure recorded); web research for stress sources authorised; equal-weight comparisons as point differences; record id D-083 | No test access, execution or commit | 2026-10-21 |
| A team member (not named in the message; shared-device session) | Implementation | Authorised ("Master Execution Instruction") | Code, tests and documents; synthetic verification only. No test access, real evaluator run, training, explainability execution, freeze or commit | 2026-10-22 |

Recorded under R-S (§0.0, D-061). The other teammate's separate confirmation was not sought.
Item statuses, with six columns per item, are in D-083 (`docs/decision_log.md`).

**Pre-registration (2026-10-22):** **DRAFT**.
- SHA-256 `c9df7be179341025e323cf0b0f1555524f93975a9dbca70910963f479ca76000`; protocol hash `f45b8b35e16d2d3c`.
- 16 of 18 items ACCEPTED.
- OPEN: `uncertainty` (independent human review) and `stress_windows` (dataset calendar
  checkable only at run time).

**Still required before any test access, in order:**
1. Independent human review of the moving-block bootstrap (G3-5).
2. A decision on how G3-6 is verified (the run-time calendar check, or excluding the windows).
3. Gate 3c: team review of the evaluator and a commit instruction with authorship (D-070).
4. Freeze: `status: frozen`, every item ACCEPTED, committed.
5. A fresh `python scripts/evaluate_test.py --plan --dataset-dir data/processed/8e00568ee2aa4de7`.
6. A **separate unsealing authorisation** naming the commit, the protocol hash, the
   pre-registration hash, the evaluation id, the dataset id, the checkpoint hashes and the
   exact command.

**Status (2026-10-22): no item is authorised for execution. The test period stays sealed.**
