"""Explanations of strategy and policy behaviour (milestone E; D-068, D-080).

* ``regime_analysis`` - allocations, risky exposure, cash, turnover and realised risk
  conditioned on the regime label known when holdings were set (observational only).
* ``sensitivity`` - permutation sensitivity of a policy's decided targets to input groups
  (sensitivity of decisions; not importance for returns and not causal).
* ``run`` - analysis runs from saved artifacts (``scripts/explain.py``): ``baselines-train``
  (training split) and ``policy-validation`` (needs an explicit, recorded authorisation).

Ablations need retraining and are planned only (D-081). SHAP is not used. See
docs/explainability.md.
"""
