"""The host connection fence must reject aliases and stale/broad exceptions."""
from types import SimpleNamespace

import pytest

from scripts.gates import verify_no_host_duckdb_connect_outside_allowlist as gate


@pytest.mark.parametrize("source", [
    "import duckdb\nduckdb.connect()",
    "import duckdb as db\ndb.connect(':memory:')",
    "from duckdb import connect\nconnect()",
    "from duckdb import connect as open_db\nopen_db()",
    "import duckdb as db\nopen_db = db.connect\nopen_db()",
    "import duckdb as db\ndb2 = db\ndb2.connect()",
    "import duckdb\nopen_db: object = duckdb.connect\nopen_db()",
    "from duckdb import *\nconnect()",
])
def test_aliases_are_connections(source):
    assert len(gate.connection_lines(source)) == 1


def test_comments_strings_and_mock_patch_targets_are_not_connections():
    source = '''# duckdb.connect()
target = "duckdb.connect()"
mock.patch("duckdb.connect")
'''
    assert gate.connection_lines(source) == []


def test_scan_rejects_new_calls_and_allowlist_count_drift(monkeypatch, tmp_path):
    files = ["new.py", "allowed.py"]
    for name in files:
        (tmp_path / name).write_text("import duckdb as db\ndb.connect()\n", encoding="utf-8")
    monkeypatch.setattr(gate.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=b"new.py\0allowed.py\0"))
    monkeypatch.setattr(gate, "ALLOWLIST", {"allowed.py": (1, "test fixture")})
    errors, hits = gate.scan(tmp_path)
    assert len(errors) == 1 and "new.py:2" in errors[0]
    assert set(hits) == set(files)
    monkeypatch.setattr(gate, "ALLOWLIST", {"allowed.py": (2, "test fixture")})
    errors, _ = gate.scan(tmp_path)
    assert any("allowlist drift 1 != 2" in error for error in errors)


def test_repository_connections_match_the_documented_inventory():
    errors, hits = gate.scan()
    assert errors == []
    assert set(hits) == set(gate.ALLOWLIST)
