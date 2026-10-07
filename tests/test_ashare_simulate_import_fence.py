"""The plan's explicit simulate boundary, including exactly one dependency layer.

Human GO P2=B permits fill-clock imports only in the ledger write path for
trade labeling, not scheduling. Scanners retain the ban; the fixed list stays.
"""

import ast
from importlib.util import resolve_name
from pathlib import Path
import re

import pytest

from backtest.research.research_family_tags import (
    ISOLATED_RESEARCH_FAMILIES,
    isolated_import_prefixes,
)


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

# P2=B annotation only. Do not grant the minute engine/scanners this exception.
FILL_CLOCK_WRITE_PATHS = frozenset({"csv_ledger"})


def forbidden_imports(source, package="backtest.research", *, module_name=""):
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
                    or name == "backtest.lebs" or name.startswith("backtest.lebs.")
                    or ("ashare_fill_clock" in name.split(".")
                        and module_name not in FILL_CLOCK_WRITE_PATHS)
                    or any(name == prefix or name.startswith(prefix + ".")
                           or name.startswith(prefix + "_")
                           for prefix in isolated_import_prefixes())):
                violations.append((node.lineno, name))
    return violations


def test_hot_path_list_matches_plan_bytes():
    plan = (ROOT / "docs/backtest/plan-ashare-engine-refactor-2026-09-18.md").read_text(encoding="utf-8")
    row = next(line for line in plan.splitlines() if line.startswith("| **C · 围栏 + 入口文档**"))
    declared = row.split("**热路径=枚举清单**：", 1)[1].split("（禁 rglob", 1)[0]
    names = re.findall(r"`([^`]+)`", declared)
    assert "\n".join(SIMULATE_HOT_PATH).encode("utf-8") == "\n".join(names).encode("utf-8")


def test_hot_path_excludes_isolated_families():
    for name in SIMULATE_HOT_PATH:
        assert not any(
            name == prefix or name.startswith(prefix + ".")
            or name.startswith(prefix + "_")
            for prefix in isolated_import_prefixes()
        ), name


def test_isolated_family_inventory_exists():
    for modules in ISOLATED_RESEARCH_FAMILIES.values():
        for name in modules:
            path = ROOT / "backtest/research" / name.replace(".", "/")
            assert path.with_suffix(".py").is_file() or (path / "__init__.py").is_file(), name


@pytest.mark.parametrize("prefix", isolated_import_prefixes())
def test_fence_rejects_isolated_family_imports(prefix):
    for source in (
        f"import {prefix} as family",
        f"from {prefix} import runner as run",
        f"def deferred():\n    import {prefix}.runner",
    ):
        assert forbidden_imports(source, module_name="csv_ledger")
    parent, _, leaf = prefix.rpartition(".")
    if parent:
        assert forbidden_imports(f"from {parent} import {leaf} as family")
    if prefix.startswith("backtest.research."):
        relative = prefix.removeprefix("backtest.research.")
        assert forbidden_imports(f"from .{relative} import runner")
        parent, _, leaf = relative.rpartition(".")
        assert forbidden_imports(f"from .{parent} import {leaf}")


@pytest.mark.parametrize("name", SIMULATE_HOT_PATH)
def test_simulate_import_fence(name):
    path = ROOT / "backtest/research" / f"{name}.py"
    assert forbidden_imports(path.read_text(encoding="utf-8"), module_name=name) == [], str(path)


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


def test_fence_rejects_fill_clock_bare_and_qualified_imports():
    assert forbidden_imports("import ashare_fill_clock")
    assert forbidden_imports("from ashare_fill_clock import SessionPhase")
    assert forbidden_imports("import backtest.research.ashare_fill_clock")
    assert forbidden_imports(
        "from backtest.research.ashare_fill_clock import FillPriceRule"
    )
    assert forbidden_imports("from backtest.research import ashare_fill_clock")
    assert forbidden_imports("from .ashare_fill_clock import session_phase")
    assert forbidden_imports("from . import ashare_fill_clock")


@pytest.mark.parametrize("name", SIMULATE_HOT_PATH)
def test_fill_clock_exception_is_only_for_ledger_labels(name):
    assert FILL_CLOCK_WRITE_PATHS == {"csv_ledger"}
    for source in (
        "import ashare_fill_clock as clock",
        "from backtest.research.ashare_fill_clock import session_phase as phase",
        "from . import ashare_fill_clock",
        "from .ashare_fill_clock import SessionPhase",
    ):
        assert bool(forbidden_imports(source, module_name=name)) == (name != "csv_ledger")
    # No exception for external execution/fee engines, even in the writer.
    assert forbidden_imports("import qlib", module_name=name)
    assert forbidden_imports("from trade_decision import trade_fee_policy", module_name=name)
    assert forbidden_imports("from backtest import lebs", module_name=name)


def test_bin_readers_and_research_fees_are_allowed():
    assert forbidden_imports("""
from backtest.research.qlib_bin_1min import load_qlib_bin_1min_bars
from .ashare_fees import DEFAULT_SCHEDULE
from qlib_cost import chip
""") == []
