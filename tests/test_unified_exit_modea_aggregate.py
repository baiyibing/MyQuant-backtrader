# -*- coding: utf-8 -*-
"""Mode A aggregation: total return / drawdown / peak concurrency (hand-calc)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.research import unified_exit_modea as m


SESSIONS = ["20251103", "20251104", "20251105", "20251106"]


def _frame(dates: list[str], closes: list[float], opens: list[float] | None = None) -> pd.DataFrame:
    opens = opens or closes
    return pd.DataFrame(
        {
            "open": opens,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
        },
        index=pd.to_datetime(dates),
    ).astype(np.float64)


def _write_pool(pool_dir: Path, ymd: str, rows: list[tuple[str, str]]) -> None:
    pool_dir.mkdir(parents=True, exist_ok=True)
    (pool_dir / f"{ymd}.csv").write_text(
        "\n".join(f"{b},{n}" for b, n in rows) + "\n", encoding="utf-8"
    )


def test_aggregate_total_return_and_peak_lots():
    """Two lots: buy day0 @10, sell day1 @11; buy day1 @10, mark day3 @10.

    Cash pool 3e6 for readable hand calc (still Mode A math).
    """
    cash = 3_000_000.0
    insts = [
        m.Instance("600000.SH", "A", "20251103", 10.0, True, None),
        m.Instance("600001.SH", "B", "20251104", 10.0, True, None),
    ]
    bars = {
        "600000.SH": _frame(
            ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06"],
            [10.0, 11.0, 11.0, 11.0],
        ),
        "600001.SH": _frame(
            ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06"],
            [10.0, 10.0, 10.0, 10.0],
        ),
    }
    exits = {
        "600000.SH|20251103": m.evaluate_exit(
            insts[0], m.StrategySpec(1, 1), bars, SESSIONS, end="20251106"
        ),
        "600001.SH|20251104": m.evaluate_exit(
            insts[1], m.StrategySpec(0, None), bars, SESSIONS, end="20251106"
        ),
    }
    # First lot sells on 11/04; second still open → peak lots >= 1
    metrics = m.aggregate_strategy(
        "mix", insts, exits, bars, SESSIONS, cash_pool=cash
    )
    assert metrics.n_instances == 2
    assert metrics.peak_concurrent_lots >= 1
    assert metrics.peak_concurrent_capital == metrics.peak_concurrent_lots * m.LOT_NOTIONAL

    # Hand equity end:
    # day0 buy A: cash -= 100000*10*1.001 = 1_001_000 → cash=1_999_000; mtm=1_000_000
    # day1 sell A: cash += 100000*11*0.999 = 1_098_900 → cash=3_097_900
    #      buy B: cash -= 1_001_000 → cash=2_096_900; mtm=1_000_000; eq=3_096_900
    # day2/3 mark B at 10: eq = 2_096_900 + 1_000_000 = 3_096_900
    expect_final = 3_096_900.0
    expect_ret = (expect_final - cash) / cash
    assert metrics.total_return == pytest.approx(expect_ret, rel=1e-9)
    assert metrics.total_pnl == pytest.approx(
        exits["600000.SH|20251103"].pnl + exits["600001.SH|20251104"].pnl
    )


def test_max_drawdown_from_equity_curve():
    rows = [
        {"equity": 100.0},
        {"equity": 120.0},
        {"equity": 90.0},  # dd = (120-90)/120 = 0.25
        {"equity": 100.0},
    ]
    assert m._max_drawdown(rows) == pytest.approx(0.25)


def test_annualize_formula():
    r = 0.10
    assert m._annualize(r) == pytest.approx((1.1) ** (365 / 322) - 1)


def test_oracle_picks_best_non_limit_down_day():
    inst = m.Instance("600000.SH", "A", "20251103", 10.0, True, None)
    bars = {
        "600000.SH": _frame(
            ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06"],
            [10.0, 10.5, 12.0, 11.0],
        )
    }
    got = m.oracle_exits([inst], bars, SESSIONS, end="20251106")
    er = got["600000.SH|20251103"]
    assert er.sell_date == "20251105"
    assert er.sell_price == pytest.approx(12.0)
    assert er.reason == "oracle"


def test_delist_zero_sensitivity():
    inst = m.Instance("600000.SH", "A", "20251103", 10.0, True, None)
    bars = {"600000.SH": _frame(["2025-11-03", "2025-11-04"], [10.0, 10.2])}
    base = {
        "600000.SH|20251103": m.evaluate_exit(
            inst, m.StrategySpec(1, 20), bars, SESSIONS, end="20251106"
        )
    }
    assert base["600000.SH|20251103"].reason == "mark_end"
    sens = m.delisting_zero_exits([inst], base, SESSIONS, end="20251106")
    er = sens["600000.SH|20251103"]
    assert er.reason == "mark_end_zero"
    assert er.sell_price == 0.0
    assert er.return_pct == -1.0


def test_next_open_buy_shifts_price(tmp_path: Path):
    inst = m.Instance("600000.SH", "A", "20251103", 10.0, True, None)
    bars = {
        "600000.SH": _frame(
            ["2025-11-03", "2025-11-04", "2025-11-05"],
            [10.0, 10.5, 10.6],
            opens=[10.0, 10.2, 10.3],
        )
    }
    got = m.next_open_buy_instances([inst], bars, SESSIONS)
    assert got[0].opened is True
    assert got[0].list_date == "20251104"
    assert got[0].buy_price == pytest.approx(10.2)


def test_run_modea_end_to_end_synthetic(tmp_path: Path):
    pool = tmp_path / "pool"
    _write_pool(pool, "20251103", [("600000", "SYN")])
    _write_pool(pool, "20251104", [("600000", "SYN")])
    bars = {
        "600000.SH": _frame(
            ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06"],
            [10.0, 10.3, 10.1, 10.2],
            opens=[10.0, 10.1, 10.0, 10.1],
        )
    }
    out = tmp_path / "out"
    result = m.run_modea(
        pool,
        start="20251103",
        end="20251106",
        sessions=SESSIONS,
        bars=bars,
        out_dir=out,
        cash_pool=5_000_000.0,
    )
    assert (out / "ranking.csv").is_file()
    assert (out / "summary.json").is_file()
    assert (out / "instance_detail_top.csv").is_file()
    assert len(result["ranked"]) >= 8
    assert "anchor_hold_end" in result["anchors"]
    assert result["anchors"]["oracle"].total_return >= result["anchors"]["r1_n1"].total_return
