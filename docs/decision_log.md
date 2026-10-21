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
| D-006 | Data date range 2007-01-01 to 2024-12-31, daily | Proposed (provisional); acknowledged provisional 2026-10-19 |
| D-007 | Costs: 10 bps transaction + 5 bps slippage | Accepted (2026-10-19; placeholder rates, disclosed) |
| D-008 | Data provider: `csv` default (offline), optional `yfinance`, `synthetic` for tests | Proposed; acknowledged provisional 2026-10-19 |
| D-009 | Train / validation / test split dates | Accepted (2026-10-19) |
| D-010 | Minimum set of conventional benchmarks | Accepted (2026-10-19; resolved by D-053) |
| D-011 | Turnover definition: two-way; default over all columns, optional `cash_column` for traded notional | Accepted |
| D-012 | Whether regime signals are agent inputs | Accepted (2026-10-19; resolved by D-062) |
| D-013 | Trade-timing convention | Accepted (2026-10-19; resolved by D-048 + D-055) |
| D-014 | PPO as the candidate RL algorithm | Set by abstract |
| D-015 | Portfolio constraints: long-only, cash allowed, max 40 % per asset | Accepted (2026-10-19) |
| D-016 | Seed policy (seed 42; number of seeds per experiment) | Accepted (2026-10-19; resolved by D-066) |
| D-017 | Where experiment outputs are written and whether they are tracked in Git | Accepted (2026-10-19; resolved by D-069) |
| D-018 | Walk-forward scheme and its relation to fixed splits | Open |
| D-019 | Embargo / purge gap between periods | Open |
| D-020 | Lower bound of -1 on per-asset weight if shorting is ever enabled | Proposed |
| D-021 | Portfolio-return input convention (simple returns from positive values) | Accepted |
| D-022 | Sample standard deviation (`ddof=1`) for volatility and Sharpe | Accepted |
| D-023 | Annualisation factor supplied explicitly; per-frequency values open | Accepted (2026-10-19; N = 252 for daily data) |
| D-024 | Geometric conversion of annual to periodic risk-free rate | Accepted |
| D-025 | Undefined metrics raise `UndefinedMetricError`; zero tolerance 1e-12 | Accepted |
| D-026 | Drawdown conventions: first observation is the initial peak; tie-breaking | Accepted |
| D-027 | NumPy as the only runtime numerical dependency for milestone 1 | Accepted |
| D-028 | Cumulative return from first and last portfolio values | Accepted |
| D-029 | Annualised return is geometric (CAGR); no minimum sample length enforced | Accepted |
| D-030 | Turnover input contract: drift-adjusted pre-trade and post-trade weight matrices | Accepted |
| D-031 | Transaction-cost basis (cash legs) and turnover-cap measure | Cost basis and no cap: Accepted (2026-10-19) · turnover-cap measure: Open |
| D-032 | pandas as a development-only dependency, `pandas>=2.2,<4` | Accepted |
| D-033 | PyYAML runtime minimum raised to 6.0.2 (wheels for Python 3.11–3.13) | Accepted |
| D-034 | Asset universe v2: SPY, EFA, EEM, IEF, TLT, LQD, GLD | Proposed (provisional); acknowledged provisional 2026-10-19 |
| D-035 | Daily data on the observed session calendar; pipeline is daily-only | Accepted (2026-10-19) |
| D-036 | Missing-data policy: `error` default, optional `drop_sessions`, never fill | Accepted (2026-10-19) |
| D-037 | Price field `adj_close` (total-return approximation); fields never mixed | Accepted (2026-10-19) |
| D-038 | Split boundary semantics: rows labelled by their own date | Accepted (2026-10-19) |
| D-039 | Raw snapshots with manifest/checksums; CSV storage; processed-dataset ids | Accepted (2026-10-19) |
| D-040 | pandas becomes a runtime dependency | Proposed |
| D-041 | yfinance as an optional extra (`.[data]`, `>=1.7,<2`) | Proposed |
| D-042 | Data-validation thresholds (sanity checks) | Proposed (provisional); acknowledged provisional 2026-10-19 |
| D-043 | Feature timing: rows dated t use returns dated <= t; decision/target pairs at split boundaries excluded | Proposed |
| D-044 | Initial causal feature set, asset groups and windows | Proposed (provisional); acknowledged provisional 2026-10-19 |
| D-045 | Regime taxonomy and training-only calibration (trend band + volatility terciles) | Proposed (provisional). *Appended 2026-10-22: Accepted for the Gate 3 protocol (decision 2026-10-21, R-S), conditional on documented provenance; see D-083* |
| D-046 | Warm-up, missing-feature and multi-session-return policy | Proposed |
| D-047 | Feature-set outputs, ids and frozen threshold artifact | Proposed |
| D-048 | Execution timing: decide at close d, execute at close d+L, earn from the next session | Accepted (2026-10-19) |
| D-049 | Cost model: 15 bps x traded notional (non-cash legs), pro rata, initial funding charged | Accepted (2026-10-19) |
| D-050 | Simulator constraints: long-only, no leverage, fractional weights, implicit cash at rf | Accepted (2026-10-19) |
| D-051 | Evaluation protocol: independent simulation per split, common start, boundary decisions dropped | Accepted (2026-10-19) |
| D-052 | Metric reporting: per-session metrics; annualised only when periods_per_year is set | Accepted (2026-10-19) |
| D-053 | Conventional baselines: equal weight monthly, equal-weight buy-and-hold, inverse volatility (63) monthly | Accepted (2026-10-19) |
| D-054 | Backtest configuration file and outputs | Accepted (2026-10-19) |
| D-055 | Primary execution lag 1 session; lag 0 as idealised sensitivity case; lag required in config; shared timing | Accepted (2026-10-19) |
| D-056 | Test split evaluated only on explicit request (`--include-test`) | Accepted (2026-10-19) |
| D-057 | `max_weight` applies to target weights at execution; holdings may drift above it | Accepted (2026-10-19) |
| D-058 | Common evaluation window covers the 126-session feature warm-up | Accepted (2026-10-19) |
| D-059 | Funding trade reported separately; annualised turnover uses recurring trades only | Accepted (2026-10-19) |
| D-060 | Test-period isolation: default runs never parse test-period values (bounded loading; G-T (a)) | Accepted (2026-10-19) |
| D-061 | Working approval rule R-S: a decision communicated by either teammate counts for both | Accepted (2026-10-19; communicated by one team member, see entry) |
| D-062 | PPO observation (51 inputs), end-of-row weights, training-only scaling with ±10 clipping | Accepted (2026-10-19; under R-S) |
| D-063 | PPO action mapping: softmax, 0.40 per-asset cap, excess to cash | Accepted (2026-10-19; under R-S) |
| D-064 | PPO reward: decision-aligned log growth after costs; terminate at the last evaluable decision | Accepted (2026-10-19; under R-S) |
| D-065 | PPO decision frequency: weekly | Accepted (2026-10-19; under R-S) |
| D-066 | PPO seeds, selection and budget: 42–46, median validation Sharpe, 8 configs × 100,000 steps | Accepted (2026-10-19; under R-S) |
| D-067 | Simulator step interface reusing the accepted accounting, with parity tests | Accepted (2026-10-19; under R-S) |
| D-068 | Explainability: permutation sensitivity and regime summaries; associations, not causation | Accepted (2026-10-19; under R-S) |
| D-069 | RL experiment outputs in `data/processed/experiments/<id>/` (git-ignored) | Accepted (2026-10-19; under R-S) |
| D-070 | Commit authorship on the shared device | Accepted (2026-10-19; under R-S) for commits `71e6333`, `85c40d1`, `c387459`, `8da032a` only: directed and reviewed by Parv Patel; no standing rule *Appended 2026-10-22: the next commit is authored as `mavp309` (Mandar) by instruction; see the note* |
| D-071 | M5.1 implementation clarifications (scaler ddof, action bounds, reward lag ≥ 1, train-only loading, weekly schedule value) | Accepted (2026-10-19; under R-S) |
| D-072 | Normalised policy action interface `Box(−1, 1)`, scaled ×5 to the D-063 logits | Accepted (2026-10-19; under R-S, after the equivalence tests passed) |
| D-073 | M5.2 environment implementation choices (terminal observation, float32, bounds, deterministic reset, misuse errors, info fields) | Accepted (2026-10-19; under R-S) |
| D-074 | M5.3 PPO wrapper settings not fixed by D-066 (pinned SB3 defaults, one thread, run layout, provenance, run kinds) | Accepted (2026-10-19; under R-S) |
| D-075 | Pre-grid run safety: exclusive finalisation, code-provenance policy, sequential execution with timeout and stop-on-failure, manifest and resume, quarantine of stale state, determinism | Accepted (2026-10-19; under R-S) |
| D-076 | PPO validation evaluation protocol: checkpoints, deterministic actions, window, valuation, metrics, baselines, seed aggregation, tie tolerance, undefined metrics, data boundary, reproducibility | Accepted (2026-10-21; under R-S; protocol only, execution not authorised). *Appended 2026-10-21: execution then authorised separately and run once as EXP-006* |
| D-077 | Follow-up programme after EXP-006: training-period evaluation, execution smoothing, turnover-aware reward, lower frequency, early stopping | Proposed |
| D-078 | Protocol for D-077 item 1: training-period evaluation of the 40 checkpoints, deterministic vs sampled actions (no validation, no test) | Proposed |
| D-079 | Milestone F: static dashboard from saved results, workflow entry point, optional `viz` extra (matplotlib) | Accepted (2026-10-21; under R-S: in-session instruction to build the dashboard) |
| D-080 | Explainability execution conventions (label at t − lag, small-sample flag, permutation groups, repeats, fidelity check) | Proposed |
| D-081 | Regime-input ablation with retraining (plan only) | Proposed |
| D-082 | Test evaluator design: pre-registration schema and freeze rule, hash and commit guards, scenarios, paired bootstrap, single run | Proposed (amended 2026-10-22 for D-083) |
| D-083 | Gate 3 test-protocol decisions with separate status columns (approved in principle / evidence / accepted / implemented / reviewed / execution) | Partly accepted (2026-10-21/22; under R-S); G3-5 and G3-6 OPEN; nothing authorised for execution |

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
- **Acknowledged as provisional (2026-10-19):** Parv Patel and Mandar Patil acknowledged the
  current value as provisional for EXP-002 (checklist §1.3). It is **not** accepted or
  validated, and the status stays Proposed. Same evidence and caveat as the approvals of
  2026-10-19 (`approval_checklist.md` §0.1, amendment A-1; identity self-declared, not
  technically verified).

