#!/usr/bin/env python3
"""Check the schema's hierarchical consistency rule in each rater's labels.

Rule (paper II-B, prompt rules 3/5/6/7), on the binarised scale (present = score>=3):
    overall "abnormal"  <=>  at least one of the four subtypes is "present"

Two violation directions:
  A) abnormal overall (abnormality>=3) but NO subtype present  ("abnormal, no reason")
  B) normal overall   (abnormality<=2) but SOME subtype present ("normal, yet a finding")

Reports counts + privacy-safe case_ids for LD (reference), SG (2nd annotator),
and the model, over the full run.

Usage: python -m analysis.check_consistency [results/<run>.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SUBTYPES = [
    "focal_epileptiform_activity",
    "generalized_epileptiform_activity",
    "focal_non_epileptiform_activity",
    "generalized_non_epileptiform_activity",
]


def present(v: int) -> bool:
    return v >= 3


def labels_of(case, rater):
    if rater == "model":
        m = case["model"]
        return ({s: m[s]["pred"] for s in SUBTYPES},
                m["abnormality"]["pred"])
    src = case[f"{rater}_labels"]
    return ({s: src[s] for s in SUBTYPES}, src["abnormality"])


def audit(cases, rater):
    viol_a, viol_b = [], []
    for c in cases:
        subs, overall = labels_of(c, rater)
        any_sub = any(present(v) for v in subs.values())
        if present(overall) and not any_sub:
            viol_a.append(c["case_id"])
        elif not present(overall) and any_sub:
            viol_b.append(c["case_id"])
    return viol_a, viol_b


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "results/q2_cpu_full_n1495.json"
    cases = json.loads(Path(src).read_text())["cases"]
    n = len(cases)
    print(f"n={n} reports   ·   rule: abnormal(overall) <=> some subtype present "
          f"(score>=3)\n")

    for rater, name in [("ld", "LD  (Reference Annotator)"),
                        ("sg", "SG  (Second Annotator)"),
                        ("model", "Model (MedGemma Q2_K)")]:
        a, b = audit(cases, rater)
        tot = len(a) + len(b)
        print(f"{name}")
        print(f"   total violations : {tot}/{n}  ({100*tot/n:.1f}%)")
        print(f"   A) abnormal but no subtype present : {len(a)}"
              + (f"   e.g. {a[:8]}" if a else ""))
        print(f"   B) normal but a subtype present    : {len(b)}"
              + (f"   e.g. {b[:8]}" if b else ""))
        print()

    # do model violations coincide with LD violations? (i.e. model copied a
    # genuinely inconsistent reference, vs the model inventing inconsistency)
    la, lb = audit(cases, "ld")
    ma, mb = audit(cases, "model")
    ld_set, md_set = set(la) | set(lb), set(ma) | set(mb)
    print("Overlap model↔LD violations:",
          f"model={len(md_set)}, of which also inconsistent in LD={len(md_set & ld_set)}\n")

    # Did the model GUESS RIGHT in its inconsistent cases, or was it erring?
    all_fields = ["abnormality"] + SUBTYPES
    inc = [c for c in cases if c["case_id"] in md_set]
    con = [c for c in cases if c["case_id"] not in md_set]

    def field_acc(group):
        hit = tot = 0
        for c in group:
            for k in all_fields:
                tot += 1
                hit += present(c["model"][k]["pred"]) == present(c["ld_labels"][k])
        return hit / tot

    def full_ok(group):
        return sum(all(present(c["model"][k]["pred"]) == present(c["ld_labels"][k])
                       for k in all_fields) for c in group)

    ab_ok = sum(present(c["model"]["abnormality"]["pred"]) ==
                present(c["ld_labels"]["abnormality"]) for c in inc)
    print("Inconsistent vs consistent model outputs (accuracy vs LD):")
    print(f"   per-field binary acc : inconsistent={field_acc(inc):.3f}   "
          f"consistent={field_acc(con):.3f}")
    print(f"   all-5-correct        : inconsistent={full_ok(inc)}/{len(inc)} "
          f"({100*full_ok(inc)/len(inc):.0f}%)   "
          f"consistent={full_ok(con)}/{len(con)} ({100*full_ok(con)/len(con):.0f}%)")
    print(f"   abnormality still correct in the inconsistent cases: "
          f"{ab_ok}/{len(inc)}")


if __name__ == "__main__":
    main()
