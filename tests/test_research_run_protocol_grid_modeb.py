"""Synthetic grid_modeb delegation parity; narrowed B1/X1, no lake certification."""

import json
import os
from pathlib import Path
import random
import subprocess
import sys
import textwrap

import pandas as pd
import pytest

from backtest.research import unified_exit_modeb as native
from backtest.research.run_protocol import (
    OMITTED, ApiResult, CliContext, CliResult, NativeApiRequest, NativeCliRequest, run,
)
from backtest.research.run_protocol.facade import UnregisteredEntryError
from tests.test_unified_exit_modeb_exit import CODE


ROOT = Path(__file__).resolve().parents[1]
API = "unified_exit_modeb.run_modeb"
CLI = "scripts/research/run_unified_exit_modeb.py"


@pytest.fixture
def cli_python(monkeypatch):
    monkeypatch.setenv("OSKH_MERGE_PYTHON", sys.executable)
    monkeypatch.delenv("OSKH_PYTHON_VERSION", raising=False)
    return sys.executable


@pytest.fixture
def synthetic_run(tmp_path):
    # Same two-half-window shape as test_pipeline_reports_robustness_and_isolation.
    sessions = ["20251023", "20251024", "20260407", "20260408", "20260909"]
    pool = tmp_path / "pool"
    pool.mkdir()
    for day in (sessions[0], sessions[2]):
        (pool / f"{day}.csv").write_text(f"code,name\n{CODE},synthetic\n", encoding="utf-8")
    bars = {CODE: pd.DataFrame(
        {"open": [100] * 5, "close": [100] * 5}, index=pd.to_datetime(sessions),
    )}
    minutes = {CODE: pd.DataFrame({
        "ymd": sessions, "hm": [900] * 5,
        "high": [100] * 5, "low": [100] * 5, "close": [100] * 5,
    })}
    return (pool,), dict(sessions=sessions, bars=bars, minute_bars=minutes,
                        exdiv={}, index_block={})


def test_full_pipeline_parity_identity_and_one_shot(synthetic_run, tmp_path, monkeypatch):
    args, kwargs = synthetic_run
    direct_out, facade_out = tmp_path / "direct", tmp_path / "facade"
    expected = native.run_modeb(*args, **kwargs, out_dir=direct_out)
    native_run_modeb = native.run_modeb
    kwargs["out_dir"] = facade_out
    calls, returned = [], []

    def spy(*received_args, **received_kwargs):
        calls.append(1)
        assert len(received_args) == len(args)
        assert all(a is b for a, b in zip(received_args, args))
        assert received_kwargs.keys() == kwargs.keys()
        assert all(received_kwargs[key] is value for key, value in kwargs.items())
        assert "tol" not in received_kwargs and "workers" not in received_kwargs
        # The adapter must leave all spec expansion and robustness runs here.
        value = native_run_modeb(*received_args, **received_kwargs)
        returned.append(value)
        return value

    monkeypatch.setattr(native, "run_modeb", spy)
    request = NativeApiRequest(family="grid_modeb", native_entry=API, args=args, kwargs=kwargs)
    result = run(request)
    assert isinstance(result, ApiResult) and result.request is request
    assert request.args is args and request.kwargs is kwargs
    assert calls == [1] and result.native_value is returned[0]
    assert result.native_artifact_refs is OMITTED
    value = result.native_value
    assert type(value) is dict
    assert set(value) == {"ranked", "anchors", "robustness", "instances", "matrix", "sessions"}
    for key in value:
        assert value[key] is returned[0][key]
    # Full returned economics, including each instance/spec ExitResult and metrics.
    assert value == expected
    assert len(value["ranked"]) == 23
    assert set(value["anchors"]) == {"anchor_hold_end", "r1_n1", "oracle", "delist_zero"}
    assert set(value["matrix"]) == {s.label() for s in native.iter_grid()} | {"oracle", "delist_zero"}
    assert len(value["instances"]) == 2
    assert all(len(exits) == 2 for exits in value["matrix"].values())
    robust = value["robustness"]
    assert len(robust["half_windows"]["h1"]) == len(robust["half_windows"]["h2"]) == 20
    assert robust["half_windows"]["top20_overlap"] == 20
    assert all(robust[key] for key in ("plateau", "board", "month", "next_open_buy"))
    # These synthetic reports have no path or timing fields; compare without scrubbing.
    reports = {"summary.json", "ranking.csv", "instance_detail_top.csv"}
    assert {p.name for p in direct_out.iterdir()} == {p.name for p in facade_out.iterdir()} == reports
    for name in reports:
        assert (facade_out / name).read_bytes() == (direct_out / name).read_bytes()
    summary = json.loads((facade_out / "summary.json").read_text(encoding="utf-8"))
    assert summary["meta"]["mode"] == "B"
    assert "Q38=A" in summary["meta"]["oracle"]
    assert summary["meta"]["minute_coverage"]["covered_codes"] == 1
    detail = pd.read_csv(facade_out / "instance_detail_top.csv")
    assert set(detail.loc[detail.is_trade, "sell_hm"]) == {900}
    assert not (tmp_path / "unified_exit_modea").exists()


