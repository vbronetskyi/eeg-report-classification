#!/usr/bin/env python3
"""Compare our MedGemma focal / generalized slowing labels on the Harvard reports against
Harvard's own annotations, three ways:

  1. against everything Harvard marked (any non-null value)                -> agree_all / kappa_all
  2. against only what Harvard sourced from the report TEXT (provenance    -> agree_report / kappa_report
     contains "report") — the fair text-to-text comparison, since we read only the text
  3. our recall on the reports an expert VERIFIED as present (provenance    -> our_recall_on_verified
     contains "verified") — the closest thing to ground truth here

Harvard stores each finding as a provenance string in its `*_EEG_with_reports` table
("report" / "annotation" / "report annotation" / "verified" / ... / NULL). NULL means the
finding is not marked; a value means it is, and the words say where it came from. Their schema
is binary (present vs not), ours is three-way (present / explicitly_absent / not_mentioned); for
every comparison we collapse ours to present vs not-present.

Caveats on (3): the verified set is Harvard's own present labels that an expert confirmed, so it
only covers positives (no verified negatives -> recall only, not precision), and BCH carries no
verified labels.

    our field            Harvard column
    focal_slowing    <-> "foc slowing"
    generalized_slowing <-> "gen slowing"

Run (after the Harvard slowing runs finish):  python -m analysis.slowing_vs_harvard
"""
from __future__ import annotations

import glob
import json
import sqlite3
from pathlib import Path

DB = "/project/6019337/databases/eeg_harvard/HarvardEEG.db"
COHORTS = ["MGH", "BWH", "BCH"]
FIELD_COL = {"focal": "foc slowing", "generalized": "gen slowing"}
ORDER = {"report": 3, "annotation_only": 2, "verified_only": 1, "absent": 0}
OUT = Path("results/harvard"); OUT.mkdir(parents=True, exist_ok=True)


def _cat(val):
    """Where Harvard sourced the finding, from its provenance string."""
    s = (val or "").lower()
    if not s:
        return "absent"
    if "report" in s:
        return "report"            # in the report text — the source we also read
    if "annotation" in s:
        return "annotation_only"   # structured annotation — may not be in the text
    return "verified_only"         # expert-verified, channel unspecified


def load_harvard(cohort, col):
    """report_id -> provenance category (absent ones included), and the set of report_ids an
    expert verified. Keeps the highest-priority provenance across a report's session rows."""
    con = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)
    cat, ver = {}, set()
    for rid, val in con.execute(
            f'SELECT "DeidentifiedName(Reports)", "{col}" FROM "{cohort}_EEG_with_reports"'):
        if not rid:
            continue
        c = _cat(val)
        if rid not in cat or ORDER[c] > ORDER[cat[rid]]:
            cat[rid] = c
        if "verified" in (val or "").lower():
            ver.add(rid)
    con.close()
    return cat, ver


def load_ours(cohort, field):
    d = {}
    for f in glob.glob(f"results/slowing_harvard/{cohort}/{field}/labels_*.json"):
        for c in json.load(open(f)).get("cases", []):
            if c.get("slowing"):
                d[c["hashed_id"]] = c["slowing"]["status"]
    return d


def kappa(a, b):
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def agree(a, b):
    return sum(x == y for x, y in zip(a, b)) / len(a)


def main():
    out = {}
    for field, col in FIELD_COL.items():
        out[field] = {}
        print(f"\n================  {field}  vs Harvard \"{col}\"  ================")
        for cohort in COHORTS:
            cat, ver = load_harvard(cohort, col)
            ours = load_ours(cohort, field)
            ids = sorted(set(ours) & set(cat))
            if not ids:
                print(f"{cohort}: no overlap yet — run pending?")
                continue
            op = [ours[i] == "present" for i in ids]
            all_ = [cat[i] != "absent" for i in ids]
            rep = [cat[i] == "report" for i in ids]
            vlab = [i for i in ver if i in ours]
            rec = sum(ours[i] == "present" for i in vlab) / len(vlab) if vlab else None
            rec = round(rec, 4) if rec is not None else None
            out[field][cohort] = dict(
                n=len(ids), ours_present=sum(op),
                harv_present_all=sum(all_), harv_present_report=sum(rep),
                agree_all=round(agree(op, all_), 4), kappa_all=round(kappa(op, all_), 4),
                agree_report=round(agree(op, rep), 4), kappa_report=round(kappa(op, rep), 4),
                verified_present_labeled=len(vlab), our_recall_on_verified=rec)
            d = out[field][cohort]
            print(f"{cohort}: n={len(ids):>6} | vs all: agree {d['agree_all']:.1%} k {d['kappa_all']:.2f}"
                  f" | vs report-text: agree {d['agree_report']:.1%} k {d['kappa_report']:.2f}"
                  f" | recall on {len(vlab)} verified: "
                  f"{f'{rec:.1%}' if rec is not None else 'n/a'}")
    (OUT / "slowing_gold.json").write_text(json.dumps(out, indent=2))
    print(f"\nsaved {OUT}/slowing_gold.json")


if __name__ == "__main__":
    main()
