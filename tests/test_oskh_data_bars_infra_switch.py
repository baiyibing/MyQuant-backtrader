"""Hermetic B2 forwarding, public-CI stubs and retained compatibility contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from oskh_data import adj_factor_meta as meta
from oskh_data import daily_parquet_write as daily


def ms(value):
    return int(pd.Timestamp(value).value // 1_000_000)


def bars(times, closes=None):
    closes = closes if closes is not None else [10.0] * len(times)
    return pd.DataFrame({
        "time": times, "open": closes, "high": closes, "low": closes,
        "close": closes, "volume": [100] * len(times), "amount": [1000.0] * len(times),
    })


@pytest.fixture
def daily_root(monkeypatch, tmp_path):
    root = tmp_path / "daily"
    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(root))
    return root


@pytest.mark.parametrize("entry", meta.__all__)
def test_metadata_calls_forward_to_patchable_infra_boundary(monkeypatch, tmp_path, entry):
    backend = Mock()
    monkeypatch.setattr(meta, "_infra_meta", backend)
    path = tmp_path / "adj_factor.parquet"
    frame = pd.DataFrame({"date": [pd.Timestamp("2026-11-04")]})
    kwargs = dict(source="bt.test", build_time="fixed", data_max_date="2026-11-04", stock_count=7)
    if entry == "write_adj_factor_meta":
        result = meta.write_adj_factor_meta(path, frame, **kwargs)
        backend.write_adj_factor_meta.assert_called_once_with(path, frame, **kwargs)
    else:
        result = getattr(meta, entry)(path)
        getattr(backend, entry).assert_called_once_with(path)
    assert result is getattr(backend, entry).return_value


def test_imports_and_patchable_stubs_without_private_package(tmp_path):
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
from oskh_data import adj_factor_meta as meta
from oskh_data import daily_parquet_write as daily
from oskh_data import adj_factor, repair_daily_parquet_schema, seed_missing_front
assert daily.STANDARD_COLUMNS == ["time", "open", "high", "low", "close", "volume", "amount"]
assert str(daily.CANONICAL_ARROW_TYPES["volume"]) == "int64"
for entry in meta.__all__:
    args = ("adj_factor.parquet",)
    kwargs = {"source": "test"} if entry == "write_adj_factor_meta" else {}
    try:
        getattr(meta, entry)(*args, **kwargs)
    except ImportError as exc:
        assert "requirements-infra.txt" in str(exc)
    else:
        raise AssertionError("metadata IO must require infra")
    stub = Mock(return_value="patched")
    setattr(meta._infra_meta, entry, stub)
    assert getattr(meta, entry)(*args, **kwargs) == "patched"
assert list(Path(sys.argv[1]).iterdir()) == []
'''
    env = os.environ.copy()
    for key in ("OSKH_SOURCE_PARQUET_ROOT", "OSKH_AUTHORITY_HINT_ROOT", "OSKH_DATA_ROOT"):
        env.pop(key, None)
    env["OSKH_PERIOD_1D_ROOT"] = str(tmp_path)
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                            env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_metadata_roundtrip_uses_infra_and_keeps_wire_contract(tmp_path):
    infra = pytest.importorskip("myquant_infra.bars.adj_factor_meta")
    assert meta._infra_meta is infra
    path = tmp_path / "space's directory" / "adj_factor.parquet"
    frame = pd.DataFrame({
        "date": ["2026-11-03", "2026-11-04", "bad"],
        "stock_code": ["600000.SH", "600001.SH", "600000.SH"],
    })
    sidecar = meta.write_adj_factor_meta(path, frame, source="bt.test", build_time="fixed")
    assert sidecar == path.with_name("adj_factor.meta.json")
    assert json.loads(sidecar.read_text(encoding="utf-8")) == {
        "data_max_date": "2026-11-04", "build_time": "fixed", "source": "bt.test", "stock_count": 2,
    }
    assert meta.read_adj_factor_data_max_date(path) == pd.Timestamp("2026-11-04")
    assert not path.exists()
    assert list(sidecar.parent.iterdir()) == [sidecar]


@pytest.mark.parametrize("content", [None, "{bad", '{"data_max_date": "bad"}', '{"data_max_date": null}'])
def test_invalid_or_absent_sidecars_keep_freshness_fallback(tmp_path, content):
    pytest.importorskip("myquant_infra.bars.adj_factor_meta")
    path = tmp_path / "adj_factor.parquet"
    if content is not None:
        meta.adj_factor_meta_path(path).write_text(content, encoding="utf-8")
    assert meta.read_adj_factor_data_max_date(path) is None


def test_installed_schema_constants_are_infra_exports():
    infra = pytest.importorskip("myquant_infra.bars.schema")
    assert daily.STANDARD_COLUMNS is infra.STANDARD_COLUMNS
    assert daily.CANONICAL_ARROW_TYPES is infra.CANONICAL_ARROW_TYPES


@pytest.mark.parametrize("entry", ["merge_write_one_daily", "_legacy_merge_write"])
@pytest.mark.parametrize("target", ["2026-11-04", "2026-11-05"])
def test_blocked_daily_merges_preserve_untouched_legacy_history(tmp_path, entry, target):
    path = tmp_path / "data.parquet"
    old_times = [ms("2026-11-02 16:00"), ms("2026-11-03 16:00")]
    bars(old_times).to_parquet(path, index=False)
    getattr(daily, entry)(path, bars([ms(target)], [12.0]))
    output = pd.read_parquet(path)
    assert output.time.iloc[0] == old_times[0]
    assert output.time.iloc[-1] == ms(target)
    assert output.close.iloc[-1] == 12.0
    assert len(output) == (2 if target == "2026-11-04" else 3)
    assert str(pq.ParquetFile(path).schema_arrow.field("volume").type) == "int64"


@pytest.mark.parametrize("mode", ["legacy", "parallel", "batch"])
def test_blocked_daily_batch_salvages_good_symbols(daily_root, tmp_path, mode):
    good = bars([ms("2026-11-04")])
    bad = good.drop(columns="close")
    ok, errors = daily.write_processed_data(
        tmp_path, "none", {"600000.SH": good, "600001.SH": bad}, mode=mode, max_workers=1,
    )
    assert ok == 1 and len(errors) == 1
    assert (daily_root / "dividend_type=none/symbol=600000_SH/data.parquet").is_file()
    assert not (daily_root / "dividend_type=none/symbol=600001_SH/data.parquet").exists()


def test_blocked_schema_repair_changes_types_without_changing_cst_time(tmp_path):
    from oskh_data.repair_daily_parquet_schema import repair_parquet_file

    path = tmp_path / "data.parquet"
    legacy_time = ms("2026-11-03 16:00")
    bars([legacy_time]).assign(volume=100.4).to_parquet(path, index=False)
    assert repair_parquet_file(path)
    assert list(pd.read_parquet(path).time) == [legacy_time]
    assert pq.ParquetFile(path).schema_arrow.field("volume").type == pa.int64()
    assert not repair_parquet_file(path)


def test_blocked_seed_keeps_bytes_and_existing_front(daily_root, tmp_path):
    from oskh_data.seed_missing_front import seed_missing_front_from_none

    none = daily._file_path(tmp_path, "none", "600000.SH")
    frame = bars([ms("2026-11-02 16:00"), ms("2026-11-04")])
    frame.to_parquet(none, index=False)
    before = none.read_bytes()
    stats = seed_missing_front_from_none(tmp_path, ["600000_SH", "600000.SH"],
                                         require_none_min_date="20261104")
    front = daily._file_path(tmp_path, "front", "600000.SH", ensure_dir=False)
    assert stats.seeded == ["600000.SH"] and stats.seeded_count == 1
    assert front.read_bytes() == before == none.read_bytes()
    frame.assign(close=99.0).to_parquet(none, index=False)
    stats = seed_missing_front_from_none(tmp_path, ["600000.SH"])
    assert stats.skipped_front_exists == ["600000.SH"]
    assert front.read_bytes() == before


def test_blocked_factor_builder_keeps_outer_dates_and_forward_fill(daily_root, monkeypatch):
    from oskh_data import adj_factor

    for attr, adjust in (("FRONT_DIR", "front"), ("NONE_DIR", "none"), ("BACK_DIR", "back")):
        monkeypatch.setattr(adj_factor, attr, str(daily_root / f"dividend_type={adjust}"))
    first, second = ms("2026-11-03"), ms("2026-11-04")
    for adjust, frame in (("front", bars([first], [5.0])), ("none", bars([first, second]))):
        path = daily_root / f"dividend_type={adjust}/symbol=600000_SH/data.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
    output = adj_factor.build_for_symbol("600000_SH")
    assert list(output.date) == [pd.Timestamp("2026-11-03"), pd.Timestamp("2026-11-04")]
    assert list(output.cumulative_adj_factor) == [0.5, 0.5]
    assert output.adj_factor_back.isna().all()


def test_blocked_factor_main_salvages_symbol_and_forwards_metadata(daily_root, tmp_path, monkeypatch):
    from oskh_data import adj_factor

    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(tmp_path))
    output = tmp_path / "adj_factor.parquet"
    monkeypatch.setattr(sys, "argv", ["adj_factor", "--output", str(output)])
    monkeypatch.setattr(adj_factor, "_common_symbols", lambda **kwargs: ["600000_SH", "600001_SH"])
    good = pd.DataFrame({
        "date": [pd.Timestamp("2026-11-04")], "stock_code": ["600000.SH"],
        "close_front": [5.0], "close_none": [10.0],
        "cumulative_adj_factor": [0.5], "adj_factor_back": [float("nan")],
    })
    monkeypatch.setattr(adj_factor, "build_for_symbol", Mock(side_effect=[good, ValueError("bad symbol")]))
    backend = Mock()
    monkeypatch.setattr(meta, "_infra_meta", backend)
    adj_factor.main()
    assert list(pd.read_parquet(output).stock_code) == ["600000.SH"]
    args, kwargs = backend.write_adj_factor_meta.call_args
    assert args[0] == str(output)
    pd.testing.assert_frame_equal(args[1], good)
    assert kwargs["source"] == "oskh_data.adj_factor.main"


def test_pin_witness_daily_history_and_cst_repair_mismatches(tmp_path):
    writer = pytest.importorskip("myquant_infra.bars.writer")
    repair = pytest.importorskip("myquant_infra.bars.repair")
    path = tmp_path / "merge.parquet"
    legacy_time = ms("2026-11-02 16:00")
    bars([legacy_time]).to_parquet(path, index=False)
    writer.merge_write_one(path, bars([ms("2026-11-04")]))
    assert pd.read_parquet(path).time.iloc[0] != legacy_time
    path = tmp_path / "repair.parquet"
    bars([legacy_time]).assign(volume=100.4).to_parquet(path, index=False)
    before = path.read_bytes()
    result = repair.repair_parquet_file(path, apply=True)
    assert result.status == "quarantine"
    assert path.read_bytes() == before
