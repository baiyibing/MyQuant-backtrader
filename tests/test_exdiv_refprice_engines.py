# -*- coding: utf-8 -*-
"""E-R6 ex-div refprice engine vectors (arch T1–T16; required subset locked)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest.research.csv_daily_backtest as daily
import backtest.research.csv_minute_backtest as minute
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
