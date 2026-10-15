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
| Market-data pipeline | `python scripts/market_data.py {validate,fetch,build,report,split}` (§11) | — |
| Features and regimes | `python scripts/market_data.py {features,regime-report}` (§12) | — |
| Baseline backtest | `python scripts/market_data.py {backtest,backtest-report}` (§13) | — |
| Install live-data extra | `python -m pip install -e ".[data]"` (yfinance; optional) | — |

GNU `make` is not installed by default on Windows; run the commands directly or install make.

CI (`.github/workflows/ci.yml`) runs lint, format check, config validation and tests offline on
pushes to `main` and on pull requests. It runs only once the repository is pushed to GitHub.

## 3. Package layout

| Path | Contents | Status |
| --- | --- | --- |
| `src/adaptive_portfolio/__init__.py` | `__version__` | Implemented |
| `src/adaptive_portfolio/config.py` | Config loading and validation | Implemented, tested |
| `src/adaptive_portfolio/evaluation/metrics.py` | Portfolio returns, cumulative return, annualised return (CAGR), annualised volatility, Sharpe ratio, maximum drawdown, two-way turnover (see §10) | Implemented, tested |
| `src/adaptive_portfolio/data/` | Market-data pipeline: providers, cache, validation, processing, splits, report, pipeline, CLI (see §11) | Implemented, tested |
| `scripts/market_data.py` | CLI wrapper for the market-data pipeline | Implemented |
| `src/adaptive_portfolio/features/` | Causal features (`engineering`), decision/target alignment (`alignment`), feature+regime pipeline (`pipeline`) (§12) | Implemented, tested |
| `src/adaptive_portfolio/regimes/` | Training-calibrated rule-based regimes (`rules`), diagnostics (`diagnostics`) (§12) | Implemented, tested |
| `src/adaptive_portfolio/baselines/strategies.py` | Conventional baselines: target weights (equal weight, fixed weights, inverse volatility with capping), rebalancing schedules (§13) | Implemented, tested |
| `src/adaptive_portfolio/evaluation/simulator.py` | Portfolio simulator: timing, drift, costs, cash, ledger (§13) | Implemented, tested |
| `src/adaptive_portfolio/evaluation/performance.py` | Per-window gross/net metrics reusing §10 functions (§13) | Implemented, tested |
| `src/adaptive_portfolio/evaluation/backtest.py` | Baseline backtest per split, outputs, report (§13) | Implemented, tested |
| `src/adaptive_portfolio/{environment,agents,explainability,visualization}/` | Docstring describing planned responsibility | Placeholders only |
| `scripts/validate_config.py` | CLI config check | Implemented |
| `tests/` | `test_package.py` (imports), `test_config.py` (loader and validation), `test_metrics.py` (return and risk metrics, input types), `test_turnover.py` (turnover), `test_data_*.py` (market-data pipeline: config, providers, validation, processing, splits/leakage, pipeline/cache/CLI), `test_feature_config.py`, `test_features.py`, `test_regimes.py`, `test_feature_pipeline.py` (milestone 3), `test_baselines.py`, `test_simulator.py`, `test_backtest_pipeline.py` (milestone 4) | — |

Runtime dependencies: NumPy, pandas (runtime since milestone 2, D-040), PyYAML. Optional
extra `data`: yfinance (live market data, D-041). Dev extras: pytest, Ruff. Metric outputs are
positional (no dates); the data pipeline works with dated pandas tables.

## 4. Configuration reference

Load everything with:

```python
from adaptive_portfolio.config import load_project_config, ConfigError

config = load_project_config("configs")  # ProjectConfig(data=..., environment=..., experiment=...)
```

Individual files: `load_data_config`, `load_environment_config`, `load_experiment_config`.
Milestone-specific files have their own loaders and are not part of `ProjectConfig`:
`load_feature_config` (`features.yaml`, §12) and `load_backtest_config` (`backtest.yaml`, §13.9).
All configs are **frozen dataclasses**. Every validation failure raises `ConfigError` (a
`ValueError`). **Unknown keys are rejected**, to catch typos.

Numbers must be finite (NaN and ±inf are rejected), and booleans are not accepted where numbers
are expected.

### `configs/data.yaml` → `DataConfig`

| Key | Default value | Validation | Status |
| --- | --- | --- | --- |
| `provider` | `csv` | one of `csv`, `synthetic`, `yfinance` | Proposed (D-008) |
| `raw_data_dir` | `data/raw` | non-empty path; relative paths resolve against the project root | — |
| `processed_data_dir` | `data/processed` | as above; must differ from `raw_data_dir` | — |
| `universe` | SPY, EFA, EEM, IEF, TLT, LQD, GLD | non-empty list; upper-cased; no duplicates; 1–20 chars from `A-Z 0-9 . - ^ =` | Provisional (D-034) |
| `start_date` / `end_date` | 2007-01-01 / 2024-12-31 | ISO dates; start < end | Provisional (D-006) |
| `frequency` | `daily` | `daily`, `weekly` or `monthly` (the pipeline supports `daily` only) | D-035 |
| `price_field` | `adj_close` | `adj_close` or `close` | D-037 |
| `provider_options.timeout_seconds` | 30 | (0, 600] | — |
| `provider_options.max_retries` | 3 | integer 0–10; transient errors only | — |
| `provider_options.retry_delay_seconds` | 2.0 | [0, 60]; doubles per attempt, capped at 60 s | — |
| `provider_options.input_dir` | `data/raw/csv_input` | path; `csv` provider reads `<TICKER>.csv` here | — |
| `cache.mode` | `use` | `use`, `refresh` or `offline` | D-039 |
| `missing_data.policy` | `error` | `error` or `drop_sessions` | D-036 |
| `missing_data.max_dropped_sessions` | 0 | integer ≥ 0; must be 0 with `error` | D-036 |
| `validation.min_sessions` | 1000 | integer ≥ 2 | Provisional (D-042) |
| `validation.max_abs_return` | 0.4 | (0, 10] | Provisional (D-042) |
| `validation.max_calendar_gap_days` | 7 | integer ≥ 1 | Provisional (D-042) |
| `validation.max_start_lag_days` / `max_end_lag_days` | 7 / 7 | integers ≥ 0 | Provisional (D-042) |

All nested sections are optional (missing or empty means defaults); unknown keys are rejected at
every level.

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
| `constraints.max_turnover` | null | null, or 0 < x ≤ 2 (two-way turnover) | Definition provisional (D-011); the backtest refuses a non-null value until D-031 settles which turnover it caps |
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
- ~~No data versioning or checksum of the input dataset.~~ Partly addressed in milestone 2: raw
  snapshots carry a manifest with SHA-256 checksums and request parameters, and processed
  datasets have content-defining ids (§11.8). This cannot freeze the provider itself.
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
- **Metric conventions (accepted 2026-10-13: D-011, D-021, D-022, D-024 to D-030):**
  - simple returns; sample standard deviation (`ddof=1`);
  - annualisation factor supplied explicitly by the caller; geometric conversion of annual
    risk-free rates; geometric (CAGR) annualised return;
  - an error rather than inf/NaN for undefined metrics;
  - the first observation as the initial drawdown peak;
  - two-way turnover from drift-adjusted pre-trade weights.

  See §10.
- **Turnover weights:** for turnover, cash must be an *explicit* column when `allow_cash` is true,
  so that each weight row sums to 1.
- **Still to be fixed** (record in the decision log when decided):
  - which `periods_per_year` the project uses for each data frequency (e.g. 252 vs. 365 for
    daily; D-023);
  - final approval of the two-way turnover definition (D-011);
  - trade timing (D-013; implementation proposed in D-048, §13.2);
  - the transaction-cost basis for cash legs (D-031; traded-notional basis proposed and
    implemented in D-049, §13.3; the measure a turnover cap applies to is still open).

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

## 10. Financial metrics (`adaptive_portfolio.evaluation.metrics`)

Implemented in milestone 1. Import from `adaptive_portfolio.evaluation`. All functions are pure and
deterministic. Their conventions were **accepted** by the team on 2026-10-13 (D-011, D-021,
D-022, D-024 to D-030). The daily annualisation factor (D-023) and the transaction-cost basis
(D-031) remain open.

| Function | Input | Output |
| --- | --- | --- |
| `portfolio_returns(values)` | Portfolio values | Array of simple returns |
| `cumulative_return(values)` | Portfolio values | Float (decimal) |
| `annualized_return(values, periods_per_year)` | Portfolio values | Float (decimal, CAGR) |
| `annualized_volatility(returns, periods_per_year)` | Returns | Float (decimal, ≥ 0) |
| `sharpe_ratio(returns, periods_per_year, *, annual_risk_free_rate=None, periodic_risk_free_rate=None)` | Returns | Float |
| `annual_to_periodic_rate(annual_rate, periods_per_year)` | Rate | Float |
| `drawdown_series(values)` / `max_drawdown(values)` | Portfolio values | Array / `MaxDrawdown` |
| `portfolio_turnover(pre_trade_weights, post_trade_weights, *, cash_column=None)` | Weight matrices (events × assets) | Array of per-event turnover in [0, 2]: the sum over all columns by default, or traded notional (cash column excluded) when `cash_column` is given |
| `annualized_turnover(event_turnover, observation_periods, periods_per_year)` | Per-event turnover | Python `float` (per year, same measure as its input) |

