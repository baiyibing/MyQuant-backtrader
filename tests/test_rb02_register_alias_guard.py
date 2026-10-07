"""Data-free registration guards; healthy registry order remains unchanged."""

from dataclasses import replace

import pytest

from backtest.research import csv_strategy_books as books


@pytest.fixture
def isolated_registries(monkeypatch):
    monkeypatch.setattr(books, "BOOKS", dict(books.BOOKS))
    monkeypatch.setattr(books, "MINUTE_ONLY_BOOKS", dict(books.MINUTE_ONLY_BOOKS))


def test_current_registries_are_healthy():
    assert books.csv_strategy_names() == tuple(books.BOOKS)
    assert len(books.BOOKS) == len(books.csv_strategy_names())
    assert "version7" in books.MINUTE_ONLY_BOOKS
    aliases = books._alias_map()
    for book in books.BOOKS.values():
        assert book.name in book.aliases
        assert all(aliases[token] == book.name for token in book.aliases)
        assert books.normalize_minute_strategy(book.name) == book.name
    for book in books.MINUTE_ONLY_BOOKS.values():
        assert book.name in book.aliases
        assert all(token not in aliases for token in (book.name, *book.aliases))
        assert all(books.normalize_minute_strategy(token) == book.name for token in book.aliases)


@pytest.mark.parametrize("field", ["name", "alias"])
@pytest.mark.parametrize("token_kind", ["name", "alias"])
def test_shared_rejects_minute_token(isolated_registries, field, token_kind):
    minute = next(iter(books.MINUTE_ONLY_BOOKS.values()))
    token = minute.name if token_kind == "name" else next(a for a in minute.aliases if a != minute.name)
    template = next(iter(books.BOOKS.values()))
    candidate = replace(template, name=token if field == "name" else "rb02_new", aliases=(token,) if field == "alias" else ("rb02_new",))
    before = dict(books.BOOKS)
    with pytest.raises(ValueError) as error:
        books.register(candidate)
    assert repr(token) in str(error.value)
    assert "already claimed" in str(error.value)
    assert "minute-only" in str(error.value)
    assert books.BOOKS == before


@pytest.mark.parametrize("token_kind", ["name", "alias"])
def test_shared_rejects_shared_alias_collision(isolated_registries, token_kind):
    existing = next(iter(books.BOOKS.values()))
    token = existing.name if token_kind == "name" else next(a for a in existing.aliases if a != existing.name)
    candidate = replace(existing, name="rb02_new", aliases=("rb02_new", token))
    with pytest.raises(ValueError) as error:
        books.register(candidate)
    assert repr(token) in str(error.value)
    assert "already claimed by a shared strategy" in str(error.value)
    assert candidate.name not in books.BOOKS


@pytest.mark.parametrize("field", ["name", "alias"])
def test_minute_still_rejects_shared_collision(isolated_registries, field):
    existing = next(iter(books.BOOKS.values()))
    candidate = replace(existing, name=existing.name if field == "name" else "rb02_minute", aliases=(existing.name,) if field == "alias" else ("rb02_minute",))
    before = dict(books.MINUTE_ONLY_BOOKS)
    with pytest.raises(ValueError):
        books.register_minute_book(candidate)
    assert books.MINUTE_ONLY_BOOKS == before


def test_alias_map_rejects_mutated_duplicate(isolated_registries):
    existing = next(iter(books.BOOKS.values()))
    duplicate = replace(existing, name="rb02_mutated", aliases=(existing.aliases[0],))
    books.BOOKS[duplicate.name] = duplicate
    with pytest.raises(ValueError) as error:
        books._alias_map()
    assert repr(existing.aliases[0]) in str(error.value)
    assert repr(existing.name) in str(error.value)
    assert repr(duplicate.name) in str(error.value)


def test_successful_registration_appends_and_allows_self_alias(isolated_registries):
    before = books.csv_strategy_names()
    candidate = replace(next(iter(books.BOOKS.values())), name="rb02_new", aliases=("rb02_new", "rb02_alias"))
    books.register(candidate)
    assert books.csv_strategy_names() == (*before, candidate.name)
    assert books._alias_map()["rb02_alias"] == candidate.name


def test_duplicate_shared_name_is_rejected(isolated_registries):
    existing = next(iter(books.BOOKS.values()))
    with pytest.raises(ValueError, match="already claimed"):
        books.register(replace(existing, aliases=("rb02_unique",)))
