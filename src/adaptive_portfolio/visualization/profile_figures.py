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


def make_dose_response_figures(comparison_dir: Path, out: Path) -> list:
    """E6: risk metrics against lambda by seed and split, and the mean allocation per lambda."""
    plt = _pyplot()
    path = comparison_dir / "seed_table.csv"
    table = pd.read_csv(path)
    table = table[table["arm"] != "E0"]
    panels = (("net_volatility", "net volatility (% p.a.)", 100),
              ("net_max_drawdown", "net max drawdown (%)", 100),
              ("target_equity", "mean target equity (%)", 100))  # fmt: skip
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.8))
    for row, split in enumerate(("train", "validation")):
        part = table[table["split"] == split]
        for col, (metric, label, scale) in enumerate(panels):
            ax = axes[row, col]
            for i, (seed, g) in enumerate(part.groupby("seed")):
                g = g.sort_values("fixed_lambda")
                ax.plot(g["fixed_lambda"], scale * g[metric], marker="o", color=PALETTE[i],
                        alpha=0.85, label=f"seed {int(seed)}")  # fmt: skip
            med = part.groupby("fixed_lambda")[metric].median()
            ax.plot(med.index, scale * med.to_numpy(), color="black", lw=2.2, ls="--",
                    label="median")  # fmt: skip
            ax.set_xticks(sorted(part["fixed_lambda"].unique()))
            ax.set_xlabel("fixed risk aversion λ")
            ax.set_title(f"{split}: {label}")
    axes[0, 2].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written = [
        _save(
            fig,
            out / "e6_risk_vs_lambda.png",
            [path],
            "Seed trajectories and median of risk metrics against lambda, both splits",
        )
    ]
    plt.close(fig)

    held = [c for c in table.columns if c.startswith("mean_held_") and c != "mean_held_cash"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, split in zip(axes, ("train", "validation"), strict=True):
        means = table[table["split"] == split].groupby("fixed_lambda")[held].mean()
        bottom = np.zeros(len(means))
        for i, column in enumerate(held):
            values = 100 * means[column].to_numpy()
            ax.bar(
                [f"λ={v:g}" for v in means.index],
                values,
                bottom=bottom,
                color=PALETTE[i % len(PALETTE)],
                label=column.removeprefix("mean_held_"),
            )
            bottom += values
        ax.set_title(f"{split}: mean held allocation (mean over seeds)")
    axes[0].set_ylabel("% of portfolio")
    axes[1].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e6_allocation_by_lambda.png",
            [path],
            "Mean held weights per lambda (7 ETFs and cash), mean over seeds",
        )
    )
    plt.close(fig)
    return written


