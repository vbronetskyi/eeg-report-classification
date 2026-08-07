#!/usr/bin/env python3
"""Does the model over-call (false alarms) or under-call (misses)?

Diverging bar per category: false positives (over-call, model says present but
LD absent) to the right, false negatives (under-call, miss) to the left.
Computed from the run JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SRC = "results/q2_cpu_full_n1495.json"
FIELDS = [("abnormality", "Abnormality"),
          ("focal_epileptiform_activity", "Focal Epi"),
          ("generalized_epileptiform_activity", "Gen Epi"),
          ("focal_non_epileptiform_activity", "Focal Non-epi"),
          ("generalized_non_epileptiform_activity", "Gen Non-epi")]
INK, INK2, GRID = "#141821", "#566072", "#e9edf3"
C_OVER, C_UNDER = "#2a78d6", "#e34948"   # over-call (alarm) / under-call (miss)
pres = lambda v: v >= 3

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.edgecolor": "#c8cfd9", "figure.dpi": 150})


def main():
    cases = json.loads(Path(SRC).read_text())["cases"]
    fp, fn = [], []
    for k, _ in FIELDS:
        a = b = 0
        for x in cases:
            m, ld = pres(x["model"][k]["pred"]), pres(x["ld_labels"][k])
            if m and not ld: a += 1
            elif ld and not m: b += 1
        fp.append(a); fn.append(b)
    tot_fp, tot_fn = sum(fp), sum(fn)

    y = np.arange(len(FIELDS))[::-1]
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    ax.barh(y, fp, 0.6, color=C_OVER, zorder=3, label=f"Завищує загрозу — хибні тривоги ({tot_fp})")
    ax.barh(y, [-v for v in fn], 0.6, color=C_UNDER, zorder=3,
            label=f"Занижує загрозу — пропуски ({tot_fn})")
    for yi, a, b in zip(y, fp, fn):
        if a: ax.text(a + 1.5, yi, str(a), va="center", ha="left", color=C_OVER,
                      fontweight="bold", fontsize=10.5, fontfamily="monospace")
        if b: ax.text(-b - 1.5, yi, str(b), va="center", ha="right", color=C_UNDER,
                      fontweight="bold", fontsize=10.5, fontfamily="monospace")
    ax.axvline(0, color="#8b94a4", lw=1.5, zorder=4)
    ax.set_yticks(y); ax.set_yticklabels([lab for _, lab in FIELDS], fontsize=11, color=INK2)
    ax.set_xlim(-max(fn) - 20, max(fp) + 20)
    ax.set_xticks([-40, -20, 0, 20, 40, 60, 80])
    ax.set_xticklabels(["40", "20", "0", "20", "40", "60", "80"])
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.tick_params(axis="x", colors=INK2, labelsize=9)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c8cfd9")
    ax.tick_params(length=0); ax.set_axisbelow(True)
    ax.set_title("Модель завищує чи занижує загрозу?",
                 fontsize=13.5, color=INK, fontweight="bold", loc="left", pad=26)
    ax.text(0, 1.05, f"Ліворуч — пропуски (занижує), праворуч — хибні тривоги (завищує).  "
            f"Загалом {tot_fp} : {tot_fn} (≈{tot_fp/tot_fn:.1f}×) — радше перестраховується",
            transform=ax.transAxes, fontsize=10, color=INK2, va="bottom", ha="left")
    ax.legend(frameon=False, fontsize=9.5, loc="upper center",
              bbox_to_anchor=(0.5, -0.13), ncol=2, handlelength=1.1)
    fig.tight_layout()
    out = Path("reports/figures/eeg_over_under.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print("saved", out, "FP=", fp, "FN=", fn)


if __name__ == "__main__":
    Path("reports/figures").mkdir(exist_ok=True)
    main()
