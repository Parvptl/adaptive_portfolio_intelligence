"""Plan or run the PPO validation evaluation (milestone B; protocol D-076; needs the ``rl`` extra).

Usage::

    python scripts/evaluate_validation.py --plan
    python scripts/evaluate_validation.py --execute --confirm-validation-evaluation

``--execute`` loads validation rows.

``--plan`` verifies all checkpoints and prints the evaluation identity; it loads no data rows
and writes nothing. ``--execute`` must not be used until D-076 is accepted and the evaluation is
separately authorised. The test split is sealed: there is no option to evaluate it.
"""

from __future__ import annotations

from adaptive_portfolio.agents.evaluate import main

if __name__ == "__main__":
    raise SystemExit(main())
