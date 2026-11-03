# Autonomous Execution Policy (D-084)

> **Status:** adopted 2026-11-03 under rule R-S (D-061).
> - **Basis:** an in-session instruction from a team member titled "Master Repository
>   Governance and Automation Prompt: One-Time Research Execution Authorisation". The message
>   does not name its author; identity is self-declared in a shared-device session. The other
>   teammate's separate confirmation was not sought, which is what R-S provides.
> - **What it is:** a standing, repository-specific authority for the remaining research work
>   listed in §3–§5. It replaces the per-step "ask the user" approvals for routine work.
> - **What it is not:**
>   - It does not record any independent review. None has occurred.
>   - It does not approve any provisional value (costs, cap, universe, dates) as validated.
>   - It does not authorise commits or pushes (§9).
> - **Precedence:** where this document conflicts with an older per-step approval rule in
>   `CLAUDE.md`, `approval_checklist.md`, `roadmap.md` or `research_protocol.md`, this document
>   governs for the work it covers. The **non-negotiable safeguards** in `CLAUDE.md` and §8 here
>   always govern.
> - **For a fresh Claude Code session:** read this file, then `CLAUDE.md`, then the latest
>   entries of `docs/project_journal.md` and D-084 to D-086 in `docs/decision_log.md`. That is
>   enough to continue without the conversation history.

---

## 1. Standing implementation authority

Claude Code may, without asking for each step:
- inspect and modify research code in `src/adaptive_portfolio/`, `scripts/` and `configs/`,
  within the scope of §3 and §4;
- add and update tests (offline, synthetic data; `@pytest.mark.network` for network tests);
- create experiment configurations needed by §4;
- implement the profile-conditioned PPO extension exactly as fixed in §3;
- update every document in the `CLAUDE.md` maintenance table, and prepare the final report;
- run offline tests, linting, formatting and configuration validation;
- diagnose and repair failures (§6);
- make routine engineering decisions: names, file layout, refactors that preserve behaviour,
  logging, progress output, retry wrappers and computational settings (threads, device);
- generate tables and figures from verified saved outputs only.

**Recording:** every non-trivial choice goes in `docs/project_journal.md`. A choice that a
reader could reasonably question goes in `docs/decision_log.md` (§5).

**Not covered:** unrelated repository functionality; dependencies beyond what the work needs
(still with version bounds in `pyproject.toml`); removing or weakening any guard listed in §8.

---

## 2. Decision categories

| Category | Examples | What Claude does |
| --- | --- | --- |
| **Routine engineering** | Function layout, test structure, threads, file names | Decide; note in the journal |
| **Routine methodological implementation** | Where the profile goes in the observation vector; the RNG stream used to sample it; output file schema | Decide the simplest option consistent with §3; note in the journal; add to D-086 if a reader could question it |
| **Unresolved scientific choice needed for execution** | Profile sampling distribution, held-out region, ablation form | Inspect the evidence; pick the simplest defensible option; record it in the decision log as **Provisional (delegated)**; continue |
| **Change to the research question, scope or a guard in §8** | A new reward, new data, new constraints, test-based tuning | **Not delegated.** Stop that item, complete everything else, and report it |

A **Provisional (delegated)** decision (status added to the decision-log vocabulary on
2026-11-03) is a choice made by Claude Code under this policy. It is **never** described as
approved, accepted or reviewed by the research team.

---

## 3. Methodology boundaries: the first profile-conditioned experiment (D-085)

**Fixed by the 2026-11-03 instruction (not changeable under this policy):**
- **Profile:** a five-dimensional continuous investor profile, each value in [0, 1]. In order:
  1. `risk_tolerance`;
  2. `risk_capacity`;
  3. `investment_horizon`;
  4. `liquidity_preference`;
  5. `growth_preference`.
- **Sampling:** continuous; sampled **once per episode** at `reset`; constant for the whole
  episode.
- **Observation:** the profile is concatenated to the existing 51-number observation (D-062),
  giving 56 inputs.
