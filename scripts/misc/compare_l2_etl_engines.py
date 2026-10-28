"""Run an isolated one-day engine comparison using the invoking interpreter."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def last_result(stdout: str) -> dict:
    """Read the last standalone JSON object, ignoring progress/log braces."""
    decoder = json.JSONDecoder()
    for pos in range(len(stdout) - 1, -1, -1):
        if stdout[pos] != "{":
            continue
        try:
            value, end = decoder.raw_decode(stdout[pos:])
        except ValueError:
            continue
        if isinstance(value, dict) and not stdout[pos + end:].strip():
            return value
    raise ValueError("ETL stdout contains no final JSON object")


def timing(profile: dict, key: str) -> str:
    value = profile.get(key)
    return f"{value:.3f}s" if isinstance(value, (int, float)) else "N/A"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out-root', required=True, help='New scratch directory; must not exist')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--chunk-files', type=int, default=400)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    if not source.is_dir():
        parser.error('source must be an existing day directory')
    out = Path(args.out_root).resolve()
    if out == source or out in source.parents or source in out.parents:
        parser.error('scratch output must be separate from source')
    # Exclusive creation prevents reuse of lake directories or stale benchmark outputs.
    out.mkdir(parents=True, exist_ok=False)
    cli = Path(__file__).resolve().parents[1] / 'run' / 'run_l2_etl_day.py'
    for engine in ('duckdb', 'polars'):
        env = dict(os.environ, OSKH_L2_ETL_ENGINE=engine,
                   POLARS_MAX_THREADS=str(args.threads))
        t = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, str(cli), '--source', str(source), '--out-root', str(out / engine),
             '--threads', str(args.threads), '--chunk-files', str(args.chunk_files)],
            env=env, text=True, stdout=subprocess.PIPE, check=True,
        )
        wall = time.perf_counter() - t
        (out / f'{engine}.log').write_text(completed.stdout, encoding='utf-8')
        result = last_result(completed.stdout)
        (out / f'{engine}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        prof = result.get('profile') or {}
        print(f"{engine}: wall={wall:.3f}s chunk={timing(prof, 'chunk_total_sum_s')} "
              f"merge_main={timing(prof, 'merge_main_s')} merge_order={timing(prof, 'merge_order_s')} "
              f"rows={result['rows_main']}/{result['rows_order']}", flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
