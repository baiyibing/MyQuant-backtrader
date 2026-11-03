"""Data-free verification of exact-head pytest marker/nodeid alignment."""
import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--raw-ci-log', type=Path)
    args = parser.parse_args()
    load = lambda name: json.loads((args.packet/name).read_text(encoding='utf-8-sig'))
    record = load('ql11-linux-link-coverage.json')
    collection = load('ql11-collected-nodeids.json')
    review = load('pr118-implementation-review.json')
    marks = record['progress_markers']
    nodes = collection['nodeids']
    assert record['head'] == collection['head'] == review['reviewed_head']
    assert len(marks) == len(nodes) == 595
    assert set(marks) == {'.', 's'} and marks.count('.') == 588 and marks.count('s') == 7
    digest = hashlib.sha256(('\n'.join(nodes)+'\n').encode('utf-8')).hexdigest()
    assert digest == record['collected_nodeids_sha256']
    actual_skips = [i for i, mark in enumerate(marks) if mark == 's']
    assert actual_skips == [row['index0'] for row in record['skip_nodes']]
    for row in record['skip_nodes']:
        assert nodes[row['index0']] == row['nodeid']
    assert len(record['symlink_nodes']) == 6
    for row in record['symlink_nodes']:
        assert nodes[row['index0']] == row['nodeid']
        assert marks[row['index0']] == row['marker'] == '.'
    raw_verified = False
    if args.raw_ci_log is not None:
        raw = args.raw_ci_log.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == review['remote_pytest_log_sha256']
        rows = [re.sub(r'^\d{4}-\d{2}-\d{2}T\S+Z ', '', row)
                for row in raw.decode('utf-8-sig', errors='replace').splitlines()]
        parsed = ''.join(row.split()[0] for row in rows
                         if re.fullmatch(r'[.sFxX,]+\s+\[\s*\d+%\]', row)).replace(',', '')
        assert parsed == marks
        raw_verified = True
    groups = []
    offset = 0
    for symbol, group in itertools.groupby(marks):
        count = len(list(group))
        groups.append({'start0': offset, 'symbol': symbol, 'length': count})
        offset += count
    print(json.dumps({'status': 'PASS', 'marker_count': len(marks), 'passed': marks.count('.'),
                      'skipped': marks.count('s'), 'skip_indices0': actual_skips,
                      'symlink_indices0': [row['index0'] for row in record['symlink_nodes']],
                      'symlink_markers': ''.join(marks[row['index0']] for row in record['symlink_nodes']),
                      'run_lengths': groups, 'raw_ci_log_sha_and_parser_verified': raw_verified}, indent=2))


if __name__ == '__main__':
    main()
