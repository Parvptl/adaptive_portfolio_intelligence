# E9 results: turnover-penalty confirmation study (EXP-022)

> **Status (2026-11-04):** complete on the training and validation splits.
> - **Methodology:** `docs/e9_confirmation_protocol.md` (D-093), committed before implementation
>   (`2c714e1`); no amendments. **Pipeline check:** EXP-021 (not a result).
> - **Test period:** sealed. Test performance is **unmeasured**.
> - **Research only;** simulated backtests on one market history; not financial advice.
> - **Traceability:** every number comes from the verified comparison
>   `0e88c06aefaeec31` (§11).

## 1. Executive summary

**Question:** does κ = 0.0015 reproducibly improve validation net Sharpe over κ = 0, or was the
E7/E8 result seed variation?

**Design:**
- **Arms:** E9B (κ = 0) and E9T1 (κ = 0.0015), λ = 0, otherwise exactly E8B/E8T1.
- **Primary population:** **10 new paired seeds (47–56).**
- **Reproduction:** seeds 42–46 retrained and checked against E8/E7.
- **Runs:** 30 full runs of 100,352 timesteps (20 confirmation + 10 reproduction), all completed,
  with no failures or retries. 4 evaluations, all verified.

**Prespecified outcome: Partial confirmation.**
- **Supported:** H1, H2, H3, H5, H6, H7, H8 and H9.
- **Partially supported:** H4 and H10.

**Verified results (validation 2017–2019, primary seeds 47–56, E9T1 − E9B):**
- **Net Sharpe (primary endpoint):**
  - mean **+0.247**, median +0.209;
  - **8 of 10 seeds positive**;
  - bootstrap 95% CI **[0.091, 0.422]**; exact permutation **p = 0.021**;
  - t-interval [0.044, 0.451];
  - medians 0.581 → 0.716.
- **Annualised net return:**
  - mean +1.02 pp (median +1.11);
  - only **6 of 10 seeds positive**; p = 0.066.
  - The bootstrap CI [0.15, 1.93] pp excludes zero, but the t-interval [−0.07, 2.11] does not.
  - Two of the four prespecified H3-style conditions fail, hence **partial**.
- **Mechanism (H5):**
  - **Cost drag:** −2.84 pp (8/10 lower).
  - **Gross return:** essentially unchanged on average (+0.49 pp, CI [−3.3, 4.5]), but it varies a
    lot by seed (SD 6.6 pp).
  - **Net cumulative:** +3.33 pp.
  - **Lower volatility** (−0.70 pp, 8/10) also contributes to the Sharpe gain.
- **Trading:** turnover −5.9 a year (18.1 → 12.5 median; 8/10 lower). In seeds 51 and 55 the
  penalty arm traded slightly *more*.
- **Risk:** volatility and maximum drawdown both improve: drawdown is 1.2 pp shallower, in 8 of 10
  seeds.
- **Composition:**
  - **Cash:** median 31% → 40% (+6.3 pp, 8/10 higher).
  - **Risky HHI:** 0.51 → 0.65 (9/10 higher; bootstrap CI excludes zero).
  - **Guard rails:** both stay inside E8's limits (cash ≤ 40%, HHI ≤ 2/3), but **only just**.
  - **Responsiveness:** kept at 85% (dispersion) and 81% (meaningful changes) of the control's.
- **Reproduction (H9):** seeds 42–46 equal E8 (28 metrics) and E7 (26 metrics) exactly on both
  splits, maximum difference 0.0. E0 reproduces EXP-006.
- **Baselines:** the medians remain far below all three (validation Sharpe 1.355 / 1.470 /
  1.754).

**Interpretation:**
- The moderate penalty's Sharpe advantage **reproduced on ten new seeds**, with a similar size:
  +0.247 here vs +0.232 in E7/E8.
- At the seed level on this market history it is unlikely to be seed noise alone.
- It is mainly a **cost and volatility effect, not better allocation**, and it comes with a
  measurable shift towards cash and concentration.

**Main limitation:**
- **One market history:** all seeds share the 2017–2019 validation period, so this is evidence
  about training-seed variability, not about other markets or periods.
- **No test-period or walk-forward evidence.**

**Recommended next step:** a separately approved walk-forward study (§10).

## 2. Protocol