### 10.1 Shared conventions

| Topic | Convention |
| --- | --- |
| Units | Returns and rates are **decimals** (0.01 = 1 %), never percentages. *Periodic* means per observation interval (e.g. per day); *annualised* means per year. |
| Input types | Series inputs: 1-D sequences of real numbers. Turnover: 2-D matrices. **Tested types:** list, tuple, NumPy array, pandas Series / DataFrame (via the dev-only dependency; tested with pandas 3.0.6 and the declared minimum, 2.2.0). Integer input is converted to float64. The pandas index is ignored. pandas missing values (NaN or the nullable `pd.NA`) are rejected. |
| Rejected with `TypeError` (all metrics) | `None`, strings, booleans, complex numbers, object arrays (e.g. `[1.0, None]`), dicts; a non-numeric or boolean `periods_per_year` or rate; a non-integer or boolean `observation_periods` (`annualized_turnover`) or `cash_column` (`portfolio_turnover`). |
| Rejected with `ValueError` (series metrics) | Empty input; too few observations; scalars, 2-D or ragged input; NaN or ±inf; portfolio values ≤ 0; returns < −1; `periods_per_year` ≤ 0 or non-finite; rates ≤ −1. Error messages give the offending position. |
| **Turnover exceptions** | `portfolio_turnover` *requires* 2-D matrices (events × assets); 1-D, 3-D and scalar input are rejected, and a single event must have shape (1, assets). Empty weight matrices raise `ValueError`. Further `ValueError`s: shape mismatch, negative weights, rows not summing to 1, and a `cash_column` outside [0, assets − 1] (negative indices are not accepted). `annualized_turnover` takes a 1-D event list, and an **empty** list returns `0.0` (no rebalancing means no trading) instead of raising. `observation_periods` ≤ 0 raises `ValueError`. |
| Undefined results | Raise `UndefinedMetricError` (a subclass of `ValueError`). Never `inf`, `nan` or a substitute value. |
| Missing data | **Not** dropped or filled. Handle it explicitly upstream (data pipeline) so that gaps are a visible decision. |
| Output alignment | Positional. `returns[i]` covers observation `i` → `i+1`; drawdown indices are positions in the input. Map to dates with `series.index[i]`. |
| Annualisation factor `N` | Always passed explicitly as `periods_per_year` (positive, finite, may be non-integer such as 365.25). There is no default frequency (D-023). |
| Zero tolerance | `ZERO_VOLATILITY_TOLERANCE = 1e-12`: a periodic sample std at or below this counts as exactly zero. Reviewed and kept (D-025): the measured floating-point noise was ≤ ~3 × 10⁻¹⁷; realistic periodic std is ≥ ~10⁻⁵. **Limitations:** the tolerance is absolute, not relative; a genuine std below 1e-12 would be treated as zero; the evidence is empirical, from one platform. |
| Weight tolerance | `WEIGHT_SUM_TOLERANCE = 1e-6`: each turnover weight row must sum to 1 within this tolerance (D-030). |

### 10.2 Portfolio returns: `portfolio_returns(portfolio_values)`

1. **Purpose.** Converts a portfolio-value path, such as the output of a backtest, into period
   returns. All other return-based metrics start from these.
2. **Definition.** r_t = V_t / V_{t−1} − 1, for t = 1, …, n.
3. **Variables.** V_t is the portfolio value at observation t, in any currency unit. r_t is the
   simple (arithmetic) return over the period ending at t.
4. **Assumptions and units.** Values are in chronological order. Values must be strictly positive:
   V ≤ 0 means the portfolio is ruined or the input is invalid, so the return is undefined or
   misleading. Output is in decimals.
5. **Example.** V = [100, 110, 99, 99] gives r = [0.10, −0.10, 0.00]. Note that +10 % followed
   by −10 % does not return to 100.
6. **Contract.** Input: at least 2 finite, positive values. Output: a float64 NumPy array of length
   n (one fewer than the input). The first observation has no preceding value, so it is
   **omitted**; it is not filled with 0 or NaN.
7. **Edge cases and limitations.** Constant values give zero returns. The pandas index is not
   preserved. Cash flows (deposits or withdrawals) are not handled; the input must be a
   self-financing value path. A total loss to exactly 0 cannot be represented and must be handled
   by the caller or environment (e.g. by terminating the episode).
8. **Tests.** Hand-calculated paths, including mixed positive and negative returns, integer input
   and constant values; telescoping identity ∏(1 + r_t) = V_n / V_0; scale invariance; output
   length, dtype and finiteness; rejection of zero, negative, NaN, inf, empty, single-value, 2-D and
   non-numeric input.

### 10.3 Annualised volatility: `annualized_volatility(returns, periods_per_year)`

1. **Purpose.** Measures how much returns fluctuate: a basic measure of risk, comparable across
   data frequencies once annualised.
2. **Definition.** σ_ann = σ_period · √N, with σ_period = sqrt( Σ (r_t − r̄)² / (T − 1) ).
3. **Variables.** r_t are periodic returns, r̄ is their arithmetic mean, T is the number of
   returns, and N = `periods_per_year`.
4. **Assumptions and units.** Sample standard deviation (`ddof=1`), an unbiased variance estimator
   for a sample. √N scaling assumes returns are independent and identically distributed;
   autocorrelation (e.g. trending or mean-reverting returns) makes it inexact. Output is an annual
   decimal (0.20 = 20 % per year).
5. **Example.** r = [0.01, −0.01, 0.02, 0.00]. The mean is 0.005; the squared deviations sum to
   5 × 10⁻⁴; the sample variance is 5 × 10⁻⁴ / 3. With N = 252: σ_ann = √(5 × 10⁻⁴ / 3 × 252)
   = √0.042 ≈ 0.2049.
6. **Contract.** Input: at least 2 finite returns, each ≥ −1, and a positive finite N. Output: a
   non-negative Python `float`. Returns exactly 0.0 when σ_period ≤ 1e-12.
7. **Edge cases and limitations.** Constant returns give 0.0. One return is rejected because the
   sample std needs at least 2. Returns below −1 are rejected as probable percentage-unit errors.
   Choosing N is the caller's responsibility; the project-wide choice per frequency is open (D-023).
8. **Tests.** Three hand-computed cases (N = 4, 12, 252); an explicit check that ddof = 1 differs
   from ddof = 0; √N scaling (N × 4 doubles σ); constant returns give exactly 0; total-loss
   return −1 is accepted; non-integer N; invalid N (0, negative, NaN, ±inf, bool, string, None,
   list).

### 10.4 Sharpe ratio: `sharpe_ratio(returns, periods_per_year, *, annual_risk_free_rate=None, periodic_risk_free_rate=None)`

1. **Purpose.** Risk-adjusted performance: average return in excess of a risk-free rate, per unit of
   volatility. One of the abstract's core metrics.
2. **Definition.** S_ann = √N · mean(r_t − r_f,t) / std(r_t − r_f,t), with std computed using `ddof=1`.
3. **Variables.** r_t are periodic returns, r_f,t is the **periodic** risk-free rate, and N =
   `periods_per_year`.
4. **Assumptions and units.**
   - The risk-free rate must match the return frequency. An annual rate R is converted
     geometrically: r_f = (1 + R)^(1/N) − 1, so that compounding N periods gives back R exactly
     (`annual_to_periodic_rate`). An annual rate is never subtracted directly from periodic returns.
   - Supply at most one of `annual_risk_free_rate` (a scalar) and `periodic_risk_free_rate` (a scalar
     or one value per return). If neither is given, the rate is 0.
   - Arithmetic mean; √N annualisation assumes i.i.d. returns. The output is dimensionless.
   - Config `environment.risk_free_rate` is an annual decimal, so pass it as `annual_risk_free_rate`.
5. **Example.** r = [0.02, 0.04, 0.00] with N = 12 and an annual rf of 1.01¹² − 1 ≈ 12.68 %, which
   converts to exactly 0.01 per month. Excess returns are [0.01, 0.03, −0.01], with mean 0.01 and
   sample std 0.02, giving a periodic Sharpe of 0.5. S_ann = 0.5 · √12 ≈ 1.732. Simple division
   (12.68 % / 12) would instead give ≈ 1.634.
6. **Contract.** Input: at least 2 valid returns and a positive finite N. Rates must be finite and
   greater than −1, and a periodic array must have the same length as the returns. Output: a Python
   `float`, which may be negative.
7. **Edge cases and limitations.** If the std of excess returns is ≤ 1e-12, the ratio is undefined
   and the function raises `UndefinedMetricError`. This also catches mathematically constant excess
   returns that floating-point arithmetic turns into ~1e-18 noise. Supplying both rate forms is an
   error. The Sharpe ratio penalises upside and downside volatility equally and ignores fat tails;
   short samples give noisy estimates.
8. **Tests.**
   - Hand-computed values: √12 with no risk-free rate; −√12 for mirrored returns; √3 with an annual
     rf (and a check that the simple-division answer is *not* returned); √3 with a scalar periodic
     rf; exactly 4 with a time-varying rf.
   - Equivalence of the zero-rf forms.
   - `UndefinedMetricError` for constant returns and for constant excess returns.
   - Rejection of: both rf forms; rf ≤ −1, NaN or ±inf; length mismatch; non-numeric rf; invalid N.

