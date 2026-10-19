"""Portfolio-allocation environment for sequential decision making.

Implemented (milestone 5.1; pure NumPy and pandas, no RL library needed):

* ``actions``     - softmax action mapping with the per-asset cap and excess to cash (D-063);
* ``observation`` - training-only feature scaling and the 51-input observation (D-062);
* ``rewards``     - weekly episode decisions and the decision-aligned log-growth reward
  (D-064, D-065).

Portfolio accounting is not implemented here: it is the simulator's ``step``
(``evaluation.simulator``, D-067).

Planned (milestone 5.2): a Gymnasium environment that combines these parts.
See docs/architecture.md and docs/roadmap.md.
"""
