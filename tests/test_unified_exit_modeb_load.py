"""Data-free Mode B loading fixtures; all symbols are invented."""
import pandas as pd

from backtest.research import ashare_bars as bars
from backtest.research import csv_minute_backtest as minute
from backtest.research import unified_exit_modeb as b


def minute_frame():
    return pd.DataFrame({"open": [10.], "high": [11.], "low": [9.],
                         "close": [10.], "ymd": ["20251024"], "hm": [600]},
                        index=pd.to_datetime(["2025-10-24 10:00"]))


def test_cache_miss_hit_subset_and_partial_preserve(tmp_path, monkeypatch):
    calls = []
    def lake(codes, start, end, **kw):
        calls.append((codes, start, end))
        return {c: minute_frame() for c in codes}
    monkeypatch.setattr(bars, "load_minute_from_lake", lake)
    status = {}
    b.load_monitor_bars({"600998.SH", "600997.SH"}, cache_dir=tmp_path, status=status)
    assert status["cache"] == "miss"
    assert calls[0][1:] == ("20251013", "20260909")
    path = tmp_path / "minute_none_20251013_20260909.parquet"
    assert path.is_file()
    cached = b.load_monitor_bars({"600998.SH"}, cache_dir=tmp_path, status=status)
    assert status["cache"] == "hit" and len(calls) == 1
    assert cached["600998.SH"]["hm"].tolist() == [600]
    assert b.minute_coverage(["600998.SH"], cached)["covered_codes"] == 1
    b.load_monitor_bars({"600996.SH"}, cache_dir=tmp_path)
    assert set(minute.read_minute_cache(path, None)) == {"600998.SH", "600997.SH", "600996.SH"}


def test_mmap_pack_write_hit_and_matches_frames(tmp_path, monkeypatch):
    def lake(codes, start, end, **kw):
        return {c: minute_frame() for c in codes}

    monkeypatch.setattr(bars, "load_minute_from_lake", lake)
    status = {}
    first = b.load_prepared_minutes({"600998.SH"}, cache_dir=tmp_path, status=status)
    assert status["pack"] == "write" and status["cache"] == "miss"
    pack = tmp_path / "modeb_pack_20251013_20260909"
    assert (pack / "meta.json").is_file()
    assert (pack / "open.f64").is_file()
    second = b.load_prepared_minutes({"600998.SH"}, cache_dir=tmp_path, status=status)
    assert status["cache"] == "pack" and status["pack"] == "hit"
    assert isinstance(first, b.PreparedMinutes) and isinstance(second, b.PreparedMinutes)
    assert first.last_close("600998.SH", "20251024") == 10.0
    assert second.last_close("600998.SH", "20251024") == 10.0
    assert b.minute_coverage(["600998.SH"], second)["covered_codes"] == 1
    assert second._mmkeep and second.packed["600998.SH"].open.base is not None


def test_coverage():
    assert b.minute_coverage({"600998.SH"}, {})["missing_codes"] == ["600998.SH"]
    report = b.minute_coverage(["600998.SH"] * 2, {"600998.SH": minute_frame()})
    assert report["requested_codes"] == report["covered_codes"] == 1
    assert report["minute_lake_end"] == "20260909"
    assert b.minute_coverage({"600998.SH"}, {"600998.SH": minute_frame()}, end="20251023")["covered_codes"] == 0


def test_session_minutes_matches_production_annotation():
    raw = pd.DataFrame(index=pd.to_datetime([
        f"2025-10-24 {clock}" for clock in
        ["09:29", "09:30", "10:00", "11:30", "11:31", "12:00",
         "12:59", "13:00", "15:00", "15:01"]
    ]))
    raw["ymd"] = raw.index.strftime("%Y%m%d")
    raw["hm"] = raw.index.hour * 60 + raw.index.minute
    got = b.session_minutes(raw)
    pd.testing.assert_frame_equal(got, bars.annotate_session(raw))
    assert got["hm"].tolist() == [570, 600, 690, 780, 900]
    for hm in (570, 900):
        assert b.minute_coverage(["600998.SH"], {
            "600998.SH": got.loc[got["hm"] == hm]
        })["covered_codes"] == 1


def test_legacy_hhmm_fixture_is_not_a_session_clock():
    # Old fixtures used HHMM; keep this guard against silently reviving that unit.
    legacy = pd.DataFrame({"ymd": ["20251024"] * 4, "hm": [930, 1000, 1459, 1500]})
    assert b.session_minutes(legacy).empty


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
