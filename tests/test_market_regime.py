"""Series-agnostic market regime core (plan-market-regime-unify-2026-10-18)."""

import pandas as pd
import pytest

from backtest.research import bigvalue_regime, market_regime


def _index_parquet(tmp_path, closes, ma5):
    days = pd.bdate_range("20260101", periods=len(closes))
    frame = pd.DataFrame({
        "date": [d.strftime("%Y%m%d") for d in days],
        "close": closes,
        "ma5": ma5,
    })
    path = tmp_path / "index_regime.parquet"
    frame.to_parquet(path, index=False)
    return path


def test_fast1_uses_value_column_as_fast_line(tmp_path):
    path = _index_parquet(tmp_path, [10.0] * 6 + [9.0] * 6, [10.0] * 6 + [9.5] * 6)
    states = market_regime.load_regime(path, fast=1, slow=5, value_col="close")
    values = list(states.values())
    assert values[:6] == [0] * 6             # close == ma5 → equal, neither state
    assert values[-3:] == [-1, -1, -1]       # close < ma5
    # no fake ma1 column is required, and ma1 absence is not "missing columns"
    assert "ma1" not in pd.read_parquet(path).columns


def test_fast1_missing_slow_ma_still_refuses(tmp_path):
    path = _index_parquet(tmp_path, [10.0] * 6, [10.0] * 6)
    frame = pd.read_parquet(path).drop(columns=["ma5"])
    frame.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        market_regime.load_regime(path, fast=1, slow=5, value_col="close")


def test_bigvalue_shim_reexports_identity():
    for name in ("load_regime", "confirmed_days", "flatten_reason",
                 "golden_cash_fraction", "with_bigvalue_gate"):
        assert getattr(bigvalue_regime, name) is getattr(market_regime, name)
    assert market_regime.regime_cash_fraction is market_regime.golden_cash_fraction
    assert market_regime.with_regime_gate is market_regime.with_bigvalue_gate


def test_regime_cash_fraction_alias_semantics():
    days = {"20260115": "allowed_golden"}
    assert market_regime.regime_cash_fraction(days, "20260115", 2, 0.5) == 1.0
    assert market_regime.regime_cash_fraction(days, "20260115", 1.2, 0.5) == 0.6
    assert market_regime.regime_cash_fraction(days, "20260114", 2, 0.5) == 0.5


def _index_fixture(tmp_path):
    days = pd.bdate_range("20260101", periods=8)
    frame = pd.DataFrame({
        "date": [d.strftime("%Y%m%d") for d in days],
        "close": [10.0] * 4 + [9.0] * 4,
        "ma5": [10.0] * 4 + [9.6] * 4,
    })
    path = tmp_path / "sse_regime.parquet"
    frame.to_parquet(path, index=False)
    return path


def _parse_topk(argv):
    import argparse
    from backtest.research.csv_strategy_books import add_topk_dropout_args
    ap = argparse.ArgumentParser()
    add_topk_dropout_args(ap)
    return ap.parse_args(argv)


def _run_kwargs_topk(args):
    from backtest.research import topk_dropout_scores, csv_strategy_books as books
    orig = topk_dropout_scores.load_scores_from_args
    topk_dropout_scores.load_scores_from_args = lambda **kw: {"20260115": {"A": 1.0}}
    try:
        return books._run_kwargs_topk_dropout(args)
    finally:
        topk_dropout_scores.load_scores_from_args = orig


def test_index_family_cli_contract(tmp_path, monkeypatch):
    path = _index_fixture(tmp_path)
    kw = _run_kwargs_topk(_parse_topk([
        "--index-block-new", "--index-flatten", "--index-regime-file", str(path),
        "--index-confirm-days", "1",
    ]))
    states, confirm = kw["bigvalue_regime"]
    last_day = max(states)
    assert confirm == 1 and states[last_day] == -1
    assert kw["bigvalue_block_new"] is True and kw["bigvalue_flatten"] is True

    def run_kwargs(argv):
        return _run_kwargs_topk(_parse_topk(argv))

    with pytest.raises(SystemExit, match="require --index-block-new"):
        run_kwargs(["--index-regime-file", str(path)])
    with pytest.raises(SystemExit, match="requires --index-regime-file"):
        run_kwargs(["--index-block-new"])
    with pytest.raises(SystemExit, match="one regime per run"):
        run_kwargs(["--index-block-new", "--index-regime-file", str(path),
                    "--index-ma5-gate"])
    with pytest.raises(SystemExit, match="one regime per run"):
        run_kwargs(["--index-block-new", "--index-regime-file", str(path),
                    "--bigvalue-block-new", "--bigvalue-regime-file", str(path)])
    with pytest.raises(SystemExit, match="base-frac"):
        run_kwargs(["--index-block-new", "--index-regime-file", str(path),
                    "--index-base-frac", "1.5"])


def test_index_family_guarded_to_topk(tmp_path):
    import subprocess
    import sys as _sys
    argv = [_sys.executable, "-m", "backtest.research.csv_daily_backtest",
            "--strategy", "version6", "--index-block-new",
            "--index-regime-file", str(_index_fixture(tmp_path))]
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=".")
    assert proc.returncode != 0
    assert "only by topk_dropout" in (proc.stderr + proc.stdout)
