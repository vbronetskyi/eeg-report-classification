from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

import core.cohort as cohort_module
from core.cohort import (
    FIELDS,
    LD_DB,
    SG_DB,
    build_cohort,
    is_present,
    load_db,
    select_cases,
)
from core.prompt import (
    OUTPUT_FIELDS,
    OUTPUT_SCHEMA,
    OUTPUT_TO_INTERNAL,
    build_grammar,
    build_prompt,
    output_to_internal_labels,
)
from core.prompt import SYSTEM

GRAMMAR = build_grammar()


DEFAULT_MODEL = "/scratch/brovik/hf/medgemma-27b-text-it"
DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"



def extract_json_text(text: str | None) -> str:
    if text is None:
        raise RuntimeError("The model returned empty message content.")

    text = text.strip()

    fence_match = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$",
        text,
        flags=re.DOTALL,
    )

    if fence_match:
        return fence_match.group(1).strip()

    return text


def request_classification(
    client: OpenAI,
    model: str,
    report_text: str,
    max_tokens: int,
):
    return client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM,
            },
            {
                "role": "user",
                "content": build_prompt(report_text),
            },
        ],
        temperature=0,
        max_tokens=max_tokens,
        logprobs=True,
        top_logprobs=20,
        extra_body={
            "grammar": GRAMMAR,
        },
    )


def score_from_token(token: str) -> int | None:
    cleaned = token.strip().strip(
        "\"'`,:;{}[]()"
    )

    if cleaned in {"1", "2", "3", "4"}:
        return int(cleaned)

    return None


def score_distribution(token_info: Any) -> dict[int, float]:
    probabilities = {
        1: 0.0,
        2: 0.0,
        3: 0.0,
        4: 0.0,
    }

    chosen_score = score_from_token(token_info.token)

    if chosen_score is not None:
        probabilities[chosen_score] = max(
            probabilities[chosen_score],
            math.exp(token_info.logprob),
        )

    for alternative in token_info.top_logprobs or []:
        alternative_score = score_from_token(
            alternative.token
        )

        if alternative_score is None:
            continue

        probabilities[alternative_score] = max(
            probabilities[alternative_score],
            math.exp(alternative.logprob),
        )

    total = sum(probabilities.values())

    if total <= 0:
        raise RuntimeError(
            "No score-token probabilities were found."
        )

    return {
        score: probability / total
        for score, probability in probabilities.items()
    }


def find_field_token(
    response: Any,
    output_field: str,
):
    token_infos = (
        response.choices[0].logprobs.content or []
    )

    generated_text = "".join(
        token_info.token
        for token_info in token_infos
    )

    pattern = re.compile(
        rf'"{re.escape(output_field)}"\s*:\s*([1-4])'
    )
    match = pattern.search(generated_text)

    if match is None:
        raise RuntimeError(
            f"Could not locate the value token for "
            f"{output_field} in generated logprobs."
        )

    digit_position = match.start(1)
    current_position = 0

    for token_info in token_infos:
        next_position = (
            current_position + len(token_info.token)
        )

        if (
            current_position
            <= digit_position
            < next_position
        ):
            return token_info

        current_position = next_position

    raise RuntimeError(
        f"Could not align the value token for "
        f"{output_field}."
    )


def parse_joint_response(
    response: Any,
) -> tuple[
    dict[str, Any],
    dict[str, dict[str, float | int]],
]:
    content = response.choices[0].message.content
    parsed = json.loads(extract_json_text(content))

    internal_labels = output_to_internal_labels(
        parsed
    )

    model_results: dict[
        str,
        dict[str, float | int],
    ] = {}

    for output_field in OUTPUT_FIELDS:
        internal_field = OUTPUT_TO_INTERNAL[
            output_field
        ]

        token_info = find_field_token(
            response,
            output_field,
        )
        distribution = score_distribution(
            token_info
        )
        prediction = internal_labels[
            internal_field
        ]

        model_results[internal_field] = {
            "pred": int(prediction),
            "p1": distribution[1],
            "p2": distribution[2],
            "p3": distribution[3],
            "p4": distribution[4],
            "p_presence": (
                distribution[3]
                + distribution[4]
            ),
        }

    return parsed, model_results


def summarize(
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}

    for field in FIELDS:
        exact_matches = sum(
            case["model"][field]["pred"]
            == case["ld_labels"][field]
            for case in cases
        )

        binary_matches = sum(
            is_present(
                case["model"][field]["pred"]
            )
            == is_present(
                case["ld_labels"][field]
            )
            for case in cases
        )

        output[field] = {
            "n": len(cases),
            "exact_matches": exact_matches,
            "binary_matches": binary_matches,
        }

    return output


