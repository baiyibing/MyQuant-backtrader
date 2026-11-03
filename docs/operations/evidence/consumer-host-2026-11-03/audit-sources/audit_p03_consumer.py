"""Read-only M5 sample attestation; never a full-market coverage signoff."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'bt'))
from profile_p15_host import sha, dump, code_identity


def main():
    code_pin = code_identity()
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    from common.infra.data_root import (resolve_parquet_container, resolve_period_root,
        resolve_index_daily_root, resolve_etf_daily_root, resolve_e_stock_data_container)
    root = resolve_parquet_container().resolve(strict=True)
    workspace = resolve_e_stock_data_container().resolve()
    if workspace.is_relative_to(root) or root.is_relative_to(workspace):
        raise RuntimeError('workspace and consumed lake must be disjoint')
    marker = root / '.authority'
    marker_hash = sha(marker)
    roots = {'stock_1d': resolve_period_root('1d'), 'stock_1m': resolve_period_root('1m'),
        'index_1d': resolve_index_daily_root(), 'etf_1d': resolve_etf_daily_root(),
        'etf_1m': root / 'etf' / 'period=1m'}
    specs = [('stock_1d', 'none', '600000_SH'), ('stock_1d', 'front', '600000_SH'),
        ('stock_1d', 'none', '001381_SZ'), ('stock_1m', 'none', '600000_SH'),
        ('stock_1m', 'none', '300750_SZ'), ('index_1d', 'none', '000001_SH'),
        ('index_1d', 'none', '000300_SH'), ('etf_1d', 'none', '510300_SH'),
        ('etf_1d', 'front', '510300_SH'), ('etf_1m', 'none', '510300_SH'),
        ('etf_1m', 'none', '512390_SH')]
    out = HERE / 'p03-consumer-20261103-r2'
    out.mkdir(exist_ok=False)
    files = [(tree, adj, code, roots[tree] / ('dividend_type=' + adj) /
              ('symbol=' + code) / 'data.parquet') for tree, adj, code in specs]
    before = {str(p): sha(p) for _, _, _, p in files if p.is_file()}
    dump(out / 'recipe.json', {'registered_utc': datetime.now(timezone.utc).isoformat(),
        'host': 'DESKTOP-M5HCFD6', 'lake': str(root), 'workspace': str(workspace),
        'authority_sha256': marker_hash, 'runner_sha256': sha(__file__),
        'code_identity': code_pin,
        'configured_roots': {k: str(v) for k, v in roots.items()},
        'target': '2026-11-02', 'source_hashes': before,
        'sample_specs': specs, 'scope': 'Last physical row group per named sample only; no full-history/all-market/other-host approval'})
    rows = []
    for tree, adj, code, path in files:
        row = {'tree': tree, 'adj': adj, 'symbol': code, 'exists': path.is_file()}
        if not path.is_file():
            row['status'] = 'MISSING'
            rows.append(row)
            continue
        with pq.ParquetFile(path) as pf:
            row.update(total_rows=pf.metadata.num_rows, row_groups=pf.metadata.num_row_groups,
                time_type=str(pf.schema_arrow.field('time').type))
            cols = [c for c in ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
                    if c in pf.schema_arrow.names]
            df = pf.read_row_group(pf.metadata.num_row_groups-1, columns=cols).to_pandas()
        times = pd.to_datetime(df['time'], unit='ms') if pd.api.types.is_integer_dtype(df['time']) else pd.to_datetime(df['time'])
        target = df.loc[times.dt.strftime('%Y-%m-%d') == '2026-11-02'].copy()
        row.update(last_group_max_time=str(times.max()), target_rows=len(target),
            date_basis='Stored time values, integer milliseconds or declared timestamp; no timezone relabeling')
        if target.empty:
            row['status'] = 'NO_TARGET_IN_LAST_GROUP'
        else:
            nums = target[[c for c in ['open','high','low','close','volume','amount'] if c in target]].to_numpy(dtype=float)
            prices = target[['open','high','low','close']].to_numpy(dtype=float)
            row.update(nonfinite_cells=int((~np.isfinite(nums)).sum()),
                nonpositive_price_cells=int((prices<=0).sum()),
                negative_volume_rows=int((target['volume']<0).sum()),
                negative_amount_rows=int((target['amount']<0).sum()) if 'amount' in target else None,
                inconsistent_ohlc_rows=int(((target['high'] < target[['open','low','close']].max(axis=1)) |
                    (target['low'] > target[['open','high','close']].min(axis=1))).sum()),
                zero_volume_rows=int((target['volume']==0).sum()),
                duplicate_target_times=int(target['time'].duplicated().sum()))
            row['status'] = 'TARGET_PRESENT_REVIEW' if any(row[k] for k in [
                'nonfinite_cells','nonpositive_price_cells','negative_volume_rows',
                'negative_amount_rows','inconsistent_ohlc_rows','duplicate_target_times']) else 'TARGET_PRESENT_SAMPLE_OK'
        rows.append(row)
    after = {str(p): sha(p) for _, _, _, p in files if p.is_file()}
    if before != after or sha(marker) != marker_hash or code_identity() != code_pin:
        raise RuntimeError('source/authority changed during audit')
    dump(out / 'readout.json', {'package': 'P03', 'package_closed': False,
        'read_only': True, 'measured_input_files_unchanged': True, 'authority_unchanged': True,
        'workspace_disjoint': True, 'samples': rows,
        'other_hosts': {'4090': 'NOT_RUN', '75': 'NOT_RUN'},
        'limits': ['No full-market or full-history coverage signoff.',
            'Zero volume alone does not prove corruption or suspension status.',
            'ETF 512390 is an explicit stale-data sentinel, not an approved fresh symbol.',
            '001381 zero-price/zero-volume rows cannot pass as valid OHLC bars.',
            'No vendor merge, source rewrite, backfill or promotion performed.']})


if __name__ == '__main__':
    main()