| Item | Value |
| --- | --- |
| Decision / experiments | D-093 (Provisional (delegated)); EXP-021 pipeline check; EXP-022 full experiment |
| Arms | E9B κ = 0, E9T1 κ = 0.0015; λ = 0; configuration 4 (lr 1e-4, n_steps 512, ent_coef 0); constant profile 0.5; `configs/confirmation_k{0,1}.yaml` |
| Seeds | Primary 47–56 (extension seeds, D-093); reproduction 42–46; pooled 42–56 secondary |
| Budget | 100,352 timesteps per run (configured 100,000; identical across arms) |
| Data | Dataset `8e00568ee2aa4de7`, features `a79347e37e653703`; training decisions 2007-07-05 → 2016-12-30; validation 2017-01-03 → 2019-12-31; test 2020– sealed |
| Evaluation | Deterministic policy actions; the unchanged ledger and 15 bps costs; baselines in the same evaluation |
| Statistics | Seed-level paired differences; percentile bootstrap (10,000, seed 20261104); exact sign-flip permutation test (2¹⁰); t-interval as sensitivity; no practical Sharpe threshold exists in the repository |

**Deviation from the requested 20 runs** (prespecified in protocol §3): 10 extra reproduction
runs (seeds 42–46).
- **Why:** E9 changes shared code (extension seeds), so reproduction had to be re-shown at the E9
  commit.
- **Use:** they are never part of the confirmation sample.

## 3. Arm-level results (validation; medians over the primary seeds 47–56)

| Metric | Better | E9B (κ 0) | E9T1 (κ 0.0015) |
| --- | --- | --- | --- |
| Net Sharpe | higher | 0.581 | 0.716 |
| Annualised net return | higher | 2.90% | 3.89% |
| Gross cumulative return (3 years) | higher | 18.47% | 19.26% |
| Net cumulative return | higher | 8.92% | 12.10% |
| Cost drag (pp, 3 years) | lower | 9.34 | 6.34 |
| Turnover / yr | lower | 18.07 | 12.46 |
| Net volatility (p.a.) | lower | 6.09% | 5.26% |
| Net max drawdown | shallower | −8.25% | −7.03% |
| Mean target cash | context (limit 40%) | 31.2% | 39.9% |
| Risky-sleeve HHI | context (limit 2/3) | 0.515 | 0.649 |
| Allocation dispersion | context (≥ 50% of control) | 0.113 | 0.097 |
| Share of meaningful changes | context (≥ 50% of control) | 0.768 | 0.619 |

**Downside risk / Sortino:** not available from the evaluator (D-076).

## 4. Seed-level results (validation)

| Seed | Sharpe B | Sharpe T1 | Δ | Ann. return B | T1 | Turnover B | T1 | Cost drag B | T1 | Δ gross cum. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 47 | 0.672 | 0.589 | −0.084 | 2.84% | 2.17% | 28.4 | 16.1 | 14.9 | 8.1 | −8.9 pp |
| 48 | 0.552 | 0.508 | −0.044 | 2.96% | 2.26% | 13.4 | 3.8 | 6.8 | 1.9 | −7.1 pp |
| 49 | 0.383 | 0.590 | +0.207 | 1.79% | 2.96% | 18.9 | 12.6 | 9.5 | 6.5 | +0.7 pp |
| 50 | 0.611 | 1.202 | +0.591 | 3.35% | 5.75% | 16.7 | 9.5 | 8.6 | 5.2 | +4.4 pp |
| 51 | 1.087 | 1.114 | +0.027 | 8.33% | 7.78% | 5.5 | 5.9 | 3.2 | 3.4 | −1.7 pp |
| 52 | 0.237 | 0.449 | +0.212 | 1.45% | 2.49% | 26.5 | 22.8 | 13.2 | 11.6 | +1.7 pp |
| 53 | 0.766 | 1.102 | +0.336 | 4.85% | 6.44% | 14.4 | 12.8 | 7.9 | 7.3 | +4.7 pp |
| 54 | 0.409 | 0.463 | +0.054 | 2.42% | 2.24% | 20.6 | 12.3 | 10.5 | 6.2 | −4.9 pp |
| 55 | 0.713 | 1.512 | +0.799 | 4.47% | 8.09% | 17.2 | 18.0 | 9.2 | 10.6 | +13.6 pp |
| 56 | 0.467 | 0.841 | +0.375 | 2.35% | 4.82% | 19.1 | 7.9 | 9.6 | 4.2 | +2.4 pp |

