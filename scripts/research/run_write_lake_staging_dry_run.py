#!/usr/bin/env python3
"""True-core residual R2 · write-lake staging dry-run CLI (NOT production write).

tool_id=minute_orders_write_lake_staging — NOT a backend_id.
Reuses research contract v0 (L2-S0) / minute_orders_research_v1 labels only.

This CLI never writes the production lake. It accepts a staging dry-run
request, refuses stock_data / configured lake roots, and writes an independent
tool report + MUST_HUMAN_CUTS.json. No --write-lake flag exists.

≠δ5≠R4; forever opt-in; never BOOKS default; empty MatchCore/Fees/simulate;
no 4090; no green R; staging dry-run ≠ host PASS ≠ production write.

Prefer existing vendor Phase2 staging (vendor_to_lake_adapter.py) and host
Phase4 ownership over blind write from this research fork (consume-only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.minute_orders_write_lake_staging import (  # noqa: E402
    BACKEND_ID,
    CONTRACT,
    MUST_HUMAN_CUTS,
    NOTICE,
    STAGING_STATUS,
    TOOL_ID,
    WriteLakeStagingError,
    load_staging_request,
    run_write_lake_staging_dry_run,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "True-core write-lake residual · staging dry-run only. "
            f"tool_id={TOOL_ID} (NOT a backend_id). "
            f"contract={CONTRACT}; backend label={BACKEND_ID}. "
            f"status={STAGING_STATUS}. "
            "NO lake write; NO --write-lake; NO MatchCore/Fees/simulate rewrite; "
            "≠δ5≠R4; forever opt-in; never BOOKS; no 4090; no green R; "
            "staging dry-run != production write != host PASS."
        )
    )
    p.add_argument(
        "--request",
        type=Path,
        required=True,
        help="Absolute path to staging dry-run request JSON",
    )
    p.add_argument(
        "--parent",
        type=Path,
        required=True,
        help="Absolute parent for independent tool root (not a lake root)",
    )
    p.add_argument(
        "--run-id",
        required=True,
        help="Run id under backtest_output/minute_orders_write_lake_staging/",
    )
    p.add_argument(
        "--print-must-cuts",
        action="store_true",
        help="Print MUST Human cuts to stdout after a successful dry-run plan",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.request.is_absolute():
            raise WriteLakeStagingError("--request must be an absolute path")
        if not args.parent.is_absolute():
            raise WriteLakeStagingError("--parent must be an absolute path")
        request = load_staging_request(args.request)
        outcome = run_write_lake_staging_dry_run(
            request=request,
            parent=args.parent,
            run_id=args.run_id,
        )
    except WriteLakeStagingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "tool_id": outcome.tool_id,
        "staging_status": outcome.staging_status,
        "report": str(outcome.report_path),
        "must_human_cuts": str(outcome.cuts_path),
        "notice": NOTICE,
    }, ensure_ascii=False, indent=2))
    if args.print_must_cuts:
        for cut in MUST_HUMAN_CUTS:
            print(f"- [{cut['id']}] {cut['cut']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
