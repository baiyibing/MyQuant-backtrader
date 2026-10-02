# -*- coding: utf-8 -*-
"""Smoke + parity: docs/backtest/ssot preferred profiles ↔ market_layer."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from backtest.research import market_layer
from backtest.research.ssot_limits_loader import (
    PREFERRED_BOARD_PROFILE,
    PREFERRED_TICK_PROFILE,
    PRICE_TICK,
    SSOT_DIR,
    board_pct_from_ssot,
    load_preferred_limits_ssot,
    preferred_board_profile,
    preferred_tick_profile,
)


def test_ssot_dir_exists_and_preferred_profiles_load():
    assert SSOT_DIR.is_dir()
    ssot = load_preferred_limits_ssot()
    assert ssot.board_profile_id == PREFERRED_BOARD_PROFILE
    assert ssot.tick_profile_id == PREFERRED_TICK_PROFILE
    assert ssot.price_tick == PRICE_TICK == Decimal("0.01")
    assert ssot.rounding_mode == "ROUND_HALF_UP"
    assert ssot.st_cutover_name == "ST_MAIN_LIMIT_PCT_SWITCH"
    assert ssot.st_cutover_date == date(2026, 7, 6)
    assert ssot.st_cutover_inclusive is True
    assert "return_null" in ssot.unknown_board_policy
    board = preferred_board_profile()
    tick = preferred_tick_profile()
    assert board["bands"]
    assert tick["rounding_mode"] == "ROUND_HALF_UP"


def test_cutover_matches_market_layer_constant():
    ssot = load_preferred_limits_ssot()
    assert market_layer.ST_MAIN_LIMIT_PCT_SWITCH == ssot.st_cutover_date


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("600000.SH", 0.10),  # main
        ("300001.SZ", 0.20),  # ChiNext
        ("688001.SH", 0.20),  # STAR
        ("920014.BJ", 0.30),  # BJ
        ("159001.SZ", None),  # unknown / fail-closed
    ],
)
def test_parity_board_limit_pct(code, expected):
    assert board_pct_from_ssot(code) == expected
    assert market_layer.board_limit_pct(code) == expected
    assert market_layer.limit_pct(code, "") == expected


@pytest.mark.parametrize(
    ("code", "name", "as_of", "expected"),
    [
        ("600000.SH", "*ST 测试", date(2026, 7, 5), 0.05),
        ("600000.SH", "*ST 测试", "20260705", 0.05),
        ("600000.SH", "*ST 测试", date(2026, 7, 6), 0.10),
        ("600000.SH", "*ST 测试", "20260706", 0.10),
        ("300001.SZ", "ST华仪", date(2026, 7, 5), 0.20),
        ("300001.SZ", "ST华仪", date(2026, 7, 6), 0.20),
        ("920014.BJ", "ST北交", date(2026, 7, 5), 0.30),
        ("920014.BJ", "ST北交", date(2026, 7, 6), 0.30),
        ("159001.SZ", "", None, None),
    ],
)
def test_parity_limit_pct_st_and_unknown(code, name, as_of, expected):
    assert market_layer.limit_pct(code, name, as_of=as_of) == expected


def test_parity_tick_half_up_worked_example():
    ssot = load_preferred_limits_ssot()
    ex = ssot.worked_example_half_up
    assert ex["prev_close"] == 10.05
    assert ex["pct"] == 0.10
    assert ex["limit_up_HALF_UP"] == 11.06
    assert ex["limit_down_HALF_UP"] == 9.05

    # Main non-ST @ 10% uses the same fen HALF_UP path as JSON.
    assert market_layer.limit_prices("600000.SH", 10.05) == (11.06, 9.05)
    assert market_layer.round_fen(11.055) == 11.06
    assert market_layer.round_fen(9.045) == 9.05

    # Identity with Decimal ROUND_HALF_UP contract in JSON.
    step = ssot.price_tick
    up = (Decimal(str(ex["prev_close"])) * (Decimal("1") + Decimal(str(ex["pct"])))).quantize(
        step, rounding=ROUND_HALF_UP
    )
    down = (Decimal(str(ex["prev_close"])) * (Decimal("1") - Decimal(str(ex["pct"])))).quantize(
        step, rounding=ROUND_HALF_UP
    )
    assert float(up) == 11.06
    assert float(down) == 9.05