### D-007: Transaction costs and slippage

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** 10 bps proportional cost plus 5 bps slippage, charged on the value traded.
  *Note (2026-10-13):* exactly which turnover measure forms the cost basis (all-column
  two-way vs. traded notional, i.e. whether the cash leg is charged) is **not yet decided**;
  see D-031 (Open).
- **Not validated:** round-number placeholders, not derived from execution data. The abstract
  requires transaction costs; slippage and sensitivity sweeps are optional extensions.
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.
- **Note (2026-10-19):** accepted as the base convention. The rates remain
  round-number placeholders, not estimates, and are disclosed as such in results.

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
- **Acknowledged as provisional (2026-10-19):** Parv Patel and Mandar Patil acknowledged the
  current value as provisional for EXP-002 (checklist §1.3). It is **not** accepted or
  validated, and the status stays Proposed. Same evidence and caveat as the approvals of
  2026-10-19 (`approval_checklist.md` §0.1, amendment A-1; identity self-declared, not
  technically verified).

### D-009: Train / validation / test split dates

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** train 2007-01-01 to 2016-12-31; validation 2017-01-01 to 2019-12-31; test
  2020-01-01 to 2024-12-31.
- **Rule (not provisional):** splits are chronological and non-overlapping; the test period is used
  once, for final evaluation.
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-010: Minimum benchmark set

- **Status:** Accepted (2026-10-19; resolved by D-053) · **Date raised:** 2026-10-13
- **Context:** The abstract requires "conventional portfolio allocation benchmarks" without naming
  them. Candidates: equal weight, buy-and-hold, a reference portfolio, minimum variance,
  mean-variance, risk parity / inverse volatility.
- **To decide:** which subset is the required minimum.
- **Proposal (2026-10-15):** see D-053. Still awaiting team approval.
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.
- **Resolution (2026-10-19, G-P option (a)):** the minimum benchmark set is the one accepted in
  D-053.

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

- **Status:** Accepted (2026-10-19; resolved by D-062; was Open; status corrected in the
  pre-grid hardening pass) · **Date raised:** 2026-10-13
- **Context:** The abstract commits to investigating rising, falling and high-volatility conditions
  and whether an adaptive policy responds to them. The title says "regime-aware". Whether explicit
  regime labels or probabilities are given to the agent (vs. used only for analysis) is not specified.
- **Note (2026-10-15, does not resolve this decision):** milestone 3 produces causal features and
  rule-based regime labels (D-044, D-045) that *could* be agent inputs. Whether the agent
  receives labels, the underlying features, both, or neither (labels used only for analysis)
  remains open for the environment and agent milestones.
- **Proposed default (2026-10-19):** see D-062: features plus one-hot regime labels as agent
  inputs. Not approved. *(Superseded on 2026-10-19: D-062 was accepted, which resolves this
  decision.)*

### D-013: Trade-timing convention

- **Status:** Accepted (2026-10-19; resolved by D-048 + D-055) · **Date raised:** 2026-10-12
- **To decide before milestone 4:** whether decisions made with data up to the close of day *t*
  execute at the close of *t* or the open of *t+1*. This choice is critical for avoiding look-ahead bias.
- **Note (2026-10-13):** `portfolio_turnover` is deliberately timing-agnostic. The pre-trade
  weights it receives must be measured at the execution time chosen here, so the future
  environment must apply this decision when computing drift.
- **Proposal (2026-10-15):** see D-048. The default lag 0 is consistent with D-043; lag 1 is
  available as a conservative sensitivity check. Still awaiting team approval.
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.
- **Resolution (2026-10-19, G-P option (a)):** trade timing is the convention accepted in
  D-048, with lag 1 as the primary convention (D-055).

### D-014: PPO as the candidate RL algorithm

- **Status:** Set by abstract · **Date:** abstract
- **Decision:** PPO "will be considered as a candidate algorithm, alongside suitable baseline
  methods". PPO is a candidate, not a guaranteed final choice. The implementation library is still
  undecided.
- **Note (2026-10-19):** the library proposal (Stable-Baselines3 with CPU PyTorch and Gymnasium, as an optional `rl`
  extra) is pending a compatibility check and team approval. Nothing is installed.

### D-015: Portfolio constraints

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** long-only; implicit cash position allowed; per-asset weight in [0, 0.40]; no
  turnover cap; daily rebalancing allowed; risk-free rate 0.0.
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-016: Seed policy

- **Status:** Accepted (2026-10-19; resolved by D-066; was Proposed / open; status corrected in
  the pre-grid hardening pass) · **Date:** 2026-10-12
- **Current:** a single global seed (42) in `experiment.yaml`.
- **To decide:** how many seeds per RL experiment (e.g. ≥ 5) and how seed variability is reported.
- **Proposed default (2026-10-19):** see D-066: seeds 42–46, selection by median validation Sharpe. Not approved. *(Superseded on 2026-10-19: D-066 was accepted, which resolves this decision.)*

### D-017: Experiment output location and Git tracking

- **Status:** Accepted (2026-10-19; resolved by D-069; was Open; status corrected in the
  pre-grid hardening pass) · **Date raised:** 2026-10-13
- **Context:** `experiment.yaml` sets `output_dir: reports`. Only `reports/figures/` is git-ignored;
  other files written to `reports/` would be picked up by `git add .`.
- **To decide:** a dedicated, git-ignored results directory (e.g. `reports/results/`), and which
  outputs (if any) are committed.
- **Proposed default (2026-10-19):** see D-069: `data/processed/experiments/<id>/` (git-ignored). Not approved. *(Superseded on 2026-10-19: D-069 was accepted, which resolves this decision.)*

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

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 1) · **Date:** 2026-10-13
- **Decision (proposed):** metric functions require `periods_per_year` explicitly. There is no
  default and no hard-coded daily frequency. Any positive finite number is accepted. Annualisation
  uses √N scaling of the standard deviation (assumes i.i.d. returns).
- **Evidence (2026-10-15, does not resolve this decision):** the first live snapshot (D-034
  universe, 2007–2024) has between 250 and 253 observed sessions per calendar year. The data
  pipeline records these counts in its quality report but applies no annualisation.
- **Open:** which N the project uses for each data frequency, e.g. daily = 252 (trading days) vs.
  365, weekly = 52, monthly = 12. To be decided with the data pipeline (milestone 2) and applied
  consistently to all strategies.
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.
- **Note (2026-10-15):** milestone-3 features are per-session quantities and are **not** annualised;
  windows are counted in sessions. This decision remains open.
- **Note (2026-10-15):** the milestone-4 backtest reports per-session metrics only by default
  (`backtest.periods_per_year: null`). Annualised metrics are computed only if the team sets
  that value, and are then labelled provisional. This decision remains open.
- **Decision recorded 2026-10-19:** N = **252** observed sessions per year for daily
  data (`backtest.periods_per_year: 252`). Annualised metrics use √252 scaling,
  which assumes independent returns.

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

- **Status:** Cost basis and "no turnover cap": **Accepted** (2026-10-19; traded notional,
  via D-049) · turnover-cap measure: **Open** · **Date raised:** 2026-10-13
  *(Status line corrected 2026-10-18: it previously read "Open", which disagreed with the
  summary table. No decision was accepted by this correction.)*
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
- **Approved by / date (cost basis and no cap only):** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.
  The question of which turnover measure a future cap would constrain stays **Open**.

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
- **Acknowledged as provisional (2026-10-19):** Parv Patel and Mandar Patil acknowledged the
  current value as provisional for EXP-002 (checklist §1.3). It is **not** accepted or
  validated, and the status stays Proposed. Same evidence and caveat as the approvals of
  2026-10-19 (`approval_checklist.md` §0.1, amendment A-1; identity self-declared, not
  technically verified).

