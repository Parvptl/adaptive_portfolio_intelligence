# Experiment Log

Every experiment whose results are discussed, plotted or reported must have an entry here. Record
negative and inconclusive results as well as positive ones. Do not edit past entries except to add
corrections, marked as such.

## How to add an entry

1. Copy the template below to the top of the **Entries** section.
2. Use the next ID (`EXP-001`, `EXP-002`, …).
3. Commit the config files used, and fill in the commit hash.
4. State which period the reported numbers come from. Test-period results are reported only for
   final, pre-registered evaluations.

---

## Template

```markdown
### EXP-XXX: <short title>

- **Date:** YYYY-MM-DD
- **Author(s):**
- **Milestone:** (see docs/roadmap.md)
- **Git commit:** `<hash>` (clean working tree? yes/no)
- **Config files:** `configs/...` (or an inline diff from defaults)
- **Random seed(s):**
- **Data:** provider, universe, date range, frequency, data snapshot/version
- **Periods used:** train YYYY-MM-DD → YYYY-MM-DD; validation …; test … (used? yes/no)

**Hypothesis / question**
What is being tested, and what result would count as support or refutation?

**Method**
Strategy / agent, key hyperparameters, cost assumptions (bps), constraints, rebalancing frequency.

**Assumptions and known limitations**
Anything provisional (costs, universe, survivorship, timing convention).

**Results** (state period; include baselines under identical conditions)

| Strategy | Ann. return | Ann. vol | Sharpe | Sortino | Max DD | Turnover | Cost drag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

Variation across seeds:
Figures: `reports/figures/...`

**Interpretation**
What the evidence does and does not support. No claims of profitability without evidence.

**Next steps**
```

---

## Entries

### EXP-005: Full D-066 PPO training grid, 40 runs (training split only; trained, not evaluated)

- **Date:** run on 2026-10-20 (UTC): 22:13:44Z–23:11:38Z (57 min 54 s). Recorded on 2026-10-21.
- **Author(s):** run by Claude Code at the request of a team member. In the session, the member
  answered "Launch the full grid" to an explicit approval question naming the grid, commit and
  settings. The message does not name its author; it was recorded under R-S (D-061), and the
  other teammate's confirmation was not sought.
- **Milestone:** M5.3: the D-066 training grid. **Training only**: no policy was evaluated and
  no configuration was selected.
- **Git commit:** `cc9784b` (`cc9784b98a8c4ec2b3ac88ce797d15dc4f6621b3`), **clean working tree**.
  The commit is in every run identity and in the grid id. It was not yet pushed when the grid
  ran.
- **Grid:** `0f1c47502dc30d84`; manifest at
  `data/processed/experiments/grids/0f1c47502dc30d84/manifest.json`.
- **Config files (SHA-256 prefixes of the working copies at run time):**
  - `agent.yaml` `cf3d767a1b222389`;
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb`.

  These are identical to EXP-004. The line-ending note there applies.
- **Random seeds:** 42, 43, 44, 45, 46 for every configuration (D-066).
- **Data:** processed dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`, loaded with
  `train_only=True`; 2,517 rows, 2007-01-04 to 2016-12-30.
- **Periods used:** **train only.** Each episode runs from decision 2007-07-05 to 2016-12-30.
  Validation and test values were not loaded or parsed.

**Question.** Train every D-066 configuration and seed on the training split under the accepted
execution policy (D-075). This is a training step; the results needed for selection (median
validation net Sharpe, D-066) are not part of it.

**Method.**
- **Command:** `python scripts/run_grid.py --execute --confirm-full-grid --dataset-dir
  data/processed/8e00568ee2aa4de7`.
- **Execution:** sequential; each run in a child process with `PYTHONHASHSEED=0` and a 900 s
  hard limit; stop at the first failure (none occurred).
- **Runs:** 8 configurations (learning rate {3e-4, 1e-4} × `n_steps` {512, 1024} × entropy
  coefficient {0, 0.01}, `batch_size` 64) × 5 seeds = 40 `full` runs with a 100,000-timestep
  budget each.
- **Settings:** the pinned settings (D-074), one torch thread,
  `torch.use_deterministic_algorithms(True)`.
- **Environment:** weekly decisions, lag 1, 15 bps, actions in `[−1, 1]` scaled ×5 (D-072).
- **Versions:** Stable-Baselines3 2.9.0, torch 2.14.1+cpu, Gymnasium 1.4.0, Python 3.13.7,
  Windows 11.

**Results (execution diagnostics only)**

