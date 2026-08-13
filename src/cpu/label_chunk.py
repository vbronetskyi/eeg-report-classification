#!/usr/bin/env python3
"""Label a chunk of the (unlabeled) processed_reports dataset with the production
pipeline (v5 prompt + ENFORCE_CONSISTENCY grammar, MedGemma-27B).

Reads reports straight from the SQLite DB by rowid slice, runs the same inference
primitives as the validated evaluator, and writes ONLY the structured labels — never
the report text. Checkpoints as it goes, so a killed/timed-out job resumes cleanly.

Run (inside the Slurm job, after the llama-server is up):
    python -m cpu.label_chunk --start-index 0 --chunk-size 2000 \
        --db /project/6019337/vvakorin/incoming/processed_reports_240325.db \
        --base-url http://127.0.0.1:PORT/v1 --model medgemma-q2 \
        --output results/labels/labels_00000_02000.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

from openai import OpenAI

from core.prompt import ENFORCE_CONSISTENCY, PROMPT_VARIANT
from cpu.evaluator import parse_joint_response, request_classification

DEFAULT_DB = "/project/6019337/vvakorin/incoming/processed_reports_240325.db"
FIELDS = [
    "abnormality",
    "focal_epileptiform_activity",
    "generalized_epileptiform_activity",
    "focal_non_epileptiform_activity",
    "generalized_non_epileptiform_activity",
]


def read_slice(db, start, size):
    """(hashed_id, report_text) for the rowid-ordered slice [start, start+size)."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute(
        'SELECT "Hashed ID", "Report" FROM reports '
        "ORDER BY rowid LIMIT ? OFFSET ?",
        (size, start),
    ).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]


def main() -> None:
    p = argparse.ArgumentParser(description="Label a chunk of processed_reports.")
    p.add_argument("--start-index", type=int, required=True)
    p.add_argument("--chunk-size", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--model", default="medgemma-q2")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--max-tokens", type=int, default=128)
    p.add_argument("--retries", type=int, default=2)
    args = p.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    reports = read_slice(args.db, args.start_index, args.chunk_size)
    end = args.start_index + len(reports)
    print(f"Slice [{args.start_index}, {end}) -> {len(reports)} reports  "
          f"(prompt={PROMPT_VARIANT}, enforce_consistency={ENFORCE_CONSISTENCY})")

    # resume: keep already-labelled ids
    cases: dict[str, dict] = {}
    if args.output.exists():
        try:
            prev = json.loads(args.output.read_text()).get("cases", [])
            cases = {c["hashed_id"]: c for c in prev if c.get("model")}
            print(f"Resuming: {len(cases)} already labelled.")
        except Exception:
            cases = {}

    client = OpenAI(base_url=args.base_url, api_key="EMPTY")

    def flush():
        meta = {"db": args.db, "table": "reports", "start_index": args.start_index,
                "end_index": end, "n": len(reports), "prompt_variant": PROMPT_VARIANT,
                "enforce_consistency": ENFORCE_CONSISTENCY, "model": args.model}
        args.output.write_text(json.dumps(
            {"meta": meta, "cases": list(cases.values())}, indent=1))

    done = 0
    for hid, text in reports:
        if hid in cases:
            done += 1
            continue
        text = (text or "").strip()
        if not text:
            cases[hid] = {"hashed_id": hid, "model": None, "error": "empty report"}
            continue
        t0 = time.time()
        model_results = None
        for attempt in range(args.retries + 1):
            try:
                resp = request_classification(client, args.model, text, args.max_tokens)
                _parsed, model_results = parse_joint_response(resp)
                break
            except Exception as e:  # noqa: BLE001 — record and move on
                err = str(e)[:200]
                if attempt == args.retries:
                    model_results = None
        cases[hid] = {
            "hashed_id": hid,
            "model": model_results,
            "report_words": len(text.split()),
            "inference_seconds": round(time.time() - t0, 2),
        }
        if model_results is None:
            cases[hid]["error"] = err
        done += 1
        if done % 50 == 0:
            flush()
            print(f"  {done}/{len(reports)} done", flush=True)

    flush()
    ok = sum(1 for c in cases.values() if c.get("model"))
    print(f"DONE: {ok}/{len(reports)} labelled -> {args.output}")


if __name__ == "__main__":
    main()
