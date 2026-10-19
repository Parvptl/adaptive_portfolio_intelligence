# Project Journal

A dated, append-only record of work sessions: what was done, what was found, which checks were
**actually run**, open issues, and AI assistance used. Newest entries go at the top. Do not rewrite
past entries; add corrections as new notes.

## Entry template

```markdown
## YYYY-MM-DD: <short title>

- **Who:** <team member(s)>; AI assistance: <tool and what it did, or "none">
- **Milestone:** <roadmap milestone>

**Work done**
-

**Findings / issues**
-

**Checks run (actual results)**
-

**Decisions** (link to decision_log.md IDs; note if proposed or accepted)
-

**Next steps**
-
```

---

## 2026-10-19 (continued): D-071, D-073, D-074 and D-075 accepted under R-S

- **Who:** user of this session; the message does not name its author (repo-local identity
  `mavp309`). AI assistance: Claude Code (Anthropic) recorded the decision. No commit or push.
- **Decision:** a team member approved D-071, D-073, D-074 and D-075 under R-S (D-061). The
  other teammate's separate confirmation was not sought.
- **Scope stated with the approval:** it does **not** authorise a commit, push, repeat smoke
  run or full-grid training. D-070 (commit authorship) stays **Open** until an explicit
  decision.
- **Recorded:**
  - **Decision log:** only the status and approval lines of the four entries, and their index
    rows, changed. Proposal texts are unchanged.
  - **Approval checklist:** the pre-grid packet's decision row is filled in.
  - **Current-status statements** were updated in the README, roadmap, handbook §14, §16 and
    §16.5, and the `agent.yaml` comments (comments only; parsed values and run identities
    unchanged). The design proposal §7 got an update line after the earlier status note.
  - **Not edited:** historical journal and experiment-log entries.
- **Checks run** (after the edits): pytest 843 passed; Ruff check and format check passed (80
  files); `validate_config.py` exit 0. EXP-003 outputs unchanged (`da738d8728a41f4e`). No
  training, no data loaded beyond configuration.

---

## 2026-10-19 (continued): Read-only full-grid preflight, then pre-grid hardening (no training)

- **Who:** user of this session; the messages do not name their author (repo-local identity
  `mavp309`). AI assistance: Claude Code (Anthropic) wrote the code, tests and documentation,
  pending team review. No commit or push.
- **Preflight (read-only):**
  - Before/after snapshots of the working tree (`ccc40bde57eb2368`) and of the experiment
    outputs (`da738d8728a41f4e`) were identical.
  - **PASS:** EXP-003 records, the grid definition, the estimate labelling, test sealing, and
    tests/Ruff/config validation.
  - **FAIL:**
    - selection-rule gaps;
    - output safety: the final move could replace a completed run (demonstrated in a scratch
      directory), there was no code version, no manifest, and no recovery after a hard kill;
    - stale documentation.
- **Hardening pass:** the scope was approved by a team member; there was no training, no
  validation or test data, no change to the grid or budget, and no deletion of outputs.
  1. **Overwrite race fixed:**
     - `run_safety.finalise_exclusive` renames only if the destination does not exist;
     - an exclusive `<run_id>.lock` covers each run;
     - the destination is re-checked under the lock.
  2. **Code provenance:**
     - the run identity has a `code` field (commit, `dirty`, `diff_sha256` of the uncommitted
       changes);
     - policy: `full` runs refuse a dirty tree, with no override; `smoke` runs record it.
  3. **Grid runner** (`agents/grid.py`, `scripts/run_grid.py`):
     - an atomic manifest, sequential execution, and child processes with a 900 s hard
       timeout;
     - stop at the first failure, with retry only via `--retry-failed`;
     - resume adopts runs that verify and refuses invalid directories untouched;
     - `--execute` needs `--confirm-full-grid`.
  4. **Recovery:** stale locks and staging directories (same host, dead process) are
     quarantined, never deleted. A failed run's staging directory is now quarantined instead of
     deleted.
  5. **Determinism:** one thread, `torch.use_deterministic_algorithms(True)` during `learn`
     (restored afterwards), and recorded settings. The same seed gives identical initial
     weights (tested). Full-run reproducibility is **not verified** (it needs training).
  6. **Execution policy** in `agent.yaml` (`execution:` sequential / 900 / stop). Parallel
     execution and continue-on-failure are rejected by validation. The grid and the budget are
     unchanged (40 runs, 100,000 steps).
  7. **Decisions:** D-075 is recorded as **Proposed**. A pre-grid decision packet (D-071,
     D-073, D-074, D-075) with a blank decision row was added to `approval_checklist.md`.
     Nothing was marked Accepted on the team's behalf; D-070 remains Open.
  8. **Corrections, with history preserved:**
    - D-012, D-016 and D-017 are now "Accepted (resolved by D-062 / D-066 / D-069)", following
      the D-010 precedent; their old lines are kept and marked superseded;
    - D-066 has a clarification note listing the grid values;
    - EXP-002 has a correction note (`04dc44a`), and EXP-003 a note that its run configs
      predate D-075;
    - superseded markers were added to protocol §8 and §9 and to design proposal §8 and §11;
      the design §7 status note says evaluation determinism is undecided;
    - handbook test counts updated; README milestone row 6 and the estimate wording updated.
- **Failures met and fixed:** all were test-side; no test was weakened.
  - A message-substring assertion in my recovery test.
  - An `UnboundLocalError` waiting to happen (`del GIT`), which I caught before running.
  - A multi-line `run_identity` call that the automated edit missed.
  - Heredoc quoting broke one string literal, which was repaired.
- **Checks run** (after all edits; no pytest or Ruff cache, no bytecode):
  - `pytest`: 843 passed. `pytest -m rl`: 25 passed. With RL libraries blocked: 818 passed, 3
    skipped cleanly.
  - Ruff check and format check passed (80 files). `validate_config.py` exit 0 (40 runs =
    8 × 5, 100,000 timesteps).
  - Simulator parity: byte-identical.
  - EXP-003 folders: hash `da738d8728a41f4e`, unchanged, and both runs pass the 28-point check
    again.
  - `run_grid.py --plan`: grid `ad72165d8035b64e`, execution **REFUSED** (uncommitted code),
    nothing written.
- **Not done:** no training (not even a repeat smoke run), no validation or test data, no grid,
  no commit or push, no installation, no deletion of outputs. The selection metric and Gate 3
  remain separate and undecided.

---

## 2026-10-19 (continued): M5.3 throughput smoke test (EXP-003): two 4,096-step runs, training split only

- **Who:** user of this session; the approving message does not name its author (repo-local
  identity `mavp309`). AI assistance: Claude Code (Anthropic) ran the approved commands, checked
  the outputs and wrote the documentation. No commit or push.
- **Approved scope:**
  - Run A: configuration 0, seed 42, 4,096 timesteps.
  - Run B: configuration 2, seed 42, 4,096 timesteps.
  - Training split only; separate output folders; a 10-minute limit per run.
  - Stop on any failure. No grid, no tuning, no validation or test data.
- **Done:**
  - **Run A** (`d06b6c2971f6ff66`): completed, 4,096 timesteps, 12.802 s of training,
    319.9 steps/s, 8 episodes.
  - **Run B** (`4ddbffd78cddcb65`): completed, 4,096 timesteps, 12.649 s, 323.8 steps/s,
    8 episodes.
  - Both ran under `timeout 600`; each process took about 17–18 s including start-up.
  - A one-off check script outside the repository verified 28 checks per run:
    - the folder is finalised: exactly the five files, no staging folder left;
    - the identity hash equals the folder name, and the metadata and file hashes are
      consistent;
    - the data ends 2016-12-30, with the training-line hashes reproduced;
    - the scaler is fitted on training rows only;
    - the checkpoint reloads with matching settings and finite weights;
    - every training-episode reward is finite, and episodes are 496 steps long.
  - After Run B, Run A's folder was rechecked and is unchanged.
- **Estimate (approximate):** about 3.5 h of training for the 4.0 million-step D-066 budget, run
  sequentially on one thread; about 5.2 minutes per 100,000-step run. This is within the
  design memo's 0.6–4 h assumption, so **no budget change is proposed**. Details and caveats
  are in EXP-003.
- **Not done:** no full run, no grid, no tuning, no validation or test data, training rewards
  not interpreted, no installation, no commit or push.

---

## 2026-10-19 (continued): D-072 resolved (normalised actions); M5.3 PPO wrapper prepared, no training

- **Who:** user of this session; the message does not name its author (repo-local identity
  `mavp309`). AI assistance: Claude Code (Anthropic) wrote the code, tests and documentation,
  pending team review. No commit or push.
- **Instruction:**
  1. Resolve D-072 with a normalised `Box(−1, 1)` action interface, scaled ×5. Equivalence
     must be shown first; accept only after the implementation and tests pass.
  2. Prepare the PPO wrapper, without the full budget.
  3. Propose, but do not run, a throughput smoke test.
  4. No validation or test data, no EXP-002 rerun, no installation.
- **D-072:**
  - **Verified before implementing:**
    - `u ↦ 5u` is a bijection from `[−1, 1]^8` onto `[−5, 5]^8`.
    - `5u` is exact in float64 for float32 actions (24 + 3 bits ≤ 53).
    - Numerically: 200,000 float32 actions were exact, the round trip of 200,000 old float32
      actions was exact, and 20,000 targets were bitwise identical.
  - **Implemented:**
    - `actions.policy_action_to_logits`;
    - constants `POLICY_ACTION_*`, `ACTION_SCALE` and `LOGIT_*` (the old `ACTION_LOW/HIGH`
      were renamed `LOGIT_LOW/HIGH`);
    - the environment now uses `Box(−1, 1)`, and `info` gains `logits`.
  - **Tests added:** mapping equivalence (non-`rl`) and an episode-equivalence test (`rl`).
  - **Failure met:** the first version of the episode test divided by 5 in **float32**, and
    failed by about 1e-7 in the logits.
    - Cause: an old float32 action has no exactly equal float32 counterpart. This is a grid
      difference, not a mapping difference.
    - Fix: the test now passes the exact float64 counterpart, and states the float32 grid bound
      explicitly. The mapping tolerance was not relaxed.
  - **Results:** the real training split passed 27 checks, and `check_env` no longer gives the
    action-space warning (the test now allows only the render-spec notice). Full suite: 801
    passed.
  - **Recorded:** D-072 is **Accepted** (conditions met). The six M5.2 implementation choices
    were split off into **D-073 (Proposed)**, because the approval covered the action interface
    only. D-063 is noted as amended in interface only.
- **M5.3 preparation:**
  - `configs/agent.yaml` and `AgentConfig`: the D-066 grid, seeds, budget and batch size. Other
    SB3 settings are pinned to the verified 2.9 defaults, with one torch thread (**D-074,
    Proposed**).
  - `agents/ppo.py`: `build_model`, `run_identity`, `write_run_outputs`, `train_ppo_run` and a
    CLI (`scripts/train_ppo.py`).
  - Outputs go to `data/processed/experiments/<run_id>/`.
  - `cache.head_sha256` hashes the training lines only.
  - `make_training_env` now records `env.provenance`.
  - `validate_config.py` also validates `agent.yaml`.
  - The core-import guard now also covers `agents.ppo`.
- **Failures met and fixed:**
  1. Two test bugs: a float32 `5.0 * action` comparison, and a wrong import. The SB3 checker
     itself passed.
  2. A real CLI bug, found by the first real-data dry run: `main()` resolved the default
     dataset directory even when `--dataset-dir` was given, and crashed because the configured
     `csv` provider's dataset does not exist. Fixed, and covered by a test.
  3. An error message that was missing its f-string prefix (found in review).
- **Checks run (actual results):**
  - `pytest`: 821 passed.
  - `pytest -m rl`: 12 passed.
  - With Gymnasium, SB3 and torch blocked: 809 passed, 2 skipped cleanly.
  - Ruff check and format check passed (75 files). `validate_config.py` passed (40 runs = 8 ×
    5, 100,000 timesteps).
  - The M5.1 parity script still gives byte-identical results.
  - **Real-data dry runs** (training split, no training, nothing written): full run id
    `bae2ef9cf5513091`, smoke run (4,096 steps) id `d06b6c2971f6ff66`, 496 steps per episode,
    15,569 policy parameters.
  - `data/processed/experiments/` was never created.
- **Not done:** no `learn()` call anywhere, no smoke test, no validation or test data, no
  EXP-002 rerun, no installation, CI and Git configuration unchanged.

---

## 2026-10-19 (continued): M5.2: Gymnasium environment, optional `rl` extra and API validation

- **Who:** user of this session; the message does not name its author (repo-local identity
  `mavp309`). AI assistance: Claude Code (Anthropic) wrote the code, tests and documentation,
  pending team review. No commit or push.
