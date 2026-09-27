"""P2 synthetic reference-price and minute-only wiring contracts."""
from dataclasses import asdict
from unittest.mock import Mock

import pandas as pd
import pytest

from backtest.research import exdiv_map as em
from backtest.research import csv_minute_backtest as minute
from backtest.research import minute_cash_order
from tests.test_exdiv_refprice_engines import CODE, _d2_book_run, _d2_stub_book_entry


@pytest.mark.parametrize("raw,k,rounded", [(10, .5, 5), (10.006, .5, 5), (10.01, .5, 5.01), (10.03, .5, 5.02)])
def test_fen_half_up_only_after_mapping(raw, k, rounded):
    ratios = {CODE: {"20251105": k}}
    assert em.mapped_prev_close(ratios, CODE, "20251105", raw) == (raw * k, True)
    assert em.mapped_prev_close(ratios, CODE, "20251105", raw, fen_round=False) == (raw * k, True)
    assert em.mapped_prev_close(ratios, CODE, "20251105", raw, fen_round=True) == (rounded, True)
    for missing in (None, {}, {CODE: {"20251104": k}}, {CODE: {"20251105": -1}}):
        assert em.mapped_prev_close(missing, CODE, "20251105", raw, fen_round=True) == (raw, False)


def test_micro_event_noise_and_fallback_unchanged(tmp_path):
    adj, ex = tmp_path / "adj.parquet", tmp_path / "ex.parquet"
    pd.DataFrame({"stock_code": [CODE] * 3, "date": ["20251103", "20251104", "20251105"],
                  "cumulative_adj_factor": [1, 1 / .999, 1 / .999**2]}).to_parquet(adj)
    pd.DataFrame({"stock_code": [CODE], "ex_date": ["20251104"]}).to_parquet(ex)
    args = dict(adj_factor_path=adj, ex_date_index_path=ex)
    assert em.load_exdiv_ratios([CODE], "20251103", "20251105", **args) == {}
    ratios = em.load_exdiv_ratios([CODE], "20251103", "20251105", noise_eps=0, **args)
    assert ratios == {CODE: {"20251104": pytest.approx(.999)}}
    assert em.mapped_prev_close(ratios, CODE, "20251104", 10, fen_round=True) == (9.99, True)


@pytest.mark.parametrize("cash_order", [False, True])
@pytest.mark.parametrize("raw,expected", [(10.006, (5.50, 4.50)), (10.01, (5.51, 4.51))])
def test_minute_limit_base_and_off_state(monkeypatch, cash_order, raw, expected):
    module = minute_cash_order if cash_order else minute
    actual = module.book_limit_prices
    observed = []

    def capture(code, ref, *args, **kwargs):
        result = actual(code, ref, *args, **kwargs)
        observed.append((ref, result))
        return result

    monkeypatch.setattr(module, "book_limit_prices", capture)
    kwargs = dict(exdiv={CODE: {"20251105": .5}}, fix_minute_cash_order=cash_order)
    off = _d2_book_run(minute, [raw, raw, 5], **kwargs)
    explicit_off = _d2_book_run(minute, [raw, raw, 5], exdiv_ref_fen=False, **kwargs)
    assert asdict(off) == asdict(explicit_off)
    observed.clear()
    _d2_book_run(minute, [raw, raw, 5], exdiv_ref_fen=True, **kwargs)
    assert observed[-1] == (5 if raw == 10.006 else 5.01, expected)


@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize("strategy,front", [("version1", False), ("version12", False), ("version12", True)])
def test_run_loader_and_simulate_wiring(tmp_path, monkeypatch, flag, strategy, front):
    _, loader, simulate, _ = _d2_stub_book_entry(monkeypatch, minute, tmp_path)
    monkeypatch.setattr(minute, "load_minute_bars", Mock(return_value={CODE: object()}))
    from common.infra import data_root
    (tmp_path / "dividend_type=front").mkdir()
    monkeypatch.setattr(data_root, "resolve_period_root", lambda *_: tmp_path)
    monkeypatch.setattr(minute, "_load_minute_from_lake", Mock(return_value={CODE: object()}))
    minute.run("20251103", "20251105", strategy=strategy, pool_dir=tmp_path,
               use_cache=False, exdiv_ref_fen=flag, dividend_type="front" if front else "none")
    assert simulate.call_args.kwargs["exdiv_ref_fen"] is flag
    if strategy == "version12":
        loader.assert_not_called()
        assert simulate.call_args.kwargs["exdiv"] is None
    else:
        assert loader.call_args.kwargs.get("noise_eps", em.NOISE_EPS) == (0 if flag else em.NOISE_EPS)


@pytest.mark.parametrize("flags", [[], ["--exdiv-ref-fen"]])
def test_cli_wiring(monkeypatch, tmp_path, flags):
    class ReachedRun(Exception):
        pass

    def capture(*args, **kwargs):
        assert kwargs["exdiv_ref_fen"] is bool(flags)
        raise ReachedRun

    monkeypatch.setattr(minute, "run", capture)
    with pytest.raises(ReachedRun):
        minute.main(["--strategy", "version8", "--pool-dir", str(tmp_path)] + flags)


@pytest.mark.parametrize("module", ["csv_daily_backtest", "csv_minute_backtest_v7"])
def test_nonminute_entries_reject_flag(module, capsys):
    import importlib
    entry = importlib.import_module("backtest.research." + module)
    with pytest.raises(SystemExit) as err:
        entry.main((["--strategy", "version1"] if module == "csv_daily_backtest" else ["--pool-dir", ".", "--start", "20251103", "--end", "20251105"]) + ["--exdiv-ref-fen"])
    assert err.value.code == 2
    assert "unrecognized arguments: --exdiv-ref-fen" in capsys.readouterr().err


@pytest.mark.parametrize("cash_order", [False, True])
def test_exday_pool_buy_uses_same_fen_base(monkeypatch, cash_order):
    from backtest.research import csv_simulate_loop as loop
    actual = loop.book_limit_prices
    observed = []

    def capture(code, ref, *args, **kwargs):
        result = actual(code, ref, *args, **kwargs)
        observed.append((ref, result))
        return result

    monkeypatch.setattr(loop, "book_limit_prices", capture)
    _d2_book_run(minute, [10.01, 10.01, 5], pool={"20251105": [CODE]},
                 exdiv={CODE: {"20251105": .5}}, exdiv_ref_fen=True,
                 fix_minute_cash_order=cash_order)
    assert observed == [(5.01, (5.51, 4.51))]


def test_rounding_changes_half_fen_limit_boundary():
    ratios = {CODE: {"20251105": .5}}
    raw, _ = em.mapped_prev_close(ratios, CODE, "20251105", 10.01)
    rounded, _ = em.mapped_prev_close(ratios, CODE, "20251105", 10.01, fen_round=True)
    assert minute.book_limit_prices(CODE, raw, {}) == (5.51, 4.50)
    assert minute.book_limit_prices(CODE, rounded, {}) == (5.51, 4.51)
