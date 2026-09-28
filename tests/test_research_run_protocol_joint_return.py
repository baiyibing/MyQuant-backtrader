"""Data-free JR Mode B delegation parity, not SSOT NAV comparison eligibility."""

from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import textwrap

import pytest

from backtest.research import joint_return_replay as jr
from backtest.research.run_protocol import (
    OMITTED, ApiResult, CliContext, CliResult, NativeApiRequest, NativeCliRequest, run,
)
from backtest.research.run_protocol.facade import UnregisteredEntryError
from tests import test_joint_return_replay as fixtures


ROOT = Path(__file__).resolve().parents[1]
CLI = "scripts/research/run_joint_return_replay.py"
ARTIFACTS = {"orders.csv", "fills.csv", "daily_nav.csv", "summary.json"}


@pytest.fixture(params=["synthetic", "frozen"])
def pack(request):
    if request.param == "frozen":
        manifest, rows, bars = fixtures.frozen_bundle()
        bars["metadata"]["reference_marks"] = fixtures.frozen_marks(rows)
    else:
        manifest, rows = fixtures.bundle(
            [fixtures.spec(quantity=200)], fees={"buy_rate": 0.001, "minimum": 5}
        )
        bars = fixtures.minute_bars(manifest, rows, price=11, capacity=100)
    return manifest, rows, fixtures.seal(bars)


@pytest.fixture
def disk_pack(tmp_path, pack):
    manifest, rows, bars = pack
    writer = fixtures.write_frozen_bundle if manifest["kind"] == "frozen" else fixtures.write_bundle
    intents = writer(tmp_path, manifest, rows)
    prices = tmp_path / "prices.json"
    prices.write_bytes(jr.canonical_bytes(bars))
    return manifest, intents, prices


@pytest.fixture
def cli_python(monkeypatch):
    # Explicit pin to the interpreter selected for this test run, including CI.
    monkeypatch.setenv("OSKH_MERGE_PYTHON", sys.executable)
    monkeypatch.delenv("OSKH_PYTHON_VERSION", raising=False)
    return sys.executable


@pytest.mark.parametrize("mode", ["M-REF", "M-LAG", "all"])
@pytest.mark.parametrize("version", [OMITTED, "v1", "v2"])
def test_replay_modeb_deep_parity_and_input_identity(pack, mode, version, monkeypatch):
    kwargs = {"arm": "P-BASE", "fill_mode": mode}
    if version is not OMITTED:
        kwargs["validate_version"] = version
    before = deepcopy(pack)
    expected = jr.replay(*pack, **kwargs)
    native = jr.replay
    returned = []

    def spy(*args, **received):
        assert all(a is b for a, b in zip(args, pack))
        assert received == kwargs
        value = native(*args, **received)
        returned.append(value)
        return value

    monkeypatch.setattr(jr, "replay", spy)
    request = NativeApiRequest(
        family="joint_return", native_entry="joint_return_replay.replay", args=pack, kwargs=kwargs
    )
    result = run(request)
    assert isinstance(result, ApiResult) and result.request is request
    assert len(returned) == 1 and result.native_value is returned[0]
    assert result.native_value == expected  # All orders/fills/NAV/flags, not a subset.
    assert result.native_artifact_refs is OMITTED
    assert pack == before and request.args is pack and request.kwargs is kwargs
    if pack[0]["kind"] == "frozen":
        assert expected["summary"]["contract_hash"] == jr.FROZEN_CONTRACT_HASH
        assert expected["summary"]["real_execution_status"] == "INPUT_BLOCKED"
        for fill in expected["fills"]:
            assert {key: fill[key] for key in jr.INTENT_FIELDS} == pack[1][0]
            assert fill["price"] == (10 if fill["fill_id"] == "M-REF" else 11)


