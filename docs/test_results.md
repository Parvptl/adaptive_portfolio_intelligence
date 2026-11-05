# Out-of-sample test evaluation, 2020–2024 (EXP-030; Gate 3)

> **Status (2026-11-05):** executed **once** under the frozen pre-registration, then verified.
> - **Pre-registration:** `configs/preregistration.yaml`, frozen at commit `67618cf`; content
>   SHA-256 `3a5e5e82ad6a45c0c8226b8b1e27a187138eecd45c455c81d61f7efd5ab6ae9f`; protocol hash
>   `f45b8b35e16d2d3c` (unchanged since D-083).
> - **Governance:** G3-5 and Gate 3c reviewed by Parv Patel (a person other than the implementer;
>   not independent of the team; no separate review document); G3-6 accepted with a delegated
>   record; policy §7 conditions checked in the journal before execution.
> - **Verification:** every pre-registered quantity recomputes **except one secondary
>   descriptive field**, `share_executions_at_cap` for the five PPO policies, which the evaluator
>   overstated (§6). The primary result is unaffected.
> - **This is a simulated historical backtest on one market history. Not live trading, not
>   financial advice.** No result here was used, or may be used, to select, tune or retrain
>   anything.

## 1. What was evaluated

- **Candidate (sole test arm):** configuration 4 (learning rate 1e-4, `n_steps` 512, entropy 0),
  seeds 42–46, the EXP-006 checkpoints (hashes verified at plan and execution).
- **Baselines:** equal weight monthly, equal-weight buy-and-hold and inverse volatility monthly
  (D-053), in the same run.
- **Window:** first decision 2020-01-02, funding execution 2020-01-03, last return 2024-12-31;
  1,256 daily return periods after the funding row. No warm-up rows skipped.
- **Accounting (primary):** lag 1, 15 bps on ETF traded notional including funding, 0.40 ETF
  target cap, cash at 0; deterministic actions; the environment and simulator ledgers agreed
  exactly.
- **Run:** evaluation `57eeefd22d8ae35d`, commit `67618cf` (clean), 8 s wall time;
  `data/processed/test_evaluations/57eeefd22d8ae35d/` (write-once; git-ignored).

## 2. Primary result (pre-registered)

**Endpoint:** the median over seeds 42–46 of the annualised net Sharpe (√252·mean/std, ddof 1,
rf 0, funding row excluded).

| | Value |
| --- | --- |
| Configuration 4, per seed (42 / 43 / 44 / 45 / 46) | 0.235 / 0.020 / −0.068 / −0.234 / −0.329 |
| **Median (endpoint)** | **−0.068** |
| Inverse volatility monthly (primary comparator) | 0.253 |
| **Difference (endpoint − comparator)** | **−0.322** |
| 95% paired moving-block bootstrap interval (L = 21, 10,000 replicates, seed 20261021) | **[−0.818, 0.192]** |

- **Effect size, not a test (G3-8):** no p-value and no pass/fail threshold were pre-registered.
  The interval includes zero, so the data do not establish a difference at this level of
  uncertainty, but the point estimate is negative.
- **Every seed is below the comparator**, and below both other baselines.
- **Descriptive point differences (no interval):** −0.439 against equal weight monthly (0.371)
  and −0.494 against buy-and-hold (0.426).
- **Validation vs test:** configuration 4's validation median was 0.635 (EXP-006, where it was
  selected among 40 policies). The test median is −0.068: the validation figure was optimistic,
  as the report warned.

**Conclusion: on the 2020–2024 test period, the selected PPO policy did not outperform any of
the three simple baselines on net Sharpe; its point estimate is lower than all three.**

## 3. Secondary metrics (primary accounting, 15 bps)

| Strategy | Net Sharpe | Gross Sharpe | Net cum. return | Net CAGR | Volatility | Net max DD | Cost drag | Turnover / yr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PPO seed 42 | 0.235 | 0.564 | 9.5% | 1.8% | 10.0% | −19.1% | 19.6 pp | 21.9 |
| PPO seed 43 | 0.020 | 0.261 | −3.3% | −0.7% | 13.6% | −28.1% | 17.3 pp | 21.9 |
| PPO seed 44 | −0.068 | 0.264 | −6.4% | −1.3% | 10.6% | −22.5% | 18.2 pp | 23.5 |
| PPO seed 45 | −0.234 | 0.014 | −14.6% | −3.1% | 11.0% | −22.8% | 12.4 pp | 18.0 |
| PPO seed 46 | −0.329 | −0.048 | −20.6% | −4.5% | 11.9% | −31.0% | 14.5 pp | 22.3 |
| Equal weight monthly | 0.371 | 0.375 | 18.4% | 3.5% | 10.8% | −24.2% | 0.4 pp | 0.27 |
| Buy-and-hold | 0.426 | 0.426 | 21.7% | 4.0% | 10.7% | −24.0% | 0.2 pp | 0 |
| Inverse volatility monthly | 0.253 | 0.266 | 9.9% | 1.9% | 9.3% | −23.0% | 0.8 pp | 0.81 |

- **Costs:** PPO traded 18–24× the portfolio a year and lost 12–20 pp to costs over five years.
- **Before costs:** the PPO median gross Sharpe (0.261) is close to inverse volatility's (0.266)
  but below equal weight and buy-and-hold.
