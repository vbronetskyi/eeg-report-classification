#!/usr/bin/env python3
"""Annotate EEG reports for **focal slowing** and **generalized slowing** (each as its own,
separate label) with MedGemma-27B under a grammar that guarantees the schema.

One field per run (--field focal | generalized), each a single three-way status:
  focal_slowing        : present | explicitly_absent | not_mentioned
  generalized_slowing  : present | explicitly_absent | not_mentioned

The prompts are the PI's detailed definitions, used essentially verbatim; the GBNF grammar
constrains the output to exactly one valid JSON object, so the model cannot emit anything but a
legal status. Same plumbing (slice / Harvard index / id-file reading, resume, meta) as the
triphasic run, so the outputs line up with the earlier releases.

Run (inside the Slurm job, after llama-server is up):
    python -m cpu.slowing --field focal --start-index 0 --chunk-size 2000 \
        --db /project/6019337/vvakorin/incoming/processed_reports_240325.db \
        --base-url http://127.0.0.1:PORT/v1 --model medgemma \
        --output results/slowing/focal/labels_00000_01999.json
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

SYSTEM = "You are an expert clinical EEG report classifier."

FOCAL = """Task: Determine whether the EEG report describes focal slowing (localized, regional, \
lateralized, or multifocal slowing of cerebral activity).

Return exactly one JSON object:

{"focal_slowing": "present | explicitly_absent | not_mentioned"}

Classification rules:

present: The report states that slowing is focal, regional, lateralized, hemispheric, or \
multifocal. This includes localized theta or delta activity described as intermittent, \
persistent, continuous, rhythmic, or polymorphic.
Examples: "left temporal slowing," "intermittent right frontotemporal theta-delta activity," \
"focal polymorphic delta slowing," "slowing over the left hemisphere," or "independent \
bitemporal slowing."
Focal slowing remains present if the report says it is subtle, rare, mild, occasional, or of \
uncertain significance.

explicitly_absent: The report directly states that focal slowing is absent.
Examples: "no focal slowing," "no focal or lateralized slowing," "no focal cerebral \
dysfunction," or "no focal abnormalities."
A statement such as "no focal epileptiform discharges" does not establish the absence of focal \
slowing.

not_mentioned: The report neither describes focal slowing nor explicitly states that it is \
absent.
Use this category for normal EEG reports that do not specifically address focal slowing.
Generalized or diffuse slowing alone is not focal slowing.
Do not infer focal slowing from a diagnosis, symptoms, imaging findings, prior EEGs, focal \
seizures, asymmetry without stated slowing, or focal epileptiform discharges.
Do not classify attenuation, suppression, voltage asymmetry, breach rhythm, or reduced \
organization as focal slowing unless the report explicitly describes localized slow activity.

Additional instructions:
Use only the information stated in the supplied report.
Interpret negation and uncertainty carefully.
Give priority to the final EEG interpretation or impression when it resolves ambiguity in the \
descriptive section.
If both presence and absence are stated, use the statement referring to the current recording \
and the most specific final interpretation. If a genuine contradiction remains, classify as \
"present" because focal slowing was documented.
Do not provide explanations, evidence, Markdown, or any text outside the JSON object.

EEG report:

<EEG_REPORT>
{report}
</EEG_REPORT>"""

GENERALIZED = """Task: Determine whether the EEG report describes generalized slowing—diffuse \
or bilaterally synchronous slowing affecting the background or broad regions of both \
hemispheres.

Return exactly one JSON object:

{"generalized_slowing": "present | explicitly_absent | not_mentioned"}

Classification rules:

present: The report describes generalized, diffuse, global, or bilaterally synchronous slowing.
Examples: "mild diffuse slowing," "generalized theta-delta slowing," "diffusely slow \
background," "background slower than expected for age," "generalized polymorphic delta \
activity," or "generalized rhythmic delta activity."
Include an abnormally slow posterior dominant rhythm when the report identifies it as abnormal \
for the patient's age or as evidence of generalized slowing.
Generalized slowing remains present when described as mild, subtle, intermittent, occasional, \
or nonspecific.
Focal slowing may coexist with generalized slowing; classify as present if generalized slowing \
is also documented.

