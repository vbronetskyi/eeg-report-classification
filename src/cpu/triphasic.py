#!/usr/bin/env python3
"""Annotate Fraser Health EEG reports for **triphasic waves** with MedGemma-27B under a
grammar that guarantees the schema and the status->phenotype consistency.

Two fields per report:
  triphasic_status    : present | explicitly_absent | not_mentioned
  triphasic_phenotype : typical | atypical | mixed | unspecified   (only when present;
                        otherwise not_applicable)

Two prompt variants are provided — a concise `short` one and a `long` one (the PI's detailed
definitions) — so we can run both and check how stable the annotations are across prompts.
The GBNF grammar makes invalid outputs (bad enum, illegal status/phenotype pair) impossible,
so neither prompt needs to spell out the output format or the valid combinations.

Run (inside the Slurm job, after llama-server is up):
    python -m cpu.triphasic --variant short --start-index 0 --chunk-size 2000 \
        --db /project/6019337/vvakorin/incoming/processed_reports_240325.db \
        --base-url http://127.0.0.1:PORT/v1 --model medgemma \
        --output results/triphasic/short/labels_00000_01999.json
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

SYSTEM = "You are an expert annotator of clinical electroencephalography (EEG) reports."

# Only one of the three top-level branches can be produced, and the phenotype is constrained
# by the status — so illegal combinations cannot be generated.
GRAMMAR = r'''
root ::= present | absent | notmentioned
present ::= "{\"triphasic_status\": \"present\", \"triphasic_phenotype\": \"" pheno "\"}"
absent ::= "{\"triphasic_status\": \"explicitly_absent\", \"triphasic_phenotype\": \"not_applicable\"}"
notmentioned ::= "{\"triphasic_status\": \"not_mentioned\", \"triphasic_phenotype\": \"not_applicable\"}"
pheno ::= "typical" | "atypical" | "mixed" | "unspecified"
'''

SHORT = """Annotate this EEG report for triphasic waves. Decide only from what the report \
explicitly states. Do not infer from diagnoses, medications, encephalopathy, or generalized \
periodic discharges.

triphasic_status
- present: the report explicitly describes triphasic waves or triphasic morphology (including \
"GPDs / periodic discharges with triphasic morphology" or "triphasic-appearing discharges").
- explicitly_absent: the report explicitly states they are absent (e.g. "no triphasic waves", \
"periodic discharges without triphasic morphology").
- not_mentioned: the report never mentions triphasic waves/morphology. Slowing, encephalopathy, \
GPDs, spikes, or seizures without the word triphasic are not_mentioned.

triphasic_phenotype (only when status is present; otherwise not_applicable)
- typical: called typical, or a classical picture — generalized/bilateral, symmetric, \
frontal-predominant positivity, at or below 2 Hz, smooth contour, anterior-posterior lag, \
state/stimulus dependence. Encephalopathy alone is not enough.
- atypical: called atypical, or clearly non-classical — asymmetry/lateralization, focal, \
prominent negativity, sharp/spiky, above 2 Hz, no lag, continuous, evolving. Coexisting \
epilepsy/seizures alone is not enough.
- mixed: the report explicitly describes both typical and atypical triphasic waves in the \
same recording.
- unspecified: present but too little morphology to choose; default here when unsure.

EEG report:
{report}"""

LONG = """Your task is to determine whether the EEG report explicitly describes triphasic \
waves or triphasic morphology and, when present, to characterize the reported triphasic \
phenotype. This is annotation of the written report, not independent diagnosis. Base every \
decision only on information explicitly contained in the report. Do not infer findings that \
are not stated. Do not use general medical knowledge, diagnoses, medications, laboratory \
abnormalities, or expected associations to infer that triphasic waves are present or absent.

Triphasic status
Assign present when the report explicitly states that triphasic waves, triphasic complexes, \
triphasic waveforms, triphasic configuration, triphasic morphology, or an equivalent \
triphasic pattern is present. Expressions such as "generalized periodic discharges with \
triphasic morphology", "GPDs with triphasic morphology", "periodic discharges with triphasic \
morphology", and "triphasic-appearing discharges" count as explicit presence.
Assign explicitly_absent only when the report explicitly states that triphasic waves or \
triphasic morphology are absent, e.g. "no triphasic waves", "no triphasic morphology", or \
"generalized periodic discharges without triphasic morphology".
Assign not_mentioned when the report does not explicitly discuss triphasic waves or triphasic \
morphology. A report describing generalized slowing, encephalopathy, periodic discharges, \
generalized periodic discharges, epileptiform discharges, seizures, metabolic abnormalities, \
or altered mental status without explicitly identifying triphasic morphology must be \
not_mentioned. Absence of the term triphasic is not evidence that the pattern was \
physiologically absent; explicitly_absent and not_mentioned stay distinct.

Triphasic phenotype (only when status is present)
Assign typical when the report explicitly identifies the pattern as typical, or gives enough \
morphological description for a predominantly classical phenotype: generalized or bilateral \
distribution, relative symmetry and synchrony, frontal or frontocentral predominance, \
prominent frontal positivity, smooth or blunted contour, frequency at or below 2 Hz, \
anterior-posterior (or posterior-anterior) lag, regular/monotonous morphology, and dependence \
on stimulation, arousal, drowsiness, or sleep. Not every feature is required, but there must \
be enough explicit information. Do not assign typical merely because the patient has toxic- \
metabolic, hepatic, renal, septic, or another encephalopathy.
Assign atypical when the report explicitly calls the pattern atypical, or describes it as \
predominantly departing from classical: persistent asymmetry or lateralization, focal or \
multifocal distribution, prominent negativity, distinctly sharp or spiky contour, frequency \
above 2 Hz, absent spatial lag, continuous activity without state/stimulus dependence, or \
dynamic/evolving morphology. Do not assign atypical solely because the report also mentions \
epilepsy, epileptiform discharges, seizures, the ictal-interictal continuum, or nonconvulsive \
status epilepticus; it must be supported by explicit morphology or by the report calling it \
atypical.
Assign mixed when the report explicitly describes both typical and atypical triphasic \
characteristics in the same recording. Do not assign mixed merely because a predominantly \
typical pattern has one unusual feature.
Assign unspecified when triphasic waves are explicitly present but there is not enough \
information to decide typical, atypical, or mixed (e.g. "triphasic waves are present", \
"triphasic morphology is noted", "GPDs with triphasic morphology"). When uncertain between \
typical, atypical, and unspecified, prefer unspecified rather than inferring from clinical \
context.

