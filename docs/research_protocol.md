# Research Protocol — DRAFT / NOT APPROVED

> **Status update (2026-10-19):**
> - The **baseline (Gate 1) parts** of this protocol were **accepted on 2026-10-19** by Parv
>   Patel and Mandar Patil, as recorded in `decision_log.md`. Confirmations were self-declared
>   in a shared-device session and arrived in one message; see `approval_checklist.md` §0.1.
> - The **PPO parts (Gate 2: §8–§13) remain DRAFT / NOT APPROVED.**
> - D-006, D-008, D-034, D-042 and D-044 are acknowledged as provisional, not validated.
> - The status lines below are updated where Gate 1 settled them.
>
> **Original status: DRAFT. Nothing in this document is approved.**
> - It collects the recommendations of the milestone-4.2 read-only audit (2026-10-18), so the
>   team can decide them before any reinforcement-learning (RL) work starts.
> - Only the student team (Parv Patel, Mandar Patil) can approve a decision. Approval is recorded
>   in [`decision_log.md`](decision_log.md) as **Accepted**, with who approved it and when.
> - Until then, every recommendation here is a proposal, and every value marked provisional
>   stays provisional.
> - The submitted abstract (`Abstract.pdf`) is the source of truth for scope. No improvement of
>   any strategy over another is assumed.

Each section separates three kinds of statement:
- **Fact:** what the code and configs do now (verified on 2026-10-18 at commit `817f8b8`,
  which contains the milestone-4.2 changes).
- **Recommendation:** a proposal, not approved.
- **Open:** a question that needs a team decision.

## 1. Scope from the abstract (fact)

- Portfolio management as sequential decision-making, with feedback based on performance and
  risk.
- Investigate rising, falling and high-volatility periods.
- PPO is a **candidate** algorithm, alongside suitable baselines (D-014).
- Compare against conventional allocation benchmarks using cumulative return, Sharpe ratio,
  maximum drawdown and portfolio turnover.
- Out-of-sample testing. Walk-forward validation and stress testing **where feasible**.
  Transaction costs are included.
- Explainability is **explored**. The study also assesses risk control, adaptability and
  interpretability.

## 2. Timing (D-013, D-043, D-048, D-055)

- **Fact:**
  - decide at row `d` using data dated `<= d`; execute at the close of `d + L`; first earned
    return is row `d + L + 1`;
  - `L` is counted in observed sessions, and `execution_lag_sessions` is required (configs: 1);
  - one implementation lives in `adaptive_portfolio/timing.py`, shared by the simulator, the
    backtest and `features.next_period_targets`.
- **Recommendation:**
  - accept lag 1 as the primary convention and lag 0 as an idealised sensitivity case;
  - any RL reward must pair decision `d` with the return the simulator credits, i.e. use
    `next_period_targets(..., execution_lag_sessions=L)` or the simulator itself.

## 3. Costs and turnover (D-007, D-031, D-049)

- **Fact:**
  - cost = (10 + 5) bps × traded notional of non-cash assets (cash leg excluded), charged on the
    value before the cost and deducted pro rata;
  - the initial funding trade is charged;
  - `max_turnover` must be null, and the backtest refuses a value.
- **Fact (milestone 4.2):** metrics report `funding_traded_notional` (the one-off funding trade)
  and `recurring_traded_notional` separately. The opt-in annualised traded notional uses
  recurring trades only (proposed D-059).
- **Recommendation:**
  - accept traded notional as the cost basis;
  - keep **no turnover cap** in the primary protocol. If a cap is ever introduced, it should
    constrain traded notional per rebalance;
  - keep 15 bps as the base rate.
- **Accepted 2026-10-19:** D-007 (15 bps, placeholder rates) and D-031's cost basis with no cap.
- **Open:**
  - D-031: the turnover-cap measure;
  - cost sensitivity at 0 and 30 bps, an optional extension that needs approval.