explicitly_absent: The report directly states that generalized or diffuse slowing is absent.
Examples: "no generalized slowing," "no diffuse background slowing," or "no evidence of \
diffuse cerebral dysfunction."
A statement that the background is "normal," "age appropriate," or "well organized" counts as \
explicitly absent only when it clearly characterizes the entire current EEG background as \
normal.
"No generalized epileptiform discharges" does not establish the absence of generalized slowing.

not_mentioned: The report neither describes generalized slowing nor clearly states that it is \
absent.
Focal, regional, hemispheric, or multifocal slowing alone is not generalized slowing.
Normal slowing associated only with drowsiness or sleep is not generalized slowing.
Do not infer generalized slowing solely from encephalopathy, altered mental status, dementia, \
medication use, imaging findings, or another clinical diagnosis.
Do not classify low voltage, attenuation, suppression, discontinuity, poor reactivity, or poor \
organization as generalized slowing unless abnormally slow activity is also described.

Additional instructions:
1. Use only information stated in the supplied EEG report.
2. Interpret negation, uncertainty, and historical references carefully.
3. Findings from previous EEGs do not describe the current recording unless the report states \
that they persist.
4. Give priority to the final interpretation or impression when it resolves ambiguity in the \
descriptive section.
5. If presence and absence are both stated, use the statement referring to the current \
recording and the most specific final interpretation. If a genuine contradiction remains, \
classify as "present" because generalized slowing was documented.
6. Return no explanation, evidence, Markdown, or text outside the JSON object.

EEG report:

<EEG_REPORT>
{report}
</EEG_REPORT>"""

FIELDS = {
    "focal":       {"key": "focal_slowing",       "prompt": FOCAL},
    "generalized": {"key": "generalized_slowing", "prompt": GENERALIZED},
}


def grammar(json_key):
    # exactly one JSON object, one of the three legal statuses — nothing else can be emitted
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
    """(report_id, text) for a Harvard (HEEDB) cohort index slice — reads report text straight
    from the zip dumps, so the same prompts run over the Harvard hospitals, not just the FHA DB."""
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
        except Exception:  # noqa: BLE001 — unreadable entry -> empty, recorded downstream
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
    p = argparse.ArgumentParser(description="Focal / generalized slowing annotation of EEG reports.")
    p.add_argument("--field", choices=FIELDS, required=True)
    p.add_argument("--start-index", type=int, required=True)
    p.add_argument("--chunk-size", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--db", default="/project/6019337/vvakorin/incoming/processed_reports_240325.db")
    p.add_argument("--ids-file", default=None, help="optional: run only these hashed ids (one per line)")
    p.add_argument("--index", default=None, help="optional: a Harvard cohort index json (read text from HEEDB zips instead of the FHA DB)")
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
            cases = {c["hashed_id"]: c for c in prev if c.get("slowing")}
            print(f"Resuming: {len(cases)} already done.")
        except Exception:
            cases = {}

    client = OpenAI(base_url=args.base_url, api_key="EMPTY", timeout=120.0, max_retries=0)

    def flush():
        meta = {"task": "slowing", "field": args.field, "json_key": json_key,
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
            cases[hid] = {"hashed_id": hid, "slowing": None, "error": "empty report"}
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
                      "slowing": ({"status": result[json_key]} if result else None),
                      "report_words": len(text.split()),
                      "inference_seconds": round(time.time() - t0, 2)}
        if result is None:
            cases[hid]["error"] = err
        done += 1
        if done % 50 == 0:
            flush()
            print(f"  {done}/{len(reports)} done", flush=True)

    flush()
    ok = sum(1 for c in cases.values() if c.get("slowing"))
    print(f"DONE [{args.field}]: {ok}/{len(reports)} annotated -> {args.output}")


if __name__ == "__main__":
    main()
