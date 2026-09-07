# -*- coding: utf-8 -*-
"""Single-source data root resolution (M-003b · RFC-003)."""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Iterable, Optional, Set

AUTHORITY_MARKER_NAME = ".authority"
_DEFAULT_AUTHORITY_HINTS = (Path("F:/stock_data"),)
_AUTHORITY_WARNED: Set[str] = set()


def resolve_data_root(
    *,
    explicit_root: Optional[str] = None,
    env_var: Optional[str] = None,
    fallback_marker: str = "stock_data",
) -> Path:
    """Resolve repository/data root directory.

    Priority:
    1) explicit_root argument
    2) environment variable (default OSKH_DATA_ROOT)
    3) walk ``__file__`` parents until ``fallback_marker`` directory exists
    """
    if explicit_root:
        return Path(explicit_root)
    if env_var is None:
        from common.infra.constants import EnvVarKeys

        env_var = EnvVarKeys.OSKH_DATA_ROOT
    env_root = os.environ.get(env_var)
    if env_root:
        return Path(env_root)
    p = Path(__file__).resolve().parent
    fallback: Path | None = None
    for ancestor in [p, *p.parents]:
        if not (ancestor / fallback_marker).is_dir():
            continue
        if (ancestor / "main.py").is_file():
            return ancestor
        if fallback is None:
            fallback = ancestor
    if fallback is not None:
        return fallback
    # Slim fork has no main.py and may not have a local stock_data/ tree.
    return Path(__file__).resolve().parents[2]


def authority_hint_roots() -> tuple[Path, ...]:
    """Roots that may hold the path-SSOT ``.authority`` marker (plan D7).

    Production default is ``F:/stock_data``. Tests may monkeypatch this
    function or set ``OSKH_AUTHORITY_HINT_ROOT`` (not a product env).
    """
    raw = str(os.environ.get("OSKH_AUTHORITY_HINT_ROOT") or "").strip()
    if raw:
        return (Path(raw),)
    return _DEFAULT_AUTHORITY_HINTS


def find_authority_marker(hints: Optional[Iterable[Path]] = None) -> Optional[Path]:
    """Return the first existing ``<hint>/.authority`` file, else None."""
    for hint in hints if hints is not None else authority_hint_roots():
        marker = Path(hint) / AUTHORITY_MARKER_NAME
        if marker.is_file():
            return marker
    return None


def reset_authority_fallback_warnings() -> None:
    """Test hook: clear the once-per-process D7 warning latch."""
    _AUTHORITY_WARNED.clear()


def _warn_authority_env_missing(*, env_key: str, fallback: Path) -> None:
    marker = find_authority_marker()
    if marker is None:
        return
    latch = f"{env_key}:{marker}"
    if latch in _AUTHORITY_WARNED:
        return
    _AUTHORITY_WARNED.add(latch)
    warnings.warn(
        f"path-SSOT authority marker present at {marker} but {env_key} is unset; "
        f"falling back to {fallback}. Set {env_key} explicitly to the F root, "
        f"or set it to the E path to roll back. Unset is not a rollback.",
        UserWarning,
        stacklevel=3,
    )


def resolve_l2_parquet_root(*, explicit_root: Optional[str] = None) -> Path:
    """Resolve the L2 tick parquet root directory (single source for all L2 consumers).

    Priority:
    1) explicit_root argument
    2) ``OSKH_L2_PARQUET_ROOT`` env var (L2-specific override; e.g. ``F:\\stock_data\\l2_parquet``)
    3) ``resolve_data_root() / "stock_data" / "l2_parquet"`` (default; honors ``OSKH_DATA_ROOT``)

    Returns the path without checking existence (callers decide: ``connect()`` raises
    ``FileNotFoundError``; ``qmt_l2_source`` returns ``[]``; ``available_l2_dates`` returns ``[]``).
    """
    if explicit_root:
        return Path(explicit_root)
    from common.infra.constants import EnvVarKeys

    env_root = os.environ.get(EnvVarKeys.OSKH_L2_PARQUET_ROOT)
    if env_root:
        return Path(env_root)
    fallback = resolve_data_root() / "stock_data" / "l2_parquet"
    _warn_authority_env_missing(
        env_key=EnvVarKeys.OSKH_L2_PARQUET_ROOT, fallback=fallback
    )
    return fallback


def resolve_period_root(
    period: str,
    *,
    explicit_root: Optional[str] = None,
    base: Optional[Path] = None,
) -> Path:
    """Resolve the parquet root for a given period (e.g. ``period=1m``).

    Priority:
    1) explicit_root argument
    2) ``OSKH_PERIOD_{PERIOD}_ROOT`` env var (period-specific override; e.g.
       ``OSKH_PERIOD_1M_ROOT=F:\\stock_data\\period=1m``)
    3) ``base / f"period={period}"`` if ``base`` given
    4) ``resolve_data_root() / "stock_data" / f"period={period}"`` (default)

    Returns the period directory without checking existence. When the env var
    is set, ``base`` is ignored (override wins regardless of caller's base).
    """
    if explicit_root:
        return Path(explicit_root)
    env_key = f"OSKH_PERIOD_{period.upper()}_ROOT"
    env_root = os.environ.get(env_key)
    if env_root:
        return Path(env_root)
    if base is not None:
        return base / f"period={period}"
    fallback = resolve_data_root() / "stock_data" / f"period={period}"
    _warn_authority_env_missing(env_key=env_key, fallback=fallback)
    return fallback


def resolve_source_parquet(
    name: str, *, explicit_root: Optional[str] = None
) -> Path:
    """Resolve a loose source-parquet file path (single source; plan-data-path-ssot D1).

    散装 parquet 源文件族（adj_factor.parquet / float_shares.parquet /
    free_float_shares.parquet / turnover_resistance_daily.parquet /
    ex_date_index.parquet / etf 目录等）——磁盘空间原因常与周期 parquet 同置
    另一块物理盘。

    Priority（与 ``resolve_period_root`` 同型）:
    1) explicit_root 参数（罕见；= 含文件族的容器目录）
    2) ``OSKH_SOURCE_PARQUET_ROOT`` env var（容器目录覆盖，如 ``F:/stock_data``）
    3) ``resolve_data_root() / "stock_data"``（默认；honors ``OSKH_DATA_ROOT``）

    不检查存在性（调用方 fail-visible：FileNotFoundError 带路径）。
    """
    if explicit_root:
        return Path(explicit_root) / name
    from common.infra.constants import EnvVarKeys

    env_root = os.environ.get(EnvVarKeys.OSKH_SOURCE_PARQUET_ROOT)
    if env_root:
        return Path(env_root) / name
    fallback_dir = resolve_data_root() / "stock_data"
    _warn_authority_env_missing(
        env_key=EnvVarKeys.OSKH_SOURCE_PARQUET_ROOT, fallback=fallback_dir / name
    )
    return fallback_dir / name