def make_turnover_figures(comparison_dir: Path, out: Path) -> list:
    """E7: turnover, cost drag and validation performance against kappa, by seed (D-091)."""
    plt = _pyplot()
    path = comparison_dir / "seed_table.csv"
    table = pd.read_csv(path)
    panels = (
        ("train", "turnover", "turnover per year (training)", 1),
        ("validation", "turnover", "turnover per year (validation)", 1),
        ("validation", "cost_drag", "cost drag, pp (validation)", 100),
        ("validation", "net_sharpe", "net Sharpe (validation)", 1),
        ("validation", "net_volatility", "net volatility, % p.a. (validation)", 100),
        ("validation", "net_max_drawdown", "net max drawdown, % (validation)", 100),
    )
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.8))
    for ax, (split, metric, label, scale) in zip(axes.flat, panels, strict=True):
        part = table[table["split"] == split]
        kappas = sorted(part["turnover_penalty"].unique())
        positions = {k: i for i, k in enumerate(kappas)}
        for i, (seed, g) in enumerate(part.groupby("seed")):
            g = g.sort_values("turnover_penalty")
            ax.plot(
                [positions[k] for k in g["turnover_penalty"]],
                scale * g[metric],
                marker="o",
                color=PALETTE[i],
                alpha=0.85,
                label=f"seed {int(seed)}",
            )
        med = part.groupby("turnover_penalty")[metric].median()
        ax.plot([positions[k] for k in med.index], scale * med.to_numpy(), color="black",
                lw=2.2, ls="--", label="median")  # fmt: skip
        ax.set_xticks(range(len(kappas)), [f"κ={k:g}" for k in kappas])
        ax.set_title(label)
    axes[0, 2].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written = [
        _save(
            fig,
            out / "e7_metrics_vs_kappa.png",
            [path],
            "Seed trajectories and median of turnover, cost and performance vs kappa",
        )
    ]
    plt.close(fig)

    part = table[table["split"] == "validation"]
    arms = list(part.sort_values("turnover_penalty")["arm"].unique())
    seeds = sorted(part["seed"].unique())
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.4))
    for ax, (metric, label, scale) in zip(axes, (("net_sharpe", "validation net Sharpe", 1),
                                                 ("turnover", "validation turnover per year", 1)),
                                          strict=True):  # fmt: skip
        width = 0.8 / len(arms)
        for j, arm in enumerate(arms):
            values = part[part["arm"] == arm].set_index("seed").loc[seeds, metric]
            ax.bar(np.arange(len(seeds)) + (j - (len(arms) - 1) / 2) * width, scale * values,
                   width, label=arm, color=PALETTE[j])  # fmt: skip
        ax.set_xticks(range(len(seeds)), [str(int(s)) for s in seeds])
        ax.set_xlabel("seed")
        ax.set_title(label)
    axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e7_seed_comparison.png",
            [path],
            "Per-seed validation net Sharpe and turnover for each arm",
        )
    )
    plt.close(fig)
    return written


def _kappa_axis(ax, kappas: list, historical: float | None) -> dict:
    positions = {k: i for i, k in enumerate(kappas)}
    ticks = [f"κ={k:g}" for k in kappas]
    if historical is not None:
        positions[historical] = len(kappas) + 0.5
        ticks.append(f"κ={historical:g}\n(E7, prior)")
    ax.set_xticks(sorted(positions.values()), ticks, fontsize=7)
    return positions


