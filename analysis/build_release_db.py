#!/usr/bin/env python3
"""Package a MedGemma labeling of the 45,545-report processed_reports dataset into a
release SQLite database, matching the schema of the Mistral public release so the two are
drop-in comparable. Stores only the structured labels — never the report text.

Tables:
  classifications  Hashed_ReportURN + the five categories, value = level 1-4  (as in Mistral)
  confidence       Hashed_ReportURN + the five categories, value = P(present), 0-1  (ours)
  about            key/value provenance (model, quantization, prompt, scale, ...)

Run:
  python -m analysis.build_release_db --source q2 \
      --out results/release/eeg_reports_release_001_medgemma_Q2_public_250825.db \
      --quant Q2_K
  python -m analysis.build_release_db --source q4 \
      --out results/release/eeg_reports_release_001_medgemma_Q4KS_public_250825.db \
      --quant Q4_K_S
"""
from __future__ import annotations

import argparse
import glob
import json
import sqlite3
from pathlib import Path

# our field key -> Mistral column name (and the Mistral column order)
COLS = [
    ("focal_epileptiform_activity", "Focal Epi"),
    ("generalized_epileptiform_activity", "Gen Epi"),
    ("focal_non_epileptiform_activity", "Focal Non-epi"),
    ("generalized_non_epileptiform_activity", "Gen Non-epi"),
    ("abnormality", "Abnormality"),
]
SOURCE = {"q2": "results/labels/labels_*.json",
          "q4": "results/labels/q4_k_s/labels_*.json"}


def load(pattern):
    d = {}
    for f in glob.glob(pattern):
        for c in json.load(open(f))["cases"]:
            if c.get("model"):
                d[c["hashed_id"]] = c["model"]
    return d


def build(rows, out: Path, about: dict):
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(out)
    coldefs = ", ".join(f'"{name}" REAL' for _, name in COLS)
    con.execute(f'CREATE TABLE classifications ("Hashed_ReportURN" TEXT PRIMARY KEY, {coldefs})')
    con.execute(f'CREATE TABLE confidence ("Hashed_ReportURN" TEXT PRIMARY KEY, {coldefs})')
    con.execute('CREATE TABLE about ("key" TEXT, "value" TEXT)')
    ph = ",".join(["?"] * (1 + len(COLS)))
    cls, conf = [], []
    for hid, m in rows.items():
        cls.append([hid] + [float(m[k]["pred"]) for k, _ in COLS])
        conf.append([hid] + [round(float(m[k]["p_presence"]), 6) for k, _ in COLS])
    con.executemany(f"INSERT INTO classifications VALUES ({ph})", cls)
    con.executemany(f"INSERT INTO confidence VALUES ({ph})", conf)
    con.executemany("INSERT INTO about VALUES (?, ?)", list(about.items()))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
    con.close()
    print(f"wrote {out}  ({n} reports)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=SOURCE, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--quant", required=True)
    args = p.parse_args()
    rows = load(SOURCE[args.source])
    about = {
        "model": "MedGemma-27B (google/medgemma-27b-text-it)",
        "quantization": args.quant,
        "prompt": "v5 + grammar-enforced consistency (v5g)",
        "decoding": "temperature 0, grammar-constrained (deterministic)",
        "dataset": "processed_reports_240325 (45,545 reports)",
        "classifications_scale": "1=definitely absent, 2=probably absent, "
                                 "3=probably present, 4=definitely present",
        "confidence_meaning": "P(present) = model probability the finding is present (0-1); "
                              "the sum of the level-3 and level-4 token probabilities",
        "note": "labels only; report text is not included",
    }
    build(rows, args.out, about)
