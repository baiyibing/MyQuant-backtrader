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


def ms(value):
    return int(pd.Timestamp(value).value // 1_000_000)


def bars(times, closes=None):
    closes = closes if closes is not None else [10.0] * len(times)
    return pd.DataFrame({
        "time": times, "open": closes, "high": closes, "low": closes,
        "close": closes, "volume": [100] * len(times), "amount": [1000.0] * len(times),
    })


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
