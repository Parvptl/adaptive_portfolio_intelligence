# Decision Log

Records design, data, methodology and scope decisions, together with who made them and whether the
team has approved them. **Only the student team (Parv Patel, Mandar Patil) can approve a decision.**
AI assistants may propose decisions but must never mark them approved.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| **Set by abstract** | Fixed by the submitted abstract (`Abstract.pdf`); changing it changes the research scope. |
| **Proposed** | Suggested (often during AI-assisted scaffolding); in use as a provisional default; **not yet approved**. |
| **Accepted** | Approved by the team. Record date and who approved. |
| **Rejected** | Considered and not adopted. Keep the entry for the record. |
| **Superseded** | Replaced by a later decision (link it). |

## How to add or update a decision

1. Use the next ID. Never renumber or delete entries.
2. To approve: change the status to **Accepted**, and fill in *Approved by* and *Date*.
3. To change an accepted decision: add a new entry and mark the old one **Superseded by D-XXX**.
4. If the change affects configs, code or docs, update them in the same change and note it in
   `project_journal.md`.

---

## Summary

| ID | Decision | Status |
| --- | --- | --- |
| D-001 | `src/` layout, `pyproject.toml`, pytest + Ruff | Proposed |
| D-002 | Minimal dependencies; add per milestone | Proposed |
| D-003 | Plain dataclass config with strict validation | Proposed |
| D-004 | MIT license; copyright holders | Proposed |
| D-005 | Asset universe: 7 US-listed ETFs (first proposal) | Superseded by D-034 |
| D-006 | Data date range 2007-01-01 to 2024-12-31, daily | Proposed (provisional) |
| D-007 | Costs: 10 bps transaction + 5 bps slippage | Proposed (provisional) |
| D-008 | Data provider: `csv` default (offline), optional `yfinance`, `synthetic` for tests | Proposed |
| D-009 | Train / validation / test split dates | Proposed (provisional) |
| D-010 | Minimum set of conventional benchmarks | Proposed (see D-053) |
| D-011 | Turnover definition: two-way; default over all columns, optional `cash_column` for traded notional | Accepted |
| D-012 | Whether regime signals are agent inputs | Open |
| D-013 | Trade-timing convention | Proposed (see D-048) |
| D-014 | PPO as the candidate RL algorithm | Set by abstract |
| D-015 | Portfolio constraints: long-only, cash allowed, max 40 % per asset | Proposed (provisional) |
| D-016 | Seed policy (seed 42; number of seeds per experiment) | Proposed / open |
| D-017 | Where experiment outputs are written and whether they are tracked in Git | Open |
| D-018 | Walk-forward scheme and its relation to fixed splits | Open |
| D-019 | Embargo / purge gap between periods | Open |
| D-020 | Lower bound of -1 on per-asset weight if shorting is ever enabled | Proposed |
| D-021 | Portfolio-return input convention (simple returns from positive values) | Accepted |
| D-022 | Sample standard deviation (`ddof=1`) for volatility and Sharpe | Accepted |
| D-023 | Annualisation factor supplied explicitly; per-frequency values open | Proposed / open |
| D-024 | Geometric conversion of annual to periodic risk-free rate | Accepted |
| D-025 | Undefined metrics raise `UndefinedMetricError`; zero tolerance 1e-12 | Accepted |
| D-026 | Drawdown conventions: first observation is the initial peak; tie-breaking | Accepted |
| D-027 | NumPy as the only runtime numerical dependency for milestone 1 | Accepted |
| D-028 | Cumulative return from first and last portfolio values | Accepted |
| D-029 | Annualised return is geometric (CAGR); no minimum sample length enforced | Accepted |
| D-030 | Turnover input contract: drift-adjusted pre-trade and post-trade weight matrices | Accepted |
| D-031 | Transaction-cost basis (cash legs); proposed direction: traded notional | Proposed (see D-049); turnover-cap measure still open |
| D-032 | pandas as a development-only dependency, `pandas>=2.2,<4` | Accepted |
| D-033 | PyYAML runtime minimum raised to 6.0.2 (wheels for Python 3.11–3.13) | Accepted |
| D-034 | Asset universe v2: SPY, EFA, EEM, IEF, TLT, LQD, GLD | Proposed (provisional) |
| D-035 | Daily data on the observed session calendar; pipeline is daily-only | Proposed |
| D-036 | Missing-data policy: `error` default, optional `drop_sessions`, never fill | Proposed |
| D-037 | Price field `adj_close` (total-return approximation); fields never mixed | Proposed |
| D-038 | Split boundary semantics: rows labelled by their own date | Proposed |
| D-039 | Raw snapshots with manifest/checksums; CSV storage; processed-dataset ids | Proposed |
| D-040 | pandas becomes a runtime dependency | Proposed |
| D-041 | yfinance as an optional extra (`.[data]`, `>=1.7,<2`) | Proposed |
| D-042 | Data-validation thresholds (sanity checks) | Proposed (provisional) |
| D-043 | Feature timing: rows dated t use returns dated <= t; decision/target pairs at split boundaries excluded | Proposed |
| D-044 | Initial causal feature set, asset groups and windows | Proposed (provisional) |
| D-045 | Regime taxonomy and training-only calibration (trend band + volatility terciles) | Proposed (provisional) |
| D-046 | Warm-up, missing-feature and multi-session-return policy | Proposed |
| D-047 | Feature-set outputs, ids and frozen threshold artifact | Proposed |
| D-048 | Execution timing: decide at close d, execute at close d+L, earn from the next session | Proposed (default lag revised by D-055) |
| D-049 | Cost model: 15 bps x traded notional (non-cash legs), pro rata, initial funding charged | Proposed (provisional rates, D-007) |
| D-050 | Simulator constraints: long-only, no leverage, fractional weights, implicit cash at rf | Proposed (cap semantics clarified by D-057) |
| D-051 | Evaluation protocol: independent simulation per split, common start, boundary decisions dropped | Proposed (test-split question answered by D-056) |
| D-052 | Metric reporting: per-session metrics; annualised only when periods_per_year is set | Proposed |
| D-053 | Conventional baselines: equal weight monthly, equal-weight buy-and-hold, inverse volatility (63) monthly | Proposed |
| D-054 | Backtest configuration file and outputs | Proposed (id and outputs extended by D-056) |
| D-055 | Primary execution lag 1 session; lag 0 as idealised sensitivity case; lag required in config; shared timing | Proposed |
| D-056 | Test split evaluated only on explicit request (`--include-test`) | Proposed |
| D-057 | `max_weight` applies to target weights at execution; holdings may drift above it | Proposed |

---

## Entries

### D-001: Project layout and tooling

- **Status:** Proposed · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** `src/`-based package `adaptive_portfolio`; `pyproject.toml` as central configuration;
  pytest for tests; Ruff for linting and formatting; Python ≥ 3.11; GitHub Actions CI.
- **Rationale:** Standard, lightweight; the `src/` layout prevents tests from accidentally importing
  uninstalled code.
- **Approved by / date:** —

### D-002: Minimal dependencies

- **Status:** Proposed · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** Runtime depends only on PyYAML at present. Numerical and ML libraries are added in
  the milestone that first needs them, with version bounds (see `architecture.md`).
- **Approved by / date:** —

### D-003: Configuration approach

- **Status:** Proposed · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** Three YAML files (`data`, `environment`, `experiment`) loaded into frozen
  dataclasses with explicit validation; unknown keys rejected; no configuration framework.
- **Approved by / date:** —

### D-004: License

- **Status:** Proposed · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** MIT license, copyright "2026 Parv Patel and Mandar Patil".
- **Open questions:** Does the institution or course have an IP / licensing policy for student
  projects? Are both team members the correct copyright holders? Should the repository be public?
