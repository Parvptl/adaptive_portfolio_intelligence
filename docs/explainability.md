# Explainability, regime analysis and ablation (milestone E)

- **Date:** 2026-10-21.
- **Status:**
  - the analysis pipeline is implemented and tested on synthetic data;
  - **one real analysis was run**: the conventional baselines on the **training split**
    (EXP-008);
  - the D-068 analysis of the selected PPO policy on validation decisions is **implemented but
    not run**: it needs an explicit, recorded authorisation;
  - the regime-input ablation needs retraining. It is **planned only** (D-081, Proposed).
- **Scope:** D-068 (accepted) is the design: permutation sensitivity on validation decisions,
  plus regime-conditional allocation, risk and performance summaries, with associations, not
  causation, and no SHAP. Conventions not fixed by D-068 are proposed as **D-080**.
- **Test period:** 2020–2024 was not read. The analysis code has no test mode.

## 1. What exists and what was added

| Component | Before milestone E | Added |
| --- | --- | --- |
| Regime labels | `regimes/rules.py`: 9 trend × volatility labels plus `unavailable`; training-calibrated thresholds (D-045); `regimes/diagnostics.py`: label frequencies and transitions | `explainability/regime_analysis.py`: strategy behaviour conditioned on the labels (reuses `REGIME_LABELS` and `UNAVAILABLE`) |
| Observation and action mapping | `environment/observation.py` (D-062 layout), `environment/actions.py` (D-072, D-063) | `explainability/sensitivity.py`: permutation sensitivity through the same mapping |
| Figures | none (`visualization/` was a placeholder) | `visualization/plots.py`: PNG figures, each with a JSON provenance sidecar |
| Runner | none | `explainability/run.py` and `scripts/explain.py`: modes `baselines-train` and `policy-validation` |

## 2. Methods (see D-080 for the conventions)

### 2.1 Regime-conditioned summaries (observational)

- **Which label applies to which row:** each ledger row *t* after the funding row gets the
  label of the session *t − lag*. That is the label known when the holdings earning *t*'s return
  were set; with lag 1 it is the decision date of a trade executed on *t*. No label from *t*'s
  own close is used.
- **Every regime is reported:** all nine regimes **and `unavailable`** (the warm-up label)
  always appear, with zero sessions if absent. Unknown labels are an error.
- **Per regime:**
  - **sample size:** sessions, share of sessions, number of contiguous **episodes**, and a
    `sufficient` flag (sessions ≥ 63, PROPOSED);
  - **allocation:** mean end-of-row weight per ETF and cash, mean risky exposure (1 − cash),
    the Herfindahl index (HHI) of the risky sleeve, and the mean largest ETF weight;
  - **trading:** recurring ETF traded notional (funding excluded), in total, per session and
    annualised;
  - **realised risk:** mean daily net return, annualised volatility (ddof 1), share of negative
    days, and the worst day.
- **Checks:**
  - the regime rows partition the "all" row;
  - every execution must sit exactly *lag* sessions after its recorded decision date.

### 2.2 Permutation sensitivity (D-068; implemented, not run on real data)

- **How it works:** for a fixed set of decision observations, the inputs of one group are
  permuted **jointly across decisions**. The groups are each recorded feature family
  (`return_momentum`, `volatility_risk`, `cross_asset`, `universe_context`), the 9 regime
  inputs, and the 8 portfolio-weight inputs.
  - The deterministic action is mapped to targets with the project's own mapping.
  - The score is the mean L1 change of the target weights, cash included, on a scale of 0 to 2.
  - 20 seeded repeats (seed 0) per group, with the minimum, maximum and standard deviation
    across repeats (PROPOSED).
- **Observations at validation decisions are rebuilt** from the saved EXP-006 ledger: scaled
  features, the regime and end-of-row weights. There is no rollout.
  - **Fidelity check:** the rebuilt deterministic targets must equal the evaluator's executed
    targets within 1e-9, otherwise the run stops.
  - In the synthetic end-to-end test the fidelity check also caught batched versus single-row
    float32 rounding (2.5e-9). The policy is therefore evaluated one observation at a time,
    exactly as in the environment.
- **What it measures:** the **sensitivity of decisions**, one step at a time. It does **not**
  measure importance for returns or risk, and it is **not causal**. Permuting one group breaks
  its correlation with the others, so some perturbed rows are out of distribution.

### 2.3 Predictive association, sensitivity and causality

| Statement type | Supported here by | Not supported |
| --- | --- | --- |
| **Association:** "in regime R, strategy S held X on average" | §2.1 summaries | A claim that R *caused* X; any test of differences between regimes |
| **Sensitivity:** "the decided targets change by Δ when group G is permuted" | §2.2 (once authorised) | Importance for performance; the effect of G in the market |
| **Causal effect** of an input or design choice | Only a controlled ablation (§4), with retraining, equal budgets and seeds, and a pre-declared comparison | Anything in §2.1 or §2.2 |

## 3. Results actually produced (EXP-008, training split, baselines only)

- **Source:** EXP-002 backtest `c6d8c473258e3194`, rows labelled `train` only (the numeric
  values of validation rows are never parsed). Regime labels come from feature set
  `a79347e37e653703` through the bounded `train_only` loader.
