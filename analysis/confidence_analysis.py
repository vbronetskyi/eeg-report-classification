#!/usr/bin/env python3
"""Does the model's confidence track its accuracy? And can we use it?

On the 2,493 human-annotated reports we look at the MedGemma-Q4 labeling and ask:
  1. Calibration — is a "confident" score (1 or 4 on the 1-4 scale) more accurate than a
     "borderline" one (2 or 3)?
  2. Selective labeling — if we auto-accept only the reports the model is confident about
     and send the rest to a human, how does whole-report accuracy trade off against how
     many reports we keep (coverage)?

Two figures: confidence_calibration.png and confidence_coverage.png.

Run:  python -m analysis.confidence_analysis
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

from analysis.full_lib import KEYS, INK, INK2, GRID, BLUE, ORANGE, VIOLET

LAB = ["Abnormality", "Focal Epi", "Gen Epi", "Focal Non-epi", "Gen Non-epi"]
MIST_DB = ("/project/6019337/databases/eeg_fha/release_001/"
           "eeg_reports_release_001_mistral_public_250825.db")
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
pres = lambda v: v >= 3
LEVEL_NAME = {1: "1\ndefinitely\nabsent", 2: "2\nprobably\nabsent",
              3: "3\nprobably\npresent", 4: "4\ndefinitely\npresent"}


def load_labels(pattern):
    d = {}
    for f in glob.glob(pattern):
        for c in json.load(open(f))["cases"]:
            if c.get("model"):
                d[c["hashed_id"]] = {k: c["model"][k]["pred"] for k in KEYS}
    return d


def load_mistral():
    conn = sqlite3.connect(f"file:{MIST_DB}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
    cols = ", ".join(f'"{l}" AS "{k}"' for k, l in zip(KEYS, LAB))
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


def per_level(model, ld, ann):
    """(n, accuracy) per confidence level 1-4, pooled over the five findings."""
    n = {L: 0 for L in (1, 2, 3, 4)}; ok = {L: 0 for L in (1, 2, 3, 4)}
    for h in ann:
        for k in KEYS:
            L = model[h][k]; n[L] += 1; ok[L] += (pres(model[h][k]) == pres(ld[h][k]))
    return {L: (n[L], 100 * ok[L] / n[L] if n[L] else 0.0) for L in (1, 2, 3, 4)}


def chart_calibration(stats, ann_n):
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    xs = [1, 2, 3, 4]
    accs = [stats[L][1] for L in xs]
    shares = [100 * stats[L][0] / sum(stats[L2][0] for L2 in xs) for L in xs]
    cols = [BLUE, ORANGE, ORANGE, BLUE]           # confident (1,4) vs borderline (2,3)
    ax.bar(xs, accs, width=0.62, color=cols, zorder=3, edgecolor="white", linewidth=1.5)
    for x, a, sh in zip(xs, accs, shares):
        ax.text(x, a + 0.6, f"{a:.1f}%", ha="center", va="bottom", color=INK,
                fontsize=11, fontweight="bold")
        ax.text(x, 71.2, f"{sh:.0f}% of calls", ha="center", va="bottom", color=INK2,
                fontsize=8.5)
    ax.set_xticks(xs); ax.set_xticklabels([LEVEL_NAME[L] for L in xs], fontsize=9.5, color=INK)
    ax.set_ylim(70, 102); ax.set_xlim(0.4, 4.6)
    ax.set_ylabel("Present/absent accuracy vs the human, %", color=INK2, fontsize=10)
    ax.grid(axis="y", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="y", colors=INK2, labelsize=9); ax.tick_params(axis="x", length=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_color(GRID)
    ax.set_axisbelow(True)
    ax.set_title("The model knows when it is unsure",
                 color=INK, fontsize=14, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.03, "MedGemma Q4 · confident calls (1 & 4) are 99% right; "
            "borderline calls (2 & 3) only 80% · n=2,493 annotated",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "confidence_calibration.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved confidence_calibration.png")


def chart_coverage(model, ld, ann):
    nborder = lambda h: sum(model[h][k] in (2, 3) for k in KEYS)
    whole_ok = lambda h: all(pres(model[h][k]) == pres(ld[h][k]) for k in KEYS)
    order = sorted(ann, key=nborder)              # most confident reports first
    cov, acc = [], []
    correct = 0
    for i, h in enumerate(order, 1):
        correct += whole_ok(h)
        cov.append(100 * i / len(ann)); acc.append(100 * correct / i)
    base = 100 * sum(whole_ok(h) for h in ann) / len(ann)
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    ax.axhline(base, color=GRID, lw=1.4, ls="--", zorder=1)
    ax.text(101, base, f"accept all: {base:.1f}%", va="center", ha="left",
            color=INK2, fontsize=9)
    ax.plot(cov, acc, color=VIOLET, lw=2.6, zorder=3)
    # mark the "confident on all five" operating point
    n0 = sum(1 for h in ann if nborder(h) == 0)
    cov0, acc0 = 100 * n0 / len(ann), 100 * sum(whole_ok(h) for h in ann if nborder(h) == 0) / n0
    ax.scatter([cov0], [acc0], s=90, color=VIOLET, zorder=4, edgecolor="white", linewidth=1.4)
    ax.annotate(f"auto-accept the {cov0:.0f}% the model is\nsure about → {acc0:.0f}% correct",
                (cov0, acc0), xytext=(72, 98.4), fontsize=9.5, color=INK,
                ha="left", va="center", arrowprops=dict(arrowstyle="->", color=INK2, lw=1))
    ax.set_xlim(60, 108); ax.set_ylim(85, 100)
    ax.set_xlabel("Coverage — reports kept, ranked most-confident first, %", color=INK2, fontsize=10)
    ax.set_ylabel("Whole-report accuracy on kept reports, %", color=INK2, fontsize=10)
    ax.grid(color=GRID, lw=1, zorder=0)
    ax.tick_params(colors=INK2, labelsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_color(GRID)
    ax.set_axisbelow(True)
    ax.set_title("Keep the confident reports, review the rest",
                 color=INK, fontsize=14, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.03, "Accuracy climbs as we auto-accept fewer, more-confident reports · "
            "MedGemma Q4 · n=2,493 annotated",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "confidence_coverage.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved confidence_coverage.png")


def _trust_fill(acc):
    """Traffic-light fill: red at 60% -> amber at 80% -> green at 100%."""
    import matplotlib.colors as mc
    t = max(0.0, min(1.0, (acc - 60) / 40))
    c0, c1, c2 = mc.to_rgb("#e0524f"), mc.to_rgb("#e0a53a"), mc.to_rgb("#2f9e5b")
    if t < 0.5:
        u = t / 0.5; return tuple(c0[i] + (c1[i] - c0[i]) * u for i in range(3))
    u = (t - 0.5) / 0.5; return tuple(c1[i] + (c2[i] - c1[i]) * u for i in range(3))


def chart_trust_grid(q4, q2, mist, ld, ann, both):
    """2x2 of per-finding present/absent accuracy: model confidence x 3-model consensus,
    with each cell's share of all 227,725 label decisions."""
    conf = lambda h, k: q4[h][k] in (1, 4)
    unan = lambda h, k: pres(q4[h][k]) == pres(q2[h][k]) == pres(mist[h][k])
    corr = lambda h, k: pres(q4[h][k]) == pres(ld[h][k])
    ncell = len(both) * len(KEYS)

    def cell(cf, un):
        A = [(h, k) for h in ann for k in KEYS if conf(h, k) == cf and unan(h, k) == un]
        F = sum(conf(h, k) == cf and unan(h, k) == un for h in both for k in KEYS)
        return 100 * sum(corr(h, k) for h, k in A) / len(A), 100 * F / ncell

    fig, ax = plt.subplots(figsize=(7.8, 5.8))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    for ci, cf in enumerate((False, True)):            # x: borderline, confident
        for yi, un in enumerate((False, True)):         # y: split(bottom), agree(top)
            acc, cov = cell(cf, un)
            ax.add_patch(plt.Rectangle((ci - 0.5, yi - 0.5), 1, 1, facecolor=_trust_fill(acc),
                                       edgecolor="white", lw=4, zorder=1))
            ax.text(ci, yi + 0.13, f"{acc:.1f}%", ha="center", va="center", color="white",
                    fontsize=21, fontweight="bold")
            ax.text(ci, yi - 0.17, f"{cov:.0f}% of all labels", ha="center", va="center",
                    color="white", fontsize=10)
    ax.set_xlim(-0.5, 1.5); ax.set_ylim(-0.5, 1.5); ax.set_aspect("equal")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["Borderline\n(scored 2 or 3)",
                                               "Confident\n(scored 1 or 4)"],
                                              fontsize=10.5, color=INK)
    ax.set_yticks([0, 1]); ax.set_yticklabels(["Models\nsplit", "Models\nagree"],
                                              fontsize=10.5, color=INK)
    ax.set_xlabel("Model confidence", color=INK2, fontsize=11, labelpad=8)
    ax.set_ylabel("3-model consensus (Q4 · Q2 · Mistral)", color=INK2, fontsize=11, labelpad=8)
    ax.tick_params(length=0)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.set_title("Which labels to trust — two signals combined",
                 color=INK, fontsize=14, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.04, "Per-finding present/absent accuracy vs the human · top-right is the "
            "gold tier · MedGemma Q4 · n=2,493", transform=ax.transAxes,
            fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "confidence_trust_grid.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved confidence_trust_grid.png")


