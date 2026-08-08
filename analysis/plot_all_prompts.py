#!/usr/bin/env python3
"""Charts for reports/all_prompts.md — the all-prompts results report.

Two figures, pooled over Zoe+Maria (n=1994), Core F1 vs LD:
  all_prompts_whole.png   — whole-report accuracy for every config (the climb)
  all_prompts_bycat.png   — per-category F1: our best (v5g) vs Mistral vs human

Everything is computed from results/*.json + stored sg_labels; Mistral's per-category
values are the paper's Table III (reproduced by analysis.pooled). Reproducible:
    python -m analysis.plot_all_prompts
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import (KEYS, LABELS, load, INK, INK2, GRID,
                               BLUE, ORANGE, GREEN)

GREY = "#8b94a4"

OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
pres = lambda v: v >= 3
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "figure.dpi": 150})

# Mistral-7B, paper Table III (reproduced by analysis.pooled), pooled n=1994
MISTRAL_F1 = [94.7, 82.8, 74.8, 75.6, 75.2]
MISTRAL_WHOLE = 74.5


def pooled(variant, quant):
    return load("zoe", variant, quant) + load("maria", variant, quant)


def whole(cases, truth="ld_labels"):
    ok = sum(1 for c in cases
             if all(pres(c["model"][k]["pred"]) == pres(c[truth][k]) for k in KEYS))
    return 100 * ok / len(cases)


def catf1(cases, k, pred, truth):
    tp = fp = fn = 0
    for c in cases:
        m, g = pres(pred(c, k)), pres(truth(c, k))
        tp += m and g; fp += m and not g; fn += (not m) and g
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 100 * (2 * p * r / (p + r) if p + r else 0.0)


MODEL = lambda c, k: c["model"][k]["pred"]
LD = lambda c, k: c["ld_labels"][k]
SG = lambda c, k: c["sg_labels"][k]


def _bare(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)


def chart_whole():
    # Cleveland dot plot — position (not bar length) encodes the value, so the
    # non-zero axis is honest. Grammar variants use Q4; v5g is the best.
    rows = [
        ("Mistral-7B",        MISTRAL_WHOLE,              GREY),
        ("v1 (baseline)",     whole(pooled("v1", "Q2")),  BLUE),
        ("v3",                whole(pooled("v3", "Q2")),  BLUE),
        ("v8g (simplified)",  whole(pooled("v8g", "Q4")), BLUE),
        ("v10g (calibrated)", whole(pooled("v10g", "Q4")),BLUE),
        ("v3g",               whole(pooled("v3g", "Q4")), BLUE),
        ("v7g",               whole(pooled("v7g", "Q4")), BLUE),
        ("v5g  (best)",       whole(pooled("v5g", "Q4")), ORANGE),
        ("Human (SG vs LD)",  89.8,                       GREEN),
    ]
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(8.8, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x0 = 72
    for yi, (name, val, col) in enumerate(rows):
        ax.plot([x0, val], [yi, yi], color=GRID, lw=1.5, zorder=1,
                solid_capstyle="round")           # faint stem
        ax.scatter([val], [yi], s=150, color=col, zorder=3)
        ax.text(val + 0.45, yi, f"{val:.1f}%", va="center", ha="left",
                color=col, fontsize=9.5, fontweight="bold", zorder=4)
    ax.axvline(89.8, color=GREEN, lw=1.1, ls=":", zorder=1)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], color=INK2)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(x0, 92)
    ax.set_xlabel("Whole-report accuracy (all 5 labels correct), %", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9)
    _bare(ax)
    ax.set_title("MedGemma-27B — whole-report accuracy by prompt  ·  pooled n=1994",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.035, "each dot = one configuration · dotted line = human annotator agreement (89.8%)",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "all_prompts_whole.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved all_prompts_whole.png")


def chart_bycat():
    v5 = pooled("v5g", "Q2")
    series = [
        ("Mistral-7B", MISTRAL_F1, GREY),
        ("MedGemma v5g", [catf1(v5, k, MODEL, LD) for k in KEYS], BLUE),
        ("Human (SG)", [catf1(v5, k, SG, LD) for k in KEYS], GREEN),
    ]
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    import numpy as np
    x = np.arange(len(KEYS)); off = 0.2
    from matplotlib.lines import Line2D
    for xi in x:                                   # faint per-category guide
        ax.plot([xi, xi], [70, 100], color=GRID, lw=1, zorder=0)
    for i, (name, vals, col) in enumerate(series):
        xs = x + (i - 1) * off
        ax.scatter(xs, vals, s=130, color=col, zorder=3)
        for xv, v in zip(xs, vals):
            ax.text(xv, v + 0.9, f"{v:.0f}", ha="center", va="bottom",
                    fontsize=8, color=col, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(LABELS, fontsize=9.5, color=INK2)
    ax.set_xlim(-0.5, len(KEYS) - 0.5)
    ax.set_ylim(72, 101); ax.set_ylabel("Core F1, %", color=INK2, fontsize=10)
    ax.grid(axis="y", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="y", colors=INK2, labelsize=9)
    _bare(ax); ax.spines["left"].set_visible(False)
    handles = [Line2D([0], [0], marker="o", linestyle="", markersize=9, color=c, label=l)
               for l, _, c in series]
    ax.legend(handles=handles, frameon=False, fontsize=9.5, loc="lower center",
              bbox_to_anchor=(0.5, -0.18), ncol=3, handletextpad=0.3)
    ax.set_title("Per-category F1 — MedGemma v5g vs Mistral-7B vs human  ·  n=1994",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=14)
    fig.tight_layout(); fig.savefig(OUT / "all_prompts_bycat.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved all_prompts_bycat.png")


if __name__ == "__main__":
    chart_whole()
    chart_bycat()
