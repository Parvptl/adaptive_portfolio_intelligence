"""Workflow over saved artifacts (milestone F). Default mode: read-only status.

Usage::

    python scripts/workflow.py              # status (read-only)
    python scripts/workflow.py verify       # artifact integrity and checkpoint provenance
    python scripts/workflow.py explain      # training-split baseline regime analysis
    python scripts/workflow.py dashboard    # static dashboard from saved, verified results

It never trains, never runs an evaluation and never reads the test period. Figures and the
dashboard need the optional ``viz`` extra (matplotlib).
"""

from __future__ import annotations

from adaptive_portfolio.workflow import main

if __name__ == "__main__":
    raise SystemExit(main())
