#!/usr/bin/env python3
"""Analyze the full triphasic-wave annotation of the FHA reports (both prompt variants).

Reads the raw per-chunk outputs under results/triphasic/{short,long}/, applies a small
faithfulness guard, and reports:
  - coverage and grammar errors,
  - the status and phenotype distribution (short vs long),
  - how stable the two prompt variants are (exact status agreement + Cohen's kappa),
  - a faithfulness cross-check against the report text.

Faithfulness guard: a `present`/`explicitly_absent` call requires the token to actually
appear in the report (triphasic, tri-phasic, tri phasic, 3-phasic, 3 phasic). When it does
not, the report does not mention triphasic waves, so the call is flipped to `not_mentioned`.
This only ever removes a claim the text does not support; it never invents one. The guarded
labels are written to results/triphasic/clean/{short,long}.json (raw files are left as-is).

Run:  python -m analysis.triphasic_analysis
"""
from __future__ import annotations

import glob
import json
import re
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.full_lib import INK, INK2, GRID, BLUE, ORANGE, GREEN, RED

DB = "/project/6019337/vvakorin/incoming/processed_reports_240325.db"
VARIANTS = ["short", "long"]
VCOL = {"short": BLUE, "long": ORANGE}
STATUSES = ["present", "explicitly_absent", "not_mentioned"]
PHENOS = ["unspecified", "typical", "atypical", "mixed"]
OUT = Path("reports/figures"); OUT.mkdir(parents=True, exist_ok=True)
CLEAN = Path("results/triphasic/clean"); CLEAN.mkdir(parents=True, exist_ok=True)

# permissive term match -> the guard only fires when NO triphasic wording exists at all
TERM = re.compile(r"tri[ \-]*phasic|3[ \-]*phasic", re.I)


def load_variant(variant):
    """report_id -> case, merged across the chunk files (last write wins on overlap)."""
    cases = {}
    for f in sorted(glob.glob(f"results/triphasic/{variant}/labels_[0-9]*.json")):
        for c in json.load(open(f)).get("cases", []):
            cases[c["hashed_id"]] = c
    return cases


def load_text():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    txt = {r[0]: re.sub(r"\s+", " ", r[1] or "") for r in
           con.execute('SELECT "Hashed ID", "Report" FROM reports')}
    con.close()
    return txt


def apply_guard(cases, txt):
    """Flip present/explicitly_absent -> not_mentioned when the term is not in the text.
    Returns (guarded_cases_list, n_flipped)."""
    flipped = 0
    out = []
    for hid, c in cases.items():
        tri = c.get("triphasic")
        g = dict(c)
        if tri and tri["status"] in ("present", "explicitly_absent") \
                and not TERM.search(txt.get(hid, "")):
            g["triphasic"] = {"status": "not_mentioned", "phenotype": "not_applicable"}
            g["guarded_from"] = tri["status"]
            flipped += 1
        out.append(g)
    return out, flipped


def status_counts(cases):
    d = {s: 0 for s in STATUSES}
    for c in cases:
        t = c.get("triphasic")
        if t:
            d[t["status"]] = d.get(t["status"], 0) + 1
    return d


def pheno_counts(cases):
    d = {p: 0 for p in PHENOS}
    for c in cases:
        t = c.get("triphasic")
        if t and t["status"] == "present":
            d[t["phenotype"]] = d.get(t["phenotype"], 0) + 1
    return d


def _kappa2(a, b, c, d):
    """present/absent kappa: a=both present-or-absent-call agree... here a,d=agree cells."""
    n = a + b + c + d
    if n == 0:
        return 0.0
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def stability(short, long):
    """Compare the two variants on the reports both annotated."""
    ids = [h for h in short if h in long
           and short[h].get("triphasic") and long[h].get("triphasic")]
    conf = {s: {t: 0 for t in STATUSES} for s in STATUSES}      # short-status x long-status
    exact = 0
    flagged_ids = []          # either variant calls present/explicitly_absent
    flag_agree = 0
    # present/absent 2x2 (present = status present or explicitly_absent i.e. "mentioned")
    a = b = c = d = 0
    for h in ids:
        s, l = short[h]["triphasic"]["status"], long[h]["triphasic"]["status"]
        conf[s][l] += 1
        if s == l:
            exact += 1
        sm, lm = s != "not_mentioned", l != "not_mentioned"
        if sm and lm: a += 1
        elif sm: b += 1
        elif lm: c += 1
        else: d += 1
        if sm or lm:
            flagged_ids.append(h)
            if s == l:
                flag_agree += 1
    return {"n": len(ids), "conf": conf, "exact": exact,
            "exact_pct": 100 * exact / len(ids),
            "kappa": _kappa2(a, b, c, d),
            "flagged": len(flagged_ids), "flag_agree": flag_agree,
            "flag_agree_pct": 100 * flag_agree / len(flagged_ids) if flagged_ids else 0.0}


