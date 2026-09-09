"""Board涨跌停 % for L2 offline templates (stock-only; no QMT / ST name source).

Mirrors ``hkcodex_miniqmt._get_limit_pct`` equity prefixes and adds **302**
(创业板段, SSOT in ``oskh_core.a_share_symbol_normalize``). ST 5% is not applied
here (no name feed) — treat estimates as board-rule only.
"""

from __future__ import annotations


def board_limit_pct(stock_code: str) -> float:
    """Return limit ratio (0.10 / 0.20 / 0.30) from bare or canonical code."""
    code = str(stock_code).strip().upper()
    if "." in code:
        code = code.split(".", 1)[0]
    if code.startswith(("300", "301", "302")):
        return 0.20
    if code.startswith(("688", "689")):
        return 0.20
    if code.startswith(("8", "4", "9")):  # BJ coarse
        return 0.30
    if code.startswith(("11", "12")):  # convertible (not used in stock templates)
        return 0.20
    return 0.10


# DuckDB expression on canonical ``stock_code`` (e.g. 000001.SZ).
BOARD_LIMIT_PCT_SQL = """
CASE
  WHEN split_part(stock_code, '.', 1) LIKE '300%'
    OR split_part(stock_code, '.', 1) LIKE '301%'
    OR split_part(stock_code, '.', 1) LIKE '302%' THEN 0.20
  WHEN split_part(stock_code, '.', 1) LIKE '688%'
    OR split_part(stock_code, '.', 1) LIKE '689%' THEN 0.20
  WHEN split_part(stock_code, '.', 1) LIKE '8%'
    OR split_part(stock_code, '.', 1) LIKE '4%'
    OR split_part(stock_code, '.', 1) LIKE '9%' THEN 0.30
  ELSE 0.10
END
""".strip()
