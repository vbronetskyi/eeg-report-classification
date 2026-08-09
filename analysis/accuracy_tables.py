#!/usr/bin/env python3
"""Accuracy tables (% guessed correctly) for reports/all_prompts.md — two views:

  CORE  — did we get present/absent right (score 1-2 vs 3-4)?  = binary accuracy
  EXACT — did we get the exact 1-4 level right?                = exact-match accuracy

Unlike F1, this is plain accuracy (correct / all). Note: for rare classes accuracy is
optimistic (predicting "absent" is right most of the time), which is why the charts use
F1 — but this is the intuitive "% correct" view. Pooled over Zoe+Maria (n=1994).

Run:  python -m analysis.accuracy_tables
"""
from __future__ import annotations

from analysis.full_lib import KEYS, LABELS, load

pres = lambda v: v >= 3


def our_pairs(variant, quant):
    for ds in ("zoe", "maria"):
        for c in load(ds, variant, quant):
            yield {k: c["model"][k]["pred"] for k in KEYS}, c["ld_labels"]


def human_pairs():
    for ds in ("zoe", "maria"):
        for c in load(ds, "v1", "Q2"):
            yield c["sg_labels"], c["ld_labels"]


def mistral_pairs():
    from analysis.plot_dumbbells import mistral_pairs as mp
    return mp()


def core_acc(pairs, k):
    pairs = pairs if isinstance(pairs, list) else list(pairs)
    return 100 * sum(pres(p[k]) == pres(g[k]) for p, g in pairs) / len(pairs)


def exact_acc(pairs, k):
    pairs = pairs if isinstance(pairs, list) else list(pairs)
    return 100 * sum(p[k] == g[k] for p, g in pairs) / len(pairs)


def whole(pairs, mode):
    pairs = list(pairs)
    if mode == "core":
        ok = sum(all(pres(p[k]) == pres(g[k]) for k in KEYS) for p, g in pairs)
    else:
        ok = sum(all(p[k] == g[k] for k in KEYS) for p, g in pairs)
    return 100 * ok / len(pairs)


ROWS = [
    ("Mistral-7B", lambda: list(mistral_pairs())),
    ("v1", lambda: list(our_pairs("v1", "Q2"))),
    ("v3", lambda: list(our_pairs("v3", "Q2"))),
    ("v3g (Q4)", lambda: list(our_pairs("v3g", "Q4"))),
    ("v5g (Q2)", lambda: list(our_pairs("v5g", "Q2"))),
    ("v5g (Q4)", lambda: list(our_pairs("v5g", "Q4"))),
    ("v7g (Q4)", lambda: list(our_pairs("v7g", "Q4"))),
    ("v8g (Q4)", lambda: list(our_pairs("v8g", "Q4"))),
    ("v10g (Q4)", lambda: list(our_pairs("v10g", "Q4"))),
    ("Human (SG)", lambda: list(human_pairs())),
]


def table(kind):
    accf = core_acc if kind == "core" else exact_acc
    head = "| Model | " + " | ".join(LABELS) + " | All-5 |"
    sep = "|" + "---|" * (len(LABELS) + 2)
    lines = [head, sep]
    for name, get in ROWS:
        pairs = get()
        cells = " | ".join(f"{accf(pairs, k):.1f}" for k in KEYS)
        lines.append(f"| {name} | {cells} | {whole(pairs, kind):.1f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print("### CORE accuracy (% present/absent correct)\n")
    print(table("core"))
    print("\n### EXACT accuracy (% exact 1-4 level correct)\n")
    print(table("exact"))