| Item | Value |
| --- | --- |
| Runs completed / failed / attempts | **40 / 0 / 40** (no retries; runner exit 0; nothing quarantined) |
| Timesteps per run | **100,352** for all 40 runs (see the note below) |
| Training episodes per run | 202 completed (496 steps each) |
| Child-process time per run | min 80.4 s, median 83.0 s, max 235.5 s (c0 s42, the first run); total 3,470 s |
| Training wall time per run | min 76.5 s, median 79.1 s, max 229.3 s; total 3,311 s |
| Environment steps per second | min 437.6 (c0 s42), median 1,268.6, max 1,311.3 |
| Independent verification (`verify_grid.py`) | **40/40 runs passed; no problems** |
| Storage | about 11 MB for `data/processed/experiments/` (all runs) |

- **The independent verification checked, for every run:**
  - manifest status `completed` with a single completed attempt;
  - `run_safety.verify_run_dir` valid;
  - `run_id` equal to the identity hash and the folder name;
  - run spec equal to the D-066 configuration and seed, run kind `full`, budget 100,000;
  - code provenance equal to the clean `cc9784b`;
  - the deterministic-algorithms setting recorded;
  - pinned settings equal to `agent.yaml`;
  - data 2007-01-04 to 2016-12-30 (2,517 rows), with the training-line hashes of the four input
    files reproducing;
  - the scaler equal to the run config and fitted on training rows only (2,389 rows). It is one
    identical scaler for all 40 runs;
  - the checkpoint reloads with matching learning rate, `n_steps`, entropy coefficient and
    seed, finite weights and the `[−1, 1]` action space;
  - monitor rewards finite, every episode 496 steps, and episode counts matching the metadata.
- **Timestep note.** Stable-Baselines3 stops only after a complete rollout, so every run did
  100,352 timesteps: 196 × 512 or 98 × 1024. That is 352 more than the 100,000 budget (+0.35%),
  identical for all configurations and seeds. It is recorded here for the team, not changed.
- **Earlier outputs:** EXP-003 folders unchanged (`da738d8728a41f4e`); EXP-004 folder unchanged
  (`dd79f9e5dd837946`).
- **Logs:**
  - runner log at `data/processed/grid_logs/0f1c47502dc30d84-runner.log`;
  - one child log per run under `data/processed/experiments/grids/0f1c47502dc30d84/logs/`;
  - all git-ignored.
- **Run ids** (configuration: seed and run id):
  - c0: s42 `0f0e3865f322bb50`; s43 `50c87a250e26d231`; s44 `6fb9a9fd05e90a9b`;
    s45 `3bb1373b092bcd41`; s46 `be9599d9ff60cee0`
  - c1: s42 `ab299094121dbe7f`; s43 `f4cebc59c0b09255`; s44 `49939c7aa87413ac`;
    s45 `635096bc56deec6e`; s46 `f628c54f5b5b3693`
  - c2: s42 `5e95542366a5c2e6`; s43 `d9c972997ad6ecc0`; s44 `fed57b758969289a`;
    s45 `df59b44fa6f66948`; s46 `46a71af10378f1a4`
  - c3: s42 `bb95040edb112d30`; s43 `4c0b18c370d7bac6`; s44 `64bcf8642643a08a`;
    s45 `057b43075f480ab0`; s46 `dfd93db6f445172c`
  - c4: s42 `c12145d46246e1c7`; s43 `4f9be9680a6334bd`; s44 `e9819a04ccc36567`;
    s45 `9f585486f8b4ce4b`; s46 `8d929082251f7c7f`
  - c5: s42 `05ae6384c7f46fe0`; s43 `466aeeeb8b133e7b`; s44 `2ddeed5b510cf4eb`;
    s45 `7b75d47261a98e93`; s46 `26d128a131c83a63`
  - c6: s42 `183b5c0bf02a2f5e`; s43 `60f4d9e08713949c`; s44 `e6136843d31a5c18`;
    s45 `cd53a0bf1fba1eb6`; s46 `ebbde71cbdb55568`
  - c7: s42 `e2bc9a0387a8caee`; s43 `90cbda70224c331d`; s44 `06d56cf4abb2a559`;
    s45 `cfca6f8a07857b93`; s46 `13bb90916c3afbcb`

**Observations (not explained).**
- The grid took about 0.96 h, at the low end of the approximate 0.9–3.5 h estimate.
- The first run (c0 s42) was about three times slower than the other 39 (229 s of training
  versus about 77–81 s). Its cause, e.g. warm-up or machine load, is not established.
  - *Correction (2026-10-21, Milestone A close-out audit):* the other 39 runs took 76.5–79.7 s
    of training wall time and 80.4–83.7 s of child-process time, not "about 77–81 s". The
    comparison is unchanged: c0 s42 took 229.3 s of training, against a median of 79.1 s for
    all 40 runs.

**Interpretation.**
- The grid trained to completion under the accepted safeguards, and every output verifies.
- No policy has been evaluated. Training-episode rewards were checked only for being finite.
  They are training-split diagnostics and are **not** reported or interpreted as investment
  performance.
