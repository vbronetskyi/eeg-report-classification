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

from analysis.full_lib import (KEYS, LABELS, load, INK, INK2, GRID,
                               BLUE, ORANGE, GREEN, VIOLET)

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


def chart_bycat():
    # Horizontal grouped dot plot: one BAND per category, the 5 models stacked on their
    # own sub-rows inside the band so every dot carries a value label. Each number is the
    # per-label Core F1 (0-100) — a single-label quality score, NOT the whole-report %.
    from matplotlib.lines import Line2D
    # Q4 for the grammar variants — matches the Full-numbers table rows.
    v3g = pooled("v3g", "Q4"); v5g = pooled("v5g", "Q4"); v7g = pooled("v7g", "Q4")
    series = [
        ("Mistral-7B", MISTRAL_F1,                              GREY),
        ("v3g",        [catf1(v3g, k, MODEL, LD) for k in KEYS], ORANGE),
        ("v7g",        [catf1(v7g, k, MODEL, LD) for k in KEYS], VIOLET),
        ("v5g (best)", [catf1(v5g, k, MODEL, LD) for k in KEYS], BLUE),
        ("Human (SG)", [catf1(v5g, k, SG, LD) for k in KEYS],    GREEN),
    ]
    n = len(series); step = 0.9 / n
    fig, ax = plt.subplots(figsize=(9.4, 7.2))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    ticks = []
    for ci, lab in enumerate(LABELS):
        base = (len(KEYS) - 1 - ci) * 1.2          # category band centre
        ticks.append((base, lab))
        ax.axhline(base, color=GRID, lw=1, zorder=0)
        for i, (name, vals, col) in enumerate(series):
            yy = base + (i - (n - 1) / 2) * step
            ax.scatter([vals[ci]], [yy], s=120, color=col, zorder=3,
                       edgecolor="white", linewidth=1)
            ax.text(vals[ci] + 0.4, yy, f"{vals[ci]:.0f}", va="center", ha="left",
                    color=col, fontsize=8, fontweight="bold")
    ax.set_yticks([t for t, _ in ticks]); ax.set_yticklabels([l for _, l in ticks],
                                                             fontsize=11.5, color=INK)
    ax.set_ylim(-0.8, (len(KEYS) - 1) * 1.2 + 0.8)
    ax.set_xlim(72, 102); ax.set_xlabel("Per-label Core F1, %", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9)
    _bare(ax)
    handles = [Line2D([0], [0], marker="o", linestyle="", markersize=9, color=c, label=l)
               for l, _, c in series]
    ax.legend(handles=handles, frameon=False, fontsize=9.5, loc="lower center",
              bbox_to_anchor=(0.5, -0.11), ncol=5, handletextpad=0.2, columnspacing=1.1)
    ax.set_title("Per-category F1 — our top prompts vs Mistral-7B vs human",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.045,
            "each label scored on its own (Core F1, 0–100) · NOT the whole-report % · "
            "grammar variants at Q4_K_S · pooled n=1994",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "all_prompts_bycat.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved all_prompts_bycat.png")


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


def chart_summary_bycat():
    """Focused per-category Core F1 for the colleague summary: Mistral, v3, v5, human."""
    from matplotlib.lines import Line2D
    v3g = pooled("v3g", "Q4"); v5g = pooled("v5g", "Q4")
    series = [
        ("Mistral-7B", MISTRAL_F1,                              GREY),
        ("v3",         [catf1(v3g, k, MODEL, LD) for k in KEYS], ORANGE),
        ("v5 (best)",  [catf1(v5g, k, MODEL, LD) for k in KEYS], BLUE),
        ("Human (SG)", [catf1(v5g, k, SG, LD) for k in KEYS],    GREEN),
    ]
    n = len(series); step = 0.72 / n
    fig, ax = plt.subplots(figsize=(9.2, 5.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    ticks = []
    for ci, lab in enumerate(LABELS):
        base = (len(KEYS) - 1 - ci) * 1.2; ticks.append((base, lab))
        ax.axhline(base, color=GRID, lw=1, zorder=0)
        for i, (name, vals, col) in enumerate(series):
            yy = base + (i - (n - 1) / 2) * step
            ax.scatter([vals[ci]], [yy], s=120, color=col, zorder=3,
                       edgecolor="white", linewidth=1)
            ax.text(vals[ci] + 0.4, yy, f"{vals[ci]:.0f}", va="center", ha="left",
                    color=col, fontsize=8.5, fontweight="bold")
    ax.set_yticks([t for t, _ in ticks]); ax.set_yticklabels([l for _, l in ticks],
                                                             fontsize=11.5, color=INK)
    ax.set_ylim(-0.8, (len(KEYS) - 1) * 1.2 + 0.8); ax.set_xlim(72, 102)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9); _bare(ax)
    handles = [Line2D([0], [0], marker="o", linestyle="", markersize=9, color=c, label=l)
               for l, _, c in series]
    ax.legend(handles=handles, frameon=False, fontsize=9.5, loc="lower center",
              bbox_to_anchor=(0.5, -0.1), ncol=4, handletextpad=0.2, columnspacing=1.1)
    ax.set_title("Per-category F1 — v5 vs v3 vs Mistral-7B vs human",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.04, "each label scored on its own (Core F1) · v3/v5 at Q4_K_S · pooled n=1994",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "summary_bycat.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved summary_bycat.png")


if __name__ == "__main__":
    chart_whole()
    chart_bycat()
    chart_q2_vs_q4()
    chart_generalization()
    chart_dumbbells()
    chart_summary_whole()
    chart_summary_bycat()
