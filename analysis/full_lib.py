#!/usr/bin/env python3
"""Shared helpers + result registry for the full 2x2x2 experiment
(prompt v1/v2 x dataset zoe/maria x quant Q2_K/Q4_K_S)."""
from __future__ import annotations

import json
from pathlib import Path

FIELDS = [
    ("abnormality", "Abnormality"),
    ("focal_epileptiform_activity", "Focal Epi"),
    ("generalized_epileptiform_activity", "Gen Epi"),
    ("focal_non_epileptiform_activity", "Focal Non-epi"),
    ("generalized_non_epileptiform_activity", "Gen Non-epi"),
]
KEYS = [k for k, _ in FIELDS]
LABELS = [lab for _, lab in FIELDS]

# result JSONs, by (dataset, prompt, quant)
RESULTS = {
    ("zoe", "v1", "Q2"): "q2_cpu_full_n1495",
    ("zoe", "v1", "Q4"): "cpu_q4_k_s_full_n1495",
    ("zoe", "v2", "Q2"): "zoe_v2_cpu_q2_k_full_n1495",
    ("zoe", "v2", "Q4"): "zoe_v2_cpu_q4_k_s_full_n1495",
    ("maria", "v1", "Q2"): "maria_cpu_q2_k_full_n499",
    ("maria", "v1", "Q4"): "maria_cpu_q4_k_s_full_n499",
    ("maria", "v2", "Q2"): "maria_v2_cpu_q2_k_full_n499",
    ("maria", "v2", "Q4"): "maria_v2_cpu_q4_k_s_full_n499",
    ("zoe", "v3", "Q2"): "zoe_v3_cpu_q2_k_full_n1495",
    ("zoe", "v3", "Q4"): "zoe_v3_cpu_q4_k_s_full_n1495",
    ("zoe", "v4", "Q2"): "zoe_v4_cpu_q2_k_full_n1495",
    ("zoe", "v4", "Q4"): "zoe_v4_cpu_q4_k_s_full_n1495",
    ("maria", "v3", "Q2"): "maria_v3_cpu_q2_k_full_n499",
    ("maria", "v3", "Q4"): "maria_v3_cpu_q4_k_s_full_n499",
    ("maria", "v4", "Q2"): "maria_v4_cpu_q2_k_full_n499",
    ("maria", "v4", "Q4"): "maria_v4_cpu_q4_k_s_full_n499",
    # v5 = v3 + focal-vs-generalized slowing discriminator
    ("zoe", "v5", "Q2"): "zoe_v5_cpu_q2_k_full_n1495",
    ("maria", "v5", "Q2"): "maria_v5_cpu_q2_k_full_n499",
    ("zoe", "v5", "Q4"): "zoe_v5_cpu_q4_k_s_full_n1495",
    ("maria", "v5", "Q4"): "maria_v5_cpu_q4_k_s_full_n499",
    # v6 = v3 + prompt-only consistency reconciliation
    ("zoe", "v6", "Q2"): "zoe_v6_cpu_q2_k_full_n1495",
    ("maria", "v6", "Q2"): "maria_v6_cpu_q2_k_full_n499",
    ("zoe", "v6", "Q4"): "zoe_v6_cpu_q4_k_s_full_n1495",
    ("maria", "v6", "Q4"): "maria_v6_cpu_q4_k_s_full_n499",
    # v3g = v3 prompt + GBNF-enforced consistency (ENFORCE_CONSISTENCY=1)
    ("zoe", "v3g", "Q2"): "zoe_v3g_cpu_q2_k_full_n1495",
    ("maria", "v3g", "Q2"): "maria_v3g_cpu_q2_k_full_n499",
    ("zoe", "v3g", "Q4"): "zoe_v3g_cpu_q4_k_s_full_n1495",
    ("maria", "v3g", "Q4"): "maria_v3g_cpu_q4_k_s_full_n499",
    # v5g = v5 prompt (slowing discriminator) + GBNF-enforced consistency
    ("zoe", "v5g", "Q2"): "zoe_v5g_cpu_q2_k_full_n1495",
    ("maria", "v5g", "Q2"): "maria_v5g_cpu_q2_k_full_n499",
    ("zoe", "v5g", "Q4"): "zoe_v5g_cpu_q4_k_s_full_n1495",
    ("maria", "v5g", "Q4"): "maria_v5g_cpu_q4_k_s_full_n499",
    # v7g = v5 + body-aware abnormality, grammar-enforced (targets the abnormality gap)
    ("zoe", "v7g", "Q2"): "zoe_v7g_cpu_q2_k_full_n1495",
    ("maria", "v7g", "Q2"): "maria_v7g_cpu_q2_k_full_n499",
    ("zoe", "v7g", "Q4"): "zoe_v7g_cpu_q4_k_s_full_n1495",
    ("maria", "v7g", "Q4"): "maria_v7g_cpu_q4_k_s_full_n499",
    # v8g = simplified lean prompt, grammar-enforced (robustness / less over-fit)
    ("zoe", "v8g", "Q2"): "zoe_v8g_cpu_q2_k_full_n1495",
    ("maria", "v8g", "Q2"): "maria_v8g_cpu_q2_k_full_n499",
    ("zoe", "v8g", "Q4"): "zoe_v8g_cpu_q4_k_s_full_n1495",
    ("maria", "v8g", "Q4"): "maria_v8g_cpu_q4_k_s_full_n499",
    # v9g = reasoning-first ("let the model decide"), grammar-enforced + REASONING
    ("zoe", "v9g", "Q2"): "zoe_v9g_cpu_q2_k_full_n1495",
    ("maria", "v9g", "Q2"): "maria_v9g_cpu_q2_k_full_n499",
    ("zoe", "v9g", "Q4"): "zoe_v9g_cpu_q4_k_s_full_n1495",
    ("maria", "v9g", "Q4"): "maria_v9g_cpu_q4_k_s_full_n499",
    # v10g = v5 + evidence-calibration (precision), grammar-enforced
    ("zoe", "v10g", "Q2"): "zoe_v10g_cpu_q2_k_full_n1495",
    ("maria", "v10g", "Q2"): "maria_v10g_cpu_q2_k_full_n499",
    ("zoe", "v10g", "Q4"): "zoe_v10g_cpu_q4_k_s_full_n1495",
    ("maria", "v10g", "Q4"): "maria_v10g_cpu_q4_k_s_full_n499",
}