- **Everything else unchanged:**
  - the PPO architecture, apart from the input dimension;
  - the D-064 reward (log growth after costs), **exactly**;
  - the D-063/D-072 action space;
  - the simulator accounting (D-049, D-050, D-055, D-057, D-059);
  - the transaction-cost model;
  - the D-044 market features and the D-045 regimes;
  - the D-009 splits.

**Scientific concern, recorded and not resolved by this policy:**
- The reward, costs and constraints do **not** depend on the profile. The profile therefore
  carries no information about the reward. The optimal policy of this MDP is the same for
  every profile.
- Any profile dependence that PPO learns is, in expectation, noise or an optimisation
  artefact.
- **Consequence:** the experiment as specified can test whether PPO is robust to an extra,
  task-irrelevant input. It **cannot** test personalisation or investor suitability.
- **What would make the profile meaningful:** a profile-dependent reward, constraint or cost.
  The instruction fixes the reward, so this needs a new team decision (§2, last row). Until
  then, results must be reported with this limitation.

The provisional protocol details (sampling distribution, held-out region, ablation, seeds,
budget, evaluation profiles) are in `docs/research_protocol.md` §15 and in D-086.

---

## 4. Execution authority

**Authorised without further approval:**

| # | Workflow step | Data | Notes |
| --- | --- | --- | --- |
| 1 | Existing PPO baseline verification | Train, validation | Reproduce or verify EXP-005/EXP-006 artifacts (hashes; `--verify` modes; deterministic re-evaluation). **No new selection.** The configuration-4 selection (D-066/D-076) stands |
| 2 | Profile-conditioned PPO training | Train only | `run_kind: full` needs a clean **committed** tree (D-075). See §9 |
| 3 | Profile-conditioning ablation | Train, validation | As in `research_protocol.md` §15.5 |
| 4 | Unseen-profile generalisation | Train, validation | As in §15.6 |
| 5 | Training- and validation-period evaluation | Train, validation | D-076 metric definitions; deterministic actions |
| 6 | Profile sensitivity analysis | Validation decisions | Allocation change across profiles; associations, not causation (D-068) |
| 7 | Portfolio allocation analysis | Train, validation | Weights, cash, cap usage, concentration |
| 8 | Risk and performance comparison | Train, validation | Against the D-053 baselines under identical data, costs, timing and constraints |
| 9 | Reproducibility checks | — | Hash and recompute saved outputs |
| 10 | Documentation of actual results | — | Experiment log, journal, report |

**Execution rules:**
- **Prespecify, then run.** Seeds, budgets, evaluation profiles and metrics are written in
  `research_protocol.md` §15 **before** any validation look.
- **No iterating on validation results.** If a validation result prompts a change, the change
  is a new, labelled exploratory experiment with its own entry. It never silently replaces the
  original.
- **Allowed operations:**
  - resuming interrupted runs through the existing manifest and resume mechanism (D-075);
  - retrying a run that failed for environmental reasons;
  - using any CPU or GPU, provided the device is recorded (results may differ by device).
- **Record every run, including failed ones,** in `docs/experiment_log.md` with its id,
  command, seed, configuration, code commit and output hashes.
- **Not covered by this list:** D-077 items 2–5, D-078/EXP-007, D-081 (regime-input ablation)
  and the PPO validation explainability of configuration 4 (`explainability_validation_plan.md`).
  They stay **Proposed**. A later instruction can add them.
  - The PPO explainability is a **[R]** abstract item, so it is a completion criterion (§10).

---

## 5. Decision recording

- **Routine:** a dated bullet in the day's journal entry.
- **Provisional (delegated):**
  - a decision-log entry or a row in D-086 with context, the options considered, the choice,
    the rationale, and the status **Provisional (delegated)**;
  - the matching config or document change in the same task.
- **Never:**
  - mark anything **Accepted** on the team's behalf, except an authorisation that a team
    member actually communicated, recorded under R-S with the standard wording;
  - edit an earlier decision's text. Changes are new entries or appended notes; superseded
    entries are kept.

---

## 6. Failure handling

