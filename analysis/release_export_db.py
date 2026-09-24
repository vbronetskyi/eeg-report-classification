#!/usr/bin/env python3
"""Build the release SQLite DBs for the slowing and background labels on the Fraser Health set,
matching the layout of the existing release_001 triphasic DB: one row per report keyed by
Hashed_ReportURN, a topic table of status columns, and an `about` metadata table. Labels only —
no report text.

Outputs (into --out-dir, default results/release/):
  eeg_reports_release_001_medgemma_Q4KS_slowing_250825.db
      table slowing    (Hashed_ReportURN, focal_slowing, generalized_slowing)
  eeg_reports_release_001_medgemma_Q4KS_background_250825.db
      table background (Hashed_ReportURN, discontinuous_background, burst_suppression, suppressed_background)

Run:  python -m analysis.release_export_db
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
from pathlib import Path

MODEL = "MedGemma-27B (google/medgemma-27b-text-it)"
QUANT = "Q4_K_S"
DATASET = "processed_reports_240325 (45,545 reports)"
STATUS_VALUES = "present, explicitly_absent, not_mentioned"

# topic -> (results subdir, container key, [(field dir, db column)], about)
SPECS = {
    "slowing": {
        "src": "results/slowing", "container": "slowing", "table": "slowing",
        "fields": [("focal", "focal_slowing"), ("generalized", "generalized_slowing")],
        "task": "focal / generalized slowing — status per report",
        "prompt": "one grammar-constrained prompt per field (focal, generalized)",
    },
    "background": {
        "src": "results/background", "container": "background", "table": "background",
        "fields": [("discontinuous", "discontinuous_background"),
                   ("burst_suppression", "burst_suppression"),
                   ("suppressed", "suppressed_background")],
        "task": "discontinuous / burst-suppression / suppressed background — status per report",
        "prompt": "one grammar-constrained prompt per field (discontinuous, burst_suppression, suppressed)",
    },
}
NAME = "eeg_reports_release_001_medgemma_Q4KS_{topic}_250825.db"


def load_field(src, field_dir, container):
    """hashed_id -> status for one field's chunk files."""
    d = {}
    for f in glob.glob(f"{src}/{field_dir}/labels_*.json"):
        for c in json.load(open(f)).get("cases", []):
            cont = c.get(container)
            if cont and c.get("hashed_id"):
                d[c["hashed_id"]] = cont["status"]
    return d


def build(topic, out_dir):
    spec = SPECS[topic]
    cols = [db for _, db in spec["fields"]]
    per = {db: load_field(spec["src"], fd, spec["container"]) for fd, db in spec["fields"]}
    ids = sorted(set().union(*[set(v) for v in per.values()]))

    out_path = Path(out_dir) / NAME.format(topic=topic)
    if out_path.exists():
        os.remove(out_path)
    out = sqlite3.connect(out_path)
    coldefs = ", ".join(f'"{c}" TEXT' for c in cols)
    out.execute(f'CREATE TABLE {spec["table"]} ("Hashed_ReportURN" TEXT PRIMARY KEY, {coldefs})')
    out.executemany(
        f'INSERT INTO {spec["table"]} VALUES (?, {", ".join("?" for _ in cols)})',
        [(rid, *[per[c].get(rid) for c in cols]) for rid in ids])
    about = [
        ("model", MODEL), ("quantization", QUANT), ("task", spec["task"]),
        ("prompt", spec["prompt"]),
        ("decoding", "temperature 0, grammar-constrained (deterministic)"),
        ("dataset", DATASET), ("status_values", STATUS_VALUES),
        ("fields", ", ".join(cols)),
        ("note", "labels only; report text is not included"),
    ]
    out.execute('CREATE TABLE about ("key" TEXT, "value" TEXT)')
    out.executemany("INSERT INTO about VALUES (?, ?)", about)
    out.commit()
    n = out.execute(f'SELECT COUNT(*) FROM {spec["table"]}').fetchone()[0]
    print(f"{out_path.name}: {n} reports, columns {cols}")
    out.close()
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="results/release")
    ap.add_argument("--topics", nargs="+", default=["slowing", "background"])
    args = ap.parse_args()
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    for t in args.topics:
        build(t, args.out_dir)


if __name__ == "__main__":
    main()
