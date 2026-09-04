#!/usr/bin/env python3
"""Build a report-id -> (zip, inner path) index for a Harvard (HEEDB) cohort, so the
labeler can read the free-text EEG reports straight from the HEEDB zip dumps.

Report ids are the `DeidentifiedName(Reports)` values in the `*_EEG_with_reports` label
table; they are matched to the text files by their `NeuroReport_*.txt` name.

Sources (confirmed 100% coverage):
  MGH  (S0001) + BWH (S0002) = I0001  -> EHR/neurology_reports_v2/I0001_Neurology_Reports_1_*.zip
  BCH  (I0003)                        -> EHR/I0003-EHR/.../I0003_EEG_Reports_11202024.zip
  BIDMC(I0002)                        -> EHR/I0002-EHR/.../I0002_EEG_Reports_2/*.zip

Run:  python -m analysis.harvard_index MGH BWH      (default: all four)
"""
from __future__ import annotations

import glob
import json
import os
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

H = "/project/6019337/databases/eeg_harvard"
DB = f"{H}/HarvardEEG.db"
SRC = {
    "MGH":   sorted(glob.glob(f"{H}/EHR/neurology_reports_v2/I0001_Neurology_Reports_1_*.zip")),
    "BWH":   sorted(glob.glob(f"{H}/EHR/neurology_reports_v2/I0001_Neurology_Reports_1_*.zip")),
    "BCH":   [f"{H}/EHR/I0003-EHR/data_Unstructured/I0003_Neurology_Reports_1/I0003_EEG_Reports_11202024.zip"],
    "BIDMC": sorted(glob.glob(f"{H}/EHR/I0002-EHR/I0002_unstructured/I0002_EEG_Reports_2/*.zip")),
}
TABLE = {c: f"{c}_EEG_with_reports" for c in SRC}
OUT = Path("results/harvard"); OUT.mkdir(parents=True, exist_ok=True)


def _key(name):
    m = re.search(r"(NeuroReport_[^/]*\.txt)$", name)
    return m.group(1) if m else os.path.basename(name)


def scan(zips):
    """suffix (NeuroReport_*.txt) -> (zip_idx, inner_name) over all zips.

    Skips macOS junk (`__MACOSX/` AppleDouble `._*` sidecars) that some zips carry — those
    are binary metadata, not the report, and their name strips to the same NeuroReport key.
    """
    m = {}
    for zi, z in enumerate(zips):
        for n in zipfile.ZipFile(z).namelist():
            base = os.path.basename(n)
            if "__MACOSX" in n or base.startswith("._"):
                continue
            if n.lower().endswith(".txt"):
                m[_key(n)] = (zi, n)
    return m


def build(cohort, name_map):
    zips = SRC[cohort]
    conn = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)
    ids = sorted({r[0] for r in conn.execute(
        f'SELECT DISTINCT "DeidentifiedName(Reports)" FROM "{TABLE[cohort]}"') if r[0]})
    reports, miss = [], 0
    for rid in ids:
        if rid in name_map:
            zi, inner = name_map[rid]; reports.append([rid, zi, inner])
        else:
            miss += 1
    (OUT / f"{cohort}_index.json").write_text(
        json.dumps({"cohort": cohort, "zips": zips, "reports": reports}))
    print(f"{cohort}: indexed {len(reports)}/{len(ids)} reports "
          f"({miss} missing) -> {OUT}/{cohort}_index.json")


if __name__ == "__main__":
    cohorts = sys.argv[1:] or ["MGH", "BWH", "BCH", "BIDMC"]
    cache = {}  # zips-tuple -> name_map, so MGH+BWH share the I0001 scan
    for c in cohorts:
        ztup = tuple(SRC[c])
        if ztup not in cache:
            print(f"scanning {len(SRC[c])} zip(s) for {c} ...", flush=True)
            cache[ztup] = scan(SRC[c])
        build(c, cache[ztup])