def make_refine_figures(comparison_dir: Path, out: Path) -> list:
    """E8: metrics, responsiveness and per-seed results against kappa (D-092).

    E8 seeds and medians are drawn as lines; the prior-experiment E7T2 median (kappa 0.0075,
    ``historical.json``) is a separate hollow grey marker, never joined to the E8 lines.
    """
    plt = _pyplot()
    path = comparison_dir / "seed_table.csv"
    hist_path = comparison_dir / "historical.json"
    table = pd.read_csv(path)
    hist = json.loads(hist_path.read_text(encoding="utf-8"))
    sources = [path, hist_path]

    def panel(ax, split: str, metric: str, label: str, scale: float) -> None:
        part = table[table["split"] == split]
        kappas = sorted(part["turnover_penalty"].unique())
        prior = hist.get(split, {})
        value = prior.get("median", {}).get(metric)
        positions = _kappa_axis(ax, kappas, prior.get("turnover_penalty") if value is not None
                                else None)  # fmt: skip
        for i, (seed, g) in enumerate(part.groupby("seed")):
            g = g.sort_values("turnover_penalty")
            ax.plot([positions[k] for k in g["turnover_penalty"]], scale * g[metric], marker="o",
                    ms=3, color=PALETTE[i], alpha=0.8, label=f"seed {int(seed)}")  # fmt: skip
        med = part.groupby("turnover_penalty")[metric].median()
        ax.plot([positions[k] for k in med.index], scale * med.to_numpy(), color="black", lw=2.2,
                ls="--", label="E8 median")  # fmt: skip
        if value is not None:
            ax.plot([positions[prior["turnover_penalty"]]], [scale * value], marker="o", ms=8,
                    mfc="none", mec="grey", mew=1.8, ls="none",
                    label="E7T2 median (prior)")  # fmt: skip
        ax.set_title(label, fontsize=9)

    panels = (
        ("validation", "turnover", "turnover per year (validation)", 1),
        ("validation", "cost_drag", "cost drag, pp (validation)", 100),
        ("validation", "net_sharpe", "net Sharpe (validation)", 1),
        ("validation", "net_annualised_return", "ann. net return, % (validation)", 100),
        ("validation", "net_volatility", "net volatility, % p.a. (validation)", 100),
        ("validation", "net_max_drawdown", "net max drawdown, % (validation)", 100),
        ("validation", "target_cash", "mean target cash, % (validation)", 100),
        ("validation", "target_risky_hhi", "risky-sleeve HHI (validation)", 1),
        ("train", "turnover", "turnover per year (training)", 1),
        ("train", "cost_drag", "cost drag, pp (training)", 100),
        ("train", "net_sharpe", "net Sharpe (training)", 1),
        ("train", "net_annualised_return", "ann. net return, % (training)", 100),
    )
    fig, axes = plt.subplots(3, 4, figsize=(13, 8.4))
    for ax, spec in zip(axes.flat, panels, strict=True):
        panel(ax, *spec)
    axes[0, 3].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written = [_save(fig, out / "e8_metrics_vs_kappa.png", sources,
                     "Seed trajectories and E8 medians vs kappa; E7T2 as a prior-experiment "
                     "marker")]  # fmt: skip
    plt.close(fig)

    control = table[(table["split"] == "validation") & (table["turnover_penalty"] == 0)]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    for ax, (metric, label, ratio) in zip(axes, (
            ("allocation_stability_dw", "D_w, consecutive targets (validation)", 0.25),
            ("allocation_dispersion", "allocation dispersion (validation)", 0.50),
            ("share_meaningful_changes", "share of changes ≥ 5% (validation)", 0.50)),
            strict=True):  # fmt: skip
        panel(ax, "validation", metric, label, 1)
        ax.axhline(ratio * float(control[metric].median()), color="firebrick", lw=1, ls=":",
                   label=f"H6 threshold ({ratio:.0%} of E8B)")  # fmt: skip
    axes[2].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e8_responsiveness_vs_kappa.png",
            sources,
            "Responsiveness measures vs kappa with the prespecified H6 thresholds",
        )
    )
    plt.close(fig)

    part = table[table["split"] == "validation"]
    arms = list(part.sort_values("turnover_penalty")["arm"].unique())
    seeds = sorted(part["seed"].unique())
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.4))
    for ax, (metric, label, scale) in zip(axes, (
            ("net_sharpe", "validation net Sharpe", 1),
            ("turnover", "validation turnover per year", 1),
            ("cost_drag", "validation cost drag, pp", 100)), strict=True):  # fmt: skip
        width = 0.8 / len(arms)
        for j, arm in enumerate(arms):
            values = part[part["arm"] == arm].set_index("seed").loc[seeds, metric]
            ax.bar(np.arange(len(seeds)) + (j - (len(arms) - 1) / 2) * width, scale * values,
                   width, label=arm, color=PALETTE[j])  # fmt: skip
        ax.set_xticks(range(len(seeds)), [str(int(s)) for s in seeds])
        ax.set_xlabel("seed")
        ax.set_title(label, fontsize=9)
    axes[2].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e8_seed_comparison.png",
            [path],
            "Per-seed validation net Sharpe, turnover and cost drag for each E8 arm",
        )
    )
    plt.close(fig)
    return written


