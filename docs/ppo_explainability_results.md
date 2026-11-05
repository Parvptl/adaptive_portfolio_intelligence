# PPO validation-decision explainability of configuration 4 (EXP-029)

> **Status (2026-11-05):** executed and verified on **validation decisions only** (2017–2019).
> - **Authorisation:** D-097 (execution authorised under R-S; settings Provisional (delegated)).
>   Plan: `docs/explainability_validation_plan.md`; design D-068 (accepted).
> - **Order:** run **before** the single test evaluation, so that no validation look at the test
>   candidate remained planned (policy §7 condition 1). The test period was not read.
> - **Nature of the results:** descriptive associations and one-step decision sensitivities of a
>   simulated backtest. **Not causal; not about returns; not test results; not financial advice.**
> - **Traceability:** every number comes from `data/processed/explainability/86b75ffd1d00783e`
>   (verified; §5).

## 1. What was analysed

- **Policy:** configuration 4 (learning rate 1e-4, `n_steps` 512, entropy 0), seeds 42–46, the
  checkpoints selected in EXP-006 (run ids `c12145d46246e1c7`, `4f9be9680a6334bd`,
  `e9819a04ccc36567`, `9f585486f8b4ce4b`, `8d929082251f7c7f`; `model.zip` hashes checked).
- **Decisions:** the 156 weekly validation decisions per seed in evaluation `1ce9c490ed03c8c9`
  (protocol `e652adec1095c95a`), rebuilt from the saved ledgers with each checkpoint's
  training-fitted scaler.
- **Fidelity gate:** the rebuilt observations reproduce the evaluated targets within
  1.1 × 10⁻¹⁶ for every seed (tolerance 1e-9).
- **Comparators:** the three D-053 baselines from the same evaluation. Configurations other than
  4 are present in the saved table (the code summarises all 43 strategies) but are not reported
  or compared here (D-097).

## 2. Which inputs the decisions respond to (permutation sensitivity)

Each input group is permuted jointly across decisions (20 repeats, seed 0); the score is the
mean L1 change of the decided target weights (cash included; range 0–2).

| Input group | Inputs | Median over seeds | Range over seeds |
| --- | --- | --- | --- |
| Return and momentum features | 14 | **0.433** | 0.373–0.559 |
| Universe context features | 6 | 0.314 | 0.181–0.338 |
| Volatility and risk features | 11 | 0.212 | 0.125–0.353 |
| Cross-asset features | 3 | 0.150 | 0.085–0.312 |
| Regime one-hot inputs | 9 | 0.118 | 0.083–0.175 |
| Current portfolio weights | 8 | **0.032** | 0.025–0.050 |

- **Return and momentum** inputs move the decided allocation most in every seed; the **current
  weights** move it least in every seed. The policy re-decides its allocation largely without
  regard to what it holds, which is consistent with its very high turnover (13–21× a year).
- The **regime one-hot** inputs rank fifth of six. This matches E12 (EXP-028), where removing
  them changed validation net Sharpe by −0.11 / −0.25 / +0.18 with no reliable direction: the
  labels are a coarse summary of momentum and volatility features the policy already sees.
- Groups differ in size, so the scores are not per-input importances. Permuting a group creates
  input combinations that never occur together (out-of-distribution).

## 3. How allocations vary with the market regime (validation, label at *t* − 1)

Only three regimes have at least 63 validation sessions (`neutral_low` 214, `neutral_normal` 74,
`positive_low` 347). The three negative regimes (17, 33 and 28 sessions) and the other small
regimes are flagged and not interpreted.

**Whole validation window, per seed (42 / 43 / 44 / 45 / 46):**

| Measure | Configuration 4 | Baselines (EW monthly / buy-and-hold / inverse volatility) |
| --- | --- | --- |
| Mean cash weight | 0.42 / 0.43 / 0.32 / 0.49 / 0.28 | 0 / 0 / 0 |
| Mean risky-sleeve HHI | 0.64 / 0.67 / 0.51 / 0.76 / 0.43 | 0.14 / 0.14 / 0.18 |
| Annualised turnover | 13.3 / 18.6 / 20.8 / 14.8 / 15.9 | 0.22 / 0 / 0.78 |

**Regime pattern in the three sufficient regimes:**

| Seed | Cash: `neutral_low` / `neutral_normal` / `positive_low` | Turnover: same order |
| --- | --- | --- |
| 42 | 0.44 / 0.35 / 0.44 | 15.0 / 19.3 / 7.7 |
| 43 | 0.46 / 0.19 / 0.50 | 16.9 / 28.1 / 17.0 |
| 44 | 0.27 / 0.27 / 0.38 | 25.0 / 39.6 / 12.0 |
| 45 | 0.49 / 0.34 / 0.53 | 16.5 / 31.6 / 6.0 |
| 46 | 0.27 / 0.23 / 0.32 | 16.4 / 27.4 / 11.0 |

- **Consistent across all five seeds:** in `neutral_normal` (no clear trend, normal volatility)
  the policy holds the **least cash** and trades the **most**; in `positive_low` (calm uptrend)
  it holds the **most cash**. Turnover is lowest in `positive_low` in 4 of 5 seeds.
- **Interpretation (association only):** the policy does respond to market conditions, but not
  in a risk-management direction: it is most invested and most active when the trend is unclear,
  and holds more cash in calm uptrends. Realised volatility is also highest in `neutral_normal`
  for every seed, which is partly mechanical (the label uses trailing market volatility).
- **Seed dependence:** the level of cash and concentration differs strongly between seeds
  (cash 0.28–0.49), so a single policy's behaviour should not be generalised.

## 4. Limitations

- One validation period (2017–2019), dominated by low-volatility regimes; falling-market
  behaviour cannot be assessed (no negative regime reaches 63 sessions).
- One-step sensitivities with the portfolio inputs held as observed; permutations create
  out-of-distribution inputs; scores depend on group size.
- Regime labels are heuristic and training-relative (D-045); associations are not causal.
- Configuration 4 underperformed all three baselines on validation net Sharpe (EXP-006). This
  analysis explains what the policy does, not whether it is good.
- No selection, tuning or retraining follows from these results.

## 5. Reproducibility and verification

| Item | Value |
| --- | --- |
| Command | `python scripts/explain.py policy-validation --evaluation-dir data/processed/evaluations/1ce9c490ed03c8c9 --dataset-dir data/processed/8e00568ee2aa4de7 --feature-dir data/processed/features/a79347e37e653703 --confirm-validation-access` |
| Code | clean commit `bcb99ec` |
| Output | `data/processed/explainability/86b75ffd1d00783e` (102 files; write-once; git-ignored) |
| Verification | every file hash matches `metadata.json`; the analysis id recomputes from the identity; a second run into a temporary folder outside the repository reproduced `regime_summary.csv`, `sensitivity_by_seed.csv` and `sensitivity_summary.csv` byte-for-byte |
| Data read | validation decisions and the training rows needed for features (bounded loader; no test row) |
| Figures | `figures/sensitivity_selected_configuration.png` and the regime figures, with provenance sidecars |
