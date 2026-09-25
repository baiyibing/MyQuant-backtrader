"""X-02 causal account clock; OFF remains the frozen research contract."""

from dataclasses import asdict
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd
import pytest
from backtest.research import ashare_bars
from backtest.research import csv_minute_backtest as minute
from backtest.research.ashare_volume_cap import BucketVolume
from backtest.research.csv_ledger import Position

A, B, C = "600000.SH", "600001.SH", "600002.SH"
D1, D2 = "20260901", "20260902"


def fen(value):
    return Decimal(str(value)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def fills(state):
    return [trade for trade in state.trades if trade["side"] in ("BUY", "SELL")]


def frames(rows, references=None):
    """Rows contain (date, hm, open, high, close) in genuine minute-of-day."""
    references = references or {}
    minutes, daily = {}, {}
    for code, values in rows.items():
        frame = pd.DataFrame(values, columns=["ymd", "hm", "open", "high", "close"])
        frame["low"] = frame[["open", "close"]].min(axis=1)
        frame["volume"] = 100_000
        frame.index = pd.to_datetime(frame["ymd"]) + pd.to_timedelta(frame["hm"], unit="m")
        minutes[code] = frame
        px = references.get(code, values[0][2])
        daily[code] = pd.DataFrame(
            {"open": px, "high": px, "low": px, "close": px},
            index=pd.to_datetime(["20260831", D1, D2]),
        )
    return minutes, daily


def run_case(rows, *, pools=None, references=None, **kwargs):
    ms, ds = frames(rows, references)
    options = {
        "strategy": "version8",
        "name_budget": 1000,
        "total_cash": 1001,
        "stop_pct": 0.05,
        "fix_minute_cash_order": True,
    }
    options.update(kwargs)
    return minute.simulate(ms, ds, pools or {}, D1, D2, **options)


def cash_case(sell_hm=899, *, gap_open=False, buy_hm=895, **kwargs):
    return run_case(
        {
            A: [(D1, 895, 10, 10, 10), (D2, sell_hm, 9.4 if gap_open else 10, 10, 9.4)],
            B: [(D1, 895, 6, 6, 6), (D2, buy_hm, 6, 6, 6)],
        },
        pools={D1: [A], D2: [B]},
        **kwargs,
    )


@pytest.mark.parametrize("sell_hm,can_buy", [(894, True), (895, True), (896, False)])
@pytest.mark.parametrize("gap_open", [False, True], ids=["close", "open"])
def test_pool_boundary_same_close_sell_proceeds_are_immediately_available(
    sell_hm, can_buy, gap_open
):
    trace = []
    state = cash_case(sell_hm, gap_open=gap_open, audit_sink=trace)
    assert [(t["code"], t["side"], t["shares"]) for t in fills(state)] == (
        [(A, "BUY", 100), (A, "SELL", 100)] + ([(B, "BUY", 100)] if can_buy else [])
    )
    assert fen(state.cash) == Decimal("338.46" if can_buy else "939.06")
    sell = next(t for t in trace if t["side"] == "SELL")
    assert (sell["hm"], sell["phase"]) == (sell_hm, "open" if gap_open else "close")
    assert fen(sell["cash_after"]) == Decimal("939.06")
    assert all(fen(t["cash_after"]) >= 0 for t in trace)


@pytest.mark.parametrize("sell_hm,quote_hm", [(893, 890), (584, 580)])
def test_fallback_quote_does_not_backdate_decision_or_borrow_capacity(
    sell_hm, quote_hm, monkeypatch
):
    is_chase = sell_hm < 600
    original = minute.init_sim_state

    def seed(*args, **kwargs):
        state, pending, names = original(*args, **kwargs)
        if is_chase:
            pending[B] = (1000, 0)
        return state, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seed)
    calls = []

    def volume(code, date, hm):
        calls.append((code, date, hm))
        return BucketVolume(100_000, hm, "raw_shares_incremental")

    trace = []
    state = run_case(
        {
            A: [(D1, 895, 10, 10, 10), (D2, sell_hm, 10, 10, 9.4)],
            B: [(D1, 895, 6, 6, 6), (D2, 570 if is_chase else quote_hm, 5.9, 6, 6)]
            + ([(D2, quote_hm, 6, 6, 6)] if is_chase else []),
        },
        pools={D1: [A], **({} if is_chase else {D2: [B]})},
        references={B: 6},
        audit_sink=trace,
        participation_rate=1,
        volume_for_bucket=volume,
    )
    assert fen(state.cash) == Decimal("338.46")
    bought = next(t for t in trace if t["code"] == B and t["side"] == "BUY")
    assert (bought["decision_hm"], bought["quote_hm"]) == (585 if is_chase else 895, quote_hm)
    assert (B, D2, quote_hm) in calls
    assert (B, D2, 585 if is_chase else 895) not in calls


