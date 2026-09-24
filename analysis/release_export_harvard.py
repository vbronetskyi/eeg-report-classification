#!/usr/bin/env python3
"""Build Harvard (HEEDB) release DBs from our MedGemma labels — the same layout as the FHA release
DBs but with a `cohort` column (MGH/BWH/BCH), keyed by the Harvard report id
(DeidentifiedName, `NeuroReport_...`). Labels only; no report text.

DUA: these carry Harvard report identifiers and must live only in the Harvard-controlled area.
This script stages them under results/harvard/release/ (git-ignored).

Outputs (into --out-dir, default results/harvard/release/):
  eeg_reports_release_001_medgemma_Q4KS_abnormality_harvard_250825.db  (classifications + confidence)
  eeg_reports_release_001_medgemma_Q4KS_slowing_harvard_250825.db      (focal/generalized slowing)
  eeg_reports_release_001_medgemma_Q4KS_background_harvard_250825.db   (discontinuous/burst/suppressed)

Run:  python -m analysis.release_export_harvard
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
from pathlib import Path

COHORTS = ["MGH", "BWH", "BCH"]
MODEL = "MedGemma-27B (google/medgemma-27b-text-it)"
AB = ["abnormality", "focal_epileptiform_activity", "generalized_epileptiform_activity",
      "focal_non_epileptiform_activity", "generalized_non_epileptiform_activity"]
AB_COLS = ["Abnormality", "Focal Epi", "Gen Epi", "Focal Non-epi", "Gen Non-epi"]


def _cases(pattern):
    for f in glob.glob(pattern, recursive=True):
        for c in json.load(open(f)).get("cases", []):
            yield c


def _rid(c):
    return c.get("hashed_id") or c.get("report_id")


def about_rows(task, prompt, fields):
    return [("model", MODEL), ("quantization", "Q4_K_S"), ("task", task), ("prompt", prompt),
            ("decoding", "temperature 0, grammar-constrained (deterministic)"),
            ("dataset", "Harvard EEG Database (HEEDB) — MGH, BWH, BCH report text"),
            ("cohorts", "MGH, BWH, BCH (BIDMC excluded — no report text)"),
            ("fields", fields), ("note", "labels only; report text is not included; DUA-restricted")]


def open_fresh(path):
    if os.path.exists(path):
        os.remove(path)
    return sqlite3.connect(path)


def build_status(topic, table, src, fields, out_dir, task, prompt):
    """Three-way status topics (slowing, background): one table, report_id + cohort + field cols."""
    cols = [db for _, db in fields]
    rows = []
    for coh in COHORTS:
        per = {}
        for fd, db in fields:
            for c in _cases(f"results/{src}/{coh}/{fd}/labels_*.json"):
                cont = c.get("slowing") or c.get("background")  # labeler's case container key
                if cont and _rid(c):
                    per.setdefault(_rid(c), {})[db] = cont["status"]
        for rid, d in per.items():
            rows.append((rid, coh, *[d.get(col) for col in cols]))
    path = Path(out_dir) / f"eeg_reports_release_001_medgemma_Q4KS_{topic}_harvard_250825.db"
    out = open_fresh(path)
    coldefs = ", ".join(f'"{c}" TEXT' for c in cols)
    out.execute(f'CREATE TABLE {table} ("report_id" TEXT, "cohort" TEXT, {coldefs}, '
                'PRIMARY KEY (report_id, cohort))')
    out.executemany(f'INSERT INTO {table} VALUES (?,?,{",".join("?" for _ in cols)})', rows)
    out.execute('CREATE TABLE about ("key" TEXT, "value" TEXT)')
    out.executemany("INSERT INTO about VALUES (?,?)", about_rows(task, prompt, ", ".join(cols)))
    out.commit()
    print(f"{path.name}: {out.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]} rows, cols {cols}")
    out.close()


def build_abnormality(out_dir):
    cls, conf, seen = [], [], set()
    for coh in COHORTS:
        for c in _cases(f"results/harvard/labels/{coh}/**/*.json"):
            m = c.get("model")
            rid = _rid(c)
            if not m or not rid or (rid, coh) in seen:
                continue
            seen.add((rid, coh))
            cls.append((rid, coh, *[m[k]["pred"] for k in AB]))
            conf.append((rid, coh, *[round(m[k].get("p_presence", 0.0), 6) for k in AB]))
    path = Path(out_dir) / "eeg_reports_release_001_medgemma_Q4KS_abnormality_harvard_250825.db"
    out = open_fresh(path)
    coldefs = ", ".join(f'"{c}" REAL' for c in AB_COLS)
    for t in ("classifications", "confidence"):
        out.execute(f'CREATE TABLE {t} ("report_id" TEXT, "cohort" TEXT, {coldefs}, '
                    'PRIMARY KEY (report_id, cohort))')
    out.executemany(f'INSERT INTO classifications VALUES (?,?,{",".join("?"*len(AB))})', cls)
    out.executemany(f'INSERT INTO confidence VALUES (?,?,{",".join("?"*len(AB))})', conf)
    out.execute('CREATE TABLE about ("key" TEXT, "value" TEXT)')
    out.executemany("INSERT INTO about VALUES (?,?)", about_rows(
        "five findings (abnormality + focal/gen epileptiform + focal/gen non-epileptiform)",
        "prompt v5 + consistency grammar (v5g); classifications = 1-4, confidence = P(present)",
        ", ".join(AB_COLS)))
    out.commit()
    print(f"{path.name}: {out.execute('SELECT COUNT(*) FROM classifications').fetchone()[0]} rows")
    out.close()


def build_triphasic(out_dir):
    """Guarded triphasic labels: long = primary columns, short = _alt (matches the FHA release DB)."""
    from analysis.triphasic_harvard_analysis import load_variant, text_lookup, guard
    rows = []
    for coh in COHORTS:
        s_raw, l_raw = load_variant(coh, "short"), load_variant(coh, "long")
        flagged = [rid for rid in set(s_raw) | set(l_raw)
                   if (s_raw.get(rid, {}).get("triphasic") or {}).get("status") in ("present", "explicitly_absent")
                   or (l_raw.get(rid, {}).get("triphasic") or {}).get("status") in ("present", "explicitly_absent")]
        txt = text_lookup(coh, flagged)
        sg, _ = guard(s_raw, txt)
        lg, _ = guard(l_raw, txt)
        for rid in set(sg) | set(lg):
            ls = lg.get(rid) or ("not_mentioned", "not_applicable")
            ss = sg.get(rid) or ("not_mentioned", "not_applicable")
            rows.append((rid, coh, ls[0], ls[1], ss[0], ss[1]))
    path = Path(out_dir) / "eeg_reports_release_001_medgemma_Q4KS_triphasic_harvard_250825.db"
    out = open_fresh(path)
    out.execute('CREATE TABLE triphasic ("report_id" TEXT, "cohort" TEXT, "status" TEXT, '
                '"phenotype" TEXT, "status_alt" TEXT, "phenotype_alt" TEXT, '
                'PRIMARY KEY (report_id, cohort))')
    out.executemany("INSERT INTO triphasic VALUES (?,?,?,?,?,?)", rows)
    out.execute('CREATE TABLE about ("key" TEXT, "value" TEXT)')
    ab = about_rows("triphasic waves — status + phenotype",
                    "two prompts (long = primary columns, short = _alt cross-check); "
                    "faithfulness guard: present/absent require the term 'triphasic' in the report text, "
                    "else reset to not_mentioned",
                    "status, phenotype, status_alt, phenotype_alt")
    out.executemany("INSERT INTO about VALUES (?,?)", ab)
    out.commit()
    print(f"{path.name}: {out.execute('SELECT COUNT(*) FROM triphasic').fetchone()[0]} rows")
    out.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="results/harvard/release")
    args = ap.parse_args()
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    build_abnormality(args.out_dir)
    build_triphasic(args.out_dir)
    build_status("slowing", "slowing", "slowing_harvard",
                 [("focal", "focal_slowing"), ("generalized", "generalized_slowing")],
                 args.out_dir, "focal / generalized slowing — status per report",
                 "one grammar-constrained prompt per field")
    build_status("background", "background", "background_harvard",
                 [("discontinuous", "discontinuous_background"),
                  ("burst_suppression", "burst_suppression"), ("suppressed", "suppressed_background")],
                 args.out_dir, "discontinuous / burst-suppression / suppressed background — status per report",
                 "one grammar-constrained prompt per field")


if __name__ == "__main__":
    main()
