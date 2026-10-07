"""Synthetic v7 delegation parity only; no lake or full V1/CLI writer certification."""

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

from backtest.research import csv_minute_backtest_v7 as native
from backtest.research.run_protocol import (
    OMITTED, ApiResult, CliContext, CliResult, NativeApiRequest, NativeCliRequest, run,
)
from backtest.research.run_protocol.facade import UnregisteredEntryError
from tests.test_csv_minute_backtest_v7 import D1, D2, SYMBOL, bar, daily, index_closes, reasons


ROOT = Path(__file__).resolve().parents[1]
API = "csv_minute_backtest_v7.simulate_v7"
CLI = "backtest/research/csv_minute_backtest_v7.py"


@pytest.fixture
def cli_python(monkeypatch):
    # Pin the explicitly selected test interpreter, including in CI.
    monkeypatch.setenv("OSKH_MERGE_PYTHON", sys.executable)
    monkeypatch.delenv("OSKH_PYTHON_VERSION", raising=False)
    return sys.executable


@pytest.mark.parametrize("case", ["frame_trial", "skip_cash", "add"])
@pytest.mark.parametrize("cash_order", [OMITTED, False], ids=["omitted", "explicit_off"])
def test_simulate_full_state_parity_and_reference_identity(case, cash_order, monkeypatch):
    kwargs = {"rule_profile": "legacy"}
    if cash_order is not OMITTED:
        kwargs["fix_minute_cash_order"] = cash_order
    if case == "frame_trial":
        frame = pd.DataFrame(
            {"open": [100.0], "high": [100.0], "low": [100.0], "close": [100.0],
             "ymd": ["20260901"], "hm": [895]},
            index=pd.DatetimeIndex([pd.Timestamp("2026-09-01 14:55:00")]),
        )
        args = ({SYMBOL: frame}, daily(), {D1: [SYMBOL]}, [D1])
    else:
        rows = [bar(D1, 895, 100)]
        if case == "add":
            rows += [bar(D2, 885, 104), bar(D2, 895, 108)]
        else:
            kwargs["cash_total"] = 1.0
        args = ({SYMBOL: rows}, daily(), {D1: [SYMBOL]}, [D1, D2])
    before = deepcopy(args)
    expected = native.simulate_v7(*args, **kwargs)
    if cash_order is OMITTED:
        explicit = native.simulate_v7(*args, **kwargs, fix_minute_cash_order=False)
        assert asdict(expected) == asdict(explicit)
    simulate, calls, returned = native.simulate_v7, [], []

    def spy(*received_args, **received_kwargs):
        calls.append(1)
        assert len(received_args) == len(args)
        assert all(a is b for a, b in zip(received_args, args))
        assert received_kwargs == kwargs
        value = simulate(*received_args, **received_kwargs)
        returned.append(value)
        return value

    monkeypatch.setattr(native, "simulate_v7", spy)
    request = NativeApiRequest(family="v7", native_entry=API, args=args, kwargs=kwargs)
    result = run(request)
    assert isinstance(result, ApiResult) and result.request is request
    assert calls == [1] and result.native_value is returned[0]
    assert type(result.native_value) is native.SimResult
    # All fields, including compare=False fields; preserve trade/reason order.
    assert asdict(result.native_value) == asdict(expected)
    for name in ("positions", "trades", "equity_curve", "volume_cap", "exdiv_economics"):
        assert getattr(result.native_value, name) is getattr(returned[0], name)
    assert result.native_artifact_refs is OMITTED
    assert request.args is args and request.kwargs is kwargs
    assert len(expected.equity_curve) == len(args[3])
    if case == "skip_cash":
        assert reasons(expected) == ["skip_cash"]
        assert expected.trades[0]["side"] == "skip" and expected.trades[0]["shares"] == 0
        assert expected.cash == 1.0 and expected.positions == {}
    else:
        position = result.native_value.positions[SYMBOL]
        assert position is returned[0].positions[SYMBOL]
        assert position.lots is returned[0].positions[SYMBOL].lots
        assert expected.trades[0]["hm"] == 895
        if case == "frame_trial":
            assert reasons(expected) == ["buy:trial"]
            assert position.stage == native.TRIAL and len(position.lots) == 1
        else:
            assert reasons(expected) == ["buy:trial", "buy:add_a104", "buy:add_a108"]
            assert position.stage == native.SIX and len(position.lots) == 3
    if case == "frame_trial":
        pd.testing.assert_frame_equal(args[0][SYMBOL], before[0][SYMBOL])
        assert args[1:] == before[1:]
    else:
        assert args == before