- These checkpoints are not results until evaluated under an approved protocol.

**Next steps.** Each needs a separate team decision or authorisation:
1. The operational definition of the selection metric and the evaluation policy: deterministic
   or stochastic actions, the validation window and funding, ties.
2. Authorisation to load validation data and run validation evaluation and selection (D-066).
3. Gate 3 items: bootstrap settings and stress windows.
4. Whether the 100,352-timestep note needs any record beyond this entry.

The test period stays sealed.

---

### EXP-004: Post-commit PPO smoke run on committed code (training split only; execution check, not a result)

- **Date:** run on 2026-10-19 (UTC): driver 17:29:03Z–17:29:12Z; training 17:29:08Z–17:29:11Z.
  Recorded on 2026-10-20.
- **Author(s):** run by Claude Code at the request of a team member, who approved this single run
  in the session. The message does not name its author; it was recorded under R-S (D-061), and
  the other teammate's confirmation was not sought.
- **Milestone:** M5.3. This is the final pre-grid check of the committed pipeline. It is **not**
  a grid run, and the 40-run grid was not started.
- **Git commit:** `20fe0b0` (`20fe0b021490de171c90849520b5906baa81553a`), **clean working tree**,
  checked before the run and recorded in the run identity:
  `code = {git_available: true, commit: 20fe0b0…, dirty: false}`.
- **Config files (SHA-256 prefixes of the working copies at run time):**
  - `agent.yaml` `cf3d767a1b222389`;
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb`.

  `backtest.yaml` and `environment.yaml` differ from their committed blobs only in line endings
  (CRLF in the Windows working copy): their LF-normalised hashes are identical, and
  `git diff HEAD -- configs` is empty. `agent.yaml` differs from EXP-003's `fb5cac2b0491bcb8`
  only through the later `execution` section and approval comments (D-074, D-075). Its grid,
  seeds, budget and pinned training settings are unchanged.
- **Random seed:** 42.
- **Data:** processed dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`, loaded with
  `train_only=True`; 2,517 rows, 2007-01-04 to 2016-12-30.
- **Periods used:** **train only.** The episode runs from decision 2007-07-05 to 2016-12-30.
  Validation and test values were not loaded or parsed.

**Question.** Does the committed pipeline (`20fe0b0`) complete a short training run end to end,
including the paths EXP-003 did not exercise?
- `torch.use_deterministic_algorithms(True)`;
- the per-run lock and exclusive finalisation;
- the grid runner's child-process launcher;
- code provenance in the run identity.

**Method.**
- **Driver:** a one-off script outside the repository launched **one** child process with the
  grid runner's launcher command, `python -m adaptive_portfolio.agents.ppo` with
  `PYTHONHASHSEED=0`, plus `--smoke --timesteps 4096`.
- **Timeout:** 600 s hard limit through the repository's `run_safety.run_with_timeout`.
- **Failure policy:** quarantine through `recover_stale` if the run failed, with no retry; it was
  not needed.
- **Watching:** while the child ran, the driver recorded whether the run's lock and staging
  directory existed.
- **Settings:** configuration 0 (learning rate 3e-4, `n_steps` 512, entropy coefficient 0), seed
  42, 4,096 timesteps, one torch thread. Other settings as in `agent.yaml` (D-074).
- **Environment:** weekly decisions, lag 1, 15 bps, actions in `[−1, 1]` scaled ×5 (D-072).
- **Versions:** Stable-Baselines3 2.9.0, torch 2.14.1+cpu, Gymnasium 1.4.0, Python 3.13.7,
  Windows 11.

**Results (execution diagnostics only)**

| Item | Value |
| --- | --- |
| Run id | `7d49ee0f53d6165e` (run kind `smoke`) |
| Status / child exit code / timed out | completed / 0 / no |
| Timesteps / training episodes | exactly 4,096 / 8 completed (496 steps each) |
| Total child-process time / training wall time | 7.6 s (7.632 s) / 3.4 s (3.414 s) |
| Environment steps per second (training) | 1,199.8 |
| Output checks (`verify_run.py`) | **28/28 passed** |
| Safety checks (`smoke_extra_checks.py`) | **12/12 passed** |

- **The 28 output checks** confirmed:
  - exactly the five run files, with no staging directory left;
  - `run_id` equals the folder name and the hash of the run config;
  - metadata matching the run identity, and output file hashes reproducing;
  - 4,096 timesteps;
  - data ending on 2016-12-30, with the training-line hashes reproducing (2,517 rows; later rows
    not read);
  - a training-only scaler (2,389 rows) matching the run config;
  - the checkpoint reloads with 4,096 timesteps, matching settings, finite weights and the
    `[−1, 1]` action space;
  - all logged training-episode rewards finite.
