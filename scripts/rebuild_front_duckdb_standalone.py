"""独立重建日线前复权 DuckDB，不依赖 oskh_data.reader。"""
import os
import sys
import time
import shutil
from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from common.infra.data_root import resolve_e_stock_data_container, resolve_period_root

# DuckDB stays on E; hive parquet is listed from the F/SSOT period root.
E_DIR = resolve_e_stock_data_container()
DB_PATH = E_DIR / "stock_data_front.duckdb"
STAGING_PATH = DB_PATH.with_name(DB_PATH.stem + "_staging" + DB_PATH.suffix)


def main():
    t0 = time.perf_counter()

    if STAGING_PATH.exists():
        STAGING_PATH.unlink()

    glob_pattern = str(
        resolve_period_root("1d") / "dividend_type=front" / "*" / "data.parquet"
    ).replace("\\", "/")

    con = duckdb.connect(str(STAGING_PATH))

    print("Creating table from parquet files...")
    con.execute(f"""
        CREATE TABLE stock_data AS
        SELECT * FROM read_parquet('{glob_pattern}', hive_partitioning=1, union_by_name=True)
    """)

    con.execute("UPDATE stock_data SET symbol = REPLACE(symbol, '_', '.')")

    print("Creating index...")
    con.execute("CREATE INDEX idx_symbol ON stock_data(symbol)")

    result = con.execute("SELECT COUNT(*) FROM stock_data").fetchone()
    row_count = result[0] if result else 0
    _sym_row = con.execute("SELECT COUNT(DISTINCT symbol) FROM stock_data").fetchone()
    sym_count = _sym_row[0] if _sym_row else 0
    con.close()

    if row_count == 0:
        STAGING_PATH.unlink()
        raise RuntimeError(f"Staging has 0 rows")

    print(f"Staging validated: {row_count:,} rows, {sym_count} symbols")

    if DB_PATH.exists():
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup = DB_PATH.with_name(f"{DB_PATH.stem}.bak.{timestamp}{DB_PATH.suffix}")
        shutil.move(str(DB_PATH), str(backup))
        print(f"Backed up to {backup.name}")

    os.replace(str(STAGING_PATH), str(DB_PATH))
    elapsed = time.perf_counter() - t0
    size_mb = DB_PATH.stat().st_size / (1024 * 1024)

    print(f"Atomic publish OK: {DB_PATH} ({size_mb:.0f} MB, {row_count:,} rows) in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