@pytest.mark.parametrize("problem,match", [
    ("short_index", "11 warmup"),
    ("tail_without_cash_order", "fix-minute-cash-order"),
])
def test_real_native_failure_is_same_instance_once(problem, match, monkeypatch):
    args, kwargs = ({}, {}, {}, index_closes([100.0] * 11)), {}
    if problem == "tail_without_cash_order":
        args, kwargs = (None, None, None), {"tail_window_buy": True}
    kwargs.setdefault("rule_profile", "legacy")
    simulate = native.simulate_v7
    with pytest.raises(ValueError, match=match) as direct:
        simulate(*args, **kwargs)
    calls, observed = [], []

    def spy(*args, **kwargs):
        calls.append(1)
        try:
            return simulate(*args, **kwargs)
        except BaseException as exc:
            observed.append(exc)
            raise

    monkeypatch.setattr(native, "simulate_v7", spy)
    with pytest.raises(ValueError, match=match) as caught:
        run(NativeApiRequest(family="v7", native_entry=API, args=args, kwargs=kwargs))
    assert calls == [1] and len(observed) == 1 and caught.value is observed[0]
    assert caught.value.args == direct.value.args


def test_api_system_exit_is_raised_once_not_returned(monkeypatch):
    # Boundary injection only: real native validation failures are covered above.
    error, calls = SystemExit("native exit"), []
    cause = ValueError("native cause")

    def fail(*args, **kwargs):
        calls.append(1)
        raise error from cause

    monkeypatch.setattr(native, "simulate_v7", fail)
    with pytest.raises(SystemExit) as caught:
        run(NativeApiRequest(family="v7", native_entry=API))
    assert caught.value is error and caught.value.__cause__ is cause and calls == [1]


@pytest.mark.parametrize("optional", [OMITTED, None, False, "", (), [], {}])
def test_api_omission_mutation_and_caller_context(optional, monkeypatch):
    mutable, calls = [], []
    callback = lambda *_: None
    args = (mutable,)
    kwargs = {"volume_for_bucket": callback, "audit_sink": mutable}
    if optional is not OMITTED:
        kwargs["fix_minute_cash_order"] = optional
    value = native.SimResult(cash=0.0, trades=mutable)

    def spy(*received_args, **received_kwargs):
        calls.append(1)
        assert received_args == args and received_args[0] is mutable
        assert received_kwargs.keys() == kwargs.keys()
        assert received_kwargs["volume_for_bucket"] is callback
        assert received_kwargs["audit_sink"] is mutable
        assert "tail_window_buy" not in received_kwargs and "pool_dir" not in received_kwargs
        if optional is not OMITTED:
            assert received_kwargs["fix_minute_cash_order"] is optional
        mutable.append({"native_mutation": True})
        return value

    monkeypatch.setattr(native, "simulate_v7", spy)
    before = (os.getcwd(), dict(os.environ), random.getstate(), list(sys.path))
    request = NativeApiRequest(family="v7", native_entry=API, args=args, kwargs=kwargs)
    result = run(request)
    assert calls == [1] and result.native_value is value
    assert result.native_value.trades is mutable and mutable == [{"native_mutation": True}]
    assert request.args is args and request.kwargs is kwargs
    assert result.native_artifact_refs is OMITTED
    assert (os.getcwd(), dict(os.environ), random.getstate(), list(sys.path)) == before