### 10.5 Maximum drawdown: `max_drawdown(portfolio_values)` and `drawdown_series(portfolio_values)`

1. **Purpose.** The worst loss from a previous high: what an investor who bought at the worst time
   would have suffered. A core risk metric in the abstract.
2. **Definition.** P_t = max_{s ≤ t} V_s, D_t = V_t / P_t − 1, MDD = min_t D_t.
3. **Variables.** V_t is the portfolio value, P_t the running peak, and D_t the drawdown at t
   (≤ 0).
4. **Assumptions and units.** The **first observation is the initial peak** (D_0 = 0). Any
   decline that started before the series is invisible. Output is a non-positive decimal (−0.25 =
   a 25 % decline).
5. **Example.** V = [100, 120, 90, 110, 130, 117] gives P = [100, 120, 120, 120, 130, 130] and
   D = [0, 0, −0.25, −0.0833, 0, −0.10]. MDD = −0.25, with the peak at index 1 (120) and the trough
   at index 2 (90). The path then recovers to a new high (130).
6. **Contract.** Input: at least 2 finite, positive values. `drawdown_series` returns a float64
   array of the same length. `max_drawdown` returns `MaxDrawdown(max_drawdown: float,
   peak_index: int, trough_index: int)`. With no decline, the result is 0.0 and both indices are 0.
   Ties: the **earliest** deepest point is the trough; the **latest** observation at the running
   peak before the trough is the peak (where the decline began).
7. **Edge cases and limitations.** Monotonically rising or constant paths give 0.0. The result
   satisfies −1 < MDD ≤ 0. Drawdown duration and recovery time are not reported. Sampling frequency
   matters: an intraday trough is invisible in daily data.
8. **Tests.**
   - The hand-computed drawdown series for the recovery path above.
   - MDD with recovery, a decline from the start, no decline, and constant values.
   - Tie-breaking: the latest peak among equal highs, and the earliest of equal troughs.
   - Scale invariance; bounds; output types; non-mutation of the input; shared invalid-input
     rejection.

### 10.6 Cumulative return: `cumulative_return(portfolio_values)`

1. **Purpose.** The total gain or loss over the whole evaluation window, the most intuitive
   performance number. It is named in the abstract.
2. **Definition.** R_cum = V_T / V_0 − 1.
3. **Variables.** V_0 is the first portfolio value, V_T is the last, and T is the number of
   periods.
4. **Assumptions and units.** The value path is self-financing (no deposits or withdrawals). The
   result is a decimal (0.21 = +21 %), and is always > −1 for positive values.
5. **Example.** V = [100, 110, 99, 121] gives 121/100 − 1 = **0.21**. Equivalently, the returns
   [0.10, −0.10, 0.2222…] compound to 1.10 × 0.90 × 1.2222… = 1.21.
6. **Contract.** Input: at least 2 finite, strictly positive values. Output: a Python `float`.
7. **Edge cases and limitations.**
   - A path that ends where it started gives 0.0, however volatile it was in between.
   - Intermediate values do not affect the result, but are still validated (NaN or ≤ 0 anywhere
     raises).
   - Cumulative return ignores both the length of the window and the risk taken. Always report it
     with T, volatility and drawdown.
8. **Tests** (`tests/test_metrics.py`, section E):
   - positive (+0.21), negative (−0.10) and zero results;
   - equality with ∏(1 + r_t) − 1 computed from `portfolio_returns`;
   - scale invariance, and a decimal (not percentage) result;
   - rejection of corrupt intermediate values;
   - shared invalid-input tests (types, empty, single value, NaN/inf, ≤ 0, 2-D).

### 10.7 Annualised return (CAGR): `annualized_return(portfolio_values, periods_per_year)`

1. **Purpose.** Puts windows of different lengths on a common per-year scale. It is the
   compounded growth rate an investor actually experienced.
2. **Definition.** R_ann = (V_T / V_0)^(N/T) − 1, computed as `expm1((N/T)·ln(V_T/V_0))`.
3. **Variables.**
   - V_0, V_T: the first and last values.
   - T: the number of observed return periods (number of values − 1).
   - N: `periods_per_year`.
   - T/N is the window length in years.
4. **Assumptions and units.** The result is a decimal per year. N is explicit, with no daily
   default (D-023). The method is geometric (D-029).
5. **Example.** 24 monthly periods (N = 12) from 100 to 121: (1.21)^(12/24) − 1 = 1.1 − 1 =
   **0.10** per year, whatever the path in between.
   - **Geometric vs. arithmetic:** 100 → 150 → 75 with N = 1. The arithmetic mean return is
     (0.5 − 0.5)/2 = 0, so mean × N = 0. CAGR is √0.75 − 1 ≈ **−0.134**. The portfolio really lost
     25 % over two years; the arithmetic figure hides this loss. In general, CAGR ≈ arithmetic
     mean − σ²/2 per period ("volatility drag").
6. **Contract.** Input: at least 2 finite, strictly positive values (T ≥ 1) and a positive,
   finite N. Output: a Python `float` > −1.
   - Extreme short-period losses may round to exactly −1.0.
   - A result too large to represent (e.g. a 1e6-fold gain in one daily period) raises
     `ValueError`.
7. **Edge cases and limitations.**
   - **Short windows are misleading.** Annualising extrapolates: one month of +5 % gives
     1.05¹² − 1 ≈ **+79.6 %** per year. The formula does not correct this, and no minimum length is
     enforced. The proposed rule (D-029) is to state T and the dates, and not to headline windows
     shorter than one year.
   - Only V_0, V_T and T matter.
   - When T = N (exactly one year), CAGR equals the cumulative return.
   - CAGR is not the same quantity as the arithmetic mean in the Sharpe numerator. Do not mix them.
8. **Tests** (`tests/test_metrics.py`, section F):
   - hand-computed 0.10 for yearly (T = 2), single-period and 24-month paths (smooth and zigzag,
     which confirms path independence);
   - −0.10 for a declining path;
   - fractional N (2.5);
   - equality with cumulative return when T = N;
   - the geometric-vs-arithmetic case;
   - the short-window extrapolation (documented, not fixed);
   - constant values give 0;
   - overflow raises; underflow gives −1.0;
   - invalid N (values and types).

### 10.8 Portfolio turnover: `portfolio_turnover(pre_trade_weights, post_trade_weights, *, cash_column=None)`

1. **Purpose.** Measures how much a strategy trades, which drives transaction costs. It is a core
   metric in the abstract.
2. **Definition** (two-way, D-011, D-030). Two measures, selected explicitly:
   - **Default, `cash_column=None`:** τ_k = Σ_{i=1..A} |w_post[k, i] − w_pre[k, i]|, summed over
     **every** column. This is unchanged from the original API.
   - **Traded notional, `cash_column=j`:** n_k = Σ_{i≠j} |w_post[k, i] − w_pre[k, i]|, summed over
     **non-cash** columns only. Cash is the settlement account, not a traded security.
   - **Relationship:** let B and S be the total non-cash weight bought and sold, with a cash column
     and rows summing to 1. The weight changes sum to 0, so |Δw_cash| = |B − S|. Therefore:
     - default τ = B + S + |B − S| = **2·max(B, S)**;
     - traded notional n = **B + S** = τ − |Δw_cash|;
     - one-way turnover = τ / 2 = **max(B, S)**;
     - so **one-way ≤ traded notional ≤ default two-way**.
   - **Without a cash column** (fully invested portfolio), B = S, so the default already equals
     traded notional and `cash_column` is unnecessary.
   - Always state which measure a reported number uses.
3. **Variables.**
   - k: a rebalance event (one row); A: the number of columns, including cash if it is a column.
   - j: the 0-based index of the cash column.
   - w_pre[k, i]: the **actual** weight of asset i immediately before trading, after market drift.
   - w_post[k, i]: the target weight immediately after trading.
4. **Assumptions and units.**
   - Weights are fractions of portfolio value.
   - Long-only: each weight is ≥ 0 and each row sums to 1 within `WEIGHT_SUM_TOLERANCE` (1e-6).
   - Both matrices use the same asset order, and both include (or both exclude) a cash column.
     With `allow_cash: true`, cash must be an explicit column.
   - τ, n ∈ [0, 2]: 0 means no trade; 2 means the whole portfolio was replaced.
   - The function is timing-agnostic. The caller measures w_pre at the execution time set by D-013.
   - It computes no transaction costs. Which measure costs are charged on is open (D-031), to be
     implemented and validated with the environment.
5. **Examples.** Columns are [A, B, CASH] and pre-trade weights are [0.5, 0.3, 0.2], unless stated
   otherwise.

   | Trade | Default (all columns) | `cash_column=2` (traded notional) |
   | --- | --- | --- |
   | Buy 0.10 of A with cash → [0.6, 0.3, 0.1] | 0.1 + 0 + 0.1 = **0.20** | 0.1 + 0 = **0.10** |
   | Switch 0.10 from A to B → [0.4, 0.4, 0.2] | **0.20** | **0.20** |
   | Sell 0.1 of A, buy 0.2 of B → [0.4, 0.5, 0.1] | **0.40** (= 2·max(0.2, 0.1)) | **0.30** (= 0.2 + 0.1) |
   | Initial funding [0, 0, 1] → [0.5, 0.5, 0] | **2.0** | **1.0** |

   - 60/40 → 50/50 with no cash column gives |−0.1| + |0.1| = **0.20** under both measures.
   - Asset A → asset B entirely gives **2.0**.
   - **Why drift matters:** the target is 50/50 at both rebalances. Asset A gains 10 % and B is
     flat, so the weights drift to 11/21 and 10/21. Returning to 50/50 needs τ = 1/21 ≈ **0.048**.
     Comparing consecutive targets (50/50 vs. 50/50) would wrongly report **0**, and therefore no
     cost.
