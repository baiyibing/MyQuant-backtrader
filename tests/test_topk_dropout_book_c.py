"""BT-C: topk_dropout stop_pct=0.10; version6 remains ~0.02; no trail."""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.research import strategy6_rules, strategy_topk_dropout_rules
from backtest.research.csv_daily_backtest import simulate
from backtest.research.csv_strategy_books import apply_csv_strategy


def test_topk_stop_pct_is_ten_percent_not_v6():
    assert strategy_topk_dropout_rules.STOP_PCT == pytest.approx(0.10)
    assert strategy6_rules.STOP_PCT == pytest.approx(0.02)
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={"20260106": {"600000.SH": 1.0}},
        topk=1,
        n_drop=1,
    )
    assert hooks["stop_pct"] == pytest.approx(0.10)
    assert hooks["take_profit"](10.0, 10.0, 12.0, 2) is None

    v6 = apply_csv_strategy("version6")
    assert v6["stop_pct"] == pytest.approx(0.02)


def test_stop_pct_zero_disables_stop():
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={"20260106": {"600000.SH": 1.0}},
        topk=1,
        n_drop=1,
        stop_pct=0,
    )
    assert hooks["stop_pct"] is None


def test_topk_stop_override_via_stop_pct_kwarg():
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={"20260106": {"600000.SH": 1.0}},
        topk=1,
        n_drop=1,
        stop_pct=0.12,
    )
    assert hooks["stop_pct"] == pytest.approx(0.12)


def test_daily_stop_kernel_gap_open_reason():
    """Existing daily stop kernel: gap_open; T+1 buy day does not sell."""
    idx = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-05"),
            pd.Timestamp("2026-01-06"),
            pd.Timestamp("2026-01-07"),
            pd.Timestamp("2026-01-08"),
        ]
    )
    # Buy on 01-06 close 10. Day 01-07: open 9.5 (<= cost*0.9=9.0? no)
    # Use cost stop 10% → trigger 9.0. Open 9.2 > LD(9.0) wait — need open<=trigger
    # and not limit-down. Board 10% LD from prev 10 = 9.0; trigger=9.0 → at LD defers.
    # So: after buy, inflate cost via... engine cost=buy px. Use stop_pct override 0.05
    # so trigger=9.5 > LD=9.0, open=9.4 → gap_open fills same day.
    bars = {
        "600000.SH": pd.DataFrame(
            {
                "open": [10.0, 10.0, 9.4, 9.5],
                "high": [10.5, 10.2, 9.6, 9.7],
                "low": [9.8, 9.9, 9.3, 9.4],
                "close": [10.0, 10.0, 9.5, 9.6],
                "volume": [1e6, 1e6, 1e6, 1e6],
            },
            index=idx,
        ),
    }
    days = ["20260105", "20260106", "20260107", "20260108"]
    pool = {d: (["600000.SH"] if d == "20260105" else []) for d in days}
    scores = {d: {"600000.SH": 1.0, "600001.SH": 0.1} for d in days}
    names = {d: {"600000.SH": "测试"} for d in days}
    st = simulate(
        bars,
        pool,
        "20260105",
        "20260108",
        total_cash=2_000_000,
        daily_quota=1_000_000,
        strategy="topk_dropout",
        scores_by_day=scores,
        topk=1,
        n_drop=1,
        stop_pct=0.05,  # trigger 9.5 > board LD 9.0 so no defer
        pool_names_by_day=names,
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert sells, st.trades
    assert sells[0]["reason"] == "stop_loss:gap_open"
    # No trail reasons
    assert all(not t["reason"].startswith("trail:") for t in sells)


def test_bare_or_canon_pads_int_stripped_leading_zeros():
    from backtest.research.topk_dropout_scores import _bare_or_canon

    assert _bare_or_canon(48) == "000048.SZ"
    assert _bare_or_canon(608) == "000608.SZ"
    assert _bare_or_canon("000048") == "000048.SZ"
    assert _bare_or_canon(600179) == "600179.SH"


def test_load_scores_dir_keeps_leading_zeros(tmp_path):
    from backtest.research.topk_dropout_scores import load_scores_dir

    p = tmp_path / "20260106.csv"
    p.write_text("code,score\n000048,0.11\n000608,0.57\n600179,0.14\n", encoding="utf-8")
    got = load_scores_dir(tmp_path)["20260106"]
    assert "000048.SZ" in got and got["000048.SZ"] == pytest.approx(0.11)
    assert "000608.SZ" in got and got["000608.SZ"] == pytest.approx(0.57)
    assert "600179.SH" in got


def _close_fill_days():
    idx = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-01-05"),
            pd.Timestamp("2026-01-06"),
            pd.Timestamp("2026-01-07"),
            pd.Timestamp("2026-01-08"),
        ]
    )
    days = ["20260105", "20260106", "20260107", "20260108"]
    names = {d: {"600000.SH": "测试", "600001.SH": "对照"} for d in days}
    return idx, days, names


