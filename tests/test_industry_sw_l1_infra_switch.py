"""B5 host authority, optional imports and read-only infra delegation."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from common.infra.data_root import UnconfiguredDataRootError
from oskh_data import industry_sw_l1 as industry


@pytest.fixture
def maps(tmp_path):
    root = tmp_path / industry.LAKE_NAME
    root.mkdir()
    (root / industry.SW_L1_MAP_NAME).write_text(
        "code_gildata,sw_l1\n600000.SH,银行\n", encoding="utf-8"
    )
    (root / industry.WIND_L1_MAP_NAME).write_text(
        "code_gildata,wind_sw_l1\n600000.SH,银行（申万）\n", encoding="utf-8"
    )
    return root


@pytest.mark.parametrize("entry,args,module", [
    ("normalize_industry", ("银行（申万）",), "vendor_wind_sw_l1"),
    ("normalize_wind_code", ("600000.sh",), "vendor_wind_sw_l1"),
    ("load_wind_csv", (Path("batch_0000.csv"),), "vendor_wind_sw_l1"),
    ("lookup_industry", ("600000", {"600000.SH": "银行"}), "readers"),
    ("industry_bucket_for_stock", ("999999.SZ", {}), "readers"),
])
def test_helpers_forward_to_verified_infra_surface(monkeypatch, entry, args, module):
    backend = Mock()
    load = Mock(return_value=backend)
    monkeypatch.setattr(industry, "require_infra", load)
    assert getattr(industry, entry)(*args) is getattr(backend, entry).return_value
    load.assert_called_once_with(f"reference_data.industry.{module}")
    getattr(backend, entry).assert_called_once_with(*args)


@pytest.mark.parametrize("entry,filename", [
    ("load_sw_l1_map", industry.SW_L1_MAP_NAME),
    ("load_wind_l1_map", industry.WIND_L1_MAP_NAME),
])
@pytest.mark.parametrize("explicit", [False, True])
def test_map_readers_pass_explicit_host_paths(monkeypatch, maps, entry, filename, explicit):
    backend = Mock()
    load = Mock(return_value=backend)
    resolve = Mock(return_value=maps)
    monkeypatch.setattr(industry, "require_infra", load)
    monkeypatch.setattr(industry, "resolve_sw_l1_root", resolve)
    target = maps / filename
    args = (target,) if explicit else ()
    assert getattr(industry, entry)(*args) is getattr(backend, entry).return_value
    getattr(backend, entry).assert_called_once_with(target)
    load.assert_called_once_with("reference_data.industry.readers")
    if explicit:
        resolve.assert_not_called()
    else:
        resolve.assert_called_once_with()


@pytest.mark.parametrize("use_source_env", [False, True])
def test_combined_reader_uses_host_authority(monkeypatch, maps, tmp_path, use_source_env):
    # Source env wins over an alternative authority marker; otherwise the marker wins.
    hint = tmp_path / "hint" if use_source_env else maps.parent
    hint.mkdir(exist_ok=True)
    (hint / ".authority").write_text("", encoding="utf-8")
    monkeypatch.setenv("OSKH_AUTHORITY_HINT_ROOT", str(hint))
    monkeypatch.setenv("OSKH_DATA_ROOT", str(tmp_path / "workspace"))
    if use_source_env:
        monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(maps.parent))
    else:
        monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT", raising=False)
    backend = Mock()
    load = Mock(return_value=backend)
    monkeypatch.setattr(industry, "require_infra", load)
    assert industry.load_industry_map() is backend.load_industry_map.return_value
    backend.load_industry_map.assert_called_once_with(maps)
    load.assert_called_once_with("reference_data.industry.readers")
    assert not (tmp_path / "workspace").exists()


@pytest.mark.parametrize("missing", [industry.SW_L1_MAP_NAME, industry.WIND_L1_MAP_NAME])
@pytest.mark.parametrize("directory", [False, True])
def test_missing_or_directory_map_fails_before_infra(monkeypatch, maps, missing, directory):
    target = maps / missing
    target.unlink()
    if directory:
        target.mkdir()
    monkeypatch.setattr(industry, "resolve_sw_l1_root", lambda: maps)
    load = Mock(side_effect=AssertionError("must validate files before infra"))
    monkeypatch.setattr(industry, "require_infra", load)
    entry = industry.load_sw_l1_map if missing == industry.SW_L1_MAP_NAME else industry.load_wind_l1_map
    for read in (entry, industry.load_industry_map):
        with pytest.raises(FileNotFoundError) as exc:
            read()
        assert str(target) in str(exc.value)
        assert "OSKH_SOURCE_PARQUET_ROOT" in str(exc.value)
    load.assert_not_called()


@pytest.mark.parametrize("entry", ["load_sw_l1_map", "load_wind_l1_map", "load_industry_map"])
def test_unconfigured_root_fails_before_infra(monkeypatch, tmp_path, entry):
    monkeypatch.delenv("OSKH_SOURCE_PARQUET_ROOT", raising=False)
    monkeypatch.delenv("OSKH_AUTHORITY_HINT_ROOT", raising=False)
    monkeypatch.setenv("OSKH_DATA_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    load = Mock(side_effect=AssertionError("must resolve host configuration first"))
    monkeypatch.setattr(industry, "require_infra", load)
    with pytest.raises(UnconfiguredDataRootError):
        getattr(industry, entry)()
    load.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_no_private_dependency_keeps_imports_and_help_available(maps):
    script = '''
import importlib.abc
from pathlib import Path
import sys

class NoInfra(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "myquant_infra" or fullname.startswith("myquant_infra."):
            raise ModuleNotFoundError(fullname, name=fullname)

sys.meta_path.insert(0, NoInfra())
from oskh_data import industry_sw_l1 as industry
from backtest.research import research_overlay, unified_exit_modea, unified_exit_modeb
for module in (unified_exit_modea, unified_exit_modeb):
    try:
        module.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("help must exit without IO")
root = Path(sys.argv[1])
before = {p.name: p.read_bytes() for p in root.iterdir()}
industry.resolve_sw_l1_root = lambda: root
calls = (
    lambda: industry.normalize_industry("银行（申万）"),
    lambda: industry.normalize_wind_code("600000.sh"),
    lambda: industry.load_wind_csv(root / "batch.csv"),
    lambda: industry.lookup_industry("600000", {"600000.SH": "银行"}),
    lambda: industry.industry_bucket_for_stock("600000", {}),
    industry.load_sw_l1_map, industry.load_wind_l1_map, industry.load_industry_map,
)
for call in calls:
    try:
        call()
    except ImportError as exc:
        assert "requirements-infra.txt" in str(exc)
        assert "reference_data.industry" in str(exc)
    else:
        raise AssertionError("industry operations must explicitly require infra")
assert before == {p.name: p.read_bytes() for p in root.iterdir()}
'''
    env = os.environ.copy()
    for key in ("OSKH_SOURCE_PARQUET_ROOT", "OSKH_AUTHORITY_HINT_ROOT", "OSKH_DATA_ROOT"):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-c", script, str(maps)], env=env,
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_reader_keeps_csv_key_rules_overlay_and_input_bytes(monkeypatch, maps):
    pytest.importorskip("myquant_infra.reference_data.industry.readers")
    (maps / industry.SW_L1_MAP_NAME).write_text(
        "Wind代码,sw_l1\nsymbol=600000_SH,银行\n600000.SH, 非银金融 \n"
        "600000.SH,\n000001,裸码\n000001.sz,小写后缀\n,无代码\n",
        encoding="utf-8",
    )
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in maps.iterdir()}
    monkeypatch.setattr(industry, "resolve_sw_l1_root", lambda: maps)
    assert industry.load_sw_l1_map() == {
        "600000.SH": "非银金融", "000001": "裸码", "000001.sz": "小写后缀",
    }
    assert industry.load_industry_map() == {
        "600000.SH": "银行（申万）", "000001": "裸码", "000001.sz": "小写后缀",
    }
    assert before == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in maps.iterdir()}


@pytest.mark.parametrize("stock,mapping,expected", [
    ("600000.SH", {"600000": "裸码", "600000.SH": "精确"}, "精确"),
    ("600000.SH", {"600000": "裸码", "600000.SZ": "扫描"}, "裸码"),
    ("SH600000", {"600000": "尾码"}, "尾码"),
    ("600000", {"600000.SH": " 扫描 "}, "扫描"),
    ("000001", {"600000.SH": "银行"}, None),
    ("", {"600000.SH": "银行"}, None),
    ("600000.SH", {}, None),
])
def test_real_lookup_preserves_precedence_and_unmapped_bucket(stock, mapping, expected):
    pytest.importorskip("myquant_infra.reference_data.industry.readers")
    assert industry.lookup_industry(stock, mapping) == expected
    assert industry.industry_bucket_for_stock(stock, mapping) == (expected or "_UNMAPPED_")
