# Technical Handbook

Practical reference for working on the codebase. It describes **what exists now**. Planned
components are described in [`architecture.md`](architecture.md) and [`roadmap.md`](roadmap.md).
Update this handbook whenever setup, commands, configuration keys, interfaces or conventions change.

## 1. Environment setup

Requires Python ≥ 3.11 (CI tests 3.11, 3.12 and 3.13).

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash; Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

`.venv/` is git-ignored. No credentials or market data are needed to install or test.

## 2. Everyday commands

| Purpose | Command | Make target |
| --- | --- | --- |
| Run tests | `python -m pytest` | `make test` |
| Lint | `python -m ruff check .` | `make lint` |
| Auto-format | `python -m ruff format .` | `make format` |
| Check formatting | `python -m ruff format --check .` | `make format-check` |
| All checks (as CI) | lint + format check + tests | `make check` |
| Validate configs | `python scripts/validate_config.py [--config-dir configs]` | — |

GNU `make` is not installed by default on Windows; run the commands directly or install make.

CI (`.github/workflows/ci.yml`) runs lint, format check, config validation and tests offline on
pushes to `main` and on pull requests. It runs only once the repository is pushed to GitHub.

## 3. Package layout

| Path | Contents | Status |
| --- | --- | --- |
| `src/adaptive_portfolio/__init__.py` | `__version__` | Implemented |
| `src/adaptive_portfolio/config.py` | Config loading and validation | Implemented, tested |
| `src/adaptive_portfolio/{data,features,regimes,environment,agents,baselines,evaluation,explainability,visualization}/` | Docstring describing planned responsibility | Placeholders only |
| `scripts/validate_config.py` | CLI config check | Implemented |
| `tests/` | `test_package.py` (imports), `test_config.py` (loader and validation) | — |

## 4. Configuration reference

Load everything with:

```python
from adaptive_portfolio.config import load_project_config, ConfigError

config = load_project_config("configs")  # ProjectConfig(data=..., environment=..., experiment=...)
```

Individual files: `load_data_config`, `load_environment_config`, `load_experiment_config`.
All configs are **frozen dataclasses**. Every validation failure raises `ConfigError` (a
`ValueError`). **Unknown keys are rejected**, to catch typos.

Numbers must be finite (NaN and ±inf are rejected), and booleans are not accepted where numbers
are expected.

### `configs/data.yaml` → `DataConfig`

| Key | Default value | Validation | Status |
| --- | --- | --- | --- |
| `provider` | `csv` | one of `csv`, `yfinance` | Open (D-008) |
| `raw_data_dir` | `data/raw` | path (optional) | — |
| `processed_data_dir` | `data/processed` | path (optional) | — |
| `universe` | SPY, QQQ, IWM, EFA, TLT, IEF, GLD | non-empty list; upper-cased; no duplicates | Provisional (D-005) |
| `start_date` / `end_date` | 2007-01-01 / 2024-12-31 | ISO dates; start < end | Provisional (D-006) |
| `frequency` | `daily` | `daily`, `weekly` or `monthly` | Provisional (D-006) |
| `price_field` | `adj_close` | non-empty string (optional) | — |

### `configs/environment.yaml` → `EnvironmentConfig`

| Key | Default value | Validation | Status |
| --- | --- | --- | --- |
| `initial_capital` | 100000.0 | > 0 | Arbitrary scale |
| `transaction_cost_bps` | 10.0 | 0 ≤ x ≤ 1000 | Provisional (D-007) |
| `slippage_bps` | 5.0 | 0 ≤ x ≤ 1000 (optional, default 0) | Provisional (D-007) |
| `rebalance_frequency` | `daily` | `daily` / `weekly` / `monthly` | Provisional (D-015) |
| `constraints.long_only` | true | bool | Provisional (D-015) |
| `constraints.allow_cash` | true | bool | Provisional (D-015) |
| `constraints.min_weight` | 0.0 | ≥ 0 if long-only; ≥ −1 always; ≤ max_weight | Provisional (D-015, D-020) |
| `constraints.max_weight` | 0.40 | 0 < x ≤ 1 | Provisional (D-015) |
| `constraints.max_turnover` | null | null, or 0 < x ≤ 2 (two-way turnover) | Definition provisional (D-011) |
| `risk_free_rate` | 0.0 | annual decimal in [−0.05, 0.25] (optional) | Provisional |

### `configs/experiment.yaml` → `ExperimentConfig`

