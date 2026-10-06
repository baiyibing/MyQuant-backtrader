"""Hand-calculated calibers and opt-in fences for RB-13."""

import ast
from pathlib import Path

import pandas as pd
import pytest
from backtest.research.csv_analysis_export import drawdown_and_win_rates, pair_round_trips
from backtest.research.metrics_pack import compute_metrics_pack, write_metrics_pack


def nav():
    return pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-05"],
            "equity": [100.0, 110.0, 99.0],
            "gross_invested": [50.0, 55.0, 49.5],
        }
    )


def test_hand_calculated_and_missing_benchmark(tmp_path):
    source = nav()
    before = source.copy(deep=True)
    pack = compute_metrics_pack(source, fees=pd.Series([1.0, 2.0]), periods_per_year=2)
    assert [r["value"] for r in pack["daily_returns"]] == pytest.approx([0.1, -0.1])
    assert pack["annualised_return"]["value"] == pytest.approx(-0.01)
    assert pack["annualised_volatility"]["value"] == pytest.approx(0.2)
    assert pack["sharpe"]["value"] == pytest.approx(0, abs=1e-14)
    assert pack["fee_drag"]["value"] == pytest.approx(9 / 309)
    assert pack["exposure"]["value"] == 0.5
    assert pack["risk_free_annual"] == 0
    for key in ("benchmark_excess", "beta", "tracking_error", "skip_rate", "defer_rate"):
        assert pack[key]["status"] == "unavailable"
        assert pack[key]["reason"]
    pd.testing.assert_frame_equal(source, before)
    assert list(tmp_path.iterdir()) == []
    out = tmp_path / "pack.json"
    write_metrics_pack(out, pack)
    first = out.read_bytes()
    write_metrics_pack(out, pack)
    assert first == out.read_bytes()
    assert first.endswith(b"\n") and b"NaN" not in first and not first.startswith(b"\xef\xbb\xbf")


def test_benchmark_and_risk_free():
    benchmark = nav().assign(equity=[100.0, 105.0, 99.75])
    pack = compute_metrics_pack(nav(), benchmark=benchmark, risk_free=0.21, periods_per_year=2)
    assert pack["benchmark_excess"]["value"] == pytest.approx(0, abs=1e-14)
    assert pack["beta"]["value"] == pytest.approx(2)
    assert pack["tracking_error"]["value"] == pytest.approx(0.1)
    assert pack["sharpe"]["value"] == pytest.approx(-1)
    short = compute_metrics_pack(nav().iloc[:1], benchmark=benchmark)
    assert short["annualised_return"]["status"] == "unavailable"
    constant = compute_metrics_pack(
        nav().assign(equity=100), benchmark=benchmark.assign(equity=100)
    )
    assert constant["sharpe"]["status"] == "unavailable"
    assert constant["beta"]["status"] == "unavailable"


def test_existing_closed_lot_definition_and_turnover():
    equity = nav().drop(columns="gross_invested")
    equity["ymd"] = ["20260101", "20260102", "20260105"]
    fills = pd.DataFrame(
        {
            "date": equity.date,
            "ymd": equity.ymd,
            "code": ["000001.SZ"] * 3,
            "side": ["BUY", "SELL", "SELL"],
            "price": [10.0, 11.0, 9.0],
            "shares": [10.0, 5.0, 5.0],
            "notional": [100.0, 55.0, 45.0],
            "commission": [0.0, 0.0, 0.0],
            "position_id": ["000001.SZ@20260101"] * 3,
            "reason": ["buy", "take", "stop"],
        }
    )
    _, trips, _ = pair_round_trips(fills, equity)
    expected = drawdown_and_win_rates(equity, trips, None)["win_rate_closed"]
    pack = compute_metrics_pack(equity, fills)
    assert pack["win_rate_closed"]["value"] == expected == 0.5
    assert pack["turnover"]["value"] == pytest.approx(600 / 309)
    assert compute_metrics_pack(equity, trips)["win_rate_closed"]["value"] == expected


@pytest.mark.parametrize("equity", [[100, 0, 99], [100, float("nan"), 99]])
def test_invalid_equity(equity):
    with pytest.raises(ValueError):
        compute_metrics_pack(nav().assign(equity=equity))


def test_opt_in_and_network_fences():
    root = Path(__file__).resolve().parents[1]
    for path in (root / "backtest/research").glob("*.py"):
        if path.name == "metrics_pack.py":
            continue
        assert "metrics_pack" not in path.read_text(encoding="utf-8"), path
    for relative in ("backtest/research/metrics_pack.py", "scripts/research/rb13_metrics_pack.py"):
        tree = ast.parse((root / relative).read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append((node.module or "").split(".")[0])
        assert not set(imports) & {"requests", "urllib", "http", "socket", "httpx", "aiohttp"}


def test_standalone_only_writes_explicit_output(tmp_path):
    from scripts.research.rb13_metrics_pack import main

    nav().to_csv(tmp_path / "daily_equity.csv", index=False)
    out = tmp_path / "explicit.json"
    assert (
        main(
            [
                "--run-dir",
                str(tmp_path),
                "--out",
                str(out),
                "--benchmark",
                str(tmp_path / "missing.csv"),
            ]
        )
        == 0
    )
    import json

    pack = json.loads(out.read_text())
    assert pack["beta"]["status"] == "unavailable"
    assert {p.name for p in tmp_path.iterdir()} == {"daily_equity.csv", "explicit.json"}
