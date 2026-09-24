#!/usr/bin/env python3
"""What our MedGemma focal / generalized slowing labels look like on the Fraser Health set
(45,545 reports). FHA has no slowing ground truth, so this just characterises the labels:

  * the three-way distribution of each field
  * how focal and generalized slowing co-occur
  * how the two new, specific fields sit inside the old bundled non-epileptiform categories
    from the five-category release (Focal Non-epi / Gen Non-epi), which lump slowing together
    with attenuation, asymmetry, disorganization, etc.

Writes results/slowing/fha_summary.json.  Run:  python -m analysis.slowing_fha
"""
from __future__ import annotations

import collections
import glob
import json
import sqlite3
from pathlib import Path

REL = ("/project/6019337/databases/eeg_fha/release_001/reports/"
       "eeg_reports_release_001_medgemma_Q4KS_public_250825.db")
STATUSES = ["present", "explicitly_absent", "not_mentioned"]
OUT = Path("results/slowing"); OUT.mkdir(parents=True, exist_ok=True)


def load_slow(field):
    d = {}
    for f in glob.glob(f"results/slowing/{field}/labels_*.json"):
        for c in json.load(open(f)).get("cases", []):
            if c.get("slowing"):
                d[c["hashed_id"]] = c["slowing"]["status"]
    return d


def load_nonepi():
    """Hashed_ReportURN -> (focal_non_epi_present, gen_non_epi_present); present = level >= 3."""
    con = sqlite3.connect(f"file:{REL}?mode=ro", uri=True)
    d = {r[0]: (r[1] >= 3, r[2] >= 3) for r in con.execute(
        'SELECT "Hashed_ReportURN", "Focal Non-epi", "Gen Non-epi" FROM classifications')}
    con.close()
    return d


def main():
    foc, gen = load_slow("focal"), load_slow("generalized")
    nonepi = load_nonepi()
    out = {"n_focal": len(foc), "n_generalized": len(gen)}

    for name, d in [("focal", foc), ("generalized", gen)]:
        c = collections.Counter(d.values()); n = sum(c.values())
        out[f"dist_{name}"] = {s: [c[s], round(100 * c[s] / n, 1)] for s in STATUSES}
        print(f"{name}: " + "  ".join(f"{s}={c[s]} ({100*c[s]/n:.1f}%)" for s in STATUSES))

    ids = sorted(set(foc) & set(gen))
    co = collections.Counter((foc[i] == "present", gen[i] == "present") for i in ids)
    out["cooccurrence"] = {
        "both_present": co[(True, True)], "focal_only": co[(True, False)],
        "generalized_only": co[(False, True)], "neither": co[(False, False)], "n": len(ids)}
    print("\nco-occurrence (present):", out["cooccurrence"])

    # new specific field vs old bundled non-epileptiform category
    out["vs_nonepi"] = {}
    for name, d, idx in [("focal", foc, 0), ("generalized", gen, 1)]:
        keys = [i for i in d if i in nonepi]
        sp = sum(d[i] == "present" for i in keys)
        np_ = sum(nonepi[i][idx] for i in keys)
        both = sum(d[i] == "present" and nonepi[i][idx] for i in keys)
        out["vs_nonepi"][name] = {
            "matched": len(keys), "slowing_present": sp, "nonepi_present": np_,
            "both_present": both,
            "slowing_present_within_nonepi": round(100 * both / np_, 1) if np_ else None,
            "nonepi_present_when_slowing": round(100 * both / sp, 1) if sp else None}
        print(f"vs non-epi ({name}): slowing_present={sp} nonepi_present={np_} both={both}")

    (OUT / "fha_summary.json").write_text(json.dumps(out, indent=2))
    print(f"\nsaved {OUT}/fha_summary.json")


if __name__ == "__main__":
    main()
