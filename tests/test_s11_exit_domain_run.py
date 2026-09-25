"""X-03 public run/CLI routing, independent lake input, and OFF isolation."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute

CODE = "600000.SH"
START, END = "20240902", "20240904"


@pytest.fixture
def lake(tmp_path, monkeypatch):
    root = tmp_path / "lake"
    monkeypatch.setenv("OSKH_SOURCE_PARQUET_ROOT", str(root))
    daily_root = root / "stock" / "period=1d"
    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", str(daily_root))
    monkeypatch.delenv("OSKH_PERIOD_1M_ROOT", raising=False)
    dates = pd.bdate_range("20240826", periods=8)
    raw = pd.DataFrame({"time": dates.as_unit("ms").asi8,
                        "open": [10.] * 5 + [10.2, 9.45, 9.7],
                        "close": [10.] * 5 + [10.5, 9.45, 9.7]})
    raw["high"] = np.maximum(raw.open, raw.close)
    raw["low"] = np.minimum(raw.open, raw.close)
    raw["volume"] = 100_000.
    front = raw.copy()
    front.loc[:5, ["open", "high", "low", "close"]] *= .9
    paths = {}
    for domain, frame in (("none", raw), ("front", front)):
        path = daily_root / f"dividend_type={domain}/symbol=600000_SH/data.parquet"
        path.parent.mkdir(parents=True)
        frame.to_parquet(path, index=False)
        paths[domain] = path
    minute_frame = raw.copy()
    minute_frame["time"] += 570 * 60_000
    minute_path = root / "stock/period=1m/dividend_type=none/symbol=600000_SH/data.parquet"
    minute_path.parent.mkdir(parents=True)
    minute_frame.to_parquet(minute_path, index=False)
    pool = tmp_path / "pool"
    pool.mkdir()
    for engine in (daily, minute):
        monkeypatch.setattr(engine, "load_pool_day_map", lambda *a, **k: {START: [CODE]})
        monkeypatch.setattr(engine, "load_pool_names_by_day", lambda *a, **k: {})
        monkeypatch.setattr(engine, "load_exdiv_ratios", lambda *a, **k: {(CODE, "20240903"): .9})
    return pool, paths


def run(engine, pool, **kwargs):
    return engine.run(START, END, strategy="version11", pool_dir=pool,
                      total_cash=100_000, daily_quota=5000, **kwargs)


@pytest.mark.parametrize("engine", [daily, minute])
def test_off_never_loads_front_and_adds_no_stats_keys(engine, lake, monkeypatch):
    from backtest.research import s11_exit_domain

    pool, paths = lake
    paths["front"].unlink()
    calls = []
    original = engine.load_daily_ohlc

    def spy(*args, **kwargs):
        calls.append(kwargs.get("dividend_type", "none"))
        return original(*args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("OFF must not read independent front")

    monkeypatch.setattr(engine, "load_daily_ohlc", spy)
    monkeypatch.setattr(s11_exit_domain, "load_signal_bars_front", forbidden)
    omitted = run(engine, pool)
    explicit = run(engine, pool, fix_s11_exit_domain=False)
    assert calls == ["none", "none"]
    assert omitted.trades == explicit.trades
    assert omitted.equity_curve == explicit.equity_curve
    assert omitted.stats.keys() == explicit.stats.keys()
    assert "fix_s11_exit_domain" not in omitted.stats
    assert "exit_signal_domain" not in omitted.stats


@pytest.mark.parametrize("engine", [daily, minute])
def test_on_loads_separate_front_but_keeps_raw_fills_marks_and_metadata(engine, lake):
    pool, _ = lake
    state = run(engine, pool, fix_s11_exit_domain=True)
    fills = [t for t in state.trades if t["side"] in ("BUY", "SELL")]
    assert [(t["side"], t["shares"]) for t in fills] == [("BUY", 400)]
    assert fills[0]["price"] == (10.5 if engine is daily else 10.2)
    assert state.trades[-1]["side"] == "EOD_MARK"
    assert state.trades[-1]["price"] == 9.7
    metadata = state.run_metadata["s11_exit_domain"]
    assert metadata["fix_s11_exit_domain"] is True
    assert metadata["exit_signal_domain"] == "front"
    assert metadata["signal_exdiv_remap"] is False
    assert metadata["fill_domain"] == metadata["mark_domain"] == "none"
    assert "fix_s11_exit_domain" not in state.stats


@pytest.mark.parametrize("engine", [daily, minute])
@pytest.mark.parametrize("defect", ["directory", "code", "today", "history", "nan", "duplicate", "extra_date"])
def test_bad_front_fails_before_simulate(engine, lake, monkeypatch, defect):
    pool, paths = lake
    path = paths["front"]
    frame = pd.read_parquet(path)
    if defect == "directory":
        path.unlink()
        path.parent.rmdir()
        path.parent.parent.rmdir()
    elif defect == "code":
        path.unlink()
    else:
        if defect == "today":
            frame = frame.drop(index=5)
        elif defect == "history":
            frame = frame.drop(index=2)
        elif defect == "nan":
            frame.loc[5, "close"] = np.nan
        elif defect == "duplicate":
            frame = pd.concat([frame, frame.iloc[[5]]])
        else:
            frame.loc[2, "time"] += 24 * 60 * 60_000 * 3
        frame.to_parquet(path, index=False)

    def forbidden(*args, **kwargs):
        pytest.fail("data contract must fail before first trade / simulate")

    monkeypatch.setattr(engine, "simulate", forbidden)
    with pytest.raises((ValueError, FileNotFoundError)):
        run(engine, pool, fix_s11_exit_domain=True)


@pytest.mark.parametrize("engine,kwargs", [
    (daily, {"dividend_type": "front"}),
    (daily, {"dividend_type": "back"}),
    (daily, {"qlib_data_root": Path("unused")}),
    (minute, {"dividend_type": "front"}),
    (minute, {"daily_source": "qlib_day"}),
    (minute, {"minute_source": "qlib_1min"}),
    (minute, {"qlib_day_root": Path("unused")}),
    (minute, {"qlib_1min_root": Path("unused")}),
])
def test_unsupported_on_sources_fail_before_loading(engine, kwargs, monkeypatch):
    monkeypatch.setattr(engine, "load_pool_day_map", lambda *a, **k: pytest.fail("early guard"))
    with pytest.raises(ValueError, match="fix_s11_exit_domain"):
        run(engine, Path("unused"), fix_s11_exit_domain=True, **kwargs)


@pytest.mark.parametrize("engine", [daily, minute])
def test_other_book_flag_is_not_silently_ignored(engine):
    with pytest.raises(ValueError, match="version11"):
        engine.run(START, END, strategy="version1", fix_s11_exit_domain=True)


@pytest.mark.parametrize("engine", [daily, minute])
def test_cli_help_advertises_default_off(engine, capsys):
    with pytest.raises(SystemExit) as exc:
        engine.main(["--strategy", "version11", "--help"])
    assert exc.value.code == 0
    assert "--fix-s11-exit-domain" in capsys.readouterr().out
