"""Phase2 vendor -> END/lots staging only. No lake write; ≠δ5 ≠R4."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location(
    '_adapter_xcheck', Path(__file__).with_name('vendor_bar_xcheck.py'))
xcheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(xcheck)
DEFAULT_SYMBOLS = ['002231.SZ', '300379.SZ', '600200.SH']
TRANSFORMATIONS = ['Wind continuous START -> END (+1 minute)',
                   'shares -> lots (floor division; remainder audited)',
                   'drop Wind START 09:30 auction before continuous output',
                   'sparse A: observed bars only; no zero-fill',
                   'THS daily: day keys, no minute shift']


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wind', action='append', nargs='+', required=True)
    p.add_argument('--ths-daily', action='append', nargs='+', default=[])
    p.add_argument('--symbols', nargs='+', default=DEFAULT_SYMBOLS)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--wind-label', choices=['START'], default='START')
    p.add_argument('--lake-label', choices=['END'], default='END')
    p.add_argument('--unit-out', choices=['lots'], default='lots')
    p.add_argument('--shares-to-lots-div', type=int, choices=[100], default=100)
    p.add_argument('--auction-policy', choices=['exclude_0930'], default='exclude_0930')
    return p


def safe_output(path, sources):
    # Check both lexical Windows spelling and resolved paths (including symlinks).
    out = path.resolve()
    for spelling in (str(path), str(out)):
        if 'stock_data' in re.split(r'[/\\]+', spelling.lower()):
            raise ValueError('protected stock_data lake path; separate Human write-lake GO required')
    for key in ('OSKH_SOURCE_PARQUET_ROOT', 'OSKH_PERIOD_1D_ROOT',
                'OSKH_PERIOD_1M_ROOT', 'OSKH_AUTHORITY_HINT_ROOT'):
        if os.environ.get(key):
            root = Path(os.environ[key]).resolve()
            if out == root or root in out.parents:
                raise ValueError(f'protected configured lake root: {key}')
    if any(out == s.parent or s.parent in out.parents or out in s.parents for s in sources):
        raise ValueError('out-dir must be separate from input directories')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError('out-dir must be new or empty; never overwrite staging')
    return out


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def json_write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_daily(paths, symbols):
    frames = []
    for path in paths:
        df = pd.read_csv(path) if path.suffix.lower() == '.csv' else pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.rename(columns={'match': 'close', 'wind_code': 'symbol', 'thscode': 'symbol', 'date': 'time'})
        if 'symbol' not in df:
            match = re.search(r'symbol=([0-9]{6}\.(?:SZ|SH|BJ))', str(path), re.I)
            if not match:
                raise ValueError(f'{path}: missing symbol')
            df['symbol'] = match.group(1)
        df['symbol'] = df.symbol.astype(str).str.strip().str.upper()
        df = df[df.symbol.isin(symbols)].copy()
        stamp = df['time']
        def day(value):
            if re.fullmatch(r'\d{8}', str(value)):
                return pd.to_datetime(str(value), format='%Y%m%d')
            ts = pd.Timestamp(value, unit='ms') if isinstance(value, (int, float, np.number)) else pd.Timestamp(value)
            return ts.tz_convert('Asia/Shanghai').tz_localize(None) if ts.tzinfo else ts
        times = stamp.map(day)
        if times.isna().any():
            raise ValueError('invalid daily date')
        df['ymd'] = pd.to_datetime(times).dt.strftime('%Y%m%d')
        df['hm'] = 0
        for field in xcheck.FIELDS:
            df[field] = pd.to_numeric(df[field], errors='raise')
            if not np.isfinite(df[field]).all() or (df[field] < 0).any():
                raise ValueError(f'invalid daily {field}')
        frames.append(df[xcheck.KEYS + list(xcheck.FIELDS)])
    result = pd.concat(frames, ignore_index=True)
    if result.duplicated(xcheck.KEYS).any():
        raise ValueError('duplicate daily keys')
    return result


def convert(rows, period, divisor):
    rows = rows.copy()
    # Float-backed vendor volume must be exact integer shares, not rounded silently.
    if ((rows.volume % 1 != 0) | (rows.volume > 2**53 - 1)).any():
        raise ValueError('volume must be exact nonnegative integer shares <= 2**53-1')
    shares = rows.volume.astype('int64')
    remainder = shares % divisor
    audit = rows.loc[remainder != 0, xcheck.KEYS].copy()
    audit['period'] = period
    audit['shares'] = shares[remainder != 0]
    audit['volume_lots'] = shares[remainder != 0] // divisor
    audit['remainder_shares'] = remainder[remainder != 0]
    rows['volume'] = shares // divisor
    times = pd.to_datetime(rows.ymd, format='%Y%m%d') + pd.to_timedelta(rows.hm, unit='m')
    rows['time'] = times.astype('datetime64[ns]').astype('int64') // 10**6
    return rows[['symbol', 'time'] + list(xcheck.FIELDS)].sort_values(['symbol', 'time']).reset_index(drop=True), audit.to_dict('records')


def verify(out, expected, audit, pin):
    """Read back artifacts before PASS; missing/altered remainder evidence fails closed."""
    if json.loads((out / 'remainder_audit.json').read_text()) != audit:
        raise ValueError('remainder audit missing or inconsistent')
    if json.loads((out / 'PIN.json').read_text()) != pin or not all(
            re.fullmatch('[0-9a-f]{64}', s['sha256']) for s in pin['sources']):
        raise ValueError('PIN incomplete or inconsistent')
    for relative, frame in expected.items():
        pd.testing.assert_frame_equal(pd.read_parquet(out / relative), frame)
    for artifact in pin['outputs']:
        if sha(out / artifact['path']) != artifact['sha256']:
            raise ValueError('staging parquet SHA mismatch')


def main(argv=None):
    args = parser().parse_args(argv)
    sources = [(period, Path(p).resolve()) for period, groups in
               [('1m', args.wind), ('1d', args.ths_daily)] for group in groups for p in group]
    # Unsafe paths must not receive even a FAIL receipt.
    try:
        out = safe_output(args.out_dir, [p for _, p in sources])
    except ValueError as exc:
        parser().error(str(exc))
    out.mkdir(parents=True, exist_ok=True)
    tip = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[2],
                         capture_output=True, text=True).stdout.strip() or 'unknown'
    status = dict(status='FAIL', stage='phase2_adapter_staging_dry_run', reason='',
                  tip=tip, out_dir=str(out), dry_run=True, lake_writes=False)
    try:
        symbols = [s.strip().upper() for s in args.symbols]
        if not all(re.fullmatch(r'[0-9]{6}\.(SZ|SH|BJ)', s) for s in symbols):
            raise ValueError('invalid canonical symbol')
        pins = [dict(period=period, path=str(p), sha256=sha(p), unit='shares') for period, p in sources]
        minute = xcheck.read_bars([p for period, p in sources if period == '1m'], 'START', symbols)
        if minute.empty:
            raise ValueError('no observed Wind bars for selected symbols')
        tables = {'1m': minute}
        if args.ths_daily:
            tables['1d'] = read_daily([p for period, p in sources if period == '1d'], symbols)
            if tables['1d'].empty:
                raise ValueError('no observed THS daily bars for selected symbols')
        expected, audit, coverage = {}, [], {}
        for period, original in tables.items():
            # read_bars has mapped 09:30 START to hm=571; exclude that source row.
            dropped = original.hm == 571 if period == '1m' else pd.Series(False, index=original.index)
            kept = original.loc[~dropped].copy()
            frame, remainder = convert(kept, period, args.shares_to_lots_div)
            if frame.empty:
                raise ValueError(f'{period}: no continuous bars after auction exclusion')
            audit.extend(remainder)
            coverage[period] = dict(bars_in=len(original), bars_out=len(frame), auction_dropped=int(dropped.sum()),
                                   per_symbol={s: dict(bars_in=int((original.symbol == s).sum()),
                                                      bars_out=int((frame.symbol == s).sum()),
                                                      auction_dropped=int(((original.symbol == s) & dropped).sum())) for s in symbols},
                                   missing_requested_symbols=[s for s in symbols if s not in set(frame.symbol)],
                                   sparse_policy='A', invented_bars=0)
            for symbol, group in frame.groupby('symbol'):
                relative = Path(f'period={period}/dividend_type=none/symbol={symbol}/data.parquet')
                expected[relative] = group.reset_index(drop=True)
        pin = dict(minute_label='END; 09:30 auction excluded', unit='lots', unit_out='lots',
                   time_encoding='local_wall_as_utc_ms', transformations=TRANSFORMATIONS if args.ths_daily else TRANSFORMATIONS[:-1],
                   sparse_policy='A', shares_to_lots_div=args.shares_to_lots_div,
                   auction_policy=args.auction_policy, dry_run=True, lake_writes=False,
                   sources=pins, symbols=symbols, tip=tip,
                   human_acceptance='2026-10-01 Phase2 GO only; Phase3/4 and write-lake need separate Human GO; ≠δ5 ≠R4',
                   daily_label='trading day; no minute shift',
                   outputs=[dict(path=str(p), rows=len(df)) for p, df in expected.items()])
        for relative, frame in expected.items():
            target = (out / relative).resolve()
            if out not in target.parents:
                raise ValueError('output escapes out-dir')
            target.parent.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(target, index=False)
        for output in pin['outputs']:
            output['sha256'] = sha(out / output['path'])
        json_write(out / 'remainder_audit.json', audit)
        json_write(out / 'coverage_audit.json', coverage)
        json_write(out / 'PIN.json', pin)
        verify(out, expected, audit, pin)
        if any(sha(Path(s['path'])) != s['sha256'] for s in pins):
            raise ValueError('source changed during staging')
        status.update(status='PASS', reason='staging contract verified; not real-vendor acceptance')
    except Exception as exc:
        status['reason'] = str(exc)
    json_write(out / 'STATUS.json', status)
    (out / 'REPORT.md').write_text(
        '# Phase2 vendor→lake staging dry-run\n\n' + status['status'] + ': ' + status['reason'] +
        '\n\n仅 staging；无湖写入，≠δ5 ≠R4，不改 MatchCore/Fees。勿合，等待 Human「合」。\n'
        '\n布局：period={1m,1d}/dividend_type=none/symbol=XXX/data.parquet；volume 为 lots。'
        '\n1m 上海墙钟 END 按 UTC 毫秒编码。09:30 START 竞价删除；09:31 START → 09:32 END；'
        '13:00 START → 13:01 END。1d 仅交易日午夜键，不加一分钟；日线竞价汇总范围尚未验证。'
        '\nSparse A：不补缺分钟。余数见 remainder_audit.json；覆盖见 coverage_audit.json（仅所选标的）。'
        '\n防护：拒绝 stock_data 路径组件、配置湖根及其后代、输入目录重叠、非空输出目录；'
        '路径防护为 best-effort，未知命名的真实湖根不可能完全识别，调用方必须指定独立 staging。'
        '\n失败目录不能用于后续验收。Phase3/4 及写湖需独立 Human GO。\n', encoding='utf-8')
    return 0 if status['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
