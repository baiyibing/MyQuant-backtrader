"""Duplicate-hm rows keep row-local predicates under open-before-close scheduling."""

from decimal import Decimal

import numpy as np
import pytest
from backtest.research import csv_minute_backtest as minute
from backtest.research.minute_cash_order import HeldMinuteCursor

from tests.minute_cash_fixtures import chronological_case, money


@pytest.mark.parametrize("opens", [(10.0, 9.0), (9.0, 10.0)])
@pytest.mark.parametrize("enabled", [False, True], ids=["off", "on"])
def test_duplicate_hm_limit_open_only_skips_its_own_close(opens, enabled):
    case = chronological_case(sell_hm=895)
    code = "600000.SH"
    frame = case["minute_bars"][code]
    frame.loc[1:, "hm"] = 895
    frame.loc[1:, "open"] = opens
    frame.loc[1:, "close"] = 9.4
    frame.loc[1:, "low"] = np.minimum(opens, 9.4)
    case["pool_days"].pop("20251105")
    state = minute.simulate(**case, fix_minute_cash_order=enabled)

    assert [(t["code"], t["side"], t["shares"]) for t in state.trades] == [
        (code, "BUY", 100), (code, "SELL", 100),
    ]
    assert state.trades[-1]["reason"] == "stop_loss:touch"
    assert state.trades[-1]["price"] == 9.4
    assert money(state.cash) == Decimal("939.06")
    assert not state.positions


def phased_scan(cursor):
    """Replay the scheduler's complete open phase before each hm's close phase."""
    for hm in np.unique(cursor.hm):
        indices = np.flatnonzero(cursor.hm == hm)
        for phase in ("open", "close"):
            for idx in indices:
                event = cursor.advance(int(idx), phase)
                if event is not None:
                    return (*event, cursor.peak, cursor.peak_hm)
    return -1, float("nan"), "", cursor.peak, cursor.peak_hm


def assert_scanner_parity(o, h, c, hm, **options):
    expected_reserve, actual_reserve = {}, {}
    expected_exit, actual_exit = {}, {}
    expected = minute.scan_held_day_python(
        o, h, c, hm=hm, reserve_state=expected_reserve, exit_state=expected_exit, **options
    )
    cursor = HeldMinuteCursor(
        o, h, c, hm=hm, reserve_state=actual_reserve, exit_state=actual_exit, **options
    )
    actual = phased_scan(cursor)
    assert (actual[0], actual[2:]) == (expected[0], expected[2:])
    if expected[0] >= 0:
        assert actual[1] == expected[1]
    assert cursor.first_exit_attempted == (expected[0] >= 0)
    assert actual_reserve == expected_reserve
    assert actual_exit == expected_exit
    return actual


@pytest.mark.parametrize("peak_gap_min", [0, 15])
def test_duplicate_hm_close_uses_its_own_peak_and_peak_clock(peak_gap_min):
    # The later high must neither trigger an earlier close nor block a mature
    # peak's earlier exit by resetting its peak_hm to this minute.
    result = assert_scanner_parity(
        np.array([10.0, 10.0]), np.array([10.2, 12.0]), np.array([10.1, 10.1]),
        np.array([895, 895]), cost=10, peak=11 if peak_gap_min else 10,
        peak_hm=570, n_days=1, can_sell=True, stop_pct=None,
        profit_base=0.05, trail_ratio=0.5, peak_gap_min=peak_gap_min,
    )
    assert result[0] == (0 if peak_gap_min else 1)
    assert result[3:] == ((11, 570) if peak_gap_min else (12, 895))


def test_duplicate_hm_no_exit_keeps_latest_observed_peak():
    cursor = HeldMinuteCursor(
        np.array([10, 10]), np.array([11, 12]), np.array([10, 10]),
        hm=np.array([895, 895]), cost=10, peak=10, n_days=1, can_sell=True,
        stop_pct=None, profit_base=100, trail_ratio=0,
    )
    assert cursor.advance(0, "open") is None
    assert cursor.advance(1, "open") is None
    assert cursor.advance(0, "close") is None
    assert (cursor.peak, cursor.peak_hm) == (12, 895)
    assert cursor.advance(1, "close") is None
    assert (cursor.peak, cursor.peak_hm) == (12, 895)


def test_duplicate_hm_later_gap_open_still_precedes_earlier_close():
    # Phase precedence intentionally differs from the row-wise OFF scanner
    # when one row has a close exit and a later row has a gap-open exit.
    cursor = HeldMinuteCursor(
        np.array([10, 9.3]), np.array([10, 11]), np.array([9.4, 9.3]),
        hm=np.array([895, 895]), cost=10, peak=10, n_days=1, can_sell=True,
        stop_pct=0.05, profit_base=0, trail_ratio=0, limit_down=9,
    )
    assert phased_scan(cursor) == (1, 9.3, "stop_loss:gap_open", 11, 895)


@pytest.mark.parametrize("mode", ["stop", "trail", "reserve", "defer", "clear", "force",
                                  "take_profit", "exit_plan", "sell_gate"])
def test_duplicate_hm_phased_cursor_matches_scanner_fuzz(mode):
    """Compare 900 seeded multi-row days without competing gap-open candidates.

    A later-row gap-open has intentional phase priority, tested separately.
    Limit-down opens are included because they skip their own close only.
    """
    rng = np.random.default_rng(204)
    for _ in range(100):
        hm = np.repeat([570, 585, 895, int(rng.choice([899, 900]))], rng.integers(2, 5, 4))
        o = rng.choice([9.0, 9.6, 10.0, 11.0], len(hm))
        c = rng.choice([9.0, 9.4, 10.0, 10.5, 11.0], len(hm))
        h = np.maximum(o, c) + rng.choice([0.0, 0.1, 1.0], len(hm))
        options = {
            "cost": 10,
            "peak": float(rng.choice([10, 12])),
            "peak_hm": -1,
            "n_days": int(rng.choice([0, 1, 5, 8])),
            "can_sell": bool(rng.integers(0, 5)),
            "stop_pct": 0.05 if mode == "stop" else None,
            "profit_base": 0.05,
            "trail_ratio": 0.5,
            "limit_down": 9,
            "limit_up": 11,
            "peak_gap_min": int(rng.choice([0, 15])),
        }
        if mode in ("reserve", "defer"):
            options[f"{mode}_limit_up"] = True
            options["reserved"] = bool(rng.integers(0, 2))
        elif mode == "clear":
            options["close_clear"] = lambda cost, peak, days: "clear" if peak < 12 else None
        elif mode == "force":
            options["force_sell_hm"] = 895
        elif mode == "take_profit":
            options["take_profit"] = minute.apply_csv_strategy("version8")["take_profit"]
        elif mode == "exit_plan":
            options["exit_plan"] = lambda code, close, *_: ("partial", 100) if close < 10 else None
        elif mode == "sell_gate":
            options["sell_gate"] = lambda code, close, *_: "gate" if close < 10 else None
        assert_scanner_parity(o, h, c, hm, **options)
