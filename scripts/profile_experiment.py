"""Profile-conditioned PPO experiment (D-085): train arms, evaluate E0-E3, verify outputs.

Needs the ``rl`` extra. See docs/profile_conditioned_ppo.md and docs/technical_handbook.md.
The test split is never read.
"""

from __future__ import annotations

import sys

from adaptive_portfolio.agents.profile_experiment import main

if __name__ == "__main__":
    sys.exit(main())
