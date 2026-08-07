#!/usr/bin/env python3
"""Pool Zoe (1495) + Maria (499) = 1994 and compare our configs vs the paper's
Mistral-7B using Mistral's ACTUAL predictions on the same reports.

F1 is pooled correctly (sum raw TP/FP/FN across both datasets, then compute F1 —
never averaging the two datasets' F1). Verifies alignment before trusting it.
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIST_DB = ("/project/6019337/databases/eeg_fha/release_001/"
           "eeg_reports_release_001_mistral_public_250825.db")
FIELDS = [
    ("abnormality", "Abnormality"),
    ("focal_epileptiform_activity", "Focal Epi"),
    ("generalized_epileptiform_activity", "Gen Epi"),
    ("focal_non_epileptiform_activity", "Focal Non-epi"),
    ("generalized_non_epileptiform_activity", "Gen Non-epi"),
]
KEYS = [k for k, _ in FIELDS]
RESULTS = {
    ("zoe", "v1", "Q2"): "q2_cpu_full_n1495",
    ("zoe", "v1", "Q4"): "cpu_q4_k_s_full_n1495",
    ("zoe", "v2", "Q2"): "zoe_v2_cpu_q2_k_full_n1495",
    ("zoe", "v2", "Q4"): "zoe_v2_cpu_q4_k_s_full_n1495",
    ("maria", "v1", "Q2"): "maria_cpu_q2_k_full_n499",
    ("maria", "v1", "Q4"): "maria_cpu_q4_k_s_full_n499",
    ("maria", "v2", "Q2"): "maria_v2_cpu_q2_k_full_n499",
    ("maria", "v2", "Q4"): "maria_v2_cpu_q4_k_s_full_n499",
}
pres = lambda v: v >= 3


def mistral_preds():
    c = sqlite3.connect(f"file:{MIST_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    cols = ", ".join(f'"{col}" AS "{k}"' for k, col in FIELDS)
    out = {}
    for r in c.execute(f'SELECT Hashed_ReportURN AS hid, {cols} FROM classifications'):
        out[r["hid"]] = {k: int(r[k]) for k in KEYS}
    return out


def cohort_order(ds):
    import core.cohort as co
    os.environ["DATASET"] = ds
    importlib.reload(co)
    ld = co.load_db(co.LD_DB); sg = co.load_db(co.SG_DB)
    return co.build_cohort(sg, ld), ld, sg


def f1_from_counts(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def main():
    mist = mistral_preds()
    # build aligned records per dataset: list of (ld_labels, mistral_labels)
    # plus our model preds per config
    data = {}   # ds -> {"ld":[...], "mist":[...], "n":int}
    align_ok = True
    for ds in ("zoe", "maria"):
        cohort, ld, sg = cohort_order(ds)
        ld_labels = [{k: ld[h]["labels"][k] for k in KEYS} for h in cohort]
        sg_labels = [{k: sg[h]["labels"][k] for k in KEYS} for h in cohort]
        mist_labels = [mist[h] for h in cohort]
        # verify our result JSON's ld_labels match cohort order (any config)
        sample = json.loads((ROOT / "results" / f"{RESULTS[(ds,'v1','Q2')]}.json").read_text())["cases"]
        mism = sum(1 for i, c in enumerate(sample)
                   if c["ld_labels"] != ld_labels[i])
        if mism:
            # our result JSONs use within-file (model, ld) pairs, so JSON order
            # need not match cohort order — this only affects the Mistral join,
            # which uses cohort order for BOTH mist and ld (consistent).
            print(f"note: {ds} JSON order differs from cohort in {mism} rows "
                  f"(harmless — our F1 uses within-file pairs).")
        data[ds] = {"ld": ld_labels, "sg": sg_labels,
                    "mist": mist_labels, "cohort": cohort}
    print()

    def pool_pairs(pairs):
        """pairs: iterable of (pred_labels, ld_labels). Order-independent."""
        cnt = {k: [0, 0, 0] for k in KEYS}  # tp, fp, fn
        full = tot = 0
        for pd, ldl in pairs:
            ok = True
            for k in KEYS:
                m, g = pres(pd[k]), pres(ldl[k])
                if m and g: cnt[k][0] += 1
                elif m and not g: cnt[k][1] += 1
                elif (not m) and g: cnt[k][2] += 1
                if m != g: ok = False
            full += ok; tot += 1
        return {k: f1_from_counts(*cnt[k]) for k in KEYS}, full, tot

    def our_pairs(prompt, quant):
        for ds in ("zoe", "maria"):
            cases = json.loads((ROOT / "results" / f"{RESULTS[(ds,prompt,quant)]}.json").read_text())["cases"]
            for c in cases:  # within-file pairs are always correctly aligned
                yield {k: c["model"][k]["pred"] for k in KEYS}, c["ld_labels"]

    def mist_pairs():
        for ds in ("zoe", "maria"):
            for md, ldl in zip(data[ds]["mist"], data[ds]["ld"]):
                yield md, ldl

    configs = [("v1", "Q2"), ("v1", "Q4"), ("v2", "Q2"), ("v2", "Q4")]
    print(f"POOLED (Zoe 1495 + Maria 499 = 1994) core F1 vs LD:")
    hdr = f"{'config':10s} " + " ".join(f"{lab:>13s}" for _, lab in FIELDS) + f" {'fullOK':>9s}"
    print(hdr)
    cache = {}
    for pr, q in configs:
        pf, fk, ft = pool_pairs(our_pairs(pr, q))
        cache[(pr, q)] = (pf, fk)
        print(f"{pr}-{q:8s} " + " ".join(f"{pf[k]:13.3f}" for k in KEYS) + f" {fk:5d}/{ft}")
    mf, mfk, mft = pool_pairs(mist_pairs())
    print(f"{'Mistral-7B':10s} " + " ".join(f"{mf[k]:13.3f}" for k in KEYS) + f" {mfk:5d}/{mft}")

    # pick best config by fully-correct
    best = max(configs, key=lambda c: cache[c][1])
    print(f"\nBEST config by fully-correct: {best[0]}-{best[1]} ({cache[best][1]}/1994)")

    # Core (binary present/absent) vs Certainty-adjusted (exact 1-4) accuracy
    def accs(pairs):
        core = {k: 0 for k in KEYS}; cert = {k: 0 for k in KEYS}; n = 0
        for pd, ldl in pairs:
            n += 1
            for k in KEYS:
                core[k] += pres(pd[k]) == pres(ldl[k])
                cert[k] += pd[k] == ldl[k]
        return {k: core[k] / n for k in KEYS}, {k: cert[k] / n for k in KEYS}

    def human_pairs():
        for ds in ("zoe", "maria"):
            for sg, ldl in zip(data[ds]["sg"], data[ds]["ld"]):
                yield sg, ldl

    raters = {
        "ours": accs(our_pairs(best[0], best[1])),
        "mistral": accs(mist_pairs()),
        "human": accs(human_pairs()),
    }
    print("\nCore accuracy (binary) vs Certainty accuracy (exact 1-4), pooled:")
    for lab_kind, idx in (("CORE ", 0), ("CERT ", 1)):
        print(f"  {lab_kind}" + "  ".join(
            f"{r}={' '.join(f'{raters[r][idx][k]:.2f}' for k in KEYS)}"
            for r in ("ours", "mistral", "human")))

    # per-dataset Mistral F1 sanity vs paper Table III
    print("\nSanity — Mistral F1 per dataset (ours-computed vs paper Table III):")
    paper = {"zoe": [0.96,0.85,0.71,0.76,0.78], "maria":[0.90,0.81,0.84,0.74,0.54]}
    for ds in ("zoe", "maria"):
        row = []
        for k in KEYS:
            tp=fp=fn=0
            for pd, ldl in zip(data[ds]["mist"], data[ds]["ld"]):
                m,g=pres(pd[k]),pres(ldl[k]); tp+=m and g; fp+=m and not g; fn+=(not m) and g
            row.append(f1_from_counts(tp,fp,fn))
        print(f"  {ds}: ours=" + " ".join(f"{v:.2f}" for v in row) +
              "  paper=" + " ".join(f"{v:.2f}" for v in paper[ds]))

    # export pooled numbers for the chart
    out = {"best": f"{best[0]}-{best[1]}",
           "our_pooled_f1": {k: cache[best][0][k] for k in KEYS},
           "mistral_pooled_f1": {k: mf[k] for k in KEYS},
           "our_full": cache[best][1], "mistral_full": mfk, "n": 1994,
           "core_acc": {r: raters[r][0] for r in raters},
           "cert_acc": {r: raters[r][1] for r in raters}}
    (ROOT / "results" / "pooled_summary.json").write_text(json.dumps(out, indent=2))
    print("\nwrote results/pooled_summary.json")


if __name__ == "__main__":
    main()
