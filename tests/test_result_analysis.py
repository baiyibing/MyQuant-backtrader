"""P1 account curve and closed-trip payoff. Synthetic frames only."""

from __future__ import annotations

import math

import pandas as pd
import pytest
from backtest.research.csv_analysis_export import write_bundle
from backtest.research.metrics_pack import compute_metrics_pack
from backtest.research.result_analysis import (
    account_curve,
    trade_payoff,
    window_split,
    with_realized_share,
)


def _nav(values, start="20260105"):
    dates = pd.bdate_range(start, periods=len(values))
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "equity": values})


def _trips(*pnls, reason="exit"):
    rows = []
    for pnl in pnls:
        rows.append({"status": "closed", "realized_pnl": pnl, "sell_reason": reason})
    return pd.DataFrame(rows)


def test_geometric_excess_is_negative_when_benchmark_rises_faster():
    nav = _nav([100.0, 110.0])
    bench = _nav([100.0, 130.0])
    curve = account_curve(nav, benchmark=bench)
    excess = curve["benchmark"]
    assert excess["geometric_excess"]["value"] == pytest.approx(1.1 / 1.3 - 1.0)
    assert excess["arithmetic_excess"]["value"] == pytest.approx(0.1 - 0.3)
    assert excess["geometric_excess"]["value"] < 0


def test_annualised_return_is_compound_not_mean_times_238():
    nav = _nav([100.0, 200.0])
    curve = account_curve(nav)
    compound = 2.0 ** (252 / 1) - 1.0
    assert curve["annualised_return"]["value"] == pytest.approx(compound)
    assert curve["annualised_return"]["value"] != pytest.approx(1.0 * 238)


def test_sharpe_matches_side_pack_including_rate_and_zero_vol():
    nav = _nav([100.0, 110.0, 100.0])
    frame = nav.copy()
    side = compute_metrics_pack(frame, risk_free=0.21, periods_per_year=252)
    curve = account_curve(nav, risk_free=0.21)
    assert curve["sharpe"]["value"] == pytest.approx(side["sharpe"]["value"])
    assert curve["annualised_volatility"]["value"] == pytest.approx(side["annualised_volatility"]["value"])
    flat = account_curve(_nav([100.0, 100.0, 100.0]))
    assert flat["annualised_volatility"]["value"] == 0.0
    assert flat["sharpe"]["status"] == "unavailable"


def test_payoff_unavailable_without_a_loss_and_ignores_open_lots():
    payoff = trade_payoff(_trips(10.0, 5.0))
    assert payoff["profit_factor"]["status"] == "unavailable"
    assert payoff["payoff_ratio"]["status"] == "unavailable"
    mixed = _trips(10.0, -4.0, 0.0)
    mixed = pd.concat(
        [mixed, pd.DataFrame([{"status": "open_eod", "realized_pnl": 99.0, "sell_reason": "EOD_MARK"}])],
        ignore_index=True,
    )
    got = trade_payoff(mixed)
    assert got["closed_trips"] == 3
    assert got["flat"] == 1
    assert got["wins"] == 1
    assert got["win_rate"]["value"] == pytest.approx(1 / 3)
    assert got["avg_loss"]["value"] == pytest.approx(-4.0)
    assert got["payoff_ratio"]["value"] == pytest.approx(10.0 / 4.0)
    assert got["profit_factor"]["value"] == pytest.approx(10.0 / 4.0)


def test_missing_benchmark_still_writes_payoff():
    curve = account_curve(_nav([100.0, 110.0, 105.0]))
    assert curve["benchmark"]["reason"] == "benchmark not supplied"
    payoff = trade_payoff(_trips(3.0, -1.0))
    assert payoff["payoff_ratio"]["status"] == "available"