Important distinctions
Generalized periodic discharges are not automatically triphasic; without an explicit triphasic \
reference, classify not_mentioned. Diffuse or generalized slowing is not automatically \
triphasic. Encephalopathy, renal/hepatic failure, sepsis, medication toxicity, delirium, coma, \
or altered mental status must not be used to infer triphasic waves. An epileptiform pattern \
with three phases is not triphasic unless the report explicitly says triphasic morphology. The \
words biphasic, polyphasic, periodic, sharp, or generalized alone do not establish triphasic \
morphology. If triphasic terminology appears only in a differential and the report says the \
pattern is not present, use explicitly_absent; if the wording only raises the possibility \
without establishing presence or absence, classify conservatively by what is explicitly \
stated. Prioritize faithful extraction of the neurologist's documented interpretation over \
independent clinical reasoning.

EEG report:
{report}"""

PROMPTS = {"short": SHORT, "long": LONG}


def read_slice(db, start, size):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute(
        'SELECT "Hashed ID", "Report" FROM reports ORDER BY rowid LIMIT ? OFFSET ?',
        (size, start)).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]


def read_index(index_file, start, size):
    """(report_id, text) for a Harvard (HEEDB) cohort index slice — reads the report text
    straight from the zip dumps, exactly like cpu.label_harvard. Lets the same triphasic
    prompts run over the Harvard hospitals, not just the FHA DB."""
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
    """(hashed_id, text) for the id-file slice [start, start+size) — for targeted subsets."""
    ids = [ln.strip() for ln in Path(ids_file).read_text().splitlines() if ln.strip()]
    ids = ids[start:start + size]
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    txt = {r[0]: r[1] for r in conn.execute(
        'SELECT "Hashed ID", "Report" FROM reports')}
    conn.close()
    return [(i, txt.get(i)) for i in ids]


def request(client, model, prompt_text, max_tokens):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": prompt_text}],
        temperature=0,
        max_tokens=max_tokens,
        extra_body={"grammar": GRAMMAR},
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Triphasic-wave annotation of FHA reports.")
    p.add_argument("--variant", choices=PROMPTS, required=True)
    p.add_argument("--start-index", type=int, required=True)
    p.add_argument("--chunk-size", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--db", default="/project/6019337/vvakorin/incoming/processed_reports_240325.db")
    p.add_argument("--ids-file", default=None, help="optional: run only these hashed ids (one per line)")
    p.add_argument("--index", default=None, help="optional: a Harvard cohort index json (read text from HEEDB zips instead of the FHA DB)")
    p.add_argument("--model", default="medgemma")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--max-tokens", type=int, default=64)
    p.add_argument("--retries", type=int, default=2)
    args = p.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.index:
        reports = read_index(args.index, args.start_index, args.chunk_size)
    elif args.ids_file:
        reports = read_ids(args.db, args.ids_file, args.start_index, args.chunk_size)
    else:
        reports = read_slice(args.db, args.start_index, args.chunk_size)
    end = args.start_index + len(reports)
    print(f"[{args.variant}] slice [{args.start_index}, {end}) -> {len(reports)} reports")

    cases: dict[str, dict] = {}
    if args.output.exists():
        try:
            prev = json.loads(args.output.read_text()).get("cases", [])
            cases = {c["hashed_id"]: c for c in prev if c.get("triphasic")}
            print(f"Resuming: {len(cases)} already done.")
        except Exception:
            cases = {}

    client = OpenAI(base_url=args.base_url, api_key="EMPTY", timeout=120.0, max_retries=0)
    tmpl = PROMPTS[args.variant]

    def flush():
        meta = {"task": "triphasic", "variant": args.variant,
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
            cases[hid] = {"hashed_id": hid, "triphasic": None, "error": "empty report"}
            done += 1
            continue
        t0 = time.time()
        result = err = None
        for attempt in range(args.retries + 1):
            try:
                resp = request(client, args.model, tmpl.format(report=text), args.max_tokens)
                result = json.loads(resp.choices[0].message.content)
                break
            except Exception as e:  # noqa: BLE001
                err = str(e)[:200]
                if attempt == args.retries:
                    result = None
        cases[hid] = {"hashed_id": hid,
                      "triphasic": ({"status": result["triphasic_status"],
                                     "phenotype": result["triphasic_phenotype"]}
                                    if result else None),
                      "report_words": len(text.split()),
                      "inference_seconds": round(time.time() - t0, 2)}
        if result is None:
            cases[hid]["error"] = err
        done += 1
        if done % 50 == 0:
            flush()
            print(f"  {done}/{len(reports)} done", flush=True)

    flush()
    ok = sum(1 for c in cases.values() if c.get("triphasic"))
    print(f"DONE [{args.variant}]: {ok}/{len(reports)} annotated -> {args.output}")


if __name__ == "__main__":
    main()