**Seed-level reading:**
- **Sharpe:** the two negative differences (47, 48) are the seeds where the penalty arm's gross
  return fell most.
- **Largest gain (55):** comes from a higher gross return, not from cost savings; that arm
  traded slightly more.

## 5. Paired differences (E9T1 − E9B; primary seeds 47–56, validation)

| Endpoint | Mean | Median | SD | + / − / ties | Bootstrap 95% CI | Permutation p | t 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Net Sharpe** | **+0.247** | +0.209 | 0.285 | 8 / 2 / 0 | **[0.091, 0.422]** | **0.021** | [0.044, 0.451] |
| Ann. net return | +1.02 pp | +1.11 pp | 1.52 pp | 6 / 4 / 0 | [0.15, 1.93] pp | 0.066 | [−0.07, 2.11] pp |
| Gross cumulative return | +0.49 pp | +1.17 pp | 6.60 pp | 6 / 4 / 0 | [−3.25, 4.52] pp | 0.82 | [−4.23, 5.21] pp |
| Net cumulative return | +3.33 pp | +3.46 pp | 5.03 pp | 6 / 4 / 0 | [0.48, 6.36] pp | 0.066 | [−0.26, 6.93] pp |
| Cost drag | −2.84 pp | −3.21 pp | 2.66 pp | 2 / 8 / 0 | [−4.37, −1.22] pp | 0.014 | [−4.74, −0.94] pp |
| Turnover / yr | −5.88 | −6.73 | 4.69 | 2 / 8 / 0 | [−8.56, −3.04] | 0.008 | [−9.24, −2.53] |
| Net volatility | −0.70 pp | −0.82 pp | 0.61 pp | 2 / 8 / 0 | [−1.03, −0.32] pp | 0.012 | [−1.13, −0.26] pp |
| Net max drawdown (+ = shallower) | +1.20 pp | +0.88 pp | 1.77 pp | 8 / 2 / 0 | [0.24, 2.33] pp | 0.041 | [−0.06, 2.47] pp |
| Mean target cash | +6.3 pp | +6.4 pp | 10.7 pp | 8 / 2 / 0 | [−0.2, 12.3] pp | 0.098 | [−1.4, 13.9] pp |
| Risky HHI | +0.105 | +0.076 | 0.157 | 9 / 1 / 0 | [0.012, 0.197] | 0.059 | [−0.007, 0.218] |
| Target equity | −4.8 pp | −4.9 pp | 6.2 pp | 2 / 8 / 0 | [−8.3, −1.0] pp | 0.045 | [−9.2, −0.3] pp |
| Allocation dispersion | −0.015 | −0.009 | 0.021 | 2 / 8 / 0 | [−0.028, −0.003] | 0.064 | [−0.031, −0.000] |
| Share of meaningful changes | −0.177 | −0.203 | 0.221 | 4 / 6 / 0 | [−0.308, −0.052] | 0.035 | [−0.336, −0.019] |

**Reading:** only the net-Sharpe row is the prespecified primary test. The other p-values are
reported for completeness and are not a family of confirmatory tests.

**Training split (primary seeds, descriptive):**
- **Net Sharpe:** Δ −0.032 (5/5 split; CI [−0.108, 0.043]), so there is **no in-sample Sharpe
  difference**.
- **Turnover:** −6.1 a year (9/10 lower).
- **Cost drag:** −60 pp.
- **Gross cumulative return:** −94 pp (9/10 lower).
- **Annualised net return:** −0.94 pp (7/10 lower).
- **Reading:** in-sample, the cost saving was offset by lower gross returns. The validation gain
  does not mirror an in-sample gain.

## 6. Hypotheses

