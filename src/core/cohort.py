import argparse
import json
import os
import sqlite3
from pathlib import Path

from core.fields import FIELD_CONFIGS, classify, single_field_probs

_INCOMING = "/project/6019337/vvakorin/incoming"

# Dataset is selectable via the DATASET env var (default "zoe").
#   zoe   : 1536 common fully-annotated, first 41-rowid pilot block excluded -> 1495
#   maria : 499 common fully-annotated, used in full -> 499
DATASETS = {
    "zoe": {
        "SG": f"{_INCOMING}/zoe_reports_240325_SG_20250305.db",
        "LD": f"{_INCOMING}/zoe_reports_240325_LD_20241215.db",
        "n_common": 1536,
        "pilot": 41,
        "n_cohort": 1495,
    },
    "maria": {
        "SG": f"{_INCOMING}/maria_reports_240325_SG_20250414.db",
        "LD": f"{_INCOMING}/maria_reports_240325_LD_20250405.db",
        "n_common": 499,
        "pilot": 0,
        "n_cohort": 499,
    },
}

DATASET = os.environ.get("DATASET", "zoe").lower()
if DATASET not in DATASETS:
    raise ValueError(f"Unknown DATASET={DATASET!r}; choose from {list(DATASETS)}")
_CFG = DATASETS[DATASET]

SG_DB = Path(_CFG["SG"])
LD_DB = Path(_CFG["LD"])

FIELDS = [
    "abnormality",
    "focal_epileptiform_activity",
    "generalized_epileptiform_activity",
    "focal_non_epileptiform_activity",
    "generalized_non_epileptiform_activity",
]


def load_db(path):
    conn = sqlite3.connect(
        f"file:{path}?mode=ro",
        uri=True,
    )

    query = """
        SELECT
            rowid,
            "Hashed ID",
            "Report",
            "Abnormality",
            "Focal Epi",
            "Gen Epi",
            "Focal Non-epi",
            "Gen Non-epi"
        FROM reports
        ORDER BY rowid
    """

    rows = {}

    try:
        for row in conn.execute(query):
            rowid, hashed_id, report, *values = row

            if hashed_id is None:
                continue

            rows[str(hashed_id)] = {
                "rowid": int(rowid),
                "report": report or "",
                "labels": dict(zip(FIELDS, values)),
                "full": all(
                    value in {1, 2, 3, 4}
                    for value in values
                ),
            }
    finally:
        conn.close()

    return rows


def is_present(value):
    return value >= 3


def build_cohort(sg, ld):
    common = sorted(
        (
            hashed_id
            for hashed_id in set(sg) & set(ld)
            if sg[hashed_id]["full"]
            and ld[hashed_id]["full"]
        ),
        key=lambda hashed_id: ld[hashed_id]["rowid"],
    )

    if len(common) != _CFG["n_common"]:
        raise RuntimeError(
            f"Expected {_CFG['n_common']} common reports, got {len(common)}"
        )

    pilot = _CFG["pilot"]
    if pilot:
        pilot_rowids = [
            ld[hashed_id]["rowid"]
            for hashed_id in common[:pilot]
        ]

        if pilot_rowids != list(range(1, pilot + 1)):
            raise RuntimeError(
                f"Expected the first common block to have rowids 1..{pilot}"
            )

    cohort = common[pilot:]

    if len(cohort) != _CFG["n_cohort"]:
        raise RuntimeError(
            f"Expected candidate cohort size {_CFG['n_cohort']}, got {len(cohort)}"
        )

    report_mismatches = sum(
        sg[hashed_id]["report"]
        != ld[hashed_id]["report"]
        for hashed_id in cohort
    )

    if report_mismatches:
        raise RuntimeError(
            f"Found {report_mismatches} SG/LD report mismatches"
        )

    return cohort