def test_chase_cannot_spend_afternoon_sale_and_does_not_retry(monkeypatch):
    original = minute.init_sim_state

    def seed(*args, **kwargs):
        state, pending, names = original(*args, **kwargs)
        pending[B] = (1000, 0)
        return state, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seed)
    rows = {
        A: [(D1, 895, 10, 10, 10), (D2, 899, 10, 10, 9.4)],
        B: [(D1, 895, 6, 6, 6), (D2, 570, 5.9, 5.9, 5.9), (D2, 585, 6, 6, 6)],
    }
    off = run_case(rows, pools={D1: [A]}, references={B: 6}, fix_minute_cash_order=False)
    on = run_case(rows, pools={D1: [A]}, references={B: 6})
    assert fen(off.cash) == Decimal("338.46")
    assert fen(on.cash) == Decimal("939.06")
    assert not any(t["code"] == B for t in fills(on))
    assert on.stats["chase_buy_fail_cash"] == 1 and on.stats["chase_pending_eod"] == 0


@pytest.mark.parametrize("failure", ["no_signal", "limit_down", "zero_capacity"])
def test_unsold_position_contributes_no_cash(failure):
    close = {"no_signal": 10, "limit_down": 9, "zero_capacity": 9.4}[failure]
    options = {}
    if failure == "zero_capacity":
        options = {
            "participation_rate": 1,
            "volume_for_bucket": lambda code, date, hm: BucketVolume(
                0 if date == D2 and code == A else 100_000, hm, "raw_shares_incremental"
            ),
        }
    state = run_case(
        {
            A: [(D1, 895, 10, 10, 10), (D2, 894, 10, 10, close)],
            B: [(D1, 895, 6, 6, 6), (D2, 895, 6, 6, 6)],
        },
        pools={D1: [A], D2: [B]},
        **options,
    )
    assert [(t["code"], t["side"]) for t in fills(state)] == [(A, "BUY")]
    assert fen(state.cash) == 0 and state.positions[A][0].shares == 100


@pytest.mark.parametrize("min_cost", [0, 5])
def test_partial_sale_only_credits_actual_shares_net_of_fee(min_cost):
    trace = []

    def volume(code, date, hm):
        return BucketVolume(
            150 if (code, date) == (A, D2) else 100_000, hm, "raw_shares_incremental"
        )

    state = run_case(
        {
            A: [(D1, 895, 10, 10, 10), (D2, 894, 10, 10, 9.4), (D2, 896, 10, 12, 9.3)],
            B: [(D1, 895, 6, 6, 6), (D2, 895, 6, 6, 6)],
        },
        pools={D1: [A], D2: [B]},
        total_cash=2000 + max(2, min_cost),
        name_budget=2000,
        min_cost=min_cost,
        participation_rate=1,
        volume_for_bucket=volume,
        audit_sink=trace,
    )
    assert [(t["code"], t["side"], t["shares"]) for t in fills(state)] == [
        (A, "BUY", 200),
        (A, "SELL", 150),
    ]
    assert state.positions[A][0].shares == 50
    assert state.positions[A][0].peak == 10  # first sell attempt ends that day's scan
    assert fen(state.cash) == fen(1410 - max(1.41, min_cost))
    assert sum(t["side"] == "SELL" for t in trace) == 1


