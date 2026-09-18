"""The plan's explicit simulate boundary, including exactly one dependency layer."""

import ast
from importlib.util import resolve_name
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
# Names and order must match plan §5-C byte for byte. This is not an rglob.
SIMULATE_HOT_PATH = (
    "csv_daily_backtest",
    "csv_minute_backtest",
    "csv_minute_backtest_v7",
    "csv_ledger",
    "csv_simulate_loop",
    "csv_common",
    "csv_strategy_books",
    "ashare_session",
    "ashare_bars",
    "ashare_fees",
    "unified_exit_modeb",
    "csv_daily_loader",
    "csv_pool",
    "market_layer",
    "exdiv_map",
)


def forbidden_imports(source, package="backtest.research"):
    violations = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = resolve_name("." * node.level + module, package)
            names = [module] + [f"{module}.{alias.name}" for alias in node.names]
        else:
            continue
        for name in names:
            if (name == "qlib" or name.startswith("qlib.")
                    or "trade_fee_policy" in name.split(".")
                    or name == "backtest.lebs" or name.startswith("backtest.lebs.")):
                violations.append((node.lineno, name))
    return violations


def test_hot_path_list_matches_plan_bytes():
    plan = (ROOT / "docs/backtest/plan-ashare-engine-refactor-2026-09-18.md").read_text(encoding="utf-8")
    row = next(line for line in plan.splitlines() if line.startswith("| **C · 围栏 + 入口文档**"))
    declared = row.split("**热路径=枚举清单**：", 1)[1].split("（禁 rglob", 1)[0]
    names = re.findall(r"`([^`]+)`", declared)
    assert "\n".join(SIMULATE_HOT_PATH).encode("utf-8") == "\n".join(names).encode("utf-8")


@pytest.mark.parametrize("name", SIMULATE_HOT_PATH)
def test_simulate_import_fence(name):
    path = ROOT / "backtest/research" / f"{name}.py"
    assert forbidden_imports(path.read_text(encoding="utf-8")) == [], str(path)


@pytest.mark.parametrize("source", [
    "import qlib as q",
    "from qlib.backtest import exchange",
    "import trade_decision.trade_fee_policy as fees",
    "from trade_decision import trade_fee_policy as fees",
    "import backtest.lebs.engine",
    "from backtest import lebs",
    "from .. import lebs",
    "from ..lebs import engine",
    "if False:\n    from trade_fee_policy import commission",
    "def deferred():\n    import qlib",
])
def test_fence_rejects_aliases_relative_and_local_imports(source):
    assert forbidden_imports(source)


def test_bin_readers_and_research_fees_are_allowed():
    assert forbidden_imports("""
from backtest.research.qlib_bin_1min import load_qlib_bin_1min_bars
from .ashare_fees import DEFAULT_SCHEDULE
from qlib_cost import chip
""") == []
