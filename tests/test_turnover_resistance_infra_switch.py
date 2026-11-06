"""B6 host forwarding and offline TR pipeline contracts at the optional pin."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from oskh_data import turnover_resistance_store as host
from oskh_factors.chip.bands import compute_tr_bb_columns
from scripts.tr import backfill_turnover_resistance_bands as backfill
from scripts.tr import compute_turnover_resistance_bands as daily

_INTERPRETER_KEYS = (
    "OSKH_MERGE_PYTHON", "VANNA312_PYTHON", "VANNA311_PYTHON",
    "OSKH_MERGE_ENV_HOME", "VANNA312_HOME", "VANNA311_HOME",
)


def _import_yearly():
    """Import the yearly script, which resolves the OSKH interpreter at import.

    Public CI has no canonical interpreter, so ``resolve_oskh_python`` raises
    SystemExit during collection. Pin it to this test Python for the import only
    (the script's subprocesses are mocked here); restore the env afterwards.
    """
    pinned = not any(os.environ.get(key) for key in _INTERPRETER_KEYS)
    if pinned:
        os.environ["OSKH_MERGE_PYTHON"] = sys.executable
    try:
        from scripts.tr import backfill_turnover_resistance_yearly as module
    except SystemExit:
        pytest.skip("OSKH interpreter unresolvable for scripts.tr yearly", allow_module_level=True)
    finally:
        if pinned:
            os.environ.pop("OSKH_MERGE_PYTHON", None)
    return module


yearly = _import_yearly()


@pytest.fixture(autouse=True)
def isolated_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(tmp_path / "lake"))
    monkeypatch.setenv("OSKH_AUTHORITY_HINT_ROOT", str(tmp_path / "lake"))
    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(tmp_path / "lake/stock/period=1d"))
    monkeypatch.setenv("TURNOVER_RESIST_DATA_DIR", str(tmp_path / "lake"))
    monkeypatch.setenv("TURNOVER_RESIST_BANDS_PATH", str(tmp_path / "tr.parquet"))
    monkeypatch.setenv("TURNOVER_RESIST_STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setattr(backfill, "PROGRESS_FILE", tmp_path / "progress.json")
    monkeypatch.setattr(yearly, "PROGRESS", tmp_path / "yearly.json")
    monkeypatch.chdir(tmp_path)

    def no_network(*args, **kwargs):
        raise AssertionError("B6 tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", no_network)


@pytest.fixture
def infra():
    return pytest.importorskip("myquant_infra.derived_data.turnover_resistance.store")


def row(code="000001.SZ", tr=1.0):
    return {"stock_code": code, "close": 10.0, "turnover_resistance": tr,
            "turnover_resistance_free": tr / 2, "cyqk_T": 0.5}


def test_resolver_precedence_and_missing_configuration(monkeypatch, tmp_path):
    explicit = tmp_path / "explicit"
    assert host.resolve_parquet_path(explicit) == explicit
    assert host.resolve_staging_dir(explicit) == explicit
    assert host.resolve_parquet_path() == tmp_path / "tr.parquet"
    assert host.resolve_staging_dir() == tmp_path / "staging"
    monkeypatch.delenv("TURNOVER_RESIST_BANDS_PATH")
    monkeypatch.delenv("TURNOVER_RESIST_STAGING_DIR")
    assert host.resolve_parquet_path() == tmp_path / "lake/turnover_resistance_daily.parquet"
    assert host.resolve_staging_dir() == tmp_path / "lake/tr_staging"
    monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT")
    monkeypatch.delenv("OSKH_AUTHORITY_HINT_ROOT")
    monkeypatch.delenv("TURNOVER_RESIST_DATA_DIR")
    with pytest.raises(Exception, match="OSKH_SOURCE_PARQUET_ROOT"):
        host.resolve_parquet_path()
    with pytest.raises(Exception, match="OSKH_SOURCE_PARQUET_ROOT"):
        host.resolve_staging_dir()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("custom", [False, True])
def test_constructor_injects_host_producer_and_explicit_path(monkeypatch, tmp_path, custom):
    backend = Mock()
    monkeypatch.setattr(host, "require_infra", Mock(return_value=backend))
    producer = Mock() if custom else compute_tr_bb_columns
    store = host.TurnoverResistanceStore(bands_producer=producer) if custom else host.TurnoverResistanceStore()
    host.require_infra.assert_called_once_with("derived_data.turnover_resistance.store")
    backend.TurnoverResistanceStore.assert_called_once_with(
        tmp_path / "tr.parquet", bands_producer=producer,
    )
    assert store.path is backend.TurnoverResistanceStore.return_value.path
    store.read_disk_loads = 7
    store.read_cache_hits = 9
    assert store.cache_stats() is backend.TurnoverResistanceStore.return_value.cache_stats.return_value
    assert store.read_disk_loads == backend.TurnoverResistanceStore.return_value.read_disk_loads == 7
    assert store.read_cache_hits == backend.TurnoverResistanceStore.return_value.read_cache_hits == 9
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("method,args,kwargs", [
    ("upsert_daily", ("20261104", [row()]), dict(window=80, source="test", free_float_policy="fail")),
    ("load_series", ("000001.SZ",), dict(end_date="20261104", n=3, window=80, strict=False)),
    ("load_cross_section", ("20261104",), dict(window=80, require_bands=True)),
    ("load_bb_breakout", ("20261104",), dict(band="lower", window=80)),
    ("load_recent_history", (), dict(n_trading_days=7, end_date="20261104", window=80)),
    ("compute_and_update_bands", (), dict(trade_dates=["20261104"], n_history=30,
                                        period=5, nbdev=1.5, ddof=0, window=80, only_missing=True)),
    ("compute_all_bands_vectorized", (), dict(period=5, nbdev=1.5, ddof=0, window=80)),
    ("list_trade_dates", (), dict(window=80)),
    ("has_trade_date", ("20261104",), dict(window=80)),
    ("distribution_stats", ("20261104",), dict(window=80)),
])
def test_public_methods_preserve_arguments_and_results(monkeypatch, method, args, kwargs):
    backend = Mock()
    monkeypatch.setattr(host, "require_infra", Mock(return_value=SimpleNamespace(
        TurnoverResistanceStore=Mock(return_value=backend),
    )))
    store = host.TurnoverResistanceStore()
    assert getattr(store, method)(*args, **kwargs) is getattr(backend, method).return_value
    getattr(backend, method).assert_called_once_with(*args, **kwargs)
    store.invalidate_cache()
    backend.invalidate_cache.assert_called_once_with()


def test_merge_normalization_and_year_name_delegate(monkeypatch, tmp_path):
    backend = Mock()
    monkeypatch.setattr(host, "require_infra", Mock(return_value=backend))
    source = tmp_path / "year.parquet"
    assert host.merge_parquet_into_canonical(source) is backend.merge_parquet_into_canonical.return_value
    backend.merge_parquet_into_canonical.assert_called_once_with(source, canonical_path=tmp_path / "tr.parquet")
    assert host.resolve_year_staging_path(2026) is backend.resolve_year_staging_path.return_value
    backend.resolve_year_staging_path.assert_called_once_with(2026, tmp_path / "staging")
    incoming = row()
    assert host.normalize_ffi_row(incoming, trade_date="20261104", window=80, source="test",
                                  free_float_policy="skip") is backend.normalize_ffi_row.return_value
    backend.normalize_ffi_row.assert_called_once_with(
        incoming, trade_date="20261104", window=80, source="test", free_float_policy="skip",
    )


def test_import_help_and_patchable_surface_without_private_infra(tmp_path):
    script = '''
import importlib.abc
from pathlib import Path
import sys
from unittest.mock import Mock
class NoInfra(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "myquant_infra" or fullname.startswith("myquant_infra."):
            raise ModuleNotFoundError("private dependency intentionally unavailable")
sys.meta_path.insert(0, NoInfra())
from oskh_data import turnover_resistance_store as host
from scripts.tr import compute_turnover_resistance_bands as daily
from scripts.tr import backfill_turnover_resistance_bands as backfill
from scripts.tr import backfill_turnover_resistance_yearly as yearly
from scripts.data import refresh_tr_store_window
mock = Mock(spec=host.TurnoverResistanceStore)
assert callable(mock.compute_and_update_bands)
for entry in (daily.main, backfill.main, yearly.main):
    try:
        entry(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
assert len(host.SCHEMA_COLUMNS) == 33
root = Path(sys.argv[1])
assert host.resolve_parquet_path(root / "tr.parquet") == root / "tr.parquet"
for action in (
    lambda: host.TurnoverResistanceStore(root / "tr.parquet"),
    lambda: host.merge_parquet_into_canonical(root / "year.parquet", canonical_path=root / "tr.parquet"),
    lambda: host.resolve_year_staging_path(2026, root),
    lambda: host.normalize_ffi_row({}, trade_date="20261104"),
):
    try:
        action()
    except ImportError as exc:
        assert "requirements-infra.txt" in str(exc)
    else:
        raise AssertionError("TR IO must require infra")
assert list(root.iterdir()) == []
'''
    env = os.environ.copy()
    repo = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = os.pathsep.join([repo, env.get("PYTHONPATH", "")])
    if not any(env.get(key) for key in _INTERPRETER_KEYS):
        env["OSKH_MERGE_PYTHON"] = sys.executable  # yearly resolves an interpreter at import
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=tmp_path,
                            env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_store_schema_host_producer_and_cache_isolation(infra, tmp_path):
    assert host.SCHEMA_COLUMNS == infra.SCHEMA_COLUMNS
    assert host.UNIQUE_KEYS == infra.UNIQUE_KEYS
    assert host.DEFAULT_WINDOW == infra.DEFAULT_WINDOW
    assert host.DEFAULT_FREE_FLOAT_POLICY == infra.DEFAULT_FREE_FLOAT_POLICY
    producer = Mock(wraps=compute_tr_bb_columns)
    store = host.TurnoverResistanceStore(bands_producer=producer)
    assert isinstance(store._store, infra.TurnoverResistanceStore)
    for i in range(1, 5):
        store.upsert_daily(f"2026110{i}", [row(tr=float(i))])
    stats = store.compute_all_bands_vectorized(period=3, nbdev=1.5, ddof=0)
    assert stats == {"updated_rows": 2, "total_rows": 4}
    assert producer.call_args.kwargs == {"period": 3, "nbdev": 1.5, "ddof": 0}
    saved = pd.read_parquet(store.path)
    assert list(saved.columns) == list(host.SCHEMA_COLUMNS)
    assert list(saved.close) == [10.0] * 4
    cross = store.load_cross_section("20261104", require_bands=True)
    assert cross.tr_bb_middle.iloc[0] == 3.0
    assert cross.tr_bb_free_middle.iloc[0] == 1.5
    cross.loc[:, "close"] = 99.0
    assert store.load_cross_section("20261104").close.iloc[0] == 10.0
    assert not store.path.with_suffix(".staging.parquet").exists()
    with store._store._locked():
        assert store.path.with_suffix(".parquet.lock").exists()


def test_producer_failure_does_not_publish_or_mutate_cached_rows(infra):
    producer = Mock(side_effect=ValueError("bad {producer}"))
    store = host.TurnoverResistanceStore(bands_producer=producer)
    store.upsert_daily("20261104", [row()])
    before = store.path.read_bytes()
    cached = store.load_cross_section("20261104")
    with pytest.raises(ValueError, match="bad"):
        store.compute_and_update_bands(["20261104"])
    assert store.path.read_bytes() == before
    pd.testing.assert_frame_equal(store.load_cross_section("20261104"), cached)


def test_daily_pipeline_injects_host_compute_and_preserves_skip_bands_only(infra, monkeypatch):
    compute = Mock(return_value=[row(tr=3.0)])
    monkeypatch.setattr(daily, "compute_turnover_resist", compute)
    assert daily.main(["--date", "20261104", "--data-dir", "synthetic", "--bb-period", "1"]) == 0
    compute.assert_called_once_with("20261104", data_dir="synthetic", window=1000,
                                    free_float_policy="warn-zero")
    compute.reset_mock()
    assert daily.main(["--date", "20261104", "--skip-existing"]) == 0
    assert daily.main(["--date", "20261104", "--backfill-bands-only"]) == 0
    compute.assert_not_called()
    assert len(host.TurnoverResistanceStore().load_cross_section("20261104", require_bands=True)) == 1


@pytest.mark.parametrize("mode", ["--year", "--all-trading-days", "--trading-days", "default"])
def test_backfill_dates_skip_and_recompute_are_host_jobs(infra, monkeypatch, tmp_path, mode):
    dates = ["20261103", "20261104"]
    monkeypatch.setattr(backfill, "list_trading_dates", Mock(return_value=dates))
    compute = Mock(return_value=[row()])
    monkeypatch.setattr(backfill, "compute_turnover_resist", compute)
    args = {"--year": ["--year", "2026"], "--all-trading-days": ["--all-trading-days"],
            "--trading-days": ["--trading-days", "2"], "default": []}[mode]
    assert backfill.main([*args, "--tr-only"]) == 0
    assert compute.call_count == 2
    assert host.TurnoverResistanceStore().list_trade_dates() == dates
    compute.reset_mock()
    assert backfill.main([*args, "--skip-existing", "--tr-only"]) == 0
    compute.assert_not_called()
    assert backfill.main(["--recompute-bands"]) == 0
    assert backfill.main(["--year", "2026", "--year-bands"]) == 0
    assert json.loads((tmp_path / "progress.json").read_text())["skip"] == 2


def test_backfill_failure_with_curly_braces_is_recorded(infra, monkeypatch, tmp_path):
    monkeypatch.setattr(backfill, "list_trading_dates", Mock(return_value=["20261104"]))
    monkeypatch.setattr(backfill, "compute_turnover_resist", Mock(side_effect=ValueError("bad {row}")))
    assert backfill.main(["--year", "2026", "--tr-only"]) == 1
    assert json.loads((tmp_path / "progress.json").read_text())["fail"] == 1


def test_yearly_merge_uses_infra_last_file_wins_and_no_compute(infra, monkeypatch, tmp_path):
    first = host.resolve_year_staging_path(2026)
    second = host.resolve_year_staging_path(2025)
    host.TurnoverResistanceStore(first).upsert_daily("20261104", [row(tr=1.0)])
    host.TurnoverResistanceStore(second).upsert_daily("20261104", [row(tr=2.0)])
    run = Mock(side_effect=AssertionError("merge-only must not launch computation"))
    monkeypatch.setattr(yearly, "_run", run)
    assert yearly.main(["--from-year", "2026", "--to-year", "2025", "--merge-only"]) == 0
    run.assert_not_called()
    cross = host.TurnoverResistanceStore().load_cross_section("20261104")
    assert len(cross) == 1 and cross.turnover_resistance.iloc[0] == 2.0
    assert json.loads((tmp_path / "yearly.json").read_text())["status"] == "completed"


def test_yearly_launches_host_job_with_resolved_paths_and_stops_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(yearly, "resolve_year_staging_path", lambda year, directory: tmp_path / f"{year}.parquet")
    run = Mock(return_value=7)
    merge = Mock()
    monkeypatch.setattr(yearly, "_run", run)
    monkeypatch.setattr(yearly, "merge_parquet_into_canonical", merge)
    assert yearly.main(["--from-year", "2026", "--to-year", "2026"]) == 7
    command = run.call_args.args[0]
    assert command[:3] == [yearly.PY, "-u", str(yearly.BACKFILL)]
    assert command[3:] == ["--year", "2026", "--tr-only", "--skip-existing",
                           "--parquet-path", str(tmp_path / "2026.parquet")]
    merge.assert_not_called()
    assert json.loads((tmp_path / "yearly.json").read_text())["status"] == "failed"


def test_yearly_pipeline_recomputes_across_year_boundary(infra, monkeypatch, tmp_path):
    dates = list(pd.bdate_range("2025-12-10", periods=25).strftime("%Y%m%d"))

    def trading_dates(data_dir, *, start_date=None, end_date=None):
        return [date for date in dates if (not start_date or date >= start_date)
                and (not end_date or date <= end_date)]

    monkeypatch.setattr(backfill, "list_trading_dates", trading_dates)
    monkeypatch.setattr(backfill, "compute_turnover_resist",
                        lambda date, **kwargs: [row(tr=float(dates.index(date) + 1))])
    commands = []

    def run_host_job(command):
        commands.append(command)
        return backfill.main(command[3:])

    monkeypatch.setattr(yearly, "_run", run_host_job)
    assert yearly.main(["--from-year", "2026", "--to-year", "2025"]) == 0
    assert len(commands) == 3
    assert commands[-1][3:] == ["--recompute-bands", "--parquet-path", str(tmp_path / "tr.parquet")]
    store = host.TurnoverResistanceStore()
    assert store.list_trade_dates() == dates
    last = store.load_cross_section(dates[-1], require_bands=True)
    assert last.tr_bb_middle.iloc[0] == 15.5
    assert last.tr_bb_free_middle.iloc[0] == 7.75
    assert host.resolve_year_staging_path(2025).is_file()
    assert host.resolve_year_staging_path(2026).is_file()
