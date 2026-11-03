"""Investor profiles for the profile-conditioned PPO extension (D-085; details D-086/D-087).

A profile is five numbers in ``[0, 1]`` (:data:`PROFILE_DIMENSIONS` order). They are research
representations for a synthetic-profile experiment, **not** validated suitability scores.
Sampling is continuous and reproducible:

* :class:`ProfileSampling` describes a distribution: independent ``Uniform(low, high)`` per
  dimension, optionally with one excluded box (a joint region such as "risk tolerance >= 0.6
  and risk capacity <= 0.4"), rejected and redrawn;
* :func:`profile_set` draws a fixed, seeded set of evaluation profiles from the full cube, from
  inside the excluded box, or from a sampling distribution.

Nothing here reads market data or depends on the ``rl`` extra.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

PROFILE_DIMENSIONS = (
    "risk_tolerance",
    "risk_capacity",
    "investment_horizon",
    "liquidity_preference",
    "growth_preference",
)
PROFILE_SIZE = len(PROFILE_DIMENSIONS)
NEUTRAL_VALUE = 0.5
SAMPLING_DISTRIBUTIONS = ("uniform", "constant")  # constant: E5 (D-089)
MAX_REJECTIONS = 10_000  # a box excluding (almost) the whole cube fails loudly, not forever


class ProfileError(ValueError):
    """Raised for an invalid profile, sampling description or profile set."""


def validate_profile(values: Sequence[float] | np.ndarray) -> np.ndarray:
    """The profile as a float64 vector of length 5 with every value finite and in [0, 1]."""
    profile = np.asarray(values, dtype=np.float64)
    if profile.shape != (PROFILE_SIZE,):
        raise ProfileError(f"a profile has {PROFILE_SIZE} values, got shape {profile.shape}")
    if not np.isfinite(profile).all() or (profile < 0).any() or (profile > 1).any():
        raise ProfileError(f"profile values must be finite and in [0, 1]: {profile.tolist()}")
    return profile


def neutral_profile() -> np.ndarray:
    """The midpoint profile (0.5, 0.5, 0.5, 0.5, 0.5)."""
    return np.full(PROFILE_SIZE, NEUTRAL_VALUE)


def profile_dict(values: Sequence[float] | np.ndarray) -> dict[str, float]:
    """``{dimension: value}`` for reports."""
    return dict(zip(PROFILE_DIMENSIONS, (float(v) for v in validate_profile(values)), strict=True))


def _interval(raw: Any, field: str) -> tuple[float, float]:
    if not isinstance(raw, Sequence) or isinstance(raw, str) or len(raw) != 2:
        raise ProfileError(f"{field} must be a [low, high] pair")
    low, high = (float(x) for x in raw)
    if not 0.0 <= low < high <= 1.0:
        raise ProfileError(f"{field} must satisfy 0 <= low < high <= 1, got {[low, high]}")
    return low, high


@dataclass(frozen=True)
class ProfileSampling:
    """Independent uniform sampling per dimension, with an optional excluded joint box.

    ``exclude`` maps some dimensions to ``(low, high)``; a draw is rejected when **every**
    listed dimension falls inside its interval (closed bounds). Dimensions not listed are
    unrestricted.
    """

    low: float = 0.0
    high: float = 1.0
    exclude: tuple[tuple[str, float, float], ...] = ()
    distribution: str = "uniform"
    constant: float | None = None  # distribution "constant": every dimension at this value

    def __post_init__(self) -> None:
        if self.distribution not in SAMPLING_DISTRIBUTIONS:
            raise ProfileError(f"distribution must be one of {SAMPLING_DISTRIBUTIONS}")
        if self.distribution == "constant":
            if self.constant is None or not 0.0 <= float(self.constant) <= 1.0 or self.exclude:
                raise ProfileError("a constant profile needs 0 <= constant <= 1 and no exclude")
        elif self.constant is not None:
            raise ProfileError("`constant` is only allowed with distribution 'constant'")
        _interval([self.low, self.high], "sampling [low, high]")
        names = [name for name, _, _ in self.exclude]
        if len(set(names)) != len(names) or not set(names) <= set(PROFILE_DIMENSIONS):
            raise ProfileError(f"exclude dimensions must be distinct profile dimensions: {names}")
        for name, low, high in self.exclude:
            _interval([low, high], f"exclude.{name}")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], field: str = "sampling") -> ProfileSampling:
        allowed = {"distribution", "low", "high", "exclude", "constant"}
        if not isinstance(raw, Mapping) or set(raw) - allowed or not {"distribution"} <= set(raw):
            raise ProfileError(f"{field} needs 'distribution' and only keys {sorted(allowed)}")
        exclude_raw = raw.get("exclude") or {}
        if not isinstance(exclude_raw, Mapping):
            raise ProfileError(f"{field}.exclude must map dimensions to [low, high]")
        exclude = tuple(
            (name, *_interval(exclude_raw[name], f"{field}.exclude.{name}"))
            for name in PROFILE_DIMENSIONS
            if name in exclude_raw
        )
        unknown = set(exclude_raw) - set(PROFILE_DIMENSIONS)
        if unknown:
            raise ProfileError(f"{field}.exclude has unknown dimensions {sorted(unknown)}")
        return cls(
            low=float(raw.get("low", 0.0)),
            high=float(raw.get("high", 1.0)),
            exclude=exclude,
            distribution=str(raw["distribution"]),
            constant=None if raw.get("constant") is None else float(raw["constant"]),
        )

    def to_dict(self) -> dict[str, Any]:
        out = {
            "distribution": self.distribution,
            "low": self.low,
            "high": self.high,
            "exclude": {name: [low, high] for name, low, high in self.exclude},
            "dimensions": list(PROFILE_DIMENSIONS),
        }
        if self.constant is not None:  # added only when set, so E1/E4 identities are unchanged
            out["constant"] = self.constant
        return out

    def in_excluded_region(self, profile: np.ndarray) -> bool:
        """Whether ``profile`` lies in the excluded box (False when nothing is excluded)."""
        if not self.exclude:
            return False
        index = {name: i for i, name in enumerate(PROFILE_DIMENSIONS)}
        return all(low <= profile[index[name]] <= high for name, low, high in self.exclude)

    def sample(self, rng: np.random.Generator) -> np.ndarray:
        """One profile; rejected and redrawn while it lies in the excluded box."""
        if self.distribution == "constant":
            return np.full(PROFILE_SIZE, float(self.constant))
        for _ in range(MAX_REJECTIONS):
            draw = rng.uniform(self.low, self.high, PROFILE_SIZE)
            if not self.in_excluded_region(draw):
                return validate_profile(draw)
        raise ProfileError("no admissible profile after the rejection limit; check `exclude`")


def profile_stream(seed: int, stream: int) -> np.random.Generator:
    """The dedicated profile generator ``default_rng([seed, stream])`` (D-086 item 3)."""
    return np.random.default_rng([int(seed), int(stream)])


def profile_set(
    count: int, seed: int, region: str, sampling: ProfileSampling | None = None
) -> np.ndarray:
    """``count`` seeded evaluation profiles, shape ``(count, 5)``.

    ``region``:

    * ``"full"``: independent Uniform(0, 1) per dimension;
    * ``"excluded"``: inside ``sampling``'s excluded box (listed dimensions uniform on their
      intervals, the others on [0, 1]);
    * ``"sampling"``: draws from ``sampling`` itself (its training distribution).
    """
    if count < 1:
        raise ProfileError("a profile set needs at least one profile")
    rng = np.random.default_rng(int(seed))
    if region == "full":
        values = rng.uniform(0.0, 1.0, (count, PROFILE_SIZE))
    elif region in ("excluded", "sampling"):
        if sampling is None or (region == "excluded" and not sampling.exclude):
            raise ProfileError(f"region {region!r} needs a sampling with an excluded box")
        if region == "sampling":
            values = np.vstack([sampling.sample(rng) for _ in range(count)])
        else:
            values = rng.uniform(0.0, 1.0, (count, PROFILE_SIZE))
            index = {name: i for i, name in enumerate(PROFILE_DIMENSIONS)}
            for name, low, high in sampling.exclude:
                values[:, index[name]] = rng.uniform(low, high, count)
    else:
        raise ProfileError(f"unknown region {region!r}")
    for row in values:
        validate_profile(row)
    return values