| | Verdict | Evidence (primary, validation) |
| --- | --- | --- |
| H1 turnover | **Supported** | Mean −5.88, CI upper −3.04 < 0, 8/10 lower |
| H2 cost drag | **Supported** | Mean −2.84 pp, CI upper −1.22 pp < 0, 8/10 lower |
| H3 net Sharpe (primary) | **Supported** | Mean +0.247 > 0; CI lower 0.091 > 0; p = 0.021 < 0.05; 8/10 ≥ 7/10 positive |
| H4 net return | **Partially** | Mean +1.02 pp > 0 and CI lower 0.15 pp > 0, but p = 0.066 and only 6/10 positive |
| H5 decomposition | **Supported** | cost drag = gross − net cumulative exactly (max error 1.4e-16); mean cost saving 2.84 pp ≥ mean gross loss (gross change +0.49 pp) |
| H6 risk | **Supported** | Median volatility −0.82 pp; drawdown 0.88 pp shallower |
| H7 composition | **Supported** (narrowly) | E9T1 medians: HHI 0.649 ≤ 0.667; cash 0.399 ≤ 0.40; near-all-cash share 0 |
| H8 responsiveness | **Supported** | Ratios to E9B: dispersion 0.85, meaningful changes 0.81, D_w 0.72 |
| H9 reproduction | **Supported** | 8/8 checks exact (§7) |
| H10 practical utility | **Partially** | H3, H6, H7 and H8 supported, H4 partial |

**Outcome rule (protocol §7):** "Confirmation" requires H3 **and** H4 supported. H4 is partial,
and the mean ΔSharpe > 0 with ≥ 6/10 positive, so the outcome is **Partial confirmation.**

## 7. Historical reproduction (H9) and historical context

| Check | Split | Metrics | Max abs difference |
| --- | --- | --- | --- |
| E9B (42–46) = E8B | validation / train | 28 / 28 | 0.0 / 0.0 |
| E9T1 (42–46) = E8T1 | validation / train | 28 / 28 | 0.0 / 0.0 |
| E9B (42–46) = E7B | validation / train | 26 / 26 | 0.0 / 0.0 |
| E9T1 (42–46) = E7T1 | validation / train | 26 / 26 | 0.0 / 0.0 |

**Also verified:**
- Before training, E8B = E7B = E6L and E8T1 = E7T1 were recomputed from the saved artifacts (26
  metrics, 0.0).
- E0 reproduces EXP-006 in both validation evaluations.

**Historical seeds 42–46 (context only; equal to E8):**
- **Net Sharpe:** Δ mean +0.232 (4/5 positive), bootstrap CI [−0.016, 0.484], permutation
  p = 0.19.
- **Net return:** Δ +1.23 pp.
- **Reading:** the new seeds show a similar mean effect with a tighter interval.

**Pooled 42–56 (secondary; 15 seeds, each once):**
- **Net Sharpe:** Δ +0.242 (12/15), CI [0.109, 0.390], p = 0.004.
- **Net return:** +1.09 pp (10/15), p = 0.015.
- **Status:** labelled secondary; it does not change the outcome.

## 8. Baselines (same verified validation evaluation, `8d43b775c997dea9`; separate from the paired test)

| Strategy | Type | Net Sharpe | Ann. net return | Net vol | Max DD | Turnover / yr | Cost drag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `buy_and_hold_equal_weight` | static (funded once, never rebalanced) | 1.355 | 8.60% | 6.28% | −11.49% | 0 | 0.19 pp |
| `equal_weight_monthly` | fixed weights, monthly rebalance | 1.470 | 8.84% | 5.93% | −10.42% | 0.22 | 0.32 pp |
| `inverse_volatility_monthly` | dynamic (63-session vol), monthly | 1.754 | 8.15% | 4.56% | −7.58% | 0.78 | 0.63 pp |
| E9B / E9T1 median (seeds 47–56) | PPO | 0.581 / 0.716 | 2.90% / 3.89% | 6.09% / 5.26% | −8.25% / −7.03% | 18.1 / 12.5 | 9.3 / 6.3 pp |

**Comparability:** all strategies share the window, the 15 bps costs (initial funding charged),
the net-Sharpe definition and the long-only universe.

**Reading:**
- One E9T1 seed (55: 1.512) exceeds two baselines; no PPO run exceeds inverse volatility.
- **PPO remains well below the simple baselines**, and still trades about 16× more than the most
  active one.

## 9. Interpretation and limitations

**Interpretation:**
- **Advantage reproduced:** on ten new seeds the moderate penalty again raised validation net
  Sharpe by about 0.25 (8/10 seeds). At this seed level it is unlikely to be seed noise alone.
- **Costs:** they fell consistently.
- **Gross return:** on average it did not change, but it moved by several pp in either direction
  per seed, and that drives the dispersion of the net effect.
