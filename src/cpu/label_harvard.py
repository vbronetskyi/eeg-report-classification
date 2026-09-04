#!/usr/bin/env python3
"""Label Harvard (HEEDB) free-text EEG reports with our production pipeline (v5g).

Reads the report text straight from the HEEDB zip dumps via a prebuilt index
(analysis/harvard_index.py), runs the SAME inference primitives and prompt as our
validated runs — nothing about the prompt changes, only the data source (zip instead of
the processed_reports DB). Writes ONLY the structured labels, keyed by report id, never
the report text. Checkpoints as it goes, so a killed/timed-out job resumes cleanly.

Run (inside the Slurm job, after llama-server is up):
    python -m cpu.label_harvard --index results/harvard/MGH_index.json \
        --start-index 0 --chunk-size 1000 --base-url http://127.0.0.1:PORT/v1 \
        --model medgemma-q2 --output results/harvard/labels/MGH/labels_00000_00999.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
import zipfile
from pathlib import Path

from openai import OpenAI

from core.prompt import ENFORCE_CONSISTENCY, PROMPT_VARIANT
from cpu.evaluator import parse_joint_response, request_classification

FIELDS = [
    "abnormality",
    "focal_epileptiform_activity",
    "generalized_epileptiform_activity",
    "focal_non_epileptiform_activity",
    "generalized_non_epileptiform_activity",
]


def main() -> None:
    p = argparse.ArgumentParser(description="Label a chunk of Harvard EEG reports.")
    p.add_argument("--index", type=Path, required=True, help="cohort index json")
    p.add_argument("--start-index", type=int, required=True)
    p.add_argument("--chunk-size", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model", default="medgemma-q2")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--max-tokens", type=int, default=128)
    p.add_argument("--retries", type=int, default=2)
    args = p.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    idx = json.loads(args.index.read_text())
    zips = idx["zips"]
    reports = idx["reports"][args.start_index:args.start_index + args.chunk_size]
    end = args.start_index + len(reports)
    print(f"cohort={idx['cohort']} slice [{args.start_index}, {end}) -> {len(reports)} "
          f"reports  (prompt={PROMPT_VARIANT}, enforce_consistency={ENFORCE_CONSISTENCY})")

    # resume: keep already-labelled ids
    cases: dict[str, dict] = {}
    if args.output.exists():
        try:
            prev = json.loads(args.output.read_text()).get("cases", [])
            cases = {c["report_id"]: c for c in prev if c.get("model")}
            print(f"Resuming: {len(cases)} already labelled.")
        except Exception:
            cases = {}

    # per-request timeout so a hung llama-server never blocks the whole job forever;
    # our own retry loop below (not the SDK's) governs retries. Raise CLIENT_TIMEOUT for the
    # rare very-long report whose prefill legitimately needs more than the default.
    _timeout = float(os.environ.get("CLIENT_TIMEOUT", "180"))
    client = OpenAI(base_url=args.base_url, api_key="EMPTY", timeout=_timeout, max_retries=0)
    zcache: dict[int, zipfile.ZipFile] = {}
    consec_unresponsive = 0  # consecutive non-400 failures -> server likely dead

    def read_text(zi, inner):
        if zi not in zcache:
            zcache[zi] = zipfile.ZipFile(zips[zi])
        return zcache[zi].open(inner).read().decode("utf-8", "replace").strip()

    def flush():
        meta = {"cohort": idx["cohort"], "source": "heedb_zip",
                "start_index": args.start_index, "end_index": end, "n": len(reports),
                "prompt_variant": PROMPT_VARIANT, "enforce_consistency": ENFORCE_CONSISTENCY,
                "model": args.model}
        args.output.write_text(json.dumps(
            {"meta": meta, "cases": list(cases.values())}, indent=1))

    done = 0
    for rid, zi, inner in reports:
        if rid in cases:
            done += 1
            continue
        try:
            text = read_text(zi, inner)
        except Exception as e:  # noqa: BLE001
            cases[rid] = {"report_id": rid, "model": None, "error": f"read: {str(e)[:120]}"}
            done += 1
            continue
        if not text:
            cases[rid] = {"report_id": rid, "model": None, "error": "empty report"}
            done += 1
            continue
        t0 = time.time()
        model_results = None
        err = None
        for attempt in range(args.retries + 1):
            try:
                resp = request_classification(client, args.model, text, args.max_tokens)
                _parsed, model_results = parse_joint_response(resp)
                break
            except Exception as e:  # noqa: BLE001 — record and move on
                err = str(e)[:200]
                if attempt == args.retries:
                    model_results = None
        cases[rid] = {
            "report_id": rid,
            "model": model_results,
            "report_words": len(text.split()),
            "inference_seconds": round(time.time() - t0, 2),
        }
        if model_results is None:
            cases[rid]["error"] = err
        # A 400 means the server replied (e.g. rejected an over-long report) -> it is alive;
        # repeated timeouts/connection errors mean it has hung. Bail out fast in that case so
        # the chunk is resubmitted onto a fresh server instead of grinding to the walltime.
        if model_results is not None or (err and "400" in err):
            consec_unresponsive = 0
        else:
            consec_unresponsive += 1
        if consec_unresponsive >= 8:
            flush()
            print(f"ABORT: {consec_unresponsive} consecutive unresponsive requests — "
                  f"llama-server likely dead; exiting so this chunk is resubmitted fresh.",
                  flush=True)
            raise SystemExit(1)
        done += 1
        if done % 50 == 0:
            flush()
            print(f"  {done}/{len(reports)} done", flush=True)

    flush()
    ok = sum(1 for c in cases.values() if c.get("model"))
    print(f"DONE: {ok}/{len(reports)} labelled -> {args.output}")


if __name__ == "__main__":
    main()
