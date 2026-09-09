# -*- coding: utf-8 -*-
"""
Canonical A-share / ETF symbol normalization to ``XXXXXX.SH`` / ``.SZ`` / ``.BJ``.

Single source for CSV selector, Monitor preview/import, and miniQMT order paths
(``hkcodex_miniqmt``) so prefix rules cannot drift between selection DB and execution.

No ``common`` / ``strategy_config`` imports — safe for adapter layers.
"""

from __future__ import annotations

import re
from typing import Optional, Set


_RE_DOTTED = re.compile(r"^\s*([0-9]{6})\s*\.\s*([A-Za-z]{2})\s*$")
_RE_NOISY = re.compile(r"^[A-Z]{0,2}\s*([0-9]{6})\s*[A-Z]{0,2}$")


def infer_exchange_suffix(six_digit: str) -> Optional[str]:
    """若 ``six_digit`` 为六位数字且命中已知前缀规则，返回 SH/SZ/BJ，否则 None。"""
    if len(six_digit) != 6 or not six_digit.isdigit():
        return None
    if six_digit.startswith(("6", "5", "11", "51", "58")):
        return "SH"
    if six_digit.startswith(("0", "3", "12", "15", "16")):
        return "SZ"
    if six_digit.startswith(("8", "4", "9")):
        return "BJ"
    return None


_infer_exchange_suffix = infer_exchange_suffix


def normalize_plain_code_to_exchange_suffix(raw: str) -> str:
    """
    Normalize a CSV cell or broker symbol string to suffixed exchange code.

    - Already ``digits.SUFFIX`` (suffix case-insensitive): if prefix rules can infer
      an exchange, use the inferred suffix (corrects ``600000.SZ`` → ``600000.SH``);
      otherwise keep the given suffix uppercased.
    - Bare 6-digit (or digits with embedded SH/SZ/BJ noise): infer SH/SZ/BJ from
      prefix rules aligned with miniQMT / industry habit (SH: 6,5,11,51,58;
      SZ: 0,3,12,15,16; BJ: 8,4,9).
    - Unknown pattern: return stripped upper string (caller may filter).
    """
    code = str(raw).strip().upper()
    if not code:
        return code

    m_dot = _RE_DOTTED.match(code)
    if m_dot:
        six = m_dot.group(1)
        given = m_dot.group(2).upper()
        inferred = _infer_exchange_suffix(six)
        if inferred is not None:
            return f"{six}.{inferred}"
        return f"{six}.{given}"

    if "." in code:
        parts = code.split(".")
        if len(parts) >= 2:
            left = parts[0].strip().upper()
            right = parts[1].strip().upper()
            left = left.replace("SH", "").replace("SZ", "").replace("BJ", "")
            inferred = _infer_exchange_suffix(left)
            if inferred is not None:
                return f"{left}.{inferred}"
            return f"{left}.{right}"

    m_noise = _RE_NOISY.match(code)
    code = m_noise.group(1) if m_noise else code

    if code.startswith(("6", "5", "11", "51", "58")):
        return f"{code}.SH"
    if code.startswith(("0", "3", "12", "15", "16")):
        return f"{code}.SZ"
    if code.startswith(("8", "4", "9")):
        return f"{code}.BJ"
    return code


def normalize_a_share_code(code: object) -> str:
    """
    统一为 ``XXXXXX.SH|SZ|BJ``。``None``、空串及仅空白输入均返回 ``""``。

    Delegates to :func:`normalize_plain_code_to_exchange_suffix` after the empty
    guard. Two-segment ``code.suffix`` is corrected when prefix rules can infer
    the exchange; otherwise the given suffix is kept.
    """
    if code is None:
        return ""
    s = str(code).strip()
    if not s:
        return ""
    return normalize_plain_code_to_exchange_suffix(s)


