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
| D-005 | Asset universe: 7 US-listed ETFs | Proposed (provisional) |
| D-006 | Data date range 2007-01-01 to 2024-12-31, daily | Proposed (provisional) |
| D-007 | Costs: 10 bps transaction + 5 bps slippage | Proposed (provisional) |
| D-008 | Data provider | Open (offline `csv` default) |
| D-009 | Train / validation / test split dates | Proposed (provisional) |
| D-010 | Minimum set of conventional benchmarks | Open |
| D-011 | Turnover definition | Proposed (provisional) |
| D-012 | Whether regime signals are agent inputs | Open |
| D-013 | Trade-timing convention | Open |
| D-014 | PPO as the candidate RL algorithm | Set by abstract |
| D-015 | Portfolio constraints: long-only, cash allowed, max 40 % per asset | Proposed (provisional) |
| D-016 | Seed policy (seed 42; number of seeds per experiment) | Proposed / open |
| D-017 | Where experiment outputs are written and whether they are tracked in Git | Open |
| D-018 | Walk-forward scheme and its relation to fixed splits | Open |
| D-019 | Embargo / purge gap between periods | Open |
| D-020 | Lower bound of -1 on per-asset weight if shorting is ever enabled | Proposed |

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

- **Status:** Proposed (provisional) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
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

### D-007: Transaction costs and slippage

- **Status:** Proposed (provisional) · **Proposed by:** Claude Code during scaffolding · **Date:** 2026-10-12
- **Decision:** 10 bps proportional cost plus 5 bps slippage on traded notional.
- **Not validated:** round-number placeholders, not derived from execution data. The abstract
  requires transaction costs; slippage and sensitivity sweeps are optional extensions.
- **Approved by / date:** —

### D-008: Data provider

- **Status:** Open · **Date raised:** 2026-10-12
- **Current default:** `provider: csv` (local files only), so that tests and CI need no network or
  credentials. `yfinance` is listed as a candidate free source.
- **To decide:** provider, licensing terms, corporate-action adjustment, data-quality checks.

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

### D-011: Turnover definition

- **Status:** Proposed (provisional) · **Proposed by:** Claude Code · **Date:** 2026-10-13
- **Decision:** Per-rebalance turnover = sum over assets of |w_new − w_old| (two-way, range 0–2).
  The config validator accepts `max_turnover` in (0, 2] accordingly.
- **Alternative:** half this quantity (one-way, range 0–1), which is also common. Choose before
  milestone 1 and state the choice in every report.
- **Approved by / date:** —

### D-012: Regime signals as agent inputs

- **Status:** Open · **Date raised:** 2026-10-13
- **Context:** The abstract commits to investigating rising, falling and high-volatility conditions
  and whether an adaptive policy responds to them. The title says "regime-aware". Whether explicit
  regime labels or probabilities are given to the agent (vs. used only for analysis) is not specified.

### D-013: Trade-timing convention

- **Status:** Open · **Date raised:** 2026-10-12
- **To decide before milestone 4:** whether decisions made with data up to the close of day *t*
  execute at the close of *t* or the open of *t+1*. This choice is critical for avoiding look-ahead bias.

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

### D-020: Short-weight lower bound

- **Status:** Proposed · **Proposed by:** Claude Code during the 2026-10-13 audit · **Date:** 2026-10-13
- **Decision:** If `long_only` is ever set to false, `min_weight` must be ≥ −1. Previously, any
  negative value was accepted. Shorting is outside the abstract's scope; long-only remains the default.
- **Approved by / date:** —
