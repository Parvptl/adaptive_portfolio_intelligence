# E5 results: fixed risk-aversion PPO (EXP-014)

> **Status (2026-11-03):** complete on the training and validation splits.
> - **Methodology:** `docs/e5_fixed_risk_aversion.md` (D-089), fixed before training.
> - **Pipeline check:** EXP-013 (not a result).
> - **Test period:** sealed. Out-of-sample test performance is **unmeasured**.
> - **Research only;** simulated backtests; not financial advice.
> - **Traceability:** every number below comes from the verified outputs in §2.

## 1. Executive summary

**What E5 tested:** whether a **fixed** risk-aversion coefficient changes the risk behaviour PPO
learns.
- **Arms:** E5L (λ = 0, the base log-growth reward) and E5H (λ = 9, relative risk aversion 10).
- **Implementation:** the same reward implementation as E4. The profile input is held constant
  at 0.5 in both arms, so the arms differ only in λ.

**Prespecified outcome: B, "reward sensitivity exists but is weak or partial".**

**What it found:**
1. **On the training years (where the policies were optimised), λ clearly controls risk.**
   - **E5H vs E5L, in every seed:** volatility −3.6 pp (13–37% lower), maximum drawdown 6.9 pp
     shallower, equity exposure −9.0 pp, turnover −6.2 a year, net Sharpe +0.27.
   - **Training records:** the realised variance of the last 50 training episodes was 0.61–0.66×
     E5L's in every seed.
2. **On validation (2017–2019), the effect remains in direction but is small.**
   - **Volatility:** lower in all 5 seeds, but only by 0.52 pp a year (a 9.7% median reduction,
     against the prespecified 10%).
   - **Drawdowns:** not consistently shallower (2 of 5).
   - **Allocation:** E5H's equity and cash do not move consistently, and the allocation difference
     between arms (D_w 0.052) is **smaller** than the differences between seeds (0.095).
3. **Performance:**
   - E5H's validation net Sharpe was higher than E5L's in all 5 seeds (+0.28 on average, median
     0.682 vs 0.512).
   - No E5 policy reached any simple baseline (best 1.223, against 1.355–1.754).
   - This is one prespecified validation look, not tuning. It is also not evidence of
     out-of-sample superiority.
4. **No pathological trading or exploitation:** E5H did not trade more.
   - Validation: median 18.9 vs 17.5 a year (within the 1.25× criterion), paired mean −3.7.
   - Training split: lower in every seed.

**Implication for E4:** the reward coefficient **can** move PPO's risk level, strongly in-sample
and weakly out of sample. E4's failure to personalise is therefore mainly a **conditioning**
problem: the policy did not learn to map profiles to λ-appropriate behaviour. It is not a reward
that PPO ignores. Personalisation is **not** established by E5. The two fixed-λ policies are not
investor-specific.

## 2. Records

