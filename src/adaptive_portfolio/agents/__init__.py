"""Reinforcement-learning agents.

Implemented (milestone 5.3; needs the ``rl`` extra, so this package does not import it):

* ``ppo`` - Stable-Baselines3 PPO training wrapper for one grid run (configuration and seed,
  D-066) on the training split, with recorded configuration, versions, data provenance,
  scaler, checkpoint and metadata under ``data/processed/experiments/<run_id>/`` (D-069).

* ``evaluate`` - the D-076 validation evaluator and selection (milestone B; run once as
  EXP-006). It has no test option.
* ``provenance`` - checkpoint integrity and configuration compatibility (milestone F; no
  ``rl`` extra needed).

Not implemented: any test-period evaluation (Gate 3) and other algorithms (optional
extensions). PPO is the candidate algorithm, not a final choice.
See docs/architecture.md and docs/roadmap.md.
"""
