#!/usr/bin/env python3
"""Compare two LLM labelings of the same Harvard EEG reports:

  MedGemma-27B (v5g, Q4)   vs   Bio-Medical-Llama-3-8B (Harvard's pipeline)

for the three mappings the PI asked for:

  MedGemma Abnormality      <-> abnormal
  MedGemma Focal non-epi    <-> foc slowing
  MedGemma Gen non-epi      <-> gen slowing

There is no human ground truth for the Harvard reports, so this is a similarity comparison
between two independent labelers. We report both raw present/absent agreement and Cohen's
kappa (agreement beyond chance) — kappa matters because raw agreement is inflated for the
rare findings, where both models say "absent" most of the time. Harvard "present" = the
finding column is non-empty; MedGemma "present" = level >= 3. BIDMC is excluded — its report
text is unavailable.

Prints the tables and saves the figures used in reports/medgemma_vs_biomedllama.md.
Run:  python -m analysis.harvard_compare
"""
from __future__ import annotations

import glob
import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import INK, INK2, GRID, BLUE, ORANGE, GREEN

GREY = "#8b94a4"
DB = "/project/6019337/databases/eeg_harvard/HarvardEEG.db"
COHORTS = ["MGH", "BWH", "BCH"]                 # BIDMC excluded — no report text
HCOL = {"MGH": BLUE, "BWH": ORANGE, "BCH": GREEN}
TABLE = {c: f"{c}_EEG_with_reports" for c in COHORTS}
MAP = [
    ("abnormality", "abnormal", "Abnormality"),
    ("focal_non_epileptiform_activity", "foc slowing", "Focal slowing"),
    ("generalized_non_epileptiform_activity", "gen slowing", "Gen. slowing"),
]
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
pres = lambda v: v >= 3


def load_ours():
    d = {}
    for f in glob.glob("results/harvard/labels/*/labels_*.json"):
        for c in json.load(open(f)).get("cases", []):
            if c.get("model"):
                d[c["report_id"]] = {k: c["model"][k]["pred"] for k in (m[0] for m in MAP)}
    return d


def load_harvard(con, table):
    cols = [m[1] for m in MAP]
    q = 'SELECT "DeidentifiedName(Reports)", ' + ", ".join(f'"{c}"' for c in cols) + \
        f' FROM "{table}"'
    hv = {}
    for row in con.execute(q):
        rid = row[0]
        if not rid:
            continue
        rec = hv.setdefault(rid, {c: False for c in cols})
        for i, c in enumerate(cols, start=1):
            if row[i] not in (None, ""):
                rec[c] = True
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
    return {"agree": 100 * (a + d) / n, "mg": 100 * (a + b) / n, "bm": 100 * (a + c) / n,
            "kappa": _kappa(a, b, c, d), "n": n}


def compute(ours, con):
    conf = {m[2]: {} for m in MAP}          # label -> coh -> [a,b,c,d]
    for coh in COHORTS:
        hv = load_harvard(con, TABLE[coh])
        ids = [r for r in hv if r in ours]
        for ourk, hcol, label in MAP:
            a = b = c = d = 0
            for r in ids:
                o, t = pres(ours[r][ourk]), hv[r][hcol]
                if o and t: a += 1
                elif o: b += 1
                elif t: c += 1
                else: d += 1
            conf[label][coh] = [a, b, c, d]
    res = {}
    for _, _, label in MAP:
        res[label] = {coh: _stat(*conf[label][coh]) for coh in COHORTS}
        A = [sum(conf[label][coh][i] for coh in COHORTS) for i in range(4)]
        res[label]["pooled"] = _stat(*A)
    return res


def _bare(ax, axis="x"):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0); ax.set_axisbelow(True); ax.tick_params(colors=INK2, labelsize=9)


