# -*- coding: utf-8 -*-
"""NP1(a) capital-ration probe (tmp_path synthetic fixture; data-free)."""

from __future__ import annotations

import json
from pathlib import Path

from backtest.research.capital_ration_probe import (
    format_report_json,
    main,
    report_capital_ration,
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    pool = tmp_path / "pool"
    _write(
        pool / "20251103.csv",
        "代码,名称\n000001,平安\n000002,万科\n600000,浦发\n600001,邯郸\n600002,齐鲁\n",
    )
    _write(pool / "20251104.csv", "600000,浦发\n")
    trades = tmp_path / "trades.csv"
    _write(
        trades,
        "date,code,side,price,shares,notional,commission,reason,lot\n"
        "20251103,000001.SZ,BUY,10.0,100,1000.0,1.0,pool,0\n"
        "2025-11-03,000002.SZ,BUY,10.0,100,1000.0,1.0,pool,0\n"
        "20251103,600000.SH,SELL,10.0,100,1000.0,1.0,trail:T+1,0\n"
        "20251104,600000.SH,BUY,11.0,100,1100.0,1.1,chase:T+1,0\n",
    )
    return trades, pool


def test_day_attribution_ranks_and_totals(tmp_path: Path):
    trades, pool = _fixture(tmp_path)
    report = report_capital_ration(trades, pool, cash_cap_names=3)
    by_day = {d.date: d for d in report.per_day}
    d0 = by_day["20251103"]
    assert d0.width == 5
    assert d0.allocated == 2
    assert d0.not_allocated_count == 3
    assert d0.not_allocated_ranks == [2, 3, 4]
    assert d0.not_allocated_codes == ["600000.SH", "600001.SH", "600002.SH"]
    assert d0.chase_buys == 0
    assert d0.wide_day is True

    d1 = by_day["20251104"]
    assert d1.width == 1
    assert d1.allocated == 0  # chase only; not reason=pool
    assert d1.not_allocated_ranks == [0]
    assert d1.chase_buys == 1
    assert d1.wide_day is False

    assert report.total_planned_slots == 6
    assert report.total_allocated_pool == 2
    assert report.total_not_allocated == 4
    assert report.days_with_pool == 2
    assert report.wide_days == 1
    assert report.total_chase_buys == 1
    assert report.chase_buys_by_day == {"20251104": 1}
    assert report.not_allocated_rank_histogram == {0: 1, 2: 1, 3: 1, 4: 1}


def test_json_format_and_cli_exit_zero(tmp_path: Path, capsys):
    trades, pool = _fixture(tmp_path)
    report = report_capital_ration(trades, pool)
    payload = json.loads(format_report_json(report))
    assert payload["total_allocated_pool"] == 2
    assert "attribution_note" in payload
    assert payload["per_day"][0]["not_allocated_ranks"] == [2, 3, 4]

    assert main([
        "--trades", str(trades),
        "--pool-dir", str(pool),
        "--format", "json",
        "--cash-cap-names", "21",
    ]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["days_with_pool"] == 2
    assert out["wide_days"] == 0


def test_start_end_window(tmp_path: Path):
    trades, pool = _fixture(tmp_path)
    report = report_capital_ration(trades, pool, start="20251103", end="20251103")
    assert report.days_with_pool == 1
    assert report.per_day[0].date == "20251103"
    assert report.total_chase_buys == 0  # chase on 20251104 filtered out
