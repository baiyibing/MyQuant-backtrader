"""Read-only minute loaders and CLI routes; only synthetic data."""
import ast
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from backtest.research import minute_bar_scan_host as host
from backtest.research.minute_bar_scan_host import OhlcBar, load_scan_bars, main
ROOT = Path(__file__).resolve().parents[1]
SYMBOL = "000739.SZ"
DAY = "20260106"
OTHER = "600000.SH"
UNIVERSE_BOOKS = ("topk_dropout", "topk_score_exit")


@pytest.mark.parametrize("source,root_arg", [("qlib_1min", "qlib_root"), ("lake", "lake_root")])
@pytest.mark.parametrize("existing_root", [False, True])
def test_missing_data_never_becomes_a_zero_summary(tmp_path, source, root_arg, existing_root):
    root = tmp_path if existing_root else tmp_path / "missing"
    kwargs = {root_arg: root}
    with pytest.raises(FileNotFoundError) as error:
        load_scan_bars(SYMBOL, DAY, DAY, source=source, **kwargs)
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



@pytest.mark.parametrize("source,root_arg", [("qlib_1min", "qlib_root"), ("lake", "lake_root")])
def test_loader_keeps_source_dates_aligned_with_bars(request, source, root_arg):
    dates = []
    bars = load_scan_bars(SYMBOL, DAY, DAY, source=source,
                          **{root_arg: request.getfixturevalue(root_arg)}, bar_dates=dates)
    assert dates == [date(2026, 1, 6)] * len(bars)
    assert len(bars) == 2



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
def test_cli_missing_data_exits_nonzero(tmp_path, capsys, source, root_flag, monkeypatch):
    monkeypatch.setattr(host, "load_pool_day_map", lambda *a, **k: {})
    assert main(["--source", source, "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 root_flag, str(tmp_path)]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert SYMBOL in output.err and str(tmp_path) in output.err



def test_cli_prints_one_summary_line(lake_root, capsys):
    assert main(["--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 "--strategy", "version1", "--cost", "10", "--peak", "10"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "flat pool start" in output.err and "partial held seed" in output.err



def _lake_cli_args(lake_root):
    return ["--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
            "--lake-root", str(lake_root)]



def test_cli_can_select_version2(lake_root, capsys):
    assert main(["--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 "--strategy", "version2", "--cost", "10", "--peak", "10"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "flat pool start" in output.err and "partial held seed" in output.err



@pytest.fixture
def scores_dir(tmp_path):
    directory = tmp_path / "scores"
    directory.mkdir()
    pd.DataFrame({"code": [SYMBOL, OTHER], "score": [-1, 2]}).to_csv(
        directory / f"{DAY}.csv", index=False,
    )
    return directory



def _universe_cli_args(strategy, scores_dir):
    return ["--strategy", strategy, "--scores-dir", str(scores_dir),
            "--topk", "1", "--n-drop", "1"]



@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
def test_cli_universe_uses_full_scores_dir(lake_root, scores_dir, capsys, strategy, monkeypatch):
    calls = []
    def runner(*a, **kw):
        calls.append(kw)
        return host.RoundTripSummary(2, 1, 1, 0, 100000, 0)
    monkeypatch.setattr(host, "run_simulate", runner)
    assert main(_lake_cli_args(lake_root) + _universe_cli_args(strategy, scores_dir)) == 0
    assert calls[0]["scores_by_day"] == {DAY: {SYMBOL: -1., OTHER: 2.}}
    assert (calls[0]["topk"], calls[0]["n_drop"], calls[0]["strategy"]) == (1, 1, strategy)
    assert len(capsys.readouterr().out.splitlines()) == 1



@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
def test_cli_propagates_simulate_error_without_summary(lake_root, scores_dir, capsys, strategy, monkeypatch):
    pd.DataFrame({"code": [SYMBOL], "score": [-1]}).to_csv(scores_dir / f"{DAY}.csv", index=False)
    calls = []
    def runner(*a, **kw):
        calls.append(kw)
        raise ValueError("engine rejected score universe")
    monkeypatch.setattr(host, "run_simulate", runner)
    assert main(_lake_cli_args(lake_root) + _universe_cli_args(strategy, scores_dir)) == 1
    assert calls[0]["scores_by_day"] == {DAY: {SYMBOL: -1.}}
    output = capsys.readouterr()
    assert not output.out and "engine rejected score universe" in output.err



@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
def test_cli_pred_csv_keeps_loader_buy_day_keys(lake_root, tmp_path, capsys, strategy, monkeypatch):
    pred = tmp_path / "pred.csv"
    pd.DataFrame({"date": ["2026-01-05"] * 2 + ["2026-01-06"] * 2,
                  "code": [SYMBOL, OTHER] * 2, "score": [-1, 2, 2, -1]}).to_csv(pred, index=False)
    calls = []
    def runner(*a, **kw):
        calls.append(kw)
        return host.RoundTripSummary(2, 0, 0, 0, 100000, 0)
    monkeypatch.setattr(host, "run_simulate", runner)
    assert main(_lake_cli_args(lake_root) + ["--strategy", strategy, "--pred-csv", str(pred),
                                             "--topk", "1", "--n-drop", "1"]) == 0
    assert calls[0]["scores_by_day"] == {"20260106": {SYMBOL: -1., OTHER: 2.}}
    assert len(capsys.readouterr().out.splitlines()) == 1



@pytest.mark.parametrize("strategy", UNIVERSE_BOOKS)
@pytest.mark.parametrize("use_both", [False, True])
def test_cli_requires_exactly_one_score_source(lake_root, scores_dir, capsys, strategy, use_both):
    flags = ["--strategy", strategy, "--topk", "1", "--n-drop", "1"]
    if use_both:
        flags += ["--scores-dir", str(scores_dir), "--pred-csv", str(scores_dir / f"{DAY}.csv")]
    assert main(_lake_cli_args(lake_root) + flags) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "--pred-csv" in output.err and "--scores-dir" in output.err



def test_cli_unknown_strategy_exits_one(lake_root, capsys):
    assert main(_lake_cli_args(lake_root) + ["--strategy", "unknown"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid choice" in output.err



def test_cli_strategy_choices_are_registered_books_plus_explicit_v7(lake_root, capsys):
    assert main(_lake_cli_args(lake_root) + ["--strategy", "unknown"]) == 1
    error = capsys.readouterr().err
    choices = error.split("(choose from ", 1)[1].split(")", 1)[0]
    assert tuple(choice.strip("'\"") for choice in choices.split(", ")) == (
        *host.csv_strategy_names(), "version7", "topk_app_dropout")



def test_source_guards():
    old_source = (ROOT / "backtest/research/csv_minute_backtest.py").read_text(encoding="utf-8")
    assert "minute_bar_scan_host" not in old_source
    source = (ROOT / "backtest/research/minute_bar_scan_host.py").read_text(encoding="utf-8")
    for forbidden in ("write_minute_cache", "load_minute_ohlc", "_read_lake_minute", "MatchCore"):
        assert forbidden not in source
    for flag in ("dropout_sell", "sx0_sell"):
        assert f"{flag}=True" not in source.replace(" ", "")



@pytest.mark.parametrize("source", ["lake", "qlib_1min"])
@pytest.mark.parametrize("membership", ["000739", "600000", ""])
def test_simulate_cli_buys_only_pool_member(tmp_path, capsys, monkeypatch, source, membership):
    monkeypatch.setattr(host, "load_daily_ohlc", lambda *a, **k: {SYMBOL: pd.DataFrame(
        {name: [10., 9.75] for name in host.OHLC},
        index=pd.to_datetime(["20260105", DAY]))})
    pool = tmp_path / "pool"
    pool.mkdir()
    (pool / f"{DAY}.csv").write_text(membership + "\n", encoding="utf-8")
    root = tmp_path / "bars"
    root.mkdir()
    stamps = ["2026-01-06 14:54", "2026-01-06 14:55", "2026-01-06 14:56"]
    values = {"open": [10, 10, 9.7], "high": [12, 10, 9.8],
              "low": [9, 10, 9.6], "close": [10, 10, 9.75]}
    if source == "lake":
        directory = root / "symbol=000739_SZ"
        directory.mkdir()
        pd.DataFrame(dict(time=[pd.Timestamp(stamp, tz="UTC").value // 1_000_000
                                for stamp in stamps], **values)).to_parquet(
            directory / "data.parquet", index=False)
        root_flag = "--lake-root"
    else:
        calendar = root / "calendars"
        calendar.mkdir()
        (calendar / "1min.txt").write_text("\n".join(stamps) + "\n", encoding="utf-8")
        for name, prices in values.items():
            _write_bin(root / "features" / "sz000739" / f"{name}.1min.bin", 0, prices)
        root_flag = "--qlib-root"
    assert main(["--source", source, "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 root_flag, str(root), "--pool-dir", str(pool), "--cash", "2000",
                 "--daily-quota", "1001"]) == 0
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1
    if membership == "000739":
        assert "bars=3 buys=1 sells=0 skips=0 equity=1974.00" in output
        assert float(output.split("return_pct=")[1]) == pytest.approx(-1.3, abs=0.000002)
    else:
        assert "buys=0 sells=0 skips=0 equity=2000.00 return_pct=0.000000" in output



def test_qlib_reads_calendar_and_each_bin_once(qlib_root, monkeypatch):
    import backtest.research.minute_bar_scan_host as host
    calendar_calls = []
    bin_calls = []
    calendar_reader, bin_reader = host.load_qlib_1min_calendar, host.read_qlib_bin
    def calendar(root):
        calendar_calls.append(root)
        return calendar_reader(root)
    def feature(path, i0, i1):
        bin_calls.append((path.name, i0, i1))
        return bin_reader(path, i0, i1)
    monkeypatch.setattr(host, "load_qlib_1min_calendar", calendar)
    monkeypatch.setattr(host, "read_qlib_bin", feature)
    load_scan_bars(SYMBOL, DAY, DAY, source="qlib_1min", qlib_root=qlib_root)
    assert calendar_calls == [qlib_root]
    assert bin_calls == [(f"{name}.1min.bin", 1, 4) for name in host.OHLC]



@pytest.mark.parametrize("name", ["open", "high", "close"])
@pytest.mark.parametrize("values", [None, [], [np.nan], [np.inf]])
def test_qlib_required_bins_fail_closed(qlib_root, name, values):
    path = qlib_root / "features" / "sz000739" / f"{name}.1min.bin"
    if values is None:
        path.unlink()
    else:
        _write_bin(path, 1, values)
    with pytest.raises((FileNotFoundError, ValueError)):
        load_scan_bars(SYMBOL, DAY, DAY, source="qlib_1min", qlib_root=qlib_root)



def test_qlib_empty_window_raises(qlib_root):
    with pytest.raises(FileNotFoundError, match="window"):
        load_scan_bars(SYMBOL, "20270101", "20270101", source="qlib_1min", qlib_root=qlib_root)



def test_qlib_kept_close_alignment_matches_public_reader(qlib_root):
    from backtest.research.qlib_bin_1min import load_qlib_bin_1min_bars
    frame = load_qlib_bin_1min_bars([SYMBOL], date(2026, 1, 6), date(2026, 1, 6),
                                    qlib_root=qlib_root, workers=1, preload_days=0)[SYMBOL]
    dates, frames = [], []
    bars = load_scan_bars(SYMBOL, DAY, DAY, source="qlib_1min", qlib_root=qlib_root,
                          bar_dates=dates, source_frames=frames)
    assert dates == list(frame["date"])
    pd.testing.assert_frame_equal(frames[0][["date", "hm"]], frame[["date", "hm"]])
    for name in ("open", "high", "close"):
        np.testing.assert_array_equal([getattr(bar, name) for bar in bars], frame[name])



def test_lake_window_matches_public_reader_normalization(tmp_path, monkeypatch):
    import pyarrow.parquet as pq
    from backtest.research.ashare_bars import load_minute_from_lake
    from backtest.research.market_layer import utc_ms_range

    folder = tmp_path / "symbol=000739_SZ"
    folder.mkdir()
    stamps = ["2026-01-05 09:30", "2026-01-06 09:31", "2026-01-06 09:30",
              "2026-01-06 12:00", "2026-01-06 09:31", "2026-01-07 09:30",
              "2026-01-08 09:30", "2026-01-09 09:30"]
    prices = np.arange(len(stamps), dtype=float) + 10
    pd.DataFrame({
        # pandas 3 stores this UTC index at microsecond resolution; convert
        # explicitly to the millisecond unit consumed by the lake reader.
        "time": pd.to_datetime(stamps, utc=True).to_numpy(dtype="datetime64[ms]").astype("int64"),
        **{name: prices for name in host.OHLC},
        "volume": [100, 999, 100, 100, 100, 0, 100, 100],
    }).to_parquet(folder / "data.parquet", index=False, row_group_size=2)
    expected = load_minute_from_lake([SYMBOL], DAY, "20260108", workers=1,
                                     lake_root=tmp_path)[SYMBOL]
    original = pq.read_table
    calls = []

    def read_table(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(pq, "read_table", read_table)
    dates, frames = [], []
    bars = load_scan_bars(SYMBOL, DAY, "20260108", source="lake", lake_root=tmp_path,
                          bar_dates=dates, source_frames=frames)
    assert bars == [OhlcBar(*row) for row in expected[list(host.OHLC)].itertuples(index=False, name=None)]
    assert [bar.close for bar in bars] == [12, 14, 16]
    assert dates == list(expected.index.date)
    assert dates == [date(2026, 1, 6), date(2026, 1, 6), date(2026, 1, 8)]
    assert frames[0]["hm"].tolist() == expected["hm"].tolist()
    t0, t1 = utc_ms_range(DAY, "20260108")
    assert len(calls) == 1
    assert calls[0]["filters"] == [("time", ">=", t0), ("time", "<=", t1)]



@pytest.mark.parametrize("strategy", ["version1", "version2", "version3", "version4", "version5", "version6"])
@pytest.mark.parametrize("flag", ["--cost", "--peak"])
def test_cli_partial_held_flags_keep_error(capsys, strategy, flag):
    assert main(["--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 "--strategy", strategy, flag, "10"]) == 1
    assert "partial held seed" in capsys.readouterr().err



def test_version5_both_held_flags_fail_closed(monkeypatch, capsys):
    assert main(["--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 "--strategy", "version5", "--cost", "10", "--peak", "10"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "flat pool start" in output.err and "partial held seed" in output.err



def test_version6_both_held_flags_fail_closed(capsys):
    assert main([
        "--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
        "--strategy", "version6", "--cost", "10", "--peak", "10",
    ]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "flat pool start" in output.err and "partial held seed" in output.err



@pytest.fixture
def version4_adjustments(monkeypatch, tmp_path):
    # Configure before import: adj_factor binds its daily directories at import.
    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(tmp_path))
    from oskh_data import adj_factor

    def install(frame):
        calls = []
        def build(symbol):
            calls.append(symbol)
            return frame.copy()
        monkeypatch.setattr(adj_factor, "build_for_symbol", build)
        return calls

    days = pd.date_range("2026-01-01", periods=13)
    install(pd.DataFrame(dict(date=days, stock_code=SYMBOL, close_front=10.0,
                              close_none=10.0, cumulative_adj_factor=1.0)))
    return adj_factor, install



def _version4_history_frame(history=10, buy_px=10):
    days = list(pd.date_range("2026-01-01", periods=history + 3).date)
    # Minute history is deliberately different from the factor frame history.
    rows = [(day, hm, px, px, px, px)
            for day in days[:history] for hm, px in [(570, 50), (900, 10)]]
    rows += [(days[history], 895, buy_px, buy_px, buy_px, buy_px),
             (days[history], 896, 9, 12, 8, 9),
             (days[history + 1], 570, 9, 9, 8, 9),
             (days[history + 2], 570, 8, 8, 8, 8)]
    return pd.DataFrame(rows, columns=["date", "hm", *host.OHLC]), days[history]



def test_version4_both_held_flags_fail_closed(monkeypatch, capsys):
    assert main(["--source", "lake", "--symbol", SYMBOL, "--start", DAY, "--end", DAY,
                 "--strategy", "version4", "--cost", "10", "--peak", "10"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "flat pool start" in output.err and "partial held seed" in output.err



@pytest.mark.parametrize("missing", [False, True])
def test_version4_qlib_simulate_daily_source(monkeypatch, capsys, tmp_path, missing, version4_adjustments):
    frame, buy_day = _version4_history_frame()
    def load_minute(symbol, start, end, *, source_frames, **kwargs):
        assert kwargs == {"source": "qlib_1min", "qlib_root": tmp_path, "lake_root": None}
        source_frames.append(frame[frame.date >= buy_day])
    monkeypatch.setattr(host, "load_scan_bars", load_minute)
    monkeypatch.setattr(host, "load_pool_day_map", lambda *a, **k: {buy_day: [SYMBOL]})
    calls = []
    def load_daily(codes, start, end, **kwargs):
        calls.append((codes, start, end, kwargs))
        return {} if missing else {SYMBOL: pd.DataFrame(
            {name: [10] * 13 for name in host.OHLC},
            index=pd.date_range("2026-01-01", periods=13))}
    monkeypatch.setattr(host, "load_daily_ohlc", load_daily)
    assert main(["--source", "qlib_1min", "--qlib-root", str(tmp_path),
                 "--symbol", SYMBOL, "--start", "20260111", "--end", "20260113",
                 "--strategy", "version4", "--cash", "2000", "--daily-quota", "1001"]) == int(missing)
    assert calls == [([SYMBOL], "20251220", "20260113",
                      {"source": "qlib_day", "qlib_root": tmp_path})]
    if missing:
        assert "daily OHLC missing" in capsys.readouterr().err