def make_confirmation_figures(comparison_dir: Path, out: Path) -> list:
    """E9: paired seed-level comparisons, decomposition and the primary difference (D-093).

    Only ``seed_table.csv`` and ``paired_differences.csv`` are read. Primary seeds (47-56) are
    blue; the reproduction seeds (42-46, equal to E8) are grey and never part of the medians.
    """
    plt = _pyplot()
    seed_path = comparison_dir / "seed_table.csv"
    diff_path = comparison_dir / "paired_differences.csv"
    table = pd.read_csv(seed_path)
    diffs = pd.read_csv(diff_path)
    sources = [seed_path, diff_path]
    val = table[table["split"] == "validation"]
    arms = list(val.sort_values("turnover_penalty")["arm"].unique())
    written = []

    panels = (
        ("net_sharpe", "net Sharpe", 1),
        ("net_annualised_return", "ann. net return, %", 100),
        ("turnover", "turnover per year", 1),
        ("cost_drag", "cost drag, pp", 100),
        ("target_cash", "mean target cash, %", 100),
        ("target_risky_hhi", "risky-sleeve HHI", 1),
    )
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.4))
    for ax, (metric, label, scale) in zip(axes.flat, panels, strict=True):
        wide = val.pivot(index="seed", columns="arm", values=metric)[arms]
        pops = val.drop_duplicates("seed").set_index("seed")["population"]
        for seed, row in wide.iterrows():
            primary = pops.loc[seed] == "primary"
            ax.plot([0, 1], scale * row.to_numpy(), marker="o", ms=3,
                    color=PALETTE[0] if primary else PALETTE[7], alpha=0.75 if primary else 0.6,
                    ls="-" if primary else "--", lw=1)  # fmt: skip
        med = wide.loc[pops[pops == "primary"].index].median()
        ax.plot([0, 1], scale * med.to_numpy(), color="black", lw=2.4, marker="s",
                label="median, seeds 47-56")  # fmt: skip
        ax.set_xticks([0, 1], arms)
        ax.set_xlim(-0.3, 1.3)
        ax.set_title(f"{label} (validation)", fontsize=9)
    axes[0, 2].plot([], [], color=PALETTE[0], label="seeds 47-56 (primary)")
    axes[0, 2].plot([], [], color=PALETTE[7], ls="--", label="seeds 42-46 (reproduction = E8)")
    axes[0, 2].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written.append(_save(fig, out / "e9_paired_seeds.png", sources,
                         "Paired seed-level validation metrics, E9B vs E9T1"))  # fmt: skip
    plt.close(fig)

    def row(metric: str, population: str) -> pd.Series:
        part = diffs[(diffs["split"] == "validation") & (diffs["metric"] == metric)
                     & (diffs["population"] == population)]  # fmt: skip
        return part.iloc[0]

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, (metric, label, scale) in zip(axes, (("net_sharpe", "Δ net Sharpe", 1),
                                                 ("net_annualised_return",
                                                  "Δ ann. net return, pp", 100)),
                                          strict=True):  # fmt: skip
        for x, population, colour in ((0, "primary", PALETTE[0]),
                                      (1, "reproduction", PALETTE[7])):  # fmt: skip
            r = row(metric, population)
            values = [r[c] for c in r.index if str(c).startswith("seed_") and pd.notna(r[c])]
            jitter = np.linspace(-0.12, 0.12, len(values))
            ax.scatter(x + jitter, scale * np.asarray(values), color=colour, s=18, zorder=3)
            boot = [
                [scale * (r["mean"] - r["bootstrap_low"])],
                [scale * (r["bootstrap_high"] - r["mean"])],
            ]
            ax.errorbar(x + 0.28, scale * r["mean"], yerr=boot, fmt="D", color="black", capsize=4,
                        label="mean, bootstrap 95% CI" if x == 0 else None)  # fmt: skip
            ax.errorbar(x + 0.4, scale * r["mean"], yerr=[[scale * (r["mean"] - r["t_low"])],
                        [scale * (r["t_high"] - r["mean"])]], fmt="o", mfc="none",
                        color="dimgray", capsize=3,
                        label="mean, t 95% CI (sensitivity)" if x == 0 else None)  # fmt: skip
        ax.axhline(0, color="firebrick", lw=1, ls=":")
        ax.set_xticks([0, 1], ["seeds 47-56\n(primary)", "seeds 42-46\n(historical, = E8)"])
        ax.set_title(f"{label}: E9T1 - E9B (validation)", fontsize=9)
    axes[1].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e9_primary_difference.png",
            sources,
            "Seed-level paired differences with bootstrap and t intervals",
        )
    )
    plt.close(fig)

    primary = [int(s) for s in val.loc[val["population"] == "primary", "seed"].unique()]
    seeds = sorted(primary)
    parts = {m: row(m, "primary") for m in ("gross_cumulative_return", "cost_drag",
                                            "net_cumulative_return")}  # fmt: skip
    series = {"Δ gross cumulative return": [parts["gross_cumulative_return"][f"seed_{s}"]
                                            for s in seeds],
              "cost saving (-Δ cost drag)": [-parts["cost_drag"][f"seed_{s}"] for s in seeds],
              "Δ net cumulative return": [parts["net_cumulative_return"][f"seed_{s}"]
                                          for s in seeds]}  # fmt: skip
    fig, ax = plt.subplots(figsize=(10, 3.6))
    width = 0.27
    for j, (label, values) in enumerate(series.items()):
        ax.bar(np.arange(len(seeds)) + (j - 1) * width, 100 * np.asarray(values), width,
               label=label, color=PALETTE[j])  # fmt: skip
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(len(seeds)), [str(s) for s in seeds])
    ax.set_xlabel("seed (primary population)")
    ax.set_ylabel("pp over the validation window")
    ax.set_title("E9T1 - E9B: gross return, cost saving and net return (validation)", fontsize=9)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e9_decomposition.png",
            sources,
            "Per-seed gross, cost and net decomposition of the paired difference",
        )
    )
    plt.close(fig)
    return written


