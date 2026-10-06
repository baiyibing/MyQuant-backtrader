"""V7 native state, accounting and single-event book callbacks.

Both native schedules belong to main/minute_cash_order.
Input adapters may traverse records; accounting may traverse lots. Production
callbacks consume one symbol preparation or one row event, never schedule days.
simulate_native validates and normalizes tail options before translating native
arguments to the registered main book.
"""
from __future__ import annotations

from backtest.research.lot_rounding import (
    BOARD_BUY_QUANTITY,
    budget_buy_quantity,
    buy_quantity_increment,
    buy_quantity_minimum,
    buy_quantity_rule,
    native_budget_board_lots,
)
from math import isfinite
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping, Sequence
from backtest.research.ashare_fees import DEFAULT_SCHEDULE, FeeSchedule
from backtest.research.csv_ledger import (
    _accrue_order_fee,
    account_sell_quantity,
    fee_order_id,
    preview_order_fees,
    release_fee_order,
)
from backtest.research.ashare_volume_cap import VolumeCap, VolumeLookup
from backtest.research.ashare_exdiv_economics import ExDivEconomics, EconomicLookup
from backtest.research.market_layer import (
    as_date as _as_date,
    as_datetime as _as_datetime,
    buy_quantity_market,
)
from backtest.research.rule_profile import RuleProfile, resolve_rule_profile
from backtest.research.strategy7_rules import (
    TRIAL, FOUR, SIX, EIGHT, FULL, TRIAL_FRACTION, build_index_gate,
    in_add_window, ladder_decision, stop_decision, timer_due,
)
from backtest.research.ashare_session import (
    t1_sellable, k_for, asof_pool_name, session_prev_close,
    session_limit_prices, skip_buy_at_limit, defer_sell_at_limit,
)
from backtest.research.minute_audit import record_fill, audit_scope
from backtest.research.tail_window_buy import (
    TAIL_MINUTES,
    TailParent,
    fee_aware_buy_quantity,
    tail_quote,
)
from oskh_data.symbol_format import to_canonical_symbol

NAME_BUDGET = 1_000_000.0


@dataclass
class Lot:
    shares: int
    buy_date: date
    price: float
    kind: str


@dataclass
class Position:
    symbol: str
    entry_A: float
    stage: str = TRIAL
    add1_A1: float | None = None
    lots: list[Lot] = field(default_factory=list)
    avg_cost: float = 0.0
    last_add_date: date | None = None
    peak: float = 0.0

    @property
    def shares(self) -> int:
        return sum(lot.shares for lot in self.lots)


@dataclass
class SimResult:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    volume_cap: VolumeCap | None = field(default=None, repr=False, compare=False)
    exdiv_economics: ExDivEconomics | None = field(default=None, repr=False, compare=False)


def _record_stamp(record: Mapping[str, Any]) -> Any:
    for key in ("datetime", "timestamp", "date", "time"):
        if key in record and record[key] is not None:
            return record[key]
    return None