def is_valid_normalized_a_share(code: str) -> bool:
    """格式正确、前六位为数字，且后缀与代码段推断的交易所一致。"""
    if len(code) != 9 or code[6] != ".":
        return False
    suffix = code[7:]
    if suffix not in ("SH", "SZ", "BJ"):
        return False
    six = code[:6]
    if not six.isdigit():
        return False
    return _infer_exchange_suffix(six) == suffix


def normalize_stock_candidates(stock: str) -> Set[str]:
    """
    生成名单匹配候选（兼容 6 位/带后缀两种输入）。
    """
    s = (stock or "").strip().upper()
    if not s:
        return set()

    out = {s}
    if len(s) >= 6:
        out.add(s[:6])

    normalized = normalize_a_share_code(s)
    if normalized:
        out.add(normalized)
        if len(normalized) >= 6:
            out.add(normalized[:6])
    return out


_A_SHARE_EQUITY_SUFFIXES = (".SH", ".SZ", ".BJ")

# Real A-share stock prefixes (SZ 主板/创业板 + SH 主板/科创板 + BJ 北交所).
# LOF/funds (530xxx 等)、ETF、转债 不在此列 → 'other'/etf/cvt_bond。
# 不用「有 exchange suffix 即 stock」这条松规则——会把 530xxx LOF/基金 误归 stock
# （530xxx 有 SH suffix 但非股；评审 #1）。
_STOCK_PREFIXES = (
    "000", "001", "002", "003",           # SZ 主板
    "300", "301", "302",                  # SZ 创业板（302 为新启用段）
    "600", "601", "603", "605",           # SH 主板
    "688", "689",                         # SH 科创板
    "430", "830", "87", "920",            # BJ 北交所（87x / 920 新段）
)


def classify_instrument_type(bare_or_canonical: str) -> str:
    """Return ``stock`` / ``etf`` / ``cvt_bond`` / ``other``.

    Single classification SSOT (formerly ``l2_analytics.classify``). ETF lookup is a
    lazy ``oskh_data.etf_limits`` import to keep this module common-/import-light so the
    ``hkcodex_miniqmt`` adapter can still import it cheaply (oskh_core→oskh_data allowed).
    """
    from oskh_data.etf_limits import is_etf_code

    code = str(bare_or_canonical).strip()
    bare = code.split(".", 1)[0] if "." in code else code
    if not bare:
        return "other"
    if is_etf_code(bare):
        return "etf"
    if len(bare) == 6 and bare.isdigit() and bare.startswith(("11", "12")):
        return "cvt_bond"
    if len(bare) == 6 and bare.isdigit() and bare.startswith(_STOCK_PREFIXES):
        return "stock"
    return "other"


def canonical_from_bare_code(bare: str) -> str:
    """``000001`` -> ``000001.SZ``; unknown / non-6-digit input returns bare unchanged.

    Common-free: delegates to ``normalize_plain_code_to_exchange_suffix`` only for a
    dotted code or a strict 6-digit bare code (keeps the L2 strictness — 5-digit junk
    is not coerced to a suffixed symbol).
    """
    text = str(bare).strip()
    if not text:
        return ""
    if "." in text or (len(text) == 6 and text.isdigit()):
        return normalize_plain_code_to_exchange_suffix(text)
    return text


def is_a_share_equity_symbol(code: str) -> bool:
    """
    True for A-share equities (excludes ETF/基金/债：510050.SH、159919.SZ 等).

    Used by pretrade daily st_set universe build. Basis is the precise-prefix 4-way
    classifier (``classify_instrument_type``) — single source, no first-digit heuristic
    divergence. Under the merge SH B-shares (``900xxx``, first digit 9) are excluded
    (not real A-share equities); count re-measured vs the historical G-2026-06-11
    probe (7345 total → ~5207 equities).
    """
    sym = str(code or "").strip().upper()
    if not sym.endswith(_A_SHARE_EQUITY_SUFFIXES):
        return False
    return classify_instrument_type(sym) == "stock"
