"""Private host evidence runner; uses the frozen BT runtime without changing it."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'bt'
EXPECTED_COMMIT = '6f3a3305b2dacba6bb4fe49549a05284227ac43f'
sys.path.insert(0, str(ROOT))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def code_identity():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    if head != EXPECTED_COMMIT or dirty:
        raise RuntimeError('frozen source commit or clean worktree requirement failed')
    return {'commit': head, 'worktree_status': dirty}


def partition_stamps(paths):
    return {str(p.parent): sorted((x.name, x.stat().st_size, x.stat().st_mtime_ns)
            for x in p.parent.iterdir()) for p in paths}


def run_worker(out, phase):
    import pandas as pd
    import psutil
    from backtest.research.ashare_bars import load_minute_ohlc
    code_identity()
    recipe = json.loads((out / 'recipe.json').read_text(encoding='utf-8'))
    proc = psutil.Process()
    peak = [proc.memory_info().rss]
    stop = threading.Event()

    def sample():
        while not stop.wait(.05):
            total = proc.memory_info().rss
            for child in proc.children(recursive=True):
                try:
                    total += child.memory_info().rss
                except psutil.NoSuchProcess:
                    pass
            peak[0] = max(peak[0], total)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    observations = []
    try:
        for repeat in range(2 if phase == 'fresh-hit' else 1):
            status = {}
            tick = time.perf_counter()
            frames = load_minute_ohlc(recipe['codes'], *recipe['window'],
                workers=8, cache_dir=out / 'cache', status=status)
            elapsed = time.perf_counter() - tick
            if set(frames) != set(recipe['codes']):
                raise AssertionError('missing requested sample code')
            h = hashlib.sha256()
            count = 0
            for code, frame in sorted(frames.items()):
                if frame.empty:
                    raise AssertionError('empty sample frame')
                h.update(code.encode())
                h.update(str([(c, str(t)) for c, t in frame.dtypes.items()]).encode())
                h.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
                count += len(frame)
            observations.append({'repeat': repeat, 'elapsed_seconds': elapsed,
                'cache_status': status['cache'], 'codes': len(frames), 'rows': count,
                'frame_digest': h.hexdigest(), 'rss_after_bytes': proc.memory_info().rss})
    finally:
        stop.set()
        sampler.join()
    info = proc.memory_info()
    dump(out / (phase + '.json'), {'phase': phase, 'observations': observations,
        'sampled_process_tree_peak_rss_bytes': max(peak[0], info.rss),
        'windows_lifetime_peak_wset_bytes': getattr(info, 'peak_wset', None)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=['fresh-miss', 'fresh-hit'])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.worker:
        run_worker(out, args.worker)
        return
    code_pin = code_identity()
    from common.infra.data_root import resolve_period_root
    root = resolve_period_root('1m') / 'dividend_type=none'
    if out.is_relative_to(ROOT) or out.is_relative_to(root.resolve()):
        raise RuntimeError('output must be outside code and market input roots')
    out.mkdir(exist_ok=False)
    # Original S1.1 explicit sample plus four different board/liquidity names.
    codes = ['600000.SH', '600036.SH', '000001.SZ', '300750.SZ', '688981.SH', '920002.BJ']
    from oskh_data.symbol_format import to_partition_key
    paths = [root / ('symbol=' + to_partition_key(c)) / 'data.parquet' for c in codes]
    before = {str(p): {'size': p.stat().st_size, 'sha256': sha(p)} for p in paths}
    partitions_before = partition_stamps(paths)
    import oskh_data
    from backtest.research import ashare_bars
    origins = {name: {'path': str(Path(module.__file__).resolve()), 'sha256': sha(module.__file__)}
               for name, module in [('oskh_data', oskh_data), ('ashare_bars', ashare_bars)]}
    if any(not Path(v['path']).is_relative_to(ROOT) for v in origins.values()):
        raise RuntimeError('measured runtime imported outside frozen worktree')
    recipe = {'registered_utc': datetime.now(timezone.utc).isoformat(),
        'source_commit': EXPECTED_COMMIT, 'code_identity': code_pin,
        'runtime': {'python': sys.version, 'executable': sys.executable,
            'packages': {name: importlib.metadata.version(name) for name in ['pandas','pyarrow','psutil','numpy']},
            'module_origins': origins},
        'runner_sha256': sha(__file__), 'codes': codes, 'window': ['20251227', '20260914'],
        'sources': before, 'partition_stamps': partitions_before, 'workers': 8,
        'scope': 'Six explicit symbols, existing runtime monolith; not full-market measurement or shard admission',
        'cache_control': 'Fresh private application cache, fresh Python process per phase. OS page cache NOT evicted; ordered observations only.'}
    dump(out / 'recipe.json', recipe)
    subprocess.run([sys.executable, str(__file__), '--worker', 'fresh-miss', '--out', str(out)], check=True)
    subprocess.run([sys.executable, str(__file__), '--worker', 'fresh-hit', '--out', str(out)], check=True)
    from scripts.diagnostics.probe_minute_cache_cold_load import probe
    probe_result = probe(codes, *recipe['window'], request_codes=5575, workers=8)
    dump(out / 'scan-probe.json', {'registered_utc': recipe['registered_utc'],
        'source_commit': EXPECTED_COMMIT, 'runner_sha256': recipe['runner_sha256'],
        'cache_control': recipe['cache_control'],
        'request_codes_caveat': '5575 is the historical plan example for FD projection only, not a measured universe.',
        'probe': probe_result})
    after = {str(p): {'size': p.stat().st_size, 'sha256': sha(p)} for p in paths}
    records = [json.loads((out / (p + '.json')).read_text(encoding='utf-8'))
               for p in ['fresh-miss', 'fresh-hit']]
    observations = [item for record in records for item in record['observations']]
    expected = ['miss', 'hit', 'mem']
    if (before != after or partitions_before != partition_stamps(paths)
            or code_pin != code_identity()
            or [v['cache_status'] for v in observations] != expected):
        raise AssertionError('source drift or unexpected cache path')
    if len({v['frame_digest'] for v in observations}) != 1:
        raise AssertionError('miss/hit/mem frame mismatch')
    dump(out / 'acceptance.json', {'package': 'P15', 'status': 'PASS_MEASUREMENT_ONLY',
        'package_closed': False, 'measured_input_files_unchanged': True,
        'measured_partition_listings_unchanged': True,
        'miss_hit_mem_frames_equal': True, 'observations': observations,
        'limits': [recipe['scope'], recipe['cache_control'],
            'No timing budget signed; no production loader/cache change.',
            'Actual shard rebuild counts remain unmeasured; S1/S2/S3 remain separate decisions.']})


if __name__ == '__main__':
    main()
