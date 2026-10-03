"""Version1 scan counts and explicit read-only sources; only temporary data."""

import ast
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.research.bar_scan_exit import OhlcBar
from backtest.research.minute_bar_scan_host import (
    load_scan_bars,
    main,
    run_scan,
    scan_held_bars,
)

ROOT = Path(__file__).resolve().parents[1]
SYMBOL = "000739.SZ"
DAY = "20260106"


def test_scan_counts_current_bar_fill_and_skip():
    result = scan_held_bars(
        [OhlcBar(10.0, 10.1, 9.95, 10.05), OhlcBar(9.70, 9.80, 9.60, 9.75)],
        cost=10.0, peak=10.0,
    )
    assert result.fills == 1
    assert result.skips == 1
    assert result.bars == 2


def test_scan_carries_peak_into_the_next_bar():
    result = scan_held_bars(
        [OhlcBar(11.0, 12.0, 10.9, 11.8), OhlcBar(10.9, 11.0, 10.8, 10.9)],
        cost=10.0, peak=10.0,
    )
    assert (result.bars, result.fills, result.skips) == (2, 1, 1)


def test_empty_bars_raise():
    with pytest.raises(ValueError, match="empty"):
        scan_held_bars([], cost=10.0, peak=10.0)


@pytest.mark.parametrize("n_days", [0, 2])
def test_scan_keeps_n_days_one(n_days):
    with pytest.raises(ValueError, match="n_days"):
        scan_held_bars([OhlcBar(10.0, 10.1, 9.95, 10.05)], cost=10, peak=10, n_days=n_days)


@pytest.mark.parametrize("strategy", ["topk_dropout", "topk_score_exit"])
def test_scan_has_no_strategy_selection(strategy):
    with pytest.raises(TypeError, match="strategy"):
        scan_held_bars([OhlcBar(10.0, 10.1, 9.95, 10.05)], cost=10, peak=10, strategy=strategy)


@pytest.mark.parametrize("source,root_arg", [("qlib_1min", "qlib_root"), ("lake", "lake_root")])
@pytest.mark.parametrize("existing_root", [False, True])
@pytest.mark.parametrize("runner", [load_scan_bars, run_scan])
def test_missing_data_never_becomes_a_zero_summary(tmp_path, source, root_arg, existing_root, runner):
    root = tmp_path if existing_root else tmp_path / "missing"
    kwargs = {root_arg: root}
    if runner is run_scan:
        kwargs.update(cost=10, peak=10)
    with pytest.raises(FileNotFoundError) as error:
        runner(SYMBOL, DAY, DAY, source=source, **kwargs)
    assert SYMBOL in str(error.value)
    assert str(root) in str(error.value)


@pytest.mark.parametrize("source,root_arg", [("qlib_1min", "qlib_root"), ("lake", "lake_root")])
def test_source_requires_its_explicit_root(source, root_arg):
    with pytest.raises(ValueError, match=root_arg):
        load_scan_bars(SYMBOL, DAY, DAY, source=source)


def test_unknown_source_lists_both_allowed_sources():
    with pytest.raises(ValueError, match="qlib_1min.*lake"):
        load_scan_bars(SYMBOL, DAY, DAY, source="csv")


