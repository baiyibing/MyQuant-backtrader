"""Strategy book: TopkDropout overlay (not version6).

Sell = qlib-style bottom dropout + optional cost stop (BT-C). No trail take-profit.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from backtest.research.topk_dropout_rules import decide_topk_dropout

BOOK_TAG = "topk_dropout"
ALLOW_ADD = False
PEAK_GAP_MIN = 0
# BT-A: None. BT-C opens 0.10 on this book only — never touch version6 STOP_PCT.
STOP_PCT = None
DEFAULT_TOPK = 50
DEFAULT_N_DROP = 5

HELP_LOCK = """
策略 topk_dropout（--strategy topk_dropout / topk / version_topk）：
  底座 = qlib TopkDropout（method_buy=top / method_sell=bottom），对引擎实仓现算。
  不是 version6：无 trail 止盈；止损仅本书画布（BT-C 默认 10% 开仓价），不改 v6 的 6%。
  卖出 reason 前缀 topk_drop:bottom；止损仍用 stop_loss:touch / gap_open。
  排序与淘汰以 --pred-csv / --scores-dir 为准；--pool-dir 仍要（日历/契约），不以池 50 行当卖出。
  禁止「今日池 CSV 没有就清仓」；禁止读 live_pool/*sell.csv。
"""


def take_profit_reason(px, cost, peak, n_days) -> None:
    del px, cost, peak, n_days
    return None


def record_topk_dropout_params(
    st,
    *,
    stop_pct: Optional[float],
    topk: int,
    n_drop: int,
) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = stop_pct
    st.stats["topk"] = int(topk)
    st.stats["n_drop"] = int(n_drop)


def make_sell_gate(
    *,
    scores_by_day: Mapping[str, Mapping[str, float]],
    topk: int,
    n_drop: int,
    day_state: dict,
):
    """sell_gate using opening held snapshotted via bind_opening_held."""

    def sell_gate(code, px, day, daily_closes_ending_yesterday) -> Optional[str]:
        del px, daily_closes_ending_yesterday
        ds = _as_ymd(day)
        scores = scores_by_day.get(ds)
        if scores is None:
            raise RuntimeError(
                f"topk_dropout fail-closed: missing scores for buy-day {ds}"
            )
        held = day_state.get("opening_held") or ()
        if day_state.get("ds") != ds:
            # Opening held not bound for this day — refuse silent wrong sells.
            raise RuntimeError(
                f"topk_dropout fail-closed: opening held not bound for {ds}"
            )
        _buy, sell = decide_topk_dropout(held, scores, topk=topk, n_drop=n_drop)
        del _buy
        if code in sell:
            return "topk_drop:bottom"
        return None

    return sell_gate


def make_planned_for_day(
    *,
    scores_by_day: Mapping[str, Mapping[str, float]],
    topk: int,
    n_drop: int,
    eligible_buy=None,
):
    """Replace pool planned list with dropout buys (post-sell held).

    BT-B may pass ``eligible_buy(code, buy_date) -> bool`` and walk-down fill.
    """

    def planned_for_day(ds: str, held_codes: Sequence[str]) -> list[str]:
        scores = scores_by_day.get(ds)
        if scores is None:
            raise RuntimeError(
                f"topk_dropout fail-closed: missing scores for buy-day {ds}"
            )
        buy, _sell = decide_topk_dropout(
            held_codes, scores, topk=topk, n_drop=n_drop
        )
        if eligible_buy is None:
            return list(buy)
        held_set = set(held_codes)
        need = len(buy)
        out: list[str] = []
        # Walk score-desc non-held; skip ineligible (ST/age). Keep length ≤ need.
        from backtest.research.topk_dropout_rules import sort_by_score_desc

        candidates = sort_by_score_desc(
            [c for c in scores.keys() if c not in held_set], scores
        )
        for code in candidates:
            if len(out) >= need:
                break
            if not eligible_buy(code, ds):
                continue
            out.append(code)
        return out

    return planned_for_day


def make_bind_opening_held(day_state: dict):
    def bind_opening_held(ds: str, held_codes: Sequence[str]) -> None:
        day_state["ds"] = ds
        day_state["opening_held"] = tuple(held_codes)

    return bind_opening_held


def _as_ymd(day) -> str:
    if hasattr(day, "strftime"):
        return day.strftime("%Y%m%d")
    text = str(day).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:4] + text[5:7] + text[8:10]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    raise ValueError(f"cannot parse day as YYYYMMDD: {day!r}")
