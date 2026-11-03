import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

parser = argparse.ArgumentParser(description='Read-only current-tree coverage audit of the 14 legacy issue #34 symbols.')
parser.add_argument('--repo-root', required=True, type=Path)
parser.add_argument('--out', required=True, type=Path)
args = parser.parse_args()
ROOT = args.repo_root.resolve()
sys.path.insert(0, str(ROOT))
from common.infra.data_root import (resolve_parquet_container, resolve_period_root,
    resolve_index_daily_root, resolve_etf_daily_root)

output = args.out.resolve()
container = resolve_parquet_container()
roots = {'stock': resolve_period_root('1d'), 'index': resolve_index_daily_root(),
         'etf': resolve_etf_daily_root()}
for kind, path in roots.items():
    if not path.is_dir():
        raise FileNotFoundError(f'resolved {kind} root absent')
if any(output.is_relative_to(path.resolve()) for path in [container, *roots.values()]):
    raise ValueError('audit output must be outside the source container and resolved roots')
symbols = {
    '000300.SH': 'index', '510050.SH': 'etf', '159915.SZ': 'etf', '588000.SH': 'etf',
    **dict.fromkeys(['000638.SZ', '600421.SH', '600599.SH', '600608.SH',
                    '600636.SH', '600696.SH', '605081.SH', '688287.SH',
                    '920081.BJ', '920136.BJ'], 'stock'),
}
rows = []
observed_files = {}
for symbol, kind in symbols.items():
    row = {'symbol': symbol, 'current_kind': kind, 'modes': {}}
    for mode in ['none', 'front', 'back']:
        partition = roots[kind] / f'dividend_type={mode}' / f'symbol={symbol.replace(".", "_")}'
        files = sorted(partition.glob('*.parquet'))
        cells = []
        for path in files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            parquet = pq.ParquetFile(path)
            fields = []
            for group in range(parquet.metadata.num_row_groups):
                rg = parquet.metadata.row_group(group)
                for c in range(rg.num_columns):
                    col = rg.column(c)
                    if col.path_in_schema in ['time', 'datetime', 'date'] and col.statistics and col.statistics.has_min_max:
                        fields.append({'name': col.path_in_schema, 'min': str(col.statistics.min), 'max': str(col.statistics.max)})
            cells.append({'file': path.name, 'rows': parquet.metadata.num_rows,
                          'sha256': digest, 'time_statistics_literal': fields})
            observed_files[path] = digest
        row['modes'][mode] = {'partition_exists': partition.is_dir(), 'files': cells,
                              'total_rows': sum(f['rows'] for f in cells)}
    rows.append(row)
assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in observed_files.items())
stocks = [r for r in rows if r['current_kind'] == 'stock']
missing = {mode: [r['symbol'] for r in stocks if not r['modes'][mode]['total_rows']] for mode in ['none', 'front', 'back']}
authority = container / '.authority'
packet = {
    'schema_version': 1, 'observed_at_utc': datetime.now(timezone.utc).isoformat(),
    'issue_url': 'https://github.com/baiyibing/OSkhQuant1.3/issues/34',
    'source_identity': 'OSKH_SOURCE_PARQUET_ROOT/configured authority resolvers; absolute host paths withheld',
    'audit_runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'resolver_source_sha256': hashlib.sha256((ROOT / 'common/infra/data_root.py').read_bytes()).hexdigest(),
    'authority_marker_present': authority.is_file(),
    'authority_marker_sha256': hashlib.sha256(authority.read_bytes()).hexdigest() if authority.is_file() else None,
    'scope': '14 legacy issue symbols resolved into current stock/index/etf daily trees; presence and nonempty row coverage only',
    'rows': rows, 'stock_nonempty_missing_by_mode': missing,
    'selected_files_unchanged_after_read': True, 'selected_file_count': len(observed_files),
    'limits': ['No all-market freshness/quality, economic equivalence, adjusted-value correctness, or live-readiness attestation.',
               'Index has only raw none in this current layout; missing index adjusted copies are not stock omissions.',
               'Any remaining stock back coverage is retained as open data debt; no raw-to-adjusted copying or downloads.'],
}
output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'stock_missing': missing, 'selected_files': len(observed_files), 'unchanged': True}, ensure_ascii=False))
