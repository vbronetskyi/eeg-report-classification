#!/usr/bin/env python3
"""Reproduce the paper's Table III / Fig 2-3 metrics for our model run.

For each of the five diagnostic categories, computes Core Agreement
(binary presence, score>=3) accuracy/precision/recall/F1/specificity plus
Certainty-Adjusted (exact 4-point) accuracy, and Cohen's kappa in both
regimes. Reports the model against LD (=Reference Annotator, the paper's
ground truth) and, for context, the human SA↔LD ceiling from the same
reports — so our model column sits directly beside the paper's Mistral-7B
and Second-Annotator columns.

Usage: python -m analysis.table3_metrics results/<full_run>.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FIELDS = [
    ("abnormality", "Abnormality"),
    ("focal_epileptiform_activity", "Focal Epi"),
    ("generalized_epileptiform_activity", "Gen Epi"),
    ("focal_non_epileptiform_activity", "Focal Non-epi"),
    ("generalized_non_epileptiform_activity", "Gen Non-epi"),
]


def present(v: int) -> bool:
    return v >= 3


def kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def core_metrics(truth_bin, pred_bin):
    tp = sum(1 for t, p in zip(truth_bin, pred_bin) if t and p)
    fp = sum(1 for t, p in zip(truth_bin, pred_bin) if not t and p)
    fn = sum(1 for t, p in zip(truth_bin, pred_bin) if t and not p)
    tn = sum(1 for t, p in zip(truth_bin, pred_bin) if not t and not p)
    n = tp + fp + fn + tn
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    return acc, prec, rec, f1, spec


def main() -> None:
    data = json.loads(Path(sys.argv[1]).read_text())
    cases = data["cases"]
    n = len(cases)
    print(f"Model run: {Path(sys.argv[1]).name}   n={n} reports")
    print("Reference = LD (RA). Model = MedGemma-27B Q2_K. "
          "SA↔LD = human ceiling.\n")

    hdr = (f"{'Category':15s} {'Metric':14s} "
           f"{'Model↔LD':>10s} {'SA↔LD':>8s}")
    for internal, label in FIELDS:
        ld = [c["ld_labels"][internal] for c in cases]
        sg = [c["sg_labels"][internal] for c in cases]
        md = [c["model"][internal]["pred"] for c in cases]

        ld_b = [present(v) for v in ld]
        sg_b = [present(v) for v in sg]
        md_b = [present(v) for v in md]

        m = core_metrics(ld_b, md_b)     # model vs LD
        h = core_metrics(ld_b, sg_b)     # SA vs LD (human)
        cert_m = sum(1 for a, b in zip(ld, md) if a == b) / n
        cert_h = sum(1 for a, b in zip(ld, sg) if a == b) / n
        k_core_m = kappa([int(x) for x in ld_b], [int(x) for x in md_b])
        k_core_h = kappa([int(x) for x in ld_b], [int(x) for x in sg_b])
        k_cert_m = kappa(ld, md)
        k_cert_h = kappa(ld, sg)

        print("-" * len(hdr))
        print(f"{label:15s}")
        print(hdr)
        names = ["Core Accuracy", "Core Precision", "Core Recall",
                 "Core F1", "Core Specificity"]
        for name, vm, vh in zip(names, m, h):
            print(f"{'':15s} {name:14s} {vm:10.2f} {vh:8.2f}")
        print(f"{'':15s} {'Cert Accuracy':14s} {cert_m:10.2f} {cert_h:8.2f}")
        print(f"{'':15s} {'Kappa core':14s} {k_core_m:10.2f} {k_core_h:8.2f}")
        print(f"{'':15s} {'Kappa cert':14s} {k_cert_m:10.2f} {k_cert_h:8.2f}")

    # compact core-F1 summary line (the paper's headline numbers)
    print("\n" + "=" * 60)
    print("CORE F1 SUMMARY  (paper Mistral-7B Zoe in brackets)")
    paper_mistral_f1 = {"abnormality": 0.96, "focal_epileptiform_activity": 0.85,
                        "generalized_epileptiform_activity": 0.71,
                        "focal_non_epileptiform_activity": 0.76,
                        "generalized_non_epileptiform_activity": 0.78}
    for internal, label in FIELDS:
        ld_b = [present(c["ld_labels"][internal]) for c in cases]
        md_b = [present(c["model"][internal]["pred"]) for c in cases]
        _, _, _, f1, _ = core_metrics(ld_b, md_b)
        print(f"  {label:15s} ours={f1:.2f}   "
              f"[paper Mistral-7B={paper_mistral_f1[internal]:.2f}]")


if __name__ == "__main__":
    main()
