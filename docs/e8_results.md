# E8 results: turnover-penalty refinement and allocation responsiveness (EXP-020)

> **Status (2026-11-04):** complete on the training and validation splits.
> - **Methodology:** `docs/e8_turnover_refinement.md` (D-092), fixed before implementation and
>   training. **Pipeline check:** EXP-019 (not a result).
> - **Test period:** sealed. Test performance is **unmeasured**.
> - **Research only;** simulated backtests on one market history; not financial advice.
> - **Traceability:** every number below comes from the verified outputs in §5.
> - **E7T2 (κ = 0.0075):** a **prior experiment** (EXP-018), shown only for reference.

## 1. Executive summary

**Prespecified outcome: C, "no reliable improvement."**
- **Supported:** H1, H2, H3, H5 and H8.
- **Partially supported:** H6 and H7.
- **Not supported:** H4 and H9.
- **Neither refined penalty (κ = 0.003, 0.0045) is a better trade-off than the moderate κ =
  0.0015.** Both save costs, but they lose responsiveness, concentrate the portfolio and lower
  validation net performance against κ = 0.0015.

**Verified results (validation 2017–2019, medians over seeds 42–46):**
1. **Trading and costs fall steadily with κ, and the fall transfers.**
   - **Turnover:** 17.5 → 15.3 → 8.0 → 4.2 a year (κ = 0 → 0.0015 → 0.003 → 0.0045).
   - **Cost drag:** 9.6 → 7.6 → 4.1 → 2.2 pp.
   - Both refined arms trade less than κ = 0.0015 in every seed.
2. **The policy tips into a concentrated, cash-heavy portfolio between κ = 0.0015 and 0.003.**
   - **Mean target cash:** 25% → 27% → 53% → 57%.
   - **Risky-sleeve HHI:** 0.47 → 0.51 → 0.83 → 0.87.
   - Both refined arms fail the prespecified concentration and cash limits (HHI ≤ 2/3; cash
     ≤ 40%).
3. **Meaningful reallocations become rare.**
   - **Share of decisions moving at least 5% of the portfolio:** 0.70 → 0.55 → 0.31 → 0.30.
   - Both refined arms are below 50% of the control's share.
   - **Allocation dispersion:** falls to 64% (T2) and 43% (T3) of the control's; T3 is below the
     50% guard rail.
4. **Net performance does not improve over κ = 0.0015.**
   - **Validation net Sharpe:** 0.512 / 0.788 / 0.390 / 0.607, and annualised net return
     3.04% / 4.06% / 1.71% / 2.89%.
   - **Against κ = 0.0015:** both refined arms are lower in 4 of 5 seeds on Sharpe and on return.
5. **Cost savings are offset by lower gross returns.**
   - **Gross cumulative return:** 17.3% / 17.6% / 10.9% / 11.0%.
   - **Paired against κ = 0.0015:** about −7 pp of gross return against about +3–4 pp of saved
     costs.
6. **Risk is lower, not higher.**
   - **Volatility:** 5.55% / 5.57% / 5.26% / 4.66%.
   - **Maximum drawdown:** −8.5% / −7.8% / −6.8% / −5.2%.
7. **Reproduction is exact** (H8).
   - E8B equals E7B and E6L, and E8T1 equals E7T1, on both splits: 26 per-seed metrics each,
     maximum difference 0.0.
   - E0 reproduces EXP-006 in every evaluation.
8. **Every arm remains below every simple baseline** (validation Sharpe 1.355 / 1.470 / 1.754).

**Interpretation:**
- The moderate penalty (κ = the cost rate) stays the most defensible setting.
- Raising κ beyond it buys cost savings mainly by holding cash and fewer funds, which is what E8
  set out to rule out.
