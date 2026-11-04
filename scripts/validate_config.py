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
    apply_walk_forward_fold,
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
            "turnover_k0.yaml",
            "turnover_k1.yaml",
            "turnover_k2.yaml",  # E7 arms
            "turnover_refine_k0.yaml",
            "turnover_refine_k1.yaml",
            "turnover_refine_k2.yaml",
            "turnover_refine_k3.yaml",  # E8 arms
            "confirmation_k0.yaml",
            "confirmation_k1.yaml",  # E9 arms
            *(f"walk_forward_{f}_k{k}.yaml" for f in "abc" for k in (0, 1)),  # E10 arms
        )
        for name in names:
            if (args.config_dir / name).is_file():
                profiles[name] = load_profile_experiment_config(args.config_dir / name)
        for name, experiment in profiles.items():
            if agent is not None and (
                experiment.base_configuration not in {s.configuration for s in agent.run_specs()}
                # E9 (D-093): declared extension seeds lie outside the grid by design.
                or not set(experiment.seeds) - set(experiment.extension_seeds) <= set(agent.seeds)
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
        e7 = [profiles.get(f"turnover_k{x}.yaml") for x in (0, 1, 2)]
        if all(x is not None for x in e7):

            def core7(d):
                reward = {k: v for k, v in d["reward"].items()
                          if k not in ("turnover_penalty", "formula")}  # fmt: skip
                return {k: v for k, v in d.items() if k not in ("label", "reward")} | {
                    "reward": reward
                }

            cores = [core7(x.to_dict()) for x in e7]
            kap = [x.reward.turnover_penalty for x in e7]
            if any(c != cores[0] for c in cores) or not 0 == kap[0] < kap[1] < kap[2]:
                raise ConfigError("E7 arms must differ only in label and turnover_penalty")
        e8 = [profiles.get(f"turnover_refine_k{x}.yaml") for x in range(4)]
        if all(x is not None for x in e8):

            def core8(d):
                reward = {k: v for k, v in d["reward"].items()
                          if k not in ("turnover_penalty", "formula")}  # fmt: skip
                return {k: v for k, v in d.items() if k not in ("label", "reward")} | {
                    "reward": reward
                }

            cores = [core8(x.to_dict()) for x in e8]
            kap = [x.reward.turnover_penalty for x in e8]
            if (
                any(c != cores[0] for c in cores)
                or kap[0] != 0
                or kap != sorted(set(kap))
                or any(x.reward.fixed_lambda != 0 for x in e8)
            ):
                raise ConfigError(
                    "E8 arms must differ only in label and turnover_penalty (ascending, lambda 0)"
                )
        e9 = [profiles.get(f"confirmation_k{x}.yaml") for x in range(2)]
        if all(x is not None for x in e9):

            def core9(d):
                reward = {k: v for k, v in d["reward"].items()
                          if k not in ("turnover_penalty", "formula")}  # fmt: skip
                return {k: v for k, v in d.items() if k not in ("label", "reward")} | {
                    "reward": reward
                }

            grid_seeds = {s.seed for s in agent.run_specs()} if agent is not None else set()
            if (
                core9(e9[0].to_dict()) != core9(e9[1].to_dict())
                or [x.reward.turnover_penalty for x in e9] != [0.0, 0.0015]
                or any(x.reward.fixed_lambda != 0 for x in e9)
                or any(x.extension_seeds != tuple(range(47, 57)) for x in e9)
                or any(set(x.extension_seeds) & grid_seeds for x in e9)
            ):
                raise ConfigError(
                    "E9 arms must differ only in label and turnover_penalty (0, 0.0015), with "
                    "lambda 0 and extension seeds 47-56 outside the grid"
                )
        e10 = {f: [profiles.get(f"walk_forward_{f}_k{k}.yaml") for k in (0, 1)] for f in "abc"}
        if all(x is not None for pair in e10.values() for x in pair):

            def core10(d):
                reward = {k: v for k, v in d["reward"].items()
                          if k not in ("turnover_penalty", "formula")}  # fmt: skip
                drop = ("label", "reward", "walk_forward_fold")
                return {k: v for k, v in d.items() if k not in drop} | {"reward": reward}

            ref = core10(e10["a"][0].to_dict())
            references = []
            for pair in e10.values():
                folds = [x.walk_forward_fold for x in pair]
                if (
                    any(core10(x.to_dict()) != ref for x in pair)
                    or folds[0] != folds[1]
                    or [x.reward.turnover_penalty for x in pair] != [0.0, 0.0015]
                    or any(x.reward.fixed_lambda != 0 for x in pair)
                    or any(x.extension_seeds for x in pair)
                ):
                    raise ConfigError(
                        "E10 arms must differ only in label and turnover_penalty (0, 0.0015) "
                        "within a fold, and only in the fold block across folds (lambda 0)"
                    )
                references.append(apply_walk_forward_fold(config, folds[0])[1])
            if references != [False, False, True]:
                raise ConfigError("E10 folds A and B must lie before the test period and fold C "
                                  "must equal the D-009 split")  # fmt: skip
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
    if all(x is not None for x in e7):
        print(
            f"  E7 arms      : kappa {', '.join(f'{x.reward.turnover_penalty:g}' for x in e7)} "
            f"({', '.join(x.label for x in e7)}), lambda 0 (D-091; Provisional (delegated))"
        )
    if all(x is not None for pair in e10.values() for x in pair):
        folds = "; ".join(
            f"{p[0].walk_forward_fold.id} train ..{p[0].walk_forward_fold.splits.train.end} "
            f"val {p[0].walk_forward_fold.splits.validation.start.year}-"
            f"{p[0].walk_forward_fold.splits.validation.end.year}"
            for p in e10.values()
        )
        print(f"  E10 folds    : {folds}; kappa 0 / 0.0015, lambda 0 (D-094; Provisional "
              "(delegated))")  # fmt: skip
    if all(x is not None for x in e9):
        print(
            f"  E9 arms      : kappa {', '.join(f'{x.reward.turnover_penalty:g}' for x in e9)} "
            f"({', '.join(x.label for x in e9)}), seeds {e9[0].seeds[0]}-{e9[0].seeds[-1]} "
            f"(extension {e9[0].extension_seeds[0]}-{e9[0].extension_seeds[-1]}), lambda 0 "
            "(D-093; Provisional (delegated))"
        )
    if all(x is not None for x in e8):
        print(
            f"  E8 arms      : kappa {', '.join(f'{x.reward.turnover_penalty:g}' for x in e8)} "
            f"({', '.join(x.label for x in e8)}), lambda 0 (D-092; Provisional (delegated))"
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
