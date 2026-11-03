"""E4 vs E1 figures from saved, verified evaluations (D-088; needs the ``viz`` extra).

Every PNG has a JSON sidecar listing its source files with their SHA-256, like
:mod:`adaptive_portfolio.visualization.plots`. Nothing here computes a new result: the inputs
are the written ``episode_metrics.csv``, ``interactions.csv`` and ``seed_table.csv``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from adaptive_portfolio.data import cache
from adaptive_portfolio.visualization.plots import DPI, PALETTE, _pyplot

VOL = "annualised.net_annualised_volatility"


def _save(fig, path: Path, sources: list[Path], description: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    sidecar = {"figure": path.name, "description": description,
               "sources": {str(s): cache.file_sha256(s) for s in sources}}  # fmt: skip
    path.with_suffix(".json").write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    return path


def make_figures(treatment_dir: Path, control_dir: Path, comparison_dir: Path, out: Path) -> list:
    """Three figures: risk response to a(U), the RT x RC grid, and per-seed Sharpe."""
    plt = _pyplot()
    t_path, c_path = treatment_dir / "episode_metrics.csv", control_dir / "episode_metrics.csv"
    t, c = pd.read_csv(t_path), pd.read_csv(c_path)
    written = []

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, (label, frame, exp) in zip(
        axes, (("E1 (D-064 reward)", c, "E1"), ("E4 (profile reward)", t, "E4")), strict=True
    ):
        part = frame[(frame["experiment"] == exp) & (frame["profile_set"] == "in_distribution")]
        a = np.minimum(part["profile_risk_tolerance"], part["profile_risk_capacity"])
        for i, (seed, idx) in enumerate(part.groupby("seed").groups.items()):
            ax.scatter(a.loc[idx], 100 * part.loc[idx, VOL], s=10, color=PALETTE[i],
                       label=f"seed {int(seed)}")  # fmt: skip
        ax.set_title(label)
        ax.set_xlabel("risk acceptance a = min(RT, RC)")
    axes[0].set_ylabel("validation net volatility (% p.a.)")
    axes[1].legend(frameon=False, ncol=1, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    written.append(
        _save(
            fig,
            out / "e4_volatility_vs_acceptance.png",
            [t_path, c_path],
            "On-path validation net volatility against a(U), 32 profiles x 5 seeds",
        )
    )
    plt.close(fig)

    i_path = treatment_dir / "interactions.csv"
    grid = pd.read_csv(i_path)
    part = grid[(grid["arm"] == "main") & (grid["first"] == "risk_tolerance")
                & (grid["second"] == "risk_capacity")]  # fmt: skip
    table = part.groupby(["second_value", "first_value"])["target_equity"].mean().unstack()
    fig, ax = plt.subplots(figsize=(4.2, 3.4))
    image = ax.imshow(100 * table.to_numpy(), origin="lower", cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(table.columns)), [f"{v:.2f}" for v in table.columns])
    ax.set_yticks(range(len(table.index)), [f"{v:.2f}" for v in table.index])
    ax.set_xlabel("risk tolerance RT")
    ax.set_ylabel("risk capacity RC")
    ax.set_title("E4 mean target equity (%), state-matched")
    fig.colorbar(image, ax=ax)
    written.append(
        _save(
            fig,
            out / "e4_equity_rt_rc_grid.png",
            [i_path],
            "Mean over seeds of target equity on the centre trajectory, H=L=G=0.5",
        )
    )
    plt.close(fig)

    s_path = comparison_dir / "seed_table.csv"
    seeds = pd.read_csv(s_path)
    arms = [("E0", "-"), ("E1", "centre"), ("E4", "centre")]
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    width = 0.25
    seed_values = sorted(seeds["seed"].unique())
    for j, (arm, name) in enumerate(arms):
        part = seeds[(seeds["arm"] == arm) & (seeds["profile_set"] == name)].set_index("seed")
        ax.bar(np.arange(len(seed_values)) + (j - 1) * width,
               part.loc[seed_values, "net_sharpe"], width, label=arm,
               color=PALETTE[j])  # fmt: skip
    base = t[t["experiment"] == "baseline"]
    for k, (_, row) in enumerate(base.iterrows()):
        ax.axhline(row["annualised.net_sharpe"], color="grey", lw=0.8, ls=("--", ":", "-.")[k % 3],
                   label=row["arm"])  # fmt: skip
    ax.set_xticks(range(len(seed_values)), [str(s) for s in seed_values])
    ax.set_xlabel("seed")
    ax.set_ylabel("validation net Sharpe")
    ax.legend(frameon=False, fontsize=7, ncol=2)
    written.append(
        _save(
            fig,
            out / "e4_sharpe_by_seed.png",
            [s_path, t_path],
            "Validation net Sharpe per seed (centre profile) with the baselines",
        )
    )
    plt.close(fig)
    return written


def make_fixed_risk_figures(comparison_dir: Path, out: Path) -> list:
    """E5: per-seed volatility, equity and Sharpe for lambda = 0 vs 9, both splits (D-089)."""
    plt = _pyplot()
    path = comparison_dir / "seed_table.csv"
    table = pd.read_csv(path)
    panels = (("net_volatility", "net volatility (% p.a.)", 100),
              ("target_equity", "mean target equity (%)", 100),
              ("net_sharpe", "net Sharpe", 1))  # fmt: skip
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.6))
    for row, split in enumerate(("train", "validation")):
        part = table[table["split"] == split]
        for col, (metric, label, scale) in enumerate(panels):
            ax = axes[row, col]
            for i, seed in enumerate(sorted(part["seed"].unique())):
                values = [part[(part["seed"] == seed) & (part["arm"] == arm)][metric].iloc[0]
                          for arm in ("E5L", "E5H")]  # fmt: skip
                ax.plot([0, 9], [scale * v for v in values], marker="o", color=PALETTE[i],
                        label=f"seed {int(seed)}")  # fmt: skip
            ax.set_xticks([0, 9], ["λ = 0 (E5L)", "λ = 9 (E5H)"])
            ax.set_title(f"{split}: {label}")
    axes[0, 2].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written = [
        _save(
            fig,
            out / "e5_fixed_lambda_by_seed.png",
            [path],
            "Seed-paired E5L vs E5H metrics on the training and validation splits",
        )
    ]
    plt.close(fig)
    return written
