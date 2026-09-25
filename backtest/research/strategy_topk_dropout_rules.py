"""Strategy book: TopkDropout overlay (not version6).

Sell = qlib-style bottom dropout + optional cost stop (BT-C). No trail take-profit.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from backtest.research.topk_dropout_rules import decide_topk_dropout

BOOK_TAG = "topk_dropout"
ALLOW_ADD = False
PEAK_GAP_MIN = 0
# BT-C: 10% cost stop on this book only — never touch version6 STOP_PCT=0.06.
STOP_PCT = 0.10
DEFAULT_TOPK = 50
DEFAULT_N_DROP = 5
# qlib BaseSignalStrategy.risk_degree default: deploy remaining cash * this / n_buy.
QLIB_CASH_DEPLOY = 0.95
# qlib exchange_kwargs.limit_threshold default (custom_train_backtest).
QLIB_LIMIT_PCT = 0.095
# Same-bar close sell for dropout (qlib deal_price=close). Default books only
# same-bar ``open_board``; without this prefix topk_drop pending-exits to next open.
SAME_BAR_PREFIXES = ("open_board", "topk_drop")

HELP_LOCK = """
策略 topk_dropout（--strategy topk_dropout / topk / version_topk）：
  底座 = qlib TopkDropout（method_buy=top / method_sell=bottom），对引擎实仓现算。
  开盘仓只 decide 一次：sell_gate 与 planned_for_day 共用那对 buy/sell（卖完不重算）。
  dropout 当日收盘卖（topk_drop 走 same-bar）；不是次日开盘 pending。
  涨跌停贴近 qlib：统一 |Δ|≥9.5% 当日买卖都不做（forbid_all_trade_at_limit）；
  不按板块 10/20/30，不追买，跌停不挂次日开盘。6/8 原语义不动。
  新买额度 = min(日额度, 现金) * 0.95 / n_buy（qlib risk_degree）。
  资金模式配对（plan-capital-pairing-2026-09-25）：本书族默认日额度 = --cash-total
  （qlib 原生现金部署）；不传 --daily-quota 即是。显式 --daily-quota 覆盖。
  不是 version6：无 trail 止盈；默认 10% 开仓价止损（stop_loss:touch / gap_open），不改 v6 的 6%。
  日线买与 dropout 卖本就按收盘。--stop-fill touch|close（默认 touch）只改止损成交：
  close = 日终收盘 ≤ cost×(1-p) 则按该收盘卖（含恰跌停，Q7）；同日止损先于 dropout。
  分钟入口拒绝 --stop-fill close（逐根 bar close ≠ 当日收盘）。
  --stop-pct 0 关闭止损（臂 0 / 对齐原生 Topk）。
  --return-threshold-filter 买入挡 5 日涨幅>15%（已加载日线收盘，T-1/T-6）；与 ST/年龄独立。
  --buy-state-file 新开买点旁路（MyQuant 导出 close/MA20/MA60/$winratio）：
  (close<MA20 且 close<MA60 且 winratio<0.10) 或 close>MA20；无 MA5 斜率；缺行/NaN fail-closed。
  盈筹 = 券商 $winratio，不是 CYQ parquet。topk_score_exit 拒绝此旗。默认不传=不滤。
  --buy-state-rule oral|above-ma20|above-ma20-week20|above-ma5-ma20-week20（默认 oral）。
  above-ma20 关掉盈筹抄底，只留 close>MA20；close=MA20 不买。
  above-ma20-week20 再要求 close>20 周均线。周线照 qlib：每周第一个交易日的收盘做 Mean($close, 20)，
  买入日沿用不晚于当日的最近一根。未满 20 周不买。用已加载的 day.bin 收盘，不 import qlib。
  above-ma5-ma20-week20 在此之上再要求 close>个股 5 日均线（含当日的 5 根收盘均值）。
  close=均线不买。未满 5 根不买。同样用已加载的日线收盘。分钟成交也可以用这几道日线闸。
  必须同时传 --buy-state-file。分钟拒绝 --stop-fill close。
  --keep-buy-vacancy 原买名单里没过 个股5日 / 20 日 / 20 周 / 上证 5 日线的不替补，名额空着。
  ST、年龄、15% 仍先滤名单并补满只数，和这个开关无关。
  当天资金按滤完名单的只数均分，均线空位的那一份留在现金里。默认关（关=按分数往下补）。
  --index-ma5-gate 新开闸（默认关）：全市场只看上证指数 000001.SH，不分板块。
  信号日=买入日前一根上证交易日。该日收盘 < 含当日的 5 日均线 → 下一交易日所有新开不买。
  收盘=均线不挡。指数缺前史或无正收盘 → 不买。不因此强卖已持仓。
  --dividend-type none|front|back 日线复权（默认 none）；front/back 不再做 E-R6 除权缩放。
  --qlib-data-root 读 qlib features/*.day.bin（$close 后复权）。成交热路径不挂 qlib 运行时；
  Mean($close, n) 用已加载收盘滚动均值，不是「算法不许像 qlib」。
  --qlib-cost 佣金对齐 qlib：买 5bp / 卖 15bp / 最低 5（默认仍是双边 10bp 无最低）。
  卖出 reason 前缀 topk_drop:bottom；止损 touch/gap_open，或 --stop-fill close → stop_loss:close。
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
    stop_fill: str = "touch",
) -> None:
    st.stats["sell_book"] = BOOK_TAG
    st.stats["stop_pct"] = stop_pct
    st.stats["topk"] = int(topk)
    st.stats["n_drop"] = int(n_drop)
    st.stats["stop_fill"] = str(stop_fill)


def _cache_opening_decision(
    day_state: dict,
    ds: str,
    held_codes: Sequence[str],
    scores: Mapping[str, float],
    *,
    topk: int,
    n_drop: int,
) -> tuple[list[str], list[str]]:
    buy, sell = decide_topk_dropout(held_codes, scores, topk=topk, n_drop=n_drop)
    day_state["ds"] = ds
    day_state["opening_held"] = tuple(held_codes)
    day_state["buy"] = list(buy)
    day_state["sell"] = list(sell)
    return list(buy), list(sell)


def make_sell_gate(
    *,
    scores_by_day: Mapping[str, Mapping[str, float]],
    topk: int,
    n_drop: int,
    day_state: dict,
):
    """sell_gate using the one-shot decide cached at bind_opening_held."""

    def sell_gate(code, px, day, daily_closes_ending_yesterday) -> Optional[str]:
        del px, daily_closes_ending_yesterday
        ds = _as_ymd(day)
        if day_state.get("ds") != ds or "sell" not in day_state:
            raise RuntimeError(
                f"topk_dropout fail-closed: opening held not bound for {ds}"
            )
        if code in day_state["sell"]:
            return "topk_drop:bottom"
        return None

    return sell_gate


def make_planned_for_day(
    *,
    scores_by_day: Mapping[str, Mapping[str, float]],
    topk: int,
    n_drop: int,
    day_state: dict,
    eligible_buy=None,
    keep_vacancy: bool = False,
):
    """Return the buy list from the opening decide (qlib one-shot).

    If bind_opening_held has not run (unit tests), fall back to decide(held).
    BT-B may pass ``eligible_buy(code, buy_date) -> bool``. Default walks down
    the score list to refill the same ``len(buy)``. ``keep_vacancy`` filters
    the original buy list only and records ``slot_count`` so the empty seat's
    cash is not spread across the names that remain.
    """

    def planned_for_day(ds: str, held_codes: Sequence[str]) -> list[str]:
        planned_for_day.slot_count = None
        scores = scores_by_day.get(ds)
        if scores is None:
            raise RuntimeError(
                f"topk_dropout fail-closed: missing scores for buy-day {ds}"
            )
        if day_state.get("ds") == ds and "buy" in day_state:
            buy = list(day_state["buy"])
        else:
            buy, _sell = decide_topk_dropout(
                held_codes, scores, topk=topk, n_drop=n_drop
            )
        if eligible_buy is None:
            return list(buy)
        if keep_vacancy:
            kept, slots = _vacancy_buys(buy, ds, scores, held_codes, eligible_buy)
            planned_for_day.slot_count = slots
            return kept
        held_set = set(held_codes)
        need = len(buy)
        out: list[str] = []
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


def _vacancy_buys(
    buy: Sequence[str],
    ds: str,
    scores: Mapping[str, float],
    held_codes: Sequence[str],
    eligible_buy,
    extra_skip: Sequence[str] = (),
) -> tuple[list[str], int]:
    """ST / age / 15% refill the roster. Seat gates then leave holes.

    ``list_ok`` (ST, listing age, and the 15% wrapper) walks down so the
    original buy count stays filled. ``seat_ok`` (MA20, 20-week, index MA5)
    drops names without a further substitute. Returned slot count is the
    roster length before the seat drop, so that cash stays unspent.
    """
    list_ok = getattr(eligible_buy, "list_ok", None)
    seat_ok = getattr(eligible_buy, "seat_ok", None)
    if list_ok is None and seat_ok is None:
        kept = [code for code in buy if eligible_buy(code, ds)]
        return kept, len(buy)
    from backtest.research.topk_dropout_rules import sort_by_score_desc

    skip = set(held_codes) | set(extra_skip)
    candidates = sort_by_score_desc([c for c in scores.keys() if c not in skip], scores)
    roster: list[str] = []
    need = len(buy)
    for code in candidates:
        if len(roster) >= need:
            break
        if list_ok is not None and not list_ok(code, ds):
            continue
        roster.append(code)
    if seat_ok is None:
        return roster, len(roster)
    return [code for code in roster if seat_ok(code, ds)], len(roster)


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
                f"topk_dropout fail-closed: missing scores for buy-day {ds}"
            )
        _cache_opening_decision(
            day_state, ds, held_codes, scores, topk=topk, n_drop=n_drop
        )

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
