# Adaptive Portfolio Intelligence

**Explainable, regime-aware reinforcement learning for dynamic portfolio allocation and risk management.**

> **Disclaimer.** This is an academic research and decision-support project. It is **not financial
> advice**, and nothing in this repository should be used to make real investment decisions. No
> improvement over traditional strategies is assumed in advance; any finding must be supported by
> the experimental evidence recorded in [`docs/experiment_log.md`](docs/experiment_log.md).

**Status:**
- **Milestone 1 (financial metrics):** complete. Committed as `94e6f74`; GitHub Actions CI passed
  on that commit.
- **Milestone 2 (market-data pipeline):** implemented and tested locally, not yet committed. Its
  decisions are *Proposed*.

Configuration loading, a reproducible market-data pipeline, and seven metrics are available:
- portfolio returns
- cumulative return
- annualised return (CAGR)
- annualised volatility
- Sharpe ratio
- maximum drawdown
- two-way turnover

There is no trading environment, baseline, agent or experimental result yet. See
[Project status](#project-status-and-milestones).

---

## Overview and motivation

Portfolio allocation is a sequential decision problem under uncertainty. Many traditional
strategies use fixed rules or rely on assumptions (stable means and covariances, negligible trading
costs) that may not hold as markets move between rising, falling and high-volatility regimes.

This project frames allocation as a reinforcement learning (RL) problem. An agent observes features
derived from historical market data, chooses portfolio weights, and is rewarded according to
risk-adjusted performance net of trading costs. The aim is to study, carefully and reproducibly,
**whether and when** an adaptive, regime-aware policy improves on credible baselines, and to make
its decisions interpretable.

The original project abstract is in [`Abstract.pdf`](Abstract.pdf).

## Research objectives

1. Formulate portfolio allocation as a sequential decision problem in which the agent's feedback
   reflects both investment performance and risk, with transaction costs included.
2. Investigate market conditions such as rising, falling and high-volatility periods (using only
   information available at decision time), and examine whether an adaptive policy responds to them.
3. Train an RL agent, with **Proximal Policy Optimization (PPO) considered as a candidate
   algorithm**, and compare it with conventional portfolio allocation benchmarks.
4. Evaluate out-of-sample, and, **where feasible**, with walk-forward validation and stress testing
   across different market conditions.
5. Explore explainability techniques to understand the factors associated with the agent's
   allocation decisions and risk-taking behaviour.
6. Assess usefulness *and* limitations (performance, risk control, adaptability, interpretability),
   reporting negative results as well as positive ones.

## Scope: abstract commitments vs. optional extensions

The submitted abstract ([`Abstract.pdf`](Abstract.pdf)) defines the required scope. Anything not in
it is an **optional extension**, pursued only if time allows and approved by the team
(see [`docs/decision_log.md`](docs/decision_log.md)).

| Area | Required by the abstract | Optional extension (not committed) |
| --- | --- | --- |
| Problem | Sequential decision formulation; risk-aware feedback | Alternative reward designs |
| Algorithms | PPO as a candidate; suitable baseline methods | DQN or other RL algorithms |
| Market conditions | Study of rising / falling / high-volatility periods | Statistical regime models (e.g. HMM) as agent inputs |
| Benchmarks | Conventional portfolio allocation benchmarks | An extended benchmark set |
| Costs | Transaction costs | Slippage model, turnover caps, cost-sensitivity sweeps |
| Metrics | Cumulative return, Sharpe ratio, maximum drawdown, turnover | Sortino, Calmar, bootstrap confidence intervals |
| Evaluation | Out-of-sample testing | Walk-forward validation and stress testing (*"where feasible"*) |
| Explainability | Explainability techniques explored | Specific methods such as SHAP |
| Output | Reproducible framework and evaluation | Interactive dashboard |

Regime handling is central to the project title ("regime-aware"). The abstract commits to studying
market conditions; whether explicit regime signals are fed to the agent, and how they are computed,
is an open design decision.

## Planned system architecture

```text
configs/*.yaml ──► config ──┐
                            ▼
   raw prices ──► data ──► features ──► regimes
                            │              │
                            ▼              ▼
                       environment ◄── (observations: features + regime signals)
                        │       ▲
                 actions│       │rewards (net of costs, risk-aware)
                        ▼       │
                agents (PPO, …)   baselines (equal weight, min-variance, …)
                        │                 │
                        └──────► evaluation ◄──┘   (metrics, walk-forward, stress tests)
                                     │
                         explainability, visualization ──► reports/
```

Module responsibilities and data flow are described in [`docs/architecture.md`](docs/architecture.md).

## Planned benchmark strategies

| Strategy | Purpose |
| --- | --- |
| Equal weight (periodically rebalanced) | Simple, hard-to-beat diversification baseline |
| Buy and hold | No-trading reference; zero turnover after entry |
| Single-asset / 60-40-style reference portfolio | Familiar market reference |
| Minimum variance | Risk-focused optimisation baseline |
| Mean-variance (Markowitz) with constraints | Classical optimisation baseline |
| Risk parity / inverse volatility | Risk-budgeting baseline |
| Momentum / volatility targeting | Simple adaptive rule-based baselines |

These are **candidates**. The abstract requires "conventional portfolio allocation benchmarks"
without naming them; the minimum required set is an open team decision. All baselines will be
evaluated under exactly the same data, cost model, constraints and periods as the RL agents.

## Evaluation methodology

- **Chronological splits.** Train → validation → test, non-overlapping and in time order
  (see [`configs/experiment.yaml`](configs/experiment.yaml)). The test period is used once, for final
  evaluation.
- **Out-of-sample testing** on the held-out test period (required).
- **Walk-forward evaluation** with expanding or rolling re-training windows, **where feasible**.
- **Costs included.** Transaction costs are charged on every trade and turnover is reported.
  Slippage and sensitivity to different cost assumptions are planned extensions.
- **Metrics.** Required by the abstract: cumulative return, Sharpe ratio, maximum drawdown and
  turnover. Planned additions: annualised return and volatility, Sortino, Calmar and cost drag.
- **Market-condition analysis.** Performance broken down by market condition (rising, falling,
  high-volatility) and, where feasible, by stress episodes.
- **Robustness.** Multiple random seeds, with variation across seeds reported.

## Financial research safeguards

These principles are binding for all work in this repository (also in [`CLAUDE.md`](CLAUDE.md)):

1. **Chronological splits, and walk-forward evaluation where feasible.** Never randomly shuffle
   financial time series for model evaluation.
2. **No look-ahead bias or data leakage.** Features, regime labels, normalisation statistics and
   model fits at time *t* may only use information available at *t*.
3. **Account for transaction costs and turnover** in every reported result.
4. **Compare learned policies with simple, credible baselines** under identical conditions.
5. **Keep training, validation and final test periods separate.** Do not tune on the test set.
6. **Report risk-adjusted returns and drawdowns,** not just cumulative returns.
7. **Never claim a strategy is profitable without evidence.** Backtests are not live performance.
8. **Record seeds, configurations, assumptions and results** for every experiment.
9. **Research and decision support only,** not financial advice.

## Repository structure

```text
adaptive_portfolio_intelligence/
├── .github/workflows/ci.yml   # Lint + tests on Python 3.11–3.13 (offline)
├── configs/                   # Provisional YAML configs: data, environment, experiment
├── data/
│   ├── raw/                   # Local raw market data (git-ignored)
│   └── processed/             # Derived datasets (git-ignored)
├── docs/
│   ├── project_journal.md     # Dated record of work sessions and findings
│   ├── technical_handbook.md  # Setup, configuration reference, conventions
│   ├── decision_log.md        # Design / research decisions and their approval status
│   ├── experiment_log.md      # Experiment record template and entries
│   ├── architecture.md        # Module responsibilities and data flow
│   ├── roadmap.md             # Milestones (required vs. optional)
│   ├── presentation_guide.md  # How to present the project honestly
│   └── glossary.md            # Finance / RL / evaluation terms
├── notebooks/                 # Exploratory analysis only; core logic lives in src/
├── reports/figures/           # Generated plots (git-ignored)
├── scripts/                   # CLI workflows: validate_config.py, market_data.py
├── src/adaptive_portfolio/
│   ├── config.py              # Config loading and validation (implemented)
│   ├── data/                  # Market-data pipeline (implemented, milestone 2)
│   ├── features/              # Planned: causal feature engineering
│   ├── regimes/               # Planned: market-regime detection
│   ├── environment/           # Planned: portfolio environment
│   ├── agents/                # Planned: RL agents (PPO, …)
│   ├── baselines/             # Planned: traditional strategies
│   ├── evaluation/            # Financial metrics (implemented); backtesting planned
│   ├── explainability/        # Planned: policy explanations
│   └── visualization/         # Planned: plots (dashboard optional)
├── tests/                     # pytest suite
├── Abstract.pdf               # Original project abstract
├── CLAUDE.md                  # Instructions for AI-assisted coding sessions
├── Makefile                   # Developer shortcuts
└── pyproject.toml             # Packaging, pytest and Ruff configuration
```

## Local setup

Requires Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
                                   # Windows (PowerShell): .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
# optional, only for live market data (yfinance):
python -m pip install -e ".[dev,data]"
```

Common tasks (with GNU make, or run the commands shown in the [`Makefile`](Makefile) directly):

| Task | make | Direct command |
| --- | --- | --- |
| Run tests | `make test` | `python -m pytest` |
| Lint | `make lint` | `python -m ruff check .` |
| Format | `make format` | `python -m ruff format .` |
| All CI checks | `make check` | lint + `ruff format --check .` + tests |
| Validate configs | — | `python scripts/validate_config.py` |
| Market-data pipeline | — | `python scripts/market_data.py --help` |

No market data, network access or credentials are needed to install the package or run the tests.
The live provider (yfinance) needs no credentials. If a provider requiring credentials is adopted
later, copy `.env.example` to `.env` and fill it in locally; `.env` is git-ignored.

## Market-data pipeline

Milestone 2 adds a configuration-driven pipeline. It turns provider data into a validated,
reproducible dataset of daily prices and simple returns, with chronological train / validation /
test labels and a quality report. All of its decisions (D-034 to D-042) are **Proposed**.

```bash
python scripts/market_data.py validate                       # check configs
python scripts/market_data.py build --provider synthetic     # offline demo (NOT market data)
python scripts/market_data.py build --provider yfinance      # live data; needs ".[data]" + network
python scripts/market_data.py build --provider yfinance --cache-mode offline   # reuse snapshot
python scripts/market_data.py report --provider yfinance     # print the quality report
python scripts/market_data.py split  --provider yfinance     # re-derive and verify the split
```

- **Universe (provisional, D-034):** SPY, EFA, EEM, IEF, TLT, LQD, GLD. These are liquid ETFs
  covering US, developed and emerging equities, Treasuries of two durations, investment-grade
  credit and gold, all with history before 2007. They are funds that exist **today**, chosen with
  hindsight, so results carry survivorship and selection bias.
- **Data source (D-008):**
  - `csv` (default): your own files in `data/raw/csv_input/`; offline.
  - `yfinance`: free, unofficial and revisable; opt-in.
  - `synthetic`: generated prices for tests and demos.
- **Daily data, 2007-01-01 to 2024-12-31** (D-006, D-035). Sessions are the dates that actually
  appear in the data; no annualisation is applied.
- **Prices:** `adj_close` by default (split- and dividend-adjusted, approximately total return);
  never mixed with `close` (D-037).
- **Missing data:** the default is to stop with an error. `drop_sessions` drops affected sessions
  and records them. Prices are never forward-filled (D-036).
- **Returns:** simple returns between consecutive retained sessions, computed with the
  milestone-1 `portfolio_returns`. Each row records how many sessions it spans.
- **Splits:** each row is labelled by its own date using `configs/experiment.yaml`; there is no
  random splitting (D-038).
- **Cache (D-039):** raw snapshots live in `data/raw/<provider>/<id>/`, with a `manifest.json`
  (request, provider version, retrieval time, SHA-256 checksums). The CLI prints `CACHE HIT` or
  `FETCHED`. Use `--cache-mode refresh` to re-download. A cached snapshot freezes one retrieval;
  it cannot make a revisable remote source permanently reproducible.
- **Outputs:** `data/processed/<id>/` contains `prices.csv`, `prices_long.csv`, `returns.csv`,
  `splits.csv`, `quality_report.{json,md}`, `metadata.json` and `run_info.json`. Everything under
  `data/` is git-ignored.

Details, schemas, validation rules, leakage semantics and troubleshooting are in
[`docs/technical_handbook.md`](docs/technical_handbook.md) §11.

## Configuration

All provisional assumptions live in [`configs/`](configs/) and are labelled as such:

- `data.yaml`: provider, asset universe, date range, frequency, price field, cache mode,
  missing-data policy and validation thresholds.
- `environment.yaml`: initial capital, transaction costs, slippage, rebalancing, weight constraints.
- `experiment.yaml`: experiment name, random seed, train/validation/test boundaries, walk-forward settings.

The asset universe (a small set of liquid US ETFs, D-034), the date range, the cost estimates (10 bps +
5 bps slippage), the weight limits and the train/validation/test dates are **provisional
placeholders chosen for development**. They have not been validated or approved by the team; their
status is tracked in [`docs/decision_log.md`](docs/decision_log.md).
Load configs in code with:

```python
from adaptive_portfolio.config import load_project_config

config = load_project_config("configs")
```

Validation rejects unknown keys, wrong types, out-of-range values, overlapping or out-of-order
splits, and infeasible weight constraints.

## Project status and milestones

| # | Milestone | Scope | Status |
| --- | --- | --- | --- |
| 0 | Repository scaffold, configuration, CI | Infrastructure | ✅ Complete: committed as `412d620`; GitHub Actions CI passed on that commit |
| 1 | Financial metrics | Required | ✅ Complete: 7 metrics implemented and tested locally; conventions accepted 2026-10-13; not yet committed or pushed |
| 2 | Data pipeline | Required | ✅ Implemented and tested locally (offline fixtures + one live yfinance retrieval); decisions Proposed; not yet committed |
| 3 | Regime detection | Required (market-condition labels); statistical models optional | Planned |
| 4 | Portfolio environment | Required | Planned |
| 5 | Baseline strategies | Required | Planned |
| 6 | RL agents | Required (PPO candidate); other algorithms optional | Planned |
| 7 | Realistic costs and constraints | Required (transaction costs); extras optional | Planned |
| 8 | Robust evaluation | Required (out-of-sample); walk-forward / stress "where feasible" | Planned |
| 9 | Explainability | Required (explored) | Planned |
| 10 | Dashboard | Optional | Planned |
| 11 | Final research report | Required | Planned |

Details: [`docs/roadmap.md`](docs/roadmap.md).

## Team

Parv Patel and Mandar Patil.

## AI tools disclosure

AI assistants are used in this project: ChatGPT (OpenAI) for language refinement and LaTeX
preparation of the abstract, and Claude Code (Anthropic) to help generate and audit this repository
scaffold and its documentation. AI-assisted work is recorded in
[`docs/project_journal.md`](docs/project_journal.md).
The project design, implementation, experiments and interpretation of results are carried out,
reviewed and verified by the student team.

## License

[MIT](LICENSE).