- **Approved by / date:** —

### D-005: Asset universe

- **Status:** Superseded by D-034 (2026-10-15) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** SPY, QQQ, IWM, EFA, TLT, IEF, GLD: liquid, diversified US-listed ETFs covering
  equities, bonds and gold, chosen only to make early development tractable.
- **Not validated:** liquidity, survivorship, ETF inception dates relative to the date range, and
  whether the universe suits the research question have not been assessed. The abstract does not
  specify a universe.
- **Approved by / date:** —

### D-006: Date range and frequency

- **Status:** Proposed (provisional) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** 2007-01-01 to 2024-12-31, daily bars, adjusted close prices.
- **Rationale:** Covers the 2008 crisis, the 2020 shock and the 2022 rate rise.
- **Not validated:** data availability for every ticker; feature warm-up periods reduce the usable
  start date.
- **Approved by / date:** —
- **Note (2026-10-15):** unchanged by milestone 2, so the existing split boundaries stay valid. Evidence from the first live snapshot: every D-034 instrument has data well before 2007-01-01 (latest first date: GLD, 2004-11-18), and the observed sessions run from 2007-01-03 to 2024-12-31. 2007-01-02 is absent, consistent with the US market closure that day. Extending the window is possible later but would be a separate decision.

### D-007: Transaction costs and slippage

- **Status:** Proposed (provisional) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** 10 bps proportional cost plus 5 bps slippage, charged on the value traded.
  *Note (2026-10-13):* exactly which turnover measure forms the cost basis (all-column
  two-way vs. traded notional, i.e. whether the cash leg is charged) is **not yet decided**;
  see D-031 (Open).
- **Not validated:** round-number placeholders, not derived from execution data. The abstract
  requires transaction costs; slippage and sensitivity sweeps are optional extensions.
- **Approved by / date:** —

### D-008: Data provider

- **Status:** Proposed (2026-10-15; was Open) · **Date raised:** 2026-10-12
- **Current default:** `provider: csv` (local files only), so that tests and CI need no network or
  credentials. `yfinance` is listed as a candidate free source.
- **To decide:** provider, licensing terms, corporate-action adjustment, data-quality checks.
- **Proposal (milestone 2, 2026-10-15):** a provider interface with three implementations:
  - `csv` stays the **config default**. It reads researcher-supplied files and needs no network,
    so default runs and CI stay offline (an existing test enforces this).
  - `yfinance` is the initial **live** source, opt-in with `--provider yfinance` and installed
    as an optional extra (D-041).
  - `synthetic` provides deterministic generated prices for tests and demos only.
- **Why yfinance:**
  - free, with no credentials;
  - daily history back to each ETF's inception;
  - supplies both `Close` and `Adj Close` plus dividend and split events;
  - Apache-2.0 licensed package.
- **Limitations (accepted risks, not validated):**
  - Unofficial access to Yahoo Finance; subject to Yahoo's terms of use (personal/research
    use).
  - Rate limits; silent revisions of adjusted history; possible outages or API breakage.
  - Not an authoritative or point-in-time source.
  - Failures can surface as empty responses rather than errors. They are treated as
    `EmptyResponseError` and never retried.
- **Alternatives considered:**
  - Stooq CSV endpoints: undocumented API; adjustment method less transparent.
  - Paid vendors (CRSP, Bloomberg, Refinitiv): authoritative, but need credentials and
    licences the team does not have.
  - Alpha Vantage, Tiingo: free tiers need API keys and impose low rate limits.
- **Evidence:** the pipeline fetched the full D-034 universe for 2007–2024 successfully on
  2026-10-15 (yfinance 1.7.0; see the project journal).
- **Scope note:** the roadmap had labelled the provider adapter `[O]` (optional). It was
  started because the team member's milestone-2 brief explicitly asked for a real-data
  adapter. That request authorised *implementing* it; the provider choice itself remains
  **Proposed**.

### D-009: Train / validation / test split dates

- **Status:** Proposed (provisional) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** train 2007-01-01 to 2016-12-31; validation 2017-01-01 to 2019-12-31; test
  2020-01-01 to 2024-12-31.
- **Rule (not provisional):** splits are chronological and non-overlapping; the test period is used
  once, for final evaluation.
- **Approved by / date:** —

### D-010: Minimum benchmark set

- **Status:** Open · **Date raised:** 2026-10-13
- **Context:** The abstract requires "conventional portfolio allocation benchmarks" without naming
  them. Candidates: equal weight, buy-and-hold, a reference portfolio, minimum variance,
  mean-variance, risk parity / inverse volatility.
- **To decide:** which subset is the required minimum.
- **Proposal (2026-10-15):** see D-053. Still awaiting team approval.


### D-011: Turnover definition

- **Status:** Accepted · **Proposed by:** Claude Code · **Date:** 2026-10-13
- **Decision:** turnover is **two-way** and measured **per rebalance event** from the drifted
  pre-trade weights w_pre and the post-trade (target) weights w_post, in one of two explicitly
  selected measures (`portfolio_turnover`, D-030):
  - **Default (`cash_column=None`):** τ = Σ |w_post − w_pre| over **all columns**, including a
    cash column if present. Range [0, 2].
  - **Traded notional (`cash_column=j`):** n = Σ |w_post − w_pre| over **non-cash columns only**.
    Range [0, 2].
  - The config validator accepts `max_turnover` in (0, 2]. **Which measure the cap constrains** is
    not yet decided (see D-031). The `configs/environment.yaml` comment describes the default.
- **Alternative (not chosen):** one-way turnover, i.e. half the two-way all-column value (range
  0–1), which is also common in the literature. Every report must state which measure it uses.
- **History:** implemented on 2026-10-13 as two-way over all columns; `cash_column` was added the
  same day (below). `w_pre` means the drifted pre-trade weights, not the previous target. If the
  team ever switches to one-way turnover, `portfolio_turnover`, its tests and the config bound must
  all change together.
- **Update 2026-10-13 (approved extension):** `portfolio_turnover` has a keyword-only
  `cash_column: int | None = None`.
  - `None` (default, unchanged): two-way turnover summed over **all** columns.
  - An index j: **traded notional**, the sum of |Δw| over **non-cash** columns only.
  - With a cash column, the default equals 2·max(B, S) and traded notional equals B + S, where B and
    S are the non-cash weight bought and sold. Without a cash column the two coincide.
  - Reported turnover must state which measure was used.
- **Approval record:** the `cash_column` extension was approved first, then the base two-way
  definition (after its wording was corrected on 2026-10-13 to match the code: "sum over assets"
  became "all columns, including cash" for the default, with traded notional for `cash_column`).
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-012: Regime signals as agent inputs

- **Status:** Open · **Date raised:** 2026-10-13
- **Context:** The abstract commits to investigating rising, falling and high-volatility conditions
  and whether an adaptive policy responds to them. The title says "regime-aware". Whether explicit
  regime labels or probabilities are given to the agent (vs. used only for analysis) is not specified.
- **Note (2026-10-15, does not resolve this decision):** milestone 3 produces causal features and
  rule-based regime labels (D-044, D-045) that *could* be agent inputs. Whether the agent
  receives labels, the underlying features, both, or neither (labels used only for analysis)
  remains open for the environment and agent milestones.


### D-013: Trade-timing convention

- **Status:** Open · **Date raised:** 2026-10-12
- **To decide before milestone 4:** whether decisions made with data up to the close of day *t*
  execute at the close of *t* or the open of *t+1*. This choice is critical for avoiding look-ahead bias.