def save_output(
    path: Path,
    cases: list[dict[str, Any]],
    model: str,
) -> None:
    payload = {
        "experiment": {
            "name": "medgemma_q2_joint_prompt",
            "model": model,
            "prompt_type": "joint_five_field",
            "generated_evidence_saved": False,
            "generated_raw_output_saved": False,
            "contains_report_text": False,
            "contains_hashed_ids": False,
        },
        "dataset": {
            "name": f"{cohort_module.DATASET}_candidate_cohort_n{cohort_module._CFG['n_cohort']}",
            "selection": (
                f"{cohort_module._CFG['n_common']} common fully annotated "
                f"SG/LD reports ordered by LD rowid; "
                f"initial rowid 1..{cohort_module._CFG['pilot']} block excluded"
                if cohort_module._CFG["pilot"] else
                f"{cohort_module._CFG['n_common']} common fully annotated "
                f"SG/LD reports ordered by LD rowid"
            ),
            "reference_used": "LD",
            "secondary_annotator": "SG",
            "paper_cohort_status": (
                "strong candidate, "
                "not independently confirmed"
            ),
        },
        "cases": cases,
        "summary_vs_ld": summarize(cases),
    }

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary_path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(path)


def load_checkpoint(
    path: Path,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )
    cases = payload.get("cases", [])

    if not isinstance(cases, list):
        raise RuntimeError(
            "Checkpoint contains an invalid cases field."
        )

    return cases


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--max-cases",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "results/"
            "real_zoe_q2_joint_smoke.json"
        ),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    args = parser.parse_args()

    if args.max_cases < 1:
        raise ValueError(
            "--max-cases must be at least 1."
        )

    if args.max_tokens < 64:
        raise ValueError(
            "--max-tokens must be at least 64."
        )

    if args.retries < 0:
        raise ValueError(
            "--retries cannot be negative."
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

    print(
        f"Candidate {cohort_module.DATASET} cohort:",
        len(cohort),
    )
    print(
        "Selected diagnostic cases:",
        len(selected),
    )
    print(
        "No report text, Hashed ID, raw model "
        "output, or evidence will be printed or saved."
    )

    for index, (hashed_id, reason) in enumerate(
        selected,
        start=1,
    ):
        print()
        print(
            f"case_{index:03d}: {reason}"
        )
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

    if args.overwrite:
        cases: list[dict[str, Any]] = []
    else:
        cases = load_checkpoint(
            args.output
        )

    completed_case_ids = {
        case["case_id"]
        for case in cases
        if "case_id" in case
    }

    if completed_case_ids:
        print()
        print(
            f"Resuming checkpoint with "
            f"{len(completed_case_ids)} "
            f"completed cases."
        )

    client = OpenAI(
        base_url=args.base_url,
        api_key="EMPTY",
    )

    for index, (hashed_id, reason) in enumerate(
        selected,
        start=1,
    ):
        case_id = f"case_{index:03d}"

        if case_id in completed_case_ids:
            print()
            print(
                f"{case_id}: already completed, "
                f"skipping."
            )
            continue

        print()
        print("=" * 80)
        print(
            case_id,
            reason,
            flush=True,
        )

        parsed: dict[str, Any] | None = None
        model_results: dict[
            str,
            dict[str, float | int],
        ] | None = None
        last_error: Exception | None = None
        attempts_used = 0
        report_words = len(
            ld[hashed_id]["report"].split()
        )
        request_start = time.perf_counter()

        for attempt in range(
            1,
            args.retries + 2,
        ):
            attempts_used = attempt

            try:
                response = request_classification(
                    client=client,
                    model=args.model,
                    report_text=ld[
                        hashed_id
                    ]["report"],
                    max_tokens=args.max_tokens,
                )

                parsed, model_results = (
                    parse_joint_response(
                        response
                    )
                )
                break

            except Exception as error:
                last_error = error
                print(
                    f"  attempt {attempt} failed: "
                    f"{type(error).__name__}: "
                    f"{error}",
                    flush=True,
                )

        inference_seconds = time.perf_counter() - request_start

        if parsed is None or model_results is None:
            print(
                f"  {case_id} skipped after "
                f"{attempts_used} failed attempts; "
                "continuing with next case.",
                flush=True,
            )
            continue

        case = {
            "case_id": case_id,
            "selection_reason": reason,
            "ld_labels": ld[
                hashed_id
            ]["labels"],
            "sg_labels": sg[
                hashed_id
            ]["labels"],
            "model": model_results,
            "attempts_used": attempts_used,
            "report_words": report_words,
            "inference_seconds": round(inference_seconds, 4),
        }

        for field in FIELDS:
            result = model_results[field]

            print(
                f"  {field}: "
                f"pred={result['pred']} "
                f"LD={ld[hashed_id]['labels'][field]} "
                f"SG={sg[hashed_id]['labels'][field]} "
                f"P(presence)="
                f"{result['p_presence']:.4f}"
            )

        print(
            f"  timing: {report_words} words, "
            f"{inference_seconds:.2f} s",
            flush=True,
        )

        cases.append(case)

        save_output(
            path=args.output,
            cases=cases,
            model=args.model,
        )

        print(
            f"  checkpoint saved to "
            f"{args.output}",
            flush=True,
        )

    print()
    print("=" * 80)
    print("SUMMARY VS LD")

    for field, metrics in summarize(
        cases
    ).items():
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