| Key | Default value | Validation | Status |
| --- | --- | --- | --- |
| `name` | `scaffold-default` | non-empty string | — |
| `description` | text | optional | — |
| `seed` | 42 | integer in [0, 2³²) | D-016 |
| `splits.{train,validation,test}.{start,end}` | 2007–2016 / 2017–2019 / 2020–2024 | each start < end; train.end < validation.start; validation.end < test.start | Provisional (D-009) |
| `walk_forward.enabled` | false | bool | Not implemented (D-018) |
| `walk_forward.scheme` | `expanding` | `expanding` or `rolling` | Not implemented |
| `walk_forward.train_window_years`, `step_months` | 5, 12 | positive integers | Not implemented |
| `output_dir` | `reports` | path (optional) | Open (D-017) |

### Cross-file checks (`ProjectConfig`)

- All splits lie within `[data.start_date, data.end_date]`.
- `rebalance_frequency` is not finer than `data.frequency` (e.g. daily rebalancing on monthly data is
  rejected).
- Weight feasibility: without cash, `max_weight × n_assets ≥ 1`; always, `min_weight × n_assets ≤ 1`.

## 5. Reproducibility: current state and gaps

**In place now**

- Seed, data assumptions, costs, constraints and split dates are explicit, validated and versioned in
  `configs/`.
- `scripts/validate_config.py` prints a summary that can be pasted into `experiment_log.md`.
- `experiment_log.md` template asks for commit hash, configs, seeds, data and periods.

**Not implemented yet (do not assume it exists)**

- No helper to apply the seed to random number generators (Python, NumPy, ML library).
- No function to serialise a resolved `ProjectConfig` to a snapshot file saved with results.
  `dataclasses.asdict` works, but `Path` and `date` values need converting for YAML or JSON.
- No data versioning or checksum of the input dataset.
- No lock file pinning exact dependency versions; `pyproject.toml` has ranges only.
- Relative paths (`raw_data_dir`, `output_dir`, `--config-dir`) resolve against the current working
  directory; run commands from the repository root.
- `walk_forward` settings are parsed and validated but not used, and folds are not checked against
  the data window.
- No embargo between splits (D-019).
- Experiment logging is manual.

These gaps should be closed in the milestones where they first matter (seeding and config snapshots
before the first logged experiment in milestone 5).

## 6. Conventions

- **Dates:** ISO-8601 strings in YAML (`"2017-01-01"`); ranges are inclusive.
- **Costs:** basis points in configs (1 bp = 0.0001).
- **Rates:** annual decimals (0.02 = 2 %).
- **Weights:** fractions of portfolio value; implicit cash = 1 − Σ weights when `allow_cash` is true.
- **Still to be fixed** (record in the decision log when decided): return type (simple vs. log) per
  use, annualisation factor (e.g. 252 trading days), Sharpe convention, turnover definition (D-011),
  trade timing (D-013).

## 7. Testing conventions

- Tests run offline. Use small synthetic data generated in the test or stored as tiny fixtures under
  `tests/`. Never download data in tests.
- Mark unavoidable network tests with `@pytest.mark.network` (CI deselects them) and slow tests with
  `@pytest.mark.slow`.
- For each data-producing function, add a **leakage test**: appending future data must not change
  past outputs.
- Shared fixtures live in `tests/conftest.py` (`data_raw`, `environment_raw` and `experiment_raw`
  return mutable copies of the default configs).

## 8. Adding a new module (checklist)

1. Check the roadmap milestone and scope label ([R]/[F]/[O]).
2. Read the target subpackage docstring and `architecture.md`.
3. Add any new dependency to `pyproject.toml` with bounds, only if needed now.
4. Implement small typed functions in `src/`, with tests in `tests/`.
5. If you add config keys: extend the dataclass with validation, update the YAML (mark provisional
   values) and update this handbook's tables.
6. Run lint, format check and tests; update the journal, glossary, decision log and roadmap as relevant.

## 9. Git hygiene

- Ignored: virtual environments, caches, `.env*` (except `.env.example`), `data/raw/*`,
  `data/processed/*`, `reports/figures/*`, root-level artifact directories (`/models/`, `/runs/`,
  `/logs/`, `/outputs/`, `/checkpoints/`, …) and serialized model files (`*.pt`, `*.pkl`, `*.zip`, …).
- Artifact directories are anchored to the repository root so that source packages such as
  `src/adaptive_portfolio/models/` are **not** ignored.
- Not ignored: other files under `reports/` (D-017). Check `git status` before committing.
- `Abstract.pdf` is tracked and must not be modified.
