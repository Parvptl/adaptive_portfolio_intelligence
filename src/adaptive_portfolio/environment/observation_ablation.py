"""E12 observation ablation (D-096): drop the 9 regime one-hot inputs.

The D-062 observation of :class:`PortfolioEnv` is ``[features (n), regime one-hot (9), weights]``
(see :mod:`adaptive_portfolio.environment.observation`). ``RegimeAblatedEnv`` removes exactly the
regime block from every observation and from the observation space and changes nothing else:
rewards, termination, info, actions, the ledger and every accounting quantity pass through
untouched. Regime labels are still computed and validated by the wrapped environment; they are
only no longer observed. It is applied below :class:`ProfileConditionedEnv`, so the profile is
still appended last.

Gymnasium (the ``rl`` extra) is imported lazily, so this module imports without it like the
rest of the core package; ``RegimeAblatedEnv`` itself needs the extra.
"""

from __future__ import annotations

from functools import cache
from typing import Any

import numpy as np

from adaptive_portfolio.regimes.rules import REGIME_LABELS

ABLATIONS = ("regime",)


@cache
def _wrapper_class() -> type:
    import gymnasium as gym

    class RegimeAblatedEnv(gym.ObservationWrapper):
        """Observation without the regime one-hot block (positions ``n_features .. +9``)."""

        def __init__(self, env: Any) -> None:
            super().__init__(env)
            n_features = len(env.unwrapped.scaler.columns)
            self.removed = np.arange(n_features, n_features + len(REGIME_LABELS))
            space = env.observation_space
            if space.shape[0] <= self.removed[-1]:
                raise ValueError("the wrapped observation has no regime block to remove")
            self.observation_space = gym.spaces.Box(
                low=np.delete(space.low, self.removed).astype(np.float32),
                high=np.delete(space.high, self.removed).astype(np.float32),
                dtype=np.float32,
            )

        def observation(self, observation: np.ndarray) -> np.ndarray:
            return np.delete(np.asarray(observation), self.removed).astype(np.float32)

    return RegimeAblatedEnv


def __getattr__(name: str) -> Any:
    if name == "RegimeAblatedEnv":
        return _wrapper_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def apply_ablation(env: Any, ablation: str | None) -> Any:
    """``env`` itself, or ``env`` wrapped for the named E12 ablation."""
    if ablation is None:
        return env
    if ablation == "regime":
        return _wrapper_class()(env)
    raise ValueError(f"unknown observation ablation {ablation!r}; expected one of {ABLATIONS}")
