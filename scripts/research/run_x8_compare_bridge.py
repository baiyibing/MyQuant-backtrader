"""TC4 · X8 comparison bridge CLI (red-label diagnostic only).

Pre-match intent snapshot ↔ X1 frozen-batch run. Independent comparison root;
comparison_status always no_ssot_compare_authorization; never writes success
summary.json. comparison_id is NOT a backend_id; reuses v0/X1. ≠δ5≠R4;
forever opt-in; never BOOKS default.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.minute_orders_x8_compare import (  # noqa: E402
    COMPARISON_ID,
    COMPARISON_ROOT_NAME,
    COMPARISON_STATUS,
    CompareBridgeError,
    CompareIngestError,
    load_prematch_intent_snapshot,
    run_x8_compare,
)

CONTRACT = "research contract v0 (L2-S0)"
BACKEND_ID = "minute_orders_research_v1"
ADAPTER_ID = "minute_orders_intent_x1"

HELP_DESCRIPTION = (
    "X8 comparison bridge (TC4): pre-match intent snapshot ↔ X1 frozen-batch. "
    f"comparison_id={COMPARISON_ID} (NOT a backend_id). "
    f"Reuses contract={CONTRACT} / backend_id={BACKEND_ID} via "
    f"adapter_id={ADAPTER_ID}. Red-label diagnostic only; "
    f"comparison_status always {COMPARISON_STATUS}; "
    "never writes success summary.json; independent comparison root "
    f"{COMPARISON_ROOT_NAME}/<run_id>/."
)

HELP_EPILOG = f"""\
Identity:
  comparison_id   {COMPARISON_ID}   (tooling only; NOT a backend_id)
  adapter_id      {ADAPTER_ID}      (reused X1; not minted here)
  contract        {CONTRACT}
  backend_id      {BACKEND_ID}      (reused; runner unchanged)
  comparison_status  always {COMPARISON_STATUS}

Bans / out of scope:
  - only 撮合前 / pre-match intent snapshots
  - NO fills→intent reconstruction
  - NO success summary.json (research-looking green run)
  - independent comparison root (NOT minute_orders_research_v1)
  - no new economic contract or backend_id for the runner
  - no MatchCore / Fees / simulate / VolumeCap edits
  - no NAV ranking; not fill-policy; ≠δ5≠R4
  - forever opt-in; never BOOKS default
  - no lake write; no X2–X5 / X6 true-lake / X7 _FAMILIES

See docs/backtest/note-true-core-tc4-x8-compare-bridge-2026-10-02.md
"""


def _run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise argparse.ArgumentTypeError("run_id must be a single safe ASCII path component")
    return value


def _nonempty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("an explicit nonempty path is required")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_x8_compare_bridge.py",
        allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=HELP_DESCRIPTION,
        epilog=HELP_EPILOG,
    )
    parser.add_argument(
        "--snapshot",
        type=_nonempty,
        required=True,
        help=(
            "path to pre-match intent snapshot JSON "
            "(schema=minute_orders_x8_prematch_intent_snapshot_v0); "
            "fills/trades payloads are refused"
        ),
    )
    parser.add_argument(
        "--preset",
        choices=("sketch_a",),
        default="sketch_a",
        help="synthetic market facts preset for the X1 run (default: sketch_a)",
    )
    parser.add_argument(
        "--parent",
        type=_nonempty,
        help=(
            f"comparison parent directory; writes under "
            f"{{parent}}/{COMPARISON_ROOT_NAME}/{{run_id}}/ (required with --run-id)"
        ),
    )
    parser.add_argument(
        "--run-id",
        type=_run_id,
        help="new isolated comparison run identity; never overwrite",
    )
    parser.add_argument(
        "--memory-only",
        action="store_true",
        help="print report to stdout only; do not write comparison root",
    )
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)

    try:
        snapshot = load_prematch_intent_snapshot(args.snapshot)
    except CompareIngestError as error:
        print(
            json.dumps(
                {
                    "status": "input_error",
                    "error_type": "CompareIngestError",
                    "reason": str(error),
                    "comparison_id": COMPARISON_ID,
                    "note": "fills→intent / malformed pre-match snapshot refused",
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "input_error",
                    "error_type": type(error).__name__,
                    "reason": str(error),
                    "comparison_id": COMPARISON_ID,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    write = not args.memory_only
    if write and (args.parent is None or args.run_id is None):
        print(
            json.dumps(
                {
                    "status": "input_error",
                    "reason": (
                        "writing requires --parent and --run-id "
                        "(or pass --memory-only)"
                    ),
                    "comparison_id": COMPARISON_ID,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    if args.memory_only and (args.parent is not None or args.run_id is not None):
        print(
            json.dumps(
                {
                    "status": "input_error",
                    "reason": "--memory-only cannot combine with --parent/--run-id",
                    "comparison_id": COMPARISON_ID,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    try:
        if write:
            outcome = run_x8_compare(
                snapshot,
                facts_preset=args.preset,
                parent=args.parent,
                run_id=args.run_id,
            )
        else:
            outcome = run_x8_compare(snapshot, facts_preset=args.preset)
    except FileExistsError as error:
        print(
            json.dumps(
                {
                    "status": "output_error",
                    "error_type": "FileExistsError",
                    "reason": str(error),
                    "comparison_id": COMPARISON_ID,
                    "note": "comparison root overwrite refused",
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 4
    except (CompareBridgeError, CompareIngestError) as error:
        print(
            json.dumps(
                {
                    "status": "output_error",
                    "error_type": type(error).__name__,
                    "reason": str(error),
                    "comparison_id": COMPARISON_ID,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 4
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "output_error",
                    "error_type": type(error).__name__,
                    "reason": str(error),
                    "comparison_id": COMPARISON_ID,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 4

    report = dict(outcome.report)
    if outcome.root is not None:
        report["root"] = str(outcome.root)
        report["report_path"] = str(outcome.report_path)
        # Hard check: no summary.json beside the report.
        summary = outcome.root / "summary.json"
        report["summary_json_absent"] = not summary.exists()
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))

    ok = (
        outcome.comparison_status == COMPARISON_STATUS
        and report.get("red_label") is True
        and report.get("intent_vs_frozen", {}).get("match") is True
    )
    if outcome.root is not None:
        ok = ok and report.get("summary_json_absent") is True
        ok = ok and (outcome.root / "summary.json").exists() is False
        ok = ok and (outcome.root / "comparison_report.json").is_file()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
