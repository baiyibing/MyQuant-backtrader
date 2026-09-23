"""Joint buy-state sidecar: oral OR, $winratio, CLI consume; score_exit refuses."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from backtest.research.csv_strategy_books import apply_csv_strategy, get_book
from backtest.research.strategy_topk_dropout_rules import HELP_LOCK as TOPK_HELP
from backtest.research.strategy_topk_score_exit_rules import HELP_LOCK as SX_HELP
from backtest.research.topk_dropout_eligibility import (
    buy_state_oral_ok,
    load_buy_state_sidecar,
    make_eligible_buy,
    weekly_ma_asof,
    with_ma5_gate,
    with_week_ma_gate,
)
from backtest.research.topk_dropout_rules import decide_topk_dropout


def test_oral_ok_cond1_winratio_lt_not_quantile():
    assert buy_state_oral_ok(9.0, 10.0, 11.0, 0.09) is True
    assert buy_state_oral_ok(9.0, 10.0, 11.0, 0.10) is False
    assert buy_state_oral_ok(9.0, 10.0, 11.0, 0.50) is False


def test_oral_ok_cond2_is_close_gt_ma20_no_ma5():
    assert buy_state_oral_ok(11.0, 10.0, 12.0, 0.99) is True
    assert buy_state_oral_ok(10.0, 10.0, 9.0, 0.01) is False
    assert buy_state_oral_ok(9.5, 10.0, 9.0, 0.01) is False


def test_oral_ok_nan_and_inf_fail_closed():
    nan = float("nan")
    assert buy_state_oral_ok(nan, 10.0, 11.0, 0.01) is False
    assert buy_state_oral_ok(9.0, 10.0, 11.0, nan) is False
    assert buy_state_oral_ok(float("inf"), 10.0, 11.0, 0.01) is False


def test_load_sidecar_csv_and_missing_row(tmp_path: Path):
    p = tmp_path / "buy_state.csv"
    p.write_text(
        "trade_date,code,close,ma20,ma60,winratio\n"
        "2026-01-06,SH600010,9.0,10.0,11.0,0.05\n"
        "2026-01-06,600011.SH,11.0,10.0,12.0,0.90\n"
        "2026-01-06,600012.SH,9.5,10.0,9.0,0.01\n",
        encoding="utf-8",
    )
    got = load_buy_state_sidecar(p)
    assert got[("600010.SH", "20260106")] == (9.0, 10.0, 11.0, 0.05)
    fn = make_eligible_buy(buy_state_by_key=got)
    assert fn("600010.SH", "20260106") is True
    assert fn("600011.SH", "20260106") is True
    assert fn("600012.SH", "20260106") is False
    assert fn("600099.SH", "20260106") is False


def test_load_sidecar_parquet_dollar_columns(tmp_path: Path):
    p = tmp_path / "buy_state.parquet"
    pd.DataFrame(
        {
            "date": ["20260106"],
            "instrument": ["SZ000001"],
            "$close": [8.0],
            "Mean($close, 20)": [9.0],
            "Mean($close, 60)": [9.5],
            "$winratio": [0.02],
        }
    ).to_parquet(p)
    got = load_buy_state_sidecar(p)
    assert ("000001.SZ", "20260106") in got
    assert got[("000001.SZ", "20260106")][3] == pytest.approx(0.02)


def test_walk_down_skips_fail_closed_buy_state():
    day = "20260106"
    scores = {
        "600000.SH": 10.0,
        "600001.SH": 9.0,
        "600010.SH": 8.0,
        "600011.SH": 7.0,
    }
    held = ["600000.SH", "600001.SH"]
    raw_buy, _sell = decide_topk_dropout(held, scores, topk=3, n_drop=1)
    assert raw_buy[0] == "600010.SH"
    eligible = make_eligible_buy(
        buy_state_by_key={
            ("600011.SH", day): (11.0, 10.0, 12.0, 0.9),
        }
    )
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={day: scores},
        topk=3,
        n_drop=1,
        eligible_buy=eligible,
    )
    planned = hooks["planned_for_day"](day, held)
    assert planned[0] == "600011.SH"
    assert "600010.SH" not in planned


def test_run_kwargs_loads_buy_state_file(tmp_path: Path):
    scores_dir = tmp_path / "scores"
    scores_dir.mkdir()
    (scores_dir / "20260106.csv").write_text(
        "code,score\n600000,1.0\n", encoding="utf-8"
    )
    sidecar = tmp_path / "state.csv"
    sidecar.write_text(
        "trade_date,code,close,ma20,ma60,winratio\n"
        "20260106,600000.SH,11.0,10.0,12.0,0.2\n",
        encoding="utf-8",
    )
    ns = argparse.Namespace(
        pred_csv=None,
        scores_dir=scores_dir,
        stop_pct=None,
        topk=50,
        n_drop=5,
        st_daily_file=None,
        age_map_file=None,
        age_days=60,
        return_threshold_filter=False,
        stop_fill=None,
        buy_state_file=sidecar,
    )
    kw = get_book("topk_dropout").run_kwargs(ns)
    assert kw["eligible_buy"]("600000.SH", "20260106") is True
    assert kw["eligible_buy"]("600099.SH", "20260106") is False


def test_score_exit_refuses_buy_state_file(tmp_path: Path):
    ns = argparse.Namespace(
        pred_csv=None,
        scores_dir=tmp_path,
        stop_pct=None,
        topk=50,
        n_drop=5,
        buy_state_file=tmp_path / "x.csv",
    )
    with pytest.raises(SystemExit, match="refuses --buy-state-file"):
        get_book("topk_score_exit").run_kwargs(ns)


def test_above_ma20_turns_off_winratio_dip():
    rows = {
        ("600010.SH", "20260106"): (9.0, 10.0, 11.0, 0.05),
        ("600011.SH", "20260106"): (11.0, 10.0, 12.0, 0.99),
        ("600012.SH", "20260106"): (10.0, 10.0, 9.0, 0.01),
    }
    oral = make_eligible_buy(buy_state_by_key=rows, buy_state_rule="oral")
    above = make_eligible_buy(buy_state_by_key=rows, buy_state_rule="above-ma20")
    assert oral("600010.SH", "20260106") is True
    assert above("600010.SH", "20260106") is False
    assert above("600011.SH", "20260106") is True
    assert above("600012.SH", "20260106") is False


def test_run_kwargs_above_ma20_rejects_dip(tmp_path: Path):
    scores_dir = tmp_path / "scores"
    scores_dir.mkdir()
    (scores_dir / "20260106.csv").write_text(
        "code,score\n600010,1.0\n", encoding="utf-8"
    )
    sidecar = tmp_path / "state.csv"
    sidecar.write_text(
        "trade_date,code,close,ma20,ma60,winratio\n"
        "20260106,600010.SH,9.0,10.0,11.0,0.05\n"
        "20260106,600011.SH,11.0,10.0,12.0,0.90\n",
        encoding="utf-8",
    )
    ns = argparse.Namespace(
        pred_csv=None,
        scores_dir=scores_dir,
        stop_pct=None,
        topk=50,
        n_drop=5,
        st_daily_file=None,
        age_map_file=None,
        age_days=60,
        return_threshold_filter=False,
        stop_fill=None,
        buy_state_file=sidecar,
        buy_state_rule="above-ma20",
    )
    kw = get_book("topk_dropout").run_kwargs(ns)
    assert kw["eligible_buy"]("600010.SH", "20260106") is False
    assert kw["eligible_buy"]("600011.SH", "20260106") is True


def test_above_ma20_requires_sidecar():
    ns = argparse.Namespace(
        pred_csv=None,
        scores_dir=Path("."),
        stop_pct=None,
        topk=50,
        n_drop=5,
        st_daily_file=None,
        age_map_file=None,
        age_days=60,
        return_threshold_filter=False,
        stop_fill=None,
        buy_state_file=None,
        buy_state_rule="above-ma20",
    )
    with pytest.raises(SystemExit, match="requires --buy-state-file"):
        get_book("topk_dropout").run_kwargs(ns)


def _weeks(n: int, start: date = date(2025, 1, 6)) -> list[date]:
    """n Mon-Fri weeks. 2025-01-06 is a Monday, qlib's week label."""
    assert start.weekday() == 0
    days: list[date] = []
    for i in range(n):
        monday = start + timedelta(days=7 * i)
        days.extend(monday + timedelta(days=k) for k in range(5))
    return days


