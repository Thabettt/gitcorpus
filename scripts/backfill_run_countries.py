from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine  # noqa: E402

from serve.analysis import backfill_countries  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch missing owner locations for a detection run and freeze countries."
    )
    parser.add_argument("--run-id", type=int, required=True, help="detect run to backfill")
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help=(
            "batch size for owners without a stored location when fetching from GitHub"
            " (default: 500; 0 fetches every one in a single pass); stored locations"
            " always resolve in full"
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="stop after one batch instead of draining every remaining owner",
    )
    parser.add_argument(
        "--repeat",
        action="store_true",
        help="deprecated: draining every remaining owner is now the default",
    )
    parser.add_argument(
        "--retry-unmatched",
        action="store_true",
        help="re-attempt owners whose previous location lookup found no country",
    )
    parser.add_argument(
        "--freeze-only",
        action="store_true",
        help="skip GitHub calls; re-resolve stored locations and freeze known countries",
    )
    parser.add_argument(
        "--rest",
        action="store_true",
        help="use REST owner lookups instead of GraphQL batching",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    engine = create_engine(os.environ["DATABASE_URL"])
    totals = {"owners": 0, "fetched": 0, "resolved": 0, "unmatched": 0, "updated": 0}
    while True:
        result = backfill_countries(
            engine,
            args.run_id,
            limit=args.limit,
            retry_unmatched=args.retry_unmatched,
            fetch=not args.freeze_only,
            force_rest=args.rest,
        )
        for key in totals:
            totals[key] += result[key]
        print(json.dumps(result, sort_keys=True), flush=True)
        if args.once or result["remaining"] == 0 or result["owners"] == 0:
            break
        if result["fetched"] == 0 and result["updated"] == 0:
            print("no progress; stopping", flush=True)
            break
    print("TOTAL " + json.dumps({**totals, "remaining": result["remaining"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
