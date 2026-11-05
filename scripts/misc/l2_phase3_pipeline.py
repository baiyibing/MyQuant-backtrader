"""Host environment and entry point for infra's bounded offline Phase3 pipeline."""
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

from scripts._script_bootstrap import resolve_oskh_python


def _path(key: str, explicit=None, default=None) -> Path:
    value = explicit if explicit is not None else os.environ.get(key, "").strip() or default
    if value is None:
        raise ValueError(f"set {key}; no machine data path is assumed")
    return Path(value)


def _etl_settings() -> dict:
    engine = os.environ.get("OSKH_L2_ETL_ENGINE", "duckdb")
    if engine not in ("duckdb", "polars"):
        raise ValueError("OSKH_L2_ETL_ENGINE must be duckdb|polars")
    values = {}
    for key, default in (("OSKH_L2_ETL_WORKERS", 2), ("OSKH_L2_ETL_POLARS_WORKERS", 0),
                         ("OSKH_L2_ETL_THREADS", 1)):
        try:
            values[key] = int(os.environ.get(key, str(default)))
        except ValueError:
            raise ValueError(f"{key} must be an integer") from None
    workers = values["OSKH_L2_ETL_WORKERS"]
    if workers < 1 or values["OSKH_L2_ETL_THREADS"] < 1:
        raise ValueError("OSKH_L2_ETL_WORKERS / OSKH_L2_ETL_THREADS must be a positive integer")
    polars = values["OSKH_L2_ETL_POLARS_WORKERS"]
    if not 0 <= polars <= workers:
        raise ValueError("OSKH_L2_ETL_POLARS_WORKERS must be in [0, WORKERS]")
    return dict(engine=engine, workers=workers, polars_workers=polars,
                threads=values["OSKH_L2_ETL_THREADS"])


def build_pipeline(
    *, source_root=None, csv_root=None, staging_root=None, archive_scratch=None,
    lake_root=None, seven_zip=None, temp_directory=None, agent_tools=None,
):
    settings = _etl_settings()  # Invalid host settings fail before imports or IO.
    source = _path("OSKH_STOCK_RAR_SRC", source_root)
    csv = _path("OSKH_STOCK_CSV_DST", csv_root)
    staging = _path("OSKH_L2_PARQUET_STAGING_ROOT", staging_root,
                    csv.parent / "l2_parquet_staging")
    if lake_root is None:
        from common.infra.data_root import resolve_l2_parquet_root

        lake_root = resolve_l2_parquet_root()
    pipeline = require_l2("ingest.pipeline").Pipeline(
        source_root=source, csv_root=csv, staging_root=staging,
        archive_scratch=_path("OSKH_L2_ARCHIVE_SCRATCH", archive_scratch,
                              csv.parent / "l2_archive_scratch"),
        lake_root=lake_root,
        seven_zip=_path("OSKH_SEVEN_ZIP", seven_zip, r"C:\Program Files\7-Zip\7z.exe"),
        temp_directory=_path("OSKH_L2_TEMP_DIRECTORY", temp_directory, staging.parent / "l2_temp"),
        **settings,
    )
    tools = _path("OSKH_L2_AGENT_TOOLS", agent_tools, staging)
    pipeline.log_jsonl = tools / "l2_batch_progress.jsonl"
    pipeline.progress = tools / "l2_batch_progress.md"
    return pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dates", nargs="+", help="otherwise read l2_phase3_dates.txt")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    # Infra ETL children use sys.executable; honor the host interpreter resolver.
    executable = resolve_oskh_python()
    if executable.resolve() != Path(sys.executable).resolve():
        import subprocess

        return subprocess.run([str(executable), str(Path(__file__).resolve()),
                               *(sys.argv[1:] if argv is None else argv)], check=False).returncode
    pipeline = build_pipeline()
    tools = _path("OSKH_L2_AGENT_TOOLS", default=pipeline.staging_root)
    dates = args.dates or [line.strip() for line in
                          (tools / "l2_phase3_dates.txt").read_text(encoding="utf-8").splitlines()
                          if line.strip()]
    skip_file = tools / "l2_skip_dates.txt"
    skip_dates = require_l2("ingest.cli")._skip_dates(skip_file) if skip_file.is_file() else set()
    if not args.dry_run:
        tools.mkdir(parents=True, exist_ok=True)
        (tools / "l2_phase3_pipeline.pid").write_text(str(os.getpid()), encoding="utf-8")
    result = pipeline.run(dates, skip_dates=skip_dates, dry_run=args.dry_run)
    if not args.dry_run:
        (tools / "l2_batch_summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
