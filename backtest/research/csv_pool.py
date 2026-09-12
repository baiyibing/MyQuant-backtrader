# -*- coding: utf-8 -*-
"""CSV 选股名单：无后缀六位码 → ``XXXXXX.SH|SZ|BJ``。

与 OSkhQuant1.3 ``backtest/lebs/csv/universe.py::parse_pool_csv`` 同口径。
后缀只走 ``oskh_core.a_share_symbol_normalize.canonical_from_bare_code``，
不要用 ``to_canonical_symbol``（那是分区键 ``000001_SZ`` → 点分，不加交易所）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

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