- **Instruction:**
  - Build the Gymnasium environment from the M5.1 parts, with no second accounting
    implementation.
  - Add the `rl` extra and the `rl` marker.
  - Validate on the training split only.
  - No PPO training, throughput test, EXP-002 rerun or installation, and no change to Gate 2.
- **Work done:**
  - `environment/portfolio_env.py`: `PortfolioEnv` and `make_training_env`. Each `step`
    advances `simulator.step` (D-067) to the next weekly decision (D-065) and returns the
    decision-aligned reward (D-064).
  - `pyproject.toml`: the optional `rl` extra (`gymnasium>=1.4,<2`, `stable-baselines3>=2.9,<3`,
    `torch>=2.8,<3`) and the `rl` pytest marker. CPU-only install instructions are in the
    README and handbook §1. CI is unchanged (`.[dev]` only).
  - Implementation choices and the action-space question are recorded as **D-072
    (Proposed)**.
- **Failures met and how they were resolved (no test was weakened):**
  1. **Collection error** "'rl' not found in markers": expected under `--strict-markers` until
     the marker was registered.
  2. **A wrong-length action** passed the softmax check and failed later in the simulator
     with `SimulationError`.
     - **Environment fixed:** the action shape is now checked against `action_space` first
       (`ActionError`).
     - `step` was also made atomic: ledger rows are committed only after the whole step
       succeeds.
  3. **The `unavailable`-regime test** put the label on a non-decision row, which the
     environment correctly never encodes. The test now targets a decision row; the property
     tested is unchanged.
  4. **Real-data check "post-trade weights == targets" (exact):**
     - 84 of 496 steps differed, by at most 1.1e-16.
     - Cause: the milestone-4 simulator renormalises executed weights (`post / post.sum()`).
       The environment's `target` is the requested target before that.
     - The check and the synthetic test now compare within 1e-15, as the M5.1 check did. This
       is documented in D-072 and the handbook.
- **Correction before reporting:** a first draft of D-072 said a `[−1, 1]` action space would
  limit any asset to about 35 %. Recomputed, the largest proposal is about 51 % and the
  smallest about 1.9 %. The text was corrected.
- **Checks run (actual results):**
  - **Real data, training split only:** `make_training_env` (train-only loading) passed 26
    checks.
    - **`check_env`:** passed, with only two known warnings: SB3's normalised-action-space
      recommendation (D-072 open question) and no registered spec for render modes.
    - **Spaces and episode:** `Box(51,)` and `Box([−5, 5]^8)`, both `float32`. One episode has
      496 steps; `terminated` is True only on the last, and `truncated` is never set.
    - **Observations:** 497 observations, all finite and inside the space; the reset
      observation is all cash.
    - **Dates and timing:** every info date is before 2017-01-01, and the last step ends on
      2016-12-30. Every execution is at decision + 1.
    - **Exactness:**
      - the environment's ledger is bit-identical to `simulate`;
      - its rewards are exactly equal to `decision_aligned_rewards`;
      - the telescoping residual is 7.2e-16;
      - episodes are deterministic.
    - **Carried over from M5.1:** the scaler and clip counts are the same.
    - No throughput or timing was measured, and no performance figure was reported.
  - **pytest (`rl` extra present):** 799 passed: 793 before M5.2, plus 5 environment tests and
    1 core-import guard.
  - **pytest with Gymnasium, SB3 and torch blocked** (to imitate CI; nothing uninstalled): the
    `rl` module was skipped cleanly ("could not import 'gymnasium'"): 794 passed, 1 skipped.
  - `pytest -m rl`: 5 passed, 794 deselected. Ruff check and format check passed (71 files).
    `validate_config.py` passed (exit 0). The M5.1 refactor parity script was rerun:
    byte-identical.
- **Not done:** no PPO training, no throughput test, no EXP-002 rerun, no validation or test
  data read, no installation, CI workflow unchanged, Git configuration unchanged.

---

## 2026-10-19 (continued): M5.1: RL environment building blocks and train-only integration check

- **Who:** user of this session; the message does not name its author (repo-local identity
  `mavp309`). AI assistance: Claude Code (Anthropic) wrote the code, tests and documentation,
  pending team review. No commit or push.
- **Instruction:** implement M5.1 with targeted tests only, then check it on the real dataset
  using the training split only. No validation or test values, no EXP-002 rerun, no PPO
  training, no throughput test, no new dependency, and no change to the Gate 2 decisions.
- **Work done:**
  - **Simulator (D-067):** `PortfolioState`, `StepRecord` and `step` in
    `evaluation/simulator.py`. `simulate` now loops over `step`.
    - Error messages are unchanged.
    - `validate_target`'s signature is unchanged; it delegates to a private `_check_target`.
  - **Weekly schedule (D-065):** `decision_rows("weekly", ...)` uses ISO weeks, and `weekly`
    was added to `REBALANCE_SCHEDULES`.
  - **New package code** in `environment/`:
    - `actions.py` (D-063);
    - `observation.py`: training-only `FeatureScaler` with a JSON artifact, ±10 clipping with
      counts, one-hot regimes and the 51-input observation (D-062);
    - `rewards.py`: weekly episode decisions, reward intervals and the decision-aligned reward
      (D-064).
  - **Loaders:** a `train_only` keyword for `load_processed_inputs` and
    `load_feature_outputs`. Defaults are unchanged; the private `_read_splits_before_test`
    became `_read_splits_before(path, config, stop)`.
  - **Clarifications** settled in code are recorded as **D-071 (Proposed)**:
    - scaler `ddof=0`;
    - out-of-bound actions raise;
    - the reward requires lag ≥ 1;
    - train-only loading;
    - `weekly` as a schedule value.
- **Test change to note:** `test_invalid_strategy_entries` used `weekly` as an example of an
  *invalid* schedule. Weekly is now valid by design (D-065, memo §13 item 3), so the example
  became `quarterly`. The invalid-input check itself is kept.