# Paper Table III (Zoe / Maria) core F1 — published constants.
PAPER_MISTRAL = {
    "zoe": [0.96, 0.85, 0.71, 0.76, 0.78],
    "maria": [0.90, 0.81, 0.84, 0.74, 0.54],
}

# palette
INK, INK2, GRID = "#141821", "#566072", "#e9edf3"
BLUE, ORANGE, AQUA, VIOLET, RED, GREEN = (
    "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7", "#e34948", "#008300")

_ROOT = Path(__file__).resolve().parent.parent


def load(dataset, prompt, quant):
    p = _ROOT / "results" / f"{RESULTS[(dataset, prompt, quant)]}.json"
    return json.loads(p.read_text())["cases"]


def present(v):
    return v >= 3


def f1(cases, k, source="model"):
    tp = fp = fn = 0
    for x in cases:
        m = present(x["model"][k]["pred"]) if source == "model" \
            else present(x[f"{source}_labels"][k])
        ld = present(x["ld_labels"][k])
        tp += m and ld; fp += m and not ld; fn += (not m) and ld
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def f1_all(cases, source="model"):
    return [f1(cases, k, source) for k in KEYS]


def fp_fn(cases, k):
    fp = fn = 0
    for x in cases:
        m = present(x["model"][k]["pred"]); ld = present(x["ld_labels"][k])
        fp += m and not ld; fn += (not m) and ld
    return fp, fn


def apply_style():
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.edgecolor": "#c8cfd9", "figure.dpi": 150})


def bare(ax, keep_left=True):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if not keep_left:
        ax.spines["left"].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
