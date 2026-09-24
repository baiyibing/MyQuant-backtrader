"""README must describe the registered CSV book and retired Cerebro accurately."""

from pathlib import Path


def test_readme_version11_claim():
    text = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    assert "另开 version11" not in text
    assert "version11" in text
    assert "--strategy version11" in text
    assert "Cerebro" in text