def make_walk_forward_figures(comparison_dir: Path, out: Path) -> list:
    """E10: fold effects, paired seeds, costs and composition from saved outputs (D-094).

    Reads ``seed_table.csv``, ``paired_differences.csv`` and ``e9_reference.json`` only. The E9
    result (seeds 47-56, 2017-2019) is drawn as a separate grey reference, never pooled.
    """
    plt = _pyplot()
    seed_path = comparison_dir / "seed_table.csv"
    diff_path = comparison_dir / "paired_differences.csv"
    e9_path = comparison_dir / "e9_reference.json"
    table = pd.read_csv(seed_path)
    diffs = pd.read_csv(diff_path)
    e9 = json.loads(e9_path.read_text(encoding="utf-8"))
    sources = [seed_path, diff_path, e9_path]
    folds = sorted(table["fold"].unique())
    val = table[table["split"] == "validation"]
    written = []

    def row(fold: str, metric: str) -> pd.Series:
        part = diffs[(diffs["split"] == "validation") & (diffs["fold"] == fold)
                     & (diffs["metric"] == metric)]  # fmt: skip
        return part.iloc[0]

    def seeds_of(r: pd.Series) -> list[float]:
        return [r[c] for c in r.index if str(c).startswith("seed_") and pd.notna(r[c])]

    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for ax, (metric, label, scale) in zip(axes, (("net_sharpe", "Δ net Sharpe", 1),
                                                 ("net_annualised_return",
                                                  "Δ ann. net return, pp", 100)),
                                          strict=True):  # fmt: skip
        for x, fold in enumerate(folds):
            r = row(fold, metric)
            values = np.asarray(seeds_of(r))
            ax.scatter(x + np.linspace(-0.1, 0.1, len(values)), scale * values, s=18,
                       color=PALETTE[x], zorder=3)  # fmt: skip
            boot = [
                [scale * (r["mean"] - r["bootstrap_low"])],
                [scale * (r["bootstrap_high"] - r["mean"])],
            ]
            ax.errorbar(x + 0.25, scale * r["mean"], yerr=boot, fmt="D", color="black", capsize=4,
                        label="mean, bootstrap 95% CI" if x == 0 else None)  # fmt: skip
        ticks = [f"fold {f}" for f in folds]
        ref = (e9.get("metrics") or {}).get(metric) if e9.get("available") else None
        if ref:
            x = len(folds) + 0.4
            yerr = [
                [scale * (ref["mean"] - ref["bootstrap_low"])],
                [scale * (ref["bootstrap_high"] - ref["mean"])],
            ]
            ax.errorbar(x, scale * ref["mean"], yerr=yerr, fmt="o", mfc="none", color="grey",
                        capsize=4, label="E9 (seeds 47-56, 2017-19; historical)")  # fmt: skip
            ticks.append("E9\n(historical)")
            ax.set_xticks([*range(len(folds)), x], ticks)
        else:
            ax.set_xticks(range(len(folds)), ticks)
        ax.axhline(0, color="firebrick", lw=1, ls=":")
        ax.set_title(f"{label}: E10T1 - E10B (validation)", fontsize=9)
    axes[1].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e10_fold_effects.png",
            sources,
            "Seed-level paired differences by fold, with the E9 reference",
        )
    )
    plt.close(fig)

    fig, axes = plt.subplots(1, len(folds), figsize=(3.6 * len(folds), 3.4), sharey=True)
    for ax, fold in zip(np.atleast_1d(axes), folds, strict=True):
        part = val[val["fold"] == fold]
        wide = part.pivot(index="seed", columns="role", values="net_sharpe")[
            ["control", "treatment"]]  # fmt: skip
        for i, (_, r) in enumerate(wide.iterrows()):
            ax.plot([0, 1], r.to_numpy(), marker="o", ms=3, color=PALETTE[i % 8], lw=1)
        ax.plot([0, 1], wide.median().to_numpy(), color="black", lw=2.4, marker="s",
                label="median")  # fmt: skip
        ax.set_xticks([0, 1], ["E10B (κ 0)", "E10T1 (κ 0.0015)"])
        ax.set_xlim(-0.3, 1.3)
        ax.set_title(f"fold {fold}: validation net Sharpe", fontsize=9)
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e10_paired_seeds.png",
            [seed_path],
            "Paired seed-level validation net Sharpe within each fold",
        )
    )
    plt.close(fig)

    panels = (("turnover", "Δ turnover / yr", 1), ("cost_drag", "Δ cost drag, pp", 100),
              ("gross_cumulative_return", "Δ gross cumulative return, pp", 100),
              ("net_cumulative_return", "Δ net cumulative return, pp", 100))  # fmt: skip
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.4))
    for ax, (metric, label, scale) in zip(axes, panels, strict=True):
        for x, fold in enumerate(folds):
            r = row(fold, metric)
            values = np.asarray(seeds_of(r))
            ax.bar(x, scale * r["mean"], 0.6, color=PALETTE[x], alpha=0.5)
            ax.scatter(x + np.linspace(-0.1, 0.1, len(values)), scale * values, s=14,
                       color="black", zorder=3)  # fmt: skip
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(range(len(folds)), [f"fold {f}" for f in folds])
        ax.set_title(f"{label} (validation)", fontsize=9)
    fig.tight_layout()
    written.append(_save(fig, out / "e10_costs_decomposition.png", sources,
                         "Turnover, cost drag, gross and net return changes by fold (mean bars, "
                         "seed dots)"))  # fmt: skip
    plt.close(fig)

    panels = (("target_cash", "mean target cash, %", 100, 40),
              ("target_risky_hhi", "risky-sleeve HHI", 1, 2 / 3),
              ("allocation_dispersion", "allocation dispersion", 1, None),
              ("share_meaningful_changes", "share of changes ≥ 5%", 1, None))  # fmt: skip
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.4))
    for ax, (metric, label, scale, limit) in zip(axes, panels, strict=True):
        for x, fold in enumerate(folds):
            for j, role in enumerate(("control", "treatment")):
                values = val[(val["fold"] == fold) & (val["role"] == role)][metric].to_numpy()
                pos = x + (j - 0.5) * 0.35
                name = ("E10B (κ 0)", "E10T1 (κ 0.0015)")[j] if x == 0 else None
                ax.scatter(np.full(len(values), pos), scale * values, s=14, color=PALETTE[j],
                           label=name)  # fmt: skip
                ax.plot([pos - 0.12, pos + 0.12], [scale * np.median(values)] * 2, color="black")
        if limit is not None:
            ax.axhline(limit, color="firebrick", lw=1, ls=":", label="E8 limit (H7)")
        ax.set_xticks(range(len(folds)), [f"fold {f}" for f in folds])
        ax.set_title(f"{label} (validation)", fontsize=9)
    axes[-1].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e10_composition.png",
            [seed_path],
            "Cash, concentration and responsiveness by fold and arm",
        )
    )
    plt.close(fig)
    return written


