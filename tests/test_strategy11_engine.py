"""Data-free v11 dual-clock, EOD FSM, consumed skips and strict volume-A pins."""

import argparse

import numpy as np
import pandas as pd
import pytest

from backtest.research import ashare_bars
from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research.ashare_volume_cap import BucketVolume
from backtest.research.csv_ledger import Position
from backtest.research.csv_strategy_books import (
    FORBIDDEN_DEFAULT_STOCK_POOL,
    apply_csv_strategy,
    get_book,
    resolve_research_pool_dir,
)

CODE = "600000.SH"
T, NEXT, THIRD = "20240902", "20240903", "20240904"
OPEN = 570


def frames(closes=(10, 9.8, 10, 10), opens=(10, 10.2, 10.1, 10.2)):
    dates = pd.bdate_range("20240826", periods=8)
    close = [10.] * 4 + list(closes)
    op = [10.] * 4 + list(opens)
    daily_frame = pd.DataFrame({"open": op, "close": close,
                               "high": np.maximum(op, close), "low": np.minimum(op, close),
                               "volume": 100_000.}, index=dates)
    rows = []
    for day, row in daily_frame.iterrows():
        for hm in (570, 585, 895):
            rows.append({"time": day + pd.Timedelta(minutes=hm), "ymd": day.strftime("%Y%m%d"),
                         "hm": hm, "open": row["open"] if hm == 570 else row["close"],
                         "high": row["high"], "low": row["low"], "close": row["close"],
                         "volume": 10_000.})
    return {CODE: daily_frame}, {CODE: pd.DataFrame(rows).set_index("time")}


def run(engine, *, ds=None, ms=None, pools=None, end=THIRD,
        fix_s11_exit_domain=False, **kwargs):
    if ds is None:
        ds, ms = frames()
    args = (ds,) if engine is daily else (ms, ds)
    if fix_s11_exit_domain:
        front = {code: frame.copy() for code, frame in ds.items()}
        for frame in front.values():
            frame[["open", "high", "low", "close"]] *= .5
        kwargs.update(fix_s11_exit_domain=True, signal_bars_front=front)
    return engine.simulate(*args, {T: [CODE]} if pools is None else pools,
                           T, end, strategy="version11", daily_quota=5000,
                           total_cash=100_000, **kwargs)


def fills(state):
    return [t for t in state.trades if t["side"] in ("BUY", "SELL")]


@pytest.mark.parametrize("alias", ["11", "v11", "version11"])
def test_registration_explicit_chase_false_and_stock_pool_fence(alias, tmp_path):
    book = get_book(alias)
    assert book.tag == "v11" and not book.allow_add and book.peak_gap_min == 0
    raw = book.apply()
    assert raw["limit_up_chase"] is False  # pin BEFORE caller setdefault(True)
    assert callable(raw["take_profit"]) and callable(raw["record_params"])
    assert apply_csv_strategy(alias, stop_pct=.02)["stop_pct"] is None
    assert "version11" in FORBIDDEN_DEFAULT_STOCK_POOL
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir(alias, None, repo=tmp_path)
    with pytest.raises(SystemExit, match="stock_pool"):
        resolve_research_pool_dir(alias, tmp_path / "stock_pool", repo=tmp_path)
    assert resolve_research_pool_dir(alias, tmp_path / "pool", repo=tmp_path) == tmp_path / "pool"
    assert book.run_kwargs(argparse.Namespace(stop_pct=None)) == {"strategy": "version11"}
    with pytest.raises(SystemExit, match="not supported"):
        book.run_kwargs(argparse.Namespace(stop_pct=.02))


@pytest.mark.parametrize("engine", [daily, minute])
@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_contract_t_fill_then_entry_day_eod_then_next_open_no_reentry(engine, fix_s11_exit_domain):
    # D=Friday, T=Monday: signal pool already shifted strictly after D by exporter.
    entry = run(engine, fix_s11_exit_domain=fix_s11_exit_domain, end=T)
    assert [(t["date"], t["side"]) for t in fills(entry)] == [(T, "BUY")]
    assert fills(entry)[0]["price"] == pytest.approx(9.8 if engine is daily else 10.2)
    assert entry.positions[CODE][0].pending_exit == "ma_signal:entry_nonpositive"
    state = run(engine, fix_s11_exit_domain=fix_s11_exit_domain, pools={T: [CODE], NEXT: [CODE]})
    assert [(t["date"], t["side"]) for t in fills(state)] == [(T, "BUY"), (NEXT, "SELL")]
    assert fills(state)[1]["price"] == pytest.approx(10.1)
    assert state.stats["skip_sold_today"] == 1 and state.positions == {}
    assert state.stats["sell_ma"] == 1
    assert state.stats["chase_pending_eod"] == 0 and state.stats["limit_up_chase"] is False


