# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from oskh_data.industry_sw_l1 import (
    industry_bucket_for_stock,
    load_industry_map,
    load_sw_l1_map,
    load_wind_csv,
    load_wind_l1_map,
    lookup_industry,
    normalize_industry,
    normalize_wind_code,
    resolve_sw_l1_root,
)


def test_normalize_industry_and_code():
    assert normalize_industry("银行（申万）") == "银行申万"
    assert normalize_wind_code("600000.sh") == "600000.SH"
    assert normalize_wind_code("bad") is None


def test_load_wind_csv_accepts_dotted_industry_header(tmp_path):
    path = tmp_path / "batch_0000.csv"
    path.write_text(
        "Wind代码,证券简称,申万一级行业.行业级别\n000001.SZ,平安银行,银行\n",
        encoding="utf-8",
    )
    rows = load_wind_csv(path)
    assert rows[0]["申万一级行业"] == "银行"


def test_load_maps_and_lookup(tmp_path):
    sw = tmp_path / "sw_l1_map.csv"
    sw.write_text(
        "code_gildata,name,sw_l1\n600000.SH,浦发银行,银行\n000001.SZ,平安银行,银行\n",
        encoding="utf-8",
    )
    wind = tmp_path / "wind_l1_map.csv"
    wind.write_text(
        "code_gildata,name,wind_sw_l1\n600000.SH,浦发银行,银行（申万）\n",
        encoding="utf-8",
    )
    sw_map = load_sw_l1_map(sw)
    assert sw_map["600000.SH"] == "银行"
    assert lookup_industry("600000", sw_map) == "银行"
    assert lookup_industry("000001.SZ", sw_map) == "银行"
    wind_map = load_wind_l1_map(wind)
    assert wind_map["600000.SH"] == "银行（申万）"
    assert industry_bucket_for_stock("999999.SZ", sw_map) == "_UNMAPPED_"


def test_load_industry_map_wind_overlays_sw(monkeypatch, tmp_path):
    root = tmp_path / "vendor_wind_sw_l1"
    root.mkdir()
    (root / "sw_l1_map.csv").write_text(
        "code_gildata,name,sw_l1\n600000.SH,浦发银行,银行\n000002.SZ,万科A,房地产\n",
        encoding="utf-8",
    )
    (root / "wind_l1_map.csv").write_text(
        "code_gildata,name,wind_sw_l1\n600000.SH,浦发银行,银行（申万）\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "oskh_data.industry_sw_l1.resolve_sw_l1_root", lambda: root
    )
    got = load_industry_map()
    assert got["600000.SH"] == "银行（申万）"
    assert got["000002.SZ"] == "房地产"


def test_missing_default_map_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "oskh_data.industry_sw_l1.resolve_sw_l1_root", lambda: tmp_path / "missing"
    )
    with pytest.raises(FileNotFoundError, match="sw_l1_map"):
        load_sw_l1_map()
    with pytest.raises(FileNotFoundError, match="sw_l1_map"):
        load_industry_map()


def test_explicit_missing_map_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_sw_l1_map(tmp_path / "nope.csv")


def test_industry_map_requires_wind_overlay(monkeypatch, tmp_path):
    root = tmp_path / "vendor_wind_sw_l1"
    root.mkdir()
    (root / "sw_l1_map.csv").write_text(
        "code_gildata,name,sw_l1\n600000.SH,浦发银行,银行\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("oskh_data.industry_sw_l1.resolve_sw_l1_root", lambda: root)
    with pytest.raises(FileNotFoundError, match="wind_l1_map"):
        load_industry_map()


def test_resolve_sw_l1_root_follows_source(monkeypatch, tmp_path):
    lake = tmp_path / "lake"
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(lake))
    monkeypatch.delenv("OSKH_AUTHORITY_HINT_ROOT", raising=False)
    assert resolve_sw_l1_root() == Path(lake) / "vendor_wind_sw_l1"


def test_stratify_by_industry():
    from backtest.research import unified_exit_modea as modea

    inst = modea.Instance("600000.SH", "浦发", "20251023", 10.0, True)
    er = modea.ExitResult("20251024", 11.0, "n_expire", 0.1, 100.0, 100, 1, True)
    key = modea.instance_key(inst)
    got = modea.stratify_mean_returns(
        [inst],
        {key: er},
        by="industry",
        industry_map={"600000.SH": "银行"},
    )
    assert got == {"银行": 0.1}
