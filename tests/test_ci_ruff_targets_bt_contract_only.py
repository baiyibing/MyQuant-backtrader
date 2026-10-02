"""Keep the lint gate scoped to the new contract and after data-free gates."""

from pathlib import Path


def test_ci_ruff_targets_bt_contract_only():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/python-tests.yml").read_text(encoding="utf-8")
    assert "ruff check bt_contract" in workflow
    assert "ruff check backtest" not in workflow
    assert "pip install ruff" in workflow
    assert workflow.index("verify_tr_bridge_import_ssot.py") < workflow.index(
        "pip install -r requirements.txt"
    ) < workflow.index("pip install ruff") < workflow.index("ruff check bt_contract")