def test_help_lock_mentions_stop_fill_close():
    assert "--stop-fill" in strategy_topk_dropout_rules.HELP_LOCK
    assert "stop_loss:close" in strategy_topk_dropout_rules.HELP_LOCK


def test_daily_stop_fill_close_ignores_gap_open():
    """Open 9.4 would gap-stop at 5%; close 9.8 stays above trigger → no stop."""
    idx, days, names = _close_fill_days()
    bars = {
        "600000.SH": pd.DataFrame(
            {
                "open": [10.0, 10.0, 9.4, 9.5],
                "high": [10.5, 10.2, 9.9, 9.7],
                "low": [9.8, 9.9, 9.3, 9.4],
                "close": [10.0, 10.0, 9.8, 9.6],
                "volume": [1e6, 1e6, 1e6, 1e6],
            },
            index=idx,
        ),
    }
    pool = {d: (["600000.SH"] if d == "20260105" else []) for d in days}
    scores = {d: {"600000.SH": 1.0, "600001.SH": 0.1} for d in days}
    st = simulate(
        bars,
        pool,
        "20260105",
        "20260108",
        total_cash=2_000_000,
        daily_quota=1_000_000,
        strategy="topk_dropout",
        scores_by_day=scores,
        topk=1,
        n_drop=1,
        stop_pct=0.05,
        stop_fill="close",
        pool_names_by_day=names,
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert all(not str(t["reason"]).startswith("stop_loss") for t in sells), sells
    assert st.stats.get("stop_fill") == "close"


def test_daily_stop_fill_close_sells_at_close_not_touch():
    """Low stays above trigger so touch would not fire; close 9.4 does."""
    idx, days, names = _close_fill_days()
    bars = {
        "600000.SH": pd.DataFrame(
            {
                "open": [10.0, 10.0, 9.8, 9.5],
                "high": [10.5, 10.2, 9.9, 9.7],
                "low": [9.8, 9.9, 9.7, 9.4],
                "close": [10.0, 10.0, 9.4, 9.6],
                "volume": [1e6, 1e6, 1e6, 1e6],
            },
            index=idx,
        ),
    }
    pool = {d: (["600000.SH"] if d == "20260105" else []) for d in days}
    scores = {d: {"600000.SH": 1.0, "600001.SH": 0.1} for d in days}
    st = simulate(
        bars,
        pool,
        "20260105",
        "20260108",
        total_cash=2_000_000,
        daily_quota=1_000_000,
        strategy="topk_dropout",
        scores_by_day=scores,
        topk=1,
        n_drop=1,
        stop_pct=0.05,
        stop_fill="close",
        pool_names_by_day=names,
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert sells, st.trades
    assert sells[0]["reason"] == "stop_loss:close"
    assert sells[0]["price"] == pytest.approx(9.4)
    assert sells[0]["price_rule"] == "daily_stop_close"


def test_daily_stop_fill_close_fills_at_limit_down():
    idx, days, names = _close_fill_days()
    bars = {
        "600000.SH": pd.DataFrame(
            {
                "open": [10.0, 10.0, 9.0, 9.1],
                "high": [10.5, 10.2, 9.0, 9.2],
                "low": [9.8, 9.9, 9.0, 9.0],
                "close": [10.0, 10.0, 9.0, 9.1],
                "volume": [1e6, 1e6, 1e6, 1e6],
            },
            index=idx,
        ),
    }
    pool = {d: (["600000.SH"] if d == "20260105" else []) for d in days}
    scores = {d: {"600000.SH": 1.0, "600001.SH": 0.1} for d in days}
    st = simulate(
        bars,
        pool,
        "20260105",
        "20260108",
        total_cash=2_000_000,
        daily_quota=1_000_000,
        strategy="topk_dropout",
        scores_by_day=scores,
        topk=1,
        n_drop=1,
        stop_pct=0.05,
        stop_fill="close",
        pool_names_by_day=names,
    )
    sells = [t for t in st.trades if t["side"] == "SELL"]
    assert sells, st.trades
    assert sells[0]["reason"] == "stop_loss:close"
    assert sells[0]["price"] == pytest.approx(9.0)


def test_daily_stop_fill_close_beats_same_day_dropout():
    idx, days, names = _close_fill_days()
    ohlc = {
        "open": [10.0, 10.0, 9.8, 9.5],
        "high": [10.5, 10.2, 9.9, 9.7],
        "low": [9.8, 9.9, 9.7, 9.4],
        "close": [10.0, 10.0, 9.4, 9.6],
        "volume": [1e6, 1e6, 1e6, 1e6],
    }
    bars = {
        "600000.SH": pd.DataFrame(ohlc, index=idx),
        "600001.SH": pd.DataFrame(
            {k: ([10.0] * 4 if k != "volume" else [1e6] * 4) for k in ohlc},
            index=idx,
        ),
    }
    pool = {d: ["600000.SH"] if d == "20260105" else [] for d in days}
    scores = {
        "20260105": {"600000.SH": 1.0, "600001.SH": 0.1},
        "20260106": {"600000.SH": 1.0, "600001.SH": 0.1},
        "20260107": {"600000.SH": 0.1, "600001.SH": 1.0},
        "20260108": {"600000.SH": 0.1, "600001.SH": 1.0},
    }
    st = simulate(
        bars,
        pool,
        "20260105",
        "20260108",
        total_cash=2_000_000,
        daily_quota=1_000_000,
        strategy="topk_dropout",
        scores_by_day=scores,
        topk=1,
        n_drop=1,
        stop_pct=0.05,
        stop_fill="close",
        pool_names_by_day=names,
    )
    sells = [t for t in st.trades if t["side"] == "SELL" and t["code"] == "600000.SH"]
    assert sells, st.trades
    assert sells[0]["reason"] == "stop_loss:close"
    assert not any(str(t["reason"]).startswith("topk_drop") for t in sells)


def test_minute_refuses_stop_fill_close():
    from backtest.research.csv_minute_backtest import simulate as minute_simulate

    with pytest.raises(SystemExit, match="minute entry refuses"):
        minute_simulate(
            {},
            {},
            {},
            "20260106",
            "20260108",
            strategy="topk_dropout",
            scores_by_day={"20260106": {"600000.SH": 1.0}},
            topk=1,
            n_drop=1,
            stop_fill="close",
        )


def test_stop_fill_close_rejected_for_version6():
    import argparse

    from backtest.research.csv_strategy_books import csv_run_kwargs_from_args

    ns = argparse.Namespace(strategy="version6", stop_fill="close", stop_pct=None)
    with pytest.raises(SystemExit, match="only for topk_dropout"):
        csv_run_kwargs_from_args(ns)
