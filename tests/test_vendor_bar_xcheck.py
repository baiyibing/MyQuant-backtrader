"""Synthetic only: no host or physical lake dependency."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location('vendor_bar_xcheck', Path(__file__).parents[1] / 'scripts/research/vendor_bar_xcheck.py')
x = importlib.util.module_from_spec(spec)
spec.loader.exec_module(x)


def fixtures(tmp_path, minutes=('10:00',), ratio=1):
    src = tmp_path / 'inputs'
    src.mkdir()
    times = pd.to_datetime(['2025-10-24 ' + t for t in minutes])
    wind = pd.DataFrame(dict(TIME=[t.isoformat() + '+08:00' for t in times], wind_code='002231.SZ', OPEN=10., HIGH=11., LOW=9., MATCH=10.5, VOLUME=100. * ratio))
    lake = pd.DataFrame(dict(time=(times + pd.Timedelta(minutes=1)).as_unit('ns').astype('int64') // 10**6, symbol='002231.SZ', open=10., high=11., low=9., close=10.5, volume=100.))
    wp, lp = src / 'wind.csv', src / 'lake.parquet'
    wind.to_csv(wp, index=False)
    lake.to_parquet(lp, index=False)
    return wp, lp


@pytest.mark.parametrize('minute,boundary', [('10:00', None), ('13:00', 'lunch_1300_to_1301'), ('09:30', 'open_0930_to_0931')])
def test_interval(tmp_path, minute, boundary):
    w, l = fixtures(tmp_path, (minute,))
    report = x.compare(x.read_bars([w], 'START'), x.read_bars([l], 'END'))
    assert report['status'] == 'PASS'
    assert report['per_symbol']['002231.SZ']['intersection'] == 1
    if boundary:
        assert report['boundary_coverage'][boundary]['intersection'] == 1


def test_missing(tmp_path):
    w, l = fixtures(tmp_path, ('10:00', '10:01'))
    pd.read_parquet(l).iloc[:1].to_parquet(l, index=False)
    r = x.compare(x.read_bars([w], 'START'), x.read_bars([l], 'END'))
    assert r['status'] == 'PASS'
    assert r['per_symbol']['002231.SZ']['intersection'] == 1
    assert r['per_symbol']['002231.SZ']['wind_only'] == 1


def test_price_mismatch(tmp_path):
    w, l = fixtures(tmp_path)
    df = pd.read_parquet(l)
    df['close'] = 12
    df.to_parquet(l, index=False)
    r = x.compare(x.read_bars([w], 'START'), x.read_bars([l], 'END'))
    assert r['status'] == 'FAIL'
    assert r['mismatches_sample'][0]['field_path'] == '002231.SZ/20251024/601/close'


@pytest.mark.parametrize('ratio', [100, .01])
def test_volume_suspect(tmp_path, ratio):
    w, l = fixtures(tmp_path, ratio=ratio)
    r = x.compare(x.read_bars([w], 'START'), x.read_bars([l], 'END'))
    assert r['status'] == 'FAIL'
    assert r['unit_notes'][0]['volume_unit_suspect']


def test_cli_scale_smoke(tmp_path):
    w, l = fixtures(tmp_path, ratio=100)
    before = (w.read_bytes(), l.read_bytes())
    out = tmp_path / 'out'
    assert x.main(['--wind', str(w), '--lake', str(l), '--volume-scale', '100', '--out-dir', str(out)]) == 0
    r = json.loads((out / 'report.json').read_text())
    assert r['policy']['volume_scale'] == 100
    assert r['unit_notes'][0]['acknowledged']
    assert (out / 'STATUS.json').exists() and (out / 'REPORT.md').exists()
    assert before == (w.read_bytes(), l.read_bytes())


def test_hive_datetime_and_duplicate(tmp_path):
    w, l = fixtures(tmp_path)
    df = pd.read_parquet(l).drop(columns='symbol')
    df['time'] = pd.to_datetime(df.time, unit='ms')
    hive = tmp_path / 'symbol=002231.SZ' / 'data.parquet'
    hive.parent.mkdir()
    df.to_parquet(hive, index=False)
    assert x.compare(x.read_bars([w], 'START'), x.read_bars([hive], 'END'))['status'] == 'PASS'
    with pytest.raises(ValueError, match='duplicate'):
        x.read_bars([hive, hive], 'END')


def test_empty_and_outside_session(tmp_path):
    w, l = fixtures(tmp_path)
    lake = x.read_bars([l], 'END')
    lake['ymd'] = '20251027'
    assert x.compare(x.read_bars([w], 'START'), lake)['status'] == 'FAIL'
    df = pd.read_csv(w)
    df['TIME'] = '2025-10-24T11:30:00+08:00'
    df.to_csv(w, index=False)
    with pytest.raises(ValueError, match='outside'):
        x.read_bars([w], 'START')


def test_host_missing_lake_reports(tmp_path):
    root = tmp_path / 'host'
    (root / 'market').mkdir(parents=True)
    pd.DataFrame({'dummy': [1]}).to_parquet(root / 'market/minute.parquet')
    out = tmp_path / 'out'
    assert x.main(['--host-root', str(root), '--out-dir', str(out)]) == 1
    r = json.loads((out / 'report.json').read_text())
    assert r['host_discovery']['market_not_adopted']
    assert r['error'] == 'missing input paths'


def test_cli_process(tmp_path):
    import subprocess
    import sys
    w, l = fixtures(tmp_path)
    out = tmp_path / 'process_out'
    result = subprocess.run([sys.executable, str(Path(x.__file__)), '--wind', str(w), '--lake', str(l), '--out-dir', str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads((out / 'STATUS.json').read_text())['status'] == 'PASS'