**Implementation and tests:**
1. Inspect the failure and find the root cause.
2. Make the smallest correction.
3. Add a regression test.
4. Re-run the affected checks, then the full suite.
5. Continue the workflow.

**Training:**
1. Classify the failure: environmental (timeout, memory, interrupted process), configuration,
   or methodological.
2. Environmental: resume through the grid manifest. Keep valid finalised runs. Quarantine stale
   state (D-075); never delete it.
3. Configuration: fix the configuration, record why, and re-run. The earlier attempt stays in
   the experiment log.
4. Methodological (for example, the method cannot be trained as specified): **do not** change
   the reward, data, constraints or costs to obtain a run. Record the failure as a result.

**Evaluation:**
- Before reporting, check the configuration hash, the data period boundaries, the checkpoint
  hashes, the metric definitions and reproducibility (`--verify`).
- Keep the complete evaluation record, including failed evaluations.

**Blocked work** (hardware, dependency, credential or data): finish everything possible on
synthetic data, then report the exact blocker and the command that resumes it.

---

## 7. Test access: the one-time final evaluation

**What is authorised (Gate 3d, G3-13):**
- **One** execution of `scripts/evaluate_test.py --execute` on the frozen pre-registration.
- It may run **only when every condition below is true**, checked and written in the journal
  immediately before execution:

  1. **Order:** every training and validation step authorised in §4 is complete and recorded
     in `docs/experiment_log.md`. No further training or validation look is planned for any
     candidate in the test.
  2. **Candidate:** the configuration selected by the accepted validation rule (D-066/D-076),
     **configuration 4, seeds 42–46**, with the `model.zip` SHA-256 values in
     `configs/preregistration.yaml`.
     - The profile-conditioned policy is **not** a test arm in this protocol (D-086,
       provisional).
     - Adding it would need a pre-registered selection rule and items, written before the
       freeze.
  3. **Frozen protocol:** `configs/preregistration.yaml` has `status: frozen`, every item
     `ACCEPTED` with a truthful `record`, and is committed. See the open items in §7.1.
  4. **Human review:** the moving-block bootstrap (G3-5) and the evaluator (Gate 3c) have
     **actually** been reviewed by a person, recorded with name (as self-declared) and date.
     Alternatively, a team member has explicitly waived that review in writing, and the waiver
     is disclosed in every test report. **Claude Code cannot provide this.**
  5. **Commit:** the evaluator and frozen file are committed. The working tree is clean, and
     HEAD is the full 40-character commit passed as `--expected-commit`. The commit itself
     needs explicit permission (§9).
  6. **Fresh plan:** `python scripts/evaluate_test.py --plan --dataset-dir
     data/processed/8e00568ee2aa4de7` was run on that commit. Its pre-registration SHA-256,
     protocol hash and evaluation id are written in the journal.
  7. **Data:** dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`, with integrity
     checks passing (`workflow verify`).
  8. **No prior run:** no test evaluation exists for this pre-registration, and no earlier
     test result has been seen.

**The command** (values from step 6):

```text
python scripts/evaluate_test.py --execute --confirm-test-unsealing \
  --preregistration-sha256 <sha256 from --plan> --expected-commit <40-char HEAD> \
  --dataset-dir data/processed/8e00568ee2aa4de7