def chart_overall(ours, con):
    """Per report: on how many of the three findings do the two labelings agree (0-3)?"""
    dist = {c: [0, 0, 0, 0] for c in COHORTS}
    for coh in COHORTS:
        hv = load_harvard(con, TABLE[coh])
        for r in hv:
            if r not in ours:
                continue
            a = sum(1 for ourk, hcol, _ in MAP if pres(ours[r][ourk]) == hv[r][hcol])
            dist[coh][a] += 1
    pooled = [sum(dist[c][k] for c in COHORTS) for k in range(4)]
    rows = ["Pooled", "BCH", "BWH", "MGH"]
    data = {"Pooled": pooled, **dist}
    seg_col = ["#d9534f", "#e0a53a", "#9ccb6b", "#2f9e5b"]
    seg_lab = ["0 of 3", "1 of 3", "2 of 3", "all 3 agree"]
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(rows)))
    for yi, name in zip(y, rows):
        tot = sum(data[name]); left = 0.0
        for k in range(4):
            w = 100 * data[name][k] / tot
            ax.barh(yi, w, left=left, color=seg_col[k], edgecolor="white", height=0.62, zorder=3)
            if w >= 5:
                ax.text(left + w/2, yi, f"{w:.0f}", ha="center", va="center", color="white",
                        fontsize=9, fontweight="bold")
            left += w
    ax.set_yticks(y); ax.set_yticklabels(rows, fontsize=11.5, color=INK)
    ax.set_xlim(0, 100); ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlabel("Share of reports, %", color=INK2, fontsize=10)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID); ax.tick_params(length=0, colors=INK2, labelsize=9)
    from matplotlib.patches import Patch
    ax.legend([Patch(color=seg_col[k]) for k in (3, 2, 1, 0)], [seg_lab[k] for k in (3, 2, 1, 0)],
              frameon=False, fontsize=9.5, loc="lower center", bbox_to_anchor=(0.5, -0.28), ncol=4)
    ax.set_title("Overall label agreement — how many of the three findings match",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    allc = sum(pooled[k]*k for k in range(4)) / (3*sum(pooled))
    ax.text(0, 1.04, f"MedGemma-27B vs Bio-Medical-Llama-3-8B · {100*allc:.0f}% of all label "
            f"decisions match · {100*pooled[3]/sum(pooled):.0f}% of reports match on all three",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "harvard_overall.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved harvard_overall.png")


def chart_agreement_kappa(res):
    """Per category: raw present/absent agreement (filled) vs Cohen's kappa x100 (open), pooled."""
    labels = [m[2] for m in MAP]
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(labels)))[::-1]
    for yi, lab in zip(y, labels):
        ag, kp = res[lab]["pooled"]["agree"], 100*res[lab]["pooled"]["kappa"]
        ax.plot([kp, ag], [yi, yi], color=GRID, lw=6, solid_capstyle="round", zorder=1)
    ag = [res[lab]["pooled"]["agree"] for lab in labels]
    kp = [100*res[lab]["pooled"]["kappa"] for lab in labels]
    ax.scatter(kp, y, s=150, facecolor="white", edgecolor=BLUE, linewidth=2, zorder=3,
               label="Cohen's κ ×100 (agreement beyond chance)")
    ax.scatter(ag, y, s=150, color=BLUE, zorder=3, edgecolor="white", linewidth=1.2,
               label="Match rate (present + absent), %")
    for yi, v in zip(y, ag):
        ax.text(v + 1, yi, f"{v:.0f}", ha="left", va="center", color=BLUE, fontsize=9,
                fontweight="bold")
    for yi, lab in zip(y, labels):
        k = res[lab]["pooled"]["kappa"]
        ax.text(100*k - 1, yi, f"κ={k:.2f}", ha="right", va="center", color=INK2, fontsize=9,
                fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11.5, color=INK)
    ax.set_ylim(-0.6, len(labels) - 0.4); ax.set_xlim(0, 104)
    ax.set_xlabel("Agreement, %  (● raw   ○ chance-adjusted, κ×100)", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.legend(frameon=False, fontsize=9.5, loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    ax.set_title("How similar the two labelings are, per finding",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.03, "Raw agreement is inflated for the rare findings; κ shows the real "
            "similarity · pooled MGH+BWH+BCH", transform=ax.transAxes, fontsize=9,
            color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "harvard_kappa.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved harvard_kappa.png")


def chart_match_by_hospital(res):
    """Per category, the present/absent match rate (a+d)/n for each hospital."""
    labels = [m[2] for m in MAP]
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(labels)))[::-1]
    for yi, lab in zip(y, labels):
        vals = [res[lab][c]["agree"] for c in COHORTS]
        ax.plot([min(vals), max(vals)], [yi, yi], color=GRID, lw=6, solid_capstyle="round", zorder=1)
    for coh in COHORTS:
        xs = [res[lab][coh]["agree"] for lab in labels]
        ax.scatter(xs, y, s=150, color=HCOL[coh], zorder=3, edgecolor="white", linewidth=1.2,
                   label=coh)
    off = {"MGH": 0.30, "BWH": 0.18, "BCH": 0.06}
    for i, lab in enumerate(labels):
        for coh in COHORTS:
            v = res[lab][coh]["agree"]
            ax.text(v, y[i] + off[coh], f"{v:.0f}", ha="center", va="bottom", color=HCOL[coh],
                    fontsize=8, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11.5, color=INK)
    ax.set_ylim(-0.6, len(labels) - 0.15); ax.set_xlim(55, 102)
    ax.set_xlabel("Label match rate (present + absent), %", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.legend(frameon=False, fontsize=10, loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=3)
    ax.set_title("How often the two labelings match, by hospital",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.03, "Present/absent match rate per finding · MedGemma-27B vs "
            "Bio-Medical-Llama-3-8B", transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "harvard_matchrate_hospital.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved harvard_matchrate_hospital.png")


def chart_kappa_by_hospital(res):
    """Per category, Cohen's kappa for each hospital."""
    labels = [m[2] for m in MAP]
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(labels)))[::-1]
    for yi, lab in zip(y, labels):
        vals = [res[lab][c]["kappa"] for c in COHORTS]
        ax.plot([min(vals), max(vals)], [yi, yi], color=GRID, lw=6, solid_capstyle="round", zorder=1)
    for coh in COHORTS:
        xs = [res[lab][coh]["kappa"] for lab in labels]
        ax.scatter(xs, y, s=150, color=HCOL[coh], zorder=3, edgecolor="white", linewidth=1.2,
                   label=coh)
    off = {"MGH": 0.30, "BWH": 0.18, "BCH": 0.06}   # stagger so close values don't overlap
    for i, lab in enumerate(labels):
        for coh in COHORTS:
            v = res[lab][coh]["kappa"]
            ax.text(v, y[i] + off[coh], f"{v:.2f}", ha="center", va="bottom", color=HCOL[coh],
                    fontsize=8, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11.5, color=INK)
    ax.set_ylim(-0.6, len(labels) - 0.15); ax.set_xlim(0, 1.0)
    ax.set_xlabel("Cohen's κ (agreement beyond chance)", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.legend(frameon=False, fontsize=10, loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=3)
    ax.set_title("Similarity beyond chance, by hospital",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.03, "Cohen's κ per finding · MedGemma-27B vs Bio-Medical-Llama-3-8B",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "harvard_kappa_hospital.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved harvard_kappa_hospital.png")


def chart_callrate(res):
    """Per category, how often each model calls the finding present (pooled)."""
    labels = [m[2] for m in MAP]
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(labels)))[::-1]
    for yi, lab in zip(y, labels):
        mg, bm = res[lab]["pooled"]["mg"], res[lab]["pooled"]["bm"]
        ax.plot([min(mg, bm), max(mg, bm)], [yi, yi], color=GRID, lw=6, solid_capstyle="round",
                zorder=1)
    mg = [res[lab]["pooled"]["mg"] for lab in labels]
    bm = [res[lab]["pooled"]["bm"] for lab in labels]
    ax.scatter(bm, y, s=150, color=GREY, zorder=3, edgecolor="white", linewidth=1.2,
               label="Bio-Medical-Llama-3-8B")
    ax.scatter(mg, y, s=150, color=BLUE, zorder=3, edgecolor="white", linewidth=1.2,
               label="MedGemma-27B (Q4)")
    for yi, v in zip(y, mg):
        ax.text(v, yi + 0.2, f"{v:.0f}%", ha="center", va="bottom", color=BLUE, fontsize=9,
                fontweight="bold")
    for yi, v in zip(y, bm):
        ax.text(v, yi - 0.28, f"{v:.0f}%", ha="center", va="top", color=GREY, fontsize=9,
                fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11.5, color=INK)
    ax.set_ylim(-0.6, len(labels) - 0.4); ax.set_xlim(0, 85)
    ax.set_xlabel("Share of reports called 'present', %  ·  pooled MGH+BWH+BCH",
                  color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.legend(frameon=False, fontsize=10, loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    ax.set_title("How often each model calls the finding present",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.03, "Aligned on overall abnormality; they diverge on the slowing findings",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "harvard_callrate.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved harvard_callrate.png")


if __name__ == "__main__":
    ours = load_ours()
    con = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)
    res = compute(ours, con)
    print(f"our labelled reports: {len(ours)}\n")

    print("### Similarity per finding — agreement and Cohen's kappa\n")
    print("| Finding | MGH agree / κ | BWH agree / κ | BCH agree / κ | Pooled agree / κ |")
    print("|---|---|---|---|---|")
    for _, _, lab in MAP:
        r = res[lab]
        cells = " | ".join(f"{r[c]['agree']:.0f}% / {r[c]['kappa']:.2f}"
                           for c in COHORTS + ["pooled"])
        print(f"| {lab} | {cells} |")
    print(f"\n(n: MGH {res['Abnormality']['MGH']['n']}, BWH {res['Abnormality']['BWH']['n']}, "
          f"BCH {res['Abnormality']['BCH']['n']}, pooled {res['Abnormality']['pooled']['n']})")

    print("\n### Call rate — share marked 'present' (pooled)\n")
    print("| Finding | MedGemma-27B (Q4) | Bio-Medical-Llama-3-8B |")
    print("|---|---|---|")
    for _, _, lab in MAP:
        r = res[lab]["pooled"]
        print(f"| {lab} | {r['mg']:.0f}% | {r['bm']:.0f}% |")

    chart_overall(ours, con)
    chart_agreement_kappa(res)
    chart_match_by_hospital(res)
    chart_kappa_by_hospital(res)
    chart_callrate(res)
