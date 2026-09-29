"""Synthetic L2-S5 native/facade parity; no lake or cross-backend NAV claims."""

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from backtest.research.minute_orders_backend import runner as native
from backtest.research.run_protocol import (
    OMITTED,
    ApiResult,
    NativeApiRequest,
    NativeCliRequest,
    run,
)
from backtest.research.run_protocol.facade import UnregisteredEntryError

from tests.test_minute_orders_artifacts import request as artifact_input
from tests.test_minute_orders_runner import bucket, inputs, mark, submit

ROOT = Path(__file__).resolve().parents[1]
FAMILY = "minute_orders_research"
ENTRY = "minute_orders_backend.runner.run_minute_orders_research"
DISK_ENTRY = ENTRY + "_with_artifacts"
SHA = "74e895e25e9ff65e6c77d84909ad17f7c6a84d32"  # Explicit synthetic provenance.


def observe_native(monkeypatch, entry):
    name = entry.rsplit(".", 1)[1]
    target, calls = getattr(native, name), []

    def spy(*args, **kwargs):
        call = {"args": args, "kwargs": kwargs}
        calls.append(call)
        try:
            call["value"] = target(*args, **kwargs)
        except BaseException as error:
            call["error"] = error
            raise
        return call["value"]

    monkeypatch.setattr(native, name, spy)
    return target, calls


def assert_forwarded_once(calls, request):
    assert len(calls) == 1
    call = calls[0]
    assert len(call["args"]) == len(request.args)
    assert all(a is b for a, b in zip(call["args"], request.args))
    assert call["kwargs"].keys() == request.kwargs.keys()
    assert all(call["kwargs"][key] is value for key, value in request.kwargs.items())


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("scenario", ["shared_capacity_expiry", "partial_fee_cancel"])
def test_full_native_result_parity_and_reference_identity(scenario, tmp_path, monkeypatch):
    run_input = artifact_input() if scenario == "partial_fee_cancel" else inputs(
        commands=(submit(qty=300, expiry="09:33:00"),
                  submit("O2", qty=200, time="09:29:01", expiry="09:33:00", sequence=2)),
        buckets=(bucket(), bucket("09:31:00"), bucket("09:32:00")),
        marks=tuple(mark(t) for t in ("09:29:01", "09:31:00", "09:32:00", "09:33:00")),
    )
    monkeypatch.chdir(tmp_path)
    before = asdict(run_input), os.getcwd(), dict(os.environ)
    target, calls = observe_native(monkeypatch, ENTRY)
    expected = target(run_input)
    args, kwargs = (run_input,), {}
    request = NativeApiRequest(family=FAMILY, native_entry=ENTRY, args=args, kwargs=kwargs)
    result = run(request)

    assert_forwarded_once(calls, request)
    assert isinstance(result, ApiResult) and result.request is request
    assert result.native_value is calls[0]["value"]
    assert type(result.native_value) is type(expected)
    assert asdict(result.native_value) == asdict(expected)
    assert expected.fills and expected.transitions and expected.marks
    assert result.native_artifact_refs is OMITTED
    assert request.args is args and request.kwargs is kwargs
    assert (asdict(run_input), os.getcwd(), dict(os.environ)) == before
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("stage", ["validation", "after_fill"])
def test_native_engine_exception_propagates_same_instance_once(stage, tmp_path, monkeypatch):
    run_input = artifact_input()
    run_input = (
        replace(run_input, calendar=replace(run_input.calendar, company_actions_covered=False))
        if stage == "validation" else replace(run_input, marks=(replace(run_input.marks[1], prices=()),))
    )
    monkeypatch.chdir(tmp_path)
    target, calls = observe_native(monkeypatch, ENTRY)
    with pytest.raises(ValueError) as direct:
        target(run_input)
    request = NativeApiRequest(family=FAMILY, native_entry=ENTRY, args=(run_input,))
    with pytest.raises(type(direct.value)) as caught:
        run(request)
    assert_forwarded_once(calls, request)
    assert caught.value is calls[0]["error"]
    assert caught.value.args == direct.value.args
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("entry", [ENTRY, DISK_ENTRY])
def test_system_exit_is_not_caught_or_retried(entry, monkeypatch):
    error, calls = SystemExit(17), []

    def stop(*args, **kwargs):
        calls.append(1)
        raise error

    monkeypatch.setattr(native, entry.rsplit(".", 1)[1], stop)
    with pytest.raises(SystemExit) as caught:
        run(NativeApiRequest(family=FAMILY, native_entry=entry))
    assert caught.value is error and calls == [1]


