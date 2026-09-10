# -*- coding: utf-8 -*-
"""
Runtime YAML + environment layered configuration.

Bootstrap: set MINIQMT_CONFIG_PATH to one or more YAML files (os.pathsep-separated).
If MINIQMT_CONFIG_PATH is unset or empty and ``config/runtime.local.yaml`` exists under
the ``live-trading-system`` package root (parent of ``common/``), that file is loaded.

Precedence for each key: non-empty environment value > YAML > absent (caller default).

Does not import common.infra.constants to avoid circular imports; bootstrap key is a literal.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import warnings
from pathlib import Path
from typing import Any, Dict, Final, List, Optional

import yaml

# Must match EnvVarKeys.MINIQMT_CONFIG_PATH string in constants.py
_BOOTSTRAP_CONFIG_PATH_ENV: Final[str] = "MINIQMT_CONFIG_PATH"

_loaded: bool = False
_flat: Dict[str, str] = {}
_resolved_paths: List[str] = []
_yaml_fingerprint: str = ""
_slow_load_warned: bool = False
_load_lock = threading.RLock()


def _scalar_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _flatten_yaml_root(loaded: Dict[str, Any]) -> Dict[str, str]:
    """Top-level keys match EnvVarKeys; nested mappings become dotted keys."""

    result: Dict[str, str] = {}

    def walk(obj: Any, prefix: str) -> None:
        if isinstance(obj, dict):
            for kk, vv in obj.items():
                np = f"{prefix}.{kk}" if prefix else str(kk)
                walk(vv, np)
        else:
            result[prefix] = _scalar_to_str(obj)

    for k, v in loaded.items():
        walk(v, str(k))
    return result


def _log_yaml_failure(msg: str) -> None:
    """Log YAML load failures through both warnings and quant_logger if available."""
    warnings.warn(f"[runtime_config] {msg}", RuntimeWarning, stacklevel=3)
    try:
        from common.infra.quant_logger import get_logger

        get_logger("runtime_config", "yaml_load", trace_id="SYSTEM").error(
            f"[runtime_config] {msg}",
            context={"detail": msg},
        )
    except ImportError:
        # quant_logger 不可用时 fail-open：本函数会在 constants 模块体的 env 引导
        # （QMTConstants.* 等 _get_env_int_in_range）期间被调用，此时 import
        # quant_logger 会回撞半初始化的 constants（ImportError: LoggingConstants，
        # 继承主仓相对 MINIQMT_CONFIG_PATH 且文件缺失时实证）。warnings 已发出，
        # 结构化日志不得阻断配置默认值路径（codex R2，2026-09-09）。
        pass


def _load_yaml_file(path: Path) -> Dict[str, str]:
    if not path.is_file():
        _log_yaml_failure(f"config file missing, skipped: {path}")
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        _log_yaml_failure(f"cannot read {path}: {e}")
        return {}
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as e:
        _log_yaml_failure(f"YAML parse error in {path}: {e}")
        return {}
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        _log_yaml_failure(f"root must be a mapping in {path}")
        return {}
    return _flatten_yaml_root(loaded)


def _parse_config_paths(raw: Optional[str]) -> List[Path]:
    if raw is None or not str(raw).strip():
        return []
    parts: List[Path] = []
    for chunk in str(raw).split(os.pathsep):
        c = chunk.strip()
        if c:
            parts.append(Path(c))
    return parts


def _default_local_yaml_path() -> Optional[Path]:
    """``live-trading-system/config/runtime.local.yaml`` if the file exists; else None."""
    root = Path(__file__).resolve().parent.parent.parent
    candidate = root / "config" / "runtime.local.yaml"
    return candidate if candidate.is_file() else None


def _effective_yaml_paths() -> List[Path]:
    """Paths from MINIQMT_CONFIG_PATH, or optional default ``runtime.local.yaml`` when env unset/empty."""
    raw = os.environ.get(_BOOTSTRAP_CONFIG_PATH_ENV)
    paths = _parse_config_paths(raw)
    if paths:
        return paths
    default = _default_local_yaml_path()
    return [default] if default is not None else []


def _compute_yaml_fingerprint(paths: List[Path], merged: Dict[str, str]) -> str:
    stat_bits: List[str] = []
    for p in paths:
        try:
            if p.is_file():
                st = p.stat()
                stat_bits.append(f"{p.resolve()}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            stat_bits.append(f"{p.resolve()}:missing")
    payload = json.dumps(
        {"stats": stat_bits, "keys": sorted(merged.items())},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _do_load() -> None:
    global _flat, _resolved_paths, _yaml_fingerprint, _slow_load_warned
    t0 = time.perf_counter()
    paths = _effective_yaml_paths()
    _resolved_paths = [str(p) for p in paths]
    merged: Dict[str, str] = {}
    for p in paths:
        piece = _load_yaml_file(p)
        merged.update(piece)
    _flat = merged
    _yaml_fingerprint = _compute_yaml_fingerprint(paths, merged)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if elapsed_ms > 50 and not _slow_load_warned:
        _slow_load_warned = True
        warnings.warn(
            f"[runtime_config] YAML load took {elapsed_ms:.1f}ms "
            f"({len(paths)} file(s), {len(merged)} keys); "
            "consider moving config to local SSD or using compiled bytecode "
            "(warning emitted once per process)",
            RuntimeWarning,
            stacklevel=2,
        )


def ensure_runtime_config_loaded() -> None:
    """Idempotent: load YAML layer once per process unless reload_runtime_config_from_files() cleared it."""
    global _loaded
    with _load_lock:
        if _loaded:
            return
        _do_load()
        _loaded = True


def reload_runtime_config_from_files() -> None:
    """Re-read YAML files from disk (for hot reload). Environment variables are always current."""
    global _loaded
    with _load_lock:
        _do_load()
        _loaded = True


def get_resolved_config_paths() -> List[str]:
    """Paths last resolved during load (for diagnostics)."""
    ensure_runtime_config_loaded()
    return list(_resolved_paths)


def get_yaml_fingerprint() -> str:
    ensure_runtime_config_loaded()
    return _yaml_fingerprint


def get_raw(key: str) -> Optional[str]:
    """
    Effective string for *key* after env + YAML merge.

    Returns None if the key is unset in both layers (caller uses code default).
    Returns \"\" if explicitly set empty in env with no YAML override.
    """
    ensure_runtime_config_loaded()
    if key in os.environ:
        ev = os.environ.get(key)
        if ev is not None and str(ev).strip() != "":
            return str(ev).strip()
        if key in _flat:
            return _flat[key]
        return ""
    if key in _flat:
        return _flat[key]
    return None


def config_value_source(key: str) -> str:
    """Where the effective non-default value would come from: ENV, YAML, or DEFAULT (unset)."""
    ensure_runtime_config_loaded()
    ev = os.environ.get(key)
    if ev is not None and str(ev).strip() != "":
        return "ENV"
    if key in _flat:
        return "YAML"
    if ev is not None:
        return "ENV"
    return "DEFAULT"
