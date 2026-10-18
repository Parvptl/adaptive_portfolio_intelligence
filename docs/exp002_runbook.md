# EXP-002 Runbook — PREPARED — NOT EXECUTED

> **Status: PREPARED — NOT EXECUTED.** EXP-002 has **not** been run, and no EXP-002 result
> exists.
> - It may run only after the Gate 1 decisions in [`approval_checklist.md`](approval_checklist.md)
>   are approved by both Parv Patel and Mandar Patil, and recorded as **Accepted** in
>   [`decision_log.md`](decision_log.md).
> - Prepared 2026-10-18 at commit `a03c4b7`, with uncommitted documentation changes.
> - Everything below was established from code, configuration and metadata only. No data rows
>   were read and nothing was run.

## 1. What EXP-002 is

- **Purpose:** the primary-convention baseline record on **train and validation only**.
  Settings, all still Proposed:
  - execution lag 1;
  - common window of 126 sessions;
  - the three existing baselines, untuned;
  - 15 bps on traded notional, funding charged;
  - long-only, target cap 0.40, cash at rf 0.
- **Not:** a test-split evaluation, a tuned comparison, or evidence that any strategy is better.
- **Relation to EXP-001:** EXP-001 used lag 0 and the milestone-4 window (from 2007-04-04). It
  stays as recorded, as the lag-0 sensitivity case.

## 2. Pre-flight checks (run immediately before the experiment)

These read configuration, code and metadata only. Each must pass, or the run does not start.

1. **Approvals:** every Gate 1 decision is recorded as Accepted with approvers and dates, and
   every §1.3 decision is approved or acknowledged as provisional by both teammates.
2. **Clean, known code state:** `git status` shows no unexplained changes. Record the commit
   hash.
3. **Quality gates:** `python -m pytest`, `python -m ruff check .`,
   `python -m ruff format --check .`, `python scripts/validate_config.py` and
   `python scripts/market_data.py validate` all pass.
4. **D-023:** if N = 252 is approved, set `periods_per_year: 252` in `configs/backtest.yaml`
   **before** the run. Otherwise leave it `null`.
5. **Dataset identity:** the configuration must still map to the existing snapshot:

   ```bash
   python -c "from pathlib import Path; from adaptive_portfolio.config import load_project_config; from adaptive_portfolio.data.pipeline import processed_dataset_dir; print(processed_dataset_dir(load_project_config('configs'), Path('.'), 'yfinance').name)"
   ```

   Expected output: `8e00568ee2aa4de7`. Anything else means a data decision changed; **stop**,
   since a rebuild or download needs separate authorisation.
   - `--dataset-dir` (below) loads the named directory **without** re-deriving the id, so this
     check is what ties the run to the approved configuration.
   - The loader still enforces the universe and order, the dates and the split labels against
     `experiment.yaml`.
6. **Expected output id** (computed 2026-10-18 from the current configs; it changes if any
   config changes):
   - `data/processed/backtests/ce46d29217983c40/` with `periods_per_year: null`;
   - `data/processed/backtests/c6d8c473258e3194/` with `periods_per_year: 252`.

   The old pipeline-version-1 folder `ac2d6b163d4f5e4b/` (lag 0, includes test results) is not
   touched and not reported.

## 3. Command (prepared, not executed)

```bash
python scripts/market_data.py --config-dir configs backtest --dataset-dir data/processed/8e00568ee2aa4de7
```

```bash
python scripts/market_data.py --config-dir configs backtest-report --dataset-dir data/processed/8e00568ee2aa4de7
```

**What sets each item** (there are no CLI flags for these; they come from the approved configs):

