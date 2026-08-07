from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gpu import evaluator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run MedGemma Q2 evaluation on a sequential cohort chunk."
    )

    parser.add_argument(
        "--start-index",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--model",
        default="medgemma-q2",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/v1",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=768,
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    args = parser.parse_args()

    if args.start_index < 0:
        raise ValueError("--start-index cannot be negative.")

    if args.chunk_size < 1:
        raise ValueError("--chunk-size must be at least 1.")

    def select_chunk(
        cohort,
        sg,
        ld,
        limit,
    ):
        del sg, ld, limit

        cohort_size = len(cohort)

        if args.start_index >= cohort_size:
            raise ValueError(
                f"--start-index={args.start_index} is outside "
                f"the cohort of {cohort_size} reports."
            )

        end_index = min(
            args.start_index + args.chunk_size,
            cohort_size,
        )

        print(
            f"Sequential cohort slice: "
            f"[{args.start_index}, {end_index})"
        )

        return [
            (
                hashed_id,
                f"cohort_index_{global_index:04d}",
            )
            for global_index, hashed_id in enumerate(
                cohort[args.start_index:end_index],
                start=args.start_index,
            )
        ]

    # Replace diagnostic selection only inside this wrapper process.
    evaluator.select_cases = select_chunk

    forwarded_args = [
        "gpu.evaluator",
        "--max-cases",
        str(args.chunk_size),
        "--output",
        str(args.output),
        "--model",
        args.model,
        "--base-url",
        args.base_url,
        "--max-tokens",
        str(args.max_tokens),
        "--retries",
        str(args.retries),
    ]

    if args.dry_run:
        forwarded_args.append("--dry-run")

    if args.overwrite:
        forwarded_args.append("--overwrite")

    sys.argv = forwarded_args
    evaluator.main()


if __name__ == "__main__":
    main()
