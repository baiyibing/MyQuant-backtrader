#!/usr/bin/env python3
"""Publish leftover ``_work_<date>`` chunk parquets as hive compact day files.

Recovery tool: if a run is killed after chunks are written but before publish,
compact surviving ``_work_<date>/{main,order}_NNNN.parquet`` into
``<out-root>/date=<date>/{main,order}.parquet`` and append ``_manifest.jsonl``.
"""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import os
import shutil
import sys
import time
from pathlib import Path

import duckdb

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

from l2_analytics.etl_day import (  # noqa: E402
    _append_manifest,
    _configure,
    _list_csv_files,
    _merge_chunks,
    _ratio,
)
from l2_analytics.paths import (  # noqa: E402
    list_legacy_flat_parts,
    main_parquet_path,
    order_parquet_path,
    rel_main_part,
    rel_order_part,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out-root", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--source", required=True, help="Original CSV day dir (for manifest)")
    p.add_argument("--keep-work", action="store_true")
    p.add_argument("--memory-limit", default="18GB")
    p.add_argument("--threads", type=int, default=0)
    args = p.parse_args(argv)

    root = Path(args.out_root)
    work = root / f"_work_{args.date}"
    main_chunks = sorted(work.glob("main_*.parquet"))
    order_chunks = sorted(work.glob("order_*.parquet"))
    if not main_chunks or len(main_chunks) != len(order_chunks):
        raise SystemExit(f"bad work dir: main={len(main_chunks)} order={len(order_chunks)}")

    t0 = time.perf_counter()
    main_out = main_parquet_path(root, args.date)
    order_out = order_parquet_path(root, args.date)
    main_out.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = root / "_duckdb_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    threads = args.threads if args.threads > 0 else max(1, (os.cpu_count() or 4) - 1)

    con = duckdb.connect(database=":memory:")
    try:
        _configure(con, memory_limit=args.memory_limit, threads=threads, temp_dir=tmp_dir)
        n_main, _ = _merge_chunks(con, chunk_paths=main_chunks, final_path=main_out)
        n_order, _ = _merge_chunks(con, chunk_paths=order_chunks, final_path=order_out)
    finally:
        con.close()

    legacy_m, legacy_o = list_legacy_flat_parts(root, args.date)
    for old in [*legacy_m, *legacy_o]:
        old.unlink(missing_ok=True)

    main_parts = [rel_main_part(args.date)]
    order_parts = [rel_order_part(args.date)]
    print(f"published hive compact in {time.perf_counter() - t0:.2f}s", flush=True)

    source = Path(args.source)
    csv_files = _list_csv_files(source)
    src_bytes = sum(path.stat().st_size for path in csv_files)
    _append_manifest(
        root / "_manifest.jsonl",
        date=args.date,
        files=csv_files,
        rows_main=n_main,
        rows_order=n_order,
        main_parts=main_parts,
        order_parts=order_parts,
    )

    con = duckdb.connect(":memory:")
    sample = con.execute(
        f"""
        SELECT stock_code, instrument_type, session, count(*) AS n
        FROM read_parquet('{main_out.as_posix()}')
        WHERE stock_code = '000001.SZ'
        GROUP BY 1, 2, 3
        ORDER BY n DESC
        """
    ).fetchall()
    codes = con.execute(
        f"""
        SELECT instrument_type, count(DISTINCT stock_code) AS n
        FROM read_parquet('{main_out.as_posix()}')
        GROUP BY 1
        ORDER BY n DESC
        """
    ).fetchall()
    con.close()

    import pyarrow.parquet as pq

    bad = 0
    prev: str | None = None
    pf = pq.ParquetFile(main_out)
    for batch in pf.iter_batches(columns=["stock_code"], batch_size=1_000_000):
        for val in batch.column(0).to_pylist():
            if prev is not None and val < prev:
                bad += 1
            prev = val

    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)

    main_bytes = main_out.stat().st_size
    order_bytes = order_out.stat().st_size
    out = {
        "rows_main": n_main,
        "rows_order": n_order,
        "main_bytes": main_bytes,
        "order_bytes": order_bytes,
        "source_csv_bytes": src_bytes,
        "compress_ratio": _ratio(src_bytes, main_bytes + order_bytes),
        "publish_elapsed_s": time.perf_counter() - t0,
        "sample_000001_sessions": [list(x) for x in sample],
        "instrument_distinct": [list(x) for x in codes],
        "sort_regressions": int(bad),
        "main_parts": main_parts,
        "order_parts": order_parts,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bad == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
