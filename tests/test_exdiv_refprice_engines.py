# -*- coding: utf-8 -*-
"""E-R6 ex-div refprice engine vectors (arch T1–T16; required subset locked)."""

from __future__ import annotations

from dataclasses import asdict
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_daily_backtest as daily
import backtest.research.csv_minute_backtest as minute
import backtest.research.csv_minute_backtest_v7 as v7
from backtest.research import ashare_session, exdiv_map
from backtest.research.csv_artifacts import summarize
from backtest.research.csv_ledger import Position, SimState, rescale_position
from backtest.research.market_layer import limit_prices


DAYS = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07"]
CODE = "600000.SH"
# k=0.5 → D-domain prev_close_ref=5; limit_up=5.50 / limit_down=4.50
EXDIV_HALF = {"600000.SH": {"20251105": 0.5}}
# Mild jump: unmapped open can sit in (limit_down, trigger] → false gap_open under E-R1.
# k=0.90 → cost' =9.0; v1 trigger'=8.82; unmapped trigger=9.8, limit_down=9.0
EXDIV_MILD = {"600000.SH": {"20251105": 0.90}}


def _daily_bars(
    rows: dict[str, list[tuple]], days: list[str] = DAYS, start_offset: int = 1
):
    out = {}
    idx = pd.to_datetime(days)
    for code, r in rows.items():
        pre = pd.Timestamp(days[0]) - pd.Timedelta(days=start_offset * 2)
        pre_idx = pd.DatetimeIndex([pre]) if pre not in idx else pd.DatetimeIndex([])
        frame = pd.DataFrame(
            {
                "open": [10.0] + [x[0] for x in r],
                "high": [10.0] + [x[1] for x in r],
                "low": [10.0] + [x[2] for x in r],
                "close": [10.0] + [x[3] for x in r],
            },
            index=pre_idx.append(idx),
        ).astype(np.float64)
        out[code] = frame
    return out


def _daily_run(pool, bars, **kwargs):
    kwargs.setdefault("strategy", "version1")
    kwargs.setdefault("total_cash", 21_000_000.0)
    return daily.simulate(bars, pool, "20251103", "20251107", **kwargs)


def _minute_day(date: str, rows: list[tuple]) -> pd.DataFrame:
    idx, opens, highs, lows, closes = [], [], [], [], []
    d = pd.Timestamp(date)
    for hm, oo, hh, ll, cc in rows:
        hour, minute_ = divmod(int(hm), 100)
        idx.append(d + pd.Timedelta(hours=hour, minutes=minute_))
        opens.append(oo)
        highs.append(hh)
        lows.append(ll)
        closes.append(cc)
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes},
        index=pd.DatetimeIndex(idx),
    ).astype(np.float64)
    return minute._annotate(df)


def _minute_daily(
    dates: list[str], ohlc: list[tuple], prev: float = 10.0
) -> pd.DataFrame:
    pre = pd.Timestamp(dates[0]) - pd.Timedelta(days=2)
    idx = pd.DatetimeIndex([pre] + [pd.Timestamp(d) for d in dates])
    return pd.DataFrame(
        {
            "open": [prev] + [r[0] for r in ohlc],
            "high": [prev] + [r[1] for r in ohlc],
            "low": [prev] + [r[2] for r in ohlc],
            "close": [prev] + [r[3] for r in ohlc],
        },
        index=idx,
    ).astype(np.float64)


def test_rescale_position_scales_cost_peak_keeps_peak_hm():
    pos = Position(CODE, 100, 10.0, 0, 12.0, peak_hm=575)
    rescale_position(pos, 0.5)
    assert pos.cost == pytest.approx(5.0)
    assert pos.peak == pytest.approx(6.0)
    assert pos.peak_hm == 575
    assert pos.shares == 100


def test_t1_false_gap_open_stop_disappears_v1():
    """T1: mild ex-div; unmapped false gap_open; mapped holds."""
    # open 9.50 ∈ (9.0 unmapped limit_down, 9.8 unmapped trigger]
    rows = {
        CODE: [
            (10.0, 10.0, 9.9, 10.0),
            (10.0, 10.0, 9.9, 10.0),
            (9.50, 9.60, 9.40, 9.55),
            (9.55, 9.65, 9.45, 9.60),
            (9.60, 9.70, 9.50, 9.65),
        ]
    }
    bars = _daily_bars(rows)
    st_false = _daily_run({"20251103": [CODE]}, bars, exdiv=None)
    assert any(
        t["reason"] == "stop_loss:gap_open" and t["date"] == "20251105"
        for t in st_false.trades
        if t["side"] == "SELL"
    )

    st = _daily_run({"20251103": [CODE]}, bars, exdiv=EXDIV_MILD)
    assert not any(
        t["reason"] == "stop_loss:gap_open" for t in st.trades if t["side"] == "SELL"
    )
    assert st.stats.get("exdiv_adjusted_lots", 0) >= 1
    assert st.stats.get("exdiv_prev_close_mapped", 0) >= 1