def test_month_return_uses_the_prior_row_and_drawdown_peak_is_last_touch():
    nav = pd.DataFrame(
        {
            "date": ["2026-01-05", "2026-01-06", "2026-02-02"],
            "equity": [100.0, 110.0, 121.0],
        }
    )
    months = account_curve(nav)["months"]
    assert months[0]["return"]["value"] == pytest.approx(0.1)
    assert months[1]["return"]["value"] == pytest.approx(0.1)
    peaked = account_curve(_nav([10.0, 12.0, 12.0, 9.0]))["max_drawdown"]
    assert peaked["trough_date"] == "2026-01-08"
    assert peaked["peak_date"] == "2026-01-07"
    assert peaked["trading_days"] == 1


def test_realized_share_uses_at_most_five_positive_names():
    frame = pd.DataFrame(
        {
            "code": ["A", "B", "C", "D", "E", "F", "G"],
            "realized_pnl": [6.0, 5.0, 4.0, 3.0, 2.0, 1.0, -4.0],
        }
    )
    got = with_realized_share(frame)
    assert got["realized_pnl_share"].sum() == pytest.approx(1.0)
    assert int(got["top_profit_count"].iloc[0]) == 5
    assert got["top_profit_share"].iloc[0] == pytest.approx(20.0 / 21.0)
    flat = with_realized_share(pd.DataFrame({"code": ["A"], "realized_pnl": [0.0]}))
    assert flat["top_profit_count"].iloc[0] == 0
    assert pd.isna(flat["realized_pnl_share"].iloc[0])


def test_later_window_is_scored_and_not_cited(tmp_path):
    nav = _nav([100.0, 110.0, 121.0, 100.0])
    split = window_split(nav)
    assert split["selection_rows"] == 2
    assert split["score_rows"] == 2
    assert split["period_return"]["value"] == pytest.approx(100.0 / 121.0 - 1.0)
    run = tmp_path / "run"
    run.mkdir()
    nav.to_csv(run / "daily_equity.csv", index=False)
    (run / "trades.csv").write_text(
        "date,code,side,price,shares,reason\n20260105,600000.SH,BUY,10,10,pool\n",
        encoding="utf-8",
    )
    out = tmp_path / "analysis"
    write_bundle(run, out, account=100.0)
    text = (out / "human_analysis.txt").read_text(encoding="utf-8")
    assert "window_split.json" not in text
    assert (out / "window_split.json").is_file()


def test_benchmark_csv_rejects_a_close_column(tmp_path):
    from backtest.research.csv_analysis_export import load_benchmark_csv

    path = tmp_path / "bench.csv"
    path.write_text("date,close\n20260105,1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_benchmark_csv(path)


def test_missing_index_root_fails_closed(monkeypatch, tmp_path):
    from backtest.research import csv_analysis_export as exp

    monkeypatch.setattr(exp, "load_benchmark_index", exp.load_benchmark_index)
    missing = tmp_path / "no-index"

    def _root():
        return missing

    monkeypatch.setattr("common.infra.data_root.resolve_index_daily_root", _root)
    with pytest.raises(FileNotFoundError):
        exp.load_benchmark_index("000300.SH", "none")


def test_export_leaves_run_files_unchanged_and_skips_fee_without_commission(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "daily_equity.csv").write_text("date,equity\n20260105,100\n20260106,110\n", encoding="utf-8")
    (run / "trades.csv").write_text(
        "date,code,side,price,shares,reason\n20260105,600000.SH,BUY,10,10,pool\n20260106,600000.SH,SELL,11,10,exit\n",
        encoding="utf-8",
    )
    before = {name: (run / name).read_bytes() for name in ("daily_equity.csv", "trades.csv")}
    out = tmp_path / "analysis"
    product = write_bundle(run, out, account=100.0)
    assert before == {name: (run / name).read_bytes() for name in before}
    assert "account_curve" not in product["summary"] or "period_return" not in product["summary"]
    curve = __import__("json").loads((out / "account_curve.json").read_text(encoding="utf-8"))
    assert curve["fee_drag"]["status"] == "unavailable"
    text = (out / "human_analysis.txt").read_text(encoding="utf-8")
    assert "account_curve.json" in text
    assert "trade_payoff.json" in text
    assert math.isfinite(curve["period_return"]["value"])