### D-035: Frequency and session calendar

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-036: Missing-data policy

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-037: Price field and corporate actions

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-038: Temporal split boundary semantics

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-039: Raw cache, storage format and reproducibility

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 2) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

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
- **Acknowledged as provisional (2026-10-19):** Parv Patel and Mandar Patil acknowledged the
  current value as provisional for EXP-002 (checklist §1.3). It is **not** accepted or
  validated, and the status stays Proposed. Same evidence and caveat as the approvals of
  2026-10-19 (`approval_checklist.md` §0.1, amendment A-1; identity self-declared, not
  technically verified).

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
- **Acknowledged as provisional (2026-10-19):** Parv Patel and Mandar Patil acknowledged the
  current value as provisional for EXP-002 (checklist §1.3). It is **not** accepted or
  validated, and the status stays Proposed. Same evidence and caveat as the approvals of
  2026-10-19 (`approval_checklist.md` §0.1, amendment A-1; identity self-declared, not
  technically verified).

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
- *Update (2026-10-22, appended; the text above is unchanged):* **Accepted** for the Gate 3
  test protocol (decision of 2026-10-21, recorded in D-083 under R-S, conditional on documented
  provenance).
  - **Provenance (re-verified 2026-10-22, read-only):**
    - `regime_thresholds.json` SHA-256 `5fc00522f02ce767ad2e16fde8539e0bf53af08e3bca4532acd48156485a16d7`;
    - calibration split `train` (2,455 of 2,517 rows used, 2007-04-04 to 2016-12-30, NumPy
      linear quantiles); `thresholds_mode: fitted_on_train`;
    - `regimes/rules.py` filters `split_labels == "train"`;
    - the thresholds equal the values recorded above;
    - the rule parameters (1/3 band quantile, terciles, windows 63 and 21) were set in
      `adffff5` (2026-10-15) and never changed.
  - **Recorded exposure:** the milestone-3 regime report (`regime_report.json`/`.md`, written
    2026-10-15, before the D-060 test isolation) iterates over all partitions, so it contains
    **test-period regime counts**. It is not opened, parsed, reproduced or used. The thresholds
    do not depend on it.
  - The labels remain heuristic descriptions; the limitations above still apply.

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

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.
- **Revision proposed (2026-10-18):** D-055 proposes lag 1 as the primary convention for
  reported comparisons and keeps lag 0 as an idealised sensitivity case. The timing rule
  itself (decide at `d`, execute at `d + L`, earn from `d + L + 1`) is unchanged.


### D-049: Transaction-cost model (proposal for D-031)

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-050: Portfolio constraints in the simulator

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.
- **Clarification proposed (2026-10-18):** see D-057. The cap is checked on target weights
  at each execution only. The milestone-4 audit found inverse-volatility holdings drifting to
  about 0.4117 between rebalances on the live data; that behaviour is kept and now
  documented. "Enforced" above means "enforced on targets".


### D-051: Backtest evaluation protocol

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.
- **Answer proposed (2026-10-18):** see D-056. Test evaluation is opt-in.


### D-052: Metric reporting convention

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-053: Conventional baselines (proposal for D-010)

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-054: Backtest configuration and outputs

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4) · **Date:** 2026-10-15
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

- **Note (2026-10-18):** the backtest id now also hashes the evaluated splits, and
  `BACKTEST_PIPELINE_VERSION` is 2 (D-056). `metrics.json`, `metadata.json` and the report
  record `evaluated_splits`. Outputs of pipeline version 1 (e.g. `ac2d6b163d4f5e4b`) are not
  reproduced by the new code under the same id.

### D-055: Primary execution lag and shared timing (revises the default of D-048)

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4.1, audit follow-up) · **Date:** 2026-10-18
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-056: Test split evaluated only on explicit request (answers the D-051 question)

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4.1, audit follow-up) · **Date:** 2026-10-18
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-057: Weight-cap semantics (clarifies D-050)

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4.1, audit follow-up) · **Date:** 2026-10-18
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
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-058: Common evaluation window covering the feature warm-up

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4.2) · **Date:** 2026-10-18
- **Decision:** `backtest.common_start_history_sessions` (integer ≥ 1; 1 if omitted, i.e. the
  milestone-4 behaviour) sets the return rows every strategy must have at the first decision of
  each split. `configs/backtest.yaml` sets it to **126**, the longest window in `features.yaml`
  (`market_drawdown`).
- **Effect:**
  - the common start is `k0 = max(s, required_history − 1)`;
  - on the live dataset the first training decision moves from row 62 (2007-04-04) to row 125
    (2007-07-05);
  - validation and test windows are unchanged.
- **Safeguard:** the CLI refuses a value below the longest feature window whenever
  `features.yaml` exists.
- **Rationale:** a later feature-based agent cannot decide before its features exist. Baselines
  must be evaluated over the same dates for a fair comparison (audit 2026-10-18).
- **Alternatives:**
  - derive the value automatically from `features.yaml`: implicit coupling;
  - start the agent later than the baselines: unequal windows.
- **Consequence:** EXP-001 (lag 0, 62-row warm-up) does not use this window. A new baseline
  record is needed.
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-059: Funding turnover reported separately (annualised turnover)

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (milestone 4.2) · **Date:** 2026-10-18
- **Decision:** metrics report `funding_traded_notional` (the one-off purchase from cash, ledger
  row 0) and `recurring_traded_notional` (all later executions). Their sum is
  `total_traded_notional`, which is unchanged. The opt-in `annualised_traded_notional` uses
  **recurring trades only**.
- **Rationale:** the funding trade happens once per simulation, so including it in a per-year
  rate inflates short windows (e.g. a 3-year validation split). Its cost stays in net returns
  and in `total_cost_*`.
- **Change of metric definition:** before milestone 4.2, `annualised_traded_notional` included
  the funding trade. It is only computed when `periods_per_year` is set, which no reported result
  has done (D-023 is open).
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-060: Test-period isolation rule for development runs (G-T option (a))

- **Status:** Accepted (2026-10-19) · **Proposed by:** Claude Code (2026-10-19) · **Date:** 2026-10-19
- **Decision:**
  - development runs never parse test-period values: the baseline backtest without
    `--include-test`, and `features.pipeline.load_feature_outputs` by default;
  - `splits.csv` (dates and labels only) is read up to the first row dated on or after the
    configured `test.start`, and that row's label must match `experiment.yaml`;
  - only the rows before it are parsed from `returns.csv`, `features.csv` and `regimes.csv`.

  The date and label of that one boundary row are the only test-period items read. No data file
  is hashed at run time.