def test_weekly_ma_uses_qlib_week_open_close():
    days = _weeks(20)
    closes = {day: 10.0 for day in days}
    label = days[-5]
    closes[label] = 12.0
    got = weekly_ma_asof(closes)
    assert days[-6].strftime("%Y%m%d") not in got
    close, ma = got[label.strftime("%Y%m%d")]
    assert close == 12.0
    assert ma == pytest.approx((19 * 10.0 + 12.0) / 20)
    later_close, later_ma = got[days[-1].strftime("%Y%m%d")]
    assert later_close == 10.0
    assert later_ma == pytest.approx(ma)
    flat = weekly_ma_asof({day: 10.0 for day in days})
    flat_close, flat_ma = flat[label.strftime("%Y%m%d")]
    assert flat_close == flat_ma


def test_week_gate_blocks_until_close_is_above_week_ma():
    days = _weeks(20)
    label = days[-5]
    prices = [10.0] * len(days)
    prices[days.index(label)] = 12.0
    frame = pd.DataFrame({"close": prices}, index=pd.to_datetime(days))
    gate = with_week_ma_gate(lambda _c, _d: True, {"600000.SH": frame})
    assert gate("600000.SH", days[-6].strftime("%Y%m%d")) is False
    assert gate("600000.SH", label.strftime("%Y%m%d")) is True
    assert gate("600000.SH", days[-1].strftime("%Y%m%d")) is False
    flat = pd.DataFrame({"close": [10.0] * len(days)}, index=pd.to_datetime(days))
    equal = with_week_ma_gate(lambda _c, _d: True, {"600000.SH": flat})
    assert equal("600000.SH", label.strftime("%Y%m%d")) is False


