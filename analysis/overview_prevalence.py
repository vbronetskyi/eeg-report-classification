#!/usr/bin/env python3
"""Overview chart for the consolidated work report: present-rate of every labeled field on the
Fraser Health set (45,545 reports), grouped by block. Reads only our own label outputs — no
Harvard comparison. Run: python -m analysis.overview_prevalence
"""
from __future__ import annotations

import glob
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import INK, INK2, BLUE, ORANGE, AQUA, VIOLET, apply_style, bare

OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
AB = ["abnormality", "focal_epileptiform_activity", "generalized_epileptiform_activity",
      "focal_non_epileptiform_activity", "generalized_non_epileptiform_activity"]


def abnormality_fha():
    tot = 0; pres = Counter()
    for f in glob.glob("results/labels/q4_k_s/**/*.json", recursive=True):
        for c in json.load(open(f)).get("cases", []):
            m = c.get("model")
            if not m:
                continue
            tot += 1
            for k in AB:
                if m.get(k, {}).get("pred", 0) >= 3:
                    pres[k] += 1
    return {k: 100 * pres[k] / tot for k in AB}


def triphasic_fha():
    cs = json.load(open("results/triphasic/clean/short.json"))["cases"]
    p = sum(1 for c in cs if c.get("triphasic", {}).get("status") == "present")
    return 100 * p / len(cs)


def collect():
    ab = abnormality_fha()
    slow = json.load(open("results/slowing/fha_summary.json"))
    bg = json.load(open("results/background/dist_summary.json"))["FHA"]
    # (label, present%, block-color)
    return [
        ("abnormal", ab["abnormality"], BLUE),
        ("focal epileptiform", ab["focal_epileptiform_activity"], BLUE),
        ("generalized epileptiform", ab["generalized_epileptiform_activity"], BLUE),
        ("focal non-epileptiform", ab["focal_non_epileptiform_activity"], BLUE),
        ("generalized non-epileptiform", ab["generalized_non_epileptiform_activity"], BLUE),
        ("triphasic waves", triphasic_fha(), VIOLET),
        ("focal slowing", slow["dist_focal"]["present"][1], ORANGE),
        ("generalized slowing", slow["dist_generalized"]["present"][1], ORANGE),
        ("discontinuous background", bg["discontinuous"]["present"][1], AQUA),
        ("burst-suppression", bg["burst_suppression"]["present"][1], AQUA),
        ("suppressed background", bg["suppressed"]["present"][1], AQUA),
    ]


def main():
    rows = collect()
    apply_style()
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    ys = list(range(len(rows)))[::-1]
    for y, (lab, val, col) in zip(ys, rows):
        ax.barh(y, val, color=col, height=0.66)
        ax.text(val + 0.5, y, f"{val:.1f}%", va="center", ha="left", fontsize=8.5, color=INK2)
    ax.set_yticks(ys); ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    ax.set_xlim(0, 52)
    ax.set_title("Present rate of every labeled finding — Fraser Health (45,545 reports)",
                 color=INK, fontsize=12.5, fontweight="bold", loc="left", pad=28)
    ax.text(0, 1.015, "share of reports the model called present (%)", transform=ax.transAxes,
            fontsize=8.5, color=INK2, va="bottom")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (BLUE, VIOLET, ORANGE, AQUA)]
    ax.legend(handles, ["abnormality", "triphasic", "slowing", "background"],
              frameon=False, fontsize=9, ncol=4, loc="lower right", bbox_to_anchor=(1, 1.0))
    bare(ax, keep_left=False)
    fig.tight_layout()
    fig.savefig(OUT / "overview_fha_prevalence.png", bbox_inches="tight", facecolor="white")
    print("saved overview_fha_prevalence.png")


if __name__ == "__main__":
    main()