6. **Contract.** Two matrices of shape (events, assets); a single event has shape (1, assets).
   Output: a float64 array of length `events`.
   - `cash_column` is keyword-only: `None` (default), or a non-negative integer index (Python or
     NumPy integer).
   - With `cash_column`, the **complete** rows, cash included, are still validated: finite,
     non-negative, summing to 1. The cash column is excluded from the sum, not from validation.
   - The function does **not** infer drift, dates or asset returns.
   - Initial funding from cash counts only if the caller supplies it as a row.
7. **Edge cases and limitations.** Errors are raised for:
   - empty matrices; 1-D, 3-D or scalar input; shape mismatch;
   - NaN/inf; negative weights ("only long-only weights are supported");
   - rows not summing to 1 (the message suggests adding a cash column); non-numeric input;
   - `cash_column` that is not an integer (`TypeError`, booleans included), or outside
     [0, assets − 1] (`ValueError`, negative indices included).

   Zero-trade events give exactly 0. A portfolio with only a cash column gives 0 with
   `cash_column=0`. Not supported: shorting or leverage, and external cash flows. The function
   cannot verify that column j really is cash; that is the caller's responsibility.
   **Open (D-031):** how transaction costs use these measures. The proposed direction is to charge
   on traded notional (`cash_column` set); not implemented in this milestone.
8. **Tests** (`tests/test_turnover.py`):
   - hand-computed partial (0.2), full (2.0) and zero-trade events; row order;
   - two drift demonstrations: drift *adds* trading (1/21 vs. a naive 0), and drift can *reduce*
     it (2 × 0.05/0.98 ≈ 0.102 vs. a naive 0.2);
   - the cash leg counts in the default; an omitted cash column is detected; initial funding only
     when supplied;
   - bounds and symmetry on 200 random Dirichlet weight rows (seeded);
   - a single-asset portfolio never trades;
   - consistency with the config cap (the maximum turnover of 2.0 is a valid `max_turnover`);
   - the weight-sum tolerance (accepted within, float32 accepted, rejected beyond);
   - all invalid inputs; tuple and pandas DataFrame input; no mutation of the inputs;
   - **`cash_column`:**
     - the four examples in the table above, plus multi-event rows;
     - cash as the first column; a NumPy integer index; a cash-only portfolio;
     - the identities n = B + S, τ = 2·max(B, S) and n = τ − |Δw_cash|, with
       one-way ≤ n ≤ τ, on 300 seeded random rows;
     - legacy default preserved (omitted = `None` = the all-column sum);
     - invalid indices (−1, −3, 3, 10; 2.0, "2", `True`, `np.bool_`, `[2]`);
     - full-row validation still applied (row sum, negative cash, omitted cash column).

### 10.9 Annualised turnover: `annualized_turnover(event_turnover, observation_periods, periods_per_year)`

1. **Purpose.** A single comparable figure ("the strategy trades 150 % of its value per year"),
   independent of how often it rebalances.
2. **Definition.** Annual turnover = Σ_k τ_k · N / T_obs.
3. **Variables.**
   - τ_k: per-event turnover from §10.8.
   - T_obs: the number of return periods in the evaluation window (not the number of events).
   - N: `periods_per_year`.
4. **Assumptions and units.** Per year, as a decimal. Events must all fall within the window. The
   result uses the same measure as its input (default two-way, or traded notional if the events
   came from `portfolio_turnover(..., cash_column=j)`), so report which one was used.
5. **Example.** 12 monthly rebalances of 0.10 within 252 daily periods (N = 252): 1.2 × 252/252 =
   **1.2** per year. 6 events of 0.2 over 24 months (N = 12): 1.2 × 12/24 = **0.6** per year.
6. **Contract.**
   - `event_turnover` is 1-D, with values in [0, 2]. An empty list gives **0.0**, because no
     rebalancing means no trading (a deliberate, documented exception to "empty raises").
   - `observation_periods` is a positive integer (Python or NumPy): `TypeError` for non-integers
     or booleans, `ValueError` for ≤ 0.
   - N is validated as elsewhere.
   - The return value is always a Python `float`, including for NumPy integer
     `observation_periods` (regression-tested).
7. **Limitations.** It cannot check that the events really lie inside the window; the caller
   supplies consistent inputs. Annualising a short window has the same extrapolation problem as
   §10.7.
8. **Tests:** the two examples above; agreement with `portfolio_turnover` output; empty input
   gives 0; out-of-range or non-finite event values; 2-D input; invalid `observation_periods`
   (values and types); invalid N; the return type is `float` for `int`, `np.int64`, `np.int32` and
   `np.uint16` periods.

### 10.10 Consistency across all metrics

| Property | How it holds |
| --- | --- |
| Decimal units | Every return, rate, volatility, drawdown and turnover is a decimal. Returns < −1 are rejected as probable percentages. |
| Explicit annualisation | `periods_per_year` is a required argument of every annualised metric; there are no defaults. |
| Risk-free handling | Only the Sharpe ratio uses a risk-free rate. An annual rate is converted geometrically (D-024). |
| Drawdown sign | `max_drawdown` ≤ 0 and > −1 (tested). |
| Turnover | Two-way, with values in [0, 2] for both measures, matching the config's `max_turnover ∈ (0, 2]` (tested for the default measure). The default sums all columns; `cash_column` gives traded notional. **Which measure the config cap constrains is not yet decided** (it stays with D-031); the config comment describes the default. |
| Invalid input | Errors are raised; nothing is cleaned silently. The one documented exception is that empty turnover events give 0. |
| Public API | All existing signatures and defaults are unchanged. `cash_column` is a new keyword-only argument whose default reproduces the earlier behaviour; the full pre-existing suite still passes. |

### 10.11 How test correctness was checked

Every expected value in `tests/test_metrics.py` and `tests/test_turnover.py` is derived by hand in
an adjacent comment. To confirm that the tests can actually fail, **hand-picked injected-error
checks** were run on a temporary copy of the module (not committed): specific, deliberately chosen
bugs, each applied one at a time. Each deliberate error made the suite fail. This is a targeted
check, not systematic mutation testing (no mutation-testing tool, no exhaustive set of mutants).
It shows the tests catch these particular mistakes, not every possible bug.

First round (2026-10-13, original four metrics; failures counted in `test_metrics.py` only):

| Deliberate error | Failing tests |
| --- | --- |
| ddof=1 → ddof=0 | 11 |
| Geometric → simple risk-free conversion | 5 |
| Zero-volatility tolerance removed | 2 |
| Earliest instead of latest drawdown peak | 1 |
| √N → N annualisation | 5 |
| NaN/inf allowed through | 11 |
| Zero portfolio values allowed | 6 |

**Correction (2026-10-13).** The second-round counts originally recorded here, for the new metrics
across the full suite, were each **overstated by 1**.
- *Cause:* the harness copies `src/` to a temporary directory. There,
  `test_default_config_dir_points_at_repo_configs` fails on every run, because the copied package
  cannot locate the repository's `configs/`.
- *Fix:* that test is now deselected in mutation runs, and a control run on an unmodified copy
  must pass before any counts are recorded.
- *Unaffected:* the first round (counted in `test_metrics.py` only), and the conclusion that every
  deliberate error was caught by at least one genuine failure.

The table below replaces the second round. It was re-measured on the current suite (395 tests
after deselection; control run: 395 passed). Some counts differ from the original second round
because tests have been added since.

| Deliberate error | Failing tests |
| --- | --- |
| Cumulative return uses V_1 instead of V_0 | 7 |
| CAGR exponent T/N instead of N/T | 8 |
| CAGR with T = number of values instead of number of periods | 8 |
| CAGR replaced by arithmetic mean × N | 7 |
| One-way (half) instead of two-way turnover | 19 |
| Default turnover ignoring the last column | 16 |
| Weight row-sum check disabled | 7 |
| Negative weights allowed | 2 |
| Shape-mismatch check disabled | 1 |
| Annual turnover using the mean instead of the sum of events | 3 |
| Empty events raising instead of returning 0 | 5 |
| `cash_column` ignored (all columns summed) | 7 |
| `cash_column` excludes the wrong column | 4 |
| Negative `cash_column` accepted (Python wrap-around) | 2 |
| Boolean `cash_column` accepted | 1 |
| `annualized_turnover` float fix reverted | 3 |

The shape-mismatch check and boolean `cash_column` rejection are each guarded by a single test.

While writing the turnover tests, one hand-derived expected value was wrong (0.0204 instead of
0.102 for the "drift reduces trading" case). The test failed against the correct implementation;
the derivation was rechecked and the expected value corrected. It was not loosened.

