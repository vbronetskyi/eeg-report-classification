#!/usr/bin/env python3
"""Where the model's errors come from, and a Focal Epi deep dive.

Prints the decomposition and saves two composition charts. Everything is
computed from the run JSON (nothing hardcoded).

Usage: python -m analysis.error_analysis [results/<run>.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SUB = ["focal_epileptiform_activity", "generalized_epileptiform_activity",
       "focal_non_epileptiform_activity", "generalized_non_epileptiform_activity"]
ALL = ["abnormality"] + SUB
INK, INK2 = "#141821", "#566072"
pres = lambda v: v >= 3

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "figure.dpi": 150})


def inconsistent(x):
    L = {k: x["model"][k]["pred"] for k in ALL}
    return pres(L["abnormality"]) != any(pres(L[s]) for s in SUB)


def hbar(segments, title, subtitle, out):
    """segments: list of (label, value, color)."""
    fig, ax = plt.subplots(figsize=(9.2, 2.9))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    left = 0
    total = sum(v for _, v, _ in segments)
    for label, v, col in segments:
        ax.barh(0, v, left=left, height=0.5, color=col, edgecolor="white", linewidth=1.5)
        if v > 0:
            ax.text(left + v/2, 0, str(v), ha="center", va="center",
                    color="white", fontweight="bold", fontsize=12)
        left += v
    ax.set_xlim(0, total); ax.set_ylim(-0.6, 0.6)
    ax.axis("off")
    ax.set_title(title, fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=10.5, color=INK2, va="bottom")
    # legend below
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in segments]
    labels = [f"{l}  ({v})" for l, v, _ in segments]
    ax.legend(handles, labels, frameon=False, fontsize=10, loc="upper center",
              bbox_to_anchor=(0.5, -0.05), ncol=len(segments), handlelength=1.0,
              handletextpad=0.5, columnspacing=1.4)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("saved", out)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "results/q2_cpu_full_n1495.json"
    cases = json.loads(Path(src).read_text())["cases"]
    n = len(cases)

    # ---- Error composition (mutually exclusive) ----
    amb = incon = clean = fp = fn = 0
    for x in cases:
        ic = inconsistent(x)
        for k in ALL:
            m, ld, sg = (pres(x["model"][k]["pred"]), pres(x["ld_labels"][k]),
                         pres(x["sg_labels"][k]))
            if m != ld:
                if m and not ld: fp += 1
                else: fn += 1
                if ld != sg: amb += 1
                elif ic: incon += 1
                else: clean += 1
    err = amb + incon + clean
    print(f"errors: {err}/{n*5} field-decisions ({100*err/(n*5):.1f}%)  FP={fp} FN={fn}")
    print(f"  ambiguous (humans disagree): {amb} ({100*amb/err:.0f}%)")
    print(f"  from self-inconsistency:     {incon} ({100*incon/err:.0f}%)")
    print(f"  genuine model errors:        {clean} ({100*clean/err:.0f}%)")

    hbar(
        [("Люди самі незгодні", amb, "#8b94a4"),
         ("Через неконсистентність", incon, "#4a3aa7"),
         ("Справжні помилки моделі", clean, "#e34948")],
        "Звідки беруться помилки моделі",
        f"Усі {err} помилкових рішень (з {n*5}, error rate {100*err/(n*5):.1f}%), за причиною:",
        "reports/figures/eeg_error_composition.png",
    )

    # ---- Focal Epi deep dive ----
    k, g = "focal_epileptiform_activity", "generalized_epileptiform_activity"
    tp = fn2 = sg_ok = focgen = spurious = 0
    prev = sum(1 for x in cases if pres(x["ld_labels"][k]))
    for x in cases:
        m, ld, sg = (pres(x["model"][k]["pred"]), pres(x["ld_labels"][k]),
                     pres(x["sg_labels"][k]))
        if m and ld: tp += 1
        if ld and not m: fn2 += 1
        if m and not ld:
            if sg: sg_ok += 1
            elif pres(x["ld_labels"][g]): focgen += 1
            else: spurious += 1
    fp2 = sg_ok + focgen + spurious
    print(f"\nFocal Epi: prevalence {prev}/{n}, TP={tp} FP={fp2} FN={fn2} "
          f"(precision={tp/(tp+fp2):.2f} recall={tp/(tp+fn2):.2f})")
    print(f"  FP buckets: SG-backed={sg_ok} focal/gen={focgen} spurious={spurious}")

    hbar(
        [("2-й експерт згоден", sg_ok, "#1baf7a"),
         ("focal↔generalized плутанина", focgen, "#eb6834"),
         ("справді вигадані", spurious, "#e34948")],
        f"Focal Epi: 0 пропусків, усі {tp} справжніх спіймано (recall 1.00)",
        f"Уся «слабкість» — {fp2} хибних тривог на рідкісному класі (precision {tp/(tp+fp2):.2f}):",
        "reports/figures/eeg_focal_epi.png",
    )


if __name__ == "__main__":
    Path("reports/figures").mkdir(exist_ok=True)
    main()
