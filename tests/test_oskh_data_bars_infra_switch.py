"""Hermetic B2 exports, required dependencies and retained wire contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from oskh_data import adj_factor_meta as meta


@pytest.mark.parametrize("entry", meta.__all__)
def test_metadata_reexports_shared_infra_api(entry):
    from myquant_infra.bars import adj_factor_meta as infra
    assert getattr(meta, entry) is getattr(infra, entry)


def test_missing_private_package_fails_without_local_stubs(tmp_path):
    script = '''
import importlib.abc
import importlib
from pathlib import Path
import sys

class NoInfra(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "myquant_infra" or fullname.startswith("myquant_infra."):
            raise ModuleNotFoundError("private dependency intentionally unavailable", name="myquant_infra")

sys.meta_path.insert(0, NoInfra())
for name in ("oskh_data.adj_factor_meta", "oskh_data.reader"):
    try:
        importlib.import_module(name)
    except ModuleNotFoundError as exc:
        assert exc.name == "myquant_infra"
    else:
        raise AssertionError("consumer imported with a local stub")
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
    assert meta.write_adj_factor_meta is infra.write_adj_factor_meta
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
