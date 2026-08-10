#!/usr/bin/env python3
"""Charts for reports/all_prompts.md — the all-prompts results report.

Two figures, pooled over Zoe+Maria (n=1994), Core F1 vs LD:
  all_prompts_whole.png   — whole-report accuracy for every config (the climb)
  all_prompts_bycat.png   — per-category F1: our best (v5g) vs Mistral vs human

Everything is computed from results/*.json + stored sg_labels; Mistral's per-category
values are the paper's Table III (reproduced by analysis.pooled). Reproducible:
    python -m analysis.plot_all_prompts
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from matplotlib.ticker import MultipleLocator

from analysis.full_lib import (KEYS, LABELS, load, INK, INK2, GRID,
                               BLUE, ORANGE, GREEN, VIOLET, RED)

GREY = "#8b94a4"

OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
pres = lambda v: v >= 3
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "figure.dpi": 150})

# Mistral-7B, paper Table III (reproduced by analysis.pooled), pooled n=1994
MISTRAL_F1 = [94.7, 82.8, 74.8, 75.6, 75.2]
MISTRAL_WHOLE = 74.5


def pooled(variant, quant):
    return load("zoe", variant, quant) + load("maria", variant, quant)


def whole(cases, truth="ld_labels"):
    ok = sum(1 for c in cases
             if all(pres(c["model"][k]["pred"]) == pres(c[truth][k]) for k in KEYS))
    return 100 * ok / len(cases)


def catf1(cases, k, pred, truth):
    tp = fp = fn = 0
    for c in cases:
        m, g = pres(pred(c, k)), pres(truth(c, k))
        tp += m and g; fp += m and not g; fn += (not m) and g
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 100 * (2 * p * r / (p + r) if p + r else 0.0)


MODEL = lambda c, k: c["model"][k]["pred"]
LD = lambda c, k: c["ld_labels"][k]
SG = lambda c, k: c["sg_labels"][k]


def _bare(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)


def chart_whole():
    # Cleveland dot plot — position (not bar length) encodes the value, so the
    # non-zero axis is honest. Grammar variants use Q4; v5g is the best.
    rows = [
        ("Mistral-7B",        MISTRAL_WHOLE,              GREY),
        ("v1 (baseline)",     whole(pooled("v1", "Q2")),  BLUE),
        ("v3",                whole(pooled("v3", "Q2")),  BLUE),
        ("v8g (simplified)",  whole(pooled("v8g", "Q4")), BLUE),
        ("v10g (calibrated)", whole(pooled("v10g", "Q4")),BLUE),
        ("v3g",               whole(pooled("v3g", "Q4")), BLUE),
        ("v7g",               whole(pooled("v7g", "Q4")), BLUE),
        ("v5g  (best)",       whole(pooled("v5g", "Q4")), ORANGE),
        ("Human (SG vs LD)",  89.8,                       GREEN),
    ]
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(8.8, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x0 = 72
    for yi, (name, val, col) in enumerate(rows):
        ax.plot([x0, val], [yi, yi], color=GRID, lw=1.5, zorder=1,
                solid_capstyle="round")           # faint stem
        ax.scatter([val], [yi], s=150, color=col, zorder=3)
        ax.text(val + 0.45, yi, f"{val:.1f}%", va="center", ha="left",
                color=col, fontsize=9.5, fontweight="bold", zorder=4)
    ax.axvline(89.8, color=GREEN, lw=1.1, ls=":", zorder=1)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], color=INK2)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(x0, 92)
    ax.set_xlabel("Whole-report accuracy (all 5 labels correct), %", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9)
    _bare(ax)
    ax.set_title("MedGemma-27B — whole-report accuracy by prompt  ·  pooled n=1994",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.035, "each dot = one configuration · dotted line = human annotator agreement (89.8%)",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "all_prompts_whole.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved all_prompts_whole.png")




def _grouped2(series, title, out, ylabel="Core F1, %", ylim=(72, 101)):
    """Two-series grouped dot plot over the 5 categories, with value labels."""
    from matplotlib.lines import Line2D
    import numpy as np
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = np.arange(len(KEYS)); off = 0.16
    for xi in x:
        ax.plot([xi, xi], list(ylim), color=GRID, lw=1, zorder=0)
    for i, (name, vals, col) in enumerate(series):
        xs = x + (i - 0.5) * off
        ax.scatter(xs, vals, s=130, color=col, zorder=3, edgecolor="white", linewidth=1)
        for xv, v in zip(xs, vals):
            ax.text(xv, v + 0.7, f"{v:.0f}", ha="center", va="bottom", fontsize=8,
                    color=col, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(LABELS, fontsize=9.5, color=INK2)
    ax.set_xlim(-0.5, len(KEYS) - 0.5); ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel, color=INK2, fontsize=10)
    ax.grid(axis="y", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="y", colors=INK2, labelsize=9)
    _bare(ax); ax.spines["left"].set_visible(False)
    handles = [Line2D([0], [0], marker="o", linestyle="", markersize=9, color=c, label=l)
               for l, _, c in series]
    ax.legend(handles=handles, frameon=False, fontsize=9.5, loc="lower center",
              bbox_to_anchor=(0.5, -0.17), ncol=2, handletextpad=0.3)
    ax.set_title(title, color=INK, fontsize=13, fontweight="bold", loc="left", pad=14)
    fig.tight_layout(); fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig); print("saved", out.name)


def chart_q2_vs_q4():
    q2 = pooled("v5g", "Q2"); q4 = pooled("v5g", "Q4")
    _grouped2([("Q2_K (~10 GB)", [catf1(q2, k, MODEL, LD) for k in KEYS], BLUE),
               ("Q4_K_S (~15 GB)", [catf1(q4, k, MODEL, LD) for k in KEYS], ORANGE)],
              "Which quantization? — v5g Q2_K vs Q4_K_S per category  ·  n=1994",
              OUT / "all_prompts_q2_vs_q4.png")


def chart_generalization():
    zoe = load("zoe", "v5g", "Q4"); maria = load("maria", "v5g", "Q4")
    _grouped2([("Zoe (in-distribution)", [catf1(zoe, k, MODEL, LD) for k in KEYS], BLUE),
               ("Maria (out-of-distribution)", [catf1(maria, k, MODEL, LD) for k in KEYS], ORANGE)],
              "Generalization — v5g on the seen vs an unseen neurologist",
              OUT / "all_prompts_generalization.png", ylim=(68, 101))


def chart_dumbbells():
    """Core F1 vs strict Certainty F1 (exact 1-4 level), per prompt with Q2 & Q4
    overlaid, plus Mistral and the best-vs-Mistral headline. Reuses plot_dumbbells."""
    from analysis.plot_dumbbells import (our_pairs, mistral_pairs, core_and_cert,
                                         dumbbell, dumbbell_multi)
    LAB = {"v3g": "v3g", "v5g": "v5g (best)", "v7g": "v7g",
           "v8g": "v8g (simplified)", "v10g": "v10g (calibrated)"}
    for pr in ["v5g", "v3g", "v7g", "v8g", "v10g"]:
        c2, ct2 = core_and_cert(our_pairs(pr, "Q2"))
        c4, ct4 = core_and_cert(our_pairs(pr, "Q4"))
        dumbbell_multi([("Q2_K", c2, ct2, BLUE), ("Q4_K_S", c4, ct4, ORANGE)],
                       f"MedGemma-27B · {LAB[pr]} — core vs certainty (Q2 vs Q4)",
                       OUT / f"dumbbell_{pr}.png")
    mc, mct = core_and_cert(mistral_pairs())
    dumbbell("Mistral-7B — core vs certainty", mc, mct, OUT / "dumbbell_mistral.png")
    v5c, v5ct = core_and_cert(our_pairs("v5g", "Q4"))
    dumbbell_multi([("MedGemma v5g", v5c, v5ct, BLUE), ("Mistral-7B", mc, mct, ORANGE)],
                   "MedGemma v5g vs Mistral-7B — core vs certainty",
                   OUT / "all_prompts_v5g_vs_mistral.png")


def chart_summary_whole():
    """Focused whole-report climb for the colleague summary: Mistral, v3, v5, human."""
    rows = [
        ("Mistral-7B",   MISTRAL_WHOLE,               GREY),
        ("v3 (Q2)",      whole(pooled("v3g", "Q2")),  ORANGE),
        ("v3 (Q4)",      whole(pooled("v3g", "Q4")),  ORANGE),
        ("v5 (Q2)",      whole(pooled("v5g", "Q2")),  BLUE),
        ("v5 (Q4, best)", whole(pooled("v5g", "Q4")), BLUE),
        ("Human (SG)",   89.8,                        GREEN),
    ]
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(8.6, 3.9))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x0 = 72
    for yi, (name, val, col) in enumerate(rows):
        ax.plot([x0, val], [yi, yi], color=GRID, lw=1.5, zorder=1, solid_capstyle="round")
        ax.scatter([val], [yi], s=150, color=col, zorder=3)
        ax.text(val + 0.4, yi, f"{val:.1f}%", va="center", ha="left", color=col,
                fontsize=9.5, fontweight="bold")
    ax.axvline(89.8, color=GREEN, lw=1.1, ls=":", zorder=1)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], color=INK2)
    ax.set_ylim(-0.6, len(rows) - 0.4); ax.set_xlim(x0, 92)
    ax.set_xlabel("Whole-report accuracy (all 5 labels correct), %", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9); _bare(ax)
    ax.set_title("Whole-report accuracy  ·  pooled n=1994",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.04, "dotted line = human annotator agreement (89.8%)",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "summary_whole.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved summary_whole.png")


def _grouped_dumbbells(series, title, subtitle, out, figsize=(9.6, 8.4), band=1.5):
    """series: list of (label, core[5], cert[5], color). Per category (row band), one
    dumbbell per model: filled dot = Core F1, open dot = Certainty F1, line = the drop."""
    from matplotlib.lines import Line2D
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    n = len(series); step = (band * 0.62) / n
    ticks = []
    for ci, lab in enumerate(LABELS):
        base = (len(KEYS) - 1 - ci) * band; ticks.append((base, lab))
        ax.axhline(base, color=GRID, lw=1, zorder=0)
        for i, (name, core, cert, col) in enumerate(series):
            yy = base + (i - (n - 1) / 2) * step
            ax.plot([cert[ci], core[ci]], [yy, yy], color=col, lw=2.4, alpha=0.85,
                    solid_capstyle="round", zorder=2)
            ax.scatter([cert[ci]], [yy], s=46, facecolor="white", edgecolor=col,
                       linewidth=1.7, zorder=3)          # Certainty (open)
            ax.scatter([core[ci]], [yy], s=58, color=col, zorder=3)   # Core (filled)
            ax.text(core[ci] + 0.7, yy, f"{core[ci]:.0f}", va="center", ha="left",
                    fontsize=7, color=col, fontweight="bold")   # Core % — right of dot
            ax.text(cert[ci] - 0.7, yy, f"{cert[ci]:.0f}", va="center", ha="right",
                    fontsize=7, color=col, fontweight="bold")   # Certainty % — left of dot
    ax.set_yticks([t for t, _ in ticks]); ax.set_yticklabels([l for _, l in ticks],
                                                             fontsize=11.5, color=INK)
    ax.set_ylim(-band * 0.7, (len(KEYS) - 1) * band + band * 0.7)
    ax.set_xlim(33, 104); ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.set_xlabel("F1, %  ·  ● Core (present/absent)   ○ Certainty (exact 1–4 level)",
                  color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9); _bare(ax)
    handles = [Line2D([0], [0], marker="o", linestyle="", markersize=9, color=c, label=l)
               for l, _core, _cert, c in series]
    ax.legend(handles=handles, frameon=False, fontsize=9.5, loc="lower center",
              bbox_to_anchor=(0.5, -0.12), ncol=len(series), handletextpad=0.2,
              columnspacing=0.9)
    ax.set_title(title, color=INK, fontsize=13, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig); print("saved", out.name)


def _mistral_pairs_ds(datasets):
    """(mistral_pred, ld) pairs restricted to the given dataset(s)."""
    import os, importlib, sqlite3
    db = ("/project/6019337/databases/eeg_fha/release_001/"
          "eeg_reports_release_001_mistral_public_250825.db")
    fc = {"abnormality": "Abnormality", "focal_epileptiform_activity": "Focal Epi",
          "generalized_epileptiform_activity": "Gen Epi",
          "focal_non_epileptiform_activity": "Focal Non-epi",
          "generalized_non_epileptiform_activity": "Gen Non-epi"}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
    cols = ", ".join(f'"{c}" AS "{k}"' for k, c in fc.items())
    mist = {r["hid"]: {k: int(r[k]) for k in KEYS}
            for r in conn.execute(f'SELECT Hashed_ReportURN AS hid, {cols} FROM classifications')}
    import core.cohort as co
    out = []
    for ds in datasets:
        os.environ["DATASET"] = ds; importlib.reload(co)
        ld = co.load_db(co.LD_DB); sg = co.load_db(co.SG_DB)
        for h in co.build_cohort(sg, ld):
            out.append((mist[h], {k: ld[h]["labels"][k] for k in KEYS}))
    return out


def chart_summary_bycat(datasets=("zoe", "maria"), suffix="", ntag="pooled n=1994"):
    """Per category: Mistral, v3 (Q2/Q4), v5 (Q2/Q4), human — both Core F1 (filled) and
    Certainty F1 (open), for the given dataset(s). suffix names the output file."""
    from analysis.plot_dumbbells import core_and_cert
    def cc(pairs):
        c, ct = core_and_cert(pairs); return [x*100 for x in c], [x*100 for x in ct]
    def our(v, q):
        return cc([({k: c["model"][k]["pred"] for k in KEYS}, c["ld_labels"])
                   for ds in datasets for c in load(ds, v, q)])
    mc, mct = cc(_mistral_pairs_ds(datasets))
    hc, hct = cc([(c["sg_labels"], c["ld_labels"]) for ds in datasets for c in load(ds, "v1", "Q2")])
    v3q2c, v3q2t = our("v3g", "Q2"); v3q4c, v3q4t = our("v3g", "Q4")
    v5q2c, v5q2t = our("v5g", "Q2"); v5q4c, v5q4t = our("v5g", "Q4")
    series = [
        ("Mistral-7B", mc, mct, GREY),
        ("v3 (Q2)", v3q2c, v3q2t, ORANGE),
        ("v3 (Q4)", v3q4c, v3q4t, RED),
        ("v5 (Q2)", v5q2c, v5q2t, BLUE),
        ("v5 (Q4)", v5q4c, v5q4t, VIOLET),
        ("Human (SG)", hc, hct, GREEN),
    ]
    _grouped_dumbbells(
        series,
        "Per-category — Core vs Certainty F1  ·  all six models",
        f"● Core F1   ○ Certainty F1 (exact level) · line = the drop · {ntag}",
        OUT / f"summary_bycat{suffix}.png", figsize=(9.8, 8.6))


if __name__ == "__main__":
    chart_whole()
    chart_q2_vs_q4()
    chart_generalization()
    chart_dumbbells()
    chart_summary_whole()
    chart_summary_bycat()
    chart_summary_bycat(("zoe",), "_zoe", "Zoe · in-distribution · n=1495")
    chart_summary_bycat(("maria",), "_maria", "Maria · out-of-distribution · n=499")
