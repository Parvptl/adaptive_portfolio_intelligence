# E6 results: fixed risk-aversion dose response (EXP-016)

> **Status (2026-11-04):** complete on the training and validation splits.
> - **Methodology:** `docs/e6_dose_response.md` (D-090), fixed before training.
> - **Pipeline check:** EXP-015 (not a result).
> - **E6 is a fixed-risk sensitivity experiment.** It does **not** establish investor
>   personalisation.
> - **Test period:** sealed. Test performance is **unmeasured**.
> - **Research only;** simulated backtests on one market history; not financial advice.
> - **Traceability:** every number below comes from the verified outputs in §2.

## 1. Executive summary

**Prespecified outcome: B, "weak or partial dose response".**

1. **The response is monotonic and graded on both splits.**
   - Volatility falls from λ = 0 to 3 to 9 within seed in 4 of 5 validation seeds, and in 5 of 5
     training seeds.
   - λ = 3 lies between the endpoints: the median fraction of the 0→9 reduction reached at λ = 3
     is 0.43 on validation and about 0.47 on training.
   - Each pairwise direction (3 < 0, 9 < 3, 9 < 0) holds in ≥ 4/5 seeds on both splits.
   - This passes H1, H2 and H3.
2. **The effect is large in-sample but small out of sample.**
   - **Training split:** volatility falls 1.5 pp (λ 0→3) and a further 2.1 pp (3→9). Drawdown is
     shallower and equity lower at each step, in every seed.
   - **Validation:** the total 0→9 reduction is only 0.52 pp a year (median 9.7%, against 29.2%
     in training).
   - This fails the transfer criterion (H4, partially supported) and the 10% practical
     threshold (H8, partially supported).
3. **Validation allocations do not separate.**
   - The allocation difference between λ = 0 and 9 (D_w 0.052) is below the seed-to-seed
     difference (0.094).
   - Equity is not lower at λ = 9 in ≥ 4/5 seeds.
   - Drawdowns are flat (H5 not supported).
4. **No trading or cost penalty; better risk-adjusted performance on validation.**
   - Turnover and cost drag stay within the criteria (H6 supported).
   - Paired validation net Sharpe rises with λ: +0.08 (3−0), +0.20 (9−3), +0.28 (9−0) (H7
     supported).
   - Every arm remains below every simple baseline.
5. **Determinism:** E6L and E6H reproduce E5L and E5H **exactly** (maximum difference 0.0),
   from different commits and at different times.

**Conclusion:** within this setup, λ is a reproducible, graded control of **in-sample** risk.
Out of sample, its effect is small: real and monotone in volatility, but not practically large,
and not matched by a stable allocation shift.

## 2. Records

**Commits:**
- `698152b` (clean) for implementation and protocol, training and evaluations;
- the results commit holds this report.

**Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`.
- Training decisions 2007-07-05 → 2016-12-30 (496); validation 2017-01-03 → 2019-12-31 (156).

| Item | Identifier |
| --- | --- |
| E6L runs (λ = 0), seeds 42–46 | ef7ba01aa36b33bc, d2eb7014b3a15b2c, 091b84c67396568a, dbe1de95f7dd6dab, d4b5237ddaac4d4f |
| E6M runs (λ = 3) | 11fc189b5c166e2f, 09e7c05ca7db6adf, c6887b8262367bac, 0fcff8c557e3328c, aa8c14e4df2ed907 |
| E6H runs (λ = 9) | 497daee0e33f029e, f0be2a72c80a5107, 45a8d1b124e53d4a, fc9b933d6f18bcf2, ede0d617c0cc9d76 |
| Training | 15 of 15 completed: 100,352 timesteps (configured 100,000) and 202 episodes each; 92–402 s per run; 2026-11-03 17:56–19:05 UTC including evaluations; **0 failures, 0 retries** |
| Evaluations (all VERIFIED; 25 of 25 comparability checks each) | E6L train `b85bc3753249fc83`, validation `01bfb1a2643f2e38`; E6M train `8203ece24ef46d66`, validation `4abfb0b026bb2ec5`; E6H train `e20c10e1882d28fb`, validation `5bb66c096879caaa` |
| E0 reproduction | EXP-006 exactly (difference 0.0) in all three validation evaluations |
| Comparison (VERIFIED, criteria D-090 v1) | `data/processed/dose_response_comparisons/0b1860cf0497e504`; references E1 `6be9dce1b006008b`, E4 `948eb21380278b03`; E5 reproduction against `d9067e393b0b26d4` and `6a505ae16055c427` |
| Figures | `reports/figures/e6/e6_risk_vs_lambda.png`, `e6_allocation_by_lambda.png` (git-ignored; source-hash sidecars) |

**Runtime:** wall time per run was 92–402 s, against about 85 s in E5. This is consistent with
CPU contention from an unrelated process on the machine. Results are unaffected, as the exact
E5 reproduction shows.

## 3. Reward

```text
r = r_base − (λ/2) · Σ_{t ∈ (d_k, d_{k+1}]} net_return_t²,   λ ∈ {0, 3, 9}, fixed
```

- **Implementation:** E5's, unchanged (`ProfileRewardSpec`, `acceptance: fixed`).
- **Logged λ:** constant in every training episode of every run.
- **Profile input:** constant 0.5.
- **Arms:** they differ only in `fixed_lambda` and `label`.

## 4. Seed-level results (centre profile)

### Validation 2017–2019, net of 15 bps costs

| Seed | Vol λ0 | Vol λ3 | Vol λ9 | Sharpe λ0 | Sharpe λ3 | Sharpe λ9 | Max DD λ0 | Max DD λ3 | Max DD λ9 | Equity λ0 | Equity λ3 | Equity λ9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | 6.23% | 6.02% | 5.73% | −0.031 | 0.103 | 0.338 | −9.54% | −7.75% | −8.43% | 14.1% | 11.7% | 18.1% |
| 43 | 6.38% | **6.45%** | 5.94% | 0.512 | 0.653 | 0.812 | −10.50% | −12.23% | −10.57% | 32.1% | 29.5% | 20.2% |
| 44 | 5.55% | 5.22% | 4.98% | 0.946 | 1.070 | 1.223 | −8.51% | −8.51% | −9.11% | 28.5% | 24.8% | 26.4% |
| 45 | 5.52% | 5.01% | 4.99% | 0.147 | 0.313 | 0.503 | −6.44% | −6.87% | −6.83% | 17.8% | 11.2% | 9.5% |
| 46 | 5.51% | 5.51% | 4.92% | 0.577 | 0.410 | 0.682 | −7.58% | −9.43% | −6.73% | 7.9% | 9.2% | 20.4% |

- **Seed 43:** λ = 3 is slightly *more* volatile than λ = 0.
- **Seed 46:** λ = 3 barely differs from λ = 0 (f = 0.002).

### Medians over seeds

| Split | λ | Net Sharpe | Ann. return | Net vol | Net max DD | Cost drag | Turnover / yr | Target equity | Target bonds | Target cash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Validation | 0 | 0.512 | 3.04% | 5.55% | −8.51% | 9.64 pp | 17.5 | 17.8% | 56.4% | 25.0% |
| Validation | 3 | 0.410 | 2.10% | 5.51% | −8.51% | 9.93 pp | 17.8 | 11.7% | 51.7% | 26.5% |
| Validation | 9 | 0.682 | 3.25% | 4.99% | −8.43% | 10.28 pp | 18.9 | 20.2% | 48.9% | 19.9% |
| Training | 0 | 1.267 | 17.40% | 13.38% | −16.78% | 192.8 pp | 25.4 | 28.2% | 40.7% | 21.8% |
| Training | 3 | 1.447 | 16.53% | 11.05% | −10.00% | 159.1 pp | 22.6 | 22.0% | 39.3% | 26.1% |
| Training | 9 | 1.612 | 14.51% | 9.88% | −7.89% | 135.3 pp | 22.4 | 18.1% | 43.3% | 27.0% |

**About the medians:** they are taken metric by metric across seeds, so they need not move
together. For example, the λ = 3 median Sharpe (0.410) is below λ = 0's, although the **paired**
λ 3 − 0 Sharpe difference is positive in 4 of 5 seeds (§5).

**Downside risk / Sortino:** not available from the evaluator (D-076). Not reported.

## 5. Paired differences (mean ± SD; 95% t-interval, descriptive; seeds with a positive difference; effect size d = mean / SD)

| Metric | Comparison | Validation | Training |
| --- | --- | --- | --- |
| Net volatility | λ 3 − 0 | −0.20 pp ± 0.24 [−0.49, 0.10]; 1/5; d −0.8 | −1.51 pp ± 0.69 [−2.37, −0.66]; 0/5; d −2.2 |
| | λ 9 − 3 | −0.33 pp ± 0.23 [−0.61, −0.05]; 0/5; d −1.4 | −2.08 pp ± 0.94 [−3.25, −0.92]; 0/5; d −2.2 |
| | λ 9 − 0 | −0.52 pp ± 0.06 [−0.60, −0.45]; 0/5; d −8.7 | −3.60 pp ± 1.35 [−5.27, −1.92]; 0/5; d −2.7 |
| Net max DD (+ = shallower) | λ 3 − 0 | −0.44 pp; 2/5 | +4.46 pp; 5/5 |
| | λ 9 − 3 | +0.62 pp; 3/5 | +2.39 pp; 5/5 |
| | λ 9 − 0 | +0.18 pp; 2/5 | +6.85 pp; 5/5 |
| Net Sharpe | λ 3 − 0 | +0.080 ± 0.139; 4/5 | +0.154 ± 0.053; 5/5 |
| | λ 9 − 3 | +0.202 ± 0.051; 5/5 | +0.112 ± 0.097; 4/5 |
| | λ 9 − 0 | +0.282 ± 0.106; 5/5 | +0.266 ± 0.127; 5/5 |
| Target equity | λ 3 − 0 | −2.80 pp; 1/5 | −4.81 pp; 0/5 |
| | λ 9 − 0 | −1.17 pp; 2/5 | −8.95 pp; 0/5 |
| Target cash | λ 3 − 0 | +3.76 pp; 5/5 | +4.04 pp; 5/5 |
| Turnover / yr | λ 3 − 0 | −2.31; 2/5 | −3.60; 0/5 |
| | λ 9 − 0 | −3.69; 2/5 | −6.20; 0/5 |

- **Within-arm variation (validation):** the seed SD of volatility is 0.48 pp (median over
  arms).
- **Allocation:** the between-arm D_w (λ 0 vs 9, median 0.052) is below the within-arm seed D_w
  (0.094).
- **Caveat:** five seeds share one market history. They show reproducibility across random
  initialisation, not generalisation across market regimes.

## 6. Dose–response analysis

- **Monotonicity:**
  - **training:** strictly monotone in volatility, drawdown and equity in every seed;
  - **validation:** monotone in volatility in 4 of 5 seeds, and the arm medians are strictly
    decreasing (5.55% → 5.51% → 4.99%).
  - **Training records:** the realised variance of the last 50 training episodes is monotone in
    λ in all 5 seeds (λ 0: 0.106–0.156; 3: 0.087–0.132; 9: 0.065–0.100).
- **Shape:**
  - λ = 3 gives about 43–47% of the λ = 9 volatility reduction: a graded response, roughly
    proportional to λ or mildly saturating. Three points cannot distinguish these shapes.
  - On validation the per-seed fraction is spread widely (−0.18 to 0.96), so the intermediate
    arm is informative in median but noisy per seed.
- **Transfer:** the validation effect is 14% of the training effect for 0→9 (0.52 vs 3.60 pp).
  The policies learn risk control on the history they were trained on; most of it does not carry
  into the calmer 2017–2019 period.
- **Allocation:**
  - **in-sample:** λ shifts equity into cash (and partly bonds) at each step;
  - **validation:** cash rises from λ 0 to 3 in every seed (+3.8 pp), but equity and bonds move
    inconsistently, and λ = 9 holds *less* cash than λ = 3 in median.
  - The validation risk reduction is therefore not produced by one consistent allocation rule.
- **Trading and costs:** higher λ trades less in-sample in every seed. On validation, turnover
  is within ±25% (medians 17.5, 17.8, 18.9) and cost drag within 1 pp, so there is no
  pathological trading.
- **Performance trade-off:**
  - **validation:** higher λ gave higher net Sharpe and annualised return in every 9 − 0 pair.
    Lower volatility did not cost return in this period.
  - **in-sample:** return fell (−1.8 pp a year, 0→9) while Sharpe rose.
  - Neither establishes out-of-sample superiority, and every arm stays below the baselines.

## 7. Hypotheses

| | Verdict | Evidence |
| --- | --- | --- |
| H1 monotonic risk response | **Supported** | vol(0) > vol(3) > vol(9) in 4/5 validation seeds; medians decreasing |
| H2 informative intermediate arm | **Supported** | Strictly between in 4/5 seeds; median f = 0.43 |
| H3 reproducible direction | **Supported** | All three pairwise directions hold in ≥ 4/5 seeds on both splits |
| H4 transfer to validation | **Partially** | Validation reduction > 0, and 9 < 0 in 5/5; but 9.7% < 50% of 29.2% |
| H5 allocation response | **Not supported** | D_w 0.052 < seed D_w 0.094; equity lower at 9 in only 3/5 |
| H6 no excess trading or cost | **Supported** | Turnover and cost drag within the criteria |
| H7 no risk-adjusted cost | **Supported** | Median paired Sharpe +0.134 (3−0) and +0.301 (9−0) |
| H8 practically meaningful | **Partially** | 0.53 pp ≥ 0.5 pp, and a mean of 0.52 pp > seed SD 0.48 pp; but 9.7% < 10% |

**Outcome B (mechanical rule):** H4 is not supported in full, so the core set for A fails.
Neither H1 nor H4 is "not supported", so the outcome is not C.

## 8. Comparison (validation medians, centre profile)

| Arm | Net Sharpe | Net vol | Net max DD | Turnover / yr |
| --- | --- | --- | --- | --- |
| Baselines (EW monthly / buy and hold / inverse vol) | 1.470 / 1.355 / 1.754 | 5.93 / 6.28 / 4.56% | −10.42 / −11.49 / −7.58% | 0.22 / 0 / 0.78 |
| E0 existing PPO | 0.635 | 5.61% | −9.24% | 15.9 |
| E1 profile in observation | 0.534 | 5.22% | −7.52% | 19.4 |
| E4 profile-dependent λ | 0.601 | 5.16% | −7.49% | 19.9 |
| E5L / E5H (= E6L / E6H exactly) | 0.512 / 0.682 | 5.55 / 4.99% | −8.51 / −8.43% | 17.5 / 18.9 |
| E6M (λ = 3) | 0.410 | 5.51% | −8.51% | 17.8 |

**Reading:** E6 adds the graded middle point to E5, and confirms that λ's effect is
reproducible and monotone. It does not make the out-of-sample effect larger.

## 9. Interpretation

1. **λ works as an in-sample risk dial.** Its effect is graded and reproducible across seeds,
   so the reward is informative and PPO optimises it.
2. **Out of sample, the dial is weak.**
   - The direction holds, but the size (about 0.5 pp of volatility) is close to seed noise.
   - It comes without a consistent allocation change.
   - This points to policies whose risk behaviour is partly fitted to the 2007–2016 path (the
     2008 crisis dominates the training variance). It does not point to a general, transferable
     rule.
3. **For profile conditioning (E4):** a profile can only personalise risk as much as λ moves
   risk out of sample, which is little. Returning to profile conditioning now would rest on a
   weak lever. Personalisation is **not** established, and E6 does not test it.

## 10. Limitations

- **Data:** one market history. The validation period 2017–2019 is mostly calm; risk control
  may matter more in turbulent periods, which only the sealed test or other data could show.
- **Statistics and design:**
  - five seeds, which measure reproducibility, not regime generalisation;
  - three λ values: coarse shape;
  - the in-sample results are where the policies were optimised.
- **Metrics:** downside risk is unavailable; drawdown is not targeted by the reward.
- **Inherited:** over-trading of about 17–25× a year, and cost drag of 9.6–10.3 pp on validation.
- **Design:** the constant profile input; no personalisation.
- **Test period:** unmeasured.

## 11. Next recommendation (not started; needs its own protocol and ID)

**Make the risk lever transfer before conditioning on it again.** The most informative next
experiment targets the out-of-sample weakness directly:
- **Option 1:** a risk measure aligned with what transfers, for example longer-horizon
  (rolling 21- or 63-session) realised variance, or a drawdown penalty, compared at fixed
  λ = 9 against the E5H/E6H per-step variance;
- **Option 2:** first address the over-trading, which costs about 10 pp of return over three
  validation years in every arm. For example, a turnover-aware reward or a no-trade band
  (D-077 items 2–3).

**Rationale:** E4–E6 show that the policy learns *in-sample* risk control but not a robust
allocation rule. More conditioning capacity would not fix that.
