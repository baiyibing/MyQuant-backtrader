"""Synthetic Phase2 staging contracts; no physical lake dependency."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location('adapter', Path(__file__).parents[1] / 'scripts/research/vendor_to_lake_adapter.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def source(tmp_path, minutes=('09:30', '09:31', '10:00', '10:02', '13:00'), volumes=None):
    inputs = tmp_path / 'inputs'
    inputs.mkdir(exist_ok=True)
    path = inputs / 'wind.csv'
    pd.DataFrame(dict(TIME=['2025-10-24T' + t + ':00+08:00' for t in minutes],
                      wind_code='002231.SZ', OPEN=10., HIGH=11., LOW=9., MATCH=10.5,
                      VOLUME=volumes or [250] * len(minutes))).to_csv(path, index=False)
    return path


def run(tmp_path, **kwargs):
    path = source(tmp_path, **kwargs)
    out = tmp_path / 'out'
    assert a.main(['--wind', str(path), '--out-dir', str(out)]) == 0
    frame = pd.read_parquet(out / 'period=1m/dividend_type=none/symbol=002231.SZ/data.parquet')
    return out, frame


def test_continuous_lunch_auction_sparse(tmp_path):
    out, frame = run(tmp_path)
    hm = pd.to_datetime(frame.time, unit='ms').dt.strftime('%H:%M').tolist()
    assert hm == ['09:32', '10:01', '10:03', '13:01']
    assert frame.volume.tolist() == [2] * 4
    assert '09:31' not in hm and '13:00' not in hm and '10:02' not in hm
    audit = json.loads((out / 'coverage_audit.json').read_text())['1m']
    assert (audit['bars_in'], audit['bars_out'], audit['auction_dropped'], audit['invented_bars']) == (5, 4, 1, 0)


def test_remainder_and_pin(tmp_path):
    out, _ = run(tmp_path, minutes=('10:00', '10:02'), volumes=[251, 300])
    audit = json.loads((out / 'remainder_audit.json').read_text())
    assert len(audit) == 1
    assert (audit[0]['shares'], audit[0]['volume_lots'], audit[0]['remainder_shares']) == (251, 2, 51)
    pin = json.loads((out / 'PIN.json').read_text())
    assert pin['minute_label'] == 'END; 09:30 auction excluded'
    assert pin['unit'] == pin['unit_out'] == 'lots'
    assert pin['dry_run'] and pin['sparse_policy'] == 'A'
    assert pin['transformations'] and len(pin['sources'][0]['sha256']) == 64
    assert pin['time_encoding'] == 'local_wall_as_utc_ms'
    (out / 'remainder_audit.json').unlink()
    with pytest.raises(FileNotFoundError):
        a.verify(out, {}, audit, pin)


def test_cli_process_read_only(tmp_path):
    path = source(tmp_path)
    before = path.read_bytes()
    outside = {p.relative_to(tmp_path) for p in tmp_path.rglob('*')}
    out = tmp_path / 'out'
    proc = subprocess.run([sys.executable, a.__file__, '--wind', str(path), '--out-dir', str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert path.read_bytes() == before
    added = {p.relative_to(tmp_path) for p in tmp_path.rglob('*')} - outside
    assert all(p.parts[0] == 'out' for p in added)
    assert json.loads((out / 'STATUS.json').read_text())['lake_writes'] is False
    assert '--write-lake' not in a.parser().format_help()
    assert subprocess.run([sys.executable, a.__file__, '--write-lake'], capture_output=True).returncode != 0


@pytest.mark.parametrize('date', ['2025-10-24', '20251024', '2025-10-24T15:00:00+08:00'])
def test_daily(tmp_path, date):
    path = source(tmp_path)
    daily = path.parent / 'ths.csv'
    pd.DataFrame(dict(time=[date], thscode=['002231.SZ'], open=[10.], high=[11.], low=[9.], close=[10.5], volume=[399])).to_csv(daily, index=False)
    out = tmp_path / 'out'
    assert a.main(['--wind', str(path), '--ths-daily', str(daily), '--out-dir', str(out)]) == 0
    frame = pd.read_parquet(out / 'period=1d/dividend_type=none/symbol=002231.SZ/data.parquet')
    assert pd.to_datetime(frame.time, unit='ms').iloc[0] == pd.Timestamp('2025-10-24')
    assert frame.volume.iloc[0] == 3
    assert any(r['period'] == '1d' and r['remainder_shares'] == 99 for r in json.loads((out / 'remainder_audit.json').read_text()))


@pytest.mark.parametrize('bad', ['stock_data/out', 'E:' + chr(92) + 'stock_data' + chr(92) + 'stage', 'inputs/stage'])
def test_protected_output(tmp_path, bad):
    path = source(tmp_path)
    out = tmp_path / bad
    with pytest.raises(SystemExit):
        a.main(['--wind', str(path), '--out-dir', str(out)])
    assert not out.exists()


def test_symlink_and_configured_root(tmp_path, monkeypatch):
    path = source(tmp_path)
    lake = tmp_path / 'stock_data'
    lake.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(lake, target_is_directory=True)
    with pytest.raises(SystemExit):
        a.main(['--wind', str(path), '--out-dir', str(alias / 'out')])
    root = tmp_path / 'custom_lake'
    monkeypatch.setenv('OSKH_SOURCE_PARQUET_ROOT', str(root))
    with pytest.raises(SystemExit):
        a.main(['--wind', str(path), '--out-dir', str(root / 'out')])
    assert not root.exists()


@pytest.mark.parametrize('minutes,volumes', [(('11:30',), [100]), (('10:00',), [1.5]), (('10:00',), [-1]), (('10:00', '10:00'), [100, 100]), (('09:30',), [100])])
def test_fail_status(tmp_path, minutes, volumes):
    path = source(tmp_path, minutes, volumes)
    out = tmp_path / 'out'
    assert a.main(['--wind', str(path), '--out-dir', str(out)]) == 1
    assert json.loads((out / 'STATUS.json').read_text())['status'] == 'FAIL'


def test_nonempty_output_untouched(tmp_path):
    path = source(tmp_path)
    out = tmp_path / 'out'
    out.mkdir()
    marker = out / 'keep'
    marker.write_text('keep')
    with pytest.raises(SystemExit):
        a.main(['--wind', str(path), '--out-dir', str(out)])
    assert list(out.iterdir()) == [marker] and marker.read_text() == 'keep'


def test_parquet_input_and_symbol_filter(tmp_path):
    path = source(tmp_path)
    frame = pd.read_csv(path)
    other = frame.copy()
    other['wind_code'] = '600113.SH'
    parquet = path.with_suffix('.parquet')
    pd.concat([frame, other]).to_parquet(parquet, index=False)
    out = tmp_path / 'out'
    assert a.main(['--wind', str(parquet), '--out-dir', str(out)]) == 0
    assert not (out / 'period=1m/dividend_type=none/symbol=600113.SH').exists()