- **Note (2026-10-13):** `portfolio_turnover` is deliberately timing-agnostic. The pre-trade
  weights it receives must be measured at the execution time chosen here, so the future
  environment must apply this decision when computing drift.
- **Proposal (2026-10-15):** see D-048. The default lag 0 is consistent with D-043; lag 1 is
  available as a conservative sensitivity check. Still awaiting team approval.


### D-014: PPO as the candidate RL algorithm

- **Status:** Set by abstract · **Date:** abstract
- **Decision:** PPO "will be considered as a candidate algorithm, alongside suitable baseline
  methods". PPO is a candidate, not a guaranteed final choice. The implementation library is still
  undecided.

### D-015: Portfolio constraints

- **Status:** Proposed (provisional) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** long-only; implicit cash position allowed; per-asset weight in [0, 0.40]; no
  turnover cap; daily rebalancing allowed; risk-free rate 0.0.
- **Approved by / date:** —

### D-016: Seed policy

- **Status:** Proposed / open · **Date:** 2026-10-12
- **Current:** a single global seed (42) in `experiment.yaml`.
- **To decide:** how many seeds per RL experiment (e.g. ≥ 5) and how seed variability is reported.

### D-017: Experiment output location and Git tracking

- **Status:** Open · **Date raised:** 2026-10-13
- **Context:** `experiment.yaml` sets `output_dir: reports`. Only `reports/figures/` is git-ignored;
  other files written to `reports/` would be picked up by `git add .`.
- **To decide:** a dedicated, git-ignored results directory (e.g. `reports/results/`), and which
  outputs (if any) are committed.

### D-018: Walk-forward scheme

- **Status:** Open · **Date raised:** 2026-10-13
- **Context:** The abstract commits to walk-forward validation "where feasible". `experiment.yaml`
  holds provisional settings (expanding, 5-year window, 12-month step) that no code uses yet.
- **To decide:** whether walk-forward folds run within train + validation only (keeping the test
  period untouched), and the window and step sizes.

### D-019: Embargo / purge gap

- **Status:** Open · **Date raised:** 2026-10-13
- **Context:** Adjacent periods currently touch (e.g. train ends 2016-12-31 and validation starts
  2017-01-01). A gap may be needed if rewards or labels use forward-looking horizons.
- **Note (2026-10-15):** for one-step decisions, D-043 already excludes decision/target pairs whose
  target lies in the next partition. Multi-step targets or rewards would need a wider gap; this
  decision remains open.


### D-020: Short-weight lower bound

- **Status:** Proposed · **Proposed by:** Claude Code during the 2026-10-13 audit · **Date:** 2026-10-13
- **Decision:** If `long_only` is ever set to false, `min_weight` must be ≥ −1. Previously, any
  negative value was accepted. Shorting is outside the abstract's scope; long-only remains the default.
- **Approved by / date:** —

### D-021: Portfolio-return input convention

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** `portfolio_returns` takes portfolio **values** V_0…V_n and returns n **simple**
  returns r_t = V_t / V_{t−1} − 1.
  - The first observation produces no return and is omitted, not filled with 0 or NaN.
  - Values must be finite and strictly positive, with at least 2 observations.
  - Missing values are rejected, never dropped or filled.
  - Output is positional (a NumPy array); the pandas index is not preserved.
- **Rationale:** Simple returns aggregate across assets, which matters for portfolio weights.
  Omitting the first value avoids a fake 0 % return. Rejecting NaN forces missing-data handling to be
  an explicit data-pipeline decision.
- **Alternatives considered:** log returns, which are additive over time and can be added later as a
  separate function if needed; a leading NaN or 0; silently dropping NaN.
- **Consequence:** a total loss to exactly 0 cannot be represented; the environment must handle ruin.
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-022: Standard-deviation convention

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** sample standard deviation with `ddof=1` (divide by T − 1) for both volatility and
  the Sharpe ratio. At least 2 returns are required.
- **Rationale:** returns are a sample from an unknown distribution. With `ddof=1`, the sample
  **variance** is an unbiased estimator of the population variance when observations are
  independent and identically distributed (the usual assumption). The sample **standard
  deviation** (its square root) is *not* generally unbiased: by Jensen's inequality it tends to
  underestimate σ slightly, especially for small samples. `ddof=1` is the pandas default for
  `.std()`; the NumPy default is `ddof=0`, so comparisons with other tools must state the
  convention.
- **Alternative:** `ddof=0` (population). The difference is negligible for long series, but
  material for short ones (factor √(T/(T−1))).
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-023: Annualisation factor

- **Status:** Proposed / open · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision (proposed):** metric functions require `periods_per_year` explicitly. There is no
  default and no hard-coded daily frequency. Any positive finite number is accepted. Annualisation
  uses √N scaling of the standard deviation (assumes i.i.d. returns).
- **Evidence (2026-10-15, does not resolve this decision):** the first live snapshot (D-034
  universe, 2007–2024) has between 250 and 253 observed sessions per calendar year. The data
  pipeline records these counts in its quality report but applies no annualisation.
- **Open:** which N the project uses for each data frequency, e.g. daily = 252 (trading days) vs.
  365, weekly = 52, monthly = 12. To be decided with the data pipeline (milestone 2) and applied
  consistently to all strategies.
- **Approved by / date:** —
- **Note (2026-10-15):** milestone-3 features are per-session quantities and are **not** annualised;
  windows are counted in sessions. This decision remains open.
- **Note (2026-10-15):** the milestone-4 backtest reports per-session metrics only by default
  (`backtest.periods_per_year: null`). Annualised metrics are computed only if the team sets
  that value, and are then labelled provisional. This decision remains open.


### D-024: Risk-free rate conversion

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** an annual risk-free rate R is converted to a periodic rate with geometric
  compounding, r_f = (1 + R)^(1/N) − 1, before it is subtracted from periodic returns.
  `sharpe_ratio` accepts either `annual_risk_free_rate` (scalar) or `periodic_risk_free_rate`
  (scalar or series), never both; the default is 0.
- **Rationale:** compounding N periodic rates reproduces R exactly. This matches the config field
  `environment.risk_free_rate`, which is an annual decimal.
- **Alternative:** simple division R / N, which is common and slightly larger. For R = 2 % and
  N = 252, simple division gives 7.937 × 10⁻⁵ and geometric gives 7.858 × 10⁻⁵ per day. The
  difference (about 7.8 × 10⁻⁷ per day) is small, but the choice is stated for reproducibility.
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-025: Behaviour for undefined metrics

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** a mathematically undefined metric raises `UndefinedMetricError` (a subclass of
  `ValueError`). Currently this is a Sharpe ratio whose excess-return std is zero. The function never
  returns `inf`, `nan` or a substitute value. Callers that build result tables catch the error and
  record "undefined" explicitly.
- **Tolerance:** a periodic sample std ≤ `ZERO_VOLATILITY_TOLERANCE` = 1e-12 counts as zero, so
  that floating-point noise (~1e-18) on constant series cannot produce ratios of ~1e16. Volatility
  is reported as exactly 0.0 under the same rule.
- **Alternative:** returning NaN, which is a widespread convention but propagates silently through
  averages and tables.
- **Tolerance review (2026-10-13), kept at 1e-12.** Measured on this machine (NumPy 2.5.4):
  - Noise std of mathematically constant series with values 1e-6 to 0.1 and lengths 2 to 25 200:
    at most ~2.8 × 10⁻¹⁷. Exact zero for values 1 to 100 in that test.
  - Noise std of `r − rf` with constant difference (2 000 random trials): at most ~1.3 × 10⁻¹⁸.
  - Smallest realistic periodic std, from daily T-bill-like returns with the rate drifting from
    4 % to 5 % p.a.: ~1.1 × 10⁻⁵.
  - So 1e-12 is about 5 orders of magnitude above the observed noise and about 7 below realistic
    volatility.
