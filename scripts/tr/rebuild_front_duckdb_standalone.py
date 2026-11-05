"""Explicit daily-front rebuild; MyQuant-infra owns DuckDB IO/publication."""
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = next(p for p in Path(__file__).resolve().parents if p.name == "scripts").parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from myquant_infra.bars.duckdb_build import rebuild_front_duckdb
from common.infra.data_root import resolve_e_stock_data_container, resolve_period_root


def main() -> None:
    started = perf_counter()
    output = resolve_e_stock_data_container() / "stock_data_front.duckdb"
    rows, symbols = rebuild_front_duckdb(resolve_period_root("1d"), output)
    print(f"Atomic publish OK: {output} ({rows:,} rows, {symbols} symbols) in {perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
