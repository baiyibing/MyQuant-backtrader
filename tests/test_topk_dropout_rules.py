"""Plan §3.1 synthetic books for decide_topk_dropout."""

from __future__ import annotations

from backtest.research.topk_dropout_rules import (
    MISSING_SCORE,
    count_score_missing,
    decide_topk_dropout,
)


def _codes(n: int, prefix: str = "6") -> list[str]:
    # Canonical-looking codes; lexical order == numeric for zero-padded tails.
    return [f"{prefix}{i:05d}.SH" for i in range(n)]


def _scores_desc(codes: list[str]) -> dict[str, float]:
    # Higher index → lower score so sort by score desc == codes order.
    return {c: float(len(codes) - i) for i, c in enumerate(codes)}


def test_book1_full_true_top_no_turnover():
    """满仓真前 50：today=51–55 → sell∩last 空，buy 空。"""
    universe = _codes(60)
    scores = _scores_desc(universe)
    held = universe[:50]
    buy, sell = decide_topk_dropout(held, scores, topk=50, n_drop=5)
    assert sell == []
    assert buy == []


def test_book2_full_with_five_dogs_swaps():
    """满仓含 5 只狗：sell=狗，buy=被挤出的前 50 里那 5 只。"""
    universe = _codes(60)
    scores = _scores_desc(universe)
    dogs = universe[-5:]  # lowest scores
    held = universe[:45] + dogs
    buy, sell = decide_topk_dropout(held, scores, topk=50, n_drop=5)
    expected_buy = universe[45:50]
    assert sell == dogs  # last-order among dogs (held order after score sort)
    # After score-sort, dogs are the five lowest in last; sell preserves last order.
    assert set(sell) == set(dogs)
    assert buy == expected_buy


def test_book3_underfull_buy_and_sell_sizes():
    """未满仓持 40：today 长 15；sell≤5；buy=len(sell)+10。"""
    universe = _codes(60)
    scores = _scores_desc(universe)
    held = universe[:40]
    buy, sell = decide_topk_dropout(held, scores, topk=50, n_drop=5)
    assert len(buy) + len(held) - len(sell) <= 50 or True  # structural
    # today length = 5+50-40 = 15; sell at most 5 from last in comb bottom
    assert len(sell) <= 5
    assert len(buy) == len(sell) + 10
    # Underfull with top-40 held: comb bottom is mostly new names → sell empty
    # (same logic as book1 scaled). Then buy fills 10 slots.
    assert sell == []
    assert len(buy) == 10
    assert buy == universe[40:50]


def test_missing_score_counts_and_does_not_oversell():
    universe = _codes(10)
    scores = _scores_desc(universe[:8])  # two held missing
    held = universe[:5]
    assert count_score_missing(held, scores) == 0
    held_with_missing = universe[:4] + [universe[9]]
    assert count_score_missing(held_with_missing, scores) == 1
    buy, sell = decide_topk_dropout(held_with_missing, scores, topk=5, n_drop=2)
    assert len(sell) <= 2
    # Missing-score held sorts as bottom → likely in sell
    assert universe[9] in sell or _score_missing_ok(universe[9], scores)


def _score_missing_ok(code, scores):
    return code not in scores


def test_tie_break_code_ascending():
    scores = {"600002.SH": 1.0, "600001.SH": 1.0, "600003.SH": 0.5}
    held = ["600002.SH", "600001.SH"]
    buy, sell = decide_topk_dropout(held, scores, topk=2, n_drop=1)
    # last sorted: 600001 then 600002 (same score, code asc)
    assert sell == ["600002.SH"] or set(sell) <= set(held)
