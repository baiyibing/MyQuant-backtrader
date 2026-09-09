"""P0a: one trading-day L2 CSV directory -> main/order Parquet (DuckDB).

Chunked ETL keeps peak spill small on disk-constrained workstations
(~13GB CSV/day, limited free NVMe).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import duckdb

# Sampled content fingerprint: head+tail (full file when small). Distinguishes
# same-size content swaps that (name, size) alone would miss (r5 🟡-5).
_CONTENT_HASH_CHUNK = 1_048_576

from l2_analytics.db import default_parquet_root
from l2_analytics.paths import (
    list_legacy_flat_parts,
    main_parquet_path,
    order_parquet_path,
    rel_main_part,
    rel_order_part,
)
from l2_analytics.perf import (
    bytes_to_gb,
    note_peak,
    note_temp_peak,
    process_rss_bytes,
)
from oskh_core.a_share_symbol_normalize import (
    canonical_from_bare_code,
    classify_instrument_type,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# DuckDB default; plan: do not enlarge (hurts A-mode pruning).
_ROW_GROUP_SIZE = 122880


@dataclass
class DayEtlResult:
    date: str
    source_dir: str
    csv_files: int
    empty_files: int
    rows_main: int
    rows_order: int
    main_parquet: str
    order_parquet: str
    main_bytes: int
    order_bytes: int
    source_csv_bytes: int
    compress_ratio: float
    elapsed_s: float
    chunks: int = 0
    skipped: bool = False
    gap_free_ok: bool = True
    gap_free_failures: list[str] = field(default_factory=list)
    instrument_counts: dict[str, int] = field(default_factory=dict)
    notes: str = ""
    profile: dict[str, Any] = field(default_factory=dict)


def _scan_csv_files(source_dir: Path) -> tuple[list[Path], dict[str, os.stat_result]]:
    """Single ``os.scandir`` pass: return sorted CSV paths + a stat cache.

    opt #7: DirEntry.stat() is cached by the OS during scandir, so callers reuse
    sizes/mtimes without re-issuing a ``stat()`` syscall per file (source bytes,
    per-chunk bytes, and manifest fingerprints all read from this one pass).
    """
    paths: list[Path] = []
    stat_by_path: dict[str, os.stat_result] = {}
    with os.scandir(source_dir) as it:
        for entry in it:
            if entry.is_file() and entry.name.lower().endswith(".csv"):
                p = Path(entry.path)
                paths.append(p)
                stat_by_path[str(p)] = entry.stat()
    paths.sort(key=lambda p: p.stem)
    return paths, stat_by_path


def _list_csv_files(source_dir: Path) -> list[Path]:
    return _scan_csv_files(source_dir)[0]


def _is_header_only_csv(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            if next(reader, None) is None:
                return True
            return next(reader, None) is None
    except OSError:
        return True


def _session_sql(time_col: str = "Time") -> str:
    """Session bucket via CAST to TIME (r5 🟡-3: VARCHAR comparison breaks if
    Time is not zero-padded — '9:30:00' > '14:57:00' lexicographically)."""
    tc = f"CAST({time_col} AS TIME)"
    return f"""
    CASE
      WHEN {tc} < TIME '09:30:00' THEN 'pre_open'
      WHEN {tc} <= TIME '11:30:00' THEN 'continuous_am'
      WHEN {tc} < TIME '13:00:00' THEN 'other'
      WHEN {tc} < TIME '14:57:00' THEN 'continuous_pm'
      ELSE 'close_auction'
    END
    """


def _ratio(src: int, dst: int) -> float:
    if dst <= 0:
        return 0.0
    return float(src) / float(dst)


def _parquet_count(path: Path) -> int:
    con = duckdb.connect(database=":memory:")
    try:
        return int(con.execute(f"SELECT count(*) FROM read_parquet('{path.as_posix()}')").fetchone()[0])
    finally:
        con.close()


def _file_content_hash(path: Path, *, size: int | None = None) -> str:
    """Blake2b hex of head+tail chunks (+ size), cheap vs hashing 13GB/day."""
    n = int(size) if size is not None else int(path.stat().st_size)
    h = hashlib.blake2b(digest_size=16)
    h.update(n.to_bytes(8, "little"))
    if n <= 0:
        return h.hexdigest()
    with path.open("rb") as fh:
        if n <= 2 * _CONTENT_HASH_CHUNK:
            h.update(fh.read())
        else:
            h.update(fh.read(_CONTENT_HASH_CHUNK))
            fh.seek(n - _CONTENT_HASH_CHUNK)
            h.update(fh.read(_CONTENT_HASH_CHUNK))
    return h.hexdigest()


def _file_fp(path: Path, st: os.stat_result | None = None) -> dict[str, Any]:
    if st is None:
        st = path.stat()
    size = int(st.st_size)
    return {
        "name": path.name,
        "size": size,
        "mtime_ns": int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))),
        "content_hash": _file_content_hash(path, size=size),
    }


def _append_manifest(
    manifest_path: Path,
    *,
    date: str,
    files: list[Path],
    rows_main: int,
    rows_order: int,
    main_parts: list[str],
    order_parts: list[str],
    stat_by_path: dict[str, os.stat_result] | None = None,
) -> None:
    cache = stat_by_path or {}
    rec = {
        "date": date,
        "rows_main": rows_main,
        "rows_order": rows_order,
        "main_parts": main_parts,
        "order_parts": order_parts,
        "files": [_file_fp(p, cache.get(str(p))) for p in files],
    }
    existing: list[dict[str, Any]] = []
    if manifest_path.is_file():
        with manifest_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("date") != date:
                    existing.append(obj)
    existing.append(rec)
    tmp = manifest_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for obj in existing:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
    os.replace(tmp, manifest_path)


def _manifest_record(manifest_path: Path, date: str) -> dict[str, Any] | None:
    if not manifest_path.is_file():
        return None
    with manifest_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("date") == date:
                return obj
    return None


def _manifest_matches(
    manifest_path: Path,
    date: str,
    files: list[Path],
    stat_by_path: dict[str, os.stat_result] | None = None,
) -> bool:
    obj = _manifest_record(manifest_path, date)
    if obj is None:
        return False
    cache = stat_by_path or {}
    want_fps = [_file_fp(p, cache.get(str(p))) for p in files]
    got_list = list(obj.get("files", []))
    # Legacy manifests (pre content_hash): fall back to (name, size) only.
    legacy = any("content_hash" not in x for x in got_list) if got_list else False
    if legacy:
        want = {(f["name"], f["size"]) for f in want_fps}
        got = {(x["name"], x["size"]) for x in got_list}
        return want == got
    want = {(f["name"], f["size"], f["content_hash"]) for f in want_fps}
    got = {(x["name"], x["size"], x.get("content_hash")) for x in got_list}
    return want == got


def _configure(con: duckdb.DuckDBPyConnection, *, memory_limit: str, threads: int, temp_dir: Path) -> None:
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"SET threads={int(threads)}")
    con.execute(f"SET temp_directory='{temp_dir.as_posix()}'")
    con.execute("SET preserve_insertion_order=false")


def _select_gap_free_targets(
    files: list[Path],
    *,
    sample: int,
    size_by_path: dict[str, int] | None = None,
) -> list[Path]:
    """Pick gap-free targets: full set, or size-stratified sample (r5 🟡-4).

    ``sample <= 0`` or ``sample >= len(files)`` → all files.
    Otherwise: heaviest ``sample//2`` by size + evenly spaced remainder (avoids
    stem-sorted head bias that only checked 000xxx).
    """
    if sample <= 0 or sample >= len(files):
        return list(files)
    sizes = size_by_path or {}

    def _sz(p: Path) -> int:
        return int(sizes.get(str(p), 0) or p.stat().st_size)

    by_size = sorted(files, key=_sz, reverse=True)
    n_heavy = max(1, sample // 2)
    heavy = by_size[:n_heavy]
    rest = by_size[n_heavy:]
    picked: list[Path] = list(heavy)
    need = sample - len(picked)
    if need > 0 and rest:
        if need >= len(rest):
            picked.extend(rest)
        else:
            step = len(rest) / need
            for i in range(need):
                picked.append(rest[min(len(rest) - 1, int(i * step))])
    # Stable unique preserve order
    seen: set[str] = set()
    out: list[Path] = []
    for p in picked:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _check_gap_free(
    files: list[Path],
    *,
    sample: int,
    size_by_path: dict[str, int] | None = None,
) -> list[str]:
    targets = _select_gap_free_targets(files, sample=sample, size_by_path=size_by_path)
    if not targets:
        return []
    # opt #8: one grouped query over the sampled file list (filename=true) instead of
    # N per-file queries. parse_filename(filename, true) yields the bare code (== stem).
    name_by_bare = {p.stem.strip(): p.name for p in targets}
    file_list_sql = "[" + ", ".join(f"'{p.as_posix()}'" for p in targets) + "]"
    failures: list[str] = []
    con = duckdb.connect(database=":memory:")
    try:
        rows = con.execute(
            f"""
            SELECT
              parse_filename(filename, true) AS bare,
              count(*)::BIGINT AS n,
              min(TranID)::BIGINT AS mn,
              max(TranID)::BIGINT AS mx
            FROM read_csv({file_list_sql}, header=true, auto_detect=true, filename=true)
            GROUP BY 1
            """
        ).fetchall()
        for bare, n, mn, mx in rows:
            if n == 0:
                continue
            if mn != 1 or mx != n:
                name = name_by_bare.get(bare, f"{bare}.csv")
                failures.append(f"{name}: n={n} min={mn} max={mx}")
    finally:
        con.close()
    return failures


def _write_chunk(
    con: duckdb.DuckDBPyConnection,
    *,
    date: str,
    files: list[Path],
    main_out: Path,
    order_out: Path,
    size_by_path: dict[str, int] | None = None,
) -> tuple[int, int, dict[str, float]]:
    """Read a contiguous bare_code range; write ordered main/order chunk parquets.

    Returns ``(rows_main, rows_order, profile)`` where *profile* carries
    per-phase wall-clock seconds for optimization analysis.
    """
    t_all = time.perf_counter()
    prof: dict[str, float] = {}
    sizes = size_by_path or {}
    csv_bytes = sum(sizes.get(str(p), 0) or p.stat().st_size for p in files)
    prof["csv_bytes"] = float(csv_bytes)

    t_sym = time.perf_counter()
    sym_rows = []
    for path in files:
        bare = path.stem.strip()
        sym_rows.append((bare, canonical_from_bare_code(bare), classify_instrument_type(bare)))

    con.execute("DROP TABLE IF EXISTS symbol_map")
    con.execute(
        """
        CREATE TEMP TABLE symbol_map (
          bare_code VARCHAR,
          stock_code VARCHAR,
          instrument_type VARCHAR
        )
        """
    )
    con.executemany("INSERT INTO symbol_map VALUES (?, ?, ?)", sym_rows)
    prof["sym_map_s"] = time.perf_counter() - t_sym

    # Explicit file list avoids glob + keeps chunk bounded.
    file_list_sql = "[" + ", ".join(f"'{p.as_posix()}'" for p in files) + "]"
    session_sql = _session_sql("Time")

    t_enrich = time.perf_counter()
    con.execute("DROP TABLE IF EXISTS enriched")
    con.execute(
        f"""
        CREATE TEMP TABLE enriched AS
        SELECT
          r.TranID::BIGINT AS TranID,
          r.Time::VARCHAR AS Time,
          -- Price: TRY_CAST(DECIMAL(10,3)) — 真实 A 股价 max ~3600 装得下；
          -- 哨兵/离群值 (e.g. 4e7) 溢出 → NULL（评审 #2：CAST 会硬崩整 chunk；
          -- TRY_CAST 不崩 + 保留行 gap-free + NULL 被 SUM(Volume*Price) 自然排除）。
          TRY_CAST(r.Price AS DECIMAL(10,3)) AS Price,
          r.Volume::BIGINT AS Volume,
          r.SaleOrderVolume::BIGINT AS SaleOrderVolume,
          r.BuyOrderVolume::BIGINT AS BuyOrderVolume,
          r.Type::VARCHAR AS Type,
          r.SaleOrderID::BIGINT AS SaleOrderID,
          CAST(r.SaleOrderPrice AS DECIMAL(18,3)) AS SaleOrderPrice,
          r.BuyOrderID::BIGINT AS BuyOrderID,
          CAST(r.BuyOrderPrice AS DECIMAL(18,3)) AS BuyOrderPrice,
          m.stock_code,
          DATE '{date}' AS date,
          m.instrument_type,
          timezone(
            'UTC',
            strptime('{date}' || ' ' || r.Time::VARCHAR, '%Y-%m-%d %H:%M:%S')
              AT TIME ZONE 'Asia/Shanghai'
          ) AS ts,
          CAST(r.Time AS TIME) AS trade_time,
          {session_sql} AS session
        -- opt #1: explicit VARCHAR columns + auto_detect=false 跳过 DuckDB 全文件
        -- 嗅探（sample_size=-1 曾在 CREATE 阶段整包扫一遍）；类型由上方 CAST/TRY_CAST
        -- 决定，语义不变。交易所 L2 dump schema 统一，故去 union_by_name。
        FROM read_csv(
          {file_list_sql},
          header=true,
          filename=true,
          auto_detect=false,
          parallel=true,
          columns={{
            'TranID': 'VARCHAR',
            'Time': 'VARCHAR',
            'Price': 'VARCHAR',
            'Volume': 'VARCHAR',
            'SaleOrderVolume': 'VARCHAR',
            'BuyOrderVolume': 'VARCHAR',
            'Type': 'VARCHAR',
            'SaleOrderID': 'VARCHAR',
            'SaleOrderPrice': 'VARCHAR',
            'BuyOrderID': 'VARCHAR',
            'BuyOrderPrice': 'VARCHAR'
          }}
        ) r
        INNER JOIN symbol_map m
          ON parse_filename(r.filename, true) = m.bare_code
        WHERE r.Type IN ('B', 'S')
          AND r.Price IS NOT NULL
          AND TRY_CAST(r.Price AS DOUBLE) > 0
        """
    )
    prof["enrich_s"] = time.perf_counter() - t_enrich

    t_main = time.perf_counter()
    n_main = int(
        con.execute(
            f"""
        COPY (
          SELECT
            stock_code, date, TranID, Time, trade_time, ts, session, instrument_type,
            Price, Volume, SaleOrderVolume, BuyOrderVolume, Type
          FROM enriched
          ORDER BY stock_code, TranID
        ) TO '{main_out.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE {_ROW_GROUP_SIZE})
        """
        ).fetchone()[0]
    )
    prof["main_copy_s"] = time.perf_counter() - t_main
    prof["main_bytes"] = float(main_out.stat().st_size)

    t_order = time.perf_counter()
    n_order = int(
        con.execute(
            f"""
        COPY (
          SELECT stock_code, date, TranID, SaleOrderID, SaleOrderPrice, BuyOrderID, BuyOrderPrice
          FROM enriched
          ORDER BY stock_code, TranID
        ) TO '{order_out.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE {_ROW_GROUP_SIZE})
        """
        ).fetchone()[0]
    )
    prof["order_copy_s"] = time.perf_counter() - t_order
    prof["order_bytes"] = float(order_out.stat().st_size)

    con.execute("DROP TABLE IF EXISTS enriched")
    prof["chunk_total_s"] = time.perf_counter() - t_all
    return n_main, n_order, prof


def _merge_chunks(
    con: duckdb.DuckDBPyConnection,
    *,
    chunk_paths: list[Path],
    final_path: Path,
) -> tuple[int, float]:
    """Concatenate range-sorted chunks in order (no global re-sort).

    Chunks are produced from contiguous ``bare_code`` ranges already
    ``ORDER BY stock_code, TranID``, so file-order concat is globally sorted
    and avoids a full external sort (disk-spike on constrained NVMe).

    Source chunks are left in place; caller removes the work directory after
    both finals are atomically published (avoids Windows file-lock races).

    Returns ``(row_count, elapsed_seconds)``.
    """
    t0 = time.perf_counter()
    if not chunk_paths:
        raise ValueError("no chunks to merge")
    if len(chunk_paths) == 1:
        shutil.copy2(chunk_paths[0], final_path)
        n = int(con.execute(f"SELECT count(*) FROM read_parquet('{final_path.as_posix()}')").fetchone()[0])
        return n, time.perf_counter() - t0

    import pyarrow.parquet as pq

    tmp = final_path.with_name(final_path.name + ".merge.tmp")
    if tmp.exists():
        tmp.unlink()
    first = pq.ParquetFile(chunk_paths[0])
    schema = first.schema_arrow
    del first
    writer = pq.ParquetWriter(tmp, schema, compression="zstd")
    try:
        for idx, path in enumerate(chunk_paths):
            pf = pq.ParquetFile(path)
            try:
                for batch in pf.iter_batches(batch_size=_ROW_GROUP_SIZE):
                    writer.write_batch(batch)
            finally:
                del pf
            if (idx + 1) % 4 == 0 or idx + 1 == len(chunk_paths):
                print(f"[l2_etl] merge {final_path.name}: {idx + 1}/{len(chunk_paths)}", flush=True)
    finally:
        writer.close()
    os.replace(tmp, final_path)
    n = int(con.execute(f"SELECT count(*) FROM read_parquet('{final_path.as_posix()}')").fetchone()[0])
    return n, time.perf_counter() - t0


def etl_one_day(
    source_dir: str | Path,
    *,
    out_root: Optional[str | Path] = None,
    memory_limit: str = "18GB",
    threads: Optional[int] = None,
    temp_directory: Optional[str | Path] = None,
    chunk_files: int = 400,
    force: bool = False,
    validate_gap_free: bool = True,
    gap_free_sample: int = 0,
    max_files: int = 0,
) -> DayEtlResult:
    """Convert one ``YYYY-MM-DD`` L2 CSV directory to main+order Parquet.

    ``max_files``: if > 0, only process the first N CSVs (smoke). 0 = all.
    """
    t0 = time.perf_counter()
    source = Path(source_dir).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"source_dir not found: {source}")
    date = source.name
    if not _DATE_RE.match(date):
        raise ValueError(f"source directory name must be YYYY-MM-DD, got {date!r}")

    data_root = Path(out_root) if out_root else default_parquet_root()
    data_root.mkdir(parents=True, exist_ok=True)
    # v5.9: hive day dir + compact 1 file/table (pyarrow ordered concat of
    # range-sorted chunks — no DuckDB global ORDER BY spill).
    main_out = main_parquet_path(data_root, date)
    order_out = order_parquet_path(data_root, date)
    main_rel = rel_main_part(date)
    order_rel = rel_order_part(date)
    main_path_str = main_out.as_posix()
    order_path_str = order_out.as_posix()
    manifest_path = data_root / "_manifest.jsonl"
    work_dir = data_root / f"_work_{date}"
    tmp_dir = Path(temp_directory) if temp_directory else (data_root / "_duckdb_tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    peak_rss: list[int | None] = [None]
    peak_rss_chunk: list[int | None] = [None]
    peak_rss_compact: list[int | None] = [None]
    peak_temp: list[int | None] = [None]
    note_peak(peak_rss)
    note_temp_peak(peak_temp, tmp_dir)

    t_scan = time.perf_counter()
    csv_files, stat_by_path = _scan_csv_files(source)
    if max_files > 0:
        csv_files = csv_files[:max_files]
    if not csv_files:
        raise FileNotFoundError(f"no *.csv under {source}")
    size_by_path = {k: int(v.st_size) for k, v in stat_by_path.items()}

    empty_files = [p for p in csv_files if _is_header_only_csv(p)]
    non_empty = [p for p in csv_files if p not in set(empty_files)]
    source_csv_bytes = sum(size_by_path.get(str(p), 0) for p in csv_files)

    instrument_counts: dict[str, int] = {}
    for path in csv_files:
        itype = classify_instrument_type(path.stem)
        instrument_counts[itype] = instrument_counts.get(itype, 0) + 1
    scan_s = time.perf_counter() - t_scan

    if not force and max_files <= 0:
        rec = _manifest_record(manifest_path, date)
        if rec is not None and _manifest_matches(manifest_path, date, csv_files, stat_by_path):
            skip_main_parts = list(rec.get("main_parts", []))
            skip_order_parts = list(rec.get("order_parts", []))
            all_parts = [*skip_main_parts, *skip_order_parts]
            # Prefer hive paths; also accept legacy flat part names in old manifests.
            parts_ok = bool(all_parts) and all((data_root / n).is_file() for n in all_parts)
            if not parts_ok and main_out.is_file() and order_out.is_file():
                skip_main_parts = [main_rel]
                skip_order_parts = [order_rel]
                all_parts = [*skip_main_parts, *skip_order_parts]
                parts_ok = True
            if parts_ok:
                main_bytes = sum((data_root / n).stat().st_size for n in skip_main_parts)
                order_bytes = sum((data_root / n).stat().st_size for n in skip_order_parts)
                return DayEtlResult(
                    date=date,
                    source_dir=str(source),
                    csv_files=len(csv_files),
                    empty_files=len(empty_files),
                    rows_main=int(rec.get("rows_main", 0)),
                    rows_order=int(rec.get("rows_order", 0)),
                    main_parquet=main_path_str,
                    order_parquet=order_path_str,
                    main_bytes=main_bytes,
                    order_bytes=order_bytes,
                    source_csv_bytes=source_csv_bytes,
                    compress_ratio=_ratio(source_csv_bytes, main_bytes + order_bytes),
                    elapsed_s=time.perf_counter() - t0,
                    skipped=True,
                    instrument_counts=instrument_counts,
                    notes="idempotent skip (manifest match)",
                )
            # Empty-day idempotent skip: manifest match with 0 rows + no parts.
            if not all_parts and int(rec.get("rows_main", 0)) == 0:
                return DayEtlResult(
                    date=date,
                    source_dir=str(source),
                    csv_files=len(csv_files),
                    empty_files=len(empty_files),
                    rows_main=0,
                    rows_order=0,
                    main_parquet=main_path_str,
                    order_parquet=order_path_str,
                    main_bytes=0,
                    order_bytes=0,
                    source_csv_bytes=source_csv_bytes,
                    compress_ratio=0.0,
                    elapsed_s=time.perf_counter() - t0,
                    skipped=True,
                    instrument_counts=instrument_counts,
                    notes="idempotent skip (empty day)",
                )

    # Empty day: CSVs exist but all are header-only (0 usable rows). Record an
    # empty manifest and return gracefully (do NOT raise) so the multi-day
    # orchestrator doesn't choke. "No CSVs at all" already raised above.
    if not non_empty:
        # r5 🔴-2: Guard against data-loss — refuse to silently delete existing
        # non-empty parquet (bad re-download / stale CSV could erase ~2.27GB good data).
        legacy_mains, _ = list_legacy_flat_parts(data_root, date)
        existing = ([main_out] if main_out.is_file() else []) + legacy_mains
        if existing:
            raise RuntimeError(
                f"[l2_etl] {date}: all CSVs header-only but {len(existing)} existing "
                f"main parquet file(s) found — refusing to delete (possible bad re-download)."
            )
        if max_files <= 0:
            _append_manifest(
                manifest_path,
                date=date,
                files=csv_files,
                rows_main=0,
                rows_order=0,
                main_parts=[],
                order_parts=[],
                stat_by_path=stat_by_path,
            )
        return DayEtlResult(
            date=date,
            source_dir=str(source),
            csv_files=len(csv_files),
            empty_files=len(empty_files),
            rows_main=0,
            rows_order=0,
            main_parquet=main_path_str,
            order_parquet=order_path_str,
            main_bytes=0,
            order_bytes=0,
            source_csv_bytes=source_csv_bytes,
            compress_ratio=0.0,
            elapsed_s=time.perf_counter() - t0,
            instrument_counts=instrument_counts,
            notes="empty day (all header-only)",
        )

    gap_failures: list[str] = []
    t_gap = time.perf_counter()
    if validate_gap_free and non_empty:
        gap_failures = _check_gap_free(
            non_empty, sample=gap_free_sample, size_by_path=size_by_path
        )
    gap_free_s = time.perf_counter() - t_gap

    t_setup = time.perf_counter()
    n_threads = threads if threads is not None else max(1, (os.cpu_count() or 4) - 1)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Contiguous ranges of sorted bare_code => parts stay globally ordered.
    chunks: list[list[Path]] = []
    usable = non_empty  # header-only files contribute 0 rows; skip read
    for i in range(0, len(usable), max(1, chunk_files)):
        chunks.append(usable[i : i + max(1, chunk_files)])

    main_chunks: list[Path] = []
    order_chunks: list[Path] = []
    rows_main = 0
    rows_order = 0
    chunk_profiles: list[dict[str, float]] = []

    con = duckdb.connect(database=":memory:")
    try:
        _configure(con, memory_limit=memory_limit, threads=n_threads, temp_dir=tmp_dir)
        setup_s = time.perf_counter() - t_setup
        for idx, group in enumerate(chunks):
            if not group:
                continue
            main_c = work_dir / f"main_{idx:04d}.parquet"
            order_c = work_dir / f"order_{idx:04d}.parquet"
            n_m, n_o, cprof = _write_chunk(
                con, date=date, files=group, main_out=main_c, order_out=order_c, size_by_path=size_by_path
            )
            rows_main += n_m
            rows_order += n_o
            main_chunks.append(main_c)
            order_chunks.append(order_c)
            chunk_profiles.append(cprof)
            note_peak(peak_rss)
            note_peak(peak_rss_chunk)
            note_temp_peak(peak_temp, tmp_dir)
            print(
                f"[l2_etl] chunk {idx + 1}/{len(chunks)} files={len(group)} "
                f"rows={n_m} main={cprof['main_copy_s']:.1f}s order={cprof['order_copy_s']:.1f}s "
                f"elapsed={time.perf_counter() - t0:.1f}s",
                flush=True,
            )
    finally:
        con.close()
    note_peak(peak_rss_chunk)
    note_temp_peak(peak_temp, tmp_dir)

    # v5.9 publish: compact range-sorted work chunks → date=D/{main,order}.parquet
    # (pyarrow concat; replace-first). Then drop legacy flat parts for this date.
    t_publish = time.perf_counter()
    main_out.parent.mkdir(parents=True, exist_ok=True)
    note_peak(peak_rss_compact)  # baseline before compact
    merge_con = duckdb.connect(database=":memory:")
    try:
        _configure(merge_con, memory_limit=memory_limit, threads=n_threads, temp_dir=tmp_dir)
        n_pub_m, merge_main_s = _merge_chunks(
            merge_con, chunk_paths=main_chunks, final_path=main_out
        )
        note_peak(peak_rss)
        note_peak(peak_rss_compact)
        note_temp_peak(peak_temp, tmp_dir)
        n_pub_o, merge_order_s = _merge_chunks(
            merge_con, chunk_paths=order_chunks, final_path=order_out
        )
        note_peak(peak_rss)
        note_peak(peak_rss_compact)
        note_temp_peak(peak_temp, tmp_dir)
    finally:
        merge_con.close()
    if n_pub_m != rows_main or n_pub_o != rows_order:
        raise RuntimeError(
            f"[l2_etl] compact row mismatch: main {n_pub_m}/{rows_main} "
            f"order {n_pub_o}/{rows_order}"
        )
    main_parts = [main_rel]
    order_parts = [order_rel]
    legacy_mains, legacy_orders = list_legacy_flat_parts(data_root, date)
    for old in [*legacy_mains, *legacy_orders]:
        old.unlink(missing_ok=True)
    # Only remove workdir after finals land (never on failure — keeps chunks).
    shutil.rmtree(work_dir, ignore_errors=True)
    publish_s = time.perf_counter() - t_publish
    print(
        f"[l2_etl] published hive compact main={merge_main_s:.1f}s order={merge_order_s:.1f}s "
        f"({publish_s:.2f}s total)",
        flush=True,
    )

    t_manifest = time.perf_counter()
    if max_files <= 0:
        _append_manifest(
            manifest_path,
            date=date,
            files=csv_files,
            rows_main=rows_main,
            rows_order=rows_order,
            main_parts=main_parts,
            order_parts=order_parts,
            stat_by_path=stat_by_path,
        )
    manifest_s = time.perf_counter() - t_manifest

    main_bytes = main_out.stat().st_size
    order_bytes = order_out.stat().st_size
    elapsed_total = time.perf_counter() - t0
    chunk_total_sum_s = sum(float(cp.get("chunk_total_s", 0.0)) for cp in chunk_profiles)
    other_s = elapsed_total - (
        scan_s + gap_free_s + setup_s + chunk_total_sum_s + publish_s + manifest_s
    )
    note_peak(peak_rss)
    note_temp_peak(peak_temp, tmp_dir)
    peak_rss_bytes = peak_rss[0]
    peak_rss_chunk_b = peak_rss_chunk[0]
    peak_rss_compact_b = peak_rss_compact[0]
    peak_temp_b = peak_temp[0]
    profile: dict[str, Any] = {
        "scan_s": round(scan_s, 3),
        "gap_free_s": round(gap_free_s, 3),
        "setup_s": round(setup_s, 3),
        "chunk_total_sum_s": round(chunk_total_sum_s, 3),
        "publish_s": round(publish_s, 3),
        "merge_main_s": round(merge_main_s, 3),
        "merge_order_s": round(merge_order_s, 3),
        "manifest_s": round(manifest_s, 3),
        # other_s = elapsed - 上列各项：兜底对账（含 idempotent glob unlink 等未单列区）。
        "other_s": round(other_s, 3),
        "peak_rss_bytes": peak_rss_bytes,
        "peak_rss_gb": bytes_to_gb(peak_rss_bytes),
        # Phase-split RSS: chunk COPY vs hive compact (pyarrow concat).
        "peak_rss_chunk_bytes": peak_rss_chunk_b,
        "peak_rss_chunk_gb": bytes_to_gb(peak_rss_chunk_b),
        "peak_rss_compact_bytes": peak_rss_compact_b,
        "peak_rss_compact_gb": bytes_to_gb(peak_rss_compact_b),
        # DuckDB SET temp_directory peak on-disk footprint (spill files).
        "temp_directory": tmp_dir.as_posix(),
        "peak_temp_bytes": peak_temp_b,
        "peak_temp_gb": bytes_to_gb(peak_temp_b),
        "rss_end_bytes": process_rss_bytes(),
        "chunks": [
            {k: round(v, 3) if isinstance(v, float) else v for k, v in cp.items()}
            for cp in chunk_profiles
        ],
    }
    return DayEtlResult(
        date=date,
        source_dir=str(source),
        csv_files=len(csv_files),
        empty_files=len(empty_files),
        rows_main=rows_main,
        rows_order=rows_order,
        main_parquet=main_path_str,
        order_parquet=order_path_str,
        main_bytes=main_bytes,
        order_bytes=order_bytes,
        source_csv_bytes=source_csv_bytes,
        compress_ratio=_ratio(source_csv_bytes, main_bytes + order_bytes),
        elapsed_s=elapsed_total,
        chunks=len(chunks),
        gap_free_ok=len(gap_failures) == 0,
        gap_free_failures=gap_failures[:20],
        instrument_counts=instrument_counts,
        notes=f"memory_limit={memory_limit}; threads={n_threads}; chunk_files={chunk_files}; layout=hive",
        profile=profile,
    )


def result_to_json(result: DayEtlResult) -> str:
    return json.dumps(asdict(result), ensure_ascii=False, indent=2)