if __name__ == "__main__":
    q4 = load_labels("results/labels/q4_k_s/labels_*.json")
    q2 = load_labels("results/labels/labels_*.json")
    mist, ld = load_mistral(), load_ld()
    both = [h for h in q4 if h in mist and h in q2]
    ann = [h for h in both if h in ld and all(isinstance(ld[h][k], int) for k in KEYS)]
    print(f"45k={len(both)}  annotated n={len(ann)}\n")
    for name, m in [("MedGemma Q4", q4), ("MedGemma Q2", q2), ("Mistral", mist)]:
        st = per_level(m, ld, ann)
        conf = sum(st[L][0] * st[L][1] for L in (1, 4)) / sum(st[L][0] for L in (1, 4))
        bord = sum(st[L][0] * st[L][1] for L in (2, 3)) / sum(st[L][0] for L in (2, 3))
        print(f"{name:12s} confident(1,4)={conf:.1f}%  borderline(2,3)={bord:.1f}%  "
              f"| per level " + " ".join(f"{L}:{st[L][1]:.0f}" for L in (1, 2, 3, 4)))
    chart_calibration(per_level(q4, ld, ann), len(ann))
    chart_coverage(q4, ld, ann)
    chart_trust_grid(q4, q2, mist, ld, ann, both)
