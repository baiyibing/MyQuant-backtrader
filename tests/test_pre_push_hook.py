"""Fast repository-only checks for the opt-in push gate."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / '.githooks' / 'pre-push'


def clean_env():
    env = os.environ.copy()
    # A pre-push self-run must not redirect temporary Git repos to the real repo.
    for name in (
        'GIT_DIR',
        'GIT_WORK_TREE',
        'GIT_INDEX_FILE',
        'GIT_OBJECT_DIRECTORY',
        'GIT_ALTERNATE_OBJECT_DIRECTORIES',
        'GIT_COMMON_DIR',
        'GIT_PREFIX',
        'GIT_CEILING_DIRECTORIES',
        'SKIP_PREPUSH',
        'OSKH_MERGE_PYTHON',
        'VANNA312_PYTHON',
        'VANNA311_PYTHON',
        'PYTHON',
        'PREPUSH_PYTEST_ARGS',
    ):
        env.pop(name, None)
    return env


def run(args, cwd, **kwargs):
    kwargs.setdefault('env', clean_env())
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=30, **kwargs
    )


def test_hook_format():
    content = HOOK.read_bytes()
    assert content.startswith(b'#!/bin/sh\n')
    assert b'\r\n' not in content


@pytest.mark.parametrize('path', ['.githooks/pre-push', 'scripts/install-git-hooks.sh'])
def test_hook_executable_index(path):
    if not shutil.which('git'):
        pytest.skip('git unavailable')
    result = run(['git', 'ls-files', '-s', path], ROOT)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith('100755 ')


@pytest.fixture
def protected_push(tmp_path):
    git_exe = shutil.which('git')
    if not git_exe:
        pytest.skip('git unavailable')
    if os.name == 'nt':
        shell_path = Path(git_exe).resolve().parents[1] / 'bin' / 'bash.exe'
        shell = str(shell_path) if shell_path.is_file() else None
    else:
        shell = shutil.which('sh')
    if not shell:
        pytest.skip('requires POSIX shell or Git Bash')

    def git(*args):
        result = run([git_exe, *args], tmp_path)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    git('init', '-q')
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    (scripts / 'ci_pytest_marker.txt').write_bytes(
        (ROOT / 'scripts/ci_pytest_marker.txt').read_bytes()
    )
    git('add', '.')
    git(
        '-c', f'core.hooksPath={tmp_path / "no-hooks"}',
        '-c', 'user.name=Hook Test', '-c', 'user.email=hook@example.invalid',
        'commit', '-qm', 'test',
    )
    sha = git('rev-parse', 'HEAD')
    interpreter = tmp_path / 'configured interpreter.sh'
    interpreter.write_bytes(
        b'#!/bin/sh\n'
        b'printf "<%s>" "$@" >> "$PREPUSH_TEST_LOG"\n'
        b'printf "\\n" >> "$PREPUSH_TEST_LOG"\n'
        b'case "$1" in\n'
        b'  --version) echo "Python hook-test"; exit 0 ;;\n'
        b'  -m) exit "${PREPUSH_TEST_STATUS:-0}" ;;\n'
        b'esac\n'
        b'exit 99\n'
    )
    interpreter.chmod(0o755)
    log = tmp_path / 'interpreter.log'

    def push(config):
        env = clean_env()
        env['PREPUSH_TEST_LOG'] = log.as_posix()
        env.update(config)
        return run(
            [shell, HOOK.as_posix(), 'github', 'unused'], tmp_path,
            input=f'refs/heads/master {sha} refs/heads/master {sha}\n', env=env,
        )

    return push, interpreter.as_posix(), log


@pytest.mark.parametrize(
    'selected', ['OSKH_MERGE_PYTHON', 'VANNA312_PYTHON', 'VANNA311_PYTHON']
)
def test_configured_interpreter_priority_and_arguments(protected_push, selected):
    push, interpreter, log = protected_push
    keys = ['OSKH_MERGE_PYTHON', 'VANNA312_PYTHON', 'VANNA311_PYTHON']
    config = {key: interpreter + '.missing' for key in keys[keys.index(selected):]}
    config[selected] = interpreter
    config['PYTHON'] = interpreter + '.obsolete'
    config['PREPUSH_PYTEST_ARGS'] = 'tests/test_example.py -k smoke'
    result = push(config)
    assert result.returncode == 0, result.stderr
    assert log.read_text(encoding='utf-8').splitlines() == [
        '<--version>',
        '<-m><pytest><-p><no:cacheprovider><-q><-x>'
        '<-m><not production and not benchmark><tests/test_example.py><-k><smoke>',
    ]


def test_invalid_configured_interpreter_fails_without_fallback(protected_push):
    push, interpreter, log = protected_push
    result = push({
        'OSKH_MERGE_PYTHON': interpreter + '.missing',
        'VANNA312_PYTHON': interpreter,
        'PYTHON': interpreter,
    })
    assert result.returncode != 0
    assert 'configured Python cannot run' in result.stderr
    assert not log.exists()


def test_selected_interpreter_pytest_failure_blocks_push(protected_push):
    push, interpreter, log = protected_push
    result = push({'OSKH_MERGE_PYTHON': interpreter, 'PREPUSH_TEST_STATUS': '23'})
    assert result.returncode != 0
    assert 'pytest failed' in result.stderr
    assert len(log.read_text(encoding='utf-8').splitlines()) == 2


@pytest.mark.skipif(
    os.name == 'nt' or not shutil.which('sh') or not shutil.which('git'),
    reason='requires POSIX sh and git',
)
def test_marker_checks(tmp_path):
    def git(*args):
        result = run(['git', *args], tmp_path)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def commit():
        git('add', '.')
        git('-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'test')
        return git('rev-parse', 'HEAD')

    def push(sha, skip=False):
        env = clean_env()
        if skip:
            env['SKIP_PREPUSH'] = '1'
        return run(
            ['sh', str(HOOK), 'origin', 'url'],
            tmp_path,
            input=f'refs/heads/feat {sha} refs/heads/feat {base}\n',
            env=env,
        )

    git('init')
    git('config', 'user.name', 'Hook Test')
    git('config', 'user.email', 'hook@example.invalid')
    (tmp_path / 'clean.txt').write_text('clean\n', encoding='utf-8')
    base = commit()
    bad_file = tmp_path / 'conflict with spaces.txt'
    bad_file.write_text('<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> b\n', encoding='utf-8')
    bad = commit()
    # The committed blob must be checked even when the worktree is clean.
    bad_file.write_text('clean worktree\n', encoding='utf-8')
    result = push(bad)
    assert result.returncode != 0
    assert 'conflict with spaces.txt:1:' in result.stderr
    assert 'conflict with spaces.txt:3:' in result.stderr
    assert 'conflict with spaces.txt:5:' in result.stderr
    assert push(bad, skip=True).returncode == 0
    clean = commit()
    assert push(clean).returncode == 0
    (tmp_path / 'heading.md').write_text('Heading\n=======\n', encoding='utf-8')
    # Binary blobs containing marker-like lines must also pass.
    (tmp_path / 'binary.bin').write_bytes(b'\0\n<<<<<<< HEAD\n=======\n>>>>>>> b\n')
    assert push(commit()).returncode == 0
