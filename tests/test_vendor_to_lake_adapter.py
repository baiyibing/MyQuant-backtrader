"""BT keeps sample/configuration and ingress guards; processing is owned by infra."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest
from myquant_infra.adapters.vendor_bars import staging as shared
from myquant_infra.artifacts.provenance import git_commit

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bt_vendor_adapter", ROOT / "scripts/research/vendor_to_lake_adapter.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def source(tmp_path):
    path = tmp_path / "inputs" / "wind.csv"
    path.parent.mkdir()
    pd.DataFrame({"TIME": ["2025-10-24T10:00:00+08:00"], "wind_code": ["002231.SZ"],
                  "OPEN": [10.], "HIGH": [11.], "LOW": [9.], "MATCH": [10.5],
                  "VOLUME": [251]}).to_csv(path, index=False)
    return path


def test_processing_names_are_shared_not_local():
    for name in ("read_wind_start", "read_daily", "convert", "verify", "StartIntervalError"):
        assert getattr(a, name) is getattr(shared, name)
    assert a.DEFAULT_SYMBOLS == ["002231.SZ", "300379.SZ", "600200.SH"]


def test_caller_context_and_config_are_injected(tmp_path, monkeypatch):
    root = tmp_path / "configured"
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(root))
    calls = []
    monkeypatch.setattr(shared, "main", lambda argv, **kwargs: calls.append((argv, kwargs)) or 17)
    assert a.main(["--help"]) == 17
    argv, kwargs = calls[0]
    assert argv == ["--help"] and kwargs["repo_root"] == ROOT
    assert kwargs["protected_roots"]["OSKH_SOURCE_PARQUET_ROOT"] == root
    assert kwargs["default_symbols"] == a.DEFAULT_SYMBOLS


@pytest.mark.parametrize("bad", ["stock_data/out", "E:" + chr(92) + "stock_data" + chr(92) + "stage", "inputs/stage"])
def test_host_protected_output(tmp_path, bad):
    path = source(tmp_path)
    out = tmp_path / bad
    with pytest.raises(SystemExit):
        a.main(["--wind", str(path), "--out-dir", str(out)])
    assert not out.exists()


@pytest.mark.parametrize("key", ["OSKH_SOURCE_PARQUET_ROOT", "OSKH_PERIOD_1D_ROOT", "OSKH_PERIOD_1M_ROOT", "OSKH_AUTHORITY_HINT_ROOT"])
def test_configured_root_stays_protected(tmp_path, monkeypatch, key):
    path = source(tmp_path)
    root = tmp_path / "configured_lake"
    monkeypatch.setenv(key, str(root))
    with pytest.raises(SystemExit):
        a.main(["--wind", str(path), "--out-dir", str(root / "out")])
    assert not root.exists()


def test_symlink_to_lake_root(tmp_path, require_directory_symlink):
    path = source(tmp_path)
    lake = tmp_path / "stock_data"
    lake.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(lake, target_is_directory=True)
    with pytest.raises(SystemExit):
        a.main(["--wind", str(path), "--out-dir", str(alias / "out")])


def test_legacy_cli_is_read_only_and_keeps_sample_and_provenance(tmp_path):
    path = source(tmp_path)
    before = path.read_bytes()
    out = tmp_path / "out"
    result = subprocess.run([sys.executable, str(Path(a.__file__)), "--wind", str(path), "--out-dir", str(out)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert path.read_bytes() == before
    status = json.loads((out / "STATUS.json").read_text(encoding="utf-8"))
    pin = json.loads((out / "PIN.json").read_text(encoding="utf-8"))
    assert status["lake_writes"] is False and status["tip"] == git_commit(ROOT)
    assert pin["symbols"] == a.DEFAULT_SYMBOLS and pin["unit_out"] == "lots"
    assert "--write-lake" not in a.parser().format_help()


def test_missing_shared_dependency_fails_without_outputs(tmp_path):
    code = """
import importlib.abc, runpy, sys
class NoInfra(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == 'myquant_infra' or name.startswith('myquant_infra.'):
            raise ModuleNotFoundError('required infra unavailable', name=name)
sys.meta_path.insert(0, NoInfra())
runpy.run_path(sys.argv[1], run_name='__main__')
"""
    result = subprocess.run([sys.executable, "-c", code, str(Path(a.__file__))],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0 and "required infra unavailable" in result.stderr
    assert list(tmp_path.iterdir()) == []
