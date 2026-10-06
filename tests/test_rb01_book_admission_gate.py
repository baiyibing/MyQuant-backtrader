"""Fast, data-free RB-01 admission diagnostics."""
from scripts.gates import verify_book_admission as gate


def test_current_registry_is_healthy(capsys):
    assert gate.main() == 0
    output = capsys.readouterr().out
    assert "OK: book admission coverage" in output
    assert "Public name order length:" in output
    assert "collisions (diagnostic only): none" in output


def test_missing_book_failure_is_actionable(monkeypatch, capsys):
    monkeypatch.setitem(gate.BOOKS, "synthetic_missing_book", next(iter(gate.BOOKS.values())))
    assert gate.main() == 1
    output = capsys.readouterr().out
    assert "BOOKS missing from BOOK_NAMES: synthetic_missing_book" in output
    assert "BOOKS missing from historical/overlay lists: synthetic_missing_book" in output
    assert "generate_off_byte_baseline.py" in output
    assert "V6F_BOOK_NAMES" in output
    assert "Do not auto-refresh golden" in output


def test_collision_is_diagnostic_only(monkeypatch, capsys):
    from dataclasses import replace

    book = next(iter(gate.MINUTE_ONLY_BOOKS.values()))
    shared_alias = next(iter(gate.BOOKS.values())).aliases[0]
    monkeypatch.setitem(gate.MINUTE_ONLY_BOOKS, book.name, replace(book, aliases=(shared_alias,)))
    assert gate.main() == 0
    assert f"collisions (diagnostic only): {shared_alias}" in capsys.readouterr().out
