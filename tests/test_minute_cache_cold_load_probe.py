"""S1.1 data-free probe checks, with real synthetic source parquet."""
import pandas as pd
import pytest

from scripts.diagnostics import probe_minute_cache_cold_load as probe
from oskh_data.symbol_format import to_partition_key


@pytest.fixture
def lake(tmp_path):
    root = tmp_path / "lake"
    path = root / f"symbol={to_partition_key('600000.SH')}" / "data.parquet"
    path.parent.mkdir(parents=True)
    index = pd.to_datetime(["2026-01-15 09:30", "2026-02-01 09:30", "2026-02-28 15:00"], utc=True)
    pd.DataFrame({"time": index.as_unit("ms").asi8,
                  **{key: [10., 11., 12.] for key in ("open", "high", "low", "close")}}).to_parquet(path, index=False)
    return root, path


def test_month_bounds_leap_year_and_inverted_request():
    assert probe.month_windows("20240215", "20240302") == [
        ("20240201", "20240229"), ("20240301", "20240331")]
    with pytest.raises(ValueError):
        probe.month_windows("20260301", "20260201")


def test_cut_a_counts_include_all_history_not_only_new_month():
    counts = probe.cut_a_counts("20251227", "20260914")
    assert counts["modeled_not_measured_request_ends"] is True
    scenarios = counts["scenarios"]
    assert scenarios["same_month_plus_one"]["expected_rebuilt_shards_per_changed_symbol"] == 10
    assert scenarios["cross_month_plus_one"]["expected_rebuilt_shards_per_changed_symbol"] == 11
    assert scenarios["cross_month_plus_one"]["scenario_extended_end"] == "20261001"
    # Scenario ends are modeled demos — not live loader request ends to paste as --end.
    assert "base_end" not in scenarios["same_month_plus_one"]
    assert "extended_end" not in scenarios["cross_month_plus_one"]


def test_real_source_scan_equivalence_and_no_writes(lake):
    root, path = lake
    before = path.read_bytes()
    report = probe.probe(["600000.SH"], "20260115", "20260215", lake_root=root,
                         request_codes=5575, open_repeats=2)
    assert report["observations"][0]["rows"] == 3  # full months, including Feb 28
    assert report["actual_rebuilt_shards"] is None
    assert report["fd_extrapolation"]["projected_shard_files"] == 11150
    assert report["fd_extrapolation"]["one_handle_per_worker_projection"] == 16
    assert list(root.rglob("*.*")) == [path]
    assert path.read_bytes() == before


def test_missing_probe_source_is_error(lake):
    root, _ = lake
    with pytest.raises(FileNotFoundError):
        probe.probe(["600001.SH"], "20260115", "20260215", lake_root=root, request_codes=1)


def test_detect_source_change_during_measurement(lake, monkeypatch):
    import os
    root, path = lake
    original = probe.bars.read_lake_minute_ohlc

    def read(*args, **kwargs):
        result = original(*args, **kwargs)
        stamp = path.stat()
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1))
        return result

    monkeypatch.setattr(probe.bars, "read_lake_minute_ohlc", read)
    with pytest.raises(RuntimeError, match="source changed"):
        probe.probe(["600000.SH"], "20260115", "20260215", lake_root=root,
                    request_codes=1, open_repeats=1)


def test_cli_requires_configured_source_and_preserves_existing_output(lake, monkeypatch, tmp_path):
    root, _ = lake
    monkeypatch.setattr("common.infra.data_root.resolve_period_root", lambda period: root.parent / "absent")
    with pytest.raises(FileNotFoundError):
        probe.probe(["600000.SH"], "20260115", "20260215", request_codes=1)
    output = tmp_path / "evidence.json"
    output.write_text("previous", encoding="utf-8")
    monkeypatch.setattr(probe, "probe", lambda *args, **kwargs: {})
    with pytest.raises(FileExistsError):
        probe.main(["--codes", "600000.SH", "--start", "20260115", "--end", "20260215",
                    "--request-codes", "1", "--output", str(output)])
    assert output.read_text() == "previous"