def test_native_all_arms_and_modes_expand_in_one_call(monkeypatch):
    manifest, rows = fixtures.bundle([fixtures.spec()])
    args = (manifest, rows, fixtures.minute_bars(manifest, rows))
    kwargs = {"arm": "all", "fill_mode": "all"}
    expected = jr.replay(*args, **kwargs)
    native, calls = jr.replay, []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return native(*args, **kwargs)

    monkeypatch.setattr(jr, "replay", spy)
    result = run(NativeApiRequest(
        family="joint_return", native_entry="joint_return_replay.replay", args=args, kwargs=kwargs
    ))
    assert len(calls) == 1
    assert result.native_value == expected
    assert len(expected["summary"]["results"]) == len(jr.ARMS) * len(jr.FILL_MODES)


@pytest.mark.parametrize("mode", ["M-REF", "M-LAG", "all"])
@pytest.mark.parametrize("version", [OMITTED, "v2"])
def test_writer_four_files_byte_parity_and_summary_last(disk_pack, tmp_path, mode, version, monkeypatch):
    manifest, intents, prices = disk_pack
    kwargs = {"arm": "P-BASE", "fill_mode": mode}
    if version is not OMITTED:
        kwargs["validate_version"] = version
    direct = jr.run_replay(intents, prices, out=tmp_path / "direct" / manifest["run_id"], **kwargs)
    out = tmp_path / "facade" / manifest["run_id"]
    native, returned, writes = jr.run_replay, [], []
    write_bytes = Path.write_bytes

    def record_write(path, data):
        if path.parent == out:
            writes.append(path.name)
        return write_bytes(path, data)

    def spy(*args, **kwargs):
        assert not out.exists()  # Facade must not pre-create the writer directory.
        value = native(*args, **kwargs)
        returned.append(value)
        return value

    monkeypatch.setattr(Path, "write_bytes", record_write)
    monkeypatch.setattr(jr, "run_replay", spy)
    result = run(NativeApiRequest(
        family="joint_return", native_entry="joint_return_replay.run_replay",
        args=(intents, prices), kwargs={**kwargs, "out": out},
    ))
    assert len(returned) == 1 and result.native_value is returned[0]
    assert result.native_artifact_refs == (out,)
    assert result.native_artifact_refs[0] is result.native_value
    assert set(writes) == ARTIFACTS and writes[-1] == "summary.json"
    assert {p.name for p in direct.iterdir()} == {p.name for p in out.iterdir()} == ARTIFACTS
    for name in ARTIFACTS:
        assert (direct / name).read_bytes() == (out / name).read_bytes()


@pytest.mark.parametrize("problem", ["existing_empty", "wrong_basename"])
def test_native_writer_rejections_are_preserved(disk_pack, tmp_path, problem):
    manifest, intents, prices = disk_pack
    out = tmp_path / (manifest["run_id"] if problem == "existing_empty" else "wrong-id")
    if problem == "existing_empty":
        out.mkdir()
    kwargs = {"arm": "P-BASE", "fill_mode": "M-LAG", "out": out}
    with pytest.raises(jr.ReplayError) as direct:
        jr.run_replay(intents, prices, **kwargs)
    with pytest.raises(jr.ReplayError) as delegated:
        run(NativeApiRequest(
            family="joint_return", native_entry="joint_return_replay.run_replay",
            args=(intents, prices), kwargs=kwargs,
        ))
    assert delegated.value.args == direct.value.args
    assert delegated.value.status == direct.value.status
    if problem == "existing_empty":
        assert out.is_dir() and not list(out.iterdir())
    else:
        assert not out.exists()


@pytest.mark.parametrize("entry", ["replay", "run_replay"])
@pytest.mark.parametrize("optional", [OMITTED, None, False, "", (), [], {}])
def test_api_omission_decimal_mutation_and_caller_context(entry, optional, monkeypatch):
    amount, mutable, calls = Decimal("12.3400"), [], []
    args = (mutable, amount)
    kwargs = {"amount": amount}
    if optional is not OMITTED:
        kwargs["optional"] = optional
    value = {"nested": [amount]}
    if entry == "run_replay":
        value = Path("native-completed-directory")

    def spy(*received_args, **received_kwargs):
        calls.append(1)
        assert received_args[0] is mutable and received_args[1] is amount
        assert received_kwargs["amount"] is amount
        assert received_kwargs.keys() == kwargs.keys()
        if optional is not OMITTED:
            assert received_kwargs["optional"] is optional
        mutable.append(amount)  # Native mutations must remain visible.
        return value

    monkeypatch.setattr(jr, entry, spy)
    before = (os.getcwd(), dict(os.environ), random.getstate(), list(sys.path))
    request = NativeApiRequest(
        family="joint_return", native_entry=f"joint_return_replay.{entry}", args=args, kwargs=kwargs
    )
    result = run(request)
    assert calls == [1] and result.native_value is value
    assert mutable[0] is amount and request.args is args and request.kwargs is kwargs
    assert (os.getcwd(), dict(os.environ), random.getstate(), list(sys.path)) == before


