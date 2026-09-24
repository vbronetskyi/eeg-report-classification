#!/usr/bin/env python3
"""Compare our MedGemma burst_suppression labels on the Harvard reports against Harvard's own
`bs` column, the same three ways as analysis.slowing_vs_harvard (vs all marked / vs report-text
only / recall on expert-verified present).

Only burst_suppression has a Harvard counterpart; discontinuous_background and
suppressed_background have no HEEDB column, so they are labels-only (see analysis.background_dist).

Run:  python -m analysis.background_vs_harvard   ->  results/harvard/burst_vs_harvard.json
"""
from __future__ import annotations

import glob
import json
import sqlite3
from pathlib import Path

DB = "/project/6019337/databases/eeg_harvard/HarvardEEG.db"
COHORTS = ["MGH", "BWH", "BCH"]
FIELD_COL = {"burst_suppression": "bs"}
ORDER = {"report": 3, "annotation_only": 2, "verified_only": 1, "absent": 0}
OUT = Path("results/harvard"); OUT.mkdir(parents=True, exist_ok=True)


def _cat(val):
    s = (val or "").lower()
    if not s:
        return "absent"
    if "report" in s:
        return "report"
    if "annotation" in s:
        return "annotation_only"
    return "verified_only"


def load_harvard(cohort, col):
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
    for f in glob.glob(f"results/background_harvard/{cohort}/{field}/labels_*.json"):
        for c in json.load(open(f)).get("cases", []):
            if c.get("background"):
                d[c["hashed_id"]] = c["background"]["status"]
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
                print(f"{cohort}: no overlap")
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
    (OUT / "burst_vs_harvard.json").write_text(json.dumps(out, indent=2))
    print(f"\nsaved {OUT}/burst_vs_harvard.json")


if __name__ == "__main__":
    main()
