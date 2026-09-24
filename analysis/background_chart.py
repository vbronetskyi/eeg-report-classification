#!/usr/bin/env python3
"""Charts for the background-patterns report:
 1. present-rate of each background field across FHA and the Harvard cohorts (prevalence)
 2. burst_suppression — our labels vs Harvard's `bs` (the only field with a Harvard column)
Reads results/background/dist_summary.json and results/harvard/burst_vs_harvard.json.
Run: python -m analysis.background_chart
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import INK, INK2, BLUE, ORANGE, AQUA, VIOLET, apply_style, bare

DIST = json.load(open("results/background/dist_summary.json"))
BURST = json.load(open("results/harvard/burst_vs_harvard.json"))["burst_suppression"]
FIELDS = [("discontinuous", "discontinuous"), ("burst_suppression", "burst-suppression"),
          ("suppressed", "suppressed")]
DATASETS = ["FHA", "MGH", "BWH", "BCH"]
DCOL = {"FHA": VIOLET, "MGH": BLUE, "BWH": ORANGE, "BCH": AQUA}
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)


def present_pct(dataset, field):
    node = DIST["FHA"][field] if dataset == "FHA" else DIST["Harvard"][dataset][field]
    return node["present"][1]


def fig_prevalence():
    apply_style()
    fig, ax = plt.subplots(figsize=(8.6, 4.3))
    x = range(len(FIELDS)); w = 0.2
    for j, ds in enumerate(DATASETS):
        vals = [present_pct(ds, k) for k, _ in FIELDS]
        xs = [i + (j - 1.5) * w for i in x]
        bars = ax.bar(xs, vals, w, color=DCOL[ds], label=ds)
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.12,
                    f"{r.get_height():.1f}", ha="center", va="bottom", fontsize=7.5, color=INK2)
    ax.set_xticks(list(x)); ax.set_xticklabels([lab for _, lab in FIELDS], fontsize=11)
    ax.set_title("How often each background pattern is called present",
                 color=INK, fontsize=12.5, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.02, "share of reports called present (%)", transform=ax.transAxes,
            fontsize=8.5, color=INK2, va="bottom")
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="upper right")
    ax.set_ylabel(""); bare(ax)
    fig.tight_layout()
    fig.savefig(OUT / "background_prevalence.png", bbox_inches="tight", facecolor="white")
    print("saved background_prevalence.png")


def fig_burst():
    apply_style()
    coh = ["MGH", "BWH", "BCH"]
    fig, ax = plt.subplots(figsize=(6.6, 4.3))
    x = range(len(coh)); w = 0.38
    ours = [100 * BURST[c]["ours_present"] / BURST[c]["n"] for c in coh]
    harv = [100 * BURST[c]["harv_present_all"] / BURST[c]["n"] for c in coh]
    b1 = ax.bar([i - w / 2 for i in x], ours, w, color=BLUE, label="MedGemma (ours)")
    b2 = ax.bar([i + w / 2 for i in x], harv, w, color=ORANGE, label="Harvard `bs`")
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.15,
                    f"{r.get_height():.1f}%", ha="center", va="bottom", fontsize=9, color=INK2)
    ax.set_title("Burst-suppression: ours vs Harvard", color=INK, fontsize=12.5,
                 fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.02, "share called present  (κ = agreement above chance)",
            transform=ax.transAxes, fontsize=8.5, color=INK2, va="bottom")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{c}\nκ {BURST[c]['kappa_all']:.2f}" for c in coh])
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    bare(ax)
    fig.tight_layout()
    fig.savefig(OUT / "background_burst.png", bbox_inches="tight", facecolor="white")
    print("saved background_burst.png")


def main():
    fig_prevalence()
    fig_burst()


if __name__ == "__main__":
    main()
