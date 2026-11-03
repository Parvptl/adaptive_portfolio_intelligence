"""Profile-conditioned observations on top of :class:`PortfolioEnv` (D-085; ``rl`` extra).

:class:`ProfileConditionedEnv` is a thin Gymnasium wrapper. It:

* draws one investor profile at every ``reset`` (or uses ``options={"profile": ...}``) and keeps
  it fixed for the whole episode;
* appends the five profile values, unscaled, after the 51 D-062 inputs: observation
  ``[features (34), regime one-hot (9), weights (8), profile (5)]``, 56 values in total;
* passes ``step`` straight through. The reward, termination, info, action space and all
  accounting are those of the wrapped environment, unchanged (D-064 reward preserved by
  construction: the wrapper never computes or modifies a reward).

Profile randomness uses a dedicated generator ``default_rng([seed, stream])`` (D-086 item 3).
It is re-created when ``reset`` receives a ``seed`` (Stable-Baselines3 seeds the first reset),
so the market path, the environment and PPO's own random streams are not affected.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from adaptive_portfolio.environment.portfolio_env import PortfolioEnv
from adaptive_portfolio.environment.profiles import (
    PROFILE_SIZE,
    ProfileError,
    ProfileSampling,
    profile_stream,
    validate_profile,
)

DEFAULT_PROFILE_STREAM = 5


class ProfileConditionedEnv(gym.Wrapper):
    """Append a constant-per-episode investor profile to every observation."""

    def __init__(
        self,
        env: PortfolioEnv,
        sampling: ProfileSampling | None,
        *,
        seed: int,
        stream: int = DEFAULT_PROFILE_STREAM,
        fixed_profile: np.ndarray | None = None,
    ) -> None:
        """
        Args:
            env: the unchanged portfolio environment.
            sampling: training distribution; ``None`` requires ``fixed_profile`` (or a profile
                passed to every ``reset``).
            seed, stream: the profile generator is ``default_rng([seed, stream])``.
            fixed_profile: used for every episode instead of sampling (evaluation).
        """
        super().__init__(env)
        if sampling is None and fixed_profile is None:
            raise ProfileError("give a sampling distribution or a fixed profile")
        self.sampling = sampling
        self.stream = int(stream)
        self.fixed_profile = None if fixed_profile is None else validate_profile(fixed_profile)
        self._rng = profile_stream(seed, self.stream)
        self.profile: np.ndarray | None = None
        self.history: list[list[float]] = []  # one profile per reset, in order
        base = env.observation_space
        self.observation_space = gym.spaces.Box(
            low=np.r_[base.low, np.zeros(PROFILE_SIZE)].astype(np.float32),
            high=np.r_[base.high, np.ones(PROFILE_SIZE)].astype(np.float32),
            dtype=np.float32,
        )

    def _append(self, observation: np.ndarray) -> np.ndarray:
        assert self.profile is not None
        return np.concatenate([observation, self.profile.astype(np.float32)])

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        options = dict(options or {})
        given = options.pop("profile", None)
        if seed is not None:
            self._rng = profile_stream(seed, self.stream)
        observation, info = self.env.reset(seed=seed, options=options or None)
        if given is not None:
            self.profile = validate_profile(given)
        elif self.fixed_profile is not None:
            self.profile = self.fixed_profile.copy()
        else:
            assert self.sampling is not None
            self.profile = self.sampling.sample(self._rng)
        self.history.append([float(x) for x in self.profile])
        return self._append(observation), {**info, "profile": self.profile.copy()}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self.profile is None:
            raise ProfileError("call reset() before step()")
        observation, reward, terminated, truncated, info = self.env.step(action)
        return (
            self._append(observation),
            reward,
            terminated,
            truncated,
            {
                **info,
                "profile": self.profile.copy(),
            },
        )