## 11. Market-data pipeline (`adaptive_portfolio.data`)

Implemented in milestone 2. The decisions referenced here (D-034 to D-042, plus D-008) are
**Proposed**, not yet approved.

### 11.1 Data flow

```text
configs/data.yaml + experiment.yaml
        │
        ▼
provider (csv | yfinance | synthetic)  ──►  raw snapshot  data/raw/<provider>/<raw_id>/
        │   fetch_with_retry (transient errors only)        <TICKER>.csv + manifest.json
        ▼
validate_raw_frame  (dates, prices, coverage, gaps)
        ▼
align_prices  (observed calendar; NaN = missing cell)
        ▼
apply_missing_data_policy  (error | drop_sessions; never fill)
        ▼
compute_returns  (simple returns via evaluation.portfolio_returns; sessions_spanned)
        ▼
assign_temporal_splits  (train / validation / test by row date)
        ▼
processed dataset  data/processed/<processed_id>/  + quality report + metadata
```

### 11.2 Commands

Run them from any directory; paths resolve against the project root (the parent of
`--config-dir`, default `configs/`).

| Command | What it does |
| --- | --- |
| `python scripts/market_data.py validate` | Load and validate all configs; print the data settings. |
| `python scripts/market_data.py fetch [--provider P] [--cache-mode M]` | Create or verify the raw snapshot only. |
| `python scripts/market_data.py build [--provider P] [--cache-mode M]` | Full pipeline; prints CACHE HIT or FETCHED, the output path, counts and split sizes. |
| `python scripts/market_data.py report [--provider P \| --dataset-dir D]` | Print `quality_report.md`. |
| `python scripts/market_data.py split [--provider P \| --dataset-dir D]` | Re-derive the split from `returns.csv` and the current config; exit 1 if it differs from `splits.csv`. |

Global options: `--config-dir DIR`, `-v` (debug) or `-q` (warnings only). Exit codes: 0 success;
1 configuration, data, provider, cache or split error; 2 invalid usage. `--provider` overrides
`data.provider` for one run. A different provider gives a different snapshot and dataset id.

**Offline demo (no network):** `python scripts/market_data.py build --provider synthetic`.
The output is labelled SYNTHETIC everywhere.

**Live data:** `python -m pip install -e ".[data]"`, then
`python scripts/market_data.py build --provider yfinance`.

### 11.3 Providers (D-008)

| Provider | Origin label | Source | Notes |
| --- | --- | --- | --- |
| `csv` (default) | `local_csv` | `<input_dir>/<TICKER>.csv`, needing a `date` column plus the price column; headers such as "Adj Close" are normalised | Offline. Source-file SHA-256 values are stored; a changed file invalidates the cache. |
| `yfinance` | `live` | Yahoo Finance via `yfinance` (optional extra) | `auto_adjust=False`, `actions=True`, `end` + 1 day (exclusive end). Rate limits, timeouts and connection errors count as transient; empty responses are errors. Unofficial and revisable. |
| `synthetic` | `synthetic` | Closed-form function of ticker and date | Weekday sessions, no holidays, no corporate actions. **Not market data.** |
| `InMemoryProvider` (code only) | `in_memory` | Frames supplied in Python | Test fixtures. |

**Retries:** at most `1 + max_retries` attempts, for `TransientProviderError` only. Delays are
`retry_delay_seconds × 2^k`, capped at 60 s. Permanent errors (`ProviderNotAvailableError`,
`EmptyResponseError`, `MalformedResponseError`) fail immediately.

### 11.4 Raw schema and validation rules

Raw frame (per instrument): `date` (tz-naive midnight), plus any of `open, high, low, close,
adj_close, volume, dividends, stock_splits, capital_gains`. Provider timezones are dropped after
taking the local trading date.

`validate_raw_frame` raises `DataValidationError` for:
- a missing `date` or price column, or an empty frame;
- **duplicate** dates, or dates **not strictly increasing** (unsorted input is rejected, never
  re-sorted);
- dates outside `[start_date, end_date]`;
- non-numeric, **infinite or non-positive** prices, or a column where every value is missing;
- **insufficient coverage**: the first price more than `max_start_lag_days` after `start_date`,
  or the last price more than `max_end_lag_days` before `end_date`;
- a gap between consecutive observations larger than `max_calendar_gap_days` (a missing block,
  or non-daily data).

`NaN` prices are *missing*, not invalid: they are counted, then handled by the missing-data
policy.

### 11.5 Calendar and missing data (D-035, D-036)

- **Calendar days** are dates on the calendar. **Sessions** are dates on which at least one
  instrument has a price (the *observed calendar*). **Observations** are an instrument's prices.
  A **missing cell** is a session on which a given instrument has no price.
- `error` (default): any missing cell stops the build, listing up to five examples.
- `drop_sessions`: each affected session is removed for **all** instruments, at most
  `max_dropped_sessions` of them, and recorded in the report with the missing instruments.
- No forward-fill, back-fill or interpolation is ever applied.
- The pipeline currently requires `frequency: daily`.

### 11.6 Return construction

For each instrument, over consecutive *retained* sessions:
r_t = P_t / P_prev − 1. This is computed with `evaluation.portfolio_returns`, so convention D-021
applies (simple, decimal, positive prices, first observation omitted).

| Column (`returns.csv`) | Meaning |
| --- | --- |
| `date` | Period end (the session of P_t) |
| `period_start` | Previous retained session (the session of P_prev) |
| `sessions_spanned` | Observed-calendar sessions from `period_start` to `date`; 1 normally, more than 1 after dropped sessions |
| `<instrument>` | Simple decimal return |

- The first retained session has no return.
- A return above `max_abs_return` raises an error, because it is probably a data error such as an
  unadjusted split.
- Returns are price-only (`close`) or approximately total-return (`adj_close`), never a mix
  (D-037). No annualisation is applied anywhere in the pipeline (D-023 is open).

**Worked example (from the tests):** sessions 01-02 to 01-08 with BBB missing on 01-05, under
`drop_sessions`. Session 01-05 is dropped. The 01-08 return of AAA, 108.9 / 99 − 1 = 0.10, has
`sessions_spanned = 2`. It is a two-session return and is labelled as such.

### 11.7 Temporal splits and leakage prevention (D-038)

- `assign_temporal_splits(dates, splits)` labels each row by its own date. The label is `train`,
  `validation` or `test` if the date falls in that partition's inclusive range from
  `experiment.yaml`; otherwise the row is `excluded` and counted (before, between or after).
- Errors are raised for unsorted or duplicate dates, overlapping partitions, and partitions with
  fewer than `min_observations` rows ("insufficient history").
- Assignment is deterministic; there is no random splitting.
- **Boundary:** the first validation return starts from the last training price. That price was
  observed before validation began, so using it is not leakage. No training row uses a price
  after `train.end`.
- **Causality (tested):** processing is row-local in time. Appending future data, including
  future missing cells under `drop_sessions`, never changes earlier prices or returns.
- **No fitted preprocessing** happens in the pipeline. Any future scaler or model must be fitted
  on the training partition only (`split_frame` returns the partitions).
- The quality report is descriptive and computed over all periods; nothing in it feeds back into
  processing or model choices. Do not choose universes, thresholds or preprocessing by looking at
  test-period statistics.
- Not yet addressed: embargo or purge gaps (D-019) and walk-forward folds (D-018).

### 11.8 Cache, ids and reproducibility (D-039)

- **Raw snapshot:** `<raw_data_dir>/<provider>/<raw_id>/`, where
  `raw_id = sha256(request)[:16]` and the request is {provider, universe (in order), start, end,
  frequency}. `manifest.json` holds:
  - the request, provider name and version, and data origin;
  - `retrieved_at_utc`;
  - software versions (Python, numpy, pandas, this package);
  - the SHA-256, row count and columns of each file;
  - for `csv`, the SHA-256 values of the source files.
- **Cache modes:**
  - `use`: load only if the manifest matches the request and every checksum (and, for `csv`,
    every source checksum) verifies; otherwise fetch again with a warning;
  - `refresh`: always fetch;
  - `offline`: never fetch, and error if no valid snapshot exists.
- **Atomic writes:** snapshots and datasets are written to a temporary directory, then moved into
  place. A failed run leaves no partial snapshot.
- **Processed dataset:** `<processed_data_dir>/<processed_id>/`, where `processed_id` hashes the
  raw id plus the processing parameters (price field, missing-data and validation settings,
  split dates, pipeline version).
- **Cached or newly retrieved?** The CLI prints `CACHE HIT` or `FETCHED`, and
  `run_info.json.cache_status` records it. `retrieved_at_utc` in the metadata and report changes
  only when data are actually re-fetched.
- **Guaranteed and tested:** with the same snapshot and configuration, every processed file except
  `run_info.json` is byte-identical.
- **Not guaranteed:** re-fetching reproduces the snapshot. Providers revise data, and Yahoo's
  adjusted history changes after new distributions. To reproduce a study exactly, keep (archive)
  the raw snapshot directory.
- **Refreshing data:** run `build --cache-mode refresh` (or delete the snapshot directory). The new
  `retrieved_at_utc` and file checksums show that the data changed.
- **Storage:** CSV (ISO dates, shortest round-trip floats, `\n` line endings) and JSON. Everything
  under `data/raw/` and `data/processed/` is git-ignored.

