"""Keep lint scoped to bt_contract plus the RB-10 leaf, after data-free gates."""

from pathlib import Path


def test_ci_ruff_targets_bt_contract_only():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/python-tests.yml").read_text(encoding="utf-8")
    lint_commands = [line.strip() for line in workflow.splitlines() if "-m ruff check" in line]
    assert lint_commands == [
        "python -m ruff check bt_contract backtest/research/strategy_hooks_types.py"
    ]
    assert "ruff check backtest" not in workflow
    assert "pip install ruff" in workflow
    assert workflow.index("verify_tr_bridge_import_ssot.py") < workflow.index(
        "pip install -r requirements.txt"
    ) < workflow.index("pip install ruff") < workflow.index("ruff check bt_contract")
