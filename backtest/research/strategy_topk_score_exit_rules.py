"""Strategy book: TopkDropout + T6-SX0 non-positive score exit.

Control book ``topk_dropout`` stays unchanged. This book runs the same 10/3
bottom plan first, then extra-sells opening names whose aligned finite score
is <= 0, and fills leftover slots from the full-universe sidecar.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from backtest.research.topk_score_exit_rules import (
    decide_topk_score_exit,
    sell_reason,
)

BOOK_TAG = "topk_score_exit"
ALLOW_ADD = False
PEAK_GAP_MIN = 0
STOP_PCT = 0.10
DEFAULT_TOPK = 50
DEFAULT_N_DROP = 5
QLIB_CASH_DEPLOY = 0.95
QLIB_LIMIT_PCT = 0.095
SAME_BAR_PREFIXES = ("open_board", "topk_drop", "model_exit")

HELP_LOCK = """
策略 topk_score_exit（--strategy topk_score_exit）：
  底座与 topk_dropout 相同：method_buy=top / method_sell=bottom，n_drop 配额不改。
  唯一增量：开盘持仓若当日对齐有限 score<=0，额外卖出 reason=model_exit:nonpositive。
  禁止先 SX0 再重跑 dropout。额外空位按全日 scores sidecar 降序补到 topk。
  缺分/非有限分不触发 SX0。score==0 计入非正。不得买回当日 sell_sx0。
  可买入其他 score<=0 的股票。无 ST/年龄/15%/buy-state 新闸。
  --stop-pct 0 关闭止损。成交核（涨跌停/停牌/整手/费用）不变。
"""


def take_profit_reason(px, cost, peak, n_days) -> None:
    del px, cost, peak, n_days
    return None


def record_topk_score_exit_params(
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
    st.stats.setdefault("sx0_planned", 0)
    st.stats.setdefault("sx0_also_bottom_planned", 0)
    st.stats.setdefault("sx0_extra_buy_planned", 0)
    st.stats.setdefault("sx0_days", 0)


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


def _require_plan(day_state: dict, ds: str):
    if day_state.get("ds") != ds or "plan" not in day_state:
        raise RuntimeError(
            f"topk_score_exit fail-closed: opening held not bound for {ds}"
        )
    return day_state["plan"]


def _cache_opening_decision(
    day_state: dict,
    ds: str,
    held_codes: Sequence[str],
    scores: Mapping[str, float],
    *,
    topk: int,
    n_drop: int,
):
    plan = decide_topk_score_exit(held_codes, scores, topk=topk, n_drop=n_drop)
    day_state["ds"] = ds
    day_state["opening_held"] = tuple(held_codes)
    day_state["plan"] = plan
    day_state["buy"] = list(plan.buy)
    day_state["sell"] = list(plan.sell)
    hist = day_state.setdefault("history", [])
    hist.append(
        {
            "ds": ds,
            "sell_bottom": list(plan.sell_bottom),
            "sell_sx0": list(plan.sell_sx0),
            "also_bottom": list(plan.also_bottom),
            "buy_bottom": list(plan.buy_bottom),
            "buy_extra": list(plan.buy_extra),
            "buy": list(plan.buy),
        }
    )
    return plan


def make_sell_gate(
    *,
    scores_by_day: Mapping[str, Mapping[str, float]],
    topk: int,
    n_drop: int,
    day_state: dict,
):
    del scores_by_day, topk, n_drop

    def sell_gate(code, px, day, daily_closes_ending_yesterday) -> Optional[str]:
        del px, daily_closes_ending_yesterday
        ds = _as_ymd(day)
        plan = _require_plan(day_state, ds)
        return sell_reason(code, plan)

    return sell_gate


def make_planned_for_day(
    *,
    scores_by_day: Mapping[str, Mapping[str, float]],
    topk: int,
    n_drop: int,
    day_state: dict,
    eligible_buy=None,
):
    def planned_for_day(ds: str, held_codes: Sequence[str]) -> list[str]:
        scores = scores_by_day.get(ds)
        if scores is None:
            raise RuntimeError(
                f"topk_score_exit fail-closed: missing scores for buy-day {ds}"
            )
        if day_state.get("ds") == ds and "plan" in day_state:
            buy = list(day_state["plan"].buy)
        else:
            plan = decide_topk_score_exit(
                held_codes, scores, topk=topk, n_drop=n_drop
            )
            buy = list(plan.buy)
        if eligible_buy is None:
            return list(buy)
        held_set = set(held_codes)
        sx0_set = (
            set(day_state["plan"].sell_sx0)
            if day_state.get("ds") == ds and "plan" in day_state
            else set()
        )
        need = len(buy)
        out: list[str] = []
        from backtest.research.topk_dropout_rules import sort_by_score_desc

        candidates = sort_by_score_desc(
            [
                c
                for c in scores.keys()
                if c not in held_set and c not in sx0_set
            ],
            scores,
        )
        for code in candidates:
            if len(out) >= need:
                break
            if not eligible_buy(code, ds):
                continue
            out.append(code)
        return out

    return planned_for_day


def make_bind_opening_held(
    day_state: dict,
    scores_by_day: Mapping[str, Mapping[str, float]],
    topk: int,
    n_drop: int,
):
    def bind_opening_held(ds: str, held_codes: Sequence[str]) -> None:
        scores = scores_by_day.get(ds)
        if scores is None:
            raise RuntimeError(
                f"topk_score_exit fail-closed: missing scores for buy-day {ds}"
            )
        _cache_opening_decision(
            day_state, ds, held_codes, scores, topk=topk, n_drop=n_drop
        )

    return bind_opening_held
