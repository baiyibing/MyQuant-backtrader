"""Export a read-only CNINFO economic-date target file. Not a lake merge."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oskh_data.cninfo_economic_date_targets import (  # noqa: E402
    TargetPackageError,
    export_cninfo_economic_date_targets,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembled-events", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--window-start", type=date.fromisoformat, required=True)
    parser.add_argument("--window-end", type=date.fromisoformat, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--d11-codes", type=Path)
    parser.add_argument("--run-manifest", type=Path)
    parser.add_argument("--run-hash")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        export_cninfo_economic_date_targets(
            assembled_events=args.assembled_events,
            universe=args.universe,
            out=args.out,
            window_start=args.window_start,
            window_end=args.window_end,
            d11_codes=args.d11_codes,
            run_manifest=args.run_manifest,
            run_hash=args.run_hash,
        )
    except TargetPackageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