- **Sharpe vs return:** the Sharpe gain is larger and more consistent than the return gain,
  because the penalty also lowers volatility.
- **Composition:** the policy moves towards cash (+6 pp) and fewer funds (HHI +0.1) while staying
  responsive. Both guard rails pass only narrowly.
- **Baselines:** the PPO approach remains far below them.
- **Research value:** this supports keeping κ = 0.0015 as the default candidate for further
  research, and testing whether the effect holds across periods.

**Limitations:**
- **One market history:** the ten seeds share it, so they are not independent markets, and the
  intervals describe training-seed variability only.
- **Validation-only inference:** a mostly calm period; no test-period or walk-forward evidence.
- **Secondary endpoints:** they have no multiplicity correction and are descriptive.
- **Guard rails:** E8's judgement-call limits, which E9T1 passes only narrowly.
- **No practical Sharpe threshold** was ever established, so the size (+0.25) is not judged
  against one.
- **Unchanged limits:** downside risk is unavailable; the profile input is constant (no
  personalisation).
- **In-sample:** there is no Sharpe gain in-sample, which is unexplained.

## 10. Recommended next step (not started; needs its own protocol and a team decision)

1. **Primary: a walk-forward evaluation of κ = 0 vs κ = 0.0015.**
   - Rolling training and validation folds inside the pre-2020 data.
   - Purpose: test whether the advantage holds across market periods.
   - It changes the split design, so it needs a team decision (CLAUDE.md, D-084).
2. **Alternative:** a penalty that spares meaningful trades (a no-trade band), compared against
   κ = 0.0015 under this E9 protocol.

The test period stays sealed. A single pre-registered test run (D-084 §7) would come only after a
candidate is fixed under a written rule.

## 11. Reproducibility

| Item | Identifier |
| --- | --- |
| Commits | Protocol `2c714e1`; implementation `43a23a0` (clean; all runs and evaluations); results — this report's commit |
| Configs | `configs/confirmation_k0.yaml`, `configs/confirmation_k1.yaml` |
| E9B runs, seeds 42–56 | f4de11ce50d8ef32, 4d0a3445ec6bf375, 28ff836653dab287, b8b79594af983076, 88c11f037bfc3364, 7d2e699c755f9eb1, 1227063d0c11b705, f66af034c0945ae6, cf4b18899ec2b5ae, b152355038d76071, 5d68fcc82bfc4b7a, 213b36145ed47c27, 4b90760d4045982d, df6ba58d7d97d9fb, 1abdb7c78fe82922 |
| E9T1 runs, seeds 42–56 | edc4f762208af37c, 696f4925b202aeb3, e41be0a27e296e9e, c57c4ebecf78d7d2, 8277412b87770214, 54e0779a1f39a20b, 659d9bdaa1a82e96, 504af839878df286, 9f6413d5281b7883, c975f3752224e280, a0545c6eac0c53b1, d4acd740faf23324, 8bdcde23fa8d8616, f92a6239b980298e, ec9bdd126ec520a0 |
| Training | 30 of 30 `full` runs: 100,352 timesteps and 202 episodes each; 84–292 s each (two control runs at 217–292 s at the start, probably contention); 2026-11-04 00:57–01:48 UTC; 0 failures, 0 retries, 0 excluded |
| Evaluations (VERIFIED; 75 of 75 comparability checks each) | E9B train `eb223d99e1549f1d`, validation `8d43b775c997dea9`; E9T1 train `6bee3b06503e0eb0`, validation `68a3342d03910626` |
| Comparison (VERIFIED, D-093 v1) | `data/processed/confirmation_comparisons/0e88c06aefaeec31` |
| Analysis command | `python scripts/profile_experiment.py --dataset-dir data/processed/8e00568ee2aa4de7 --experiment-config configs/confirmation_k0.yaml compare-confirm --validation <E9B val> <E9T1 val> --train <E9B train> <E9T1 train> --reproduce-validation <E8B> <E8T1> <E7B> <E7T1> --reproduce-train <...> --execute` |
| Bootstrap | 10,000 resamples, `numpy.random.default_rng(20261104)` |
| Figures (git-ignored; source-hash sidecars) | `reports/figures/e9/e9_paired_seeds.png`, `e9_primary_difference.png`, `e9_decomposition.png` |
