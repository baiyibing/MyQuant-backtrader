"""Pure TopkDropout (qlib bottom/top) without importing qlib.

Sort keys match MyQuant export: score descending, then instrument/code ascending.
Missing scores are tagged score_missing and treated as extremely low; sell count
still cannot exceed n_drop.
"""

from __future__ import annotations

from typing import Mapping, Sequence

# Extremely low; held names without a score sort to the bottom of comb.
MISSING_SCORE = -1.0e300


def _score_of(code: str, scores: Mapping[str, float]) -> float:
    if code not in scores:
        return MISSING_SCORE
    return float(scores[code])


def sort_by_score_desc(codes: Sequence[str], scores: Mapping[str, float]) -> list[str]:
    """Stable policy: (-score, code ascending)."""
    return sorted(codes, key=lambda c: (-_score_of(c, scores), str(c)))


def decide_topk_dropout(
    held: Sequence[str],
    scores: Mapping[str, float],
    *,
    topk: int,
    n_drop: int,
) -> tuple[list[str], list[str]]:
    """Return ``(buy, sell)`` per plan §2 / qlib TopkDropout method_buy=top, method_sell=bottom.

    - ``last``: current held sorted by score desc (missing → score_missing / MISSING_SCORE).
    - ``today``: highest-scoring non-held, length ``n_drop + topk - len(last)``.
    - ``comb``: last ∪ today sorted by score desc.
    - ``sell``: members of last that fall in comb's worst ``n_drop``.
    - ``buy``: ``today[:len(sell) + topk - len(last)]``.

    Does not apply limit-up/down or T+1; the engine owns those.
    """
    topk_i = int(topk)
    n_drop_i = int(n_drop)
    if topk_i < 0 or n_drop_i < 0:
        raise ValueError(f"topk and n_drop must be >= 0, got topk={topk!r} n_drop={n_drop!r}")

    last = sort_by_score_desc(list(held), scores)
    held_set = set(last)
    n_today = n_drop_i + topk_i - len(last)
    if n_today < 0:
        n_today = 0

    not_held = [c for c in scores.keys() if c not in held_set]
    today = sort_by_score_desc(not_held, scores)[:n_today]

    comb = sort_by_score_desc([*last, *today], scores)
    bottom = set(comb[-n_drop_i:]) if n_drop_i and comb else set()
    # Preserve last order (qlib Index filter order).
    sell = [c for c in last if c in bottom]
    buy = today[: len(sell) + topk_i - len(last)]
    return list(buy), list(sell)


def count_score_missing(held: Sequence[str], scores: Mapping[str, float]) -> int:
    return sum(1 for c in held if c not in scores)
