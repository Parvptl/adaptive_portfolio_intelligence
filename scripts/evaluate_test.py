"""Plan, run once, or verify the pre-registered test evaluation (milestone D; Gate 3; ``rl``).

Usage::

    python scripts/evaluate_test.py --plan --dataset-dir data/processed/<dataset_id>
    python scripts/evaluate_test.py --verify data/processed/test_evaluations/<id>
    python scripts/evaluate_test.py --execute --confirm-test-unsealing \\
        --preregistration-sha256 <sha256> --expected-commit <commit> --dataset-dir ...

``--plan`` reads no data rows. ``--execute`` READS THE SEALED TEST PERIOD and must only be run
after an explicit, recorded unsealing authorisation naming the commit, protocol hash,
pre-registration hash, evaluation id, dataset id, checkpoint hashes and this command. It refuses
unless the pre-registration (configs/preregistration.yaml) is frozen and every guard holds.
"""

from __future__ import annotations

from adaptive_portfolio.agents.test_evaluate import main

if __name__ == "__main__":
    raise SystemExit(main())