- **Limitations:**
  - The tolerance is absolute, not relative to the size of the returns.
  - A genuine standard deviation below 1e-12 would be reported as zero volatility, making the
    Sharpe ratio undefined.
  - Noise grows roughly with return magnitude × machine epsilon (~2.2 × 10⁻¹⁶). It could
    approach 1e-12 only for returns of order 10³ or more, which are not realistic decimal returns.
  - The measurements are empirical, from one platform, not a proof.
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-026: Drawdown conventions

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** drawdown is measured from the running peak P_t = max_{s≤t} V_s, with the **first
  observation as the initial peak**. Maximum drawdown is reported as a non-positive decimal, with
  positional `peak_index` and `trough_index`.
  - Ties: the earliest deepest point is the trough; the latest observation at the running-peak level
    before it is the peak.
  - With no decline, the result is 0.0 and both indices are 0.
- **Consequence:** any drawdown already in progress at the start of an evaluation window is not
  counted. Evaluation windows should be reported with this caveat.
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-027: Dependencies for milestone 1

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** add `numpy>=1.26,<3` as the only new runtime dependency. pandas is not a runtime
  dependency of the metrics; it is used in tests only (D-032) to verify that pandas Series and
  DataFrames are accepted.
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-028: Cumulative return

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** `cumulative_return(portfolio_values)` = V_T / V_0 − 1, a decimal. Same input rules as
  D-021 (at least 2 finite, strictly positive values). Intermediate values are validated even though
  only the first and last enter the formula, so a corrupt path is rejected.
- **Mathematical fact:** this equals ∏(1 + r_t) − 1 for the periodic simple returns (telescoping).
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-029: Annualised return (geometric, CAGR)

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** `annualized_return(portfolio_values, periods_per_year)` = (V_T / V_0)^(N/T) − 1.
  - T is the number of return periods (number of values − 1).
  - N is passed explicitly, as in D-023.
  - At least one period is required.
  - The result is computed as `expm1((N/T)·log(V_T/V_0))` for precision.
  - A result too large to represent raises `ValueError`. Extreme short-period losses may round
    to −1.0.
- **Why geometric:** it is the constant yearly growth rate that reproduces the realised outcome.
  The arithmetic alternative mean(r_t) · N overstates compounded growth when returns vary
  ("volatility drag", approximately σ²/2 per period). Example: +50 % then −50 % has an
  arithmetic mean of 0 but a geometric rate of −13.4 % per period.
- **Known limitation, not solved:** annualising a short window extrapolates it. For example, one
  month at +5 % annualises to ≈ +79.6 %. No minimum length is enforced in the function.
- **Reporting rule (accepted with this decision):** state T and the dates with every annualised
  figure, and do not headline annualised returns for windows shorter than one year.
- **Consistency note:** the Sharpe ratio uses the *arithmetic* mean of excess returns (handbook
  §10.4; D-022, D-024), so CAGR and the Sharpe numerator are different quantities by design.
  Reports should not mix them.
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-030: Turnover input contract

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** `portfolio_turnover(pre_trade_weights, post_trade_weights, *, cash_column=None)`
  takes two matrices of shape (events, assets) and returns a float64 array with one two-way value
  per row, in [0, 2]. The measure is the all-column default, or traded notional if `cash_column` is
  given (D-011).
  - **Pre-trade weights** are the actual, drift-adjusted weights immediately before trading,
    supplied by the caller. **Post-trade weights** are the target weights immediately after
    trading.
  - The function does not infer drift, dates or asset returns. Comparing consecutive targets is
    wrong after drift; this is demonstrated in `tests/test_turnover.py`.
  - Same asset ordering in both matrices. Cash is a column if the portfolio can hold cash, so that
    each row sums to 1.
  - **Long-only only:** weights must be finite and ≥ 0, and each row must sum to 1 within
    `WEIGHT_SUM_TOLERANCE = 1e-6`. This accepts float64/float32 rounding and rejects real
    allocation errors such as an omitted cash column.
  - Initial funding from cash counts only if supplied as a row.
  - `ValueError` for: empty matrices; non-2-D input (a single event must have shape
    (1, assets)); shape mismatch; non-finite, negative or non-summing weights.
  - `TypeError` for non-numeric or boolean weights.
- **Aggregation:** `annualized_turnover(event_turnover, observation_periods, periods_per_year)`
  = Σ τ_k · N / T_obs.
  - T_obs is the number of return periods in the evaluation window, independent of the number of
    events.
  - An empty event list means no trading and gives 0.0. This is a deliberate exception to the
    "empty raises" rule, because zero events is a meaningful outcome (e.g. buy-and-hold).
  - Event values must be finite and in [0, 2], with an allowance of 2 × `WEIGHT_SUM_TOLERANCE`
    above 2 for rounding; otherwise `ValueError`. 2-D input raises `ValueError`.
  - `observation_periods` must be a Python or NumPy integer (`TypeError` otherwise, booleans
    included) and > 0 (`ValueError` otherwise).
  - `periods_per_year` is validated as for the other annualised metrics.
- **`cash_column` (approved 2026-10-13):** optional, keyword-only, 0-based, non-negative index.
  - The column is excluded from the sum but **not** from validation: complete rows, cash
    included, must still be finite, non-negative and sum to 1.
  - Non-integers and booleans raise `TypeError`; indices outside [0, assets − 1], negative ones
    included, raise `ValueError`.
  - The function cannot verify that column j really is cash.
- **`annualized_turnover` return type:** always a Python `float`, also for NumPy integer
  `observation_periods` (fixed and regression-tested on 2026-10-13). The aggregate inherits the
  measure of its input events.
- **Not handled:** short positions or leverage (would need a gross-exposure definition), and
  cash flows into or out of the portfolio.
- **Approval record:** the `cash_column` extension was approved first, then the full contract
  (input rules, `WEIGHT_SUM_TOLERANCE` = 1e-6, aggregation, empty-events rule). Before acceptance,
  the wording was corrected on 2026-10-13 to match the code: the signature now shows
  `cash_column`, `TypeError` and `ValueError` cases are separated, and the event-value range and
  `observation_periods` rules are stated.
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-031: Turnover vs. transaction-cost basis

- **Status:** Open · **Date raised:** 2026-10-13
- **Context:** two-way turnover with a cash column counts both legs of a trade into or out of cash.
  - Example: buying 0.10 of an asset with cash gives τ = 0.20, but only 0.10 of a security is
    actually traded.
  - Switching 0.10 between two assets gives τ = 0.20, and 0.20 of securities is traded.
  - So "cost = cost_bps × τ × V" would double-charge cash-funded trades.
- **Options:**
  - (a) Charge costs on non-cash legs only: Σ over non-cash assets of |Δw| × V.
  - (b) Charge on τ / 2 (one-way).
  - (c) Accept the asymmetry and document it.
- **Analysis (pre-commit review, 2026-10-13):** with cash as a column, one-way = max(B, S) ≤ traded
  notional = B + S ≤ default two-way = 2·max(B, S). Neither turnover variant equals traded notional
  in general. Charging costs on traded notional is the mathematically consistent choice.
- **Proposed direction (approved as direction, not implemented):**
  - cost per rebalance = κ · n · V_pre, where n = `portfolio_turnover(..., cash_column=j)` and
    κ = (transaction_cost_bps + slippage_bps) / 10⁴;
  - the cost is deducted pro rata, which keeps post-trade weights on target, with a cost error of
    at most κ · cost (second order).
