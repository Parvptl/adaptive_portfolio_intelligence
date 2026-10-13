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