| Item | Identifier |
| --- | --- |
| Commit (training and evaluations) | `addcf7b` (clean); figures function added afterwards (results commit) |
| Data | dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`; train 2007-07-05 → 2016-12-30 (496 decisions), validation 2017-01-03 → 2019-12-31 (156 decisions) |
| E5L runs (λ = 0), seeds 42–46 | 7a393d5f1cceed1a, 1abfccd67254832b, 1fbbfa5856a35807, a5e06bb681959f4a, ff7519f36021c7cb |
| E5H runs (λ = 9), seeds 42–46 | 2b36cc3df2033b9a, 5f6454cdbbe2e0b5, b10c77e09537ba5a, 35914f921e295b03, 9c51b857f83b9971 |
| Training | 10 of 10 completed; 100,352 timesteps and 202 episodes each; 85.9–88.8 s each; 08:01–08:16 UTC; no failures |
| Evaluations (VERIFIED) | E5L train `771b962770f17efe`, validation `d9067e393b0b26d4`; E5H train `3d05b0aefeba01d6`, validation `6a505ae16055c427`; 25 of 25 comparability checks each |
| E0 reproduction | Validation: EXP-006 exactly (maximum absolute Sharpe difference 0.0), in both arms' evaluations |
| Comparison (VERIFIED) | `data/processed/fixed_risk_comparisons/36c60c635effca26` (criteria D-089 v1; E1 `6be9dce1b006008b` and E4 `948eb21380278b03` as references) |
| Figure | `reports/figures/e5/e5_fixed_lambda_by_seed.png` (git-ignored; source-hash sidecar) |

## 3. Reward

```text
r = r_base − (λ/2) · Σ_{t ∈ (d_k, d_{k+1}]} net_return_t²,   λ fixed: 0 (E5L) or 9 (E5H)
```

- **Terms:** r_base is the D-064 log growth after 15 bps costs. The sum is the step's own
  realised variance.
- **Shared code:** `ProfileRewardSpec.components()` is unchanged from E4. With `acceptance:
  fixed`, `penalty_coefficient()` returns the constant.
- **Logged:** λ was constant in every training episode of every run ([0.0] or [9.0]).

## 4. Seed-level results

### Validation 2017–2019

| Seed | Sharpe L | Sharpe H | Vol L | Vol H | Max DD L | Max DD H | Equity L | Equity H | Turnover L | Turnover H |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | −0.031 | 0.338 | 6.23% | 5.73% | −9.54% | −8.43% | 14.1% | 18.1% | 27.2 | 21.7 |
| 43 | 0.512 | 0.812 | 6.38% | 5.94% | −10.50% | −10.57% | 32.1% | 20.2% | 31.2 | 18.9 |
| 44 | 0.946 | 1.223 | 5.55% | 4.98% | −8.51% | −9.11% | 28.5% | 26.4% | 17.5 | 18.5 |
| 45 | 0.147 | 0.503 | 5.52% | 4.99% | −6.44% | −6.83% | 17.8% | 9.5% | 17.3 | 11.9 |
| 46 | 0.577 | 0.682 | 5.51% | 4.92% | −7.58% | −6.73% | 7.9% | 20.4% | 15.5 | 19.2 |

### Medians (centre profile)

| Arm | Split | Net Sharpe | Net cum. return | Ann. return | Net vol | Net max DD | Cost drag | Turnover / yr | Target equity | Target bonds | Target cash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E5L (λ = 0) | Validation | 0.512 | 9.37% | 3.04% | 5.55% | −8.51% | 9.64 pp | 17.5 | 17.8% | 56.4% | 25.0% |
| E5H (λ = 9) | Validation | 0.682 | 10.04% | 3.25% | 4.99% | −8.43% | 10.28 pp | 18.9 | 20.2% | 48.9% | 19.9% |
| E5L | Training | 1.267 | 358.3% | 17.40% | 13.38% | −16.78% | 192.8 pp | 25.4 | 28.2% | 40.7% | 21.8% |
| E5H | Training | 1.612 | 261.8% | 14.51% | 9.88% | −7.89% | 135.3 pp | 22.4 | 18.1% | 43.3% | 27.0% |

Note: the medians are taken metric by metric, so a column's median can come from a different seed
than its neighbour's.

### Paired differences E5H − E5L (mean ± SD; 95% t-interval, descriptive; seeds with E5H higher)

| Metric | Validation | Training |
| --- | --- | --- |
| Net volatility | **−0.52 pp ± 0.06 [−0.60, −0.45]; 0/5** | **−3.60 pp ± 1.35 [−5.27, −1.92]; 0/5** |
| Net max DD (+ = shallower) | +0.18 pp ± 0.76; 2/5 | **+6.85 pp ± 4.27 [1.55, 12.14]; 5/5** |
| Net Sharpe | **+0.282 ± 0.106 [0.151, 0.413]; 5/5** | **+0.266 ± 0.127 [0.108, 0.423]; 5/5** |
| Annualised net return | +1.35 pp ± 0.77 [0.38, 2.31]; 5/5 | −1.76 pp ± 1.94; 1/5 |
| Turnover / yr | −3.69 ± 6.23; 2/5 | −6.20 ± 4.25; 0/5 |
| Cost drag | −1.56 pp ± 3.21; 2/5 | −75.1 pp ± 35.2; 0/5 |
| Target equity | −1.17 pp ± 9.78; 2/5 | **−8.95 pp ± 2.76; 0/5** |
| Target cash | +4.14 pp ± 6.67; 3/5 | +5.70 pp ± 4.95; 4/5 |
| Step realised variance (sum) | −0.0017; 0/5 | −0.078; 0/5 |

Five seeds share one market history. The t-intervals are descriptive and are not significance
tests.

## 5. Risk response, allocation and seed variation

- **Risk response (H1, H6, H7):**
  - **in-sample:** large and fully consistent;
  - **validation:** consistent in sign (5 of 5 seeds), but about one seventh of the in-sample
    size. The median relative reduction was 9.7% against 29.2% in training, so H7's "≥ 50% of
    training" criterion failed.
  - **Practical size:** 0.52 pp a year on a portfolio with about 5–6% volatility. That is
    barely above the prespecified 0.5 pp practical threshold.
- **Allocation (H3, H8):**
  - **in-sample:** E5H holds less equity (all seeds), more cash and more bonds (4 of 5);
  - **validation:** these shifts do not hold. Equity went up in 2 seeds and down in 3, and
    drawdowns were not consistently shallower.
  - **Reading:** in this low-volatility validation period, E5H's lower risk does not come from a
    stable, recognisably more conservative allocation.
- **Seed variation (H2):** the paired allocation D_w between arms (mean held weights, median
  0.052) is **below** the within-arm seed-to-seed D_w (0.095). The seed changes the allocation
  more than λ does.
- **Training dynamics (H5):**
  - **E5H:** the realised variance fell from the first to the last 50 episodes in all 5 runs
    (0.104–0.117 → 0.065–0.100).
  - **E5L:** it rose in 3 runs.
  - **Penalty share:** E5H's last-50 penalty per episode (0.29–0.45) was about 0.6–0.8 of its
    base log growth (0.38–0.73). That is substantial, but it does not dominate, and the base
    reward stayed positive.
- **Exploitation (H4):** none.
  - **Validation turnover:** E5H's median was slightly higher (18.9 vs 17.5 a year, within
    1.25×), but its paired mean was lower (−3.7) and only 2 of 5 seeds traded more.
  - **Training turnover:** lower in every seed (22.4 vs 25.4 median).
  - **Cost drag:** within the 1 pp criterion.

## 6. Comparison with earlier experiments (validation medians, centre profile)

| Arm | Net Sharpe | Net vol | Net max DD | Turnover / yr | Source |
| --- | --- | --- | --- | --- | --- |
| Baselines | 1.355 / 1.470 / 1.754 | 4.56–6.28% | −7.58% to −11.49% | 0–0.78 | EXP-002/EXP-006 |
| E0 existing PPO | 0.635 | 5.61% | −9.24% | 15.9 | re-evaluated here (= EXP-006) |
| E1 profile, λ = 0 | 0.534 | 5.22% | −7.52% | 19.4 | `6be9dce1b006008b` |
| E4 profile-dependent λ | 0.601 | 5.16% | −7.49% | 19.9 | `948eb21380278b03` |
| **E5L** constant profile, λ = 0 | 0.512 | 5.55% | −8.51% | 17.5 | `d9067e393b0b26d4` |
| **E5H** constant profile, λ = 9 | 0.682 | 4.99% | −8.43% | 18.9 | `6a505ae16055c427` |

- E5H has the lowest validation volatility of the PPO arms, but it remains above inverse
  volatility (4.56%).
- Every PPO arm stays below every baseline on net Sharpe.

**Consistency check with E4:**
- With i.i.d. Uniform(0, 1) profiles, E[min(RT, RC)] = 1/3, so E4's mean training λ was
  9·(2/3) = 6.
- E4's in-sample volatility reduction relative to E1 (−2.6 pp) lies between 0 and E5's −3.6 pp
  at λ = 9.
- This matches E4 learning an approximately **average-λ** policy (EXP-012 §5).

## 7. Hypotheses

| | Verdict | Evidence |
| --- | --- | --- |
| **H1** lower risk at λ = 9 (primary) | **Partially** | Lower volatility in 5/5 seeds; median reduction 9.7% (< 10%) |
| H2 allocation difference > seed variation | **Not supported** | Cross-arm D_w 0.052 < seed D_w 0.095 |
| H3 more conservative exposure | **Not supported** | Equity lower in 3/5; cash + bonds higher in 3/5 |
| H4 not via turnover or costs | Supported | Turnover 18.9 vs 17.5 (≤ 1.25×); cost drag within 1 pp |
| H5 distinguishable reward components | Supported | Last-50 realised-variance ratio 0.61–0.66 in 5/5 |
| H6 reproducible | Supported | Volatility lower in 5/5 seeds on both splits |
| H7 stable on validation | **Partially** | Validation reduction > 0, but 9.7% < 50% of 29.2% |
| H8 interpretable | **Not supported** | Drawdown shallower in 2/5; equity criterion failed |

**Outcome B (prespecified rule):** H1 partially, H2 not, H6 supported.

## 8. Conclusion

- **Can a fixed risk aversion produce different trained risk behaviour?** Yes in-sample,
  clearly, reproducibly and interpretably. On validation, only weakly.
  - **Volatility:** λ = 9 consistently lowers it (5 of 5 seeds on both splits).
  - **Weakness out of sample:** the validation effect is small (0.5 pp a year), is not
    accompanied by a stable conservative allocation, and is smaller than seed-to-seed allocation
    variation.
- **Is λ a reliable risk-control mechanism?** Not out of sample in this setup.
- **Performance:** E5H improved validation net Sharpe over E5L in every seed (+0.28). It did
  not reach any baseline. Trading did not increase.
- **Implications:**
  - **For E4:** the reward is informative enough to move PPO's risk level. E4's
    non-personalisation is mainly a conditioning failure.
  - **For profile conditioning:** a profile-dependent reward is technically viable in the sense
    that λ matters. Because even the fixed-λ effect is weak out of sample, however, profile
    effects learned through λ would be weaker still.
  - **Investor personalisation:** not demonstrated by E5.
- **Where further work should focus:**
  1. **training and conditioning**, not new architectures: more profile-diverse training
     signal, or profile-specific constraints;
  2. **reward design**, so that the risk effect transfers out of sample (a stronger or
     longer-horizon risk measure);
  3. **the inherited over-trading** (about 15–30 a year), which still dominates the cost drag.

## 9. Limitations

- **Coverage:** one λ pair, so nothing about intermediate values or the λ–risk curve;
  one market history; five seeds.
- **Evidence:** validation-only, in a mostly low-volatility period. The in-sample results are
  where the policies were optimised.
- **Design:** the constant profile input carries no information. E5's policies are not
  investor-specific by design. The synthetic-profile limitations of E1–E4 still apply to any
  extension.
- **Reward:** the risk measure is per-step realised variance. Drawdown is not targeted, which
  may explain why drawdowns did not improve on validation.
- **Inherited:** E0's over-trading and its cost drag.
- **Test period:** unmeasured, by design.

## 10. Recommendation

**Do not build new conditioning architectures yet.** The most informative next experiment
(prespecified before running, with a new ID) is a **λ dose–response with longer or diversified
training**:
- λ ∈ {0, 3, 9}, seeds 42–46;
- optionally an extended budget, if throughput allows.

**Purposes:**
1. check that risk falls monotonically in λ;
2. test whether more training makes the validation effect larger than seed variation.

**How to read the outcome:**

| Outcome | Next step |
| --- | --- |
| The effect becomes robust out of sample | Return to profile conditioning (E4), with many more profile draws per run or profile-specific constraints |
| It stays weak | Revisit the reward's risk measure (for example, drawdown or longer-horizon variance) and the turnover problem first |
