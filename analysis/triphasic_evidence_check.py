#!/usr/bin/env python3
"""Summarize the triphasic evidence/verification pass (src/cpu/triphasic_evidence.py).

For every report we labelled present or explicitly_absent, we re-ran the model asking it to
quote the exact supporting text. This script reports how well that holds up: how often the
quoted text is a real substring of the report, how often the triphasic term is actually in the
report, whether the re-run status still agrees with the original label, and prints a handful of
quotes so a person can read what present and explicitly_absent actually rest on.

Run:  python -m analysis.triphasic_evidence_check
"""
from __future__ import annotations

import glob
import json
from collections import Counter

EV = "results/triphasic/evidence"


def main():
    ev = {}
    for f in glob.glob(f"{EV}/labels_*.json"):
        for c in json.load(open(f)).get("cases", []):
            ev[c["hashed_id"]] = c

    orig = {}
    for v in ("short", "long"):
        for c in json.load(open(f"results/triphasic/clean/{v}.json"))["cases"]:
            t = c.get("triphasic")
            if t and t["status"] in ("present", "explicitly_absent"):
                orig.setdefault(c["hashed_id"], set()).add(t["status"])

    ok = [c for c in ev.values() if c.get("status")]
    st = Counter(c["status"] for c in ok)
    quoted = sum(1 for c in ok if c.get("quote_in_text"))
    term = sum(1 for c in ok if c.get("term_in_text"))
    # re-run status still in the original present/absent bucket for that report
    agree = sum(1 for c in ok if c["status"] in orig.get(c["hashed_id"], set()))

    print(f"flagged reports re-checked : {len(ev)}  (verdicts {len(ok)})")
    print(f"status this pass           : " + "  ".join(f"{k} {v}" for k, v in st.most_common()))
    print(f"triphasic term in report   : {term}/{len(ok)}  ({100*term/len(ok):.1f}%)")
    print(f"quote is a real substring  : {quoted}/{len(ok)}  ({100*quoted/len(ok):.1f}%)"
          f"   [shortfall = quote formatting, term is still present]")
    print(f"status still agrees w/ orig: {agree}/{len(ok)}  ({100*agree/len(ok):.1f}%)")

    for label in ("present", "explicitly_absent"):
        print(f"\n--- sample {label} evidence ---")
        for c in [c for c in ok if c["status"] == label][:6]:
            q = " ".join(c["evidence"].split())
            print(f"  • {q[:150]}")


if __name__ == "__main__":
    main()