def _write_bin(path, ref, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(np.asarray([ref, *values], dtype="<f").tobytes())


@pytest.fixture
def qlib_root(tmp_path):
    calendar = tmp_path / "calendars" / "1min.txt"
    calendar.parent.mkdir()
    calendar.write_text(
        "2026-01-05 14:55:00\n2026-01-06 09:30:00\n2026-01-06 09:31:00\n"
        "2026-01-06 09:32:00\n2026-01-06 09:33:00\n2026-01-07 09:30:00\n",
        encoding="utf-8",
    )
    feature = tmp_path / "features" / "sz000739"
    _write_bin(feature / "close.1min.bin", 0, [999, 10.05, np.nan, np.inf, 9.75, 999])
    _write_bin(feature / "open.1min.bin", 0, [999, 10.0, 10, 10, 9.7, 999])
    _write_bin(feature / "high.1min.bin", 0, [999, 10.1, 10, 10, 9.8, 999])
    # Different feature offset; missing low is legal only on dropped-close rows.
    _write_bin(feature / "low.1min.bin", 1, [9.95, np.nan, np.nan, 9.6])
    return tmp_path


def test_qlib_low_aligns_by_kept_calendar_positions_without_preload(qlib_root):
    bars = load_scan_bars("000739_SZ", date(2026, 1, 6), date(2026, 1, 6),
                          source="qlib_1min", qlib_root=qlib_root)
    assert len(bars) == 2
    assert [bar.low for bar in bars] == pytest.approx([9.95, 9.6])
    assert [bar.close for bar in bars] == pytest.approx([10.05, 9.75])
    assert [bar.open for bar in bars] == pytest.approx([10.0, 9.7])
    assert [bar.high for bar in bars] == pytest.approx([10.1, 9.8])


@pytest.mark.parametrize("values", [None, [], [np.nan], [np.inf], [9.95]])
def test_qlib_missing_or_nonfinite_kept_low_raises(qlib_root, values):
    path = qlib_root / "features" / "sz000739" / "low.1min.bin"
    if values is None:
        path.unlink()
    else:
        _write_bin(path, 1, values)
    with pytest.raises((FileNotFoundError, ValueError), match="low"):
        load_scan_bars(SYMBOL, DAY, DAY, source="qlib_1min", qlib_root=qlib_root)


def test_qlib_absent_symbol_raises(qlib_root):
    with pytest.raises(FileNotFoundError, match="600000.SH"):
        load_scan_bars("600000.SH", DAY, DAY, source="qlib_1min", qlib_root=qlib_root)


@pytest.fixture
def lake_root(tmp_path):
    directory = tmp_path / "symbol=000739_SZ"
    directory.mkdir()
    pd.DataFrame({
        "time": [pd.Timestamp(stamp, tz="UTC").value // 1_000_000 for stamp in
                 ["2026-01-06 09:31", "2026-01-06 09:30"]],
        "open": [9.7, 10.0], "high": [9.8, 10.1],
        "low": [9.6, 9.95], "close": [9.75, 10.05],
    }).to_parquet(directory / "data.parquet", index=False)
    return tmp_path


def test_lake_walks_the_reader_index_in_time_order(lake_root):
    bars = load_scan_bars(SYMBOL, DAY, DAY, source="lake", lake_root=lake_root)
    assert bars == [OhlcBar(10.0, 10.1, 9.95, 10.05), OhlcBar(9.7, 9.8, 9.6, 9.75)]


@pytest.mark.parametrize("column", ["open", "high", "low", "close"])
def test_lake_missing_ohlc_raises(lake_root, column):
    path = lake_root / "symbol=000739_SZ" / "data.parquet"
    pd.read_parquet(path).drop(columns=column).to_parquet(path, index=False)
    with pytest.raises(FileNotFoundError) as error:
        load_scan_bars(SYMBOL, DAY, DAY, source="lake", lake_root=lake_root)
    assert SYMBOL in str(error.value)
    assert str(lake_root) in str(error.value)


def test_lake_empty_window_raises(lake_root):
    with pytest.raises(FileNotFoundError, match=SYMBOL):
        load_scan_bars(SYMBOL, "20260107", "20260107", source="lake", lake_root=lake_root)


@pytest.mark.parametrize("source,root_flag", [("qlib_1min", "--qlib-root"), ("lake", "--lake-root")])
def test_cli_missing_data_exits_nonzero(tmp_path, capsys, source, root_flag):
    assert main(["--source", source, "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 root_flag, str(tmp_path), "--cost", "10", "--peak", "10"]) != 0
    output = capsys.readouterr()
    assert output.out == ""
    assert SYMBOL in output.err
    assert str(tmp_path) in output.err


def test_cli_prints_one_summary_line(lake_root, capsys):
    assert main(["--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 "--lake-root", str(lake_root), "--cost", "10", "--peak", "10"]) == 0
    assert capsys.readouterr().out == f"symbol={SYMBOL} source=lake version1 bars=2 fills=1 skips=1\n"


def test_source_guards():
    old_source = (ROOT / "backtest/research/csv_minute_backtest.py").read_text(encoding="utf-8")
    assert "minute_bar_scan_host" not in old_source
    source = (ROOT / "backtest/research/minute_bar_scan_host.py").read_text(encoding="utf-8")
    for forbidden in ("write_minute_cache", "load_minute_ohlc", "_read_lake_minute", "MatchCore", "simulate"):
        assert forbidden not in source
    calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "invoke_minute_strategy"]
    assert [call.args[0].value for call in calls] == ["version1"]