def test_run_kwargs_week20_sets_gate(tmp_path: Path):
    scores_dir = tmp_path / "scores"
    scores_dir.mkdir()
    (scores_dir / "20260106.csv").write_text(
        "code,score\n600011,1.0\n", encoding="utf-8"
    )
    sidecar = tmp_path / "state.csv"
    sidecar.write_text(
        "trade_date,code,close,ma20,ma60,winratio\n"
        "20260106,600010.SH,9.0,10.0,11.0,0.05\n"
        "20260106,600011.SH,11.0,10.0,12.0,0.90\n",
        encoding="utf-8",
    )
    ns = argparse.Namespace(
        pred_csv=None,
        scores_dir=scores_dir,
        stop_pct=None,
        topk=50,
        n_drop=5,
        st_daily_file=None,
        age_map_file=None,
        age_days=60,
        return_threshold_filter=False,
        stop_fill=None,
        buy_state_file=sidecar,
        buy_state_rule="above-ma20-week20",
    )
    kw = get_book("topk_dropout").run_kwargs(ns)
    assert kw["week_ma_gate"] is True
    assert kw["eligible_buy"]("600010.SH", "20260106") is False
    assert kw["eligible_buy"]("600011.SH", "20260106") is True


def test_ma5_gate_needs_close_strictly_above_five_day_mean():
    days = [date(2026, 3, d) for d in (5, 6, 9, 10, 11, 12)]
    frame = pd.DataFrame(
        {"close": [10.0, 10.0, 10.0, 10.0, 10.0, 12.0]},
        index=pd.to_datetime(days),
    )
    gate = with_ma5_gate(lambda _c, _d: True, {"688031.SH": frame})
    assert gate("688031.SH", "20260310") is False
    assert gate("688031.SH", "20260311") is False
    assert gate("688031.SH", "20260312") is True
    low = pd.DataFrame(
        {"close": [10.0, 10.0, 10.0, 10.0, 10.0, 9.0]},
        index=pd.to_datetime(days),
    )

    def allow(code: str, buy_date: str) -> bool:
        del code, buy_date
        return True

    allow.list_ok = lambda _c, _d: True  # type: ignore[attr-defined]
    allow.seat_ok = lambda _c, _d: True  # type: ignore[attr-defined]
    blocked = with_ma5_gate(allow, {"688031.SH": low})
    assert blocked.list_ok("688031.SH", "20260312") is True
    assert blocked.seat_ok("688031.SH", "20260312") is False
    assert blocked("688031.SH", "20260312") is False


def test_run_kwargs_ma5_sets_both_gates(tmp_path: Path):
    scores_dir = tmp_path / "scores"
    scores_dir.mkdir()
    (scores_dir / "20260106.csv").write_text(
        "code,score\n600011,1.0\n", encoding="utf-8"
    )
    sidecar = tmp_path / "state.csv"
    sidecar.write_text(
        "trade_date,code,close,ma20,ma60,winratio\n"
        "20260106,600010.SH,9.0,10.0,11.0,0.05\n"
        "20260106,600011.SH,11.0,10.0,12.0,0.90\n",
        encoding="utf-8",
    )
    ns = argparse.Namespace(
        pred_csv=None,
        scores_dir=scores_dir,
        stop_pct=None,
        topk=50,
        n_drop=5,
        st_daily_file=None,
        age_map_file=None,
        age_days=60,
        return_threshold_filter=False,
        stop_fill=None,
        buy_state_file=sidecar,
        buy_state_rule="above-ma5-ma20-week20",
    )
    kw = get_book("topk_dropout").run_kwargs(ns)
    assert kw["week_ma_gate"] is True
    assert kw["ma5_gate"] is True
    assert kw["eligible_buy"]("600010.SH", "20260106") is False
    assert kw["eligible_buy"]("600011.SH", "20260106") is True


def test_minute_refuses_stop_fill_close():
    from backtest.research.csv_minute_backtest import run

    with pytest.raises(SystemExit, match="daily EOD"):
        run("20260106", "20260107", strategy="topk_dropout", stop_fill="close")


def test_help_lock_buy_state_and_winratio():
    assert "--buy-state-file" in TOPK_HELP
    assert "--buy-state-rule" in TOPK_HELP
    assert "above-ma20-week20" in TOPK_HELP
    assert "above-ma5-ma20-week20" in TOPK_HELP
    assert "above-ma20" in TOPK_HELP
    assert "$winratio" in TOPK_HELP
    assert "MA5" in TOPK_HELP
    assert "--buy-state-file" in SX_HELP
