"""Regime diagnostics: a JSON document and a Markdown rendering.

Descriptive only. Test-period summaries are post-hoc diagnostics; nothing here feeds
back into the fitted thresholds.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.config import RegimeConfig
from adaptive_portfolio.data.splits import PARTITIONS
from adaptive_portfolio.features.engineering import FeatureSet, availability_summary
from adaptive_portfolio.regimes.rules import REGIME_LABELS, UNAVAILABLE, RegimeThresholds

DISCLAIMER = (
    "Regime labels are heuristic classifications from two causal features and "
    "training-calibrated thresholds. They are not objectively verified market states, "
    "and they say nothing about the performance of any strategy."
)


def _iso(value: pd.Timestamp) -> str:
    return value.date().isoformat()


def _transitions(labels: pd.Series) -> dict[str, Any]:
    """Counts and row-normalised proportions of consecutive labelled rows (same split)."""
    values = labels.to_numpy()
    counts: dict[str, dict[str, int]] = {}
    for current, following in pairwise(values):
        if UNAVAILABLE in (current, following):
            continue
        counts.setdefault(current, {}).setdefault(following, 0)
        counts[current][following] += 1
    ordered = {
        a: {b: counts[a][b] for b in REGIME_LABELS if b in counts[a]}
        for a in REGIME_LABELS
        if a in counts
    }
    proportions = {
        a: {b: n / sum(row.values()) for b, n in row.items()} for a, row in ordered.items()
    }
    changes = sum(n for a, row in ordered.items() for b, n in row.items() if a != b)
    pairs = sum(sum(row.values()) for row in ordered.values())
    return {
        "counts": ordered,
        "proportions": proportions,
        "regime_changes": changes,
        "consecutive_pairs": pairs,
    }


def build_regime_report(
    *,
    feature_set: FeatureSet,
    regimes: pd.DataFrame,
    split_labels: pd.Series,
    thresholds: RegimeThresholds,
    thresholds_mode: str,
    config: RegimeConfig,
    summary_features: Sequence[str],
    dataset: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the machine-readable regime report (deterministic for identical inputs)."""
    warnings: list[str] = []
    origin = dataset.get("data_origin")
    if origin in ("synthetic", "in_memory"):
        warnings.append(f"Input data origin is {origin!r}: NOT market data.")

    per_split: dict[str, Any] = {}
    for split in PARTITIONS:
        mask = (split_labels == split).to_numpy()
        labels = regimes.loc[mask, "regime"]
        total = int(mask.sum())
        available = labels[labels != UNAVAILABLE]
        counts = {r: int((labels == r).sum()) for r in REGIME_LABELS}
        regimes_info = {}
        for regime in REGIME_LABELS:
            dates = labels.index[(labels == regime).to_numpy()]
            regimes_info[regime] = {
                "count": counts[regime],
                "proportion_of_available": counts[regime] / len(available)
                if len(available)
                else 0.0,
                "first_date": _iso(dates[0]) if len(dates) else None,
                "last_date": _iso(dates[-1]) if len(dates) else None,
            }
            if len(available) and counts[regime] == 0:
                warnings.append(f"{split}: regime {regime} is absent.")
            elif len(available) and counts[regime] / len(available) < config.sparse_regime_fraction:
                warnings.append(
                    f"{split}: regime {regime} is sparse ({counts[regime]} of {len(available)} "
                    f"available rows < {config.sparse_regime_fraction:.0%})."
                )
            if split == "train" and len(dates):
                share = dates.year.value_counts().max() / len(dates)
                if share > config.concentration_warning_fraction:
                    year = int(dates.year.value_counts().idxmax())
                    warnings.append(
                        f"train: {share:.0%} of regime {regime} rows fall in {year} "
                        "(concentrated in one period)."
                    )
        components = {
            "trend": {
                k: int((regimes.loc[mask, "trend_label"] == k).sum())
                for k in ("negative", "neutral", "positive", UNAVAILABLE)
            },
            "volatility": {
                k: int((regimes.loc[mask, "volatility_label"] == k).sum())
                for k in ("low", "normal", "high", UNAVAILABLE)
            },
        }
        distributions = {}
        for regime in REGIME_LABELS:
            selected = feature_set.frame.loc[mask][(labels == regime).to_numpy()]
            if len(selected):
                distributions[regime] = {
                    name: {
                        "median": float(np.nanmedian(selected[name]))
                        if selected[name].notna().any()
                        else None,
                        "min": float(selected[name].min())
                        if selected[name].notna().any()
                        else None,
                        "max": float(selected[name].max())
                        if selected[name].notna().any()
                        else None,
                    }
                    for name in summary_features
                }
        per_split[split] = {
            "rows": total,
            "available_rows": len(available),
            "unavailable_rows": total - len(available),
            "regimes": regimes_info,
            "components": components,
            "transitions": _transitions(labels),
            "feature_distributions_by_regime": distributions,
        }

    excluded = int((~split_labels.isin(PARTITIONS)).sum())
    availability = availability_summary(feature_set)
    availability_by_split = {
        split: {
            name: int(feature_set.frame.loc[(split_labels == split).to_numpy(), name].isna().sum())
            for name in feature_set.frame.columns
        }
        for split in PARTITIONS
    }
    if thresholds.volatility_low == thresholds.volatility_high:
        warnings.append("volatility thresholds are equal: the 'normal' band is a single value.")
    if thresholds.trend_band == 0:
        warnings.append("trend band is 0: only exactly-zero momentum is 'neutral'.")

    return {
        "report_schema_version": 1,
        "disclaimer": DISCLAIMER,
        "warnings": warnings,
        "dataset": dict(dataset),
        "thresholds_mode": thresholds_mode,
        "thresholds": thresholds.to_dict(),
        "rows": {"total": len(split_labels), "excluded_from_partitions": excluded},
        "missing_features": {
            "warm_up_and_other_by_feature": availability,
            "missing_by_split": availability_by_split,
            "rule": "warm-up rows are NaN and never filled; regimes need both regime features",
        },
        "splits": per_split,
        "summary_features": list(summary_features),
    }