- **Checks run (actual results):**
  - **Refactor parity:** `simulate` outputs from before the refactor were saved and compared
    after it, on 12 random synthetic configurations (one-off script in `%TEMP%`). Ledgers and
    executions were byte-identical.
  - **pytest:** 793 passed (780 before; 13 new tests, 1 updated). Ruff check and format check
    passed (69 files). `validate_config.py` passed.
  - **Integration check, training split only:**
    - Inputs: dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`, loaded with
      `train_only=True` (2,517 rows, 2007-01-04 to 2016-12-30). No row dated on or after
      2017-01-01 was loaded.
    - Episode: `k0` = row 125 (2007-07-05), `x0` = 2007-07-06, `e` = 2016-12-30. There were
      496 weekly decisions (2007-07-05 to 2016-12-27) and 2,391 ledger rows.
    - Scaler: fitted on 2,389 training rows (2007-07-05 to 2016-12-27). 8 values were clipped
      over rows `k0..e`: SPY_ret_1 1, EEM_ret_1 1, LQD_ret_1 3, equity_ret_1 1, xs_dispersion 2.
    - Regime labels at decisions: only the 9 valid labels; `unavailable` never occurred.
    - A random-action episode (seed 42, uniform actions, no learning) passed 25 checks,
      including:
      - observations of shape (496, 51), all finite;
      - observed weights equal to the end-of-row ledger weights;
      - executed weights equal to the projected targets;
      - one execution per decision, at `d + 1`;
      - sequential `step` values bit-identical to `simulate`;
      - sequential rewards exactly equal to `decision_aligned_rewards`;
      - a telescoping residual of 6.7e-16;
      - the funding cost charged inside `r_0`.
    - No performance figures were computed for reporting. The random policy has no meaning as
      a strategy.
- **Not done:** no Gymnasium environment (M5.2), no PPO training, no throughput smoke test, no
  EXP-002 rerun, no validation or test data read, nothing installed, `pyproject.toml`
  unchanged, Git configuration unchanged.

---

## 2026-10-19 (continued): Gate 2 defaults accepted; RL libraries installed into the local `.venv`

- **Who:** user of this session; the message does not name its author (repo-local identity
  `mavp309`). AI assistance: Claude Code (Anthropic). No commit or push.
- **Gate 2:** a team member approved D-062 to D-069 as the working design for PPO implementation.
  - Recorded as **Accepted (2026-10-19)** under R-S (D-061). The other teammate's confirmation was
    not sought.
  - The checklist's Gate 2 row is filled in, and a note was added to `ppo_design_proposal.md` §15.
  - Bootstrap settings (#10) and the stress-window protocol (#11) stay **open for Gate 3**. No
    values were proposed, and the sealed test period was not used. D-070 stays Open.
- **Installation (authorised by the team member):** packages were installed into the existing
  project `.venv` (Python 3.13.7, pip 26.2.1, Windows) using the CPU-only PyTorch index
  (`--index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple`).
  - NumPy, pandas and PyYAML were held at their existing versions by a constraints file.
  - The package inventory was saved before installing, outside the repository (in `%TEMP%`), and a
    dry run was done first.
  - Installed: `stable_baselines3==2.9.0`, `torch==2.14.1+cpu`, `gymnasium==1.4.0`, plus 10 new
    transitive packages: cloudpickle 3.1.2, Farama-Notifications 0.0.6, filelock 4.2.4, fsspec
    2026.9.0, Jinja2 3.1.6, MarkupSafe 3.0.4, mpmath 1.3.0, networkx 3.7, setuptools 84.0.0, sympy
    1.14.0.
  - Before/after `pip freeze` diff: additions only. No existing package was upgraded, downgraded or
    removed.
  - filelock resolved to 4.2.4, newer than the 4.2.2 in the earlier disposable dry run.
- **Checks run (actual results):**
  - Versions verified by import: numpy 2.5.4, pandas 3.0.6, PyYAML 6.0.3, torch 2.14.1+cpu (no CUDA
    build; `cuda.is_available()` False), gymnasium 1.4.0, SB3 2.9.0. `from stable_baselines3 import
    PPO` succeeds.
  - `pip check`: no broken requirements.
  - pytest: 780 passed. Ruff check and format check passed (65 files). `validate_config.py` passed.
  - This shows that the libraries import and coexist with the existing suite. It does **not** show
    that SB3 runs correctly with project code: no environment or training run exists yet.
- **Not changed:** `pyproject.toml` (the version bounds are proposed, not applied), so CI and fresh
  clones do not install these libraries yet. Git configuration unchanged.
- **Not done:** no PPO training, no environment code, test period not accessed.

---

## 2026-10-19 (continued): Approval rule R-S; Gate 2 defaults recorded as Proposed

- **Who:** user of this session; the messages do not name their author (repo-local identity
  `mavp309`). AI assistance: Claude Code (Anthropic). No commit or push.
- **Governance:** a team member communicated a simplified rule: a task or decision communicated
  by either teammate is treated as approved by both, from now on.
  - It is recorded as **D-061 (Accepted)**, stating that the author was not named and that the
    other teammate's confirmation was not sought (as the rule provides).
  - The Gate 1 record under A-1, including its one-message deviation, is unchanged.
  - The review's earlier recommendation, R1 (confirmations from each teammate's own GitHub
    account), was not adopted.
- **Gate 2:** the packet's recommendations are recorded as proposed defaults D-062 to D-069, all
  **Proposed**.
  - Explainability was added as checklist item #17, stated as indicating associations, not
    causation.
  - Bootstrap details and stress windows stay open until before Gate 3.
  - Commit authorship is **Open** (D-070), with the actual identities recorded.
  - Notes were added to D-012, D-014, D-016 and D-017.
- **Git configuration:** unchanged, as instructed.
- **Not done:** no PPO, no training, nothing installed into `.venv`, `pyproject.toml`
  unchanged, test period untouched.

---

## 2026-10-19 (continued): Status wording aligned with Gate 1; Gate 2 decision packet (no experiment run)

- **Who:** user of this session (repo-local identity `mavp309`). AI assistance: Claude Code
  (Anthropic). No commit, push, install, download, approval or status change.
- **Status wording corrected** (README, technical handbook, roadmap, presentation guide,
  research protocol):
  - the accepted Gate 1 decisions are distinguished from the provisional data-value
    acknowledgments (D-006, D-008, D-034, D-042, D-044);
  - Gate 2 is still pending;
  - accepted items cite the self-declared, single-message confirmation caveat.

  The research protocol keeps its original header below a dated update note.
- **Audit:** the decision-log diff removes only:
  - 29 summary-table status cells;
  - 24 entry status lines;
  - 21 "Approved by: —" placeholders;
  - D-031's old status continuation line;
  - 4 blank lines.

  No decision text was removed. EXP-002 output and config hashes, the dataset id and the split
  boundaries still match the experiment log; it was not rerun.
- **Gate 2:** a 16-item decision packet was added to the checklist, with dependencies. Items
  flagged as unresolved: reward alignment, bootstrap details, the stress-window rule and source
  (its dates must not be derived from the project's own test-period data), and attribution plus
  the approval channel for Gate 2. Every decision field is blank.

---

## 2026-10-19 (continued): Gate 1 confirmed and recorded; EXP-002 executed and verified

- **Who:** user of this session (repo-local identity `mavp309`). Named confirmations were
  received from Parv Patel and Mandar Patil, self-declared in this shared-device session.
  AI assistance: Claude Code (Anthropic). No commit or push.
- **Approval evidence:**
  - Both teammates adopted amendment A-1 and confirmed the whole §0 package (D-023 N = 252, no
    amendments) in named first-person statements dated 2026-10-19.
  - Both statements arrived in **one** conversation message, whereas A-1 asks for one message
    per teammate. This is disclosed in the checklist and the decision log rather than waived
    silently.
  - Recorded verbatim in checklist §0.1.
- **Decision log:**
  - Accepted: D-007, D-009, D-015, D-023, D-031 (cost basis and no cap only; the cap measure
    stays Open), D-035–D-039, D-048–D-059; D-010 and D-013 (resolved by D-053 and by
    D-048 + D-055, G-P (a));
  - new D-060 (test-period isolation, G-T (a));
  - D-006, D-008, D-034, D-042 and D-044 stay Proposed with provisional-acknowledgment notes;
  - every approval line carries the self-declared-identity caveat.
- **Config:** `periods_per_year: 252`. Config status comments were updated; no other value
  changed.
- **Test updated:** `test_default_backtest_config_is_valid` asserted
  `periods_per_year is None` ("D-023 open"). It now asserts 252, the accepted value.
- **Pre-flight:**
  - 780 tests passed after that update; Ruff and format clean; config and market-data
    validation passed; `git diff --check` clean;
  - dataset `8e00568ee2aa4de7` confirmed;
  - expected id `c6d8c473258e3194`.
- **EXP-002:** ran with exit 0 and wrote `data/processed/backtests/c6d8c473258e3194/`.
  - Every runbook §5 check passed, including recomputing every ledger row.
  - The first version of my verification script compared funding notional to exactly 1.0 and
    failed: 7 × 1/7 = 0.9999999999999997 in floating point. The check was corrected to a 1e-12
    tolerance; the outputs were not changed.
  - An identical re-run was byte-identical.
  - Results are in `experiment_log.md` EXP-002; descriptive only.
- **Test split:** not used, and no test-period return value was parsed.

---

## 2026-10-19 (continued): Proposed amendment A-1 to the approval-identification rule (no approval recorded)

- **Request:** the team asked whether written confirmations in this conversation can serve as
  approval evidence.
- **Finding:**
  - `decision_log.md` requires only "Approved by" and "Date", and states that only the team may
    approve.
  - Checklist §0.1, kept by the team, additionally requires identification "bound to the person,
    not to this device", through "a channel tied to the individual". In-conversation messages on
    the shared device do not meet that clause.
- **Action:** added **Amendment A-1 (PROPOSED)** to §0.1. Named, separate, verbatim-recorded
  written confirmations in the Claude Code conversation count, with the disclosed caveat that
  author identity is self-declared and not technically verified.
  - It takes effect only when both teammates adopt it in their own named messages.
  - It is not retroactive.
- **Unchanged:** approval rows blank, decision log and configs untouched, EXP-002 not run.

---

## 2026-10-19 (continued): Unnamed in-session confirmation received (no approval recorded)

- A first-person confirmation of the whole §0 package (including G-T (a), G-P (a) and D-023
  N = 252, dated 19/10/26) was received in this session. It is recorded verbatim in checklist
  §0.1.
- It names no teammate and came through the shared-device session, so it fills neither §0.1
  row. It could be at most one of the two required confirmations.
- No decision recorded, no config change, EXP-002 not run.

---

## 2026-10-19 (continued): Joint agreement reported; awaiting identifiable confirmations (no experiment run)

- **Who:** user of this session (repo-local identity `mavp309`). AI assistance: Claude Code
  (Anthropic). No commit, push, approval or status change.
- **Reported:** the session's user stated that Parv Patel and Mandar Patil reviewed the latest
  changes together. According to that statement, both agree with the entire recommended Gate 1
  package, including G-T (a), G-P (a) and D-023 N = 252, and asked for EXP-002 to proceed
  within the repository's governance.
- **Not recorded as approval:** checklist §0.1, kept by the team, requires each row to be
  filled only by the named person, through a channel tied to that individual; a single report
  from the shared device does not identify each person. So:
  - the §0.1 rows remain blank;
  - `decision_log.md` is unchanged;
  - `configs/backtest.yaml` still has `periods_per_year: null`;
  - EXP-002 was not run.

  A dated note and confirmation text were added to §0.1.
- **Technical pre-flight completed (no run):**
  - tests: 780 passed; Ruff check and format; config and market-data validation;
    `git diff --check`;
  - dataset `8e00568ee2aa4de7` (raw `e27437b97742fa43`, yfinance 1.7.0, retrieved
    2026-10-15T10:21:14Z) is the intended snapshot; no rebuild or download is needed;
  - the expected output id with N = 252 is `c6d8c473258e3194` (not present);
  - the command parses with `include_test = False`.

---

## 2026-10-19 (continued): Pre-commit review of the 11-file diff (no approval recorded)

- **Who:** user of this session (repo-local identity `mavp309`). AI assistance: Claude Code
  (Anthropic). No commit, push, approval or status change.
- **Issues found and fixed:**
  1. §0.1 accepted "own commit hash" as identification. On the shared device the repo-local
     identity is `mavp309` for whoever types, and pushes appear under the `Parvptl` account, so
     a commit does not identify a person. Identification must now use a channel bound to the
     individual, and each row is filled only by the named person.
  2. §0.1 said to record "acknowledged provisional", which is not a decision-log status. Those
     items now keep "Proposed (provisional)" with a dated acknowledgment note (§0.1, §1.3).
  3. The Gate 1 summary (§1.6) now mentions the §0.1 route.
  4. The checklist and runbook headers claimed their content was "committed in `8e52693`";
     they now say "first committed in", with a pointer to git history.
  5. The annualised status printed "N = 252.0"; it now prints "N = 252", and the tests assert
     the exact phrase.
- **Approvals:** both §0.1 rows and all §1 fields are blank, and the decision log is unchanged.
  EXP-002 has not been run.

---

## 2026-10-19 (continued): Package-confirmation option added (no approval recorded)

- **Who:** user of this session (repo-local identity `mavp309`). AI assistance: Claude Code
  (Anthropic). No commit, push, approval or status change.
- The user supplied a recommended Gate 1 package. It matches the recommended defaults already
  in checklist §0, item for item, including keeping D-015 and D-031 consistent on "no turnover
  cap".
- **Added checklist §0.1:** an optional one-step confirmation of that package. It applies only
  when **both** teammates confirm, identifiably, with matching D-023 choices. Amendments send
  items back to individual decisions in §1.
- **Fields are blank.** A recommendation is not an approval. The decision log is unchanged, and
  EXP-002 remains blocked.

---

## 2026-10-19 (continued): Output status text made approval-neutral; Gate 1 packet (no experiment run)

- **Who:** user of this session (repo-local identity `mavp309`). AI assistance: Claude Code
  (Anthropic). No commit, push, install, download, approval or status change.
- **Defect found during the EXP-002 readiness check:** backtest outputs hard-coded approval
  states:
  - `metrics.json` and report status: "PROVISIONAL: conventions D-048 to D-057 are Proposed";
  - annualised status: "provisional (D-023 not accepted)";
  - conventions text: "proposal for D-013 / D-031", "proposed primary convention";
  - CLI line: "under provisional conventions".

  Once the team accepts those decisions, EXP-002's outputs would have misstated their status.
- **Fix:** neutral wording that states the facts and points to `docs/decision_log.md` for
  approval status. Decision ids are kept for traceability. The research conventions, the
  computed values and the output ids are unchanged (the ids do not hash this text). Tests now
  assert that no approval status is claimed.
- **Docs:**
  - checklist §0: a concise Gate 1 approval packet with recommended defaults, explicitly not
    approvals;
  - runbook verification item 9a;
  - handbook outputs row.
- **Checks:** see the session report.

---

## 2026-10-19 (continued): State after `8e52693`; status wording corrected (no experiment run)

- **Who:** user of this session (repo-local identity `mavp309`). AI assistance: Claude Code
  (Anthropic). No commit, push, install, download, approval or status change.
- **Verified:**
  - `main` = `origin/main` = `8e52693` (local refs). GitHub Actions run #8 passed on
    `8e52693`, which includes `a717f34` and `a03c4b7` (neither had a run of its own).
  - Clean tree; the backup branch is still at `4b37aae`.
- **Correction (append-only):** the entries below describe the boundary code, checklist and
  runbook as "local, uncommitted". They were true when written; the work was committed in
  `8e52693` and pushed. Current-status wording was updated in the README, architecture,
  checklist and runbook.
- **Audit:**
  - the bounded loaders were re-read; no defect found;
  - `validate` reads configuration only;
  - the `features` command still reads all rows (milestone-3 behaviour), but EXP-002 does not
    use it;
  - boundary regression tests: 18 passed; full suite: 780 passed.
- **EXP-002 re-verified** without running it:
  - command, test split off, dataset `8e00568ee2aa4de7`;
  - lag 1, window 126, the three baselines, 10 + 5 bps, cap 0.40, rf 0, funding charged;
  - expected output `ce46d29217983c40` (not present), or `c6d8c473258e3194` with N = 252.
- **Blocked:** no approval evidence in the checklist or the decision log.

---

## 2026-10-19 (continued): Bounded feature loading for later modelling (no experiment run)

- **Who:** user of this session (repo-local identity `mavp309`). AI assistance: Claude Code
  (Anthropic). No commit, push, install, download, approval or status change.
- **State verified:**
  - no Gate 1 or Gate 2 approvals recorded;
  - gymnasium, Stable-Baselines3, PyTorch, matplotlib, streamlit, SHAP, scipy and sklearn are
    **not installed**;
  - the `agents`, `environment`, `explainability` and `visualization` modules are
    placeholders.
- **Finding:** the milestone-3 feature artifact (`a79347e37e653703`) contains test-period
  feature rows, and no loader bounded them. A later agent reading `features.csv` directly would
  bypass the test boundary.
- **Change:** `features.pipeline.load_feature_outputs(...)`, safe by default. It parses only
  rows dated before `test.start` (the bound comes from the dataset's `splits.csv`) and checks
  the dataset id, the headers (before parsing), and the dates and labels.
- **Tests:** 5 new tests on synthetic data:
  - bounded rows equal the prefix of a full read;
  - corrupted test rows are never parsed (control: a full read fails on them);
  - a different dataset, a missing row and a bad header are rejected.

  Injected bug (`exclude_test` ignored): 2 tests fail.
- **Not done, and why:**
  - **EXP-002:** no approvals.
  - **PPO environment and training:** Gate 2 decisions are not approved (observation, reward,
    projection, frequency) and the RL dependencies are absent.
  - **Dashboard:** an optional extension ([O]) needing approval, and no UI dependency is
    installed.
  - **Explainability, bootstrap, stress tests:** these depend on a trained model and on
    unapproved Gate 2 parameters.
  - **Walk-forward:** D-018 is open; not implemented.
  - **Final report:** no results yet.
  - **Raw-snapshot checksum verification:** not run, because hashing the raw files would read
    test-period bytes (G-T is not agreed).

---

## 2026-10-19 (continued): Boundary strengthened; Gate 2 matrix (no experiment run)

- **Who:** user of this session (repo-local identity `mavp309`). AI assistance: Claude Code
  (Anthropic). No commit, push, approval or status change.
- **Re-audit finding:** the bounded loader stopped at the first row **labelled** `test`. A
  test-period row mislabelled `validation` would have had its return values parsed before the
  label check failed.
- **Fix:** the stop is now the first row **dated** on or after the configured `test.start`. Its
  label must match the configuration, and an error is raised before `returns.csv` is opened.
- **Tests:**
  - added: a mislabelled test-period row; the CLI `backtest --dataset-dir` boundary;
  - injected-bug check: restoring the label-based stop fails exactly the new test.
- **Docs:**
  - runbook: what the command reads and writes, and hashing vs parsing;
  - checklist: G-T wording;
  - handbook: interface row;
  - PPO proposal: §14 decision matrix.
- **Approvals:** none present. EXP-002 is blocked.

---

## 2026-10-19: Test-data boundary for the baseline backtest (no experiment run)

- **Who:** requested by the user of this session (repo-local Git identity `mavp309`; global
  `Parvptl`). AI assistance: Claude Code (Anthropic). Nothing was committed or pushed, and no
  approval or decision status changed.
- **Finding:** the baseline backtest loaded the whole `returns.csv` and `splits.csv`, test
  period included, for data-contract checks, and the simulator checked every row for
  finiteness. Test rows were never simulated or reported, but their values were parsed.
- **Change:** the default run (no `--include-test`) now uses bounded loading via
  `load_processed_inputs(..., exclude_test=True)`, `data.cache.read_csv_head` and
  `data.splits.label_dates`.
  - It reads `splits.csv` up to the first test row (checking that row's date) and only the
    matching `returns.csv` rows. **Test-period return values are never parsed.**
  - All contract checks run on the rows read.
  - `--include-test` and the feature pipeline are unchanged.
  - Details: `exp002_runbook.md` §4.
- **Tests:** `test_multi_session_returns_refused` was updated, because its 2-session return lies
  in the test period:
  - with `--include-test` it is still refused;
  - by default the row is never reached, which is asserted.

  Added:
  - corrupted test rows give byte-identical results, while an `--include-test` run fails on
    them;
  - a `returns.csv` without any test rows gives byte-identical results;
  - 5 integrity cases in the permitted rows;
  - a `read_csv_head` unit test.

  Two injected bugs were caught (temporary copy; targeted check).
- **Data access:** synthetic test data only. The live dataset was not read; nothing was
  downloaded or installed.
- **Open:** the team's G-T choice and review of this code. The rest of Gate 1 is unchanged.

---

## 2026-10-18: EXP-002 preparation (approval gate not met; no experiment run)

- **Who:** requested by the user of this session (the repository-local Git identity is
  `mavp309`; the device's global identity is `Parvptl`). AI assistance: Claude Code
  (Anthropic). Nothing was staged, committed or pushed. No Git identity was changed.
- **Milestone:** 4.2 follow-up. No decision was accepted, and **EXP-002 was not run**.

**Correction (append-only):** the milestone-4.2 entry below says "4.2, local". Since then the
work was committed as `817f8b8` and pushed, and GitHub Actions CI run #7 passed on it (checked
on the public Actions page on 2026-10-18).

**Starting state (verified):**
- `main` at `817f8b8`, equal to `origin/main`; clean tree; no stash.
- The backup branch is still at `4b37aae`. `Abstract.pdf` and `tatus` are unchanged.
- 762 tests passed.

**Work done**
- Current-status lines still calling milestone 4.2 "local / not committed" were corrected
  (README, roadmap, presentation guide, research protocol).
- **Test A (integration):** an end-to-end test builds the feature set and the backtest from
  one synthetic dataset. It checks that:
  - the first decision is the first row with every feature available (a 15-row warm-up that
    dominates the strategy lookbacks);
  - execution and the first earned return follow `timing.py` at lag 1;
  - split boundaries hold, with no test rows by default;
  - every strategy shares identical dates.
- **Test B:**
  - the funding cost stays in `total_cost_fraction`, `total_cost_value` and the net value path,
    while annualised turnover excludes funding;
  - funding-only and zero-cost boundary cases.

  At zero cost, `cost_drag` is about 2e-16 rather than exactly 0. The two value paths multiply
  in a different order, so this is rounding noise. The exact properties (net = gross on every
  row, cost totals of 0) are asserted, and `cost_drag` is compared with a 1e-12 tolerance. The
  accounting was not changed.
- **Injected-bug check of the new tests** (temporary copy outside the repository):
  - control: 3 passed;
  - common window ignored: Test A failed;
  - funding cost dropped from the totals: both Test B tests failed.

  This is a targeted check, not mutation testing.
- **New document:** `docs/ppo_design_proposal.md`, **PROPOSED — NOT APPROVED**. It covers
  simulator integration, observation, scaling, projection, reward, frequency, library, seeds and
  budget, evaluation, and pre-registration. Its decision-date counts come from the dates and
  split labels of train and validation only.

**EXP-002 approval gate:** not met. D-007, D-009, D-015, D-023, D-031 (cost basis and cap
measure), D-048–D-059 (including D-053, D-055, D-058 and D-059) are all still Proposed or Open
in the decision log. EXP-002 was therefore not run, and no experiment record was added.

**Checks run:** see the session report (full suite, Ruff, format, config validation,
`git diff --check`).

**Data access:** no external data was fetched, and no test-split rows were read. The local
processed dataset's dates and split labels were read for train and validation only.

---

## 2026-10-18: Milestone 4.2: research-protocol preparation before PPO

- **Who:** Mandar Patil, by his own statement in the session, working on Parv Patel's device
  (global Git identity `Parvptl`). At his request this repository's local Git identity was set to
  `mavp309 <mandar.avp@gmail.com>`, which is used as author and committer of the milestone-4.2
  commit; the device's global Git configuration was not changed. AI assistance: Claude Code
  (Anthropic). It first ran a read-only protocol audit, then implemented the preparatory work in
  the milestone-4.2 brief.
- **Milestone:** 4.2, local. No research decision was accepted. D-058 and D-059 are new and
  **Proposed**.

**Correction to earlier entries (append-only)**

- On 2026-10-18 the two milestone-4 commits were rewritten with changed author and committer
  metadata and force-pushed: `a7134b7` → `66f9ed7` (simulator and baselines) and `4b37aae` →
  `880d82c` (4.1 hardening). The file trees are identical. The original commits, with their
  original metadata, remain on the local branch `backup/main-before-author-rewrite`.
- The 2026-10-15 and 2026-10-18 entries below cite `a7134b7` and `4b37aae`. Those hashes are the
  pre-rewrite originals, and their statements were true when written.
- GitHub Actions: run #3 passed on `a7134b7`, run #4 on `4b37aae`, run #5 on `b4234c9` (an
  intermediate rewrite), and run #6 on `880d82c` (checked on the public Actions page,
  2026-10-18). There is no separate run for `66f9ed7`.
- The entries' "Who" lines (sessions run under Git identity `Parvptl`) are unchanged.
- The milestone-4.2 audit raised a question: the rewritten author and committer metadata
  conflicts with these records and with the team's stated commit policy. It is left for the
  team to resolve; this session changed no metadata.

**Starting state (verified)**

- `main` at `880d82c`, equal to `origin/main`; clean tree; no stash.
- The backup branch's tree is identical to `main`.
- 749 tests passed.
- `Abstract.pdf` `ac701b0c…` and `tatus` `59fb61c3…`, both unchanged at the end.

**Work done**

- `docs/research_protocol.md`: **DRAFT / NOT APPROVED**. It holds the audit's recommendations,
  with facts, recommendations and open questions separated.
- Common evaluation window (D-058, Proposed):
  - new `backtest.common_start_history_sessions` key (1 if omitted) and
    `BacktestConfig.required_history`;
  - `check_feature_warm_up`, run by the CLI whenever `features.yaml` exists;
  - `configs/backtest.yaml` sets 126;
  - the windows record `required_history_sessions`;
  - only the training window moves, from row 62 to row 125.
- Funding turnover (D-059, Proposed):
  - new `funding_traded_notional` and `recurring_traded_notional` keys, also in `metrics.csv`;
  - the opt-in `annualised_traded_notional` now uses recurring trades only;
  - `periods_per_year` stays `null`.
- Docs:
  - status lines with stale hashes corrected (README, roadmap, presentation guide);
  - append-only notes in the experiment log and this journal;
  - D-031 status made consistent: cost basis Proposed, cap measure Open, nothing accepted;
  - the handbook (§13.5, §13.7, §13.9, §13.11), architecture and glossary.
- `configs/experiment.yaml`: comments only.
  - `output_dir` and `walk_forward` are **not used by any code**;
  - only `reports/figures/` is git-ignored, so the earlier comment "(kept out of Git)" was
    inaccurate.
  - No value changed.
- **Not done (approval gates):**
  - no decision accepted;
  - `periods_per_year` not set;
  - no PPO, reward choice or tuning;
  - no live-data run and no `--include-test`;
  - no old output folder or branch deleted.

**Checks run (actual results; main `.venv`, Python 3.13.7)**

- `python -m pytest`: **762 passed**, i.e. 749 + 13 new: baselines +8, simulator +2,
  pipeline +3.
- Ruff check: passed; Ruff format check: all files formatted.
- `scripts/validate_config.py`: OK; `market_data.py validate`: OK, with the feature-warm-up
  check active.
- `git diff --check`: clean.
- **Not run:** the minimum-version environments; CI on these changes, which are not committed.

**Open / next approvals**

- The team decides the items listed in `research_protocol.md` §14.
- Then a primary-convention baseline run (lag 1, 126-session window) on train and validation,
  recorded as EXP-002.
- Then milestone 5 (PPO).

---

## 2026-10-18: Milestone 4.1: backtest hardening and research-protocol corrections

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code (Anthropic).
  It first ran a read-only audit of milestone 4, then implemented the corrections from the team
  member's milestone-4.1 brief. Nothing was staged, committed or pushed.
- **Milestone:** 4.1, implemented and tested locally. New decisions D-055 to D-057 are
  **Proposed**. D-023 remains open.

**Corrections to earlier entries (append-only)**

- The 2026-10-15 milestone-4 entry says that work was uncommitted and that GitHub Actions had not
  run. Since then, milestone 4 was committed as `a7134b7` and pushed (`main` = `origin/main`).
  GitHub Actions CI run #3 passed on `a7134b7`; this was re-checked on the public Actions page on
  2026-10-18.
- Milestones 2 and 3 (`1a289ab`, `adffff5`) were pushed together with it. CI ran on the head
  commit only.

**Read-only audit (2026-10-18; no repository files changed, verified with a full SHA-256
fingerprint)**

- 692 tests passed.
- The milestone-4 backtest was reproduced byte-for-byte from `a7134b7` in an isolated copy.
- No leakage and no accounting defect were found. The hand-calculated cost cases all matched.
- Findings addressed here:
  1. the cap is enforced only on targets (drift up to about 0.41);
  2. test-split results were produced and printed by default;
  3. the milestone-3 alignment helper had no execution lag;
  4. the direct `simulate()` API accepted negative or NaN cost rates, and NaN propagated
     silently;
  5. the ledger weight semantics were undocumented;
  6. the order-`k²` cost-basis approximation was undocumented;
  7. stale config comments and docstrings;
  8. the funding-row treatment in metrics was unclear;
  9. EXP-001 and journal records were stale.
- The audit's 16 injected bugs were all caught, except one that is equivalent by construction:
  `ddof` cancels in normalised inverse-volatility weights.

**Starting state (independently verified before changes)**

- `main` at `a7134b7`, equal to `origin/main`; clean tree; no stash.
- 692 passed.
- `Abstract.pdf` SHA-256 prefix `ac701b0cbe949ce1`; `tatus` prefix `59fb61c3202ba1b1`; both
  unchanged at the end.

**Work done**

- **Timing (D-055):**
  - New `src/adaptive_portfolio/timing.py` holds the single decision → execution → earned-row
    implementation, used by the simulator, the backtest drop rule and
    `features.next_period_targets`.
  - `next_period_targets` gains `execution_lag_sessions` (default 0 keeps the milestone-3
    pairing) and a new `execution_date` column.
  - `backtest.execution_lag_sessions` is now **required**, with no default. This is an
    interface change: configs without it are rejected. `configs/backtest.yaml` sets 1, the
    proposed primary convention; lag 0 is the idealised sensitivity case.
  - The timing rule itself is unchanged.
- **Test split (D-056):**
  - `run_backtest(..., include_test=False)` and CLI `--include-test` on `backtest` and
    `backtest-report`.
  - By default only train and validation are evaluated, written and printed.
  - The evaluated splits are hashed into the id; `BACKTEST_PIPELINE_VERSION` is now 2.
  - The CLI prints the evaluated splits and a banner when test is included.
- **Settings validation:** `SimulationSettings.__post_init__` rejects:
  - non-finite or non-positive capital;
  - a cost rate outside `[0, 0.5)` or non-finite;
  - `cash_return` `<= −1` or non-finite;
  - non-bool flags;
  - invalid constraints, and a set `max_turnover` (which would otherwise be silently
    ignored);
  - booleans and strings as numbers.

  `simulate` also validates the lag and the settings type, and its value guard is now
  `isfinite(V) and V > 0`, so NaN can no longer propagate.
- **Cap semantics (D-057):** behaviour unchanged. Config comments, docs and the conventions text
  now state that the cap applies to target weights at execution and that holdings may drift
  above it.
- **Docs:**
  - stale comments in `environment.yaml` and the `metrics.py` docstring;
  - handbook §13: timing, four kinds of weights, valuation basis of the charge, funding-row
    treatment per metric, settings validation, evaluated splits, config table, tests;
  - decision log (D-055 to D-057, plus notes on D-043, D-048, D-050, D-051, D-054);
  - experiment log (append-only correction to EXP-001);
  - README, architecture, roadmap, glossary, presentation guide.
- **Not changed:** the cost formula, the strategy rules, the data pipeline, the metric
  functions (docstring only), the splits.
- **Not run:** a new backtest on the live data. No new results, lag 1 or otherwise, were
  produced, and no test-split figures were exposed.

**Findings / issues**

- Making the lag required changed the default from an implicit 0 to an explicit choice.
- With lag 1, each split drops `L + 1 = 2` boundary decisions for a daily strategy, and funding
  happens one row later.
- The local lag-0 output `data/processed/backtests/ac2d6b163d4f5e4b/` (pipeline version 1,
  includes test results) is still on disk, git-ignored. I did not delete it; the team may
  remove it.
- **Final read-only review before commit:** no code issues were found (timing helper,
  config compatibility, test-split isolation). Two documentation omissions were fixed:
  - the README's milestone-2/3 decision range left out D-008;
  - handbook §12.2 and the architecture did not say to pass the backtest's lag to
    `next_period_targets`, whose default 0 differs from the proposed primary lag 1.
  The default run still validates the whole return table, test rows included, for
  finiteness. This is an input-integrity check: no test value affects results.
- **Hand-picked injected-bug checks for 4.1** (temporary copy of the working tree; control: 0
  failures). The test split included by default, the evaluated splits missing from the id, the
  CLI flag ignored, the drop rule ignoring the lag, the alignment ignoring the lag, a same-bar
  first earned row, the old NaN-blind value guard, negative cost accepted, initial capital
  unchecked, `max_turnover` silently ignored, and the lag defaulting to 0 were each caught (1 to
  17 failing tests).

  One bug survived at first: a boundary check on the endpoints only. It is equivalent while
  partitions are contiguous, which the backtest enforces. A gap test was added and catches it.
  This is a targeted check, not mutation testing.

**Checks run (actual results; Windows, main `.venv`, Python 3.13.7)**

- `python -m pytest`: **749 passed**, i.e. 692 plus 57 new: baselines +3, simulator +31,
  pipeline +9, timing +14.
- `python -m ruff check .`: passed; `python -m ruff format --check .`: all files formatted.
- `scripts/validate_config.py`: OK; `market_data.py validate`: OK (execution lag 1).
- `git diff --check`: clean.
- Run with no bytecode or pytest cache; the test runs wrote nothing into the repository.
- **Not run:** the clean minimum-version environments (Python 3.12 and 3.13) and Python 3.11;
  GitHub Actions on these changes, which are not committed.

**Decisions**

- Proposed, awaiting team approval:
  - D-055 (lag 1 primary, lag 0 sensitivity, required key, shared timing);
  - D-056 (test opt-in);
  - D-057 (cap on targets at execution).
- Still Proposed: D-048 to D-054. Still open: D-023 and the turnover-cap measure (D-031).

**Next steps**

- Team review and approval of D-048 to D-057.
- If approved: a primary lag-1 run on train and validation (new EXP entry), and the lag-0
  sensitivity run.
- The team decides whether to delete the old version-1 output folder.
- Do not start milestone 5 (RL) before approval.

---

## 2026-10-15: Milestone 4: portfolio simulator and conventional baselines

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code (Anthropic)
  implemented the milestone from the team member's milestone-4 brief. Nothing was staged,
  committed or pushed.
- **Milestone:** team milestone 4, which covers the simulator part of roadmap 4 and the minimum
  set of roadmap 5. Implemented and tested locally. Decisions D-048 to D-054 are **Proposed**.
  D-010, D-013 and D-031 now point to those proposals and are not accepted. D-023 remains open.

**Starting state**

- `main` at `adffff5` (milestone 3), 2 commits ahead of `origin/main` (not pushed).
- Baseline before changes: 615 tests passed.
- The tracked stray `tatus` file is still present and untouched.

**Work done**

- `configs/backtest.yaml` and `load_backtest_config` / `BacktestConfig` / `StrategyConfig` in
  `config.py`. `ProjectConfig` is unchanged; unknown keys are rejected; cross-checks run against
  the universe and the constraints.
- `baselines/strategies.py`: target weights for equal weight, fixed weights and inverse
  volatility (water-filling cap), plus rebalancing schedules. No regime input.
- `evaluation/simulator.py`: timing with an execution lag, drift, traded-notional costs via the
  milestone-1 `portfolio_turnover(..., cash_column)`, cash, value, drawdown and a ledger. Invalid
  states raise errors; inputs are not mutated.
- `evaluation/performance.py`: gross and net window metrics using only milestone-1 functions.
  Per-session by default; annualised only when `periods_per_year` is set.
- `evaluation/backtest.py`:
  - independent simulation per split with a common start;
  - boundary decisions dropped;
  - deterministic outputs under `data/processed/backtests/<id>/`.
- CLI `backtest` and `backtest-report`; `validate` also checks `backtest.yaml`.
- 77 new tests: `test_baselines.py` 37, `test_simulator.py` 26, `test_backtest_pipeline.py` 14.
- Docs: decision log (D-048 to D-054, plus notes on D-010, D-013, D-023 and D-031), handbook
  §13, architecture, roadmap, README, glossary, presentation guide, and experiment log EXP-001.

**Findings / issues**

- **Live run** (processed `8e00568ee2aa4de7`, backtest `ac2d6b163d4f5e4b`):
  - completed offline; reruns are byte-identical;
  - the training split starts on 2007-04-04 after 62 warm-up rows; no decisions dropped.
  - Train and validation figures are in EXP-001 and are descriptive only.
- **Test split:** the command also evaluates the test split. The experiment log reserves
  test-period results for final, pre-registered evaluations, so test figures are **not recorded
  or discussed** in the docs. Whether test evaluation should be opt-in is an open question for the
  team (D-051).
- **Independent recomputation on the live data** agreed to about 1e-8:
  - buy-and-hold in closed form;
  - equal-weight monthly with a separate loop;
  - inverse-volatility weights by hand.
- **Net-return formula:** written as `g − c(1 + g)`. The algebraically equal `(1 + g)(1 − c) − 1`
  left about 4e-17 of noise at zero cost. The code was fixed, not the test tolerance. As a
  result, the live outputs changed at the floating-noise level after this fix; figures agree to
  the reported precision.
- **Hand-picked injected-error checks** (temporary copy of the package; control run passed):

  | Deliberate bug | Failing tests |
  | --- | --- |
  | weights earn the execution-day return | 1 |
  | costs charged on the cash leg | 3 |
  | no weight drift between rebalances | 3 |
  | cash earns nothing when rf ≠ 0 | 1 |
  | initial funding not charged | 3 |
  | boundary decisions kept | 9 |
  | no common start | 9 |
  | inverse-volatility cap not applied | 1 |
  | monthly schedule = every session | 1 |
  | `max_weight` not validated | 1 |
  | leverage allowed | 1 |
  | inverse-volatility window peeks one row ahead | 0 at first; 1 after the fix below |

  The "peeks one row ahead" bug was **initially missed**. The strategy-level future-invariance
  test passes the history slice explicitly, so it could not see a slicing error in the pipeline.
  `test_pipeline_weights_use_row_k_but_never_row_k_plus_1` was added: altering row *k + 1* must
  leave the decision weights unchanged, and altering row *k* must change them. Its first version
  failed on correct code (it assumed more validation decisions than the fixture has) and was
  rewritten. It now passes on the control and catches the bug. This is a targeted check, not
  systematic mutation testing; most bugs are guarded by a single test.
- **Minimum-version failure found and fixed:** `test_ledger_hand_calculated` failed under pandas
  2.2.0 / 2.2.3. A row cross-section of the mixed-dtype ledger is `object` dtype there, but
  `float64` in pandas 3. The ledger columns themselves are `float64` in both versions; only the
  test's selection was affected. The test now converts with `to_numpy(dtype=float)`.
- **Doc correction before finishing:** the first draft of handbook §13 described two things
  wrongly, and both were corrected:
  - a simulator check that does not exist;
  - a timing test as "perturbing all earlier returns", where it actually uses a return spike on
    the execution day.

**Checks run (actual results; all local, Windows)**

- **Main `.venv`** (Python 3.13.7, numpy 2.5.4, pandas 3.0.6):
  - pytest: **692 passed**, i.e. 615 + 77;
  - Ruff check: passed, after fixing one RUF059 unused variable in a new test;
  - Ruff format check: 59 files formatted;
  - `scripts/validate_config.py` OK; `market_data.py validate` OK (backtest.yaml checked).
- **Clean Python 3.12.1 at the declared minimums** (numpy 1.26.0, pandas 2.2.0, PyYAML 6.0.2,
  pytest 8.0.0, ruff 0.6.0): **692 passed** after the fix above (1 failed before it). There is 1
  warning: pandas 2.2.0's pyarrow deprecation notice. Ruff 0.6.0 check passed; 49 files
  formatted.
- **Clean Python 3.13.7** (numpy 2.1.0, pandas 2.2.3, PyYAML 6.0.2, pytest 8.0.0, ruff 0.6.0):
  **692 passed** after the fix; ruff 0.6.0 check passed.
- `git diff --check`: clean (one trailing blank line in `experiment_log.md` was removed). New
  untracked files have no trailing whitespace.
- `Abstract.pdf` SHA-256 prefix `ac701b0cbe949ce1` (unchanged).
- **Not tested:** Python 3.11, non-Windows platforms, and GitHub Actions on milestones 2–4.

**Decisions**

- Proposed, awaiting team approval: D-048 (timing), D-049 (costs), D-050 (constraints and cash),
  D-051 (per-split protocol), D-052 (metric reporting), D-053 (baseline set), D-054 (outputs).
- Open: D-023 (annualisation); the turnover-cap measure (D-031); whether test-split evaluation
  becomes opt-in (D-051).

**Next steps**

- Team review of the code, the hand calculations in the tests, and decisions D-048 to D-054.
- If approved: lag-1 and cost-sensitivity runs on train and validation.
- Later, and only after the team starts its next milestone: the RL environment interface,
  reusing the simulator's accounting and timing (roadmap 4).

---

## 2026-10-15: Milestone 3: causal features and rule-based regimes

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code (Anthropic)
  implemented the milestone from the team member's milestone-3 brief. Nothing was staged,
  committed or pushed.
- **Milestone:** 3, implemented and tested locally. Decisions D-043 to D-047 are **Proposed**.
  D-012, D-013, D-018, D-019, D-023 and D-031 remain open (notes added to D-012, D-019 and D-023
  only).

**Starting state (inspected before changes)**

- `main` at `1a289ab` (milestone 2), 1 commit ahead of `origin/main` (not pushed); clean tree,
  nothing staged, no stash.
- GitHub Actions: success on `94e6f74` and `412d620`; no run on `1a289ab`.
- Still tracked from `94e6f74`: the stray `tatus` file, left untouched as before.
- Baseline independently re-run: 525 passed; Ruff lint and format clean; config OK;
  `git diff --check` clean; `Abstract.pdf` SHA-256 prefix `ac701b0cbe949ce1`.
- Local processed live dataset `data/processed/8e00568ee2aa4de7` available. Its contract was
  verified before designing anything:
  - `returns.csv` = `date, period_start, sessions_spanned` + 7 ETFs in universe order;
  - `r_t = P_t / P_{period_start} − 1`, checked numerically for the first row;
  - `sessions_spanned` always 1;
  - `splits.csv` dates equal the return dates.

**Design findings**

- **Timing (D-043):** a row dated `t` is known at the close of `t`, so features use rows ≤ `t`.
  The next row is the outcome of a decision at `t`.
- **Back-adjusted levels:** adjusted price levels at `t` depend on dividends paid later, so
  features use returns and ratios only.
- **Boundary pairs (issue found):** pairing a decision at `t` with `r_{t+1}` by decision date
  would put the first validation return into training at the boundary.
  - Added `features.next_period_targets`, which labels such pairs `boundary`.
  - The splits themselves are unchanged.
  - On the live data, the boundary decisions are 2016-12-30 and 2019-12-31.

**Implementation**

- `src/adaptive_portfolio/config.py`: appended `FeatureWindows`, `RegimeConfig`, `FeatureConfig`
  and `load_feature_config` (configs/features.yaml). Existing classes and `ProjectConfig` are
  unchanged.
- `configs/features.yaml` (new), documented and marked provisional.
- `features/engineering.py`: rolling primitives on NumPy sliding windows, plus
  `build_features` (34 columns by default).
- `features/alignment.py`: decision/target alignment.
- `features/pipeline.py`:
  - contract checks (columns, order, dates, splits against experiment.yaml, multi-session
    returns);
  - fit or load thresholds;
  - outputs written atomically to `data/processed/features/<id>/`.
- `regimes/rules.py` (training-only fit, frozen JSON artifact, assignment, compatibility check)
  and `regimes/diagnostics.py`.
- `features/__init__.py` and `regimes/__init__.py` rewritten from placeholder docstrings.
- `data/cli.py`: new `features` and `regime-report` commands; `validate` also checks
  `features.yaml` when present.
- Tests:
  - `tests/conftest.py` gained helpers (additions only).
  - New test files: `test_feature_config.py` (30), `test_features.py` (26), `test_regimes.py`
    (21), `test_feature_pipeline.py` (13).
  - No existing test was modified.
- Docs: README, architecture, technical handbook (new §12; §2/§3 updated), decision log, glossary,
  presentation guide, roadmap, this journal. Stale statuses corrected: M1 is committed (CI passed);
  M2 is committed locally and not pushed. `experiment_log.md` is unchanged: no experiment was run.
- No new dependency.

**Run on real data (offline; nothing downloaded)**

- Command: `python scripts/market_data.py features --provider yfinance`, on the existing processed
  dataset `8e00568ee2aa4de7` (origin live). Output: feature set `a79347e37e653703`.
- Thresholds (training only, 2,455 rows, 2007-04-04 to 2016-12-30):
  - trend band b = 0.037974;
  - volatility 0.008937 / 0.013051 per session;
  - 62 training warm-up rows excluded.
- All 9 regimes occur; validation and test have no unavailable rows. Four warnings:
  - training `negative_low` 1.5 % (sparse);
  - 62 % of training `positive_high` rows fall in 2009;
  - validation `positive_normal` 1.6 % and `positive_high` 1.5 % (sparse).
- Validation is 46 % `positive_low`. These are descriptive; nothing was tuned in response.
- A rerun gave byte-identical outputs. Outputs are git-ignored (`git check-ignore` confirmed).

**Failures and corrections**

- One E501 (line too long) and one RUF007 (`zip` instead of `itertools.pairwise`) in new code;
  fixed.
- Import-order (I001) findings in four new test files; fixed with `ruff --fix`.
- I simplified a convoluted `dataset_dir` expression to use the existing `relative_to_root`, so no
  absolute paths are written.
- **Hand-picked injected-error checks** (temporary copy of the package; config-location artifact
  test deselected; control 614 passed). All 12 bugs were caught:

  | Deliberate bug | Failing tests |
  | --- | --- |
  | window aligned to the future | 14 |
  | warm-up filled with zeros | 7 |
  | volatility `ddof=0` | 1 |
  | drawdown ignoring the window's starting level | 1 |
  | undefined correlation set to 0 | 2 |
  | dispersion `ddof=1` | 1 |
  | calibration on all splits | 6 |
  | trend boundary not inclusive | 1 |
  | boundary pairs not flagged | 1 |
  | split-consistency check disabled | 1 |
  | multi-session check disabled | 1 |
  | artifact compatibility unchecked | 2 |

  This is a targeted check, not systematic mutation testing. Seven of these bugs are guarded by a
  single test each.

**Checks run (actual results; all local, Windows)**

- **Main `.venv`** (Python 3.13.7, numpy 2.5.4, pandas 3.0.6, PyYAML 6.0.3, pytest 8.4.2,
  ruff 0.17.0):
  - pytest: **615 passed**, 0 skipped. That is the 525 earlier tests plus 90 new: 30 + 26 + 21 + 13.
  - Ruff check: passed; format check: 52 files formatted.
  - `scripts/validate_config.py` OK; `market_data.py validate` OK (features.yaml checked).
- **Clean Python 3.12.1 at the declared minimums** (numpy 1.26.0, pandas 2.2.0, PyYAML 6.0.2,
  pytest 8.0.0, ruff 0.6.0): **615 passed**, 1 warning (not inspected this time; in milestone 2 the
  same warning was pandas 2.2.0's pyarrow notice); ruff 0.6.0 check passed; 42 files formatted.
- **Clean Python 3.13.7 at the lowest versions with 3.13 wheels** (numpy 2.1.0, pandas 2.2.3):
  **615 passed**; ruff 0.6.0 check passed.
- `git diff --check`: exit 0. The untracked files were checked separately: no trailing
  whitespace.
- Diff review:
  - only the intended files changed;
  - `pyproject.toml`, all of `configs/` except the new `features.yaml`, the milestone-1/2 code,
    every existing test file, CI, `.gitignore`, `CLAUDE.md`, `tatus` and `Abstract.pdf` are
    unchanged;
  - the only removed lines are placeholder docstrings, the CLI description and the private
    `_cmd_validate` signature.
- **Not tested:** Python 3.11; non-Windows platforms. GitHub Actions has not run on milestone 2 or
  milestone 3.

**Remaining**

- Team approval of D-043 to D-047 (and of D-008, D-034 to D-042 from milestone 2).
- D-012 (regime signals as agent inputs) to be decided with the environment.
- Next: milestone 4 (portfolio environment), which needs D-013 (timing) and D-031 (cost basis)
  first.

---

## 2026-10-15: Milestone 2: market-data pipeline

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code (Anthropic)
  implemented the milestone from the team member's milestone-2 brief. Nothing was staged,
  committed or pushed.
- **Milestone:** 2, Data pipeline: implemented and tested locally. Every new decision (D-034 to
  D-042, and D-008 moved from Open to Proposed) is **Proposed**. Open decisions D-013, D-018,
  D-019, D-023 and D-031 were not resolved.

**Starting state (inspected before changes)**

- `main` = `origin/main` = `94e6f74` ("feat: complete financial metrics with optional
  traded-notional turnover"); clean tree, nothing staged, no stash.
- GitHub Actions: CI succeeded on `94e6f74` and on `412d620` (queried via the GitHub API).
- **Finding, not changed:** commit `94e6f74` contains a tracked root-level file named `tatus`
  (142,459 bytes). It is a capture of Git command output and was probably created by a mistyped
  `git status`. It was left untouched; the team may want to remove it in its own commit.
- Baseline: Python 3.13.7, numpy 2.5.4, pandas 3.0.6, PyYAML 6.0.3, pytest 8.4.2, ruff 0.17.0.
  396 tests passed; Ruff lint and format clean; config OK; `git diff --check` clean.
  `Abstract.pdf` SHA-256 prefix `ac701b0cbe949ce1`.

**Research decisions (all Proposed; details and alternatives in the decision log)**

- **D-034 universe:** SPY, EFA, EEM, IEF, TLT, LQD, GLD, superseding the D-005 proposal (QQQ and
  IWM out; EEM and LQD in).
  - Evidence was gathered with yfinance 1.7.0 in a throwaway environment: first available dates
    for 13 candidates, dividend and split counts, and average 2024 dollar volume.
  - Rejected: BIL (starts 2007-05-30), DBC (≈ $23M/day), SHY, VNQ, QQQ, IWM.
  - Survivorship and selection bias are documented.
- **D-008 / D-041 provider:**
  - `csv` stays the config default (offline; the existing test that the default provider needs
    no network is unchanged).
  - `yfinance` is the opt-in live source (optional extra `.[data]`, `>=1.7,<2`).
  - `synthetic` provides test and demo data.
  - The roadmap had labelled the adapter `[O]`; it was started because the brief explicitly
    requested a real-data adapter.
- **D-035:** daily data on the observed calendar; the pipeline is daily-only; no annualisation.
- **D-036:** missing data stops by default; optional `drop_sessions`; never filled.
- **D-037:** `adj_close` by default, never mixed with `close`.
- **D-038:** split rows labelled by their own date.
- **D-039:** snapshots, manifests, checksums, CSV storage, processed ids.
- **D-040:** pandas moved to runtime.
- **D-042:** provisional validation thresholds.
- **Unchanged:** the date range 2007–2024 (D-006) and the split dates, so existing boundaries
  remain valid.

**Implementation**

- `src/adaptive_portfolio/config.py`:
  - `DataConfig` extended with optional sections `provider_options`, `cache`, `missing_data` and
    `validation`;
  - stricter `price_field`;
  - an identifier pattern for tickers;
  - path checks.

  Existing fields, defaults and behaviour are unchanged. Nested dataclass defaults use
  `field(default_factory=...)`.
- New `src/adaptive_portfolio/data/` modules: `providers.py`, `validation.py`, `processing.py`,
  `splits.py`, `cache.py`, `report.py`, `pipeline.py`, `cli.py`. `data/__init__.py` was rewritten
  from its placeholder docstring. New `scripts/market_data.py`.
- Returns reuse `evaluation.portfolio_returns` (D-021). No metric code was changed.
- `configs/data.yaml`: new universe and documented new sections. `pyproject.toml`: pandas
  moved to runtime; new `data` extra.
- Tests:
  - `tests/conftest.py` gained fixtures (additions only).
  - New test files: `test_data_config.py` (41), `test_data_providers.py` (28),
    `test_data_validation.py` (15), `test_data_processing.py` (11), `test_data_splits.py` (13),
    `test_data_pipeline.py` (21).
  - The milestone-1 test files are unchanged.
- Docs: README, architecture, technical handbook (new §11 plus updates to §2–§5), decision log,
  glossary (new "Market data" section), presentation guide, roadmap, this journal.
  `experiment_log.md` is unchanged: **no portfolio experiment was run**.

**Live retrieval (actually performed)**

- `python -m pip install -e ".[dev,data]"` installed yfinance 1.7.0 into the project `.venv`.
- `python scripts/market_data.py build --provider yfinance` succeeded at 2026-10-15T10:21:14Z:
  - 7 instruments × 4,530 rows, 2007-01-03 to 2024-12-31, 0 missing cells, every validation rule
    passed;
  - snapshot `data/raw/yfinance/e27437b97742fa43/`; processed dataset
    `data/processed/8e00568ee2aa4de7/`. Both are git-ignored and confirmed by `git check-ignore`.
- Report facts: 250–253 sessions per calendar year; largest gap 5 days; largest |daily return|
  0.2277 (EEM). EEM has 1 split event in range, and GLD has 0 dividends.
- Determinism: `build --provider yfinance --cache-mode offline` was a CACHE HIT, and all 7
  deterministic processed files were byte-identical (SHA-256) to the first build.
- `split --provider yfinance` reproduced `splits.csv` (train 2,517, validation 754, test 1,258
  return rows).
- These are data-quality facts only. No performance statistic was computed or reported.

**Failures and corrections during the session (recorded as they happened)**

- My first offline rerun omitted `--provider yfinance`, so it looked for a `csv` snapshot. The
  pipeline correctly refused with an actionable error; the rerun with the right provider passed.
- Two hand-derived test expectations of mine were wrong and were corrected after rechecking the
  arithmetic, not loosened. Weekdays from 2024-01-01 to 2024-02-29 are 23 + 21 = 44, not 43.
- `DataFrame.stack()` was replaced by `melt` before any test, because stack behaves differently
  in pandas 2.2 and 3.x.
- Ruff 0.17.0 passed, but the declared minimum **ruff 0.6.0 reported 4 × RUF009** (function
  calls as dataclass defaults). Fixed with `field(default_factory=...)`; both versions now pass.
- A decision-log helper stopped at its own uniqueness check: "Status: Open" matched both D-008
  and D-013. It was re-scoped to D-008, and D-013 is unchanged.
- **Hand-picked injected-error checks** (temporary copy of the package; the known config-location
  artifact test was deselected; the control run gave 524 passed). Each deliberate bug was caught:

  | Deliberate bug | Failing tests |
  | --- | --- |
  | forward-fill instead of drop | 6 |
  | `sessions_spanned` always 1 | 4 |
  | return threshold disabled | 1 |
  | duplicates accepted | 1 |
  | start-coverage unchecked | 1 |
  | exclusive split end | 13 |
  | checksums ignored | 2 |
  | CSV source change ignored | 1 |
  | permanent errors retried | 4 |
  | yfinance end not extended | 1 |
  | offline mode fetching | 2 |

  This is a targeted check, not systematic mutation testing. Five of these bugs are guarded by a
  single test each.

**Checks run (actual results; all local, Windows)**

- **Main `.venv`** (Python 3.13.7, numpy 2.5.4, pandas 3.0.6, PyYAML 6.0.3, pytest 8.4.2,
  ruff 0.17.0, yfinance 1.7.0):
  - `python -m pytest`: **525 passed**, 0 skipped. The 396 milestone-1 tests are among them.
  - `python -m ruff check .`: all passed; `python -m ruff format --check .`: 43 files formatted.
  - `python scripts/validate_config.py`: OK; `python scripts/market_data.py validate`: OK.
  - `git diff --check`: exit 0.
- **Clean Python 3.12.1 at the declared minimums** (numpy 1.26.0, pandas 2.2.0, PyYAML 6.0.2,
  pytest 8.0.0, ruff 0.6.0):
  - 525 passed, with 1 warning: pandas 2.2.0's own import-time notice about pyarrow;
  - ruff check passed; 33 files formatted;
  - config OK.
- **Clean Python 3.13.7 at the lowest versions with 3.13 wheels** (numpy 2.1.0, pandas 2.2.3,
  PyYAML 6.0.2, pytest 8.0.0, ruff 0.6.0): 525 passed; ruff check passed; config OK.
- **Not tested:** Python 3.11 (not installed); non-Windows platforms; yfinance versions other
  than 1.7.0; the yfinance adapter in CI (it uses a fake module).
- **GitHub Actions has not run on milestone 2** (nothing pushed).

**Remaining / next**

- Team review and approval of D-008 and D-034 to D-042.
- D-023 (annualisation), D-019 (embargo) and D-018 (walk-forward) remain open.
- Next milestone: 3 (market conditions / regime labels), built on the processed returns.

---

## 2026-10-13: Final review corrections, decisions accepted, PyYAML bound

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code (Anthropic)
  applied the corrections the team member approved after the final approval review. All changes
  are uncommitted and unpushed.
- **Milestone:** 1, Financial metrics: **complete**. All conventions are accepted. Not yet
  committed, so GitHub Actions has not run on it.
- **Git state at start:** `main` = `origin/main` = `412d620`; nothing staged; 11 modified and 3
  untracked files; unchanged since the review. Baseline: 396 tests passed.

**Changes**

1. Decision log:
   - D-021, D-022 and D-024 to D-029 marked **Accepted**. Their wording was checked against the
     code first. For D-029, the "Proposed reporting rule" is now accepted as part of D-029, and
     its Sharpe citation is corrected to handbook §10.4 (D-022, D-024).
   - D-011 and D-030 **Accepted only after correcting their wording to match the code**:
     - D-011 previously said "sum over assets", and that cash "counts like any asset", which is
       true only for the default. It now distinguishes the all-column default from traded notional
       (`cash_column`), and states that the measure the config cap constrains is open (D-031).
     - D-030 now shows `cash_column` in the signature, separates `TypeError` and `ValueError`
       cases, and states the event-value range and `observation_periods` rules.
     - Each claim in the new wording was verified against the code with a script (10 checks,
       all OK).
   - D-032's Status line set to Accepted, matching its summary row.
   - New **D-033** (PyYAML bound, Accepted).
   - D-007 clarified so that it does not imply D-031 is decided.
   - **D-031 remains Open.** D-023 and D-013 are unchanged.
2. `pyproject.toml`: `PyYAML>=6.0,<7` → `PyYAML>=6.0.2,<7`. The Python support declaration is
   unchanged.
3. Stale status statements fixed: README (status paragraph; milestones 0 and 1) and roadmap
   (milestone 0; milestone 1 sign-off).
4. Roadmap minimum-version claim replaced with the exact environments tested; "two mutation
   checks" replaced with "hand-picked injected-error checks". The presentation guide and
   handbook §10.11 now describe these as targeted checks, not systematic mutation testing.
5. Older "traded notional" uses no longer imply that D-031 is decided: D-007, the glossary's
   *Transaction cost* entry, roadmap milestone 4, and a comment in `configs/environment.yaml`
   (comment only; config values and validation unchanged).
6. `annualized_turnover` docstring: "counting both legs" now applies only to the default
   all-column measure. Behaviour is unchanged.
7. Handbook (§6, §10 intro) and presentation guide status text updated from "proposed" to
   "accepted", with the remaining open items listed.

**Findings**

- **Line endings (cause identified):** `README.md`, `architecture.md` and `decision_log.md` have
  CRLF endings in the working tree. The cause is that my earlier Python edit scripts used
  `write_text` on Windows, which writes `\r\n`. Content is unaffected and Git normalises the
  endings on commit (`core.autocrlf=true`). This session's scripts preserved the existing endings.
- **Python 3.13 and declared minimums:** `numpy` 1.26.0 (runtime minimum, kept unchanged by
  instruction) and `pandas` 2.2.0 (dev minimum) have **no Python 3.13 wheels**. The lowest
  versions with 3.13 wheels are numpy 2.1.0 and pandas 2.2.3 (checked against PyPI file lists).
  Recorded in D-033 as a limitation; bounds not changed.

**Checks run (actual results; all local, on Windows)**

- Main `.venv` (Python 3.13.7, numpy 2.5.4, pandas 3.0.6, PyYAML 6.0.3, pytest 8.4.2,
  ruff 0.17.0):
  - pytest: **396 passed**, 0 skipped (50 config, 247 metrics, 11 package, 88 turnover);
  - `ruff check .`: all passed; `ruff format --check .`: 28 files formatted;
  - `scripts/validate_config.py`: OK (exit 0);
  - `git diff --check`: exit 0, no issues. The untracked files were checked separately: no
    trailing whitespace, LF endings.
- Clean temporary venv, **Python 3.12.1, at every declared minimum** (numpy 1.26.0, pandas 2.2.0,
  PyYAML 6.0.2, pytest 8.0.0, ruff 0.6.0): pytest 396 passed; ruff 0.6.0 lint passed; format
  check 18 files formatted (0.6.0 does not format Markdown); config OK.
- Clean temporary venv, **Python 3.13.7, at the lowest versions with 3.13 wheels** (numpy 2.1.0,
  pandas 2.2.3, PyYAML 6.0.2, pytest 8.0.0, ruff 0.6.0): pytest 396 passed; lint passed; format
  check 18 files formatted; config OK.
- **Not tested:**
  - Python 3.11 (not installed; installing an interpreter was not requested);
  - non-Windows platforms;
  - numpy 1.26.x and pandas 2.2.0–2.2.2 on Python 3.13 (no wheels exist).
- `Abstract.pdf`: unchanged vs HEAD. No transaction-cost code exists outside the existing config
  loader. "Profitable" and "beats the market" appear only as warnings.
- **GitHub Actions:** the only run on record is CI on `412d620` (the scaffold), which succeeded.
  It has **not** run on any Milestone 1 change, because nothing has been pushed.

---

## 2026-10-13: Pre-commit review fixes and approved `cash_column` turnover extension

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code (Anthropic)
  implemented the fixes below, following decisions the team member approved in the session. All
  changes are uncommitted and unpushed.
- **Milestone:** 1, Financial metrics. Implementation complete; sign-off of the remaining
  Proposed conventions is still pending.
- **Git state observed:**
  - At the start of this session HEAD was `5b28973` ("feat: complete financial metrics and
    turnover", 1 commit ahead of `origin/main`, not pushed).
  - During the session the reflog recorded `reset: moving to HEAD~1` (14:10:52) and
    `reset: moving to HEAD` (14:11:01). These were not run by Claude Code, which ran no
    ref-changing Git commands.
  - `main` is now `412d620`, level with `origin/main`.
  - Verified that no content was lost: the working tree equals `5b28973` plus this session's
    changes, `tests/test_metrics.py` is byte-identical to the commit, and `5b28973` remains
    reachable via the reflog.
- **Baseline before changes:** 371 tests passed.

**Work done (approved fixes)**

1. `pyproject.toml`: the dev dependency is raised from `pandas>=2.1,<4` to `pandas>=2.2,<4`. The
   NumPy minimum is unchanged (D-032 revised and Accepted).
2. Handbook §10.1: the shared rules table now separates series-metric rules from **turnover
   exceptions** (2-D required; empty event list gives 0.0; `observation_periods`; `cash_column`).
3. `metrics.py` module docstring: now cites D-011 and D-021 to D-030, and notes that D-031 is open.
4. `annualized_turnover`: always returns a Python `float`, using `int(observation_periods)`.
   Regression test for `int`, `np.int64`, `np.int32` and `np.uint16`.
5. Journal: the CI wording in the previous entry is corrected (marked in place).
6. `portfolio_turnover(..., *, cash_column: int | None = None)`:
   - `None` keeps the all-column sum.
   - An index excludes that column, giving traded notional.
   - Complete rows are still validated, cash included.
   - Non-integers and booleans raise `TypeError`; out-of-range or negative indices raise
     `ValueError`.
7. Tests: 25 new in `tests/test_turnover.py`, all checked against hand calculations:
   - cash-funded 10 % purchase: default 0.20, traded notional 0.10;
   - 10 % switch: 0.20 under both measures;
   - mixed trade: default 0.40, traded 0.30, one-way 0.20;
   - initial funding: default 2.0, traded 1.0;
   - cash in the first column; multiple events;
   - identities on 300 seeded random rows;
   - legacy default preserved; invalid indices; full-row validation; NumPy-integer index;
     cash-only portfolio.
8. Docs: D-011, D-030, D-031 and D-032 updated with approval records limited to the approved
   items; handbook §10.8–§10.11; glossary; presentation guide; architecture; roadmap.
9. Not done, as instructed: no transaction-cost deduction and no environment. D-031 stays Open.
   `configs/environment.yaml` is unchanged in this session; which measure `max_turnover`
   constrains is left to D-031.

**Findings**

- **Mutation-harness artifact.** `test_default_config_dir_points_at_repo_configs` fails whenever
  `src/` is copied to a temporary directory. The previous entry's full-suite mutation counts were
  therefore each inflated by 1 (corrected in place).
  - Re-measured with that test deselected; the control run on an unmodified copy gave 395 passed.
  - All 16 mutations (11 earlier and 5 new) were caught, with 1 to 19 genuine failures each
    (handbook §10.11).
  - A Git Bash path conversion silently prevented one mutation from being applied on the first
    attempt; it was rerun with `MSYS_NO_PATHCONV=1`.
- **ruff 0.6.0 (the declared minimum) flagged RUF003** on a Unicode minus sign in a new test
  comment; ruff 0.17.0 did not. Fixed by replacing it with an ASCII hyphen.
- **PyYAML 6.0 (the declared runtime minimum) cannot be installed on Python 3.12.** pip reported a
  build-subprocess error and installed nothing. 6.0.1 was used for the minimum-version run. The
  bound was not changed (not approved); it is recorded in D-032 as a limitation.

**Checks run (actual results, local Windows)**

- Main `.venv` (Python 3.13.7, numpy 2.5.4, pandas 3.0.6, PyYAML 6.0.3, pytest 8.4.2,
  ruff 0.17.0):
  - `python -m pytest`: **396 passed**, 0 skipped (50 config, 247 metrics, 11 package,
    88 turnover).
  - `python -m ruff check .`: all checks passed.
  - `python -m ruff format --check .`: 28 files already formatted.
  - `python scripts/validate_config.py`: Configuration OK (exit 0).
- Minimum-version run in a clean temporary Python 3.12.1 venv (numpy 1.26.0, pandas 2.2.0,
  PyYAML 6.0.1 because 6.0 is not installable on 3.12, pytest 8.0.0, ruff 0.6.0):
  - pytest: **396 passed**;
  - ruff 0.6.0 check: all checks passed;
  - ruff 0.6.0 format check: 18 files already formatted (0.6.0 does not format Markdown code
    blocks);
  - config validation: OK.
- Mutation re-measurement: control 395 passed; all 16 mutations caught (handbook §10.11).
- The GitHub Actions workflow has not run for these changes.

---

## 2026-10-13: Milestone 1 completed in code: review fixes, cumulative return, CAGR, turnover

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code (Anthropic)
  implemented the changes below, after a review session with the team member. Everything is
  uncommitted and pending team review.
- **Milestone:** 1, Financial metrics. **Implementation complete; formal sign-off pending team
  approval of the proposed conventions.**
- **Baseline before changes:** 227 tests passed; Ruff lint and format clean; no decision approved
  in the decision log.

**Work done**

- *Review fixes:*
  - Direct tests for invalid `periods_per_year` in `annual_to_periodic_rate`.
  - Tuple inputs tested.
  - pandas added as a **dev-only** dependency (`pandas>=2.1,<4`, D-032); pandas Series/DataFrame
    inputs tested, including rejection of NaN and nullable `pd.NA`.
  - D-022 corrected: `ddof=1` gives an unbiased *variance*; the std is not generally unbiased.
  - Zero-volatility tolerance reviewed with measurements and kept at 1e-12 (D-025). The
    limitations are documented.
- *New metrics* in `src/adaptive_portfolio/evaluation/metrics.py`:
  - `cumulative_return` (V_T/V_0 − 1, D-028);
  - `annualized_return` (geometric CAGR, (V_T/V_0)^(N/T) − 1, D-029);
  - `portfolio_turnover` (two-way, per event, from caller-supplied drift-adjusted pre-trade and
    post-trade weights, D-011/D-030);
  - `annualized_turnover` (Σ τ · N / T_obs; empty means 0);
  - new constant `WEIGHT_SUM_TOLERANCE = 1e-6`.
- *Internal refactor:* the shared type/dtype check was extracted into `_as_real_array` so that the
  1-D and 2-D validators share it. The behaviour and messages of the existing functions are
  unchanged; the full pre-existing suite passed after the refactor.
- *Config consistency:* `max_turnover ∈ (0, 2]` already assumed two-way, per-rebalance turnover,
  which matches the implementation. Only a 3-line comment was added to `configs/environment.yaml`;
  the validator and its semantics are unchanged.
- *CI:* the workflow is configured to install `.[dev]`, so it will install pandas and run the pandas
  tests when it runs. No workflow change was needed. *[Corrected 2026-10-13: this originally said
  that pandas "is installed in CI and the pandas tests run there". The workflow has not run, so
  this describes the configuration only.]*
- *Docs updated:*
  - `technical_handbook.md`: §3, §6 and §10 (new §10.6–§10.11);
  - `decision_log.md`: D-011, D-013, D-022, D-025 and D-027 updated; new D-028 to D-032;
  - `glossary.md`, `presentation_guide.md` (now covers all seven metrics, with self-check
    questions);
  - `roadmap.md`, `architecture.md` (new metric-interface section), `README.md`.
  - `experiment_log.md` was not changed: no experiment was run.

**Findings**

- Floating-point noise vs. tolerance (NumPy 2.5.4, this machine):
  - constant series: ≤ ~2.8 × 10⁻¹⁷;
  - constant excess r − rf: ≤ ~1.3 × 10⁻¹⁸;
  - realistic smallest periodic std: ~1.1 × 10⁻⁵.

  So 1e-12 has wide margins in both directions.
- **D-031 (new, Open):** two-way turnover with a cash column counts both legs of a cash-funded
  trade. A cost model of `bps × τ` would double-charge such trades. This must be decided with the
  environment and cost model; it does not affect the metric itself.
- Config says cash is *implicit* (`allow_cash`), but turnover needs an *explicit* cash column so
  that rows sum to 1. This is documented; it is not a contradiction.
- **Error caught by the tests:** my hand-derived expected value for the "drift reduces trading"
  case was wrong (0.0204 instead of 2 × 0.05/0.98 ≈ 0.102). The test failed against the
  implementation, the derivation was redone, and the value was corrected. It was not loosened.
- Mutation check on the new code (temporary copy, deleted). Every deliberate error was caught,
  with 2 to 10 failures each: wrong V_0; exponent T/N; T = number of values; arithmetic instead of
  geometric; one-way turnover; cash column ignored; row-sum check off; negatives allowed; shape
  check off; mean instead of sum; empty events raising. *[Corrected 2026-10-13: each count included
  one harness-artifact failure (see the next entry), so the genuine counts were 1 to 9. Every error
  was still caught by at least one genuine failure. Re-measured counts are in handbook §10.11.]*

**Checks run (actual results, local Windows)**

- `python -m pytest` (Python 3.13.7 `.venv`): **371 passed**, 0 skipped (50 config, 247 metrics,
  11 package, 63 turnover).
- The full suite on a fresh temporary Python 3.12.1 environment (numpy 2.5.4, pandas 3.0.6):
  371 passed. Python 3.11 is not installed locally; untested here.
- `python -m ruff check .`: all checks passed.
- `python -m ruff format --check .`: 28 files already formatted.
- `python scripts/validate_config.py`: Configuration OK (exit 0).
- Packaging: `pip wheel --no-deps .` built `adaptive_portfolio_intelligence-0.1.0-py3-none-any.whl`.
  Runtime requirements are NumPy and PyYAML only; pandas, pytest and ruff appear only under
  `extra == "dev"`. `metrics.py` is included in the wheel.
- No type checker is configured in the repository; none was run.
- The GitHub Actions workflow has not been observed running for these changes.
- `git diff` review: only the intended files changed. `config.py`, existing tests, CI,
  `.gitignore`, `Abstract.pdf`, `CLAUDE.md`, `experiment_log.md`, `data.yaml` and
  `experiment.yaml` are unchanged.

**Files changed (vs. commit `412d620`, cumulative for milestone 1)**

- New: `src/adaptive_portfolio/evaluation/metrics.py`, `tests/test_metrics.py`,
  `tests/test_turnover.py`.
- Modified: `src/adaptive_portfolio/evaluation/__init__.py`, `pyproject.toml`,
  `configs/environment.yaml` (comment only), `README.md`, `docs/architecture.md`,
  `docs/decision_log.md`, `docs/glossary.md`, `docs/presentation_guide.md`,
  `docs/project_journal.md`, `docs/roadmap.md`, `docs/technical_handbook.md`.

**Remaining**

- Team approval (or revision) of D-011, D-021, D-022, D-024 to D-030 and D-032.
- Later milestones: D-023 (daily N) in milestone 2; D-013 (timing) and D-031 (cost basis) in
  milestones 4 and 7.

---

## 2026-10-13: Milestone 1 (partial): four core financial metrics

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code (Anthropic)
  implemented the metrics, tests and documentation updates below. They are uncommitted and pending
  team review.
- **Milestone:** 1, Financial metrics. **In progress, not complete.**
- **Starting point:** commit `412d620` (scaffold). Baseline before changes: 61 tests passed; Ruff
  lint and format clean.

**Work done**

- New module `src/adaptive_portfolio/evaluation/metrics.py`, NumPy only:
  - `portfolio_returns`, `annualized_volatility`, `sharpe_ratio` (with `annual_to_periodic_rate`),
    `drawdown_series`, `max_drawdown` (returns a `MaxDrawdown` dataclass).
  - Error type `UndefinedMetricError`; constant `ZERO_VOLATILITY_TOLERANCE` (1e-12).
- `evaluation/__init__.py` re-exports the public API.
- `pyproject.toml`: added `numpy>=1.26,<3`. pandas is not added.
- New `tests/test_metrics.py` (166 tests): hand-calculated examples, edge cases and validation.
- Docs updated: technical handbook §3, §6 and new §10; decision log D-021 to D-027; glossary;
  presentation guide; roadmap; README status; architecture.

**Decisions** (all **Proposed**, none approved)

- D-021: simple returns from strictly positive values; the first observation is omitted; NaN is
  rejected.
- D-022: sample standard deviation (`ddof=1`).
- D-023: `periods_per_year` must be passed explicitly. The per-frequency value is open (252 vs. 365).
- D-024: geometric conversion of annual to periodic risk-free rates.
- D-025: undefined metrics raise `UndefinedMetricError`; zero-volatility tolerance 1e-12.
- D-026: the first observation is the initial drawdown peak; earliest trough and latest peak on ties.
- D-027: NumPy only.

**Findings**

- Floating-point noise makes mathematically constant series have std ~1e-18. Without a tolerance,
  the Sharpe ratio would be ~1e16 instead of undefined. This is covered by
  `test_sharpe_constant_excess_return_is_undefined`.
- While writing the decision log, I verified a numeric claim and found it wrong by a factor of 10.
  The gap between simple and geometric daily risk-free rates for R = 2 % is about 7.8 × 10⁻⁷ per
  day, not 8 × 10⁻⁸. It was corrected before saving.
- Mutation check (a temporary copy of the module, deleted afterwards). Each deliberate error made
  the new tests fail: ddof 1→0 (11 failures), geometric→simple risk-free conversion (5), tolerance
  removed (2), earliest instead of latest peak (1), √N→N (5), NaN allowed (11), zero values
  allowed (6).

**Checks run (actual results, local Windows)**

- `python -m pytest` (full suite, Python 3.13.7 `.venv`): **227 passed** (50 config, 166 metrics,
  11 package).
- The full suite in a fresh, temporary Python 3.12.1 environment (numpy 2.5.4): 227 passed.
  Python 3.11 is not installed locally; untested here.
- `python -m ruff check .`: all checks passed.
- `python -m ruff format --check .`: 27 files already formatted, after formatting the two new files.
- `python scripts/validate_config.py`: Configuration OK (exit 0). Configs and the loader are
  unchanged.
- `git diff` review: only the intended files changed. `configs/`, `config.py`, existing tests,
  `.gitignore`, CI and `Abstract.pdf` are unchanged.
- The GitHub Actions workflow has not been observed running for this change.

**Remaining work for milestone 1**

- Cumulative return; turnover (blocked on D-011); annualised return (arithmetic vs. geometric).
- Team review of D-021 to D-027; decide `periods_per_year` per frequency (D-023).

---

## 2026-10-13: Pre-commit audit of the scaffold

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code (Anthropic)
  performed the audit and proposed the fixes below. The fixes have not yet been reviewed by the team.
- **Milestone:** 0 (scaffold). No financial metrics, environment or RL code was written.

**Work done**

- Audited the documentation, research scope, configuration and loader, Git and security setup.
- Created missing documents: `project_journal.md` (this file), `technical_handbook.md`,
  `decision_log.md`, `presentation_guide.md`, `glossary.md`.
- Added "Research scope" and "Documentation maintenance (required)" sections to `CLAUDE.md`.

**Findings and fixes**

1. *Config validation bug:* NaN or ±inf was accepted for `initial_capital`, `min_weight` and other
   float fields, because NaN fails every comparison. Fixed: non-finite numbers are now rejected.
   Tests added.
2. *Unbounded short weights:* with `long_only: false`, any negative `min_weight` (e.g. −5) was
   accepted. Now bounded at ≥ −1 (proposed as D-020); long-only remains the default. Tests added.
3. *`.gitignore` over-matching:* unanchored patterns (`models/`, `runs/`, `outputs/`, `logs/`, …)
   would have silently ignored any same-named source or test directory, e.g. a future
   `src/adaptive_portfolio/models/`. These patterns are now anchored to the repository root.
   Serialized model formats (`*.pkl`, `*.joblib`, `*.onnx`, `*.safetensors`, `*.pickle`) were added.
4. *Scope drift vs. abstract:* the docs presented some extensions as plans without marking them
   optional: DQN, statistical (HMM) regime models, SHAP, dashboard, slippage and cost sweeps,
   Sortino/Calmar. Walk-forward evaluation appeared as unconditional, whereas the abstract says
   "where feasible". Fixed:
   - Added a required-vs-optional scope table to the README.
   - Added [R]/[F]/[O] labels to the roadmap.
   - Aligned the wording in the architecture doc, the subpackage docstrings and the safeguards.
5. *Undocumented assumptions:* the turnover definition implied by the validator (two-way,
   0–2) was not stated in the YAML; the risk-free rate bounds were not documented; there was no note
   on embargo between splits. Comments added; definitions recorded as provisional or open decisions
   (D-011, D-019).
6. *Repository state:* the folder is **not yet a Git repository** (`git init` has not been run), so
   there is no staged or untracked state to inspect. A dry run of `git add -A` against a throwaway
   Git directory listed 40 files (including this journal), with no virtual environment, cache, secret, dataset or model files.

**Confirmed consistent (no change needed)**

- PPO is described as a candidate; no performance improvement is assumed; benchmarks, transaction
  costs, risk metrics (cumulative return, Sharpe, max drawdown, turnover), out-of-sample testing,
  explainability and risk management are central.
- The asset universe, date range, costs, slippage, weight limits and split dates are labelled
  provisional in the configs and docs.
- The validator enforces date ordering, non-overlapping chronological splits, splits within the data
  window, cost bounds, weight-constraint feasibility, and rebalancing no finer than the data frequency.
- `.env.example` contains placeholders only; a scan found no key-like values in the repository.
- `Abstract.pdf` is unchanged (SHA-256 `ac701b0c…296319cd`, 127,113 bytes), including its AI-tools
  disclosure. The README's AI disclosure is retained and extended to mention this audit.

**Known limitations (not implemented; see technical_handbook.md §5)**

- No seeding helper, no config snapshot or serialisation, no data checksums, no dependency lock file.
- Walk-forward settings are parsed but unused; relative paths depend on the working directory.
- `output_dir: reports` writes into a directory that is only partly git-ignored (D-017).

**Checks run (actual results, local Windows, Python 3.13.7 in `.venv`)**

- `python -m pytest`: 61 passed.
- `python -m ruff check .`: all checks passed.
- `python -m ruff format --check .`: passed after fixing one spacing issue in a Markdown code block.
- `python scripts/validate_config.py`: Configuration OK (exit 0).
- The GitHub Actions workflow has **not** run (the repository has not been pushed).

**Decisions requiring team approval:** D-004 (license), D-005 to D-009 and D-015 (provisional data,
cost, split and constraint values), D-010 (minimum benchmark set), D-011 (turnover definition),
D-012 (regime signals as agent inputs), D-013 (trade timing), D-016 to D-019, D-020 (short-weight
bound).

**Next steps**

- Team reviews the scaffold and this audit, then runs `git init` and makes the first commit.
- Resolve D-011 and the metric conventions (annualisation, Sharpe), then start milestone 1
  (financial metrics).

---

## 2026-10-12: Repository scaffold created

- **Who:** session run under local Git identity `Parvptl`; AI assistance: Claude Code generated the
  scaffold, which is pending team review.
- **Milestone:** 0.

**Work done**

- `Abstract.pdf` (file timestamp 2026-10-02) was the only file present. It was kept unchanged and
  used as the scope reference.
- Created the `src/adaptive_portfolio` package with placeholder subpackages, a config loader with
  validation, provisional YAML configs, tests, a CLI config check, the Makefile, the CI workflow, the
  README, CLAUDE.md, and the architecture, roadmap and experiment-log documents.
- Installed in editable mode into a local `.venv`.

**Checks run (actual results)**

- 55 tests passed on Python 3.13.7, and on Python 3.12 in a temporary environment.
- Ruff lint and format checks passed. Config validation passed.
- `make` is not installed on this machine, so the Makefile targets were not executed. Python 3.11
  was not available locally.
