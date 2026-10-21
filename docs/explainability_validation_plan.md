# Validation-only PPO explainability: plan for review (NOT EXECUTED)

> **NOT AN EXECUTION AUTHORISATION.**
> - PPO validation explainability **has not been run** under any instruction so far.
> - No test-period row may be accessed for explainability.
> - Running this plan needs (1) a review of this document, (2) acceptance of the open settings
>   below (D-080 is Proposed) and (3) an explicit, recorded **validation-access authorisation**.
> - Drafted 2026-10-22 by Claude Code at a team member's request (D-083, G3-17).

## 1. Purpose and scope

The analysis describes **which observation inputs the selected policy's decisions are sensitive
to**, and how its allocations vary across regimes, on **validation decisions only** (D-068).

It does **not**:
- measure the importance of inputs for returns;
- establish causal effects;
- select, tune or retrain anything.

Configuration 4 stays the selected candidate whatever the results show.

## 2. Inputs (all existing; nothing new is produced before authorisation)

- **Validation outputs:** `data/processed/evaluations/1ce9c490ed03c8c9/` (`ledgers.csv`,
  `evaluation.json`, `metadata.json`), verified against their recorded SHA-256 values.
- **Checkpoints:** configuration 4, seeds 42–46, run ids `c12145d46246e1c7`,
  `4f9be9680a6334bd`, `e9819a04ccc36567`, `9f585486f8b4ce4b` and `8d929082251f7c7f`.
  - Each `model.zip` must match the EXP-006 hash and pass `agents.provenance.verify_checkpoint`.
  - Each `scaler.json` must equal the one recorded in its run config.
- **Feature set:** `data/processed/features/a79347e37e653703` (`features.csv`, `regimes.csv`,
  `feature_metadata.json`), and dataset `data/processed/8e00568ee2aa4de7` (`splits.csv`).
  - They are read with the bounded loader, which excludes the test period. This also reads
    **training** rows, and the date and label of the first test row only (D-060).
  - The first validation decision needs the last training-row regime label (label at *t* − 1).
- **Not read:**
  - test-period values;
  - the old pipeline-v1 test-results folder;
  - `regime_report.*` (contains test-period counts; D-045 exposure note).

## 3. Protocol

1. **Integrity:** all hashes above. Any mismatch stops the run before anything is computed.
2. **Rebuild observations** at every validation decision date from the saved ledger:
   - the 34 features scaled with the checkpoint's frozen scaler;
   - the regime one-hot;
   - the end-of-row weights at the decision date (all cash before funding).
3. **Fidelity gate:** the rebuilt observations, passed through the policy one observation at
   a time, must reproduce the EXP-006 executed targets **within 1e-9**. Otherwise the run stops
   and nothing is written.
4. **Permutation sensitivity** for each seed and each input group:
   - the groups are the 4 recorded feature families, the 9 regime inputs and the 8 weight
     inputs;
   - each group is permuted jointly across decisions; the D-072/D-063 mapping gives the
     targets;
   - the score is the mean L1 change in target weights (cash included, range 0–2), with
     repeats and a seed. The median over seeds is reported, with the per-seed range.
5. **Regime-conditioned summaries** of the saved validation ledgers: allocation, cash, risky
   exposure, turnover, concentration, volatility and path drawdown, with sample counts,
   episodes and the 63-session flag.

## 4. Settings still to decide (not assumed accepted)

| Setting | Current proposal (D-080, Proposed) | Alternatives |
| --- | --- | --- |
| Repeats and seed | 20 repeats, seed 0 | more repeats |
| Groups | 4 feature families + regime + weights | individual features (more noise) |
| Fidelity tolerance | 1e-9 | none proposed |
| Regime-summary scope | currently all 43 validation strategies; **recommended:** configuration 4 seeds plus the three baselines only, so that other configurations are not compared | keep all 43 |
| Code state | run only from a committed tree | — |

## 5. Outputs and reproducibility

- **Location:** `data/processed/explainability/<analysis_id>/`, never overwritten. It contains:
  - `regime_summary.csv`, `sensitivity_by_seed.csv`, `sensitivity_summary.csv`;
  - figures with provenance sidecars;
  - `analysis.json` (fidelity gaps per seed, limitations);
  - `metadata.json` (SHA-256 of every file).
- **Reproducibility:** a second run into a temporary folder outside the repository must
  reproduce the CSV hashes. Afterwards the record goes to the experiment log as a new EXP
  entry.

## 6. Limitations to state with any result

- These are one-step decision sensitivities; the portfolio inputs are held as observed.
- Permuting a group creates out-of-distribution combinations.
- One validation period of mostly low-volatility regimes; few episodes in some regimes.
- The regime labels are heuristic and training-relative (D-045).
- Nothing here is causal or about returns.

## 7. Proposed command (do not run without authorisation)

```bash
python scripts/explain.py policy-validation --evaluation-dir data/processed/evaluations/1ce9c490ed03c8c9 --dataset-dir data/processed/8e00568ee2aa4de7 --feature-dir data/processed/features/a79347e37e653703 --confirm-validation-access
```

The flag is a guard, not an authorisation. The authorisation must be recorded first (approval
checklist, under R-S).
