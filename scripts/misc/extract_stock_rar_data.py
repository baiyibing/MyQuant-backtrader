"""Host CLI/environment defaults for infra's offline date-archive unpacker."""
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

DEFAULT_7Z = Path(r"C:\Program Files\7-Zip\7z.exe")


def _resolve_dir(cli: Path | None, env_key: str, flag: str) -> Path:
    raw = str(cli or os.environ.get(env_key) or "").strip()
    if not raw:
        raise SystemExit(f"FAIL: pass {flag} or set {env_key}")
    return Path(raw)


def discover_archives(src: Path) -> list[Path]:
    return require_l2("ingest.archives").discover_archives(src)


def extract_one(seven_zip: Path, rar_path: Path, out_dir: Path) -> bool:
    return require_l2("ingest.archives").extract_one(seven_zip, rar_path, out_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path)
    parser.add_argument("--dst", type=Path)
    parser.add_argument("--seven-zip", type=Path, default=DEFAULT_7Z)
    parser.add_argument("--dates", nargs="*")
    parser.add_argument("--month")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-dates-file", type=Path)
    args = parser.parse_args(argv)
    source = _resolve_dir(args.src, "OSKH_STOCK_RAR_SRC", "--src")
    destination = _resolve_dir(args.dst, "OSKH_STOCK_CSV_DST", "--dst")
    skip = require_l2("ingest.cli")._skip_dates(args.skip_dates_file)
    result = require_l2("ingest.archives").unpack(
        src=source, dst=destination, seven_zip=args.seven_zip,
        dates=args.dates, month=args.month, force=args.force,
        skip_dates=skip, dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
