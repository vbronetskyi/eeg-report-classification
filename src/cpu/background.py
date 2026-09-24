#!/usr/bin/env python3
"""Annotate EEG reports for three background patterns, each as its own separate three-way
status, with MedGemma-27B under a grammar that guarantees the schema:

  discontinuous_background : present | explicitly_absent | not_mentioned
  burst_suppression        : present | explicitly_absent | not_mentioned
  suppressed_background    : present | explicitly_absent | not_mentioned

One field per run (--field discontinuous | burst_suppression | suppressed). The prompts are the
PI's, used essentially verbatim; the GBNF grammar constrains the output to exactly one valid JSON
object. Same plumbing as cpu.slowing (slice / Harvard index / id-file reading, resume, meta), so
the outputs line up with the earlier runs.

Run (inside the Slurm job, after llama-server is up):
    python -m cpu.background --field burst_suppression --start-index 0 --chunk-size 2000 \
        --db /project/6019337/vvakorin/incoming/processed_reports_240325.db \
        --base-url http://127.0.0.1:PORT/v1 --model medgemma \
        --output results/background/burst_suppression/labels_00000_01999.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import zipfile
from pathlib import Path

from openai import OpenAI

SYSTEM = "You are an expert annotator of routine clinical EEG reports."

DISCONTINUOUS = """Determine whether the report explicitly describes the EEG background as \
discontinuous.

Use only information stated in the EEG report. Your task is to extract the neurologist's \
documented interpretation, not to independently diagnose the EEG.

Return valid JSON only:

{"discontinuous_background": "present | explicitly_absent | not_mentioned"}

Assign "present" when the report explicitly states that the EEG background is discontinuous or \
uses clearly equivalent language indicating interruptions in the continuity of the background \
activity.

Examples include statements such as "discontinuous background," "the background is \
discontinuous," or equivalent explicit descriptions of discontinuity of the EEG background.

Assign "explicitly_absent" only when the report explicitly states that the background is \
continuous, normally continuous, or that discontinuity is absent.

Assign "not_mentioned" when the report does not explicitly describe the continuity of the EEG \
background.

Do not infer a discontinuous background from generalized slowing, focal slowing, low voltage, \
attenuation, intermittent slowing, intermittent abnormalities, encephalopathy, sedation, coma, \
or reduced organization of the background.

Do not automatically classify burst-suppression, burst-attenuation, suppression, or \
electrocerebral inactivity as "discontinuous_background": "present". These are separate \
background categories and should be annotated independently unless the report also explicitly \
describes the background as discontinuous.

Do not interpret the word "intermittent" as evidence of a discontinuous background when it \
refers to another finding, such as intermittent focal slowing, intermittent epileptiform \
discharges, artifacts, or periodic abnormalities.

When the wording is ambiguous and does not clearly refer to continuity of the EEG background, \
use "not_mentioned".

EEG report:

{report}"""

BURST_SUPPRESSION = """Determine whether the report explicitly describes a burst-suppression or \
suppression-burst pattern.

Use only information explicitly stated in the EEG report. Your task is to extract the \
neurologist's documented interpretation, not to independently diagnose the EEG.

Return valid JSON only:

{"burst_suppression": "present | explicitly_absent | not_mentioned"}

Assign "present" when the report explicitly states that burst-suppression, suppression-burst, a \
burst-suppression pattern, or clearly equivalent terminology is present.

Examples include "burst-suppression," "burst suppression pattern," "suppression-burst \
activity," or "background demonstrates alternating bursts and periods of suppression" when this \
description clearly identifies a burst-suppression pattern.

Assign "explicitly_absent" only when the report explicitly states that burst-suppression or \
suppression-burst activity is absent.

Assign "not_mentioned" when the report does not explicitly mention or clearly describe a \
burst-suppression pattern.

Do not infer burst-suppression from generalized slowing, focal slowing, discontinuous \
background, low-voltage background, attenuation, suppressed background, coma, encephalopathy, \
sedation, anesthesia, or reduced background organization.

Do not classify "burst-attenuation" as burst-suppression unless the report also explicitly \
identifies burst-suppression. Burst-attenuation, discontinuous background, suppression, and \
electrocerebral inactivity are separate background patterns.

When the wording is ambiguous and does not clearly establish burst-suppression, use \
"not_mentioned".

EEG report:

{report}"""

SUPPRESSED = """Determine whether the report explicitly describes the EEG background as \
suppressed.

Use only information explicitly stated in the EEG report. Your task is to extract the \
neurologist's documented interpretation, not to independently diagnose the EEG.

Return valid JSON only:

{"suppressed_background": "present | explicitly_absent | not_mentioned"}

Assign "present" when the report explicitly states that the EEG background is suppressed or \
uses clearly equivalent terminology indicating generalized or diffuse suppression of the \
background activity.

Examples include "suppressed background," "background suppression," "diffusely suppressed \
background," "generalized background suppression," or "marked suppression of the background."

Assign "explicitly_absent" only when the report explicitly states that background suppression \
is absent, for example "no background suppression" or "the background is not suppressed."

Assign "not_mentioned" when the report does not explicitly describe the background as \
suppressed or explicitly state that suppression is absent.

Do not infer a suppressed background from generalized slowing, focal slowing, low amplitude, \
low voltage, attenuation, poorly organized background, reduced reactivity, coma, \
encephalopathy, sedation, or anesthesia unless the report explicitly characterizes the \
background as suppressed.

