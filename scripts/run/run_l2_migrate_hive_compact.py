#!/usr/bin/env python3
"""Migrate legacy flat L2 part-files into hive ``date=D/{main,order}.parquet``.

Compacts ``{date}.part-NNNN.{main,order}.parquet`` via ordered pyarrow concat
(same as ETL publish). Updates ``_manifest.jsonl`` part lists. Optionally
rewrites ``instrument_type`` for 302* → stock (rebake).
"""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import os
import re
import sys
import time
from pathlib import Path

import duckdb

_sb_dir = next(
    (_p for _p in Path(__file__).resolve().parents if (_p.name == "scripts")),
    Path(__file__).resolve().parent,
)
_sb_spec = _ilu.spec_from_file_location("_script_bootstrap", _sb_dir / "_script_bootstrap.py")
if _sb_spec is None or _sb_spec.loader is None:
    raise ImportError("_script_bootstrap unavailable")
_bs_mod = _ilu.module_from_spec(_sb_spec)
sys.modules["_script_bootstrap"] = _bs_mod
_sb_spec.loader.exec_module(_bs_mod)
_bs_mod.ensure_repo_on_syspath(__file__)

from l2_analytics.etl_day import _configure, _merge_chunks  # noqa: E402
from l2_analytics.paths import (  # noqa: E402
    list_legacy_flat_parts,
    main_parquet_path,
    order_parquet_path,
    rel_main_part,
    rel_order_part,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _dates_with_legacy(root: Path) -> list[str]:
    found: set[str] = set()
    for p in root.glob("*.part-*.main.parquet"):
        d = p.name.split(".part-", 1)[0]
        if _DATE_RE.match(d):
            found.add(d)
    return sorted(found)


def _rewrite_manifest_parts(root: Path, date: str) -> None:
    manifest = root / "_manifest.jsonl"
    if not manifest.is_file():
        return
    lines: list[dict] = []
    with manifest.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("date") == date:
                obj["main_parts"] = [rel_main_part(date)]
                obj["order_parts"] = [rel_order_part(date)]
            lines.append(obj)
    tmp = manifest.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for obj in lines:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
    os.replace(tmp, manifest)


def _rebake_302(path: Path) -> int:
    """Rewrite instrument_type for 302* codes; return rows that needed fix."""
    con = duckdb.connect(database=":memory:")
    try:
        row = con.execute(
            f"""
                SELECT count(*) FROM read_parquet('{path.as_posix()}')
                WHERE split_part(stock_code, '.', 1) LIKE '302%'
                  AND instrument_type <> 'stock'
                """
        ).fetchone()
        n = int(row[0]) if row is not None else 0
        if n == 0:
            return 0
        tmp = path.with_name(path.name + ".rebake.tmp")
        if tmp.exists():
            tmp.unlink()
        con.execute(
            f"""
            COPY (
              SELECT * REPLACE (
                CASE
                  WHEN split_part(stock_code, '.', 1) LIKE '302%'
                       AND instrument_type <> 'stock'
                  THEN 'stock'
                  ELSE instrument_type
                END AS instrument_type
              )
              FROM read_parquet('{path.as_posix()}')
            ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
        os.replace(tmp, path)
        return n
    finally:
        con.close()


def migrate_date(
    root: Path,
    date: str,
    *,
    memory_limit: str,
    threads: int,
    rebake_302: bool,
    keep_legacy: bool,
) -> dict:
    t0 = time.perf_counter()
    mains, orders = list_legacy_flat_parts(root, date)
    main_out = main_parquet_path(root, date)
    order_out = order_parquet_path(root, date)
    if not mains:
        if main_out.is_file() and order_out.is_file():
            touched = 0
            if rebake_302:
                touched = _rebake_302(main_out) + _rebake_302(order_out)
            return {
                "date": date,
                "status": "already_hive",
                "rebake_302_rows": touched,
                "elapsed_s": time.perf_counter() - t0,
            }
        return {"date": date, "status": "no_parts", "elapsed_s": time.perf_counter() - t0}
    if len(mains) != len(orders):
        raise SystemExit(f"{date}: main parts {len(mains)} != order parts {len(orders)}")

    main_out.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = root / "_duckdb_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(database=":memory:")
    try:
        _configure(con, memory_limit=memory_limit, threads=threads, temp_dir=tmp_dir)
        n_m, _ = _merge_chunks(con, chunk_paths=mains, final_path=main_out)
        n_o, _ = _merge_chunks(con, chunk_paths=orders, final_path=order_out)
    finally:
        con.close()

    if not keep_legacy:
        for p in [*mains, *orders]:
            p.unlink(missing_ok=True)
    _rewrite_manifest_parts(root, date)

    rebake_n = 0
    if rebake_302:
        rebake_n = _rebake_302(main_out) + _rebake_302(order_out)

    # Migrate legacy flat aggs into hive day dir if present.
    for kind in ("daily_metrics", "cluster_agg"):
        legacy = root / f"{date}.{kind}.parquet"
        target = main_out.parent / f"{kind}.parquet"
        if legacy.is_file() and not target.is_file():
            os.replace(legacy, target)
        elif legacy.is_file() and target.is_file():
            legacy.unlink()

    return {
        "date": date,
        "status": "migrated",
        "rows_main": n_m,
        "rows_order": n_o,
        "main": str(main_out),
        "order": str(order_out),
        "rebake_302_rows": rebake_n,
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-root", required=True, help="l2_parquet root")
    p.add_argument("--date", action="append", default=[], help="YYYY-MM-DD (repeatable)")
    p.add_argument("--all-legacy", action="store_true", help="All dates with flat parts")
    p.add_argument("--rebake-302", action="store_true", help="Fix 302* instrument_type")
    p.add_argument("--keep-legacy", action="store_true", help="Keep flat parts after compact")
    p.add_argument("--memory-limit", default="18GB")
    p.add_argument("--threads", type=int, default=0)
    args = p.parse_args(argv)

    root = Path(args.out_root).resolve()
    if not root.is_dir():
        raise SystemExit(f"out-root not found: {root}")
    dates = list(args.date)
    if args.all_legacy:
        dates = sorted(set(dates) | set(_dates_with_legacy(root)))
    if not dates and args.rebake_302:
        # hive-only rebake
        dates = sorted(
            p.parent.name.removeprefix("date=")
            for p in root.glob("date=*/main.parquet")
            if _DATE_RE.match(p.parent.name.removeprefix("date="))
        )
    if not dates:
        raise SystemExit("no dates: pass --date / --all-legacy / --rebake-302 on hive")

    threads = args.threads if args.threads > 0 else max(1, (os.cpu_count() or 4) - 1)
    results = []
    for d in dates:
        if not _DATE_RE.match(d):
            raise SystemExit(f"bad date: {d}")
        print(f"[migrate] {d} …", flush=True)
        results.append(
            migrate_date(
                root,
                d,
                memory_limit=args.memory_limit,
                threads=threads,
                rebake_302=args.rebake_302,
                keep_legacy=args.keep_legacy,
            )
        )
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    print(json.dumps({"dates": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
