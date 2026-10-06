"""Data-free checks for the RB-07 shared pytest marker and required job."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shared_marker_content():
    content = (ROOT / "scripts/ci_pytest_marker.txt").read_text(encoding="utf-8")
    assert content.strip() == "not production and not benchmark"
    assert content.splitlines() == ["not production and not benchmark"]


def test_workflow_uses_shared_marker_and_required_job():
    workflow = (ROOT / ".github/workflows/python-tests.yml").read_text(encoding="utf-8")
    assert "ci_pytest_marker.txt" in workflow
    assert "  pytest-and-gates:" in workflow


def test_pre_push_uses_shared_marker():
    hook = (ROOT / ".githooks/pre-push").read_text(encoding="utf-8")
    assert "ci_pytest_marker.txt" in hook


def test_marker_crlf_raw_bytes_normalize_to_canonical():
    """Simulate a Windows CRLF checkout of the marker file (raw bytes)."""
    raw = b"not production and not benchmark\r\n"
    assert b"\r" in raw
    normalized = raw.replace(b"\r", b"").decode("utf-8").strip()
    assert normalized == "not production and not benchmark"


def test_pre_push_strips_cr_when_reading_marker():
    hook = (ROOT / ".githooks/pre-push").read_text(encoding="utf-8")
    assert "tr -d '\\r'" in hook or 'tr -d "\\r"' in hook
