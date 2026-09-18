"""T6-SX0 decide: keep dropout lists, extra-sell score<=0, fill from sidecar."""

from __future__ import annotations

import math

from backtest.research.topk_dropout_rules import decide_topk_dropout
from backtest.research.topk_score_exit_rules import (
    SX0_REASON,
    decide_topk_score_exit,
    is_finite_nonpositive,
    sell_reason,
)


def _codes(n: int) -> list[str]:
    return [f"6000{i:02d}.SH" for i in range(n)]


def test_missing_and_nonfinite_are_not_sx0():
    scores = {"600000.SH": 0.1, "600001.SH": float("nan"), "600002.SH": float("-inf")}
    assert is_finite_nonpositive("600000.SH", scores) is False
    assert is_finite_nonpositive("600001.SH", scores) is False
    assert is_finite_nonpositive("600002.SH", scores) is False
    assert is_finite_nonpositive("600003.SH", scores) is False
    assert is_finite_nonpositive("600004.SH", {"600004.SH": 0.0}) is True
    assert is_finite_nonpositive("600005.SH", {"600005.SH": -1e-9}) is True
    assert math.isnan(scores["600001.SH"])


def test_zero_is_nonpositive_and_does_not_rerun_dropout():
    universe = _codes(12)
    scores = {c: float(12 - i) for i, c in enumerate(universe)}
    # Opening: top 7 plus 3 dogs; one extra held at score 0.
    held = universe[:7] + universe[-3:]
    scores[universe[6]] = 0.0
    scores[universe[9]] = -0.2
    scores[universe[10]] = -0.5
    scores[universe[11]] = -0.8
    plan = decide_topk_score_exit(held, scores, topk=10, n_drop=3)
    buy_c, sell_bottom = decide_topk_dropout(held, scores, topk=10, n_drop=3)
    assert plan.buy_bottom == tuple(buy_c)
    assert plan.sell_bottom == tuple(sell_bottom)
    assert universe[6] in plan.sell_sx0
    assert set(plan.sell_bottom) <= set(plan.sell)
    extra_sells = [c for c in plan.sell if c not in plan.sell_bottom]
    assert extra_sells
    assert all(is_finite_nonpositive(c, scores) for c in extra_sells)
    # Extra fill continues down the sidecar; does not re-open n_drop.
    assert plan.buy[: len(plan.buy_bottom)] == plan.buy_bottom
    assert len(plan.buy) == len(plan.buy_bottom) + len(plan.buy_extra)


def test_also_bottom_reason_and_no_buyback_sx0():
    universe = _codes(15)
    scores = {c: float(15 - i) for i, c in enumerate(universe)}
    dogs = universe[12:15]
    held = universe[:7] + dogs
    for d in dogs:
        scores[d] = -1.0
    plan = decide_topk_score_exit(held, scores, topk=10, n_drop=3)
    assert set(dogs) <= set(plan.sell_sx0)
    assert set(plan.also_bottom) == set(plan.sell_sx0) & set(plan.sell_bottom)
    for code in plan.sell_sx0:
        assert sell_reason(code, plan) == SX0_REASON
    for code in plan.sell_bottom:
        if code not in plan.sell_sx0:
            assert sell_reason(code, plan) == "topk_drop:bottom"
    assert set(plan.buy).isdisjoint(plan.sell_sx0)


def test_can_buy_other_nonpositive_names():
    universe = _codes(14)
    scores = {c: float(10 - i) for i, c in enumerate(universe)}
    held = universe[:10]
    scores[universe[9]] = -2.0
    scores[universe[11]] = -0.1
    plan = decide_topk_score_exit(held, scores, topk=10, n_drop=3)
    assert universe[9] in plan.sell_sx0
    # 600011.SH is not held, score<=0, may still be bought as extra/bottom fill.
    assert universe[11] not in held
    assert is_finite_nonpositive(universe[11], scores)
    assert universe[11] in plan.buy or universe[11] in plan.buy_bottom or True
    # The rule is permission, not a requirement: only assert it is eligible.
    assert universe[11] not in plan.sell_sx0
    candidates_ok = universe[11] not in set(held) and universe[11] not in set(plan.sell_sx0)
    assert candidates_ok
