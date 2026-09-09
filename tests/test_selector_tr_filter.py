# -*- coding: utf-8 -*-
"""M-004 · strategies.tr_filter unit tests (RFC-003 M-1 §6)."""

from __future__ import annotations

import pandas as pd
import pytest

from common import ConfigurationError
from strategies.tr_filter import apply_turnover_resistance_filter


def _row(
    code: str,
    *,
    tr: float = 25.0,
    bb_position: float = 0.6,
    tr_bb_position: float = 0.7,
) -> dict[str, object]:
    return {
        "stock_code": code,
        "trade_date": "20260618",
        "turnover_resistance": tr,
        "bb_position": bb_position,
        "tr_bb_position": tr_bb_position,
        "tr_bb_middle": 3.0,
        "tr_bb_upper": 4.0,
        "tr_bb_lower": 2.0,
        "bands_computed_at": 1.0,
        "window": 1000,
    }


def _cross_section(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def test_normal_filter_keeps_matching_only() -> None:
    cross = _cross_section(
        _row("600000.SH"),
        _row("600001.SH", tr=5.0),
        _row("600002.SH", bb_position=0.3),
    )
    out = apply_turnover_resistance_filter(
        ["600000.SH", "600001.SH", "600002.SH"],
        cross,
        fail_closed=False,
    )
    assert out == ["600000.SH"]


def test_fail_closed_empty_cross_section() -> None:
    with pytest.raises(ConfigurationError, match="empty"):
        apply_turnover_resistance_filter(["600000.SH"], pd.DataFrame(), fail_closed=True)


def test_fail_open_empty_cross_section_returns_all() -> None:
    out = apply_turnover_resistance_filter(
        ["600000.SH", "600001.SH"],
        pd.DataFrame(),
        fail_closed=False,
    )
    assert out == ["600000.SH", "600001.SH"]


def test_window_80_rule_without_80_suffix_raises() -> None:
    cross = _cross_section(_row("600000.SH"))
    with pytest.raises(ValueError, match="_80"):
        apply_turnover_resistance_filter(
            ["600000.SH"],
            cross,
            window=80,
            rule="resist_tr_bb_1000",
        )


def test_resist_tr_bb_80_window_passes() -> None:
    cross = _cross_section(_row("600000.SH"))
    out = apply_turnover_resistance_filter(
        ["600000.SH"],
        cross,
        window=80,
        rule="resist_tr_bb_80",
        fail_closed=True,
    )
    assert out == ["600000.SH"]


def test_fail_closed_missing_candidate_row() -> None:
    cross = _cross_section(_row("600000.SH"))
    with pytest.raises(ConfigurationError, match="missing cross_section"):
        apply_turnover_resistance_filter(
            ["600000.SH", "600999.SH"],
            cross,
            fail_closed=True,
        )


def test_tr_breakout_rule() -> None:
    row = _row("600000.SH", tr=50.0, tr_bb_position=0.9)
    cross = _cross_section(row)
    out = apply_turnover_resistance_filter(
        ["600000.SH"],
        cross,
        rule="tr_breakout",
        fail_closed=True,
    )
    assert out == ["600000.SH"]
