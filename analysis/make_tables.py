#!/usr/bin/env python3
"""Generate the master numbers tables for results_prompt_variants.md.

Everything is computed from results/*.json (our runs), the released Mistral
prediction DB (external baseline), and the sg_labels inside our JSONs (human
second annotator). Prints GitHub-flavoured markdown tables for:
  - Pooled (Zoe+Maria, n=1994)
  - Zoe (n=1495)
  - Maria (n=499)

Metric: Core F1 vs LD per category (binary present/absent, score >= 3), plus
"Fully-correct" = reports where all five present/absent calls match LD.

Run:  python -m analysis.make_tables       # print
      python -m analysis.make_tables > /tmp/tables.md
"""
from __future__ import annotations

import importlib
import os
import sqlite3

from analysis.full_lib import KEYS, LABELS, load

pres = lambda v: v >= 3

MIST_DB = ("/project/6019337/databases/eeg_fha/release_001/"
           "eeg_reports_release_001_mistral_public_250825.db")
FIELD_COL = {"abnormality": "Abnormality", "focal_epileptiform_activity": "Focal Epi",
             "generalized_epileptiform_activity": "Gen Epi",
             "focal_non_epileptiform_activity": "Focal Non-epi",
             "generalized_non_epileptiform_activity": "Gen Non-epi"}


def _f1(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def stats(pairs):
    """pairs: iterable of (pred_dict, ld_dict). Returns (f1_per_cat, fully_correct, n)."""
    pairs = [(p, l) for p, l in pairs]
    f1s = []
    for k in KEYS:
        tp = fp = fn = 0
        for pd, ld in pairs:
            m, g = pres(pd[k]), pres(ld[k])
            tp += m and g; fp += m and not g; fn += (not m) and g
        f1s.append(_f1(tp, fp, fn))
    full = sum(1 for pd, ld in pairs if all(pres(pd[k]) == pres(ld[k]) for k in KEYS))
    return f1s, full, len(pairs)


def our_pairs(prompt, quant, datasets):
    for ds in datasets:
        for c in load(ds, prompt, quant):
            yield {k: c["model"][k]["pred"] for k in KEYS}, c["ld_labels"]


def human_pairs(quant, datasets):
    # SG (second annotator) vs LD, read from the sg_labels stored in our JSONs.
    for ds in datasets:
        for c in load(ds, "v1", quant):
            yield c["sg_labels"], c["ld_labels"]


def mistral_pairs(datasets):
    conn = sqlite3.connect(f"file:{MIST_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cols = ", ".join(f'"{c}" AS "{k}"' for k, c in FIELD_COL.items())
    mist = {r["hid"]: {k: int(r[k]) for k in KEYS}
            for r in conn.execute(
                f'SELECT Hashed_ReportURN AS hid, {cols} FROM classifications')}
    import core.cohort as co
    for ds in datasets:
        os.environ["DATASET"] = ds; importlib.reload(co)
        ld = co.load_db(co.LD_DB); sg = co.load_db(co.SG_DB)
        for h in co.build_cohort(sg, ld):
            yield mist[h], {k: ld[h]["labels"][k] for k in KEYS}


ROWS = [("MedGemma-27B v1", "Q2_K", "v1", "Q2"),
        ("MedGemma-27B v1", "Q4_K_S", "v1", "Q4"),
        ("MedGemma-27B v2", "Q2_K", "v2", "Q2"),
        ("MedGemma-27B v2", "Q4_K_S", "v2", "Q4"),
        ("MedGemma-27B v3", "Q2_K", "v3", "Q2"),
        ("MedGemma-27B v3", "Q4_K_S", "v3", "Q4"),
        ("MedGemma-27B v4", "Q2_K", "v4", "Q2"),
        ("MedGemma-27B v4", "Q4_K_S", "v4", "Q4")]


def table(title, datasets, n):
    head = "| Model | Prompt | Quant | " + " | ".join(LABELS) + " | Fully-correct |"
    sep = "|" + "---|" * (3 + len(LABELS) + 1)
    lines = [f"### {title}  (n={n})", "", head, sep]
    for model, quant_lbl, pv, q in ROWS:
        f1s, full, _ = stats(our_pairs(pv, q, datasets))
        nums = " | ".join(f"{x:.2f}" for x in f1s)
        pv_lbl = pv
        lines.append(f"| {model.replace(' '+pv, '')} | {pv_lbl} | {quant_lbl} | {nums} | {full} |")
    # external baseline + human
    f1s, full, _ = stats(mistral_pairs(datasets))
    lines.append("| *Mistral-7B (paper)* | — | — | " +
                 " | ".join(f"*{x:.2f}*" for x in f1s) + f" | *{full}* |")
    f1s, full, _ = stats(human_pairs("Q2", datasets))
    lines.append("| *Human (SG, 2nd annotator)* | — | — | " +
                 " | ".join(f"*{x:.2f}*" for x in f1s) + f" | *{full}* |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(table("Pooled — Zoe + Maria", ("zoe", "maria"), 1994))
    print(table("Zoe (in-distribution)", ("zoe",), 1495))
    print(table("Maria (out-of-distribution)", ("maria",), 499))