def test_first_rejected_sell_attempt_does_not_retry_or_observe_later_high():
    looked_up = []

    def volume(code, date, hm):
        looked_up.append((code, date, hm))
        return BucketVolume(0 if (date, hm) == (D2, 894) else 100_000, hm, "raw_shares_incremental")

    state = run_case(
        {A: [(D1, 895, 10, 10, 10), (D2, 894, 10, 10, 9.4), (D2, 896, 10, 12, 9.3)]},
        pools={D1: [A]},
        participation_rate=1,
        volume_for_bucket=volume,
    )
    assert [t["side"] for t in fills(state)] == ["BUY"]
    assert state.positions[A][0].peak == 10
    assert (A, D2, 896) not in looked_up


def test_future_sale_does_not_remove_held_before_pool(monkeypatch):
    real = minute.prepare_strategy_hooks

    def hooks(*args, **kwargs):
        got = real(*args, **kwargs)
        got["allow_add"] = False
        return got

    monkeypatch.setattr(minute, "prepare_strategy_hooks", hooks)
    state = run_case(
        {A: [(D1, 895, 10, 10, 10), (D2, 895, 10, 10, 10), (D2, 899, 10, 10, 9.4)]},
        pools={D1: [A], D2: [A]},
        total_cash=5000,
    )
    assert [(t["date"], t["side"]) for t in fills(state)] == [(D1, "BUY"), (D2, "SELL")]
    assert state.stats["skip_held"] == 1


@pytest.mark.parametrize("min_cost", [0, 5])
def test_partial_sale_funds_affordable_buy_and_preserves_trigger_high(monkeypatch, min_cost):
    original = minute.init_sim_state

    def seed(*args, **kwargs):
        state, pending, names = original(*args, **kwargs)
        state.positions[A] = [Position(A, 200, 10, 0, 10)]
        return state, pending, names

    monkeypatch.setattr(minute, "init_sim_state", seed)

    def volume(code, date, hm):
        return BucketVolume(
            150 if code == A and date == D2 else 100_000, hm, "raw_shares_incremental"
        )

    state = run_case(
        {
            A: [(D1, 895, 10, 10, 10), (D2, 894, 10, 13, 9.4), (D2, 896, 10, 14, 9.3)],
            B: [(D1, 895, 6, 6, 6), (D2, 895, 6, 6, 6)],
        },
        pools={D2: [B]},
        total_cash=0,
        min_cost=min_cost,
        participation_rate=1,
        volume_for_bucket=volume,
    )
    assert [(t["code"], t["side"], t["shares"]) for t in fills(state)] == [
        (A, "SELL", 150),
        (B, "BUY", 100),
    ]
    assert fen(state.cash) == fen(1410 - max(1.41, min_cost) - 600 - max(0.6, min_cost))
    assert (state.positions[A][0].shares, state.positions[A][0].peak) == (50, 13)


@pytest.mark.parametrize("gap_open", [False, True])
def test_single_name_without_crossed_clocks_keeps_fill_tuples(gap_open):
    rows = {A: [(D1, 895, 10, 10, 10), (D2, 899, 9.4 if gap_open else 10, 10, 9.4)]}
    kwargs = {"pools": {D1: [A]}, "total_cash": 100_000}
    off = run_case(rows, fix_minute_cash_order=False, **kwargs)
    on = run_case(rows, **kwargs)
    assert on.trades == off.trades
    assert on.cash == off.cash and on.positions == off.positions


