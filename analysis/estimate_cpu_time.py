#!/usr/bin/env python3
"""Extrapolate full-cohort CPU inference time from a timed benchmark sample.

Reads a benchmark result JSON (with per-case ``report_words`` and
``inference_seconds``), fits ``seconds = a + b * words`` by least squares,
and applies the fit to the actual word-count distribution of all 1495
cohort reports. This avoids the short-report bias of a plain sample mean,
because early cohort reports (by LD rowid) run slightly shorter than the
cohort as a whole.

Usage:
    python -m analysis.estimate_cpu_time results/q2_cpu_0000_0049_jobXXXX.json
"""

from __future__ import annotations

import json
import sqlite3
import statistics as st
import sys
from pathlib import Path

LD = "/project/6019337/vvakorin/incoming/zoe_reports_240325_LD_20241215.db"
SG = "/project/6019337/vvakorin/incoming/zoe_reports_240325_SG_20250305.db"
COLS = ["Abnormality", "Focal Epi", "Gen Epi", "Focal Non-epi", "Gen Non-epi"]


def load_reports(path: str) -> dict:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    query = (
        'SELECT rowid, "Hashed ID" AS hid, Report, '
        + ", ".join(f'"{c}" AS "{c}"' for c in COLS)
        + " FROM reports"
    )
    out = {}
    for row in conn.execute(query):
        full = all(str(row[c]).strip() in {"1", "2", "3", "4"} for c in COLS)
        out[row["hid"]] = {
            "rowid": row["rowid"],
            "words": len((row["Report"] or "").split()),
            "full": full,
        }
    return out


def cohort_word_counts() -> list[int]:
    ld, sg = load_reports(LD), load_reports(SG)
    common = [h for h in set(sg) & set(ld) if sg[h]["full"] and ld[h]["full"]]
    cohort = sorted(
        (h for h in common if 42 <= ld[h]["rowid"] <= 2000),
        key=lambda h: ld[h]["rowid"],
    )
    return [ld[h]["words"] for h in cohort]


def linreg(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Ordinary least squares. Returns (intercept a, slope b, R^2)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
    return a, b, r2


def fmt_hms(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600}h {s % 3600 // 60}m {s % 60}s"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: estimate_cpu_time.py <benchmark.json>")
    data = json.loads(Path(sys.argv[1]).read_text())
    cases = data["cases"]

    pairs = [
        (c["report_words"], c["inference_seconds"])
        for c in cases
        if "inference_seconds" in c and "report_words" in c
    ]
    if not pairs:
        sys.exit("No timing fields in JSON — was this run with the "
                 "instrumented evaluator?")

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    n = len(pairs)

    print(f"Sample: n={n} timed reports")
    print(f"  words   : mean={st.mean(xs):.1f} median={st.median(xs):.0f} "
          f"min={min(xs)} max={max(xs)}")
    print(f"  seconds : mean={st.mean(ys):.2f} median={st.median(ys):.2f} "
          f"min={min(ys):.2f} max={max(ys):.2f} "
          f"std={st.pstdev(ys):.2f}")

    a, b, r2 = linreg(xs, ys)
    print()
    print(f"Fit: seconds = {a:.3f} + {b:.4f} * words   (R^2={r2:.3f})")
    print(f"  => fixed per-request cost ~{a:.1f}s, "
          f"+{b * 1000:.1f}s per 1000 words")

    cohort = cohort_word_counts()
    N = len(cohort)
    total_words = sum(cohort)
    print()
    print(f"Full cohort: N={N}, total_words={total_words}, "
          f"mean_words={total_words / N:.1f}")

    naive = st.mean(ys) * N
    regression = a * N + b * total_words
    print()
    print("ESTIMATED TOTAL INFERENCE TIME (excludes one-time build/load):")
    print(f"  naive  (sample_mean * N)     : {fmt_hms(naive)}  "
          f"({naive / N:.2f} s/report)")
    print(f"  regression (fit on cohort)   : {fmt_hms(regression)}  "
          f"({regression / N:.2f} s/report)")
    print(f"  regression is the reliable number "
          f"(corrects sample length bias)")

    print()
    print("PRODUCTION SHAPING (regression basis):")
    for walltime_h in (3, 12, 24):
        # usable = walltime minus ~5 min one-time build+copy+load overhead
        usable = walltime_h * 3600 - 300
        per_job = usable / (regression / N)
        jobs = -(-N // int(per_job)) if per_job >= 1 else float("inf")
        print(f"  {walltime_h:2d}h walltime/job -> ~{int(per_job)} reports/job "
              f"-> {jobs} job(s) for full cohort")


if __name__ == "__main__":
    main()
