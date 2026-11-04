"""E10 walk-forward fold inputs (D-094): build and verify a fold's dataset and feature set.

A fold dataset is derived from the parent processed dataset with the bounded reader (no row on
or after the project's test start is read); regime thresholds are fitted on the fold's training
rows. See docs/e10_walk_forward_protocol.md.
"""

from __future__ import annotations

import sys

from adaptive_portfolio.data.walk_forward import main

if __name__ == "__main__":
    sys.exit(main())