@pytest.mark.parametrize("engine", [daily, minute])
@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_green_entry_above_sma_holds_through_red_then_breaks(engine, fix_s11_exit_domain):
    ds, ms = frames(closes=(10, 10.5, 10.4, 9.8))
    state = run(engine, fix_s11_exit_domain=fix_s11_exit_domain, ds=ds, ms=ms, end=NEXT)
    assert len(fills(state)) == 1
    assert state.positions[CODE][0].pending_exit == ""  # red vs T but above SMA5
    state = run(engine, fix_s11_exit_domain=fix_s11_exit_domain, ds=ds, ms=ms)
    assert len(fills(state)) == 1  # T+2 EOD can only schedule T+3
    assert state.positions[CODE][0].pending_exit == "ma_signal:SMA5"


@pytest.mark.parametrize("engine", [daily, minute])
@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_green_entry_below_sma5_schedules_exit_on_entry_day(engine, fix_s11_exit_domain):
    ds, ms = frames(closes=(9, 9.5, 10, 10), opens=(9, 9.4, 9.6, 10))
    state = run(engine, fix_s11_exit_domain=fix_s11_exit_domain, ds=ds, ms=ms, end=T)
    assert len(fills(state)) == 1
    assert state.positions[CODE][0].pending_exit == "ma_signal:SMA5"
    extended = run(engine, fix_s11_exit_domain=fix_s11_exit_domain, ds=ds, ms=ms, end=NEXT)
    assert fills(extended)[1]["date"] == NEXT


@pytest.mark.parametrize("engine", [daily, minute])
@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_limit_up_skip_consumes_signal_and_actual_chase_queue_stays_empty(engine, monkeypatch, fix_s11_exit_domain):
    original = engine.init_sim_state
    queues = []

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        queues.append(result[1])
        return result

    monkeypatch.setattr(engine, "init_sim_state", capture)
    ds, ms = frames(closes=(10, 11, 10.5, 10.6), opens=(10, 11, 10.1, 10.3))
    # T is one-price limit-up; NEXT would satisfy the old chase condition.
    state = run(engine, fix_s11_exit_domain=fix_s11_exit_domain, ds=ds, ms=ms)
    assert fills(state) == [] and state.positions == {} and queues == [{}]
    assert state.stats["skip_limit_up"] == 1
    assert state.stats["limit_up_chase"] is False
    assert state.stats["chase_buy"] == state.stats["chase_pending_eod"] == 0


@pytest.mark.parametrize("engine", [daily, minute])
@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_pending_down_limit_defers_to_next_day_open_despite_intraday_rebound(engine, fix_s11_exit_domain):
    ds, ms = frames(opens=(10, 10.2, 8.82, 10.2))  # NEXT down limit from T=9.8
    state = run(engine, fix_s11_exit_domain=fix_s11_exit_domain, ds=ds, ms=ms, end=NEXT)
    assert len(fills(state)) == 1
    assert state.positions[CODE][0].pending_exit == "ma_signal:entry_nonpositive"
    assert state.stats["defer_sell_limit_down"] == 1
    state = run(engine, fix_s11_exit_domain=fix_s11_exit_domain, ds=ds, ms=ms)
    assert [(t["date"], t["side"]) for t in fills(state)] == [(T, "BUY"), (THIRD, "SELL")]


@pytest.mark.parametrize("mode", ["missing_open", "zero_volume", "invalid_volume"])
@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_open_buy_skip_does_not_retry_later_minute_or_day(mode, fix_s11_exit_domain):
    ds, ms = frames()
    opening = (ms[CODE]["ymd"] == T) & (ms[CODE]["hm"] == OPEN)
    if mode == "missing_open":
        ms[CODE] = ms[CODE].loc[~opening]
    else:
        ms[CODE].loc[opening, "volume"] = 0 if mode == "zero_volume" else np.nan
    state = run(minute, fix_s11_exit_domain=fix_s11_exit_domain, ds=ds, ms=ms)
    assert fills(state) == [] and state.stats["chase_pending_eod"] == 0
    assert state.stats["skip_no_bar"] == 1
    assert state.stats["skip_buy_volume"] == (0 if mode == "missing_open" else 1)


@pytest.mark.parametrize("mode", ["missing_open", "zero_volume"])
@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_pending_sell_waits_for_next_open_when_no_open_or_zero_volume(mode, fix_s11_exit_domain):
    ds, ms = frames()
    opening = (ms[CODE]["ymd"] == NEXT) & (ms[CODE]["hm"] == OPEN)
    if mode == "missing_open":
        ms[CODE] = ms[CODE].loc[~opening]
    else:
        ms[CODE].loc[opening, "volume"] = 0
    state = run(minute, fix_s11_exit_domain=fix_s11_exit_domain, ds=ds, ms=ms)
    assert [(t["date"], t["side"]) for t in fills(state)] == [(T, "BUY"), (THIRD, "SELL")]
    assert state.stats["defer_sell_volume"] == (mode == "zero_volume")


