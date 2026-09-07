#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fail CI / preflight if ``oskh_data`` violates package boundary contracts,
or if live_trading / trade_decision modules misuse adjust_type in daily bar calls.

Checks performed:
  1. oskh_data does not import from backtest/ (no reverse dependency)
  2. oskh_data does not import from oskh_core / oskh_db (orthogonal)
  3. oskh_data does not import backtrader at module level, and must not
     import xtquant anywhere (this fork has no QMT download)
  3b. backtest/ must not import download modules or xtquant
  4. data_audit.db direct sqlite3 access is whitelisted in oskh_data/audit.py
  5. live_trading/ and trade_decision/ hot-path calls to stock_daily_bars /
     stock_daily_bars_cfg_only / read_stock must use adjust_type="none"
     (whitelist: live_trading_ma_indicator_provider.py)

Usage (repo root)::

  python scripts/gates/verify_oskh_data_contract.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2] if _HERE.parent.name == "gates" else _HERE.parents[1]
_OSKH_DATA = _REPO / "oskh_data"

# Forbidden anywhere in oskh_data (including nested / lazy imports)
_FORBIDDEN_ANYWHERE_IMPORTS: Tuple[Tuple[str, str], ...] = (
    ("backtest", "oskh_data must not depend on backtest/"),
    ("oskh_core", "oskh_data must not depend on oskh_core (orthogonal)"),
    ("oskh_db", "oskh_data must not depend on oskh_db (orthogonal)"),
    ("xtquant", "this fork has no QMT download; xtquant is forbidden"),
)

# Forbidden only at module top-level (delayed import inside functions OK)
_FORBIDDEN_MODULE_LEVEL_IMPORTS: Tuple[Tuple[str, str], ...] = (
    ("backtrader", "backtrader must not be imported at module level (use delayed import)"),
    ("xtquant", "xtquant must not be imported at module level (use delayed import)"),
)

# Back-compat alias for older call sites / docs
_FORBIDDEN_MODULE_IMPORTS = _FORBIDDEN_ANYWHERE_IMPORTS + _FORBIDDEN_MODULE_LEVEL_IMPORTS

_BACKTEST_DIR = _REPO / "backtest"

# This fork keeps thin backtest/ shims that re-export oskh_data CLIs.
_BACKTEST_SHIM_WHITELIST: set[str] = set()

# backtest/ must read local hive only — download/update lives in oskh_data + scripts/
_FORBIDDEN_BACKTEST_IMPORT_MODULES: Tuple[str, ...] = (
    "xtquant",
    "oskh_data.backfill",
    "oskh_data.float_shares",
    "oskh_data.float_shares_history",
    "oskh_data.adj_factor",
    "oskh_data.integrity",
    "oskh_data.download_ops",
    "oskh_data.minute_backfill",
    "oskh_data.etf_backfill",
    "oskh_data.downloader",
    "oskh_data.qmt_xtdata",
    "oskh_data.download_transport",
)

_FORBIDDEN_BACKTEST_CALL_NAMES: Tuple[str, ...] = (
    "DataDownloader",
    "download_history_data2",
    "download_market_data",
    "get_miniqmt_data",
    "download_data",
)

# Whitelist: modules allowed to use direct sqlite3 (independent audit db)
_SQLITE_WHITELIST = {
    "oskh_data/audit.py": "data_audit.db is an independent operations audit database, "
                          "isolated from the oskh_db.DatabaseGateway five-db routing. "
                          "See plan-refactor-backtest-data-to-oskh-data-2026-05-16.md §10.1 E.",
}

# Modules allowed to use adjust_type != "none" (explicitly documented reason required)
_ADJUST_TYPE_WHITELIST: Tuple[str, ...] = (
    "live_trading/indicators/ma_provider.py",
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

    # Layering: catch nested/lazy imports of oskh_core / oskh_db / backtest
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden, reason in _FORBIDDEN_ANYWHERE_IMPORTS:
                    if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                        errors.append(f"{path}: import '{alias.name}' — {reason}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for forbidden, reason in _FORBIDDEN_ANYWHERE_IMPORTS:
                    if node.module == forbidden or node.module.startswith(forbidden + "."):
                        errors.append(f"{path}: from '{node.module}' import ... — {reason}")

    # Heavy deps: only forbid at module top-level (delayed import OK)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden, reason in _FORBIDDEN_MODULE_LEVEL_IMPORTS:
                    if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                        errors.append(f"{path}: module-level 'import {alias.name}' — {reason}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for forbidden, reason in _FORBIDDEN_MODULE_LEVEL_IMPORTS:
                    if node.module == forbidden or node.module.startswith(forbidden + "."):
                        errors.append(f"{path}: module-level 'from {node.module} import ...' — {reason}")

    return errors


def _check_backtest_no_download_ops(path: Path) -> List[str]:
    """backtest/ is read-only for market data; no download/update imports or calls."""
    relative = str(path.relative_to(_REPO)).replace("\\", "/")
    if relative in _BACKTEST_SHIM_WHITELIST:
        return []
    errors: List[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        errors.append(f"{path}: syntax error: {e}")
        return errors

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "xtquant" or alias.name.startswith("xtquant."):
                    errors.append(
                        f"{path}: backtest must not import xtquant "
                        f"(market download lives in the original repo)"
                    )
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            for forbidden in _FORBIDDEN_BACKTEST_IMPORT_MODULES:
                if mod == forbidden or mod.startswith(forbidden + "."):
                    errors.append(
                        f"{path}: backtest must not import download module '{mod}' "
                        f"(market download lives in the original repo)"
                    )
            if mod == "oskh_data" and node.names:
                for alias in node.names:
                    if alias.name in {"DataDownloader", "PeriodDataManager", "StockDataManager"}:
                        errors.append(
                            f"{path}: backtest must not import oskh_data.{alias.name} "
                            f"(download SSOT is outside backtest)"
                        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _resolve_call_name(node)
            if name in _FORBIDDEN_BACKTEST_CALL_NAMES:
                errors.append(
                    f"{path}: backtest must not call {name}() "
                    f"(download/update → scripts/ or oskh_data CLI)"
                )
        if isinstance(node, ast.Name) and node.id == "DataDownloader":
            errors.append(
                f"{path}: backtest must not reference DataDownloader "
                f"(download/update → scripts/ or oskh_data CLI)"
            )

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

    if _BACKTEST_DIR.is_dir():
        for py_file in sorted(_BACKTEST_DIR.rglob("*.py")):
            errors.extend(_check_backtest_no_download_ops(py_file))

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