@pytest.mark.parametrize("family,entry,cli", [
    ("v7", "unknown", False),
    ("v7", "csv_minute_backtest_v7.run", False),
    ("v7", "csv_minute_backtest_v7.write_run_artifacts", False),
    ("v7", "csv_minute_backtest.simulate", False),
    ("v7", "joint_return_replay.replay", False),
    ("csv_minute", API, False),
    ("joint_return", API, False),
    ("grid_modeb", API, False),
    ("v7", CLI, False),
    ("v7", API, True),
    ("csv_minute", CLI, True),
])
def test_unregistered_entry_cannot_reach_native(family, entry, cli, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unregistered entry reached native")

    monkeypatch.setattr(native, "simulate_v7", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    request = (
        NativeCliRequest(family=family, native_entry=entry, argv=[])
        if cli else NativeApiRequest(family=family, native_entry=entry)
    )
    with pytest.raises(UnregisteredEntryError, match="Unregistered research entry"):
        run(request)


@pytest.mark.parametrize("argv,status,marker", [
    (["--help"], 0, b"--pool-dir"),
    ([], 2, b"--start"),
    (["--start", "20260901", "--end", "20260902"], 1,
     b"--pool-dir or OSKH_TURTLE_POOL_DIR is required"),
    (["--start", "20260901", "--end", "20260902", "--tail-volume-unit", "invalid"],
     2, b"--tail-volume-unit: invalid choice"),
])
def test_cli_parser_exit_and_raw_bytes_without_lake(argv, status, marker, tmp_path, cli_python,
                                                  monkeypatch):
    monkeypatch.setenv("OSKH_TURTLE_POOL_DIR", str(tmp_path / "parent-only-pool"))
    overlay = {"OSKH_TURTLE_POOL_DIR": ""}
    direct = subprocess.run(
        [cli_python, str(ROOT / CLI), *argv], cwd=tmp_path,
        env={**os.environ, **overlay}, capture_output=True, check=False,
    )
    before = (os.getcwd(), dict(os.environ))
    request = NativeCliRequest(
        family="v7", native_entry=CLI, argv=argv,
        context=CliContext(cwd=tmp_path, env_overlay=overlay),
    )
    result = run(request)
    assert isinstance(result, CliResult) and result.request is request and request.argv is argv
    assert result.native_exit_status == direct.returncode == status
    assert (result.stdout_bytes, result.stderr_bytes) == (direct.stdout, direct.stderr)
    assert isinstance(result.stdout_bytes, bytes) and isinstance(result.stderr_bytes, bytes)
    assert marker in (result.stdout_bytes if status == 0 else result.stderr_bytes)
    assert result.native_artifact_refs is OMITTED
    assert (os.getcwd(), dict(os.environ)) == before
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("context", [
    CliContext(), CliContext(env_overlay={}),
    CliContext(cwd="literal/../child dir", env_overlay={"OSKH_TURTLE_POOL_DIR": "", "PYTHONPATH": "literal"}),
])
def test_cli_one_launch_literal_tokens_and_child_only_context(context, cli_python, monkeypatch):
    argv = ["--output-dir", "a b", "--pool-dir", "", "--pool-dir", "$(literal)", r".\path\..\file"]
    before = (os.getcwd(), dict(os.environ))
    stdout, stderr, calls = b"\xff\r\n", b"\x00native\n", []

    def launch(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, -15, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", launch)
    result = run(NativeCliRequest(family="v7", native_entry=CLI, argv=argv, context=context))
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
    assert result.native_artifact_refs is OMITTED
    assert (os.getcwd(), dict(os.environ)) == before


def test_missing_interpreter_fails_before_launch(tmp_path, monkeypatch):
    monkeypatch.setenv("OSKH_MERGE_PYTHON", str(tmp_path / "missing-python"))

    def forbidden(*args, **kwargs):
        pytest.fail("must not fall back to another interpreter")

    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(SystemExit) as caught:
        run(NativeCliRequest(family="v7", native_entry=CLI, argv=[]))
    assert caught.value.code == 2


def test_transport_failure_is_not_a_native_exit(cli_python, monkeypatch):
    error, calls = FileNotFoundError("child cwd unavailable"), []

    def launch(*args, **kwargs):
        calls.append(1)
        raise error

    monkeypatch.setattr(subprocess, "run", launch)
    with pytest.raises(FileNotFoundError) as caught:
        run(NativeCliRequest(family="v7", native_entry=CLI, argv=[]))
    assert caught.value is error and calls == [1]


def test_fresh_import_and_v7_dispatch_are_lazy():
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
            'csv_minute_backtest', 'csv_minute_backtest_v7', 'joint_return_replay', 'unified_exit_modeb')}
        assert not engines.intersection(sys.modules)
        assert not any(name.startswith(prefix + 'run_protocol.adapters') for name in sys.modules)
        try:
            run(protocol.NativeApiRequest(family='v7', native_entry='unknown'))
        except UnregisteredEntryError:
            pass
        else:
            raise AssertionError('unregistered entry accepted')
        assert not engines.intersection(sys.modules)
        assert not any(name.startswith(prefix + 'run_protocol.adapters') for name in sys.modules)
        assert (os.getcwd(), dict(os.environ), list(sys.path)) == before
        try:
            run(protocol.NativeApiRequest(
                family='v7', native_entry='csv_minute_backtest_v7.simulate_v7',
                args=(None, None, None),
                kwargs={'tail_window_buy': True, 'rule_profile': 'legacy'}))
        except ValueError as exc:
            assert 'fix-minute-cash-order' in str(exc)
        else:
            raise AssertionError('native validation did not run')
        assert engines.intersection(sys.modules) == {prefix + 'csv_minute_backtest_v7'}
        assert prefix + 'run_protocol.adapters.v7' in sys.modules
        assert prefix + 'run_protocol.adapters.csv_minute' not in sys.modules
        assert prefix + 'run_protocol.adapters.joint_return' not in sys.modules
        assert (os.getcwd(), dict(os.environ), list(sys.path)) == before
    """)
    process = subprocess.run(
        [sys.executable, "-I", "-c", code, str(ROOT)], capture_output=True, timeout=30
    )
    assert process.returncode == 0, process.stdout + process.stderr
