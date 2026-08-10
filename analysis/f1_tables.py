#!/usr/bin/env python3
"""F1 tables for reports/all_prompts.md — two strictness levels, both as F1:

  CORE F1      — present/absent (1-2 vs 3-4); "3 vs 4" counts as correct.
  CERTAINTY F1 — the exact 1-4 level must match; "3 vs 4" is a miss.

F1 = 2*TP / (2*TP + FP + FN); it ignores the easy true-negatives, so it stays honest on
the rare classes (unlike plain accuracy). Pooled over Zoe+Maria (n=1994).

Run:  python -m analysis.f1_tables
"""
from __future__ import annotations

from analysis.full_lib import KEYS, LABELS, load
from analysis.plot_dumbbells import our_pairs, mistral_pairs, core_and_cert


def human_pairs():
    out = []
    for ds in ("zoe", "maria"):
        for c in load(ds, "v1", "Q2"):
            out.append((c["sg_labels"], c["ld_labels"]))
    return out


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
    ("Human (SG)", human_pairs),
]


def _tables():
    core_rows, cert_rows = {}, {}
    for name, get in ROWS:
        core, cert = core_and_cert(get())
        core_rows[name] = core
        cert_rows[name] = cert
    return core_rows, cert_rows


def _md(title, rows):
    head = "| Model | " + " | ".join(LABELS) + " |"
    sep = "|" + "---|" * (len(LABELS) + 1)
    out = [f"### {title}", "", head, sep]
    for name, vals in rows.items():
        out.append(f"| {name} | " + " | ".join(f"{v * 100:.1f}" for v in vals) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    core_rows, cert_rows = _tables()
    print(_md("Core F1 (present/absent)", core_rows))
    print()
    print(_md("Certainty F1 (exact 1-4 level)", cert_rows))