@pytest.mark.parametrize("status", ["success", "failed"])
@pytest.mark.parametrize("code_sha", [OMITTED, None, SHA])
def test_explicit_disk_wrapper_bytes_and_result_identity(status, code_sha, tmp_path, monkeypatch):
    run_input = artifact_input()
    if status == "failed":
        run_input = replace(run_input, marks=(replace(run_input.marks[1], prices=()),))
    cwd = tmp_path / "caller"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    before = asdict(run_input), os.getcwd(), dict(os.environ)
    kwargs = {"parent": tmp_path / "facade", "run_id": "same-id", "evidence_level": "synthetic"}
    if code_sha is not OMITTED:
        kwargs["code_sha"] = code_sha
    target, calls = observe_native(monkeypatch, DISK_ENTRY)
    expected = target(run_input, **{**kwargs, "parent": tmp_path / "direct"})
    request = NativeApiRequest(family=FAMILY, native_entry=DISK_ENTRY, args=(run_input,), kwargs=kwargs)
    assert not kwargs["parent"].exists()
    result = run(request)

    assert_forwarded_once(calls, request)
    assert isinstance(result, ApiResult) and result.request is request
    assert result.status == "returned" and result.native_value.status == status
    assert result.native_value is calls[0]["value"]
    assert replace(result.native_value, root=expected.root) == expected
    root = result.native_value.root
    assert root == kwargs["parent"] / "backtest_output/minute_orders_research_v1/same-id"
    assert result.native_artifact_refs == (root,)
    assert result.native_artifact_refs[0] is root
    assert tree_bytes(root) == tree_bytes(expected.root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["backend_id"] == "minute_orders_research_v1"
    assert manifest["comparison_status"] == "no_ssot_compare_authorization"
    assert (root / "summary.json").exists() is (status == "success")
    assert (root / "failure.json").exists() is (status == "failed")
    assert request.kwargs is kwargs
    assert (asdict(run_input), os.getcwd(), dict(os.environ)) == before
    assert list(cwd.iterdir()) == []


@pytest.mark.parametrize("missing", ["parent", "run_id", "evidence_level"])
def test_disk_wrapper_never_fills_required_output_arguments(missing, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    kwargs = {"parent": tmp_path, "run_id": "explicit", "evidence_level": "synthetic"}
    del kwargs[missing]
    request = NativeApiRequest(
        family=FAMILY, native_entry=DISK_ENTRY, args=(artifact_input(),), kwargs=kwargs,
    )
    target, calls = observe_native(monkeypatch, DISK_ENTRY)
    with pytest.raises(TypeError) as direct:
        target(*request.args, **request.kwargs)
    with pytest.raises(TypeError) as caught:
        run(request)
    assert_forwarded_once(calls, request)
    assert caught.value is calls[0]["error"]
    assert caught.value.args == direct.value.args
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("foreign", [False, True])
def test_existing_root_rejection_is_preserved(foreign, tmp_path, monkeypatch):
    root = tmp_path / "backtest_output/minute_orders_research_v1/existing"
    root.mkdir(parents=True)
    if foreign:
        (root / "summary.json").write_bytes(b"foreign evidence")
    before = tree_bytes(tmp_path), sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    request = NativeApiRequest(
        family=FAMILY, native_entry=DISK_ENTRY, args=(artifact_input(),),
        kwargs={"parent": tmp_path, "run_id": "existing", "evidence_level": "synthetic", "code_sha": SHA},
    )
    target, calls = observe_native(monkeypatch, DISK_ENTRY)
    with pytest.raises(FileExistsError) as direct:
        target(*request.args, **request.kwargs)
    with pytest.raises(FileExistsError) as caught:
        run(request)
    assert_forwarded_once(calls, request)
    assert caught.value is calls[0]["error"]
    assert caught.value.args == direct.value.args
    assert (tree_bytes(tmp_path), sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))) == before


