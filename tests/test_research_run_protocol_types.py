"""Data-free L1-S0 contracts; no native runner or adapter is exercised."""

from dataclasses import FrozenInstanceError, fields
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from typing import get_args

import pytest

from backtest.research.run_protocol import (
    OMITTED,
    ApiExceptionResult,
    ApiResult,
    CallerContext,
    CliContext,
    CliResult,
    EntryKind,
    Family,
    NativeApiRequest,
    NativeCliRequest,
    NotRunResult,
)


FAMILIES = ("csv_minute", "v7", "joint_return", "grid_modeb", "minute_orders_research")


@pytest.mark.parametrize("value", [None, False, "", (), [], {}])
def test_native_omission_is_key_absence_not_a_falsy_value(value):
    omitted = NativeApiRequest(family="joint_return", native_entry="unregistered")
    kwargs = {"native_option": value}
    explicit = NativeApiRequest(
        family="joint_return", native_entry="unregistered", kwargs=kwargs
    )

    assert "native_option" not in omitted.kwargs
    assert "native_option" in explicit.kwargs
    assert explicit.kwargs is kwargs
    assert explicit.kwargs["native_option"] is value
    assert omitted.kwargs.get("native_option", OMITTED) is OMITTED
    assert value is not OMITTED
    assert value != OMITTED


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("entry_kind", ["native_api", "native_cli"])
def test_family_and_entry_kind_round_trip(family, entry_kind):
    assert get_args(Family) == FAMILIES
    assert get_args(EntryKind) == ("native_api", "native_cli")
    if entry_kind == "native_api":
        request = NativeApiRequest(family=family, native_entry="unregistered.api")
    else:
        request = NativeCliRequest(
            family=family, native_entry="unregistered.cli", argv=[]
        )
    # Shallow reconstruction: serialization/deepcopy of native payloads is not
    # part of the protocol. A tag alone does not make this entry runnable.
    payload = {f.name: getattr(request, f.name) for f in fields(request) if f.init}
    restored = type(request)(**payload)
    assert (restored.family, restored.entry_kind, restored.native_entry) == (
        family, entry_kind, request.native_entry
    )
    with pytest.raises(TypeError):
        type(request)(**payload, entry_kind="other")
    with pytest.raises(FrozenInstanceError):
        request.family = "v7"


def test_api_payload_preserves_containers_and_native_objects_by_reference():
    class NativeObject:
        def __deepcopy__(self, memo):
            raise AssertionError("native objects must not be deep-copied")

    native = NativeObject()
    amount = Decimal("12.3400")
    args = (native, amount)
    kwargs = {"bars": native, "amount": amount, "mutable": []}
    request = NativeApiRequest(
        family="joint_return", native_entry="unregistered", args=args, kwargs=kwargs
    )
    assert request.args is args
    assert request.kwargs is kwargs
    assert request.args[0] is request.kwargs["bars"] is native
    assert request.args[1] is request.kwargs["amount"] is amount
    kwargs["mutable"].append(native)
    assert request.kwargs["mutable"][0] is native
    assert "new_option" not in request.kwargs
    kwargs["new_option"] = False
    assert request.kwargs["new_option"] is False


def test_context_construction_is_inert_and_cli_tokens_are_literal():
    cwd_before, env_before = os.getcwd(), dict(os.environ)
    api = NativeApiRequest(family="joint_return", native_entry="unregistered")
    assert api.context == CallerContext()
    assert api.context.kind == "caller"
    with pytest.raises(TypeError):
        NativeApiRequest(
            family="joint_return", native_entry="unregistered", context=CliContext()
        )

    argv = ["--pool-dir", r".\data dir\..\pool", "--tag", "a", "--tag", "a", ""]
    overlay = {"RUN_PROTOCOL_TEST_ENV": "", "OTHER": "literal"}
    context = CliContext(cwd="./missing/../literal dir", env_overlay=overlay)
    cli = NativeCliRequest(
        family="grid_modeb", native_entry="unregistered", argv=argv, context=context
    )
    assert cli.argv is argv
    assert list(cli.argv) == [
        "--pool-dir", r".\data dir\..\pool", "--tag", "a", "--tag", "a", ""
    ]
    assert cli.context is context
    assert context.cwd == "./missing/../literal dir"
    assert context.env_overlay is overlay
    assert CliContext().cwd is OMITTED
    assert CliContext().env_overlay is OMITTED
    assert CliContext(env_overlay={}).env_overlay == {}
    assert (os.getcwd(), dict(os.environ)) == (cwd_before, env_before)
    with pytest.raises(FrozenInstanceError):
        context.cwd = "elsewhere"