## 4. Constraints and cash (D-015, D-050, D-057)

- **Fact:**
  - long-only, Σw ≤ 1, fractional weights;
  - `max_weight` 0.40 is checked on **target** weights at execution; holdings may drift above it
    between rebalances;
  - residual cash earns `risk_free_rate` = 0.
- **Recommendation:** keep rf = 0 for both the cash return and the Sharpe ratio, labelled "excess
  over zero". Document the limitation: T-bill yields were about 4–5 % in 2022–2024, so cash is
  understated in part of the test period. The rule is the same for every strategy.
- **Alternative (new scope, needs approval):** a daily T-bill series, with its own timing and
  leakage rules.
- **Accepted 2026-10-19:** D-015 (cap 0.40 on targets, rf = 0).

## 5. Annualisation and metrics (D-023, D-052)

- **Fact:**
  - metrics are per session by default (`periods_per_year: null`);
  - annualised values appear only when `periods_per_year` is set, and are labelled provisional;
  - volatility and Sharpe exclude the funding row; cumulative return and drawdown include it.
- **Evidence (not a decision):** training years 2008–2016 average 251.9 observed sessions per
  year (range 250–253).
- **Recommendation:**
  - N = 252 for daily data;
  - report the annualised Sharpe (√252 × per-session mean/std) alongside the per-session value;
  - CAGR over the return periods.

  The limitation of √N scaling (it assumes independent returns) must be stated.
- **Accepted 2026-10-19:** D-023, N = 252 (`periods_per_year: 252`).

## 6. Splits, evaluation window and test isolation (D-009, D-018, D-019, D-051, D-056, D-058)

- **Fact:**
  - train 2007–2016 (2,517 rows), validation 2017–2019 (754), test 2020–2024 (1,258);
  - each split is simulated independently from cash;
  - decisions whose earned return falls in the next split are dropped;
  - test is evaluated only with `--include-test`.
- **Fact (milestone 4.2, proposed D-058):** `backtest.common_start_history_sessions: 126` makes
  every strategy's first training decision wait for the longest feature window (126 sessions).
  The CLI refuses a value below the longest window in `features.yaml`. Validation and test
  windows are unchanged.
- **Fact:** walk-forward evaluation is **not implemented**. The `walk_forward` settings in
  `experiment.yaml` are not read by any code.
- **Recommendation:**
  - the fixed split is the primary evaluation;
  - walk-forward as a robustness check, with expanding folds **inside 2007–2019 only** (e.g.
    validate on each of 2015–2019) and no per-fold tuning;
  - no embargo is needed for one-step rewards; revisit if a multi-step reward is adopted.
- **Accepted 2026-10-19:** D-009, D-051, D-056, D-058.
- **Open:** D-018 (walk-forward scheme), D-019 (embargo).

## 7. Baselines (D-010, D-053)

- **Fact:** equal weight monthly, equal-weight buy-and-hold, inverse volatility (63) monthly.
  None has fitted parameters, and none uses regime information.
- **Recommendation:** keep this set. Do not add strategies without a stated reason. Baselines
  stay untuned, and that asymmetry with a tuned agent is reported.
- **Accepted 2026-10-19:** D-053; EXP-002 is the primary baseline record.
- **Missing record:** EXP-001 used lag 0. A primary-convention baseline run (lag 1, common
  window 126) on train and validation has not been made yet.

## 8. Agent design (needed before PPO; new decisions, none recorded yet)

A more detailed design, also **PROPOSED — NOT APPROVED**, is in
[`ppo_design_proposal.md`](ppo_design_proposal.md).