def select_cases(cohort, sg, ld, limit):
    rules = [
        (
            "all_labels_negative",
            lambda ld_labels, sg_labels: all(
                value <= 2
                for value in ld_labels.values()
            ),
        ),
        (
            "abnormality_score_2",
            lambda ld_labels, sg_labels:
                ld_labels["abnormality"] == 2,
        ),
        (
            "focal_epileptiform_positive",
            lambda ld_labels, sg_labels:
                ld_labels["focal_epileptiform_activity"] >= 3,
        ),
        (
            "generalized_epileptiform_positive",
            lambda ld_labels, sg_labels:
                ld_labels["generalized_epileptiform_activity"] >= 3,
        ),
        (
            "focal_non_epileptiform_positive",
            lambda ld_labels, sg_labels:
                ld_labels["focal_non_epileptiform_activity"] >= 3,
        ),
        (
            "generalized_non_epileptiform_positive",
            lambda ld_labels, sg_labels:
                ld_labels["generalized_non_epileptiform_activity"] >= 3,
        ),
        (
            "contains_score_3",
            lambda ld_labels, sg_labels:
                any(value == 3 for value in ld_labels.values()),
        ),
        (
            "contains_score_2",
            lambda ld_labels, sg_labels:
                any(value == 2 for value in ld_labels.values()),
        ),
        (
            "human_binary_disagreement",
            lambda ld_labels, sg_labels: any(
                is_present(ld_labels[field])
                != is_present(sg_labels[field])
                for field in FIELDS
            ),
        ),
        (
            "human_ordinal_disagreement",
            lambda ld_labels, sg_labels: any(
                ld_labels[field] != sg_labels[field]
                for field in FIELDS
            ),
        ),
    ]

    selected = []
    selected_ids = set()

    for reason, rule in rules:
        for hashed_id in cohort:
            if hashed_id in selected_ids:
                continue

            if rule(
                ld[hashed_id]["labels"],
                sg[hashed_id]["labels"],
            ):
                selected.append((hashed_id, reason))
                selected_ids.add(hashed_id)
                break

        if len(selected) >= limit:
            return selected[:limit]

    for hashed_id in cohort:
        if hashed_id not in selected_ids:
            selected.append(
                (hashed_id, "deterministic_fill")
            )
            selected_ids.add(hashed_id)

        if len(selected) >= limit:
            break

    return selected


def summarize(cases):
    output = {}

    for field in FIELDS:
        exact_matches = sum(
            case["model"][field]["pred"]
            == case["ld_labels"][field]
            for case in cases
        )

        binary_matches = sum(
            is_present(case["model"][field]["pred"])
            == is_present(case["ld_labels"][field])
            for case in cases
        )

        output[field] = {
            "n": len(cases),
            "exact_matches": exact_matches,
            "binary_matches": binary_matches,
        }

    return output


def save_output(path, cases):
    payload = {
        "dataset": {
            "name": "zoe_candidate_cohort_n1495",
            "selection": (
                "1536 common fully annotated SG/LD reports "
                "ordered by LD rowid; initial rowid 1..41 "
                "block excluded"
            ),
            "reference_used": "LD",
            "secondary_annotator": "SG",
            "paper_cohort_status": (
                "strong candidate, not independently confirmed"
            ),
            "contains_report_text": False,
            "contains_hashed_ids": False,
        },
        "cases": cases,
        "summary_vs_ld": summarize(cases),
    }

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--max-cases",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "real_zoe_smoke_results.json"
        ),
    )

    args = parser.parse_args()

    if args.max_cases < 1:
        raise ValueError(
            "--max-cases must be at least 1"
        )

    sg = load_db(SG_DB)
    ld = load_db(LD_DB)

    cohort = build_cohort(sg, ld)

    selected = select_cases(
        cohort=cohort,
        sg=sg,
        ld=ld,
        limit=args.max_cases,
    )

    print("Candidate Zoe cohort:", len(cohort))
    print("Selected diagnostic cases:", len(selected))
    print(
        "No report text or Hashed ID "
        "will be printed or saved."
    )

    for index, (hashed_id, reason) in enumerate(
        selected,
        start=1,
    ):
        print()
        print(f"case_{index:03d}: {reason}")
        print(
            "  LD:",
            ld[hashed_id]["labels"],
        )
        print(
            "  SG:",
            sg[hashed_id]["labels"],
        )

    if args.dry_run:
        print()
        print(
            "Dry run complete. "
            "No model requests were sent."
        )
        return

    cases = []

    for index, (hashed_id, reason) in enumerate(
        selected,
        start=1,
    ):
        case_id = f"case_{index:03d}"

        case = {
            "case_id": case_id,
            "selection_reason": reason,
            "ld_labels": ld[hashed_id]["labels"],
            "sg_labels": sg[hashed_id]["labels"],
            "model": {},
        }

        print()
        print("=" * 80)
        print(case_id, reason)

        for field in FIELDS:
            print(
                f"  {field} ...",
                flush=True,
            )

            response = classify(
                field,
                FIELD_CONFIGS[field]["instruction"],
                ld[hashed_id]["report"],
            )

            result = single_field_probs(
                response,
                field,
            )

            case["model"][field] = {
                "pred": int(result["pred"]),
                "p1": result["p1"],
                "p2": result["p2"],
                "p3": result["p3"],
                "p4": result["p4"],
                "p_presence": result["p_presence"],
            }

            print(
                f"    pred={result['pred']} "
                f"LD={ld[hashed_id]['labels'][field]} "
                f"SG={sg[hashed_id]['labels'][field]} "
                f"P(presence)="
                f"{result['p_presence']:.4f}"
            )

        cases.append(case)

        save_output(
            args.output,
            cases,
        )

    print()
    print("=" * 80)
    print("SUMMARY VS LD")

    for field, metrics in summarize(cases).items():
        print(
            f"{field}: "
            f"exact={metrics['exact_matches']}/"
            f"{metrics['n']} "
            f"binary={metrics['binary_matches']}/"
            f"{metrics['n']}"
        )

    print()
    print(
        f"Saved privacy-safe results "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
