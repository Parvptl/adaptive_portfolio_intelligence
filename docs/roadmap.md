# Roadmap

Milestones are sequential: each builds on tested code from the previous one. Every milestone ends
with passing tests, updated docs (journal, handbook, decision log, glossary as relevant), and (from
milestone 5 onward) entries in [`experiment_log.md`](experiment_log.md).

**Status:** ✅ done · ◐ partly done · ⏳ next · ▫️ planned
**Scope:** **[R]** required by the submitted abstract · **[F]** required "where feasible" by the
abstract · **[O]** optional extension, not committed; pursue only with team approval
(record in [`decision_log.md`](decision_log.md)).

All dates, assets, costs and constraints mentioned here are provisional (see
[`decision_log.md`](decision_log.md)).

## 0. Repository scaffold ✅

Complete. Committed as `412d620` and pushed; the GitHub Actions CI workflow passed on that commit.

- `src/` package layout, `pyproject.toml`, Ruff, pytest, Makefile, CI workflow.
- Provisional YAML configs with validated loader (`adaptive_portfolio.config`).
- README, CLAUDE.md, documentation set under `docs/`.

## 1. Financial metrics: ✅ complete

All conventions for this milestone (D-011, D-021, D-022, D-024 to D-030, D-032, D-033) were
accepted on 2026-10-13. Committed as `94e6f74`; GitHub Actions CI passed on that commit
(Python 3.11–3.13).

Implement and unit-test metrics on synthetic return series *before* any real data or models, so that
everything later is measured with trusted tools.

Implemented, documented and tested (2026-10-13; uncommitted, pending team review):

- ✅ [R] Portfolio (simple) returns from portfolio values: `portfolio_returns` (D-021).
- ✅ [R] Cumulative return: `cumulative_return` (D-028).
- ✅ [R] Annualised return, geometric / CAGR: `annualized_return` (D-029).
- ✅ [R] Annualised volatility: `annualized_volatility` (D-022, D-023).
- ✅ [R] Sharpe ratio, with explicit risk-free conversion: `sharpe_ratio`, `annual_to_periodic_rate`
  (D-024, D-025).
- ✅ [R] Maximum drawdown, with peak and trough positions: `max_drawdown`, `drawdown_series` (D-026).
- ✅ [R] Two-way portfolio turnover from drift-adjusted weights: `portfolio_turnover`, plus
  `annualized_turnover` (D-011, D-030). An optional `cash_column` gives traded notional
  (extension approved 2026-10-13; the default is unchanged).
- ✅ Pre-commit review fixes (2026-10-13):
  - pandas dev minimum raised to 2.2 (D-032, Accepted). That day's minimum-version run used
    Python 3.12.1 on Windows with numpy 1.26.0, pandas 2.2.0, pytest 8.0.0 and ruff 0.6.0. PyYAML
    was 6.0.1, because the then-declared minimum 6.0 could not be installed on 3.12.
  - PyYAML minimum raised to 6.0.2 (D-033, Accepted). The final local runs (all on Windows) were:
    - **Python 3.12.1** at the declared minimums (numpy 1.26.0, pandas 2.2.0, PyYAML 6.0.2,
      pytest 8.0.0, ruff 0.6.0): all tests pass, lint and format clean.
    - **Python 3.13.7** at the lowest versions with 3.13 wheels (numpy 2.1.0, pandas 2.2.3,
      PyYAML 6.0.2, pytest 8.0.0, ruff 0.6.0): all tests pass. The declared numpy 1.26 and pandas
      2.2.0 minimums have no 3.13 wheels.
    - **Python 3.11:** not tested locally (not installed). Only Windows was tested.
  - handbook rules table; module docstring;
  - `annualized_turnover` always returns a `float`;
  - journal CI wording corrected; mutation counts corrected.
- ✅ Review fixes:
  - direct validation tests for `annual_to_periodic_rate`;
  - tuple and pandas inputs tested (pandas dev-only, D-032);
  - `ddof` wording clarified (D-022);
  - zero-volatility tolerance reviewed with evidence and kept (D-025).