def test_real_native_failure_is_same_instance_once(tmp_path, monkeypatch):
    args = (tmp_path / "unused-pool",)
    kwargs = {"out_dir": tmp_path / "unified_exit_modea" / "nested"}
    with pytest.raises(ValueError, match="Mode B") as direct:
        native.run_modeb(*args, **kwargs)
    native_run_modeb = native.run_modeb
    calls, observed = [], []

    def spy(*args, **kwargs):
        calls.append(1)
        try:
            return native_run_modeb(*args, **kwargs)
        except BaseException as exc:
            observed.append(exc)
            raise

    monkeypatch.setattr(native, "run_modeb", spy)
    with pytest.raises(ValueError, match="Mode B") as caught:
        run(NativeApiRequest(family="grid_modeb", native_entry=API, args=args, kwargs=kwargs))
    assert calls == [1] and len(observed) == 1 and caught.value is observed[0]
    assert caught.value.args == direct.value.args
    assert not list(tmp_path.iterdir())


def test_api_system_exit_is_raised_once_not_returned(monkeypatch):
    error, cause, calls = SystemExit("native exit"), ValueError("native cause"), []

    def fail(*args, **kwargs):
        calls.append(1)
        raise error from cause

    monkeypatch.setattr(native, "run_modeb", fail)
    with pytest.raises(SystemExit) as caught:
        run(NativeApiRequest(family="grid_modeb", native_entry=API))
    assert caught.value is error and caught.value.__cause__ is cause and calls == [1]


@pytest.mark.parametrize("optional", [OMITTED, None, False, "", (), [], {}])
def test_api_omission_mutation_and_caller_context(optional, monkeypatch):
    # Transport boundary only; these values do not certify native tol combinations.
    mutable, calls = {}, []
    args, kwargs = (object(),), {"bars": mutable}
    if optional is not OMITTED:
        kwargs["tol"] = optional
    value = {"matrix": mutable}

    def spy(*received_args, **received_kwargs):
        calls.append(1)
        assert received_args[0] is args[0]
        assert received_kwargs.keys() == kwargs.keys()
        assert received_kwargs["bars"] is mutable
        assert not {"workers", "cash_pool", "start", "end", "out_dir"}.intersection(received_kwargs)
        if optional is not OMITTED:
            assert received_kwargs["tol"] is optional
        mutable["native_mutation"] = True
        return value

    monkeypatch.setattr(native, "run_modeb", spy)
    before = (os.getcwd(), dict(os.environ), random.getstate(), list(sys.path))
    request = NativeApiRequest(family="grid_modeb", native_entry=API, args=args, kwargs=kwargs)
    result = run(request)
    assert calls == [1] and result.native_value is value
    assert result.native_value["matrix"] is mutable and mutable == {"native_mutation": True}
    assert request.args is args and request.kwargs is kwargs
    assert result.native_artifact_refs is OMITTED
    assert (os.getcwd(), dict(os.environ), random.getstate(), list(sys.path)) == before


