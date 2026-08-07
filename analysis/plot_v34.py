#!/usr/bin/env python3
"""Charts for the v3/v4 prompt-engineering experiment (improving Focal Epi).
All numbers from results/*.json; Mistral pooled from results/pooled_summary.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.full_lib import (
    KEYS, LABELS, PAPER_MISTRAL, INK, INK2, GRID,
    BLUE, ORANGE, AQUA, VIOLET, RED, GREEN, load, f1, apply_style, bare,
)

apply_style()
OUT = Path("reports/figures")
FE = "focal_epileptiform_activity"
PROMPTS = ["v1", "v2", "v3", "v4"]
pres = lambda v: v >= 3


def pooled_cases(prompt, quant="Q2"):
    return load("zoe", prompt, quant) + load("maria", prompt, quant)


def pr(cases, k):
    tp = fp = fn = 0
    for x in cases:
        m = pres(x["model"][k]["pred"]); ld = pres(x["ld_labels"][k])
        tp += m and ld; fp += m and not ld; fn += (not m) and ld
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return (2 * p * r / (p + r) if p + r else 0.0), p, r


def grouped(ax, series, ymax=1.08, xt=None):
    x = np.arange(len(xt)); m = len(series); w = 0.8 / m
    for i, (label, vals, col) in enumerate(series):
        xs = x + (i - (m - 1) / 2) * w
        ax.bar(xs, vals, w * 0.92, label=label, color=col, zorder=3,
               edgecolor="white", linewidth=0.5)
        for xi, v in zip(xs, vals):
            ax.text(xi, v + 0.012, f"{v:.2f}", ha="center", va="bottom",
                    fontsize=8, color=INK, fontfamily="monospace")
    ax.set_ylim(0, ymax); ax.set_yticks(np.arange(0, 1.01, 0.25))
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(xt, fontsize=10.5, color=INK2)
    ax.tick_params(axis="y", colors=INK2, labelsize=8.5); bare(ax)


def chart_focal_by_prompt():
    summary = json.loads((Path("results") / "pooled_summary.json").read_text())
    mist_pool = summary["mistral_pooled_f1"][FE]
    zoe = [f1(load("zoe", p, "Q2"), FE) for p in PROMPTS] + [PAPER_MISTRAL["zoe"][1]]
    maria = [f1(load("maria", p, "Q2"), FE) for p in PROMPTS] + [PAPER_MISTRAL["maria"][1]]
    pool = [pr(pooled_cases(p), FE)[0] for p in PROMPTS] + [mist_pool]
    xt = ["v1", "v2", "v3", "v4", "Mistral-7B"]
    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    grouped(ax, [("Zoe", zoe, BLUE), ("Maria", maria, AQUA),
                 ("Pooled (1994)", pool, VIOLET)], xt=xt)
    ax.set_ylabel("Focal Epi — Core F1", fontsize=10.5, color=INK2)
    ax.set_title("MedGemma-27B — Focal Epi F1 by prompt version (Q2_K)",
                 fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=10)
    ax.legend(frameon=False, fontsize=9.5, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.09))
    fig.tight_layout()
    fig.savefig(OUT / "v34_focal_by_prompt.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("focal_by_prompt")


def chart_precision_recall():
    prec = [pr(pooled_cases(p), FE)[1] for p in PROMPTS]
    rec = [pr(pooled_cases(p), FE)[2] for p in PROMPTS]
    xt = ["v1", "v2", "v3", "v4"]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    grouped(ax, [("Precision (fewer false alarms →)", prec, ORANGE),
                 ("Recall (catch true cases)", rec, BLUE)], xt=xt)
    ax.set_ylabel("Focal Epi (pooled, n=1994)", fontsize=10.5, color=INK2)
    ax.set_title("Why v3/v4 help: they raise Focal Epi precision, keeping recall",
                 fontsize=13, color=INK, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.03, "v2 over-calls (precision crashes); v3/v4 cut false alarms",
            transform=ax.transAxes, fontsize=9.5, color=INK2)
    ax.legend(frameon=False, fontsize=9.5, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.09))
    fig.tight_layout()
    fig.savefig(OUT / "v34_precision_recall.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("precision_recall")


def chart_v1_v3_mistral():
    summary = json.loads((Path("results") / "pooled_summary.json").read_text())
    v1 = [pr(pooled_cases("v1"), k)[0] for k in KEYS]
    v3 = [pr(pooled_cases("v3"), k)[0] for k in KEYS]
    mist = [summary["mistral_pooled_f1"][k] for k in KEYS]
    fig, ax = plt.subplots(figsize=(10.0, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    grouped(ax, [("MedGemma v1", v1, "#9db8d8"),
                 ("MedGemma v3", v3, BLUE),
                 ("Mistral-7B (paper)", mist, ORANGE)], xt=LABELS)
    ax.set_ylabel("Core F1 (pooled, n=1994)", fontsize=10.5, color=INK2)
    ax.set_title("New best prompt (v3) vs previous best (v1) vs Mistral-7B — all data",
                 fontsize=13, color=INK, fontweight="bold", loc="left", pad=10)
    ax.legend(frameon=False, fontsize=9.5, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.09))
    fig.tight_layout()
    fig.savefig(OUT / "v34_v1_v3_mistral.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("v1_v3_mistral")


GREY = "#8b94a4"
PROMPT_COL = {"v1": GREY, "v2": ORANGE, "v3": BLUE, "v4": AQUA}
PROMPT_LAB = {"v1": "v1", "v2": "v2", "v3": "v3", "v4": "v4"}


def chart_variants_by_category():
    fig, ax = plt.subplots(figsize=(11, 5.2))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    series = [(PROMPT_LAB[p], [pr(pooled_cases(p), k)[0] for k in KEYS], PROMPT_COL[p])
              for p in PROMPTS]
    grouped(ax, series, xt=LABELS)
    ax.set_ylabel("Core F1 (pooled, n=1994)", fontsize=10.5, color=INK2)
    ax.set_title("MedGemma-27B — all four prompt variants, every category (pooled, Q2_K)",
                 fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=10)
    ax.legend(frameon=False, fontsize=9.5, ncol=4, loc="upper center",
              bbox_to_anchor=(0.5, -0.09))
    fig.tight_layout()
    fig.savefig(OUT / "v34_variants_by_category.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("variants_by_category")


def chart_variants_overall():
    KEYS_ = KEYS
    def full(cases):
        return sum(1 for x in cases
                   if all(pres(x["model"][k]["pred"]) == pres(x["ld_labels"][k]) for k in KEYS_))
    vals = [full(pooled_cases(p)) for p in PROMPTS]
    cols = [PROMPT_COL[p] for p in PROMPTS]
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = np.arange(len(PROMPTS))
    ax.bar(x, vals, 0.6, color=cols, zorder=3)
    for xi, v in zip(x, vals):
        ax.text(xi, v + 6, f"{v}\n{100*v/1994:.0f}%", ha="center", va="bottom",
                fontsize=10, color=INK, fontweight="bold")
    ax.set_ylim(0, 1994 * 1.02)
    ax.axhline(1994, color=GRID, lw=1)
    ax.set_xticks(x); ax.set_xticklabels([PROMPT_LAB[p] for p in PROMPTS], fontsize=11, color=INK2)
    ax.set_yticks([]); bare(ax, keep_left=False)
    ax.set_ylabel("Reports fully correct (all 5 labels) / 1994", fontsize=10, color=INK2)
    ax.set_title("MedGemma-27B — reports fully correct by prompt variant (Q2_K)",
                 fontsize=13, color=INK, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.03, "v3 is the new best; v2 is the weakest",
            transform=ax.transAxes, fontsize=9.5, color=INK2)
    fig.tight_layout()
    fig.savefig(OUT / "v34_variants_overall.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("variants_overall")


def chart_quant_by_prompt():
    def full(cases):
        return sum(1 for x in cases
                   if all(pres(x["model"][k]["pred"]) == pres(x["ld_labels"][k]) for k in KEYS))
    q2 = [full(pooled_cases(p, "Q2")) for p in PROMPTS]
    q4 = [full(pooled_cases(p, "Q4")) for p in PROMPTS]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = np.arange(len(PROMPTS)); w = 0.38
    for xs, vals, col, lab in [(x - w/2, q2, BLUE, "Q2_K (~10 GB)"),
                               (x + w/2, q4, ORANGE, "Q4_K_S (~15 GB)")]:
        ax.bar(xs, vals, w * 0.92, color=col, zorder=3, label=lab)
        for xi, v in zip(xs, vals):
            ax.text(xi, v + 6, str(v), ha="center", va="bottom", fontsize=9.5,
                    color=INK, fontweight="bold", fontfamily="monospace")
    ax.set_ylim(1400, 1994 * 1.02)
    ax.set_xticks(x); ax.set_xticklabels(PROMPTS, fontsize=11, color=INK2)
    ax.set_yticks([]); bare(ax, keep_left=False)
    ax.set_ylabel("Reports fully correct / 1994", fontsize=10, color=INK2)
    ax.set_title("MedGemma-27B — Q2_K vs Q4_K_S, by prompt",
                 fontsize=13, color=INK, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.03, "Q2 wins for v1/v3/v4; Q4 only helps v2 (y-axis starts at 1400)",
            transform=ax.transAxes, fontsize=9.5, color=INK2)
    ax.legend(frameon=False, fontsize=9.5, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(OUT / "v34_quant_by_prompt.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("quant_by_prompt")


def chart_quant_cat():
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.6))
    axes = axes.flatten()
    for idx, (k, lab) in enumerate(zip(KEYS, LABELS)):
        ax = axes[idx]; ax.set_facecolor("white")
        q2 = [pr(pooled_cases(p, "Q2"), k)[0] for p in PROMPTS]
        q4 = [pr(pooled_cases(p, "Q4"), k)[0] for p in PROMPTS]
        x = np.arange(len(PROMPTS)); w = 0.38
        for xs, vals, col in [(x - w/2, q2, BLUE), (x + w/2, q4, ORANGE)]:
            ax.bar(xs, vals, w * 0.9, color=col, zorder=3)
            for xi, v in zip(xs, vals):
                ax.text(xi, v + 0.008, f"{v:.2f}", ha="center", va="bottom",
                        fontsize=7, color=INK, fontfamily="monospace")
        ax.set_ylim(0.5, 1.03); ax.set_yticks([0.5, 0.75, 1.0])
        ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
        ax.set_xticks(x); ax.set_xticklabels(PROMPTS, fontsize=10, color=INK2)
        ax.tick_params(axis="y", colors=INK2, labelsize=8); bare(ax)
        ax.set_title(lab, fontsize=12, color=INK, fontweight="bold", loc="left")
    axes[5].axis("off")
    from matplotlib.patches import Patch
    axes[5].legend(handles=[Patch(color=BLUE, label="Q2_K (~10 GB)"),
                            Patch(color=ORANGE, label="Q4_K_S (~15 GB)")],
                   frameon=False, fontsize=11, loc="center")
    fig.suptitle("MedGemma-27B — Q2_K vs Q4_K_S, per prompt and category "
                 "(pooled n=1994, Core F1; y starts at 0.5)",
                 fontsize=13.5, fontweight="bold", color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT / "v34_quant_cat.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("quant_cat")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    chart_quant_by_prompt()
    chart_quant_cat()
    chart_variants_overall()
    chart_variants_by_category()
    chart_focal_by_prompt()
    chart_precision_recall()
    chart_v1_v3_mistral()