@pytest.mark.parametrize("entry_kind", ["native_api", "native_cli"])
def test_not_run_cannot_look_like_an_empty_native_success(entry_kind):
    if entry_kind == "native_api":
        request = NativeApiRequest(family="joint_return", native_entry="unregistered")
    else:
        request = NativeCliRequest(
            family="joint_return", native_entry="unregistered", argv=()
        )
    pending = NotRunResult(request=request)
    assert pending.request is request
    assert pending.status == "not_run"
    assert not isinstance(pending, (ApiResult, ApiExceptionResult, CliResult))
    for name in ("native_value", "native_exception", "native_exit_status", "success"):
        assert not hasattr(pending, name)
    with pytest.raises(FrozenInstanceError):
        pending.status = "returned"
    with pytest.raises(TypeError):
        ApiResult(request=request)  # Native None must be explicitly supplied.
    with pytest.raises(TypeError):
        CliResult(request=request)  # No default zero exit or empty streams.


@pytest.mark.parametrize("native_value", [None, False, {}, Decimal("12.3400")])
def test_explicit_native_return_is_an_unconverted_reference(native_value):
    request = NativeApiRequest(family="joint_return", native_entry="unregistered")
    result = ApiResult(request=request, native_value=native_value)
    assert result.status == "returned"
    assert result.request is request
    assert result.native_value is native_value
    assert result.native_artifact_refs is OMITTED
    refs = (Path("./native-output/report.csv"),)
    reported = ApiResult(
        request=request, native_value=native_value, native_artifact_refs=refs
    )
    assert reported.native_artifact_refs is refs
    assert reported.native_artifact_refs[0] is refs[0]
    assert ApiResult(
        request=request, native_value=native_value, native_artifact_refs=()
    ).native_artifact_refs == ()


@pytest.mark.parametrize("exception_type", [ValueError, SystemExit])
def test_exception_observation_preserves_identity_and_chaining(exception_type):
    request = NativeApiRequest(family="joint_return", native_entry="unregistered")
    cause = RuntimeError("original cause")
    try:
        try:
            raise cause
        except RuntimeError:
            raise exception_type("native failure", 2) from cause
    except BaseException as native_exception:
        traceback = native_exception.__traceback__
        args = native_exception.args
        observation = ApiExceptionResult(request=request, native_exception=native_exception)
        assert observation.status == "raised"
        assert observation.request is request
        assert observation.native_exception is native_exception
        assert native_exception.args is args
        assert native_exception.__cause__ is cause
        assert native_exception.__context__ is cause
        assert native_exception.__traceback__ is traceback
        assert native_exception.__suppress_context__ is True
        assert not hasattr(observation, "native_value")
    # Future S1 must prove one native call and re-raise the same object. This
    # observation-only test does not implement or certify delegation.


@pytest.mark.parametrize("exit_status", [0, 2, -15])
def test_cli_outcome_preserves_native_status_and_raw_streams(exit_status):
    request = NativeCliRequest(family="joint_return", native_entry="unregistered", argv=())
    stdout, stderr = b"\xffnative\r\n", b"\x00error\n"
    result = CliResult(
        request=request, native_exit_status=exit_status,
        stdout_bytes=stdout, stderr_bytes=stderr,
    )
    assert result.status == "exited"
    assert result.request is request
    assert result.native_exit_status == exit_status
    assert result.stdout_bytes is stdout
    assert result.stderr_bytes is stderr
    assert result.native_artifact_refs is OMITTED
    assert not hasattr(result, "success")


@pytest.mark.parametrize("statement", [
    "import backtest.research.run_protocol",
    "from backtest.research.run_protocol.types import NativeApiRequest",
])
def test_fresh_import_loads_only_stdlib_and_protocol(statement):
    # A fresh interpreter avoids false passes from engines already imported by
    # other tests; -I -S also excludes user site hooks and PYTHONPATH additions.
    code = textwrap.dedent("""
        import os
        import sys
        sys.path.insert(0, sys.argv[1])
        before = set(sys.modules)
        cwd_before, env_before = os.getcwd(), dict(os.environ)
        exec(sys.argv[2])
        added = set(sys.modules) - before
        engines = {
            'backtest.research.csv_minute_backtest',
            'backtest.research.csv_minute_backtest_v7',
            'backtest.research.joint_return_replay',
            'backtest.research.unified_exit_modeb',
        }
        assert not (added & engines), sorted(added & engines)
        allowed = {
            'backtest', 'backtest.research',
            'backtest.research.run_protocol',
            'backtest.research.run_protocol.types',
        }
        unexpected = {
            name for name in added
            if name not in allowed
            and name.split('.')[0] not in sys.stdlib_module_names
        }
        assert not unexpected, sorted(unexpected)
        assert (os.getcwd(), dict(os.environ)) == (cwd_before, env_before)
    """)
    process = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code,
         str(Path(__file__).resolve().parents[1]), statement],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
