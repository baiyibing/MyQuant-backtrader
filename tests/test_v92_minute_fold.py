"""The last book-local minute loop is hosted by the shared clock/cursor."""
import pandas as pd
import pytest

from backtest.research import csv_minute_backtest as minute
from backtest.research import strategy9_2_engine as engine
from backtest.research import strategy9_2_rules as rules
from backtest.research.csv_ledger import execute_buy
from backtest.research.csv_strategy_books import BOOKS, apply_csv_strategy
from backtest.research.fill_config import FillConfig, book_fill_defaults
from backtest.research.minute_held_scan_core import HeldMinuteCursor
from tests.test_strategy9_2_book import fixture_bars

CODE = "600000.SH"


def run_seeded(monkeypatch, paths, *, units=1, anchor=-1, previous_close=9., **kwargs):
    days, daily = fixture_bars(len(paths) + 1)
    daily.loc[days[0], "close"] = previous_close  # Opening stop is tradable above the 8.10 floor.
    original = minute.init_sim_state

    def seeded(*args, **kw):
        st, pending, names = original(*args, **kw)
        execute_buy(st, CODE, 10., 10000., -1, days[0], reason="pool")
        mem = engine.memory_for(st, CODE)
        mem.units, mem.anchor_idx = units, anchor
        return st, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seeded)
    rows = []
    for day, path in zip(days[1:], paths):
        for hm, opening, high, low, closing in path:
            rows.append(dict(time=day + pd.Timedelta(minutes=hm), ymd=day.strftime("%Y%m%d"),
                             hm=hm, open=opening, high=high, low=low, close=closing, volume=10000.))
    minutes = pd.DataFrame(rows).set_index("time")
    return minute.simulate({CODE: minutes}, {CODE: daily}, {},
                           days[1].strftime("%Y%m%d"), days[-1].strftime("%Y%m%d"),
                           strategy="version9_2", name_budget=10000., **kwargs)


def sells(st):
    return [t for t in st.trades if t["side"] == "SELL"]


def test_no_book_retains_separate_minute_hook():
    for book in BOOKS:
        assert "run_minute_day" not in apply_csv_strategy(book, scores_by_day={"20260303": {CODE: 1.}}, topk=1, n_drop=1, eligible_buy=lambda *_: True)
    assert not hasattr(engine, "run_minute_day")
    hooks = apply_csv_strategy("version9_2")
    assert hooks["run_daily_day"] is engine.run_daily_day
    assert hooks["minute_session"] is engine.MinuteSession
    assert book_fill_defaults(hooks)["stop"] == FillConfig()


@pytest.mark.parametrize("chronological", [False, True])
@pytest.mark.parametrize("row,price,reason", [
    ((600, 8.8, 8.9, 8.7, 8.85), 8.8, "stop_loss:gap_open"),
    ((600, 9.5, 9.6, 8.7, 8.8), 8.8, "stop_loss:touch"),
])
def test_default_chosen_stop(monkeypatch, chronological, row, price, reason):
    st = run_seeded(monkeypatch, [[row]], fix_minute_cash_order=chronological)
    assert [(t["price"], t["reason"], t["shares"]) for t in sells(st)] == [(price, reason, 1000)]


def test_limit_down_retries_next_day_not_next_bar(monkeypatch):
    st = run_seeded(monkeypatch, [[(600, 8.1, 8.1, 8.1, 8.1), (601, 8.8, 8.8, 8.8, 8.8)],
                                 [(600, 9.5, 9.5, 9.5, 9.5)]])
    assert [(t["date"], t["price"], t["reason"]) for t in sells(st)] == [
        ("20260304", 9.5, "stop_loss:gap_open")]
    assert st.stats["limit_down_pending"] == 1


@pytest.mark.parametrize("units,anchor,row,reason,shares", [
    (3, -1, (600, 13., 13., 13., 13.), "profit_take:band:1", 300),
    (1, -20, (600, 10., 10.3, 10., 10.), "force_sell:hold_days_20", 1000),
    (3, -1, (600, 11., 12., 11., 11.), "trail:profit_drawdown", 1000),
])
def test_default_plans(monkeypatch, units, anchor, row, reason, shares):
    st = run_seeded(monkeypatch, [[row]], units=units, anchor=anchor)
    assert [(t["reason"], t["shares"], t["price"]) for t in sells(st)] == [(reason, shares, row[-1])]


def test_adds_use_line_and_follow_successful_units(monkeypatch):
    st = run_seeded(monkeypatch, [[(600, 10., 10.5, 10., 10.5), (601, 10.6, 11., 10.6, 11.)]], previous_close=10.5)
    assert [t["price"] for t in st.trades if t["side"] == "BUY"] == [10., 10.4, 11.]
    assert engine.memory_for(st, CODE).units == 3


