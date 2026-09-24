#!/usr/bin/env python3
"""Export our Harvard slowing labels into a small browsable SQLite DB, next to Harvard's own
values, with ready-made tables of every report we called `not_mentioned`.

Tables:
  harvard_slowing            report_id, cohort, focal_ours, generalized_ours, foc_harvard, gen_harvard
  focal_not_mentioned        the reports where our focal call is not_mentioned
  generalized_not_mentioned  the reports where our generalized call is not_mentioned

Run:  python -m analysis.slowing_export_db      ->  results/harvard/slowing_labels.db
"""
from __future__ import annotations

import glob
import json
import os
import sqlite3
from pathlib import Path

DB = "/project/6019337/databases/eeg_harvard/HarvardEEG.db"
COHORTS = ["MGH", "BWH", "BCH"]
OUT = Path("results/harvard/slowing_labels.db")


def load_ours(cohort, field):
    d = {}
    for f in glob.glob(f"results/slowing_harvard/{cohort}/{field}/labels_*.json"):
        for c in json.load(open(f)).get("cases", []):
            if c.get("slowing"):
                d[c["hashed_id"]] = c["slowing"]["status"]
    return d


def load_harvard(cohort, col):
    con = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)
    d = {}
    for rid, v in con.execute(
            f'SELECT "DeidentifiedName(Reports)", "{col}" FROM "{cohort}_EEG_with_reports"'):
        if not rid:
            continue
        # keep the richest provenance string seen across the report's rows
        s = v or ""
        if rid not in d or len(s) > len(d[rid] or ""):
            d[rid] = v
    con.close()
    return d


def main():
    if OUT.exists():
        os.remove(OUT)
    out = sqlite3.connect(OUT)
    out.execute('CREATE TABLE harvard_slowing (report_id TEXT, cohort TEXT, '
                'focal_ours TEXT, generalized_ours TEXT, foc_harvard TEXT, gen_harvard TEXT)')
    rows = []
    for coh in COHORTS:
        fo, go = load_ours(coh, "focal"), load_ours(coh, "generalized")
        fh, gh = load_harvard(coh, "foc slowing"), load_harvard(coh, "gen slowing")
        for rid in sorted(set(fo) | set(go)):
            rows.append((rid, coh, fo.get(rid), go.get(rid), fh.get(rid), gh.get(rid)))
    out.executemany('INSERT INTO harvard_slowing VALUES (?,?,?,?,?,?)', rows)
    out.execute('CREATE TABLE focal_not_mentioned AS '
                'SELECT report_id, cohort, foc_harvard FROM harvard_slowing '
                'WHERE focal_ours = "not_mentioned"')
    out.execute('CREATE TABLE generalized_not_mentioned AS '
                'SELECT report_id, cohort, gen_harvard FROM harvard_slowing '
                'WHERE generalized_ours = "not_mentioned"')
    out.commit()
    n = out.execute('SELECT COUNT(*) FROM harvard_slowing').fetchone()[0]
    fnm = out.execute('SELECT COUNT(*) FROM focal_not_mentioned').fetchone()[0]
    gnm = out.execute('SELECT COUNT(*) FROM generalized_not_mentioned').fetchone()[0]
    print(f"harvard_slowing: {n} reports")
    print(f"focal not_mentioned: {fnm}")
    print(f"generalized not_mentioned: {gnm}")
    out.close()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