- **Window and checks:** 2007-07-06 to 2016-12-30, 2,390 sessions per strategy, label at
  *t* − 1. All 229 baseline executions lie 1 session after their decision.
- **Analysis id:** `1d0548a0ca7857c4` (see the experiment log for the other ids with identical
  numbers).
- **Cross-check:** the "all" rows reproduce EXP-002's training annualised traded notional,
  annualised volatility and return periods exactly. The regime rows partition them.

**Observed (descriptive, one historical path):**

- **Sample sizes:**
  - `negative_low` has only 38 sessions, in 12 episodes, so it is flagged small;
  - the other 8 regimes have 113–435 sessions;
  - `unavailable` has 0, because the backtest window starts after the 126-session warm-up;
  - labels change often: 369 episodes in 2,390 sessions, about 6.5 sessions each.
- **Realised volatility is highest in `negative_high` for all three baselines:** buy-and-hold
  0.140, equal weight monthly 0.183, inverse volatility 0.104 (training all-session values
  0.091, 0.109 and 0.071). This is **partly mechanical**, because the volatility regimes are
  defined from trailing market volatility.
- **Inverse volatility allocation:** it holds less SPY in high-volatility regimes (0.089 in
  `negative_high` against 0.121 in `negative_low`) and more IEF and TLT (0.279 and 0.144 in
  `negative_high`). This is a direct consequence of its own rule, not evidence about markets.
- **Turnover:** annualised turnover is highest in `negative_high` for inverse volatility (1.27)
  and equal weight monthly (0.69). Buy-and-hold has no recurring trades.
- **Risky exposure is 1.0 in every regime:** the baselines never hold cash.

**Interpretation limits:** these summaries describe how known rules behave across labels. They
say nothing about the PPO policy, and nothing about whether any strategy "adapts well". No
confidence intervals are given, and comparisons between regimes are **not statistically
supported** (overlapping market events, autocorrelation, few episodes).

## 4. Ablation: removing the regime inputs (planned; D-081, Proposed; NOT run)

- **Why retraining is needed:** the policy's input size is fixed (51). Zeroing or permuting
  the regime inputs at inference is a **sensitivity** analysis (§2.2), not an ablation: the
  policy was never trained without them.
- **A fair ablation** retrains the same configuration without the 9 regime inputs (42
  inputs), with everything else unchanged:
  - the same feature set, scaler, reward, costs, constraints, timing, budget (100,000
    timesteps), hyperparameters (configuration 4: learning rate 1e-4, `n_steps` 512, entropy
    coefficient 0) and seeds 42–46;
  - evaluated by the D-076 rules on validation, next to the existing configuration-4 runs.
- **Exact feature change:** the observation drops the one-hot `regime_inputs` group (indices
  34–42 of the D-062 layout). The 34 scaled features and the 8 portfolio weights are
  unchanged.
- **Needs:**
  - a decision amending D-062 for this experiment only, plus an observation option with tests;
  - training authorisation: 5 runs. EXP-005 run `c12145d46246e1c7` took 79 s, so 5 runs would
    take roughly 7 min (an estimate, not measured for this variant);
  - a validation-access authorisation for one comparison.

  Validation has already been used once for selection, so this is a further look (D-077
  principles).
- **Pre-declared comparison (PROPOSED):**
  - the difference in median validation net Sharpe over seeds 42–46, with every seed reported
    and no significance claim (5 seeds, one window);
  - turnover and allocation by regime as secondary metrics.

  A feature-family ablation (e.g. without `cross_asset`) would follow the same template.

## 5. Blockers and remaining work

1. **PPO explainability on validation decisions (D-068).** Implemented and tested end to end on
   synthetic checkpoints. It needs an explicit, recorded authorisation to read
   validation-period feature and regime rows. Command:
   `python scripts/explain.py policy-validation --evaluation-dir data/processed/evaluations/1ce9c490ed03c8c9 --dataset-dir data/processed/8e00568ee2aa4de7 --confirm-validation-access`.
2. **PPO behaviour on the training period** (D-078, Proposed) and on the test period (Gate 3):
   not available.
3. **Ablations (D-081):** they need decisions and training authorisation.
4. **Committed provenance:** the real analysis ran from uncommitted code (recorded). After a
   commit it should be re-run once for clean provenance.

---

*Update (2026-10-21, appended):*
- **Path drawdown:** regime summaries now include the mean and deepest **path drawdown** level
  per regime (when the ledger has `value`). This is the level of the window's drawdown on the
  rows with that label, **not** a regime-specific loss.
- **Threshold hash:** the analysis identity now records the regime-threshold artifact SHA-256.
- **Re-run:** on the training split as `b89e6b0c03289d34` (EXP-008 note). Earlier analyses are
  kept and marked superseded on the dashboard.
- **Dates:**
  - a row's label is that of its decision or information date (*t* − lag);
  - its return accrues on *t*;
  - a trade executed on *t* was decided at *t* − lag.
- **The taxonomy is not frozen as accepted:** D-045 is still Proposed. The threshold artifact
  is identified by hash, and the draft pre-registration proposes freezing that exact file (G3-14).
- **The PPO analysis on validation decisions was not run:** no validation-access authorisation
  was given.

*Update (2026-10-22, appended):* the PPO explainability on validation decisions is specified,
for separate review, in `docs/explainability_validation_plan.md`. **It has not been executed.**
No explainability code was changed.
