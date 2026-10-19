"""Train one PPO run on the training split, or inspect the grid (needs the ``rl`` extra).

Usage::

    python scripts/train_ppo.py --list
    python scripts/train_ppo.py --configuration 0 --seed 42 --dry-run
    python scripts/train_ppo.py --configuration 0 --seed 42 --smoke --timesteps 4096

See ``adaptive_portfolio.agents.ppo`` and docs/technical_handbook.md section 16. Validation
and test data are never loaded.
"""

from __future__ import annotations

from adaptive_portfolio.agents.ppo import main

if __name__ == "__main__":
    raise SystemExit(main())
