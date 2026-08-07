#!/usr/bin/env python3
"""Two charts, computed from the run JSON:
  1. Errors counted in files (reports), per category.
  2. Effect of enforcing the consistency rule: top-down vs bottom-up
     (change in fully-correct reports and in abnormality, vs doing nothing).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SRC = "results/q2_cpu_full_n1495.json"
SUB = ["focal_epileptiform_activity", "generalized_epileptiform_activity",
       "focal_non_epileptiform_activity", "generalized_non_epileptiform_activity"]
ALL = ["abnormality"] + SUB
LABELS = {"abnormality": "Abnormality", "focal_epileptiform_activity": "Focal Epi",
          "generalized_epileptiform_activity": "Gen Epi",
          "focal_non_epileptiform_activity": "Focal Non-epi",
          "generalized_non_epileptiform_activity": "Gen Non-epi"}
INK, INK2, GRID = "#141821", "#566072", "#e9edf3"
pres = lambda v: v >= 3

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.edgecolor": "#c8cfd9", "figure.dpi": 150})


def load():
    return json.loads(Path(SRC).read_text())["cases"]


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)


def chart_file_errors(cases):
    n = len(cases)
    cats = ALL
    errs = [sum(1 for x in cases if pres(x["model"][k]["pred"]) != pres(x["ld_labels"][k]))
            for k in cats]
    full = sum(1 for x in cases if all(pres(x["model"][k]["pred"]) == pres(x["ld_labels"][k])
                                       for k in ALL))
    y = np.arange(len(cats))[::-1]
    fig, ax = plt.subplots(figsize=(8.4, 4.3))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    bars = ax.barh(y, errs, 0.6, color="#2a78d6", zorder=3)
    for yi, e in zip(y, errs):
        ax.text(e + 1.5, yi, f"{e}", va="center", ha="left", color=INK,
                fontweight="bold", fontsize=11, fontfamily="monospace")
    ax.set_yticks(y); ax.set_yticklabels([LABELS[k] for k in cats], fontsize=11, color=INK2)
    ax.set_xlim(0, max(errs) + 14)
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9)
    style(ax); ax.spines["left"].set_color("#c8cfd9")
    ax.set_xlabel("Files (reports) with a wrong label vs LD", fontsize=10.5, color=INK2)
    ax.set_title("Errors counted in files, by category",
                 fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.05, f"{n-full} of {n} reports have ≥1 error  ·  {100*full/n:.0f}% "
            f"fully correct (all 5 labels)", transform=ax.transAxes,
            fontsize=10.5, color=INK2, va="bottom")
    fig.tight_layout()
    out = Path("reports/figures/eeg_file_errors.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("saved", out, errs)


def chart_repair(cases):
    n = len(cases)

    def cur(x): return {k: pres(x["model"][k]["pred"]) for k in ALL}

    def top_down(x):
        p = cur(x)
        if not p["abnormality"]:
            for s in SUB: p[s] = False
        elif not any(p[s] for s in SUB):
            p[max(SUB, key=lambda s: x["model"][s]["p_presence"])] = True
        return p

    def bottom_up(x):
        p = cur(x); p["abnormality"] = any(p[s] for s in SUB); return p

    def full(fn): return sum(all(fn(x)[k] == pres(x["ld_labels"][k]) for k in ALL) for x in cases)
    def abn(fn): return sum(fn(x)["abnormality"] == pres(x["ld_labels"]["abnormality"]) for x in cases)

    base_f, base_a = full(cur), abn(cur)
    d_full = [full(top_down) - base_f, full(bottom_up) - base_f]
    d_abn = [abn(top_down) - base_a, abn(bottom_up) - base_a]

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = np.arange(2); w = 0.34
    b1 = ax.bar(x - w/2, d_full, w, color="#2a78d6", zorder=3, label="Δ файлів повністю правильних")
    b2 = ax.bar(x + w/2, d_abn, w, color="#eb6834", zorder=3, label="Δ правильних Abnormality")
    for bars in (b1, b2):
        for b in bars:
            v = b.get_height()
            ax.text(b.get_x() + b.get_width()/2, v + (0.7 if v >= 0 else -0.7),
                    f"{v:+d}", ha="center", va="bottom" if v >= 0 else "top",
                    color=INK, fontweight="bold", fontsize=11, fontfamily="monospace")
    ax.axhline(0, color="#c8cfd9", lw=1.5, zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels(["TOP-DOWN\n(довіряй Abnormality,\nпідганяй підтипи)",
                        "BOTTOM-UP\n(з підтипів\nвиводь Abnormality)"], fontsize=10, color=INK2)
    ax.set_ylim(min(d_abn) - 6, max(d_full) + 8)
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.tick_params(axis="y", colors=INK2, labelsize=9)
    style(ax); ax.spines["left"].set_color("#c8cfd9"); ax.spines["bottom"].set_visible(False)
    ax.set_ylabel("Зміна проти «нічого не робити» (файли)", fontsize=10.5, color=INK2)
    ax.set_title("Чи допоможе примусова консистентність?",
                 fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.05, "Top-down трохи допомагає; bottom-up ламає найсильніший сигнал (Abnormality)",
            transform=ax.transAxes, fontsize=10, color=INK2, va="bottom")
    ax.legend(frameon=False, fontsize=9.5, loc="upper center",
              bbox_to_anchor=(0.5, -0.16), ncol=2, handlelength=1.1)
    fig.tight_layout()
    out = Path("reports/figures/eeg_consistency_repair.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("saved", out, "d_full=", d_full, "d_abn=", d_abn)


if __name__ == "__main__":
    Path("reports/figures").mkdir(exist_ok=True)
    cs = load()
    chart_file_errors(cs)
    chart_repair(cs)
