"""Opt-in fill slippage and portfolio caps. Absent overlay leaves fills unchanged."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class SlippageModel:
    """Buy pays more and sell receives less, in basis points of the quote."""

    name: str
    bp: float

    def buy_price(self, px: float) -> float:
        return float(px) * (1.0 + self.bp / 10_000.0)

    def sell_price(self, px: float) -> float:
        return float(px) * (1.0 - self.bp / 10_000.0)


@dataclass(frozen=True)
class PortfolioConstraints:
    """Caps apply to new names only. Adds to a name already held are kept."""

    max_names: int | None = None
    industry_cap: int | None = None
    industry_of: Callable[[str], str | None] | None = None


def resolve_slippage(name: str | None, bp: float | None) -> SlippageModel | None:
    """``none`` and a zero fixed spread attach nothing, so the quote is not rewritten."""
    label = (name or "none").strip().lower()
    if label == "none":
        return None
    if label != "fixed_bp":
        raise ValueError(f"slippage must be none or fixed_bp, got {name}")
    if bp is None or not math.isfinite(bp) or bp < 0:
        raise ValueError("fixed_bp requires a nonnegative --slippage-bp")
    if bp == 0:
        return None
    return SlippageModel(name="fixed_bp", bp=float(bp))


def build_research_overlay(
    *,
    slippage: str | None = None,
    slippage_bp: float | None = None,
    max_names: int | None = None,
    industry_cap: int | None = None,
):
    model = resolve_slippage(slippage, slippage_bp)
    industry_of = None
    if max_names is not None and max_names < 1:
        raise ValueError("max_names must be at least 1")
    if industry_cap is not None:
        if industry_cap < 1:
            raise ValueError("industry_cap must be at least 1")
        industry_of = _industry_lookup()
    if model is None and max_names is None and industry_cap is None:
        return None
    return ResearchOverlay(slippage=model, max_names=max_names, industry_cap=industry_cap, industry_of=industry_of)


@dataclass(frozen=True)
class ResearchOverlay:
    slippage: SlippageModel | None = None
    max_names: int | None = None
    industry_cap: int | None = None
    industry_of: Callable[[str], str | None] | None = None


def bind_research_overlay(st, overlay: ResearchOverlay | None) -> None:
    if overlay is None:
        return
    if overlay.slippage is not None:
        st.slippage_model = overlay.slippage
    if overlay.max_names is not None or overlay.industry_cap is not None:
        st.portfolio_constraints = overlay


def constrain_planned(st, planned: list[str]) -> list[str]:
    """Return ``planned`` itself when no cap is bound."""
    spec = getattr(st, "portfolio_constraints", None)
    if spec is None:
        return planned
    held = {code for code, lots in st.positions.items() if lots}
    industry_counts: dict[str, int] = {}
    if spec.industry_cap is not None and spec.industry_of is not None:
        for code in held:
            industry = spec.industry_of(code)
            if industry:
                industry_counts[industry] = industry_counts.get(industry, 0) + 1
    accepted: list[str] = []
    accepted_new: set[str] = set()
    for code in planned:
        if code in held or code in accepted_new:
            accepted.append(code)
            continue
        if spec.max_names is not None and len(held) + len(accepted_new) >= spec.max_names:
            st.stats["skip_max_names"] = int(st.stats.get("skip_max_names", 0)) + 1
            continue
        if spec.industry_cap is not None:
            industry = spec.industry_of(code) if spec.industry_of is not None else None
            if not industry:
                st.stats["skip_industry_unknown"] = int(st.stats.get("skip_industry_unknown", 0)) + 1
                continue
            if industry_counts.get(industry, 0) >= spec.industry_cap:
                st.stats["skip_industry_cap"] = int(st.stats.get("skip_industry_cap", 0)) + 1
                continue
            industry_counts[industry] = industry_counts.get(industry, 0) + 1
        accepted_new.add(code)
        accepted.append(code)
    return accepted


def _industry_lookup() -> Callable[[str], str | None]:
    from oskh_data.industry_sw_l1 import load_industry_map, lookup_industry

    mapping = load_industry_map()

    def industry_of(code: str) -> str | None:
        return lookup_industry(code, mapping)

    return industry_of


def add_research_overlay_args(parser) -> None:
    parser.add_argument(
        "--slippage",
        choices=("none", "fixed_bp"),
        default="none",
        help="none (default) leaves quotes unchanged. fixed_bp needs --slippage-bp",
    )
    parser.add_argument(
        "--slippage-bp",
        type=float,
        default=None,
        help="basis points for --slippage fixed_bp. Buy pays more, sell receives less",
    )
    parser.add_argument(
        "--max-names",
        type=int,
        default=None,
        help="optional cap on distinct held names. Default off",
    )
    parser.add_argument(
        "--industry-cap",
        type=int,
        default=None,
        help="optional cap on new names in one Shenwan L1 industry. Default off. Missing map fails",
    )
