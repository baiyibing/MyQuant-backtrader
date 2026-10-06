#!/usr/bin/env python3
"""Data-free book admission diagnostic; never records or refreshes goldens."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.research.csv_strategy_books import BOOKS, MINUTE_ONLY_BOOKS, csv_strategy_names
from scripts.research import generate_off_byte_baseline as baseline


def format_coverage_failure(error: AssertionError) -> str:
    missing = sorted(set(BOOKS) - set(baseline.BOOK_NAMES))
    extra = sorted(set(baseline.BOOK_NAMES) - set(BOOKS))
    groups = (
        "HISTORICAL", "V61", "V91", "V92", "V6F", "S8", "S12", "S9",
        "P03", "P04", "P05",
    )
    covered = set().union(*(set(getattr(baseline, f"{group}_BOOK_NAMES")) for group in groups))
    lines = [
        "FAIL: book admission baseline coverage",
        f"AssertionError: {error or '(unnamed coverage assertion)'}",
        f"BOOKS missing from BOOK_NAMES: {', '.join(missing) or 'none'}",
        f"BOOKS missing from historical/overlay lists: {', '.join(sorted(set(BOOKS) - covered)) or 'none'}",
        f"BOOK_NAMES absent from BOOKS: {', '.join(extra) or 'none'}",
        "Human action: update scripts/research/generate_off_byte_baseline.py explicitly:",
        "  BOOK_NAMES, the appropriate scoped *_BOOK_NAMES / *_CASES, and CASES.",
        "  For the 6.x family, update V6F_BOOK_NAMES / V6F_CASES and its scoped overlay:",
        f"  {baseline.V6F_GOLDEN.relative_to(ROOT)}",
        "Existing historical/overlay contracts (review the relevant list and golden):",
    ]
    for group in groups:
        golden = baseline.GOLDEN if group == "HISTORICAL" else getattr(baseline, f"{group}_GOLDEN")
        lines.append(f"  {group}_BOOK_NAMES / {group}_CASES -> {golden.relative_to(ROOT)}")
    lines.append("Do not auto-refresh golden or fixtures; any scoped golden update requires explicit human authorization.")
    return "\n".join(lines)


def main() -> int:
    names = csv_strategy_names()
    shared = set(BOOKS)
    for book in BOOKS.values():
        shared.update(book.aliases)
    collisions = sorted({
        token for book in MINUTE_ONLY_BOOKS.values()
        for token in (book.name, *book.aliases) if token in shared
    })
    print(f"Public name order length: {len(names)}; matches BOOKS insertion order: {names == tuple(BOOKS)}")
    print(f"Minute-only/shared name or alias collisions (diagnostic only): {', '.join(collisions) or 'none'}")
    try:
        baseline.assert_baseline_coverage()
    except AssertionError as error:
        print(format_coverage_failure(error))
        return 1
    print(f"OK: book admission coverage; {len(BOOKS)} shared books, {len(MINUTE_ONLY_BOOKS)} minute-only books; no simulations or golden writes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
