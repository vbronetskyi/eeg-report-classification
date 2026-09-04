#!/usr/bin/env python3
"""Abnormality-only comparison of the two labelings of the Harvard EEG reports:

    MedGemma-27B (v5g, Q4)   vs   Bio-Medical-Llama-3-8B

We compare a single finding — the overall abnormal-or-normal call — because it maps cleanly
1:1 between the two schemas. (The slowing findings do not: our focal/generalized
non-epileptiform categories bundle slowing together with attenuation, asymmetry,
disorganization, encephalopathy, and excessive beta, which the Harvard schema files under
separate columns — see analysis/mapping_check.py — so those comparisons are left out here.)

No human ground truth exists for these reports, so this is a similarity comparison. We report
the present/absent match rate (a+d)/n and Cohen's kappa (agreement beyond chance). Harvard
"abnormal" = the column is non-empty; MedGemma "abnormal" = level >= 3. BIDMC is excluded — its
report text is unavailable.

Prints the tables and saves the figures used in reports/medgemma_vs_biomedllama_abnormality.md.
Run:  python -m analysis.harvard_abnormality
"""
from __future__ import annotations

import glob
import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from analysis.full_lib import INK, INK2, GRID, BLUE, ORANGE, GREEN

GREY = "#8b94a4"
DB = "/project/6019337/databases/eeg_harvard/HarvardEEG.db"
COHORTS = ["MGH", "BWH", "BCH"]
HCOL = {"MGH": BLUE, "BWH": ORANGE, "BCH": GREEN}
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
pres = lambda v: v >= 3


def load_ours():
    d = {}
    for f in glob.glob("results/harvard/labels/*/labels_*.json"):
        for c in json.load(open(f)).get("cases", []):
            if c.get("model"):
                d[c["report_id"]] = pres(c["model"]["abnormality"]["pred"])
    return d


def load_harvard(con, table):
    hv = {}
    for rid, val in con.execute(f'SELECT "DeidentifiedName(Reports)", "abnormal" FROM "{table}"'):
        if rid:
            hv[rid] = val not in (None, "")
    return hv


def _kappa(a, b, c, d):
    n = a + b + c + d
    if n == 0:
        return 0.0
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def _stat(a, b, c, d):
    n = a + b + c + d
    return {"a": a, "b": b, "c": c, "d": d, "n": n,
            "agree": 100 * (a + d) / n, "kappa": _kappa(a, b, c, d),
            "both_abn": 100 * a / n, "both_norm": 100 * d / n, "disagree": 100 * (b + c) / n,
            "mg": 100 * (a + b) / n, "bm": 100 * (a + c) / n}


def compute(ours, con):
    res = {}
    tot = [0, 0, 0, 0]
    for coh in COHORTS:
        hv = load_harvard(con, f"{coh}_EEG_with_reports")
        a = b = c = d = 0
        for r in hv:
            if r not in ours:
                continue
            o, t = ours[r], hv[r]
            if o and t: a += 1
            elif o: b += 1
            elif t: c += 1
            else: d += 1
        res[coh] = _stat(a, b, c, d)
        for i, v in enumerate((a, b, c, d)):
            tot[i] += v
    res["Pooled"] = _stat(*tot)
    return res


def _bare(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0, colors=INK2, labelsize=9); ax.set_axisbelow(True)


