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


class ProfileRewardEnv(gym.Wrapper):
    """E4: replace the reward by the profile-dependent reward of ``spec`` (D-088).

    Wraps a :class:`ProfileConditionedEnv`. The base reward, observation, termination and all
    accounting come unchanged from the wrapped environment; only the returned reward differs:
    ``r_base - (lambda(U) / 2) * RV``, with ``RV`` the sum of squared net returns of the ledger
    rows this step added (its own interval; no later row). Every component is in ``info`` and
    per-episode sums are kept in :attr:`episodes`.
    """

    def __init__(self, env: ProfileConditionedEnv, spec: Any) -> None:
        super().__init__(env)
        if not isinstance(env, ProfileConditionedEnv):
            raise ProfileError("the profile reward needs a ProfileConditionedEnv")
        self.reward_spec = spec  # not `spec`: gym.Wrapper.spec is the EnvSpec
        self.episodes: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        observation, info = self.env.reset(seed=seed, options=options)
        profile = self.env.profile
        self._current = {
            "profile": [float(x) for x in profile],
            "lambda": self.reward_spec.penalty_coefficient(profile),
            "steps": 0,
            "reward_base": 0.0,
            "risk_penalty": 0.0,
            "reward": 0.0,
            "realised_variance": 0.0,
        }
        self.episodes.append(self._current)
        return observation, info

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self._current is None:
            raise ProfileError("call reset() before step()")
        ledger = self.env.unwrapped.ledger
        start = len(ledger)
        observation, reward, terminated, truncated, info = self.env.step(action)
        records = [record for _, record in ledger[start:]]
        # Recurring traded notional of this step; the first step's execution is the funding
        # trade from cash and is excluded, as in the reported turnover (D-059; E7, D-091).
        traded = 0.0 if self._current["steps"] == 0 else sum(r.traded_notional for r in records)
        parts = self.reward_spec.components(
            reward, [r.net_return for r in records], self.env.profile, traded_notional=traded
        )
        for key in ("reward_base", "risk_penalty", "reward", "realised_variance",
                    "turnover_penalty", "traded_notional"):  # fmt: skip
            if key in parts:
                self._current[key] = self._current.get(key, 0.0) + parts[key]
        self._current["steps"] += 1
        return observation, parts["reward"], terminated, truncated, {**info, **parts}