- **Still open:**
  - implementation and validation in the environment milestone;
  - which measure the config `max_turnover` cap constrains. The config comment currently describes
    the default all-column measure; it was **not** changed.
- **To decide** with the environment and cost model (milestones 4 and 7) before any cost-inclusive
  result is reported. `portfolio_turnover` itself is not affected.
- **Proposal implemented (2026-10-15):** see D-049. Costs are charged on traded notional
  (non-cash legs). Still open: which turnover measure a `max_turnover` cap constrains; the
  simulator refuses a non-null cap until this is decided.


### D-032: pandas as a development-only dependency

- **Status:** Accepted · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision:** add `pandas>=2.2,<4` to the `dev` optional dependencies only, so that tests verify
  the documented support for pandas Series and DataFrames.
- **Revision 2026-10-13 (approved):** the minimum was raised from 2.1 to **2.2**.
  - The pre-commit review found that a test using the month-end alias `"ME"` fails on pandas
    2.1.4 (`Invalid frequency: ME`); the alias exists only from pandas 2.2.
  - Verified in a clean Python 3.12.1 environment at the declared minimums (numpy 1.26.0,
    pandas 2.2.0, pytest 8.0.0, ruff 0.6.0): the full suite passed. pandas 3.0.6 was also tested.
  - **Limitation found:** the existing runtime minimum `PyYAML>=6.0` cannot be installed on
    Python 3.12, because PyYAML 6.0 has no 3.12 wheel and its source build failed. 6.0.1 was used
    instead. Normal installs resolve to a newer PyYAML, and 6.0 has Python 3.11 wheels. Whether to
    raise the PyYAML bound is a separate, unapproved decision; it was not changed.
  Runtime dependencies stay PyYAML and NumPy. pandas may become a runtime dependency with the data
  pipeline (milestone 2); that would be a separate decision.
- **Approved by / date:** team member using Git identity `Parvptl`, in the Claude Code session of 2026-10-13 (bound `pandas>=2.2,<4`, dev-only).

### D-033: PyYAML runtime minimum

- **Status:** Accepted · **Proposed by:** Claude Code (final review) · **Date:** 2026-10-13
- **Decision:** raise the runtime dependency from `PyYAML>=6.0,<7` to `PyYAML>=6.0.2,<7`. The
  Python support declaration (`requires-python >=3.11`; classifiers 3.11–3.13; CI matrix
  3.11–3.13) is unchanged.
- **Evidence:**
  - PyPI file lists (checked 2026-10-13):
    - PyYAML 6.0 has CPython wheels for 3.11 only, none for 3.12 or 3.13.
    - 6.0.1 adds 3.12 wheels, but none for 3.13.
    - 6.0.2 has wheels for 3.11, 3.12 and 3.13 (including win_amd64).
  - Locally, installing PyYAML 6.0 on Python 3.12.1 failed in the source-build step, and nothing
    was installed.
  - 6.0.2 is therefore the lowest version installable from wheels on every declared Python.
- **Effect:** normal installs already resolved to a newer PyYAML (6.0.3 locally), so typical
  installs and CI are unaffected. The change makes the declared minimum truthful.
- **Related limitation (not changed; NumPy bound kept by instruction):** on Python 3.13 the
  declared minimums `numpy>=1.26` (runtime) and `pandas>=2.2` (dev) also lack wheels.
  - The lowest versions with 3.13 wheels are numpy 2.1.0 and pandas 2.2.3.
  - The bounds remain correct for 3.11 and 3.12, and pip picks compatible versions on 3.13.
  - Per-Python minimums or environment markers would be a separate decision.
- **Approved by / date:** team member using Git identity `Parvptl`, Claude Code session of 2026-10-13.

### D-034: Asset universe v2

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
- **Status detail:** Proposed (provisional). It supersedes the D-005 proposal and has **not**
  been validated empirically.
- **Decision:** SPY (US large-cap equity), EFA (developed ex-US equity), EEM (emerging-markets
  equity), IEF (7–10y Treasuries), TLT (20+y Treasuries), LQD (US investment-grade credit),
  GLD (gold). Cash is not an ETF: the environment holds an implicit cash position
  (`configs/environment.yaml`).
- **Selection criteria:**
  1. One instrument per distinct risk driver: equity region, rate duration, credit, gold.
  2. Long-only, unleveraged, US-listed ETF.
  3. Price history starting before `start_date` (2007-01-01).
  4. High liquidity, so that the provisional cost assumptions (D-007) are not absurd: average
     2024 dollar volume ≥ ~$300M/day.
  5. A small universe (7) that the team can manage and explain.
- **Evidence (yfinance, retrieved 2026-10-15):**
  - First available dates: SPY 1993-01-29, EFA 2001-08-27, EEM 2003-04-14, IEF/TLT/LQD
    2002-07-30, GLD 2004-11-18.
  - Average 2024 dollar volume: SPY ≈ $30.6B, EFA ≈ $1.0B, EEM ≈ $1.2B, IEF ≈ $0.7B,
    TLT ≈ $3.7B, LQD ≈ $2.9B, GLD ≈ $1.5B.
- **Changes from D-005:** QQQ and IWM removed (largely the same US-equity risk as SPY); EEM
  (emerging markets) and LQD (credit) added.
- **Rejected alternatives:**
  - BIL (T-bills): first data 2007-05-30, after `start_date`.
  - SHY: a near-cash duration asset; implicit cash is used instead.
  - DBC (commodities): low liquidity (≈ $23M/day in 2024) and futures-roll effects.
  - VNQ (REITs): largely equity beta.
  - QQQ and IWM: overlap with SPY.
- **Limitations:**
  - **Survivorship and selection bias:** these are funds that exist today, chosen with
    hindsight. Funds that closed, or alternatives that performed badly, are absent. Results
    are therefore not evidence about a historical investable universe.
  - ETF prices reflect fund structure (expense ratios, tracking error); GLD and other ETFs have
    their own specific costs.
  - The universe was chosen using data up to 2024, which includes the test period. To avoid
    tuning on test data, the universe must not be revised in response to test-period results.
- **Approved by / date:** —

### D-035: Frequency and session calendar

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
- **Decision:** daily observations on the **observed calendar**: the union of dates on which at
  least one instrument has a price.
  - No exchange calendar is assumed or added as a dependency; a session exists only if the data
    show it.
  - The pipeline rejects non-daily `frequency` values with an actionable error. The config
    schema still allows them for other modules.
  - Calendar days, trading sessions, observations and missing cells are reported separately.
  - **No annualisation factor** is applied or implied (D-023 stays open).
- **Alternatives:** an exchange calendar package (an extra dependency, and still an assumption);
  resampling to weekly or monthly (left for later).
- **Approved by / date:** —

### D-036: Missing-data policy

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
- **Decision:** the default `missing_data.policy: error` stops when any instrument lacks a price
  on an observed session, and lists the missing cells.
  - Optional `drop_sessions` removes affected sessions for **all** instruments, up to
    `max_dropped_sessions`, and records each dropped session with the missing instruments.
  - The following return is flagged with `sessions_spanned > 1`.
  - Prices are **never** forward-filled or interpolated.
  - Within a raw frame, `NaN` prices count as missing; infinite or non-positive prices are
    errors.
- **Rationale:** filling invents prices and returns. Silently dropping rows hides gaps. Making
  both choices explicit keeps every gap visible in the quality report.
- **Evidence:** the first live snapshot had 0 missing cells (see the journal).
- **Approved by / date:** —

### D-037: Price field and corporate actions

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
- **Decision:** `price_field: adj_close` by default; `close` is the only alternative. The two
  are never mixed or substituted.
  - With yfinance, `adj_close` is back-adjusted for splits **and** dividends, so its simple
    returns approximate **total returns**.
  - `close` is split-adjusted only, so it gives **price returns** (dividends excluded).
  - The raw snapshot keeps dividend, split and capital-gain events for audit.