### 11.9 Processed outputs

| File | Content |
| --- | --- |
| `prices.csv` | `date` + one column per instrument (selected price field), in universe order |
| `prices_long.csv` | canonical long form `date, instrument, <price_field>`; unique key (date, instrument); sorted |
| `returns.csv` | see §11.6 |
| `splits.csv` | `date, split` for each return row |
| `quality_report.json` / `.md` | quality report (§11.10) |
| `metadata.json` | ids, data origin, provider, retrieval time, raw snapshot path (relative), manifest SHA-256, request, processing parameters, schemas, units, software versions, limitations |
| `run_info.json` | cache status and run time (run-specific; not deterministic) |

Units: prices in quote currency (USD for the default universe); returns are simple decimals.

### 11.10 Quality report

`quality_report.json` contains:
- **Origin:** `data_origin` (`live`, `local_csv`, `synthetic` or `in_memory`) and warnings. The
  first warning always states the origin.
- **Dataset:** ids, provider and version, retrieval time, the request and the price field.
- **Per instrument:** raw rows, raw missing prices, first and last observation, missing cells,
  largest gap, dividend and split event counts (raw), processed price min/max, return min/max.
- **Calendar:** observed sessions, first and last, largest gap, sessions per calendar year.
- **Integrity:** duplicate and invalid-price counts. These are always 0, because violations
  raise an error.
- **Missing data:** policy, missing cells, dropped sessions with reasons, and returns that span
  several sessions.
- **Exclusions**, **processed** sessions, **returns** (rows, largest |return| against the
  threshold) and **splits** (configured and observed boundaries, counts, exclusions).

The Markdown file renders the same information. Every number is computed from the processed data;
the report never invents statistics for data that was not processed.

### 11.11 Troubleshooting

| Message | Meaning / fix |
| --- | --- |
| `expected local file …/<TICKER>.csv` | The `csv` provider has no input. Supply files, or use `--provider yfinance` or `--provider synthetic`. |
| `the yfinance package is not installed` | `python -m pip install -e ".[data]"` |
| `giving up after N attempt(s)` | Network, rate limit or timeout. Retry later or raise `timeout_seconds`. |
| `returned no rows` | Unknown or delisted ticker, no data in the range, or a suppressed provider error. |
| `cache mode 'offline' but …` | No valid snapshot. Run once with `--cache-mode use`. |
| `checksum mismatch` | A snapshot file was edited. In `use` mode it is re-fetched automatically. |
| `insufficient coverage` | The instrument starts after `start_date` (beyond the lag). Change the dates or the universe. |
| `missing_data.policy is 'error'` | Missing cells were found. Inspect the raw data, or use `drop_sessions` explicitly. |
| `exceeds validation.max_abs_return` | Probably an unadjusted split or bad tick. Check the raw data and `price_field`. |
| `insufficient history: <partition>` | The data range does not cover a split. Check `experiment.yaml` against the data. |

### 11.12 Limitations

- Universe chosen with hindsight: survivorship and selection bias (D-034).
- Adjusted prices follow the provider's method and can be revised. `adj_close` returns only
  approximate total returns (D-037).
- The observed calendar cannot reveal a session missing for *every* instrument. Daily data only.
- Live data were verified once, on 2026-10-15 (yfinance 1.7.0). Tests and CI never contact a
  provider; the yfinance adapter is tested against a fake module.
- No exchange calendar, no intraday data, no point-in-time vendor data, no currency conversion.

### 11.13 How the tests verify the pipeline

Test files:
- `test_data_config.py`: configuration.
- `test_data_providers.py`: providers and retry policy, including the fake yfinance module.
- `test_data_validation.py`, `test_data_processing.py`: validation, alignment, missing data and
  returns, checked against hand calculations.
- `test_data_splits.py`: splits and leakage/causality.
- `test_data_pipeline.py`: end-to-end build, cache and CLI, including a subprocess run of the
  script.

Expected values are derived by hand in comments.

A hand-picked set of 11 injected errors was applied, each on its own, to a temporary copy of the
package. For example: forward-filling instead of dropping, `sessions_spanned` forced to 1, an
exclusive split end, cache checksums ignored, permanent errors retried, offline mode fetching.
Each one made the suite fail; see the project journal for the counts. This is a targeted check,
not systematic mutation testing.

## 12. Causal features and rule-based regimes (`adaptive_portfolio.features`, `adaptive_portfolio.regimes`)

Implemented in milestone 3. Decisions D-043 to D-047 are **Proposed**. Configuration:
`configs/features.yaml` (loaded by `load_feature_config`; `ProjectConfig` is unchanged).

### 12.1 Input contract (verified against the real processed dataset)

The pipeline reads one processed dataset directory (§11.9). It checks:
- `returns.csv` starts with `date, period_start, sessions_spanned`, followed by asset columns that
  equal `data.universe` (same instruments, same order) and `metadata.json` `request.universe`;
- dates are unique and increasing;
- `splits.csv` has columns `date, split`, with the same dates;
- the split labels equal those derived from `experiment.yaml`, so a dataset built with other
  boundaries is refused;
- `sessions_spanned == 1` everywhere, unless `allow_multi_session_returns: true`;
- every return is finite.

Violations raise `FeatureDataError` with an actionable message. Nothing is downloaded: the
feature pipeline runs offline on existing processed files.

### 12.2 Timing convention (D-043)

```text
close of t-1          close of t                 close of t+1
     P_{t-1} ───────────► P_t ─────────────────────► P_{t+1}
            r_t (row dated t)        r_{t+1} (row dated t+1)
                          ▲
       features_t, regime_t use rows dated <= t   →   decision at t   →   outcome r_{t+1}
```

- Row `t` of `returns.csv` is `P_t / P_prev − 1`, known at the close of `t`. A feature dated `t`
  uses rows dated ≤ `t` only (a trailing window ending at `t`).
- `r_{t+1}` is never part of the features of `t`. To pair them, use
  `next_period_targets(returns, split_labels)`. Its `pair_split` is a partition only when the
  decision and target dates share it; otherwise it is `boundary`, and such pairs must not be used
  for training, tuning or evaluation in either partition.
- Only returns and ratios are used. Back-adjusted price *levels* depend on later dividends, so
  they are not information available at `t`.
- Windows count **return observations** (sessions), not calendar days. No annualisation is
  applied (D-023 is open).

### 12.3 Feature definitions (defaults; D-044)

Let `r_{a,t}` be asset `a`'s return, `G_t = mean_{a∈G} r_{a,t}` an equal-weight group composite,
and `M_t` the market composite (group `market_group` = equity). "min history" is the number of
return rows needed including `t`. Before that, the value is NaN (warm-up).

| Feature | Family | Definition | Inputs | Window / min history | Interpretation |
| --- | --- | --- | --- | --- | --- |
| `<A>_ret_1` | return/momentum | `r_{A,t}` | asset A | 1 / 1 | latest one-session return |
| `<A>_mom_63` | return/momentum | `∏_{k=0}^{62}(1+r_{A,t−k}) − 1` (via expm1 Σ log1p) | A | 63 / 63 | quarter-scale trend |
| `<A>_vol_21` | volatility/risk | sample std (`ddof=1`) of `r_{A,t−20..t}` | A | 21 / 21 | recent variability (per session) |
| `equity_ret_1`, `bond_ret_1` | universe context | `G_t` | group members | 1 / 1 | composite daily return (descriptive, not tradable) |
| `<G>_mom_21`, `<G>_mom_63` | universe context | `∏(1+G) − 1` over the window | group | 21, 63 | group trend |
| `market_vol_21`, `market_vol_63` | volatility/risk | sample std of `M` over the window | equity | 21, 63 | market volatility |
| `market_downside_vol_63` | volatility/risk | `sqrt(mean(min(M,0)^2))` over 63 rows | equity | 63 / 63 | size of market losses (gains count as 0) |
| `market_drawdown_126` | volatility/risk | `W_end / max(1, max W) − 1`, `W_k = ∏_{j≤k}(1+M_j)` within the last 126 rows | equity | 126 / 126 | distance below the recent high (≤ 0) |
| `xs_dispersion` | cross-asset | population std (`ddof=0`) of `r_{·,t}` across all assets | all | 1 / 1 | how differently assets moved on `t` |
| `avg_asset_vol_21` | cross-asset | mean over assets of `<A>` 21-row sample std | all | 21 / 21 | market-wide volatility summary |
| `equity_bond_corr_63` | cross-asset | Pearson correlation of equity and bond composites over 63 rows; NaN if either has zero variance | equity, bond | 63 / 63 | co-movement / diversification |

That makes 34 columns for the default universe. Every definition, including its timestamp rule
and missing-value behaviour, is also written to `feature_metadata.json`.

**Numerical method:** each window is evaluated independently on NumPy sliding windows, using
two-pass statistics with no running sums. Prefix invariance is therefore exact, not approximate.
Standard deviations at or below 1e-12 are snapped to 0 (D-025).

### 12.4 Warm-up and missing values (D-046)

- First `w − 1` rows: NaN, never filled. With the defaults, the longest warm-up is 125 rows
  (`market_drawdown_126`), all inside the training period (2007).
