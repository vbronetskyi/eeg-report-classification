#!/usr/bin/env python3
"""Grouped bar chart of Core F1 by category: our Q2_K vs paper Mistral-7B vs human.

Our numbers are read from the run JSON; paper columns (Mistral-7B, Second
Annotator) are Table III (Zoe). Saves a PNG under figures/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

FIELDS = [
    ("abnormality", "Abnormality"),
    ("focal_epileptiform_activity", "Focal Epi"),
    ("generalized_epileptiform_activity", "Gen Epi"),
    ("focal_non_epileptiform_activity", "Focal Non-epi"),
    ("generalized_non_epileptiform_activity", "Gen Non-epi"),
]
PAPER_MISTRAL = [0.96, 0.85, 0.71, 0.76, 0.78]
PAPER_HUMAN_SA = [0.98, 0.85, 0.90, 0.90, 0.90]


def core_f1(cases, field):
    tp = fp = fn = 0
    for c in cases:
        p = c["model"][field]["pred"] >= 3
        t = c["ld_labels"][field] >= 3
        tp += p and t
        fp += p and not t
        fn += (not p) and t
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return 2 * prec * rec / (prec + rec) if prec + rec else 0.0


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else \
        "results/q2_cpu_full_n1495.json"
    cases = json.loads(Path(src).read_text())["cases"]
    ours = [round(core_f1(cases, k), 2) for k, _ in FIELDS]
    labels = [lab for _, lab in FIELDS]
    n = len(cases)

    # palette (dataviz slots 1/2/3, light mode)
    C_OURS, C_MISTRAL, C_HUMAN = "#2a78d6", "#eb6834", "#1baf7a"
    INK, INK2, GRID = "#141821", "#566072", "#e9edf3"

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.edgecolor": "#c8cfd9", "axes.linewidth": 1.0,
        "figure.dpi": 150,
    })
    fig, ax = plt.subplots(figsize=(9.4, 5.0))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    import numpy as np
    x = np.arange(len(labels))
    w = 0.26
    series = [
        ("Our model · Q2_K", ours, C_OURS),
        ("Mistral-7B · paper", PAPER_MISTRAL, C_MISTRAL),
        ("Human expert", PAPER_HUMAN_SA, C_HUMAN),
    ]
    for i, (name, vals, col) in enumerate(series):
        xs = x + (i - 1) * w
        bars = ax.bar(xs, vals, w * 0.92, label=name, color=col,
                      zorder=3, edgecolor="white", linewidth=0.6)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.2f}",
                    ha="center", va="bottom", fontsize=8.5, color=INK,
                    fontfamily="monospace", fontweight="bold", zorder=4)

    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_locator(MultipleLocator(0.2))
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11, color=INK2)
    ax.tick_params(axis="y", colors=INK2, labelsize=9)
    ax.tick_params(length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c8cfd9")

    ax.set_ylabel("Core F1  (higher = better)", fontsize=10.5, color=INK2)
    ax.set_title(f"EEG report classification accuracy by category   ·   n={n}",
                 fontsize=13.5, color=INK, fontweight="bold", pad=14, loc="left")
    ax.legend(frameon=False, fontsize=10, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.09), handlelength=1.1)

    fig.tight_layout()
    out = Path("reports/figures/eeg_core_f1.png")
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print(f"saved {out}  (ours F1: {dict(zip(labels, ours))})")


if __name__ == "__main__":
    main()
