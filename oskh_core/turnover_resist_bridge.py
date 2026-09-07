# -*- coding: utf-8 -*-
"""Turnover-resist Rust 桥接：PyO3 FFI 主通道，CLI 子进程 fallback。

plan-main v22 Phase A1 交付项：替代 CLI subprocess.run 调用，
消除 39ms 子进程启动开销和临时 CSV 文件读写。

用法::

    from oskh_core.turnover_resist_bridge import compute_turnover_resist

    results = compute_turnover_resist(
        date="20260606",
        data_dir="E:/data/parquet",
    )
    # returns list[dict] with keys: stock_code, stock_name, date, close,
    #   cyqk_T, cyqk_T_1, profit_chip_diff, turnover, turnover_resistance,
    #   turnover_free, turnover_resistance_free, circulating_capital,
    #   freeFloatCapital, bb_upper, bb_middle, bb_lower, bb_position, bb_width
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.infra.quant_logger import get_logger

_log = get_logger("turnover_resist_bridge")

# ---------------------------------------------------------------------------
# PyO3 FFI (primary path)
# ---------------------------------------------------------------------------

_FFI_MODULE: Any = None
_FFI_LOAD_ERROR: Optional[str] = None


def _load_ffi_module() -> Any:
    """Lazy-load the PyO3 extension module 'turnover_resist'.

    Returns the module on success, None if not installed (caller should
    fall back to CLI subprocess).
    """
    global _FFI_MODULE, _FFI_LOAD_ERROR
    if _FFI_MODULE is not None:
        return _FFI_MODULE
    if _FFI_LOAD_ERROR:
        return None
    try:
        import turnover_resist as mod  # type: ignore[import-not-found]

        _FFI_MODULE = mod
        _log.info("turnover_resist PyO3 FFI loaded")
        return mod
    except ImportError as exc:
        _FFI_LOAD_ERROR = str(exc)
        _log.warning(
            "turnover_resist PyO3 not installed; falling back to CLI subprocess (%s)",
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_turnover_resist(
    date: str,
    *,
    data_dir: str = "",
    window: int = 1000,
    step: float = 0.01,
    sort_by: str = "circulating",
    free_float_policy: str = "warn-zero",
    target_date_policy: str = "strict",
    bb_ddof: int = 1,
    max_grid_points: int = 250_000,
    prefer_ffi: bool = True,
) -> List[Dict[str, Any]]:
    """Compute turnover resistance for all stocks on *date*.

    Parameters match the Rust CLI arguments (see ``turnover-resist --help``).
    Returns a list of dicts (one per stock), sorted by |turnover_resistance|
    descending.

    *prefer_ffi* (default True): try PyO3 FFI first, fall back to CLI
    subprocess if the extension module is not installed.
    """
    if not data_dir:
        data_dir = _default_data_dir()

    if prefer_ffi:
        results = _ffi_compute(
            date=date,
            data_dir=data_dir,
            window=window,
            step=step,
            sort_by=sort_by,
            free_float_policy=free_float_policy,
            target_date_policy=target_date_policy,
            bb_ddof=bb_ddof,
            max_grid_points=max_grid_points,
        )
        if results is not None:
            return results

    return _cli_compute(
        date=date,
        data_dir=data_dir,
        window=window,
        step=step,
        sort_by=sort_by,
        free_float_policy=free_float_policy,
        target_date_policy=target_date_policy,
        bb_ddof=bb_ddof,
        max_grid_points=max_grid_points,
    )


# ---------------------------------------------------------------------------
# Internal: PyO3 FFI path
# ---------------------------------------------------------------------------

def _ffi_compute(**kwargs: Any) -> Optional[List[Dict[str, Any]]]:
    mod = _load_ffi_module()
    if mod is None:
        return None
    try:
        json_str: str = mod.compute_turnover_resist(
            kwargs["date"],
            kwargs["window"],
            kwargs["step"],
            kwargs["data_dir"],
            kwargs["sort_by"],
            kwargs["free_float_policy"],
            kwargs["target_date_policy"],
            kwargs["bb_ddof"],
            kwargs["max_grid_points"],
        )
        results: List[Dict[str, Any]] = json.loads(json_str)
        return results
    except Exception as exc:
        _log.error("PyO3 FFI compute failed: %s; falling back to CLI", exc)
        return None


# ---------------------------------------------------------------------------
# Internal: CLI subprocess fallback
# ---------------------------------------------------------------------------

def _cli_compute(**kwargs: Any) -> List[Dict[str, Any]]:
    date = kwargs["date"]
    data_dir = kwargs["data_dir"]
    output_path = Path(data_dir) / f"_turnover_resist_{date}.csv"
    exe = _find_exe()

    cmd: List[str] = [
        str(exe),
        "--date", date,
        "--data-dir", data_dir,
        "--window", str(kwargs["window"]),
        "--step", str(kwargs["step"]),
        "--sort-by", kwargs["sort_by"],
        "--free-float-policy", kwargs["free_float_policy"],
        "--target-date-policy", kwargs["target_date_policy"],
        "--bb-ddof", str(kwargs["bb_ddof"]),
        "--max-grid-points", str(kwargs["max_grid_points"]),
        "--output", str(output_path),
    ]

    _log.info("Running CLI: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(
            f"turnover-resist CLI failed (exit {proc.returncode}):\n"
            f"  stdout: {proc.stdout}\n  stderr: {proc.stderr}"
        )

    import csv

    results: List[Dict[str, Any]] = []
    with open(output_path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            for key in (
                "close", "cyqk_T", "cyqk_T_1", "profit_chip_diff",
                "turnover", "turnover_resistance", "turnover_free",
                "turnover_resistance_free", "circulating_capital",
                "freeFloatCapital",
                "bb_upper", "bb_middle", "bb_lower", "bb_position", "bb_width",
            ):
                try:
                    row[key] = float(row[key])
                except (KeyError, ValueError):
                    continue  # field missing or non-numeric; skip conversion
            results.append(row)
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_exe() -> Path:
    """Locate the turnover-resist.exe binary.

    Checks (in order):
      1. TURNOVER_RESIST_EXE env var
      2. E:/rust-targets/release/turnover-resist.exe
      3. E:/rust-targets/release-fast/turnover-resist.exe
    """
    import os

    env = os.getenv("TURNOVER_RESIST_EXE")
    if env:
        p = Path(env)
        if p.is_file():
            return p
    candidates = [
        Path("E:/rust-targets/release/turnover-resist.exe"),
        Path("E:/rust-targets/release-fast/turnover-resist.exe"),
    ]
    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError(
        "turnover-resist.exe not found. Set TURNOVER_RESIST_EXE env var "
        "or build with: cd turnover-resist && cargo build --release"
    )


def _default_data_dir() -> str:
    import os

    return os.getenv("TURNOVER_RESIST_DATA_DIR", "E:/data/parquet")


# ---------------------------------------------------------------------------
# Module-level availability check
# ---------------------------------------------------------------------------

def is_ffi_available() -> bool:
    """Return True if the PyO3 extension module can be loaded."""
    return _load_ffi_module() is not None


def bridge_mode() -> str:
    """Return the active bridge mode: 'pyo3_ffi' or 'cli_fallback'."""
    return "pyo3_ffi" if is_ffi_available() else "cli_fallback"