- Validation and test rows have full history: their windows legitimately reach back into earlier
  periods, which is historical lookback, not leakage.
- Undefined values (zero-variance correlation) are NaN and reported as "other missing" separately
  from warm-up (`availability_summary`).
- Regimes need both regime features; otherwise the label is `unavailable` and `regime_status` is
  `missing_trend_feature`, `missing_volatility_feature` or `missing_both_features`.

### 12.5 Regime rules and training-only calibration (D-045)

| Component | Feature | Rule (thresholds frozen from training) |
| --- | --- | --- |
| Trend | `equity_mom_63` = `m` | negative if `m < −b`; positive if `m > +b`; neutral if `−b ≤ m ≤ +b`; `b` = quantile 0.3333 of `|m|` on train |
| Volatility | `market_vol_21` = `v` | low if `v < q_low`; high if `v > q_high`; normal otherwise; `q_low`, `q_high` = train quantiles 0.3333 and 0.6667 |
| Regime | both | `<trend>_<volatility>` (up to 9 values; none forced); `unavailable` if a feature is missing |

**Calibration:**
- `fit_regime_thresholds` uses only rows whose split is `train` and whose two features are finite.
- Quantiles use NumPy `linear` interpolation.
- Fitting fails if fewer than `min_calibration_observations` (250) rows are usable.

**Frozen artifact:**
- `regime_thresholds.json` records the thresholds, rules, quantile levels, calibration dates and
  counts, and the source dataset ids.
- `assign_regimes` applies it unchanged to all partitions; validation and test data never refit
  it.
- `--thresholds FILE` re-applies a saved artifact without refitting. It is refused if the
  artifact's features or quantile levels differ from the configuration.

### 12.6 Leakage prevention: what is guaranteed and tested

| Property | Test |
| --- | --- |
| Changing or appending rows after `t` leaves features ≤ `t` unchanged | `test_modifying_future_rows…`, `test_appending_rows…` |
| Changing only `r_{t+1}` leaves the features of `t` unchanged | `test_next_return_never_enters_features_at_t` |
| Thresholds depend only on training rows (validation/test values altered → identical artifact; training altered → different) | `test_validation_and_test_values_cannot_change_thresholds`, `test_altering_validation_and_test_returns…` |
| Frozen thresholds give identical labels on a historical prefix | `test_frozen_thresholds_give_prefix_invariant_labels`, `test_frozen_artifact_on_longer_dataset…` |
| Refitting after appending future (non-training) data gives identical thresholds | `test_refitting_after_appending_future_data…` |
| Decision/target pairs crossing a split boundary are labelled `boundary` | `test_next_period_targets_alignment_and_boundaries` |
| Split membership of feature rows equals `splits.csv` and `experiment.yaml` | `test_end_to_end_outputs_and_schema`, `test_split_mismatch_is_rejected` |

The regime report is computed over all partitions as a post-hoc description. It is never used to
choose thresholds, windows or features.

### 12.7 Outputs (D-047) and commands

All outputs go to `data/processed/features/<feature_set_id>/` (git-ignored). They are
deterministic: reruns are byte-identical.

| File | Content |
| --- | --- |
| `features.csv` | `date, split`, then the feature columns (§12.3 order) |
| `regimes.csv` | `date, split`, the trend and volatility features, `market_drawdown_126`, `xs_dispersion`, `equity_bond_corr_63`, `trend_label`, `volatility_label`, `regime`, `regime_status` |
| `regime_thresholds.json` | frozen artifact (§12.5) |
| `regime_report.json` / `.md` | per-split regime counts and proportions, first and last dates, component counts, transition counts and proportions, missing-feature counts, warm-up exclusions, feature medians/min/max by regime, warnings (absent, sparse, concentrated in one year, degenerate thresholds), disclaimer |
| `feature_metadata.json` | feature definitions, configuration, input ids, timing and split rules, software versions |

Commands, run offline on an existing processed dataset:

```bash
python scripts/market_data.py validate                              # also checks features.yaml
python scripts/market_data.py features --provider yfinance          # fit on train, label, report
python scripts/market_data.py regime-report --provider yfinance     # print the report
python scripts/market_data.py features --provider yfinance --thresholds path/to/regime_thresholds.json
python scripts/market_data.py build --provider synthetic && python scripts/market_data.py features --provider synthetic
```

`--dataset-dir DIR` selects a specific processed dataset. The `regime_thresholds.json` from a
fitted run is the artifact to keep when you want to reproduce labels without refitting.

### 12.8 Limitations

- Regimes are heuristic two-feature classifications, not verified market states. The 63-session
  momentum lags turning points.
- Volatility labels are relative to the training period. With training 2007–2016, which includes
  2008, the calmer validation years are mostly "low".
- Some regimes are sparse in some splits; the report says so. They are not merged or re-tuned.
- Composites are equal-weight and descriptive, not tradable portfolios. Features inherit the
  universe's survivorship and selection bias (D-034) and the provider's adjustment method (D-037).
- No feature scaling or normalisation is applied. If later models need it, it must be fitted on
  the training partition only.

### 12.9 How the tests verify this

Test files:
- `test_feature_config.py` (30 tests): configuration validation.
- `test_features.py` (26): hand-calculated primitives, schema, warm-up, edge cases, invalid
  inputs, three future-invariance tests, decision/target boundary alignment.
- `test_regimes.py` (21): hand-calculated thresholds, inclusive boundaries and ties, missing
  values, degenerate thresholds, artifact round-trip and validation, compatibility, prefix
  invariance and training-only calibration under the real pipeline contract, diagnostics.
- `test_feature_pipeline.py` (13): end-to-end on synthetic data built by the milestone-2
  pipeline; byte-identical reruns; frozen artifact versus refitting; offline execution without a
  raw snapshot; contract violations; CLI.

Expected values are derived by hand in comments.

Twelve hand-picked injected bugs were each caught by the suite, for example: a window aligned to
the future, warm-up filled with zeros, calibration on all splits, boundary pairs not flagged.
See the project journal. This is a targeted check, not systematic mutation testing.

## 13. Portfolio simulator and conventional baselines (`adaptive_portfolio.evaluation`, `adaptive_portfolio.baselines`)

Milestone 4. All conventions here are **Proposed** (D-048 to D-054) and all cost and constraint
values are provisional (D-007, D-015). Results produced with them are descriptive backtest output,
not a validated comparison and not financial advice.

### 13.1 Components

| Module | Function | Responsibility |
| --- | --- | --- |
| `baselines.strategies` | `target_weights(strategy, history, universe, max_weight)` | Target weights from a return history whose last row is the decision row. Raises `StrategyError` on column mismatch, too little history or zero volatility |
| | `cap_and_redistribute(raw, max_weight)` | Water-filling cap (§13.6) |
| | `decision_rows(schedule, dates, start, end)` | Decision row positions for `daily`, `monthly` (first observed session of each new month) or `never` (only `start`) |
| `evaluation.simulator` | `simulate(returns, targets, *, lag, window, settings)` | Accounting: drift, executions, costs, cash, value, drawdown. Returns `SimulationResult(ledger, executions)`. Does not mutate inputs |
| `evaluation.performance` | `summarize_window(ledger, *, initial_capital, annual_risk_free_rate, periods_per_year)` | Gross and net metrics for one window, computed with the §10 functions |
| `evaluation.backtest` | `run_backtest(config, backtest, project_root, *, dataset_dir=None, provider_name=None)` | Loads the processed dataset through the milestone-3 contract (`load_processed_inputs`), runs every strategy on every split, writes outputs. Returns `BacktestResult(output_dir, backtest_id, metrics)` |

Strategies only produce target weights; they never see the simulator, costs or future rows. The
simulator never decides weights. All strategies share the same simulator, timing, costs and
constraints.

### 13.2 Timing (D-048)

Row `t` of `returns.csv` is `P_t / P_{t−1} − 1` (close to close). With execution lag `L`
(`backtest.execution_lag_sessions`, default 0):

```text
row:        d (decision)        x = d + L (execution)        x + 1          x + 2 ...
info used:  returns dated <= d
trade:                          at the close of x
earns:                                                       r_{x+1}        r_{x+2} ...
```

- With `L = 0`, the strategy trades at the close it observed. This is optimistic (a real
  market-on-close order is submitted before the close). Use `L = 1` as a conservative check.
- A weight never earns a return dated `<= x`. This is tested with a +50 % return on the
  execution row that the newly bought asset must not earn, and with lag 0 and 1.

### 13.3 Accounting and costs (D-049)

For each ledger row `t` (value before trading `V`, weights `w` held over `(t−1, t]`):

1. Gross return `g_t = Σ_i w_i r_{i,t} + w_cash · rf_periodic`.
2. Drift: `w_i ← w_i (1 + r_{i,t}) / (1 + g_t)` (cash likewise with `rf_periodic`).
3. If an execution occurs at the close of `t`:
   - traded notional `n_t = Σ_{non-cash} |w_target,i − w_drifted,i|`, computed by
     `portfolio_turnover(pre, post, cash_column=...)` (§10);
   - cost fraction `c_t = k · n_t`, where `k = (transaction_cost_bps + slippage_bps) / 10⁴`
     (15 bps by default, provisional);
   - the cost is deducted pro rata, so post-trade weights equal the target.
