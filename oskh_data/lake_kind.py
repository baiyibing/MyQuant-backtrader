# -*- coding: utf-8 -*-
"""日线湖品种分类（plan-hive-ashare-pure-index-etf-split-l2-2026-09-09 §2.1）。

三树路由的唯一裁决器：``stock/{1d,1m}`` · ``index/1d`` · ``etf/1d``。

只认 **带交易所后缀** 的 canonical 代码（``000001.SZ`` / ``000001_SZ``）。
裸码不做后缀猜测——裸 ``000001`` 经 ``infer_exchange_suffix`` 会猜成 ``.SZ``
（平安银行），而湖里 ``000001_SH`` 是上证指数（§2.1 分类陷阱），一律
``unknown``：写路径 fail-closed 拒写，读路径按调用方语义处理。

刻意不复用 ``classify_instrument_type`` / ``is_a_share_equity_symbol`` 做湖
路由（plan §2 明令）：它们不区分 ``000xxx.SH`` 指数与 ``000xxx.SZ`` 股票。
ETF 前缀判定复用 ``oskh_data.etf_limits.is_etf_code``（前缀 SSOT）。
"""

from __future__ import annotations

from typing import Literal

from oskh_data.etf_limits import is_etf_code

LakeKind = Literal["ashare", "index", "etf", "unknown"]

# 指数：带后缀判定（§2.1）——000xxx.SH / 399xxx.SZ
_INDEX_SH_PREFIX = "000"
_INDEX_SZ_PREFIXES = ("399",)

# A 股股票前缀（排除指数 / ETF 之后；沪深京 A 股）
_ASHARE_PREFIXES: dict[str, tuple[str, ...]] = {
    "SH": ("60", "68"),  # 主板 600/601/603/605 + 科创 688/689
    "SZ": ("00", "30"),  # 主板 000/001/002/003 + 创业 300/301/302
    "BJ": ("43", "82", "83", "87", "92"),  # 北交所
}


def classify_daily_lake_kind(symbol: str) -> LakeKind:
    """Classify a suffixed canonical symbol into its daily-lake tree kind.

    - ETF → ``is_etf_code`` 前缀 SSOT；
    - 指数 → ``000xxx.SH`` / ``399xxx.SZ``；
    - A 股 → 排除后的股票前缀（SH 60/68 · SZ 00/30 · BJ 43/82/83/87/92）；
    - 其余（裸码 / B 股 900·200 / 可转债 11x·12x / 板块指数 880xxx 等）→
      ``unknown``，fail-closed。
    """
    code, _, suffix = symbol.replace(".", "_").rpartition("_")
    suffix = suffix.strip().upper()
    if len(code) != 6 or not code.isdigit() or not suffix:
        return "unknown"
    if is_etf_code(code):
        return "etf"
    if suffix == "SH" and code.startswith(_INDEX_SH_PREFIX):
        return "index"
    if suffix == "SZ" and code.startswith(_INDEX_SZ_PREFIXES):
        return "index"
    prefixes = _ASHARE_PREFIXES.get(suffix)
    if prefixes and any(code.startswith(p) for p in prefixes):
        return "ashare"
    return "unknown"
