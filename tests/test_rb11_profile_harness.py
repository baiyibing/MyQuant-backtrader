"""Fast synthetic RB-11 harness checks and production import fences."""

import ast
import json
from pathlib import Path

import pytest

from scripts.research import rb11_profile_synthetic as harness


def test_tiny_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("CSV_SCAN_HELD_DAY_BACKEND", "numba")
    result = harness.run_profile(tmp_path, names=2, days=4, minutes=240, top=5)
    assert json.loads((tmp_path / "profile.json").read_text()) == result
    assert set(p.name for p in tmp_path.iterdir()) == {"profile.json", "profile.txt"}
    assert {"scenario", "backend", "stages", "profile_top", "outcome", "scope"} <= result.keys()
    assert result["backend"]["effective"] == "python"
    assert result["outcome"]["buys"] > 0
    assert result["stages"]["scan_profile_cumulative_s"] > 0
    assert result["stages"]["frame_conversion_s"] is None
    assert result["profile_top"]
    assert "cumulative" in (tmp_path / "profile.txt").read_text()
    assert harness.os.environ["CSV_SCAN_HELD_DAY_BACKEND"] == "numba"


def test_required_output_and_sizes(tmp_path):
    with pytest.raises(SystemExit):
        harness.main([])
    with pytest.raises(ValueError):
        harness.run_profile(tmp_path, days=1)
    assert not list(tmp_path.iterdir())


def test_synthetic_source_and_engine_import_fence():
    # Include the reused builder's source in the direct-import fence.
    for source in (Path(harness.__file__),
                   harness.REPO / "scripts/research/bench_minute_simulate_hotpath.py"):
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(word in (node.module or "") for word in ("lake", "oskh_data", "csv_loader"))
            if isinstance(node, ast.Import):
                assert all(not any(word in alias.name for word in ("lake", "oskh_data", "csv_loader"))
                           for alias in node.names)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not node.value.startswith(("/workspace/", "/home/", "/mnt/", "E:/", "F:/", "D:/", "E:\\", "F:\\", "D:\\"))
    for source in (harness.REPO / "backtest").rglob("*.py"):
        assert "rb11_profile_synthetic" not in source.read_text(encoding="utf-8")
