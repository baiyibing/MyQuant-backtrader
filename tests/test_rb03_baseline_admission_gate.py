"""Fast, data-free baseline admission diagnostics."""
import json

import pytest

from scripts.gates import verify_baseline_admission as gate


def test_happy_path(capsys):
    assert gate.main() == 0
    output = capsys.readouterr().out
    assert "OK" in output
    assert "triple-anchor" in output
    assert "overlay schema" in output


@pytest.mark.parametrize("key", gate.REQUIRED_KEYS)
def test_missing_overlay_key(monkeypatch, tmp_path, capsys, key):
    manifest = json.loads(gate.baseline.S8_GOLDEN.read_text(encoding="utf-8"))
    del manifest[key]
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(gate.baseline, "S8_GOLDEN", path)
    assert gate.main() == 1
    output = capsys.readouterr().out
    assert str(path) in output
    assert key in output


@pytest.mark.parametrize("version", [None, 306, "3.0.5"])
def test_pandas_anchor_failure(monkeypatch, tmp_path, capsys, version):
    manifest = json.loads(gate.baseline.S8_GOLDEN.read_text(encoding="utf-8"))
    manifest["captured_environment"]["pandas"] = version
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(gate.baseline, "S8_GOLDEN", path)
    assert gate.main() == 1
    output = capsys.readouterr().out
    assert "captured_environment.pandas" in output
    assert "independent re-anchor ticket" in output
