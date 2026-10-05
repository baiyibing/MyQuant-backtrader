"""Version12 callbacks share the main clock and held cursor."""
import pytest

from backtest.research import csv_minute_backtest as minute
from backtest.research import strategy12_engine as engine
from backtest.research import strategy12_rules as rules
from backtest.research.csv_ledger import Position
from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.fill_config import FillConfig, book_fill_defaults
from backtest.research.minute_held_scan_core import HeldMinuteCursor
from tests.test_strategy12_engine import CODE, bars_for, fills


def run(paths, **kwargs):
    mins, days, dates = bars_for(paths)
    mins[CODE]["low"] = mins[CODE]["close"]
    return minute.simulate(mins, days, {"20251103": [CODE]},
                           "20251103", dates[-1].strftime("%Y%m%d"),
                           strategy="12", name_budget=10000, **kwargs)


def test_no_separate_minute_engine():
    hooks = apply_csv_strategy("version12")
    assert hooks.get("run_minute_day") is None
    assert not hasattr(engine, "run_minute_day")
    assert hooks["run_daily_day"] is engine.run_daily_day
    assert book_fill_defaults(hooks)["stop"] == FillConfig()


@pytest.mark.parametrize("chronological", [False, True])
def test_default_limit_down_retries(chronological):
    st = run([[(895, 10)], [(600, 8), (601, 8.9), (895, 8.9), (900, 8.9)]],
             fix_minute_cash_order=chronological)
    assert fills(st) == [("pool", 1000), (rules.STOP, 1000)]
    sale = next(t for t in st.trades if t["side"] == "SELL")
    assert sale["price"] == 8.9


@pytest.mark.parametrize("chronological", [False, True])
@pytest.mark.parametrize("config,price", [(FillConfig(), 8.9), (FillConfig(fill_at=9.1), 9.1),
                                         (FillConfig(fill_timing="next_bar_open"), 9.5)])
def test_custom_config_reaches_cursor(monkeypatch, chronological, config, price):
    seen = []
    original = HeldMinuteCursor.advance

    def advance(self, idx, phase):
        if callable(self.exit_plan):
            seen.append(self.fill_config)
        return original(self, idx, phase)

    monkeypatch.setattr(HeldMinuteCursor, "advance", advance)
    st = run([[(895, 10)], [(600, 8.9), (601, 9.5)]],
             fill_config=config, fix_minute_cash_order=chronological)
    assert config in seen
    assert next(t for t in st.trades if t["side"] == "SELL")["price"] == price
    assert engine.memory_for(st, CODE).stopped.shares == 1000


@pytest.mark.parametrize("config,message", [
    (FillConfig(trigger_basis="bar_low", fill_at="bar_low"), "look-ahead"),
    (FillConfig(fill_at="line"), "explicit stop/target line"),
])
def test_callback_rejects_noncausal_or_missing_line(config, message):
    with pytest.raises(ValueError, match=message):
        run([[(895, 10)], [(600, 8.9)]], fill_config=config)


def test_partial_hold20_pins_only_due_lot_and_keeps_t1_lot(monkeypatch):
    original = minute.init_sim_state

    def seeded(*args, **kwargs):
        st, pending, names = original(*args, **kwargs)
        st.positions[CODE] = [Position(CODE, 1000, 10, -20, 10),
                              Position(CODE, 400, 11, 0, 11, lot_id=1)]
        return st, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seeded)
    mins, days, _ = bars_for([[(600, 10.5), (601, 10.5)]])
    st = minute.simulate(mins, days, {}, "20251103", "20251103", strategy="12")
    assert fills(st) == [(rules.HOLD20, 1000)]
    assert [(p.lot_id, p.shares) for p in st.positions[CODE]] == [(1, 400)]


def test_next_open_carries_plan_across_session_and_pins_signal_lots():
    mins, days, _ = bars_for([[(895, 10)], [(895, 8.9)], [(570, 9.5)]])
    st = minute.simulate(mins, days, {"20251103": [CODE], "20251104": [CODE]},
                         "20251103", "20251105", strategy="12", name_budget=10000,
                         fill_config=FillConfig(fill_timing="next_bar_open"))
    sell = next(t for t in st.trades if t["side"] == "SELL")
    assert (sell["date"], sell["price"], sell["shares"]) == ("20251105", 9.5, 1000)
    # The 1100-share pool lot purchased after the close signal is now T+1
    # eligible, but the queued allocation must still touch only signal lots.
    assert [(p.lot_id, p.shares) for p in st.positions[CODE]] == [(1, 1100)]


def test_chase_and_pool_fallback_clocks_are_in_shared_loop(monkeypatch):
    from tests.test_strategy12_engine import test_chase_and_pool_use_existing_clocks_and_chase_resets_memory
    seen = []
    original = engine.MinuteSession.after_close

    def after_close(self, hm):
        before = len(self.context["st"].trades)
        original(self, hm)
        seen.extend((hm, t["reason"]) for t in self.context["st"].trades[before:]
                    if t["side"] == "BUY")

    monkeypatch.setattr(engine.MinuteSession, "after_close", after_close)
    test_chase_and_pool_use_existing_clocks_and_chase_resets_memory()
    assert seen == [(585, "chase:T+1"), (895, "pool")]


def test_default_partial_capacity_retries_next_minute():
    from backtest.research.ashare_volume_cap import BucketVolume
    lookup = {(CODE, "20251103", 895): BucketVolume(1000, 895, "raw_shares_incremental"),
              (CODE, "20251104", 600): BucketVolume(300, 600, "raw_shares_incremental"),
              (CODE, "20251104", 601): BucketVolume(700, 601, "raw_shares_incremental")}
    st = run([[(895, 10)], [(600, 8.9), (601, 8.9)]],
             participation_rate=1, volume_for_bucket=lookup)
    assert fills(st) == [("pool", 1000), (rules.STOP, 300), (rules.STOP, 700)]
    assert engine.memory_for(st, CODE).stopped.shares == 1000


def test_custom_next_open_rejects_uncompleted_execution_bucket():
    from backtest.research.ashare_volume_cap import BucketVolume
    lookup = {(CODE, "20251103", 895): BucketVolume(1000, 895, "raw_shares_incremental"),
              (CODE, "20251104", 600): BucketVolume(300, 600, "raw_shares_incremental"),
              (CODE, "20251104", 601): BucketVolume(1000, 601, "raw_shares_incremental")}
    st = run([[(895, 10)], [(600, 8.9), (601, 9.5)]],
             fill_config=FillConfig(fill_timing="next_bar_open"),
             participation_rate=1, volume_for_bucket=lookup)
    assert fills(st) == [("pool", 1000)]
    assert any(t["reason"] == "skip_volume_unavailable:bucket_not_completed"
               for t in st.trades if t["side"] == "SKIP")
    assert engine.memory_for(st, CODE).stopped.shares == 0
