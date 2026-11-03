"""Profile-dependent reward for E4 (D-088; ``docs/e4_profile_reward.md``; no ``rl`` extra).

The E4 reward of step ``k`` for profile ``U``::

    r_E4,k(U) = r_base,k - (lambda(U) / 2) * RV_k
    RV_k      = sum over the step's ledger rows of net_return_t ** 2
    a(U)      = min(risk_tolerance, risk_capacity)
    gamma(U)  = gamma_min + (gamma_max - gamma_min) * (1 - a(U))
    lambda(U) = gamma(U) - 1

``r_base`` is the unchanged D-064 log growth after costs. Because log growth is, to second order,
``sum r_t - 1/2 sum r_t**2`` (relative risk aversion 1), the penalty raises the effective relative
risk aversion to ``gamma(U)``. With the default ``gamma_min = 1`` the reward equals ``r_base``
exactly when ``a(U) = 1``. Horizon, liquidity and growth preference are deliberately not used
(see the methodology document).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from adaptive_portfolio.environment.profiles import PROFILE_DIMENSIONS, validate_profile

RISK_MEASURES = ("realised_variance",)
# "fixed" (E5, D-089): lambda is a constant, independent of the profile.
ACCEPTANCE_RULES = ("min_tolerance_capacity", "fixed")
GAMMA_LIMIT = 50.0  # sanity bound on the configured relative risk aversion
TURNOVER_PENALTY_LIMIT = 0.1  # sanity bound on kappa (per unit of traded notional; E7, D-091)
_RT = PROFILE_DIMENSIONS.index("risk_tolerance")
_RC = PROFILE_DIMENSIONS.index("risk_capacity")


class ProfileRewardError(ValueError):
    """Raised for an invalid reward specification or invalid reward inputs."""


@dataclass(frozen=True)
class ProfileRewardSpec:
    """The E4 risk-aversion reward: parameters fixed before training (D-088)."""

    gamma_min: float = 1.0
    gamma_max: float = 10.0
    risk_measure: str = "realised_variance"
    acceptance: str = "min_tolerance_capacity"
    fixed_lambda: float | None = None  # only with acceptance "fixed" (E5)
    # E7 (D-091): kappa x traded notional of the step's recurring execution; 0 = no penalty.
    turnover_penalty: float = 0.0

    def __post_init__(self) -> None:
        kappa = self.turnover_penalty
        if not np.isfinite(kappa) or not 0.0 <= kappa <= TURNOVER_PENALTY_LIMIT:
            raise ProfileRewardError(
                f"need 0 <= turnover_penalty <= {TURNOVER_PENALTY_LIMIT}, got {kappa}"
            )
        if kappa > 0 and self.acceptance != "fixed":
            raise ProfileRewardError("turnover_penalty is only allowed with acceptance 'fixed'")
        if self.risk_measure not in RISK_MEASURES:
            raise ProfileRewardError(f"risk_measure must be one of {RISK_MEASURES}")
        if self.acceptance not in ACCEPTANCE_RULES:
            raise ProfileRewardError(f"acceptance must be one of {ACCEPTANCE_RULES}")
        values = (self.gamma_min, self.gamma_max)
        if not all(np.isfinite(v) for v in values):
            raise ProfileRewardError("gamma_min and gamma_max must be finite")
        if not 1.0 <= self.gamma_min <= self.gamma_max <= GAMMA_LIMIT:
            raise ProfileRewardError(
                f"need 1 <= gamma_min <= gamma_max <= {GAMMA_LIMIT}, got {list(values)}"
            )
        if self.acceptance == "fixed":
            lam = self.fixed_lambda
            if lam is None or not np.isfinite(lam) or not 0.0 <= lam <= GAMMA_LIMIT - 1:
                raise ProfileRewardError(
                    f"acceptance 'fixed' needs 0 <= fixed_lambda <= {GAMMA_LIMIT - 1}, got {lam}"
                )
        elif self.fixed_lambda is not None:
            raise ProfileRewardError("fixed_lambda is only allowed with acceptance 'fixed'")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ProfileRewardSpec:
        if not isinstance(raw, Mapping):
            raise ProfileRewardError("reward must be a mapping")
        if raw.get("acceptance") == "fixed":  # E5: a constant lambda, no gamma mapping
            allowed = {"fixed_lambda", "risk_measure", "acceptance"}
            if not allowed <= set(raw) <= allowed | {"turnover_penalty"}:
                raise ProfileRewardError(
                    f"a fixed reward needs the keys {sorted(allowed)} (optional turnover_penalty)"
                )
            return cls(
                risk_measure=str(raw["risk_measure"]),
                acceptance="fixed",
                fixed_lambda=float(raw["fixed_lambda"]),
                turnover_penalty=float(raw.get("turnover_penalty", 0.0)),
            )
        allowed = {"gamma_min", "gamma_max", "risk_measure", "acceptance"}
        if set(raw) != allowed:
            raise ProfileRewardError(f"reward needs exactly the keys {sorted(allowed)}")
        return cls(
            gamma_min=float(raw["gamma_min"]),
            gamma_max=float(raw["gamma_max"]),
            risk_measure=str(raw["risk_measure"]),
            acceptance=str(raw["acceptance"]),
        )

    def to_dict(self) -> dict[str, Any]:
        if self.acceptance == "fixed":
            out = {
                "formula": "r_base - (lambda/2) * sum(net_return_t**2); lambda fixed",
                "fixed_lambda": self.fixed_lambda,
                "risk_measure": self.risk_measure,
                "acceptance": self.acceptance,
            }
            if self.turnover_penalty > 0:  # added only when set: E5/E6 identities unchanged
                out["formula"] += "; - kappa * recurring traded notional (funding step excluded)"
                out["turnover_penalty"] = self.turnover_penalty
            return out
        return {
            "formula": "r_base - (lambda(U)/2) * sum(net_return_t**2); "
            "lambda = gamma - 1; gamma = gamma_min + (gamma_max - gamma_min) * (1 - min(RT, RC))",
            "gamma_min": self.gamma_min,
            "gamma_max": self.gamma_max,
            "risk_measure": self.risk_measure,
            "acceptance": self.acceptance,
        }

    def risk_acceptance(self, profile: Sequence[float] | np.ndarray) -> float:
        """``a(U) = min(RT, RC)`` in [0, 1]."""
        values = validate_profile(profile)
        return float(min(values[_RT], values[_RC]))

    def risk_aversion(self, profile: Sequence[float] | np.ndarray) -> float:
        """Relative risk aversion ``gamma(U)`` in ``[gamma_min, gamma_max]`` (fixed: 1 + lambda)."""
        if self.acceptance == "fixed":
            validate_profile(profile)
            return 1.0 + float(self.fixed_lambda)
        return self.gamma_min + (self.gamma_max - self.gamma_min) * (
            1.0 - self.risk_acceptance(profile)
        )

    def penalty_coefficient(self, profile: Sequence[float] | np.ndarray) -> float:
        """``lambda(U) = gamma(U) - 1 >= 0``."""
        return self.risk_aversion(profile) - 1.0

    def components(
        self,
        base_reward: float,
        net_returns: Sequence[float] | np.ndarray,
        profile: Sequence[float] | np.ndarray,
        traded_notional: float = 0.0,
    ) -> dict[str, float]:
        """Every term of one step's reward (no state; the inputs are the step's own rows).

        ``traded_notional`` is the step's recurring ETF traded notional (0 for the funding step).
        It only matters when ``turnover_penalty`` > 0 (E7): the penalty kappa x traded notional
        is a reward-shaping term on trading activity. The real transaction cost is already in
        ``base_reward`` (log growth after costs) and is not deducted again.
        """
        returns = np.asarray(net_returns, dtype=np.float64)
        if not np.isfinite(base_reward):
            raise ProfileRewardError(f"base reward must be finite, got {base_reward}")
        if returns.ndim != 1 or not np.isfinite(returns).all():
            raise ProfileRewardError("net returns must be a finite vector")
        variance = float(np.sum(returns**2))
        lam = self.penalty_coefficient(profile)
        penalty = 0.5 * lam * variance
        parts = {
            "reward_base": float(base_reward),
            "realised_variance": variance,
            "lambda": lam,
            "risk_penalty": penalty,
            "reward": float(base_reward) - penalty,
        }
        if self.turnover_penalty > 0:  # keys added only when used: earlier outputs unchanged
            if not (np.isfinite(traded_notional) and traded_notional >= 0):
                raise ProfileRewardError(f"traded notional must be >= 0, got {traded_notional}")
            trading = self.turnover_penalty * float(traded_notional)
            parts.update(traded_notional=float(traded_notional), turnover_penalty=trading,
                         reward=parts["reward"] - trading)  # fmt: skip
        return parts
