"""Named rule profiles for opt-in backtest convention changes.

This leaf is intentionally stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleProfile:
    """Resolved, immutable rule-profile settings."""

    name: str
    revision: str
    special_no_limit_days: bool = False
    exchange_quantity_rules: bool = False
    account_odd_lot_exit: bool = False
    supplementary_min_lot: bool = False
    fee_aware_affordability: bool = False
    account_fee_schedule: bool = False
    chronological_v7: bool = False
    s12_domain_stamp: bool = False
    slippage_bp: float = 0.0


LEGACY = RuleProfile(name="legacy", revision="legacy")
INDUSTRY = RuleProfile(
    name="industry",
    revision="industry-p03-20261006",
    account_fee_schedule=True,
    s12_domain_stamp=True,
)


def resolve_rule_profile(name_or_obj: str | RuleProfile) -> RuleProfile:
    """Resolve a public profile name or return an already-resolved profile."""

    if isinstance(name_or_obj, RuleProfile):
        return name_or_obj
    if name_or_obj == "legacy":
        return LEGACY
    if name_or_obj == "industry":
        return INDUSTRY
    raise ValueError(
        f"rule_profile must be 'legacy', 'industry', or a RuleProfile instance; got {name_or_obj!r}"
    )