- ✅ Tests: hand-computed values, edge cases, input validation, drift demonstrations, consistency
  with the config `max_turnover` bound, plus hand-picked injected-error checks. These are a
  selected set of deliberate bugs, not systematic mutation testing.
- ✅ Dependencies: `numpy` (runtime), `pandas` (dev-only).

Sign-off: ✅ all milestone conventions were accepted on 2026-10-13 (see the decision log). If any
convention changes later, the code, tests and docs must change together.

Moved to later milestones, because they cannot be decided without them:

- D-023: the project-wide `periods_per_year` per data frequency (252 vs. 365 for daily) belongs to
  milestone 2 (data pipeline). The metric functions already require N explicitly.
- D-031: the transaction-cost basis for cash legs belongs to milestones 4 and 7 (environment, costs).
- D-013: trade timing belongs to milestone 4; turnover is timing-agnostic.

Optional, not started:

- [O] Log returns, Sortino, Calmar, drawdown duration, transaction-cost drag.

## 2. Data pipeline: ✅ implemented and tested · committed (`1a289ab`) and pushed · methods D-035–D-039 accepted 2026-10-19; D-006, D-008, D-034, D-042 provisional

Implemented on 2026-10-15 in `src/adaptive_portfolio/data/`, with the CLI
`scripts/market_data.py` (technical handbook §11). Every decision introduced here (D-034 to
D-042, and D-008 moved from Open to Proposed) awaits team approval. GitHub Actions has not run on
this work.

- ✅ [R] Load historical prices from local CSV (`csv` provider); reproducible preprocessing.
- ✅ [R] Observed-calendar alignment, missing-data policy (`error` / `drop_sessions`, never
  fill), adjusted prices (`adj_close`, never mixed with `close`), simple-return construction
  that reuses `portfolio_returns`.
- ✅ [R] Data-quality report (JSON + Markdown: coverage, gaps, missing cells, corporate-action
  counts, return range, split counts); processed datasets in `data/processed/<id>/`.
- ✅ [R] Chronological split assignment (D-038), with leakage/causality tests.
- ✅ [R] Raw snapshots with manifest and checksums; cache modes use / refresh / offline (D-039).
- ✅ [O] Provider adapter (yfinance, optional extra). Started because the team member's
  milestone-2 brief explicitly requested a real-data adapter. The provider choice itself is
  Proposed (D-008, D-041). One live retrieval of the full universe (2007–2024) succeeded on
  2026-10-15.
- ✅ Offline tests with hand-calculated fixtures, synthetic data and a fake yfinance module; no
  network access in tests or CI.
- Still open: D-023 (annualisation), D-019 (embargo), D-018 (walk-forward), and team approval of
  D-008 and D-034 to D-042.

## 3. Market conditions and regime detection: ✅ implemented and tested · committed (`adffff5`) and pushed · ⏳ decisions Proposed (D-044 acknowledged as provisional)

Implemented on 2026-10-15 in `features/` and `regimes/`, with the CLI commands `features` and
`regime-report` (technical handbook §12). Decisions D-043 to D-047 await team approval.

- ✅ [R] Causal features in `features/`: momentum, volatility, downside volatility, drawdown,
  dispersion, equity–bond correlation, and group composites (34 columns by default). Trailing
  windows only; warm-up kept as NaN.
- ✅ [R] Transparent rule-based labels for rising / falling (trend) and high-volatility periods:
  thresholds fitted on the training partition only, frozen in an artifact, re-applicable without
  refitting.
- ✅ Diagnostics: regime counts and proportions by split, transitions, feature medians by regime,
  and sparse, absent and concentrated warnings.
- ✅ Leakage tests: features and frozen-threshold labels unchanged when future data is modified or
  appended; thresholds unaffected by validation/test values; boundary-crossing decision/target
  pairs flagged.
- ✅ Run offline on the existing live processed dataset (2007–2024): all 9 regimes occur; the
  report lists 4 warnings (descriptive, not tuned).
- [R/decision] Whether regime signals are given to the agent as observations: still open (D-012).
- [O] Statistical regime models (e.g. hidden Markov model or clustering): not started.

