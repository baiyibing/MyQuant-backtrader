"""T6-SX0: keep original topk_dropout, then extra-sell finite score<=0.

Does not re-run dropout after the extra sells. Extra slots are filled from the
full-universe score map, score descending, never buying back the same-day SX0
names. Missing / non-finite scores are not treated as non-positive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from backtest.research.topk_dropout_rules import decide_topk_dropout, sort_by_score_desc

SX0_REASON = "model_exit:nonpositive"
BOTTOM_REASON = "topk_drop:bottom"


@dataclass(frozen=True)
class ScoreExitPlan:
    buy: tuple[str, ...]
    sell: tuple[str, ...]
    buy_bottom: tuple[str, ...]
    sell_bottom: tuple[str, ...]
    sell_sx0: tuple[str, ...]
    also_bottom: tuple[str, ...]
    buy_extra: tuple[str, ...]


def is_finite_nonpositive(code: str, scores: Mapping[str, float]) -> bool:
    """SX0 trigger: finite score <= 0. Missing / NaN / Inf do not fire."""
    if code not in scores:
        return False
    try:
        val = float(scores[code])
    except (TypeError, ValueError):
        return False
    if not math.isfinite(val):
        return False
    return val <= 0.0


def decide_topk_score_exit(
    held: Sequence[str],
    scores: Mapping[str, float],
    *,
    topk: int,
    n_drop: int,
) -> ScoreExitPlan:
    """Return one-shot C-then-X plan. Dropout lists are frozen before SX0 fill."""
    buy_bottom, sell_bottom = decide_topk_dropout(
        held, scores, topk=topk, n_drop=n_drop
    )
    sell_sx0 = tuple(c for c in held if is_finite_nonpositive(c, scores))
    sell_bottom_set = set(sell_bottom)
    sell_sx0_set = set(sell_sx0)
    also_bottom = tuple(c for c in sell_sx0 if c in sell_bottom_set)

    sell: list[str] = list(sell_bottom)
    seen = set(sell)
    for code in sell_sx0:
        if code not in seen:
            sell.append(code)
            seen.add(code)

    opening_set = set(held)
    remaining = len(held) - len(seen)
    need_buys = max(0, int(topk) - remaining)
    buy = list(buy_bottom)
    buy_set = set(buy)
    extra_need = max(0, need_buys - len(buy))
    buy_extra: list[str] = []
    if extra_need:
        candidates = [
            c
            for c in scores.keys()
            if c not in opening_set and c not in sell_sx0_set and c not in buy_set
        ]
        for code in sort_by_score_desc(candidates, scores):
            if len(buy_extra) >= extra_need:
                break
            buy_extra.append(code)
            buy.append(code)
            buy_set.add(code)

    return ScoreExitPlan(
        buy=tuple(buy),
        sell=tuple(sell),
        buy_bottom=tuple(buy_bottom),
        sell_bottom=tuple(sell_bottom),
        sell_sx0=sell_sx0,
        also_bottom=also_bottom,
        buy_extra=tuple(buy_extra),
    )


def sell_reason(code: str, plan: ScoreExitPlan) -> str | None:
    if code in plan.sell_sx0:
        return SX0_REASON
    if code in plan.sell_bottom:
        return BOTTOM_REASON
    return None
