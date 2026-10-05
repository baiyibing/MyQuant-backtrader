"""The host delegates registered books to the complete minute loop."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from backtest.research import minute_bar_scan_host as host
from backtest.research.csv_strategy_books import csv_strategy_names

CODE = "600000.SH"


@pytest.fixture
def inputs(monkeypatch):
    days = pd.to_datetime(["2026-01-05", "2026-01-06"])
    minute = pd.DataFrame(dict(date=days.date, hm=[895, 895],
                               open=[10., 10.5], high=[10., 10.5],
                               low=[10., 10.5], close=[10., 10.5]))
    daily = pd.DataFrame({k: [10., 10., 10.5] for k in host.OHLC},
                         index=pd.to_datetime(["2026-01-02", *days]))
    def load(*a, source_frames, **kw):
        source_frames.append(minute.copy())
    monkeypatch.setattr(host, "load_scan_bars", load)
    monkeypatch.setattr(host, "load_daily_ohlc", lambda *a, **k: {CODE: daily})
    monkeypatch.setattr(host, "load_pool_day_map", lambda *a, **k: {days[0].date(): [CODE]})
    monkeypatch.setattr(host, "invoke_minute_strategy", lambda *a, **k: pytest.fail("partial host called"))
    return minute, daily


@pytest.mark.parametrize("book", csv_strategy_names())
def test_every_registered_book_calls_simulate(monkeypatch, inputs, book):
    calls = []
    scores = {"20260105": {CODE: 1}}
    def simulate(minute, daily, pool, start, end, **kw):
        calls.append(kw)
        assert pool == {"20260105": [CODE]}
        assert (start, end) == ("20260105", "20260106")
        assert set((*host.OHLC, "ymd", "hm")) <= set(minute[CODE])
        assert minute[CODE].ymd.tolist() == ["20260105", "20260106"]
        assert isinstance(daily[CODE].index, pd.DatetimeIndex)
        return SimpleNamespace(trades=[{"side": "BUY"}, {"side": "SELL"},
                                       {"side": "EOD_MARK"}], equity_curve=[("20260106", 1234)], cash=1)
    monkeypatch.setattr(host.csv_minute_backtest, "simulate", simulate)
    result = host.run_simulate(CODE, "20260105", "20260106", pool_dir=Path("unused"),
                               source="lake", cash=2000, daily_quota=1001,
                               strategy=book, scores_by_day=scores, topk=1, n_drop=1)
    assert calls == [dict(strategy=book, total_cash=2000, daily_quota=1001,
                          scores_by_day=scores, topk=1, n_drop=1)]
    assert (result.buys, result.sells, result.equity) == (1, 1, 1234)


@pytest.mark.parametrize("book", csv_strategy_names())
def test_main_uses_simulate_entry(monkeypatch, capsys, book):
    calls = []
    monkeypatch.setattr(host, "load_scores_from_args", lambda **k: {"20260105": {CODE: 1}})
    def runner(*a, **kw):
        calls.append(kw)
        return host.RoundTripSummary(2, 1, 1, 0, 2001, .05)
    monkeypatch.setattr(host, "run_simulate", runner)
    for name in ("run_scan", "run_round_trip", "invoke_minute_strategy"):
        monkeypatch.setattr(host, name, lambda *a, **k: pytest.fail("partial route called"))
    assert host.main(["--source", "lake", "--symbol", CODE, "--start", "20260105",
                      "--end", "20260106", "--strategy", book]) == 0
    assert calls[0]["strategy"] == book
    assert capsys.readouterr().out.count("\n") == 1


@pytest.mark.parametrize("book", csv_strategy_names())
def test_main_rejects_held_seed(monkeypatch, capsys, book):
    monkeypatch.setattr(host, "run_scan", lambda *a, **k: pytest.fail("held route called"))
    assert host.main(["--source", "lake", "--symbol", CODE, "--start", "20260105",
                      "--end", "20260106", "--strategy", book, "--cost", "10", "--peak", "12"]) == 1
    output = capsys.readouterr()
    assert not output.out
    assert "flat pool start" in output.err and "partial held seed" in output.err


def test_real_simulate_summary_matches_engine_trades(monkeypatch, inputs, capsys):
    minute, daily = inputs
    real = host.csv_minute_backtest.simulate
    # Real loop baseline, followed by real loop through the host CLI.
    frame = minute.assign(ymd=["20260105", "20260106"])
    st = real({CODE: frame}, {CODE: daily}, {"20260105": [CODE]},
              "20260105", "20260106", strategy="version5", total_cash=2000,
              daily_quota=1001)
    buys = sum(t["side"] == "BUY" for t in st.trades)
    sells = sum(t["side"] == "SELL" for t in st.trades)
    assert (buys, sells) == (1, 1)
    capsys.readouterr()
    assert host.main(["--source", "lake", "--symbol", CODE, "--start", "20260105",
                      "--end", "20260106", "--strategy", "version5", "--cash", "2000",
                      "--daily-quota", "1001"]) == 0
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1
    assert f"buys={buys} sells={sells}" in output
    assert f"equity={st.equity_curve[-1][1]:.2f}" in output


@pytest.mark.parametrize("book", ["version1", "topk_dropout", "topk_score_exit"])
def test_adapter_preserves_pool_and_loads_universe(monkeypatch, inputs, book):
    minute, daily = inputs
    other = "600001.SH"
    score_only = "600002.SH"
    loaded = []
    def load(code, *a, source_frames, **kw):
        loaded.append(code)
        source_frames.append(minute.copy())
    monkeypatch.setattr(host, "load_scan_bars", load)
    monkeypatch.setattr(host, "load_daily_ohlc", lambda codes, *a, **k: {c: daily for c in codes})
    monkeypatch.setattr(host, "load_pool_day_map", lambda *a, **k: {date(2026, 1, 5): [CODE, other]})
    def simulate(minutes, days, pool, *a, **kw):
        assert pool == {"20260105": [CODE, other]}
        expected = {CODE} if book == "version1" else {CODE, other, score_only}
        assert set(minutes) == set(days) == expected
        return SimpleNamespace(trades=[], equity_curve=[("20260106", 2000)], cash=2000)
    monkeypatch.setattr(host.csv_minute_backtest, "simulate", simulate)
    host.run_simulate(CODE, "20260105", "20260106", pool_dir=Path("unused"),
                      source="lake", cash=2000, strategy=book,
                      scores_by_day={"20260105": {score_only: 1}}, topk=1, n_drop=1)
    assert set(loaded) == ({CODE} if book == "version1" else {CODE, other, score_only})


@pytest.mark.parametrize("book", ["version4", "version11", "version12"])
def test_adapter_uses_existing_daily_history_loader(monkeypatch, inputs, book):
    _, daily = inputs
    calls = []
    def load(codes, start, end, **kw):
        calls.append((codes, start, end, kw))
        return {CODE: daily}
    monkeypatch.setattr(host, "load_daily_ohlc", load)
    monkeypatch.setattr(host.csv_minute_backtest, "simulate", lambda *a, **k: SimpleNamespace(
        trades=[], equity_curve=[("20260106", 2000)], cash=2000))
    host.run_simulate(CODE, "20260105", "20260106", pool_dir=Path("unused"),
                      source="lake", strategy=book, cash=2000)
    expected_start = (host.warmup_start("20260105", host.STRATEGY4_CALENDAR_SLACK_DAYS)
                      if book in ("version4", "version12") else host.warmup_start("20260105"))
    assert calls == [([CODE], expected_start, "20260106",
                      {"source": "lake", **({"dividend_type": "front"} if book == "version12" else {})})]


def test_lake_adapter_preserves_minute_volume_for_engine(tmp_path):
    path = tmp_path / "symbol=600000_SH" / "data.parquet"
    path.parent.mkdir()
    pd.DataFrame(dict(time=[pd.Timestamp("2026-01-05 14:55", tz="UTC").value // 1_000_000],
                      open=[10.], high=[10.], low=[10.], close=[10.], volume=[12345.])).to_parquet(path)
    frames = []
    host.load_scan_bars(CODE, "20260105", "20260105", source="lake",
                        lake_root=tmp_path, source_frames=frames)
    assert frames[0].volume.tolist() == [12345.]
