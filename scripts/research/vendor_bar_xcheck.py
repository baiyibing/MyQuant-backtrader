"""Read-only sample interval comparison; never relabel or write source tables.

The median near 100 or 0.01 heuristic only flags volume_unit_suspect.
--volume-scale is an explicit, recorded lake-volume multiplier for comparison;
never silently detect or convert lots/shares, including in future CLI edits.
HostRoot market/**/*.parquet is listed only as market_not_adopted: mixed
START/END overlays are not pure lake by default. Opt-in requires separate
Human GO and must not enter this knife's default path.
Synthetic tests / sample PASS cover the scaffold contract only: ≠δ5 ≠R4;
they do not substitute δ5 certified or R4 market acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

import numpy as np
import pandas as pd

FIELDS = ('open', 'high', 'low', 'close', 'volume')
KEYS = ['symbol', 'ymd', 'hm']


def read_bars(paths, label, symbols=None):
    frames = []
    for path in paths:
        path = Path(path)
        df = pd.read_csv(path) if path.suffix.lower() == '.csv' else pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.rename(columns={'match': 'close', 'wind_code': 'symbol'})
        if 'symbol' not in df:
            match = re.search(r'symbol=([0-9]{6}\.(?:SZ|SH|BJ))', str(path), re.I)
            if not match:
                raise ValueError(f'{path}: missing symbol column/hive partition')
            df['symbol'] = match.group(1)
        df['symbol'] = df.symbol.astype(str).str.upper().str.strip()
        if symbols:
            df = df[df.symbol.isin(symbols)].copy()
        if df.empty:
            frames.append(pd.DataFrame(columns=KEYS + list(FIELDS)))
            continue
        if not df.symbol.str.fullmatch(r'[0-9]{6}\.(SZ|SH|BJ)').all():
            raise ValueError(f'{path}: invalid canonical symbol')
        stamp = df['time']
        # Numeric lake times encode wall clock as UTC ms, not actual UTC instants.
        if pd.api.types.is_numeric_dtype(stamp):
            times = pd.to_datetime(stamp, unit='ms', utc=True).dt.tz_localize(None)
        else:
            def wall(value):
                ts = pd.Timestamp(value)
                return ts.tz_convert('Asia/Shanghai').tz_localize(None) if ts.tzinfo else ts
            times = stamp.map(wall)
        if times.isna().any() or ((times.dt.second != 0) | (times.dt.microsecond != 0) | (times.dt.nanosecond != 0)).any():
            raise ValueError(f'{path}: invalid/non-minute time')
        df['ymd'] = times.dt.strftime('%Y%m%d')
        hm = times.dt.hour * 60 + times.dt.minute
        valid = ((hm >= 570) & (hm < 690) | (hm >= 780) & (hm < 900)) if label == 'START' else ((hm > 570) & (hm <= 690) | (hm > 780) & (hm <= 900))
        if not valid.all():
            raise ValueError(f'{path}: outside declared continuous-session intervals; boundary/auction requires review')
        # Explicit open 09:30 -> 09:31 and lunch 13:00 -> 13:01;
        # no cross-lunch shift and no source-table mutation.
        df['hm'] = hm + (1 if label == 'START' else 0)
        for field in FIELDS:
            df[field] = pd.to_numeric(df[field], errors='raise')
            if not np.isfinite(df[field]).all() or (df[field] < 0).any():
                raise ValueError(f'{path}: invalid {field}')
        frames.append(df[KEYS + list(FIELDS)])
    if not frames:
        raise ValueError('missing input paths')
    result = pd.concat(frames, ignore_index=True)
    if result.duplicated(KEYS).any():
        raise ValueError('duplicate interval keys')
    return result


def compare(wind, lake, *, price_atol=1e-8, price_rtol=0.0, volume_atol=0.0,
            volume_scale=None, pin=None):
    joined = wind.merge(lake, on=KEYS, how='outer', suffixes=('_wind', '_lake'), indicator=True)
    both = joined[joined._merge == 'both'].copy()
    mismatches, stats, units = [], {}, []
    for symbol in sorted(joined.symbol.unique()):
        rows = joined[joined.symbol == symbol]
        common = both[both.symbol == symbol]
        ratios = common.loc[common.volume_lake > 0, 'volume_wind'] / common.loc[common.volume_lake > 0, 'volume_lake']
        median = float(ratios.median()) if len(ratios) else None
        suspect = median is not None and any(math.isclose(median, x, rel_tol=.05) for x in (100, .01))
        acknowledged = volume_scale is not None or bool((pin or {}).get('volume_unit_suspect_acknowledgement'))
        units.append(dict(symbol=symbol, median_wind_over_lake=median, volume_unit_suspect=suspect,
                          acknowledged=acknowledged, recommendation='Confirm lots/shares in source-specific PIN; no automatic scaling'))
        count = 0
        for field in FIELDS:
            w = common[field + '_wind']
            l = common[field + '_lake']
            # User-supplied comparison multiplier only; never infer a unit conversion.
            if field == 'volume':
                l = l * (volume_scale if volume_scale is not None else 1)
            ok = np.isclose(w, l, atol=volume_atol if field == 'volume' else price_atol,
                            rtol=0 if field == 'volume' else price_rtol)
            count += int((~ok).sum())
            for idx in common.index[~ok]:
                if len(mismatches) < 100:
                    row = common.loc[idx]
                    mismatches.append(dict(symbol=symbol, ymd=row.ymd, hm=int(row.hm), field=field,
                                           field_path=f'{symbol}/{row.ymd}/{int(row.hm)}/{field}',
                                           wind=float(w.loc[idx]), lake=float(l.loc[idx])))
        stats[symbol] = dict(intersection=len(common), wind_only=int((rows._merge == 'left_only').sum()),
                             lake_only=int((rows._merge == 'right_only').sum()), mismatch_fields=count)
    boundaries = {}
    for name, hm in [('open_0930_to_0931', 571), ('lunch_1300_to_1301', 781)]:
        rows = joined[joined.hm == hm]
        boundaries[name] = dict(intersection=int((rows._merge == 'both').sum()),
                                wind_only=int((rows._merge == 'left_only').sum()), lake_only=int((rows._merge == 'right_only').sum()),
                                keys=rows[KEYS].head(20).to_dict('records'))
    failed = not len(both) or any(s['intersection'] == 0 or s['mismatch_fields'] for s in stats.values()) or any(u['volume_unit_suspect'] and not u['acknowledged'] for u in units)
    return dict(status='FAIL' if failed else 'PASS', per_symbol=stats, mismatches_sample=mismatches,
                coverage_samples={side: joined[joined._merge == code][KEYS].head(20).to_dict('records') for side, code in [('wind_only', 'left_only'), ('lake_only', 'right_only')]},
                boundary_coverage=boundaries, unit_notes=units,
                policy=dict(price_atol=price_atol, price_rtol=price_rtol, volume_atol=volume_atol,
                            volume_scale=volume_scale, scale_applies_to='lake volume', intersection_only=True), pin_notes=pin)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('wind', 'lake'):
        p.add_argument('--' + name, action='append', nargs='+', default=[])
    p.add_argument('--host-root', type=Path,
                   help='Discover Wind/prepare inputs; market/**/*.parquet is listed only '
                        '(market_not_adopted). Mixed START/END overlay is not pure lake by '
                        'default; opt-in requires separate Human GO, outside this knife default.')
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--symbols', nargs='+')
    for name, default in [('wind', 'START'), ('lake', 'END')]:
        p.add_argument('--' + name + '-label', choices=['START', 'END'], default=default)
    for name, default in [('price-atol', 1e-8), ('price-rtol', 0), ('volume-atol', 0), ('volume-scale', None)]:
        help_text = ('Explicit recorded lake-volume multiplier for comparison; acknowledges '
                     'volume_unit_suspect, never auto-detects or converts lots/shares. '
                     'Future CLI edits must not add automatic unit conversion.'
                     if name == 'volume-scale' else None)
        p.add_argument('--' + name, type=float, default=default, help=help_text)
    p.add_argument('--pin', type=Path)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    wind = [Path(x) for group in args.wind for x in group]
    lake = [Path(x) for group in args.lake for x in group]
    discovery = {}
    if args.host_root:
        found_wind = sorted(args.host_root.glob('vendor_fill/raw/wind_*_1m*.csv'))
        found_prepare = sorted(args.host_root.glob('prepare/**/*minute*.parquet'))
        found_market = sorted(args.host_root.glob('market/**/*.parquet'))
        discovery = dict(wind=[str(p) for p in found_wind], prepare_candidates=[str(p) for p in found_prepare],
                         market_not_adopted=[str(p) for p in found_market], note='Market listed only; mixed START/END overlay is not pure lake by default. Opt-in requires separate Human GO and explicit lake paths; do not fold into this knife default.')
        wind = wind or found_wind
        lake = lake or found_prepare
    out = args.out_dir.resolve()
    # Refuse output inside input locations, including a lake hive tree.
    protected = [p.resolve().parent for p in wind + lake] + ([args.host_root.resolve()] if args.host_root else [])
    if any(out == p or p in out.parents for p in protected):
        parser().error('out-dir must be outside input directories/HostRoot')
    try:
        for value in (args.price_atol, args.price_rtol, args.volume_atol):
            if not math.isfinite(value) or value < 0:
                raise ValueError('tolerances must be finite and nonnegative')
        if args.volume_scale is not None and (not math.isfinite(args.volume_scale) or args.volume_scale <= 0):
            raise ValueError('volume-scale must be finite and positive')
        pin = json.loads(args.pin.read_text(encoding='utf-8')) if args.pin else None
        if pin is not None and not isinstance(pin, dict):
            raise ValueError('PIN must be a JSON object')
        report = compare(read_bars(wind, args.wind_label, args.symbols), read_bars(lake, args.lake_label, args.symbols),
                         price_atol=args.price_atol, price_rtol=args.price_rtol, volume_atol=args.volume_atol,
                         volume_scale=args.volume_scale, pin=pin)
        report['inputs'] = {name: [dict(path=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths] for name, paths in [('wind', wind), ('lake', lake)]}
        report['labels'] = dict(wind=args.wind_label, lake=args.lake_label)
        reason = 'intersection policy satisfied' if report['status'] == 'PASS' else 'mismatch, unacknowledged unit suspect, or empty symbol intersection'
    except Exception as exc:  # Input/decoder errors must also leave a FAIL receipt.
        report = dict(status='FAIL', error=str(exc))
        reason = str(exc)
    report['host_discovery'] = discovery
    tip = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or 'unknown'
    status = dict(status=report['status'], stage='sample_cross_check', reason=reason, tip=tip, out_dir=str(out))
    out.mkdir(parents=True, exist_ok=True)
    for name, content in [('STATUS.json', status), ('report.json', report)]:
        (out / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'REPORT.md').write_text('# Wind ↔ lake sample OHLCV cross-check\n\n' + report['status'] + ': ' + reason + '\n\nRead-only; ≠δ5 ≠R4. No source relabel, zero-fill or automatic unit conversion.\n09:30 auction scope remains source-specific; sample PASS does not authorize ingest.\n\n```json\n' + json.dumps(report, ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