@pytest.mark.parametrize("config,price", [
    (FillConfig(), 8.8), (FillConfig(fill_at="line"), 9.),
    (FillConfig(fill_at=9.2), 9.2),
    (FillConfig(fill_timing="next_bar_open"), 9.5),
    (FillConfig(trigger_basis="bar_low", fill_at="line"), 9.),
])
def test_custom_fill_config_reaches_cursor(monkeypatch, config, price):
    seen = []
    advance = HeldMinuteCursor.advance

    def observed(self, idx, phase):
        if self.phase_exit:
            seen.append(self.fill_config)
        return advance(self, idx, phase)

    monkeypatch.setattr(HeldMinuteCursor, "advance", observed)
    st = run_seeded(monkeypatch, [[(600, 9.5, 9.6, 8.7, 8.8), (601, 9.5, 9.5, 9.5, 9.5)]],
                    fill_config=config)
    assert config in seen
    assert sells(st)[0]["price"] == price


@pytest.mark.parametrize("config,message", [
    (FillConfig(fill_at="line"), "explicit stop/target line"),
    (FillConfig(trigger_basis="bar_low", fill_at="bar_low"), "look-ahead"),
])
def test_plan_without_explicit_line_rejects_invalid_fill(monkeypatch, config, message):
    with pytest.raises(ValueError, match=message):
        run_seeded(monkeypatch, [[(600, 13., 13., 13., 13.)]], units=3, fill_config=config)


def test_next_open_survives_session_boundary(monkeypatch):
    st = run_seeded(monkeypatch, [[(895, 9.5, 9.6, 8.7, 8.8)], [(570, 9.5, 9.5, 9.5, 9.5)]],
                    fill_config=FillConfig(fill_timing="next_bar_open"))
    assert [(t["date"], t["price"]) for t in sells(st)] == [("20260304", 9.5)]


def test_pool_max_available_clock_and_add_before_exit(monkeypatch):
    from tests.test_strategy9_2_book import test_strategy9_2_minute_same_day_and_t1_residual
    seen = []
    original = engine.MinuteSession.after_close

    def observed(self, hm):
        st = self.context["st"]
        start = len(st.trades)
        original(self, hm)
        seen.extend((hm, t["reason"]) for t in st.trades[start:] if t["side"] == "BUY")

    monkeypatch.setattr(engine.MinuteSession, "after_close", observed)
    test_strategy9_2_minute_same_day_and_t1_residual(False)
    assert seen == [(895, "pool")]


def test_external_retired_hook_fails_clearly(monkeypatch):
    original = minute.prepare_strategy_hooks

    def external(*args, **kwargs):
        hooks = original(*args, **kwargs)
        hooks["run_minute_day"] = lambda *a, **k: None
        return hooks

    monkeypatch.setattr(minute, "prepare_strategy_hooks", external)
    from tests.test_minute_fill_config import minute_fixture
    with pytest.raises(ValueError, match="run_minute_day is retired"):
        minute.simulate(**minute_fixture(), strategy="version9_2")


@pytest.mark.parametrize("config,expected", [(None, []),
    (FillConfig(trigger_basis="bar_low", fill_at="line"), [9.])])
def test_low_only_stop_is_opt_in(monkeypatch, config, expected):
    st = run_seeded(monkeypatch, [[(600, 9.5, 9.6, 8.7, 9.5)]], fill_config=config)
    assert [t["price"] for t in sells(st)] == expected


def test_next_open_completed_volume_gate(monkeypatch):
    from backtest.research.ashare_volume_cap import BucketVolume
    lookup = {(CODE, "20260303", hm): BucketVolume(10000, hm, "raw_shares_incremental")
              for hm in (600, 601)}
    st = run_seeded(monkeypatch, [[(600, 9.5, 9.6, 8.7, 8.8), (601, 9.5, 9.5, 9.5, 9.5)]],
                    fill_config=FillConfig(fill_timing="next_bar_open"),
                    participation_rate=1., volume_for_bucket=lookup)
    assert not sells(st)
    assert any(t["reason"] == "skip_volume_unavailable:bucket_not_completed" for t in st.trades)
    assert st.book_state["turtle_pending"][CODE] == ("stop_loss:touch", 1000)


@pytest.mark.parametrize("config,price", [
    (FillConfig(fill_at=13.2), 13.2),
    (FillConfig(fill_timing="next_bar_open"), 13.5),
])
def test_custom_scale_plan_keeps_dispatched_band_and_quantity(monkeypatch, config, price):
    st = run_seeded(monkeypatch, [[(600, 13., 13., 13., 13.), (601, 13.5, 13.5, 13.5, 13.5)]],
                    units=3, fill_config=config)
    assert [(t["reason"], t["shares"], t["price"]) for t in sells(st)] == [
        ("profit_take:band:1", 300, price)]
    assert engine.memory_for(st, CODE).sell_band_seq == 1
    assert sum(p.shares for p in st.positions[CODE]) == 700


def test_pool_fallback_uses_last_available_bar(monkeypatch):
    from tests.test_minute_fill_config import minute_fixture
    fixture = minute_fixture()
    frame = fixture["minute_bars"][CODE]
    frame["hm"] = 890
    seen = []
    original = engine.MinuteSession.after_close

    def observed(self, hm):
        before = len(self.context["st"].trades)
        original(self, hm)
        seen.extend(hm for t in self.context["st"].trades[before:] if t["side"] == "BUY")

    monkeypatch.setattr(engine.MinuteSession, "after_close", observed)
    minute.simulate(**fixture, strategy="version9_2")
    assert seen[0] == 890
