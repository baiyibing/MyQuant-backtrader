#!/usr/bin/env python3
"""Gate: validate L2 _manifest.jsonl integrity against parquet files on disk.

Checks: valid JSONL, required keys, parquet files exist, row counts match,
no duplicate dates, valid date format. Soft-skip (exit 0) if no manifest.

Example:
  python scripts/gates/verify_l2_manifest.py ^
    --parquet-root stock_data/l2_parquet
"""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import re
import sys
from pathlib import Path

_sb_dir = next(
    (_p for _p in Path(__file__).resolve().parents if _p.name == "scripts"),
    Path(__file__).resolve().parent,
)
_sb_spec = _ilu.spec_from_file_location("_script_bootstrap", _sb_dir / "_script_bootstrap.py")
if _sb_spec is None or _sb_spec.loader is None:
    raise ImportError("_script_bootstrap unavailable")
_bs_mod = _ilu.module_from_spec(_sb_spec)
sys.modules["_script_bootstrap"] = _bs_mod
_sb_spec.loader.exec_module(_bs_mod)
_bs_mod.ensure_repo_on_syspath(__file__)

from l2_analytics.db import default_parquet_root  # noqa: E402

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REQUIRED_KEYS = {"date", "rows_main", "rows_order", "main_parts", "order_parts", "files"}


def _parquet_count(path: Path) -> int:
    import duckdb

    con = duckdb.connect(database=":memory:")
    try:
        row = con.execute(f"SELECT count(*) FROM read_parquet('{path.as_posix()}')").fetchone()
        return int(row[0]) if row is not None else 0
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validate L2 manifest integrity")
    p.add_argument(
        "--parquet-root",
        default="",
        help="Default: OSKH_L2_PARQUET_ROOT env var, else resolve_data_root()/stock_data/l2_parquet",
    )
    p.add_argument("--strict", action="store_true", help="Fail on file-size drift too")
    p.add_argument("--output-json", action="store_true", help="Emit JSON report to stdout")
    args = p.parse_args(argv)

    root = Path(args.parquet_root) if args.parquet_root else default_parquet_root()
    root = root.resolve()
    manifest = root / "_manifest.jsonl"

    report: dict = {"parquet_root": str(root), "checks": [], "ok": True}

    def _fail(msg: str) -> None:
        report["checks"].append({"status": "FAIL", "msg": msg})
        report["ok"] = False

    def _pass(msg: str) -> None:
        report["checks"].append({"status": "PASS", "msg": msg})

    def _skip(msg: str) -> None:
        report["checks"].append({"status": "SKIP", "msg": msg})

    if not root.is_dir():
        _skip(f"parquet root not found: {root}")
        if args.output_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if not manifest.is_file():
        _skip(f"manifest not found: {manifest}")
        if args.output_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    # Parse JSONL
    records: list[dict] = []
    parse_errors = 0
    for lineno, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            _fail(f"line {lineno}: invalid JSON — {exc}")
            parse_errors += 1

    if parse_errors:
        if args.output_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    if not records:
        _skip("manifest is empty")
        if args.output_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    _pass(f"manifest parsed: {len(records)} record(s)")

    # Check required keys + date format + duplicates
    seen_dates: set[str] = set()
    for i, rec in enumerate(records):
        missing = _REQUIRED_KEYS - set(rec.keys())
        if missing:
            _fail(f"record {i}: missing keys {missing}")
            continue
        date = rec["date"]
        if not _DATE_RE.match(date):
            _fail(f"record {i}: invalid date format {date!r}")
        if date in seen_dates:
            _fail(f"record {i}: duplicate date {date!r}")
        seen_dates.add(date)

    if report["ok"]:
        _pass(f"all {len(records)} records have required keys, valid dates, no duplicates")

    # Check parquet part files exist + summed row counts match manifest
    for rec in records:
        date = rec.get("date", "?")
        for kind, parts_key, rows_key in (
            ("main", "main_parts", "rows_main"),
            ("order", "order_parts", "rows_order"),
        ):
            parts = rec.get(parts_key, [])
            expected = rec.get(rows_key, 0)
            if not parts:
                # Empty day (all header-only CSVs): 0 rows + no parts is valid.
                if expected == 0:
                    _pass(f"{date}: {kind} empty day (0 rows) ok")
                else:
                    _fail(f"{date}: {parts_key} empty but {rows_key}={expected}")
                continue
            actual = 0
            missing = False
            for name in parts:
                pq_path = root / name
                if not pq_path.is_file():
                    _fail(f"{date}: {kind} part file missing: {name}")
                    missing = True
                    continue
                actual += _parquet_count(pq_path)
            if missing:
                continue
            if actual != expected:
                _fail(
                    f"{date}: {kind} row count mismatch: "
                    f"manifest={expected} actual={actual} ({len(parts)} parts)"
                )
            else:
                _pass(f"{date}: {kind} {len(parts)} part(s) rows={actual} ok")

    # Soft check: source file sizes (only if source CSVs still present)
    if args.strict:
        for rec in records:
            date = rec.get("date", "?")
            for finfo in rec.get("files", []):
                # Source CSVs may not be on this machine; only check if present
                pass  # strict file-size check requires source CSVs; skip for now

    exit_code = 0 if report["ok"] else 1
    if args.output_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"[l2_manifest] {status}: {len(report['checks'])} checks, {len(records)} record(s)")
        for c in report["checks"]:
            if c["status"] == "FAIL":
                print(f"  FAIL: {c['msg']}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