- **Implementation:** commit `8e52693` (CI #8 passed). Regression tests use corrupted, removed
  and mislabelled synthetic test rows.
- **Approved by / date:** Parv Patel and Mandar Patil, 2026-10-19: named written confirmations of the whole Gate 1
  package in the Claude Code session, recorded verbatim in `approval_checklist.md` §0.1
  (amendment A-1). Author identity is self-declared in a shared-device session and was not
  technically verified; both confirmations arrived in one conversation message.

### D-061: Working approval rule R-S

- **Status:** Accepted (2026-10-19) · **Date:** 2026-10-19
- **Decision:** a task approval or decision communicated by either teammate is treated as
  approved by both Parv Patel and Mandar Patil.
  - No separate confirmations from the other teammate are required.
  - It applies to Gate 2, future decisions and task authorisations, unless a teammate asks for
    an additional step.
  - Approving a task authorises only its stated scope, never expressly prohibited actions.
- **Effect on history:** it applies from now on. Gate 1 (recorded under `approval_checklist.md`
  §0.1 and amendment A-1, with its one-message deviation) is unchanged.
- **Records under this rule** name the communicating teammate (as self-declared), or "a team
  member (not named)", and state that the other teammate's confirmation was not sought.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session); under the rule, the other teammate's separate confirmation was not sought.

### D-062: PPO observation, weights and scaling (proposal for D-012)

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** a team member, from the Claude Code recommendations (Gate 2 packet) · **Date:** 2026-10-19
- **Proposal:**
  - 51 inputs: 34 causal features, 9 one-hot regime labels (frozen thresholds; the label
    `unavailable` raises an error) and 8 end-of-row portfolio weights;
  - standardisation fitted on training rows only and then frozen; clipping at ±10, with clipping
    counts logged.
- **Source:** `approval_checklist.md` Gate 2 items 1–3; `ppo_design_proposal.md` §13–§15.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought.

### D-063: PPO action mapping

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** a team member, from the Claude Code recommendations (Gate 2 packet) · **Date:** 2026-10-19
- **Proposal:** `Box[−5, 5]^8` → softmax → each asset ≤ 0.40 → excess to cash. Every target must
  pass the simulator's `validate_target`.
- **Amended by D-072 (2026-10-19):** the policy now acts in `Box(−1, 1)^8`, scaled ×5 to these
  `[−5, 5]` logits. The mapping from logits to targets is unchanged.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought.

### D-064: PPO reward and episode termination

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** a team member, from the Claude Code recommendations (Gate 2 packet) · **Date:** 2026-10-19
- **Proposal:**
  - decision-aligned log growth after transaction costs, `r_k = log(V_(d_k+1) / V_(d_k))`, with
    the timing documented and tested;
  - terminate at the last evaluable decision of each split.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought.

### D-065: PPO decision frequency

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** a team member, from the Claude Code recommendations (Gate 2 packet) · **Date:** 2026-10-19
- **Proposal:** weekly, on the first observed session of each ISO week. This needs a tested
  `weekly` schedule.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought.

### D-066: PPO seeds, selection and training budget (proposal for D-016)

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** a team member, from the Claude Code recommendations (Gate 2 packet) · **Date:** 2026-10-19
- **Proposal:**
  - seeds 42–46;
  - select by the median validation net Sharpe, with tie-break lower learning rate → smaller
    `n_steps` → no entropy bonus;
  - 100,000 timesteps per run × 8 configurations × 5 seeds, subject to a throughput check
    before tuning;
  - report every seed.
- **Clarification (2026-10-19; no change):**
  - The 8 configurations are those of the accepted Gate 2 packet: learning rate {3e-4, 1e-4} ×
    `n_steps` {512, 1024} × entropy coefficient {0, 0.01}, with `batch_size` 64. They come from
    `ppo_design_proposal.md` §13 item 9 and §14 rows 6–7, summarised in §15.
  - They are implemented in `configs/agent.yaml`.
  - The throughput check was EXP-003 (about 3.5 h estimated); no budget change was proposed.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought.

### D-067: Simulator step interface

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** a team member, from the Claude Code recommendations (Gate 2 packet) · **Date:** 2026-10-19
- **Proposal:** a `PortfolioState` and `step` inside `evaluation/simulator.py` that reuse the
  accepted accounting (D-048–D-059). Regression tests must show ledgers identical to
  `simulate`.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought.

### D-068: Explainability scope

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** a team member, from the Claude Code recommendations (Gate 2 packet) · **Date:** 2026-10-19
- **Proposal:** permutation sensitivity of actions to observation features, on validation
  decisions only, plus regime-conditional allocation, risk and performance summaries. No SHAP.
  **These indicate associations, not causation**, and instability across seeds is reported.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought.

### D-069: RL experiment output location (proposal for D-017)

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** a team member, from the Claude Code recommendations (Gate 2 packet) · **Date:** 2026-10-19
- **Proposal:** `data/processed/experiments/<id>/` (git-ignored), with configs, seeds, package
  versions and hashes in metadata.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought.

### D-070: Commit authorship on the shared device

- **Status:** Accepted (2026-10-19; was Open), **limited to the four commits named in the
  decision below; no standing rule for future commits** · **Date raised:** 2026-10-19
- **Facts (2026-10-19):**
  - repository-local Git identity `mavp309 <mandar.avp@gmail.com>`, used for every commit in this
    repository on the shared device, whoever is working;
    *(Correction, 2026-10-19: this describes the default. `c1c1925` and the four commits named
    below set `Parvptl` explicitly per commit, so not every commit uses the local identity.)*
  - global identity `Parvptl <pparv2515@gmail.com>`, which would apply if the local setting
    were removed;
  - pushes appear under the `Parvptl` GitHub account.

  Git configuration is unchanged, and no history is rewritten.
- **Options:**
  - keep the local identity;
  - remove it, so commits default to `Parvptl`;
  - set an explicit identity per commit, matching the person who directed and reviewed the
    work.

  `Co-authored-by` is used only for genuine joint work, and AI assistance is disclosed in the
  journal.
- **Any Git configuration change** needs a separate, explicit decision.
- **Decision (2026-10-19):** the M5.1–M5.3 and pre-grid hardening work, committed and
  pushed on 2026-10-19 as `71e6333`, `85c40d1`, `c387459` and `8da032a`, was **directed and
  reviewed by Parv Patel**.
  - Its author and committer, `Parvptl <pparv2515@gmail.com>`, is therefore the accurate
    attribution. This follows the option "explicit identity of the person who directed and
    reviewed the work".
  - The code and documentation in these commits were largely written by Claude Code under
    that direction. This is disclosed in the README and the project journal; there is no AI
    trailer in the commit messages (CLAUDE.md).
  - The decision covers these four commits only. It does not re-attribute any other commit.
- **Facts recorded with the decision:**
  - The identity was set per commit. The Git configuration is **unchanged**: the
    repository-local identity is still `mavp309 <mandar.avp@gmail.com>`, so a plain
    `git commit` in this repository is still attributed to `mavp309`, whoever runs it.
  - No commit was rewritten. The earlier rewrite of 2026-10-18 (see the project journal and
    the local branch `backup/main-before-author-rewrite`) is unchanged.
  - `mandar.avp@gmail.com` is not linked to a GitHub account; commits under it show as
    unlinked on GitHub.
- **Not decided by this entry:** a standing rule for future commits, and any Git
  configuration change. Each needs its own explicit decision.
  - *Recommendation from the pre-commit review (not a team decision):* until a rule exists,
    choose each commit's identity explicitly, case by case.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team
  member ("Parv directed and reviewed it"; the message does not otherwise name its author;
  identity self-declared in a shared-device session), under rule R-S (D-061); the other
  teammate's separate confirmation was not sought.
- *Update (2026-10-22, appended; the decision above is unchanged):*
  - **Which commit:** the commit made on 2026-10-22 on top of `0f8341b`. It contains the
    EXP-006 close-out, the D-077 and D-078 drafts, milestones E and F, and the milestone-D and
    Gate 3 (D-083) implementation.
  - **Identity:** it is authored and committed with the repository-local identity
    `mavp309 <mandar.avp@gmail.com>`.
  - **Basis:** an in-session instruction to "commit last few stages as mandar". The message
    does not otherwise name its author; identity is self-declared in a shared-device session,
    recorded under R-S (D-061).
  - **Scope:** a per-commit choice, **not a standing rule**. Git configuration is unchanged.
    `0f8341b` keeps its recorded authorship (Parvptl).
  - The code and documents in that commit were largely written by Claude Code at the team's
    direction (see the project journal).

### D-071: M5.1 implementation clarifications

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** Claude Code during M5.1 implementation, for team
  review · **Date:** 2026-10-19
- **Context:** points that D-062 to D-067 do not fix, settled in code so that M5.1 could run.
  None of them changes an accepted decision.
- **Proposal:**
  1. **Scaler standard deviation** uses `ddof=0`. A constant feature on the fit rows is an
     error.
  2. **Out-of-bound actions:** an action outside `[−5, 5]`, or a non-finite one, raises in the
     action mapping rather than being clipped there. Stable-Baselines3 clips sampled actions
     to the `Box` bounds before the environment sees them.
  3. **The decision-aligned reward requires lag ≥ 1.** With lag 0 an action executes at its
     own decision close, so its cost would fall in the previous step's reward. Lag 0 stays a
     backtest sensitivity case (D-055) and is not offered to the agent.
  4. **Train-only loading** (`train_only=True`) extends the D-060 bound to the validation
     boundary, for building training inputs without parsing validation values.
  5. **`weekly`** is a valid baseline schedule value (not used by any baseline).
- **Observation:** the training episode has 496 weekly decisions, matching the design memo's
  count of 496. The memo's "about 494" estimate in item 9 assumed that the last `L + 1`
  decisions are dropped; no weekly decision falls in the last two training rows.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought. The approval does not authorise a commit, push, repeat smoke run or full-grid training; D-070 stays Open.

### D-072: Normalised policy action interface (resolves the M5.2 action-space warning)

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** Claude Code (M5.2 report),
  for team review · **Date:** 2026-10-19
- **Context:** Gymnasium's `check_env` warned that Stable-Baselines3 recommends a normalised
  action space. D-063 used `Box[−5, 5]^8`.
- **Decision:**
  - The environment's action space is `Box(−1, 1, shape=(8,))`, `float32`.
  - Each policy action `u` is scaled to logits `a = 5u` inside the environment.
  - The D-063 mapping is then applied unchanged: softmax, each asset ≤ 0.40, excess to cash.
  - Portfolio accounting and reward timing are unchanged.
  - This amends D-063's **interface** only. The D-063 mapping from logits to targets is
    unchanged.
- **Equivalence (verified before acceptance):**
  - **Mathematics:** `u ↦ 5u` is a bijection from `[−1, 1]^8` onto `[−5, 5]^8`. So the reachable
    targets are exactly those of D-063, and every D-063 action `a` gives the same target as the
    normalised action `u = a/5`.
  - **Floating point:**
    - A `float32` action, as SB3 emits it, has at most 24 significant bits and 5 needs 3. So
      `5u` is exact in `float64`, and the bounds map exactly (±1 → ±5).
    - For `float32`-origin actions, the round trip `a → a/5 → 5u` is exact. The float32 action
      *grids* of the two interfaces differ: an old float32 action's counterpart rounded to
      float32 is off by at most one float32 rounding of `a/5` (logits within 3e-7). That is a
      representation limit, not a change of the mapping.
  - **Checks:**
    - 200,000 random float32 actions plus edge cases: exact.
    - 20,000 old-vs-new targets: bitwise identical.
    - `test_normalised_actions_reproduce_the_d063_mapping`: bitwise for float32-origin actions,
      within 1e-15 for arbitrary float64 actions; out-of-bound, NaN and wrong-shape inputs are
      rejected.
    - `test_normalised_action_episode_equals_the_d063_episode`: driving the environment with
      `u = a/5` reproduces, bit for bit, the `simulate` ledger and rewards of the D-063 targets
      of `a`.
    - Real training split: 27 checks passed, and `check_env` no longer warns about the action
      space.
    - Full suite: 801 passed.
- **Consequence to note:** the *mapping* is equivalent, but PPO's learning behaviour is not
  meant to be. A Gaussian policy with unit initial standard deviation now explores the whole
  `[−5, 5]` logit range instead of a fifth of it. That is the purpose of normalising.
- **Approved by / date:** approval to investigate and implement, with acceptance conditional on
  the implementation and tests passing, communicated in the Claude Code session on 2026-10-19
  by a team member (the message does not name its author; identity self-declared in a
  shared-device session), under rule R-S (D-061). The other teammate's separate confirmation
  was not sought. Conditions met on 2026-10-19.

### D-073: M5.2 environment implementation choices

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** Claude Code during M5.2 implementation, for team
  review · **Date:** 2026-10-19 (originally listed under D-072; split off when D-072 was
  accepted, because the approval covered the action interface only)
- **Context:** points that D-062 to D-067 do not fix. They are settled in code so that M5.2
  could be validated. None of them changes an accepted decision.
- **Proposal:**
  1. **Terminal observation:** the last step returns the observation formed at the split's last
     row `e`. It uses the features and regime at `e` and the end-of-row weights. With
     `terminated=True` it is not used to estimate future value.
  2. **`float32` observations** (the Gymnasium and SB3 convention); accounting stays `float64`.
  3. **Observation-space bounds:** `[−10, 10]` for the features (the clip bound), `[0, 1]`
     for the regime flags and weights.
  4. **Deterministic `reset`:** every episode starts at `k0` from cash, with no random start
     offsets. This is consistent with the PPO design memo, item 9.
  5. **Misuse raises** `PortfolioEnvError`: `step` before `reset`, or after termination. A step
     is atomic.
  6. **`info["target"]`** is the requested target, assets plus cash.
     `info["post_trade_weights"]` holds the simulator's executed weights, renormalised as in
     milestone 4, so they can differ by one rounding unit (at most 2.2e-16 observed).
     `info["action"]` is the policy action `u`, and `info["logits"]` is `5u`.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought. The approval does not authorise a commit, push, repeat smoke run or full-grid training; D-070 stays Open.

### D-074: M5.3 PPO wrapper settings not fixed by D-066

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** Claude Code during M5.3 preparation, for team review ·
  **Date:** 2026-10-19
- **Context:** D-066 fixes the seeds, the 8-configuration grid, `batch_size` 64, the budget and
  the selection rule. The wrapper needs every other setting to be explicit.
- **Proposal:**
  1. **Pinned Stable-Baselines3 2.9 defaults** (in `configs/agent.yaml` under `fixed`, and in
     `agents/ppo.py` `SB3_CONSTANTS`). They are PROVISIONAL and not tuned:
     - `n_epochs` 10, `gamma` 0.99, `gae_lambda` 0.95, `clip_range` 0.2, `vf_coef` 0.5,
       `max_grad_norm` 0.5;
     - separate policy and value networks `[64, 64]` with tanh, orthogonal initialisation,
       `log_std_init` 0;
     - advantage normalisation on; no value clipping, no SDE, no target KL; one environment.

     Pinning means a library update cannot change a run silently. These values were verified
     against the installed SB3 2.9.0 signature.
  2. **`torch_num_threads` 1** and CPU only, matching the one-core assumption of the budget
     (design memo item 9).
  3. **Run layout (D-069):**
     - one directory per run, `data/processed/experiments/<run_id>/`, where `run_id` is a
       hash of the full identity: grid values, seed, budget, run kind, pinned settings,
       environment and costs, data provenance, scaler and package versions;
     - a run directory is written in staging, moved into place when complete, and never
       overwritten (enforced at the final move since D-075; before that, only at the start);
     - files: `run_config.json`, `metadata.json`, `scaler.json`, `model.zip` (final checkpoint
       only) and `monitor.csv` (training episodes).
  4. **Data provenance:** the dataset and feature-set ids plus the SHA-256 of the header and
     *training lines only* of `returns.csv`, `splits.csv`, `features.csv` and `regimes.csv`.
     Hashing whole files would read test-period bytes.
  5. **Run kinds:** `full` (the configured budget) and `smoke` (a smaller budget, for the
     throughput check only). The kind is part of the identity, so a smoke run can never be
     mistaken for a full run.
  6. **No evaluation or selection** in the wrapper. Validation evaluation needs separate
     authorisation.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought. The approval does not authorise a commit, push, repeat smoke run or full-grid training; D-070 stays Open.

### D-075: Pre-grid run safety, execution policy, code provenance and determinism

- **Status:** Accepted (2026-10-19; was Proposed) · **Proposed by:** Claude Code during the pre-grid hardening pass
  (requested by a team member on 2026-10-19), for team review · **Date:** 2026-10-19
- **Context:** the read-only preflight (2026-10-19) found the following problems:
  - the final move could replace a completed run;
  - runs did not record the code version;
  - there was no grid manifest or runner;
  - stale-state recovery after a hard kill was undefined;
  - the determinism intent of the design (§7) was not implemented.

  These rules govern how runs execute. They do not change the D-066 grid or budget.
- **Proposal:**
  1. **Exclusive finalisation:**
     - a completed run is renamed into place only if its directory does not exist;
     - completed results are never replaced;
     - each run holds an exclusive `<run_id>.lock`.
  2. **Code provenance policy:**
     - every run records its Git commit, whether the working tree is dirty, and a SHA-256 of
       the uncommitted changes, and these are part of the run id;
     - `full` runs **refuse** a dirty tree, or a tree without Git, with no override;
     - `smoke` runs may use uncommitted code, which is recorded;
     - a grid id includes the commit, so a resumed grid continues with the same code.
  3. **Execution:**
     - **sequential only**; parallel execution and continue-on-failure need separate approval;
     - each run is a child process (`PYTHONHASHSEED=0`) with a hard limit of **900 s**,
       about three times the expected 5.2 min;
     - the grid **stops at the first failure**: a non-zero exit, a timeout, or an output that
       fails verification;
     - failed and interrupted runs are retried only with `--retry-failed`;
     - launching needs `--execute --confirm-full-grid`.
  4. **Manifest and resume:**
     - `data/processed/experiments/grids/<grid_id>/manifest.json` is written atomically and
       records every run, status and attempt, plus a log per attempt;
     - on resume, completed run directories that verify are adopted, and a directory that
       fails verification stops the grid untouched;
     - a run that was `running` when its runner died is marked `failed` (`interrupted`).
  5. **Stale state after a hard termination:**
     - locks and staging directories are recovered only when their owner is on this host and
       its process is gone;
     - such items are **moved** to `_quarantine/<UTC time>-<name>/` with a `reason.json`,
       never deleted;
     - a failed run's staging directory is quarantined too (previously it was deleted);
     - locks from live processes, other hosts or unreadable files are left for a human.
  6. **Determinism:**
     - one torch thread;
     - `torch.use_deterministic_algorithms(True)` during training, which makes any
       non-deterministic operation raise instead of running silently; the previous setting is
       restored afterwards;
     - Stable-Baselines3 seeding (Python, NumPy, torch, action space) and the deterministic
       environment reset;
     - same seed → identical initial weights (tested).

     **Limits:** full-run bitwise reproducibility is **not verified** (verifying it needs
     training), and reproducibility across machines or library versions is not guaranteed.
- **Not covered here:** the validation-selection metric and evaluation policy, and the Gate 3
  items. They stay separate.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-19 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought. The approval does not authorise a commit, push, repeat smoke run or full-grid training; D-070 stays Open.

### D-076: PPO validation evaluation protocol (milestone B)

- **Status:** Accepted (2026-10-21; was Proposed) · **Proposed by:** Claude Code during
  milestone B, at a team member's
  request, for team review · **Date:** 2026-10-21
- **Context:**
  - EXP-005 trained 40 PPO policies on the training split.
  - D-066 fixes the selection rule in outline: median validation net Sharpe over seeds 42–46,
    tie-break lower learning rate → smaller `n_steps` → no entropy bonus.
  - It leaves the operational evaluation choices open.
  - This entry fixes every one of them, so that the evaluation is reproducible before any
    validation row is loaded. Each item says whether it **restates** an accepted decision or
    is a **new proposed choice**.
- **Proposal:**
  1. **Checkpoints** *(new)*:
     - the final checkpoints of grid `0f1c47502dc30d84` (EXP-005), exactly the 40 runs of
       `configs/agent.yaml`;
     - each is verified before evaluation: manifest status, files and SHA-256, identity hash
       equal to the run id, run spec equal to the grid run, clean training commit, data ids,
       training data ending before `validation.start`, and one shared training-only scaler;
     - **any failure aborts the whole evaluation; no checkpoint is skipped or replaced.**
  2. **Policy actions** *(new)*:
     - **deterministic**: the mean of the Gaussian policy, Stable-Baselines3
       `predict(deterministic=True)`, clipped to `[−1, 1]`, then the D-072 and D-063 mapping;
     - sampled actions are not used; a sampled-action sensitivity would need separate
       approval.
  3. **Evaluation window** *(restates D-051, D-058, D-064, D-065)*:
     - the validation split's common window of the baseline backtest: first decision `k0` =
       the first validation row (the 126-session history is met by earlier rows);
     - funding execution `x0 = k0 + 1`; last return row `e` = the last validation row; the
       last decision `≤ e − 2`;
     - policies decide weekly; baselines keep their own schedules (memo §6);
     - **every policy and baseline ledger must have identical dates**, which is checked;
     - observations at a validation row may use causal features computed from earlier,
       training-period rows. The scaler is the frozen training scaler stored with each
       checkpoint, and an `unavailable` regime at a decision row is an error.
  4. **Starting portfolio and final valuation** *(restates D-049, D-050, D-064)*:
     - start in cash at `initial_capital`; the funding trade at `x0` is charged at 15 bps
       (10 + 5);
     - mark to market at the close of `e`; **terminal positions are not liquidated and no
       terminal cost is charged** (as for the baselines); zero cash return.
  5. **Daily net return and Sharpe** *(restates the D-011 and D-021–D-030 metric conventions,
     D-023 and D-052)*:
     - net return `(1 + g)(1 − c) − 1` per ledger row;
     - annualised Sharpe = √252 × mean / std (`ddof=1`) of the daily net returns **excluding
       the funding row**, with rf = 0;
     - the evaluator refuses a configuration with N ≠ 252, rf ≠ 0 or lag ≠ 1.
  6. **Other metrics** *(restates D-052 and D-059; the allocation summary is new)*:
     - from `summarize_window`, exactly as for the baselines: gross and net cumulative return,
       annualised return (CAGR) and volatility, net maximum drawdown with its peak and
       trough dates, and gross maximum drawdown, both including the funding row, cost value,
       cost fraction and cost drag, funding and
       recurring traded notional, annualised recurring turnover, and two-way turnover;
     - **allocation:** time-averaged and maximum end-of-row weight per asset and cash, mean
       executed target, and the number of executions and decisions;
     - Sortino and Calmar are **not** reported. They are optional extensions in the README
       scope, with no agreed definition.
  7. **Baselines** *(restates D-053)*:
     - the three `configs/backtest.yaml` strategies (equal weight monthly, equal-weight buy and
       hold, inverse volatility monthly), untuned;
     - same simulator, costs, constraints, lag, window and metrics.

     The evaluator's baseline results are tested to equal the baseline backtest's validation
     results exactly.
  8. **Seed aggregation and selection** *(D-066 made operational; tolerance new)*:
     - per configuration, the **median** over the 5 seeds of validation annualised net Sharpe;
     - mean, sample standard deviation (`ddof=1`), minimum, maximum and **every seed** are
       reported;
     - the highest median is selected;
     - **tie tolerance 1e-9** (numerical only): every configuration within 1e-9 of the best
       median is tied;
     - ties go to the lower learning rate, then the smaller `n_steps`, then the lower entropy
       coefficient. The result is deterministic and independent of input order.
  9. **Undefined metrics** *(new)*: if any run's Sharpe is undefined (zero volatility) or
     non-finite, the evaluation **stops without a selection**, pending a team decision.
  10. **Data boundary** *(extends D-060)*:
      - rows are read only before `test.start` (2020-01-01), with the bounded loaders;
      - the rows actually held are checked against the configured dates and labels;
      - the evaluator has **no test option**;
      - training code now also checks that it holds only rows dated before `validation.start`
        and labelled `train`.
  11. **Reproducibility** *(new)*:
      - the evaluation id hashes the protocol, the grid manifest, every checkpoint hash, the
        data ids, the backtest and environment conventions, the code state and the package
        versions;
      - execution requires `--confirm-validation-evaluation` and a clean, committed tree;
      - one torch thread with deterministic algorithms; deterministic environment reset;
      - outputs go to `data/processed/evaluations/<evaluation_id>/` (git-ignored), written in
        staging, finalised exclusively, and never overwritten.
  12. **Use of results** *(new)*:
      - validation metrics serve configuration selection. They are not test results and not
        evidence of out-of-sample performance;
      - the test split stays sealed until Gate 3; its bootstrap settings and stress windows
        are still open.
- **Implementation:** `configs/evaluation.yaml` (parameters, validated by `EvaluationConfig`),
  `agents/evaluate.py`, `evaluation/selection.py`, `data/boundaries.py`,
  `scripts/evaluate_validation.py` (technical handbook §17). It is tested on synthetic data
  only; **not executed on project data**.
- **Amended on acceptance (2026-10-21):**
  - **Item 6 wording.** It previously read "net and gross maximum drawdown with dates
    (including the funding row)". That overstated the outputs: only the net drawdown has
    peak and trough dates.
  - No protocol choice changed.
  - Before acceptance, the evaluator received three implementation fixes, none of which
    changes the protocol: clean failure reporting, one code-provenance snapshot per
    operation, and a protocol hash. See the project journal.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-21 by a team member (the message does not name its author; identity self-declared in a shared-device session), under rule R-S (D-061); the other teammate's separate confirmation was not sought. Acceptance covers the protocol only; executing the validation evaluation needs a separate authorisation.
- *Update (2026-10-21, appended; the text above was true when written):*
  - execution was then authorised separately (approval checklist, item 2, under R-S) and run
    once as EXP-006 (evaluation `1ce9c490ed03c8c9`), with the protocol unchanged;
  - the "not executed on project data" note under *Implementation* describes the state at
    acceptance.

### D-077: Follow-up programme after EXP-006 (turnover and generalisation)

- **Status:** Proposed · **Proposed by:** Claude Code at a team member's request, for team
  review · **Date:** 2026-10-21
- **Context:** in EXP-006 no PPO policy reached any baseline's validation net Sharpe. The
  policies traded 13–28× per year, almost entirely through target changes. Training fit was
  inversely related to validation Sharpe. Analysis is in `docs/exp006_turnover_diagnostic.md`.
- **Proposal** (prioritised; each item needs its own approval before implementation or
  running):
  1. a training-period deterministic and sampled evaluation of the existing checkpoints, with
     no training and no validation;
  2. execution smoothing or a no-trade band on configuration 4, with parameters chosen on
     training data and one validation look;
  3. a turnover-aware reward, retraining configuration 4's hyperparameters;
  4. a lower decision frequency;
  5. early stopping or a smaller budget on an inner training split.

  Shared principles: parameters are fixed on training data only; validation is used at most
  once per item; the test period is never used; the configuration-4 selection under D-066 and
  D-076 stands.
- **Not affected:** D-076, the EXP-006 outputs, the selected configuration and the sealed test
  period.
- **Approved by / date:** —
- *Update (2026-10-21, appended):* a protocol for item 1 is drafted as D-078 (Proposed).
- *Clarification (2026-10-21, appended):* "13–28× per year" is recurring ETF traded notional per year: the initial funding trade and the cash leg are excluded (D-059).

### D-078: Protocol for D-077 item 1: training-period evaluation of the existing checkpoints, deterministic vs sampled actions

- **Status:** Proposed · **Proposed by:** Claude Code at a team member's request, for team
  review · **Date:** 2026-10-21
- **Full protocol:** `docs/protocol_d078_training_modes.md`. Nothing is implemented or run.
- **Summary:**
  - all 40 EXP-005 final checkpoints, on the training split only:
    - first decision 2007-07-05; funding 2007-07-06; last return 2016-12-30;
    - 496 weekly decisions; lag 1;
    - identical to training and to EXP-002's training window;
  - deterministic actions, as D-076: one rollout plus a bit-identical repeat;
  - sampled actions by the training mechanism (SB3 `predict(deterministic=False)`, clipped to
    [−1, 1]): R = 50 rollouts per checkpoint, seeds 10000–10049, common to all checkpoints;
  - the EXP-006 accounting and metrics, plus a new gross Sharpe and episode log growth;
  - the baselines must reproduce EXP-002's training metrics;
  - **primary metrics:** net Sharpe and annualised traded notional;
  - pre-declared comparisons C1–C5. Descriptive only: no selection, no tuning;
  - data boundary: `train_only` loading, guards on the rows held, and training-line hashes
    equal to those of training. No validation or test row is read;
  - new code, configuration and CLI. The D-076 evaluator, configuration and protocol hash are
    unchanged.
- *Revision before review (2026-10-21, appended):* protocol §2, §6 and §8 now state exactly:
  - the gross Sharpe call;
  - the turnover basis (recurring, ETF legs only);
  - that, as for EXP-005 training, the date and label of the one `splits.csv` boundary row
    (the first validation session) are read to check the boundary. No validation market
    value is parsed.
  "No validation or test row is read" above should be read in that sense. No protocol choice
  changed. EXP-007 remains planned, not executed.
- **Open choices U1–U12**, with proposed defaults: §11 of the protocol.
- **Cannot support:** a causal claim (e.g. "the policies overfit"), any statistical
  significance, a change to D-076's deterministic rule, or anything about the test period.
- **Relation to D-077:** accepting D-078 adopts only D-077 item 1; items 2–5 stay Proposed.
- **Approvals needed, in order:** A1 protocol; A2 implementation; A3 execution, naming the
  id, protocol hash, commit, grid and dataset.
- **Approved by / date:** —

### D-079: Milestone F: static dashboard, workflow entry point and `viz` extra

- **Status:** Accepted (2026-10-21; under R-S) · **Proposed by:** Claude Code · **Date:**
  2026-10-21
- **Context:** the dashboard is an optional extension (milestone 10 [O]). `CLAUDE.md` requires
  team approval before an [O] item starts.
- **Decision:**
  1. **Static dashboard:** a self-contained HTML page with embedded PNG figures, built **only
     from saved, hash-verified artifacts** named in `configs/workflow.yaml`. There is no server
     and no new web dependency.
     - Missing, failed or unauthorised analyses are shown as "Not available" with the reason.
     - No metric is hard-coded.
     - Builds go to `reports/figures/dashboard/<build_id>/` (git-ignored) and are never
       overwritten; the build id hashes the source files and the dashboard code.
  2. **Workflow entry point:** `scripts/workflow.py` with the modes `status` (the default;
     read-only), `verify`, `explain` and `dashboard`. It never trains, evaluates or reads the
     test period.
  3. **Optional `viz` extra:** `matplotlib>=3.8,<4`, for the figures and the dashboard. The core
     package and CI do not need it; figure tests skip without it.
  4. **Checkpoint provenance:** `agents/provenance.py` checks a run's integrity, identity, data
     boundary and compatibility with the current configuration before its results are shown.
- **Approved by / date:** communicated in the Claude Code session on 2026-10-21 by a team
  member. The message does not name its author; identity is self-declared in a shared-device
  session. The message asked to "integrate the finished research pipeline into a usable
  dashboard" and to produce "publication-quality plots". Recorded under rule R-S (D-061); the
  other teammate's separate confirmation was not sought. The static, no-server form and the
  matplotlib dependency were chosen by Claude Code within that instruction.

### D-080: Explainability execution conventions (proposed details for D-068)

- **Status:** Proposed · **Proposed by:** Claude Code · **Date:** 2026-10-21
- **Proposal** (implemented as defaults; see `docs/explainability.md` §2):
  - a ledger row *t* takes the regime label of session *t − lag*;
  - the funding row is excluded;
  - all nine regimes and `unavailable` are always reported;
  - a summary is flagged small below 63 sessions;
  - contiguous episodes are counted;
  - there are no confidence intervals;
  - the permutation groups are the recorded feature families, the 9 regime inputs and the 8
    weight inputs, permuted jointly across decisions;
  - 20 repeats with seed 0;
  - the score is the mean L1 change of the target weights (cash included);
  - observations are rebuilt from the saved ledger, and the rebuilt targets must match the
    executed ones within 1e-9;
  - the policy is evaluated one observation at a time.
- **Execution of the policy analysis on validation decisions is not authorised by this
  entry.**
- **Approved by / date:** —

### D-081: Regime-input ablation with retraining (plan only)

- **Status:** Proposed · **Proposed by:** Claude Code · **Date:** 2026-10-21
- **Proposal:** retrain configuration 4 (seeds 42–46, the same budget, data, reward, costs and
  timing) without the 9 one-hot regime inputs (42 inputs instead of 51). Compare on validation
  by the D-076 rules with the existing configuration-4 runs. Report every seed, with no
  significance claim. Full plan: `docs/explainability.md` §4.
- **Needs:**
  - a decision amending D-062 for this experiment only, plus code and tests;
  - training authorisation;
  - authorisation for a further validation look.

  It must not use the test period.
- **Approved by / date:** —

### D-082: Separate test evaluator and machine-readable pre-registration (milestone D)

- **Status:** Proposed · **Proposed by:** Claude Code · **Date:** 2026-10-21
- **Context:**
  - A team member's in-session message asked to "implement a separate test evaluator" using
    "the frozen Gate 3 protocol".
  - **No Gate 3 decision packet was attached and no Gate 3 item is decided**, so the protocol
    is not frozen.
  - The evaluator was therefore implemented as protocol-agnostic machinery. Every choice is
    read from `configs/preregistration.yaml`, which is a **DRAFT** with every item OPEN.
- **Proposal (implemented; see `docs/technical_handbook.md` §19):**
  1. **Pre-registration schema** (`PreregistrationConfig`):
     - 18 items, mirroring G3-1 to G3-27;
     - each item `decision: OPEN | ACCEPTED`, plus a `record` saying where the acceptance is
       written;
     - status `draft | frozen`; a frozen file must have every item ACCEPTED, and a cited source
       if stress windows are included;
     - unsupported choices are refused (lag 0 for PPO, D-071; any change to the policy cap;
       Sortino, which is not implemented);
     - hashes: the **pre-registration SHA-256** (full content) and a 16-hex **protocol hash**
       (values only).
  2. **Resolving the commit/pre-registration circularity:**
     - the frozen pre-registration carries no commit;
     - the unsealing authorisation names the pre-registration SHA-256 and the evaluator commit
       separately;
     - the evaluator refuses unless both match (`--preregistration-sha256`,
       `--expected-commit`, clean tree).
  3. **Evaluator** (`agents/test_evaluate.py`, a separate module; D-076 code and hash
     unchanged):
     - `--plan` reads no data rows and lists the blockers;
     - `--execute` checks the candidate against the validation selection and its provenance,
       refuses rows after `test.end`, does no selection, and allows one run per frozen
       pre-registration (immutable output id);
     - `--verify` recomputes the Sharpe ratios, the endpoint and the bootstrap draws.
  4. **Scenarios:**
     - the primary scenario (D-076 conventions on the test window);
     - pre-registered cost levels and lags (policies and baselines);
     - baseline caps (the PPO cap is never changed).

     A secondary scenario that cannot be computed is recorded as "not computed" with its
     reason. Example: equal weight cannot satisfy a cap below 1/N; the real universe has
     1/7 ≈ 0.143.
  5. **Uncertainty** (`evaluation/uncertainty.py`):
     - a paired stationary or circular block bootstrap with one index draw for all strategies;
     - the statistic: the seed-aggregate Sharpe minus each baseline's Sharpe;
     - percentile intervals, bootstrap p-values, and a Holm/Bonferroni/none adjustment;
     - outcomes `higher`, `lower` or `inconclusive`.
  6. **Risk** (`evaluation/risk.py`):
     - concentration on the risky sleeve, with cash reported separately;
     - stress-window metrics, with the drawdown measured inside the window;
     - gross Sharpe.
- **Reconciliation (no accepted content changed):**
  - D-018 and D-019 stay Open; D-043 and D-045 stay Proposed;
  - D-068 is Accepted, but its execution is not authorised;
  - D-071 (lag ≥ 1) is enforced;
  - D-076 is unchanged, and a regression test pins `e652adec1095c95a`;
  - D-077, D-078, D-080 and D-081 stay Proposed;
  - D-066 did not set a test endpoint.
- **Not implied:** no Gate 3 item is accepted, and no test data was read. Tests use synthetic
  data only.
- **Approved by / date:** —
- *Amendment (2026-10-22, appended; still Proposed):* implemented for D-083. Changes:
  - a moving-block method, plus a loop-based reference verification path
    (`evaluation/bootstrap_reference.py`);
  - a primary-only percentile interval with no p-values or outcome labels;
  - descriptive point differences for the equal-weight baselines;
  - fixed-action cost replay with a primary-cost identity check;
  - stress windows (peak close, trough close] with a run-time session check;
  - allocations, regime labels and boundary evidence in the outputs;
  - a full 40-character commit required;
  - an undefined primary metric fails the run;
  - verification extended to recompute every output.

### D-083: Gate 3 decisions (test protocol), recorded with separate status columns

- **Status:** **Partly accepted**, item by item, in the table below. The pre-registration stays
  a **DRAFT**, and the test period stays **sealed**.
- **Proposed by:** Claude Code, from the Gate 3 packet (G3-1 to G3-27).
- **Decided by:** a team member, as attributed below.
- **Date:** decisions 2026-10-21; recorded 2026-10-22.
- **Attribution:** communicated in the Claude Code session by a team member: approval in principle of the Gate 3 packet and decisions 1-6 (lag 2 omitted; baseline caps omitted; D-045 accepted conditionally; web research for stress sources; equal-weight comparisons as point differences; record id D-083) on 2026-10-21, and the implementation authorisation ("Master Execution Instruction") on 2026-10-22. The messages do not name their author; identity is self-declared in a shared-device session. Recorded under rule R-S (D-061); the other teammate's separate confirmation was not sought. R-S applies to these decisions only: it authorises no commit, push, test access, PPO explainability, training, ablation, stress evaluation or real-data bootstrap.
- **Machine-readable form:** `configs/preregistration.yaml`, status `draft`:
  - pre-registration SHA-256 `c9df7be179341025e323cf0b0f1555524f93975a9dbca70910963f479ca76000`;
  - protocol hash `f45b8b35e16d2d3c`;
  - 16 of 18 items ACCEPTED; `uncertainty` and `stress_windows` OPEN.
- **Numbering:** the packet's own numbers differed from the repository's from G3-9 onward.
  This table uses repository numbers; "(user Gx)" marks the packet's label.

**Status columns:**
1. **AIP** — approved in principle;
2. **EV** — evidence verified;
3. **FA** — formally accepted and recorded here;
4. **IM** — implemented;
5. **IR** — independently reviewed by a person other than the implementer;
6. **EX** — authorised for execution.

| Repository item | Decision | AIP | EV | FA | IM | IR | EX |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G3-1 candidate | Configuration 4, seeds 42–46, run ids and `model.zip` SHA-256 values as in EXP-006 | ✓ | ✓ hashes, run ids, compatibility; selection recomputed from the saved metrics | ✓ | ✓ plan check | ✗ | ✗ |
| G3-2 primary endpoint | Median over the five seeds of the annualised net Sharpe (√252·mean/std, ddof 1, rf 0, funding row excluded; D-076 definition, **not** set by D-066). Primary comparator: `inverse_volatility_monthly` | ✓ | ✓ consistent with D-076 | ✓ | ✓ | ✗ | ✗ |
| G3-3 secondary metrics | D-076 metric set plus gross Sharpe, allocation and trade counts | ✓ | ✓ synthetic tests | ✓ | ✓ | ✗ | ✗ |
| G3-4 baselines and accounting | Three D-053 baselines in the same run; 10+5 bps on ETF traded notional; funding charged; lag 1; cap 0.40; cash return 0 | ✓ | ✓ configurations | ✓ | ✓ | ✗ | ✗ |
| G3-5 uncertainty | Paired **moving-block** bootstrap: L = 21, 10,000 replicates, seed 20261021, 95% percentile interval for the primary difference; **no p-values** | ✓ | partial: synthetic, hand-calculated and reference-path tests by the implementer | **✗ OPEN** | ✓ | **✗** | ✗ |
| G3-6 stress windows | COVID crash 2020-02-19 → 2020-03-23 (23 sessions); 2022 bear market 2022-01-03 → 2022-10-12 (195 sessions); boundary (peak close, trough close] | ✓ | dates, levels and NYSE calendar ✓; **dataset calendar not checkable before unsealing** | **✗ OPEN** | ✓ run-time count check | ✗ | ✗ |
| G3-7 comparisons (user G3-7; selection part = user G3-8) | One inferential comparison (configuration 4 vs inverse volatility); equal-weight baselines as **descriptive point differences** only; no multiplicity adjustment needed; no test-based selection | ✓ | ✓ no selection path in the evaluator | ✓ | ✓ | ✗ | ✗ |
| G3-8 success criteria (user G3-9) | Effect size with interval; no threshold; validation underperformance acknowledged | ✓ | n/a | ✓ | ✓ no outcome labels | ✗ | ✗ |
| G3-9, G3-10, G3-18, G3-19 (user G3-21) | Immutable outputs; one run per frozen pre-registration; artifact hashes; full 40-character commit; independent recomputation; boundary evidence; an undefined primary metric fails the run | ✓ | ✓ synthetic tests | ✓ | ✓ | ✗ | ✗ |
| G3-11 pre-registration document | `configs/preregistration.yaml` | ✓ | n/a | ✓ (draft) | ✓ | ✗ | ✗ |
| G3-12, G3-21 reporting (user G3-20) | Report all pre-registered results, including underperformance; stress windows are descriptive slices of one history | ✓ | n/a | ✓ | ✓ notes | ✗ | ✗ |
| G3-13 unsealing (user G3-22) | A separate explicit authorisation naming the commit, both hashes, the evaluation id, the dataset, the checkpoint hashes and the command | ✓ procedure | n/a | ✓ procedure | ✓ guards | ✗ | **✗ not given** |
| G3-14 regime taxonomy (user G3-10) | D-045 thresholds (SHA-256 `5fc00522…16d7`) frozen for analysis; label at *t* − lag | ✓ conditional | ✓ re-verified 2026-10-22 | ✓ (D-045 note) | ✓ | ✗ | ✗ |
| G3-15 walk-forward (user G3-11) | Excluded from this protocol; D-018 stays Open | ✓ | n/a | ✓ | ✓ | ✗ | n/a |
| G3-16 embargo (user G3-12) | Not applied and not claimed; D-019 stays Open, D-043 Proposed | ✓ | n/a | ✓ | ✓ | ✗ | n/a |
| G3-17 explainability (user G3-13) | Plan only: `docs/explainability_validation_plan.md` | plan | — | ✗ | ✗ | ✗ | **✗** |
| G3-20 Sortino (user G3-19) | Excluded; D-076 unchanged | ✓ | n/a | ✓ | ✓ | ✗ | n/a |
| G3-22 amendments | Only before freezing, recorded with date and reason (amendment log in the YAML) | ✓ | n/a | ✓ | ✓ | ✗ | n/a |
| G3-23 costs (user G3-14) | 0, 15, 30 bps as **fixed-action accounting**; 15 bps must equal the primary run | ✓ | ✓ synthetic identity test | ✓ | ✓ | ✗ | ✗ |
| G3-24 lag (user G3-15) | Omitted (lag 1 only) | ✓ | n/a | ✓ | ✓ | ✗ | n/a |
| G3-25 caps (user G3-16) | Baseline caps omitted; PPO cap 0.40 | ✓ | n/a | ✓ | ✓ | ✗ | n/a |
| G3-26 concentration (user G3-17) | Risky-sleeve HHI (mean, max), effective positions, cash separate, share at cap, maximum held weight; undefined rows counted | ✓ | ✓ hand-checked | ✓ | ✓ | ✗ | ✗ |
| G3-27 regime minimum (user G3-18) | 63 sessions; smaller regimes flagged | ✓ | n/a | ✓ | ✓ | ✗ | ✗ |

**Stress-window evidence (web research authorised 2026-10-21; ETF, strategy and test results
never used):**
- **Wikipedia** "Closing milestones of the S&P 500" (read 2026-10-21): the 2020-02-19 close
  3386.15, and the "bear-market closing low of 3,577.03 set on Oct. 12, 2022".
- **CNBC** (S. Schnipper, 2022-06-13; S&P Dow Jones Indices table, read 2026-10-22):
  2/19/2020 → 3/23/2020 from 3386; 1/3/2022 from 4796; a closing-basis threshold of 3837 (20%
  below 4,796.56).
- **Intercontinental Exchange** NYSE holiday releases for 2020–2022 and 2022–2024 (read
  2026-10-22).
  - 2020: Feb 17 and Apr 10, so none inside the COVID window.
  - 2022: Jan 17, Feb 21, Apr 15, May 30, Jun 20, Jul 4 and Sep 5 inside the window.
  - This gives **23** and **195** return sessions in (peak close, trough close].
- **No official bear-market definition exists.** A ≥ 20% peak-to-trough decline on a closing
  basis is the convention.
- **Search summaries not used as evidence:** Reuters, Yardeni and others appeared only as
  search-engine summaries; Investing.com refused command-line access.
- **Still unchecked:** the counts are verified against the exchange calendar, **not** against
  the dataset. The evaluator checks them at run time; a mismatch gives `not computed`, and the
  dates are never moved.

**Blocking freeze:**
1. G3-5 independent human review.
2. G3-6: the team must either accept the run-time calendar check as the verification, or
   exclude the stress windows. Otherwise the item can only be resolved by reading test-period
   dates.
3. Gate 3c: a team review of the evaluator, and a commit instruction with authorship (D-070
   has no standing rule).
- **Approved by / date:** as attributed above. AIP and FA are given only where marked. IR and
  EX are not given for any item.
