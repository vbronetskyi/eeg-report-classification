#!/usr/bin/env python3
"""Fraser Health slowing chart: the three-way split of each field, as a 100% stacked bar.
Reads results/slowing/fha_summary.json.  Run: python -m analysis.slowing_fha_chart
Output: reports/figures/slowing_fha.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import INK, INK2, BLUE, ORANGE, apply_style, bare

S = json.load(open("results/slowing/fha_summary.json"))
GREY = "#c9d1dc"
COLORS = {"present": BLUE, "explicitly_absent": ORANGE, "not_mentioned": GREY}
LABEL = {"present": "present", "explicitly_absent": "explicitly absent",
         "not_mentioned": "not mentioned"}
FIELDS = [("focal", "focal slowing"), ("generalized", "generalized slowing")]
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)


def main():
    apply_style()
    fig, ax = plt.subplots(figsize=(9, 2.9))
    y = [1, 0]
    for (key, _), yy in zip(FIELDS, y):
        left = 0
        for st in ["present", "explicitly_absent", "not_mentioned"]:
            pct = S[f"dist_{key}"][st][1]
            ax.barh(yy, pct, left=left, height=0.55, color=COLORS[st],
                    edgecolor="white", linewidth=1.5)
            if pct >= 6:
                ax.text(left + pct / 2, yy, f"{pct:.0f}%", ha="center", va="center",
                        color="white" if st != "not_mentioned" else INK2,
                        fontsize=10, fontweight="bold")
            left += pct
    ax.set_yticks(y); ax.set_yticklabels([f for _, f in FIELDS], fontsize=11, color=INK)
    ax.set_xlim(0, 100); ax.set_xticks([])
    ax.set_title("Fraser Health — what the model called (45,545 reports)",
                 color=INK, fontsize=12.5, fontweight="bold", loc="left", pad=24)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[s]) for s in COLORS]
    ax.legend(handles, [LABEL[s] for s in COLORS], frameon=False, fontsize=9,
              ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    bare(ax, keep_left=False)
    ax.spines["bottom"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "slowing_fha.png", bbox_inches="tight", facecolor="white")
    print("saved reports/figures/slowing_fha.png")


if __name__ == "__main__":
    main()