@pytest.mark.parametrize("entry", ["replay", "run_replay"])
@pytest.mark.parametrize("kind", ["ReplayError", "SystemExit"])
def test_same_exception_instance_is_raised_once(entry, kind, monkeypatch):
    manifest, rows = fixtures.bundle()
    try:
        jr.replay(manifest, rows, None, arm="P-BASE", fill_mode="M-LAG")
    except jr.ReplayError as caught:
        error = caught
    if kind == "SystemExit":
        error = SystemExit(2)
    cause = RuntimeError("original native cause")
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        try:
            raise cause
        except RuntimeError:
            raise error from cause

    monkeypatch.setattr(jr, entry, fail)
    with pytest.raises(type(error)) as caught:
        run(NativeApiRequest(family="joint_return", native_entry=f"joint_return_replay.{entry}"))
    assert caught.value is error and calls == [1]
    assert error.__cause__ is cause and error.__context__ is cause


@pytest.mark.parametrize("kwargs", [{}, {"arm": "P-BASE"}, {"fill_mode": "M-LAG"}])
def test_required_api_selection_stays_native(kwargs):
    manifest, rows = fixtures.bundle()
    args = (manifest, rows, fixtures.minute_bars(manifest, rows))
    with pytest.raises(TypeError) as direct:
        jr.replay(*args, **kwargs)
    with pytest.raises(TypeError) as delegated:
        run(NativeApiRequest(
            family="joint_return", native_entry="joint_return_replay.replay", args=args, kwargs=kwargs
        ))
    assert delegated.value.args == direct.value.args


