#!/usr/bin/env python3
"""One distribution chart per background field, for the three per-field reports.

For each field (discontinuous_background, burst_suppression, suppressed_background) draw a stacked
horizontal bar per dataset (FHA, MGH, BWH, BCH) showing the three-way split
present / explicitly_absent / not_mentioned. Reads results/background/dist_summary.json.

Run: python -m analysis.background_field_charts
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import INK, INK2, ORANGE, GRID, apply_style, bare

DIST = json.load(open("results/background/dist_summary.json"))
DATASETS = ["FHA", "MGH", "BWH", "BCH"]
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)

# field key in dist_summary -> (nice title, output filename)
FIELDS = {
    "discontinuous":     ("Discontinuous background", "dist_discontinuous.png"),
    "burst_suppression": ("Burst-suppression",        "dist_burst_suppression.png"),
    "suppressed":        ("Suppressed background",     "dist_suppressed.png"),
}
STATUS = [("present", ORANGE), ("explicitly_absent", INK2), ("not_mentioned", GRID)]
LABEL = {"present": "present", "explicitly_absent": "explicitly absent",
         "not_mentioned": "not mentioned"}


def node(ds, field):
    return DIST["FHA"][field] if ds == "FHA" else DIST["Harvard"][ds][field]


def draw(field, title, fname):
    apply_style()
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    ys = list(range(len(DATASETS)))[::-1]  # FHA on top
    for y, ds in zip(ys, DATASETS):
        left = 0.0
        for status, color in STATUS:
            v = node(ds, field)[status][1]
            ax.barh(y, v, left=left, color=color, height=0.62,
                    edgecolor="white", linewidth=0.8)
            if v >= 6:  # only label segments wide enough to hold text
                tc = "white" if color in (ORANGE, INK2) else INK2
                ax.text(left + v / 2, y, f"{v:.1f}", ha="center", va="center",
                        fontsize=8.5, color=tc)
            left += v
    ax.set_yticks(ys); ax.set_yticklabels(DATASETS, fontsize=11)
    ax.set_xlim(0, 100); ax.set_xlabel("share of reports (%)", fontsize=9, color=INK2)
    ax.set_title(f"{title}: how each report was classified", color=INK,
                 fontsize=12.5, fontweight="bold", loc="left", pad=26)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c in STATUS]
    ax.legend(handles, [LABEL[s] for s, _ in STATUS], frameon=False, fontsize=9,
              ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    bare(ax, keep_left=False)
    fig.tight_layout()
    fig.savefig(OUT / fname, bbox_inches="tight", facecolor="white")
    print("saved", fname)


def main():
    for field, (title, fname) in FIELDS.items():
        draw(field, title, fname)


if __name__ == "__main__":
    main()
