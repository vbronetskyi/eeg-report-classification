#!/usr/bin/env python3
"""Charts for the slowing report, from results/harvard/slowing_gold.json:
 1. present-rate — our labels vs Harvard's — per hospital, focal & generalized
 2. our recall on Harvard's expert-verified present reports (closest to ground truth)
Run: python -m analysis.slowing_chart   (outputs to reports/figures/)
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import INK, INK2, BLUE, ORANGE, AQUA, apply_style, bare

G = json.load(open("results/harvard/slowing_gold.json"))
COH = ["MGH", "BWH", "BCH"]
TIT = {"focal": "Focal slowing", "generalized": "Generalized slowing"}
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)


def fig_present():
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.3))
    x = range(len(COH)); w = 0.38
    for ax, field in zip(axes, ["focal", "generalized"]):
        ours = [100 * G[field][c]["ours_present"] / G[field][c]["n"] for c in COH]
        harv = [100 * G[field][c]["harv_present_all"] / G[field][c]["n"] for c in COH]
        b1 = ax.bar([i - w / 2 for i in x], ours, w, color=BLUE, label="MedGemma (ours)")
        b2 = ax.bar([i + w / 2 for i in x], harv, w, color=ORANGE, label="Harvard annotation")
        for bars in (b1, b2):
            for r in bars:
                ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 1.5,
                        f"{r.get_height():.0f}%", ha="center", va="bottom",
                        fontsize=9, color=INK2)
        ax.set_title(TIT[field], color=INK, fontsize=12.5, fontweight="bold", loc="left", pad=18)
        ax.text(0, 1.02, "share of reports called present  (κ = agreement above chance)",
                transform=ax.transAxes, fontsize=8.5, color=INK2, va="bottom")
        ax.set_xticks(list(x))
        ax.set_xticklabels([f"{c}\nκ {G[field][c]['kappa_all']:.2f}" for c in COH])
        ax.set_ylim(0, 100); ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_yticklabels(["0", "25", "50", "75", "100%"])
        bare(ax)
    axes[0].legend(frameon=False, fontsize=9, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT / "slowing_vs_harvard.png", bbox_inches="tight", facecolor="white")
    print("saved slowing_vs_harvard.png")


def fig_recall():
    apply_style()
    fig, ax = plt.subplots(figsize=(6.2, 4.3))
    cohs = ["MGH", "BWH"]; x = range(len(cohs)); w = 0.38
    foc = [100 * G["focal"][c]["our_recall_on_verified"] for c in cohs]
    gen = [100 * G["generalized"][c]["our_recall_on_verified"] for c in cohs]
    b1 = ax.bar([i - w / 2 for i in x], foc, w, color=BLUE, label="focal")
    b2 = ax.bar([i + w / 2 for i in x], gen, w, color=AQUA, label="generalized")
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 1.2,
                    f"{r.get_height():.0f}%", ha="center", va="bottom",
                    fontsize=9.5, color=INK2)
    ax.set_title("Do we catch what an expert confirmed?", color=INK, fontsize=12.5,
                 fontweight="bold", loc="left", pad=18)
    ax.text(0, 1.02, "our recall on Harvard's expert-verified present reports",
            transform=ax.transAxes, fontsize=8.5, color=INK2, va="bottom")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{c}\nfoc n={G['focal'][c]['verified_present_labeled']}  "
                        f"gen n={G['generalized'][c]['verified_present_labeled']}" for c in cohs])
    ax.set_ylim(0, 100); ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0", "25", "50", "75", "100%"])
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    bare(ax)
    fig.tight_layout()
    fig.savefig(OUT / "slowing_recall_verified.png", bbox_inches="tight", facecolor="white")
    print("saved slowing_recall_verified.png")


def main():
    fig_present()
    fig_recall()


if __name__ == "__main__":
    main()
