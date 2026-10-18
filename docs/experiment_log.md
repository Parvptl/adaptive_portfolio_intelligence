# Experiment Log

Every experiment whose results are discussed, plotted or reported must have an entry here. Record
negative and inconclusive results as well as positive ones. Do not edit past entries except to add
corrections, marked as such.

## How to add an entry

1. Copy the template below to the top of the **Entries** section.
2. Use the next ID (`EXP-001`, `EXP-002`, …).
3. Commit the config files used, and fill in the commit hash.
4. State which period the reported numbers come from. Test-period results are reported only for
   final, pre-registered evaluations.

---

## Template

```markdown
### EXP-XXX: <short title>

- **Date:** YYYY-MM-DD
- **Author(s):**
- **Milestone:** (see docs/roadmap.md)
- **Git commit:** `<hash>` (clean working tree? yes/no)
- **Config files:** `configs/...` (or an inline diff from defaults)
- **Random seed(s):**
- **Data:** provider, universe, date range, frequency, data snapshot/version
- **Periods used:** train YYYY-MM-DD → YYYY-MM-DD; validation …; test … (used? yes/no)

**Hypothesis / question**
What is being tested, and what result would count as support or refutation?

**Method**
Strategy / agent, key hyperparameters, cost assumptions (bps), constraints, rebalancing frequency.

**Assumptions and known limitations**
Anything provisional (costs, universe, survivorship, timing convention).

**Results** (state period; include baselines under identical conditions)

| Strategy | Ann. return | Ann. vol | Sharpe | Sortino | Max DD | Turnover | Cost drag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

Variation across seeds:
Figures: `reports/figures/...`

**Interpretation**
What the evidence does and does not support. No claims of profitability without evidence.

**Next steps**
```

---

## Entries

### EXP-001: Conventional baselines on the training and validation splits (milestone 4)

- **Date:** 2026-10-15
- **Author(s):** project team (run by Claude Code at the team's request; to be checked by the team)
- **Milestone:** roadmap 4–5 (team milestone 4: portfolio simulation and conventional baselines)
- **Git commit:** none. Uncommitted working tree on top of `adffff5`; record the commit hash when
  the team commits.
- **Config files:** `configs/backtest.yaml`, `configs/environment.yaml`, `configs/data.yaml`,
  `configs/experiment.yaml` (defaults, unchanged)
- **Random seed(s):** not applicable (deterministic; no randomness)
- **Data:** yfinance live snapshot, raw id `e27437b97742fa43`, processed id `8e00568ee2aa4de7`.
  Universe SPY, EFA, EEM, IEF, TLT, LQD, GLD (provisional, D-034); daily adjusted close,
  2007–2024.
- **Backtest id:** `ac2d6b163d4f5e4b` (pipeline version 1); outputs in
  `data/processed/backtests/ac2d6b163d4f5e4b/` (git-ignored); reruns byte-identical.
- **Periods used:** train 2007-04-04 → 2016-12-30 (common start after 62 warm-up rows);
  validation 2017-01-03 → 2019-12-31. **Test: computed by the command but not reported here**
  (see D-051 open question).

**Question**
Does the simulator produce consistent, reproducible baseline results under the proposed
conventions? This is a pipeline check and a reference point. It is not a hypothesis about which
strategy is better, and no parameter was tuned.

**Method**
The three baselines of D-053:
- timing D-048 with lag 0;
- costs D-049: 10 + 5 bps on traded notional, including initial funding;
- constraints D-050: long-only, max weight 0.40, cash at rf 0;
- protocol D-051: independent per split, starting from cash.

**Assumptions and known limitations**
- All conventions are Proposed. Costs, cap and universe are provisional.
- Close-to-close execution at lag 0 is optimistic.
- Metrics are per session because D-023 is open: no annualised return, volatility or Sharpe is
  reported.
- Sortino is not implemented.

**Results** (net of costs unless stated; per-session values not annualised; descriptive only)

| Split | Strategy | Rebalances | Gross cum. | Net cum. | Cost drag | Net max DD | Net vol / session | Net Sharpe / session (rf 0) | Traded notional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | equal_weight_monthly | 117 | 66.93 % | 65.78 % | 1.15 pp | −28.56 % | 0.68 % | 0.034 | 4.60 |
| train | buy_and_hold_equal_weight | 1 | 54.39 % | 54.16 % | 0.23 pp | −25.94 % | 0.60 % | 0.032 | 1.00 |
| train | inverse_volatility_monthly | 117 | 73.73 % | 71.38 % | 2.36 pp | −18.15 % | 0.44 % | 0.052 | 9.11 |
| validation | equal_weight_monthly | 36 | 29.81 % | 29.48 % | 0.33 pp | −10.29 % | 0.37 % | 0.095 | 1.69 |
| validation | buy_and_hold_equal_weight | 1 | 28.85 % | 28.65 % | 0.19 pp | −11.51 % | 0.40 % | 0.087 | 1.00 |
| validation | inverse_volatility_monthly | 36 | 27.34 % | 26.71 % | 0.63 pp | −7.54 % | 0.29 % | 0.112 | 3.29 |

"Rebalances" counts executions, including the initial funding. No decisions were dropped at
split ends.

**Independent checks:**
- buy-and-hold matches its closed form;
- equal-weight monthly matches a separately written loop;
- inverse-volatility weights match a hand computation.
All agree to about 1e-8. Figures: none produced.

**Interpretation**
- The pipeline runs offline, deterministically, and agrees with independent recomputation.
- Differences between strategies are single-path historical outcomes under provisional costs
  and timing. They have no significance test, no annualisation and no test-period evidence.
  **They do not show that any strategy is better.**
- Descriptively: inverse volatility traded about twice the notional of equal weight and had
  the largest cost drag, and it had the smallest drawdowns in both splits.
- The ordering of cumulative returns differs between train and validation.

**Next steps**
- Team decisions on D-048 to D-054 and D-023.
- Decide whether test-split evaluation becomes opt-in.
- Lag-1 and cost-sensitivity runs if approved.

**Correction (2026-10-18), added after the milestone-4 audit; the entry above is unchanged:**
- **Git commit:** the code and configs used are those committed as `a7134b7` ("feat: add
  portfolio simulator and conventional baselines"), pushed to `origin/main`. GitHub Actions CI
  passed on that commit.
- The read-only audit (2026-10-18) re-ran the backtest from `a7134b7` in an isolated copy. All
  outputs were byte-identical except the `dataset_dir` path in `metadata.json`.
- **Timing:** this run used `execution_lag_sessions: 0`. Under D-055 (Proposed, 2026-10-18) lag 1
  is the proposed primary convention, and lag 0 an idealised sensitivity case. The figures above
  are therefore the **lag-0 sensitivity case**. No lag-1 run has been made or reported yet.
- **Test split:** this run (pipeline version 1) also computed test-split results, which were
  printed to the console during the milestone-4 session. They exist in a git-ignored local folder
  (`data/processed/backtests/ac2d6b163d4f5e4b/`). They are not recorded here, were not used for any
  choice, and must not be reported. From pipeline version 2 (D-056), test evaluation is opt-in.
- **Weight cap:** inverse-volatility holdings exceeded the 0.40 cap between rebalances (up to
  about 0.4117 on 19 training-split ledger rows; test-split rows are not reported). The cap
  applies to target weights at execution (D-057, Proposed).
