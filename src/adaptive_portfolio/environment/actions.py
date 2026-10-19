"""Action mapping for the PPO agent (decisions D-063, D-072).

The policy outputs a normalised action ``u`` in ``[POLICY_ACTION_LOW, POLICY_ACTION_HIGH]``
(``[-1, 1]``; the ``Box`` bounds, to which Stable-Baselines3 clips sampled actions), with one
entry per asset plus a final entry for cash. The environment scales it to logits
``a = ACTION_SCALE * u`` in ``[LOGIT_LOW, LOGIT_HIGH]`` (``[-5, 5]``, D-072) and applies the
D-063 mapping:

1. proposal ``p = softmax(a)``, so ``p >= 0`` and ``sum(p) = 1``;
2. risky targets ``w_i = min(p_i, max_weight)`` for each asset;
3. the capped excess goes to cash: ``w_cash = 1 - sum_i w_i`` (implicit in the simulator).

Equivalence (D-072): ``u -> 5u`` maps ``[-1, 1]^n`` one-to-one onto ``[-5, 5]^n``, so the
reachable targets are those of D-063, and the action ``u = a / 5`` gives the D-063 target of
``a``. For ``float32`` actions (Stable-Baselines3) ``5u`` is exact in ``float64`` (a 24-bit
significand times the 3-bit constant 5 fits in 53 bits).

It is deterministic, never moves weight to an asset the policy did not choose, and needs
``allow_cash: true``. Values outside the bounds or non-finite values are errors, not clipped
here.
"""

from __future__ import annotations

import numpy as np

POLICY_ACTION_LOW = -1.0
POLICY_ACTION_HIGH = 1.0
ACTION_SCALE = 5.0
LOGIT_LOW = ACTION_SCALE * POLICY_ACTION_LOW  # -5.0, the D-063 bounds
LOGIT_HIGH = ACTION_SCALE * POLICY_ACTION_HIGH  # 5.0


class ActionError(ValueError):
    """Raised for an action that is not a finite vector inside the action bounds."""


def _finite_vector(values: np.ndarray, low: float, high: float, name: str) -> np.ndarray:
    v = np.asarray(values, dtype=np.float64)
    if v.ndim != 1 or len(v) < 2:
        raise ActionError(f"{name} must be a vector of assets plus cash, got shape {v.shape}")
    if not np.isfinite(v).all():
        raise ActionError(f"{name} must be finite, got {v}")
    if (v < low).any() or (v > high).any():
        raise ActionError(f"{name} outside the bounds [{low}, {high}]: {v}")
    return v


def policy_action_to_logits(action: np.ndarray) -> np.ndarray:
    """Scale a normalised policy action ``u`` in ``[-1, 1]`` to logits ``5u`` (D-072)."""
    u = _finite_vector(action, POLICY_ACTION_LOW, POLICY_ACTION_HIGH, "policy action")
    return ACTION_SCALE * u


def action_proposal(logits: np.ndarray) -> np.ndarray:
    """Softmax proposal ``p`` over the assets and cash (cash last) for logits in ``[-5, 5]``."""
    a = _finite_vector(logits, LOGIT_LOW, LOGIT_HIGH, "logits")
    exp = np.exp(a - a.max())  # shift-invariant; avoids overflow
    return exp / exp.sum()


def project_action(logits: np.ndarray, max_weight: float) -> np.ndarray:
    """Risky target weights (universe order) for ``logits``; cash is ``1 - sum`` (D-063)."""
    if not 0 < max_weight <= 1:
        raise ActionError(f"max_weight must be in (0, 1], got {max_weight}")
    proposal = action_proposal(logits)
    return np.minimum(proposal[:-1], max_weight)
