"""E12 regime observation ablation wrapper (D-096; ``rl`` extra).

The wrapper must remove exactly the 9 regime one-hot inputs and change nothing else.
"""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.rl
gym = pytest.importorskip("gymnasium")

from gymnasium.utils.env_checker import check_env  # noqa: E402

from adaptive_portfolio.environment.observation_ablation import (  # noqa: E402
    RegimeAblatedEnv,
    apply_ablation,
)
from adaptive_portfolio.environment.profile_env import ProfileConditionedEnv  # noqa: E402
from adaptive_portfolio.environment.profiles import ProfileSampling  # noqa: E402
from adaptive_portfolio.regimes.rules import REGIME_LABELS  # noqa: E402
from test_portfolio_env import KNOWN_WARNINGS, N_ASSETS, N_FEATURES, _env  # noqa: E402

N_REGIME = len(REGIME_LABELS)


def _actions(env, n: int, seed: int = 3) -> list[np.ndarray]:
    env.action_space.seed(seed)
    return [env.action_space.sample() for _ in range(n)]


def test_exactly_the_regime_block_is_removed() -> None:
    full, ablated = _env(), RegimeAblatedEnv(_env())
    assert full.observation_space.shape == (N_FEATURES + N_REGIME + N_ASSETS + 1,)
    assert ablated.observation_space.shape == (N_FEATURES + N_ASSETS + 1,)
    regime = slice(N_FEATURES, N_FEATURES + N_REGIME)
    assert np.array_equal(ablated.observation_space.low,
                          np.delete(full.observation_space.low, regime))  # fmt: skip
    obs_full, _ = full.reset(seed=1)
    obs_ablated, _ = ablated.reset(seed=1)
    assert obs_full[regime].sum() == 1.0  # the one-hot block is really there ...
    assert np.array_equal(obs_ablated, np.delete(obs_full, regime))  # ... and only it goes
    assert np.array_equal(obs_ablated[:N_FEATURES], obs_full[:N_FEATURES])  # scaled features
    assert np.array_equal(obs_ablated[N_FEATURES:], obs_full[N_FEATURES + N_REGIME :])  # weights


def test_rewards_info_and_accounting_are_unchanged() -> None:
    full, ablated = _env(), RegimeAblatedEnv(_env())
    actions = _actions(full, full.n_steps)
    full.reset(seed=0)
    ablated.reset(seed=0)
    for action in actions:
        a = full.step(action)
        b = ablated.step(action)
        assert np.array_equal(b[0], np.delete(a[0], slice(N_FEATURES, N_FEATURES + N_REGIME)))
        assert a[1:4] == b[1:4]  # reward, terminated, truncated
        assert a[4].keys() == b[4].keys()
        if a[2]:
            break
    assert full.ledger_frame().equals(ablated.unwrapped.ledger_frame())


def test_gymnasium_api_and_the_profile_wrapper_on_top() -> None:
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        check_env(RegimeAblatedEnv(_env()), skip_render_check=True)
    known = (*KNOWN_WARNINGS, "different from the unwrapped version")  # any wrapper
    assert [str(w.message) for w in caught if not any(k in str(w.message) for k in known)] == []
    conditioned = ProfileConditionedEnv(RegimeAblatedEnv(_env()),
                                        ProfileSampling.from_dict({"distribution": "constant",
                                                                   "constant": 0.5}, "main"),
                                        seed=42)  # fmt: skip
    observation, _ = conditioned.reset(seed=0)
    assert observation.shape == (N_FEATURES + N_ASSETS + 1 + 5,)
    assert np.allclose(observation[-5:], 0.5)  # the profile is still appended last


def test_apply_ablation_is_opt_in() -> None:
    env = _env()
    assert apply_ablation(env, None) is env
    assert isinstance(apply_ablation(env, "regime"), RegimeAblatedEnv)
    with pytest.raises(ValueError, match="unknown observation ablation"):
        apply_ablation(env, "features")
