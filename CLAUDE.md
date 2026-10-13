# CLAUDE.md

Guidance for AI-assisted coding sessions (Claude Code and similar) in this repository.

## Project in one paragraph

Adaptive Portfolio Intelligence is an academic research project (Parv Patel, Mandar Patil): an
explainable, regime-aware reinforcement learning system for dynamic portfolio allocation, compared
against traditional strategies under transaction costs and realistic constraints. It is research and
decision support, **not financial advice**. No performance improvement is assumed in advance.

## Before changing anything

1. **Inspect first.** Read the relevant modules in `src/adaptive_portfolio/`, their tests in `tests/`,
   the configs in `configs/`, and `docs/architecture.md` / `docs/roadmap.md` before editing. Skim the
   latest entries in `docs/project_journal.md` and open items in `docs/decision_log.md`.
2. **Check the current milestone** in `docs/roadmap.md` and keep work inside its scope.
3. **Run the tests** (`python -m pytest`) to know the baseline state before you change it.

## How to work

- **Work incrementally.** Small, reviewable changes; one milestone or sub-task at a time.
- **Do not silently change assumptions or interfaces.** Changing a config key, a default value, a
  function signature, a return type, a split boundary, a cost assumption or a metric definition must
  be stated explicitly to the user and reflected in docs/tests. If unsure, ask.
- **Core logic lives in `src/`.** Notebooks are for exploration only and import from the package.
- **Prefer small, readable functions** with type hints and docstrings where they add clarity. Avoid
  speculative abstractions.
- **Dependencies:** add only what the current milestone needs, with version bounds in
  `pyproject.toml`. Do not add large ML frameworks (e.g. PyTorch, Stable-Baselines3) until the RL
  milestone requires them.
- **Configuration:** extend `src/adaptive_portfolio/config.py` (plain dataclasses + explicit
  validation). Do not introduce a configuration framework. Label unvalidated values as PROVISIONAL.
- **Tests:** add or update tests with every behavioural change. Tests and CI must run offline, with
  no market-data credentials or downloaded datasets; use small synthetic data in tests. Mark any
  network-dependent test with `@pytest.mark.network`.

## Research scope

- The submitted abstract (`Abstract.pdf`) defines the required scope. The README's "Scope" table and
  the [R]/[F]/[O] labels in `docs/roadmap.md` distinguish required work from optional extensions.
- PPO is a **candidate** algorithm, not a committed choice. Do not describe it as final.
- Do not start an optional extension ([O]) or change the research scope without the team's approval,
  recorded in `docs/decision_log.md`.
- Values marked PROVISIONAL (asset universe, date ranges, costs, slippage, weight limits, split
  dates) are not approved. Never describe them as validated or approved unless `decision_log.md`
  records that approval.
- Never modify `Abstract.pdf`.

## Documentation maintenance (required)

Keep these documents current **whenever the work touches them**. Update them in the same task as the
code change, not later:

| Document | Update when |
| --- | --- |
| `docs/project_journal.md` | Every working session: add a dated entry (what was done, findings, checks actually run, open issues, AI assistance used). |
| `docs/technical_handbook.md` | Setup, commands, config keys, module interfaces, conventions (timing, return and metric definitions) change. |
| `docs/decision_log.md` | A design, data, methodology or scope decision is proposed, approved, rejected or superseded. Never mark a decision approved on the team's behalf. |
| `docs/experiment_log.md` | Any experiment whose results are discussed, plotted or reported (including negative results). |
| `docs/presentation_guide.md` | Key messages, demonstrable results or the honest status of the project change. |
| `docs/glossary.md` | A new technical term, metric or abbreviation appears in code or docs. |
| `docs/roadmap.md` | A milestone starts, finishes, or changes scope. |
| `docs/architecture.md` | A module's responsibility, interface or data flow changes. |
| `README.md` | Setup, status, scope or headline structure changes. |

Never fabricate implementation details, experiment results, dates or approvals in any document.

## Before finishing a task

Run and report the actual results of:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Also run `python scripts/validate_config.py` when configs or the loader change.

If something could not be run or fails, say so explicitly. Do not claim checks passed if they were
not run, and do not claim the GitHub Actions workflow passed unless it has actually run.

## Financial research safeguards (non-negotiable)

1. Use chronological splits, and walk-forward evaluation where feasible. **Never randomly shuffle**
   financial time series for model evaluation (no `shuffle=True` K-fold on time-ordered data).
2. Prevent **look-ahead bias and data leakage**: features, labels, scalers, regime models and any
   fitted statistic at time *t* may only use data available at *t*. Fit preprocessing on the training
   period only. Be explicit about whether a trade at *t* uses the close of *t* or the next bar.
3. Account for **transaction costs and turnover** in every reported result.
4. Compare learned policies with **simple, credible baselines** under identical data, costs,
   constraints and periods.
5. Keep **training, validation and final test** periods separate. Never tune on the test period.
6. Report **risk-adjusted returns and drawdowns** (Sharpe, Sortino, max drawdown, turnover), not just
   cumulative returns.
7. **Never claim a strategy is profitable** or "beats the market" without evidence; describe
   backtest results as backtest results, with their limitations.
8. **Record seeds, configurations, assumptions and results** in `docs/experiment_log.md`.
9. This is **research and decision support, not financial advice.**

## Repository conventions

- Layout: `src/` package `adaptive_portfolio`; tests in `tests/`; CLI workflows in `scripts/`.
- Data in `data/raw/` and `data/processed/` and figures in `reports/figures/` are git-ignored.
- Secrets: never create or commit real credentials. Only `.env.example` with placeholders is tracked.
- Python ≥ 3.11; Ruff for lint and formatting (line length 100); pytest for tests.

## Git conventions

- Do not commit or push unless explicitly asked.
- Do not append `Co-Authored-By: Claude`, Claude Code attribution trailers or promotional text to
  commit messages.
- Use concise conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`), e.g.
  `docs: add project learning journal`.
- Preserve accurate author/committer identities; do not rewrite history to hide authorship.
- Before a commit, summarise the staged changes and the tests that were actually run. The student
  team reviews, understands and verifies every change before committing.
- Do not remove AI-use disclosures from documentation or academic submissions (README "AI tools
  disclosure", `docs/project_journal.md`, `Abstract.pdf`).
