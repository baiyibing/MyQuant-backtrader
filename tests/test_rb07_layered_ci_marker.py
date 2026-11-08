"""Data-free checks for the RB-07 shared pytest marker and required job."""
from pathlib import Path
import subprocess
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
MARKER_PATH = ROOT / "scripts/ci_pytest_marker.txt"
CANONICAL = "not production and not benchmark"


def test_shared_marker_content():
    content = MARKER_PATH.read_text(encoding="utf-8")
    assert content.strip() == CANONICAL
    assert content.splitlines() == [CANONICAL]


def test_workflow_uses_shared_marker_and_required_job():
    workflow = (ROOT / ".github/workflows/python-tests.yml").read_text(encoding="utf-8")
    assert "ci_pytest_marker.txt" in workflow
    assert "  pytest-and-gates:" in workflow
    assert "tr -d '\\r'" in workflow


def test_pre_push_uses_shared_marker():
    hook = (ROOT / ".githooks/pre-push").read_text(encoding="utf-8")
    assert "ci_pytest_marker.txt" in hook
    assert "tr -d '\\r'" in hook


def test_marker_crlf_raw_bytes_via_tr_pipeline(tmp_path):
    """Raw CRLF bytes through the same tr|sed pipeline used by hook/CI."""
    raw = (CANONICAL + "\r\n").encode("ascii")
    assert b"\r" in raw
    sample = tmp_path / "ci_pytest_marker.txt"
    sample.write_bytes(raw)
    bash = shutil.which("bash")
    if bash is None and sys.platform == "win32":
        git = shutil.which("git")
        if git:
            candidate = Path(git).resolve().parents[1] / "bin" / "bash.exe"
            if candidate.is_file():
                bash = str(candidate)
    assert bash is not None, "Bash is required to exercise the actual CI/hook pipeline"
    out = subprocess.check_output(
        [bash, "-lc", "tr -d '\\r' < \"$1\" | sed 's/[[:space:]]*$//'", "bash", sample.as_posix()],
        text=True,
    )
    assert out.strip("\n") == CANONICAL and "\r" not in out


def test_pre_push_and_workflow_share_cr_strip_pipeline():
    hook = (ROOT / ".githooks/pre-push").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/python-tests.yml").read_text(encoding="utf-8")
    needle = "tr -d '\\r'"
    assert needle in hook and needle in workflow
