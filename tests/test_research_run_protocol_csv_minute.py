"""Synthetic CSV delegation parity only; no lake or full CLI writer certification."""

from copy import deepcopy
from dataclasses import asdict
import os
from pathlib import Path
import random
import subprocess
import sys
import textwrap

import pandas as pd
import pytest

from backtest.research import csv_minute_backtest as native
from backtest.research.csv_ledger import InsufficientCashError, SimState
from backtest.research.run_protocol import (
    OMITTED, ApiResult, CliContext, CliResult, NativeApiRequest, NativeCliRequest, run,
)
from backtest.research.run_protocol.facade import UnregisteredEntryError
from tests.test_csv_minute_backtest import _daily, _day


ROOT = Path(__file__).resolve().parents[1]
CLI = "backtest/research/csv_minute_backtest.py"


@pytest.fixture
def bars():
    dates = ["2025-11-03", "2025-11-04"]
    first = _day(dates[0], [(1455, 10., 10., 10., 10.)])
    stop = _day(dates[1], [(1000, 10., 10.1, 9.3, 9.4)])
    hold = _day(dates[1], [(1000, 10., 10., 9.98, 10.)])
    minute = {"600000.SH": pd.concat([first, stop]), "600001.SH": pd.concat([first, hold])}
    daily = {"600000.SH": _daily(dates, [10., 9.4]), "600001.SH": _daily(dates, [10., 10.])}
    return minute, daily, {"20251103": list(minute)}, "20251103", "20251104"


@pytest.fixture
def cli_python(monkeypatch):
    # Pin the explicitly selected test interpreter, including in CI.
    monkeypatch.setenv("OSKH_MERGE_PYTHON", sys.executable)
    monkeypatch.delenv("OSKH_PYTHON_VERSION", raising=False)
    return sys.executable


@pytest.mark.parametrize("trigger", [OMITTED, "close", "hl"])
def test_simulate_full_state_parity_and_reference_identity(bars, trigger, monkeypatch):
    kwargs = {
        "strategy": "version6",
        "stop_pct": 0.05,
        "rule_profile": "legacy",
    }
    if trigger is not OMITTED:
        kwargs["minute_stop_trigger"] = trigger
    before = deepcopy(bars)
    expected = native.simulate(*bars, **kwargs)
    if trigger is OMITTED:
        explicit = native.simulate(*bars, **kwargs, minute_stop_trigger="close")
        assert asdict(expected) == asdict(explicit)
    simulate, calls, returned = native.simulate, [], []

    def spy(*args, **received):
        calls.append(1)
        assert all(a is b for a, b in zip(args, bars))
        assert received == kwargs
        value = simulate(*args, **received)
        returned.append(value)
        return value

    monkeypatch.setattr(native, "simulate", spy)
    request = NativeApiRequest(
        family="csv_minute", native_entry="csv_minute_backtest.simulate", args=bars, kwargs=kwargs
    )
    result = run(request)
    assert isinstance(result, ApiResult) and result.request is request
    assert calls == [1] and result.native_value is returned[0]
    assert type(result.native_value) is SimState
    # Include compare=False fields too; retain trade/reason order and open lots.
    assert asdict(result.native_value) == asdict(expected)
    for name in ("trades", "positions", "stats", "equity_curve", "book_state"):
        assert getattr(result.native_value, name) is getattr(returned[0], name)
    assert [t["side"] for t in expected.trades] == ["BUY", "BUY", "SELL", "EOD_MARK"]
    sell = expected.trades[2]
    assert sell["reason"] == "stop_loss:touch"
    assert sell["price"] == pytest.approx(9.5 if trigger == "hl" else 9.4)
    assert expected.positions["600001.SH"] and len(expected.equity_curve) == 2
    assert result.native_artifact_refs is OMITTED
    assert request.args is bars and request.kwargs is kwargs
    for original, snapshot in zip(bars[:2], before[:2]):
        assert original.keys() == snapshot.keys()
        for code in original:
            pd.testing.assert_frame_equal(original[code], snapshot[code])
    assert bars[2:] == before[2:]


