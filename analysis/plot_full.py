#!/usr/bin/env python3
"""Generate every chart for the full v1/v2 x zoe/maria x Q2/Q4 experiment.

All numbers are computed from results/*.json (paper Mistral columns are the
published Table III constants). Figures -> figures/.
Usage: python -m analysis.plot_full
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.full_lib import (
    KEYS, LABELS, PAPER_MISTRAL, INK, INK2, GRID,
    BLUE, ORANGE, AQUA, VIOLET, RED, GREEN,
    load, f1_all, f1, fp_fn, apply_style, bare,
)

apply_style()
OUT = Path("reports/figures")
OUT.mkdir(exist_ok=True)
DS_TITLE = {"zoe": "Zoe (n=1495)", "maria": "Maria (n=499)"}


def grouped(ax, series, ymax=1.08, value_fmt="{:.2f}"):
    """series: list of (label, values[5], color)."""
    x = np.arange(len(LABELS))
    m = len(series)
    w = 0.8 / m
    for i, (label, vals, col) in enumerate(series):
        xs = x + (i - (m - 1) / 2) * w
        ax.bar(xs, vals, w * 0.92, label=label, color=col, zorder=3,
               edgecolor="white", linewidth=0.5)
        for xi, v in zip(xs, vals):
            ax.text(xi, v + 0.012, value_fmt.format(v), ha="center",
                    va="bottom", fontsize=7.2, color=INK,
                    fontfamily="monospace")
    ax.set_ylim(0, ymax)
    ax.set_yticks(np.arange(0, 1.01, 0.25))
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(LABELS, fontsize=9.5, color=INK2)
    ax.tick_params(axis="y", colors=INK2, labelsize=8.5)
    bare(ax)


def core_f1_chart(ds):
    v1 = f1_all(load(ds, "v1", "Q2"))
    v2 = f1_all(load(ds, "v2", "Q2"))
    human = f1_all(load(ds, "v1", "Q2"), source="sg")
    fig, ax = plt.subplots(figsize=(9.6, 4.8))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    grouped(ax, [
        ("Our Q2 · prompt v1", v1, BLUE),
        ("Our Q2 · prompt v2", v2, VIOLET),
        ("Mistral-7B · paper", PAPER_MISTRAL[ds], ORANGE),
        ("Human (2nd annotator)", human, AQUA),
    ])
    ax.set_ylabel("Core F1  (higher = better)", fontsize=10, color=INK2)
    ax.set_title(f"{DS_TITLE[ds]} — accuracy by category",
                 fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=10)
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="upper center",
              bbox_to_anchor=(0.5, -0.09))
    fig.tight_layout()
    fig.savefig(OUT / f"{ds}_core_f1.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print(ds, "core_f1")


def prompt_effect_chart(ds):
    d = {q: {p: f1_all(load(ds, p, q)) for p in ("v1", "v2")} for q in ("Q2", "Q4")}
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = np.arange(len(LABELS)); w = 0.38
    dq2 = [b - a for a, b in zip(d["Q2"]["v1"], d["Q2"]["v2"])]
    dq4 = [b - a for a, b in zip(d["Q4"]["v1"], d["Q4"]["v2"])]
    for xs, dvals, col, lab in [(x - w/2, dq2, BLUE, "Q2_K"), (x + w/2, dq4, ORANGE, "Q4_K_S")]:
        ax.bar(xs, dvals, w * 0.92, color=col, zorder=3, label=lab)
        for xi, v in zip(xs, dvals):
            ax.text(xi, v + (0.004 if v >= 0 else -0.004), f"{v:+.2f}", ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=7.5, color=INK,
                    fontfamily="monospace")
    ax.axhline(0, color="#c8cfd9", lw=1.5)
    lim = max(abs(min(dq2 + dq4)), abs(max(dq2 + dq4))) + 0.06
    ax.set_ylim(-lim, lim)
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(LABELS, fontsize=9.5, color=INK2)
    ax.tick_params(axis="y", colors=INK2, labelsize=8.5)
    bare(ax); ax.spines["bottom"].set_visible(False)
    ax.set_ylabel("Δ Core F1  (v2 − v1)", fontsize=10, color=INK2)
    ax.set_title(f"{DS_TITLE[ds]} — effect of the professor's prompt (v2)",
                 fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.03, "above 0 = v2 better · below 0 = v2 worse",
            transform=ax.transAxes, fontsize=9.5, color=INK2)
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(OUT / f"{ds}_prompt_effect.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print(ds, "prompt_effect")


def quant_chart(ds):
    q2 = f1_all(load(ds, "v1", "Q2")); q4 = f1_all(load(ds, "v1", "Q4"))
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    grouped(ax, [("Q2_K (~10 GB)", q2, BLUE), ("Q4_K_S (~15 GB)", q4, ORANGE)])
    ax.set_ylabel("Core F1", fontsize=10, color=INK2)
    ax.set_title(f"{DS_TITLE[ds]} — quantization: Q2_K vs Q4_K_S (prompt v1)",
                 fontsize=13, color=INK, fontweight="bold", loc="left", pad=10)
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(OUT / f"{ds}_quant.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print(ds, "quant")


def over_under_chart(ds):
    cases = load(ds, "v1", "Q2")
    fp = [fp_fn(cases, k)[0] for k in KEYS]
    fn = [fp_fn(cases, k)[1] for k in KEYS]
    tfp, tfn = sum(fp), sum(fn)
    y = np.arange(len(LABELS))[::-1]
    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    ax.barh(y, fp, 0.6, color=BLUE, zorder=3, label=f"Over-call — false alarms ({tfp})")
    ax.barh(y, [-v for v in fn], 0.6, color=RED, zorder=3, label=f"Under-call — misses ({tfn})")
    for yi, a, b in zip(y, fp, fn):
        if a: ax.text(a + max(fp) * 0.02, yi, str(a), va="center", ha="left",
                      color=BLUE, fontsize=9, fontfamily="monospace", fontweight="bold")
        if b: ax.text(-b - max(fp) * 0.02, yi, str(b), va="center", ha="right",
                      color=RED, fontsize=9, fontfamily="monospace", fontweight="bold")
    ax.axvline(0, color="#8b94a4", lw=1.5)
    ax.set_yticks(y); ax.set_yticklabels(LABELS, fontsize=10, color=INK2)
    ax.set_xlim(-max(fn) - max(fp) * 0.18, max(fp) + max(fp) * 0.18)
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=8.5)
    bare(ax, keep_left=False)
    ax.set_title(f"{DS_TITLE[ds]} — over- vs under-calling (Q2 · v1)",
                 fontsize=13, color=INK, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.04, f"{tfp} false alarms vs {tfn} misses "
            f"({tfp/max(tfn,1):.1f}:1) — {'over-cautious' if tfp>tfn else 'conservative'}",
            transform=ax.transAxes, fontsize=9.5, color=INK2)
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout()
    fig.savefig(OUT / f"{ds}_over_under.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print(ds, "over_under")


def combined_core_f1():
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 4.8), sharey=True)
    fig.patch.set_facecolor("white")
    for ax, ds in zip(axes, ("zoe", "maria")):
        ax.set_facecolor("white")
        ours = f1_all(load(ds, "v1", "Q2"))
        human = f1_all(load(ds, "v1", "Q2"), source="sg")
        grouped(ax, [
            ("Our Q2 (v1)", ours, BLUE),
            ("Mistral-7B (paper)", PAPER_MISTRAL[ds], ORANGE),
            ("Human", human, AQUA),
        ])
        ax.set_title(DS_TITLE[ds], fontsize=12.5, color=INK, fontweight="bold", loc="left")
    axes[0].set_ylabel("Core F1", fontsize=10, color=INK2)
    axes[0].legend(frameon=False, fontsize=9, ncol=3, loc="upper center",
                   bbox_to_anchor=(1.02, -0.09))
    fig.suptitle("Our model vs the paper's Mistral-7B and human — both datasets",
                 fontsize=14, fontweight="bold", color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT / "combined_core_f1.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("combined core_f1")


def generalization_chart():
    zoe = f1_all(load("zoe", "v1", "Q2")); maria = f1_all(load("maria", "v1", "Q2"))
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    grouped(ax, [("Zoe (in-distribution)", zoe, BLUE),
                 ("Maria (out-of-distribution)", maria, AQUA)])
    ax.set_ylabel("Core F1", fontsize=10, color=INK2)
    ax.set_title("Generalization — same model (Q2 · v1) on both neurologists",
                 fontsize=13, color=INK, fontweight="bold", loc="left", pad=10)
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(OUT / "generalization.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("generalization")


def reliability_chart():
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    edges = [0.0, 0.9, 0.99, 0.999, 1.0001]
    bands = ["Unsure\n<90%", "Fairly sure\n90–99%", "Confident\n99–99.9%", "Very confident\n≥99.9%"]
    x = np.arange(len(bands)); w = 0.38
    for off, ds, col in [(-w/2, "zoe", BLUE), (w/2, "maria", AQUA)]:
        cases = load(ds, "v1", "Q2")
        pts = []
        for c in cases:
            for k in KEYS:
                m = c["model"][k]
                pts.append((max(m["p1"], m["p2"], m["p3"], m["p4"]),
                            1 if m["pred"] == c["ld_labels"][k] else 0))
        accs = []
        for lo, hi in zip(edges, edges[1:]):
            sub = [v for cf, v in pts if lo <= cf < hi]
            accs.append(sum(sub) / len(sub) if sub else 0)
        ax.bar(x + off, accs, w * 0.92, color=col, zorder=3, label=ds.capitalize())
        for xi, a in zip(x + off, accs):
            ax.text(xi, a + 0.015, f"{a*100:.0f}%", ha="center", va="bottom",
                    fontsize=8.5, color=INK, fontfamily="monospace", fontweight="bold")
    ax.set_ylim(0, 1.1); ax.set_yticks(np.arange(0, 1.01, 0.25))
    ax.set_yticklabels([f"{int(t*100)}%" for t in np.arange(0, 1.01, 0.25)])
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(bands, fontsize=9.5, color=INK2)
    ax.tick_params(axis="y", colors=INK2, labelsize=8.5)
    bare(ax)
    ax.set_ylabel("Exact accuracy", fontsize=10, color=INK2)
    ax.set_title("Confidence stays meaningful on both datasets (Q2 · v1)",
                 fontsize=13, color=INK, fontweight="bold", loc="left", pad=10)
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(OUT / "reliability_both.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("reliability")


def pooled_best_vs_mistral():
    import json
    s = json.loads((Path("results") / "pooled_summary.json").read_text())
    ours = [s["our_pooled_f1"][k] for k in KEYS]
    mist = [s["mistral_pooled_f1"][k] for k in KEYS]
    fig, ax = plt.subplots(figsize=(9.8, 5.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    grouped(ax, [(f"Our best (MedGemma-27B, {s['best']})", ours, BLUE),
                 ("Mistral-7B (paper)", mist, ORANGE)])
    ax.set_ylabel("Core F1  (higher = better)", fontsize=10, color=INK2)
    ax.set_title(f"All data pooled (Zoe + Maria, n={s['n']}) — our best vs Mistral-7B",
                 fontsize=14, color=INK, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.03, f"Fully-correct reports (all 5 labels): "
            f"ours {s['our_full']}/{s['n']} vs Mistral {s['mistral_full']}/{s['n']}",
            transform=ax.transAxes, fontsize=10, color=INK2)
    ax.legend(frameon=False, fontsize=10, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(OUT / "pooled_best_vs_mistral.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("pooled best_vs_mistral")


def core_vs_cert_pooled():
    import json
    s = json.loads((Path("results") / "pooled_summary.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.0), sharey=True)
    fig.patch.set_facecolor("white")
    panels = [("Core agreement — normal / abnormal", "core_acc"),
              ("Certainty agreement — exact level 1–4", "cert_acc")]
    for ax, (title, key) in zip(axes, panels):
        ax.set_facecolor("white")
        grouped(ax, [
            (f"Our best ({s['best']})", [s[key]["ours"][k] for k in KEYS], BLUE),
            ("Mistral-7B", [s[key]["mistral"][k] for k in KEYS], ORANGE),
            ("Human", [s[key]["human"][k] for k in KEYS], AQUA),
        ], value_fmt="{:.2f}")
        ax.set_title(title, fontsize=12.5, color=INK, fontweight="bold", loc="left")
    axes[0].set_ylabel("Accuracy (share of reports matching LD)", fontsize=10, color=INK2)
    axes[0].legend(frameon=False, fontsize=9, ncol=3, loc="upper center",
                   bbox_to_anchor=(1.02, -0.09))
    fig.suptitle(f"How exactly do we match the expert? — pooled, n={s['n']}",
                 fontsize=14, fontweight="bold", color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUT / "pooled_core_vs_cert.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("pooled core_vs_cert")


def core_vs_cert_dumbbell():
    import json
    from matplotlib.lines import Line2D
    s = json.loads((Path("results") / "pooled_summary.json").read_text())
    raters = [("Our best", BLUE, "ours"), ("Mistral-7B", ORANGE, "mistral"),
              ("Human", AQUA, "human")]
    fig, ax = plt.subplots(figsize=(11, 6.2))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    ncat = len(KEYS)
    yticks = []
    for ci, (k, lab) in enumerate(zip(KEYS, LABELS)):
        ybase = ncat - 1 - ci
        yticks.append((ybase, lab))
        for ri, (rlab, col, rk) in enumerate(raters):
            yy = ybase + (1 - ri) * 0.26
            core = s["core_acc"][rk][k]; cert = s["cert_acc"][rk][k]
            ax.plot([cert, core], [yy, yy], color=col, lw=3.2, alpha=0.85,
                    solid_capstyle="round", zorder=2)
            ax.scatter([cert], [yy], s=70, facecolor="white", edgecolor=col,
                       linewidth=2, zorder=3)
            ax.scatter([core], [yy], s=70, color=col, zorder=3)
            ax.text(cert - 0.006, yy, f"{cert:.2f}", va="center", ha="right",
                    fontsize=7, color=col, fontfamily="monospace")
    ax.set_yticks([y for y, _ in yticks])
    ax.set_yticklabels([lab for _, lab in yticks], fontsize=11, color=INK, fontweight="bold")
    ax.set_ylim(-0.6, ncat - 0.4)
    ax.set_xlim(0.6, 1.02)
    ax.set_xlabel("Accuracy vs LD", fontsize=10, color=INK2)
    ax.xaxis.set_major_locator(plt.MultipleLocator(0.1))
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.set_axisbelow(True)
    ax.set_title("Core → certainty drop: the longer the line, the bigger the gap",
                 fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=30)
    ax.text(0, 1.045, f"○ exact level 1–4   ●—● …to… normal/abnormal   ·   pooled n={s['n']}",
            transform=ax.transAxes, fontsize=10, color=INK2)
    handles = [Line2D([0], [0], color=c, lw=3.2, label=l) for l, c, _ in raters]
    ax.legend(handles=handles, frameon=False, fontsize=9.5, ncol=3,
              loc="upper center", bbox_to_anchor=(0.5, -0.09))
    fig.tight_layout()
    fig.savefig(OUT / "pooled_cert_dumbbell.png", bbox_inches="tight", facecolor="white")
    plt.close(fig); print("pooled cert_dumbbell")


if __name__ == "__main__":
    pooled_best_vs_mistral()
    core_vs_cert_pooled()
    core_vs_cert_dumbbell()
    combined_core_f1()
    generalization_chart()
    reliability_chart()
    for ds in ("zoe", "maria"):
        core_f1_chart(ds)
        prompt_effect_chart(ds)
        quant_chart(ds)
        over_under_chart(ds)