```

Then `python scripts/evaluate_test.py --verify <output dir>` **before** any result is
discussed.

**Restrictions that stay (enforced in code where marked):**
- **Candidate:** the evaluator cannot change the frozen candidate. Model hashes are checked at
  plan and execute time *(code)*.
- **No tuning:** test results are never used to tune, select, retrain or re-specify anything.
  Any analysis after the test is labelled exploratory.
- **Once only:**
  - one run per frozen pre-registration *(code)*;
  - no new pre-registration may be frozen after a test run in order to run again;
  - test outputs are never deleted or overwritten *(code: write-once)*.
  - **Limitation:** outputs live in git-ignored `data/processed/`. Deleting them by hand would
    bypass the once-only check, so the run is recorded in the experiment log at once.
- **Reporting:** every pre-registered result is kept and reported, including
  underperformance (G3-12, G3-21).
- **Scope:** no other code path may read the test period (D-060 bounded loaders stay). The old
  local results folder `data/processed/backtests/ac2d6b163d4f5e4b` and the milestone-3
  `regime_report.*` files are never opened.

### 7.1 Pre-registration items still open

| Item | Status | Can this policy resolve it? |
| --- | --- | --- |
| G3-5 `uncertainty` | OPEN: awaits independent human review | **No.** Needs a real review, or an explicit written waiver by a team member (§7, condition 4) |
| G3-6 `stress_windows` | OPEN | **Yes, at freeze time.** D-086 provisionally selects the run-time calendar check that is already implemented: a mismatch gives `not computed`, and the dates never move. At freeze it may be set to `ACCEPTED` with the record "Provisional (delegated) choice under D-084/D-086; not reviewed by the team" |

---

## 8. Non-negotiable research integrity (unchanged)

- **Reward:** no change to the reward during the initial profile experiment.
- **No changes to improve performance:** market data, features, constraints, costs and
  evaluation periods stay fixed, and no change is made after seeing results.
- **Test period:**
  - no tuning, selection or retraining from test results;
  - no repeated or selective test runs;
  - no test-period read outside §7.
- **Results:**
  - no deleted negative results; no failed runs removed from the experiment log;
  - every reported result is net of costs, with Sharpe, drawdown and turnover reported.
- **No fabrication:** no approval, review, experiment completion or result is invented.
- **Claims:** no claim of superiority without comparable evidence; no claim of investor
  suitability or financial advice; backtests are described as backtests.
- **Evaluation design:** chronological splits only; no shuffled K-fold on time-ordered data;
  preprocessing is fitted on training data only.
- **Other files:** `Abstract.pdf` is never modified, and AI-use disclosures are never removed.

If one of these conflicts with autonomous completion, the restriction wins. Everything else is
completed and the conflict is reported.

---

## 9. Commits, pushes and authorship (not delegated)

- **Commits and pushes need explicit permission in the instruction that runs the work.** This
  policy does not grant it. That is the user's standing requirement in `CLAUDE.md`.
- **Effect on autonomy:** full training runs (D-075) and the test evaluator both refuse
  uncommitted code. An autonomous workflow therefore needs commit permission, for example
  "you may make local commits; push only when asked", and the **author identity** to use
  (D-070 has no standing rule).
- **Before each commit:** summarise the staged changes and the checks actually run. No
  `Co-Authored-By` trailer (`CLAUDE.md`).

---

## 10. Completion criteria

The research workflow is complete only when all of these are true:
1. Every §4 step has run, or is recorded as blocked with a reason. Results, including negative
   ones, are in `docs/experiment_log.md`.
2. The full test suite, Ruff and configuration validation pass on the final commit.
3. The one-time test evaluation (§7) has run and been verified, **or** it is recorded as not
   run, with the unmet condition named.
4. The **[R]** explainability item has been run (it needs an authorisation, §4), **or** it is
   recorded as not done.
5. `docs/final_report.md`, the presentation guide and the README reflect the actual results
   and limitations, including the profile limitation in §3.
6. No document claims an approval, a review or a result that did not happen.

---

## 11. Audit trail

Every run and evaluation records:
- the command line and the code commit, including dirty state and diff hash;
- the configuration hashes and seeds;
- the dataset and feature-set ids, and hashes of the rows read;
- the checkpoint and output SHA-256 values;
- package versions and the device;
- start and end times.

These live in the run metadata (`data/processed/experiments/…`, git-ignored), mirrored in
`docs/experiment_log.md`, with a dated journal entry per session.

---

## Appendix A. Governance audit (2026-11-03, before changes)

| # | Gate | Defined in | Blocks | Type | Smallest change | Keep for integrity? |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | "If unsure, ask"; every change of an assumption or interface stated to the user | `CLAUDE.md` "How to work" | Routine implementation | Implementation | Routine → decide and record; material → Provisional (delegated) entry | Keep the duty to *state* changes in docs |
| 2 | No [O] extension or scope change without recorded team approval | `CLAUDE.md`, `roadmap.md`, README scope | Profile-conditioned PPO | Methodology / scope | D-085 records the in-session authorisation (R-S) for this extension only | Keep for any other extension |
| 3 | Only the team approves; AI never marks approved | `decision_log.md` header | Methodology choices | Methodology | Add the **Provisional (delegated)** status | Keep |
| 4 | Each task approved separately (R-S task scope) | `approval_checklist.md` §0.0, D-061 | All execution | Execution | D-084 standing authority for the §4 workflow | Keep R-S wording rules |
| 5 | Training needs authorisation; `--execute --confirm-full-grid` | D-066, D-075, `roadmap.md` | Profile training | Execution | Authorised by D-084 §4 | Keep the flags |
| 6 | Full runs refuse uncommitted code | D-075 (code) | All full training | Implementation guard | None | **Keep** (reproducibility); needs commit permission (§9) |
| 7 | Validation used once for selection; each validation execution authorised | D-076, D-077 | Profile validation | Execution / data access | Prespecified validation looks authorised by D-084 | Keep: no iteration; config-4 selection stands |
| 8 | Validation-access authorisation for PPO explainability | D-080, `explainability_validation_plan.md` | [R] explainability | Data access | **Not covered** by the instruction; flagged | — |
| 9 | Pre-registration freeze: every item ACCEPTED | `config.py` (code), D-082/D-083 | Test | Methodology | G3-6 resolvable as Provisional (delegated) at freeze | Keep the code check |
| 10 | G3-5 independent human review | D-083, prereg YAML | Freeze | Review | None possible by Claude | **Keep** |
| 11 | Gate 3c team review and commit instruction | D-083, checklist | Freeze, test | Review / commit | Commit needs permission; review as in #10 | **Keep** |
| 12 | Separate unsealing authorisation naming every identifier | D-083 G3-13, checklist, roadmap S7 | Test | Data access | Standing one-time authorisation (§7); identifiers bound by the code checks and recorded in the journal before execution | Keep every code guard |
| 13 | Test-period isolation in default loaders | D-056, D-060 (code) | Any test read | Data access | None | **Keep** |
| 14 | No commit or push unless asked | `CLAUDE.md` | Commit-dependent steps | Repository | None (the user requires it) | **Keep** |
| 15 | Large ML frameworks only when the RL milestone needs them | `CLAUDE.md` | — | Dependencies | None (already satisfied) | Keep |

## Appendix B. Final governance audit (2026-11-03, after changes)

| Gate | Original restriction | Updated policy | Remaining blocker |
| --- | --- | --- | --- |
| Routine implementation | Ask when unsure; per-task approval | Standing authority (§1, §2) | None |
| Routine tests and checks | Per-task | Standing authority | None |
| Profile extension scope | Needs recorded team approval | D-085 (R-S, this instruction) | Scientific concern §3 (reward is profile-independent) |
| Profile protocol details | Team decision | Provisional (delegated), D-086 / protocol §15 | None for execution; not team-reviewed |
| Training | Per-run authorisation | Authorised (§4) | **Commit permission** (D-075 clean-tree rule) |
| Validation experiments | Per-look authorisation | Prespecified looks authorised (§4) | None |
| Configuration-4 explainability ([R]) | Validation-access authorisation | Not covered | Needs an explicit instruction |
| Pre-registration preparation | Team decisions | Can be prepared | — |
| Pre-registration freeze | Every item ACCEPTED | G3-6 resolvable by delegation | **G3-5 human review (or written waiver)**; Gate 3c review; commit permission |
| Unsealing | Separate authorisation naming identifiers | Standing one-time authorisation (§7) under conditions 1–8 | Conditions 3–5 above |
| Test evaluator protection | Code guards | Unchanged | — |
| Documentation | Per-task | Autonomous (§1) | None |
| Fresh-session continuation | Conversation history | This document plus D-084–D-086 | None |
