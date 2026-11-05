"""Recover surviving L2 work chunks through infra's verified publisher."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from l2_analytics._infra import require_l2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", required=True, type=Path)
    parser.add_argument("--date", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument("--memory-limit", default="18GB")
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--temp-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = require_l2("ingest.recovery").recover_day(
        root=args.out_root, date=args.date, source=args.source,
        temp_directory=args.temp_dir or args.out_root / "_duckdb_tmp",
        memory_limit=args.memory_limit,
        threads=args.threads if args.threads > 0 else max(1, (os.cpu_count() or 4) - 1),
        keep_work=args.keep_work, dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
