"""Publication-quality figures from saved results (needs the optional ``viz`` extra: matplotlib).

Every figure is written as a PNG together with a JSON sidecar (same name, ``.json``) that records
its source files with their SHA-256, the method and the scope label, so each figure can be traced
to the result it shows. Nothing here computes a result: inputs are saved summaries or ledgers.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adaptive_portfolio.data import cache
from adaptive_portfolio.explainability.regime_analysis import REGIME_ORDER

# Okabe-Ito palette (colour-blind safe), then greys for cash.
PALETTE = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#999999")
DPI = 200


def _pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            'figures need matplotlib: pip install -e ".[viz]" (see docs/technical_handbook.md)'
        ) from exc
    plt.rcParams.update({
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 8,
        "axes.spines.top": False, "axes.spines.right": False, "svg.hashsalt": "api",
    })  # fmt: skip
    return plt


def save_figure(fig: Any, path: Path, provenance: Mapping[str, Any]) -> Path:
    """Write ``path`` (PNG, deterministic metadata) and its ``.json`` provenance sidecar."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", metadata={"Software": None})
    _pyplot().close(fig)
    sidecar = {"figure": path.name, "figure_sha256": cache.file_sha256(path), **provenance}
    path.with_suffix(".json").write_text(
        json.dumps(sidecar, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return path


def _regime_rows(summary: pd.DataFrame) -> pd.DataFrame:
    rows = summary.set_index("regime").reindex(list(REGIME_ORDER))
    if rows["sessions"].isna().any():
        raise ValueError("summary must contain every regime of REGIME_ORDER")
    return rows


def plot_regime_allocation(
    summary: pd.DataFrame, assets: Sequence[str], path: Path, *, title: str,
    provenance: Mapping[str, Any],
) -> Path:  # fmt: skip
    """Stacked mean allocation per regime for one strategy; n and episodes annotated."""
    plt = _pyplot()
    rows = _regime_rows(summary)
    columns = [*assets, "CASH"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    y = np.arange(len(rows))
    left = np.zeros(len(rows))
    for i, asset in enumerate(columns):
        values = rows[f"mean_weight_{asset}"].fillna(0.0).to_numpy()
        ax.barh(y, values, left=left, color=PALETTE[i % len(PALETTE)], label=asset,
                edgecolor="white", linewidth=0.4)  # fmt: skip
        left += values
    for yi, (_, row) in zip(y, rows.iterrows(), strict=True):
        note = f"n={int(row['sessions'])}, ep={int(row['episodes'])}"
        if row["sessions"] == 0:
            note = "absent (n=0)"
        elif not row["sufficient"]:
            note += " (small)"
        ax.text(1.01, yi, note, va="center", fontsize=7, transform=ax.get_yaxis_transform())
    ax.set_yticks(y, list(rows.index))
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("mean end-of-row weight")
    ax.set_title(title)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.14), frameon=False)
    return save_figure(fig, path, provenance)


def plot_regime_metric(
    summary: pd.DataFrame, metric: str, path: Path, *, ylabel: str, title: str,
    provenance: Mapping[str, Any],
) -> Path:  # fmt: skip
    """Grouped bars of one metric per regime and strategy; small samples hatched."""
    plt = _pyplot()
    strategies = sorted(summary["strategy"].unique())
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    x = np.arange(len(REGIME_ORDER))
    width = 0.8 / max(len(strategies), 1)
    for i, strategy in enumerate(strategies):
        rows = _regime_rows(summary[summary["strategy"] == strategy])
        values = rows[metric].to_numpy(dtype=float)
        bars = ax.bar(x + (i - (len(strategies) - 1) / 2) * width, np.nan_to_num(values),
                      width, color=PALETTE[i % len(PALETTE)], label=strategy)  # fmt: skip
        for bar, ok, n in zip(bars, rows["sufficient"], rows["sessions"], strict=True):
            if not ok:
                bar.set_hatch("///")
                bar.set_alpha(0.45)
            if n == 0:
                bar.set_visible(False)
    counts = _regime_rows(summary[summary["strategy"] == strategies[0]])["sessions"]
    ax.set_xticks(x, [f"{r}\nn={int(n)}" for r, n in zip(REGIME_ORDER, counts, strict=True)],
                  rotation=45, ha="right", fontsize=7)  # fmt: skip
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    from matplotlib.patches import Patch  # plain swatches: the first bar may be hatched

    ax.legend(handles=[Patch(color=PALETTE[i % len(PALETTE)], label=s)
                       for i, s in enumerate(strategies)], frameon=False, fontsize=7)  # fmt: skip
    ax.text(0.0, -0.42, "Hatched: fewer sessions than the minimum (descriptive only). "
            "No confidence intervals; differences are not tested.", fontsize=7,
            transform=ax.transAxes)  # fmt: skip
    return save_figure(fig, path, provenance)


def plot_sensitivity(
    table: pd.DataFrame, path: Path, *, title: str, provenance: Mapping[str, Any]
) -> Path:
    """Mean L1 change of decided targets per permuted input group, with the repeat range."""
    plt = _pyplot()
    rows = table.sort_values("mean_l1_change")
    fig, ax = plt.subplots(figsize=(6.4, 0.45 * len(rows) + 1.2))
    y = np.arange(len(rows))
    low = rows["mean_l1_change"] - rows["min_l1_change"]
    high = rows["max_l1_change"] - rows["mean_l1_change"]
    ax.barh(y, rows["mean_l1_change"], xerr=[low, high], color=PALETTE[0], capsize=3)
    ax.set_yticks(y, [f"{g} ({n})" for g, n in zip(rows["group"], rows["n_inputs"], strict=True)])
    ax.set_xlabel("mean L1 change of target weights (0 to 2); bars: min-max over repeats")
    ax.set_title(title)
    return save_figure(fig, path, provenance)


def plot_value_paths(
    ledgers: pd.DataFrame, strategies: Sequence[str], path: Path, *, initial_capital: float,
    title: str, provenance: Mapping[str, Any],
) -> Path:  # fmt: skip
    """Net value (growth of 1) and drawdown paths of the given strategies from saved ledgers."""
    plt = _pyplot()
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(7.6, 5.2), sharex=True,
                                      gridspec_kw={"height_ratios": [2, 1]})  # fmt: skip
    for i, name in enumerate(strategies):
        rows = ledgers[ledgers["strategy"] == name].sort_values("date")
        if rows.empty:
            raise ValueError(f"no ledger rows for {name!r}")
        dates = pd.to_datetime(rows["date"])
        growth = rows["value"].to_numpy(dtype=float) / initial_capital
        peak = np.maximum.accumulate(np.r_[1.0, growth])[1:]
        style = {"color": PALETTE[i % len(PALETTE)], "linewidth": 1.1}
        top.plot(dates, growth, label=name, **style)
        bottom.plot(dates, growth / peak - 1.0, **style)
    top.set_ylabel("net value (start = 1)")
    bottom.set_ylabel("drawdown")
    top.set_title(title)
    top.legend(frameon=False, fontsize=7, ncol=2)
    return save_figure(fig, path, provenance)


def plot_mean_allocation(
    allocations: pd.DataFrame, assets: Sequence[str], path: Path, *, title: str,
    provenance: Mapping[str, Any],
) -> Path:  # fmt: skip
    """Stacked time-averaged weights per strategy (``mean_weight_<asset>`` columns)."""
    plt = _pyplot()
    columns = [*assets, "CASH"]
    fig, ax = plt.subplots(figsize=(7.2, 0.4 * len(allocations) + 1.4))
    y = np.arange(len(allocations))
    left = np.zeros(len(allocations))
    for i, asset in enumerate(columns):
        values = allocations[f"mean_weight_{asset}"].to_numpy(dtype=float)
        ax.barh(y, values, left=left, color=PALETTE[i % len(PALETTE)], label=asset)
        left += values
    ax.set_yticks(y, list(allocations["strategy"]))
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("time-averaged end-of-row weight")
    ax.set_title(title)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False)
    return save_figure(fig, path, provenance)