- **The 12 safety checks** confirmed:
  - child exit 0 within 600 s, and `run_safety.verify_run_dir` valid;
  - code provenance equal to the clean `HEAD` commit;
  - the deterministic-algorithms setting recorded in the run identity;
  - the per-run lock observed during the run and held by the child process (pid 20336), not
    the driver (pid 24336);
  - the staging directory `7d49ee0f53d6165e.staging-20336` observed;
  - after the run, the finalised folder present with no lock or staging directory (exclusive
    finalisation into an absent destination);
  - nothing quarantined;
  - no error in the child log;
  - the working tree still clean.
- **Deterministic algorithms** (`torch.use_deterministic_algorithms(True)`) were enabled during
  training. Training completed without raising, so no non-deterministic operation was hit.
- **Outputs:** `data/processed/experiments/7d49ee0f53d6165e/`.
- **Evidence:** `data/processed/smoke_checks/20261019T172904Z-c0-s42-7d49ee0f53d6165e.log` and
  `data/processed/smoke_checks/20261019T172904Z-7d49ee0f53d6165e-evidence.json` (git-ignored).
- **EXP-003 output folders** `d06b6c2971f6ff66` and `4ddbffd78cddcb65` were **unchanged**:
  combined SHA-256 `da738d8728a41f4e` before and after, and both re-verified 28/28.
- **Not exercised:**
  - the refusal to finalise into an existing destination (covered by unit tests only);
  - the grid manifest, because the grid runner launches only full runs.

**Reproducibility observation (this machine and configuration only).**
- The final model weights and the training episode-reward sequence of this run were
  **bit-identical** to those of EXP-003 Run A (`d06b6c2971f6ff66`).
- Run A used the same configuration, seed and budget, but a pre-hardening working tree, the
  determinism flag off, a different launch path and no fixed `PYTHONHASHSEED`.
- This is consistent with (a) the hardening not changing the training computation, and (b) a
  seeded run reproducing in a fresh process on this machine.
- It is one comparison on one machine, configuration and library set. It is **not** a general
  guarantee of reproducibility across machines, library versions or other configurations.
- The rewards are training-split execution diagnostics, **not** evidence of investment
  performance.

**Throughput observation (not explained).**
- Training ran at about 1,200 steps/s, versus about 320 in EXP-003, with the same library
  versions and one torch thread.
- Machine load or power state at the time is a plausible factor, but this run does not establish
  the cause.
- The approximate full-grid estimate (4.0 million steps, sequential) therefore ranges from
  about 0.9 h (at ~1,200 steps/s) to about 3.5 h (at ~320 steps/s). It is an extrapolation from
  three short runs. No budget change is proposed.

**Interpretation.** The committed pipeline runs end to end on the training split with its safety
features active. Nothing here evaluates a policy or says anything about portfolio performance.

**Next steps.**
- The team commits this entry; the grid id will change with the commit.
- Then `run_grid.py --plan` must show "allowed".
- The full 40-run grid needs separate explicit approval.

---

### EXP-003: M5.3 PPO throughput smoke test (training split only; execution check, not a result)

- **Date:** 2026-10-19. Run A 2026-10-19T10:39:58Z–10:40:11Z; Run B 10:40:48Z–10:41:01Z.
- **Author(s):** run by Claude Code at the request of a team member. The message approving
  both runs does not name its author; it was recorded under R-S (D-061), and the other
  teammate's confirmation was not sought.
- **Milestone:** M5.3 preparation (roadmap 4/6). It checks the throughput assumption behind the
  D-066 budget **before** any tuning.
- **Git commit:** code at `c1c1925` plus **uncommitted** M5.1–M5.3 working-tree changes. Record
  the commit hash here once the team commits them.
  - *Correction (2026-10-19, after the commit and push):*
    - The exact working-tree state that ran EXP-003 was **never committed as such**.
    - The code was committed later as `71e6333` and `85c40d1`, with documentation in `c387459`
      and `8da032a`, all pushed. Those commits also contain the pre-grid hardening done after
      EXP-003: run locks, exclusive finalisation, quarantine, code provenance in the run
      identity, and `torch.use_deterministic_algorithms(True)` during training.
    - According to the session record in the project journal, the hardening did not change
      the training computation path used here: the environment, simulator, reward and pinned
      PPO settings. This cannot be checked by a commit comparison, because the intermediate
      state was never committed.
    - **EXP-003 predates the deterministic-algorithm setting:**
      `torch.use_deterministic_algorithms(True)` was **not active** during these runs.
    - Separately, the run configs have no code hash, because they predate D-075.
    - The nearest committed code is `85c40d1`.