## 4. Portfolio environment: ◐ simulator (`66f9ed7`) and hardening 4.1 (`880d82c`, CI passed) · 4.2 preparation (`817f8b8`, CI #7 passed) · conventions accepted 2026-10-19 · Gate 2 defaults accepted 2026-10-19 · RL building blocks M5.1 and Gymnasium environment M5.2 implemented (uncommitted)

Done on 2026-10-15, together with milestone 5, as the team's "milestone 4: portfolio simulation
and conventional baselines" (technical handbook §13). It was originally committed and
pushed as `a7134b7`, and CI passed on it. After a metadata rewrite on 2026-10-18 the same
tree is commit `66f9ed7` (see the project journal). Decisions D-048 to D-054 await team
approval.

**Milestone 4.1 (2026-10-18, commit `880d82c`, originally `4b37aae`; CI run #6 passed):**
hardening after the read-only milestone-4 audit. Decisions D-055 to D-057 are Proposed.
- lag 1 as the primary convention, with the lag required in the config;
- shared timing with the feature alignment;
- test split opt-in;
- validated simulator settings;
- documented cap and ledger semantics.

- ✅ [R] Explicit timing convention: decide at close *d*, execute at close *d* + lag, earn from
  the next session (D-048, D-013). Lag 1 is the primary convention and lag 0 an idealised
  sensitivity case (D-055; accepted 2026-10-19).
- ✅ [R] Transaction costs on traded notional, cash leg excluded, initial funding charged (D-049,
  proposal for D-031). Long-only, unlevered, fractional weights with implicit cash (D-050).
- ✅ Deterministic tests on toy paths with hand-calculated ledgers.
- [R] Sequential RL environment (observations, weight actions, risk-aware reward, episode
  boundaries). It must reuse the simulator's accounting and timing.
  - ✅ **M5.1 (2026-10-19, `71e6333`):** building blocks per D-062 to D-067, without an RL
    library:
    - the simulator `step` interface, with `simulate` looping over it;
    - the `weekly` schedule;
    - training-only feature scaling and the 51-input observation;
    - the softmax action mapping;
    - weekly episode decisions and the decision-aligned reward;
    - `train_only` bounded loading.

    Bounded integration check on the real training split: passed (journal, 2026-10-19).
  - ✅ **M5.2 (2026-10-19, `71e6333`):** the Gymnasium `PortfolioEnv`, the optional `rl`
    extra and the `rl` test marker.
    - It passes `check_env`. The action space was normalised to `[−1, 1]` by D-072
      (accepted 2026-10-19), so only a render-spec notice remains.
    - It was validated on the real training split only (26 checks).
  - ◐ **M5.3 (2026-10-19, `85c40d1`): PPO training wrapper ready. Full grid trained as
    EXP-005 (updated 2026-10-21); evaluation and selection not yet done.**
    - D-072 was accepted after the equivalence tests passed: normalised `[−1, 1]` actions,
      scaled ×5.
    - Added `agents/ppo.py`, `configs/agent.yaml` (D-066 grid; other settings pinned, D-074
      Proposed), run outputs under `data/processed/experiments/` and `scripts/train_ppo.py`.
    - **Throughput smoke test done (EXP-003):** two 4,096-step runs on the training split,
      both completed, about 320 steps/s on one thread. The full D-066 budget is estimated at
      about 3.5 h sequentially (an approximate extrapolation from two 4,096-step runs). No
      budget change is proposed.
    - ✅ **Pre-grid hardening (2026-10-19, `85c40d1`):** exclusive finalisation, code
      provenance policy, a sequential grid runner with a manifest, quarantine-based recovery,
      determinism settings, stale statuses corrected. D-075 was proposed, then accepted on
      2026-10-19 (with D-071, D-073 and D-074).
    - ✅ **Full grid trained (EXP-005, 2026-10-20, commit `cc9784b`):**
      - 40 policies (8 configurations × seeds 42–46), training data only, ending 2016-12-30;
      - 40/40 completed and independently verified.
    - Policy evaluation and configuration selection were done in Milestone C (EXP-006,
      below).
    - ✅ **Milestone B (2026-10-21, commit `0f8341b`): evaluation protocol and validation evaluator.**
      - Protocol D-076 was accepted on 2026-10-21 (under R-S; protocol only). Execution was
        authorised separately the same day.
      - Evaluator, selection rule and data-boundary guards are implemented and tested on
        synthetic data.
      - All 40 checkpoints were verified by `--plan`.
    - ✅ **Milestone C (2026-10-21): validation evaluation EXP-006.**
      - Evaluation `1ce9c490ed03c8c9`, validation 2017–2019 only.
      - Configuration 4 selected.
      - No policy reached any baseline's validation net Sharpe.
      - Diagnostic and proposals: `docs/exp006_turnover_diagnostic.md`. Follow-ups are D-077
        (Proposed).
    - ▫️ **Follow-up D-077 item 1:** the protocol is drafted as D-078 (Proposed,
      `docs/protocol_d078_training_modes.md`). It is not implemented or run, and needs approvals
      A1–A3.
    - ▫️ **Gate 3 (test evaluation):** not started; the decisions listed in the diagnostic
      document are open.
      *(Update 2026-10-21: Gate 3 is now planned in Phase D, at the end of this file, and its
      items are listed in the `approval_checklist.md` Gate 3 packet; all are OPEN.)*
- ✅ Test split opt-in (`--include-test`, D-056, Proposed).
- **Milestone 4.2 (2026-10-18, commit `817f8b8`, CI run #7 passed): protocol preparation before PPO.**
  - ✅ draft [`research_protocol.md`](research_protocol.md), **not approved**;
  - ✅ common evaluation window covering the 126-session feature warm-up (D-058, Proposed);
  - ✅ funding turnover reported separately and excluded from annualised turnover (D-059,
    Proposed).
  - Walk-forward evaluation is **not implemented** (D-018 open).
  - A primary-convention (lag 1) baseline record does not exist yet.
- Still open: D-023 (annualisation) and the turnover-cap measure (D-031).
- Likely dependency (RL interface only): `gymnasium`.

## 5. Baseline strategies: ✅ minimum set accepted 2026-10-19 · primary record EXP-002 (train and validation)

- ✅ [R] Conventional allocation benchmarks, proposed minimum set (D-053, proposal for D-010):
  equal weight monthly, equal-weight buy-and-hold, inverse volatility (63) monthly. Fixed weights
  are also supported.
- ✅ Offline run on the live processed dataset (2007–2024); train and validation results
  recorded as EXP-001 (descriptive only). It used lag 0, now the idealised sensitivity case.
  The primary lag-1 run has not been made yet.
- Candidates not implemented: reference portfolio (possible with `fixed_weights`), minimum
  variance, mean-variance, risk parity.
- [O] Momentum / volatility targeting and other rule-based strategies.
- Same backtest engine, costs and constraints as the agents.
- First logged experiments: baselines on train/validation periods.

## 6. RL agents ▫️

*Status note (2026-10-21, appended; the heading marker above is stale):*
- PPO work was tracked under milestone 4 (M5.1–M5.3) and Milestones B–C.
- The D-066 grid was trained (EXP-005), evaluated on validation and configuration 4 was
  selected (EXP-006).
- It has not been evaluated on test. Remaining work is in Phase D.

- [R] PPO, as the candidate algorithm named in the abstract. If PPO proves unsuitable, record why
  and what replaces it.
- [O] Other algorithms (e.g. DQN on discretised actions), only if justified.
- Library choice decided here (e.g. Stable-Baselines3); add the dependency at this point, not before.
- Hyperparameter search on validation only; multiple seeds.
- [O] Regime-aware vs. regime-agnostic variants (depends on D-012).

## 7. Realistic costs and constraints ▫️

- [R] Transaction costs included in every reported result.
- [O] Cost sensitivity sweeps (e.g. 0–50 bps), slippage model, turnover caps, rebalancing-frequency
  comparison.

## 8. Robust evaluation ▫️

- [R] Single final out-of-sample run on the held-out test period.
- [F] Walk-forward evaluation (expanding / rolling).
- [F] Stress testing across different market conditions.
- [R] Performance by market condition; seed variability.
- [O] Statistical comparison with baselines (e.g. bootstrap confidence intervals).

## 9. Explainability ▫️

*Status note (2026-10-21, appended; the marker above is stale):* ◐
- The milestone E pipeline is implemented and tested (`docs/explainability.md`).
- Baselines were analysed on the training split (EXP-008).
- **The PPO analysis on validation decisions (D-068) awaits an explicit authorisation.**
- The regime-input ablation is planned only (D-081, Proposed).

- [R] Explore techniques to understand factors associated with allocation decisions and
  risk-taking behaviour (e.g. allocation behaviour by market condition, sensitivity analysis).
- [O] Specific attribution libraries (e.g. SHAP), permutation importance.

## 10. Dashboard ▫️ [O]

*Status note (2026-10-21, appended):* ◐ started at a team member's instruction (D-079,
under R-S). It is a static dashboard from saved, verified results
(`python scripts/workflow.py dashboard`). It shows training and validation results only.

- Lightweight interactive view of equity curves, drawdowns, allocations and regimes (e.g. Streamlit),
  reading saved results only. Not mentioned in the abstract.

## 11. Final research report ▫️ [R]

*Status note (2026-10-21, appended):* ◐ the draft `docs/final_report.md` is checked against
the outputs. **It is incomplete:** there are no test results (Gate 3), no PPO
explainability, and no stress or bootstrap analysis.

- Methodology, assumptions, results with uncertainty, limitations and negative results.
- Reproducibility appendix: configs, seeds, commit hashes, data provenance.
- AI-use disclosure.

## Phase D — Finalization, Robustness and Out-of-Sample Evaluation ▫️ (planned 2026-10-21; nothing started)

**Where it fits:**
- Phase D is the next lettered work package after Milestones A–C (the PPO close-out, the
  evaluation protocol and evaluator, and the validation evaluation). It does not replace the
  numbered milestones.
- It delivers the remaining parts of milestones 7 (costs, where pre-registered), 8 (robust
  evaluation, including the single test run), 9 (explainability, see the note below) and 11
  (final report), and it contains **Gate 3**.

**Approval categories used below:**
- **Done:** completed and recorded.
- **Proposed:** written down, not approved.
- **Needs implementation authorisation:** code may be written only after an explicit approval.
- **Needs execution authorisation:** a run that reads data needs its own explicit approval,
  naming the ids and hashes.
- **Gate 3:** the pre-registration and test-access approvals.

**Test-period restriction (unchanged):** 2020–2024 stays **sealed** until a separately
recorded unsealing authorisation (D5). No Phase D step before D5 may load, inspect or report
any test row or metric. This includes the old local folder with pipeline-v1 test results
(`research_protocol.md` §12).

| Workstream | Status | Depends on | Deliverables | Acceptance criteria | Approval gate |
| --- | --- | --- | --- | --- | --- |
| **D1** Current-work close-out | ◐ records reconciled (2026-10-21); **uncommitted** | — | EXP-006 records, the diagnostic and D-077/D-078 drafts committed; the journal records the actual Git state | The EXP-006 figures reconcile with the saved outputs; artifact hashes are unchanged; `git diff --check`, Ruff and pytest pass; only `README.md` and `docs/` change | An explicit commit instruction. Commit authorship has no standing rule (D-070), so the team states it per commit |
| **D2** D-078 and optional EXP-007 | Proposed (D-078); EXP-007 planned, not executed | D1 (recommended) | If authorised: code and tests (protocol §12); one training-only run; an EXP-007 entry | As D-078 §12–§14. Descriptive only; training rows only | A1 protocol → A2 implementation → A3 execution (`approval_checklist.md`, D-078 packet) |
| **D3** Candidate freeze and Gate 3 pre-registration | ▫️ all items **OPEN** | D1. The team's decision on whether any D-077 follow-up is pursued **before** the freeze | A pre-registration document, committed, with its SHA-256 recorded | Every item of the Gate 3 packet (`approval_checklist.md`) decided and recorded in the decision log. No item chosen from test data | Gate 3a: acceptance of the pre-registration (under R-S) |
| **D4** Test evaluator readiness | ▫️ not started; **needs implementation authorisation** | D3 accepted | A separate test evaluator, configuration, protocol version and hash, tests and review notes; D-076 untouched | Synthetic-data tests pass (including boundary, single-run and plan-reads-no-rows tests). Reviewed by a team member. Clean commit, CI green | Gate 3b: implementation authorisation; Gate 3c: review and commit instruction |
| **D5** Test execution and reporting (future) | ▫️ **gated** | D3 and D4 complete; Gate 3d | One test run; independent verification; an experiment-log entry reporting every pre-registered result, including underperformance | The run matches the pre-registered protocol hash, commit, checkpoints and dataset. Verification passes before any result is discussed | Gate 3d: **an explicit unsealing and execution authorisation** naming the id, protocol hash, commit, checkpoint hashes, dataset and pre-registration hash |
| **D6** Final deliverables | ▫️ planned; none exist yet | D5. Explainability (milestone 9) | Final experiment and decision records; reproducible tables and figures (from saved outputs); the technical report; presentation updates; a limitations and failure-analysis section; a final integrity and provenance audit | Every reported number traces to a saved artifact and hash. Limitations and negative results are reported. AI-use disclosures are intact | Team review of the report and presentation |

**Workstream notes:**
- **D1:** what can be committed later is listed in the project journal (2026-10-21, Phase D
  audit). Nothing is committed in the audit itself.
- **D2:** EXP-007 is **optional research, not a prerequisite for Phase D or Gate 3**. Its
  results describe in-sample behaviour only. They give no permission to tune against
  validation or test data, and they cannot establish overfitting. Protocol:
  [`protocol_d078_training_modes.md`](protocol_d078_training_modes.md).
- **D3:** the candidate as of 2026-10-21 is configuration 4, seeds 42–46, selected under
  D-066 and D-076. It **trailed all three baselines on validation net Sharpe**. Freezing it is
  a decision, not a recommendation of the strategy. Packet: `approval_checklist.md`, "Gate 3
  pre-registration packet".
- **D4:** the D-076 evaluator cannot evaluate the test split, and it must not be changed to do
  so:
  - `EvaluationConfig` rejects any split but validation;
  - `evaluate()` loads with `exclude_test=True` and asserts that no test row is held;
  - it always runs configuration selection.

  A separate evaluator is required. The baseline backtest's `--include-test` (D-056) exists,
  but using it would be a separate test look. The proposal is that only the D5 run touches
  test rows.

**Dependencies:** D1 → D3 → D4 → D5 → D6. D2 is optional and runs in parallel; it must not
delay or alter D3 unless the team decides so before the freeze.

**Required by the abstract but outside the D1–D6 outline:**
- **Explainability, milestone 9 [R]:** the design is accepted (D-068: permutation sensitivity
  on validation decisions, plus regime summaries; associations, not causation). It is **not
  implemented**; implementation and execution each need authorisation. It does not need the
  test period, so it can run before or in parallel with D3/D4. D6 depends on it.
- **Walk-forward [F] (D-018, Open), embargo (D-019, Open) and stress testing [F]:** the team
  must either schedule these or record why they were not feasible. Walk-forward with
  retraining would need training authorisation.
- **Scope labels that conflict:**
  - the README and milestone 8 label bootstrap confidence intervals **[O]**, but the Gate 2
    item 10 recommendation and `research_protocol.md` §10 use them for test inference;
  - Sortino is [O] in the README and is not implemented, while `CLAUDE.md` lists it among the
    metrics to report.

  The Gate 3 packet asks the team to decide both.

### Phase D revision (2026-10-21, dependency review; appended, the text above is kept)

**What this revision fixes in the plan above:**
1. **Explainability had no slot.** D6 depended on it, but no workstream produced it. It is
   required: the abstract says "explored", D-068 is accepted, and milestone 9 is [R].
2. **Regime analysis had no decision point.** The G3-3 regime metrics need a frozen taxonomy,
   and D-045 is still Proposed.
3. **A circular dependency in Gate 3.** G3-11 and G3-13 asked the pre-registration document to
   carry the evaluator commit, while that commit must contain the document. Resolved in the
   Gate 3 addendum (G3-22): the document fixes the decisions and the configuration hash; the
   commit is named only in the unsealing authorisation and recorded in the run identity.
4. The **Dependencies** line above (D1 → D3 → D4 → D5 → D6) is superseded by the sequence
   below. Workstreams D1–D6 keep their names.

**Status of the contested items** (sources: the abstract, the decision log, the README, the
approval checklist Gate 2 packet, `research_protocol.md` (draft, not approved) and
`CLAUDE.md`):

| Topic | Required by the abstract or an accepted decision | Recommended by an open gate or draft | Marked optional | Unresolved | Smallest explicit decision needed |
| --- | --- | --- | --- | --- | --- |
| Explainability | **Yes:** abstract ("explored"); D-068 accepted (permutation sensitivity on validation decisions; regime summaries; associations only) | Gate 2 item 17 (became D-068) | SHAP only | Protocol details: feature groups, number of permutations, seeds, sensitivity measure, outputs | One explainability protocol decision, with implementation and execution authorisations (G3-17) |
| Regime / market-condition analysis | **Yes in substance:** the abstract studies rising, falling and high-volatility periods; milestone 8 "[R] performance by market condition". The checkpoints already use the D-045 labels as inputs (D-062, accepted) | Regime-conditional secondary metrics (research protocol §10) | Statistical regime models | **D-045 is Proposed** (provisional) | Accept D-045, or acknowledge it as provisional as D-044 was, and freeze the threshold artifact used by the checkpoints for all analysis (G3-14) |
| Walk-forward (D-018) | Abstract: "where feasible" ([F]) | Research protocol: expanding folds inside 2007–2019, no per-fold tuning | **README scope table puts it in the optional column (contradiction)** | **D-018 Open**; feasibility not assessed. It would need retraining | Decide D-018: schedule it (training authorisation; after the freeze; cannot change the candidate) or record it as not feasible, with the reason (G3-15) |
| Embargo (D-019) | Not in the abstract | Research protocol: no embargo needed for one-step rewards. D-043 (Proposed) excludes boundary-crossing pairs. Handbook fact: no embargo | — | **D-019 Open; D-043 Proposed** | Close D-019 by recording "no embargo for one-step decision-aligned rewards (D-064)", or specify a gap (G3-16) |
| Stress testing | Abstract: "where feasible" ([F]) | Gate 2 item 11 (open): a public-rule windows rule, with dates from a cited source | **README scope table: optional column** | Rule and source | Decide G3-6 (rule and citation) or record it as not feasible |
| Bootstrap intervals | No accepted record requires them. D-076 item 12 only notes "bootstrap settings … still open" | Gate 2 item 10 (open); research protocol §10; `ppo_design_proposal.md` §13 | README scope table and milestone 8: [O] | Whether test inference uses them, and their settings | Decide G3-5: adopt (and then mark milestone 8's [O] as superseded) or report descriptively only |
| Sortino | No. **D-076 (accepted) excludes it** for validation: "optional … no agreed definition" | `CLAUDE.md` safeguard 6 lists it (working guidance, not a project decision); README methodology "planned additions" | README scope table: optional | Whether the test report includes it, and its definition | Decide G3-20: include with a definition (implementation needed) or exclude, consistent with D-076 |

**Dependency-aware sequence (supersedes the Dependencies line above):**

| Stage | Content | Depends on | Approval needed | Can run in parallel with |
| --- | --- | --- | --- | --- |
| S0 | **Research close-out (D1):** commit the reconciled EXP-006 records and drafts | — | Commit instruction and authorship (D-070 has no standing rule) | S1, S2 |
| S1 | **Methodological decisions:** D-045, D-018, D-019, bootstrap status, Sortino, stress-test inclusion, the explainability protocol, whether any D-077 follow-up is pursued | S0 recommended | Team decisions (G3-14 to G3-17, G3-20, G3-1 note) | S2 |
| S2 | **Optional EXP-007 (D2):** training-only, descriptive | D-078 A1–A3 | A1, A2, A3 | S0, S1, S3 to S5. **Not a prerequisite** of any stage. If pursued, it must finish before S3, and it may never be used to tune on validation or test |
| S3 | **Candidate freeze (G3-1):** checkpoints by hash, plus frozen artifacts (G3-18) | S1 (the D-077 follow-up decision) | Team decision | — |
| S4 | **Pre-registration decisions (Gate 3a):** G3-2 to G3-21 | S1, S3 | Team acceptance under R-S | — |
| S5a | **Explainability:** protocol → implementation → execution on validation decisions (D-068) → independent verification → recorded | S3 (freeze), S1 (protocol, D-045) | Implementation authorisation, then execution authorisation | S5b |
| S5b | **Independent test evaluator (D4):** implementation, synthetic-data tests, review, commit; D-076 untouched | S4 | Gate 3b (implementation), Gate 3c (review and commit instruction) | S5a |
| S6 | **Pre-registration freeze (G3-11, G3-22):** final document committed; amendments allowed only before this point, for implementation reasons, with no test data seen, and recorded | S4, S5b; **S5a recorded (proposed)** | Team acceptance of the frozen document | — |
| S7 | **Unsealing and execution authorisation (Gate 3d, G3-13):** names the evaluator commit, protocol hash, configuration hash, dataset id, checkpoint hashes, pre-registration hash and command | S6 | Explicit authorisation under R-S | — |
| S8 | **One pre-registered test evaluation (D5)** and independent verification **before** results are discussed | S7 | — (covered by S7) | — |
| S9 | **Final report, presentation and reproducibility audit (D6)** | S8, S5a; S2 and walk-forward if run | Team review | — |

**Why explainability runs alongside the test evaluator, but is recorded before unsealing
(proposed; OPEN for the team):**
- It needs no test data: D-068 limits permutation sensitivity to validation decisions. So it
  is not blocked by Gate 3, and the code is independent of the test evaluator. Building both at
  once costs no extra waiting.
- Running it **after the candidate freeze** (S3) stops its findings from influencing which
  checkpoints are tested.
- Recording its results **before unsealing** (S6/S7) keeps the interpretation of the
  allocation drivers independent of test outcomes.
- Any test-period explainability, such as regime-conditional allocation on 2020–2024, can only
  come from the single pre-registered test run (G3-17), not a second test access.
- If the team prefers not to wait, the alternative is to finish S5a after S8. The cost is that
  its interpretation could then be coloured by the test results, which must be disclosed.

*Status note (2026-10-21, appended; milestones D-F completion request):*
- **D1:** records reconciled; still uncommitted (17 modified and 26 new files).
- **D2:** D-078 Proposed; EXP-007 not run.
- **D3:** **OPEN.** No Gate 3 decision was supplied. The pre-registration exists as a DRAFT,
  `configs/preregistration.yaml`.
- **D4:**
  - the test evaluator was implemented and tested on synthetic data (D-082, Proposed);
  - Gate 3b was instructed in the session;
  - Gate 3c (review and commit) is pending.
- **D5:** not started. It needs the frozen pre-registration, a commit and the unsealing
  authorisation.
- **D6:** draft report and dashboard only. Explainability (milestone 9): the PPO analysis is
  still unauthorised.

*Status note (2026-10-22, appended; Gate 3 implementation):*
- **D3:** Gate 3 decisions recorded as D-083; 16 of 18 pre-registration items accepted. The
  file is still a **DRAFT**: G3-5 awaits human review, and G3-6 awaits a decision on run-time
  calendar verification.
- **D4:** the evaluator was updated and verified on synthetic data only: moving-block
  bootstrap, fixed-action costs, stress-window check, extended verification. Gate 3c (review
  and commit) is pending.
- **D5:** not started. It needs the freeze, a commit, a fresh plan and a separate unsealing
  authorisation.
- **Explainability:** the plan `docs/explainability_validation_plan.md` is for review; it has
  not been executed.
