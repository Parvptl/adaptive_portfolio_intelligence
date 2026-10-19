"""Milestone 5.3: PPO agent configuration (configs/agent.yaml; no RL library needed)."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from adaptive_portfolio.config import AgentConfig, ConfigError, load_agent_config, load_yaml
from conftest import CONFIG_DIR

RAW = load_yaml(CONFIG_DIR / "agent.yaml")


def test_default_agent_config_matches_d066() -> None:
    agent = load_agent_config(CONFIG_DIR / "agent.yaml")
    specs = agent.run_specs()
    assert agent.seeds == (42, 43, 44, 45, 46)
    assert agent.total_timesteps == 100_000 and agent.batch_size == 64
    assert len(specs) == 40 and len({s.configuration for s in specs}) == 8
    assert {(s.learning_rate, s.n_steps, s.ent_coef) for s in specs} == {
        (lr, n, c) for lr in (3e-4, 1e-4) for n in (512, 1024) for c in (0.0, 0.01)
    }
    assert [s.seed for s in specs[:5]] == [42, 43, 44, 45, 46]  # configuration-major order
    assert agent.device == "cpu" and agent.torch_num_threads == 1
    assert (agent.execution_mode, agent.run_timeout_seconds, agent.on_failure) == (
        "sequential",
        900,
        "stop",
    )


def _with(path: str, value: Any) -> dict[str, Any]:
    raw = copy.deepcopy(RAW)
    *parents, key = path.split(".")
    target = raw
    for name in parents:
        target = target[name]
    target[key] = value
    return raw


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("algorithm", "sac", "only 'ppo'"),
        ("device", "cuda", "only 'cpu'"),
        ("seeds", [42, 42], "unique"),
        ("seeds", [-1], "integer in"),
        ("total_timesteps", 0, ">= 1"),
        ("grid.n_steps", [500], "multiples of agent.batch_size"),
        ("grid.learning_rate", [0.0], r"\(0, 1\)"),
        ("grid.ent_coef", [-0.1], ">= 0"),
        ("fixed.gamma", 1.5, r"\(0, 1\]"),
        ("fixed.activation", "gelu", "not one of"),
        ("fixed.net_arch", [], "non-empty list"),
        ("output_dir", "", "non-empty string"),
        ("execution.mode", "parallel", "separate approval"),
        ("execution.on_failure", "continue", "only 'stop'"),
        ("execution.run_timeout_seconds", 10, ">= 60"),
    ],
)
def test_invalid_agent_config_is_rejected(path: str, value: Any, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        AgentConfig.from_dict(_with(path, value))


def test_unknown_agent_keys_are_rejected() -> None:
    with pytest.raises(ConfigError, match="unknown key"):
        AgentConfig.from_dict({**RAW, "learning_rate": 0.1})