- **Limitations:**
  - The adjustment method is the provider's: dividends are reinvested at the close, and taxes
    are ignored.
  - Yahoo revises the whole adjusted history when new distributions occur, so re-downloads can
    differ.
  - The pipeline does not reconstruct total returns from the dividend data itself.
- **Approved by / date:** —

### D-038: Temporal split boundary semantics

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
- **Decision:** every row is labelled by its own date: the session for prices, the period-end
  date for returns.
  - A row belongs to the partition whose inclusive `[start, end]` from `experiment.yaml`
    contains that date. Other rows are `excluded` and counted.
  - The assignment is a pure function of dates and configuration, with no random splitting.
- **Consequence:** the first validation (or test) return uses the last earlier price as its
  starting price. That price was observed before the partition began, so this is not
  look-ahead. No training row depends on a price dated after `train.end`.
- **No fitted preprocessing** exists in the pipeline. Future fitted transforms must be fitted on
  the training partition only.
- **Still open:** an embargo or purge gap (D-019); the walk-forward scheme (D-018).
- **Approved by / date:** —

### D-039: Raw cache, storage format and reproducibility

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
- **Decision:**
  - Raw provider output is stored as a snapshot:
    `data/raw/<provider>/<raw_dataset_id>/`, with one CSV per instrument and a `manifest.json`.
    The manifest records the request, provider and version, retrieval time (UTC), software
    versions, SHA-256 per file, and the checksums of local CSV sources.
  - The id is a hash of the request parameters.
  - Cache modes:
    - `use`: reuse only if the manifest matches and every checksum verifies, otherwise
      re-fetch;
    - `refresh`: always fetch again;
    - `offline`: never fetch.
  - Processed datasets go to `data/processed/<processed_dataset_id>/`, where the id is a hash of
    the raw id plus the processing parameters.
  - **Storage format:** plain CSV with shortest round-trip floats and `\n` line endings, plus
    JSON. No Parquet, avoiding an extra dependency. The data are small (≈ 4,500 rows × 7
    instruments).
- **Guarantee (tested):** identical snapshot and configuration give byte-identical processed
  files, except `run_info.json`.
- **Not guaranteed:** that the provider would return the same data again. A snapshot freezes
  one retrieval; re-fetching can change adjusted history.
- **Approved by / date:** —

### D-040: pandas as a runtime dependency

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
- **Decision:** move `pandas>=2.2,<4` from the dev extras (D-032) to the runtime dependencies,
  for dated tables, CSV I/O and alignment in the data pipeline. D-032 had anticipated this as
  "a separate decision". The bounds are unchanged.
- **Known limitation (from D-033):** pandas 2.2.0–2.2.2 have no Python 3.13 wheels (2.2.3+ do).
- **Approved by / date:** —

### D-041: yfinance as an optional extra

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
- **Decision:** `pip install -e ".[data]"` installs `yfinance>=1.7,<2`.
  - It is not installed by default or in CI: its 12 dependencies include `curl_cffi`, `lxml`,
    `protobuf` and `websockets`.
  - The adapter imports it lazily and raises an actionable error if it is missing.
  - Tests use a fake module.
  - Only yfinance 1.7.0 was tested, so the lower bound is the tested version.
- **Approved by / date:** —

### D-042: Data-validation thresholds

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
- **Decision:** these are provisional sanity checks, not statistical choices:
  - `min_sessions` 1000;
  - `max_abs_return` 0.4, which catches an unadjusted 2:1 split (−50 %) but not smaller
    split ratios;
  - `max_calendar_gap_days` 7;
  - `max_start_lag_days` and `max_end_lag_days` 7.
- **Evidence:** in the first live snapshot, the largest observed |daily return| was 0.228 (EEM,
  October 2008) and the largest gap between sessions was 5 days. These are consistent with the
  thresholds, but they were **not** tuned to them.
- **Approved by / date:** —

### D-043: Feature timing convention and decision/target alignment

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 3) · **Date:** 2026-10-15
- **Decision:**
  - A feature or regime label dated `t` uses only `returns.csv` rows dated `<= t`. The row dated
    `t` holds `P_t / P_prev - 1`, observable at the close of `t`.
  - A decision taken at the close of `t` is evaluated with `r_{t+1}`, the next row. It is never a
    feature of `t`.
  - Windows are trailing (never centred) and counted in return observations.
- **Adjusted levels are not used:** back-adjusted price levels at `t` embed dividends paid
  *after* `t`, so features use returns and ratios only.
- **Split-boundary pairs:** feature rows keep the split of their own date (D-038). When pairing a
  decision at `t` with `r_{t+1}`, the pair gets a partition only if both dates are in it; pairs
  across a boundary are labelled `boundary`
  (`adaptive_portfolio.features.next_period_targets`). Without this rule, the last training
  decision's outcome (a validation return) would enter training data. This is an issue found in
  milestone 3; the splits themselves are unchanged.
- **Lookback vs. leakage:** validation/test features may use earlier-period returns in their
  trailing windows. That history was available at the time, so it is not leakage.
- **Approved by / date:** —
- **Note (2026-10-18):** `next_period_targets` now takes `execution_lag_sessions` (default 0,
  so this decision's pairing is unchanged). With lag `L` it pairs decision `t` with
  `r_{t+L+1}` and labels the pair `boundary` unless rows `t` to `t+L+1` share one partition.
  The arithmetic is shared with the simulator through `adaptive_portfolio.timing` (D-055).


### D-044: Initial feature set, groups and windows

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 3) · **Date:** 2026-10-15
- **Decision:** 34 features for the default 7-ETF universe:
  - per asset: latest return, 63-session momentum, 21-session volatility (3 × 7);
  - equal-weight `equity` (SPY, EFA, EEM) and `bond` (IEF, TLT, LQD) composites: latest return,
    21- and 63-session momentum;
  - market (equity composite): 21- and 63-session volatility, 63-session downside volatility,
    126-session drawdown;
  - cross-asset: dispersion (population std across assets), average 21-session asset volatility,
    63-session equity–bond correlation.
  - GLD is in no group and is described by its per-asset features.
- **Why these families:** momentum and volatility are the dimensions of the regime taxonomy
  (rising, falling, high-volatility, as in the abstract). Drawdown and downside volatility capture
  stress. Dispersion and equity–bond correlation describe diversification conditions. All are
  simple, widely used, and explainable in one sentence.
- **Conventions:**
  - sample std (`ddof=1`) for volatility, not annualised;
  - downside volatility = root-mean-square of negative returns (target 0);
  - drawdown measured from the window's peak, including the level at the window start;
  - correlation is NaN, never 0, when a series has zero variance;
  - values at or below 1e-12 are snapped to 0, as in D-025.
- **Windows (provisional):** 21 / 63 / 126 sessions, roughly one month, one quarter and half a
  year of observed sessions. They were chosen for interpretability, not tuned. They must not be
  changed in response to validation or test results.
- **Alternatives:** larger libraries (technical indicators, PCA factors), rejected for
  interpretability; exponentially weighted estimates, possible later.
- **Approved by / date:** —