- **Drawdowns:** three PPO seeds had shallower net drawdowns than the baselines (−19.1% to
  −22.8% vs −23.0% to −24.2%); two were deeper (−28.1%, −31.0%).
- **Allocation:** PPO held 32–47% cash on average, with a concentrated risky sleeve (HHI
  0.51–0.69 vs 0.14–0.17 for the baselines).

## 4. Cost sensitivity (fixed-action accounting; the policy does not adapt)

| Cost | PPO net Sharpe per seed | PPO median | EW monthly | Buy-and-hold | Inverse vol. |
| --- | --- | --- | --- | --- | --- |
| 0 bps | 0.564 / 0.261 / 0.264 / 0.014 / −0.048 | 0.261 | 0.375 | 0.426 | 0.266 |
| 15 bps (primary) | 0.235 / 0.020 / −0.068 / −0.234 / −0.329 | −0.068 | 0.371 | 0.426 | 0.253 |
| 30 bps | −0.094 / −0.222 / −0.399 / −0.481 / −0.610 | −0.399 | 0.367 | 0.426 | 0.241 |

Even with no trading costs, the median PPO policy is below every baseline. The 15 bps replay
reproduced the primary ledgers exactly (fixed-action identity).

## 5. Stress windows (descriptive slices; counts matched the dataset calendar)

| Window (peak close, trough close] | Sessions | PPO net return (42 / 43 / 44 / 45 / 46) | EW monthly | Buy-and-hold | Inverse vol. |
| --- | --- | --- | --- | --- | --- |
| COVID crash (2020-02-19, 2020-03-23] | 23 | −17.3% / −28.1% / −18.7% / −22.0% / −22.0% | −14.0% | −13.0% | −10.6% |
| 2022 bear market (2022-01-03, 2022-10-12] | 195 | −15.7% / −14.1% / −18.8% / −11.1% / −20.8% | −22.2% | −22.3% | −20.9% |

- **COVID crash:** every PPO seed lost more than every baseline, with higher volatility
  (40–67% annualised vs 28–32%).
- **2022 bear market:** every PPO seed lost less than every baseline, with lower volatility
  (7.5–11.2% vs 11.2–12.8%), consistent with its large cash holding (cash earns 0 here and
  does not fall).
- Two windows of one history are not independent tests.

## 6. Regime behaviour (labels at *t* − 1; regimes with ≥ 63 sessions)

Five regimes are sufficient on the test period, including `negative_high` (falling, high
volatility; 167 sessions), which never reached 63 sessions on validation.

- **Cash in `negative_high`:** 0.10–0.38, lower than in `positive_low` (0.32–0.50) in every
  seed. The policy is **not** more defensive in falling, volatile markets.
- **Volatility in `negative_high`:** 0.20–0.30 for PPO vs 0.16–0.19 for the baselines, higher in
  every seed; mean annualised net return −0.10 to −0.31 vs +0.01 / +0.01 / −0.04.
- This repeats the validation finding (EXP-029): the policy's allocation varies with the regime,
  but not in a risk-reducing direction.

## 7. Verification and the one defect found

`python scripts/evaluate_test.py --verify data/processed/test_evaluations/57eeefd22d8ae35d`:
every Sharpe ratio, the endpoint, the cost and net-return identities, the funding row and lag,
the fixed-action identity, the bootstrap replicates (main implementation exactly; the
loop-based reference within 1e-9), the interval, the descriptive differences, allocations, stress
windows and regime summaries recompute. **It reports one failure:** "concentration does not
recompute" for the five PPO policies.

- **Cause:** the evaluator passed the simulator's executions, which include `target_CASH`, to
  `risk.concentration`, so executions with **cash** ≥ 0.40 were counted as "at the ETF cap". The
  cap applies to ETFs only (D-063, D-057); the verifier rebuilds ETF targets only. The baselines
  hold no cash, so they were unaffected. Confirmed for every seed: the saved count equals the
  number of executions with an ETF **or** cash weight ≥ 0.40.
- **Corrected values** (from the saved ledgers, ETF targets only; 261 executions per seed):

  | Seed | Saved (wrong) | Corrected |
  | --- | --- | --- |
  | 42 | 0.943 | 0.908 |
  | 43 | 0.839 | 0.766 |
  | 44 | 0.847 | 0.831 |
  | 45 | 0.927 | 0.858 |
  | 46 | 0.770 | 0.766 |

- **Action:** `risk.concentration` now drops `target_CASH`, with a regression test. The saved
  test output is write-once and was **not** regenerated; the test was **not** re-run. The
  official verification of this output will keep reporting this field.

## 8. Limitations

- One market history and one test period; five seeds of one configuration are not five
  independent samples.
- The bootstrap resamples realised returns with the actions fixed; it is not a significance test.
- Costs, the cap, the universe and the regime thresholds are provisional placeholders, not
  calibrated (D-007, D-034, D-045).
- The universe was chosen with hindsight (survivorship and selection bias).
- Only configuration 4 (κ = 0, the original grid) was tested. The turnover-penalty arms of
  E7–E12, which did better on validation, were never test arms and cannot be judged from this run.
- The review of the bootstrap and the evaluator was by a team member, not an external reviewer,
  and no review document exists.