def test_opening_snapshot_pool_plan_budget_and_step_see_current_lots(monkeypatch):
    real = minute.prepare_strategy_hooks
    observed = {"opening": [], "plan": [], "budget": [], "step": []}

    def hooks(*args, **kwargs):
        got = real(*args, **kwargs)
        got["bind_opening_held"] = lambda date, held: observed["opening"].append((date, held))

        def plan(date, held):
            observed["plan"].append((date, held))
            return [A]

        def budget(value, lots):
            observed["budget"].append([p.entry_idx for p in lots])
            return value

        def step(lots, px):
            observed["step"].append([p.entry_idx for p in lots])
            return False

        got.update(planned_for_day=plan, name_lot_budget=budget, step_add=step)
        return got

    monkeypatch.setattr(minute, "prepare_strategy_hooks", hooks)
    state = run_case(
        {A: [(D1, 895, 10, 10, 10), (D2, 895, 10, 10, 10), (D2, 899, 10, 10, 9.4)]}, total_cash=5000
    )
    assert observed["opening"] == [(D1, []), (D2, [A])]
    assert observed["plan"] == [(D1, []), (D2, [A])]
    assert observed["budget"] == [[], [0]]
    assert observed["step"] == [[0], [0, 1]]
    assert [(p.entry_idx, p.shares, p.peak) for p in state.positions[A]] == [(1, 100, 10)]


def test_future_high_cannot_open_add_gate(monkeypatch):
    real = minute.prepare_strategy_hooks

    def hooks(*args, **kwargs):
        got = real(*args, **kwargs)
        got.update(
            add_gate=lambda lots, px: lots[0].peak >= 11,
            take_profit=lambda *_: None,
            reserve_limit_up=False,
            defer_limit_up=False,
            step_add=None,
        )
        return got

    monkeypatch.setattr(minute, "prepare_strategy_hooks", hooks)
    state = run_case(
        {A: [(D1, 895, 10, 10, 10), (D2, 895, 10, 10, 10), (D2, 899, 10, 11, 10)]},
        pools={D1: [A], D2: [A]},
        total_cash=5000,
    )
    assert len(fills(state)) == 1 and state.stats["skip_add_loser"] == 1
    assert state.positions[A][0].peak == 11


@pytest.mark.parametrize("ration", ["file_order", "seeded_shuffle"])
@pytest.mark.parametrize("strategy", ["version8_1", "version8_2"])
def test_whole_pool_denominator_ration_and_commission_match_legacy(ration, strategy):
    rows = {code: [(D1, 895, 10, 10, 10)] for code in (A, B, C)}
    arguments = {
        "pools": {D1: [A, B, C]},
        "total_cash": 6006 if strategy == "version8_1" else 2002,
        "daily_quota": 3000,
        "name_budget": 1000,
        "ration": ration,
        "ration_seed": 137,
        "strategy": strategy,
    }
    off = run_case(rows, fix_minute_cash_order=False, **arguments)
    on = run_case(rows, **arguments)
    assert on.trades == off.trades
    assert on.cash == off.cash
    assert on.daily_quota_used == off.daily_quota_used
    assert [(p.shares, p.cost) for lots in on.positions.values() for p in lots] == (
        [(100, 10)] * (3 if strategy == "version8_1" else 2)
    )


def test_on_lunch_bars_are_filtered_by_production_annotation():
    clocks = [
        "09:29",
        "09:30",
        "10:00",
        "11:30",
        "11:31",
        "12:00",
        "12:59",
        "13:00",
        "15:00",
        "15:01",
    ]
    raw = pd.DataFrame(index=pd.to_datetime([f"2026-09-02 {hm}" for hm in clocks]))
    raw["open"], raw["high"], raw["low"], raw["close"] = 10.0, 10.0, 9.4, 10.0
    raw.loc[raw.index.hour == 12, "close"] = 9.4
    filtered = ashare_bars.annotate_session(raw)
    assert filtered.hm.tolist() == [570, 600, 690, 780, 900]
    ms, ds = frames({A: [(D1, 895, 10, 10, 10)]})
    ms[A] = pd.concat([ms[A], filtered])
    trace = []
    state = minute.simulate(
        ms,
        ds,
        {D1: [A]},
        D1,
        D2,
        strategy="version8",
        name_budget=1000,
        total_cash=1001,
        stop_pct=0.05,
        fix_minute_cash_order=True,
        audit_sink=trace,
    )
    assert [t["side"] for t in fills(state)] == ["BUY"]
    assert all(not 690 < t["hm"] < 780 for t in trace)


