from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .assets import fetch_dataset_assets
from .dataset import load_dataset
from .judge import aggregate_judgments, prepare_judge_batch
from .prerequisites import check_prerequisites
from .public_pricing import build_public_offer_url, build_public_region_index_url
from .report import generate_report
from .runner import load_profile, run_experiment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aws-agent-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate a dataset")
    validate.add_argument("--dataset", type=Path, required=True)

    experiment = subparsers.add_parser("experiment", help="Run and evaluate agent trials")
    experiment.add_argument("--dataset", type=Path, required=True)
    experiment.add_argument("--profile", type=Path, required=True)
    experiment.add_argument("--run-dir", type=Path, required=True)
    experiment.add_argument("--repetitions", type=int, default=3)
    experiment.add_argument("--case", action="append", dest="cases")
    experiment.add_argument(
        "--asset-cache",
        type=Path,
        help="Use public assets previously downloaded by fetch-assets",
    )

    fetch_assets = subparsers.add_parser(
        "fetch-assets", help="Download public reference assets without AWS credentials"
    )
    fetch_assets.add_argument("--dataset", type=Path, required=True)
    fetch_assets.add_argument("--cache-dir", type=Path, required=True)

    report = subparsers.add_parser("report", help="Generate Markdown and JSON summary")
    report.add_argument("--run-dir", type=Path, required=True)

    judge = subparsers.add_parser("prepare-judge", help="Create anonymous Judge JSONL")
    judge.add_argument("--run-dir", type=Path, required=True)
    judge.add_argument("--repeats", type=int, default=3)
    judge.add_argument("--seed", type=int, default=20260725)

    aggregate = subparsers.add_parser("aggregate-judge", help="Validate and aggregate Judge JSONL")
    aggregate.add_argument("--run-dir", type=Path, required=True)
    aggregate.add_argument("--input", type=Path, required=True)

    prerequisites = subparsers.add_parser(
        "check-prerequisites", help="Check live profile prerequisites"
    )
    prerequisites.add_argument("--profile", type=Path, required=True)

    price_url = subparsers.add_parser(
        "public-price-url",
        help="Print a credential-free AWS public price-list URL",
    )
    price_url.add_argument("--service-code", required=True)
    price_url.add_argument("--region-code")
    price_url.add_argument("--version", default="current")
    price_url.add_argument("--format", choices=["json", "csv"], default="json")
    price_url.add_argument("--region-index", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            dataset = load_dataset(args.dataset)
            print(f"valid: {dataset.id} {dataset.version} ({len(dataset.cases)} cases)")
        elif args.command == "experiment":
            dataset = load_dataset(args.dataset)
            profile = load_profile(args.profile)
            result = run_experiment(
                dataset,
                profile,
                args.run_dir,
                repetitions=args.repetitions,
                selected_case_ids=set(args.cases) if args.cases else None,
                asset_cache=args.asset_cache,
            )
            print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
            if result["summary"]["successes"] != result["summary"]["trials"]:
                raise SystemExit(2)
        elif args.command == "fetch-assets":
            dataset = load_dataset(args.dataset)
            result = fetch_dataset_assets(dataset, args.cache_dir)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "report":
            print(generate_report(args.run_dir))
        elif args.command == "prepare-judge":
            print(prepare_judge_batch(args.run_dir, args.repeats, seed=args.seed))
        elif args.command == "aggregate-judge":
            print(aggregate_judgments(args.run_dir, args.input))
        elif args.command == "check-prerequisites":
            profile = load_profile(args.profile)
            result = check_prerequisites(profile)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if not result["ok"]:
                raise SystemExit(2)
        elif args.command == "public-price-url":
            if args.region_index:
                print(build_public_region_index_url(args.service_code, version=args.version))
            else:
                print(
                    build_public_offer_url(
                        args.service_code,
                        region_code=args.region_code,
                        version=args.version,
                        file_format=args.format,
                    )
                )
        else:
            raise AssertionError(f"Unhandled command: {args.command}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
