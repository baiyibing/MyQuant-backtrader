"""Optional Polars chunk conversion and streaming compaction for offline L2 ETL."""
from __future__ import annotations

import os
import shutil
import sys
import time
from datetime import date as Date
from pathlib import Path

from l2_analytics.etl_day import _ROW_GROUP_SIZE
from oskh_core.a_share_symbol_normalize import canonical_from_bare_code, classify_instrument_type

_COLUMNS = ["TranID", "Time", "Price", "Volume", "SaleOrderVolume", "BuyOrderVolume",
            "Type", "SaleOrderID", "SaleOrderPrice", "BuyOrderID", "BuyOrderPrice"]
_MAIN = ["stock_code", "date", "TranID", "Time", "trade_time", "ts", "session",
         "instrument_type", "Price", "Volume", "SaleOrderVolume", "BuyOrderVolume", "Type"]
_ORDER = ["stock_code", "date", "TranID", "SaleOrderID", "SaleOrderPrice", "BuyOrderID", "BuyOrderPrice"]


def configure_threads(threads: int | None) -> None:
    """Polars' process-wide pool must be configured before its first import."""
    if threads is not None:
        if threads < 1:
            raise ValueError("Polars threads must be positive")
        if "polars" in sys.modules:
            import polars as pl
            if pl.thread_pool_size() != threads:
                raise ValueError("Polars pool already initialized; set threads in a fresh process")
        else:
            os.environ["POLARS_MAX_THREADS"] = str(threads)
    try:
        import polars  # noqa: F401
    except ImportError as exc:
        raise ImportError("Polars ETL requires: pip install -r requirements-l2-polars.txt") from exc


def _arrow_schema(frame):
    import pyarrow as pa
    schema = frame.to_arrow().schema
    return pa.schema([pa.field(f.name,
                      pa.time64("us") if pa.types.is_time(f.type) else
                      f.type)
                      for f in schema])


def write_chunk(con, *, date, files, main_out, order_out, size_by_path=None):
    import polars as pl

    t0 = time.perf_counter()
    prof = {"csv_bytes": float(sum((size_by_path or {}).get(str(p), 0) or p.stat().st_size for p in files))}
    t = time.perf_counter()
    frames = []
    for path in files:
        # Skip exchange header, fix the 11 positional fields and drop watermark
        # overflow. GBK/UTF-8 watermark bytes never enter the ASCII trading fields.
        frame = pl.read_csv(
            path, has_header=False, skip_rows=1,
            schema={name: pl.String for name in _COLUMNS},
            encoding="utf8-lossy", truncate_ragged_lines=True,
        ).with_columns(
            pl.lit(canonical_from_bare_code(path.stem.strip())).alias("stock_code"),
            pl.lit(classify_instrument_type(path.stem.strip())).alias("instrument_type"),
        )
        frames.append(frame)
    prof["sym_map_s"] = 0.0  # symbol literals included in enrich_s
    frame = pl.concat(frames).filter(
        pl.col("Type").is_in(["B", "S"]) & (pl.col("Price").cast(pl.Float64, strict=False) > 0)
    )
    # Round before decimal cast, matching DuckDB DECIMAL scale conversion.
    def decimal(name, precision, strict=True):
        return pl.col(name).cast(pl.Decimal(38, 12), strict=strict).round(3, mode="half_away_from_zero").cast(
            pl.Decimal(precision, 3), strict=strict)
    frame = frame.with_columns(
        *[pl.col(c).cast(pl.Int64) for c in ["TranID", "Volume", "SaleOrderVolume", "BuyOrderVolume", "SaleOrderID", "BuyOrderID"]],
        decimal("Price", 10, False), decimal("SaleOrderPrice", 18), decimal("BuyOrderPrice", 18),
        pl.lit(Date.fromisoformat(date)).alias("date"),
        pl.col("Time").str.to_time("%H:%M:%S").alias("trade_time"),
        (pl.lit(date + " ") + pl.col("Time")).str.to_datetime("%Y-%m-%d %H:%M:%S", time_unit="us")
        .dt.replace_time_zone("Asia/Shanghai").dt.convert_time_zone("UTC").dt.replace_time_zone(None).alias("ts"),
    )
    tt = pl.col("trade_time")
    from datetime import time as Time
    frame = frame.with_columns(
        pl.when(tt < Time(9, 30)).then(pl.lit("pre_open"))
        .when(tt <= Time(11, 30)).then(pl.lit("continuous_am"))
        .when(tt < Time(13)).then(pl.lit("other"))
        .when(tt < Time(14, 57)).then(pl.lit("continuous_pm"))
        .otherwise(pl.lit("close_auction")).alias("session")
    ).sort("stock_code", "TranID")
    prof["enrich_s"] = time.perf_counter() - t
    for name, columns, path in [("main", _MAIN, main_out), ("order", _ORDER, order_out)]:
        t = time.perf_counter()
        selected = frame.select(columns)
        selected.write_parquet(path, compression="zstd", row_group_size=_ROW_GROUP_SIZE,
                               arrow_schema=_arrow_schema(selected))
        prof[f"{name}_copy_s"] = time.perf_counter() - t
        prof[f"{name}_bytes"] = float(path.stat().st_size)
    prof["chunk_total_s"] = time.perf_counter() - t0
    return frame.height, frame.height, prof


def merge_chunks(con, *, chunk_paths: list[Path], final_path: Path):
    import polars as pl

    if not chunk_paths:
        raise ValueError("no chunks to merge")
    t = time.perf_counter()
    tmp = final_path.with_name(final_path.name + ".merge.tmp")
    # Explicit concat preserves caller chunk order; streaming sink avoids a full-day collect.
    import pyarrow.parquet as pq
    if len(chunk_paths) == 1:
        shutil.copy2(chunk_paths[0], tmp)
        n = pq.ParquetFile(tmp).metadata.num_rows
        os.replace(tmp, final_path)
        return n, time.perf_counter() - t
    schema = pq.ParquetFile(chunk_paths[0]).schema_arrow
    pl.concat([pl.scan_parquet(p, hive_partitioning=False) for p in chunk_paths]).sink_parquet(
        tmp, compression="zstd", row_group_size=_ROW_GROUP_SIZE, maintain_order=True, arrow_schema=schema,
    )
    n = pl.scan_parquet(tmp, hive_partitioning=False).select(pl.len()).collect().item()
    os.replace(tmp, final_path)
    return n, time.perf_counter() - t
