"""Reinforcement-learning agents.

Implemented (milestone 5.3; needs the ``rl`` extra, so this package does not import it):

* ``ppo`` - Stable-Baselines3 PPO training wrapper for one grid run (configuration and seed,
  D-066) on the training split, with recorded configuration, versions, data provenance,
  scaler, checkpoint and metadata under ``data/processed/experiments/<run_id>/`` (D-069).

Not implemented: validation evaluation and model selection (need separate authorisation),
other algorithms (optional extensions). PPO is the candidate algorithm, not a final choice.
See docs/architecture.md and docs/roadmap.md.
"""