def render_regime_markdown(report: Mapping[str, Any]) -> str:
    th = report["thresholds"]["thresholds"]
    calibration = report["thresholds"]["calibration"]
    lines = [
        "# Regime report",
        "",
        f"> {report['disclaimer']}",
        "",
        *[f"> WARNING: {w}" for w in report["warnings"]],
        "",
        "## Definition (frozen thresholds)",
        "",
        f"- Mode: `{report['thresholds_mode']}`; input dataset "
        f"`{report['dataset'].get('processed_dataset_id')}` "
        f"(origin `{report['dataset'].get('data_origin')}`)",
        f"- Trend feature `{report['thresholds']['trend_feature']}`: negative < "
        f"{-th['trend_band']:.6f} <= neutral <= {th['trend_band']:.6f} < positive "
        f"(band = q{report['thresholds']['trend_neutral_quantile']} of |m| on train)",
        f"- Volatility feature `{report['thresholds']['volatility_feature']}`: low < "
        f"{th['volatility_low']:.6f} <= normal <= {th['volatility_high']:.6f} < high "
        f"(train quantiles {report['thresholds']['volatility_quantiles']})",
        f"- Calibrated on {calibration.get('rows_used')} training rows "
        f"({calibration.get('first_date_used')} to {calibration.get('last_date_used')}); "
        f"{calibration.get('rows_excluded_missing_features')} training rows excluded "
        "(features unavailable)",
        "",
        "## Regime counts by split",
        "",
        "| Regime | " + " | ".join(PARTITIONS) + " |",
        "| --- | " + " | ".join("---" for _ in PARTITIONS) + " |",
    ]
    for regime in (*REGIME_LABELS, UNAVAILABLE):
        cells = []
        for split in PARTITIONS:
            info = report["splits"][split]
            if regime == UNAVAILABLE:
                cells.append(str(info["unavailable_rows"]))
            else:
                r = info["regimes"][regime]
                cells.append(f"{r['count']} ({r['proportion_of_available']:.1%})")
        lines.append(f"| {regime} | " + " | ".join(cells) + " |")
    lines += ["", "## Regime changes", ""]
    for split in PARTITIONS:
        t = report["splits"][split]["transitions"]
        rate = t["regime_changes"] / t["consecutive_pairs"] if t["consecutive_pairs"] else 0.0
        lines.append(
            f"- {split}: {t['regime_changes']} changes over {t['consecutive_pairs']} "
            f"consecutive pairs ({rate:.1%})"
        )
    lines += [
        "",
        "## Median feature values by regime (training split)",
        "",
        "| Regime | " + " | ".join(report["summary_features"]) + " |",
        "| --- | " + " | ".join("---" for _ in report["summary_features"]) + " |",
    ]
    train_dist = report["splits"]["train"]["feature_distributions_by_regime"]
    for regime, stats in train_dist.items():
        cells = [
            "n/a" if stats[name]["median"] is None else f"{stats[name]['median']:+.4f}"
            for name in report["summary_features"]
        ]
        lines.append(f"| {regime} | " + " | ".join(cells) + " |")
    lines += ["", f"Rows outside all partitions: {report['rows']['excluded_from_partitions']}.", ""]
    return "\n".join(lines)