- Validation Sharpe is **not monotone in κ** (0.79 at κ = 0.0015, 0.39 at 0.003, 0.61 at 0.0045,
  0.69 for E7's 0.0075). Differences between κ values are of the same size as seed-to-seed
  variation, so the moderate arm's own advantage over κ = 0 is uncertain too.

## 2. Research question and motivation

**Question:** can a refined turnover penalty improve the trade-off between transaction-cost
reduction and portfolio responsiveness?

**Motivation (EXP-018):**
- **κ = 0.0015** was balanced.
- **κ = 0.0075** saved far more cost but became near-static and concentrated (57% cash, HHI
  0.93), and was worse in-sample.
- **E7's rule** ignored responsiveness, and its only responsiveness measure (D_w) is path length,
  which a turnover penalty lowers by construction.

## 3. Protocol, decision and hypotheses

- **Protocol:** `docs/e8_turnover_refinement.md`; decision **D-092** (Provisional (delegated));
  criteria `D-092 v1`, fixed before training.
- **Hypotheses H1–H9 and the outcome rule:** see §5–§6 of the protocol. They were applied
  mechanically; §9 below gives the verdicts.
- **New measures** (protocol §4, unit-tested, applied to every arm):
  - `allocation_dispersion`: the mean SD of each target weight across decisions;
  - `share_meaningful_changes`: the share of decisions with ½·Σ|Δw| ≥ 0.05.
  - **E7T2:** it predates these measures, so they are unavailable for it.

## 4. Data, reward and arms

**Data:** dataset `8e00568ee2aa4de7`, feature set `a79347e37e653703`.
- **Training decisions:** 2007-07-05 → 2016-12-30 (496).
- **Validation decisions:** 2017-01-03 → 2019-12-31 (156).
- **Test:** 2020– sealed.

```text
r_k = r_base,k − κ · TN_k          (λ = 0 in every arm)
TN_k = recurring ETF traded notional of step k (cash leg excluded; funding step := 0)
```

**No double counting:**
- **Real cost:** 0.0015·TN stays in r_base through the unchanged ledger.
- **Penalty:** shaping only. In all 20 training runs the logged penalty equals κ × the logged
  traded notional in every episode (H2 accounting part).

| Arm | κ | Role |
| --- | --- | --- |
| E8B | 0 | Control (= E6L = E7B) |
| E8T1 | 0.0015 | Moderate reference (= E7T1) |
| E8T2 | 0.003 | Intermediate (2× the cost rate) |
| E8T3 | 0.0045 | Upper intermediate (3× the cost rate) |
| *E7T2* | *0.0075* | *Prior experiment (EXP-018); not retrained* |

## 5. Training details and verification

**Commits:**
- **implementation:** `d4732b0` (clean; all runs and evaluations);
- **results:** this report's commit.

| Item | Identifier |
| --- | --- |
| E8B runs (seeds 42–46) | 59225e1317bec444, dbf5af2a86ee11e3, 2fb9d50ca07b8380, 422fdbb39228ad29, d7d4d82eaa61bcfc |
| E8T1 runs | e7a73c6cc0776fad, 988b4ac83e068310, 1e3c9a8f12536360, cf41e27fea2260c2, 185abc25e683e2e5 |
| E8T2 runs | c106ceb52b13fbf3, 3b99bcf2a5549b00, ad0fadca801a8984, fc5ffd02759c917e, 4d4259171cde395d |
| E8T3 runs | 9bdaf17e23afe25b, 3b9bdd292a98c060, 1fda783521b56a97, 224a5b40e81795c5, 5027d0dd22bddb88 |
| Training | 20 of 20 `full` runs: 100,352 timesteps and 202 episodes each; 88–357 s each (three E8T3 runs took 311–357 s, probably CPU contention; training is deterministic); 2026-11-03 21:20–22:03 UTC; **0 failures, 0 retries** |
| Evaluations (all VERIFIED; 25 of 25 comparability checks each) | E8B train `a931ec8d25ad4828`, validation `64d6b16103588285`; E8T1 `bd40c7c961253661`, `354fed8fdf2898ee`; E8T2 `7ebde559b75547a2`, `7a37c5a8b1f723d6`; E8T3 `da7887bdde94e343`, `cfe64b5b5a1f506f` |
| Comparison (VERIFIED, criteria D-092 v1) | `data/processed/turnover_refine_comparisons/2a4d574cd9c95bbc`; references E1, E4, E6H; historical E7T2 (`27223e4c92aa897e`, `a99a9a7ee29bc750`) |
| Figures (git-ignored; source-hash sidecars) | `reports/figures/e8/e8_metrics_vs_kappa.png`, `e8_responsiveness_vs_kappa.png`, `e8_seed_comparison.png` |

**Training reward components** (mean over the last 50 episodes; range across seeds):
- **base log growth:** 0.50–0.91 in every arm;
- **reward after the penalty:**
  - E8T1: −0.04 to 0.31;
  - E8T2: −0.44 to 0.15;
  - E8T3: −0.69 to 0.02.

## 6. Baseline reproduction (H8)

| Check | Split | Metrics compared | Max abs difference |
| --- | --- | --- | --- |
| E8B = E7B | validation / train | 26 / 26 | 0.0 / 0.0 |
| E8B = E6L | validation / train | 26 / 26 | 0.0 / 0.0 |
| E8T1 = E7T1 | validation / train | 26 / 26 | 0.0 / 0.0 |

**Conclusion:** the controls are identical in data, reward, budget, seeds, evaluation and
accounting. No drift exists to attribute to κ.

## 7. Results by split (medians over seeds)

| Split | Arm | Net Sharpe | Ann. net return | Gross cum. | Net vol | Net max DD | Cost drag | Turnover / yr | Equity | Bonds | Cash | Risky HHI | D_w | Dispersion | Meaningful share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Validation | E8B | 0.512 | 3.04% | 17.33% | 5.55% | −8.51% | 9.64 pp | 17.5 | 17.8% | 56.4% | 25.0% | 0.47 | 0.060 | 0.110 | 0.70 |
| Validation | E8T1 | **0.788** | **4.06%** | 17.62% | 5.57% | −7.83% | 7.63 pp | 15.3 | 8.1% | 47.6% | 27.0% | 0.51 | 0.045 | 0.095 | 0.55 |
| Validation | E8T2 | 0.390 | 1.71% | 10.85% | 5.26% | −6.77% | 4.05 pp | 8.0 | 5.2% | 38.3% | 52.9% | 0.83 | 0.027 | 0.070 | 0.31 |
| Validation | E8T3 | 0.607 | 2.89% | 10.96% | 4.66% | −5.16% | 2.15 pp | 4.2 | 3.3% | 39.2% | 56.6% | 0.87 | 0.018 | 0.047 | 0.30 |
| *Validation* | *E7T2 (prior)* | *0.691* | *3.73%* | *13.28%* | *4.55%* | *−5.18%* | *1.36 pp* | *2.6* | *2.5%* | *39.4%* | *57.1%* | *0.93* | *0.010* | *n/a* | *n/a* |
| Training | E8B | 1.267 | 17.40% | 542% | 13.38% | −16.78% | 192.8 pp | 25.4 | 28.2% | 40.7% | 21.8% | 0.45 | 0.080 | 0.145 | 0.86 |
| Training | E8T1 | 1.310 | 16.28% | 477% | 12.10% | −19.29% | 148.3 pp | 21.2 | 17.0% | 39.0% | 27.5% | 0.48 | 0.063 | 0.136 | 0.73 |
| Training | E8T2 | 1.346 | 16.74% | 434% | 11.28% | −16.85% | 114.7 pp | 17.8 | 14.8% | 36.9% | 40.8% | 0.64 | 0.055 | 0.130 | 0.65 |
| Training | E8T3 | 1.281 | 14.33% | 331% | 11.83% | −13.09% | 69.7 pp | 11.5 | 11.0% | 32.8% | 47.5% | 0.66 | 0.038 | 0.119 | 0.45 |
| *Training* | *E7T2 (prior)* | *1.026* | *12.37%* | *241%* | *11.14%* | *−14.66%* | *31.7 pp* | *7.5* | *10.5%* | *33.4%* | *49.8%* | *0.75* | *0.026* | *n/a* | *n/a* |

**Notes:**
- **Downside risk / Sortino:** not available from the evaluator (D-076).
- **Near-all-cash share:** 0 for every arm on both splits.

## 8. Paired seed comparisons (validation unless stated; mean, median; seeds where higher)

**Reading:** 95% t-intervals are descriptive. The five seeds share one market history, so these
are **not** significance tests.

| Metric | T1 − B | T2 − B | T3 − B | T2 − T1 | T3 − T1 | T3 − T2 |
| --- | --- | --- | --- | --- | --- | --- |
| Net Sharpe | +0.232, +0.211; 4/5 | +0.015, −0.095; 2/5 | +0.185, +0.150; 4/5 | **−0.218, −0.306; 1/5** [−0.571, 0.135] | **−0.048, −0.205; 1/5** [−0.455, 0.359] | +0.170, +0.245; 4/5 |
| Ann. net return | +1.23, +1.25 pp; 4/5 | −0.12, −0.50 pp; 2/5 | +0.53, +0.15 pp; 4/5 | −1.35, −1.75 pp; 1/5 | −0.71, −1.41 pp; 1/5 | +0.64, +0.96 pp; 4/5 |
| Gross cum. return | −0.05, −0.16 pp; 2/5 | −7.52, −6.48 pp; 0/5 | −6.62, −5.79 pp; 0/5 | −7.47, −6.58 pp; 0/5 | −6.57, −8.44 pp; 1/5 | +0.90, +1.85 pp; 4/5 |
| Cost drag | −3.90, −3.91 pp; 0/5 | −7.05, −5.50 pp; 0/5 | −8.16, −7.10 pp; 0/5 | −3.15, −3.57 pp; 0/5 | −4.26, −4.72 pp; 0/5 | −1.10, −1.39 pp; 1/5 |
| Turnover / yr | −8.0, −7.9; 0/5 | −13.7, −11.0; 0/5 | −16.0, −13.1; 0/5 | −5.7, −7.3; 0/5 | −8.0, −7.9; 0/5 | −2.4, −2.9; 1/5 |
| Net volatility | −0.22, −0.14 pp; 1/5 | −0.74, −0.97 pp; 2/5 | −1.03, −1.00 pp; 0/5 | −0.52, −0.83 pp; 2/5 | −0.81, −1.06 pp; 0/5 | −0.29, −0.49 pp; 1/5 |
| Max DD (+ = shallower) | +1.06, +1.59 pp; 4/5 | +1.01, +0.81 pp; 4/5 | +1.51, +1.56 pp; 4/5 | −0.05, −0.19 pp; 2/5 | +0.45, +1.05 pp; 4/5 | +0.50, +0.38 pp; 4/5 |
| Target cash | +8.1, +6.7 pp; 4/5 | +19.9, +21.1 pp; 5/5 | +19.1, +17.7 pp; 5/5 | +11.8, +7.5 pp; 5/5 | +10.9, +7.9 pp; 5/5 | −0.9, +1.3 pp; 4/5 |
| Risky HHI | +0.11, +0.06; 5/5 | +0.25, +0.29; 5/5 | +0.26, +0.16; 5/5 | +0.14, +0.09; 5/5 | +0.14, +0.09; 5/5 | +0.01, +0.02; 4/5 |
| Dispersion | −0.019; 0/5 | −0.038; 0/5 | −0.051; 0/5 | −0.019; 0/5 | −0.032; 0/5 | −0.013; 1/5 |
| Meaningful share | −0.22; 0/5 | −0.39; 0/5 | −0.47; 0/5 | −0.17; 0/5 | −0.25; 0/5 | −0.09; 1/5 |

**Training:**
- **Turnover:** lower than T1 in 5/5 seeds for both arms (T2 −4.8, T3 −9.2).
- **Net Sharpe vs B:** T2 median −0.005 (2/5), T3 +0.070 (3/5). Unlike E7T2 (−0.30, 0/5), the
  refined arms are not worse in-sample.
- **Return vs T1:** T3 is lower in 5/5 seeds (−1.9 pp).

**Seed variation:**
- **Within-arm seed SD of validation turnover:** 2.2–7.0 (median 4.2).
- **Within-arm seed SD of validation net Sharpe:** 0.08–0.38.

## 9. Hypotheses

| | Verdict | Evidence |
| --- | --- | --- |
| H1 turnover response | **Supported** | Medians strictly decreasing on both splits; on training, T2 < T1 and T3 < T2 in 5/5 seeds |
| H2 cost reduction | **Supported** | Validation cost-drag medians strictly decreasing; T2 < T1 in 5/5 and T3 < T2 in 4/5 seeds; penalty logging exact in all 20 runs |
| H3 validation transfer | **Supported** | Both refined arms below T1 on turnover and cost drag in 5/5 seeds. Validation relative reductions vs B (63% / 76%) exceed the training ones (48% / 62%) |
| H4 net performance vs T1 | **Not supported** | Median Sharpe −0.31 (T2) and −0.20 (T3); median return −1.75 and −1.41 pp |
| H5 risk preservation vs T1 | **Supported** | Volatility lower (−0.83 / −1.06 pp); drawdown not deeper (+0.19 / −1.05 pp deepening) |
| H6 responsiveness | **Partially** | D_w ≥ 25% of B for both (44% / 30%). Dispersion: T2 64% (pass), T3 43% (fail). Meaningful share 44% / 43% of B (both fail) |
| H7 concentration and cash | **Partially** | HHI 0.83 / 0.87 (> 2/3, fail); cash 53% / 57% (> 40%, fail); near-all-cash share 0 (pass) |
| H8 reproducibility | **Supported** | §6 |
| H9 practical utility | **Not supported** | Cost-drag reduction vs T1 (3.6 / 4.7 pp) and turnover reduction (5.7 / 8.0 > SD 4.2) pass, but neither arm keeps H6 and H7 |

**Outcome rule:**
- **Arm status:** both refined arms are cost-efficient, but neither keeps activity (H6 + H7) nor
  performance (H4 + H5).
- **Result:** **C, no reliable improvement.**

## 10. Analysis

**Turnover and cost:**
- The penalty is a precise, transferable trading lever: costs fall with κ in every seed.
- **Seed 43 is the one exception:** its T3 turnover (12.0) slightly exceeds its T2 (11.5).

**Sharpe and return:**
- Validation Sharpe is non-monotone in κ, and its per-seed responses disagree.
- **Seed 42:** rises steadily (−0.03 → 0.64).
- **Seed 44 still behaves differently:** its control is the best single policy in E8 (0.946),
  and every penalty lowers it, monotonically (0.76 → 0.65 → 0.53).
- **κ = 0.003:** the weakest arm on validation (1/5 seeds above T1). κ = 0.0045 recovers part of
  it (T3 − T2: +0.17 in 4/5).
- Both refined arms beat T1 in only one seed.
- **Overall:** this pattern looks like noise around a flat-to-negative response, not a usable
  optimum.

**Do cost savings explain the net changes?**
- **κ = 0 → 0.0015:** yes. Gross return is unchanged and costs fall by 3.9 pp.
- **κ = 0.0015 → 0.003 / 0.0045:** no. Costs fall another 3.2–4.3 pp, but gross return falls by
  about 7 pp, so net return falls.
- **Why:** the extra penalty changes *what* is held (cash and fewer funds), not only how often it
  trades.

**Risk:** volatility and drawdowns fall with κ, consistent with more cash. This is lower risk
from lower exposure, not better risk management.

**Responsiveness:**
- **Meaningful changes:** roughly halve between κ = 0.0015 (55% of decisions) and κ = 0.003
  (31%). The upper intermediate penalty does suppress responsiveness.
- **Dispersion:** declines more slowly, so the refined policies still drift between allocations,
  but in fewer and smaller steps.
- **Moderate arm (descriptive, not a hypothesis):** κ = 0.0015 keeps 86% of the control's
  dispersion and 78% of its meaningful-change share.

**Concentration and cash:**
- At κ = 0.003, median cash doubles (27% → 53%) and the risky sleeve concentrates (HHI 0.51 →
  0.83).
- E8T3 is already close to E7T2 (57% cash, HHI 0.87 vs 0.93).
- **The near-static regime begins at about 2× the cost rate, not only at 5×.**

**Transfer:**
- **Trading effects:** they transfer and are larger on validation.
- **Performance effects:** they do not.
  - **In-sample:** the refined arms are roughly neutral on Sharpe.
  - **Validation:** they are worse than T1.

## 11. Comparison with references (validation medians)

| Arm | Net Sharpe | Turnover / yr | Cost drag |
| --- | --- | --- | --- |
| Baselines (buy and hold / EW monthly / inverse vol) | 1.355 / 1.470 / 1.754 | 0 / 0.22 / 0.78 | 0.19 / 0.32 / 0.63 pp |
| E0 existing PPO | 0.635 | 15.9 | 8.4 pp |
| E1 / E4 / E6H | 0.534 / 0.601 / 0.682 | 19.4 / 19.9 / 18.9 | 10.9 / 11.2 / 10.3 pp |
| E8B / E8T1 / E8T2 / E8T3 | 0.512 / **0.788** / 0.390 / 0.607 | 17.5 / 15.3 / 8.0 / 4.2 | 9.6 / 7.6 / 4.1 / 2.2 pp |
| *E7T2 (prior, κ = 0.0075)* | *0.691* | *2.6* | *1.4 pp* |

**No PPO arm approaches the simple baselines.**

## 12. Limitations

- **Data and seeds:** one market history; a calm validation period; five seeds. Sharpe intervals
  are wide, and seed responses disagree.
- **New measures:**
  - the 5% change threshold, the 50% ratios and the HHI and cash limits are judgement calls fixed
    in advance; they are guard rails, not validated definitions of good allocation;
  - they are unavailable for E7T2.
- **Penalty design:** one linear form. It does not distinguish useful from noisy trades, which
  plausibly explains the concentration.
- **Unchanged limits:** downside risk is unavailable; the profile input is constant (no
  personalisation); test performance is unmeasured.

## 13. Conclusion

**Can a refined turnover penalty improve the trade-off between cost reduction and portfolio
responsiveness?** **Not in this experiment.**

**Verified:**
- Raising κ above the cost rate keeps cutting turnover and costs.
- Responsiveness falls with κ, and the portfolio concentrates into cash and few funds, beyond the
  prespecified limits.
- Validation net performance is lower than at the moderate setting.
- Risk is lower only because exposure is lower.

**Interpretation:**
- κ = 0.0015 remains the balanced setting among those tested.
- Its own advantage over κ = 0 (+0.23 Sharpe, 4/5 seeds, interval including zero) is still
  uncertain.
- PPO remains below the simple baselines.

## 14. Recommended next experiment (not started; needs its own protocol and ID)

1. **Primary: a robustness study of the moderate setting.** Compare κ = 0 and κ = 0.0015 with
   more seeds, for example 10 additional seeds, under the same protocol style.
   - **Reason:** the only positive E7/E8 result depends on five seeds with wide intervals.
   - **Also:** walk-forward folds inside the pre-2020 data would further strengthen it. They
     change the split design, so they need a team decision.
2. **Alternative: a penalty that spares meaningful trades**, for example a no-trade band or a
   penalty only on small reallocations, at the moderate scale.
   - **Aim:** keep the cost savings without the cash and concentration shift.

The test period stays sealed until a candidate is selected under a pre-registered rule.
