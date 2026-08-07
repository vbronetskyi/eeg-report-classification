#!/usr/bin/env python3
"""One core-vs-certainty dumbbell per algorithm (v1..v4 x Q2/Q4 + Mistral),
matching figures/eeg_core_vs_cert.png. Pooled over Zoe+Maria (1994).

Core F1 = binary present/absent. Certainty F1 = strict, a positive counts only
if the exact 1-4 level matches. Line length = the drop.
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

from analysis.full_lib import KEYS, LABELS, INK, INK2, GRID, BLUE, AQUA, load

MIST_DB = ("/project/6019337/databases/eeg_fha/release_001/"
           "eeg_reports_release_001_mistral_public_250825.db")
FIELD_COL = {"abnormality": "Abnormality", "focal_epileptiform_activity": "Focal Epi",
             "generalized_epileptiform_activity": "Gen Epi",
             "focal_non_epileptiform_activity": "Focal Non-epi",
             "generalized_non_epileptiform_activity": "Gen Non-epi"}
OUT = Path("reports/figures"); OUT.mkdir(exist_ok=True)
pres = lambda v: v >= 3
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "figure.dpi": 150})


def our_pairs(prompt, quant):
    for ds in ("zoe", "maria"):
        for c in load(ds, prompt, quant):
            yield {k: c["model"][k]["pred"] for k in KEYS}, c["ld_labels"]


def mistral_pairs():
    conn = sqlite3.connect(f"file:{MIST_DB}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
    cols = ", ".join(f'"{c}" AS "{k}"' for k, c in FIELD_COL.items())
    mist = {r["hid"]: {k: int(r[k]) for k in KEYS}
            for r in conn.execute(f'SELECT Hashed_ReportURN AS hid, {cols} FROM classifications')}
    import core.cohort as co
    for ds in ("zoe", "maria"):
        os.environ["DATASET"] = ds; importlib.reload(co)
        ld = co.load_db(co.LD_DB); sg = co.load_db(co.SG_DB)
        for h in co.build_cohort(sg, ld):
            yield mist[h], {k: ld[h]["labels"][k] for k in KEYS}


def core_and_cert(pairs):
    pairs = list(pairs)
    core, cert = [], []
    for k in KEYS:
        tp = fp = fn = tpc = fpc = fnc = 0
        for pd, ld in pairs:
            m, g = pres(pd[k]), pres(ld[k])
            tp += m and g; fp += m and not g; fn += (not m) and g
            if m and g and pd[k] == ld[k]: tpc += 1
            elif m: fpc += 1
            if g and not (m and pd[k] == ld[k]): fnc += 1
        core.append(_f1(tp, fp, fn)); cert.append(_f1(tpc, fpc, fnc))
    return core, cert


def _f1(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def dumbbell(title, core, cert, out):
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(KEYS)))[::-1]
    lo = min(min(core), min(cert))
    x0 = max(0.2, (lo // 0.1) * 0.1 - 0.05)
    for yi, co, ce in zip(y, core, cert):
        ax.plot([ce, co], [yi, yi], color="#c8cfd9", lw=3, zorder=1, solid_capstyle="round")
        ax.text((co + ce) / 2, yi + 0.17, f"−{co - ce:.2f}", ha="center", va="bottom",
                fontsize=8.5, color=INK2, fontfamily="monospace")
    ax.set_ylim(-0.6, len(KEYS) - 0.25)
    ax.scatter(cert, y, s=130, color=AQUA, zorder=3, label="Certainty F1 (exact 1–4)")
    ax.scatter(core, y, s=130, color=BLUE, zorder=3, label="Core F1 (is it present?)")
    for xi, yi in zip(core, y):
        ax.text(xi + 0.012, yi, f"{xi:.2f}", va="center", ha="left", fontsize=8.5,
                color=BLUE, fontfamily="monospace", fontweight="bold")
    for xi, yi in zip(cert, y):
        ax.text(xi - 0.012, yi, f"{xi:.2f}", va="center", ha="right", fontsize=8.5,
                color=AQUA, fontfamily="monospace", fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(LABELS, fontsize=11, color=INK2)
    ax.set_xlim(x0, 1.06); ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9); ax.tick_params(length=0)
    for sp in ("top", "right", "left", "bottom"):
        ax.spines[sp].set_visible(False)
    ax.set_axisbelow(True)
    ax.set_title(title, fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.05, "F1: binary present/absent vs strict exact-level match  ·  pooled n=1994",
            transform=ax.transAxes, fontsize=10, color=INK2, va="bottom")
    ax.legend(frameon=False, fontsize=9.5, loc="lower center",
              bbox_to_anchor=(0.5, -0.16), ncol=2, handletextpad=0.3)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig); print("saved", out.name)


def dumbbell_multi(series, title, out):
    """series: list of (label, core[5], cert[5], color). Two-model overlay."""
    from matplotlib.lines import Line2D
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    ncat = len(KEYS); nser = len(series)
    lo = min(min(s[2]) for s in series)
    x0 = max(0.2, (lo // 0.1) * 0.1 - 0.05)
    yticks = []
    for ci, lab in enumerate(LABELS):
        ybase = ncat - 1 - ci; yticks.append((ybase, lab))
        for si, (slab, core, cert, col) in enumerate(series):
            yy = ybase + (si - (nser - 1) / 2) * 0.24
            ax.plot([cert[ci], core[ci]], [yy, yy], color=col, lw=3, alpha=0.85,
                    solid_capstyle="round", zorder=2)
            ax.scatter([cert[ci]], [yy], s=70, facecolor="white", edgecolor=col,
                       linewidth=2, zorder=3)
            ax.scatter([core[ci]], [yy], s=70, color=col, zorder=3)
            ax.text(core[ci] + 0.012, yy, f"{core[ci]*100:.0f}%", va="center",
                    ha="left", fontsize=7.5, color=col, fontfamily="monospace",
                    fontweight="bold")
            ax.text(cert[ci] - 0.012, yy, f"{cert[ci]*100:.0f}%", va="center",
                    ha="right", fontsize=7.5, color=col, fontfamily="monospace",
                    fontweight="bold")
    ax.set_yticks([y for y, _ in yticks])
    ax.set_yticklabels([l for _, l in yticks], fontsize=11, color=INK, fontweight="bold")
    ax.set_ylim(-0.6, ncat - 0.35); ax.set_xlim(x0 - 0.05, 1.10)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    for sp in ("top", "right", "left", "bottom"):
        ax.spines[sp].set_visible(False)
    ax.set_axisbelow(True)
    ax.set_title(title, fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.045, "● core (present/absent)   ○ exact level 1–4   ·   pooled n=1994",
            transform=ax.transAxes, fontsize=10, color=INK2, va="bottom")
    handles = [Line2D([0], [0], color=c, lw=3, label=l) for l, _, _, c in series]
    ax.legend(handles=handles, frameon=False, fontsize=10, ncol=len(series),
              loc="lower center", bbox_to_anchor=(0.5, -0.13))
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig); print("saved", out.name)


CONFIGS = [("v1", "Q2"), ("v1", "Q4"), ("v2", "Q2"), ("v2", "Q4"),
           ("v3", "Q2"), ("v3", "Q4"), ("v4", "Q2"), ("v4", "Q4")]
LAB = {"v1": "v1", "v2": "v2", "v3": "v3", "v4": "v4"}
ORANGE = "#eb6834"

if __name__ == "__main__":
    for pr, q in CONFIGS:
        core, cert = core_and_cert(our_pairs(pr, q))
        dumbbell(f"MedGemma-27B · {LAB[pr]} · {q}_K — core vs certainty",
                 core, cert, OUT / f"dumbbell_{pr}_{q.lower()}.png")
    m_core, m_cert = core_and_cert(mistral_pairs())
    dumbbell("Mistral-7B (paper) — core vs certainty",
             m_core, m_cert, OUT / "dumbbell_mistral.png")
    # combined MedGemma v1 vs Mistral for the baseline report
    v1_core, v1_cert = core_and_cert(our_pairs("v1", "Q2"))
    dumbbell_multi(
        [("MedGemma-27B (v1)", v1_core, v1_cert, BLUE),
         ("Mistral-7B", m_core, m_cert, ORANGE)],
        "MedGemma-27B (v1) vs Mistral-7B — core vs certainty",
        OUT / "baseline_v1_vs_mistral.png")