- **Config files (SHA-256 prefixes at run time):**
  - `agent.yaml` `fb5cac2b0491bcb8`;
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb`.
- **Random seed:** 42, for both runs.
- **Data:**
  - processed dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`, loaded with
    `train_only=True`;
  - 2,517 rows, 2007-01-04 to 2016-12-30;
  - training-line SHA-256 values are recorded in each run's `run_config.json`.
- **Periods used:** **train only.** The episode runs from decision 2007-07-05 to 2016-12-30.
  Validation and test values were not used, and none was loaded or parsed.

**Question.** Does the PPO pipeline run end to end, and what is its throughput (environment
steps per second) on one CPU thread? The answer is used to judge whether the D-066 budget is
feasible: 100,000 steps × 8 configurations × 5 seeds = 4.0 million steps.

**Method.**
- Stable-Baselines3 2.9.0 PPO, torch 2.14.1+cpu, Gymnasium 1.4.0, Python 3.13.7, Windows 11.
  One torch thread; 16 logical CPUs present; one run at a time.
- Settings: `run_kind: smoke`, 4,096 timesteps each, other settings as in `agent.yaml` (D-074
  pinned defaults).
- Weekly decisions, lag 1, 15 bps, actions in `[−1, 1]` scaled ×5 (D-072).
- Each run had a 10-minute hard limit (`timeout 600`). The outputs were then checked
  independently: 28 checks per run.

**Results (execution diagnostics only)**

| Run | Configuration | `n_steps` | Run id | Status | Timesteps | Training wall time | Env steps/s | Episodes | Process time incl. start-up |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0 (lr 3e-4, ent 0) | 512 | `d06b6c2971f6ff66` | completed | 4,096 | 12.802 s | 319.9 | 8 | ≈ 18 s |
| B | 2 (lr 3e-4, ent 0) | 1024 | `4ddbffd78cddcb65` | completed | 4,096 | 12.649 s | 323.8 | 8 | ≈ 17 s |

- **Both runs passed all 28 checks:**
  - exactly the five output files, no staging folder left, the folder name equal to the
    identity hash;
  - metadata containing the identical identity, file hashes reproduced, status `completed`,
    4,096 timesteps;
  - data ending 2016-12-30, with the training-line hashes reproduced;
  - a train-only scaler (2,389 rows) matching the run config;
  - a checkpoint that reloads with 4,096 timesteps, the matching hyperparameters, finite
    weights and the `[−1, 1]` action space;
  - every logged training-episode reward finite, and every completed episode 496 steps long.
- Each run completed 8 training episodes (3,968 steps); the remaining 128 steps were part of an
  unfinished ninth episode. `n_steps` 512 versus 1024 made no material speed difference: Run B
  was 1.2 % faster than Run A.
- Training-episode rewards were checked only for being finite. They are **not** reported or
  interpreted: these are 4,096-step runs, on training data, never evaluated.

**Approximate estimate for the full D-066 budget** (an extrapolation, not a measurement)
- At the mean measured 321.9 steps/s:
  - 4.0 million steps take about 12,400 s, i.e. **about 3.5 hours** of training when run
    sequentially on one thread;
  - plus about 5 s of start-up per run, about 3 minutes in total;
  - one 100,000-step run takes about 5.2 minutes.
- **Caveats:**
  - two short runs only;
  - sustained speed over 100,000 steps can differ (machine load, thermal limits, memory);
  - 16 CPUs could run several single-thread runs in parallel, which is not measured and
    needs approval.
- This lies within the design memo's assumed range (0.6–4 h, item 9). **No budget change is
  proposed.**

*Note (2026-10-19, after the pre-grid hardening): these two run configs predate D-075. They
contain no Git commit or working-tree hash; their code state is the one stated above. Their
folders are preserved unchanged (SHA-256 of all files checked).*

**Interpretation.** The pipeline runs end to end on the training split, and its outputs are
complete and reproducible. Throughput is at the low end of the memo's assumption, but the
D-066 budget stays practical. Nothing here says anything about portfolio performance.

**Next steps.** Any full run, the 40-run grid, tuning or validation evaluation each need separate
approval. Full runs would need a time limit larger than the smoke test's 10 minutes; at about
5.2 minutes per run, 15 minutes per run is a reasonable limit.

---

### EXP-002: Primary-convention conventional baselines, train and validation (Gate 1)

- **Date:** 2026-10-19 (local time; run at 2026-10-18T22:11Z)
- **Author(s):** run by Claude Code at the request of Parv Patel and Mandar Patil, after both
  confirmed Gate 1 on 2026-10-19. That approval evidence is self-declared in a shared-device
  session; see `approval_checklist.md` §0.1.
