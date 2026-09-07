"""多进程并发读取测试：验证 duckdb_persistent / parquet 模式安全性."""
import os
import random
import sys
import time
from multiprocessing import Pool, cpu_count

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

N_PROCS = min(8, cpu_count())
N_QUERIES = 20
TEST_CODES = ['000001.SZ', '000002.SZ', '600000.SH', '600036.SH']


def worker_persistent(worker_id):
    """每个进程独立创建 StockDataReader (duckdb_persistent)."""
    from backtest.stock_data_reader import StockDataReader
    results = []
    try:
        reader = StockDataReader(mode='duckdb_persistent')
        for _ in range(N_QUERIES):
            code = random.choice(TEST_CODES)
            df = reader.read_stock(code, start_time='20250101', end_time='20250601', period='1d')
            if df is not None:
                results.append((code, len(df)))
        reader.close()
        return {'worker': worker_id, 'queries': len(results), 'ok': True}
    except Exception as e:
        return {'worker': worker_id, 'error': str(e), 'ok': False}


def worker_parquet(worker_id):
    """每个进程独立创建 StockDataReader (parquet)."""
    from backtest.stock_data_reader import StockDataReader
    results = []
    try:
        reader = StockDataReader(mode='parquet')
        for _ in range(N_QUERIES):
            code = random.choice(TEST_CODES)
            df = reader.read_stock(code, start_time='20250101', end_time='20250601', period='1d')
            if df is not None:
                results.append((code, len(df)))
        reader.close()
        return {'worker': worker_id, 'queries': len(results), 'ok': True}
    except Exception as e:
        return {'worker': worker_id, 'error': str(e), 'ok': False}


def worker_duckdb(worker_id):
    """每个进程独立创建 :memory: DuckDB."""
    from backtest.stock_data_reader import StockDataReader
    results = []
    try:
        reader = StockDataReader(mode='duckdb')
        for _ in range(N_QUERIES):
            code = random.choice(TEST_CODES)
            df = reader.read_stock(code, start_time='20250101', end_time='20250601', period='1d')
            if df is not None:
                results.append((code, len(df)))
        reader.close()
        return {'worker': worker_id, 'queries': len(results), 'ok': True}
    except Exception as e:
        return {'worker': worker_id, 'error': str(e), 'ok': False}


def run_test(label, worker_fn):
    print(f'\n--- {label} ---')
    t0 = time.perf_counter()
    with Pool(processes=N_PROCS) as pool:
        results = pool.map(worker_fn, range(N_PROCS))
    elapsed = time.perf_counter() - t0

    ok = all(r['ok'] for r in results)
    total_queries = sum(r['queries'] for r in results)
    print(f'  Procs: {N_PROCS}, Queries: {total_queries}, Time: {elapsed:.1f}s ({total_queries / elapsed:.0f} q/s)')
    for r in results:
        if not r['ok']:
            print(f'  Worker {r["worker"]}: FAIL — {r["error"]}')
    print(f'  Result: {"PASS" if ok else "FAIL"}')
    return ok


if __name__ == '__main__':
    print(f'Multi-process concurrency test ({N_PROCS} workers × {N_QUERIES} queries)')
    print(f'CPU count: {cpu_count()}')
    print(f'Test codes: {TEST_CODES}')

    r1 = run_test('duckdb_persistent (read_only .duckdb)', worker_persistent)
    r2 = run_test('parquet (pd.read_parquet)', worker_parquet)
    r3 = run_test('duckdb (:memory: read_parquet glob)', worker_duckdb)

    print(f'\n{"=" * 50}')
    print(f'Summary: persistent={"PASS" if r1 else "FAIL"}, '
          f'parquet={"PASS" if r2 else "FAIL"}, '
          f'duckdb={"PASS" if r3 else "FAIL"}')
    if r1 and r2 and r3:
        print('All multi-process tests PASSED')
    else:
        print('Some tests FAILED')
        sys.exit(1)
