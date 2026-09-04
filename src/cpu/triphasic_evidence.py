#!/usr/bin/env python3
"""Verification pass for the triphasic annotation: re-run only the reports we labelled
present or explicitly_absent and make the model quote the exact text it based the call on.

For each report the model returns its status again plus an `evidence` string copied verbatim
from the report. We then check, in plain code, whether that quote is actually a substring of
the report (quote_in_text) and whether the triphasic token appears at all (term_in_text). This
lets us confirm by hand what present and explicitly_absent really mean in the data, instead of
trusting the label alone.

The grammar pins the status enum and the JSON shape; the evidence field is a free JSON string
(the model copies the sentence), so nothing about the format can come back malformed.

Run (inside the Slurm job, after llama-server is up):
    python -m cpu.triphasic_evidence --ids-file results/triphasic/flagged_ids.txt \
        --start-index 0 --chunk-size 600 --base-url http://127.0.0.1:PORT/v1 \
        --model medgemma-q2 --output results/triphasic/evidence/labels_00000_00599.json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import zipfile
from pathlib import Path

from openai import OpenAI

from cpu.triphasic import SYSTEM, read_ids

# status enum is pinned; evidence is any JSON string (raw " and control chars excluded so the
# object always parses — escaped forms are still allowed).
GRAMMAR = r'''
root ::= "{\"status\": \"" status "\", \"evidence\": \"" str "\"}"
status ::= "present" | "explicitly_absent" | "not_mentioned"
str ::= char*
char ::= [^"\\\n\r\t] | "\\" ["\\/bfnrt]
'''

PROMPT = """You are checking an EEG report for triphasic waves. Read the report and quote the \
exact text it uses about triphasic waves, then decide the status from that text alone.

- present: the report states triphasic waves or triphasic morphology are present (including \
periodic discharges / GPDs with triphasic morphology, or triphasic-appearing discharges).
- explicitly_absent: the report explicitly says they are absent (e.g. no triphasic waves, \
periodic discharges without triphasic morphology).
- not_mentioned: the report never mentions triphasic waves or morphology.

Put in evidence the exact words copied verbatim from the report — the sentence or phrase that \
contains the triphasic reference. Do not paraphrase, summarize, or add anything. If the report \
never mentions triphasic waves, leave evidence empty.

EEG report:
{report}"""

TERM = re.compile(r"tri[ \-]*phasic|3[ \-]*phasic", re.I)


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def read_ids_index(index_file, ids_file, start, size):
    """(report_id, text) for an id-file slice, reading Harvard text from HEEDB zips via the
    cohort index — the evidence pass for the Harvard reports, not just the FHA DB."""
    ids = [ln.strip() for ln in Path(ids_file).read_text().splitlines() if ln.strip()]
    ids = ids[start:start + size]
    idx = json.loads(Path(index_file).read_text())
    zips = idx["zips"]
    loc = {rid: (zi, inner) for rid, zi, inner in idx["reports"]}
    zc: dict[int, zipfile.ZipFile] = {}
    out = []
    for rid in ids:
        if rid not in loc:
            out.append((rid, None)); continue
        zi, inner = loc[rid]
        try:
            if zi not in zc:
                zc[zi] = zipfile.ZipFile(zips[zi])
            out.append((rid, zc[zi].open(inner).read().decode("utf-8", "replace").strip()))
        except Exception:  # noqa: BLE001
            out.append((rid, None))
    return out


def request(client, model, text, max_tokens):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": PROMPT.format(report=text)}],
        temperature=0, max_tokens=max_tokens,
        extra_body={"grammar": GRAMMAR},
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Evidence/verification pass for triphasic labels.")
    p.add_argument("--ids-file", required=True)
    p.add_argument("--start-index", type=int, required=True)
    p.add_argument("--chunk-size", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--db", default="/project/6019337/vvakorin/incoming/processed_reports_240325.db")
    p.add_argument("--index", default=None, help="Harvard cohort index json (read text from HEEDB zips)")
    p.add_argument("--model", default="medgemma-q2")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--max-tokens", type=int, default=200)
    p.add_argument("--retries", type=int, default=2)
    args = p.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    reports = (read_ids_index(args.index, args.ids_file, args.start_index, args.chunk_size)
               if args.index else
               read_ids(args.db, args.ids_file, args.start_index, args.chunk_size))
    end = args.start_index + len(reports)
    print(f"[evidence] slice [{args.start_index}, {end}) -> {len(reports)} reports")

    cases: dict[str, dict] = {}
    if args.output.exists():
        try:
            prev = json.loads(args.output.read_text()).get("cases", [])
            cases = {c["hashed_id"]: c for c in prev if "status" in c}
            print(f"Resuming: {len(cases)} already done.")
        except Exception:
            cases = {}

    client = OpenAI(base_url=args.base_url, api_key="EMPTY", timeout=180.0, max_retries=0)

    def flush():
        meta = {"task": "triphasic_evidence", "ids_file": args.ids_file,
                "start_index": args.start_index, "end_index": end, "n": len(reports),
                "model": args.model}
        args.output.write_text(json.dumps({"meta": meta, "cases": list(cases.values())}, indent=1))

    done = 0
    for hid, text in reports:
        if hid in cases:
            done += 1
            continue
        text = (text or "").strip()
        if not text:
            cases[hid] = {"hashed_id": hid, "status": None, "error": "empty report"}
            done += 1
            continue
        result = err = None
        for attempt in range(args.retries + 1):
            try:
                resp = request(client, args.model, text, args.max_tokens)
                result = json.loads(resp.choices[0].message.content)
                break
            except Exception as e:  # noqa: BLE001
                err = str(e)[:200]
                if attempt == args.retries:
                    result = None
        if result:
            ev = result.get("evidence", "")
            cases[hid] = {"hashed_id": hid, "status": result["status"], "evidence": ev,
                          "quote_in_text": bool(ev) and _norm(ev) in _norm(text),
                          "term_in_text": bool(TERM.search(text))}
        else:
            cases[hid] = {"hashed_id": hid, "status": None, "error": err}
        done += 1
        if done % 50 == 0:
            flush()
            print(f"  {done}/{len(reports)} done", flush=True)

    flush()
    ok = sum(1 for c in cases.values() if c.get("status"))
    print(f"DONE [evidence]: {ok}/{len(reports)} -> {args.output}")


if __name__ == "__main__":
    main()