@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_volume_a_unfinished_open_bucket_buy_skips_before_lookup(fix_s11_exit_domain):
    calls = []

    def lookup(*key):
        calls.append(key)
        return BucketVolume(10**9, OPEN, "raw_shares_incremental")

    state = run(minute, fix_s11_exit_domain=fix_s11_exit_domain, participation_rate=.1, volume_for_bucket=lookup)
    assert calls == []  # no borrowing completed same-minute, prior or EOD volume
    assert fills(state) == [] and state.positions == {} and state.cash == 100_000
    assert state.volume_cap.used == {}
    assert state.stats["skip_buy_volume"] == 1
    assert state.stats["skip_volume_unavailable"] == 1
    assert state.stats["chase_pending_eod"] == 0
    assert state.trades[0]["reason"] == "skip_volume_unavailable:bucket_not_completed"
    assert state.trades[0]["bucket"] == OPEN


@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_volume_a_unfinished_open_bucket_pending_sell_defers_preserves_position(monkeypatch, fix_s11_exit_domain):
    original = minute.init_sim_state
    pending_reason = "ma_signal:entry_nonpositive"

    def seed(*args, **kwargs):
        state, pending, names = original(*args, **kwargs)
        # Existing lot: T is entry_idx=0; T+1 checks must block T's open.
        state.positions[CODE] = [Position(CODE, 100, 10, 0, 10, pending_exit=pending_reason)]
        return state, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seed)

    def unavailable_lookup(*_):
        pytest.fail("unfinished opening bucket must be rejected before lookup")

    state = run(minute, fix_s11_exit_domain=fix_s11_exit_domain, pools={}, participation_rate=.1, volume_for_bucket=unavailable_lookup)
    assert fills(state) == [] and state.cash == 100_000 and state.volume_cap.used == {}
    pos = state.positions[CODE][0]
    assert pos.shares == 100 and pos.pending_exit == pending_reason
    skips = [t for t in state.trades if t["side"] == "SKIP"]
    assert [t["date"] for t in skips] == [NEXT, THIRD]  # one attempt/day, no T sell
    assert all(t["reason"] == "skip_volume_unavailable:bucket_not_completed" for t in skips)
    assert state.stats["defer_sell_volume"] == 2


@pytest.mark.parametrize("fix_s11_exit_domain", [False, True], ids=["legacy", "front"])
def test_cap_off_never_looks_up_volume_and_keeps_open_fills(fix_s11_exit_domain):
    def forbidden(*_):
        pytest.fail("cap-off does not consult capacity")

    state = run(minute, fix_s11_exit_domain=fix_s11_exit_domain, volume_for_bucket=forbidden)
    assert [t["side"] for t in fills(state)] == ["BUY", "SELL"]


def test_v11_loader_keeps_zero_open_volume_and_bypasses_old_cache(tmp_path):
    root = tmp_path / "lake"
    path = root / "symbol=600000_SH" / "data.parquet"
    path.parent.mkdir(parents=True)
    _, ms = frames()
    frame = ms[CODE].drop(columns=["ymd", "hm"]).copy()
    frame.loc[pd.Timestamp(T) + pd.Timedelta(minutes=OPEN), "volume"] = 0
    frame["time"] = frame.index.as_unit("ms").asi8
    frame.to_parquet(path, index=False)
    legacy = ashare_bars.read_lake_minute_ohlc(CODE, root, T, THIRD)
    assert "volume" not in legacy
    cache = tmp_path / "cache"
    cache.mkdir()
    ashare_bars.minute_cache_path(T, THIRD, cache).write_bytes(b"not a readable legacy cache")
    status = {}
    loaded = ashare_bars.load_minute_ohlc({CODE}, T, THIRD, lake_root=root,
                                         include_volume=True, cache_dir=cache, status=status)
    assert loaded[CODE]["volume"].iloc[0] == 0
    assert status == {"cache": "off:volume_required"}
    frame.drop(columns="volume").to_parquet(path, index=False)
    with pytest.raises(ValueError, match="volume required"):
        ashare_bars.load_minute_ohlc({CODE}, T, THIRD, lake_root=root, include_volume=True)
    with pytest.raises(FileNotFoundError):
        ashare_bars.load_minute_ohlc({"600001.SH"}, T, THIRD, lake_root=root, include_volume=True)


@pytest.mark.parametrize("engine", [daily, minute])
def test_cli_alias_help_and_default_pool_rejected(engine, capsys):
    with pytest.raises(SystemExit) as exc:
        engine.main(["--strategy", "11", "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "非已验证多头" in help_text and "volume=A" in help_text
    with pytest.raises(SystemExit, match="stock_pool"):
        engine.main(["--strategy", "11"])