| Item | Source | Current value |
| --- | --- | --- |
| Dataset | `--dataset-dir` | `data/processed/8e00568ee2aa4de7` (yfinance 1.7.0 snapshot `e27437b97742fa43`, retrieved 2026-10-15T10:21:14Z) |
| Splits evaluated | default; **`--include-test` is never passed** | train, validation |
| Execution lag | `backtest.yaml` `execution_lag_sessions` | 1 |
| Common window | `backtest.yaml` `common_start_history_sessions`, checked against `features.yaml` by the CLI | 126 (first training decision 2007-07-05) |
| Strategies | `backtest.yaml` `strategies` | equal_weight_monthly, buy_and_hold_equal_weight, inverse_volatility_monthly (63) |
| Funding cost | `backtest.yaml` `charge_initial_funding` | true |
| Costs | `environment.yaml` | 10 + 5 bps on traded notional |
| Constraints and cash | `environment.yaml` | long-only, `max_weight` 0.40 on targets, `allow_cash` true, `max_turnover` null, rf 0 |
| Annualisation | `backtest.yaml` `periods_per_year` | null (per-session only) unless D-023 is approved |
| Output | `backtest.yaml` `output_dir` + id | `data/processed/backtests/<id>/` (git-ignored) |

**Argument parsing was verified without running anything** (`build_parser().parse_args`):
`include_test = False`, so the evaluated splits are (`train`, `validation`). No network access
is needed, and yfinance is not imported.

**What the command reads and writes** (from the code path `cli._cmd_backtest` →
`evaluation.backtest.run_backtest`):

| Access | What exactly | Test-period content? |
| --- | --- | --- |
| Reads configs | `data.yaml`, `environment.yaml`, `experiment.yaml`, `backtest.yaml`, `features.yaml` (the window check uses configuration only) | No |
| Reads `metadata.json` | Ids, provider, request, processing settings, schemas, limitations. No market values. | No values |
| Reads `splits.csv` | Rows dated before `test.start`, plus the date and label of the first row on or after it (§4) | One calendar date and label; **no values** |
| Parses `returns.csv` | Header plus exactly the rows before `test.start` (`read_csv_head`) | **No** (later lines are not decoded) |
| Computes | Weights from rows up to each decision; simulation on train and validation windows; metrics | No |
| Writes | `data/processed/backtests/<id>/` via a staging directory: `ledger.csv`, `executions.csv`, `metrics.json`, `metrics.csv`, `backtest_report.md`, `metadata.json` | No |
| Does **not** do | No full-file hash of any data file at run time, no network access, no reads of `prices*.csv`, the quality report, the raw snapshot or the feature outputs | — |

**Byte-level integrity vs value parsing:**
- The raw manifest stores SHA-256 checksums, created at build time.
- **Hashing** a file would read every byte, test rows included, without interpreting any value
  as a number. The backtest **does not** hash data files.
- If the team wants a checksum check before EXP-002, hashing `returns.csv` would read the
  test-row bytes as opaque data. That needs the team's explicit agreement under G-T.

## 4. Test-period rows: what the run touches (a governance decision is needed)

- **History (prepared 2026-10-18):** the loader read the whole `returns.csv` and
  `splits.csv`, test-period rows included, for contract checks, and the simulator checked every
  row for finiteness. Test rows were never simulated, evaluated or reported.
- **Implementation (2026-10-19; local, uncommitted, not approved):** the default run (no
  `--include-test`) now uses a bounded loader,
  `features.pipeline.load_processed_inputs(..., exclude_test=True)`:
  1. `splits.csv`, which holds dates and split labels and **no market values**, is read line by
     line up to and including the **first row dated on or after `test.start`** from
     `experiment.yaml`. The boundary therefore comes from the configured dates, not from the
     file's labels (strengthened 2026-10-19).
     - That row's label must equal the label the configuration implies, otherwise an error is
       raised **before** `returns.csv` is opened;
     - an earlier row labelled `test` is rejected the same way;
     - no later row is read.
  2. `returns.csv` is read with `data.cache.read_csv_head`: the header and exactly the rows
     before that first test row. Later lines are never decoded or parsed. The operating system
     may still buffer bytes beyond that point; they are not inspected.
  3. Every existing contract check runs on the rows that are read: column names and order, the
     universe against metadata, unique ascending dates, `splits.csv` dates equal to `returns.csv`
     dates, labels equal to `experiment.yaml` (via `data.splits.label_dates`), the multi-session
     check, and the simulator's finiteness check.
  4. With `--include-test` the previous full-file loading and full checks apply unchanged. The
     feature pipeline also still loads all rows.
