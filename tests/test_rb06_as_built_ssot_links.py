"""Fast, data-free checks for the RB-06 documentation index."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/backtest/rb06-as-built-ssot-index-2026-10-06.md"


def test_as_built_index_repo_links_exist():
    links = re.findall(r"\[[^\]]+\]\(([^\s)]+)\)", INDEX.read_text(encoding="utf-8"))
    assert links, "The as-built index must contain repository pointers"
    for target in links:
        if "://" in target or target.startswith("#"):
            continue
        path = (INDEX.parent / target.split("#", 1)[0]).resolve()
        assert path.is_relative_to(ROOT), target
        assert path.is_file(), target


def test_contributing_cerebro_retirement():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "保留现有 Cerebro 代码用于旧对照" not in text


def test_agents_admission_gate_pointers():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "verify_book_admission" in text
    assert "verify_baseline_admission" in text
