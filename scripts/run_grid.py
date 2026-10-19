"""Plan, inspect, recover or run the PPO grid (needs the ``rl`` extra).

Usage::

    python scripts/run_grid.py --plan          # writes nothing
    python scripts/run_grid.py --status        # read-only
    python scripts/run_grid.py --recover       # quarantines stale run state (never deletes)
    python scripts/run_grid.py --execute --confirm-full-grid   # TRAINING: needs approval

Sequential only; stops at the first failure (D-075). See ``adaptive_portfolio.agents.grid``
and docs/technical_handbook.md section 16. Validation and test data are never loaded.
"""

from __future__ import annotations

from adaptive_portfolio.agents.grid import main

if __name__ == "__main__":
    raise SystemExit(main())
