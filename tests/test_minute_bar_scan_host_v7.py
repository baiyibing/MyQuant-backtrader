"""Data-free contract for the explicit v7 host entry."""
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backtest.research import ashare_session, csv_minute_backtest_v7 as v7
from backtest.research import minute_bar_scan_host as host


@pytest.mark.parametrize("asof", [False, True])
@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("cash", [None, 123456.0])
def test_v7_cli_loads_once_and_dispatches(tmp_path, monkeypatch, asof, empty, cash):
    start, end = date(2026, 1, 9), date(2026, 1, 12)
    pools = {} if empty else {start: ["000001.SZ"], end: ["000002.SZ"]}
    minute, daily = {}, {}
    index = {start: 3000., end: 3001.}
    exdiv, names = {"000001.SZ": {"20260109": 0.9}}, {"000001.SZ": "ST fixture"}
    day_names = {"20260109": names}
    loaders = {
        "load_pool_days": Mock(return_value=pools),
        "_load_cli_bars": Mock(return_value=(minute, daily)),
        "load_index_daily": Mock(return_value=index),
        "load_pool_names_by_day": Mock(return_value=day_names),
    }
    for name, loader in loaders.items():
        monkeypatch.setattr(v7, name, loader)
    context = Mock(return_value=(exdiv, names))
    monkeypatch.setattr(ashare_session, "load_limit_context", context)
    runner = Mock(return_value=SimpleNamespace(trades=[], equity_curve=[], cash=21000000.))
    monkeypatch.setattr(v7, "simulate_v7", runner)
    shared = Mock(side_effect=AssertionError("v7 must not use shared simulate"))
    monkeypatch.setattr(host.csv_minute_backtest, "simulate", shared)
    # Environment fallback is v7-only; explicit --pool-dir takes precedence.
    monkeypatch.setenv("OSKH_TURTLE_POOL_DIR", str(tmp_path))
    argv = ["--source", "lake", "--symbol", "000001.SZ", "--start", "20260109",
            "--end", "20260112", "--strategy", "version7"]
    pool_dir = tmp_path
    if cash is not None:
        pool_dir = tmp_path / "explicit"
        argv += ["--cash", str(cash), "--pool-dir", str(pool_dir)]
    if asof:
        argv += ["--asof-pool-names"]
    assert host.main(argv) == 0
    loaders["load_pool_days"].assert_called_once_with(pool_dir, start, end)
    loaders["_load_cli_bars"].assert_called_once_with(pools, start, end)
    context.assert_called_once_with(pool_dir, {c for codes in pools.values() for c in codes}, start, end)
    if empty:
        loaders["load_index_daily"].assert_not_called()
        index = [start + timedelta(days=n) for n in range((end - start).days + 1)]
    else:
        loaders["load_index_daily"].assert_called_once_with(start, end)
    if asof:
        loaders["load_pool_names_by_day"].assert_called_once_with(pool_dir, start, end)
    else:
        loaders["load_pool_names_by_day"].assert_not_called()
    runner.assert_called_once_with(
        minute, daily, pools, index, cash_total=21000000. if cash is None else cash,
        start=start, end=end, exdiv=exdiv, names=None if asof else names,
        names_by_day=day_names if asof else None,
    )
    shared.assert_not_called()


def test_v7_requires_explicit_pool(monkeypatch):
    monkeypatch.delenv("OSKH_TURTLE_POOL_DIR", raising=False)
    loader = Mock(side_effect=AssertionError("must fail before loading"))
    monkeypatch.setattr(v7, "load_pool_days", loader)
    with pytest.raises(ValueError, match="--pool-dir or OSKH_TURTLE_POOL_DIR"):
        host.run_version7("20260109", "20260112")
    loader.assert_not_called()
