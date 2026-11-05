"""Offline forwarding and public-CI contracts for the B7 Hithink facade."""
from __future__ import annotations

import builtins
from datetime import date
from decimal import Decimal
import hashlib
import importlib.util
import socket

import pyarrow as pa
import pytest

from oskh_data import hithink_artifact as host
from scripts.data import hithink_incremental


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("artifact compatibility tests must stay offline")

    monkeypatch.setattr(socket, "create_connection", fail)


def load_with_import_error(monkeypatch, error):
    original = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name == "myquant_infra" or name.startswith("myquant_infra."):
            raise error
        return original(name, *args, **kwargs)

    spec = importlib.util.spec_from_file_location("hithink_without_infra", host.__file__)
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", unavailable)
        spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["infra", "public"])
def facade(request, monkeypatch):
    if request.param == "infra":
        pytest.importorskip("myquant_infra.hithink.artifacts")
        return host
    return load_with_import_error(
        monkeypatch, ModuleNotFoundError("private package unavailable", name="myquant_infra")
    )


def test_installed_exports_use_the_pinned_public_modules():
    artifacts = pytest.importorskip("myquant_infra.hithink.artifacts")
    export = pytest.importorskip("myquant_infra.hithink.export")
    consumer_names = {
        "ERRORS", "FILES", "canonical_json", "proves_empty", "read_artifact",
        "read_json", "request_identity", "validate_probes",
    }
    for name in host.__all__:
        if name in consumer_names:
            expected = getattr(artifacts, name)
        else:
            expected = getattr(export, {"PAYLOAD_FILES": "FILES", "parse_dump": "inspect_dump"}.get(name, name))
        assert getattr(host, name) is expected, name
    assert host.parse_dump is artifacts.parse_dump is host.inspect_dump
    assert hithink_incremental.artifact is host
    assert hithink_incremental.import_artifact.__module__ == "scripts.data.hithink_incremental"


def test_economics_helpers_and_wire_constants_remain_available(facade, tmp_path):
    assert facade.SOURCE == "hithink:market-dumps/adjustment-factors"
    assert facade.PAYLOAD_FILES == ("hithink_dump.parquet", "probes.json")
    assert facade.FILES == (*facade.PAYLOAD_FILES, "manifest.json", "COMMITTED.json")
    assert facade.SHANGHAI.key == "Asia/Shanghai"
    assert facade.code("600036.SH") == "600036.SH"
    assert facade.day("2026-11-05") == date(2026, 11, 5)
    assert facade.number(Decimal(".199999")) == Decimal(".199999")
    assert facade.number(-0.5, allow_negative=True) == Decimal("-.5")
    path = tmp_path / "proof.json"
    path.write_text('{"z":"证据","a":1}', encoding="utf-8")
    assert facade.read_json(path) == {"z": "证据", "a": 1}
    assert facade.canonical_json(facade.read_json(path)) == '{"a":1,"z":"证据"}'
    assert facade.digest(path) == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("value", [True, "0.2", Decimal("NaN"), float("inf"), Decimal("-.1")])
def test_numeric_validation_never_weakens_without_infra(facade, value):
    with pytest.raises(ValueError):
        facade.number(value)


def test_scale_loss_and_invalid_identity_still_fail(facade):
    with pytest.raises(pa.ArrowInvalid):
        facade.number(Decimal("0.0000000000001"))
    with pytest.raises(ValueError):
        facade.code("600036")
    with pytest.raises(ValueError):
        facade.day("2026-02-30")
    with pytest.raises(ValueError):
        facade.canonical_json({"amount": float("nan")})


def test_absent_optional_package_has_no_local_artifact_consumer(monkeypatch, tmp_path):
    facade = load_with_import_error(
        monkeypatch, ModuleNotFoundError("private package unavailable", name="myquant_infra")
    )
    for name in (
        "read_artifact", "parse_dump", "inspect_dump", "request_identity",
        "validate_probes", "proves_empty", "present_codes",
    ):
        with pytest.raises(ImportError, match="requirements-infra.txt"):
            getattr(facade, name)(tmp_path, {})
    assert not list(tmp_path.iterdir())
    assert facade.parse_dump is facade.inspect_dump


@pytest.mark.parametrize(
    "error",
    [
        ImportError("cannot import name 'read_artifact'"),
        ModuleNotFoundError("missing consumer module", name="myquant_infra.hithink.artifacts"),
        ModuleNotFoundError("missing transitive dependency", name="broken_dependency"),
    ],
)
def test_incomplete_installed_infra_never_uses_public_fallback(monkeypatch, error):
    with pytest.raises(type(error), match=str(error)):
        load_with_import_error(monkeypatch, error)
