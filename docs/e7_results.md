# E7 results: turnover-aware PPO (EXP-018)

> **Status (2026-11-04):** complete on the training and validation splits.
> - **Methodology:** `docs/e7_turnover_aware.md` (D-091), fixed before training.
> - **Pipeline check:** EXP-017 (not a result).
> - **Test period:** sealed. Test performance is **unmeasured**.
> - **Research only;** simulated backtests on one market history; not financial advice.
> - **Traceability:** every number below comes from the verified outputs in §2.

## 1. Executive summary

**Prespecified outcome: A, "strong support"** (H1–H5, H7 and H8 supported; H6 partially). The
verdicts and their caveats need to be read together.

**Verified results:**
1. **Trading falls sharply and consistently.**
   - Validation turnover falls from a median of 17.5 a year (E7B) to 15.3 (E7T1, κ = 0.0015) and
     2.6 (E7T2, κ = 0.0075). It is lower in every seed for both arms.
   - The median relative reduction is **larger on validation than on training**: 41% vs 24% for
     T1, 86% vs 73% for T2.
2. **Cost drag falls with it.** Validation cost drag falls from 9.6 pp to 7.6 pp and 1.4 pp over
   the three years (paired mean −3.9 pp and −9.6 pp; lower in every seed).
3. **Validation net performance improves in median, but not uniformly.**
   - **Net Sharpe:** median 0.512 → 0.788 (T1) and 0.691 (T2).
   - **Paired means:** +0.23 and +0.34 (each 4 of 5 seeds). Both descriptive t-intervals include
     zero.
   - **Annualised net return:** +1.2 and +1.4 pp (4 of 5 seeds).
   - **Seed 44 is worse under both penalties.**
4. **The gain comes from lower costs, not better allocation.**
   - Validation **gross** return is unchanged for T1 (−0.05 pp) and lower for T2 (−5.4 pp, in
     every seed).
5. **In-sample, the strong penalty costs performance.** On the training split, T2 lowers net
   Sharpe in all 5 seeds (−0.30) and annualised return by 6.3 pp. T1 is roughly neutral in-sample.
6. **The strong penalty makes the policy nearly static and concentrated.**
   - **Holdings:** median 57% cash; the risky sleeve is concentrated in one fund (TLT in 4
     seeds; EFA and gold in seed 43); risky HHI 0.93.
   - **Reallocation activity** (`allocation_stability_dw`) is 17% of the control's, so T2 fails
     the responsiveness criterion (H6 partial).
7. **Against the baselines:** all three arms remain below every simple baseline on validation
   (best single policy 0.982, against 1.355 / 1.470 / 1.754).
8. **The control reproduces E6L exactly** (maximum difference 0.0). E0 reproduces EXP-006 in
   every evaluation.

**Interpretation:**
- A turnover penalty is the **first intervention in this research line to improve validation net
  performance**, and it does so by addressing the documented source of poor performance: cost
  drag from over-trading.
- **The moderate penalty (κ = 0.0015) is the more defensible result:** it cuts cost drag by
  about 40% while keeping gross performance, responsiveness and in-sample performance.
- **The strong penalty (κ = 0.0075) "wins" on validation** largely by becoming a near
  buy-and-hold of cash and one asset. That suited the calm 2017–2019 period, but it is a
  concentration and responsiveness trade-off, and it underperforms in-sample.

## 2. Records

**Commits:**
- `c682e32` (clean) for implementation, protocol, training and evaluations;
- the results commit holds this report.

**Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`; training decisions
2007-07-05 → 2016-12-30 (496); validation 2017-01-03 → 2019-12-31 (156).

| Item | Identifier |
| --- | --- |
| E7B runs (κ = 0), seeds 42–46 | cfd7ca4cdebd29c7, 21440b40672308cf, d20341e993bfc9df, 11d2d91fb9cade86, 7c7fcc911080ffd8 |
| E7T1 runs (κ = 0.0015) | 5aa8f4a944781cea, 532bf2990857b828, 4084e8c86e688270, eaa6b323401f3199, 50489bf5cc838d12 |
| E7T2 runs (κ = 0.0075) | 30a0c2708397778f, 336353126f61842f, 3e8b29d17d826043, 4aaa66dcca7b5837, b74fd3eb4d8cdb0a |
| Training | 15 of 15 completed: 100,352 timesteps (configured 100,000) and 202 episodes each; 89–155 s each; 2026-11-03 20:11–20:37 UTC; **0 failures, 0 retries** |
| Evaluations (all VERIFIED; 25 of 25 comparability checks each) | E7B train `300fc313f83f26ed`, validation `853856814f0d9687`; E7T1 train `00b9cde548df6173`, validation `a9529bf9b69c6052`; E7T2 train `a99a9a7ee29bc750`, validation `27223e4c92aa897e` |
| Reproduction | E7B = E6L (`01bfb1a2643f2e38`) exactly; E0 = EXP-006 exactly |
| Comparison (VERIFIED, criteria D-091 v1) | `data/processed/turnover_comparisons/9ddf7284e9c26661` (references E1, E4, E6H) |
| Figures | `reports/figures/e7/e7_metrics_vs_kappa.png`, `e7_seed_comparison.png` (git-ignored; source-hash sidecars) |

## 3. Reward

```text
r_k = r_base,k − κ · TN_k          (λ = 0)
TN_k = recurring ETF traded notional of step k (Σ|Δw| over 7 ETFs, cash leg excluded; funding step := 0)
κ = 0 (E7B), 0.0015 (E7T1, = the cost rate), 0.0075 (E7T2, = 5× the cost rate)
```

**No double counting:**
- **The real cost stays where it was.** 0.0015 × TN is in r_base through the ledger, which is
  identical with and without the penalty (tested).
- **The penalty is reward shaping only.** It appears in no reported metric.

**Logged training components:**
Values are the mean over the last 50 training episodes, as a range across the five seeds
(`training_components.json`).
- **E7T1:** base log growth 0.57–0.88 per episode; reward after the penalty −0.04 to 0.31.
- **E7T2:** base log growth 0.60–0.84; reward −1.07 to −0.13. At the end of training the mean
  penalty still exceeded the mean base reward in every seed, so the policies were still under
  strong trading pressure.

## 4. Seed-level validation results (2017–2019, net of 15 bps costs)

| Seed | Sharpe B | Sharpe T1 | Sharpe T2 | Turnover B | Turnover T1 | Turnover T2 | Cost drag B | Cost drag T1 | Cost drag T2 | Max DD B | Max DD T1 | Max DD T2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | −0.031 | 0.117 | 0.559 | 27.2 | 16.0 | 2.5 | 12.9 pp | 7.6 pp | 1.3 pp | −9.54% | −7.83% | −5.18% |
| 43 | 0.512 | 0.831 | 0.941 | 31.2 | 19.9 | 4.4 | 16.6 pp | 10.9 pp | 2.5 pp | −10.50% | −8.53% | **−11.72%** |
| 44 | **0.946** | 0.763 | 0.691 | 17.5 | 15.3 | 3.3 | 9.6 pp | 8.2 pp | 1.7 pp | −8.51% | −8.40% | −7.36% |
| 45 | 0.147 | 0.812 | 0.681 | 17.3 | 9.8 | 2.6 | 8.3 pp | 5.2 pp | 1.4 pp | −6.44% | −6.50% | −4.41% |
| 46 | 0.577 | 0.788 | 0.982 | 15.5 | 7.7 | 0.9 | 8.0 pp | 4.0 pp | 0.5 pp | −7.58% | −5.99% | −4.35% |

**Exceptions:**
- **Seed 44:** both penalties lowered Sharpe.
- **Seed 43:** the strong penalty deepened the drawdown.

## 5. Medians over seeds

| Split | Arm | Net Sharpe | Ann. net return | Gross cum. | Net vol | Net max DD | Cost drag | Turnover / yr | Equity | Bonds | Cash | Risky HHI | Stability D_w |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Validation | E7B | 0.512 | 3.04% | 17.33% | 5.55% | −8.51% | 9.64 pp | 17.5 | 17.8% | 56.4% | 25.0% | 0.47 | 0.060 |
| Validation | E7T1 | 0.788 | 4.06% | 17.62% | 5.57% | −7.83% | 7.63 pp | 15.3 | 8.1% | 47.6% | 27.0% | 0.51 | 0.045 |
| Validation | E7T2 | 0.691 | 3.73% | 13.28% | 4.55% | −5.18% | 1.36 pp | 2.6 | 2.5% | 39.4% | 57.1% | 0.93 | 0.010 |
| Training | E7B | 1.267 | 17.40% | 542% | 13.38% | −16.78% | 192.8 pp | 25.4 | 28.2% | 40.7% | 21.8% | 0.45 | 0.080 |
| Training | E7T1 | 1.310 | 16.28% | 477% | 12.10% | −19.29% | 148.3 pp | 21.2 | 17.0% | 39.0% | 27.5% | 0.48 | 0.063 |
| Training | E7T2 | 1.026 | 12.37% | 241% | 11.14% | −14.66% | 31.7 pp | 7.5 | 10.5% | 33.4% | 49.8% | 0.75 | 0.026 |

**Downside risk / Sortino:** not available from the evaluator (D-076).

## 6. Paired differences (mean ± SD; 95% t-interval, descriptive; seeds with a positive difference)

| Metric | Comparison | Validation | Training |
| --- | --- | --- | --- |
| Turnover / yr | T1 − B | **−8.00 ± 3.73 [−12.63, −3.37]; 0/5** (median −41%) | −7.97 ± 3.23; 0/5 (−24%) |
| | T2 − B | **−19.00 ± 6.17 [−26.66, −11.34]; 0/5** (−86%) | −21.06 ± 5.65; 0/5 (−73%) |
| | T2 − T1 | −11.00 ± 3.82; 0/5 | −13.09 ± 4.04; 0/5 |
| Cost drag | T1 − B | **−3.90 pp ± 1.71 [−6.02, −1.78]; 0/5** | −81.1 pp; 0/5 |
| | T2 − B | **−9.60 pp ± 3.11 [−13.46, −5.74]; 0/5** | −198.0 pp; 0/5 |
| Net Sharpe | T1 − B | +0.232 ± 0.306 [−0.148, 0.613]; 4/5 | +0.016 ± 0.143; 3/5 |
| | T2 − B | +0.341 ± 0.341 [−0.083, 0.765]; 4/5 | **−0.304 ± 0.178 [−0.526, −0.083]; 0/5** |
| | T2 − T1 | +0.109 ± 0.228; 3/5 | −0.320 ± 0.082; 0/5 |
| Ann. net return | T1 − B | +1.23 pp ± 1.61; 4/5 | −1.12 pp; 2/5 |
| | T2 − B | +1.36 pp ± 1.71; 4/5 | **−6.25 pp; 0/5** |
| Gross cum. return | T1 − B | −0.05 pp; 2/5 | −117 pp; 0/5 |
| | T2 − B | **−5.37 pp; 0/5** | −381 pp; 0/5 |
| Net volatility | T1 − B | −0.22 pp; 1/5 | −1.02 pp; 0/5 |
| | T2 − B | −1.03 pp; 1/5 | −1.89 pp; 1/5 |
| Net max DD (+ = shallower) | T1 − B | +1.06 pp; 4/5 | −1.48 pp; 1/5 |
| | T2 − B | +1.91 pp; 4/5 | +0.29 pp; 3/5 |

**Seed variation:** the within-arm seed SD of validation turnover is 4.9 a year (median over
arms).

**Caveat:** five seeds share one market history, so the t-intervals are descriptive and are not
significance tests.

## 7. Analysis

- **Does the trading reduction transfer?** Yes, and more strongly than the risk lever in E5 and
  E6 (§1 item 1). The penalty changes a robust behavioural trait (how often the policy trades)
  rather than a market-dependent one.
- **Does lower turnover reduce cost drag?** Yes, almost proportionally: cost drag is
  0.0015 × traded notional, and the accounting is unchanged.
- **Is net Sharpe better?**
  - **On validation:** in median and in 4 of 5 seeds for each arm, but the intervals include
    zero and seed 44 is worse.
  - **On training:** only T1 is neutral; T2 is worse in every seed.
  - Positive on validation, not robust across splits for T2.
- **Is the policy too conservative?**
  - **T1:** no. Equity is lower, and cash slightly higher.
  - **T2:** yes, by the responsiveness and concentration measures. Its validation advantage
    comes from holding cash and one bond or diversifier fund through a calm period.
- **Drawdown:** validation drawdowns are shallower for both arms in 4 of 5 seeds. In-sample, T1's
  are deeper in 4 of 5 seeds (−1.5 pp).
- **Allocation:** penalties shift the portfolio from equity to cash, and concentrate the risky
  sleeve. These shifts exceed seed variation for turnover (H8). They are a by-product of trading
  less, not a learned allocation skill: gross returns do not improve.
- **Does the change address the actual source of poor performance?** Partly. Over-trading
  explained much of the cost drag (E7B loses 9.6 pp to costs; T1 recovers about 3.9 pp of
  that). But gross performance is unchanged, and every arm remains below the baselines, so
  allocation quality is not improved.

## 8. Hypotheses

| | Verdict | Evidence |
| --- | --- | --- |
| H1 turnover reduction (train) | **Supported** | T1 and T2 lower in 5/5 seeds; median T2 7.5 ≤ T1 21.2 |
| H2 cost efficiency (validation) | **Supported** | Cost drag lower in 5/5 seeds for both arms; no double counting (tested) |
| H3 transfer | **Supported** | Validation turnover lower in 5/5; relative reductions 41% / 86% ≥ 50% of the training 24% / 73% |
| H4 net performance | **Supported** | Median paired Sharpe +0.21 / +0.43, return +1.25 / +1.85 pp (validation) |
| H5 risk preservation | **Supported** | Median volatility −0.14 / −1.29 pp; drawdowns shallower |
| H6 responsiveness | **Partially** | T1 stability 75% of B (pass); T2 17% (fail); no cash collapse (> 95% cash share = 0) |
| H7 reproduction | **Supported** | E7B = E6L exactly |
| H8 practical utility | **Supported** | Cost-drag reduction 3.9 / 7.9 pp ≥ 2 pp; turnover reduction 8.0 / 19.0 > seed SD 4.9 |

**Outcome A (mechanical rule).** The rule did not require H6 or in-sample performance. The
caveats in §1 and §7 are therefore part of the conclusion.

## 9. Comparison (validation medians, centre profile)

| Arm | Net Sharpe | Net vol | Net max DD | Turnover / yr | Cost drag |
| --- | --- | --- | --- | --- | --- |
| Baselines (EW monthly / buy and hold / inverse vol) | 1.470 / 1.355 / 1.754 | 5.93 / 6.28 / 4.56% | −10.42 / −11.49 / −7.58% | 0.22 / 0 / 0.78 | 0.32 / 0.19 / 0.63 pp |
| E0 existing PPO | 0.635 | 5.61% | −9.24% | 15.9 | 8.4 pp |
| E1 profile in observation | 0.534 | 5.22% | −7.52% | 19.4 | 10.9 pp |
| E4 profile-dependent λ | 0.601 | 5.16% | −7.49% | 19.9 | 11.2 pp |
| E6L = E7B (λ = 0) / E6H (λ = 9) | 0.512 / 0.682 | 5.55 / 4.99% | −8.51 / −8.43% | 17.5 / 18.9 | 9.6 / 10.3 pp |
| **E7T1** (κ = 0.0015) | **0.788** | 5.57% | −7.83% | 15.3 | 7.6 pp |
| **E7T2** (κ = 0.0075) | 0.691 | 4.55% | −5.18% | 2.6 | 1.4 pp |

**Reading:**
- E7T1 has the highest median validation net Sharpe of any PPO arm so far.
- E7T2 has the lowest PPO volatility and drawdown.
- Both remain below all three simple baselines. E7T2's turnover (2.6) is still about 3× inverse
  volatility's.

## 10. Limitations

- **Data:** one market history. Validation is calm (2017–2019); a near-static, cash-heavy policy
  may do worse in a trending or volatile period.
- **Seeds:** five; the intervals cross zero for Sharpe.
- **Coefficients:** two κ values. The optimum between them, and the risk of over-penalising, are
  unresolved.
- **Penalty design:** linear in traded notional; it does not distinguish useful from noisy
  trades.
- **In-sample trade-off:** T2's in-sample underperformance suggests the penalty trades return for
  inactivity.
- **Unchanged:** allocation quality (gross returns) is not improved; downside risk is
  unavailable; the profile input is constant (no personalisation).
- **Test period:** unmeasured.

## 11. Conclusion

- **Can a turnover-aware reward reduce excessive trading and cost drag without materially
  degrading net performance?** **On validation, yes.**
  - Trading and costs fall sharply and consistently. Net Sharpe and return improve in median
    and in 4 of 5 seeds. Volatility and drawdown do not worsen in median.
  - **Not established:**
    - that the gains are robust: the intervals include zero, one seed is worse, and the strong
      penalty underperforms in-sample;
    - that allocation skill improves: gross returns are unchanged or lower;
    - that PPO beats simple baselines: it does not.
- **Which arm:** the moderate penalty (κ = the cost rate) is the balanced setting. The strong
  penalty buys its validation result with a static, concentrated portfolio.

## 12. Recommended next experiment (not started; needs its own protocol and ID)

1. **Primary: a κ dose–response refinement around the moderate setting.** For example
   κ ∈ {0.0015, 0.003, 0.0045}, seeds 42–46, the same protocol style.
   - **Aim:** find whether the cost savings can be increased without T2's concentration and
     in-sample loss.
   - **Add:** a concentration or responsiveness criterion to the primary decision rule (H6
     failed silently in the outcome rule here).
2. **Alternative: combine the moderate turnover penalty with the E6 risk term** (κ = 0.0015,
   λ = 9), to test whether the two levers are complementary.

Either way, the test period stays sealed until a candidate is selected under a pre-registered
rule.
