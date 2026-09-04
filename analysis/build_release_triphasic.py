#!/usr/bin/env python3
"""Package the MedGemma triphasic-wave labeling of the 45,545-report processed_reports
dataset into a release SQLite database, alongside the public five-category release and keyed
the same way (Hashed_ReportURN), so the two line up 1:1. Structured labels only — no text.

The labeling was run twice, with a short and a longer prompt (a robustness check; the two
agree on 99.97% of reports). We carry the longer prompt as the primary call and keep the short
prompt's call beside it as a cross-check.

Table:
  triphasic   Hashed_ReportURN
              status           present / explicitly_absent / not_mentioned   (long prompt)
              phenotype        typical / atypical / mixed / unspecified / not_applicable
              status_alt       the short prompt's status   (cross-check)
              phenotype_alt    the short prompt's phenotype
  about       key/value provenance

Run:
  python -m analysis.build_release_triphasic \
      --out results/release/eeg_reports_release_001_medgemma_Q4KS_triphasic_250825.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

PRIMARY = "long"   # the fuller prompt; the short prompt is carried as the cross-check
ALT = "short"


def load(variant):
    d = json.load(open(f"results/triphasic/clean/{variant}.json"))
    return {c["hashed_id"]: c["triphasic"] for c in d["cases"]}


def build(out: Path):
    prim, alt = load(PRIMARY), load(ALT)
    assert set(prim) == set(alt), "primary/alt prompt cover different reports"

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(out)
    con.execute('CREATE TABLE triphasic ('
                '"Hashed_ReportURN" TEXT PRIMARY KEY, '
                '"status" TEXT, "phenotype" TEXT, '
                '"status_alt" TEXT, "phenotype_alt" TEXT)')
    con.execute('CREATE TABLE about ("key" TEXT, "value" TEXT)')

    rows = []
    for hid in prim:
        p, a = prim[hid], alt[hid]
        rows.append([hid, p["status"], p["phenotype"], a["status"], a["phenotype"]])
    con.executemany("INSERT INTO triphasic VALUES (?,?,?,?,?)", rows)

    about = {
        "model": "MedGemma-27B (google/medgemma-27b-text-it)",
        "quantization": "Q4_K_S",
        "task": "triphasic waves — status and phenotype",
        "prompt": f"two prompts ({PRIMARY} = primary, {ALT} = cross-check); "
                  "grammar-constrained output",
        "faithfulness_guard": "present/explicitly_absent require the term 'triphasic' in the "
                              "report text; otherwise the call is reset to not_mentioned",
        "decoding": "temperature 0, grammar-constrained (deterministic)",
        "dataset": "processed_reports_240325 (45,545 reports)",
        "status_values": "present, explicitly_absent, not_mentioned",
        "phenotype_values": "typical, atypical, mixed, unspecified, not_applicable "
                            "(not_applicable when status is not 'present')",
        "prompt_agreement": "short vs long prompt agree on 99.97% of reports (Cohen's kappa 0.99)",
        "note": "labels only; report text is not included",
    }
    con.executemany("INSERT INTO about VALUES (?, ?)", list(about.items()))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM triphasic").fetchone()[0]
    present = con.execute("SELECT COUNT(*) FROM triphasic WHERE status='present'").fetchone()[0]
    con.close()
    print(f"wrote {out}  ({n} reports, {present} triphasic present)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path,
                   default=Path("results/release/"
                                "eeg_reports_release_001_medgemma_Q4KS_triphasic_250825.db"))
    build(p.parse_args().out)
