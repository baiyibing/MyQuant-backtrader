"""Compatibility exports for A-share symbol contracts owned by infra."""
from myquant_infra.reference_data.symbols import (
    canonical_from_bare_code, classify_instrument_type, infer_exchange_suffix,
    is_a_share_equity_symbol, is_valid_normalized_a_share, normalize_a_share_code,
    normalize_plain_code_to_exchange_suffix, normalize_stock_candidates,
)

_infer_exchange_suffix = infer_exchange_suffix

__all__ = [
    "canonical_from_bare_code", "classify_instrument_type", "infer_exchange_suffix",
    "is_a_share_equity_symbol", "is_valid_normalized_a_share", "normalize_a_share_code",
    "normalize_plain_code_to_exchange_suffix", "normalize_stock_candidates",
]