def cross_check(cases, txt):
    """Faithfulness of the (guarded) labels vs the report text."""
    call_no_term = 0        # present/absent but term absent (should be 0 after guard)
    nm_has_term = 0         # not_mentioned yet term present (conservative / template cases)
    for c in cases:
        t = c.get("triphasic")
        if not t:
            continue
        has = bool(TERM.search(txt.get(c["hashed_id"], "")))
        if t["status"] in ("present", "explicitly_absent") and not has:
            call_no_term += 1
        if t["status"] == "not_mentioned" and has:
            nm_has_term += 1
    return call_no_term, nm_has_term


# ----------------------------------------------------------------------------- charts
def _bare(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0, colors=INK2, labelsize=9); ax.set_axisbelow(True)


def chart_status(sc, lc):
    """present + explicitly_absent counts (not_mentioned is the rest — noted in subtitle)."""
    cats = ["present", "explicitly_absent"]
    labels = ["Present", "Explicitly absent"]
    fig, ax = plt.subplots(figsize=(8.6, 3.9))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(cats)))[::-1]; h = 0.36
    for i, (v, col) in enumerate([("short", BLUE), ("long", ORANGE)]):
        d = sc if v == "short" else lc
        vals = [d[c] for c in cats]
        yy = [yi + (h/2 if i == 0 else -h/2) for yi in y]
        ax.barh(yy, vals, height=h, color=col, zorder=3,
                label=f"{v} prompt", edgecolor="white")
        for Y, val in zip(yy, vals):
            ax.text(val + max(sc["present"], lc["present"]) * 0.012, Y, f"{val:,}",
                    va="center", ha="left", color=col, fontsize=10, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11.5, color=INK)
    ax.set_xlim(0, max(sc["present"], lc["present"]) * 1.16)
    ax.set_xlabel("Reports", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.legend(frameon=False, fontsize=10, loc="lower right")
    ax.set_title("Triphasic waves across 45,545 EEG reports",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.05, f"The remaining ~{sc['not_mentioned']:,} reports do not mention "
            "triphasic waves · MedGemma-27B, Q4", transform=ax.transAxes,
            fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "triphasic_status.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved triphasic_status.png")


def chart_phenotype(sp, lp):
    """Phenotype breakdown of the present reports, short vs long."""
    fig, ax = plt.subplots(figsize=(8.6, 4.0))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    y = list(range(len(PHENOS)))[::-1]; h = 0.36
    names = {"unspecified": "Unspecified", "typical": "Typical",
             "atypical": "Atypical", "mixed": "Mixed"}
    for i, (v, col) in enumerate([("short", BLUE), ("long", ORANGE)]):
        d = sp if v == "short" else lp
        vals = [d[p] for p in PHENOS]
        yy = [yi + (h/2 if i == 0 else -h/2) for yi in y]
        ax.barh(yy, vals, height=h, color=col, zorder=3,
                label=f"{v} prompt", edgecolor="white")
        for Y, val in zip(yy, vals):
            if val:
                ax.text(val + 6, Y, f"{val}", va="center", ha="left", color=col,
                        fontsize=9.5, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels([names[p] for p in PHENOS], fontsize=11.5, color=INK)
    ax.set_xlim(0, max(max(sp.values()), max(lp.values())) * 1.16)
    ax.set_xlabel("Reports called present", color=INK2, fontsize=10)
    ax.grid(axis="x", color=GRID, lw=1, zorder=0); _bare(ax)
    ax.legend(frameon=False, fontsize=10, loc="lower right")
    ax.set_title("What kind of triphasic waves — reported phenotype",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.05, "Most present reports do not give enough morphology to sub-type",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "triphasic_phenotype.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved triphasic_phenotype.png")


def chart_stability(stab):
    """3x3 confusion of short-status vs long-status."""
    conf = stab["conf"]
    short_lab = ["present", "expl. absent", "not mentioned"]
    fig, ax = plt.subplots(figsize=(6.7, 5.2))
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    M = [[conf[s][t] for t in STATUSES] for s in STATUSES]
    mx = max(max(r) for r in M)
    for i in range(3):
        for j in range(3):
            v = M[i][j]
            # log-ish shading so the huge not/not cell doesn't wash out the rest
            shade = (v / mx) ** 0.35 if mx else 0
            on_diag = i == j
            base = GREEN if on_diag else RED
            ax.add_patch(plt.Rectangle((j, 2 - i), 1, 1, facecolor=base, alpha=0.10 + 0.55*shade,
                                       edgecolor="white", lw=2, zorder=1))
            ax.text(j + 0.5, 2 - i + 0.5, f"{v:,}", ha="center", va="center",
                    color=INK, fontsize=12,
                    fontweight="bold" if v else "normal", zorder=2)
    ax.set_xlim(0, 3); ax.set_ylim(0, 3)
    ax.set_xticks([0.5, 1.5, 2.5]); ax.set_yticks([0.5, 1.5, 2.5])
    ax.set_xticklabels(short_lab, fontsize=10, color=INK)
    ax.set_yticklabels(short_lab[::-1], fontsize=10, color=INK)
    ax.set_xlabel("long prompt", color=ORANGE, fontsize=11, fontweight="bold")
    ax.set_ylabel("short prompt", color=BLUE, fontsize=11, fontweight="bold")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("Do the two prompts agree? short vs long status",
                 color=INK, fontsize=13, fontweight="bold", loc="left", pad=24)
    ax.text(0, 1.04, f"Exact status agreement {stab['exact_pct']:.2f}% · "
            f"present/absent κ = {stab['kappa']:.2f} · green = agree, red = differ (n={stab['n']:,})",
            transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout(); fig.savefig(OUT / "triphasic_stability.png", bbox_inches="tight",
                                    facecolor="white")
    plt.close(fig); print("saved triphasic_stability.png")


def write_clean(variant, guarded):
    meta = {"task": "triphasic", "variant": variant, "guard": "term-in-text",
            "n": len(guarded)}
    (CLEAN / f"{variant}.json").write_text(
        json.dumps({"meta": meta, "cases": guarded}, indent=1))


if __name__ == "__main__":
    txt = load_text()
    raw = {v: load_variant(v) for v in VARIANTS}
    guarded = {}
    sc = {}; pc = {}
    print(f"reports in DB: {len(txt):,}\n")
    for v in VARIANTS:
        cases = raw[v]
        ok = sum(1 for c in cases.values() if c.get("triphasic"))
        err = sum(1 for c in cases.values() if not c.get("triphasic"))
        g, flipped = apply_guard(cases, txt)
        guarded[v] = g
        write_clean(v, g)
        sc[v] = status_counts(g); pc[v] = pheno_counts(g)
        cn, nm = cross_check(g, txt)
        print(f"[{v}] annotated {ok:,}/{len(cases):,}  grammar-errors {err}  "
              f"guard-flipped {flipped}")
        print(f"      status: present {sc[v]['present']:,}  explicitly_absent "
              f"{sc[v]['explicitly_absent']:,}  not_mentioned {sc[v]['not_mentioned']:,}")
        print(f"      phenotype: " + "  ".join(f"{p} {pc[v][p]}" for p in PHENOS))
        print(f"      cross-check: present/absent w/o term {cn} (0 = guard clean); "
              f"not_mentioned w/ term {nm}\n")

    stab = stability({c["hashed_id"]: c for c in guarded["short"]},
                     {c["hashed_id"]: c for c in guarded["long"]})
    print(f"stability (n={stab['n']:,}): exact status {stab['exact_pct']:.2f}%  "
          f"present/absent κ {stab['kappa']:.3f}")
    print(f"  on reports flagged by either prompt (n={stab['flagged']:,}): "
          f"status agreement {stab['flag_agree_pct']:.1f}%")

    chart_status(sc["short"], sc["long"])
    chart_phenotype(pc["short"], pc["long"])
    chart_stability(stab)
