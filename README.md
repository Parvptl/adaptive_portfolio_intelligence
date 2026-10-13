# Adaptive Portfolio Intelligence

**Explainable, regime-aware reinforcement learning for dynamic portfolio allocation and risk management.**

> **Disclaimer.** This is an academic research and decision-support project. It is **not financial
> advice**, and nothing in this repository should be used to make real investment decisions. No
> improvement over traditional strategies is assumed in advance; any finding must be supported by
> the experimental evidence recorded in [`docs/experiment_log.md`](docs/experiment_log.md).

**Status:** repository scaffold (v0.1.0). Only configuration loading and validation are
implemented. See [Project status](#project-status-and-milestones).

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
├── scripts/                   # Reproducible command-line workflows
├── src/adaptive_portfolio/
│   ├── config.py              # Config loading and validation (implemented)
│   ├── data/                  # Planned: data acquisition and cleaning
│   ├── features/              # Planned: causal feature engineering
│   ├── regimes/               # Planned: market-regime detection
│   ├── environment/           # Planned: portfolio environment
│   ├── agents/                # Planned: RL agents (PPO, …)
│   ├── baselines/             # Planned: traditional strategies
│   ├── evaluation/            # Planned: backtesting and metrics
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
```

Common tasks (with GNU make, or run the commands shown in the [`Makefile`](Makefile) directly):

| Task | make | Direct command |
| --- | --- | --- |
| Run tests | `make test` | `python -m pytest` |
| Lint | `make lint` | `python -m ruff check .` |
| Format | `make format` | `python -m ruff format .` |
| All CI checks | `make check` | lint + `ruff format --check .` + tests |
| Validate configs | — | `python scripts/validate_config.py` |

No market data or credentials are needed to install the package or run the tests. If a data
provider requiring credentials is adopted later, copy `.env.example` to `.env` and fill it in
locally; `.env` is git-ignored.

## Configuration

All provisional assumptions live in [`configs/`](configs/) and are labelled as such:

- `data.yaml`: provider, asset universe, date range, frequency.
- `environment.yaml`: initial capital, transaction costs, slippage, rebalancing, weight constraints.
- `experiment.yaml`: experiment name, random seed, train/validation/test boundaries, walk-forward settings.

The asset universe (a small set of liquid US ETFs), the date range, the cost estimates (10 bps +
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
| 0 | Repository scaffold, configuration, CI | Infrastructure | ✅ Scaffold complete (not yet committed; CI not yet run) |
| 1 | Financial metrics | Required | ⏳ Next |
| 2 | Data pipeline | Required | Planned |
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