@pytest.mark.parametrize("entry,problem,error_type", [
    ("simulate", "cash", InsufficientCashError),
    ("simulate", "stop_fill", SystemExit),
    ("run", "stop_fill", SystemExit),
    ("run", "tail_without_cash_order", ValueError),
])
def test_real_native_failure_is_same_instance_once(bars, entry, problem, error_type, monkeypatch):
    args = bars if entry == "simulate" else bars[3:]
    kwargs = {"strategy": "version8", "rule_profile": "legacy"}
    if problem == "cash":
        kwargs["total_cash"] = 1_000_000.
    elif problem == "stop_fill":
        # Match the existing TopK refusal case: other books may ignore this kw
        # in simulate(), while run() rejects it before any loader.
        kwargs.update(strategy="topk_dropout", stop_fill="close",
                      scores_by_day={"20251103": {"600000.SH": 1.0}}, topk=1, n_drop=1)
    else:
        kwargs["tail_window_buy"] = True

    def forbidden(*args, **kwargs):
        pytest.fail("validation must fail before loading pool or market data")

    monkeypatch.setattr(native, "load_pool_day_map", forbidden)
    target = getattr(native, entry)
    with pytest.raises(error_type) as direct:
        target(*args, **kwargs)
    calls, observed = [], []

    def spy(*args, **kwargs):
        calls.append(1)
        try:
            return target(*args, **kwargs)
        except BaseException as exc:
            observed.append(exc)
            raise

    monkeypatch.setattr(native, entry, spy)
    with pytest.raises(error_type) as caught:
        run(NativeApiRequest(
            family="csv_minute", native_entry=f"csv_minute_backtest.{entry}", args=args, kwargs=kwargs
        ))
    assert calls == [1] and len(observed) == 1 and caught.value is observed[0]
    assert caught.value.args == direct.value.args
    if problem == "stop_fill":
        assert "minute entry refuses" in str(caught.value)
    if problem == "cash":
        assert caught.value.date == "20251103" and caught.value.code == "600000.SH"
        assert caught.value.available == 1_000_000.
        assert caught.value.needed == pytest.approx(1_001_000.)


@pytest.mark.parametrize("entry", ["simulate", "run"])
@pytest.mark.parametrize("optional", [OMITTED, None, False, "", (), [], {}])
def test_api_omission_mutation_and_caller_context(entry, optional, monkeypatch):
    mutable, calls = [], []
    callback = lambda *_: None
    args = (mutable,)
    kwargs = {"take_profit": callback}
    if optional is not OMITTED:
        kwargs["audit_sink"] = optional  # Native optional kw; no normalization here.
    value = SimState(trades=mutable)

    def spy(*received_args, **received_kwargs):
        calls.append(1)
        assert received_args[0] is mutable
        assert received_kwargs.keys() == kwargs.keys()
        assert received_kwargs["take_profit"] is callback
        assert "minute_stop_trigger" not in received_kwargs
        if optional is not OMITTED:
            assert received_kwargs["audit_sink"] is optional
        mutable.append({"native_mutation": True})
        return value

    monkeypatch.setattr(native, entry, spy)
    before = (os.getcwd(), dict(os.environ), random.getstate(), list(sys.path))
    request = NativeApiRequest(
        family="csv_minute", native_entry=f"csv_minute_backtest.{entry}", args=args, kwargs=kwargs
    )
    result = run(request)
    assert calls == [1] and result.native_value is value
    assert result.native_value.trades is mutable and mutable == [{"native_mutation": True}]
    assert request.args is args and request.kwargs is kwargs
    assert result.native_artifact_refs is OMITTED
    assert (os.getcwd(), dict(os.environ), random.getstate(), list(sys.path)) == before