@pytest.mark.parametrize("family,entry", [
    ("csv_minute", "joint_return_replay.replay"),
    ("v7", "joint_return_replay.replay"),
    ("grid_modeb", "joint_return_replay.replay"),
    ("joint_return", "unknown"),
    ("joint_return", CLI),  # Correct id with wrong transport is still blocked.
])
def test_unregistered_entry_fails_before_native(family, entry, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unregistered entry reached native")

    monkeypatch.setattr(jr, "replay", forbidden)
    monkeypatch.setattr(jr, "run_replay", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(UnregisteredEntryError, match="Unregistered research entry"):
        run(NativeApiRequest(family=family, native_entry=entry))


@pytest.mark.parametrize("mode", ["M-REF", "M-LAG", "all"])
def test_cli_success_bytes_and_child_cwd(disk_pack, tmp_path, cli_python, mode):
    manifest, intents, prices = disk_pack
    direct_cwd, facade_cwd = tmp_path / "direct", tmp_path / "facade"
    direct_cwd.mkdir()
    facade_cwd.mkdir()
    relative_out = Path("output with spaces") / manifest["run_id"]
    argv = ["--intents", str(intents), "--bars", str(prices), "--arm", "P-BASE",
            "--fill-mode", mode, "--out", str(relative_out)]
    direct = subprocess.run([cli_python, str(ROOT / CLI), *argv], cwd=direct_cwd, capture_output=True)
    before = (os.getcwd(), dict(os.environ))
    request = NativeCliRequest(
        family="joint_return", native_entry=CLI, argv=argv, context=CliContext(cwd=facade_cwd)
    )
    result = run(request)
    assert isinstance(result, CliResult) and result.request is request and request.argv is argv
    assert result.native_exit_status == direct.returncode == 0, result.stdout_bytes + result.stderr_bytes
    assert result.stdout_bytes == direct.stdout and result.stderr_bytes == direct.stderr
    assert isinstance(result.stdout_bytes, bytes) and isinstance(result.stderr_bytes, bytes)
    assert result.native_artifact_refs is OMITTED
    assert (os.getcwd(), dict(os.environ)) == before
    for name in ARTIFACTS:
        assert (direct_cwd / relative_out / name).read_bytes() == (facade_cwd / relative_out / name).read_bytes()


@pytest.mark.parametrize("mode", ["M-REF", "M-LAG"])
def test_cli_missing_bars_is_native_exit_two(disk_pack, tmp_path, cli_python, mode):
    manifest, intents, _ = disk_pack
    out = tmp_path / "blocked" / manifest["run_id"]
    argv = ["--intents", str(intents), "--arm", "P-BASE", "--fill-mode", mode, "--out", str(out)]
    direct = subprocess.run([cli_python, str(ROOT / CLI), *argv], capture_output=True)
    result = run(NativeCliRequest(family="joint_return", native_entry=CLI, argv=argv))
    assert result.native_exit_status == direct.returncode == 2
    assert (result.stdout_bytes, result.stderr_bytes) == (direct.stdout, direct.stderr)
    assert json.loads(result.stdout_bytes)["status"] == "INPUT_BLOCKED"
    assert not out.exists()


def test_cli_parser_error_preserves_stderr(cli_python):
    direct = subprocess.run([cli_python, str(ROOT / CLI)], capture_output=True)
    result = run(NativeCliRequest(family="joint_return", native_entry=CLI, argv=[]))
    assert result.native_exit_status == direct.returncode == 2
    assert result.stderr_bytes == direct.stderr and result.stderr_bytes
    assert result.stdout_bytes == direct.stdout == b""


@pytest.mark.parametrize("context", [CliContext(), CliContext(env_overlay={}),
    CliContext(cwd="literal/../child dir", env_overlay={"L1_JR_TEST": "", "PYTHONPATH": "literal"})])
def test_cli_one_launch_literal_tokens_child_only_overrides(context, cli_python, monkeypatch):
    argv = ["--tag", "a b", "--tag", "", "$(literal)", r".\path\..\file"]
    before = (os.getcwd(), dict(os.environ))
    calls = []
    stdout, stderr = b"\xff\r\n", b"\x00native\n"

    def launch(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, -15, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", launch)
    result = run(NativeCliRequest(family="joint_return", native_entry=CLI, argv=argv, context=context))
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
        run(NativeCliRequest(family="joint_return", native_entry=CLI, argv=[]))
    assert caught.value.code == 2


def test_transport_failure_is_raised_not_native_exit(cli_python, monkeypatch):
    error, calls = FileNotFoundError("child cwd unavailable"), []

    def launch(*args, **kwargs):
        calls.append(1)
        raise error

    monkeypatch.setattr(subprocess, "run", launch)
    with pytest.raises(FileNotFoundError) as caught:
        run(NativeCliRequest(family="joint_return", native_entry=CLI, argv=[]))
    assert caught.value is error and calls == [1]


def test_fresh_imports_and_selected_dispatch_are_lazy():
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
            'joint_return_replay', 'csv_minute_backtest', 'csv_minute_backtest_v7', 'unified_exit_modeb')}
        assert not engines.intersection(sys.modules)
        assert not any(name.startswith(prefix + 'run_protocol.adapters') for name in sys.modules)
        try:
            run(protocol.NativeApiRequest(family='grid_modeb', native_entry='unknown'))
        except UnregisteredEntryError:
            pass
        else:
            raise AssertionError('unregistered entry accepted')
        assert not engines.intersection(sys.modules)
        try:
            run(protocol.NativeApiRequest(
                family='joint_return', native_entry='joint_return_replay.replay',
                args=(None, None, None), kwargs={'arm': 'invalid', 'fill_mode': 'M-LAG'}))
        except ValueError as exc:
            assert type(exc).__name__ == 'ReplayError'
        else:
            raise AssertionError('native validation did not run')
        assert engines.intersection(sys.modules) == {prefix + 'joint_return_replay'}
        assert (os.getcwd(), dict(os.environ), list(sys.path)) == before
    """)
    process = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code, str(ROOT)], capture_output=True, timeout=20
    )
    assert process.returncode == 0, process.stdout + process.stderr
