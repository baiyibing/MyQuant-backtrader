"""Hermetic host boundary checks; fakes also run without the private package."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from l2_analytics import _infra, aggregates, etl_day, etl_polars, paths, perf
from scripts.misc import extract_stock_rar_data as archives
from scripts.misc import l2_phase3_pipeline as phase3
from scripts.run import run_l2_merge_work_chunks as recovery
from scripts.run import run_l2_migrate_hive_compact as maintenance


def fake_l2(monkeypatch, **modules):
    calls = []

    def load(name):
        calls.append(name)
        return modules[name.removeprefix("myquant_infra.l2.")]

    monkeypatch.setattr(_infra, "import_module", load)
    return calls


@pytest.mark.parametrize("engine,environment,expected", [
    (None, None, "duckdb"), (None, "polars", "polars"),
    ("duckdb", "polars", "duckdb"), ("polars", "duckdb", "polars"),
])
def test_etl_preserves_host_defaults_and_options(tmp_path, monkeypatch, engine, environment, expected):
    if environment is None:
        monkeypatch.delenv("OSKH_L2_ETL_ENGINE", raising=False)
    else:
        monkeypatch.setenv("OSKH_L2_ETL_ENGINE", environment)
    run = Mock(return_value=object())
    fake_l2(monkeypatch, **{"ingest.etl": SimpleNamespace(etl_one_day=run)})
    source, root = tmp_path / "2025-01-02", tmp_path / "output"
    result = etl_day.etl_one_day(source, out_root=root, engine=engine, threads=3,
                                 chunk_files=12, force=True, validate_gap_free=False,
                                 gap_free_sample=7, max_files=2, memory_limit="1GB")
    run.assert_called_once_with(
        source, out_root=root, temp_directory=root / "_duckdb_tmp", engine=expected,
        threads=3, chunk_files=12, force=True, validate_gap_free=False,
        gap_free_sample=7, max_files=2, memory_limit="1GB",
    )
    assert result is run.return_value
    assert not root.exists()


def test_etl_uses_host_resolver_and_explicit_temp(tmp_path, monkeypatch):
    root, temp = tmp_path / "configured", tmp_path / "spill"
    monkeypatch.setattr("common.infra.data_root.resolve_l2_parquet_root", lambda: root)
    run = Mock()
    fake_l2(monkeypatch, **{"ingest.etl": SimpleNamespace(etl_one_day=run)})
    etl_day.etl_one_day("2025-01-02", temp_directory=temp)
    assert run.call_args.kwargs["out_root"] == root
    assert run.call_args.kwargs["temp_directory"] == temp


def test_invalid_engine_fails_before_infra_or_output(tmp_path, monkeypatch):
    load = Mock(side_effect=AssertionError("must fail before import"))
    monkeypatch.setattr(_infra, "import_module", load)
    monkeypatch.setenv("OSKH_L2_ETL_ENGINE", "typo")
    with pytest.raises(ValueError, match="OSKH_L2_ETL_ENGINE"):
        etl_day.etl_one_day("missing", out_root=tmp_path / "output")
    load.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_aggregate_root_and_connection_are_forwarded(tmp_path, monkeypatch):
    all_days, one_day = Mock(), Mock()
    fake_l2(monkeypatch, aggregates=SimpleNamespace(
        build_all_aggregates=all_days, build_aggregates_for_date=one_day))
    monkeypatch.setattr("common.infra.data_root.resolve_l2_parquet_root", lambda: tmp_path)
    aggregates.build_all_aggregates(dates=["2025-01-02"], force=True, memory_limit="2GB")
    all_days.assert_called_once_with(tmp_path, dates=["2025-01-02"], force=True, memory_limit="2GB")
    con = object()
    aggregates.build_aggregates_for_date(con, date="2025-01-02", out_root=tmp_path, force=True)
    one_day.assert_called_once_with(con, date="2025-01-02", out_root=tmp_path, force=True)


def test_path_perf_and_polars_use_infra(monkeypatch, tmp_path):
    path, sample, convert, merge = Mock(), Mock(), Mock(), Mock()
    fake_l2(monkeypatch, **{
        "ingest.paths": SimpleNamespace(main_parquet_path=path),
        "ingest.perf": SimpleNamespace(note_peak=sample, bytes_to_gb=convert),
        "ingest.polars": SimpleNamespace(merge_chunks=merge),
    })
    paths.main_parquet_path(tmp_path, "2025-01-02")
    path.assert_called_once_with(tmp_path, "2025-01-02")
    tracker = [None]
    perf.note_peak(tracker, 25)
    sample.assert_called_once_with(tracker, 25)
    perf.bytes_to_gb(None)
    convert.assert_called_once_with(None)
    etl_polars.merge_chunks(None, chunk_paths=[], final_path=tmp_path / "main.parquet")
    merge.assert_called_once_with(None, chunk_paths=[], final_path=tmp_path / "main.parquet")


@pytest.mark.parametrize("dry_run", [False, True])
def test_maintenance_cli_keeps_explicit_apply_contract(tmp_path, monkeypatch, dry_run):
    run = Mock(return_value={"results": []})
    fake_l2(monkeypatch, **{"maintenance.migrate_hive_compact": SimpleNamespace(migrate_hive_compact=run)})
    argv = ["--out-root", str(tmp_path), "--date", "2025-01-02", "--all-legacy",
            "--keep-legacy", "--rebake-302", "--threads", "3", "--memory-limit", "1GB"]
    assert maintenance.main(argv + (["--dry-run"] if dry_run else [])) == 0
    run.assert_called_once_with(
        tmp_path, dates=["2025-01-02"], all_legacy=True, keep_legacy=True,
        rebake_302=True, apply=not dry_run, threads=3, memory_limit="1GB", temp_directory=None,
    )


def test_recovery_forwards_paths_and_exit_code(tmp_path, monkeypatch):
    run = Mock(return_value={"exit_code": 2})
    fake_l2(monkeypatch, **{"ingest.recovery": SimpleNamespace(recover_day=run)})
    assert recovery.main(["--out-root", str(tmp_path), "--date", "2025-01-02",
                          "--source", str(tmp_path / "source"), "--keep-work", "--threads", "2"]) == 2
    assert run.call_args.kwargs == dict(
        root=tmp_path, date="2025-01-02", source=tmp_path / "source",
        temp_directory=tmp_path / "_duckdb_tmp", memory_limit="18GB", threads=2,
        keep_work=True, dry_run=False,
    )


def test_archive_cli_environment_and_skip_file(tmp_path, monkeypatch):
    run, skip = Mock(return_value={"success": False}), Mock(return_value={"2025-01-03"})
    fake_l2(monkeypatch, **{"ingest.archives": SimpleNamespace(unpack=run),
                            "ingest.cli": SimpleNamespace(_skip_dates=skip)})
    monkeypatch.setenv("OSKH_STOCK_RAR_SRC", str(tmp_path / "archives"))
    monkeypatch.setenv("OSKH_STOCK_CSV_DST", str(tmp_path / "csv"))
    skip_file = tmp_path / "skip.txt"
    assert archives.main(["--skip-dates-file", str(skip_file), "--force", "--dry-run"]) == 1
    skip.assert_called_once_with(skip_file)
    assert run.call_args.kwargs["skip_dates"] == {"2025-01-03"}
    assert run.call_args.kwargs["src"] == tmp_path / "archives"
    assert run.call_args.kwargs["dst"] == tmp_path / "csv"
    assert run.call_args.kwargs["force"] is True
    assert run.call_args.kwargs["dry_run"] is True


def test_phase3_composes_explicit_roots_without_io(tmp_path, monkeypatch):
    factory = Mock()
    fake_l2(monkeypatch, **{"ingest.pipeline": SimpleNamespace(Pipeline=factory)})
    for key, value in {
        "OSKH_STOCK_RAR_SRC": "source", "OSKH_STOCK_CSV_DST": "csv",
        "OSKH_L2_PARQUET_ROOT": "lake", "OSKH_L2_PARQUET_STAGING_ROOT": "stage",
        "OSKH_L2_TEMP_DIRECTORY": "temp", "OSKH_L2_ARCHIVE_SCRATCH": "archives",
        "OSKH_L2_AGENT_TOOLS": "tools",
    }.items():
        monkeypatch.setenv(key, str(tmp_path / value))
    monkeypatch.setenv("OSKH_L2_ETL_WORKERS", "4")
    monkeypatch.setenv("OSKH_L2_ETL_POLARS_WORKERS", "2")
    monkeypatch.setenv("OSKH_L2_ETL_ENGINE", "duckdb")
    monkeypatch.setenv("OSKH_L2_ETL_THREADS", "3")
    result = phase3.build_pipeline()
    options = factory.call_args.kwargs
    assert options["source_root"] == tmp_path / "source"
    assert options["csv_root"] == tmp_path / "csv"
    assert options["lake_root"] == tmp_path / "lake"
    assert options["staging_root"] == tmp_path / "stage"
    assert options["archive_scratch"] == tmp_path / "archives"
    assert options["temp_directory"] == tmp_path / "temp"
    assert (options["workers"], options["polars_workers"], options["threads"]) == (4, 2, 3)
    assert result.log_jsonl == tmp_path / "tools" / "l2_batch_progress.jsonl"
    assert result.progress == tmp_path / "tools" / "l2_batch_progress.md"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("key,value", [("OSKH_L2_ETL_WORKERS", "0"),
    ("OSKH_L2_ETL_POLARS_WORKERS", "9"), ("OSKH_L2_ETL_ENGINE", "typo")])
def test_phase3_bad_config_fails_before_import(key, value, monkeypatch):
    monkeypatch.setenv("OSKH_L2_ETL_WORKERS", "2")
    monkeypatch.setenv("OSKH_L2_ETL_POLARS_WORKERS", "0")
    monkeypatch.setenv("OSKH_L2_ETL_ENGINE", "duckdb")
    monkeypatch.setenv(key, value)
    load = Mock(side_effect=AssertionError("must fail before import"))
    monkeypatch.setattr(_infra, "import_module", load)
    with pytest.raises(ValueError):
        phase3.build_pipeline()
    load.assert_not_called()


def test_phase3_missing_source_is_explicit(monkeypatch):
    monkeypatch.delenv("OSKH_STOCK_RAR_SRC", raising=False)
    with pytest.raises(ValueError, match="OSKH_STOCK_RAR_SRC"):
        phase3.build_pipeline()


@pytest.mark.parametrize("dry_run", [False, True])
def test_phase3_main_propagates_failure_and_preserves_host_evidence(tmp_path, monkeypatch, dry_run):
    report = {"exit_code": 1, "pending": ["2025-01-02"]}
    run = Mock(return_value=report)
    monkeypatch.setattr(phase3, "resolve_oskh_python", lambda: Path(sys.executable))
    monkeypatch.setattr(phase3, "build_pipeline", lambda: SimpleNamespace(staging_root=tmp_path, run=run))
    monkeypatch.setenv("OSKH_L2_AGENT_TOOLS", str(tmp_path))
    assert phase3.main(["--dates", "2025-01-02"] + (["--dry-run"] if dry_run else [])) == 1
    run.assert_called_once_with(["2025-01-02"], skip_dates=set(), dry_run=dry_run)
    if dry_run:
        assert list(tmp_path.iterdir()) == []
    else:
        assert json.loads((tmp_path / "l2_batch_summary.json").read_text()) == report
        assert (tmp_path / "l2_phase3_pipeline.pid").read_text() == str(__import__("os").getpid())


def test_missing_private_package_allows_import_and_cli_help():
    # A fresh interpreter prevents installed/cached infra modules hiding absence.
    code = '''
import importlib.abc, runpy, sys
from pathlib import Path
class BlockInfra(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "myquant_infra" or fullname.startswith("myquant_infra."):
            raise ModuleNotFoundError(fullname, name=fullname)
sys.meta_path.insert(0, BlockInfra())
from l2_analytics import etl_day, etl_polars, aggregates, paths, perf
for name in ("scripts/misc/extract_stock_rar_data.py", "scripts/misc/l2_phase3_pipeline.py",
             "scripts/run/run_l2_etl_day.py", "scripts/run/run_l2_etl_multi_day.py",
             "scripts/run/run_l2_build_aggregates.py", "scripts/run/run_l2_merge_work_chunks.py",
             "scripts/run/run_l2_migrate_hive_compact.py"):
    sys.argv = [name, "--help"]
    try:
        runpy.run_path(name, run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 0
try:
    etl_day.etl_one_day("missing", out_root="must-not-be-created")
except ImportError as exc:
    assert "requirements-infra.txt" in str(exc)
else:
    raise AssertionError("missing package must fail explicitly")
assert not Path("must-not-be-created").exists()
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[1], timeout=30)
    assert result.returncode == 0, result.stderr


def test_transitive_missing_dependency_is_not_masked(monkeypatch):
    def missing(name):
        raise ModuleNotFoundError("missing duckdb", name="duckdb")

    monkeypatch.setattr(_infra, "import_module", missing)
    with pytest.raises(ModuleNotFoundError, match="missing duckdb"):
        _infra.require_l2("ingest.etl")


def test_private_pin_is_optional_and_contains_the_approved_commit():
    root = Path(__file__).resolve().parents[1]
    assert "myquant-infra" not in (root / "requirements.txt").read_text(encoding="utf-8")
    optional = (root / "requirements-infra.txt").read_text(encoding="utf-8")
    assert "MyQuant-infra.git@7d48c4e310f9636cad9c3e544db1766025db4e3c" in optional


@pytest.fixture
def tiny_lake(tmp_path):
    pytest.importorskip("myquant_infra.l2.ingest.etl")
    day = tmp_path / "csv" / "2025-01-02"
    day.mkdir(parents=True)
    (day / "302001.csv").write_text(
        "TranID,Time,Price,Volume,SaleOrderVolume,BuyOrderVolume,Type,"
        "SaleOrderID,SaleOrderPrice,BuyOrderID,BuyOrderPrice\n"
        "1,09:30:00,10,100,100,100,B,1,10,2,10\n", encoding="utf-8")
    root = tmp_path / "lake"
    etl_day.etl_one_day(day, out_root=root, threads=1, engine="duckdb")
    return day, root


def test_real_compaction_preserves_manifest_and_canonical_order(tiny_lake):
    import pyarrow as pa
    import pyarrow.parquet as pq

    day, root = tiny_lake
    main = root / f"date={day.name}" / "main.parquet"
    table = pq.ParquetFile(main).read()
    table = table.set_column(table.schema.get_field_index("instrument_type"),
                             "instrument_type", pa.array(["other"]))
    pq.write_table(table, main)
    manifest = root / "_manifest.jsonl"
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record["host_evidence"] = "retained"
    for side in ("main", "order"):
        target = f"{day.name}.part-0000.{side}.parquet"
        (root / f"date={day.name}" / f"{side}.parquet").rename(root / target)
        record[f"{side}_parts"] = [target]
    manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    plan = maintenance.migrate_date(root, day.name, rebake_302=True, keep_legacy=True, apply=False)
    assert plan["dry_run"] is True
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = maintenance.migrate_date(root, day.name, rebake_302=True, keep_legacy=True, threads=1)
    assert result["status"] == "migrated" and result["rebake_302_rows"] == 1
    rewritten = json.loads(manifest.read_text(encoding="utf-8"))
    assert rewritten["host_evidence"] == "retained"
    assert rewritten["main_parts"] == [f"date={day.name}/main.parquet"]
    assert list(root.glob("*.part-*.main.parquet"))
    assert pq.ParquetFile(main).read()["instrument_type"].to_pylist() == ["stock"]
    assert maintenance.migrate_date(root, day.name, threads=1)["status"] == "migrated"


@pytest.mark.parametrize("corrupt", [False, True])
def test_real_work_chunk_recovery_verifies_source_before_publish(tiny_lake, corrupt):
    import pyarrow as pa
    import pyarrow.parquet as pq

    day, root = tiny_lake
    work = root / f"_work_{day.name}"
    work.mkdir()
    for side in ("main", "order"):
        source = root / f"date={day.name}" / f"{side}.parquet"
        source.rename(work / f"{side}_0000.parquet")
    (root / "_manifest.jsonl").unlink()
    if corrupt:
        main = work / "main_0000.parquet"
        table = pq.ParquetFile(main).read()
        pq.write_table(pa.concat_tables([table, table]), main)
        with pytest.raises(ValueError, match="row counts differ"):
            recovery.main(["--out-root", str(root), "--date", day.name,
                           "--source", str(day), "--threads", "1"])
        assert work.is_dir() and not (root / "_manifest.jsonl").exists()
    else:
        assert recovery.main(["--out-root", str(root), "--date", day.name,
                              "--source", str(day), "--threads", "1"]) == 0
        assert not work.exists()
        assert (root / f"date={day.name}" / "order.parquet").is_file()
        record = json.loads((root / "_manifest.jsonl").read_text(encoding="utf-8"))
        assert record["rows_main"] == record["rows_order"] == 1
