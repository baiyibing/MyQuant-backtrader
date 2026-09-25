"""Strict pool checks are opt-in and run before either engine loads bars."""

from unittest.mock import Mock

import pytest

from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_pool

DAY = "20260901"


class _Stop(Exception):
    """Stop execution at the first loader or CLI dispatch without touching data."""


def _write_pool(tmp_path, text):
    path = tmp_path / f"{DAY}.csv"
    path.write_text(text, encoding="utf-8")
    return path


def _assert_strict_rejects_before_loader(engine, tmp_path, monkeypatch):
    pool = _write_pool(tmp_path, "SZ300190,维尔利\n")
    before = pool.read_bytes()
    loader = Mock(side_effect=AssertionError("loader must not run"))
    monkeypatch.setattr(engine, "load_daily_ohlc", loader)

    with pytest.raises(SystemExit, match="strict pool"):
        engine.run(DAY, DAY, strategy="version6", pool_dir=tmp_path, strict_pool=True)

    loader.assert_not_called()
    assert pool.read_bytes() == before


def _assert_default_reaches_loader(engine, tmp_path, monkeypatch):
    _write_pool(tmp_path, "SZ300190,维尔利\n")
    validator = Mock(side_effect=AssertionError("validator must not run"))
    loader = Mock(side_effect=_Stop)
    monkeypatch.setattr(csv_pool, "validate_pool_dir", validator)
    monkeypatch.setattr(engine, "load_daily_ohlc", loader)

    with pytest.raises(_Stop):
        engine.run(DAY, DAY, strategy="version6", pool_dir=tmp_path)

    validator.assert_not_called()
    loader.assert_called_once()
    assert loader.call_args.args[0] == {"300190.SZ"}


def test_daily_run_strict_pool_exits_before_bar_load(tmp_path, monkeypatch):
    _assert_strict_rejects_before_loader(daily, tmp_path, monkeypatch)


def test_minute_run_strict_pool_exits_before_bar_load(tmp_path, monkeypatch):
    _assert_strict_rejects_before_loader(minute, tmp_path, monkeypatch)


def test_daily_run_default_does_not_validate(tmp_path, monkeypatch):
    _assert_default_reaches_loader(daily, tmp_path, monkeypatch)


def test_minute_run_default_does_not_validate(tmp_path, monkeypatch):
    _assert_default_reaches_loader(minute, tmp_path, monkeypatch)


def test_strict_pool_accepts_bare_six_digits_and_reaches_loader(tmp_path, monkeypatch):
    pool = _write_pool(tmp_path, "600000,浦发\n")
    before = pool.read_bytes()
    for engine in (daily, minute):
        loader = Mock(side_effect=_Stop)
        monkeypatch.setattr(engine, "load_daily_ohlc", loader)

        with pytest.raises(_Stop):
            engine.run(DAY, DAY, strategy="version6", pool_dir=tmp_path, strict_pool=True)

        loader.assert_called_once()
        assert loader.call_args.args[0] == {"600000.SH"}
    assert pool.read_bytes() == before


def test_cli_help_strict_pool_present(tmp_path, monkeypatch, capsys):
    out_dir = tmp_path / "output"
    for engine in (daily, minute):
        with pytest.raises(SystemExit) as caught:
            engine.main(["--strategy", "version6", "--help"])
        assert caught.value.code == 0
        assert "--strict-pool" in capsys.readouterr().out

        dispatch = Mock(side_effect=_Stop)
        monkeypatch.setattr(engine, "run", dispatch)
        argv = [
            "--strategy", "version6",
            "--start", DAY,
            "--end", DAY,
            "--pool-dir", str(tmp_path),
            "--out-dir", str(out_dir),
        ]
        for flags, expected in (([], False), (["--strict-pool"], True)):
            dispatch.reset_mock()
            with pytest.raises(_Stop):
                engine.main([*argv, *flags])
            dispatch.assert_called_once()
            assert dispatch.call_args.kwargs["strict_pool"] is expected
            assert dispatch.call_args.kwargs["strategy"] == "version6"
            assert dispatch.call_args.kwargs["pool_dir"] == tmp_path
    assert not out_dir.exists()
