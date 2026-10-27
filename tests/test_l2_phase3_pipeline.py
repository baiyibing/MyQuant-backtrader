"""Data-free orchestration and interrupted publish checks (stdlib unittest)."""
import json
import tempfile
import threading
import unittest
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
        folder.mkdir(exist_ok=True)
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

        def etl(day):
            if day == days[0]:
                self.assertTrue(second_extracted.wait(5), 'extract must overlap ETL')
            if day == days[2]:
                third_etl.set()
            self.ready(day)
            record = json.loads((pipeline.STAGING / f'date={day}' / '_ready.json').read_text())['manifest']
            with (pipeline.STAGING / '_manifest.jsonl').open('a') as handle:
                handle.write(json.dumps(record) + '\n')
            # The real ETL does not create the orchestrator readiness marker.
            (pipeline.STAGING / f'date={day}' / '_ready.json').unlink()
            return 0, 0.2, '', {'profile': {'test': True}}

        publish = pipeline.publish_day

        def delayed_publish(day):
            if day == days[0]:
                self.assertTrue(third_etl.wait(5), 'ETL must overlap publisher')
            published.append(day)
            return publish(day)

        with patch.object(pipeline, 'run_extract', side_effect=extract), \
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
        self.assertEqual(command[command.index('--out-root') + 1], str(pipeline.STAGING))
        self.assertEqual(kwargs['env']['OSKH_L2_PARQUET_ROOT'], str(pipeline.STAGING))
        self.assertEqual(rc, 0)
        self.assertEqual(parsed['profile'], {'chunk_s': 2})

    def test_ready_stage_resumes_without_archive_or_csv(self):
        day = '2025-01-02'
        self.ready(day)
        with patch.object(pipeline, 'run_extract', side_effect=AssertionError('extract')), \
             patch.object(pipeline, 'run_etl', side_effect=AssertionError('etl')):
            counts = pipeline.process_pipeline([day])
        self.assertEqual(counts['ok'], 1)


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

    def etl(day):
        assert pipeline.csv_ready(day)
        folder = pipeline.STAGING / f'date={day}'
        folder.mkdir()
        for name in ('main.parquet', 'order.parquet'):
            (folder / name).write_bytes(b'fake-parquet')
        with (pipeline.STAGING / '_manifest.jsonl').open('a') as handle:
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


if __name__ == '__main__':
    unittest.main()