Do not classify burst-suppression, suppression-burst, burst-attenuation, or discontinuous \
background as "suppressed_background": "present" merely because periods of suppression occur \
within those patterns. These are separate background categories unless the report also \
explicitly states that the overall background is suppressed.

Do not classify electrocerebral inactivity or an isoelectric EEG as a suppressed background \
unless the report separately describes background suppression.

Do not use transient or event-related suppression, such as suppression associated with a \
seizure, artifact, stimulation, or a brief localized interval, as evidence of a globally \
suppressed background.

When wording is ambiguous, prefer "not_mentioned" rather than inferring suppression.

EEG report:

{report}"""

FIELDS = {
    "discontinuous":     {"key": "discontinuous_background", "prompt": DISCONTINUOUS},
    "burst_suppression": {"key": "burst_suppression",        "prompt": BURST_SUPPRESSION},
    "suppressed":        {"key": "suppressed_background",     "prompt": SUPPRESSED},
}


def grammar(json_key):
    return ('root ::= "{\\"' + json_key + '\\": \\"" status "\\"}"\n'
            'status ::= "present" | "explicitly_absent" | "not_mentioned"\n')


def read_slice(db, start, size):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute(
        'SELECT "Hashed ID", "Report" FROM reports ORDER BY rowid LIMIT ? OFFSET ?',
        (size, start)).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]


def read_index(index_file, start, size):
    idx = json.loads(Path(index_file).read_text())
    zips = idx["zips"]
    items = idx["reports"][start:start + size]
    zc: dict[int, zipfile.ZipFile] = {}
    out = []
    for rid, zi, inner in items:
        try:
            if zi not in zc:
                zc[zi] = zipfile.ZipFile(zips[zi])
            text = zc[zi].open(inner).read().decode("utf-8", "replace").strip()
        except Exception:  # noqa: BLE001
            text = None
        out.append((rid, text))
    return out


def read_ids(db, ids_file, start, size):
    ids = [ln.strip() for ln in Path(ids_file).read_text().splitlines() if ln.strip()]
    ids = ids[start:start + size]
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    txt = {r[0]: r[1] for r in conn.execute('SELECT "Hashed ID", "Report" FROM reports')}
    conn.close()
    return [(i, txt.get(i)) for i in ids]


def request(client, model, prompt_text, gbnf, max_tokens):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": prompt_text}],
        temperature=0,
        max_tokens=max_tokens,
        extra_body={"grammar": gbnf},
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Background-pattern annotation of EEG reports.")
    p.add_argument("--field", choices=FIELDS, required=True)
    p.add_argument("--start-index", type=int, required=True)
    p.add_argument("--chunk-size", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--db", default="/project/6019337/vvakorin/incoming/processed_reports_240325.db")
    p.add_argument("--ids-file", default=None)
    p.add_argument("--index", default=None, help="a Harvard cohort index json (read text from HEEDB zips)")
    p.add_argument("--model", default="medgemma")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--max-tokens", type=int, default=32)
    p.add_argument("--retries", type=int, default=2)
    args = p.parse_args()

    json_key = FIELDS[args.field]["key"]
    tmpl = FIELDS[args.field]["prompt"]
    gbnf = grammar(json_key)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.index:
        reports = read_index(args.index, args.start_index, args.chunk_size)
    elif args.ids_file:
        reports = read_ids(args.db, args.ids_file, args.start_index, args.chunk_size)
    else:
        reports = read_slice(args.db, args.start_index, args.chunk_size)
    end = args.start_index + len(reports)
    print(f"[{args.field}] slice [{args.start_index}, {end}) -> {len(reports)} reports")

    cases: dict[str, dict] = {}
    if args.output.exists():
        try:
            prev = json.loads(args.output.read_text()).get("cases", [])
            cases = {c["hashed_id"]: c for c in prev if c.get("background")}
            print(f"Resuming: {len(cases)} already done.")
        except Exception:
            cases = {}

    client = OpenAI(base_url=args.base_url, api_key="EMPTY", timeout=120.0, max_retries=0)

    def flush():
        meta = {"task": "background", "field": args.field, "json_key": json_key,
                "source": args.index or args.db,
                "start_index": args.start_index, "end_index": end, "n": len(reports),
                "model": args.model, "quant": os.environ.get("GGUF_QUANT")}
        args.output.write_text(json.dumps({"meta": meta, "cases": list(cases.values())}, indent=1))

    done = 0
    for hid, text in reports:
        if hid in cases:
            done += 1
            continue
        text = (text or "").strip()
        if not text:
            cases[hid] = {"hashed_id": hid, "background": None, "error": "empty report"}
            done += 1
            continue
        t0 = time.time()
        result = err = None
        for attempt in range(args.retries + 1):
            try:
                resp = request(client, args.model, tmpl.replace("{report}", text), gbnf, args.max_tokens)
                result = json.loads(resp.choices[0].message.content)
                break
            except Exception as e:  # noqa: BLE001
                err = str(e)[:200]
                if attempt == args.retries:
                    result = None
        cases[hid] = {"hashed_id": hid,
                      "background": ({"status": result[json_key]} if result else None),
                      "report_words": len(text.split()),
                      "inference_seconds": round(time.time() - t0, 2)}
        if result is None:
            cases[hid]["error"] = err
        done += 1
        if done % 50 == 0:
            flush()
            print(f"  {done}/{len(reports)} done", flush=True)

    flush()
    ok = sum(1 for c in cases.values() if c.get("background"))
    print(f"DONE [{args.field}]: {ok}/{len(reports)} annotated -> {args.output}")


if __name__ == "__main__":
    main()
