#!/usr/bin/env python3
"""Compare the two full labelings of the 45,545 processed_reports dataset —
MedGemma-27B (v5g, ours, in results/labels/) vs Mistral-7B (the paper's release DB) —
and, on the reports that also have human ground truth (LD), show which labeler is more
accurate. Prints the markdown tables used in reports/medgemma_vs_mistral.md and saves
the accuracy chart.

Run:  python -m analysis.labels_vs_mistral
"""
from __future__ import annotations

import glob
import json
import os
import importlib
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import INK, INK2, GRID, BLUE

KEYS = ["abnormality", "focal_epileptiform_activity", "generalized_epileptiform_activity",
        "focal_non_epileptiform_activity", "generalized_non_epileptiform_activity"]
LAB = ["Abnormality", "Focal Epi", "Gen Epi", "Focal Non-epi", "Gen Non-epi"]
COL = dict(zip(KEYS, LAB))
GREY = "#8b94a4"
MIST_DB = ("/project/6019337/databases/eeg_fha/release_001/"
           "eeg_reports_release_001_mistral_public_250825.db")
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
pres = lambda v: v >= 3


def load_ours():
    ours = {}
    for f in glob.glob("results/labels/labels_*.json"):
        for c in json.load(open(f))["cases"]:
            if c.get("model"):
                ours[c["hashed_id"]] = {k: c["model"][k]["pred"] for k in KEYS}
    return ours


def load_mistral():
    conn = sqlite3.connect(f"file:{MIST_DB}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
    cols = ", ".join(f'"{COL[k]}" AS "{k}"' for k in KEYS)
    return {r["hid"]: {k: int(round(r[k])) for k in KEYS}
            for r in conn.execute(f'SELECT Hashed_ReportURN AS hid, {cols} FROM classifications')}


def load_ld():
    import core.cohort as co
    ld = {}
    for ds in ("zoe", "maria"):
        os.environ["DATASET"] = ds; importlib.reload(co)
        for h, rec in co.load_db(co.LD_DB).items():
            ld[h] = rec["labels"]
    return ld


def f1(hs, a, b, k):
    tp = fp = fn = 0
    for h in hs:
        m, g = pres(a[h][k]), pres(b[h][k])
        tp += m and g; fp += m and not g; fn += (not m) and g
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 100 * (2 * p * r / (p + r) if p + r else 0.0)


def whole(hs, a, b):
    return 100 * sum(1 for h in hs if all(pres(a[h][k]) == pres(b[h][k]) for k in KEYS)) / len(hs)


def chart(ann, ours, mist, ld):
    from matplotlib.lines import Line2D
    mg = [f1(ann, ours, ld, k) for k in KEYS]
    mi = [f1(ann, mist, ld, k) for k in KEYS]
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(KEYS)))[::-1]
    for yi, a, b in zip(y, mg, mi):
        ax.plot([min(a, b), max(a, b)], [yi, yi], color=GRID, lw=6,
                solid_capstyle="round", zorder=1)
    ax.scatter(mi, y, s=150, color=GREY, zorder=3, edgecolor="white", linewidth=1.2,
               label="Mistral-7B")
    ax.scatter(mg, y, s=150, color=BLUE, zorder=3, edgecolor="white", linewidth=1.2,
               label="MedGemma v5g (ours)")
    for yi, a in zip(y, mg):
        ax.text(a + 0.6, yi, f"{a:.0f}", va="center", ha="left", color=BLUE,
                fontsize=9, fontweight="bold")
    for yi, b in zip(y, mi):
        ax.text(b - 0.6, yi, f"{b:.0f}", va="center", ha="right", color=GREY,
                fontsize=9, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(LAB, fontsize=11, color=INK)
    ax.set_ylim(-0.6, len(KEYS) - 0.4); ax.set_xlim(68, 100)
    ax.set_xlabel("Core F1 vs the human annotator (LD), %", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=10, loc="lower center",
              bbox_to_anchor=(0.5, -0.22), ncol=2)
    ax.set_title("Accuracy on the annotated reports — MedGemma vs Mistral",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.03, f"Core F1 vs human ground truth (LD) · n={len(ann)} annotated of 45,545",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "mistral_45k_accuracy.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved mistral_45k_accuracy.png")


if __name__ == "__main__":
    ours, mist, ld = load_ours(), load_mistral(), load_ld()
    both = [h for h in ours if h in mist]
    ann = [h for h in both if h in ld and all(isinstance(ld[h][k], int) for k in KEYS)]
    print(f"45k comparable: {len(both)} · annotated overlap: {len(ann)}\n")
    print("### Agreement on the 45,545 reports (present/absent)\n")
    print("| Category | MedGemma 'present' | Mistral 'present' | Agreement |")
    print("|---|---|---|---|")
    for k in KEYS:
        mg = 100 * sum(pres(ours[h][k]) for h in both) / len(both)
        mi = 100 * sum(pres(mist[h][k]) for h in both) / len(both)
        ag = 100 * sum(pres(ours[h][k]) == pres(mist[h][k]) for h in both) / len(both)
        print(f"| {COL[k]} | {mg:.1f}% | {mi:.1f}% | {ag:.1f}% |")
    print(f"\nWhole-report agreement (present/absent): {whole(both, ours, mist):.1f}%")
    print("\n### Accuracy vs human (LD) on the annotated overlap — Core F1\n")
    print("| Category | MedGemma | Mistral |")
    print("|---|---|---|")
    for k in KEYS:
        print(f"| {COL[k]} | {f1(ann, ours, ld, k):.1f} | {f1(ann, mist, ld, k):.1f} |")
    print(f"| **Whole-report** | **{whole(ann, ours, ld):.1f}%** | **{whole(ann, mist, ld):.1f}%** |")
    chart(ann, ours, mist, ld)
