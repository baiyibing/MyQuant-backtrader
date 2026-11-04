"""Data-free orchestration and interrupted publish checks (stdlib unittest)."""
import json
import os
import tempfile
import threading
import unittest
import pytest
from pathlib import Path
from unittest.mock import patch

from scripts.misc import l2_phase3_pipeline as pipeline


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for key in ('SRC', 'CSV_ROOT', 'STAGING', 'ARCHIVES', 'LAKE'):
            value = root / key
            value.mkdir()
            patcher = patch.object(pipeline, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for key in ('LOG_JSONL', 'PROGRESS'):
            patcher = patch.object(pipeline, key, root / key)
            patcher.start()
            self.addCleanup(patcher.stop)

    def ready(self, day):
        folder = pipeline.STAGING / f'date={day}'
        folder.mkdir(parents=True, exist_ok=True)
        for name in ('main.parquet', 'order.parquet'):
            (folder / name).write_bytes(b'fake-parquet')
        record = {'date': day, 'main_parts': [f'date={day}/main.parquet'],
                  'order_parts': [f'date={day}/order.parquet']}
        (folder / '_ready.json').write_text(json.dumps({'manifest': record}))
        return folder

    def test_copy_failure_keeps_day_invisible_then_retry(self):
        day = '2025-01-02'
        self.ready(day)
        copy = pipeline.shutil.copy2

        def interrupted(source, target):
            if source.name == 'order.parquet':
                raise OSError('interrupted')
            return copy(source, target)

        with patch.object(pipeline.shutil, 'copy2', side_effect=interrupted):
            with self.assertRaises(OSError):
                pipeline.publish_day(day)
        self.assertFalse((pipeline.LAKE / f'date={day}').exists())
        self.assertNotIn(day, pipeline.done_dates())
        pipeline.publish_day(day)
        pipeline.publish_day(day)
        self.assertEqual(pipeline.done_dates(), {day})
        self.assertEqual(len(pipeline.manifest_records(pipeline.LAKE)), 1)

    def test_manifest_failure_after_rename_resumes(self):
        day = '2025-01-02'
        self.ready(day)
        with patch.object(pipeline.os, 'replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                pipeline.publish_day(day)
        self.assertTrue(pipeline.verify_lake(day)[0])
        self.assertNotIn(day, pipeline.done_dates())
        pipeline.publish_day(day)
        self.assertIn(day, pipeline.done_dates())

    def test_incomplete_lake_day_is_preserved(self):
        day = '2025-01-02'
        self.ready(day)
        folder = pipeline.LAKE / f'date={day}'
        folder.mkdir()
        (folder / 'main.parquet').write_bytes(b'original')
        with self.assertRaisesRegex(RuntimeError, 'incomplete existing'):
            pipeline.publish_day(day)
        self.assertEqual((folder / 'main.parquet').read_bytes(), b'original')

    def test_stages_overlap_without_batch_barrier(self):
        days = ['2025-01-02', '2025-01-03', '2025-01-06']
        for day in days:
            (pipeline.SRC / f'{day}.rar').write_bytes(b'archive')
        second_extracted = threading.Event()
        third_etl = threading.Event()
        published = []

        def extract(day):
            folder = pipeline.CSV_ROOT / day
            folder.mkdir()
            (folder / 'tick.csv').write_text('tick')
            if day == days[1]:
                second_extracted.set()
            return 0, 0.1, ''

        def etl(day, *, engine=None):
            if day == days[0]:
                self.assertTrue(second_extracted.wait(5), 'extract must overlap ETL')
            if day == days[2]:
                third_etl.set()
            self.ready(day)
            legacy = pipeline.STAGING / f'date={day}'
            target = pipeline.etl_root(day) / f'date={day}'
            target.parent.mkdir(parents=True)
            legacy.rename(target)
            record = json.loads((pipeline.stage_folder(day) / '_ready.json').read_text())['manifest']
            with (pipeline.etl_root(day) / '_manifest.jsonl').open('a') as handle:
                handle.write(json.dumps(record) + '\n')
            # The real ETL does not create the orchestrator readiness marker.
            (pipeline.stage_folder(day) / '_ready.json').unlink()
            return 0, 0.2, '', {'profile': {'test': True}}

        publish = pipeline.publish_day

        def delayed_publish(day):
            if day == days[0]:
                self.assertTrue(third_etl.wait(5), 'ETL must overlap publisher')
            published.append(day)
            return publish(day)

        with patch.dict(pipeline.os.environ, {'OSKH_L2_ETL_WORKERS': '1'}), \
             patch.object(pipeline, 'run_extract', side_effect=extract), \
             patch.object(pipeline, 'run_etl', side_effect=etl), \
             patch.object(pipeline, 'publish_day', side_effect=delayed_publish):
            counts = pipeline.process_pipeline(days)
        self.assertEqual(counts['ok'], 3)
        self.assertEqual(published, days)
        self.assertEqual(pipeline.done_dates(), set(days))
        self.assertFalse(any(pipeline.CSV_ROOT.iterdir()))

    def test_etl_subprocess_writes_staging_and_retains_profile(self):
        result = type('Result', (), {'returncode': 0, 'stdout':
                      'log\n{"profile": {"chunk_s": 2}}', 'stderr': ''})()
        with patch.object(pipeline, 'resolve_oskh_python', return_value=Path('/test/python')), \
             patch.object(pipeline.subprocess, 'run', return_value=result) as run:
            rc, _, _, parsed = pipeline.run_etl('2025-01-02')
        args, kwargs = run.call_args
        command = args[0]
        self.assertEqual(command[command.index('--out-root') + 1], str(pipeline.etl_root('2025-01-02')))
        self.assertEqual(kwargs['env']['OSKH_L2_PARQUET_ROOT'], str(pipeline.etl_root('2025-01-02')))
        self.assertEqual(rc, 0)
        self.assertEqual(parsed['profile'], {'chunk_s': 2})

    def test_ready_stage_resumes_without_archive_or_csv(self):
        day = '2025-01-02'
        self.ready(day)
        with patch.object(pipeline, 'run_extract', side_effect=AssertionError('extract')), \
             patch.object(pipeline, 'run_etl', side_effect=AssertionError('etl')):
            counts = pipeline.process_pipeline([day])
        self.assertEqual(counts['ok'], 1)

    def test_publish_raise_omits_timing(self):
        day = '2025-01-02'
        self.ready(day)
        with patch.object(pipeline, 'publish_day', side_effect=RuntimeError('publish interrupted')):
            counts = pipeline.process_pipeline([day])
        self.assertEqual(counts['publish_fail'], 1)
        self.assertEqual(counts['ok'], 0)
        rec = json.loads(pipeline.LOG_JSONL.read_text())
        self.assertEqual(rec['status'], 'publish_fail')
        self.assertNotIn('publish_s', rec)
        self.assertNotIn('csv_delete_s', rec)
        cells = [cell.strip() for cell in pipeline.PROGRESS.read_text().splitlines()[-1].split('|')[1:-1]]
        self.assertEqual(cells[6:8], ['', ''])

    def test_finalize_raise_retains_publish_timing(self):
        day = '2025-01-02'
        self.ready(day)
        with patch.object(pipeline, 'publish_day', return_value=(6.7896, 3, 4)), \
             patch.object(pipeline, 'finalize_ok', side_effect=RuntimeError('finalize interrupted')):
            counts = pipeline.process_pipeline([day])
        self.assertEqual(counts['publish_fail'], 1)
        self.assertEqual(counts['ok'], 0)
        rec = json.loads(pipeline.LOG_JSONL.read_text())
        self.assertEqual(rec['status'], 'publish_fail')
        self.assertEqual(rec['publish_s'], 6.79)
        self.assertNotIn('csv_delete_s', rec)
        cells = [cell.strip() for cell in pipeline.PROGRESS.read_text().splitlines()[-1].split('|')[1:-1]]
        self.assertEqual(cells[6:8], ['6.790', ''])


def test_readonly_archive_retry_and_cleanup(tmp_path, monkeypatch, capsys):
    import stat

    for key in ('SRC', 'CSV_ROOT', 'STAGING', 'ARCHIVES', 'LAKE'):
        root = tmp_path / key
        root.mkdir()
        monkeypatch.setattr(pipeline, key, root)
    for key in ('LOG_JSONL', 'PROGRESS'):
        monkeypatch.setattr(pipeline, key, tmp_path / key)

    replace = pipeline.os.replace
    unlink = Path.unlink
    source_days = ['2025-01-02', '2025-01-03']
    for day in source_days:
        source = pipeline.SRC / f'{day}.rar'
        source.write_bytes(b'archive')
        source.chmod(stat.S_IREAD)
        for suffix in ('.rar', '.rar.copying'):
            leftover = pipeline.ARCHIVES / f'{day}{suffix}'
            leftover.write_bytes(b'interrupted')
            leftover.chmod(stat.S_IREAD)

    def windows_replace(source, target):
        target = Path(target)
        if target.exists() and not target.stat().st_mode & stat.S_IWRITE:
            raise PermissionError('read-only destination')
        return replace(source, target)

    def windows_unlink(path, *args, **kwargs):
        if path.suffix == '.rar':
            assert path.stat().st_mode & stat.S_IWRITE
            if path.stem == source_days[1]:
                raise PermissionError('scratch file held open')
        return unlink(path, *args, **kwargs)

    def extract(day):
        archive = pipeline.ARCHIVES / f'{day}.rar'
        assert not archive.stat().st_mode & stat.S_IWRITE  # copy2 preserved mode
        folder = pipeline.CSV_ROOT / day
        folder.mkdir()
        (folder / 'tick.csv').write_text('tick', encoding='utf-8')
        return 0, 0.1, ''

    def etl(day, *, engine=None):
        assert pipeline.csv_ready(day)
        folder = pipeline.etl_root(day) / f'date={day}'
        folder.mkdir(parents=True)
        for name in ('main.parquet', 'order.parquet'):
            (folder / name).write_bytes(b'fake-parquet')
        with (pipeline.etl_root(day) / '_manifest.jsonl').open('a') as handle:
            handle.write(json.dumps({'date': day}) + '\n')
        return 0, 0.2, '', {}

    monkeypatch.setattr(pipeline.os, 'replace', windows_replace)
    monkeypatch.setattr(Path, 'unlink', windows_unlink)
    monkeypatch.setattr(pipeline, 'run_extract', extract)
    monkeypatch.setattr(pipeline, 'run_etl', etl)
    counts = pipeline.process_pipeline(source_days)
    assert counts['ok'] == 2
    assert counts['archive_fail'] == counts['extract_fail'] == 0
    assert pipeline.done_dates() == set(source_days)
    assert not (pipeline.ARCHIVES / f'{source_days[0]}.rar').exists()
    assert (pipeline.ARCHIVES / f'{source_days[1]}.rar').exists()
    assert 'archive cleanup deferred' in capsys.readouterr().out


def test_delete_csv_retries_readonly_file(tmp_path, monkeypatch):
    import stat

    monkeypatch.setattr(pipeline, 'CSV_ROOT', tmp_path)
    day = '2025-01-02'
    folder = tmp_path / day
    folder.mkdir()
    csv = folder / 'tick.csv'
    csv.write_text('tick', encoding='utf-8')
    csv.chmod(stat.S_IREAD)
    unlink = pipeline.os.unlink
    attempts = []

    def windows_unlink(path, *args, **kwargs):
        # Real rmtree may pass a basename with dir_fd or the full path.
        if Path(path).name == csv.name:
            writable = bool(csv.stat().st_mode & stat.S_IWRITE)
            attempts.append(writable)
            if len(attempts) == 1:
                assert not writable
                raise PermissionError('read-only CSV')
            assert writable  # The onerror helper must chmod before retrying.
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(pipeline.os, 'unlink', windows_unlink)
    pipeline.delete_csv(day)
    assert attempts == [False, True]
    assert not folder.exists()


def test_retry_readonly_reraises_non_permission_error(tmp_path):
    import pytest

    error = OSError('other')

    def unexpected_retry(path):
        raise AssertionError('non-permission errors must not be retried')

    with pytest.raises(OSError, match='other') as raised:
        pipeline._retry_readonly(unexpected_retry, str(tmp_path / 'missing.csv'),
                                 (OSError, error, None))
    assert raised.value is error


def test_finalize_observability(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, 'PROGRESS', tmp_path / 'progress.md')
    monkeypatch.setattr(pipeline, 'LOG_JSONL', tmp_path / 'progress.jsonl')
    monkeypatch.setattr(pipeline, 'delete_csv', lambda day: None)
    pipeline.finalize_ok('2025-01-02', 1.26, 2.34, 3, 4,
                         {'profile': {'chunk_s': 2}}, 'test',
                         archive_s=5.1236, publish_s=6.7896)
    rec = json.loads(pipeline.LOG_JSONL.read_text())
    assert 'prefetch_wait_s' not in rec
    assert rec['profile'] == {'chunk_s': 2}
    assert rec['archive_s'] == 5.124
    assert rec['publish_s'] == 6.79
    lines = pipeline.PROGRESS.read_text().splitlines()
    assert 'archive_s' in lines[2] and 'publish_s' in lines[2]
    assert 'csv_delete_s' in lines[2]
    assert '5.124' in lines[-1] and '6.790' in lines[-1]
    assert len(lines[2].split('|')) == len(lines[-1].split('|'))
    out = capsys.readouterr().out
    assert 'OK' in out and 'archive_s=5.124' in out and 'publish_s=6.790' in out
    assert 'extract_s=1.3' in out and 'etl_s=2.3' in out
    assert f"csv_delete_s={rec['csv_delete_s']:.3f}" in out


def test_failure_retains_partial_timings(tmp_path, monkeypatch):
    for key in ('SRC', 'CSV_ROOT', 'STAGING', 'ARCHIVES', 'LAKE'):
        root = tmp_path / key
        root.mkdir()
        monkeypatch.setattr(pipeline, key, root)
    for key in ('LOG_JSONL', 'PROGRESS'):
        monkeypatch.setattr(pipeline, key, tmp_path / key)
    day = '2025-01-02'
    (pipeline.SRC / f'{day}.rar').write_bytes(b'archive')
    monkeypatch.setattr(pipeline, 'run_extract', lambda day: (1, 1.26, 'extract failed'))
    counts = pipeline.process_pipeline([day])
    assert counts['extract_fail'] == 1
    rec = json.loads(pipeline.LOG_JSONL.read_text())
    assert rec['status'] == 'extract_fail'
    assert rec['archive_s'] >= 0
    assert rec['extract_s'] == 1.3
    assert not {'etl_s', 'publish_s', 'csv_delete_s'} & rec.keys()
    lines = pipeline.PROGRESS.read_text().splitlines()
    cells = [cell.strip() for cell in lines[-1].split('|')[1:-1]]
    assert cells[3] == f"{rec['archive_s']:.3f}"
    assert cells[4] == '1.3'
    assert cells[5:8] == ['', '', '']
    assert len(lines[2].split('|')) == len(lines[-1].split('|'))
    assert not pipeline.done_dates()


def test_progress_warns_for_legacy_header(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, 'PROGRESS', tmp_path / 'progress.md')
    legacy = ("# Legacy progress\n\n"
              "| time | date | status | extract_s | etl_s | main_gib | order_gib | notes |\n")
    pipeline.PROGRESS.write_text(legacy, encoding='utf-8')
    row = pipeline.progress_row({'ts': 'now', 'status': 'batch_start'})
    pipeline.append_progress_md(row)
    err = capsys.readouterr().err
    assert 'WARNING' in err and str(pipeline.PROGRESS) in err
    assert 'header lacks archive_s' in err and 'rotate' in err
    assert 'Continuing with new 11-column rows' in err
    assert pipeline.PROGRESS.read_text() == legacy + row + '\n'


def test_progress_invalid_utf8_warns_and_appends(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, 'PROGRESS', tmp_path / 'progress.md')
    legacy = b'# Legacy progress\xff\n\n| time | date | status | notes |\n'
    pipeline.PROGRESS.write_bytes(legacy)
    row = pipeline.progress_row({'ts': 'now', 'status': 'batch_start'})
    pipeline.append_progress_md(row)
    err = capsys.readouterr().err
    assert 'WARNING' in err and str(pipeline.PROGRESS) in err
    assert 'header lacks archive_s' in err
    assert pipeline.PROGRESS.read_bytes() == legacy + (row + os.linesep).encode('utf-8')


def test_progress_current_header_does_not_warn(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, 'PROGRESS', tmp_path / 'progress.md')
    row = pipeline.progress_row({'ts': 'now', 'status': 'batch_start'})
    pipeline.append_progress_md(row)
    pipeline.append_progress_md(row)
    assert capsys.readouterr().err == ''
    assert pipeline.PROGRESS.read_text().splitlines()[-2:] == [row, row]


if __name__ == '__main__':
    unittest.main()


def test_etl_worker_setting(monkeypatch):
    import pytest

    monkeypatch.delenv('OSKH_L2_ETL_WORKERS', raising=False)
    assert pipeline.etl_workers() == 2
    for raw in ('1', '3'):
        monkeypatch.setenv('OSKH_L2_ETL_WORKERS', raw)
        assert pipeline.etl_workers() == int(raw)
    for raw in ('0', '-1', 'bad', ''):
        monkeypatch.setenv('OSKH_L2_ETL_WORKERS', raw)
        with pytest.raises(ValueError, match='positive integer'):
            pipeline.process_pipeline([])


class DualETLTest(unittest.TestCase):
    setUp = PipelineTest.setUp
    ready = PipelineTest.ready

    def test_parallel_etl_drains_before_publish_exit(self):
        days = ['2025-01-02', '2025-01-03']
        both_running = threading.Barrier(2)
        second_published = threading.Event()
        published = []
        real_publish = pipeline.publish_day

        def etl(day, *, engine=None):
            both_running.wait(timeout=5)
            if day == days[0]:
                self.assertTrue(second_published.wait(5))
            folder = pipeline.etl_root(day) / f'date={day}'
            folder.mkdir(parents=True)
            for name in ('main.parquet', 'order.parquet'):
                (folder / name).write_bytes(b'parquet')
            (pipeline.etl_root(day) / '_manifest.jsonl').write_text(
                json.dumps({'date': day}) + '\n')
            return 0, 0.2, '', {'profile': {'day': day}}

        def publish(day):
            result = real_publish(day)
            published.append(day)
            if day == days[1]:
                second_published.set()
            return result

        for day in days:
            folder = pipeline.CSV_ROOT / day
            folder.mkdir()
            (folder / 'tick.csv').write_text('tick')
            (folder / '_extract_ready').touch()
        capacities = []
        queue_type = pipeline.queue.Queue

        def make_queue(maxsize):
            capacities.append(maxsize)
            return queue_type(maxsize=maxsize)

        with patch.dict(pipeline.os.environ, {'OSKH_L2_ETL_WORKERS': '2'}), \
             patch.object(pipeline.queue, 'Queue', side_effect=make_queue), \
             patch.object(pipeline, 'run_etl', side_effect=etl), \
             patch.object(pipeline, 'publish_day', side_effect=publish):
            counts = pipeline.process_pipeline(days + days)
        self.assertEqual(capacities, [1, 1, 2, 1])
        self.assertEqual(counts['ok'], 2)
        self.assertEqual(published, list(reversed(days)))
        self.assertEqual(pipeline.done_dates(), set(days))
        records = [json.loads(line) for line in pipeline.LOG_JSONL.read_text().splitlines()]
        self.assertEqual({r['profile']['day'] for r in records}, set(days))

    def test_three_failures_stop_and_workers_drain(self):
        days = [f'2025-01-{n:02d}' for n in range(1, 15)]
        for day in days:
            self.ready(day)
        with patch.dict(pipeline.os.environ, {'OSKH_L2_ETL_WORKERS': '2'}), \
             patch.object(pipeline, 'publish_day', side_effect=OSError('disk failure')):
            counts = pipeline.process_pipeline(days)
        self.assertEqual(counts['publish_fail'], 3)
        self.assertEqual(counts['ok'], 0)
        self.assertIn('batch_stop', pipeline.PROGRESS.read_text())
        self.assertIn('3 consecutive failures since last completed publish', pipeline.PROGRESS.read_text())
        self.assertTrue(all(pipeline.stage_ready(day) for day in days))


def test_mixed_engine_slots_and_subprocess_env(monkeypatch):
    monkeypatch.setenv("OSKH_L2_ETL_WORKERS", "4")
    monkeypatch.setenv("OSKH_L2_ETL_POLARS_WORKERS", "2")
    monkeypatch.setenv("OSKH_L2_ETL_ENGINE", "duckdb")
    assert pipeline.etl_engine_slots() == ["polars", "polars", "duckdb", "duckdb"]
    result = type("Result", (), {"returncode": 0, "stdout": "{}", "stderr": ""})()
    with patch.object(pipeline, "resolve_oskh_python", return_value=Path("/test/python")), \
         patch.object(pipeline.subprocess, "run", return_value=result) as run:
        for slot, engine in enumerate(pipeline.etl_engine_slots()):
            pipeline.run_etl(f"2025-01-0{slot + 1}", engine=engine)
    assert [c.kwargs["env"]["OSKH_L2_ETL_ENGINE"] for c in run.call_args_list] == [
        "polars", "polars", "duckdb", "duckdb"]
    monkeypatch.setenv("OSKH_L2_ETL_ENGINE", "polars")
    assert pipeline.etl_engine_slots() == ["polars"] * 4
    for invalid in ("-1", "5", "oops", "1.5"):
        monkeypatch.setenv("OSKH_L2_ETL_POLARS_WORKERS", invalid)
        with pytest.raises(ValueError, match="OSKH_L2_ETL_POLARS_WORKERS"):
            pipeline.process_pipeline([])


@pytest.fixture
def isolated_pipeline(tmp_path, monkeypatch):
    for key in ('SRC', 'CSV_ROOT', 'STAGING', 'ARCHIVES', 'LAKE'):
        root = tmp_path / key
        root.mkdir()
        monkeypatch.setattr(pipeline, key, root)
    for key in ('LOG_JSONL', 'PROGRESS'):
        monkeypatch.setattr(pipeline, key, tmp_path / key)
    monkeypatch.setenv('OSKH_L2_ETL_WORKERS', '1')
    monkeypatch.setenv('OSKH_L2_ETL_POLARS_WORKERS', '0')
    monkeypatch.setattr(pipeline, 'resolve_oskh_python', lambda: Path('/test/python'))


@pytest.mark.parametrize('engine', ['duckdb', 'polars'])
@pytest.mark.parametrize('rc', [2, 0])
def test_gap_free_failure_retains_evidence_and_blocks_publish(isolated_pipeline, monkeypatch, engine, rc):
    day = '2021-01-06'
    monkeypatch.setenv('OSKH_L2_ETL_ENGINE', engine)
    csv = pipeline.CSV_ROOT / day
    csv.mkdir()
    (csv / 'tick.csv').write_text('retained', encoding='utf-8')
    (csv / '_extract_ready').touch()
    folder = pipeline.stage_folder(day)
    folder.mkdir(parents=True)
    for name in ('main.parquet', 'order.parquet'):
        (folder / name).write_bytes(b'nonempty staging')
    failures = ['000001.csv: rows=123 uniq=123 min=2 max=124', '600036.csv: rows=50 uniq=49 min=1 max=70']
    result = {'gap_free_ok': False, 'gap_free_failures': failures,
              'profile': {'chunks': ['profile-tail-scrap' * 100]}}
    output = json.dumps(result, indent=2)
    response = type('Result', (), {'returncode': rc, 'stdout': output, 'stderr': 'warning'})()
    with patch.object(pipeline.subprocess, 'run', return_value=response) as run, \
         patch.object(pipeline, 'publish_day', side_effect=AssertionError('must not publish')):
        counts = pipeline.process_pipeline([day])
    assert counts['etl_fail'] == 1 and counts['ok'] == 0
    assert not (folder / '_ready.json').exists()
    assert not pipeline.done_dates()
    assert (csv / 'tick.csv').exists()
    record = json.loads(pipeline.LOG_JSONL.read_text(encoding='utf-8'))
    assert '"gap_free_ok": false' in record['notes']
    assert all(failure in record['notes'] for failure in failures)
    assert 'profile-tail-scrap' not in record['notes']
    evidence = json.loads((pipeline.etl_root(day) / '_etl_fail.json').read_text(encoding='utf-8'))
    assert evidence == {'day': day, 'engine': engine, 'returncode': rc,
                        'result': result, 'stderr_excerpt': 'warning'}
    command = run.call_args.args[0]
    assert command[command.index('--gap-free-sample') + 1] == '50'


@pytest.mark.parametrize('operation', ['mkdir', 'write_text', 'replace'])
@pytest.mark.parametrize('rc', [2, 0])
def test_evidence_oserror_preserves_cli_result(isolated_pipeline, capsys, operation, rc):
    day = '2021-01-07'
    result = {'gap_free_ok': False, 'gap_free_failures': ['sample.csv: rows=9 uniq=9 min=2 max=10']}
    response = type('Result', (), {'returncode': rc, 'stdout': json.dumps(result), 'stderr': ''})()
    target = pipeline.os if operation == 'replace' else Path
    with patch.object(pipeline.subprocess, 'run', return_value=response), \
         patch.object(target, operation, side_effect=OSError('evidence unavailable')):
        actual_rc, elapsed, note, parsed = pipeline.run_etl(day, engine='duckdb')
    assert actual_rc == rc and elapsed >= 0
    assert parsed == result
    assert note == f'ETL rc={rc}: ' + json.dumps(result)
    assert not (pipeline.etl_root(day) / '_etl_fail.json').exists()
    assert f'WARNING: ETL failure evidence write failed {day}: evidence unavailable' in capsys.readouterr().err


def test_evidence_oserror_keeps_worker_validation_note(isolated_pipeline):
    day = '2021-01-08'
    csv = pipeline.CSV_ROOT / day
    csv.mkdir()
    (csv / 'tick.csv').write_text('retained', encoding='utf-8')
    (csv / '_extract_ready').touch()
    folder = pipeline.stage_folder(day)
    folder.mkdir(parents=True)
    for name in ('main.parquet', 'order.parquet'):
        (folder / name).write_bytes(b'nonempty staging')
    result = {'gap_free_ok': False, 'gap_free_failures': ['sample.csv: rows=9 uniq=9 min=2 max=10']}
    response = type('Result', (), {'returncode': 2, 'stdout': json.dumps(result), 'stderr': ''})()
    with patch.object(pipeline.subprocess, 'run', return_value=response), \
         patch.object(pipeline.os, 'replace', side_effect=OSError('evidence unavailable')), \
         patch.object(pipeline, 'publish_day') as publish:
        counts = pipeline.process_pipeline([day])
    assert counts['etl_fail'] == 1 and counts['ok'] == 0
    publish.assert_not_called()
    assert not (folder / '_ready.json').exists()
    assert not pipeline.done_dates()
    assert (csv / 'tick.csv').exists()
    record = json.loads(pipeline.LOG_JSONL.read_text(encoding='utf-8'))
    assert record['status'] == 'etl_fail' and 'etl_s' in record
    assert record['notes'] == 'ETL rc=2: ' + json.dumps(result)


@pytest.mark.parametrize('output', ['crash\n' * 2000, '{invalid json', '[1, 2]'])
def test_etl_crash_fallback_is_bounded_and_raw_output_persisted(isolated_pipeline, output):
    stderr = 'traceback\n' * 2000
    response = type('Result', (), {'returncode': 1, 'stdout': output, 'stderr': stderr})()
    with patch.object(pipeline.subprocess, 'run', return_value=response):
        rc, _, note, parsed = pipeline.run_etl('2021-01-07', engine='duckdb')
    assert rc == 1 and parsed == {}
    assert len(note) <= 850
    assert 'ETL rc=1: stdout=' in note and '; stderr=' in note
    evidence = json.loads((pipeline.etl_root('2021-01-07') / '_etl_fail.json').read_text(encoding='utf-8'))
    assert evidence['stdout'] == output
    assert evidence['returncode'] == 1 and evidence['engine'] == 'duckdb'
    assert evidence['stderr_excerpt'] == stderr.strip()[-1000:]


def test_mocked_nonzero_etl_uses_validation_note(isolated_pipeline, monkeypatch):
    day = '2021-01-12'
    csv = pipeline.CSV_ROOT / day
    csv.mkdir()
    (csv / 'tick.csv').touch()
    (csv / '_extract_ready').touch()
    folder = pipeline.stage_folder(day)
    folder.mkdir(parents=True)
    for name in ('main.parquet', 'order.parquet'):
        (folder / name).write_bytes(b'parquet')
    result = {'gap_free_ok': False, 'gap_free_failures': ['sample.csv: rows=9 uniq=9 min=2 max=10']}
    monkeypatch.setattr(pipeline, 'run_etl', lambda day, *, engine: (2, 1.2, 'profile scrap', result))
    with patch.object(pipeline, 'publish_day') as publish:
        counts = pipeline.process_pipeline([day])
    assert counts['etl_fail'] == 1
    publish.assert_not_called()
    assert not (folder / '_ready.json').exists()
    note = json.loads(pipeline.LOG_JSONL.read_text(encoding='utf-8'))['notes']
    assert 'sample.csv: rows=9 uniq=9 min=2 max=10' in note
    assert 'profile scrap' not in note