def _record_dict(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    if hasattr(record, "_asdict"):
        return dict(record._asdict())
    return dict(vars(record))


def _minute_records(minute_bars: Any) -> dict[date, dict[str, list[dict[str, Any]]]]:
    """Accept symbol->records, day->symbol->records, or a flat record iterable."""
    out: dict[date, dict[str, list[dict[str, Any]]]] = {}
    if minute_bars is None:
        return out
    flat: list[dict[str, Any]] = []
    if isinstance(minute_bars, Mapping):
        for key, value in minute_bars.items():
            if isinstance(value, Mapping) and not any(k in value for k in ("close", "open", "datetime", "date")):
                day = _as_date(key)
                for symbol, records in value.items():
                    for record in _iter_records(records):
                        record.setdefault("date", day)
                        record.setdefault("symbol", symbol)
                        flat.append(record)
            else:
                for record in _iter_records(value):
                    record.setdefault("symbol", key)
                    flat.append(record)
    else:
        flat = list(_iter_records(minute_bars))
    for record in flat:
        stamp = _record_stamp(record)
        if stamp is None:
            raise ValueError("minute record requires datetime/timestamp/date/time")
        parsed = _as_datetime(stamp)
        day = parsed.date()
        if "hm" not in record:
            record["hm"] = int(parsed.hour) * 60 + int(parsed.minute)
        symbol = to_canonical_symbol(str(record["symbol"]))
        record["symbol"] = symbol
        record["date"] = day
        out.setdefault(day, {}).setdefault(symbol, []).append(record)
    for symbols in out.values():
        for records in symbols.values():
            records.sort(key=lambda row: int(row["hm"]))
    return out


def _iter_records(value: Any) -> Iterable[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        try:
            value = value.to_dict("records")
        except TypeError:
            pass
    if isinstance(value, Mapping):
        value = [value]
    for record in value or []:
        yield _record_dict(record)


def _daily_closes(daily_bars: Any) -> dict[str, dict[date, float]]:
    out: dict[str, dict[date, float]] = {}
    if not daily_bars:
        return out
    if isinstance(daily_bars, Mapping):
        for symbol, records in daily_bars.items():
            canonical = to_canonical_symbol(str(symbol))
            if hasattr(records, "empty") and hasattr(records, "columns") and "close" in getattr(records, "columns", ()):
                for ts, close in records["close"].items():
                    out.setdefault(canonical, {})[_as_date(ts)] = float(close)
            elif isinstance(records, Mapping) and "close" not in records:
                for day, close in records.items():
                    out.setdefault(canonical, {})[_as_date(day)] = float(close)
            else:
                for row in _iter_records(records):
                    stamp = _record_stamp(row)
                    if stamp is None:
                        raise ValueError("daily record requires date/datetime/time")
                    out.setdefault(canonical, {})[_as_date(stamp)] = float(row["close"])
    return out


def _pool(pool_days: Mapping[Any, Sequence[str]] | None) -> dict[date, list[str]]:
    return {
        _as_date(day): [to_canonical_symbol(str(symbol)) for symbol in symbols]
        for day, symbols in (pool_days or {}).items()
    }


def _rescale_position(position: Position, k: float) -> None:
    factor = float(k)
    if factor <= 0:
        return
    position.entry_A *= factor
    position.avg_cost *= factor
    position.peak *= factor
    if position.add1_A1 is not None:
        position.add1_A1 *= factor
    position.lots = [Lot(lot.shares, lot.buy_date, lot.price * factor, lot.kind) for lot in position.lots]


def _apply_exdiv_economics(state: SimResult, position: Position, ds: str) -> None:
    account = state.exdiv_economics
    if account is None:
        return
    lots = list(position.lots)
    entitlement = account.entitle(position.symbol, ds, [lot.shares for lot in lots])
    if entitlement is None:
        return
    # Separate entitlement lots reuse the source reference price; buy_date is
    # list_date, so the existing t1_sellable gate protects all new shares.
    position.lots.extend(
        Lot(added, _as_date(entitlement.list_date), lot.price, "exdiv_bonus")
        for lot, added in zip(lots, entitlement.bonus_shares) if added
    )
    state.cash += account.settle(ds)


def _event(state: SimResult, day: date, symbol: str, hm: int | None, side: str, shares: int,
           price: float | None, reason: str, *, cash_before: float | None = None,
           order_id=None) -> None:
    trade = {"date": day.isoformat(), "symbol": symbol, "hm": hm, "side": side,
             "shares": shares, "price": price, "reason": reason}
    if getattr(
        getattr(state, "account_fee_schedule", None), "dated_sell_stamp_duty", False
    ):
        trade.update(
            notional=shares * price if price is not None else 0.0,
            commission=0.0,
            stamp_duty=0.0,
        )
    if getattr(
        getattr(state, "account_fee_schedule", None),
        "dated_bilateral_transfer_fee",
        False,
    ):
        trade["transfer_fee"] = 0.0
    if order_id is not None and price is not None:
        trade.update(notional=shares * price, commission=0.0)
    state.trades.append(trade)
    commission = 0.0
    if order_id is not None:
        commission = _accrue_order_fee(state, side.upper(), order_id, trade)
    elif cash_before is not None and price is not None:
        if side == "buy":
            commission = cash_before - state.cash - shares * price
        elif side == "sell":
            commission = shares * price - (state.cash - cash_before)
    audit_trade = (
        state.trades[-1]
        if order_id is not None
        else {**state.trades[-1], "commission": commission}
    )
    record_fill(
        state, audit_trade, state.cash if cash_before is None else cash_before
    )


def _buy(state: SimResult, position: Position | None, symbol: str, day: date, hm: int,
         price: float, fraction: float, reason: str, kind: str,
         fee: FeeSchedule = DEFAULT_SCHEDULE) -> Position | None:
    target = NAME_BUDGET * fraction
    profile = getattr(state, "rule_profile", None)
    quantity_rule = buy_quantity_rule(
        buy_quantity_market(symbol),
        exchange_quantity_rules=bool(
            getattr(profile, "exchange_quantity_rules", False)
        ),
    )
    shares = (
        native_budget_board_lots(target, price)
        if quantity_rule == BOARD_BUY_QUANTITY
        else budget_buy_quantity(target, price, quantity_rule)
    )
    if getattr(
        profile, "fee_aware_affordability", False
    ):
        shrink_short_cash = bool(
            getattr(profile, "shrink_on_short_cash", False)
        )
        shares = fee_aware_buy_quantity(
            shares,
            price,
            target,
            state.cash if shrink_short_cash else target,
            lambda notional: fee.debit_buy(notional, day, symbol),
            increment=buy_quantity_increment(quantity_rule),
            minimum=buy_quantity_minimum(quantity_rule),
        )
    order_id = fee_order_id(state)
    if order_id is None:
        cost = fee.debit_buy(shares * price)
    else:
        cost = shares * price + preview_order_fees(
            state, "BUY", order_id, shares * price, day, symbol
        )
    if shares < buy_quantity_minimum(quantity_rule) or cost > state.cash:
        _event(state, day, symbol, hm, "skip", 0, price, "skip_cash")
        return None
    if state.volume_cap is not None:
        key = (symbol, day.strftime("%Y%m%d"), hm)
        shares, skip = state.volume_cap.clamp(key, hm, shares, buy=True)
        if not shares:
            _event(state, day, symbol, hm, "skip", 0, price, skip)
            return None
        if order_id is None:
            cost = fee.debit_buy(shares * price)
        else:
            cost = shares * price + preview_order_fees(
                state, "BUY", order_id, shares * price, day, symbol
            )
    cash_before = state.cash
    state.cash -= cost
    if position is None:
        position = Position(symbol=symbol, entry_A=price, last_add_date=day)
        state.positions[symbol] = position
    old_shares = position.shares
    position.avg_cost = ((position.avg_cost * old_shares) + price * shares) / (old_shares + shares)
    position.lots.append(Lot(shares, day, price, kind))
    position.last_add_date = day
    _event(
        state, day, symbol, hm, "buy", shares, price, reason,
        cash_before=cash_before, order_id=order_id,
    )
    if state.volume_cap is not None:
        state.volume_cap.consume(key, shares)
    return position


def _sell_lots(state: SimResult, position: Position, day: date, hm: int, price: float,
               reason: str, *, kind: str | None = None,
               fee: FeeSchedule = DEFAULT_SCHEDULE, at: int | None = None) -> int:
    wanted = sum(
        lot.shares for lot in position.lots
        if t1_sellable(lot.buy_date, day) and (kind is None or lot.kind == kind)
    )
    if wanted <= 0:
        return 0
    adjusted = account_sell_quantity(state, position.symbol, position.shares, wanted)
    include_other_kinds = adjusted > wanted and sum(
        lot.shares for lot in position.lots if t1_sellable(lot.buy_date, day)
    ) >= adjusted
    if include_other_kinds:
        wanted = adjusted
    order_key = ("v7-sell", id(position), reason, kind)
    order_id = fee_order_id(state, order_key)
    requested = wanted
    if state.volume_cap is not None:
        key = (position.symbol, day.strftime("%Y%m%d"), hm)
        wanted, skip = state.volume_cap.clamp(key, hm if at is None else at, wanted)
        if not wanted:
            _event(state, day, position.symbol, hm, "skip", 0, price, skip)
            return 0
    remaining = wanted
    kept: list[Lot] = []
    for lot in position.lots:
        eligible = t1_sellable(lot.buy_date, day) and (
            include_other_kinds or kind is None or lot.kind == kind
        )
        take = min(lot.shares, remaining) if eligible else 0
        if lot.shares > take:
            kept.append(Lot(lot.shares - take, lot.buy_date, lot.price, lot.kind))
        remaining -= take
    sold = wanted - remaining
    position.lots = kept
    cash_before = state.cash
    if order_id is None:
        state.cash += fee.credit_sell(sold * price)
    else:
        fee_delta = preview_order_fees(
            state, "SELL", order_id, sold * price, day, position.symbol
        )
        state.cash += sold * price - fee_delta
    _event(
        state, day, position.symbol, hm, "sell", sold, price, reason,
        cash_before=cash_before, order_id=order_id,
    )
    if order_id is not None and sold >= requested:
        release_fee_order(state, order_key)
    if state.volume_cap is not None:
        state.volume_cap.consume(key, sold)
    if position.shares:
        position.avg_cost = sum(l.price * l.shares for l in position.lots) / position.shares
    else:
        state.positions.pop(position.symbol, None)
    return sold


def _buy_tail_slice(state: SimResult, parent: TailParent, symbol: str, day: date,
                    hm: int, row: Mapping[str, Any], volume_unit: str,
                    fee: FeeSchedule) -> None:
    quote = tail_quote(row, hm, volume_unit)
    if quote is None:
        _event(state, day, symbol, hm, "skip", 0, None, "skip_tail_quote")
        return
    debit = lambda value: fee.debit_buy(value, day, symbol)
    fee_aware = getattr(
        getattr(state, "rule_profile", None), "fee_aware_affordability", False
    )
    shares = parent.allocation(
        quote,
        state.cash,
        debit,
        budget_debit_fn=debit if fee_aware else None,
    )
    if not shares:
        _event(state, day, symbol, hm, "skip", 0, quote.price, "skip_tail_allocation")
        return
    if state.volume_cap is not None:
        key = (symbol, day.strftime("%Y%m%d"), hm)
        shares, skip = state.volume_cap.clamp(key, hm, shares, buy=True)
        if not shares:
            _event(state, day, symbol, hm, "skip", 0, quote.price, skip)
            return
    order_id = fee_order_id(state)
    cash_before = state.cash
    if order_id is None:
        state.cash -= fee.debit_buy(shares * quote.price)
    else:
        fee_delta = preview_order_fees(
            state, "BUY", order_id, shares * quote.price, day, symbol
        )
        state.cash -= shares * quote.price + fee_delta
    position = state.positions.get(symbol)
    if position is None:
        position = Position(symbol=symbol, entry_A=quote.price, last_add_date=day,
                            peak=quote.price)
        state.positions[symbol] = position
    previous_shares = position.shares
    position.avg_cost = (position.avg_cost * previous_shares + quote.price * shares) / (previous_shares + shares)
    trial_lot = next((lot for lot in position.lots if lot.buy_date == day and lot.kind == "trial"), None)
    if trial_lot is None:
        position.lots.append(Lot(shares, day, quote.price, "trial"))
    else:
        trial_lot.price = (trial_lot.price * trial_lot.shares + quote.price * shares) / (trial_lot.shares + shares)
        trial_lot.shares += shares
    position.last_add_date = day
    # Merged T+0 children change size and weighted cost, never the initial peak.
    parent.book(shares, quote.price, debit if fee_aware else None)
    _event(
        state, day, symbol, hm, "buy", shares, quote.price, "buy:trial",
        cash_before=cash_before, order_id=order_id,
    )
    if state.volume_cap is not None:
        state.volume_cap.consume(key, shares)


def _is_frame_map(minute_bars: Any) -> bool:
    if not isinstance(minute_bars, Mapping) or not minute_bars:
        return False
    sample = next(iter(minute_bars.values()))
    return hasattr(sample, "loc") and hasattr(sample, "columns")


def _day_frame_records(frame: Any, day: date) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    # Slice A frame contract (b): accept book ymd/DatetimeIndex here;
    # qlib_1min keeps its compact date column. Materialize only the needed day.
    if "ymd" in frame.columns:
        sl = frame.loc[frame["ymd"] == day.strftime("%Y%m%d")]
    elif "date" in frame.columns:
        sl = frame.loc[frame["date"] == day]
    else:
        sl = frame.loc[frame.index.date == day]
    if sl.empty:
        return []
    return sl.to_dict("records")


def prepare_calendar(index_days, frames, minutes, pools, start=None, end=None):
    gate: dict[date, bool] = {}
    if isinstance(index_days, Mapping):
        index_closes = {_as_date(day): float(close) for day, close in index_days.items()}
        gate = build_index_gate(index_closes)
        calendar = sorted(gate)
    elif index_days:
        calendar = sorted(_as_date(day) for day in index_days)
    elif frames is not None:
        calendar = sorted({_as_date(stamp) for frame in frames.values()
                           for stamp in frame.index} | set(pools))
    else:
        calendar = sorted(set(minutes) | set(pools))
    if start is not None:
        calendar = [day for day in calendar if day >= _as_date(start)]
    if end is not None:
        calendar = [day for day in calendar if day <= _as_date(end)]
    if isinstance(index_days, Mapping) and any(day not in gate for day in calendar):
        raise ValueError("index closes lack the required 11-session gate warmup")

    return calendar, gate


@dataclass(frozen=True)
class StopCandidate:
    price: float
    phase: str
    reason: str
    at: int


class MinuteSession:
    """Native v7 decisions; caller owns row order and audit phase scopes."""

    @staticmethod
    def observe_row(state, symbol, row, last_prices):
        open_px = float(row.get("open", row["close"]))
        close_px = float(row["close"])
        high_px = float(row.get("high", max(open_px, close_px)))
        last_prices[symbol] = close_px

        return open_px, close_px, high_px

    @staticmethod
    def stop(state, position, symbol, day, hm, first, open_px, close_px,
             high_px, previous, limits, fee, audit_sink):
        position.peak = max(position.peak, high_px)
        candidate = MinuteSession.stop_candidate(position, hm, first, open_px, close_px)
        if candidate is not None:
            with audit_scope(audit_sink, decision_hm=hm, phase=candidate.phase):
                if limits is None:
                    _event(state, day, symbol, hm, "skip", 0, candidate.price,
                           "skip_no_prev_close" if previous is None else "skip_unknown_board")
                elif defer_sell_at_limit(candidate.price, limits):
                    _event(state, day, symbol, hm, "defer", 0, candidate.price, "defer_limit_down")
                else:
                    _sell_lots(state, position, day, hm, candidate.price,
                               candidate.reason, fee=fee,
                               **({"at": candidate.at} if state.volume_cap is not None else {}))

    @staticmethod
    def stop_candidate(position, hm, first, open_px, close_px):
        decision = stop_decision(position.stage, entry_a=position.entry_A,
                                 average_cost=position.avg_cost)
        gap_open = first and decision.line is not None and open_px <= decision.line
        check_px = open_px if gap_open else close_px
        if not (decision.line is not None and check_px <= decision.line):
            return None
        reasons = {
            "dump_trial": "stop:trial_a090", "clear_four": "stop:four_avg095",
            "clear_six": "stop:six_avg0965", "clear_eight": "stop:eight_avg0975",
            "clear_full": "stop:full_avg098",
        }
        return StopCandidate(check_px, "open" if gap_open else "close",
                             reasons.get(decision.action, f"stop:{decision.action}"),
                             hm - 1 if gap_open else hm)

    @staticmethod
    def add(state, position, symbol, day, hm, close_px, previous, limits, fee):
        if position is not None and in_add_window(hm):
            ladder = ladder_decision(position.stage, close_px, entry_a=position.entry_A)
            reasons = {
                "add_a104": "buy:add_a104",
                "add_a108": "buy:add_a108",
                "add_a112": "buy:add_a112",
                "add_a116": "buy:add_a116",
            }
            if ladder.action != "none":
                if limits is None:
                    _event(state, day, symbol, hm, "skip", 0, close_px,
                           "skip_no_prev_close" if previous is None else "skip_unknown_board")
                elif skip_buy_at_limit(close_px, limits):
                    _event(state, day, symbol, hm, "skip", 0, close_px, "skip_limit_up")
                elif defer_sell_at_limit(close_px, limits):
                    pass
                elif _buy(state, position, symbol, day, hm, close_px, ladder.fraction,
                          reasons[ladder.action], ladder.action, fee=fee):
                    if ladder.action == "add_a104":
                        position.stage = FOUR
                    elif ladder.action == "add_a108":
                        position.stage = SIX
                    elif ladder.action == "add_a112":
                        position.stage = EIGHT
                    elif ladder.action == "add_a116":
                        position.stage = FULL

    @staticmethod
    def trial(state, symbol, day, hm, close_px, blocked_new, previous, name, fee):
        if blocked_new:
            _event(state, day, symbol, hm, "skip", 0, close_px, "skip_index_gate")
        elif previous is None:
            _event(state, day, symbol, hm, "skip", 0, close_px, "skip_no_prev_close")
        else:
            priced = session_limit_prices(symbol, previous, name, as_of=day)
            if priced is None:
                _event(state, day, symbol, hm, "skip", 0, close_px, "skip_unknown_board")
            else:
                if skip_buy_at_limit(close_px, priced):
                    _event(state, day, symbol, hm, "skip", 0, close_px, "skip_limit_up")
                elif not defer_sell_at_limit(close_px, priced):
                    _buy(state, None, symbol, day, hm, close_px, TRIAL_FRACTION, "buy:trial", "trial",
                         fee=fee)

    @staticmethod
    def timer(state, symbol, day, hm, close_px, calendar, previous, limits, fee, cleared_today):
        position = state.positions.get(symbol)
        if (position is not None and position.last_add_date is not None
                and timer_due(calendar, position.last_add_date, day, position.stage)):
            if limits is None:
                _event(state, day, symbol, hm, "skip", 0, close_px,
                       "skip_no_prev_close" if previous is None else "skip_unknown_board")
            elif defer_sell_at_limit(close_px, limits):
                _event(state, day, symbol, hm, "defer", 0, close_px, "defer_limit_down")
            elif _sell_lots(state, position, day, hm, close_px, "exit:timer10", fee=fee):
                if symbol not in state.positions:
                    cleared_today.add(symbol)

    @staticmethod
    def begin_symbol(state, symbol, day, closes, exdiv, names, names_by_day):
        ymd = day.strftime("%Y%m%d")
        factor = k_for(exdiv, symbol, ymd)
        position = state.positions.get(symbol)
        if position is not None:
            _apply_exdiv_economics(state, position, ymd)
        if factor is not None and position is not None:
            _rescale_position(position, factor)
        if names_by_day is not None:
            name = asof_pool_name(names_by_day, ymd, symbol)
        else:
            name = (names or {}).get(symbol, "")
        previous = session_prev_close(closes.get(symbol, {}), day, symbol, exdiv)
        limits = session_limit_prices(symbol, previous, name, as_of=day)

        return previous, limits, name

    @staticmethod
    def finish_symbol(state, symbol, day, in_pool, open_checked, records):
        if in_pool and symbol not in state.positions and not open_checked:
            if not any(int(row["hm"]) == 895 for row in records):
                _event(state, day, symbol, None, "skip", 0, None, "skip_no_1455")

    buy_tail_slice = staticmethod(_buy_tail_slice)

    @staticmethod
    def write_artifacts(state, output_dir):
        from backtest.research.csv_minute_backtest_v7 import write_run_artifacts
        write_run_artifacts(state, output_dir)


class AccountingPolicy:
    """Native lot ledger, aggregate fees and persistent minute-close marks."""

    buy = staticmethod(_buy)
    sell_lots = staticmethod(_sell_lots)
    buy_tail_slice = staticmethod(_buy_tail_slice)
    rescale_position = staticmethod(_rescale_position)
    apply_exdiv_economics = staticmethod(_apply_exdiv_economics)

    @staticmethod
    def settle_day(state, day):
        if state.exdiv_economics is not None:
            state.cash += state.exdiv_economics.settle(day.strftime("%Y%m%d"))

    @staticmethod
    def append_equity(state, day, last_prices):
        holdings = sum(pos.shares * last_prices.get(symbol, pos.avg_cost) for symbol, pos in state.positions.items())
        equity = state.cash + holdings
        if state.exdiv_economics is not None:
            equity += state.exdiv_economics.receivable_total
        state.equity_curve.append({"date": day.isoformat(), "cash": state.cash,
                                   "holdings": holdings, "equity": equity})


def prepare_main_inputs(minute_bars, daily_bars, pool_days, start, end, context):
    """Conversion only; main owns state construction and day advancement."""
    frames = minute_bars if _is_frame_map(minute_bars) else None
    minutes = {} if frames is not None else _minute_records(minute_bars)
    closes = _daily_closes(daily_bars)
    pools = _pool(pool_days)
    calendar, gate = prepare_calendar(
        context.index_days if context else None, frames, minutes, pools, start, end)
    return frames, minutes, closes, pools, calendar, gate


def minute_hooks(**kwargs):
    from backtest.research.minute_engine_policies import MinuteEnginePolicy
    return {"minute_session": MinuteSession,
            "minute_policy": MinuteEnginePolicy(
                schedule="chronological" if kwargs.get("fix_minute_cash_order") else "symbol_major",
                day_start=_main_day_start,
                append_marks=_main_append_marks, writer=MinuteSession.write_artifacts),
            "on_short_cash": "skip", "name": "version7", "sizing": "per_name"}


def _main_day_start(state, *, day, **kwargs):
    AccountingPolicy.settle_day(state, day)


def _main_append_marks(state, *, day, last_prices, **kwargs):
    AccountingPolicy.append_equity(state, day, last_prices)


def chronological_stop(
    state, cursor, index, row, phase, stopped_rows, day, hm, audit_sink, fee, cleared_today,
):
    symbol = cursor.symbol
    position = state.positions[symbol]
    decision = stop_decision(position.stage, entry_a=position.entry_A,
                             average_cost=position.avg_cost)
    open_px, close_px = float(row.get("open", row["close"])), float(row["close"])
    gap_open = index == 0 and decision.line is not None and open_px <= decision.line
    if phase != ("open" if gap_open else "close"):
        return
    check_px = open_px if gap_open else close_px
    if decision.line is None or check_px > decision.line:
        return
    stopped_rows.add((symbol, index))
    with audit_scope(audit_sink, decision_hm=hm, phase=phase):
        if cursor.limits is None:
            _event(state, day, symbol, hm, "skip", 0, check_px,
                   "skip_no_prev_close" if cursor.previous is None else "skip_unknown_board")
        elif defer_sell_at_limit(check_px, cursor.limits):
            _event(state, day, symbol, hm, "defer", 0, check_px, "defer_limit_down")
        else:
            reasons_stop = {
                "dump_trial": "stop:trial_a090", "clear_four": "stop:four_avg095",
                "clear_six": "stop:six_avg0965", "clear_eight": "stop:eight_avg0975",
                "clear_full": "stop:full_avg098",
            }
            _sell_lots(state, position, day, hm, check_px,
                       reasons_stop.get(decision.action, f"stop:{decision.action}"),
                       fee=fee, at=hm - 1 if gap_open else hm)
    if symbol not in state.positions:
        cleared_today.add(symbol)


def chronological_parent(
    state, cursor, row, day, hm, duplicate_tail_symbols, blocked_new, tail_parents, audit_sink,
):
    symbol = cursor.symbol
    cursor.open_checked = True
    with audit_scope(audit_sink, decision_hm=hm, phase="open"):
        if symbol in duplicate_tail_symbols:
            _event(state, day, symbol, hm, "skip", 0, None, "skip_duplicate_tail_start")
        elif blocked_new:
            _event(state, day, symbol, hm, "skip", 0, None, "skip_index_gate")
        elif cursor.previous is None:
            _event(state, day, symbol, hm, "skip", 0, None, "skip_no_prev_close")
        elif cursor.limits is None:
            _event(state, day, symbol, hm, "skip", 0, None, "skip_unknown_board")
        else:
            try:
                opening = float(row["open"])
            except (KeyError, TypeError, ValueError):
                opening = 0.0
            if isfinite(opening) and opening > 0:
                profile = getattr(state, "rule_profile", None)
                quantity_rule = buy_quantity_rule(
                    buy_quantity_market(symbol),
                    exchange_quantity_rules=bool(
                        getattr(profile, "exchange_quantity_rules", False)
                    ),
                )
                tail_parents[symbol] = TailParent.from_budget(
                    NAME_BUDGET * TRIAL_FRACTION,
                    opening,
                    declaration_increment=buy_quantity_increment(quantity_rule),
                    declaration_minimum=buy_quantity_minimum(quantity_rule),
                )
            else:
                _event(state, day, symbol, hm, "skip", 0, None, "skip_no_tail_start")


def chronological_buy(
    state, cursor, row, day, hm, audit_sink, tail_window_buy, tail_parents, tail_attempted,
    duplicate_tail_symbols, tail_volume_unit, fee, pool, cleared_today, blocked_new,
):
    symbol, close_px = cursor.symbol, float(row["close"])
    with audit_scope(audit_sink, decision_hm=hm, phase="close"):
        if (tail_window_buy and hm in TAIL_MINUTES and symbol in tail_parents
                and (symbol, hm) not in tail_attempted):
            tail_attempted.add((symbol, hm))
            quote = (None if symbol in duplicate_tail_symbols
                     else tail_quote(row, hm, tail_volume_unit))
            if symbol in duplicate_tail_symbols:
                _event(state, day, symbol, hm, "skip", 0, None, "skip_duplicate_tail_bar")
            elif quote is not None and skip_buy_at_limit(quote.price, cursor.limits):
                _event(state, day, symbol, hm, "skip", 0, quote.price, "skip_limit_up")
            elif quote is not None and defer_sell_at_limit(quote.price, cursor.limits):
                _event(state, day, symbol, hm, "skip", 0, quote.price, "skip_limit_down")
            else:
                _buy_tail_slice(state, tail_parents[symbol], symbol, day, hm, row, tail_volume_unit, fee)
        position = state.positions.get(symbol)
        if position is not None and in_add_window(hm):
            ladder = ladder_decision(position.stage, close_px, entry_a=position.entry_A)
            if ladder.action != "none":
                if cursor.limits is None:
                    _event(state, day, symbol, hm, "skip", 0, close_px,
                           "skip_no_prev_close" if cursor.previous is None else "skip_unknown_board")
                elif skip_buy_at_limit(close_px, cursor.limits):
                    _event(state, day, symbol, hm, "skip", 0, close_px, "skip_limit_up")
                elif (not defer_sell_at_limit(close_px, cursor.limits)
                      and _buy(state, position, symbol, day, hm, close_px, ladder.fraction,
                               f"buy:{ladder.action}", ladder.action, fee=fee)):
                    position.stage = {"add_a104": FOUR, "add_a108": SIX,
                                      "add_a112": EIGHT, "add_a116": FULL}[ladder.action]
        if (not tail_window_buy and hm == 895 and symbol in pool and symbol not in state.positions
                and symbol not in cleared_today):
            cursor.open_checked = True
            if blocked_new:
                _event(state, day, symbol, hm, "skip", 0, close_px, "skip_index_gate")
            elif cursor.previous is None:
                _event(state, day, symbol, hm, "skip", 0, close_px, "skip_no_prev_close")
            elif cursor.limits is None:
                _event(state, day, symbol, hm, "skip", 0, close_px, "skip_unknown_board")
            elif skip_buy_at_limit(close_px, cursor.limits):
                _event(state, day, symbol, hm, "skip", 0, close_px, "skip_limit_up")
            elif not defer_sell_at_limit(close_px, cursor.limits):
                _buy(state, None, symbol, day, hm, close_px, TRIAL_FRACTION,
                     "buy:trial", "trial", fee=fee)


def chronological_timer(state, cursor, row, day, hm, calendar, audit_sink, fee, cleared_today):
    symbol, close_px = cursor.symbol, float(row["close"])
    position = state.positions.get(symbol)
    if (position is None or position.last_add_date is None
            or not timer_due(calendar, position.last_add_date, day, position.stage)):
        return
    with audit_scope(audit_sink, decision_hm=hm, phase="timer"):
        if cursor.limits is None:
            _event(state, day, symbol, hm, "skip", 0, close_px,
                   "skip_no_prev_close" if cursor.previous is None else "skip_unknown_board")
        elif defer_sell_at_limit(close_px, cursor.limits):
            _event(state, day, symbol, hm, "defer", 0, close_px, "defer_limit_down")
        elif (_sell_lots(state, position, day, hm, close_px, "exit:timer10", fee=fee)
              and symbol not in state.positions):
            cleared_today.add(symbol)


# Single-event phase decisions selected by the registered native session.
MinuteSession.chronological_stop = staticmethod(chronological_stop)
MinuteSession.chronological_parent = staticmethod(chronological_parent)
MinuteSession.chronological_buy = staticmethod(chronological_buy)
MinuteSession.chronological_timer = staticmethod(chronological_timer)

def chronological_tokens(symbol, source):
    """Supply stable session rows; duplicate clocks remain separate tokens."""
    from backtest.research.ashare_bars import _in_session
    keep = _in_session([int(row["hm"]) for row in source])
    from backtest.research.minute_engine_policies import MinuteRowToken
    records = [row for row, valid in zip(source, keep) if valid]
    return [MinuteRowToken(symbol, index, int(row["hm"]), row)
            for index, row in enumerate(records)]


def chronological_observe(state, symbol, row, last_prices, tail_parent):
    close_px = float(row["close"])
    open_px = float(row.get("open", close_px))
    last_prices[symbol] = close_px
    position = state.positions.get(symbol)
    if position is not None and not tail_parent:
        position.peak = max(position.peak, float(row.get("high", max(open_px, close_px))))


MinuteSession.chronological_tokens = staticmethod(chronological_tokens)
MinuteSession.chronological_observe = staticmethod(chronological_observe)


def simulate_native(minute_bars: Any, daily_bars: Any, pool_days: Mapping[Any, Sequence[str]] | None,
                index_days: Any = None, *, cash_total: float = 21_000_000.0,
                start: Any = None, end: Any = None,
                exdiv: Mapping[str, Mapping[str, float]] | None = None,
                exdiv_economics: EconomicLookup | None = None,
                names: Mapping[str, str] | None = None,
                names_by_day: Mapping[str, Mapping[str, str]] | None = None,
                fee: FeeSchedule | None = None,
                participation_rate: float | None = None,
                volume_for_bucket: VolumeLookup | None = None,
                fix_minute_cash_order: bool = False,
                tail_window_buy: bool = False,
                tail_volume_unit: str | None = "shares",
                audit_sink: Any = None,
                rule_profile: str | RuleProfile = "industry",
                ) -> SimResult:
    """Validate/normalize tail options, then translate native v7/APP arguments."""
    profile = resolve_rule_profile(rule_profile)
    fix_minute_cash_order = bool(
        fix_minute_cash_order or profile.chronological_v7
    )
    # Reject invalid native tail options before loading main (facade lazy-import contract).
    from backtest.research.tail_window_buy import validate_tail_options, resolve_tail_volume_unit
    validate_tail_options(tail_window_buy, fix_minute_cash_order, tail_volume_unit)
    if tail_window_buy:
        tail_volume_unit = resolve_tail_volume_unit(tail_volume_unit)
    context_fee = (
        DEFAULT_SCHEDULE
        if fee is None and not profile.account_fee_schedule
        else fee
    )
    from backtest.research.csv_minute_backtest import simulate
    from backtest.research.minute_engine_policies import MinutePolicyContext
    return simulate(
        minute_bars, daily_bars, pool_days, start, end, strategy="version7",
        total_cash=cash_total, exdiv=exdiv, exdiv_economics=exdiv_economics,
        pool_names=names, pool_names_by_day=names_by_day,
        participation_rate=participation_rate, volume_for_bucket=volume_for_bucket,
        audit_sink=audit_sink, fix_minute_cash_order=fix_minute_cash_order,
        tail_window_buy=tail_window_buy, tail_volume_unit=tail_volume_unit,
        policy_context=MinutePolicyContext(
            index_days=index_days, fee_schedule=context_fee, rule_profile=profile,
        ),
        rule_profile=profile,
    )