- **Milestone:** roadmap 4–5 (primary baseline record before any RL work)
- **Approval:** the run used only decisions recorded as Accepted on 2026-10-19:
  - D-007, D-009, D-010, D-013, D-015, D-023, D-031 (cost basis, no cap);
  - D-035–D-039, D-048–D-060.

  D-006, D-008, D-034, D-042 and D-044 are **acknowledged as provisional**, not validated.
- **Git commit:** code at `8e52693` plus **uncommitted** working-tree changes. Those were
  approval-neutral output wording, a test update, `periods_per_year: 252` and documentation;
  none changes computed values. Record the commit hash here once the team commits them.
  - *Correction (2026-10-19, pre-grid hardening): those changes were committed locally as
    `04dc44a` (`feat: record Gate 1 approvals, run EXP-002 baselines and prepare Gate 2
    packet`), which is not yet pushed. The code state of EXP-002 is therefore `04dc44a`.*
  - *Correction (2026-10-19, after the push): `04dc44a` was pushed to `origin/main` on
    2026-10-19, together with the later commits up to `8da032a`.*
- **Config files (SHA-256 prefixes at run time):**
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb` (used only for the window check).
- **Seeds:** none; the run is deterministic.
- **Data:**
  - processed dataset `8e00568ee2aa4de7`, from raw snapshot `e27437b97742fa43` (yfinance 1.7.0,
    retrieved 2026-10-15T10:21:14Z);
  - SPY, EFA, EEM, IEF, TLT, LQD, GLD; daily adjusted close. Read offline; no download.
- **Periods used:**
  - **train:** decisions from 2007-07-05 (126-session common window), returns earned
    2007-07-06 to 2016-12-30 (2,390 return periods);
  - **validation:** decisions from 2017-01-03, returns earned 2017-01-04 to 2019-12-31 (752);
  - **test: not used.** No `--include-test`; test-period return values were never parsed
    (D-060).
- **Command:**
  `python scripts/market_data.py --config-dir configs backtest --dataset-dir data/processed/8e00568ee2aa4de7`
- **Output:** `data/processed/backtests/c6d8c473258e3194/` (git-ignored). SHA-256 prefixes:
  - `ledger.csv` `ae141edb87a3f524`;
  - `executions.csv` `f604b0340b72d652`;
  - `metrics.json` `d6924a0511e6eee6`;
  - `metrics.csv` `b57f69a701ba27e2`;
  - `backtest_report.md` `951c56f0ce1e7653`;
  - `metadata.json` `30aba7b2885a198b`.
- **Software:** Python 3.13.7, numpy 2.5.4, pandas 3.0.6, adaptive_portfolio 0.1.0 (Windows).

**Question**
What do the three approved conventional baselines achieve on train and validation under the
primary convention (lag 1, 15 bps, 126-session window, N = 252)? This is the reference record
for any later comparison. No hypothesis about which strategy is better is tested, and nothing
was tuned.

**Method**
- **Strategies:** `equal_weight_monthly`, `buy_and_hold_equal_weight`,
  `inverse_volatility_monthly` (63-session lookback, cap 0.40).
- **Rules:** long-only; Σw ≤ 1 with cash at rf = 0; funding trade charged.
- **Protocol:** each split simulated independently from 100,000 in cash.
- **Metrics:**
  - per-session metrics, plus annualised metrics with N = 252, using √252 scaling and CAGR over
    the return periods;
  - Sharpe uses rf = 0 and excludes the funding row;
  - cumulative return and drawdown include the funding cost;
  - turnover is traded notional; annualised turnover counts recurring trades only.

**Results** (net of costs unless stated; descriptive; single historical path; no significance
testing)

| Split | Strategy | Rebal. | Gross cum. | Net cum. | Cost drag | Net max DD | Ann. return | Ann. vol | Ann. Sharpe (rf 0) | Recurring notional | Ann. recurring turnover | Total cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | equal_weight_monthly | 114 | 62.15 % | 61.06 % | 1.09 pp | −28.51 % | 5.15 % | 10.93 % | 0.516 | 3.503 | 0.369 | 0.675 % |
| train | buy_and_hold_equal_weight | 1 | 52.72 % | 52.49 % | 0.23 pp | −24.44 % | 4.55 % | 9.15 % | 0.534 | 0.000 | 0.000 | 0.150 % |
| train | inverse_volatility_monthly | 114 | 73.88 % | 71.55 % | 2.33 pp | −18.64 % | 5.85 % | 7.06 % | 0.843 | 7.979 | 0.841 | 1.347 % |
| validation | equal_weight_monthly | 36 | 29.13 % | 28.81 % | 0.32 pp | −10.42 % | 8.84 % | 5.93 % | 1.470 | 0.662 | 0.222 | 0.249 % |
| validation | buy_and_hold_equal_weight | 1 | 28.15 % | 27.96 % | 0.19 pp | −11.49 % | 8.60 % | 6.28 % | 1.355 | 0.000 | 0.000 | 0.150 % |
| validation | inverse_volatility_monthly | 36 | 27.01 % | 26.37 % | 0.63 pp | −7.58 % | 8.15 % | 4.56 % | 1.754 | 2.334 | 0.782 | 0.500 % |

- **Notes on the table:**
  - "Rebal." counts executions, including the funding trade.
  - Total traded notional = 1.0 (funding) + recurring.
  - Total cost is the sum of cost fractions, funding included.
  - No decision was dropped at split ends.
- **Per-session values** (rf 0), net volatility / net Sharpe:
  - train: 0.689 % / 0.0325, 0.576 % / 0.0336, 0.445 % / 0.0531;
  - validation: 0.373 % / 0.0926, 0.396 % / 0.0853, 0.287 % / 0.1105;

  in the table's strategy order.

**Verification (all passed)**
- outputs contain train and validation only, with every ledger date before 2020;
- all values are finite;
- the three strategies have identical dates in each split;
- each of the 302 executions happens exactly one session after its decision;
- every row's gross return was recomputed as the previous row's weights × that row's returns;
- cost = 15 bps × traded notional, net = g − c(1 + g), and the value path compounds from
  100,000;
- funding: notional 1.0 (within 1e-12), gross 0, cost 0.0015 on the first row;
- recurring turnover is 0 for buy-and-hold;
- cost drag > 0;
- targets are within [0, 0.40] with Σ ≤ 1;
- annualised Sharpe was recomputed as √252 × mean / std;
- metadata ids match;
- the output status text claims no approval state;
- **an identical re-run reproduced all six files byte for byte.**

**Interpretation (descriptive only)**
- **Inverse volatility:**
  - in both splits it had the smallest maximum drawdown and the lowest volatility;
  - it also traded about 2–3.5× the recurring notional of monthly equal weight and had the
    largest cost drag;
  - its annualised Sharpe (rf 0) was the highest of the three in both splits.
- **Cumulative return** ranks differ between splits: inverse volatility first in train, last in
  validation.
- **These are single historical paths** under placeholder costs and rf = 0, with no confidence
  intervals. **They do not show that any strategy is better,** and nothing here concerns PPO,
  which has not been implemented.
- **Compared with EXP-001** (lag 0, 62-row window), the figures differ modestly; the two runs
  use different conventions and windows and are not a controlled comparison.

**Limitations**
- Provisional data values (universe, date range, provider, validation thresholds, feature
  windows).
- Placeholder cost rates; rf = 0 for cash and Sharpe.
- Close-to-close execution, even at lag 1.
- √N annualisation assumes independent returns; untuned baselines; survivorship and selection
  bias in an ETF universe chosen with hindsight.
- Approval evidence self-declared, not technically verified.

**Next steps**
- The team commits the working-tree changes and records the commit hash above.
- Gate 2 (PPO design) decisions and dependency authorisation; then PPO training on train and
  validation only.
- The test split stays sealed until Gate 3.

### EXP-001: Conventional baselines on the training and validation splits (milestone 4)

- **Date:** 2026-10-15
- **Author(s):** project team (run by Claude Code at the team's request; to be checked by the team)
- **Milestone:** roadmap 4–5 (team milestone 4: portfolio simulation and conventional baselines)
- **Git commit:** none. Uncommitted working tree on top of `adffff5`; record the commit hash when
  the team commits.
- **Config files:** `configs/backtest.yaml`, `configs/environment.yaml`, `configs/data.yaml`,
  `configs/experiment.yaml` (defaults, unchanged)
- **Random seed(s):** not applicable (deterministic; no randomness)
- **Data:** yfinance live snapshot, raw id `e27437b97742fa43`, processed id `8e00568ee2aa4de7`.
  Universe SPY, EFA, EEM, IEF, TLT, LQD, GLD (provisional, D-034); daily adjusted close,
  2007–2024.
- **Backtest id:** `ac2d6b163d4f5e4b` (pipeline version 1); outputs in
  `data/processed/backtests/ac2d6b163d4f5e4b/` (git-ignored); reruns byte-identical.
- **Periods used:** train 2007-04-04 → 2016-12-30 (common start after 62 warm-up rows);
  validation 2017-01-03 → 2019-12-31. **Test: computed by the command but not reported here**
  (see D-051 open question).

**Question**
Does the simulator produce consistent, reproducible baseline results under the proposed
conventions? This is a pipeline check and a reference point. It is not a hypothesis about which
strategy is better, and no parameter was tuned.

**Method**
The three baselines of D-053:
- timing D-048 with lag 0;
- costs D-049: 10 + 5 bps on traded notional, including initial funding;
- constraints D-050: long-only, max weight 0.40, cash at rf 0;
- protocol D-051: independent per split, starting from cash.

**Assumptions and known limitations**
- All conventions are Proposed. Costs, cap and universe are provisional.
- Close-to-close execution at lag 0 is optimistic.
- Metrics are per session because D-023 is open: no annualised return, volatility or Sharpe is
  reported.
- Sortino is not implemented.

**Results** (net of costs unless stated; per-session values not annualised; descriptive only)

| Split | Strategy | Rebalances | Gross cum. | Net cum. | Cost drag | Net max DD | Net vol / session | Net Sharpe / session (rf 0) | Traded notional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | equal_weight_monthly | 117 | 66.93 % | 65.78 % | 1.15 pp | −28.56 % | 0.68 % | 0.034 | 4.60 |
| train | buy_and_hold_equal_weight | 1 | 54.39 % | 54.16 % | 0.23 pp | −25.94 % | 0.60 % | 0.032 | 1.00 |
| train | inverse_volatility_monthly | 117 | 73.73 % | 71.38 % | 2.36 pp | −18.15 % | 0.44 % | 0.052 | 9.11 |
| validation | equal_weight_monthly | 36 | 29.81 % | 29.48 % | 0.33 pp | −10.29 % | 0.37 % | 0.095 | 1.69 |
| validation | buy_and_hold_equal_weight | 1 | 28.85 % | 28.65 % | 0.19 pp | −11.51 % | 0.40 % | 0.087 | 1.00 |
| validation | inverse_volatility_monthly | 36 | 27.34 % | 26.71 % | 0.63 pp | −7.54 % | 0.29 % | 0.112 | 3.29 |

"Rebalances" counts executions, including the initial funding. No decisions were dropped at
split ends.

**Independent checks:**
- buy-and-hold matches its closed form;
- equal-weight monthly matches a separately written loop;
- inverse-volatility weights match a hand computation.
All agree to about 1e-8. Figures: none produced.

**Interpretation**
- The pipeline runs offline, deterministically, and agrees with independent recomputation.
- Differences between strategies are single-path historical outcomes under provisional costs
  and timing. They have no significance test, no annualisation and no test-period evidence.
  **They do not show that any strategy is better.**
- Descriptively: inverse volatility traded about twice the notional of equal weight and had
  the largest cost drag, and it had the smallest drawdowns in both splits.
- The ordering of cumulative returns differs between train and validation.

**Next steps**
- Team decisions on D-048 to D-054 and D-023.
- Decide whether test-split evaluation becomes opt-in.
- Lag-1 and cost-sensitivity runs if approved.

**Correction (2026-10-18), added after the milestone-4 audit; the entry above is unchanged:**
- **Git commit:** the code and configs used are those committed as `a7134b7` ("feat: add
  portfolio simulator and conventional baselines"), pushed to `origin/main`. GitHub Actions CI
  passed on that commit.
- The read-only audit (2026-10-18) re-ran the backtest from `a7134b7` in an isolated copy. All
  outputs were byte-identical except the `dataset_dir` path in `metadata.json`.
- **Timing:** this run used `execution_lag_sessions: 0`. Under D-055 (Proposed, 2026-10-18) lag 1
  is the proposed primary convention, and lag 0 an idealised sensitivity case. The figures above
  are therefore the **lag-0 sensitivity case**. No lag-1 run has been made or reported yet.
- **Test split:** this run (pipeline version 1) also computed test-split results, which were
  printed to the console during the milestone-4 session. They exist in a git-ignored local folder
  (`data/processed/backtests/ac2d6b163d4f5e4b/`). They are not recorded here, were not used for any
  choice, and must not be reported. From pipeline version 2 (D-056), test evaluation is opt-in.
- **Weight cap:** inverse-volatility holdings exceeded the 0.40 cap between rebalances (up to
  about 0.4117 on 19 training-split ledger rows; test-split rows are not reported). The cap
  applies to target weights at execution (D-057, Proposed).

**Correction (2026-10-18, milestone 4.2), appended; the entries above are unchanged:**
- **Commit hashes:** the commit cited above as `a7134b7` was rewritten on 2026-10-18 with
  changed author and committer metadata and force-pushed as `66f9ed7`. The file tree is
  identical, so the code and configs used by EXP-001 are unchanged. The original commit remains
  on the local branch `backup/main-before-author-rewrite`. CI passed on `a7134b7` (run #3) and
  on the current head `880d82c` (run #6). No separate run exists for `66f9ed7`.
- **Evaluation window:** EXP-001 used the milestone-4 common start (first training decision
  2007-04-04, 62 warm-up rows). Under the proposed D-058 the training window would start on
  2007-07-05. EXP-001 is not a record of the proposed primary protocol, which uses lag 1 and the
  126-session window.
