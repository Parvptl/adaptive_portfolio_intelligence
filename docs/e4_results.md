# E4 results: profile-dependent reward PPO (EXP-012)

> **Status (2026-11-03):** complete on the training and validation splits.
> - **Methodology:** `docs/e4_profile_reward.md` (D-088), fixed before training.
> - **Pipeline check:** EXP-011 (not a result).
> - **Test period:** sealed. Out-of-sample test performance is **unmeasured**.
> - **Research only;** simulated backtests; not financial advice. The profiles are synthetic.
> - **Traceability:** every number below is read from the verified outputs listed in §2.

## 1. Executive summary

**What E4 tested:** whether making the PPO reward depend on the investor profile produces
meaningful, financially interpretable personalisation.
- The reward is the base log-growth reward minus a variance penalty.
- The penalty's strength is set by the investor's risk aversion γ = 1 + 9·(1 − min(RT, RC)).
- Everything else is identical to E1.

**What it found:**
1. **The reward was implemented and applied as specified:**
   - every reward-integrity test passed;
   - E0 reproduced EXP-006 exactly;
   - 50 of 50 comparability checks passed on each split.
2. **No meaningful personalisation emerged:**
   - **size:** profile-driven allocation differences stayed small. The within-set D_w median
     was 0.0109, against 0.0115 for E1, and the extreme-profile contrast was 0.009–0.046. Both
     are far below seed-to-seed variation (0.118).
   - **direction:** it was the opposite of the intended one. More risk-accepting profiles
     received *less* equity and *lower* volatility.
   - **specificity:** the reward-irrelevant dimensions (horizon, liquidity, growth) moved the
     allocation about as much as risk tolerance and capacity did.
3. **Average risk level:** in-sample (training years), E4 learned a lower-risk policy than E1
   on average: volatility 2.6 pp lower, maximum drawdown 8.9 pp better, net Sharpe +0.215, all
   in 5 of 5 seeds. **This did not carry over to validation**, where E4 and E1 were
   indistinguishable (Sharpe difference +0.004 ± 0.043).
4. **Performance:** validation performance did not improve beyond seed noise. Every E4
   main-arm policy remained below all three baselines.
   - One held-out-arm seed (s44) exceeded buy-and-hold (1.355) in all 65 of its profile
     episodes, and equal-weight (1.470) in 8; its maximum was 1.499.
   - No episode reached inverse volatility (1.754).
   - This is a single seed, not a robust result.
5. **Verdicts on the prespecified hypotheses:**

   | Verdict | Hypotheses |
   | --- | --- |
   | Not supported | H2 (direction), H3 (risk), H7 (effect beyond seed variation) |
   | Partially supported | H1 (stronger sensitivity than E1), H6 (unseen combinations) |
   | Supported | H4 (not via turnover), H5 (seed stability) |

**Conclusion:**
- **Not shown:** personalisation, or improved financial or risk performance on validation.
- **Partly addressed:** the EXP-010 limitation (the reward ignored the profile) was addressed
  in the objective, but not in the learned behaviour.

## 2. Records

**Commits:**
- `82bca2e`: implementation and methodology;
- `7903f6c`: figures module.

**Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`.

| Item | Identifier |
| --- | --- |
| E4 main runs (seeds 42–46) | 7897e4dbc0b75d35, ef0471726f4796b3, e318b70ae6f64a16, 7c1a9c28b4c9561a, 35f1a7760f9aaf33 |
| E4 held-out runs (seeds 42–46) | 66df7dc70477edba, eac21893088eef47, 1239366219c2124e, ca3d5abb5214be89, b78c9c9236689f31 |
| E4 evaluations | train `9470b1719f6f9ec7` (250.0 s), validation `948eb21380278b03` (81.6 s); both VERIFIED, clean commit `82bca2e` |
| E1 control (EXP-010) | train `93cdfece7bca1f77`, validation `6be9dce1b006008b` (re-verified) |
| Comparisons (H1–H7, paired differences) | validation `2b55a054fcf0a51f`, train `7982b02a83f54dcf`; both VERIFIED |
| Figures | `reports/figures/e4_validation/` (git-ignored; source-hash sidecars) |

**Training:**
- 10 of 10 runs completed: 100,352 timesteps and 202 episodes each; 87.0–89.6 s each; one torch
  thread; 06:58–07:14 UTC.
- No run failed.

## 3. Reward (as implemented)

```text
r_E4,k(U) = r_base,k − (λ(U)/2) · Σ_{t ∈ (d_k, d_{k+1}]} net_return_t²
λ(U)      = γ(U) − 1 = 9 · (1 − min(RT, RC))       ∈ [0, 9]
```

| Term | Meaning |
| --- | --- |
| r_base | The D-064 log growth after costs |
| net_return_t | The ledger's daily net return (after the 15 bps costs) |
| γ | Relative risk aversion: 1 (log utility, E1's objective) to 10 |

Horizon, liquidity and growth preference are not in the reward (D-088). They are negative
controls.

## 4. Financial results (centre profile a = 0.5, λ = 4.5; medians over seeds 42–46)

### Validation 2017–2019 (unseen market period)

| Arm | Net Sharpe (range) | Net cum. return | Net vol | Net max DD | Cost drag | Turnover / yr | Target equity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Equal weight monthly | 1.470 | 28.81% | 5.93% | −10.42% | 0.32 pp | 0.22 | — |
| Buy and hold | 1.355 | 27.96% | 6.28% | −11.49% | 0.19 pp | 0.00 | — |
| Inverse volatility | 1.754 | 26.37% | 4.56% | −7.58% | 0.63 pp | 0.78 | — |
| E0 existing PPO | 0.635 (0.253 to 1.149) | 10.60% | 5.61% | −9.24% | 8.40 pp | 15.9 | 38.6% |
| E1 profile, D-064 reward | 0.534 (−0.149 to 1.007) | 5.47% | 5.22% | −7.52% | 10.94 pp | 19.4 | 20.8% |
| **E4** profile reward | **0.601 (−0.166 to 1.026)** | 6.68% | 5.16% | −7.49% | 11.19 pp | 19.9 | 25.3% |
| E3 held-out, D-064 | 0.311 (−0.007 to 1.157) | 3.80% | 5.08% | −9.34% | 9.27 pp | 19.6 | 27.8% |
| **E4H** held-out, profile reward | 0.184 (−0.044 to 1.442) | 2.27% | 4.92% | −9.43% | 9.98 pp | 19.9 | 33.1% |

E4 per seed (validation net Sharpe): −0.166, 0.639, 1.026, 0.601, 0.340.

### Training 2007–2016 (in-sample)

| Arm | Net Sharpe | Net vol | Net max DD | Turnover / yr |
| --- | --- | --- | --- | --- |
| E0 | 1.114 | 13.28% | −17.32% | 27.7 |
| E1 | 1.200 | 13.14% | −20.30% | 27.3 |
| **E4** | 1.349 | 10.67% | −11.70% | 26.8 |
| E4H | 1.349 | 10.72% | −8.56% | 23.3 |
| Baselines | 0.516–0.843 | 7.06–10.93% | −18.64% to −28.51% | 0–0.84 |

### Paired seed differences (centre profile; mean ± SD; 95% t-interval, descriptive; seeds with E4 higher)

| Comparison | Metric | Validation | Training |
| --- | --- | --- | --- |
| E4 − E1 | Net Sharpe | +0.004 ± 0.043 [−0.049, 0.058]; 2/5 | **+0.215 ± 0.136 [0.046, 0.384]; 5/5** |
| E4 − E1 | Net volatility | +0.16 pp ± 0.46 [−0.42, 0.74]; 2/5 | **−2.60 pp ± 0.53 [−3.26, −1.95]; 0/5** |
| E4 − E1 | Net max DD (+ = shallower) | −0.97 pp ± 0.85; 1/5 | **+8.92 pp ± 3.15 [5.01, 12.84]; 5/5** |
| E4 − E1 | Turnover / yr | +0.99 ± 2.06; 3/5 | −0.64 ± 0.53; 0/5 |
| E4 − E0 | Net Sharpe | −0.163 ± 0.715 [−1.051, 0.725]; 3/5 | +0.139 ± 0.183 [−0.089, 0.367]; 4/5 |
| E4 − E0 | Target equity | −9.6 pp ± 2.7; 0/5 | −11.2 pp ± 4.7; 0/5 |

**Reading:**
- **In-sample**, the average penalty made E4 consistently less volatile, with shallower
  drawdowns, than E1. The t-intervals exclude zero, but five seeds share one market history,
  so this is descriptive.
- **On validation**, none of these differences remains. Every E4 − E1 interval covers zero.
- **Against E0**, E4 is not distinguishable on validation Sharpe. Its Sharpe range is wider
  than any difference.

## 5. Personalisation (validation; state-matched unless stated)

| Measure | E1 (EXP-010) | E4 |
| --- | --- | --- |
| Within-set D_w, `in_distribution`, median (range) | 0.0115 (0.0065–0.0165) | 0.0109 (0.0065–0.0191) |
| E4 > E1 per seed (H1) | — | 4 of 5; median ratio 1.31 |
| Seed-to-seed D_w at the centre profile | 0.122 | 0.118 |
| D_w, a = 0 vs a = 1 (RT = RC = 0 vs 1) | — | 0.009–0.046 (median 0.026) |
| E2: D_w, correct vs neutral profile, mean | 0.005–0.012 per seed | 0.0089 |
| E2: D_w, correct vs shuffled profile, mean | 0.007–0.018 per seed | 0.0129 |

**Direction (Spearman across the 32 profiles, per seed 42–46):**
- ρ(a, target equity) = −0.20, −0.65, −0.74, −0.56, −0.77;
- ρ(a, on-path volatility) = −0.38, −0.44, −0.74, +0.49, −0.80;
- high-a / low-a tercile volatility ratio 0.91–1.03 (the prespecified expectation was > 1.1).

More risk-accepting profiles thus got slightly **less** equity and lower volatility, the
opposite of the reward's intent. The same sign appears on the training split (ρ(a, volatility)
−0.32 to −0.75 in all five seeds).

**Sweeps** (validation; each dimension from 0 to 1, others 0.5; mean change in target exposure
over seeds):

| Dimension | Equity | Bonds | Max D_w vs centre |
| --- | --- | --- | --- |
| RT (in the reward) | −3.1 pp | +3.4 pp | ≤ 0.017 |
| RC (in the reward) | −2.3 pp | +1.7 pp | ≤ 0.011 |
| H (control) | −2.1 pp | +1.9 pp | ≤ 0.009 |
| L (control) | −1.6 pp | +2.2 pp | ≤ 0.009 |
| G (control) | −2.0 pp | +2.1 pp | ≤ 0.013 |

- **Negative controls:** their median ρ with equity is −0.47 (H) and −0.49 (L); L with gold
  is −0.68.
- **Reading:** the policy reacts to the size of the profile inputs generically. It does not
  isolate the reward-relevant risk acceptance.
- **Interaction:** the RT × RC grid shows equity falling in both directions, with a range of
  about 21–26%. There is no `min`-shaped interaction (figure `e4_equity_rt_rc_grid.png`).

**Training-episode diagnostic** (saved reward components; not a new experiment):
- Within each run, an episode's realised variance is essentially unrelated to its profile's a
  (Spearman, later half of training, −0.26 to +0.15).
- The mean realised variance did fall between the first and last 20 episodes in 9 of 10 runs.
- **Reading:** PPO learned a lower **average** risk level, not a profile-dependent one.

## 6. Generalisation

- **Unseen profile combinations (E4H; the box RT ≥ 0.6, RC ≤ 0.4, i.e. a ≤ 0.4):**
  - validation volatility on the box was below the training-profile volatility in only 2 of 5
    seeds (H6 part 1 failed);
  - the median Sharpe gap was +0.018, within the 0.046 within-seed SD (H6 part 2 held).
  - Because the policy barely uses the profile, this is consistency, not evidence of
    generalisation.
- **Unseen market period:** E4's median net Sharpe falls from 1.349 (training) to 0.601
  (validation). Its in-sample risk advantage over E1 disappears. The market-period gap
  dominates every profile effect.

## 7. Reward-exploitation checks

| Check | Result |
| --- | --- |
| Share of decisions with target cash > 95%, E4 mean (max per episode) | 2.7% (33%) |
| Maximum held weight | E4 0.423, E1 0.425 |
| Mean risky-sleeve HHI | E4 0.552, E1 0.556 |
| Turnover per year (median) | E4 19.75, E1 19.38 |
| Training: mean penalty / mean \|r_base\| per run | 0.88–1.02 |
| Training: episodes with penalty > \|r_base\| | 46–54% |

There was no cash collapse, no extra concentration and no turnover inflation. The penalty was
of the prespecified order, neither negligible nor dominant. No exploitation was found.

## 8. Hypotheses

| | Verdict | Evidence |
| --- | --- | --- |
| H1 stronger sensitivity than E1 | Partially | E4 > E1 in 4/5 seeds, but the median ratio is 1.31 (needed ≥ 2) |
| H2 financially aligned direction | **Not supported** | ρ(a, equity) negative in every seed; the controls H and L respond |
| H3 risk-appropriate exposure | **Not supported** | ρ(a, vol) negative in 4/5 seeds; tercile ratio 0.91–1.03 |
| H4 not via turnover | Supported | Turnover within 1.25 × E1 (19.75 vs 19.38) |
| H5 seed stability | Supported | Same sign in 4/5 seeds; seed-scale D_w 0.118 vs 0.122 |
| H6 unseen combinations | Partially | Sharpe consistent; volatility not lower in the box |
| H7 beyond seed variation | **Not supported** | Contrast 0.026 (median) vs seed scale 0.118 |

## 9. Conclusion

- **What changed relative to E1:** only the reward. The observation, architecture, PPO
  settings, seeds, budget, data, accounting, costs and evaluation are identical, and verified.
- **Training:** 10 of 10 runs (2 arms × seeds 42–46), dataset `8e00568ee2aa4de7`, training
  split 2007–2016.
- **Answer to the research question:** **no.** A profile-dependent risk-aversion reward did not
  produce meaningful, reproducible or financially interpretable personalisation in this setup.
- **Effect on behaviour:** it lowered the policies' **average** in-sample risk. It did not teach
  them to differentiate between investors. Their small profile responses run against the
  intended direction and are not specific to the reward-relevant dimensions.
- **Validation:** no improvement over E1 or E0 beyond seed variation, and all main-arm policies
  remain below the simple baselines.
- **Risk and exploitation:** no reward exploitation was found. In-sample, the risk behaviour
  improved on average, but not per profile, and not out of sample.
- **Did E4 address the EXP-010 limitation?** In the objective, yes: the profile now matters to
  the reward. In the learned policy, no.
- **Further development:** justified only as a **diagnostic**, not by results (§11).

## 10. Limitations

- Synthetic, uniform profiles; there are only 202 profile draws per run (one per episode).
- One market history; five seeds; validation-only evidence, in a mostly low-volatility
  period.
- One prespecified reward formulation (γ range, the `min` rule, a realised-variance penalty).
  This is not a general verdict on profile-dependent rewards.
- The inherited E0 over-trading (about 20× turnover) and its cost drag remain.
- The direction and controls findings are descriptive. The mechanism (§5) is a hypothesis, not
  tested.
- The test period is unmeasured, by design.

## 11. Recommendation for the next experiment

The evidence points to a **learning problem**, not a reward-scale problem: the reward varies
by profile, but the policy does not condition on it. The most informative next step is a
**fixed-profile control** (a new experiment ID, prespecified before running):
- train configuration 4 at constant a = 0 (λ = 9) and at constant a = 1 (λ = 0), seeds 42–46;
- compare their risk on training and validation.

**How to read the outcome:**

| Outcome | Interpretation | Next step |
| --- | --- | --- |
| The two fixed-λ policies differ clearly in risk | PPO can express risk aversion under this reward; the conditioning failed (202 profile samples per run, weak signal through a shared network) | Many more episodes or profile resampling, or profile-specific constraints |
| They do not differ | The reward or budget cannot move PPO's risk level within 100,000 steps | Reconsider the reward scale and horizon, and the over-trading first |

**Not recommended before this control:** architectural extensions (profile encoders, attention,
meta-RL, hierarchical policies). There is no evidence that the network fails to *represent* the
profile; the evidence is that the training signal does not make it *use* the profile.
