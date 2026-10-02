"""True-core X6 · synthetic_fixture / attestation differential CLI (NOT true lake).

Documents and hardens tip source_loader synthetic_fixture boundary (TC1 §5 X6).
tool_id is NOT a backend_id; reuses v0 identity labels only. Fixture PASS !=
lake PASS; no host attestation; forever opt-in; never BOOKS default.
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

from backtest.research.minute_orders_x6_synthetic import (  # noqa: E402
    BACKEND_ID,
    CONTRACT,
    DIFFERENTIAL_ROOT_NAME,
    DIFFERENTIAL_STATUS,
    FIXTURE_NOTICE,
    TOOL_ID,
    DifferentialError,
    DifferentialIngestError,
    load_synthetic_boundary_meta,
    run_x6_synthetic_differential,
)

HELP_DESCRIPTION = (
    "X6 synthetic_fixture / attestation differential (true-core): "
    f"tool_id={TOOL_ID} (NOT a backend_id). "
    f"Documents tip source_loader gap vs TC1 §5 X6; "
    f"reuses contract={CONTRACT} / backend_id={BACKEND_ID} labels only. "
    f"differential_status always {DIFFERENTIAL_STATUS}; "
    "Fixture PASS != lake PASS; independent tool root "
    f"{DIFFERENTIAL_ROOT_NAME}/<run_id>/; never writes success summary.json."
)

HELP_EPILOG = f"""\
Identity:
  tool_id            {TOOL_ID}   (tooling only; NOT a backend_id)
  contract           {CONTRACT}  (documented; not minted)
  backend_id         {BACKEND_ID} (documented; not minted)
  differential_status  always {DIFFERENTIAL_STATUS}
  fixture_notice     {FIXTURE_NOTICE}

Bans / out of scope:
  - synthetic_fixture ONLY (source_kind=lake refused; true lake = separate knife)
  - evidence_level=synthetic ONLY (no lake loader)
  - account_origin=synthetic_account; commands_origin=designed_limit_batch
  - NO host attestation / lake PASS / green R / comparison authorization claims
  - NO success summary.json
  - independent tool root (NOT minute_orders_research_v1)
  - no new economic contract or backend_id
  - no MatchCore / Fees / simulate / VolumeCap edits
  - ≠δ5≠R4; forever opt-in; never BOOKS default
  - no lake write; no X2–X5 / X7 _FAMILIES / X8 (separate knives)

See docs/backtest/note-true-core-x6-synthetic-attestation-2026-10-02.md
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
        prog="run_x6_synthetic_differential.py",
        allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=HELP_DESCRIPTION,
        epilog=HELP_EPILOG,
    )
    parser.add_argument(
        "--meta",
        type=_nonempty,
        required=True,
        help=(
            "path to X6 synthetic boundary meta JSON "
            "(schema=minute_orders_x6_synthetic_boundary_meta_v0); "
            "source_kind=lake / evidence_level=lake payloads are refused"
        ),
    )
    parser.add_argument(
        "--parent",
        type=_nonempty,
        help=(
            f"differential parent directory; writes under "
            f"{{parent}}/{DIFFERENTIAL_ROOT_NAME}/{{run_id}}/ (required with --run-id)"
        ),
    )
    parser.add_argument(
        "--run-id",
        type=_run_id,
        help="new isolated differential run identity; never overwrite",
    )
    parser.add_argument(
        "--memory-only",
        action="store_true",
        help="print report to stdout only; do not write differential root",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        meta = load_synthetic_boundary_meta(args.meta)
    except DifferentialIngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
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
        outcome = run_x6_synthetic_differential(
            meta,
            parent=None if args.memory_only else args.parent,
            run_id=None if args.memory_only else args.run_id,
        )
    except (DifferentialError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(outcome.report, ensure_ascii=True, sort_keys=True, indent=2))
    if outcome.report_path is not None:
        print(f"wrote: {outcome.report_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
