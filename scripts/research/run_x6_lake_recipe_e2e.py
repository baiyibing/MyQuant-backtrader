"""True-core X6 · lake recipe e2e CLI (read-only load_minute_orders_source).

Completes the lake recipe path under tool_id=minute_orders_x6_lake after #309
boundary. tool_id is NOT a backend_id; reuses v0 identity labels only.
Lake recipe e2e load != host PASS; no lake write; does NOT unlock CLI
--evidence-level=lake; forever opt-in; never BOOKS default.
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

from backtest.research.minute_orders_x6_lake import (  # noqa: E402
    BACKEND_ID,
    CONTRACT,
    DIFFERENTIAL_ROOT_NAME,
    E2E_STATUS,
    LAKE_E2E_NOTICE,
    TOOL_ID,
    LakeRecipeE2EError,
    run_x6_lake_recipe_e2e,
)

HELP_DESCRIPTION = (
    "X6 lake recipe e2e (true-core): "
    f"tool_id={TOOL_ID} (NOT a backend_id). "
    "Calls load_minute_orders_source on a pinned lake+END recipe (read-only); "
    f"reuses contract={CONTRACT} / backend_id={BACKEND_ID} labels only. "
    f"e2e_status always {E2E_STATUS}; "
    "lake recipe e2e load != host PASS; independent tool root "
    f"{DIFFERENTIAL_ROOT_NAME}/<run_id>/e2e_report.json; "
    "never writes success summary.json; no lake write; "
    "does NOT unlock CLI --evidence-level=lake; does NOT run MatchCore fills."
)

HELP_EPILOG = f"""\
Identity:
  tool_id            {TOOL_ID}   (tooling only; NOT a backend_id)
  contract           {CONTRACT}  (documented; not minted)
  backend_id         {BACKEND_ID} (documented; not minted)
  e2e_status         always {E2E_STATUS}
  lake_e2e_notice    {LAKE_E2E_NOTICE}

Bans / out of scope:
  - source_kind=lake ONLY (synthetic_fixture masquerade refused)
  - bar_time_label=END + availability=bucket_end (Phase5 research path)
  - account_origin=synthetic_account; commands_origin=designed_limit_batch
    (enforced by tip load_minute_orders_source)
  - NO host attestation / lake PASS / green R / comparison authorization claims
  - NO lake write; NO success summary.json under research_v1
  - NO MatchCore fills / Fees rewrite / simulate edit
  - does NOT unlock backend CLI --evidence-level=lake (separate opt-in GO)
  - ≠δ5≠R4; forever opt-in; never BOOKS default
  - no 4090 / item-4 live host attestation

See docs/backtest/note-true-core-x6-lake-recipe-e2e-2026-10-02.md
"""


def _run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise argparse.ArgumentTypeError("run_id must be a single safe ASCII path component")
    return value


def _nonempty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("an explicit nonempty path is required")
    return value


def _sha256(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise argparse.ArgumentTypeError("expected_sha256 must be 64 hex chars")
    return value.lower()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_x6_lake_recipe_e2e.py",
        allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=HELP_DESCRIPTION,
        epilog=HELP_EPILOG,
    )
    parser.add_argument(
        "--recipe",
        type=_nonempty,
        required=True,
        help=(
            "absolute path to pinned minute_orders_source_recipe_v1 JSON "
            "(source_kind=lake; bars time.label=END; availability=bucket_end)"
        ),
    )
    parser.add_argument(
        "--expected-sha256",
        type=_sha256,
        required=True,
        help="pinned sha256 of the recipe file (64 hex)",
    )
    parser.add_argument(
        "--parent",
        type=_nonempty,
        help=(
            f"e2e parent directory; writes under "
            f"{{parent}}/{DIFFERENTIAL_ROOT_NAME}/{{run_id}}/ (required with --run-id)"
        ),
    )
    parser.add_argument(
        "--run-id",
        type=_run_id,
        help="new isolated e2e run identity; never overwrite",
    )
    parser.add_argument(
        "--memory-only",
        action="store_true",
        help="print report to stdout only; do not write e2e root",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    recipe = Path(args.recipe)
    if not recipe.is_absolute():
        print("error: --recipe must be an absolute path", file=sys.stderr)
        return 2

    write = not args.memory_only
    if write and (args.parent is None or args.run_id is None):
        print(
            "error: --parent and --run-id required unless --memory-only",
            file=sys.stderr,
        )
        return 2
    if args.memory_only and (args.parent is not None or args.run_id is not None):
        print(
            "error: --memory-only cannot combine with --parent/--run-id",
            file=sys.stderr,
        )
        return 2

    try:
        outcome = run_x6_lake_recipe_e2e(
            recipe,
            expected_sha256=args.expected_sha256,
            parent=None if args.memory_only else args.parent,
            run_id=None if args.memory_only else args.run_id,
        )
    except (LakeRecipeE2EError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(outcome.report, ensure_ascii=True, sort_keys=True, indent=2))
    if outcome.report_path is not None:
        print(f"wrote: {outcome.report_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