| Item | Options | Recommendation |
| --- | --- | --- |
| Algorithm and library (D-014) | Stable-Baselines3 + PyTorch; other libraries | Choose before implementation; add version-bounded dependencies then |
| Observation (D-012) | (a) causal features only; (b) features + one-hot regime label; (c) both, as an ablation [O] | (b) primary, because the title says "regime-aware"; plus the current drifted weights |
| Feature scaling | none; train-only fitted scaler | Fit on train only, then freeze (like the regime thresholds) |
| Action mapping | softmax over assets + cash, then a projection | A deterministic projection onto 0 ≤ w ≤ 0.40, Σw ≤ 1, with capped excess going **to cash** and logged |
| Decision frequency | daily; weekly; monthly (114 training decisions from the 126-session common start, too few; 117 under the earlier milestone-4 start) | Daily or weekly, fixed before tuning; costs and turnover always reported |
| Reward | (a) log net growth per step; (b) differential Sharpe ratio (Moody & Saffell, cited in the abstract); (c) (a) minus a risk penalty | (a) primary, (b) the only alternative compared, on validation. **Not chosen; must not be chosen by looking at test results.** |
| Accounting | Separate environment code; the existing simulator | Reuse `simulate` and `timing.py` exactly, so that agent and baselines share costs, timing and constraints |

## 9. Tuning, seeds and selection (D-016)

- **Recommendation:**
  - a fixed hyperparameter budget and search space, declared before tuning;
  - at least 5 training seeds (e.g. 42–46);
  - select by the median over seeds of validation net Sharpe. Annualising does not change the
    ranking while rf = 0 (see `ppo_design_proposal.md` §13, items 7–8, including the
    tie-break);
  - early stopping, if used, on validation only;
  - report every seed: mean, standard deviation, median and range. Never report only the best
    seed.
- **Open:** D-016.

## 10. Primary endpoint, statistics and stress tests

- **Recommendation (pre-registration):**
  - **Primary:** test-split net Sharpe at lag 1 and 15 bps of the selected configuration,
    as the **median over the same 5 seeds** (annualised with N if D-023 is approved,
    otherwise per session). Every seed is reported. Inference uses a joint block bootstrap
    over time (`ppo_design_proposal.md` §13, item 8). *(Seed aggregation added
    2026-10-18 for consistency with the PPO proposal; still a proposal.)*
  - **Secondary:** cumulative return, maximum drawdown, recurring turnover, cost drag, and
    regime-conditional metrics using the frozen thresholds (D-045).
  - **Statistics:** block-bootstrap confidence intervals for Sharpe differences against each
    baseline, plus the across-seed distribution, with a multiple-comparison caveat.
  - **Stress windows** inside the test period (e.g. the 2020 drawdown and the 2022 rate shock)
    must be named **before** the test run.

## 11. Explainability

- **Recommendation:**
  - permutation sensitivity of actions to observation features;
  - regime-conditional allocation and risk summaries;
  - SHAP is optional and needs approval plus a new dependency.

## 12. Reproducibility and outputs (D-017)

- **Fact:**
  - backtest and feature outputs live under `data/processed/` (git-ignored) with content-hashed
    ids, and reruns are byte-identical;
  - `experiment.yaml` `output_dir: reports` is not used by any code, and only `reports/figures/`
    is git-ignored;
  - an old pipeline-version-1 output folder containing test-split results
    (`data/processed/backtests/ac2d6b163d4f5e4b/`) is kept locally and must not be reported.
- **Recommendation:**
  - a git-ignored results root for RL experiments;
  - commit only configs and experiment-log entries;
  - record seeds, configs, data ids and software versions for every run.
- **Open:** D-017.

## 13. Test-run rule

The test split is evaluated **once**, after the team has:
1. approved this protocol (as decision-log entries);
2. frozen all configs; record their hashes in the experiment log;
3. recorded the selected agent configuration and seeds from validation only.

No result from that run may be used to change anything afterwards. Any later change must be
reported as a new, explicitly labelled exploratory analysis.

## 14. Approvals required before PPO

D-007, D-009, D-012, D-014 (library), D-015, D-016, D-017, D-018, D-019, D-023, D-031,
D-048–D-059, and the agent-design items in §8–§10.
