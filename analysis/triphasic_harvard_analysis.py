#!/usr/bin/env python3
"""Analyze the triphasic-wave annotation of the Harvard EEG reports (MGH, BWH, BCH), the same
two prompts we ran on the FHA set. Reports per-hospital status/phenotype distribution, the
short-vs-long stability, and applies the same faithfulness guard (a present/absent call needs
the triphasic token in the report text, else -> not_mentioned). Report text is read from the
HEEDB zips via the cohort indexes, only for the flagged reports (fast).

Run:  python -m analysis.triphasic_harvard_analysis
"""
from __future__ import annotations

import glob
import json
import re
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import INK, INK2, GRID, BLUE, ORANGE, GREEN

COHORTS = ["MGH", "BWH", "BCH"]
HCOL = {"MGH": BLUE, "BWH": ORANGE, "BCH": GREEN}
STATUSES = ["present", "explicitly_absent", "not_mentioned"]
PHENOS = ["unspecified", "typical", "atypical", "mixed"]
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
TERM = re.compile(r"tri[ \-]*phasic|3[ \-]*phasic", re.I)


def load_variant(coh, variant):
    cases = {}
    for f in sorted(glob.glob(f"results/triphasic_harvard/{coh}/{variant}/labels_*.json")):
        for c in json.load(open(f)).get("cases", []):
            cases[c["hashed_id"]] = c
    return cases


def text_lookup(coh, ids):
    """report_id -> normalized text, for the given ids only (read from HEEDB zips)."""
    idx = json.load(open(f"results/harvard/{coh}_index.json"))
    zips = idx["zips"]
    loc = {rid: (zi, inner) for rid, zi, inner in idx["reports"]}
    zc = {}
    out = {}
    for rid in ids:
        if rid not in loc:
            out[rid] = ""
            continue
        zi, inner = loc[rid]
        try:
            if zi not in zc:
                zc[zi] = zipfile.ZipFile(zips[zi])
            out[rid] = re.sub(r"\s+", " ", zc[zi].open(inner).read().decode("utf-8", "replace"))
        except Exception:
            out[rid] = ""
    return out


def _kappa(a, b, c, d):
    n = a + b + c + d
    if n == 0:
        return 0.0
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def guard(cases, txt):
    """Return {id: status} with present/absent flipped to not_mentioned when no term in text."""
    out = {}
    flips = 0
    for hid, c in cases.items():
        t = c.get("triphasic")
        if not t:
            out[hid] = None
            continue
        st = t["status"]
        if st in ("present", "explicitly_absent") and not TERM.search(txt.get(hid, "")):
            st = "not_mentioned"
            flips += 1
        out[hid] = (st, t["phenotype"])
    return out, flips


def analyze():
    res = {}
    pooled = {"present": 0, "explicitly_absent": 0, "not_mentioned": 0}
    pooled_ph = {p: 0 for p in PHENOS}
    pool_conf = [0, 0, 0, 0]      # present/absent kappa cells across cohorts
    pool_exact = 0
    pool_n = 0
    for coh in COHORTS:
        s_raw = load_variant(coh, "short")
        l_raw = load_variant(coh, "long")
        ids = set(s_raw) | set(l_raw)
        # flagged reports (either variant present/absent) need text for the guard
        flagged = {h for h in ids
                   if (s_raw.get(h, {}).get("triphasic") or {}).get("status") in ("present", "explicitly_absent")
                   or (l_raw.get(h, {}).get("triphasic") or {}).get("status") in ("present", "explicitly_absent")}
        txt = text_lookup(coh, flagged)
        sg, sf = guard(s_raw, txt)
        lg, lf = guard(l_raw, txt)

        sc = {k: 0 for k in STATUSES}
        for v in sg.values():
            if v:
                sc[v[0]] += 1
        ph = {p: 0 for p in PHENOS}
        for v in sg.values():
            if v and v[0] == "present":
                ph[v[1]] += 1

        # stability short vs long
        common = [h for h in ids if sg.get(h) and lg.get(h)]
        exact = a = b = c = d = 0
        for h in common:
            s, l = sg[h][0], lg[h][0]
            if s == l:
                exact += 1
            sm, lm = s != "not_mentioned", l != "not_mentioned"
            if sm and lm: a += 1
            elif sm: b += 1
            elif lm: c += 1
            else: d += 1
        res[coh] = {"n": len(common), "status": sc, "pheno": ph,
                    "present_pct": 100 * sc["present"] / len(common),
                    "exact_pct": 100 * exact / len(common),
                    "kappa": _kappa(a, b, c, d), "flips": sf + lf}
        for k in STATUSES:
            pooled[k] += sc[k]
        for p in PHENOS:
            pooled_ph[p] += ph[p]
        for i, v in enumerate((a, b, c, d)):
            pool_conf[i] += v
        pool_exact += exact
        pool_n += len(common)
    res["Pooled"] = {"n": pool_n, "status": pooled, "pheno": pooled_ph,
                     "present_pct": 100 * pooled["present"] / pool_n,
                     "exact_pct": 100 * pool_exact / pool_n,
                     "kappa": _kappa(*pool_conf), "flips": sum(res[c]["flips"] for c in COHORTS)}
    return res


