#!/usr/bin/env python3
"""Integrity + accuracy audit of a benchmark result JSON.

Checks each model output for validity and internal consistency, then
scores predictions against both annotators (LD = reference, SG = second)
under core (binary presence, score>=3) and exact (4-point) agreement.
LD-vs-SG is reported as the human agreement ceiling.

Usage: python -m analysis.check_outputs results/<file>.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FIELDS = [
    "abnormality",
    "focal_epileptiform_activity",
    "generalized_epileptiform_activity",
    "focal_non_epileptiform_activity",
    "generalized_non_epileptiform_activity",
]
SHORT = {
    "abnormality": "abnormality",
    "focal_epileptiform_activity": "focal_epi",
    "generalized_epileptiform_activity": "gen_epi",
    "focal_non_epileptiform_activity": "focal_non",
    "generalized_non_epileptiform_activity": "gen_non",
}


def present(v: int) -> bool:
    return v >= 3


def main() -> None:
    data = json.loads(Path(sys.argv[1]).read_text())
    cases = data["cases"]
    n = len(cases)
    print(f"=== INTEGRITY ({n} cases) ===")

    problems = []
    inconsistent = []
    for c in cases:
        cid = c["case_id"]
        m = c["model"]
        # every field present, pred in 1..4, probs sane
        for f in FIELDS:
            r = m.get(f)
            if r is None:
                problems.append(f"{cid}: missing field {f}")
                continue
            if r["pred"] not in (1, 2, 3, 4):
                problems.append(f"{cid}: {f} pred={r['pred']} out of range")
            ps = r["p1"] + r["p2"] + r["p3"] + r["p4"]
            if abs(ps - 1.0) > 1e-3:
                problems.append(f"{cid}: {f} p-sum={ps:.4f} != 1")
            if abs((r["p3"] + r["p4"]) - r["p_presence"]) > 1e-6:
                problems.append(f"{cid}: {f} p_presence mismatch")
        if c.get("attempts_used", 1) != 1:
            problems.append(f"{cid}: attempts_used={c['attempts_used']}")
        # internal consistency: overall>=3 iff any subtype>=3
        overall_pos = present(m["abnormality"]["pred"])
        sub_pos = any(present(m[f]["pred"]) for f in FIELDS[1:])
        if overall_pos != sub_pos:
            inconsistent.append(
                (cid, m["abnormality"]["pred"],
                 [m[f]["pred"] for f in FIELDS[1:]])
            )

    print(f"skipped/missing cases : {50 - n if n < 50 else 0}")
    print(f"validity problems     : {len(problems)}")
    for p in problems[:20]:
        print("   ", p)
    print(f"internal inconsistencies (overall vs subtypes): {len(inconsistent)}")
    for cid, ov, subs in inconsistent:
        print(f"    {cid}: overall={ov} subtypes={subs}")

    # accuracy
    print()
    print("=== AGREEMENT (core = binary >=3 ; exact = 4-point) ===")
    hdr = (f"{'field':11s} | {'model-vs-LD':>18s} | {'model-vs-SG':>18s} | "
           f"{'LD-vs-SG (human)':>18s}")
    print(hdr)
    print("-" * len(hdr))

    def rate(cases, a, b, kind, f):
        hit = 0
        for c in cases:
            va = c[a][f] if a != "model" else c["model"][f]["pred"]
            vb = c[b][f] if b != "model" else c["model"][f]["pred"]
            if kind == "core":
                hit += present(va) == present(vb)
            else:
                hit += va == vb
        return hit

    for f in FIELDS:
        row = f"{SHORT[f]:11s} |"
        for a, b in (("model", "ld_labels"), ("model", "sg_labels"),
                     ("ld_labels", "sg_labels")):
            core = rate(cases, a, b, "core", f)
            exact = rate(cases, a, b, "exact", f)
            row += f" core {core:2d}/{n} exact {exact:2d}/{n} |"
        print(row)

    # confusion for abnormality (model vs LD)
    print()
    print("=== abnormality confusion (model vs LD, binary) ===")
    tp = fp = fn = tn = 0
    for c in cases:
        mp = present(c["model"]["abnormality"]["pred"])
        lp = present(c["ld_labels"]["abnormality"])
        tp += mp and lp
        fp += mp and not lp
        fn += (not mp) and lp
        tn += (not mp) and (not lp)
    print(f"    TP={tp} FP={fp} FN={fn} TN={tn}")
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    print(f"    precision={prec:.2f} recall={rec:.2f} F1={f1:.2f}")

    # disagreements where model differs from LD on binary (the interesting ones)
    print()
    print("=== cases where model disagrees with LD on presence ===")
    for c in cases:
        diffs = [SHORT[f] for f in FIELDS
                 if present(c["model"][f]["pred"]) != present(c["ld_labels"][f])]
        if diffs:
            sg_diffs = [SHORT[f] for f in FIELDS
                        if present(c["model"][f]["pred"]) != present(c["sg_labels"][f])]
            agrees_sg = set(diffs) - set(sg_diffs)
            note = f" (but agrees with SG on: {sorted(agrees_sg)})" if agrees_sg else ""
            print(f"    {c['case_id']}: differs from LD on {diffs}{note}")


if __name__ == "__main__":
    main()
