#!/usr/bin/env python3
"""Cross-annotator validation: do our prompt improvements hold against the SECOND
annotator (SG), not only the reference (LD)?

We tune against LD, so gains that appear only vs LD may be fitting LD's idiosyncrasies.
A real improvement should also raise agreement with SG. We also report the SG-vs-LD
human agreement as the signal ceiling — beyond it, higher LD-scores are not improvement.

Everything is read from results/*.json (each case carries model preds, ld_labels, and
sg_labels). Pooled over Zoe+Maria (n=1994).

Run:  python -m analysis.validate_vs_sg
"""
from __future__ import annotations

from analysis.full_lib import KEYS, load

pres = lambda v: v >= 3


def _f1(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def pooled(variant, quant):
    return load("zoe", variant, quant) + load("maria", variant, quant)


def score(cases, pred_of, truth_of):
    """Return (mean per-category F1, fully-correct count, n)."""
    f1s = []
    for k in KEYS:
        tp = fp = fn = 0
        for c in cases:
            m, g = pres(pred_of(c, k)), pres(truth_of(c, k))
            tp += m and g; fp += m and not g; fn += (not m) and g
        f1s.append(_f1(tp, fp, fn))
    full = sum(1 for c in cases
               if all(pres(pred_of(c, k)) == pres(truth_of(c, k)) for k in KEYS))
    return f1s, full, len(cases)


MODEL = lambda c, k: c["model"][k]["pred"]
LD = lambda c, k: c["ld_labels"][k]
SG = lambda c, k: c["sg_labels"][k]


def row(name, cases, pred, truth):
    f1s, full, n = score(cases, pred, truth)
    mean = sum(f1s) / len(f1s)
    return f"{name:22s} full={full:>4d} ({100*full/n:5.1f}%)  meanF1={100*mean:5.1f}%   " + \
        " ".join(f"{100*x:4.0f}" for x in f1s)


if __name__ == "__main__":
    variants = [("v1", "Q2"), ("v3", "Q2"), ("v5g", "Q2"), ("v5g", "Q4")]
    print("Per-category order:", " ".join(k.split("_")[0][:4] for k in KEYS))
    print("\n=== scored vs LD (reference — what we tuned on) ===")
    for v, q in variants:
        print(row(f"{v} {q}", pooled(v, q), MODEL, LD))
    print("\n=== scored vs SG (held-out second annotator) ===")
    for v, q in variants:
        print(row(f"{v} {q}", pooled(v, q), MODEL, SG))
    print("\n=== human ceiling: SG vs LD (annotator agreement) ===")
    # any variant's cases carry the same ld/sg labels; use v1 Q2
    base = pooled("v1", "Q2")
    print(row("SG vs LD", base, SG, LD))
