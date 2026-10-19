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

### EXP-003: M5.3 PPO throughput smoke test (training split only; execution check, not a result)

- **Date:** 2026-10-19. Run A 2026-10-19T10:39:58Z–10:40:11Z; Run B 10:40:48Z–10:41:01Z.
- **Author(s):** run by Claude Code at the request of a team member. The message approving
  both runs does not name its author; it was recorded under R-S (D-061), and the other
  teammate's confirmation was not sought.
- **Milestone:** M5.3 preparation (roadmap 4/6). It checks the throughput assumption behind the
  D-066 budget **before** any tuning.
- **Git commit:** code at `c1c1925` plus **uncommitted** M5.1–M5.3 working-tree changes. Record
  the commit hash here once the team commits them.
- **Config files (SHA-256 prefixes at run time):**
  - `agent.yaml` `fb5cac2b0491bcb8`;
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb`.
- **Random seed:** 42, for both runs.
- **Data:**
  - processed dataset `8e00568ee2aa4de7` and feature set `a79347e37e653703`, loaded with
    `train_only=True`;
  - 2,517 rows, 2007-01-04 to 2016-12-30;
  - training-line SHA-256 values are recorded in each run's `run_config.json`.
- **Periods used:** **train only.** The episode runs from decision 2007-07-05 to 2016-12-30.
  Validation and test values were not used, and none was loaded or parsed.

**Question.** Does the PPO pipeline run end to end, and what is its throughput (environment
steps per second) on one CPU thread? The answer is used to judge whether the D-066 budget is
feasible: 100,000 steps × 8 configurations × 5 seeds = 4.0 million steps.

**Method.**
- Stable-Baselines3 2.9.0 PPO, torch 2.14.1+cpu, Gymnasium 1.4.0, Python 3.13.7, Windows 11.
  One torch thread; 16 logical CPUs present; one run at a time.
- Settings: `run_kind: smoke`, 4,096 timesteps each, other settings as in `agent.yaml` (D-074
  pinned defaults).
- Weekly decisions, lag 1, 15 bps, actions in `[−1, 1]` scaled ×5 (D-072).
- Each run had a 10-minute hard limit (`timeout 600`). The outputs were then checked
  independently: 28 checks per run.

**Results (execution diagnostics only)**

| Run | Configuration | `n_steps` | Run id | Status | Timesteps | Training wall time | Env steps/s | Episodes | Process time incl. start-up |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0 (lr 3e-4, ent 0) | 512 | `d06b6c2971f6ff66` | completed | 4,096 | 12.802 s | 319.9 | 8 | ≈ 18 s |
| B | 2 (lr 3e-4, ent 0) | 1024 | `4ddbffd78cddcb65` | completed | 4,096 | 12.649 s | 323.8 | 8 | ≈ 17 s |

- **Both runs passed all 28 checks:**
  - exactly the five output files, no staging folder left, the folder name equal to the
    identity hash;
  - metadata containing the identical identity, file hashes reproduced, status `completed`,
    4,096 timesteps;
  - data ending 2016-12-30, with the training-line hashes reproduced;
  - a train-only scaler (2,389 rows) matching the run config;
  - a checkpoint that reloads with 4,096 timesteps, the matching hyperparameters, finite
    weights and the `[−1, 1]` action space;
  - every logged training-episode reward finite, and every completed episode 496 steps long.
- Each run completed 8 training episodes (3,968 steps); the remaining 128 steps were part of an
  unfinished ninth episode. `n_steps` 512 versus 1024 made no material speed difference: Run B
  was 1.2 % faster than Run A.
- Training-episode rewards were checked only for being finite. They are **not** reported or
  interpreted: these are 4,096-step runs, on training data, never evaluated.

**Approximate estimate for the full D-066 budget** (an extrapolation, not a measurement)
- At the mean measured 321.9 steps/s:
  - 4.0 million steps take about 12,400 s, i.e. **about 3.5 hours** of training when run
    sequentially on one thread;
  - plus about 5 s of start-up per run, about 3 minutes in total;
  - one 100,000-step run takes about 5.2 minutes.
- **Caveats:**
  - two short runs only;
  - sustained speed over 100,000 steps can differ (machine load, thermal limits, memory);
  - 16 CPUs could run several single-thread runs in parallel, which is not measured and
    needs approval.
- This lies within the design memo's assumed range (0.6–4 h, item 9). **No budget change is
  proposed.**

*Note (2026-10-19, after the pre-grid hardening): these two run configs predate D-075. They
contain no Git commit or working-tree hash; their code state is the one stated above. Their
folders are preserved unchanged (SHA-256 of all files checked).*

**Interpretation.** The pipeline runs end to end on the training split, and its outputs are
complete and reproducible. Throughput is at the low end of the memo's assumption, but the
D-066 budget stays practical. Nothing here says anything about portfolio performance.

**Next steps.** Any full run, the 40-run grid, tuning or validation evaluation each need separate
approval. Full runs would need a time limit larger than the smoke test's 10 minutes; at about
5.2 minutes per run, 15 minutes per run is a reasonable limit.

---

### EXP-002: Primary-convention conventional baselines, train and validation (Gate 1)

- **Date:** 2026-10-19 (local time; run at 2026-10-18T22:11Z)
- **Author(s):** run by Claude Code at the request of Parv Patel and Mandar Patil, after both
  confirmed Gate 1 on 2026-10-19. That approval evidence is self-declared in a shared-device
  session; see `approval_checklist.md` §0.1.
- **Milestone:** roadmap 4–5 (primary baseline record before any RL work)
- **Approval:** the run used only decisions recorded as Accepted on 2026-10-19:
  - D-007, D-009, D-010, D-013, D-015, D-023, D-031 (cost basis, no cap);
  - D-035–D-039, D-048–D-060.

  D-006, D-008, D-034, D-042 and D-044 are **acknowledged as provisional**, not validated.
- **Git commit:** code at `8e52693` plus **uncommitted** working-tree changes. Those were
  approval-neutral output wording, a test update, `periods_per_year: 252` and documentation;
  none changes computed values. Record the commit hash here once the team commits them.
  - *Correction (2026-10-19, pre-grid hardening): those changes were committed locally as
    `04dc44a` (`feat: record Gate 1 approvals, run EXP-002 baselines and prepare Gate 2
    packet`), which is not yet pushed. The code state of EXP-002 is therefore `04dc44a`.*
- **Config files (SHA-256 prefixes at run time):**
  - `backtest.yaml` `80fd3a57cfdae3ce`;
  - `environment.yaml` `4a89283353bc1267`;
  - `experiment.yaml` `b36a86fe6278cc05`;
  - `data.yaml` `65bc85babfe7e7a6`;
  - `features.yaml` `fa1030f9202301fb` (used only for the window check).
- **Seeds:** none; the run is deterministic.
- **Data:**
  - processed dataset `8e00568ee2aa4de7`, from raw snapshot `e27437b97742fa43` (yfinance 1.7.0,
    retrieved 2026-10-15T10:21:14Z);
  - SPY, EFA, EEM, IEF, TLT, LQD, GLD; daily adjusted close. Read offline; no download.
- **Periods used:**
  - **train:** decisions from 2007-07-05 (126-session common window), returns earned
    2007-07-06 to 2016-12-30 (2,390 return periods);
  - **validation:** decisions from 2017-01-03, returns earned 2017-01-04 to 2019-12-31 (752);
  - **test: not used.** No `--include-test`; test-period return values were never parsed
    (D-060).
- **Command:**
  `python scripts/market_data.py --config-dir configs backtest --dataset-dir data/processed/8e00568ee2aa4de7`
- **Output:** `data/processed/backtests/c6d8c473258e3194/` (git-ignored). SHA-256 prefixes:
  - `ledger.csv` `ae141edb87a3f524`;
  - `executions.csv` `f604b0340b72d652`;
  - `metrics.json` `d6924a0511e6eee6`;
  - `metrics.csv` `b57f69a701ba27e2`;
  - `backtest_report.md` `951c56f0ce1e7653`;
  - `metadata.json` `30aba7b2885a198b`.
- **Software:** Python 3.13.7, numpy 2.5.4, pandas 3.0.6, adaptive_portfolio 0.1.0 (Windows).

**Question**
What do the three approved conventional baselines achieve on train and validation under the
primary convention (lag 1, 15 bps, 126-session window, N = 252)? This is the reference record
for any later comparison. No hypothesis about which strategy is better is tested, and nothing
was tuned.

**Method**
- **Strategies:** `equal_weight_monthly`, `buy_and_hold_equal_weight`,
  `inverse_volatility_monthly` (63-session lookback, cap 0.40).
- **Rules:** long-only; Σw ≤ 1 with cash at rf = 0; funding trade charged.
- **Protocol:** each split simulated independently from 100,000 in cash.
- **Metrics:**
  - per-session metrics, plus annualised metrics with N = 252, using √252 scaling and CAGR over
    the return periods;
  - Sharpe uses rf = 0 and excludes the funding row;
  - cumulative return and drawdown include the funding cost;
  - turnover is traded notional; annualised turnover counts recurring trades only.

**Results** (net of costs unless stated; descriptive; single historical path; no significance
testing)

| Split | Strategy | Rebal. | Gross cum. | Net cum. | Cost drag | Net max DD | Ann. return | Ann. vol | Ann. Sharpe (rf 0) | Recurring notional | Ann. recurring turnover | Total cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | equal_weight_monthly | 114 | 62.15 % | 61.06 % | 1.09 pp | −28.51 % | 5.15 % | 10.93 % | 0.516 | 3.503 | 0.369 | 0.675 % |
| train | buy_and_hold_equal_weight | 1 | 52.72 % | 52.49 % | 0.23 pp | −24.44 % | 4.55 % | 9.15 % | 0.534 | 0.000 | 0.000 | 0.150 % |
| train | inverse_volatility_monthly | 114 | 73.88 % | 71.55 % | 2.33 pp | −18.64 % | 5.85 % | 7.06 % | 0.843 | 7.979 | 0.841 | 1.347 % |
| validation | equal_weight_monthly | 36 | 29.13 % | 28.81 % | 0.32 pp | −10.42 % | 8.84 % | 5.93 % | 1.470 | 0.662 | 0.222 | 0.249 % |
| validation | buy_and_hold_equal_weight | 1 | 28.15 % | 27.96 % | 0.19 pp | −11.49 % | 8.60 % | 6.28 % | 1.355 | 0.000 | 0.000 | 0.150 % |
| validation | inverse_volatility_monthly | 36 | 27.01 % | 26.37 % | 0.63 pp | −7.58 % | 8.15 % | 4.56 % | 1.754 | 2.334 | 0.782 | 0.500 % |

- **Notes on the table:**
  - "Rebal." counts executions, including the funding trade.
  - Total traded notional = 1.0 (funding) + recurring.
  - Total cost is the sum of cost fractions, funding included.
  - No decision was dropped at split ends.
- **Per-session values** (rf 0), net volatility / net Sharpe:
  - train: 0.689 % / 0.0325, 0.576 % / 0.0336, 0.445 % / 0.0531;
  - validation: 0.373 % / 0.0926, 0.396 % / 0.0853, 0.287 % / 0.1105;

  in the table's strategy order.

**Verification (all passed)**
- outputs contain train and validation only, with every ledger date before 2020;
- all values are finite;
- the three strategies have identical dates in each split;
- each of the 302 executions happens exactly one session after its decision;
- every row's gross return was recomputed as the previous row's weights × that row's returns;
- cost = 15 bps × traded notional, net = g − c(1 + g), and the value path compounds from
  100,000;
- funding: notional 1.0 (within 1e-12), gross 0, cost 0.0015 on the first row;
- recurring turnover is 0 for buy-and-hold;
- cost drag > 0;
- targets are within [0, 0.40] with Σ ≤ 1;
- annualised Sharpe was recomputed as √252 × mean / std;
- metadata ids match;
- the output status text claims no approval state;
- **an identical re-run reproduced all six files byte for byte.**

**Interpretation (descriptive only)**
- **Inverse volatility:**
  - in both splits it had the smallest maximum drawdown and the lowest volatility;
  - it also traded about 2–3.5× the recurring notional of monthly equal weight and had the
    largest cost drag;
  - its annualised Sharpe (rf 0) was the highest of the three in both splits.
- **Cumulative return** ranks differ between splits: inverse volatility first in train, last in
  validation.
- **These are single historical paths** under placeholder costs and rf = 0, with no confidence
  intervals. **They do not show that any strategy is better,** and nothing here concerns PPO,
  which has not been implemented.
- **Compared with EXP-001** (lag 0, 62-row window), the figures differ modestly; the two runs
  use different conventions and windows and are not a controlled comparison.

**Limitations**
- Provisional data values (universe, date range, provider, validation thresholds, feature
  windows).
- Placeholder cost rates; rf = 0 for cash and Sharpe.
- Close-to-close execution, even at lag 1.
- √N annualisation assumes independent returns; untuned baselines; survivorship and selection
  bias in an ETF universe chosen with hindsight.
- Approval evidence self-declared, not technically verified.

**Next steps**
- The team commits the working-tree changes and records the commit hash above.
- Gate 2 (PPO design) decisions and dependency authorisation; then PPO training on train and
  validation only.
- The test split stays sealed until Gate 3.

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

**Correction (2026-10-18, milestone 4.2), appended; the entries above are unchanged:**
- **Commit hashes:** the commit cited above as `a7134b7` was rewritten on 2026-10-18 with
  changed author and committer metadata and force-pushed as `66f9ed7`. The file tree is
  identical, so the code and configs used by EXP-001 are unchanged. The original commit remains
  on the local branch `backup/main-before-author-rewrite`. CI passed on `a7134b7` (run #3) and
  on the current head `880d82c` (run #6). No separate run exists for `66f9ed7`.
- **Evaluation window:** EXP-001 used the milestone-4 common start (first training decision
  2007-04-04, 62 warm-up rows). Under the proposed D-058 the training window would start on
  2007-07-05. EXP-001 is not a record of the proposed primary protocol, which uses lag 1 and the
  126-session window.
