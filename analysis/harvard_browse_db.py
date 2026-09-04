#!/usr/bin/env python3
"""Build a small, local, browsable copy of the Harvard EEG label tables so they can be opened in
a SQLite viewer (e.g. in VS Code) without loading the full 600 MB read-only DB. Copies only the
four per-hospital label tables plus the two small lookup tables — not the 2.6 M-row medication
table. Report text is not in the DB (it lives in the HEEDB zips), so it is not here either.

Run:  python -m analysis.harvard_browse_db
Then open results/harvard/heedb_browse.db in a SQLite VS Code extension.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SRC = "/project/6019337/databases/eeg_harvard/HarvardEEG.db"
OUT = Path("results/harvard/heedb_browse.db")
TABLES = ["MGH_EEG_with_reports", "BWH_EEG_with_reports", "BCH_EEG_with_reports",
          "BIDMC_EEG_with_reports", "icd10_lookup", "atc_lookup"]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    src = sqlite3.connect(f"file:{SRC}?immutable=1", uri=True)
    dst = sqlite3.connect(OUT)
    for t in TABLES:
        cols = [c[1] for c in src.execute(f'PRAGMA table_info("{t}")')]
        coldef = ", ".join(f'"{c}"' for c in cols)
        dst.execute(f'CREATE TABLE "{t}" ({coldef})')
        rows = src.execute(f'SELECT * FROM "{t}"').fetchall()
        dst.executemany(f'INSERT INTO "{t}" VALUES ({",".join("?" * len(cols))})', rows)
        # a helpful index for lookups by report id
        if "DeidentifiedName(Reports)" in cols:
            dst.execute(f'CREATE INDEX "ix_{t}_rid" ON "{t}" ("DeidentifiedName(Reports)")')
        print(f"  {t}: {len(rows)} rows, {len(cols)} cols")
    dst.commit()
    dst.close()
    print(f"\nwrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB) — open it in a SQLite VS Code extension")


if __name__ == "__main__":
    main()