- **What is still touched in the test period:** the date and label of the first row dated on
  or after `test.start` in `splits.csv`. No test-period return or price value is parsed.
- **Verified by tests** (`tests/test_backtest_pipeline.py`, synthetic data only):
  - test-period rows of `returns.csv`, and `splits.csv` rows after the first test row, replaced
    with undecodable bytes leave the default run's results byte-identical, while an
    `--include-test` run fails on them;
  - a `returns.csv` with all test rows physically removed gives byte-identical results;
  - bad values or labels, a mislabelled boundary row, a missing row or a wrong column order in
    the permitted rows are still rejected;
  - `read_csv_head` never decodes later lines.

  Added 2026-10-19:
  - a test-period row mislabelled `validation` (with an undecodable return line) fails with
    the label error before `returns.csv` is read;
  - the CLI path `backtest --dataset-dir` honours the boundary.

  Injected bugs were each caught by these tests: full reads restored; the boundary-row date
  unchecked; a label-based instead of date-based stop. This was a targeted check, not
  mutation testing.
- **Not verified on the live dataset**, so as not to touch it during preparation. The evidence
  is the synthetic tests.
- **Decision for the team (Gate 1, item G-T):**
  - **(a)** accept this bounded loading as satisfying the test-isolation rule for EXP-002;
  - **(b)** require stricter handling, e.g. not even reading the first test row's date. That
    would need row counts recorded in the dataset metadata, i.e. a rebuild, which needs
    separate authorisation.

  The implementation must also be reviewed (and, if wanted, committed) by the team. Until
  both of you choose, EXP-002 must not run.

## 5. Output verification plan (after a legitimate run)

Use only the output files, which contain train and validation only, plus metadata.

| # | Check | How |
| --- | --- | --- |
| 1 | Only train and validation | `metrics.json` `evaluated_splits == ["train", "validation"]`; `test_split` starts with "excluded"; no `test` in the `split` column of `ledger.csv`, `executions.csv` or `metrics.csv`; no `## test` in the report |
| 2 | Finite values | No NaN or inf in the numeric ledger and metrics columns. Annualised fields are `null` unless D-023 is approved. |
| 3 | Same dates for every strategy | Per split, the set of `ledger.csv` dates is identical across the three strategies; all `first_date` values in `metrics.json` are equal |
| 4 | Window and timing | `windows.train.first_decision_date == 2007-07-05`, `required_history_sessions == 126`. `first_execution_date` is the next session (lag 1). Validation first decision is 2017-01-03, last return 2019-12-31. |
| 5 | Funding treatment | For every strategy and split: `funding_traded_notional == 1.0`; the first ledger row has `gross_return 0` and `cost_fraction 0.0015`; `total_traded_notional == funding + recurring` |
| 6 | Recurring turnover | Buy-and-hold `recurring_traded_notional == 0`; monthly strategies > 0 |
| 7 | Costs reach net results | `cost_drag > 0` and net ≤ gross cumulative return for every row; `total_cost_fraction` includes the funding charge |
| 8 | Identity and reproducibility | `metadata.json`: `processed_dataset_id 8e00568ee2aa4de7`, `raw_dataset_id e27437b97742fa43`, `backtest.execution_lag_sessions 1`, `common_start_history_sessions 126`, `evaluated_splits`, software versions. Directory name equals the expected id (§2.6). |
| 9 | Determinism | Re-run the same command; the SHA-256 of all six output files is identical |
| 10 | Record | Append EXP-002 to `experiment_log.md`. Include the commit, exact command, ids, dates, settings, the metrics with their definitions, and the limitations: provisional data decisions; rf = 0; untuned baselines; per-session metrics if D-023 is unapproved; single historical path. **No result is written anywhere before the run has actually happened and passed checks 1–9.** |

If any check fails, stop and diagnose. A fix that changes a research decision, the dataset, the
costs, the splits or the methodology needs approval before a re-run.
