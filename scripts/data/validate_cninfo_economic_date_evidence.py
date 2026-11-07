"""Validate a 1.3 economic-date evidence directory. Suggestions are not approval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oskh_data.cninfo_economic_date_targets import (  # noqa: E402
    TargetPackageError,
    validate_cninfo_economic_date_evidence,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--assembled-events", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_cninfo_economic_date_evidence(
            evidence_dir=args.evidence_dir,
            targets=args.targets,
            assembled_events=args.assembled_events,
            universe=args.universe,
            out=args.out,
            run_manifest=args.run_manifest,
        )
    except TargetPackageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
