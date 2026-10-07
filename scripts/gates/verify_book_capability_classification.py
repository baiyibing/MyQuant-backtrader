#!/usr/bin/env python3
"""Data-free registered prefix-family capability classification guard."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.research.book_capabilities import assert_prefix_family_classified
from backtest.research.csv_strategy_books import BOOKS, MINUTE_ONLY_BOOKS


def main() -> int:
    try:
        assert_prefix_family_classified(BOOKS.keys() | MINUTE_ONLY_BOOKS.keys())
    except AssertionError as error:
        print(f"FAIL: book capability classification\n{error}")
        return 1
    print("OK: all registered version6_/version8 family books explicitly classified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
