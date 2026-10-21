"""Seed aggregation and configuration selection for the PPO grid (D-066, made operational by D-076).

Pure Python; it never reads data. Inputs are one validation metric value per run.

* Every configuration must have a value for every seed (no silent gaps).
* Any undefined or non-finite value stops selection (``undefined_metric: fail``).
* Per configuration: the median over seeds is the selection statistic. Mean, sample standard
  deviation (``ddof=1``), minimum, maximum and every seed's value are reported.
* Selection: the highest median. Every configuration whose median is within ``tie_tolerance``
  of the best is tied; ties go to the lower learning rate, then the smaller ``n_steps``, then
  the lower entropy coefficient. The result is deterministic and independent of input order.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


class SelectionError(ValueError):
    """Raised for incomplete or undefined inputs; no selection is made."""


@dataclass(frozen=True)
class ConfigurationSummary:
    configuration: int
    learning_rate: float
    n_steps: int
    ent_coef: float
    values: dict[int, float]  # seed -> metric value
    median: float
    mean: float
    std: float  # sample standard deviation (ddof=1)
    minimum: float
    maximum: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "configuration": self.configuration,
            "learning_rate": self.learning_rate,
            "n_steps": self.n_steps,
            "ent_coef": self.ent_coef,
            "values_by_seed": {str(k): v for k, v in sorted(self.values.items())},
            "median": self.median,
            "mean": self.mean,
            "std_ddof1": self.std,
            "min": self.minimum,
            "max": self.maximum,
        }


def summarise_configurations(runs: Sequence[dict[str, Any]]) -> list[ConfigurationSummary]:
    """``runs``: dicts with configuration, learning_rate, n_steps, ent_coef, seed, value."""
    by_config: dict[int, list[dict[str, Any]]] = {}
    for run in runs:
        value = run["value"]
        if value is None or not math.isfinite(float(value)):
            raise SelectionError(
                f"configuration {run['configuration']} seed {run['seed']}: metric is undefined "
                f"({value}); selection stops (undefined_metric: fail)"
            )
        by_config.setdefault(int(run["configuration"]), []).append(run)
    if not by_config:
        raise SelectionError("no runs to summarise")
    seed_sets = {c: sorted(int(r["seed"]) for r in rs) for c, rs in by_config.items()}
    reference = next(iter(seed_sets.values()))
    for configuration, seeds in seed_sets.items():
        if seeds != reference or len(set(seeds)) != len(seeds):
            raise SelectionError(
                f"configuration {configuration} has seeds {seeds}, expected {reference}"
            )
    if len(reference) < 2:
        raise SelectionError("at least two seeds per configuration are required")
    summaries = []
    for configuration in sorted(by_config):
        rs = by_config[configuration]
        params = {(r["learning_rate"], r["n_steps"], r["ent_coef"]) for r in rs}
        if len(params) != 1:
            raise SelectionError(f"configuration {configuration} mixes hyperparameters {params}")
        ((lr, n_steps, ent),) = params
        values = {int(r["seed"]): float(r["value"]) for r in rs}
        ordered = [values[s] for s in sorted(values)]
        summaries.append(
            ConfigurationSummary(
                configuration=configuration,
                learning_rate=float(lr),
                n_steps=int(n_steps),
                ent_coef=float(ent),
                values=values,
                median=statistics.median(ordered),
                mean=statistics.fmean(ordered),
                std=statistics.stdev(ordered),
                minimum=min(ordered),
                maximum=max(ordered),
            )
        )
    return summaries


def select_configuration(
    summaries: Sequence[ConfigurationSummary], tie_tolerance: float
) -> dict[str, Any]:
    """The selected configuration under the D-066 rule with the D-076 tie tolerance."""
    if not summaries:
        raise SelectionError("no configurations to select from")
    if not tie_tolerance >= 0:  # also rejects NaN
        raise SelectionError("tie_tolerance must be >= 0")
    best = max(s.median for s in summaries)
    tied = [s for s in summaries if best - s.median <= tie_tolerance]
    chosen = min(tied, key=lambda s: (s.learning_rate, s.n_steps, s.ent_coef, s.configuration))
    return {
        "selected_configuration": chosen.configuration,
        "selected_hyperparameters": {
            "learning_rate": chosen.learning_rate,
            "n_steps": chosen.n_steps,
            "ent_coef": chosen.ent_coef,
        },
        "selected_median": chosen.median,
        "best_median": best,
        "tie_tolerance": tie_tolerance,
        "tied_configurations": sorted(s.configuration for s in tied),
        "rule": "highest median validation net Sharpe over seeds; ties within tie_tolerance go "
        "to the lower learning rate, then the smaller n_steps, then the lower entropy "
        "coefficient (D-066, D-076)",
    }
