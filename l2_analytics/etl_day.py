"""BT root/environment composition for the pinned infra offline L2 ingester."""
from __future__ import annotations

import os
from pathlib import Path

from l2_analytics._infra import require_l2


def etl_one_day(
    source_dir: str | Path, *, out_root: str | Path | None = None,
    memory_limit: str = "18GB", threads: int | None = None,
    temp_directory: str | Path | None = None, chunk_files: int = 400,
    force: bool = False, validate_gap_free: bool = True,
    gap_free_sample: int = 0, max_files: int = 0, engine: str | None = None,
):
    selected = engine if engine is not None else os.environ.get("OSKH_L2_ETL_ENGINE", "duckdb")
    if selected not in ("duckdb", "polars"):
        raise ValueError(f"invalid OSKH_L2_ETL_ENGINE: {selected!r}; expected duckdb|polars")
    implementation = require_l2("ingest.etl")
    if out_root:
        root = Path(out_root)
    else:
        from common.infra.data_root import resolve_l2_parquet_root

        root = resolve_l2_parquet_root()
    return implementation.etl_one_day(
        source_dir, out_root=root,
        temp_directory=Path(temp_directory) if temp_directory else root / "_duckdb_tmp",
        memory_limit=memory_limit, threads=threads, chunk_files=chunk_files,
        force=force, validate_gap_free=validate_gap_free,
        gap_free_sample=gap_free_sample, max_files=max_files, engine=selected,
    )


def result_to_json(result) -> str:
    return require_l2("ingest.etl").result_to_json(result)


def _is_header_only_csv(path: Path) -> bool:
    return require_l2("ingest.etl").is_header_only_csv(path)


def _file_fp(path: Path, st=None):
    return require_l2("ingest.publish").file_fingerprint(path, st)


def _select_gap_free_targets(files, *, sample, size_by_path=None):
    return require_l2("ingest.etl")._select_gap_free_targets(
        files, sample=sample, size_by_path=size_by_path,
    )


def __getattr__(name: str):
    if name == "DayEtlResult":
        return require_l2("ingest.etl").DayEtlResult
    raise AttributeError(name)
