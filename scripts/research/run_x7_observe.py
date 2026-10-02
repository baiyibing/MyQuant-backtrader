#!/usr/bin/env python3
"""A·X7 observation surface CLI (new projection entry; never views._FAMILIES).

observation_id=minute_orders_x7_observe — NOT a backend_id.
Reuses research contract v0 (L2-S0) / minute_orders_research_v1 labels only.

Projects already-obtained New-core tool reports into a red-label observation
slice. Observation ≠ green R; no NAV rewrite; no production lake write; no 4090;
empty MatchCore/Fees/simulate; forever opt-in; never BOOKS default; ≠δ5≠R4.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.minute_orders_x7_observe import (  # noqa: E402
    BACKEND_ID,
    CONTRACT,
    OBSERVATION_ID,
    OBSERVATION_STATUS,
    X7_PROJECTION_FAMILY,
    ObserveError,
    load_observe_request,
    run_x7_observe,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "A·X7 observation surface · new projection entry only. "
            f"observation_id={OBSERVATION_ID} (NOT a backend_id). "
            f"projection_family={X7_PROJECTION_FAMILY} (never views._FAMILIES). "
            f"contract={CONTRACT}; backend label={BACKEND_ID}. "
            f"status={OBSERVATION_STATUS}. "
            "NO NAV rewrite; NO green R; NO summary.json; NO lake write; NO 4090; "
            "NO MatchCore/Fees/simulate rewrite; ≠δ5≠R4; forever opt-in; never BOOKS; "
            "observation != green R."
        )
    )
    p.add_argument(
        "--request",
        type=Path,
        required=True,
        help="Absolute path to observation request JSON (already-obtained source)",
    )
    p.add_argument(
        "--parent",
        type=Path,
        help="Absolute parent for independent observation root (omit with --memory-only)",
    )
    p.add_argument(
        "--run-id",
        help="Run id under backtest_output/minute_orders_x7_observe/",
    )
    p.add_argument(
        "--memory-only",
        action="store_true",
        help="Project in memory only; do not write observation root",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.request.is_absolute():
            raise ObserveError("--request must be an absolute path")
        request = load_observe_request(args.request)
        if args.memory_only:
            outcome = run_x7_observe(request=request, memory_only=True)
        else:
            if args.parent is None or args.run_id is None:
                raise ObserveError("--parent and --run-id required unless --memory-only")
            if not args.parent.is_absolute():
                raise ObserveError("--parent must be an absolute path")
            outcome = run_x7_observe(
                request=request,
                parent=args.parent,
                run_id=args.run_id,
            )
    except ObserveError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = {
        "observation_id": outcome.observation_id,
        "observation_status": outcome.observation_status,
        "projection_family": X7_PROJECTION_FAMILY,
        "report": str(outcome.report_path) if outcome.report_path else None,
        "memory_only": args.memory_only,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