def test_t1_false_gap_open_stop_disappears_v8():
    # v8 stop 30%: trigger=7. Use open 5.05 below unmapped limit_down 9.0:
    # unmapped: open 5.05 <= limit_down 9.0 → DEFER (not gap_open) under E-R1.
    # Mapped k=0.5: cost=5 trigger=3.5, open 5.05 → no stop.
    rows = {
        CODE: [
            (10.0, 10.2, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (5.05, 5.20, 5.00, 5.10),
            (5.10, 5.20, 5.00, 5.15),
            (5.15, 5.25, 5.10, 5.20),
        ]
    }
    bars = _daily_bars(rows)
    st_false = _daily_run({"20251103": [CODE]}, bars, strategy="version8", exdiv=None)
    assert st_false.stats["defer_sell_limit_down"] >= 1 or any(
        t["side"] == "SELL" and t["date"] == "20251105" for t in st_false.trades
    )
    st = _daily_run({"20251103": [CODE]}, bars, strategy="version8", exdiv=EXDIV_HALF)
    assert not any(
        t["reason"].startswith("stop_loss") for t in st.trades if t["side"] == "SELL"
    )
    assert st.stats.get("exdiv_adjusted_lots", 0) >= 1


def test_t2_limit_mapping_d_domain():
    lu, ld = limit_prices(CODE, 5.0)
    assert lu == pytest.approx(5.50)
    assert ld == pytest.approx(4.50)


def test_t3_false_fill_disappears_limit_down_defer():
    """T3: D open=4.50 (=mapped limit_down). Mapped → defer; unmapped → false fill
    only when open sits above unmapped limit_down — use open=4.50 with a sell path
    that checks trigger vs limit (touch) after rescale would defer at D-domain.
    """
    # Path: pending_exit from prior day; D open at mapped limit_down → defer.
    # Seed pending via trail on 11/04 then open-at-limit on 11/05.
    rows = {
        CODE: [
            (10.0, 10.2, 9.9, 10.0),
            (12.0, 12.5, 11.5, 11.6),  # peak up; close may arm trail pending
            (4.50, 4.60, 4.50, 4.55),  # ex open at mapped LD
            (4.60, 4.70, 4.55, 4.65),
            (4.70, 4.80, 4.60, 4.75),
        ]
    }
    # Simpler direct: gap path with k=0.5 v1 — mapped open=4.50 == LD → defer.
    rows = {
        CODE: [
            (10.0, 10.0, 9.9, 10.0),
            (10.0, 10.0, 9.9, 10.0),
            (4.50, 4.60, 4.50, 4.55),
            (4.60, 4.70, 4.55, 4.65),
            (4.70, 4.80, 4.60, 4.75),
        ]
    }
    bars = _daily_bars(rows)
    st = _daily_run({"20251103": [CODE]}, bars, strategy="version1", exdiv=EXDIV_HALF)
    assert not any(t["side"] == "SELL" and t["date"] == "20251105" for t in st.trades)
    assert st.stats["defer_sell_limit_down"] >= 1

    # Unmapped: open 4.50 << limit_down 9.0 → also defers under E-R1 (no false fill).
    # Demonstrate false fill with mild open above unmapped LD but below unmapped trigger:
    rows_fill = {
        CODE: [
            (10.0, 10.0, 9.9, 10.0),
            (10.0, 10.0, 9.9, 10.0),
            (9.50, 9.60, 9.40, 9.55),  # false gap_open fill under unmapped
            (9.55, 9.65, 9.45, 9.60),
            (9.60, 9.70, 9.50, 9.65),
        ]
    }
    st_false = _daily_run(
        {"20251103": [CODE]}, _daily_bars(rows_fill), strategy="version1", exdiv=None
    )
    assert any(
        t["reason"] == "stop_loss:gap_open" and t["price"] == pytest.approx(9.50)
        for t in st_false.trades
        if t["side"] == "SELL"
    )


def test_t4_touch_stop_fill_price_in_d_domain():
    """T4: after rescale, touch stop fills at D-domain trigger 4.9."""
    rows = {
        CODE: [
            (10.0, 10.0, 9.9, 10.0),
            (10.0, 10.0, 9.9, 10.0),
            # open above trigger 4.9 so not gap; low touches 4.85
            (5.20, 5.30, 4.85, 5.10),
            (5.10, 5.20, 5.00, 5.15),
            (5.15, 5.25, 5.10, 5.20),
        ]
    }
    st = _daily_run({"20251103": [CODE]}, _daily_bars(rows), exdiv=EXDIV_HALF)
    sells = [t for t in st.trades if t["side"] == "SELL" and t["date"] == "20251105"]
    assert sells, f"expected touch stop; trades={st.trades} stats={st.stats}"
    assert sells[0]["reason"] == "stop_loss:touch"
    assert sells[0]["price"] == pytest.approx(4.9)


def test_t5_target_consistency_v8():
    from backtest.research.strategy8_rules import take_profit_reason

    rows = {
        CODE: [
            (10.0, 10.2, 9.9, 10.0),
            (10.02, 10.05, 10.00, 10.03),
            (5.01, 5.04, 5.00, 5.02),
            (5.01, 5.03, 5.00, 5.02),
            (5.01, 5.03, 5.00, 5.01),
        ]
    }
    st = _daily_run(
        {"20251103": [CODE]}, _daily_bars(rows), strategy="version8", exdiv=EXDIV_HALF
    )
    lots = st.positions.get(CODE) or []
    assert lots, f"T+2 keeps the lot below the mapped 1.01 floor; trades={st.trades}"
    assert lots[0].cost == pytest.approx(5.0)
    assert take_profit_reason(5.04, 5.0, 5.04, 1) is None
    assert take_profit_reason(5.05, 5.0, 5.05, 1) == "trail:max101_80"
    assert take_profit_reason(5.04, 5.0, 5.04, 8) == "force_sell:stale"
    assert not [t for t in st.trades if t["side"] == "SELL"]


def test_t6_buy_day_exdiv_no_double_scale():
    rows = {
        CODE: [
            (10.0, 10.2, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (5.06, 5.20, 5.00, 5.06),
            (5.10, 5.20, 5.00, 5.15),
            (5.15, 5.25, 5.10, 5.20),
        ]
    }
    st = _daily_run({"20251105": [CODE]}, _daily_bars(rows), exdiv=EXDIV_HALF)
    assert st.stats["buys"] == 1
    lots = st.positions.get(CODE) or []
    assert lots and lots[0].cost == pytest.approx(5.06)


def test_t8_chase_due_on_exdiv_day_uses_mapped_limit():
    rows = {
        CODE: [
            (10.5, 11.0, 10.5, 11.0),  # limit-up vs prev 10
            (10.0, 10.2, 9.9, 10.0),
            (5.05, 5.30, 5.00, 5.20),
            (5.10, 5.25, 5.05, 5.15),
            (5.15, 5.25, 5.10, 5.20),
        ]
    }
    bars = _daily_bars(rows)
    bars[CODE] = bars[CODE].drop(labels=[pd.Timestamp("2025-11-04")])
    st = _daily_run({"20251103": [CODE]}, bars, exdiv=EXDIV_HALF)
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert st.stats["skip_limit_up"] == 1
    chase = next(t for t in buys if t["reason"] == "chase:T+1")
    assert chase["date"] == "20251105"
    assert chase["price"] == pytest.approx(5.20)
    assert st.stats.get("exdiv_prev_close_mapped", 0) >= 1


def test_t9_pool_buy_limit_up_uses_mapped_band():
    """T9: close=5.50 on ex day → mapped limit_up hit → chase; unmapped buys."""
    rows = {
        CODE: [
            (10.0, 10.2, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (5.40, 5.50, 5.30, 5.50),
            (5.50, 5.60, 5.40, 5.55),
            (5.55, 5.65, 5.45, 5.60),
        ]
    }
    bars = _daily_bars(rows)
    st_false = _daily_run({"20251105": [CODE]}, bars, exdiv=None)
    assert st_false.stats["skip_limit_up"] == 0
    assert st_false.stats["buys"] == 1

    st = _daily_run({"20251105": [CODE]}, bars, exdiv=EXDIV_HALF)
    assert st.stats["skip_limit_up"] == 1
    # Chase may fill later days; day-of pool buy must not execute.
    pool_buys = [
        t
        for t in st.trades
        if t["side"] == "BUY" and t["reason"] == "pool" and t["date"] == "20251105"
    ]
    assert pool_buys == []


def test_t11_halt_resume_day_applies_scale():
    rows = {
        CODE: [
            (10.0, 10.0, 9.9, 10.0),
            (10.0, 10.0, 9.9, 10.0),
            (9.50, 9.60, 9.40, 9.55),
            (9.50, 9.60, 9.40, 9.55),
            (9.60, 9.70, 9.50, 9.65),
        ]
    }
    bars = _daily_bars(rows)
    bars[CODE] = bars[CODE].drop(labels=[pd.Timestamp("2025-11-05")])
    # Mild k on resume day 11/06; unmapped false gap on resume open 9.50
    exdiv = {"600000.SH": {"20251106": 0.90}}
    st_false = _daily_run({"20251103": [CODE]}, bars, exdiv=None)
    assert any(
        t["reason"] == "stop_loss:gap_open"
        for t in st_false.trades
        if t["side"] == "SELL"
    )
    st = _daily_run({"20251103": [CODE]}, bars, exdiv=exdiv)
    assert not any(
        t["reason"] == "stop_loss:gap_open" for t in st.trades if t["side"] == "SELL"
    )
    assert st.stats.get("exdiv_adjusted_lots", 0) >= 1


def test_t15_empty_exdiv_trades_match_baseline():
    rows = {
        CODE: [
            (10.0, 10.2, 9.9, 10.0),
            (10.1, 10.3, 10.0, 10.2),
            (10.2, 10.4, 10.1, 10.3),
            (10.3, 10.5, 10.2, 10.4),
            (10.4, 10.6, 10.3, 10.5),
        ]
    }
    bars = _daily_bars(rows)
    pool = {"20251103": [CODE]}
    assert (
        _daily_run(pool, bars, exdiv=None).trades
        == _daily_run(pool, bars, exdiv={}).trades
    )


def test_t16_equity_still_marks_raw_close_on_ex_day():
    rows = {
        CODE: [
            (10.0, 10.2, 9.9, 10.0),
            (10.0, 10.1, 9.9, 10.0),
            (5.05, 5.20, 5.00, 5.10),
            (5.10, 5.20, 5.00, 5.15),
            (5.15, 5.25, 5.10, 5.20),
        ]
    }
    st = _daily_run({"20251103": [CODE]}, _daily_bars(rows), exdiv=EXDIV_HALF)
    eq = {d: e for d, e in st.equity_curve}
    buys = [t for t in st.trades if t["side"] == "BUY"]
    assert buys and eq["20251105"] < eq["20251104"] - buys[0]["shares"] * 3.0


def test_t1_minute_false_gap_open_disappears():
    dates = ["2025-11-03", "2025-11-04", "2025-11-05"]
    m0 = _minute_day(
        "2025-11-03", [(930, 10.0, 10.0, 9.9, 10.0), (1455, 10.0, 10.0, 9.9, 10.0)]
    )
    m1 = _minute_day(
        "2025-11-04", [(930, 10.0, 10.0, 9.9, 10.0), (1455, 10.0, 10.0, 9.9, 10.0)]
    )
    m2 = _minute_day(
        "2025-11-05", [(930, 9.50, 9.55, 9.40, 9.50), (1455, 9.55, 9.60, 9.45, 9.55)]
    )
    minute_bars = {CODE: pd.concat([m0, m1, m2])}
    daily_bars = {
        CODE: _minute_daily(
            dates,
            [
                (10.0, 10.0, 9.9, 10.0),
                (10.0, 10.0, 9.9, 10.0),
                (9.50, 9.60, 9.40, 9.55),
            ],
        )
    }
    pool = {"20251103": [CODE]}
    st_false = minute.simulate(
        minute_bars, daily_bars, pool, "20251103", "20251105", strategy="version1"
    )
    assert any(
        t["reason"] == "stop_loss:gap_open"
        for t in st_false.trades
        if t["side"] == "SELL"
    )
    st = minute.simulate(
        minute_bars,
        daily_bars,
        pool,
        "20251103",
        "20251105",
        strategy="version1",
        exdiv=EXDIV_MILD,
    )
    assert not any(
        t["reason"] == "stop_loss:gap_open" for t in st.trades if t["side"] == "SELL"
    )


def test_summarize_omits_zero_exdiv_stats():
    st = SimState()
    st.equity_curve = [("20251103", 21_000_000.0)]
    st.stats["invested_notional"] = 0.0
    st.stats["bars_loaded"] = 1
    st.stats["pool_days"] = 1
    assert "除权" not in summarize(st, 21_000_000.0, "20251103", "20251103")
    st.stats["exdiv_adjusted_lots"] = 2
    assert "除权缩放 lots 2" in summarize(st, 21_000_000.0, "20251103", "20251103")


def _d2_book_run(engine, prices, *, pool=None, missing=None, exdiv=None, **kwargs):
    """Same-domain flat bars; strategy overrides are explicit in each pin."""
    dates = DAYS[:len(prices)]
    rows = [(px, px, px, px) for px in prices]
    bars = {CODE: _minute_daily(dates, rows)}
    minutes = {CODE: pd.concat([
        _minute_day(day, [(930, *row), (1455, *row)])
        for day, row in zip(dates, rows)
    ])}
    if missing == "daily":
        bars[CODE] = bars[CODE].drop(pd.Timestamp(DAYS[2]))
    elif missing == "minute":
        minutes[CODE] = minutes[CODE].loc[minutes[CODE]["ymd"] != "20251105"]
    kwargs.setdefault("strategy", "version1")
    kwargs.setdefault("take_profit", lambda *args: None)
    pool = {"20251103": [CODE]} if pool is None else pool
    args = (bars,) if engine is daily else (minutes, bars)
    return engine.simulate(*args, pool, "20251103", dates[-1].replace("-", ""),
                           exdiv=exdiv, **kwargs)


def test_d2_book_multilot_field_scope_and_non_idempotence():
    lots = [
        Position(CODE, 100, 10, 0, 12, peak_hm=575, pending_exit="trail:test",
                 reserved=True, ride_with=7),
        Position(CODE, 200, 11, 1, 13, lot_id=1, is_step=True),
    ]
    for lot in lots:
        before = asdict(lot)
        rescale_position(lot, 0.5)
        assert asdict(lot) == {**before, "cost": before["cost"] * 0.5,
                              "peak": before["peak"] * 0.5}
        rescale_position(lot, 0.5)
        assert lot.cost == before["cost"] * 0.25  # No helper dedup state.


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_d2_book_once_per_event_and_new_lot_not_rescaled(engine, monkeypatch):
    calls = []
    real = engine.rescale_position

    def observe(pos, k):
        calls.append((pos.entry_idx, pos.cost, k))
        real(pos, k)

    monkeypatch.setattr(engine, "rescale_position", observe)
    st = _d2_book_run(
        engine, [10, 10, 5, 4, 4], strategy="version8",
        pool={"20251103": [CODE], "20251105": [CODE]},
        exdiv={CODE: {"20251105": 0.5, "20251106": 0.8}},
    )
    assert calls == [(0, 10, 0.5), (0, 5, 0.8), (2, 5, 0.8)]
    assert [lot.cost for lot in st.positions[CODE]] == [4, 4]
    assert [lot.peak for lot in st.positions[CODE]] == [4, 4]
    assert st.stats["exdiv_adjusted_lots"] == 3
    assert [(t["date"], t["price"]) for t in st.trades if t["side"] == "BUY"] == [
        ("20251103", 10), ("20251105", 5),
    ]
    assert not [t for t in st.trades if t["side"] == "SELL"]


@pytest.mark.parametrize("engine,missing", [(daily, "daily"), (minute, "daily"),
                                            (minute, "minute")])
def test_d2_missing_event_bar_is_not_replayed_on_resume(engine, missing):
    st = _d2_book_run(engine, [10, 10, 5, 5], missing=missing, exdiv=EXDIV_HALF,
                      stop_pct=0.0)
    assert st.positions[CODE][0].cost == 10
    assert st.stats.get("exdiv_adjusted_lots", 0) == 0


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("event_px,blocked", [(6.02, True), (6.0, False)])
def test_d2_step_uses_mapped_band_and_new_raw_cost(engine, event_px, blocked):
    # v8 is a default Decimal book, no qlib_limit_pct override. Off-list step only.
    # Prior session stays below limit-up, avoiding the separate open-board exit.
    st = _d2_book_run(engine, [10, 10.95, event_px], strategy="version8", exdiv=EXDIV_HALF)
    assert limit_prices(CODE, 5.475) == (6.02, 4.93)
    step = [t for t in st.trades if t["side"] == "BUY" and t["reason"] == "add:step20"]
    assert bool(step) is not blocked
    assert st.positions[CODE][0].cost == 5
    assert st.stats["exdiv_adjusted_lots"] == 1
    if blocked:
        assert len(st.positions[CODE]) == 1
        assert st.stats["skip_limit_up"] == 1
    else:
        assert len(step) == 1 and step[0]["price"] == event_px
        added = st.positions[CODE][1]
        assert added.is_step and added.cost == event_px and added.entry_idx == 2


@pytest.mark.parametrize("event_open", [5.0, 4.5], ids=["fill", "limit-down-defer"])
def test_d2_pending_exit_precedes_scan_after_exdiv(event_open, monkeypatch):
    snapshots = []
    real = daily.rescale_position

    def observe(pos, k):
        before = asdict(pos)
        real(pos, k)
        snapshots.append((before, asdict(pos)))

    monkeypatch.setattr(daily, "rescale_position", observe)
    # Public take_profit callback writes pending at D-1 close, not injected state.
    st = _d2_book_run(daily, [10, 10, event_open, 4.6], exdiv=EXDIV_HALF,
                      take_profit=lambda px, cost, peak, n: "trail:d2" if n == 1 else None)
    before, after = snapshots.pop()
    assert not snapshots
    assert before["pending_exit"] == after["pending_exit"] == "trail:d2"
    assert (before["cost"], after["cost"], after["peak"]) == (10, 5, 5)
    buy = next(t for t in st.trades if t["side"] == "BUY")
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert len(sells) == 1
    sell = sells[0]
    assert sell["reason"] == "trail:d2" and sell["shares"] == buy["shares"]
    assert sell["date"] == ("20251105" if event_open == 5 else "20251106")
    assert sell["price"] == (event_open if event_open == 5 else 4.6)
    assert st.stats["defer_sell_limit_down"] == (0 if event_open == 5 else 1)


def test_d2_economic_residual_small_oracle():
    from backtest.research.csv_simulate_loop import append_equity_and_eod_marks

    pos = Position(CODE, 100, 10, 0, 12)
    st = SimState(cash=2000, positions={CODE: [pos]})
    bars = {CODE: _minute_daily(DAYS[:2], [(10, 10, 10, 10), (5, 5, 5, 5)])}
    for index, day in enumerate(pd.to_datetime(DAYS[:2])):
        if index:
            rescale_position(pos, 0.5)
        append_equity_and_eod_marks(st, ds=day.strftime("%Y%m%d"), day=day,
                                   calendar_last=pd.Timestamp(DAYS[1]), mark_bars=bars)
    assert (pos.cost, pos.peak, pos.shares, st.cash) == (5, 6, 100, 2000)
    assert st.equity_curve == [("20251103", 3000), ("20251104", 2500)]
    assert [t["side"] for t in st.trades] == ["EOD_MARK"]


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_d2_public_book_raw_mark_keeps_shares_and_cash(engine):
    before = _d2_book_run(engine, [10, 10])
    after = _d2_book_run(engine, [10, 10, 5], exdiv=EXDIV_HALF)
    shares = before.positions[CODE][0].shares
    assert after.positions[CODE][0].shares == shares
    assert after.cash == before.cash
    assert after.positions[CODE][0].cost == after.positions[CODE][0].peak == 5
    assert before.equity_curve[-1][1] - after.equity_curve[-1][1] == shares * 5
    assert not [t for t in after.trades if t["side"] == "SELL"]


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_d2_real_loader_recovery_day_wrong_domain_residual(tmp_path, monkeypatch, engine):
    def forbidden(*args, **kwargs):
        pytest.fail("both loader paths must be explicit temporary fixtures")

    monkeypatch.setattr(exdiv_map, "resolve_source_parquet", forbidden)
    adj, ex = tmp_path / "adj.parquet", tmp_path / "ex.parquet"
    pd.DataFrame({"date": ["20251103", "20251104", "20251105"],
                  "stock_code": [CODE] * 3,
                  "cumulative_adj_factor": [1.0, np.nan, 1.0 / 0.95]}).to_parquet(adj)
    pd.DataFrame({"stock_code": [CODE], "ex_date": ["20251104"]}).to_parquet(ex)
    ratios = exdiv_map.load_exdiv_ratios([CODE], "20251103", "20251105",
                                       adj_factor_path=adj, ex_date_index_path=ex)
    assert ratios == {CODE: {"20251105": pytest.approx(0.95)}}
    seen_previous = []
    real = engine.book_limit_prices

    def observe(code, previous, *args, **kwargs):
        seen_previous.append(previous)
        return real(code, previous, *args, **kwargs)

    monkeypatch.setattr(engine, "book_limit_prices", observe)
    held = _d2_book_run(engine, [10, 9.5, 9.5], strategy="version8", exdiv=ratios,
                       pool={"20251103": [CODE], "20251104": [CODE]})
    assert [p.cost for p in held.positions[CODE]] == pytest.approx([9.5, 9.025])
    assert seen_previous[-1] == pytest.approx(9.025)  # Already-new-domain 9.5 × k.
    sold = _d2_book_run(engine, [10, 9.5, 9.5], exdiv=ratios)
    sells = [t for t in sold.trades if t["side"] == "SELL"]
    assert len(sells) == 1
    assert (sells[0]["date"], sells[0]["reason"], sells[0]["price"]) == (
        "20251104", "stop_loss:gap_open", 9.5,
    )
    assert not sold.positions  # Later rescale cannot undo a real SELL.


def _d2_stub_book_entry(monkeypatch, module, tmp_path):
    pool = {"20251103": [CODE]}
    monkeypatch.setattr(module, "warn_stale_period_env", Mock())
    monkeypatch.setattr(module, "resolve_research_pool_dir", Mock(return_value=tmp_path))
    monkeypatch.setattr(module, "load_pool_day_map", Mock(return_value=pool))
    monkeypatch.setattr(module, "load_pool_names_by_day", Mock(return_value={}))
    bars = {CODE: _minute_daily(DAYS[:1], [(10, 10, 10, 10)])}
    load_bars = Mock(return_value=bars)
    loader = Mock(return_value=EXDIV_HALF)
    simulate = Mock(return_value=SimState())
    writer = Mock(side_effect=AssertionError("run() must not write artifacts"))
    monkeypatch.setattr(module, "load_daily_ohlc", load_bars)
    monkeypatch.setattr(module, "load_exdiv_ratios", loader)
    monkeypatch.setattr(module, "simulate", simulate)
    monkeypatch.setattr(module, "write_run_artifacts", writer)
    return load_bars, loader, simulate, writer


@pytest.mark.parametrize("domain", ["none", "front", "back", "qlib_day"])
def test_d2_daily_run_price_domain_skip_matrix(tmp_path, monkeypatch, domain):
    bars, loader, simulate, writer = _d2_stub_book_entry(monkeypatch, daily, tmp_path)
    kwargs = {"qlib_data_root": tmp_path} if domain == "qlib_day" else {"dividend_type": domain}
    daily.run("20251103", "20251105", strategy="version1", pool_dir=tmp_path, **kwargs)
    assert bars.call_args.kwargs["source"] == ("qlib_day" if domain == "qlib_day" else "lake")
    assert bars.call_args.kwargs["dividend_type"] == ("none" if domain == "qlib_day" else domain)
    assert simulate.call_args.kwargs["exdiv"] is (EXDIV_HALF if domain == "none" else None)
    assert loader.call_count == (1 if domain == "none" else 0)
    if domain == "none":
        assert loader.call_args.args == ({CODE}, "20251103", "20251105")
    writer.assert_not_called()


@pytest.mark.parametrize("daily_source", ["lake", "qlib_day"])
@pytest.mark.parametrize("minute_source", ["lake", "qlib_1min"])
def test_d2_minute_run_still_loads_map_in_all_source_combinations(
    tmp_path, monkeypatch, daily_source, minute_source
):
    bars, loader, simulate, writer = _d2_stub_book_entry(monkeypatch, minute, tmp_path)
    load_minute = Mock(return_value={CODE: object()})
    compact = Mock(return_value={CODE: object()})
    convert = Mock(return_value={CODE: object()})
    monkeypatch.setattr(minute, "load_minute_bars", load_minute)
    monkeypatch.setattr(minute, "_load_minute_compact", compact)
    monkeypatch.setattr(minute, "book_frames_from_compact", convert)
    minute.run("20251103", "20251105", strategy="version1", pool_dir=tmp_path,
               use_cache=False, daily_source=daily_source, minute_source=minute_source,
               qlib_day_root=tmp_path, qlib_1min_root=tmp_path)
    assert bars.call_args.kwargs["source"] == daily_source
    if minute_source == "lake":
        assert load_minute.call_args.kwargs["use_cache"] is False
        compact.assert_not_called()
    else:
        assert compact.call_args.kwargs["source"] == "qlib_1min"
        convert.assert_called_once_with(compact.return_value)
        load_minute.assert_not_called()
    loader.assert_called_once()
    assert loader.call_args.args == ({CODE}, "20251103", "20251105")
    assert simulate.call_args.kwargs["exdiv"] is EXDIV_HALF  # Includes hazardous qlib_day.
    writer.assert_not_called()


@pytest.mark.parametrize("daily_source", ["lake", "qlib_day"])
@pytest.mark.parametrize("minute_source", ["lake", "qlib_1min"])
def test_d2_v7_main_keeps_real_context_chain_with_nonempty_pool(
    tmp_path, monkeypatch, daily_source, minute_source
):
    start = pd.Timestamp(DAYS[0]).date()
    monkeypatch.setattr(v7, "load_pool_days", Mock(return_value={start: [CODE]}))
    bars = Mock(return_value=SimpleNamespace(minute={CODE: []}, daily_close={CODE: {}}))
    monkeypatch.setattr(v7, "bars_from_pool", bars)  # Keep _load_cli_bars as well.
    loader = Mock(return_value=EXDIV_HALF)
    monkeypatch.setattr(ashare_session, "load_exdiv_ratios", loader)
    monkeypatch.setattr(ashare_session, "load_pool_names_by_day", Mock(return_value={}))
    index = Mock(return_value=[start])
    monkeypatch.setattr(v7, "load_index_daily", index)
    simulate = Mock(return_value=v7.SimResult(21_000_000.0))
    monkeypatch.setattr(v7, "simulate_v7", simulate)
    writer = Mock()
    monkeypatch.setattr(v7, "write_run_artifacts", writer)
    assert v7.main(["--start", "20251103", "--end", "20251105", "--pool-dir", str(tmp_path),
                    "--output-dir", str(tmp_path / "out"), "--daily-source", daily_source,
                    "--minute-source", minute_source]) == 0
    assert bars.call_args.kwargs["daily_source"] == daily_source
    assert bars.call_args.kwargs["minute_source"] == minute_source
    loader.assert_called_once_with([CODE], "20251103", "20251105")
    index.assert_called_once()
    assert simulate.call_args.kwargs["exdiv"] is EXDIV_HALF
    writer.assert_called_once()
    assert not (tmp_path / "out").exists()


def test_d6_design_only_pure_bonus_equity_oracle():
    """δ6_design_oracle B3: arithmetic only; no production entitlement API."""
    q, price, cash, bonus, dividend = 100, 10, 2000, 1, 0
    ex_price = (price - dividend) / (1 + bonus)
    new_rights = q * bonus
    design_equity = cash + (q + new_rights) * ex_price
    assert ex_price / price == 0.5
    assert (q + new_rights, cash, design_equity) == (200, 2000, 3000)
    # Before listing, the new rights replace the new shares in valuation.
    assert cash + q * ex_price + new_rights * ex_price == design_equity
    # As-built 100-share/2000-cash residual is pinned by the existing d2 oracle.
    assert cash + q * ex_price == 2500 < design_equity


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_d6_design_only_cash_receivable_to_pay_vs_raw_residual(engine):
    """δ6_design_oracle B4: design transfer conserves NAV; public books do not post it."""
    q, price, cash, dividend, bonus = 100, 10, 2000, 1, 0
    ex_price = (price - dividend) / (1 + bonus)
    receivable = q * dividend
    design_ex_equity = cash + q * ex_price + receivable
    paid_cash, paid_receivable = cash + receivable, 0
    assert (ex_price, receivable, design_ex_equity) == (9, 100, 3000)
    assert (paid_cash, paid_receivable) == (2100, 0)
    assert paid_cash + q * ex_price + paid_receivable == design_ex_equity

    # Day 3 is ex-date; day 4 is the design pay-date only. Production receives
    # its existing ratio map, which carries neither receivables nor pay events.
    # Default 10bp charges 1 on the prior 1000 buy. Start with 3001 so the
    # event oracle begins after that fee, with exactly 2000 cash / 3000 equity.
    state = _d2_book_run(
        engine, [price, price, ex_price, ex_price],
        exdiv={CODE: {"20251105": ex_price / price}},
        total_cash=3001, daily_quota=1000, name_budget=1000,
    )
    lot, = state.positions[CODE]
    assert (lot.shares, lot.cost, state.cash) == (q, ex_price, cash)
    assert state.equity_curve[:2] == [("20251103", 3000), ("20251104", 3000)]
    assert state.equity_curve[2:] == [("20251105", 2900), ("20251106", 2900)]
    assert design_ex_equity - state.equity_curve[-1][1] == receivable
    assert [trade["side"] for trade in state.trades] == ["BUY", "EOD_MARK"]
    assert [trade["commission"] for trade in state.trades] == [1, 0]


def test_d6_design_only_mixed_bonus_cash_equity_oracle():
    """δ6_design_oracle B5: mixed rights need explicit b/c, not q/k plus cash."""
    q, price, cash, bonus, dividend = 100, 10, 2000, 1, 1
    ex_price = Fraction(price - dividend, 1 + bonus)
    design_shares, receivable = q * (1 + bonus), q * dividend
    assert (design_shares, ex_price, receivable) == (200, Fraction(9, 2), 100)
    assert cash + design_shares * ex_price + receivable == 3000
    k = ex_price / price
    assert q / k != design_shares
    # q/k already preserves pre-event stock value; adding cash rights double counts.
    assert cash + (q / k) * ex_price + receivable == 3100


def test_d6_design_only_k_non_identifiability():
    """δ6_design_oracle B5: identical k cannot identify cash versus bonus rights."""
    q, price, cash = 100, 10, 2000
    structures = []
    for bonus, dividend in [(Fraction(0), Fraction(1)), (Fraction(1, 9), Fraction(0))]:
        ex_price = (price - dividend) / (1 + bonus)
        shares, receivable = q * (1 + bonus), q * dividend
        assert ex_price == 9 and ex_price / price == Fraction(9, 10)
        assert cash + shares * ex_price + receivable == 3000
        structures.append((shares, receivable))
    assert structures == [(100, 100), (Fraction(1000, 9), 0)]
    assert structures[0] != structures[1]  # No real fractional-share entitlement claim.


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("bonus,cash,price", [(1, 0, 5), (0, 1, 9), (1, 1, 4.5)])
def test_d6_public_book_production_conservation(engine, bonus, cash, price):
    from backtest.research.ashare_exdiv_economics import ExDivEvent

    events = {(CODE, "20251105"): ExDivEvent("rights", bonus, cash, "20251105", "20251106")}
    args = dict(exdiv={CODE: {"20251105": price / 10}}, total_cash=3001,
                daily_quota=1000, name_budget=1000, exdiv_economics=events)
    on_ex = _d2_book_run(engine, [10, 10, price], **args)
    pos, = on_ex.positions[CODE]
    assert (pos.shares, pos.cost, pos.peak, on_ex.cash) == (100 * (1 + bonus), price, price, 2000)
    assert on_ex.exdiv_economics.receivable_total == 100 * cash
    assert [value for _, value in on_ex.equity_curve] == [3000] * 3
    paid = _d2_book_run(engine, [10, 10, price, price], **args)
    assert paid.cash == 2000 + 100 * cash and paid.exdiv_economics.receivable_total == 0
    assert [value for _, value in paid.equity_curve] == [3000] * 4
    assert [(t["side"], t["commission"]) for t in paid.trades] == [("BUY", 1), ("EOD_MARK", 0)]
    assert paid.stats["exdiv_adjusted_lots"] == 1


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_d6_book_empty_invalid_lookup_does_not_invent_from_k(engine):
    kwargs = dict(exdiv=EXDIV_HALF, total_cash=3001, daily_quota=1000)
    off = _d2_book_run(engine, [10, 10, 5], **kwargs)
    for events in (None, {}, lambda *_: None, {(CODE, "20251105"): {"bonus_ratio": 1}}):
        state = _d2_book_run(engine, [10, 10, 5], exdiv_economics=events, **kwargs)
        assert state.positions == off.positions
        assert (state.cash, state.equity_curve, state.trades) == (off.cash, off.equity_curve, off.trades)
        assert state.stats.get("exdiv_econ_invalid_event", 0) == int(isinstance(events, dict) and bool(events))


@pytest.mark.parametrize("engine,missing", [(daily, "daily"), (minute, "daily"), (minute, "minute")])
def test_d6_book_missing_ex_bar_is_not_replayed(engine, missing):
    from backtest.research.ashare_exdiv_economics import ExDivEvent

    state = _d2_book_run(
        engine, [10, 10, 5, 5], missing=missing, stop_pct=0.0, exdiv=EXDIV_HALF,
        exdiv_economics={(CODE, "20251105"): ExDivEvent("rights", 1, 1, "20251105", "20251106")},
        total_cash=3001, daily_quota=1000,
    )
    assert (state.positions[CODE][0].shares, state.cash) == (100, 2000)
    assert state.exdiv_economics.applied_ids == set()


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_d6_book_cash_event_without_k_and_pay_after_exit(engine):
    from backtest.research.ashare_exdiv_economics import ExDivEvent

    # Small explicit cash event works without any reference-map event/noise gate.
    # Next-day price decline exits the old shares; pay_date still posts to cash.
    state = _d2_book_run(
        engine, [10, 10, 9.99, 9.7, 9.7], total_cash=3001, daily_quota=1000,
        exdiv_economics={(CODE, "20251105"): ExDivEvent("cash", 0, .01, "20251105", "20251107")},
    )
    assert not state.positions
    assert state.stats.get("exdiv_adjusted_lots", 0) == 0
    assert state.cash == pytest.approx(2970.03)  # 2000 + 970 - .97 + 1
    assert state.exdiv_economics.receivable_total == 0
    assert state.equity_curve[2][1] == 3000
    assert state.equity_curve[-1][1] == state.equity_curve[-2][1]
    assert [t["side"] for t in state.trades] == ["BUY", "SELL"]


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
@pytest.mark.parametrize("factor", [None, EXDIV_HALF])
def test_d6_book_off_byte_snapshot_with_p2_b_labels(engine, factor):
    import hashlib
    import json

    # Human GO P2=B: full book snapshots gain only the two label keys.
    # Removing them reproduces the original frozen f145ffde hashes exactly.
    expected = {
        (daily, False): "42554d791ff405f3f90fd186eea84f0713e34925e73b29fe01f733893e00c3b8",
        (daily, True): "4b27fbaa6cf3d060016f258145f9290b4fb08b6e02f21b053afb2279177cb163",
        (minute, False): "2dbed1ca050c17d552683e49ea23d5db532072de137dbdae1e8e12cbd2b391a4",
        (minute, True): "b128ee6a2b616da77942622f2b31c14cd1842eee9574d12fe8a4c5524b708ad9",
    }
    for kwargs in ({}, {"exdiv_economics": None}, {"exdiv_economics": {}}):
        state = _d2_book_run(engine, [10, 10, 5], exdiv=factor,
                             total_cash=3001, daily_quota=1000, **kwargs)
        snapshot = {"cash": state.cash, "positions": {k: [asdict(p) for p in v]
                    for k, v in state.positions.items()}, "trades": state.trades,
                    "equity": state.equity_curve, "stats": state.stats}
        assert hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest() == expected[engine, bool(factor)]


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_d6_book_public_bonus_t1_and_following_sale(engine):
    from backtest.research.ashare_exdiv_economics import ExDivEvent

    args = dict(exdiv=EXDIV_HALF, total_cash=3001, daily_quota=1000,
                exdiv_economics={(CODE, "20251105"): ExDivEvent("bonus", 1, 0, "20251105", "20251105")})
    on_ex = _d2_book_run(engine, [10, 10, 4.8], **args)
    assert on_ex.positions[CODE][0].shares == 100
    assert [(t["shares"], t["commission"]) for t in on_ex.trades if t["side"] == "SELL"] == [(100, .48)]
    after = _d2_book_run(engine, [10, 10, 4.8, 4.8], **args)
    assert not after.positions
    assert [(t["date"], t["shares"]) for t in after.trades if t["side"] == "SELL"] == [
        ("20251105", 100), ("20251106", 100)]
    assert after.cash == pytest.approx(2959.04)


@pytest.mark.parametrize("engine", [daily, minute], ids=["daily", "minute"])
def test_d6_book_exday_pool_add_has_no_entitlement(engine):
    from backtest.research.ashare_exdiv_economics import ExDivEvent

    state = _d2_book_run(
        engine, [10, 10, 5], strategy="version8", pool={"20251103": [CODE], "20251105": [CODE]},
        name_budget=1000, exdiv=EXDIV_HALF,
        exdiv_economics={(CODE, "20251105"): ExDivEvent("bonus", 1, 0, "20251105", "20251105")},
    )
    assert [(p.entry_idx, p.shares) for p in state.positions[CODE]] == [(0, 200), (2, 200)]
    assert state.stats["exdiv_econ_bonus_shares"] == 100