@pytest.mark.parametrize("family,entry,cli", [
    ("csv_minute", "unknown", False),
    ("csv_minute", "joint_return_replay.replay", False),
    ("joint_return", "csv_minute_backtest.simulate", False),
    ("v7", "csv_minute_backtest.simulate", False),
    ("grid_modeb", "csv_minute_backtest.run", False),
    ("csv_minute", CLI, False),
    ("csv_minute", "csv_minute_backtest.run", True),
    ("joint_return", CLI, True),
])
def test_unregistered_entry_cannot_reach_native(family, entry, cli, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unregistered entry reached native")

    monkeypatch.setattr(native, "simulate", forbidden)
    monkeypatch.setattr(native, "run", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    request = (
        NativeCliRequest(family=family, native_entry=entry, argv=[])
        if cli else NativeApiRequest(family=family, native_entry=entry)
    )
    with pytest.raises(UnregisteredEntryError, match="Unregistered research entry"):
        run(request)


@pytest.mark.parametrize("argv,status", [
    (["--help"], 0),
    ([], 2),
    (["--strategy", "version6", "--minute-stop-trigger", "invalid"], 2),
])
def test_cli_parser_exit_and_raw_bytes_without_lake(argv, status, tmp_path, cli_python):
    direct = subprocess.run(
        [cli_python, str(ROOT / CLI), *argv], cwd=tmp_path, capture_output=True, check=False
    )
    before = (os.getcwd(), dict(os.environ))
    request = NativeCliRequest(
        family="csv_minute", native_entry=CLI, argv=argv, context=CliContext(cwd=tmp_path)
    )
    result = run(request)
    assert isinstance(result, CliResult) and result.request is request and request.argv is argv
    assert result.native_exit_status == direct.returncode == status
    assert (result.stdout_bytes, result.stderr_bytes) == (direct.stdout, direct.stderr)
    assert isinstance(result.stdout_bytes, bytes) and isinstance(result.stderr_bytes, bytes)
    assert b"--strategy" in (result.stdout_bytes if status == 0 else result.stderr_bytes)
    assert result.native_artifact_refs is OMITTED
    assert (os.getcwd(), dict(os.environ)) == before
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("context", [
    CliContext(), CliContext(env_overlay={}),
    CliContext(cwd="literal/../child dir", env_overlay={"L1_CSV_TEST": "", "PYTHONPATH": "literal"}),
])
def test_cli_one_launch_literal_tokens_and_child_only_context(context, cli_python, monkeypatch):
    argv = ["--out-dir", "a b", "--tag", "", "--tag", "$(literal)", r".\path\..\file"]
    before = (os.getcwd(), dict(os.environ))
    stdout, stderr, calls = b"\xff\r\n", b"\x00native\n", []

    def launch(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, -15, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", launch)
    result = run(NativeCliRequest(family="csv_minute", native_entry=CLI, argv=argv, context=context))
    assert len(calls) == 1
    command, options = calls[0]
    assert command == [str(Path(cli_python).absolute()), str(ROOT / CLI), *argv]
    expected = {"capture_output": True, "check": False}
    if context.cwd is not OMITTED:
        expected["cwd"] = context.cwd
    if context.env_overlay is not OMITTED:
        expected["env"] = {**before[1], **context.env_overlay}
    assert options == expected
    assert result.native_exit_status == -15
    assert result.stdout_bytes is stdout and result.stderr_bytes is stderr
    assert (os.getcwd(), dict(os.environ)) == before


def test_missing_interpreter_fails_before_launch(tmp_path, monkeypatch):
    monkeypatch.setenv("OSKH_MERGE_PYTHON", str(tmp_path / "missing-python"))

    def forbidden(*args, **kwargs):
        pytest.fail("must not fall back to another interpreter")

    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(SystemExit) as caught:
        run(NativeCliRequest(family="csv_minute", native_entry=CLI, argv=[]))
    assert caught.value.code == 2


def test_transport_failure_is_not_a_native_exit(cli_python, monkeypatch):
    error, calls = FileNotFoundError("child cwd unavailable"), []

    def launch(*args, **kwargs):
        calls.append(1)
        raise error

    monkeypatch.setattr(subprocess, "run", launch)
    with pytest.raises(FileNotFoundError) as caught:
        run(NativeCliRequest(family="csv_minute", native_entry=CLI, argv=[]))
    assert caught.value is error and calls == [1]


def test_fresh_import_and_csv_dispatch_are_lazy():
    code = textwrap.dedent("""
        import os
        import sys
        sys.path.insert(0, sys.argv[1])
        before = (os.getcwd(), dict(os.environ), list(sys.path))
        import backtest.research.run_protocol as protocol
        assert 'backtest.research.run_protocol.facade' not in sys.modules
        from backtest.research.run_protocol.facade import run, UnregisteredEntryError
        assert protocol.run is run
        prefix = 'backtest.research.'
        engines = {prefix + name for name in (
            'csv_minute_backtest', 'joint_return_replay', 'csv_minute_backtest_v7', 'unified_exit_modeb')}
        assert not engines.intersection(sys.modules)
        assert not any(name.startswith(prefix + 'run_protocol.adapters') for name in sys.modules)
        try:
            run(protocol.NativeApiRequest(family='csv_minute', native_entry='unknown'))
        except UnregisteredEntryError:
            pass
        else:
            raise AssertionError('unregistered entry accepted')
        assert not engines.intersection(sys.modules)
        assert (os.getcwd(), dict(os.environ), list(sys.path)) == before
        try:
            run(protocol.NativeApiRequest(
                family='csv_minute', native_entry='csv_minute_backtest.run',
                args=('20251103', '20251104'),
                kwargs={'strategy': 'version6', 'stop_fill': 'close'}))
        except SystemExit as exc:
            assert 'minute entry refuses' in str(exc)
        else:
            raise AssertionError('native validation did not run')
        assert engines.intersection(sys.modules) == {prefix + 'csv_minute_backtest'}
        assert prefix + 'run_protocol.adapters.joint_return' not in sys.modules
        # The native CSV import itself prepends REPO to sys.path; L1 adds none.
        assert (os.getcwd(), dict(os.environ)) == before[:2]
    """)
    process = subprocess.run(
        [sys.executable, "-I", "-c", code, str(ROOT)], capture_output=True, timeout=30
    )
    assert process.returncode == 0, process.stdout + process.stderr
