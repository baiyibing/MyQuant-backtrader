"""
ETF 涨跌幅限制规则表。

A 股 ETF 涨跌幅与个股不同：
- 大多数 ETF：10%
- 科创板 ETF (588xxx)：20%
- 创业板 ETF (159xxx 部分)：20%
- 跨境 ETF（如纳指 100ETF 513100）：无涨跌幅限制或 20%
- 商品 ETF（如黄金 ETF 518880）：无涨跌幅限制
- 可转债 ETF (511xxx 部分)：无涨跌幅限制

本模块提供 symbol → limit_pct 映射，供 check_limit_up_stocks 使用。
规则来源：交易所公告 + QMT get_instrument_detail。结果写入审计。
"""
from __future__ import annotations

from typing import Dict, Optional

# ETF 涨跌幅限制映射（Phase 2 P1: expanded coverage）
# key: 代码前缀，value: 涨跌幅百分比（None = 无限制）
_ETF_LIMIT_RULES: Dict[str, Optional[float]] = {
    # 科创板 ETF：20%
    "588": 20.0, "589": 20.0,
    # 创业板 ETF：20%（1590-1599 all Chinext ETFs）
    "159": 20.0,
    # 跨境 ETF（纳指、港股、日经、德国等）：无限制
    "513": None,
    # 商品 ETF（黄金、原油、有色等）：无限制
    "518": None,
    # 债券 ETF：10%（默认，不在此表中）
    # 宽基/行业 ETF：10%（510/512/515/516/517/560/561/562/563 等默认）
}


def get_etf_limit_pct(symbol: str) -> float | None:
    """返回 ETF 的涨跌幅百分比限制。

    Args:
        symbol: 6 位纯数字代码或 000001.SH 格式。

    Returns:
        涨跌幅百分比（如 10.0 表示 10%）。None 表示无涨跌幅限制。
    """
    code = symbol.split(".")[0] if "." in symbol else symbol
    code = code.strip()
    for prefix, limit in _ETF_LIMIT_RULES.items():
        if code.startswith(prefix):
            return limit
    # Phase 2 P0/P1 fix: return 10% for recognized ETFs without special rules,
    # None for non-ETF codes (so stock-specific limits apply).
    if is_etf_code(code):
        return _DEFAULT_ETF_LIMIT
    return None


# Comprehensive ETF prefix list (Phase 2 P1: expanded beyond _ETF_LIMIT_RULES
# which only covers ETFs with non-standard limits)
_ETF_PREFIXES = frozenset({
    "510", "511", "512", "513", "515", "516", "517", "518", "520",
    "560", "561", "562", "563", "588", "589", "159",
})

_DEFAULT_ETF_LIMIT = 10.0


def is_etf_code(symbol: str) -> bool:
    """Return True if the symbol matches known ETF code prefixes."""
    code = symbol.split(".")[0] if "." in symbol else symbol
    code = code.strip()
    return any(code.startswith(prefix) for prefix in _ETF_PREFIXES)


def is_price_at_limit(
    current_price: float,
    prev_close: float,
    symbol: str,
    *,
    price_tolerance: float = 0.001,
) -> bool:
    """判断 ETF 是否处于涨跌停价。

    Args:
        current_price: 当前价
        prev_close: 前收盘价
        symbol: ETF 代码
        price_tolerance: 价格容差

    Returns:
        True 如果当前价在涨跌停价附近。
    """
    if not is_etf_code(symbol):
        return False  # not an ETF — use stock limit logic instead
    limit_pct = get_etf_limit_pct(symbol)
    if limit_pct is None:
        return False  # 无涨跌幅限制，永不涨停
    limit_price = prev_close * (1 + limit_pct / 100)
    return abs(current_price - limit_price) <= price_tolerance


def export_limit_rules() -> Dict[str, Optional[float]]:
    """导出完整的涨跌幅规则表（供审计快照使用）。"""
    return dict(_ETF_LIMIT_RULES)
