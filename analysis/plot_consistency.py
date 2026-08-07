#!/usr/bin/env python3
"""Two consistency charts (computed from the run JSON, nothing hardcoded):
  1. Rule violations per rater (LD / SG / Model), split by direction.
  2. Inconsistency is a red flag: fully-correct rate for consistent vs
     inconsistent model outputs.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SRC = "results/q2_cpu_full_n1495.json"
SUB = ["focal_epileptiform_activity", "generalized_epileptiform_activity",
       "focal_non_epileptiform_activity", "generalized_non_epileptiform_activity"]
ALL = ["abnormality"] + SUB
INK, INK2, GRID = "#141821", "#566072", "#e9edf3"
pres = lambda v: v >= 3

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.edgecolor": "#c8cfd9", "figure.dpi": 150})


def load():
    return json.loads(Path(SRC).read_text())["cases"]


def labs(case, rater):
    if rater == "model":
        return {k: case["model"][k]["pred"] for k in ALL}
    return case[f"{rater}_labels"]


def violations(cases, rater):
    a = b = 0  # A: abnormal-no-subtype, B: normal-but-subtype
    for c in cases:
        L = labs(c, rater)
        ov, anysub = pres(L["abnormality"]), any(pres(L[s]) for s in SUB)
        if ov and not anysub:
            a += 1
        elif not ov and anysub:
            b += 1
    return a, b


def style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c8cfd9")
    ax.tick_params(length=0)
    ax.set_axisbelow(True)


def chart_violations(cases):
    raters = [("ld", "LD\n(reference)"), ("sg", "SG\n(2nd expert)"),
              ("model", "Model\n(Q2_K)")]
    A = [violations(cases, r)[0] for r, _ in raters]
    B = [violations(cases, r)[1] for r, _ in raters]
    C_A, C_B = "#eb6834", "#4a3aa7"  # orange / violet

    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = np.arange(len(raters))
    b1 = ax.bar(x, A, 0.5, color=C_A, zorder=3, label="Abnormal overall, but no subtype flagged")
    b2 = ax.bar(x, B, 0.5, bottom=A, color=C_B, zorder=3, label="Normal overall, but a subtype flagged")
    for xi, a, b in zip(x, A, B):
        tot = a + b
        if a: ax.text(xi, a/2, str(a), ha="center", va="center", color="white", fontweight="bold", fontsize=10)
        if b: ax.text(xi, a+b/2, str(b), ha="center", va="center", color="white", fontweight="bold", fontsize=10)
        ax.text(xi, tot+0.7, f"{tot}", ha="center", va="bottom", color=INK,
                fontweight="bold", fontsize=12, fontfamily="monospace")
        ax.text(xi, tot+2.4, f"{100*tot/len(cases):.1f}%", ha="center", va="bottom",
                color=INK2, fontsize=9)
    ax.set_ylim(0, max(np.array(A)+np.array(B))+6)
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_xticks(x); ax.set_xticklabels([lab for _, lab in raters], fontsize=10.5, color=INK2)
    ax.tick_params(axis="y", colors=INK2, labelsize=9)
    style(ax)
    ax.set_ylabel("Rule violations (of 1495)", fontsize=10.5, color=INK2)
    ax.set_title("Consistency-rule violations by rater",
                 fontsize=13.5, color=INK, fontweight="bold", pad=8, loc="left")
    ax.text(0, 1.10, "Rule: abnormal overall  ⇔  at least one subtype present",
            transform=ax.transAxes, fontsize=10, color=INK2)
    ax.legend(frameon=False, fontsize=9, loc="upper center",
              bbox_to_anchor=(0.5, -0.11), ncol=1, handlelength=1.1)
    fig.tight_layout()
    out = Path("reports/figures/eeg_consistency.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("saved", out, "A=", A, "B=", B)


def chart_redflag(cases):
    def full_ok(x):
        return all(pres(x["model"][k]["pred"]) == pres(x["ld_labels"][k]) for k in ALL)

    def inconsistent(x):
        L = labs(x, "model")
        return pres(L["abnormality"]) != any(pres(L[s]) for s in SUB)

    con = [x for x in cases if not inconsistent(x)]
    inc = [x for x in cases if inconsistent(x)]
    rate = [sum(full_ok(x) for x in con)/len(con), sum(full_ok(x) for x in inc)/len(inc)]
    ns = [len(con), len(inc)]
    labels = [f"Consistent output\n(n={ns[0]})", f"Inconsistent output\n(n={ns[1]})"]
    cols = ["#008300", "#e34948"]  # good / warning

    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = np.arange(2)
    ax.bar(x, rate, 0.52, color=cols, zorder=3)
    for xi, r in zip(x, rate):
        ax.text(xi, r+0.02, f"{r*100:.0f}%", ha="center", va="bottom",
                color=INK, fontweight="bold", fontsize=14, fontfamily="monospace")
    ax.set_ylim(0, 1.06)
    ax.set_yticks(np.arange(0, 1.01, 0.25))
    ax.set_yticklabels([f"{int(t*100)}%" for t in np.arange(0, 1.01, 0.25)])
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=11, color=INK2)
    ax.tick_params(axis="y", colors=INK2, labelsize=9)
    style(ax)
    ax.set_ylabel("All 5 labels correct vs LD", fontsize=10.5, color=INK2)
    ax.set_title("Inconsistency is a red flag for errors",
                 fontsize=13.5, color=INK, fontweight="bold", pad=8, loc="left")
    ax.text(0, 1.10, "When the model breaks the rule, it is almost always wrong somewhere",
            transform=ax.transAxes, fontsize=10, color=INK2)
    fig.tight_layout()
    out = Path("reports/figures/eeg_inconsistency_errors.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("saved", out, "rates=", [round(r, 2) for r in rate])


if __name__ == "__main__":
    Path("reports/figures").mkdir(exist_ok=True)
    cs = load()
    chart_violations(cs)
    chart_redflag(cs)