def test_chase_queue_order_and_unfixed_x04_pool_budget_match_off():
    rows = {
        A: [(D1, 895, 11, 11, 11), (D2, 570, 10, 10, 10), (D2, 585, 10.5, 10.5, 10.5)],
        B: [(D1, 895, 6.6, 6.6, 6.6), (D2, 570, 6, 6, 6), (D2, 585, 6.3, 6.3, 6.3)],
        C: [(D1, 895, 5, 5, 5), (D2, 895, 5, 5, 5)],
    }
    args = {
        "pools": {D1: [B, A], D2: [C]},
        "references": {A: 10, B: 6, C: 5},
        "strategy": "version8_1",
        "total_cash": 10000,
        "daily_quota": 4000,
    }
    off = run_case(rows, fix_minute_cash_order=False, **args)
    on = run_case(rows, **args)
    assert on.trades == off.trades and on.cash == off.cash
    assert [(t["code"], t["shares"], t["reason"]) for t in fills(on)] == [
        (B, 300, "chase:T+1"),
        (A, 100, "chase:T+1"),
        (C, 800, "pool"),
    ]
    # X-04 intentionally remains: pool uses the existing full daily quota even
    # after chase spent 2940. X-02 must not quietly change this budget rule.
    assert on.daily_quota_used == 6940
    assert on.stats["chase_buy"] == 2 and on.stats["chase_pending_eod"] == 0


def test_explicit_off_matches_omission_complete_state():
    ms, ds = frames({A: [(D1, 895, 10, 10, 10), (D2, 899, 10, 10, 9.4)]})
    args = (ms, ds, {D1: [A]}, D1, D2)
    omitted = minute.simulate(*args, strategy="version8", name_budget=1000, stop_pct=0.05)
    explicit = minute.simulate(
        *args, strategy="version8", name_budget=1000, stop_pct=0.05, fix_minute_cash_order=False
    )
    assert asdict(explicit) == asdict(omitted)
    assert "fix_minute_cash_order" not in explicit.stats


def test_strategy12_explicitly_rejects_cash_order_flag():
    ms, ds = frames({A: [(D1, 895, 10, 10, 10)]})
    with pytest.raises((ValueError, SystemExit), match="(?i)(version12|strategy.?12|s12)"):
        minute.simulate(ms, ds, {}, D1, D2, strategy="version12", fix_minute_cash_order=True)


def force_on(monkeypatch):
    real = minute.simulate

    def enabled(*args, **kwargs):
        kwargs["fix_minute_cash_order"] = True
        return real(*args, **kwargs)

    monkeypatch.setattr(minute, "simulate", enabled)


def cursor_scan(o, h, c, **kwargs):
    from backtest.research.minute_cash_order import HeldMinuteCursor

    kwargs.pop("use_numba", None)
    cursor = HeldMinuteCursor(o, h, c, **kwargs)
    event = None
    for idx in range(len(c)):
        for phase in ("open", "close"):
            result = cursor.advance(idx, phase)
            if result is not None:
                event = result
        if event is not None:
            break
    return (*(event or (-1, float("nan"), "")), cursor.peak, cursor.peak_hm)


