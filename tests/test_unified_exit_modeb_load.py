"""Data-free Mode B loading fixtures; all symbols are invented."""
import pandas as pd

from backtest.research import csv_minute_backtest as minute
from backtest.research import unified_exit_modeb as b


def minute_frame():
    return pd.DataFrame({"open": [10.], "high": [11.], "low": [9.],
                         "close": [10.], "ymd": ["20251024"], "hm": [1000]},
                        index=pd.to_datetime(["2025-10-24 10:00"]))


def test_cache_miss_hit_subset_and_partial_preserve(tmp_path, monkeypatch):
    calls = []
    def lake(codes, start, end, **kw):
        calls.append((codes, start, end))
        return {c: minute_frame() for c in codes}
    monkeypatch.setattr(minute, "_load_minute_from_lake", lake)
    status = {}
    b.load_monitor_bars({"600998.SH", "600997.SH"}, cache_dir=tmp_path, status=status)
    assert status["cache"] == "miss"
    assert calls[0][1:] == ("20251013", "20260909")
    path = tmp_path / "minute_none_20251013_20260909.parquet"
    assert path.is_file()
    b.load_monitor_bars({"600998.SH"}, cache_dir=tmp_path, status=status)
    assert status["cache"] == "hit" and len(calls) == 1
    b.load_monitor_bars({"600996.SH"}, cache_dir=tmp_path)
    assert set(minute.read_minute_cache(path, None)) == {"600998.SH", "600997.SH", "600996.SH"}


def test_coverage():
    assert b.minute_coverage({"600998.SH"}, {})["missing_codes"] == ["600998.SH"]
    report = b.minute_coverage(["600998.SH"] * 2, {"600998.SH": minute_frame()})
    assert report["requested_codes"] == report["covered_codes"] == 1
    assert report["minute_lake_end"] == "20260909"
    assert b.minute_coverage({"600998.SH"}, {"600998.SH": minute_frame()}, end="20251023")["covered_codes"] == 0


def test_none_root_and_pool(tmp_path, monkeypatch):
    seen = {}
    def load(codes, start, end, **kw):
        seen.update(kw)
        return {}
    monkeypatch.setattr(b.modea, "load_front_bars", load)
    monkeypatch.setattr(b, "resolve_period_root", lambda period: tmp_path / period)
    b.load_none_bars([], "20251023", "20260909")
    assert seen["front_root"] == tmp_path / "1d" / "dividend_type=none"
    (tmp_path / "20251023.csv").write_text("code,name\n600998.SH,fixture\n", encoding="utf-8")
    bars = {"600998.SH": pd.DataFrame({"close": [10., 10.5]}, index=pd.to_datetime(["20251022", "20251023"]))}
    instances = b.assemble_instances(tmp_path, ["20251023"], bars)
    assert len(instances) == 1 and instances[0].opened
    assert instances[0].buy_price == 10.5
