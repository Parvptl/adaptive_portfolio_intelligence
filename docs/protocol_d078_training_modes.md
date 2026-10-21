# Protocol D-078 (Proposed): training-period evaluation of existing checkpoints, deterministic vs sampled actions

- **Status: PROPOSED, not approved.** Nothing in this document is implemented or has been run.
  Approval is needed in three separate steps (§12) before anything is executed.
- **Date drafted:** 2026-10-21, by Claude Code at a team member's request, for team review.
- **Origin:** item 1 of D-077 (Proposed); see `docs/exp006_turnover_diagnostic.md` §3.
- **Proposed record ids:** decision **D-078**; experiment **EXP-007** when run.
- **Data:** the **training split only** (2007–2016). No validation or test row is read. The test
  period (2020–2024) stays sealed.
- **What it does not change:** D-076, the D-076 evaluator (`agents/evaluate.py`,
  `configs/evaluation.yaml`, protocol hash `e652adec1095c95a`), the EXP-006 outputs, the
  configuration-4 selection, and every training output.
- **What it does not do:** no training, no tuning and no selection. No choice in this protocol
  may be revised after its results are seen.

## 1. Purpose and questions

EXP-006 evaluated the final checkpoints with **deterministic** actions (the policy's mean action)
on validation. During training, the same policies acted with **sampled** actions (the mean plus
Gaussian noise; final noise std 0.69–1.02 on the `[−1, 1]` action scale), and the training
rewards come from those sampled actions.

This diagnostic describes, **on the training period only**:

- **Q1:** how each final checkpoint performs in-sample with deterministic actions, under exactly
  the EXP-006 conventions;
- **Q2:** how the deterministic result compares with the distribution of results from sampled
  actions for the same checkpoint;
- **Q3:** how the in-sample results compare with the three baselines on the same training
  window;
- **Q4:** whether the final checkpoints' sampled rollouts are consistent with the late training
  episodes recorded in `monitor.csv`.

It is **descriptive**. It does not test a hypothesis and cannot establish causes (see §10).

## 2. Window and timing (identical to training and to EXP-002's training window)

| Item | Value | Source |
| --- | --- | --- |
| Split | `train` (2007-01-01 to 2016-12-31 in `experiment.yaml`) | configuration |
| Rows loaded | training rows only, `train_only=True` (2007-01-04 to 2016-12-30). As in EXP-005 training, `splits.csv` is read up to and including the date and label of the first validation session (the boundary check). No validation or test market value, feature or regime is parsed | `make_training_env`, `_read_splits_before`, run configs |
| First decision `k0` | 2007-07-05 (126 sessions of history, `common_start_history_sessions`) | run configs `first_decision_date` |
| Funding execution `x0 = k0 + 1` | 2007-07-06 | EXP-002 training window |
| Last return row `e` | 2016-12-30 | run configs `last_row_date` |
| Decisions | weekly (D-065): `k0`, then the first session of each later ISO week, up to the last decision that earns a return by `e`; **496 decisions** | `episode_decisions`; run configs `steps_per_episode` |
| Execution | the target decided at the close of `d_k` executes at the close of `d_k + 1` (lag 1, D-055) | `backtest.yaml` |
| Ledger rows | 2,391 (from `x0` to `e`); 2,390 return periods after the funding row | EXP-002 training metrics |

- **Episodes:** each policy rollout is one full training episode from cash, reset
  deterministically (`env.reset(seed=0)`, no random start), exactly as in training and EXP-006.
- **Check:** the environment window `(first_decision, first_execution, last_row)` must equal
  `split_window(labels, dates, "train", 126, 1)`. Otherwise the run stops.

## 3. Checkpoints and seeds

- **Included:** all **40** final checkpoints of grid `0f1c47502dc30d84` (EXP-005): 8
  configurations × training seeds 42–46, the same `model.zip` files as EXP-006.
- **Why all 40, not only configuration 4:** the question concerns how the learning rate and the
  entropy coefficient relate to in-sample behaviour. Nothing is selected from the results. *(U1)*
- **Integrity:** checked by the D-076 function `discover_checkpoints`, imported unchanged:
  - manifest and run ids;
  - clean training commit;
  - data ids;
  - training data ends before the validation start;
  - the scaler;
  - recorded model hashes.

  Each `model.zip` is re-hashed before loading. Any failure stops the whole run. No checkpoint
  is skipped or substituted.
- **No intermediate checkpoints exist** (D-066), so training-time behaviour is available only
  through `monitor.csv` (§7, C5).

## 4. Inference semantics

### 4.1 Deterministic actions (as D-076)

- `model.predict(observation, deterministic=True)`: the mean of the Gaussian policy, clipped to
  `[−1, 1]` by Stable-Baselines3.
- Then the D-072 scaling (`5u`) and the D-063 mapping: capped softmax, with excess weight sent to
  cash.
- One rollout per checkpoint, plus a **repeat rollout** that must reproduce it bit for bit. The
  run stops if it does not.

### 4.2 Sampled actions (the training-time mechanism)

- **Mechanism:** `model.predict(observation, deterministic=False)`. This is the same code path
  Stable-Baselines3 used to collect training rollouts:
  - an action is drawn from `Normal(mean(obs), exp(log_std))` with torch's global generator
    (`rsample`);
  - it is clipped to `[−1, 1]` (`np.clip` in `predict`, and likewise in `collect_rollouts`);
  - the environment applies the same scaling and mapping.

  *(U4)*
- **Rollouts:** **R = 50 independent rollouts per checkpoint** (*U2*), indexed `r = 0..49`.
- **Seeds:** immediately before rollout `r` of every checkpoint, call
  `stable_baselines3.common.utils.set_random_seed(10_000 + r)` (Python, NumPy and torch). The
  rollout seeds are therefore **10000–10049, the same for every checkpoint** (common random
  numbers). *(U3)*
- **Independence:** nothing else may draw from these generators between seeding and the end of
  the rollout. A rollout's result therefore depends only on (checkpoint, `r`), not on the order
  of execution.
- **Reproducibility check:** rollout `r = 0` of the first checkpoint is repeated at the end of
  the run and must match bit for bit.
- **Determinism settings (as D-074 and D-076):** `torch.set_num_threads(1)`;
  `torch.use_deterministic_algorithms(True)`; CPU. Bitwise reproducibility across machines is not
  claimed.
- **Recorded per checkpoint:** `exp(log_std)` for each action dimension. This is a model
  parameter, not data; in this configuration it does not depend on the state, because gSDE is
  off.

## 5. Accounting, costs and constraints (identical for every rollout and baseline)

- Start in cash at `initial_capital` 100,000 at `k0`.
- The funding trade at `x0` is charged.
- 15 bps on non-cash traded notional (10 + 5 bps, D-049, D-007).
- Long-only, with cash allowed. The 0.40 cap applies to **target** weights (D-057); holdings may
  drift above it.
- `max_turnover` is null.
- Cash return 0; rf = 0; N = 252.
- The final value is marked to market at the close of `e`, with no liquidation and no terminal
  cost.
- **Policies:** the targets decided by the environment are re-simulated with `simulate` (the
  baselines' path). The environment's own ledger must equal the simulator's ledger exactly
  (values and weights), **in both action modes**. Otherwise the run stops.
- **Baselines:** the three `backtest.yaml` strategies, through `strategy_targets` and
  `simulate`, on the same window. Their metrics **must equal EXP-002's training metrics**
  (backtest `c6d8c473258e3194`, `metrics["train"]`). Otherwise the run stops. *(U11)*
- **Not deterministic or sampled:** the baselines have no random actions; each is run once.

## 6. Metrics

All metrics are computed from a ledger by `summarize_window` (the D-076 functions), plus the new
items marked *new*. The definitions are those of EXP-006 unless stated.

**Primary (per checkpoint, for each action mode)** *(U6)*:
1. **Annualised net Sharpe:** `√252 · mean / std (ddof = 1)` of net returns on the rows after
   the funding row (`annualised.net_sharpe`).
2. **Annualised traded notional:** recurring traded notional / return periods × 252
   (`annualised.annualised_traded_notional`, D-052, D-059).
   - Traded notional is Σ|target − drifted weight| over the 7 ETFs: the cash leg is
     excluded, and this is the D-049 cost base.
   - The initial funding trade is excluded and reported separately.
   - With 2,390 return periods, this is Σ recurring / 2,390 × 252.
   - Two-way turnover, which includes the cash leg, is a secondary metric only.

**Secondary:**
- **Gross annualised Sharpe** *(new, U5)*: the same formula on the ledger's `gross_return`
  over the same rows as the net Sharpe.
  - Exactly: `sharpe_ratio(ledger["gross_return"].to_numpy()[1:], 252,
    annual_risk_free_rate=0.0)`. This drops the funding row; `ddof = 1`; rf = 0.
  - `gross_return` is the return of the pre-trade holdings before any cost.
  - The existing metrics have no gross Sharpe.
- Net and gross cumulative return; cost drag (gross − net cumulative return).
- Total cost value, split into funding and recurring cost value.
- Net and gross maximum drawdown (including the funding row, as D-076), with the net peak and
  trough dates.
- Net annualised return and volatility; final value.
- **Episode log growth** *(new)*: `log(final value / initial capital)`.
  - It must equal the sum of the D-064 rewards that the environment returned over the same
    rollout, to 1e-9.
  - It is the same quantity that training logged in `monitor.csv` column `r`, for earlier policy
    versions; that link is used only in C5.
- **Behaviour** *(new; definitions as in the EXP-006 diagnostic)*:
  - mean target cash;
  - share of executions with at least one ETF at the cap;
  - mean traded notional per recurring execution;
  - the target-change share of traded notional;
  - the **clip share**, i.e. the share of action components at ±1 after clipping.
- **Undefined metrics:** any undefined Sharpe, e.g. from zero variance, stops the run, as in
  D-076.

## 7. Summaries and comparisons (all fixed in advance; no tuning; no selection)

**Stochastic variability, per checkpoint and metric over the R = 50 sampled rollouts:**
- the mean;
- the standard deviation (ddof = 1);
- the Monte Carlo standard error of the mean (`std / √R`);
- the minimum;
- the 5th, 25th, 50th, 75th and 95th percentiles (NumPy `linear`);
- the maximum.

This dispersion measures the **policy's own action noise on one fixed historical path**. It is
**not** uncertainty about future markets and supports no statistical test of performance.

**Pre-declared comparisons:**

| Id | Comparison | Definition |
| --- | --- | --- |
| C1 | Mode gap (each primary metric) | `Δ = deterministic − median(sampled)`. The **percentile rank** of the deterministic value among the 50 sampled values counts ties as ½. **Label** *(U7)*: "below" if under the 5th percentile, "above" if over the 95th, otherwise "within". |
| C2 | Turnover ratio | Deterministic / median sampled annualised traded notional. |
| C3 | In-sample vs baselines | For each checkpoint and mode (deterministic, and sampled median), the count of the 3 baselines whose training net Sharpe it exceeds. Totals over the 40 checkpoints. |
| C4 | Per configuration | The median over the 5 seeds of each checkpoint-level quantity above. Descriptive only: **no ranking or selection is derived from it**, and the D-066 selection is unaffected. |
| C5 | Consistency with training logs | Per checkpoint: how many of the last 10 `monitor.csv` episode rewards lie inside the sampled [5th, 95th] range of episode log growth. Information only: the monitored episodes came from earlier policy versions within the last updates. |

**Validation and test data are not used for any choice.** Every setting above (R, seeds,
metrics, percentiles, labels) is fixed before execution. No setting is chosen or changed from a
validation or test result.

**Reporting juxtaposition** *(U9; after the outputs are final and recorded)*:
- The EXP-007 write-up may show, next to the training results, the **already published**
  EXP-006 validation net Sharpe of the same checkpoints, with a Spearman rank correlation.
- This uses no new validation rows and no new validation metrics.
- It is descriptive and must be labelled as such.
- The decision to run this diagnostic was itself prompted by EXP-006's validation results. That
  is stated, not hidden.

## 8. Outputs, identity and provenance

- **Location:** `data/processed/diagnostics/training_modes/<diagnostic_id>/` (git-ignored). It
  is written in staging and finalised exclusively, **never overwritten**. A failure is
  quarantined, not deleted (D-075 helpers). *(U12)*

**Files:**

| File | Rows | Content |
| --- | --- | --- |
| `diagnostic.json` | — | Status text; id; protocol hash; window; C1–C5 results; the per-checkpoint `exp(log_std)` |
| `deterministic_metrics.csv` | 40 | Checkpoint fields (configuration, seed, hyperparameters, run id, model hash), every §6 metric |
| `sampled_rollouts.csv` | 40 × 50 | The same, plus `rollout` and `rollout_seed` |
| `sampled_summary.csv` | 40 × metrics | §7 statistics, the deterministic value, Δ, the percentile rank and the label (long format) |
| `configuration_summary.csv` | 8 × metrics | C4 medians over seeds (descriptive) |
| `baseline_metrics.csv` | 3 | Baseline metrics plus `matches_exp002 = true` |
| `ledgers_deterministic.csv` | 43 × 2,391 | Ledgers of the 40 deterministic policies and the 3 baselines |
| `ledgers_sampled_r0.csv` | 40 × 2,391 | Ledgers of sampled rollout 0 only. The other rollouts are reproducible from their seeds *(U8)* |
| `metadata.json` | — | The identity (below), start time, wall time, SHA-256 of every other file |

**Identity (hashed into `diagnostic_id`):**
- the schema version and the protocol (`configs/training_diagnostic.yaml`, normalised; its own
  `protocol_hash`, separate from D-076's);
- the grid id and manifest hash, and every checkpoint (run id, model SHA-256);
- the dataset and feature-set ids;
- the **SHA-256 of the training lines read**. This must equal each checkpoint's
  `run_config.json` `data.train_prefix_sha256`, which proves the bytes are the ones it was
  trained on;
- the split bounds and the "rows read before `validation.start`" rule;
- the backtest and environment conventions;
- the code state (a clean commit is required), the package versions and the determinism
  settings.

**Data-boundary checks (each stops the run if it fails):**
1. Rows are loaded with `train_only=True`. `assert_training_only` is applied to returns and
   features, against the configured dates **and** the labels.
2. The latest date held is before 2017-01-01.
   - No validation or test market value, feature or regime is parsed.
   - Only the date and label of the single `splits.csv` boundary row are read, as in training
     and D-060.
   - There is no option to select another split.
3. The training-line hashes equal those recorded at training time, and the refitted scaler
   equals every checkpoint's `scaler.json`.
4. The dataset and feature ids are unchanged between the plan and execution.
5. The window equals `split_window(train)`, and all 43 ledgers have identical dates.

## 9. Execution design

- **`--plan`:** reads only configuration, the manifest, run directories and dataset/feature
  metadata. It loads **no data rows** and writes nothing. It prints the diagnostic id, the
  protocol hash, the 40 verified checkpoints, the window rule and the output path.
- **`--execute`:** requires `--confirm-training-diagnostic` and a clean committed tree.
- **Runtime estimate (not measured):** about 2,040 policy rollouts (40 × (1 + 50)) plus repeat
  checks, of 496 steps each. Scaling EXP-006's 4.9 s for 40 × 156 steps gives roughly 15
  minutes on the same machine.

## 10. What the results can and cannot support

**Can support (descriptive, in-sample, this dataset and these checkpoints only):**
- how the deterministic final policies behave on the period they were trained on, under the
  EXP-006 conventions;
- whether deterministic and sampled actions differ in in-sample net Sharpe, turnover and costs,
  and by how much relative to the rollout dispersion;
- whether the policies outperform, match or trail the baselines in-sample;
- whether the final checkpoints are consistent with the late training logs.

**Cannot support:**
- **Overfitting as a cause.** A high in-sample result next to the lower EXP-006 validation
  result is *consistent with* overfitting, but other explanations remain:
  - the market conditions differ (2007–2016 includes the 2008 crisis);
  - the baselines' own Sharpe also differs between periods;
  - selection effects.
- **Causes of turnover or underperformance.** No variable is manipulated in a controlled way.
- **Choosing sampled actions for evaluation.** Any change to D-076's deterministic rule would be
  a new decision, and it could not be validated without another validation look.
- **Statistical significance or out-of-sample performance.** There is one historical path; the
  rollout dispersion is policy noise, not sampling uncertainty about markets.
- **Anything about the test period.**

## 11. Open protocol choices, with proposed defaults

| Id | Choice | Proposed default | Alternatives |
| --- | --- | --- | --- |
| U1 | Checkpoints | All 40 | Configuration 4 only (5 checkpoints) |
| U2 | Sampled rollouts per checkpoint | R = 50 | 20; 100 (about 2× runtime) |
| U3 | Seeds | 10000 + r, common to all checkpoints | Distinct seeds per checkpoint, e.g. `10000 + 100·index + r` |
| U4 | Sampling mechanism | SB3 `predict(deterministic=False)` with seeded global generators (the training mechanism) | Explicit NumPy generator draws from the policy mean and std (independent of torch's generator) |
| U5 | Gross Sharpe | New metric as §6 | Omit |
| U6 | Primary metrics | Net Sharpe and annualised traded notional | Net Sharpe only |
| U7 | Label band | [5th, 95th] percentile | [2.5th, 97.5th] |
| U8 | Sampled ledgers saved | Rollout 0 only | None; all (about 1 GB) |
| U9 | Juxtaposition with EXP-006 validation | Allowed in the write-up, descriptive, after outputs are final | Not allowed |
| U10 | Record ids | D-078; EXP-007 | — |
| U11 | Baseline equality with EXP-002 | Hard check (stop on mismatch) | Report only |
| U12 | Output location | `data/processed/diagnostics/training_modes/` | `data/processed/evaluations_train/` |

## 12. Required code changes and tests (to be implemented only after step A2 below)

**Code (no new dependencies; D-076 code and config untouched):**
1. **`src/adaptive_portfolio/config.py`:** `TrainingDiagnosticConfig` (with a `SamplingConfig`)
   as plain dataclasses, plus `load_training_diagnostic_config`, `to_dict` and
   `protocol_hash()`. Validation:
   - `split == "train"` only;
   - modes exactly `{deterministic, sampled}`;
   - `1 ≤ rollouts ≤ 1000`; `seed_base ≥ 0`;
   - the mechanism is one allowed value;
   - quantiles sorted, in (0, 1), and include 0.5;
   - the label band is a pair of the declared quantiles;
   - `baseline_reference` is a 16-hex id.
2. **`configs/training_diagnostic.yaml`:** the §2–§8 settings, with the U-defaults marked
   PROVISIONAL until D-078 is accepted.
3. **`src/adaptive_portfolio/agents/training_diagnostic.py`:**
   - `plan_diagnostic` (no rows);
   - `rollout(model, env, mode, seed)`, returning targets, rewards and clip counts;
   - `evaluate_diagnostic` (in memory);
   - `run_diagnostic`: lock, staging, exclusive finalisation, quarantine, clean-tree check;
   - `main` (CLI).

   It reuses `make_training_env`, `discover_checkpoints`, `_data_ids` and `_flatten` (imported
   from `agents/evaluate.py`, unchanged), as well as `simulate`, `strategy_targets`,
   `split_window`, `summarize_window`, `sharpe_ratio` and the `run_safety` helpers.
4. **`scripts/evaluate_training_modes.py`:** a thin CLI wrapper, the same pattern as
   `scripts/evaluate_validation.py`.
5. **`scripts/validate_config.py`:** print the diagnostic configuration and its protocol hash.
6. **Documentation:**
   - technical handbook (new section);
   - `architecture.md` (module and data flow);
   - glossary;
   - README and roadmap status.

**Tests:** `tests/test_training_diagnostic.py`, using synthetic data only and offline. The parts
that need SB3 are marked `rl`.
- **Config:**
  - the default loads;
  - each validation rule rejects bad values;
  - the protocol hash is stable under YAML formatting and changes with every setting;
  - **the D-076 protocol hash is still `e652adec1095c95a`** (a regression guard).
- **Plan:**
  - an audit hook shows that no returns, features, regimes or splits file is opened;
  - nothing is written;
  - corrupted checkpoints are refused (reusing the evaluator fixtures).
- **Data boundary:**
  - with every row on or after the validation start replaced by undecodable bytes, the results
    are identical;
  - a train-prefix hash mismatch is refused;
  - a scaler mismatch is refused;
  - there is no split option in the CLI.
- **Window and parity:**
  - the window equals `split_window(train)`;
  - the environment ledger equals the `simulate` ledger in both modes;
  - all ledgers share dates.
- **Determinism:**
  - two deterministic rollouts are bit-identical;
  - sampled rollout `r` is bit-identical whether run alone or in sequence (order independence);
  - different seeds give different targets when the std > 0;
  - with `log_std` set very low, sampled ≈ deterministic;
  - all sampled actions are within [−1, 1];
  - the clip share is counted correctly.
- **Metrics:**
  - the gross Sharpe equals `sharpe_ratio` on the gross rows after funding;
  - episode log growth = Σ rewards = log(final / initial);
  - the summary statistics, percentile rank (ties ½) and labels are correct on known arrays;
  - a baseline mismatch with the reference is refused.
- **Outputs:**
  - the exact file set;
  - the hashes in the metadata;
  - id = hash(identity);
  - nothing is overwritten;
  - a dirty tree is refused;
  - the lock is held; failures are quarantined;
  - CLI exit codes: 2 without the confirmation flag, 1 on expected failures, 0 for the plan.

## 13. Planned commands (only after approvals A1–A3)

```bash
python scripts/evaluate_training_modes.py --plan --dataset-dir data/processed/8e00568ee2aa4de7
```

```bash
python scripts/evaluate_training_modes.py --execute --confirm-training-diagnostic --dataset-dir data/processed/8e00568ee2aa4de7
```

The diagnostic id and the protocol hash will be known only after the implementation is
committed, because the identity includes the commit. The execution authorisation (A3) should
name them, as was done for EXP-006.

## 14. Approvals required, in order (each under R-S, §0.0 of the approval checklist)

1. **A1, protocol:** accept, amend or reject D-078, including choices U1–U12. Accepting D-078
   adopts **only item 1 of D-077**; items 2–5 stay Proposed.
2. **A2, implementation:** authorise writing the code, configuration, tests and documentation
   of §12. Then review, and commit only on an explicit instruction.
3. **A3, execution:** authorise one run of the §13 `--execute` command. The authorisation names
   the diagnostic id, protocol hash, commit, grid `0f1c47502dc30d84` and dataset
   `8e00568ee2aa4de7`. It covers training data only: no validation or test rows, no training,
   no tuning, no protocol change.

---

*Revision before review (2026-10-21, appended; no protocol choice changed):*
- §2 and §8 now state the `splits.csv` boundary-row read exactly.
- §6 gives the exact gross Sharpe call and the turnover basis.
- Status is unchanged: **D-078 Proposed; EXP-007 planned, not executed.**
- In the Phase D roadmap, EXP-007 is optional research and **not a prerequisite for Gate 3**.
  Its results must not be used to tune anything against validation or test data.
