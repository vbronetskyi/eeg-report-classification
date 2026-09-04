#!/usr/bin/env python3
"""Three-way comparison of the 45,545-report labelings — Mistral-7B vs our MedGemma
Q2 vs our MedGemma Q4 — with two figures:

  1. models_diff_45k.png   — how the three labelers differ from each other on the full
     set (per-category "present" rate; no ground truth needed).
  2. models_vs_human_bycat.png — accuracy on the human-annotated reports, in the
     per-category Core-vs-Certainty dumbbell style of the other reports.

The annotated set is de-duplicated first (unique by hashed id AND by report text; the
"two Maria" files are LD- vs SG-annotations of one Maria set, not two datasets).

Run:  python -m analysis.models_compare
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

from analysis.full_lib import KEYS, LABELS, INK, INK2, GRID, BLUE, VIOLET
from analysis.plot_dumbbells import core_and_cert
from analysis.plot_all_prompts import _grouped_dumbbells

GREY = "#8b94a4"
LAB_COL = dict(zip(KEYS, LABELS))
MIST_DB = ("/project/6019337/databases/eeg_fha/release_001/"
           "eeg_reports_release_001_mistral_public_250825.db")
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
pres = lambda v: v >= 3


def load_labels(pattern):
    d = {}
    for f in glob.glob(pattern):
        for c in json.load(open(f))["cases"]:
            if c.get("model"):
                d[c["hashed_id"]] = {k: c["model"][k]["pred"] for k in KEYS}
    return d


def load_mistral():
    conn = sqlite3.connect(f"file:{MIST_DB}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
    cols = ", ".join(f'"{LAB_COL[k]}" AS "{k}"' for k in KEYS)
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


def chart_diff(q2, q4, mist, both):
    """Per category, one dot per labeler at its 'present' rate — the gaps ARE the
    differences between the three labelings (all 45,545, no ground truth). Value labels
    sit above the dots and are spread horizontally (with thin leaders) so they never
    overlap, even where the three labelers coincide (the epileptiform classes)."""
    series = [("Mistral-7B", mist, GREY), ("MedGemma Q2", q2, BLUE),
              ("MedGemma Q4", q4, VIOLET)]
    rate = {name: [100 * sum(pres(d[h][k]) for h in both) / len(both) for k in KEYS]
            for name, d, _ in series}
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    top = len(KEYS) - 1
    y = [top - ci for ci in range(len(KEYS))]             # category ci sits at row y[ci]
    for ci in range(len(KEYS)):
        vals = [rate[name][ci] for name, _, _ in series]
        ax.plot([min(vals), max(vals)], [y[ci], y[ci]], color=GRID, lw=6,
                solid_capstyle="round", zorder=1)
    for name, _d, col in series:
        ax.scatter([rate[name][ci] for ci in range(len(KEYS))], y, s=150, color=col,
                   zorder=3, edgecolor="white", linewidth=1.2, label=name)
    # value labels above the dots, spread apart so they never collide
    OFF, MINSEP = 0.46, 4.0
    for ci in range(len(KEYS)):
        trip = sorted(((rate[name][ci], col) for name, _d, col in series),
                      key=lambda t: t[0])
        xs = [v for v, _ in trip]
        placed = [xs[0]]
        for i in range(1, len(xs)):
            placed.append(max(xs[i], placed[-1] + MINSEP))
        shift = sum(xs) / len(xs) - sum(placed) / len(placed)   # recenter on the cluster
        placed = [p + shift for p in placed]
        for (v, col), px in zip(trip, placed):
            if abs(px - v) > 0.4:                                # leader only when nudged
                ax.plot([v, px], [y[ci] + 0.15, y[ci] + OFF - 0.05], color=col,
                        lw=0.8, alpha=0.55, zorder=2)
            ax.text(px, y[ci] + OFF, f"{v:.0f}%", ha="center", va="bottom", fontsize=10,
                    color=col, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(LABELS, fontsize=11.5, color=INK)
    ax.set_ylim(-0.6, top + 0.9); ax.set_xlim(0, 52)
    ax.set_xlabel("Share of the 45,545 reports called 'present', %", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=10, loc="lower center",
              bbox_to_anchor=(0.5, -0.17), ncol=3)
    ax.set_title("How the three labelings differ  ·  all 45,545 reports",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.03, "Whole-report agreement: Q2~Q4 90.9% · Q4~Mistral 77.4% — "
            "they diverge on the slowing classes",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "models_diff_45k.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved models_diff_45k.png")


def chart_vs_human(q2, q4, mist, ld, ann):
    """Core + Certainty F1 vs the human annotator (LD) on the unique annotated set,
    in the shared per-category dumbbell style."""
    def cc(d):
        c, ct = core_and_cert([(d[h], {k: ld[h][k] for k in KEYS}) for h in ann])
        return [x * 100 for x in c], [x * 100 for x in ct]
    mc, mct = cc(mist); q2c, q2t = cc(q2); q4c, q4t = cc(q4)
    series = [
        ("Mistral-7B", mc, mct, GREY),
        ("MedGemma Q2", q2c, q2t, BLUE),
        ("MedGemma Q4", q4c, q4t, VIOLET),
    ]
    _grouped_dumbbells(
        series,
        "Accuracy vs the human annotator — per category",
        f"● Core F1   ○ Certainty F1 (exact 1–4 level) · line = the drop · "
        f"vs LD · n={len(ann)} annotated of 45,545",
        OUT / "models_vs_human_bycat.png", figsize=(9.8, 7.4), band=1.3)


if __name__ == "__main__":
    q4 = load_labels("results/labels/q4_k_s/labels_*.json")
    q2 = load_labels("results/labels/labels_*.json")
    mist, ld = load_mistral(), load_ld()
    both = [h for h in q4 if h in mist and h in q2]
    ann = [h for h in both if h in ld and all(isinstance(ld[h][k], int) for k in KEYS)]
    print(f"45k comparable: {len(both)} · unique annotated overlap: {len(ann)}")
    chart_diff(q2, q4, mist, both)
    chart_vs_human(q2, q4, mist, ld, ann)
