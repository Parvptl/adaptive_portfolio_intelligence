"""Validate the project configuration and print a short summary.

Usage::

    python scripts/validate_config.py [--config-dir configs]

Exits with a non-zero status if any configuration file is invalid.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from adaptive_portfolio.config import (
    ConfigError,
    load_agent_config,
    load_evaluation_config,
    load_preregistration,
    load_profile_experiment_config,
    load_project_config,
    load_workflow_config,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    args = parser.parse_args(argv)

    try:
        config = load_project_config(args.config_dir)
        agent_path = args.config_dir / "agent.yaml"
        agent = load_agent_config(agent_path) if agent_path.is_file() else None
        evaluation_path = args.config_dir / "evaluation.yaml"
        evaluation = load_evaluation_config(evaluation_path) if evaluation_path.is_file() else None
        workflow_path = args.config_dir / "workflow.yaml"
        workflow = load_workflow_config(workflow_path) if workflow_path.is_file() else None
        prereg_path = args.config_dir / "preregistration.yaml"
        prereg = load_preregistration(prereg_path) if prereg_path.is_file() else None
        profiles = {}
        names = (
            "profile_experiment.yaml",
            "profile_reward_experiment.yaml",  # E1, E4
            "fixed_risk_low.yaml",
            "fixed_risk_high.yaml",  # E5 arms
            "dose_response_l0.yaml",
            "dose_response_l3.yaml",
            "dose_response_l9.yaml",  # E6 arms
        )
        for name in names:
            if (args.config_dir / name).is_file():
                profiles[name] = load_profile_experiment_config(args.config_dir / name)
        for name, experiment in profiles.items():
            if agent is not None and (
                experiment.base_configuration not in {s.configuration for s in agent.run_specs()}
                or not set(experiment.seeds) <= set(agent.seeds)
            ):
                raise ConfigError(f"{name}: base_configuration and seeds must come from agent.yaml")
        profile = profiles.get("profile_experiment.yaml")
        reward = profiles.get("profile_reward_experiment.yaml")
        if reward is not None and reward.reward is None:
            raise ConfigError("profile_reward_experiment.yaml must define the E4 reward")
        if reward is not None and profile is not None and reward.output_dir == profile.output_dir:
            raise ConfigError("E4 must write under its own output root, not E1's")

        def core(d):
            return {k: v for k, v in d.items() if k not in ("label", "reward")} | {
                "reward": {k: v for k, v in d["reward"].items() if k != "fixed_lambda"}
            }

        e5 = [profiles.get(n) for n in ("fixed_risk_low.yaml", "fixed_risk_high.yaml")]
        if all(x is not None for x in e5):
            low, high = (x.to_dict() for x in e5)
            if core(low) != core(high) or not (
                e5[0].reward.fixed_lambda < e5[1].reward.fixed_lambda
            ):
                raise ConfigError("E5 arms must differ only in label and fixed_lambda (low < high)")
        e6 = [profiles.get(f"dose_response_l{x}.yaml") for x in (0, 3, 9)]
        if all(x is not None for x in e6):
            cores = [core(x.to_dict()) for x in e6]
            lams = [x.reward.fixed_lambda for x in e6]
            if any(c != cores[0] for c in cores) or not lams[0] < lams[1] < lams[2]:
                raise ConfigError("E6 arms must differ only in label and fixed_lambda (ascending)")
    except ConfigError as exc:
        print(f"Invalid configuration: {exc}", file=sys.stderr)
        return 1

    splits = config.experiment.splits
    print(f"Configuration OK ({args.config_dir})")
    print(f"  provider     : {config.data.provider} (provisional)")
    print(f"  universe     : {', '.join(config.data.universe)}")
    print(f"  frequency    : {config.data.frequency}")
    print(f"  train        : {splits.train.start} -> {splits.train.end}")
    print(f"  validation   : {splits.validation.start} -> {splits.validation.end}")
    print(f"  test         : {splits.test.start} -> {splits.test.end}")
    print(
        f"  costs (bps)  : {config.environment.transaction_cost_bps} + slippage "
        f"{config.environment.slippage_bps} (provisional)"
    )
    print(f"  seed         : {config.experiment.seed}")
    if agent is not None:
        print(
            f"  agent (PPO)  : {len(agent.run_specs())} runs = "
            f"{len(agent.run_specs()) // len(agent.seeds)} configurations x "
            f"{len(agent.seeds)} seeds, {agent.total_timesteps} timesteps each"
        )
    if evaluation is not None:
        print(
            f"  evaluation   : grid {evaluation.grid_id}, {evaluation.split} split, "
            f"{evaluation.policy_actions} actions, {evaluation.seed_aggregation} "
            f"{evaluation.selection_metric} (protocol D-076: see decision log for status)"
        )
    if workflow is not None:
        print(
            f"  workflow     : evaluation {workflow.validation_evaluation_dir.as_posix()}, "
            f"backtest {workflow.baseline_backtest_dir.as_posix()} (saved artifacts only)"
        )
    if prereg is not None:
        print(
            f"  test prereg : {prereg.status.upper()}, {len(prereg.open_items())} blocking "
            f"item(s), sha256 {prereg.sha256()[:16]}... (Gate 3; see the approval checklist)"
        )
    if profile is not None:
        excluded = profile.arms["heldout"].to_dict()["exclude"]
        print(
            f"  profile PPO  : configuration {profile.base_configuration} x seeds "
            f"{list(profile.seeds)}, arms main and heldout (excluded {excluded}); splits "
            f"{', '.join(profile.splits)} (D-085; details Provisional (delegated))"
        )
    if all(x is not None for x in e5):
        print(
            f"  E5 arms      : {e5[0].label} lambda {e5[0].reward.fixed_lambda:g} vs "
            f"{e5[1].label} lambda {e5[1].reward.fixed_lambda:g}, constant profile 0.5 "
            "(D-089; Provisional (delegated))"
        )
    if all(x is not None for x in e6):
        print(
            f"  E6 arms      : lambda {', '.join(f'{x.reward.fixed_lambda:g}' for x in e6)} "
            f"({', '.join(x.label for x in e6)}), constant profile 0.5 (D-090; Provisional "
            "(delegated))"
        )
    if reward is not None:
        spec = reward.reward
        print(
            f"  E4 reward    : r_base - (lambda/2) RV, gamma {spec.gamma_min:g}.."
            f"{spec.gamma_max:g} from min(RT, RC); output {reward.output_dir.as_posix()} "
            "(D-088; Provisional (delegated))"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
