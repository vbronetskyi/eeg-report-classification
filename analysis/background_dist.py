#!/usr/bin/env python3
"""Distributions of our three background-pattern labels on FHA and on the Harvard cohorts
(labels only). Writes results/background/dist_summary.json.
Run: python -m analysis.background_dist
"""
from __future__ import annotations

import collections
import glob
import json
from pathlib import Path

FIELDS = ["discontinuous", "burst_suppression", "suppressed"]
STATUSES = ["present", "explicitly_absent", "not_mentioned"]
OUT = Path("results/background"); OUT.mkdir(parents=True, exist_ok=True)


def dist(pattern):
    c = collections.Counter()
    for f in glob.glob(pattern):
        try:
            for x in json.load(open(f)).get("cases", []):
                if x.get("background"):
                    c[x["background"]["status"]] += 1
        except Exception:
            pass
    n = sum(c.values())
    return {s: [c[s], round(100 * c[s] / n, 2) if n else 0] for s in STATUSES}, n


def main():
    out = {"FHA": {}, "Harvard": {}}
    for fld in FIELDS:
        d, n = dist(f"results/background/{fld}/labels_*.json")
        out["FHA"][fld] = {"n": n, **{s: d[s] for s in STATUSES}}
        print(f"FHA {fld:18} n={n:>6}  " + "  ".join(f"{s}={d[s][0]}({d[s][1]}%)" for s in STATUSES))
    for coh in ["MGH", "BWH", "BCH"]:
        out["Harvard"][coh] = {}
        for fld in FIELDS:
            d, n = dist(f"results/background_harvard/{coh}/{fld}/labels_*.json")
            out["Harvard"][coh][fld] = {"n": n, **{s: d[s] for s in STATUSES}}
            print(f"{coh} {fld:18} n={n:>6}  " + "  ".join(f"{s}={d[s][0]}({d[s][1]}%)" for s in STATUSES))
    (OUT / "dist_summary.json").write_text(json.dumps(out, indent=2))
    print(f"\nsaved {OUT}/dist_summary.json")


if __name__ == "__main__":
    main()
