#!/usr/bin/env python3
"""Assemble the master comparison table (markdown) for the consolidated report, from the saved
summaries: slowing (results/harvard/slowing_gold.json), burst-suppression
(results/harvard/burst_vs_harvard.json), and the FHA/Harvard distributions
(results/slowing/fha_summary.json, results/background/dist_summary.json).

Run: python -m analysis.master_table
"""
from __future__ import annotations

import json
import math

SLOW = json.load(open("results/harvard/slowing_gold.json"))
BURST = json.load(open("results/harvard/burst_vs_harvard.json"))
FHA_SLOW = json.load(open("results/slowing/fha_summary.json"))
DIST = json.load(open("results/background/dist_summary.json"))
COH = ["MGH", "BWH", "BCH"]


def pct(node, key="ours_present"):
    return 100 * node[key] / node["n"]


def rec(node):
    r = node["our_recall_on_verified"]
    # round half up so a boundary like 64.5% reads 65%, matching the per-field reports
    return f"{math.floor(100*r + 0.5)}% ({node['verified_present_labeled']})" if r is not None else "—"


def comparison_rows():
    rows = []
    src = [("focal slowing", SLOW["focal"]), ("generalized slowing", SLOW["generalized"]),
           ("burst-suppression", BURST["burst_suppression"])]
    for name, data in src:
        for c in COH:
            d = data[c]
            rows.append(f"| {name} — {c} | {pct(d):.1f}% | {100*d['harv_present_all']/d['n']:.1f}% | "
                        f"{100*d['agree_all']:.0f}% | {d['kappa_all']:.2f} | {d['kappa_report']:.2f} | {rec(d)} |")
    return rows


def main():
    print("### Master comparison (Harvard) — fields with a Harvard column\n")
    print("| field — hospital | ours present | Harvard present | agreement | κ | κ text-only | our recall on verified |")
    print("|---|---|---|---|---|---|---|")
    print("\n".join(comparison_rows()))

    print("\n### Present-rate on Fraser Health (our labels; no ground truth there)\n")
    print("| field | present | explicitly_absent | not_mentioned |")
    print("|---|---|---|---|")
    for name, key in [("focal slowing", "focal"), ("generalized slowing", "generalized")]:
        d = FHA_SLOW[f"dist_{key}"]
        print(f"| {name} | {d['present'][1]}% | {d['explicitly_absent'][1]}% | {d['not_mentioned'][1]}% |")
    for name, key in [("discontinuous", "discontinuous"), ("burst-suppression", "burst_suppression"),
                      ("suppressed", "suppressed")]:
        d = DIST["FHA"][key]
        print(f"| {name} | {d['present'][1]}% | {d['explicitly_absent'][1]}% | {d['not_mentioned'][1]}% |")


if __name__ == "__main__":
    main()