### D-045: Regime taxonomy and training-only calibration

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 3) · **Date:** 2026-10-15
- **Decision:**
  - **Trend** from `equity_mom_63`: negative if `m < -b`, positive if `m > b`, neutral otherwise.
    `b` is the 1/3 quantile (0.3333) of `|m|` over training rows, so the labels keep their sign
    meaning.
  - **Volatility** from `market_vol_21`: low / normal / high, split at the training terciles
    (0.3333, 0.6667). These labels are relative to the training period.
  - The regime is `<trend>_<volatility>` (up to 9). Boundaries are inclusive for the middle
    category. Rows with a missing feature are `unavailable`.
  - Quantiles use NumPy `linear` interpolation.
  - Thresholds are fitted once on training rows with both features available, frozen in
    `regime_thresholds.json`, and applied unchanged to all partitions. A frozen artifact can be
    re-applied with `--thresholds` (compatibility is checked).
- **Alternatives:**
  - Pure terciles for trend: rejected, because "negative" could then include positive returns.
  - Fixed zero threshold: no neutral class, and noisy.
  - Hidden Markov models or clustering: optional extension (roadmap `[O]`); less transparent.
- **Evidence (first live snapshot, descriptive; not used to tune):**
  - `b` = 0.037974; volatility thresholds 0.008937 / 0.013051 per session (2,455 training rows,
    2007-04-04 to 2016-12-30).
  - All 9 regimes occur.
  - Warnings: training `negative_low` 1.5 %; validation `positive_normal` 1.6 % and
    `positive_high` 1.5 % (sparse); 62 % of training `positive_high` rows fall in 2009.
  - Validation is dominated by low-volatility regimes (`positive_low` 46 %), because the
    volatility thresholds are relative to a training period that includes 2008.
- **Limitations:** heuristic labels, not verified states. Training-relative volatility levels
  shift meaning if volatility regimes change. 63-session momentum lags turning points. Results
  inherit the universe's survivorship and selection bias (D-034).
- **Approved by / date:** —

### D-046: Warm-up, missing-feature and multi-session policy

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 3) · **Date:** 2026-10-15
- **Decision:**
  - A feature with window `w` is NaN for the first `w - 1` rows of the dataset (warm-up) and is
    never filled. Warm-up occurs only at the start of the data (training); validation and test
    rows have full history.
  - Undefined values (e.g. correlation with zero variance) are NaN and counted separately from
    warm-up.
  - Regimes require both regime features. Rows lacking them are labelled `unavailable` with a
    status that says which feature is missing, and they are excluded from calibration (counted).
  - Datasets containing returns with `sessions_spanned > 1` are refused unless
    `allow_multi_session_returns: true`, because windows would cover unequal periods.
- **Approved by / date:** —

### D-047: Feature-set outputs, ids and threshold artifact

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 3) · **Date:** 2026-10-15
- **Decision:**
  - Outputs go to `data/processed/features/<feature_set_id>/` (git-ignored). The id hashes the
    processed-dataset id, the feature configuration, the pipeline version, and `fit` or the
    SHA-256 of a loaded artifact.
  - The files are `features.csv`, `regimes.csv`, `regime_thresholds.json`,
    `regime_report.{json,md}` and `feature_metadata.json`. All are deterministic, with no
    timestamps (tested: reruns are byte-identical).
  - The threshold artifact is stored separately from the row data and records its provenance:
    calibration dates, row counts, and source dataset ids.
  - Configuration lives in a new `configs/features.yaml`, loaded by
    `load_feature_config`. `ProjectConfig` and its three-file contract are unchanged.
- **Approved by / date:** —

### D-048: Execution timing (proposal for D-013)

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
- **Decision:** a target is decided at the close of decision row `d` from information dated
  `<= d` (returns, and later features, D-043). It is executed at the close of `x = d + L`, and
  the resulting weights earn returns from row `x + 1` onward, drifting until the next execution.
  `L` = `backtest.execution_lag_sessions`, default **0**.
- **Rationale for L = 0:** it matches the close-to-close return definition and D-043 (decision
  at `t`, outcome `r_{t+1}`).
- **Known optimism:** with L = 0 the strategy trades at the same closing price it observed;
  real market-on-close orders must be submitted before the close. L = 1 (trade one session
  later) is the conservative check.
- **Alternatives:** execution at the next open (not possible: the processed data hold adjusted
  closes only); VWAP-style execution (no intraday data).
- **Guarantee (tested):** a weight never earns a return dated `<= x`.
- **Approved by / date:** —
- **Revision proposed (2026-10-18):** D-055 proposes lag 1 as the primary convention for
  reported comparisons and keeps lag 0 as an idealised sensitivity case. The timing rule
  itself (decide at `d`, execute at `d + L`, earn from `d + L + 1`) is unchanged.


### D-049: Transaction-cost model (proposal for D-031)

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
- **Decision:** at each execution:
  - traded notional `n = Σ_non-cash |w_target − w_drifted|`, computed with the milestone-1
    `portfolio_turnover(..., cash_column)` (D-011, D-030);
  - cost fraction `c = k · n` with `k = (transaction_cost_bps + slippage_bps) / 10^4`, i.e.
    15 bps under the provisional D-007 rates;
  - the cost is deducted from portfolio value pro rata, so post-trade weights equal the target;
  - net return `= g − c(1 + g)`, algebraically `(1 + g)(1 − c) − 1`.
- **Initial funding:** the first purchase from cash is a trade and is charged
  (`charge_initial_funding: true`).
- **Reporting:** the two-way all-column turnover (D-011 default) is also recorded, but not used
  for costs.
- **Not modelled:** market impact that depends on trade size, bid-ask variation over time,
  taxes, borrowing costs.
- **Approved by / date:** —

### D-050: Portfolio constraints in the simulator

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
- **Decision:**
  - Long-only (weights ≥ `min_weight` ≥ 0) and **no leverage** (Σ w ≤ 1), with fractional
    weights.
  - The remainder `1 − Σ w` is **cash**, earning the periodic risk-free rate.
  - `environment.risk_free_rate` is a provisional 0.0, so cash earns 0. A non-zero rate needs
    D-023 to convert it to a per-session rate, and is refused otherwise.
  - Per-asset `max_weight` (provisional 0.40, D-015) is enforced.
  - Invalid targets (NaN, negative, above `max_weight`, sum > 1, sum ≠ 1 when cash is not
    allowed) and a non-positive portfolio value raise `SimulationError`. Nothing is clipped or
    normalised silently.
- **Inverse volatility:** the only rule that can exceed `max_weight`. Its weights are capped by
  documented water-filling: the excess is redistributed proportionally among uncapped assets.
- **Approved by / date:** —
- **Clarification proposed (2026-10-18):** see D-057. The cap is checked on target weights
  at each execution only. The milestone-4 audit found inverse-volatility holdings drifting to
  about 0.4117 between rebalances on the live data; that behaviour is kept and now
  documented. "Enforced" above means "enforced on targets".


### D-051: Backtest evaluation protocol

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
- **Decision:**
  - Each split is simulated independently, starting from cash at `initial_capital`.
  - All strategies share one evaluation window per split: the first decision row is the first
    row at which every strategy has its required lookback (only the training split is affected:
    62 rows for a 63-session lookback).
  - Weights at decision row `k` use returns of rows `<= k`, which may come from earlier splits
    (historical lookback, not leakage).
  - A decision whose execution would occur on or after the split's last row would earn a return
    from the next split, so it is dropped and counted.
  - Results for one split therefore never contain another split's returns (tested, including by
    altering later-split returns).
  - No strategy parameter is fitted on validation or test data. The baselines have no fitted
    parameters beyond the fixed lookback.
- **Consequence:** split results are not one continuous track record; values restart at each
  split.
- **Open question (team):** the `backtest` command currently evaluates the test split too. The
  experiment log reports test-period results only for final, pre-registered evaluations.
  Should test-split evaluation become opt-in (e.g. a `--include-test` flag)? Until decided,
  milestone-4 documentation reports train and validation results only.
