"""Figures for the first-analysis writeup.

Palette: SchoolFactors uses the validated reference dataviz palette (light mode)
— series blue #2a78d6, orange #eb6834; ink #0b0b0b/#52514e; recessive grid #e1e0d9.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from schoolfactors.paths import REPO_ROOT

FIG_DIR = REPO_ROOT / "analysis" / "figures"

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": "#c3c2b7",
        "axes.labelcolor": INK2,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": INK,
        "font.family": "sans-serif",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlecolor": INK,
    }
)


def fig_adjustment_scatter(effects: pl.DataFrame) -> Path:
    """Before/after adjustment vs economic disadvantage — the key teaching figure."""
    d = effects.filter(
        pl.col("level").is_not_null()
        & pl.col("level_adj").is_not_null()
        & pl.col("share_econ_dis").is_not_null()
    )
    x = d["share_econ_dis"].to_numpy() * 100
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    for ax, col, title in (
        (axes[0], "level", "Raw average score"),
        (axes[1], "level_adj", "After demographic adjustment"),
    ):
        y = d[col].to_numpy()
        r = np.corrcoef(x, y)[0, 1]
        ax.scatter(x, y, s=4, alpha=0.18, color=BLUE, edgecolors="none", rasterized=True)
        ax.axhline(0, color="#c3c2b7", lw=1)
        ax.set_title(f"{title}   (r = {r:+.2f})", fontsize=11)
        ax.set_xlabel("% of tested students economically disadvantaged")
        ax.set_ylim(-2.2, 2.2)
    axes[0].set_ylabel("School level vs state average\n(student-level SDs)")
    fig.suptitle(
        "What demographic adjustment removes — each dot is a California school",
        fontsize=12,
        y=1.02,
    )
    fig.tight_layout()
    out = FIG_DIR / "adjustment_scatter.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def fig_funnel(effects: pl.DataFrame) -> Path:
    """Funnel plot: adjusted level vs school size, with sampling control limits."""
    d = effects.filter(
        pl.col("level_adj").is_not_null()
        & pl.col("level_var").is_not_null()
        & (pl.col("level_var") > 0)
        & pl.col("total_scores").is_not_null()
    )
    n = d["total_scores"].to_numpy().astype(float)
    y = d["level_adj"].to_numpy()
    c = float(np.median(d["level_var"].to_numpy() * n))  # level_var ≈ c / n
    ngrid = np.geomspace(n.min(), n.max(), 200)
    lim = 1.96 * np.sqrt(c / ngrid)

    sig = np.abs(y) > 1.96 * np.sqrt(c / n)
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.scatter(
        n[~sig], y[~sig], s=4, alpha=0.18, color=MUTED, edgecolors="none", rasterized=True,
        label="not distinguishable from expectation",
    )
    ax.scatter(
        n[sig], y[sig], s=5, alpha=0.35, color=BLUE, edgecolors="none", rasterized=True,
        label="outside 95% sampling band",
    )
    ax.plot(ngrid, lim, color=ORANGE, lw=1.5)
    ax.plot(ngrid, -lim, color=ORANGE, lw=1.5)
    ax.axhline(0, color="#c3c2b7", lw=1)
    ax.set_xscale("log")
    ax.set_xlabel("Total tested scores across years (log scale)")
    ax.set_ylabel("Adjusted level\n(student-level SDs)")
    ax.set_title("Small schools are noisy by construction — funnel plot of adjusted level")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    fig.tight_layout()
    out = FIG_DIR / "funnel.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def fig_quadrant(effects: pl.DataFrame) -> Path:
    """Adjusted level × adjusted growth, EB-shrunken, with indistinguishable band."""
    d = effects.filter(
        pl.col("level_adj_eb").is_not_null()
        & pl.col("growth_adj_eb").is_not_null()
        & (pl.col("growth_reliability") >= 0.7)
    )
    x = d["level_adj_eb"].to_numpy()
    y = d["growth_adj_eb"].to_numpy()
    fig, ax = plt.subplots(figsize=(7.6, 6))
    ax.axvspan(-0.1, 0.1, color=GRID, alpha=0.5, zorder=0)
    ax.axhspan(-0.02, 0.02, color=GRID, alpha=0.5, zorder=0)
    ax.scatter(x, y, s=5, alpha=0.25, color=BLUE, edgecolors="none", rasterized=True)
    ax.axhline(0, color="#c3c2b7", lw=1)
    ax.axvline(0, color="#c3c2b7", lw=1)
    ax.set_xlabel("Adjusted level (student SDs vs similar schools)")
    ax.set_ylabel("Adjusted growth (student SDs per grade)")
    ax.set_title(
        "Level and growth are different questions\n"
        "(EB-shrunken, reliability ≥ 0.70; gray band ≈ not meaningfully different)"
    )
    fig.tight_layout()
    out = FIG_DIR / "quadrant.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def make_all(effects: pl.DataFrame) -> list[Path]:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    return [fig_adjustment_scatter(effects), fig_funnel(effects), fig_quadrant(effects)]