@pytest.mark.parametrize("family,entry,cli", [
    (FAMILY, "unknown", False),
    (FAMILY, "csv_minute_backtest.simulate", False),
    (FAMILY, "minute_orders_backend.artifacts.write_minute_orders_artifacts", False),
    (FAMILY, ENTRY, True),
    (FAMILY, DISK_ENTRY, True),
    (FAMILY, "backtest/research/minute_orders_backend/runner.py", True),
    ("", ENTRY, False),
    ("minute_orders_research_v1", ENTRY, False),
    *((family, ENTRY, False) for family in ("csv_minute", "v7", "joint_return", "grid_modeb")),
])
def test_unregistered_combination_never_reaches_native(family, entry, cli, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unregistered request reached native execution")

    monkeypatch.setattr(native, "run_minute_orders_research", forbidden)
    monkeypatch.setattr(native, "run_minute_orders_research_with_artifacts", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    request = (
        NativeCliRequest(family=family, native_entry=entry, argv=[])
        if cli else NativeApiRequest(family=family, native_entry=entry)
    )
    with pytest.raises(UnregisteredEntryError, match="Unregistered research entry"):
        run(request)


def test_no_implicit_family_selection():
    with pytest.raises(TypeError, match="family"):
        NativeApiRequest(native_entry=ENTRY)


@pytest.mark.parametrize("entry", [ENTRY, DISK_ENTRY])
def test_fresh_registry_and_adapter_imports_load_no_engines_until_dispatch(entry, tmp_path):
    code = textwrap.dedent("""
        import importlib.abc
        import os
        import sys
        sys.path.insert(0, sys.argv[1])
        before = (os.getcwd(), dict(os.environ), list(sys.path))
        backend = 'backtest.research.minute_orders_backend'
        blocked = ('backtest.research.csv_minute_backtest',
                   'backtest.research.csv_minute_backtest_v7',
                   'backtest.research.joint_return_replay',
                   'backtest.research.unified_exit_modeb', 'oskh_data',
                   'l2_analytics', 'vendor', backend + '.artifacts')
        allow_backend = False

        class Fence(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                prefixes = blocked if allow_backend else (*blocked, backend)
                assert not any(fullname == p or fullname.startswith(p + '.')
                               for p in prefixes), fullname

        sys.meta_path.insert(0, Fence())
        import backtest.research.run_protocol as protocol
        assert 'backtest.research.run_protocol.facade' not in sys.modules
        import backtest.research.run_protocol.adapters
        from backtest.research.run_protocol.facade import run, UnregisteredEntryError
        assert protocol.run is run
        adapter = 'backtest.research.run_protocol.adapters.minute_orders'
        assert adapter not in sys.modules
        # Even explicitly importing the selected adapter is inert.
        import backtest.research.run_protocol.adapters.minute_orders
        for request in (
            protocol.NativeApiRequest(family='minute_orders_research', native_entry='unknown'),
            protocol.NativeCliRequest(family='minute_orders_research', native_entry=sys.argv[2], argv=[]),
        ):
            try:
                run(request)
            except UnregisteredEntryError:
                pass
            else:
                raise AssertionError('unregistered combination accepted')
        assert not any(name == backend or name.startswith(backend + '.') for name in sys.modules)
        allow_backend = True
        try:
            run(protocol.NativeApiRequest(family='minute_orders_research', native_entry=sys.argv[2]))
        except TypeError as error:
            assert 'run_input' in str(error)  # Native signature validation, no synthetic fallback.
        else:
            raise AssertionError('missing native input accepted')
        assert backend + '.runner' in sys.modules
        assert not any(name == p or name.startswith(p + '.') for name in sys.modules for p in blocked)
        assert {name for name in sys.modules
                if name.startswith('backtest.research.run_protocol.adapters.')} == {adapter}
        assert (os.getcwd(), dict(os.environ), list(sys.path)) == before
    """)
    process = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code, str(ROOT), entry],
        cwd=tmp_path, capture_output=True, timeout=30, check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert list(tmp_path.iterdir()) == []
