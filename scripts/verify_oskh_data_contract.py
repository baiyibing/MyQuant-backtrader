#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fail CI / preflight if ``oskh_data`` violates package boundary contracts,
or if live_trading / trade_decision modules misuse adjust_type in daily bar calls.

Checks performed:
  1. oskh_data does not import from backtest/ (no reverse dependency)
  2. oskh_data does not import from oskh_core / oskh_db (orthogonal)
  3. oskh_data does not import backtrader / xtquant at module level
     (delayed imports only)
  4. data_audit.db direct sqlite3 access is whitelisted in oskh_data/audit.py
  5. live_trading/ and trade_decision/ hot-path calls to stock_daily_bars /
     stock_daily_bars_cfg_only / read_stock must use adjust_type="none"
     (whitelist: live_trading_ma_indicator_provider.py)

Usage (repo root)::

  D:\\anaconda3\\envs\\vanna311\\python.exe scripts/verify_oskh_data_contract.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple

_REPO = Path(__file__).resolve().parent.parent
_OSKH_DATA = _REPO / "oskh_data"

# Module-level imports forbidden in oskh_data
_FORBIDDEN_MODULE_IMPORTS: Tuple[Tuple[str, str], ...] = (
    ("backtest", "oskh_data must not depend on backtest/"),
    ("oskh_core", "oskh_data must not depend on oskh_core (orthogonal)"),
    ("oskh_db", "oskh_data must not depend on oskh_db (orthogonal)"),
    ("backtrader", "backtrader must not be imported at module level (use delayed import)"),
    ("xtquant", "xtquant must not be imported at module level (use delayed import)"),
)

# Transitional exceptions (to be removed after Phase 3 cleanup)
_TRANSITIONAL_BACKTEST_IMPORTS: Tuple[str, ...] = (
    "backtest.qmt_utils_new",  # StockCodeProcessor — pending extraction to oskh_data
    "backtest.qmt_utils_adv",  # tool functions (get_stock_data_from_cache etc.) — pending move to common/infra
)

# Whitelist: modules allowed to use direct sqlite3 (independent audit db)
_SQLITE_WHITELIST = {
    "oskh_data/audit.py": "data_audit.db is an independent operations audit database, "
                          "isolated from the oskh_db.DatabaseGateway five-db routing. "
                          "See plan-refactor-backtest-data-to-oskh-data-2026-05-16.md §10.1 E.",
}

# Modules allowed to use adjust_type != "none" (explicitly documented reason required)
_ADJUST_TYPE_WHITELIST: Tuple[str, ...] = (
    "live_trading/live_trading_ma_indicator_provider.py",
)

# Hot-path directories to scan for adjust_type misuse
_HOT_PATH_DIRS: Tuple[Path, ...] = (
    _REPO / "live_trading",
    _REPO / "trade_decision",
)

# Method/function names and their adjust keyword parameter names
_ADJUST_KEYWORD_TARGETS: Tuple[Tuple[str, str], ...] = (
    ("stock_daily_bars", "adjust"),
    ("stock_daily_bars_cfg_only", "adjust"),
    ("read_stock", "adjust_type"),
)

_RED = "\033[91m"
_GREEN = "\033[92m"
_RESET = "\033[0m"


def _collect_py_files(root: Path) -> List[Path]:
    return sorted(f for f in root.rglob("*.py") if f.name != "__init__.py")


# ------------------------------------------------------------------
# Check 1-3: oskh_data module-level imports
# ------------------------------------------------------------------

def _check_module_imports(path: Path) -> List[str]:
    errors: List[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        errors.append(f"{path}: syntax error: {e}")
        return errors

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden, reason in _FORBIDDEN_MODULE_IMPORTS:
                    if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                        errors.append(f"{path}: module-level 'import {alias.name}' — {reason}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for forbidden, reason in _FORBIDDEN_MODULE_IMPORTS:
                    if node.module == forbidden or node.module.startswith(forbidden + "."):
                        if node.module in _TRANSITIONAL_BACKTEST_IMPORTS:
                            continue
                        errors.append(f"{path}: module-level 'from {node.module} import ...' — {reason}")

    return errors


# ------------------------------------------------------------------
# Check 4: sqlite3 whitelist
# ------------------------------------------------------------------

def _check_sqlite_whitelist(path: Path) -> List[str]:
    errors: List[str] = []
    relative = str(path.relative_to(_REPO)).replace("\\", "/")
    if relative in _SQLITE_WHITELIST:
        return errors

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlite3":
                    errors.append(
                        f"{path}: direct 'import sqlite3' not allowed. "
                        f"Whitelisted files: {list(_SQLITE_WHITELIST)}"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module == "sqlite3":
                errors.append(
                    f"{path}: direct 'from sqlite3 import ...' not allowed. "
                    f"Whitelisted files: {list(_SQLITE_WHITELIST)}"
                )

    return errors


# ------------------------------------------------------------------
# Check 5: adjust_type guard (static scan)
# ------------------------------------------------------------------

def _check_adjust_type_hot_path() -> List[str]:
    """Scan live_trading/ and trade_decision/ for calls to stock_daily_bars /
    read_stock with adjust_type != 'none'.
    """
    errors: List[str] = []
    for hot_dir in _HOT_PATH_DIRS:
        if not hot_dir.is_dir():
            continue
        for py_file in _collect_py_files(hot_dir):
            relative = str(py_file.relative_to(_REPO)).replace("\\", "/")
            if relative in _ADJUST_TYPE_WHITELIST:
                continue

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                # match func name: stock_daily_bars(...), stock_daily_bars_cfg_only(...),
                # or .read_stock(...)
                func_name = _resolve_call_name(node)
                if not func_name:
                    continue

                for target_name, kw_name in _ADJUST_KEYWORD_TARGETS:
                    if func_name != target_name:
                        continue
                    # check keyword arguments
                    for kw in node.keywords:
                        if kw.arg == kw_name:
                            val = _resolve_constant(kw.value)
                            if val is not None and val != "none":
                                errors.append(
                                    f"{relative}: {func_name}(..., {kw_name}='{val}') — "
                                    f"adjust_type must be 'none' in hot-path modules. "
                                    f"Whitelist: {list(_ADJUST_TYPE_WHITELIST)}"
                                )
    return errors


def _resolve_call_name(node: ast.Call) -> str | None:
    """Extract function/method name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _resolve_constant(node: ast.expr) -> str | None:
    """Resolve ast.Constant string value, or None if not a simple string literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> int:
    errors: List[str] = []

    # Checks 1-4: oskh_data package boundaries
    if not _OSKH_DATA.is_dir():
        print(f"{_RED}oskh_data/ directory not found{_RESET}")
        return 1

    for py_file in _collect_py_files(_OSKH_DATA):
        errors.extend(_check_module_imports(py_file))
        errors.extend(_check_sqlite_whitelist(py_file))

    # Check 5: adjust_type hot-path guard
    errors.extend(_check_adjust_type_hot_path())

    if errors:
        print(f"{_RED}oskh_data contract violations ({len(errors)}):{_RESET}")
        for e in errors:
            print(f"  {_RED}✗{_RESET} {e}")
        return 1

    print(f"{_GREEN}oskh_data contract: OK{_RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
