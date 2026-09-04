#!/usr/bin/env python3
"""Check the two slowing mappings we used in the MedGemma-vs-Bio-Medical-Llama report:

    our focal_non_epileptiform_activity   <-> Harvard "foc slowing"
    our generalized_non_epileptiform_activity <-> Harvard "gen slowing"

Our category definitions bundle slowing together with attenuation, asymmetry, dysfunction,
disorganization, encephalopathy, and excessive beta; the Harvard schema files each of those
under its own column (foc/gen slowing, breach, low voltage, diffuse Beta, bs, ...). So the two
sides may not be measuring the same thing. We test this on the reports where the two disagree:
when WE call the finding present but Harvard's slowing column is absent, does the report text
actually talk about slowing, or about the other (non-slowing) non-epileptiform findings our
category also covers? Reads report text from the HEEDB zips via the cohort indexes.

Run:  python -m analysis.mapping_check
"""
from __future__ import annotations

import glob
import json
import re
import sqlite3
import zipfile
from pathlib import Path

DB = "/project/6019337/databases/eeg_harvard/HarvardEEG.db"
COHORTS = ["MGH", "BWH", "BCH"]
SAMPLE = 400            # reports sampled per disagreement bucket per cohort (deterministic head)

SLOW = re.compile(r"slow", re.I)
OTHER_FOCAL = re.compile(r"attenuat|asymmetr|breach|dysfunction|disorganiz|suppress|focal.{0,15}abnormal", re.I)
OTHER_GEN = re.compile(r"attenuat|disorganiz|encephalopath|excess.{0,10}beta|suppress|low volt", re.I)

pres = lambda v: v >= 3


def load_ours():
    d = {}
    for f in glob.glob("results/harvard/labels/*/labels_*.json"):
        for c in json.load(open(f)).get("cases", []):
            if c.get("model"):
                d[c["report_id"]] = {
                    "foc": c["model"]["focal_non_epileptiform_activity"]["pred"],
                    "gen": c["model"]["generalized_non_epileptiform_activity"]["pred"]}
    return d


def load_harvard(con, table):
    cols = ["foc slowing", "gen slowing", "breach", "low voltage", "diffuse Beta", "bs"]
    q = 'SELECT "DeidentifiedName(Reports)", ' + ", ".join(f'"{c}"' for c in cols) + f' FROM "{table}"'
    hv = {}
    for row in con.execute(q):
        if not row[0]:
            continue
        hv[row[0]] = {c: (row[i + 1] not in (None, "")) for i, c in enumerate(cols)}
    return hv


def index_map(cohort):
    idx = json.loads(Path(f"results/harvard/{cohort}_index.json").read_text())
    return idx["zips"], {rid: (zi, inner) for rid, zi, inner in idx["reports"]}


def main():
    ours = load_ours()
    con = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)
    agg = {"foc": {"slow": 0, "other": 0, "sibling": 0, "n": 0},
           "gen": {"slow": 0, "other": 0, "sibling": 0, "n": 0}}
    for coh in COHORTS:
        hv = load_harvard(con, f"{coh}_EEG_with_reports")
        zips, loc = index_map(coh)
        zc = {}

        def text_of(rid):
            zi, inner = loc[rid]
            if zi not in zc:
                zc[zi] = zipfile.ZipFile(zips[zi])
            return zc[zi].open(inner).read().decode("utf-8", "replace")

        for key, hcol, sib, other in [
                ("foc", "foc slowing", ["breach", "low voltage"], OTHER_FOCAL),
                ("gen", "gen slowing", ["diffuse Beta", "low voltage", "bs"], OTHER_GEN)]:
            # our-extra: we present, Harvard slowing absent
            extra = [r for r in ours if r in hv and pres(ours[r][key]) and not hv[r][hcol]]
            for rid in extra[:SAMPLE]:
                try:
                    t = re.sub(r"\s+", " ", text_of(rid))
                except Exception:
                    continue
                agg[key]["n"] += 1
                if SLOW.search(t):
                    agg[key]["slow"] += 1
                elif other.search(t):
                    agg[key]["other"] += 1
                if any(hv[rid][s] for s in sib):
                    agg[key]["sibling"] += 1

    print("Among reports where WE call the finding present but Harvard's slowing column is "
          "absent (sampled):\n")
    for key, label in [("foc", "focal_non_epileptiform vs foc slowing"),
                       ("gen", "generalized_non_epileptiform vs gen slowing")]:
        a = agg[key]; n = a["n"] or 1
        print(f"{label}  (n={a['n']})")
        print(f"  report text mentions slowing        : {a['slow']:4d}  ({100*a['slow']/n:.0f}%)")
        print(f"  no slowing, but other non-epi term  : {a['other']:4d}  ({100*a['other']/n:.0f}%)")
        print(f"  Harvard flagged a sibling non-epi col: {a['sibling']:4d}  ({100*a['sibling']/n:.0f}%)\n")


if __name__ == "__main__":
    main()