def chart_by_hospital(res):
    """Match rate (filled) and kappa x100 (open) for abnormality, per hospital + pooled."""
    rows = ["Pooled", "BCH", "BWH", "MGH"]
    fig, ax = plt.subplots(figsize=(9.0, 4.3))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(rows)))
    for yi, r in zip(y, rows):
        ag, kp = res[r]["agree"], 100 * res[r]["kappa"]
        ax.plot([kp, ag], [yi, yi], color=GRID, lw=6, solid_capstyle="round", zorder=1)
    ag = [res[r]["agree"] for r in rows]
    kp = [100 * res[r]["kappa"] for r in rows]
    ax.scatter(kp, y, s=160, facecolor="white", edgecolor=BLUE, linewidth=2, zorder=3,
               label="Cohen's κ ×100 (beyond chance)")
    ax.scatter(ag, y, s=160, color=BLUE, zorder=3, edgecolor="white", linewidth=1.2,
               label="Match rate (abnormal + normal), %")
    for yi, r in zip(y, rows):
        ax.text(res[r]["agree"] + 1, yi, f"{res[r]['agree']:.0f}", ha="left", va="center",
                color=BLUE, fontsize=9.5, fontweight="bold")
        k = res[r]["kappa"]
        ax.text(100 * k - 1, yi, f"κ={k:.2f}", ha="right", va="center", color=INK2,
                fontsize=9.5, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(rows, fontsize=12, color=INK)
    ax.set_ylim(-0.6, len(rows) - 0.4); ax.set_xlim(0, 104)
    ax.set_xlabel("Agreement, %  (● raw   ○ chance-adjusted, κ×100)", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.legend(frameon=False, fontsize=9.5, loc="lower center", bbox_to_anchor=(0.5, -0.24), ncol=2)
    ax.set_title("Abnormal-or-normal: how much the two labelings agree",
                 color=INK, fontsize=13.5, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.03, "MedGemma-27B vs Bio-Medical-Llama-3-8B · by hospital and pooled",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "abnormality_by_hospital.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved abnormality_by_hospital.png")


def chart_agreement(res):
    """Per hospital: share of reports both-abnormal / both-normal / disagree."""
    rows = ["Pooled", "BCH", "BWH", "MGH"]
    fig, ax = plt.subplots(figsize=(9.4, 4.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(rows)))
    for yi, r in zip(y, rows):
        segs = [res[r]["both_abn"], res[r]["both_norm"], res[r]["disagree"]]
        cols = [GREEN, BLUE, "#d9534f"]
        left = 0.0
        for w, col in zip(segs, cols):
            ax.barh(yi, w, left=left, color=col, edgecolor="white", height=0.62, zorder=3)
            if w >= 6:
                ax.text(left + w / 2, yi, f"{w:.0f}", ha="center", va="center", color="white",
                        fontsize=9.5, fontweight="bold")
            left += w
    ax.set_yticks(y); ax.set_yticklabels(rows, fontsize=12, color=INK)
    ax.set_xlim(0, 100); ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlabel("Share of reports, %", color=INK2, fontsize=10)
    _bare(ax)
    ax.legend([Patch(color=GREEN), Patch(color=BLUE), Patch(color="#d9534f")],
              ["both abnormal", "both normal", "disagree"],
              frameon=False, fontsize=9.5, loc="lower center", bbox_to_anchor=(0.5, -0.26), ncol=3)
    ax.set_title("Where the two labelings land on abnormal vs normal",
                 color=INK, fontsize=13.5, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.04, "Most reports are agreed abnormal; disagreement is a thin slice",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "abnormality_agreement.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved abnormality_agreement.png")


def chart_callrate(res):
    """Per hospital, how often each model calls the EEG abnormal."""
    rows = ["Pooled", "BCH", "BWH", "MGH"]
    fig, ax = plt.subplots(figsize=(9.0, 4.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(rows)))
    for yi, r in zip(y, rows):
        mg, bm = res[r]["mg"], res[r]["bm"]
        ax.plot([min(mg, bm), max(mg, bm)], [yi, yi], color=GRID, lw=6, solid_capstyle="round",
                zorder=1)
    mg = [res[r]["mg"] for r in rows]; bm = [res[r]["bm"] for r in rows]
    ax.scatter(bm, y, s=160, color=GREY, zorder=3, edgecolor="white", linewidth=1.2,
               label="Bio-Medical-Llama-3-8B")
    ax.scatter(mg, y, s=160, color=BLUE, zorder=3, edgecolor="white", linewidth=1.2,
               label="MedGemma-27B (Q4)")
    for yi, r in zip(y, rows):
        ax.text(res[r]["mg"], yi + 0.2, f"{res[r]['mg']:.0f}%", ha="center", va="bottom",
                color=BLUE, fontsize=9, fontweight="bold")
        ax.text(res[r]["bm"], yi - 0.28, f"{res[r]['bm']:.0f}%", ha="center", va="top",
                color=GREY, fontsize=9, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(rows, fontsize=12, color=INK)
    ax.set_ylim(-0.6, len(rows) - 0.4); ax.set_xlim(0, 100)
    ax.set_xlabel("Share of reports called abnormal, %", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.legend(frameon=False, fontsize=9.5, loc="lower center", bbox_to_anchor=(0.5, -0.24), ncol=2)
    ax.set_title("How often each model calls the EEG abnormal",
                 color=INK, fontsize=13.5, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.03, "The two call abnormality at nearly the same rate",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "abnormality_callrate.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved abnormality_callrate.png")


if __name__ == "__main__":
    ours = load_ours()
    con = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)
    res = compute(ours, con)
    print(f"our labelled reports: {len(ours)}\n")
    print("### Abnormality — agreement, kappa, call rate\n")
    print("| Hospital | n | Match rate | Cohen's κ | MedGemma abnormal | Bio-Medical-Llama abnormal |")
    print("|---|---|---|---|---|---|")
    for r in ["MGH", "BWH", "BCH", "Pooled"]:
        s = res[r]
        print(f"| {r} | {s['n']:,} | {s['agree']:.0f}% | {s['kappa']:.2f} | {s['mg']:.0f}% | {s['bm']:.0f}% |")
    print(f"\nPooled: both-abnormal {res['Pooled']['both_abn']:.0f}%, both-normal "
          f"{res['Pooled']['both_norm']:.0f}%, disagree {res['Pooled']['disagree']:.0f}%")

    chart_by_hospital(res)
    chart_agreement(res)
    chart_callrate(res)
