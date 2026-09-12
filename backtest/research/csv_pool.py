# -*- coding: utf-8 -*-
"""CSV 选股名单：无后缀六位码 → ``XXXXXX.SH|SZ|BJ``。

与 OSkhQuant1.3 ``backtest/lebs/csv/universe.py::parse_pool_csv`` 同口径。
后缀只走 ``oskh_core.a_share_symbol_normalize.canonical_from_bare_code``，
不要用 ``to_canonical_symbol``（那是分区键 ``000001_SZ`` → 点分，不加交易所）。
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Literal, Tuple

from oskh_core.a_share_symbol_normalize import canonical_from_bare_code

_BARE_CODE_RE = re.compile(r"(\d{6})")
_HEADER_FIRST = frozenset(
    {"代码", "code", "symbol", "证券代码", "ticker", "stock", "stock_code"}
)


def _cell_to_bare(raw: str) -> str:
    text = str(raw or "").strip().strip('"').strip("'")
    if text.startswith("="):
        text = text[1:].strip().strip('"').strip("'")
    match = _BARE_CODE_RE.search(text)
    return match.group(1) if match else ""


def parse_pool_csv_entries(path: Path) -> List[Tuple[str, str]]:
    """解析一份名单文件 → ``(canonical, name)``（去重、保序）。"""
    text = Path(path).read_text(encoding="utf-8-sig")
    out: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        first = parts[0] if parts else ""
        if i == 0 and first.strip('"').strip("'").lower() in _HEADER_FIRST:
            continue
        bare = _cell_to_bare(first)
        if not bare:
            continue
        canon = canonical_from_bare_code(bare)
        if not canon or canon in seen:
            continue
        seen.add(canon)
        name = parts[1] if len(parts) > 1 else ""
        out.append((canon, name))
    return out


def parse_pool_csv(path: Path) -> List[str]:
    """解析一份名单文件 → canonical 代码（去重、保序）。"""
    return [code for code, _name in parse_pool_csv_entries(path)]


def _window_ymd(start: str | date, end: str | date) -> tuple[str, str]:
    start_ymd = start.strftime("%Y%m%d") if isinstance(start, date) else str(start).replace("-", "")
    end_ymd = end.strftime("%Y%m%d") if isinstance(end, date) else str(end).replace("-", "")
    return start_ymd, end_ymd


def load_pool_name_map(
    pool_dir: Path,
    start: str | date,
    end: str | date,
) -> dict[str, str]:
    """Union of CSV second-column names in [start, end]; later files win."""
    root = Path(pool_dir)
    start_ymd, end_ymd = _window_ymd(start, end)
    names: dict[str, str] = {}
    for path in sorted(root.glob("*.csv")):
        stem = path.stem
        if len(stem) != 8 or not stem.isdigit() or not start_ymd <= stem <= end_ymd:
            continue
        try:
            entries = parse_pool_csv_entries(path)
        except Exception as exc:
            print(f"skip pool {path.name}: {exc}", flush=True)
            continue
        for code, name in entries:
            if name:
                names[code] = name
    return names


def load_pool_day_map(
    pool_dir: Path,
    start: str | date,
    end: str | date,
    *,
    key: Literal["ymd", "date"] = "ymd",
    empty_in_map: bool = False,
) -> dict[str, list[str]] | dict[date, list[str]]:
    """Load dated pool CSVs with an explicit key and empty-file policy."""
    if key not in ("ymd", "date"):
        raise ValueError("key must be 'ymd' or 'date'")
    root = Path(pool_dir)
    start_ymd, end_ymd = _window_ymd(start, end)
    days = {}
    for path in sorted(root.glob("*.csv")):
        stem = path.stem
        if len(stem) != 8 or not stem.isdigit() or not start_ymd <= stem <= end_ymd:
            continue
        try:
            codes = parse_pool_csv(path)
        except Exception as exc:
            print(f"skip pool {path.name}: {exc}", flush=True)
            continue
        if codes or empty_in_map:
            map_key = datetime.strptime(stem, "%Y%m%d").date() if key == "date" else stem
            days[map_key] = codes
    return days