@pytest.mark.parametrize("family,entry,cli", [
    ("grid_modeb", "unknown", False),
    ("grid_modeb", "unified_exit_modeb.evaluate_exit_modeb", False),
    ("grid_modeb", "unified_exit_modeb.evaluate_matrix", False),
    ("grid_modeb", "unified_exit_modeb.assemble_instances", False),
    ("grid_modeb", "unified_exit_modeb.write_reports", False),
    ("grid_modeb", "unified_exit_modeb.main", False),
    ("grid_modeb", "fullstrat_research_hooks.run_modeb", False),
    ("grid_modeb", "joint_return_replay.replay", False),
    ("grid_modeb", "csv_minute_backtest.run", False),
    ("grid_modeb", "csv_minute_backtest_v7.simulate_v7", False),
    ("joint_return", API, False),
    ("csv_minute", API, False),
    ("v7", API, False),
    ("modeb", API, False),
    ("Mode B", API, False),
    ("grid_modeb_native", API, False),
    ("grid_modeb", CLI, False),
    ("grid_modeb", API, True),
    ("joint_return", CLI, True),
])
def test_unregistered_entry_cannot_reach_native(family, entry, cli, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unregistered entry reached native")

    monkeypatch.setattr(native, "run_modeb", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    request = (
        NativeCliRequest(family=family, native_entry=entry, argv=[])
        if cli else NativeApiRequest(family=family, native_entry=entry)
    )
    with pytest.raises(UnregisteredEntryError, match="Unregistered research entry"):
        run(request)


@pytest.mark.parametrize("argv,status,marker", [
    (["--help"], 0, "窄网格".encode("utf-8")),
    (["--workers", "invalid"], 2, b"--workers: invalid int value"),
    (["--out-dir", "unified_exit_modea/nested"], 2, b"Mode B"),
])
def test_cli_parser_exit_and_raw_bytes_without_lake(argv, status, marker, tmp_path, cli_python):
    overlay = {"PYTHONIOENCODING": "utf-8"}
    direct = subprocess.run(
        [cli_python, str(ROOT / CLI), *argv], cwd=tmp_path,
        env={**os.environ, **overlay}, capture_output=True, check=False,
    )
    before = (os.getcwd(), dict(os.environ))
    request = NativeCliRequest(
        family="grid_modeb", native_entry=CLI, argv=argv,
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
    CliContext(cwd="literal/../child dir", env_overlay={"GRID_TEST": "", "PYTHONPATH": "literal"}),
])
def test_cli_one_launch_literal_tokens_and_child_only_context(context, cli_python, monkeypatch):
    argv = ["--out-dir", "a b", "--pool-dir", "", "--pool-dir", "$(literal)", r".\path\..\file"]
    before = (os.getcwd(), dict(os.environ))
    stdout, stderr, calls = b"\xff\r\n", b"\x00native\n", []

    def launch(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, -15, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", launch)
    result = run(NativeCliRequest(family="grid_modeb", native_entry=CLI, argv=argv, context=context))
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
        run(NativeCliRequest(family="grid_modeb", native_entry=CLI, argv=[]))
    assert caught.value.code == 2


def test_transport_failure_is_not_a_native_exit(cli_python, monkeypatch):
    error, calls = FileNotFoundError("child cwd unavailable"), []

    def launch(*args, **kwargs):
        calls.append(1)
        raise error

    monkeypatch.setattr(subprocess, "run", launch)
    with pytest.raises(FileNotFoundError) as caught:
        run(NativeCliRequest(family="grid_modeb", native_entry=CLI, argv=[]))
    assert caught.value is error and calls == [1]


def test_cli_clean_parent_uses_working_child_and_api_imports_on_call(tmp_path, cli_python):
    code = textwrap.dedent("""
        import importlib.util
        import os
        import subprocess
        import sys
        sys.path.insert(0, sys.argv[1])
        assert importlib.util.find_spec('numpy') is None
        before = (os.getcwd(), dict(os.environ), list(sys.path))
        allowed = {
            'backtest', 'backtest.research', 'backtest.research.run_protocol',
            'backtest.research.run_protocol.types', 'backtest.research.run_protocol.facade',
            'backtest.research.run_protocol.adapters',
            'backtest.research.run_protocol.adapters.grid_modeb',
            'scripts', 'scripts._script_bootstrap',
        }
        class ParentImportFence:
            def find_spec(self, fullname, path=None, target=None):
                assert fullname in allowed or fullname.split('.')[0] in sys.stdlib_module_names, fullname
        fence = ParentImportFence()
        sys.meta_path.insert(0, fence)
        from backtest.research.run_protocol import CliResult, NativeApiRequest, NativeCliRequest, run
        entry = 'scripts/research/run_unified_exit_modeb.py'
        direct = subprocess.run(
            [sys.argv[2], sys.argv[1] + '/' + entry, '--help'],
            capture_output=True, check=False,
        )
        result = run(NativeCliRequest(family='grid_modeb', native_entry=entry, argv=['--help']))
        assert isinstance(result, CliResult)
        assert result.native_exit_status == direct.returncode == 0
        assert (result.stdout_bytes, result.stderr_bytes) == (direct.stdout, direct.stderr)
        assert b'--workers' in result.stdout_bytes
        assert not {'numpy', 'pandas', 'backtest.research.unified_exit_modeb'}.intersection(sys.modules)
        assert (os.getcwd(), dict(os.environ), list(sys.path)) == before
        sys.meta_path.remove(fence)
        # This parent lacks engine dependencies; only invoking the API needs them.
        try:
            run(NativeApiRequest(family='grid_modeb', native_entry='unified_exit_modeb.run_modeb'))
        except ModuleNotFoundError as exc:
            assert exc.name == 'numpy', exc
        else:
            raise AssertionError('API did not import its native engine')
    """)
    process = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", code, str(ROOT), cli_python],
        cwd=tmp_path, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True, timeout=30,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert not list(tmp_path.iterdir())


def test_fresh_import_and_grid_modeb_dispatch_are_lazy(tmp_path):
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
            run(protocol.NativeApiRequest(family='grid_modeb', native_entry='unknown'))
        except UnregisteredEntryError:
            pass
        else:
            raise AssertionError('unregistered entry accepted')
        assert not engines.intersection(sys.modules)
        assert not any(name.startswith(prefix + 'run_protocol.adapters') for name in sys.modules)
        assert (os.getcwd(), dict(os.environ), list(sys.path)) == before
        try:
            run(protocol.NativeApiRequest(
                family='grid_modeb', native_entry='unified_exit_modeb.run_modeb',
                args=('unused-pool',), kwargs={'out_dir': sys.argv[2]}))
        except ValueError as exc:
            assert 'Mode B' in str(exc)
        else:
            raise AssertionError('native validation did not run')
        assert engines.intersection(sys.modules) == {prefix + 'unified_exit_modeb'}
        assert prefix + 'run_protocol.adapters.grid_modeb' in sys.modules
        for name in ('csv_minute', 'v7', 'joint_return'):
            assert prefix + 'run_protocol.adapters.' + name not in sys.modules
        assert (os.getcwd(), dict(os.environ), list(sys.path)) == before
    """)
    process = subprocess.run(
        [sys.executable, "-I", "-c", code, str(ROOT), str(tmp_path / "unified_exit_modea")],
        capture_output=True, timeout=30,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert not list(tmp_path.iterdir())