def _bare(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0, colors=INK2, labelsize=9); ax.set_axisbelow(True)


def chart_prevalence(res):
    """Present-call rate per hospital, with the FHA rate as a reference line."""
    rows = ["MGH", "BWH", "BCH", "Pooled"]
    fig, ax = plt.subplots(figsize=(8.8, 3.9))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(rows)))[::-1]
    vals = [res[r]["present_pct"] for r in rows]
    cols = [HCOL.get(r, INK2) for r in rows]
    ax.barh(y, vals, color=cols, height=0.6, zorder=3, edgecolor="white")
    for yi, r in zip(y, rows):
        ax.text(res[r]["present_pct"] + 0.02, yi, f"{res[r]['present_pct']:.2f}%  "
                f"({res[r]['status']['present']:,})", va="center", ha="left",
                color=INK, fontsize=9.5, fontweight="bold")
    ax.axvline(1.0, color=INK2, lw=1, ls="--", zorder=2)
    ax.text(1.0, len(rows) - 0.4, " FHA ≈ 1.0%", color=INK2, fontsize=8.5, va="top")
    ax.set_yticks(y); ax.set_yticklabels(rows, fontsize=12, color=INK)
    ax.set_xlim(0, max(vals) * 1.5 + 0.3)
    ax.set_xlabel("Reports called triphasic present, %", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.set_title("Triphasic waves across the Harvard hospitals",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=22)
    ax.text(0, 1.04, "MedGemma-27B, short prompt (guarded) · dashed line = FHA prevalence",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "triphasic_harvard_prevalence.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved triphasic_harvard_prevalence.png")


def chart_stability(res):
    """Short vs long exact status agreement + kappa per hospital."""
    rows = ["MGH", "BWH", "BCH", "Pooled"]
    fig, ax = plt.subplots(figsize=(8.8, 3.9))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(rows)))[::-1]
    for yi, r in zip(y, rows):
        ax.plot([100 * res[r]["kappa"], res[r]["exact_pct"]], [yi, yi], color=GRID, lw=6,
                solid_capstyle="round", zorder=1)
    ax.scatter([100 * res[r]["kappa"] for r in rows], y, s=150, facecolor="white",
               edgecolor=BLUE, linewidth=2, zorder=3, label="present/absent κ ×100")
    ax.scatter([res[r]["exact_pct"] for r in rows], y, s=150, color=BLUE, zorder=3,
               edgecolor="white", linewidth=1.2, label="exact status agreement, %")
    for yi, r in zip(y, rows):
        ax.text(res[r]["exact_pct"] + 0.4, yi, f"{res[r]['exact_pct']:.1f}", va="center",
                ha="left", color=BLUE, fontsize=9, fontweight="bold")
        ax.text(100 * res[r]["kappa"] - 0.6, yi, f"κ={res[r]['kappa']:.2f}", va="center",
                ha="right", color=INK2, fontsize=9, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(rows, fontsize=12, color=INK)
    ax.set_xlim(60, 104)
    ax.set_xlabel("Short vs long agreement  (● exact status   ○ κ×100)", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.legend(frameon=False, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, -0.26), ncol=2)
    ax.set_title("Prompt stability on the Harvard reports",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=22)
    ax.text(0, 1.04, "Do the two prompts give the same triphasic status?",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "triphasic_harvard_stability.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved triphasic_harvard_stability.png")


if __name__ == "__main__":
    res = analyze()
    print("\n| Hospital | reports | present | present% | expl_absent | not_mentioned | "
          "short↔long exact | κ | guard flips |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in ["MGH", "BWH", "BCH", "Pooled"]:
        s = res[r]
        print(f"| {r} | {s['n']:,} | {s['status']['present']:,} | {s['present_pct']:.2f}% | "
              f"{s['status']['explicitly_absent']:,} | {s['status']['not_mentioned']:,} | "
              f"{s['exact_pct']:.2f}% | {s['kappa']:.3f} | {s['flips']} |")
    print("\nPhenotype (pooled, of present, short prompt): " +
          "  ".join(f"{p} {res['Pooled']['pheno'][p]}" for p in PHENOS))
    chart_prevalence(res)
    chart_stability(res)