@pytest.mark.parametrize(
    "case",
    [
        "defer_lu",
        "reserve_lu",
        "reserved_open_board",
        "gap15",
        "stale_priority",
        "missing_close",
        "missing_close_defer",
        "t0",
        "high_before_gap",
        "exit_plan",
        "sell_gate",
        "force_time",
    ],
)
def test_resumable_cursor_matches_whole_day_scanner(case):
    from backtest.research.minute_cash_order import HeldMinuteCursor

    hooks = minute.apply_csv_strategy("version8")
    rows = [(570, 10, 10, 10), (585, 10, 10, 10), (895, 10, 10, 10), (899, 10, 10, 10)]
    options = {
        "cost": 10,
        "peak": 10,
        "n_days": 1,
        "can_sell": True,
        "stop_pct": 0.05,
        "profit_base": 0.0,
        "trail_ratio": 0.0,
        "peak_gap_min": 15,
        "take_profit": hooks["take_profit"],
        "limit_up": 11,
        "limit_down": 9,
    }
    if case in ("defer_lu", "reserve_lu"):
        rows = [(570, 11, 11, 11), (585, 11, 11, 11), (895, 11, 11, 11), (899, 10.9, 10.95, 10.9)]
        options["defer_limit_up" if case == "defer_lu" else "reserve_limit_up"] = True
    elif case == "reserved_open_board":
        options.update(reserved=True, reserve_limit_up=True)
        rows = [(570, 10.9, 10.95, 10.9)]
    elif case == "gap15":
        rows = [
            (570, 11.8, 12, 11.5),
            (584, 11.5, 11.55, 11.5),
            (585, 11.5, 11.55, 11.5),
            (895, 11.5, 11.55, 11.5),
        ]
    elif case == "stale_priority":
        options.update(peak=12, n_days=8, peak_gap_min=0)
        rows = [(585, 11.6, 11.7, 11.6)]
    elif case.startswith("missing_close"):
        options.update(close_clear=lambda *_: "force_sell:test_close", take_profit=lambda *_: None)
        if case == "missing_close_defer":
            options["defer_limit_up"] = True
            rows = [(570, 11, 11, 11), (585, 11, 11, 11), (895, 11, 11, 11)]
    elif case == "t0":
        options.update(can_sell=False, n_days=0)
        rows = [(570, 9.4, 13, 9.3)]
    elif case == "high_before_gap":
        rows = [(585, 9.4, 13, 9.3), (895, 9.3, 14, 9.2)]
    elif case == "exit_plan":
        options.update(exit_plan=lambda *_: ("partial:test", 150), peak_gap_min=0)
    elif case == "sell_gate":
        options.update(sell_gate=lambda *_: "gate:test", peak_gap_min=0)
    elif case == "force_time":
        options.update(force_sell_hm=895, take_profit=lambda *_: None)
    hm, o, h, c = (np.array(values) for values in zip(*rows))
    old_reserve, new_reserve = (
        {"reserved": options.get("reserved", False)},
        {"reserved": options.get("reserved", False)},
    )
    old_exit, new_exit = {}, {}
    original = minute.scan_held_day_python(
        o, h, c, hm=hm, reserve_state=old_reserve, exit_state=old_exit, **options
    )
    cursor = HeldMinuteCursor(
        o, h, c, hm=hm, reserve_state=new_reserve, exit_state=new_exit, **options
    )
    event = None
    for idx in range(len(c)):
        for phase in ("open", "close"):
            result = cursor.advance(idx, phase)
            if result is not None:
                event = result
        if case.startswith("missing_close") and idx < len(c) - 1:
            assert event is None  # pausing at chase/pool is never an EOD fallback
        if event is not None:
            break
    result = (*(event or (-1, float("nan"), "")), cursor.peak, cursor.peak_hm)
    assert (result[0], result[2:]) == (original[0], original[2:])
    if original[0] >= 0:
        assert result[1] == original[1]
        assert cursor.first_exit_attempted
    else:
        assert not cursor.first_exit_attempted
    assert new_reserve == old_reserve and new_exit == old_exit
    if case == "defer_lu":
        assert cursor.lu_today
    if case == "reserve_lu":
        assert not cursor.current_reserved and result[2] == "open_board"


