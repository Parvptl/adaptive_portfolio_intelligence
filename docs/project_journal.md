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