4. Net return `net_t = g_t − c_t (1 + g_t)`, which equals `(1 + g_t)(1 − c_t) − 1` but is written
   so that zero cost gives exactly `net = gross`.
5. `V_t = V_{t−1} (1 + net_t)`. Drawdown is measured from the running peak, starting at
   `initial_capital`.

The **funding row** is the first ledger row (the first execution date `x₀`): the portfolio starts
as cash, its gross return is 0, and its net return is minus the funding cost when
`charge_initial_funding: true`. Hence `Π(1 + net) = V_end / initial_capital`.

Each row also records `turnover_two_way` (the D-011 all-column measure), for reporting only.

### 13.4 Constraints, cash and invalid states (D-050)

- Long-only (`min_weight ≥ 0`), no leverage (Σ w ≤ 1), fractional weights, per-asset
  `max_weight`. The remainder is cash when `allow_cash` is true; without cash, targets must sum
  to 1.
- Cash earns the periodic risk-free rate. The default rate is 0. The backtest refuses a non-zero
  `risk_free_rate` unless `periods_per_year` is set, because converting it needs D-023.
- `SimulationError` is raised for:
  - NaN or non-finite returns or targets;
  - negative weights, a weight above `max_weight`, or Σ w > 1;
  - a target that would execute outside `[first, last)` of the window, or a window whose
    first row is not an execution (the funding row);
  - a non-positive portfolio value.
  Nothing is clipped, normalised or filled silently.
- A non-null `constraints.max_turnover` is refused (`ConfigError`) until D-031 decides which
  turnover measure a cap constrains.

### 13.5 Evaluation protocol per split (D-051)

For each split with row range `[s, e]`:

1. **Common start:** `k₀ = max(s, max_lookback − 1)`, where `max_lookback` is the largest
   `min_history` over all strategies. With the 63-session inverse-volatility lookback, only the
   training split is affected (62 warm-up rows). All strategies start on the same row.
2. Decision rows come from each strategy's schedule within `[k₀, e]`. Weights at row `k` use
   returns of rows `<= k`; for validation and test, the lookback may reach into the previous split
   (history, not leakage).
3. A decision with `k + L >= e` would earn a return of the next split, so it is **dropped** and
   counted (`decisions_dropped_at_split_end`).
4. The simulation starts from cash at `initial_capital` on row `k₀ + L` and ends at `e`.
   Results for one split never contain returns from another split.

Rows with `sessions_spanned > 1` (returns spanning several sessions after dropped sessions) are
refused unless `allow_multi_session_returns: true`. The current live dataset has none.

### 13.6 Baselines (D-053)

| Name | Type | Rule | Rebalance |
| --- | --- | --- | --- |
| `equal_weight_monthly` | `equal_weight` | `1/N` for each asset | first session of each month |
| `buy_and_hold_equal_weight` | `equal_weight` | `1/N` at the start, then drift | never |
| `inverse_volatility_monthly` | `inverse_volatility` | `w_i ∝ 1/σ_i`, sample std (`ddof=1`) of the last 63 returns up to and including the decision row, then capped | first session of each month |

`fixed_weights` (explicit weights, unlisted assets 0, remainder cash) is also supported, but not in
the default set.

**Capping (`cap_and_redistribute`):** any weight above `max_weight` is set to the cap, and the
excess is redistributed to the uncapped assets in proportion to their current weights. This
repeats until no weight exceeds the cap. If `N × max_weight < 1`, it raises (cannot be fully
invested). A zero-volatility asset raises `StrategyError` rather than receiving an arbitrary
weight. Equal weight with 7 assets (0.143) is below the 0.40 cap.

### 13.7 Metrics (D-052)

Computed separately for gross and net returns, on the ledger rows after the funding row (the
funding cost is included in net results):

| Key | Definition |
| --- | --- |
| `gross_/net_cumulative_return` | `cumulative_return` (§10) on the value path |
| `cost_drag` | gross minus net cumulative return |
| `gross_/net_max_drawdown` | `max_drawdown` (§10), peak starting at `initial_capital` |
| `net_volatility_per_session` | `annualized_volatility(r, 1)`: per-session sample std, **not annualised** |
| `net_sharpe_per_session_rf0` | `sharpe_ratio(r, 1)` with rf 0: per-session mean/std, **not annualised**; omitted when rf ≠ 0 |
| `total_traded_notional`, `total_cost_fraction`, `total_cost_value` | sums over executions, including the funding trade |
| `net_annualised_return`, `_volatility`, `net_sharpe` | only if `backtest.periods_per_year` is set; labelled provisional (D-023 open) |

Undefined values (e.g. zero volatility) are `None` with a note, never inf or NaN. Sortino is not
implemented (§10 scope).

### 13.8 Outputs (D-054) and commands

`data/processed/backtests/<backtest_id>/` (git-ignored). Byte-identical on rerun:

| File | Content |
| --- | --- |
| `ledger.csv` | per strategy, split and date: `gross_return, rebalanced, decision_date, turnover_two_way, traded_notional, cost_fraction, cost_value, net_return, value, drawdown, weight_<asset>…, weight_CASH` |
| `executions.csv` | decision and execution dates and target weights |
| `metrics.json` / `metrics.csv` | §13.7 metrics per split and strategy, with notes |
| `backtest_report.md` | human-readable summary with conventions and disclaimers |
| `metadata.json` | input dataset ids, backtest and environment settings, conventions, software versions |

`backtest_id` is a short hash of the processed-dataset id, the backtest config, the environment
values used and `BACKTEST_PIPELINE_VERSION`.

```bash
python scripts/market_data.py validate                            # also checks backtest.yaml
python scripts/market_data.py backtest --provider yfinance        # offline, on the processed dataset
python scripts/market_data.py backtest-report --provider yfinance
python scripts/market_data.py build --provider synthetic && python scripts/market_data.py backtest --provider synthetic
```

`--dataset-dir DIR` selects a specific processed dataset. No network access is needed.

**Test split:** the command currently evaluates all three splits, including test. Under the
experiment-log rule, test-period results are reported only for final, pre-registered
evaluations. Whether the baseline command should exclude the test split by default is an open
question (D-051).

### 13.9 `configs/backtest.yaml` → `BacktestConfig`

| Key | Default | Validation | Status |
| --- | --- | --- | --- |
| `output_dir` | `data/processed/backtests` | non-empty path | D-054 |
| `execution_lag_sessions` | 0 | integer 0–5 | Proposed (D-048) |
| `charge_initial_funding` | true | bool | Proposed (D-049) |
| `periods_per_year` | null | null or (0, 400] | D-023 open |
| `allow_multi_session_returns` | false | bool | — |
| `strategies[].name` | — | lowercase identifier, unique | — |
| `strategies[].type` | — | `equal_weight`, `inverse_volatility`, `fixed_weights` | Proposed (D-053) |
| `strategies[].rebalance` | — | `daily`, `monthly`, `never`; not finer than `rebalance_frequency` | — |
| `strategies[].lookback` | — | integer ≥ 2; inverse volatility only | 63, fixed, not tuned |
| `strategies[].weights` | — | fixed weights only; tickers in the universe; within bounds; Σ ≤ 1 (= 1 without cash) | — |

`check_against(data, environment)` performs the cross-checks (universe, bounds, feasibility,
long-only). Unknown keys are rejected.

### 13.10 Limitations

- Close-to-close execution at `L = 0` is optimistic. The cost model is linear and does not depend
  on trade size; no market impact, bid–ask variation, taxes or borrowing.
- Costs and the 0.40 cap are provisional. Results change with them.
- Each split is an independent simulation from cash; there is no continuous track record.
- Metrics are per session by default. Annual figures need D-023.
- Adjusted-close returns assume reinvested distributions (D-037). The universe has survivorship
  and selection bias (D-034).
- The baselines are a minimum conventional set (D-010/D-053). Optimisation-based benchmarks
  (minimum variance, mean-variance, risk parity) are not implemented.

### 13.11 How the tests verify this

Test files (77 tests):
- `test_baselines.py` (37): config validation and cross-checks; hand-calculated equal, fixed and
  inverse-volatility weights; capping cases; schedules; weights at `k` unaffected by later rows.
- `test_simulator.py` (26): a hand-calculated two-asset ledger, with every column derived in
  comments; lag 0 and 1 alignment; a weight never earns a return dated at or before execution;
  cash and cost-leg handling; cost equals §10 turnover × rate; value identity; zero-cost
  gross = net; uncharged funding; invalid targets, schedules and returns; total loss; no
  mutation; summary equals §10 functions.
- `test_backtest_pipeline.py` (14): end-to-end on synthetic data; split containment; common start
  and boundary drops; buy-and-hold equals its closed form; byte-identical reruns; altering later
  splits leaves earlier results unchanged; weights depend on row `k` but not row `k + 1`; lag
  shift; opt-in annualisation; refusal of `max_turnover` and of non-zero rf without D-023; offline
  run; multi-session refusal; CLI.

Independent checks on the live dataset recomputed buy-and-hold in closed form, equal-weight
monthly with a separate loop, and inverse-volatility weights by hand. All agreed to about 1e-8.
Twelve hand-picked injected bugs were run against the suite; all are now caught (one only after a
test was added). See the project journal. This is a targeted check, not systematic mutation
testing.