def test_close_proceeds_cannot_fund_same_minute_earlier_open_buy():
    from backtest.research.csv_ledger import SimState, _sell, execute_buy
    from backtest.research.minute_cash_order import HeldMinuteCursor

    state = SimState(cash=0)
    old = Position(A, 100, 10, 0, 10)
    state.positions[A] = [old]
    cursor = HeldMinuteCursor(
        np.array([10.0]),
        np.array([10.0]),
        np.array([9.4]),
        hm=np.array([895]),
        cost=10,
        peak=10,
        n_days=1,
        can_sell=True,
        stop_pct=0.05,
        profit_base=0,
        trail_ratio=0,
    )
    assert cursor.advance(0, "open") is None
    assert not execute_buy(state, B, 6, 1000, 1, pd.Timestamp(D2))
    _, px, reason = cursor.advance(0, "close")
    _sell(state, A, old, px, pd.Timestamp(D2), reason, day_i=1)
    assert fen(state.cash) == Decimal("939.06")
    assert [(t["code"], t["side"]) for t in fills(state)] == [(A, "SELL")]


@pytest.mark.parametrize(
    "name",
    [
        "test_contract_t_fill_then_entry_day_eod_then_next_open_no_reentry",
        "test_green_entry_above_sma_holds_through_red_then_breaks",
        "test_pending_down_limit_defers_to_next_day_open_despite_intraday_rebound",
        "test_cap_off_never_looks_up_volume_and_keeps_open_fills",
        "test_volume_a_unfinished_open_bucket_buy_skips_before_lookup",
    ],
)
def test_strategy11_contracts_with_chronological_clock(name, monkeypatch):
    from tests import test_strategy11_engine as existing

    force_on(monkeypatch)
    test = getattr(existing, name)
    if "engine" in test.__code__.co_varnames[: test.__code__.co_argcount]:
        test(minute)
    else:
        test()


def test_strategy11_limit_up_no_chase_and_pending_volume_with_clock(monkeypatch):
    from tests import test_strategy11_engine as existing

    force_on(monkeypatch)
    existing.test_limit_up_skip_consumes_signal_and_actual_chase_queue_stays_empty(
        minute, monkeypatch
    )
    existing.test_volume_a_unfinished_open_bucket_pending_sell_defers_preserves_position(
        monkeypatch
    )


@pytest.mark.parametrize(
    "name",
    [
        "test_v8_5_minute_t4_sells_at_close_not_open",
        "test_v8_5_minute_uses_last_bar_when_close_missing",
        "test_v8_5_peak_gap_blocks_target_not_t4_clear",
        "test_v8_6_minute_clears_on_t1_close",
    ],
)
def test_close_clear_milestones_with_chronological_clock(name, monkeypatch):
    from tests import test_strategy8_milestones as existing

    force_on(monkeypatch)
    monkeypatch.setattr(minute, "scan_held_day", cursor_scan)
    getattr(existing, name)()


@pytest.mark.parametrize(
    "name",
    [
        "test_t0_after_buy_high_does_not_set_peak",
        "test_simulate_trail_defers_at_limit_down_close_then_resells",
        "test_simulate_limit_up_chases_when_945_above_open",
    ],
)
def test_existing_minute_contracts_with_chronological_clock(name, monkeypatch):
    from tests import test_csv_minute_backtest as existing

    force_on(monkeypatch)
    getattr(existing, name)()


@pytest.mark.parametrize("economics", [False, True])
def test_reference_adjustment_and_explicit_entitlement_are_separate(economics, monkeypatch):
    from tests import test_exdiv_refprice_engines as existing

    force_on(monkeypatch)
    if economics:
        existing.test_d6_book_exday_pool_add_has_no_entitlement(minute)
        existing.test_d6_book_public_bonus_t1_and_following_sale(minute)
    else:
        from backtest.research import minute_cash_order

        # Existing spy observes the public minute module; bridge only the spy,
        # leaving the production scheduler and rescale implementation intact.
        monkeypatch.setattr(
            minute_cash_order, "rescale_position", lambda *args: minute.rescale_position(*args)
        )
        existing.test_d2_book_once_per_event_and_new_lot_not_rescaled(minute, monkeypatch)
        existing.test_d2_step_uses_mapped_band_and_new_raw_cost(minute, 6.0, False)
        existing.test_d6_book_empty_invalid_lookup_does_not_invent_from_k(minute)
