"""Regime analysis and explainability from saved artifacts (milestone E; D-068).

Usage::

    python scripts/explain.py baselines-train --backtest-dir data/processed/backtests/<id>
    python scripts/explain.py policy-validation --evaluation-dir \\
        data/processed/evaluations/<id> --confirm-validation-access

``baselines-train`` reads training rows only. ``policy-validation`` reads validation-period
feature and regime rows and must only be run after an explicit, recorded authorisation. There
is no test-period mode. Figures need the optional ``viz`` extra (matplotlib).
"""

from __future__ import annotations

from adaptive_portfolio.explainability.run import main

if __name__ == "__main__":
    raise SystemExit(main())
