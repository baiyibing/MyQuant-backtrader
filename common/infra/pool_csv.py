"""Lightweight pool CSV records and duplicate validation shared by readers."""

from __future__ import annotations

import csv
import re
from itertools import chain
from pathlib import Path
from typing import Iterator

_BARE_CODE_RE = re.compile(r"(\d{6})")
_HEADER_FIRST = frozenset(
    {"代码", "code", "symbol", "证券代码", "ticker", "stock", "stock_code"}
)


class PoolDuplicateCodeError(ValueError):
    """A pool contains the same canonical code twice on one day."""

    def __init__(
        self, path: Path, code: str, first_line: int, second_line: int,
        *, day: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.code = code
        self.first_line = first_line
        self.second_line = second_line
        self.day = day
        date_note = f" on {day}" if day is not None else ""
        super().__init__(
            f"{self.path}: duplicate pool code {code}{date_note}: "
            f"first occurrence at line {first_line}, "
            f"second occurrence at line {second_line}"
        )


def check_pool_duplicate(
    path: Path,
    seen: dict[tuple[str | None, str], int],
    code: str,
    line_number: int,
    *,
    day: str | None = None,
) -> None:
    """Record a canonical code's physical row, raising on a same-day repeat.

    Call after code normalization, before filtering/ranking rows. Keep ``seen``
    local to one file; multi-day readers must pass a normalized calendar day.
    Single-day files can omit ``day`` because the file supplies the day scope.
    """
    key = (day, code)
    if key in seen:
        raise PoolDuplicateCodeError(path, code, seen[key], line_number, day=day)
    seen[key] = line_number


def pool_cell_to_bare(raw: str) -> str:
    text = str(raw or "").strip().strip('"').strip("'")
    if text.startswith("="):
        text = text[1:].strip().strip('"').strip("'")
    match = _BARE_CODE_RE.search(text)
    return match.group(1) if match else ""


def iter_pool_csv_rows(
    path: Path, *, encoding: str = "utf-8-sig",
) -> Iterator[tuple[int, list[str]]]:
    """Yield data records with their 1-based starting physical line number."""
    with Path(path).open(encoding=encoding, newline="") as stream:
        physical_line = 0
        while first_line := stream.readline():
            physical_line += 1
            # Ignore comments only at record boundaries. Quotes in a comment
            # must not consume later records; comments inside quoted names stay.
            if not first_line.strip() or first_line.lstrip().startswith("#"):
                continue
            line_number = physical_line
            reader = csv.reader(chain([first_line], stream))
            row = next(reader)
            physical_line += reader.line_num - 1
            parts = [part.strip() for part in row]
            first = parts[0] if parts else ""
            if not any(parts) or first.startswith("#"):
                continue
            if line_number == 1 and first.strip('"').strip("'").lower() in _HEADER_FIRST:
                continue
            yield line_number, parts
