"""Host CLI for infra's one-off L2 hive compactor.

An explicit host migration invocation retains its historical apply behavior;
--dry-run requests infra's read-only plan.
"""
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


def migrate_date(
    root: Path, date: str, *, memory_limit: str = "18GB", threads: int = 1,
    rebake_302: bool = False, keep_legacy: bool = False,
    apply: bool = True, temp_directory: str | Path | None = None,
) -> dict:
    return require_l2("maintenance.migrate_hive_compact").migrate_date(
        root, date, memory_limit=memory_limit, threads=threads,
        rebake_302=rebake_302, keep_legacy=keep_legacy,
        apply=apply, temp_directory=temp_directory,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", required=True, type=Path)
    parser.add_argument("--date", action="append", default=[])
    parser.add_argument("--all-legacy", action="store_true")
    parser.add_argument("--rebake-302", action="store_true")
    parser.add_argument("--keep-legacy", action="store_true")
    parser.add_argument("--memory-limit", default="18GB")
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--temp-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = require_l2("maintenance.migrate_hive_compact").migrate_hive_compact(
        args.out_root, dates=args.date, all_legacy=args.all_legacy,
        rebake_302=args.rebake_302, keep_legacy=args.keep_legacy,
        apply=not args.dry_run, memory_limit=args.memory_limit,
        threads=args.threads if args.threads > 0 else max(1, (os.cpu_count() or 4) - 1),
        temp_directory=args.temp_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
