"""BT-B: ST/age new-buy gate + walk-down; never sell solely for becoming ST."""

from __future__ import annotations

from datetime import date

from backtest.research.csv_strategy_books import apply_csv_strategy
from backtest.research.topk_dropout_eligibility import make_eligible_buy
from backtest.research.topk_dropout_rules import decide_topk_dropout


def test_walk_down_skips_st_first_candidate():
    day = "20260106"
    # Underfull: today wants 600010 then 600011; 600010 is ST → walk to 600011.
    scores = {
        "600000.SH": 10.0,  # held
        "600001.SH": 9.0,  # held
        "600010.SH": 8.0,  # would-be buy #1 but ST
        "600011.SH": 7.0,  # walk-down target
        "600012.SH": 6.0,
    }
    held = ["600000.SH", "600001.SH"]
    raw_buy, _sell = decide_topk_dropout(held, scores, topk=3, n_drop=1)
    assert raw_buy[0] == "600010.SH"

    eligible = make_eligible_buy(
        st_by_day={date(2026, 1, 6): {"600010.SH"}},
    )
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={day: scores},
        topk=3,
        n_drop=1,
        eligible_buy=eligible,
    )
    planned = hooks["planned_for_day"](day, held)
    assert planned[0] == "600011.SH"
    assert "600010.SH" not in planned
    assert len(planned) == len(raw_buy)


def test_age_gate_blocks_young_name():
    day = "20260106"
    scores = {
        "600000.SH": 10.0,
        "600001.SH": 9.0,
        "600020.SH": 8.0,  # too young
        "600021.SH": 7.0,
    }
    held = ["600000.SH"]
    eligible = make_eligible_buy(
        min_buy_ymd={"600020.SH": "20260301", "600021.SH": "20250101"},
    )
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={day: scores},
        topk=2,
        n_drop=1,
        eligible_buy=eligible,
    )
    planned = hooks["planned_for_day"](day, held)
    assert "600020.SH" not in planned
    assert planned[0] == "600021.SH"


def test_held_becoming_st_does_not_force_sell_gate():
    """ST alone must not produce topk_drop:bottom; only dropout sell set does."""
    day = "20260106"
    scores = {
        "600000.SH": 10.0,
        "600001.SH": 9.0,
        "600002.SH": 8.0,  # held, will be marked ST today
        "600003.SH": 0.1,  # true dog to sell
        "600004.SH": 7.0,
        "600005.SH": 6.5,
    }
    held = ["600000.SH", "600001.SH", "600002.SH", "600003.SH"]
    eligible = make_eligible_buy(st_by_day={date(2026, 1, 6): {"600002.SH"}})
    hooks = apply_csv_strategy(
        "topk_dropout",
        scores_by_day={day: scores},
        topk=3,
        n_drop=1,
        eligible_buy=eligible,
    )
    hooks["bind_opening_held"](day, held)
    assert hooks["sell_gate"]("600003.SH", 1.0, day, []) == "topk_drop:bottom"
    assert hooks["sell_gate"]("600002.SH", 1.0, day, []) is None