def make_budget_figures(comparison_dir: Path, out: Path) -> list:
    """E11: budget effects, training vs validation, costs, composition and baselines (D-095).

    Reads ``seed_table.csv``, ``paired_differences.csv`` and ``baselines.json`` only. Arms:
    E11R (the D-066 budget, 100,352 timesteps; = E10T1) and E11H (50,176). Folds stay separate.
    """
    plt = _pyplot()
    seed_path = comparison_dir / "seed_table.csv"
    diff_path = comparison_dir / "paired_differences.csv"
    base_path = comparison_dir / "baselines.json"
    table = pd.read_csv(seed_path)
    diffs = pd.read_csv(diff_path)
    baselines = json.loads(base_path.read_text(encoding="utf-8"))
    folds = sorted(table["fold"].unique())
    names = {"control": "E11R (100,352)", "treatment": "E11H (50,176)"}
    written = []

    def row(fold: str, metric: str, split: str = "validation") -> pd.Series:
        part = diffs[(diffs["split"] == split) & (diffs["fold"] == fold)
                     & (diffs["metric"] == metric)]  # fmt: skip
        return part.iloc[0]

    def seeds_of(r: pd.Series) -> np.ndarray:
        return np.asarray([r[c] for c in r.index if str(c).startswith("seed_") and pd.notna(r[c])])

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for ax, (metric, label, scale) in zip(axes, (("net_sharpe", "Δ net Sharpe", 1),
                                                 ("net_annualised_return",
                                                  "Δ ann. net return, pp", 100)),
                                          strict=True):  # fmt: skip
        for x, fold in enumerate(folds):
            r = row(fold, metric)
            values = seeds_of(r)
            ax.scatter(x + np.linspace(-0.1, 0.1, len(values)), scale * values, s=18,
                       color=PALETTE[x], zorder=3)  # fmt: skip
            boot = [
                [scale * (r["mean"] - r["bootstrap_low"])],
                [scale * (r["bootstrap_high"] - r["mean"])],
            ]
            ax.errorbar(x + 0.25, scale * r["mean"], yerr=boot, fmt="D", color="black", capsize=4,
                        label="mean, bootstrap 95% CI" if x == 0 else None)  # fmt: skip
        ax.axhline(0, color="firebrick", lw=1, ls=":")
        ax.set_xticks(range(len(folds)), [f"fold {f}" for f in folds])
        ax.set_title(f"{label}: E11H - E11R (validation)", fontsize=9)
    axes[1].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written.append(_save(fig, out / "e11_fold_effects.png", [seed_path, diff_path],
                         "Seed-level paired budget effects (E11H - E11R) by fold"))  # fmt: skip
    plt.close(fig)

    fig, axes = plt.subplots(1, len(folds), figsize=(3.8 * len(folds), 3.6), sharey=False)
    for ax, fold in zip(np.atleast_1d(axes), folds, strict=True):
        for k, split in enumerate(("train", "validation")):
            part = table[(table["fold"] == fold) & (table["split"] == split)]
            wide = part.pivot(index="seed", columns="role", values="net_sharpe")[
                ["control", "treatment"]]  # fmt: skip
            x0 = 2.5 * k
            for i, (_, r) in enumerate(wide.iterrows()):
                ax.plot([x0, x0 + 1], r.to_numpy(), marker="o", ms=3, color=PALETTE[i % 8], lw=1)
            ax.plot([x0, x0 + 1], wide.median().to_numpy(), color="black", lw=2.2, marker="s")
        ax.set_xticks([0, 1, 2.5, 3.5], ["train\nE11R", "train\nE11H", "valid.\nE11R",
                                          "valid.\nE11H"], fontsize=7)  # fmt: skip
        ax.axhline(0, color="grey", lw=0.6)
        ax.set_title(f"fold {fold}: net Sharpe, training vs validation", fontsize=9)
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e11_train_vs_validation.png",
            [seed_path],
            "In-sample and validation net Sharpe by budget (paired seeds)",
        )
    )
    plt.close(fig)

    panels = (("cost_drag", "Δ cost drag, pp", 100), ("turnover", "Δ turnover / yr", 1),
              ("gross_cumulative_return", "Δ gross cumulative return, pp", 100),
              ("net_volatility", "Δ net volatility, pp", 100))  # fmt: skip
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.4))
    for ax, (metric, label, scale) in zip(axes, panels, strict=True):
        for x, fold in enumerate(folds):
            r = row(fold, metric)
            values = seeds_of(r)
            ax.bar(x, scale * r["mean"], 0.6, color=PALETTE[x], alpha=0.5)
            ax.scatter(x + np.linspace(-0.1, 0.1, len(values)), scale * values, s=14,
                       color="black", zorder=3)  # fmt: skip
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(range(len(folds)), [f"fold {f}" for f in folds])
        ax.set_title(f"{label} (validation)", fontsize=9)
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e11_costs_turnover.png",
            [diff_path],
            "Cost drag, turnover, gross return and volatility changes by fold",
        )
    )
    plt.close(fig)

    panels = (("target_cash", "mean target cash, %", 100, 40),
              ("target_risky_hhi", "risky-sleeve HHI", 1, 2 / 3),
              ("allocation_dispersion", "allocation dispersion", 1, None),
              ("share_meaningful_changes", "share of changes ≥ 5%", 1, None))  # fmt: skip
    val = table[table["split"] == "validation"]
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.4))
    for ax, (metric, label, scale, limit) in zip(axes, panels, strict=True):
        for x, fold in enumerate(folds):
            for j, role in enumerate(("control", "treatment")):
                values = val[(val["fold"] == fold) & (val["role"] == role)][metric].to_numpy()
                pos = x + (j - 0.5) * 0.35
                name = names[role] if x == 0 else None
                ax.scatter(np.full(len(values), pos), scale * values, s=14, color=PALETTE[j],
                           label=name)  # fmt: skip
                ax.plot([pos - 0.12, pos + 0.12], [scale * np.median(values)] * 2, color="black")
        if limit is not None:
            ax.axhline(limit, color="firebrick", lw=1, ls=":", label="E8 limit")
        ax.set_xticks(range(len(folds)), [f"fold {f}" for f in folds])
        ax.set_title(f"{label} (validation)", fontsize=9)
    axes[-1].legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e11_composition.png",
            [seed_path],
            "Cash, concentration and responsiveness by fold and budget",
        )
    )
    plt.close(fig)

    fig, axes = plt.subplots(1, len(folds), figsize=(3.8 * len(folds), 3.4))
    for ax, fold in zip(np.atleast_1d(axes), folds, strict=True):
        for j, role in enumerate(("control", "treatment")):
            values = val[(val["fold"] == fold) & (val["role"] == role)]["net_sharpe"].to_numpy()
            ax.scatter(np.full(len(values), j), values, s=16, color=PALETTE[j])
            ax.plot([j - 0.15, j + 0.15], [np.median(values)] * 2, color="black", lw=2)
        for k, (strategy, stats) in enumerate(sorted(baselines[fold]["strategies"].items())):
            ax.axhline(stats["net_sharpe"], color=PALETTE[4 + k], lw=1, ls="--",
                       label=strategy)  # fmt: skip
        ax.set_xticks([0, 1], [names["control"], names["treatment"]], fontsize=7)
        ax.set_xlim(-0.5, 1.5)
        ax.set_title(f"fold {fold}: validation net Sharpe vs baselines", fontsize=9)
    np.atleast_1d(axes)[-1].legend(frameon=False, fontsize=7, loc="upper left",
                                   bbox_to_anchor=(1.0, 1.0))  # fmt: skip
    fig.tight_layout()
    written.append(
        _save(
            fig,
            out / "e11_baselines.png",
            [seed_path, base_path],
            "PPO arms against each fold's own simple baselines",
        )
    )
    plt.close(fig)
    return written
