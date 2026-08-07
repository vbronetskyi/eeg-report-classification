#!/usr/bin/env python3
"""Two extra result charts:
  1. Reliability — exact accuracy rises with the model's own confidence.
  2. Core vs Certainty-adjusted accuracy per category (the paper's nuance).
Saves PNGs under figures/.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MultipleLocator

SRC = "results/q2_cpu_full_n1495.json"
FIELDS = [
    ("abnormality", "Abnormality"),
    ("focal_epileptiform_activity", "Focal Epi"),
    ("generalized_epileptiform_activity", "Gen Epi"),
    ("focal_non_epileptiform_activity", "Focal Non-epi"),
    ("generalized_non_epileptiform_activity", "Gen Non-epi"),
]
INK, INK2, GRID = "#141821", "#566072", "#e9edf3"
BLUE, AQUA = "#2a78d6", "#1baf7a"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.edgecolor": "#c8cfd9", "figure.dpi": 150,
})


def load():
    return json.loads(Path(SRC).read_text())["cases"]


def style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c8cfd9")
    ax.tick_params(length=0)
    ax.set_axisbelow(True)


def reliability(cases):
    # pool all field predictions; confidence = peak prob among the 4 levels
    pts = []
    for x in cases:
        for k, _ in FIELDS:
            m = x["model"][k]
            conf = max(m["p1"], m["p2"], m["p3"], m["p4"])
            pts.append((conf, 1 if m["pred"] == x["ld_labels"][k] else 0))
    edges = [0.0, 0.9, 0.99, 0.999, 1.0001]
    labels = ["Unsure\n(<90%)", "Fairly sure\n(90–99%)",
              "Confident\n(99–99.9%)", "Very confident\n(≥99.9%)"]
    total = len(pts)
    accs, shares = [], []
    for lo, hi in zip(edges, edges[1:]):
        sub = [c for cf, c in pts if lo <= cf < hi]
        accs.append(sum(sub) / len(sub) if sub else 0)
        shares.append(len(sub) / total)

    # sequential blue ramp light->dark by bin
    ramp = ["#bcd4f2", "#7fb0e8", "#4a8ee0", "#1f66c2"]
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = np.arange(len(labels))
    bars = ax.bar(x, accs, 0.62, color=ramp, zorder=3,
                  edgecolor="white", linewidth=0.8)
    txtcol = ["#1f3d66", "#12305c", "white", "white"]  # per-bar readable ink
    for b, a, sh, tc in zip(bars, accs, shares, txtcol):
        ax.text(b.get_x()+b.get_width()/2, a+0.02, f"{a*100:.0f}%",
                ha="center", va="bottom", fontsize=12, color=INK,
                fontweight="bold", fontfamily="monospace")
        ax.text(b.get_x()+b.get_width()/2, 0.04, f"{sh*100:.0f}% of\npredictions",
                ha="center", va="bottom", fontsize=8.5, color=tc,
                fontweight="bold")
    ax.set_ylim(0, 1.12)
    ax.set_yticks(np.arange(0, 1.01, 0.25))
    ax.set_yticklabels([f"{int(t*100)}%" for t in np.arange(0, 1.01, 0.25)])
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10.5, color=INK2)
    ax.tick_params(axis="y", colors=INK2, labelsize=9)
    style(ax)
    ax.set_ylabel("Exact accuracy", fontsize=10.5, color=INK2)
    ax.set_title("The model knows when it is unsure",
                 fontsize=14, color=INK, fontweight="bold", pad=6, loc="left")
    ax.text(0, 1.20, "Exact-match accuracy vs the model's own confidence  ·  n=1495 reports",
            transform=ax.transAxes, fontsize=10.5, color=INK2, va="bottom")
    fig.tight_layout()
    out = Path("reports/figures/eeg_reliability.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("saved", out, "accs=", [round(a, 2) for a in accs])


def core_vs_cert(cases):
    pres = lambda v: v >= 3

    def core_f1(k):  # binary present/absent F1 (same metric as chart 1)
        tp = fp = fn = 0
        for x in cases:
            m, ld = pres(x["model"][k]["pred"]), pres(x["ld_labels"][k])
            tp += m and ld; fp += m and not ld; fn += (not m) and ld
        p = tp/(tp+fp) if tp+fp else 0; r = tp/(tp+fn) if tp+fn else 0
        return 2*p*r/(p+r) if p+r else 0

    def cert_f1(k):  # strict F1: a positive counts only if the exact 1-4 level matches
        tp = fp = fn = 0
        for x in cases:
            mp, lp = x["model"][k]["pred"], x["ld_labels"][k]
            m, ld = pres(mp), pres(lp)
            if m and ld and mp == lp: tp += 1
            elif m: fp += 1
            if ld and not (m and mp == lp): fn += 1
        p = tp/(tp+fp) if tp+fp else 0; r = tp/(tp+fn) if tp+fn else 0
        return 2*p*r/(p+r) if p+r else 0

    labels = [lab for _, lab in FIELDS]
    core = [core_f1(k) for k, _ in FIELDS]
    cert = [cert_f1(k) for k, _ in FIELDS]

    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = np.arange(len(labels))[::-1]
    for yi, co, ce in zip(y, core, cert):
        ax.plot([ce, co], [yi, yi], color="#c8cfd9", lw=3, zorder=1,
                solid_capstyle="round")
        ax.text((co+ce)/2, yi+0.17, f"−{(co-ce):.2f}", ha="center",
                va="bottom", fontsize=8.5, color=INK2, fontfamily="monospace")
    ax.set_ylim(-0.6, 4.75)
    ax.scatter(cert, y, s=130, color=AQUA, zorder=3, label="Certainty F1 (exact 1–4)")
    ax.scatter(core, y, s=130, color=BLUE, zorder=3, label="Core F1 (is it present?)")
    for xi, yi in zip(core, y):
        ax.text(xi+0.012, yi, f"{xi:.2f}", va="center", ha="left",
                fontsize=8.5, color=BLUE, fontfamily="monospace", fontweight="bold")
    for xi, yi in zip(cert, y):
        ax.text(xi-0.012, yi, f"{xi:.2f}", va="center", ha="right",
                fontsize=8.5, color=AQUA, fontfamily="monospace", fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11, color=INK2)
    ax.set_xlim(0.30, 1.06)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9)
    style(ax); ax.spines["bottom"].set_visible(False)
    ax.set_title("Getting the level of confidence right is harder",
                 fontsize=14, color=INK, fontweight="bold", pad=30, loc="left")
    ax.text(0, 1.055, "F1 (same metric as chart 1): binary present/absent vs strict exact-level match",
            transform=ax.transAxes, fontsize=10.5, color=INK2, va="bottom")
    ax.legend(frameon=False, fontsize=9.5, loc="lower center",
              bbox_to_anchor=(0.5, -0.16), ncol=2, handletextpad=0.3)
    fig.tight_layout()
    out = Path("reports/figures/eeg_core_vs_cert.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("saved", out)


if __name__ == "__main__":
    Path("reports/figures").mkdir(exist_ok=True)
    cs = load()
    reliability(cs)
    core_vs_cert(cs)