- **Alternatives:** one continuous simulation with per-split segments. Rejected: positions
  entering a split would depend on the previous split's path.
- **Approved by / date:** —
- **Answer proposed (2026-10-18):** see D-056. Test evaluation is opt-in.


### D-052: Metric reporting convention

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
- **Decision:** always report, for gross and net results:
  - cumulative return;
  - maximum drawdown from initial capital;
  - per-session volatility (milestone-1 `annualized_volatility` with N = 1, i.e. not
    annualised);
  - per-session Sharpe (only while the risk-free rate is 0);
  - traded notional, two-way turnover, costs and cost drag.
- **Annualised metrics** (return, volatility, Sharpe, turnover) are computed only when
  `backtest.periods_per_year` is set. The default is `null` because D-023 is open; when set,
  they are labelled provisional.
- All values come from the milestone-1 functions. Undefined values are reported as `None` with a
  reason.
- **Evidence for D-023 (not a decision):** the live snapshot has 250–253 sessions per calendar
  year.
- **Approved by / date:** —

### D-053: Conventional baselines (proposal for D-010)

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
- **Decision:**
  1. `equal_weight_monthly`: 1/N, rebalanced at the first session of each month.
  2. `buy_and_hold_equal_weight`: 1/N at the start, then drifting, never rebalanced.
  3. `inverse_volatility_monthly`: weights ∝ 1/sample std over the last 63 returns, capped at
     `max_weight`, rebalanced monthly.
- **Rationale:** equal weight is the standard naive-diversification benchmark. Buy-and-hold
  isolates the effect of rebalancing and its costs. Inverse volatility is the simplest
  risk-based allocation and uses only past returns.
- **What they are not:** none uses regime information, so they stay distinct from later
  regime-aware methods.
- **Not included (possible later, with approval):** minimum variance and mean-variance (need
  covariance estimation and optimisation choices), risk parity, momentum.
- The 63-session lookback is fixed, not tuned.
- **Approved by / date:** —

### D-054: Backtest configuration and outputs

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
- **Configuration:** `configs/backtest.yaml` (loaded by `load_backtest_config`; `ProjectConfig`
  is unchanged). Capital, costs, constraints and the risk-free rate are read from
  `environment.yaml`, so every strategy uses identical rules.
- **Outputs:** `data/processed/backtests/<backtest_id>/` (git-ignored) contains `ledger.csv`
  (per strategy, split and date: gross return, rebalance flag, decision date, two-way turnover,
  traded notional, cost, net return, value, drawdown, effective weights), `executions.csv`
  (decision and execution dates, target weights), `metrics.json`, `metrics.csv`,
  `backtest_report.md` and `metadata.json`. All are deterministic.
- **Id:** a hash of the processed-dataset id, the backtest config, the environment values and the
  pipeline version.
- **Approved by / date:** —

- **Note (2026-10-18):** the backtest id now also hashes the evaluated splits, and
  `BACKTEST_PIPELINE_VERSION` is 2 (D-056). `metrics.json`, `metadata.json` and the report
  record `evaluated_splits`. Outputs of pipeline version 1 (e.g. `ac2d6b163d4f5e4b`) are not
  reproduced by the new code under the same id.

### D-055: Primary execution lag and shared timing (revises the default of D-048)

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4.1, audit follow-up) · **Date:** 2026-10-18
- **Decision:** use an execution lag of **1 observed session** as the primary convention for
  reported comparisons. Keep **lag 0** as an explicitly idealised sensitivity case.
  `backtest.execution_lag_sessions` is a **required** key with no default, set to 1 in
  `configs/backtest.yaml`, so every run states its lag.
- **Rationale:** with lag 0 a signal that uses the close of `t` is filled at that same close,
  which a real order cannot achieve (market-on-close orders are submitted before the close). The
  milestone-4 audit classed this as a modelling choice, not a bug. Equal weight and buy-and-hold
  do not use prices to decide, so the lag only shifts their dates. Inverse volatility and any
  later RL policy do use the close of `t`.
- **Timing (unchanged rule):** decide at row `d` from data dated `<= d`; execute at the close of
  `d + L` (rows, i.e. observed sessions, not calendar days); first earned return row
  `d + L + 1`. The execution-day return is never earned by the new weights.
- **Shared timing:** `adaptive_portfolio.timing` (`execution_row`, `first_earned_row`,
  `last_evaluable_decision`, `validate_execution_lag`) is the single implementation, used by the
  simulator, the backtest drop rule and `features.next_period_targets`. Tests show that for lag 0
  and lag 1 the alignment targets equal the returns the simulator credits, and that the backtest
  keeps exactly the decisions the alignment assigns to each split.
- **Alternatives:**
  - keep lag 0 primary: optimistic;
  - next-open execution: no open prices in the processed data;
  - lag 2 or more: more conservative, but the delay is arbitrary.
- **Consequences:**
  - existing results computed with lag 0 (EXP-001) are the sensitivity case, not the primary
    convention;
  - each split loses `L` more rows at the start (funding at `k0 + L`) and `L + 1` decisions
    at the end.
- **Approved by / date:** —

### D-056: Test split evaluated only on explicit request (answers the D-051 question)

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4.1, audit follow-up) · **Date:** 2026-10-18
- **Decision:**
  - `backtest` evaluates **train and validation only** by default.
  - The test split is simulated, written, printed and reported only with the command-line
    option `--include-test` (`run_backtest(..., include_test=True)`). Use it only for the
    final, pre-registered evaluation.
  - It is deliberately **not** a configuration key, so a config file and the command line
    cannot disagree, and a copied config cannot silently enable it.
- **Outputs:**
  - The evaluated splits are part of the backtest id, so runs with and without test never
    overwrite each other.
  - Outputs record `evaluated_splits` and `test_split`.
  - The CLI prints the evaluated splits, and prints a warning banner when test is included.
  - `backtest-report --include-test` selects the opt-in run.
- **Guarantees (tested):**
  - test absent by default;
  - opt-in includes it;
  - train and validation metrics, decisions and target weights are identical with or without
    the test split and when test returns change;
  - split containment holds in both modes.
  No baseline has fitted parameters; nothing is fitted on test.
- **Alternatives:**
  - a config key: risk of a silent opt-in through a copied config;
  - an environment variable: invisible in the command;
  - a separate command: duplicates the code path.
- **Approved by / date:** —

### D-057: Weight-cap semantics (clarifies D-050)

- **Status:** Proposed · **Proposed by:** Claude Code (milestone 4.1, audit follow-up) · **Date:** 2026-10-18
- **Decision:**
  - `environment.constraints.max_weight` (provisional 0.40) constrains **target weights at each
    execution/rebalance**. A target above it is rejected (`SimulationError`), never clipped.
  - Between scheduled executions, holdings drift with prices and **may exceed the cap**. No
    trade is triggered, and no extra cost is charged.
  - The configuration name is unchanged; its comments, the docs and the conventions text state
    this meaning.
- **Rationale:** forcing holdings back to the cap between scheduled rebalances would change the
  strategies and their transaction costs. Rebalance-time limits are the common convention for
  periodically rebalanced benchmarks.
- **Evidence:**
  - Milestone-4 audit, live data, lag 0: inverse volatility exceeded 0.40 between rebalances on
    19 training-split ledger rows (maximum about 0.4117). Test-split rows are not reported.
  - A deterministic test shows a 0.40 target drifting to 0.48/1.08 with no trade.
- **Alternatives:**
  - continuous enforcement, i.e. a forced trade when the cap is breached: changes the
    strategy and its costs;
  - tolerance bands, e.g. rebalance when above 0.45: a new parameter.
  Either needs team approval.
- **Approved by / date:** —
