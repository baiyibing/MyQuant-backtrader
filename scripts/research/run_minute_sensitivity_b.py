#!/usr/bin/env python3
"""Human GO B: synthetic/lake read-only event sensitivity; never a strategy replay."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backtest.research import csv_minute_backtest as book
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research import unified_exit_modea as modea
from backtest.research import unified_exit_modeb as modeb
from backtest.research.ashare_fees import BILATERAL_10BP, FeeSchedule
from backtest.research.ashare_bars import book_frames_from_compact, load_minute_from_lake
from backtest.research.qlib_bin_1min import load_qlib_bin_1min_bars
from backtest.research.ashare_session import (
    defer_sell_at_limit, session_limit_prices, skip_buy_at_limit, t1_sellable,
)
from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap
from backtest.research.csv_ledger import Position, SimState, _sell
from backtest.research.csv_simulate_loop import run_chase_due_day
from backtest.research.strategy7_rules import in_add_window, ladder_decision, stop_decision
from common.infra.data_root import resolve_period_root

BASE = "f2fe15124ffbc62d3c0526fc90fed78d014b1bb1"
SYMBOL = "600000.SH"
DAY = date(2026, 9, 17)
NEXT_DAY = date(2026, 9, 18)
PREV_DAY = date(2026, 9, 16)
SESSIONS = (DAY, NEXT_DAY)
SCOPE = "SYNTHETIC_LOCAL_PRICE_ONLY_NOT_STRATEGY_REPLAY"
SOURCE_NAMES = (
    "csv_minute_backtest", "csv_minute_backtest_v7", "unified_exit_modea",
    "unified_exit_modeb", "csv_ledger", "csv_simulate_loop", "ashare_fees",
    "ashare_volume_cap", "ashare_fill_clock", "ashare_session", "strategy7_rules",
)


def stamp(day: date, hm: int) -> datetime:
    # Naive wall-clock values are explicitly Asia/Shanghai in all artifacts.
    return datetime.combine(day, datetime.min.time()) + timedelta(minutes=hm)


@dataclass(frozen=True)
class Bar:
    day: date
    hm: int  # right-end completed-minute label, not an assertion about the lake
    open: float
    close: float

    @property
    def end(self) -> datetime:
        return stamp(self.day, self.hm)

    @property
    def start(self) -> datetime:
        return self.end - timedelta(minutes=1)

    def record(self) -> dict:
        return dict(date=self.day, hm=self.hm, open=self.open, close=self.close,
                    high=max(self.open, self.close), low=min(self.open, self.close),
                    bar_start=self.start, bar_end=self.end)


@dataclass
class Case:
    engine: str
    case_id: str
    decision_hm: int
    price: float
    candidates: list[Bar]
    stage: str = "trial"
    quote_hm: int | None = None
    previous: float = 10.0
    cash: float = 1_000_000.0
    exit_price: float = 10.7
    exit_day: date = date(2026, 9, 21)
    entry_a: float = 10.0
    notes: str = ""

    def frame(self) -> pd.DataFrame:
        hm = self.decision_hm if self.quote_hm is None else self.quote_hm
        rows = [Bar(DAY, hm, 10.0 if self.engine == "Book" else self.price, self.price)]
        if self.engine == "Book":
            rows.insert(0, Bar(DAY, 571, 10.0, 10.0))
        return pd.DataFrame([b.record() for b in rows])


def fixtures() -> list[Case]:
    def bars(hm, *prices):
        return [Bar(DAY, hm + i, p, p) for i, p in enumerate(prices)]

    cases = [
        Case("Book", "up", 585, 10.2, bars(586, 10.25, 10.6), exit_price=10.7),
        Case("Book", "down", 585, 10.2, bars(586, 10.25, 9.9), exit_price=10.5),
        Case("Book", "unchanged_price", 585, 10.2, bars(587, 10.2)),
        Case("Book", "fallback_0943", 585, 10.2, bars(586, 10.25, 10.3), quote_hm=583),
        Case("Book", "missing_bar", 585, 10.2, bars(591, 10.4)),
        Case("Book", "limit_release", 585, 10.2, bars(587, 11.0, 10.5)),
        Case("Book", "limit_exhausted", 585, 10.2, bars(587, 11.0, 11.0)),
        Case("Book", "overnight", 585, 10.2, [Bar(NEXT_DAY, 571, 10.4, 10.4)]),
        Case("Book", "cash_reject", 585, 10.2, bars(587, 10.5), cash=9250),
        Case("Book", "no_next_bar", 585, 10.2, []),
        Case("Book", "abandon", 585, 9.9, bars(587, 10.1)),
        Case("Book", "decision_limit", 585, 11.0, bars(587, 10.5)),
    ]
    for stage, price in (("trial", 10.4), ("four", 10.8), ("six", 11.2), ("eight", 11.6)):
        cases.append(Case("v7", f"{stage}_add", 885, price,
                          bars(886, price, price + .2), stage=stage,
                          previous=price, exit_price=price + .5))
    cases.extend([
        Case("v7", "down", 885, 10.4, bars(887, 10.1), exit_price=10.8),
        Case("v7", "unchanged_price", 885, 10.4, bars(887, 10.4)),
        Case("v7", "missing_bar", 885, 10.4, bars(891, 10.5)),
        Case("v7", "overnight", 895, 10.4, [Bar(NEXT_DAY, 571, 10.6, 10.6)]),
        Case("v7", "limit_release", 885, 10.4, bars(887, 11.0, 10.5)),
        Case("v7", "limit_down_release", 885, 10.4, bars(887, 9.0, 10.3)),
        Case("v7", "limit_exhausted", 885, 10.4, bars(887, 11.0)),
        Case("v7", "no_next_bar", 885, 10.4, []),
        Case("v7", "no_signal", 885, 10.3, bars(887, 10.4)),
        Case("v7", "outside_add_window", 884, 10.4, bars(887, 10.4)),
    ])
    return cases


def v7_position(case: Case) -> v7.Position:
    stages = ("trial", "four", "six", "eight")
    prices = [case.entry_a * mult for mult in (1., 1.04, 1.08, 1.12)[:stages.index(case.stage) + 1]]
    lots = [v7.Lot(int(200_000 / px / 100) * 100, PREV_DAY, px,
                   "trial" if i == 0 else "prior_add") for i, px in enumerate(prices)]
    average = sum(lot.price * lot.shares for lot in lots) / sum(lot.shares for lot in lots)
    return v7.Position(SYMBOL, case.entry_a, stage=case.stage, lots=lots,
                       avg_cost=average, last_add_date=PREV_DAY, peak=max(prices))


def baseline(case: Case, cap: VolumeCap | None = None) -> dict:
    """Run original decision and booking functions; no production rebinding."""
    if case.engine == "Book":
        frame = case.frame()
        quotes = book._chase_quotes(frame)
        assert quotes is not None
        st = SimState(cash=case.cash, volume_cap=cap)
        pending = {SYMBOL: (10_000.0, 0)}
        run_chase_due_day(st, pending, day_i=1, day=pd.Timestamp(DAY), names={},
                          allow_add=False, buy_gate=None,
                          quotes_for=lambda _: (*quotes, [case.previous]),
                          volume_bucket_for=lambda _: case.quote_hm or case.decision_hm)
        trades = [t for t in st.trades if t["side"] == "BUY"]
        reason = (trades[-1]["reason"] if trades else
                  st.trades[-1]["reason"] if st.trades else
                  "limit" if st.stats["chase_skip_limit"] else
                  "abandon" if st.stats["chase_abandon"] else "buy_failed")
        action = book.chase_decision(*quotes, session_limit_prices(SYMBOL, case.previous)[0])
    else:
        st = v7.SimResult(case.cash, volume_cap=cap)
        pos = v7_position(case)
        st.positions[SYMBOL] = pos
        decision = ladder_decision(case.stage, case.price, entry_a=case.entry_a)
        stop = stop_decision(case.stage, entry_a=pos.entry_A, average_cost=pos.avg_cost)
        assert case.price > stop.line, "Add-only fixture must survive the preceding stop gate"
        action = decision.action if in_add_window(case.decision_hm) else "outside_add_window"
        limits = session_limit_prices(SYMBOL, case.previous)
        reason = action
        if action.startswith("add_"):
            if skip_buy_at_limit(case.price, limits):
                reason = "limit_up"
            elif defer_sell_at_limit(case.price, limits):
                reason = "limit_down"
            else:
                v7._buy(st, pos, SYMBOL, DAY, case.decision_hm, case.price,
                        decision.fraction, "buy:" + action, action)
                reason = st.trades[-1]["reason"]
        trades = [t for t in st.trades if t["side"] == "buy"]
    qty = int(trades[-1]["shares"]) if trades else 0
    px = float(trades[-1]["price"]) if trades else None
    return dict(status="FILLED" if qty else "NO_FILL", reason=reason,
                shares=qty, fill_px=px, cash_after=st.cash, action=action)


def next_open(*, engine: str, side: str, decision_at: datetime, candidates: list[Bar],
              previous_by_day: dict[date, float], shares: int, cash: float,
              buy_day: date = PREV_DAY, cap: VolumeCap | None = None,
              symbol: str = SYMBOL, sessions=SESSIONS) -> tuple[dict, list[dict]]:
    """Frozen order: chronological first eligible open, no close/volume lookahead."""
    submit = decision_at + timedelta(milliseconds=1)
    attempts = []
    for bar in sorted(candidates, key=lambda b: b.start):
        why = ""
        start_hm = bar.start.hour * 60 + bar.start.minute
        if bar.start < submit:
            why = "before_submit"
        elif bar.day not in sessions:
            why = "outside_fixture_calendar"
        elif not (570 <= start_hm < 690 or 780 <= start_hm < 897):
            why = "outside_continuous_session"
        elif side == "sell" and not t1_sellable(buy_day, bar.day):
            why = "t1_locked"
        else:
            limits = session_limit_prices(symbol, previous_by_day.get(bar.day))
            if limits is None:
                why = "missing_limit_reference"
            elif side == "buy" and skip_buy_at_limit(bar.open, limits):
                why = "limit_up"
            elif (side == "sell" or engine == "v7") and defer_sell_at_limit(bar.open, limits):
                why = "limit_down"
        filled = shares
        if not why and side == "buy" and BILATERAL_10BP.debit_buy(shares * bar.open) > cash:
            why = "cash_reject_terminal"
        if not why and cap is not None:
            # This open cannot spend the bar's future completed volume.
            end_hm = bar.end.hour * 60 + bar.end.minute
            filled, why = cap.clamp((symbol, bar.day.strftime("%Y%m%d"), end_hm),
                                    start_hm, shares, buy=side == "buy")
        attempts.append(dict(candidate_start=bar.start, candidate_end=bar.end,
                             submit_at=submit, candidate_px=bar.open,
                             previous_close=previous_by_day.get(bar.day),
                             outcome=why or "FILLED", candidate_shares=filled if not why else 0))
        if not why:
            if cap is not None:
                cap.consume((symbol, bar.day.strftime("%Y%m%d"), end_hm), filled)
            delta = (BILATERAL_10BP.debit_buy(filled * bar.open) if side == "buy"
                     else -BILATERAL_10BP.credit_sell(filled * bar.open))
            return dict(status="FILLED", fill_px=bar.open, fill_at=bar.start,
                        shares=filled, cash_after=cash - delta, reason="first_eligible_open"), attempts
        if why == "cash_reject_terminal":
            break
    return dict(status="UNFILLED", fill_px=None, fill_at=None, shares=0,
                cash_after=cash, reason=(attempts[-1]["outcome"] if attempts else "no_candidate")), attempts


def economics(buy_px, sell_px, qty, *, slip_bp=0, scheme="BILATERAL_10BP") -> dict:
    buy = buy_px * (1 + slip_bp / 10_000)
    sell = sell_px * (1 - slip_bp / 10_000)
    if scheme == "BILATERAL_10BP":
        buy_fee = BILATERAL_10BP.buy_fee(buy * qty)
        sell_fee = BILATERAL_10BP.sell_fee(sell * qty)
        stamp_fee = 0.0
    elif scheme == "REPLACE_COMMISSION_3BP_MIN5_STAMP_SELL5BP":
        fee = FeeSchedule(.0003, .0003, 5.0)
        buy_fee, sell_fee = fee.buy_fee(buy * qty), fee.sell_fee(sell * qty)
        stamp_fee = sell * qty * .0005
    else:
        raise ValueError(scheme)
    debit = qty * buy + buy_fee
    pnl = qty * sell - sell_fee - stamp_fee - debit
    return dict(buy_px=buy, sell_px=sell, buy_fee=buy_fee, sell_fee=sell_fee,
                stamp_fee=stamp_fee, net_pnl=pnl, net_return=pnl / debit)


def clock_rows(cases: list[Case]) -> tuple[list[dict], list[dict]]:
    rows, audits = [], []
    for case in cases:
        base = baseline(case)
        at = stamp(DAY, case.decision_hm)
        if base["shares"]:
            alt, attempts = next_open(engine=case.engine, side="buy", decision_at=at,
                                      candidates=case.candidates,
                                      previous_by_day={DAY: case.previous, NEXT_DAY: case.price},
                                      shares=base["shares"], cash=case.cash)
        else:
            alt, attempts = dict(status="NO_FILL", fill_px=None, fill_at=None, shares=0,
                                 cash_after=case.cash, reason="no_baseline_order"), []
        common = base["shares"] > 0 and alt["shares"] > 0
        old = economics(base["fill_px"], case.exit_price, base["shares"]) if base["shares"] else {}
        new = economics(alt["fill_px"], case.exit_price, alt["shares"]) if common else {}
        if common:
            assert t1_sellable(alt["fill_at"].date(), case.exit_day)
        quote_at = stamp(DAY, case.quote_hm or case.decision_hm)
        row = dict(engine=case.engine, case_id=case.case_id, axis="clock", scope=SCOPE,
                   source="constructed_fixture", symbol=SYMBOL, stage=case.stage,
                   quote_at=quote_at, close_available_at=quote_at, decision_at=at,
                   submit_at=at + timedelta(milliseconds=1), decision_px=case.price,
                   quote_age_seconds=(at - quote_at).total_seconds(), action=base["action"],
                   baseline_status=base["status"], baseline_reason=base["reason"],
                   baseline_fill_at=at if base["shares"] else None,
                   baseline_fill_px=base["fill_px"], baseline_shares=base["shares"],
                   baseline_cash_after=base["cash_after"], next_status=alt["status"],
                   next_reason=alt["reason"], next_fill_at=alt["fill_at"], next_fill_px=alt["fill_px"],
                   next_shares=alt["shares"], next_cash_after=alt["cash_after"],
                   status_match=(base["shares"] > 0) == (alt["shares"] > 0),
                   matched_fill=common, same_price=(math.isclose(base["fill_px"], alt["fill_px"], abs_tol=1e-9)
                                                   if common else None),
                   price_diff=(alt["fill_px"] - base["fill_px"] if common else None),
                   price_diff_bp=((alt["fill_px"] / base["fill_px"] - 1) * 10_000 if common else None),
                   fixed_exit_day=case.exit_day, fixed_exit_px=case.exit_price,
                   baseline_local_pnl=old.get("net_pnl"), next_local_pnl=new.get("net_pnl"),
                   baseline_local_return=old.get("net_return"), next_local_return=new.get("net_return"),
                   local_pnl_delta=new["net_pnl"] - old["net_pnl"] if common else None,
                   local_return_delta_bp=((new["net_return"] - old["net_return"]) * 10_000 if common else None))
        rows.append(row)
        audits.extend(dict(engine=case.engine, case_id=case.case_id, **a) for a in attempts)
    # Average ranks for ties; common cohort only; never rank different engines.
    for engine in ("Book", "v7"):
        cohort = [r for r in rows if r["engine"] == engine and r["matched_fill"]]
        for prefix in ("baseline", "next"):
            ranks = pd.Series([r[prefix + "_local_return"] for r in cohort]).round(12).rank(ascending=False)
            for row, rank in zip(cohort, ranks):
                row[prefix + "_local_rank"] = float(rank)
        for row in cohort:
            row["local_rank_delta"] = row["next_local_rank"] - row["baseline_local_rank"]
    return rows, audits


def modeb_baselines() -> list[dict]:
    rows = []
    daily = {SYMBOL: pd.DataFrame({"open": [10, 10], "close": [10, 10]},
                                 index=pd.to_datetime([PREV_DAY, DAY]))}
    inst = modea.Instance(SYMBOL, "合成", DAY.strftime("%Y%m%d"), 10.0, True)
    for label, op, close in (("close_take_profit", 10.1, 10.6), ("gap_stop", 9.4, 9.3)):
        frame = pd.DataFrame([Bar(NEXT_DAY, 586, op, close).record()])
        frame["ymd"] = NEXT_DAY.strftime("%Y%m%d")
        frame.index = pd.to_datetime([stamp(NEXT_DAY, 586)])
        args = (inst, modea.StrategySpec(2, 10, 5, 5), daily, {SYMBOL: frame},
                [DAY.strftime("%Y%m%d"), NEXT_DAY.strftime("%Y%m%d")])
        result = modeb.evaluate_exit_modeb(*args, end="20260918")
        assert result == modeb.evaluate_exit_modeb(*args, end="20260918", impl="ref")
        rows.append(dict(engine="ModeB", case_id=label, scope=SCOPE, entry_px=10.0,
                         entry_clock="none_daily_close", fill_px=result.sell_price,
                         shares=result.shares, reason=result.reason, local_pnl=result.pnl,
                         local_return=result.return_pct, clock_comparison="NOT_RUN_BATCH1",
                         oracle="NOT_RUN_EX_POST_UPPER_BOUND_NOT_EXECUTABLE"))
    return rows


def cost_rows(clock: list[dict], modeb_rows: list[dict]) -> list[dict]:
    inputs = [dict(engine=r["engine"], case_id=r["case_id"], buy=r["baseline_fill_px"],
                   sell=r["fixed_exit_px"], qty=r["baseline_shares"])
              for r in clock if r["baseline_shares"]]
    inputs += [dict(engine="ModeB", case_id=r["case_id"], buy=r["entry_px"],
                    sell=r["fill_px"], qty=r["shares"]) for r in modeb_rows]
    rows = []
    for event in inputs:
        base = economics(event["buy"], event["sell"], event["qty"])
        scenarios = [("slippage", "BILATERAL_10BP", bp) for bp in (0, 5, 10, 20)]
        scenarios += [("fee", name, 0) for name in
                      ("BILATERAL_10BP", "REPLACE_COMMISSION_3BP_MIN5_STAMP_SELL5BP")]
        for axis, scheme, bp in scenarios:
            econ = economics(event["buy"], event["sell"], event["qty"], slip_bp=bp, scheme=scheme)
            rows.append(dict(engine=event["engine"], case_id=event["case_id"], scope=SCOPE,
                             axis=axis, scheme=scheme, slip_per_side_bp=bp, shares=event["qty"],
                             coverage=("commission_proxy_only" if scheme == "BILATERAL_10BP" else
                                       "replacement_commission_min5_plus_assumed_sell_stamp5bp_no_transfer"),
                             **econ, pnl_delta=econ["net_pnl"] - base["net_pnl"],
                             return_delta_bp=(econ["net_return"] - base["net_return"]) * 10_000))
    for engine in ("Book", "v7", "ModeB"):
        for axis in ("slippage", "fee"):
            base_cohort = [r for r in rows if r["engine"] == engine and r["axis"] == axis
                           and r["scheme"] == "BILATERAL_10BP" and r["slip_per_side_bp"] == 0]
            base_ranks = dict(zip([r["case_id"] for r in base_cohort],
                                  pd.Series([r["net_return"] for r in base_cohort]).round(12).rank(ascending=False)))
            for scheme, bp in sorted({(r["scheme"], r["slip_per_side_bp"]) for r in rows
                                      if r["engine"] == engine and r["axis"] == axis}):
                cohort = [r for r in rows if r["engine"] == engine and r["axis"] == axis
                          and r["scheme"] == scheme and r["slip_per_side_bp"] == bp]
                ranks = pd.Series([r["net_return"] for r in cohort]).round(12).rank(ascending=False)
                for row, rank in zip(cohort, ranks):
                    row["baseline_local_rank"] = float(base_ranks[row["case_id"]])
                    row["scenario_local_rank"] = float(rank)
                    row["local_rank_delta"] = float(rank - base_ranks[row["case_id"]])
    return rows


def capacity_rows() -> list[dict]:
    rows = []
    for engine, hm, px in (("Book", 585, 10.2), ("v7", 885, 10.4)):
        case = Case(engine, "cap", hm, px, [])
        key = (SYMBOL, DAY.strftime("%Y%m%d"), hm)
        for sample_name, sample in (
            ("enough", BucketVolume(1_000_000, hm, "raw_shares_incremental")),
            ("partial", BucketVolume(3500, hm, "raw_shares_incremental")),
            ("missing", None),
            ("late", BucketVolume(1_000_000, hm + 1, "raw_shares_incremental")),
        ):
            for enabled in (False, True):
                cap = VolumeCap(.1, {key: sample}) if enabled else None
                result = baseline(case, cap)
                rows.append(dict(engine=engine, case_id=sample_name, axis="capacity_close",
                                 scope=SCOPE, cap_on=enabled, participation_rate=.1 if enabled else None,
                                 raw_volume=sample.shares if sample else None,
                                 volume_unit=sample.unit if sample else None,
                                 available_at=sample.available_at if sample else None,
                                 bucket=hm, at=hm, **result))
    return rows


def gap_rows() -> list[dict]:
    """Protective-open axis; never relabel as a delayed close order."""
    rows = []
    for engine in ("Book", "v7"):
        for enabled in (False, True):
            hm, px = 571, 9.4
            key = (SYMBOL, DAY.strftime("%Y%m%d"), hm)
            cap = VolumeCap(.1, {key: BucketVolume(100_000, hm, "raw_shares_incremental")}) if enabled else None
            limits = session_limit_prices(SYMBOL, 10.0)
            if engine == "Book":
                scan = book.scan_held_day_python(
                    np.array([px]), np.array([9.6]), np.array([9.3]), cost=10., peak=10.,
                    n_days=1, can_sell=True, stop_pct=.05, profit_base=99., trail_ratio=.2,
                    hm=np.array([hm]), limit_down=limits[1])
                assert scan[2] == "stop_loss:gap_open" and scan[1] == px
                st = SimState(cash=0., volume_cap=cap)
                pos = Position(SYMBOL, 1000, 10., 0, 10.)
                st.positions[SYMBOL] = [pos]
                _sell(st, SYMBOL, pos, px, pd.Timestamp(DAY), scan[2], bucket_id=hm, at=hm - 1, day_i=1)
                sells = [t for t in st.trades if t["side"] == "SELL"]
                trigger = 9.5
            else:
                st = v7.SimResult(0., volume_cap=cap)
                pos = v7.Position(SYMBOL, 9.8, stage="four",
                                  lots=[v7.Lot(500, PREV_DAY, 9.8, "trial"),
                                        v7.Lot(500, PREV_DAY, 10.2, "prior_add")], avg_cost=10.)
                st.positions[SYMBOL] = pos
                trigger = stop_decision(pos.stage, entry_a=pos.entry_A, average_cost=pos.avg_cost).line
                assert px <= trigger and not defer_sell_at_limit(px, limits)
                v7._sell_lots(st, pos, DAY, hm, px, "stop:four_avg095", at=hm - 1)
                sells = [t for t in st.trades if t["side"] == "sell"]
            rows.append(dict(engine=engine, case_id="protective_first_open", axis="gap_open_capacity",
                             scope=SCOPE, cap_on=enabled, participation_rate=.1 if enabled else None,
                             trigger=trigger, candidate_px=px, shares=sum(t["shares"] for t in sells),
                             fill_px=px if sells else None, reason=st.trades[-1]["reason"],
                             cash_after=st.cash, bucket=hm, at=hm - 1, available_at=hm,
                             raw_volume=100_000, volume_unit="raw_shares_incremental"))
    return rows


def shared_capacity_rows() -> list[dict]:
    rows = []
    for engine, hm in (("Book", 585), ("v7", 885)):
        for enabled in (False, True):
            key = (SYMBOL, DAY.strftime("%Y%m%d"), hm)
            cap = VolumeCap(.1, {key: BucketVolume(3500, hm, "raw_shares_incremental")}) if enabled else None
            if engine == "Book":
                state = SimState(cash=1_000_000., volume_cap=cap)
                old = Position(SYMBOL, 1000, 10., 0, 10.)
                state.positions[SYMBOL] = [old]
                book.execute_buy(state, SYMBOL, 10.2, 10_000., 1, pd.Timestamp(DAY), bucket_id=hm)
                _sell(state, SYMBOL, old, 10.2, pd.Timestamp(DAY), "fixture_exit", bucket_id=hm, day_i=1)
            else:
                state = v7.SimResult(1_000_000., volume_cap=cap)
                old = v7.Position(SYMBOL, 10., lots=[v7.Lot(1000, PREV_DAY, 10., "trial")], avg_cost=10.)
                state.positions[SYMBOL] = old
                v7._buy(state, old, SYMBOL, DAY, hm, 10.2, .2, "fixture_buy", "add")
                v7._sell_lots(state, old, DAY, hm, 10.2, "fixture_exit")
            for trade in state.trades:
                rows.append(dict(engine=engine, scope=SCOPE, axis="shared_capacity", cap_on=enabled,
                                 side=trade["side"], shares=trade["shares"], fill_px=trade["price"],
                                 final_bucket_used=cap.used.get(key, 0) if cap else None,
                                 raw_volume=3500, participation_rate=.1 if enabled else None,
                                 available_at=hm, bucket=hm, at=hm))
    return rows


def boundary_rows() -> list[dict]:
    probes = [
        ("lunch", "buy", stamp(DAY, 690), [Bar(DAY, 781, 10.2, 10.3)], PREV_DAY, None),
        ("t1_same_day", "sell", stamp(DAY, 600), [Bar(DAY, 602, 10.2, 10.3)], DAY, None),
        ("t1_next_session", "sell", stamp(DAY, 895), [Bar(NEXT_DAY, 571, 10.2, 10.3)], DAY, None),
        ("closing_call_skip", "buy", stamp(DAY, 896), [Bar(DAY, 898, 10.2, 10.3)], PREV_DAY, None),
        ("sell_limit_release", "sell", stamp(DAY, 600),
         [Bar(DAY, 602, 9.0, 9.0), Bar(DAY, 603, 9.1, 9.1)], PREV_DAY, None),
        ("next_open_future_volume", "buy", stamp(DAY, 585), [Bar(DAY, 587, 10.2, 10.3)], PREV_DAY,
         VolumeCap(.1, {(SYMBOL, DAY.strftime("%Y%m%d"), 587):
                       BucketVolume(100_000, 587, "raw_shares_incremental")})),
    ]
    rows = []
    for label, side, at, bars, buy_day, cap in probes:
        result, attempts = next_open(engine="Book", side=side, decision_at=at, candidates=bars,
                                     previous_by_day={DAY: 10., NEXT_DAY: 10.}, shares=100,
                                     cash=100_000., buy_day=buy_day, cap=cap)
        rows.append(dict(engine="SCHEDULER_PROBE_NOT_STRATEGY", case_id=label, scope=SCOPE,
                         side=side, decision_at=at, buy_day=buy_day, **result,
                         attempts=json.dumps(attempts, default=str, ensure_ascii=False)))
    # Actual pending-day behavior, with no fake empty-market success.
    st, pending = SimState(cash=10_000.), {SYMBOL: (10_000., 0)}
    kwargs = dict(names={}, allow_add=False, buy_gate=None)
    run_chase_due_day(st, pending, day_i=1, day=pd.Timestamp(DAY), quotes_for=lambda _: None, **kwargs)
    assert SYMBOL in pending and not st.trades
    run_chase_due_day(st, pending, day_i=2, day=pd.Timestamp(NEXT_DAY),
                      quotes_for=lambda _: (10., 10.2, [10.]), **kwargs)
    assert SYMBOL not in pending and st.stats["chase_buy"] == 1
    rows.append(dict(engine="Book", case_id="missing_quote_pending_next_session", scope=SCOPE,
                     status="FILLED", reason=st.trades[-1]["reason"], shares=st.trades[-1]["shares"],
                     fill_px=st.trades[-1]["price"], fill_at=stamp(NEXT_DAY, 585)))
    return rows


def fee_granularity_rows() -> list[dict]:
    rows = []
    for name, fee in (("BILATERAL_10BP", BILATERAL_10BP),
                      ("REPLACE_COMMISSION_3BP_MIN5_STAMP_SELL5BP", FeeSchedule(.0003, .0003, 5.))):
        st = SimState(cash=0., sell_cost_rate=fee.sell_rate, min_cost=fee.min_cost)
        lots = [Position(SYMBOL, 100, 10., 0, 10., lot_id=i) for i in range(2)]
        st.positions[SYMBOL] = list(lots)
        for lot in lots:
            _sell(st, SYMBOL, lot, 10., pd.Timestamp(DAY), "fixture_exit")
        state = v7.SimResult(0.)
        pos = v7.Position(SYMBOL, 10., lots=[v7.Lot(100, PREV_DAY, 10., "trial") for _ in range(2)], avg_cost=10.)
        state.positions[SYMBOL] = pos
        v7._sell_lots(state, pos, DAY, 585, 10., "fixture_exit", fee=fee)
        for engine, cash, calls in (("Book", st.cash, 2), ("v7", state.cash, 1)):
            rows.append(dict(engine=engine, scheme=name, scope=SCOPE, sell_calls=calls,
                             total_sell_notional=2000., sell_commission=2000. - cash,
                             assumed_stamp=1. if name.startswith("REPLACE") else 0.,
                             note="synthetic_two_100_share_lots_same_price"))
    return rows


def data_gaps() -> list[dict]:
    gaps = []
    configured = {name: bool(os.environ.get(name)) for name in
                  ("OSKH_SOURCE_PARQUET_ROOT", "OSKH_AUTHORITY_HINT_ROOT", "OSKH_PERIOD_1M_ROOT")}
    try:
        root = resolve_period_root("1m")
        if not root.is_dir():
            raise FileNotFoundError(f"Configured minute root does not exist: {root}")
        evidence = "root_exists_but_full_sample_manifest_and_replay_not_implemented"
    except (RuntimeError, ValueError, OSError) as exc:
        evidence = f"{type(exc).__name__}: {exc}"
    gaps.append(dict(item="production_minute_lake", status="DATA_GAP", evidence=evidence,
                     env_configured=json.dumps(configured, sort_keys=True)))
    sample = ROOT / "stock_pool/20260909.csv"
    with sample.open(encoding="utf-8-sig", newline="") as handle:
        first = next(csv.reader(handle))
    gaps.append(dict(item="pool_availability", status="DATA_GAP",
                     evidence=f"stock_pool/20260909.csv sampled: {len(first)} columns, code/name only; no publication timestamp; not a full upstream audit"))
    for item, evidence in (
        ("factor_availability", "no audited generated_at/available_at chain"),
        ("real_bar_timestamp_semantics", "fixture end labels are constructed, not audited lake labels"),
        ("real_volume_and_units", "synthetic shares/available_at only; handoff fixtures are not market coverage"),
        ("closed_cash_path_daily_marks_corporate_actions", "event order and frozen quantity only; no full strategy replay"),
    ):
        gaps.append(dict(item=item, status="DATA_GAP", evidence=evidence))
    return gaps


def source_hashes() -> dict:
    # Compare as git blobs would: normalize CRLF so Windows working trees with
    # autocrlf do not false-fail the production BASE fence.
    return {
        f"backtest/research/{name}.py": hashlib.sha256(
            (ROOT / f"backtest/research/{name}.py").read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        for name in SOURCE_NAMES
    }


def write_csv(path: Path, rows: list[dict], fields=()) -> None:
    fields = list(dict.fromkeys([*fields, *(k for row in rows for k in row)]))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summaries(rows: list[dict]) -> list[dict]:
    out = []
    for engine in ("Book", "v7"):
        group = [r for r in rows if r["engine"] == engine]
        base = [r for r in group if r["baseline_shares"]]
        common = [r for r in group if r["matched_fill"]]
        out.append(dict(engine=engine, scope=SCOPE, events=len(group), baseline_fills=len(base),
                        next_fills=sum(r["next_shares"] > 0 for r in group), common_fills=len(common),
                        status_match_rate=sum(r["status_match"] for r in group) / len(group),
                        matched_fill_rate=len(common) / len(base) if base else None,
                        same_price_rate=sum(r["same_price"] for r in common) / len(common) if common else None,
                        mean_local_return_delta_bp=np.mean([r["local_return_delta_bp"] for r in common]) if common else None,
                        changed_local_ranks=sum(r["local_rank_delta"] != 0 for r in common),
                        max_drawdown=None, strategy_rank=None, full_strategy_return=None,
                        full_replay_status="DATA_GAP"))
    out.append(dict(engine="ModeB", scope=SCOPE, full_replay_status="DATA_GAP",
                    clock_status="NOT_RUN_BATCH1", oracle="EX_POST_UPPER_BOUND_NOT_EXECUTABLE"))
    return out


def check_source_fence() -> dict:
    before = source_hashes()
    for path, digest in before.items():
        base_bytes = subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)
        if hashlib.sha256(base_bytes).hexdigest() != digest:
            raise ValueError(f"Production source differs from experiment BASE: {path}")
    return before


def run(output: Path) -> dict:
    # Fail closed before any output mutation; never reuse baseline/artifact dirs.
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {output}")
    before = check_source_fence()
    cases = fixtures()
    clocks, audits = clock_rows(cases)
    mb = modeb_baselines()
    payloads = {
        "clock_trades.csv": clocks, "clock_candidates.csv": audits,
        "clock_summary.csv": summaries(clocks), "modeb_baseline.csv": mb,
        "cost_sensitivity.csv": cost_rows(clocks, mb), "capacity.csv": capacity_rows(),
        "gap_stop.csv": gap_rows(), "clock_boundaries.csv": boundary_rows(),
        "capacity_shared.csv": shared_capacity_rows(),
        "fee_granularity.csv": fee_granularity_rows(), "data_gaps.csv": data_gaps(),
    }
    assert source_hashes() == before, "Production source changed during run"
    output.mkdir(parents=True, exist_ok=False)
    for filename, rows in payloads.items():
        write_csv(output / filename, rows)
    (output / "fixtures.json").write_text(json.dumps(
        [asdict(c) for c in cases], default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(output / "minute_frames.csv", [
        dict(engine=c.engine, case_id=c.case_id, role=role, **record)
        for c in cases for role, records in
        (("baseline_input", c.frame().to_dict("records")),
         ("candidate", [bar.record() for bar in c.candidates])) for record in records
    ])
    manifest = dict(base=BASE, git_head=subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), scope=SCOPE,
        python=sys.version, pandas=pd.__version__, numpy=np.__version__,
        timezone="Asia/Shanghai", bar_label="end", order_delay_ms=1,
        source_hashes_before=before, source_hashes_after=source_hashes(),
        checked_sources_match_base=True,
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        production_replay="DATA_GAP", source="constructed_synthetic_not_handoff_market_sample",
        quantities="frozen_from_baseline_for_clock_and_cost; no_strategy_sizing_replay",
        files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())})
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dict(output=str(output), rows={k: len(v) for k, v in payloads.items()}, status="DATA_GAP_SYNTHETIC_BATCH_COMPLETE")


LAKE_SCOPE = "local event sensitivity not strategy claim"
LAKE_LABEL = "lake_index_is_bar_start_wallclock"
DEFAULT_QLIB_1MIN_ROOT = Path(r"C:\Users\wangc\.qlib\qlib_data\my_data_1min")
SOURCE_LINEAGE = "parquet_lineage"
STAGES = ("trial", "four", "six", "eight")
FULL_GAPS = dict(production_replay="DATA_GAP", full_replay_status="DATA_GAP",
                 full_strategy_nav=None, full_strategy_return=None,
                 max_drawdown=None, strategy_rank=None, strategy_rank_delta=None)


@dataclass(frozen=True)
class LakeBar(Bar):
    # Deliberately separate from batch1's END labels. Never subtract one minute.
    @property
    def start(self) -> datetime:
        return stamp(self.day, self.hm)

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=1)


def lake_dates(start: str, end: str) -> list[date]:
    if not all(re.fullmatch(r"\d{8}", x) for x in (start, end)):
        raise ValueError("Lake dates must be YYYYMMDD, without hyphens")
    first, last = (datetime.strptime(x, "%Y%m%d").date() for x in (start, end))
    if first > last:
        raise ValueError("--start must be <= --end")
    # Calendar dates, not an invented trading calendar; absent days become gaps.
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def lake_symbols(values: list[str] | None) -> list[str]:
    symbols = sorted({s.strip().upper() for value in (values or [SYMBOL])
                      for s in value.split(",")})
    if not symbols or any(not re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", s) for s in symbols):
        raise ValueError("--symbols requires canonical symbols, e.g. 600000.SH")
    return symbols


def publication_gaps() -> list[dict]:
    """Inspect repository CSV headers only; filenames/mtime are never PIT evidence."""
    samples = []
    tokens = ("published_at", "publication_timestamp", "generated_at", "available_at")
    for path in sorted((ROOT / "stock_pool").glob("*.csv"))[:20]:
        if path.is_symlink():
            continue
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                header = next(csv.reader(handle), [])
            samples.append(dict(path=str(path.relative_to(ROOT)), columns=len(header),
                                timestamp_columns=[c for c in header if c.strip().lower() in tokens]))
        except (OSError, UnicodeError, csv.Error) as exc:
            samples.append(dict(path=str(path.relative_to(ROOT)), error=str(exc)))
    return [dict(item="pool_availability", status="DATA_GAP", evidence=json.dumps(
        samples, ensure_ascii=False), reason="header_sample_only_no_audited_publication_chain"),
        dict(item="factor_availability", status="DATA_GAP",
             evidence="No audited generated_at/available_at chain; no external search")]


def validate_lake_frame(frame: pd.DataFrame, start: str, end: str) -> None:
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is not None:
        raise ValueError("Expected naive lake wall-clock DatetimeIndex; no timezone conversion inferred")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Lake frame must have unique chronological timestamps")
    if frame.index.hasnans or not (frame.index == frame.index.floor("min")).all():
        raise ValueError("Lake frame has missing/non-minute labels")
    prices = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or not (prices > 0).all():
        raise ValueError("Lake OHLC must be finite and positive")
    if ((frame["high"] < frame[["open", "close"]].max(axis=1)).any()
            or (frame["low"] > frame[["open", "close"]].min(axis=1)).any()):
        raise ValueError("Inconsistent lake OHLC envelope")
    labels = frame.index.strftime("%Y%m%d")
    if not ((labels >= start) & (labels <= end)).all():
        raise ValueError("Lake reader returned bars outside the requested window")
    if not (frame["ymd"].to_numpy() == labels).all() or not (
            frame["hm"].to_numpy() == frame.index.hour * 60 + frame.index.minute).all():
        raise ValueError("Lake hm/ymd disagrees with START wall-clock index")


def lake_baseline(*, engine, symbol, day, hm, frame, previous, anchor, stage,
                  cap=None) -> dict:
    """Original decision/ledger calls on real prices, with declared injected state."""
    price = float(frame.loc[stamp(day, hm), "close"])
    limits = session_limit_prices(symbol, previous)
    if limits is None:
        return dict(status="DATA_GAP", reason="unknown_board_or_limit_reference",
                    shares=None, fill_px=None, cash_after=None, action=None)
    if engine == "Book":
        quotes = book._chase_quotes(frame.loc[frame.index <= stamp(day, hm)])
        state = SimState(cash=1_000_000., volume_cap=cap)
        action = book.chase_decision(*quotes, limits[0])
        run_chase_due_day(state, {symbol: (10_000., 0)}, day_i=1, day=pd.Timestamp(day),
                          names={}, allow_add=False, buy_gate=None,
                          quotes_for=lambda _: (*quotes, [previous]),
                          volume_bucket_for=lambda _: hm + 1)
        trades = [t for t in state.trades if t["side"] == "BUY"]
        reason = (state.trades[-1]["reason"] if state.trades else
                  "limit" if state.stats["chase_skip_limit"] else
                  "abandon" if state.stats["chase_abandon"] else "buy_failed")
    else:
        anchor_at, entry = anchor
        state = v7.SimResult(1_000_000., volume_cap=cap)
        # All stages are counterfactual independent snapshots, not inferred history.
        position = v7.Position(symbol, entry, stage=stage, avg_cost=entry, peak=entry,
                               lots=[v7.Lot(100, anchor_at.date(), entry, "injected_anchor")],
                               last_add_date=anchor_at.date())
        state.positions[symbol] = position
        decision = ladder_decision(stage, price, entry_a=entry)
        stop = stop_decision(stage, entry_a=entry, average_cost=entry)
        action = decision.action if in_add_window(hm) else "outside_add_window"
        reason = action
        if price <= stop.line:
            reason = "stop_gate_blocks_add"
        elif action.startswith("add_"):
            if skip_buy_at_limit(price, limits):
                reason = "limit_up"
            elif defer_sell_at_limit(price, limits):
                reason = "limit_down"
            else:
                # Ledger's integer bucket is completed time; signal hm stays START.
                v7._buy(state, position, symbol, day, hm + 1, price,
                        decision.fraction, "buy:" + action, action)
                reason = state.trades[-1]["reason"]
        trades = [t for t in state.trades if t["side"] == "buy"]
    return dict(status="FILLED" if trades else "NO_FILL", reason=reason, action=action,
                shares=int(trades[-1]["shares"]) if trades else 0,
                fill_px=float(trades[-1]["price"]) if trades else None,
                cash_after=state.cash)


def lake_event(frame, *, engine, symbol, day, hm, stage) -> tuple[dict, list[dict], list[dict]]:
    quote = stamp(day, hm)
    available = quote + timedelta(minutes=1)
    previous_at = stamp(day - timedelta(days=1), 900)
    row = dict(engine=engine, case_id=f"{symbol}_{day:%Y%m%d}_{hm}_{stage}", symbol=symbol,
               date=day, scope=LAKE_SCOPE, axis="clock", source="oskh_parquet_none",
               stage=stage, signal_hm=hm, bar_label_semantics=LAKE_LABEL,
               quote_at=quote, close_available_at=available, decision_at=available,
               submit_at=available + timedelta(milliseconds=1), decision_px=None,
               limit_reference_at=previous_at, limit_reference_px=None,
               limit_reference_kind="previous_calendar_day_1500_minute_close_proxy_not_official_daily",
               injected_entry_a=None, injected_anchor_at=None,
               injected_lot_shares=100 if engine == "v7" else None,
               injected_cash=1_000_000., baseline_status="DATA_GAP", baseline_reason=None,
               baseline_fill_at=None, baseline_fill_px=None, baseline_shares=None,
               baseline_cash_after=None, next_status="DATA_GAP", next_reason=None,
               next_fill_at=None, next_fill_px=None, next_shares=None, next_cash_after=None,
               matched_fill=None, status_match=None, same_price=None, price_diff=None,
               price_diff_bp=None, fixed_exit_day=day + timedelta(days=1), fixed_exit_px=None,
               exit_mark_at=None, local_pair_status="DATA_GAP",
               baseline_local_pnl=None, next_local_pnl=None, baseline_local_return=None,
               next_local_return=None, local_pnl_delta=None, local_return_delta_bp=None,
               baseline_local_rank=None, next_local_rank=None, local_rank_delta=None, **FULL_GAPS)
    missing = []
    if frame is None:
        missing.append("missing_or_unreadable_symbol_window")
    else:
        if quote not in frame.index:
            missing.append("missing_required_signal_bar_no_fallback")
        else:
            row["decision_px"] = float(frame.at[quote, "close"])
        if stamp(day, 570) not in frame.index:
            missing.append("missing_0930_open")
        if previous_at not in frame.index:
            missing.append("missing_previous_calendar_day_1500_reference")
        else:
            row["limit_reference_px"] = float(frame.at[previous_at, "close"])
        anchors = frame.loc[(frame["hm"] == 570) & (frame.index < stamp(day, 0))]
        if engine == "v7" and anchors.empty:
            missing.append("missing_prior_date_0930_entry_anchor")
    capacities = []
    if missing:
        row["baseline_reason"] = row["next_reason"] = ";".join(missing)
        attempts = []
    else:
        anchor = ((anchors.index[0].to_pydatetime(), float(anchors.iloc[0]["open"]))
                  if engine == "v7" else None)
        if anchor:
            row.update(injected_anchor_at=anchor[0], injected_entry_a=anchor[1])
        day_frame = frame.loc[frame["ymd"] == day.strftime("%Y%m%d")]
        kwargs = dict(engine=engine, symbol=symbol, day=day, hm=hm, frame=day_frame,
                      previous=row["limit_reference_px"], anchor=anchor, stage=stage)
        base = lake_baseline(**kwargs)
        row.update(action=base["action"], baseline_status=base["status"], baseline_reason=base["reason"],
                   baseline_fill_px=base["fill_px"], baseline_shares=base["shares"],
                   baseline_cash_after=base["cash_after"],
                   baseline_fill_at=available if base["shares"] else None)
        if base["shares"]:
            # Order lifetime ends this calendar day; no overnight session inference.
            candidates = [LakeBar(day, int(r.hm), float(r.open), float(r.close))
                          for r in day_frame.loc[day_frame.index > quote].itertuples()]
            alt, attempts = next_open(engine=engine, side="buy", decision_at=available,
                                      candidates=candidates, previous_by_day={day: row["limit_reference_px"]},
                                      shares=base["shares"], cash=1_000_000., symbol=symbol, sessions=(day,))
        else:
            alt, attempts = dict(status=base["status"], reason="no_baseline_order",
                                 fill_at=None, fill_px=None, shares=base["shares"],
                                 cash_after=base["cash_after"]), []
        row.update({"next_" + k: v for k, v in alt.items()})
        if base["status"] != "DATA_GAP":
            common = bool(base["shares"] and alt["shares"])
            row.update(matched_fill=common, status_match=bool(base["shares"]) == bool(alt["shares"]))
            if common:
                row.update(same_price=math.isclose(base["fill_px"], alt["fill_px"], abs_tol=1e-9),
                           price_diff=alt["fill_px"] - base["fill_px"],
                           price_diff_bp=(alt["fill_px"] / base["fill_px"] - 1) * 10_000)
        # A predeclared next-calendar-day 14:55 close price pair, never an exit replay.
        exit_at = stamp(day + timedelta(days=1), 895)
        if exit_at in frame.index and base["shares"]:
            exit_px = float(frame.at[exit_at, "close"])
            old = economics(base["fill_px"], exit_px, base["shares"])
            row.update(fixed_exit_px=exit_px, exit_mark_at=exit_at,
                       local_pair_status="PRICE_PAIR_ONLY_NOT_EXECUTED_EXIT",
                       baseline_local_pnl=old["net_pnl"], baseline_local_return=old["net_return"])
            if row["matched_fill"]:
                new = economics(alt["fill_px"], exit_px, alt["shares"])
                row.update(next_local_pnl=new["net_pnl"], next_local_return=new["net_return"],
                           local_pnl_delta=new["net_pnl"] - old["net_pnl"],
                           local_return_delta_bp=(new["net_return"] - old["net_return"]) * 10_000)
        elif not base["shares"] and base["status"] != "DATA_GAP":
            row["local_pair_status"] = "NO_FILL"
        # A missing/untyped volume lookup is intentional, never fabricated shares.
        capped = lake_baseline(**kwargs, cap=VolumeCap(.1, {}))
        capacities = [dict(cap_on=False, participation_rate=None, **base),
                      dict(cap_on=True, participation_rate=.1, **capped)]
    if not capacities:
        capacities = [dict(cap_on=enabled, participation_rate=.1 if enabled else None,
                           status="DATA_GAP", reason=row["baseline_reason"], shares=None,
                           fill_px=None, cash_after=None) for enabled in (False, True)]
    capacities = [dict(engine=engine, case_id=row["case_id"], symbol=symbol, scope=LAKE_SCOPE,
                       axis="capacity_close", volume_status="DATA_GAP", raw_volume=None,
                       volume_unit=None, available_at=None, bucket=hm + 1,
                       note="reader_drops_volume_no_audited_units_or_availability",
                       **c, **FULL_GAPS) for c in capacities]
    return row, [dict(engine=engine, case_id=row["case_id"], symbol=symbol, **a) for a in attempts], capacities


def lake_cost_rows(clocks: list[dict]) -> list[dict]:
    rows = []
    scenarios = [("slippage", "BILATERAL_10BP", bp) for bp in (0, 5, 10, 20)]
    scenarios += [("fee", scheme, 0) for scheme in
                  ("BILATERAL_10BP", "REPLACE_COMMISSION_3BP_MIN5_STAMP_SELL5BP")]
    for r in clocks:
        paired = r["local_pair_status"] == "PRICE_PAIR_ONLY_NOT_EXECUTED_EXIT"
        for axis, scheme, bp in scenarios:
            econ = economics(r["baseline_fill_px"], r["fixed_exit_px"], r["baseline_shares"],
                             slip_bp=bp, scheme=scheme) if paired else {}
            rows.append(dict(engine=r["engine"], case_id=r["case_id"], scope=LAKE_SCOPE,
                             axis=axis, scheme=scheme, slip_per_side_bp=bp,
                             status=r["local_pair_status"], shares=r["baseline_shares"],
                             buy_px=None, sell_px=None, buy_fee=None, sell_fee=None, stamp_fee=None,
                             net_pnl=None, net_return=None, **FULL_GAPS))
            rows[-1].update(econ, pnl_delta=(econ["net_pnl"] - r["baseline_local_pnl"] if paired else None),
                            return_delta_bp=((econ["net_return"] - r["baseline_local_return"]) * 10_000
                                             if paired else None))
    rows.append(dict(engine="ModeB", scope=LAKE_SCOPE, status="NOT_RUN", **FULL_GAPS))
    return rows


def lake_summaries(clocks: list[dict]) -> list[dict]:
    rows = []
    for engine in ("Book", "v7"):
        group = [r for r in clocks if r["engine"] == engine]
        valid = [r for r in group if r["baseline_status"] != "DATA_GAP"]
        base = [r for r in valid if r["baseline_shares"]]
        common = [r for r in valid if r["matched_fill"]]
        rows.append(dict(engine=engine, scope=LAKE_SCOPE,
                         clock_status="LOCAL_EVENTS_COMPLETE" if len(valid) == len(group) else "DATA_GAP",
                         requested_events=len(group), evaluated_events=len(valid),
                         data_gap_events=len(group) - len(valid),
                         baseline_fills=len(base) if valid else None,
                         next_fills=sum(bool(r["next_shares"]) for r in valid) if valid else None,
                         common_fills=len(common) if valid else None,
                         status_match_rate=sum(r["status_match"] for r in valid) / len(valid) if valid else None,
                         matched_fill_rate=len(common) / len(base) if base else None,
                         same_price_rate=sum(r["same_price"] for r in common) / len(common) if common else None,
                         mean_price_diff_bp=np.mean([r["price_diff_bp"] for r in common]) if common else None,
                         **FULL_GAPS))
    rows.append(dict(engine="ModeB", scope=LAKE_SCOPE, clock_status="NOT_RUN", **FULL_GAPS))
    return rows



def resolve_qlib_1min_root(explicit: Path | str | None = None) -> Path | None:
    """Prefer explicit CLI, then env; never invent alternate drive letters."""
    candidates = []
    if explicit is not None:
        candidates.append(Path(explicit))
    for key in ("QLIB_1MIN_ROOT", "OSKH_QLIB_1MIN_ROOT"):
        value = os.environ.get(key)
        if value:
            candidates.append(Path(value))
    candidates.append(DEFAULT_QLIB_1MIN_ROOT)
    for root in candidates:
        cal = root / "calendars" / "1min.txt"
        feat = root / "features"
        if cal.is_file() and feat.is_dir():
            return root
    return None


def normalize_book_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Ensure book-engine OHLC envelope; qlib compact often omits low."""
    out = frame.copy()
    oc_min = out[["open", "close"]].min(axis=1)
    oc_max = out[["open", "close"]].max(axis=1)
    low = out["low"] if "low" in out.columns else oc_min
    high = out["high"] if "high" in out.columns else oc_max
    out["low"] = np.minimum(low.to_numpy(dtype=float), oc_min.to_numpy(dtype=float))
    out["high"] = np.maximum(high.to_numpy(dtype=float), oc_max.to_numpy(dtype=float))
    return out


def load_minute_frames(symbols: list[str], start: str, end: str, *,
                       qlib_root: Path | str | None = None
                       ) -> tuple[dict, str | None, Path | None, Path | None, Path | None, list[dict]]:
    """Same parquet lineage; prefer qlib 1min bin I/O, fall back to OSKH parquet.

    Returns frames, access, qlib_root_used, period_root, lake_root, inventory.
    """
    gaps_extra: list[dict] = []
    inventory: list[dict] = []
    start_d = datetime.strptime(start, "%Y%m%d").date()
    end_d = datetime.strptime(end, "%Y%m%d").date()
    chosen = resolve_qlib_1min_root(qlib_root)
    if chosen is not None:
        try:
            compact = load_qlib_bin_1min_bars(symbols, start_d, end_d, qlib_root=chosen, workers=4)
            frames = {code: normalize_book_frame(frame)
                      for code, frame in book_frames_from_compact(compact).items()}
            # Restrict to requested window (loader may preload prior days).
            clipped = {}
            for code, frame in frames.items():
                keep = (frame["ymd"] >= start) & (frame["ymd"] <= end)
                clipped[code] = frame.loc[keep]
            inventory.append(dict(access="qlib_bin_1min", qlib_root=str(chosen),
                                  status="PRESENT", symbols=sorted(clipped)))
            return clipped, "qlib_bin_1min", chosen, None, None, inventory
        except (OSError, ValueError, SystemExit, RuntimeError) as exc:
            gaps_extra.append(dict(item="qlib_bin_1min_load", status="DATA_GAP",
                                   evidence=f"{type(exc).__name__}: {exc}; falling_back_to_parquet"))

    period_root = lake_root = None
    try:
        period_root = resolve_period_root("1m")
        lake_root = period_root / "dividend_type=none"
        if not period_root.is_dir() or not lake_root.is_dir():
            raise FileNotFoundError(f"Configured minute/none directory does not exist: {lake_root}")
    except (RuntimeError, ValueError, OSError) as exc:
        inventory.extend(gaps_extra)
        inventory.append(dict(access="oskh_parquet_1m", status="DATA_GAP",
                              evidence=f"{type(exc).__name__}: {exc}"))
        return {}, None, chosen, period_root, lake_root, inventory

    from backtest.research.ashare_bars import to_partition_key
    for symbol in symbols:
        path = lake_root / f"symbol={to_partition_key(symbol)}" / "data.parquet"
        try:
            stat = path.stat()
            inventory.append(dict(symbol=symbol, path=str(path), size=stat.st_size,
                                  mtime_ns=stat.st_mtime_ns, status="PRESENT",
                                  access="oskh_parquet_1m"))
        except OSError as exc:
            inventory.append(dict(symbol=symbol, path=str(path), status="DATA_GAP",
                                  error=str(exc), access="oskh_parquet_1m"))
    loaded = load_minute_from_lake(symbols, start, end, lake_root=lake_root)
    frames = {symbol: normalize_book_frame(frame) for symbol, frame in loaded.items()
              if frame is not None and not frame.empty}
    inventory = gaps_extra + inventory
    return frames, "oskh_parquet_1m", chosen, period_root, lake_root, inventory


def run_lake(output: Path, *, symbols=None, start="20260916", end="20260918",
             qlib_1min_root: Path | str | None = None) -> dict:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite output directory: {output}")
    dates, symbols = lake_dates(start, end), lake_symbols(symbols)
    before = check_source_fence()  # Fatal drift is never downgraded to DATA_GAP.
    reader_sources = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                      ("backtest/research/ashare_bars.py", "common/infra/data_root.py",
                       "backtest/research/qlib_bin_1min.py")}
    gaps, publication = [], publication_gaps()
    frames, access, qlib_used, period_root, lake_root, inventory = load_minute_frames(
        symbols, start, end, qlib_root=qlib_1min_root)
    lake_status = "DATA_GAP"
    if access is None:
        gaps.append(dict(item="production_minute_source", status="DATA_GAP",
                         evidence="qlib_bin_1min unavailable and parquet resolver/root missing; no drive probing",
                         inventory=json.dumps(inventory, ensure_ascii=False)))
    else:
        for symbol in symbols:
            frame = frames.get(symbol)
            try:
                if frame is None or frame.empty:
                    raise ValueError("Missing/unreadable/filtered symbol window; reader gives no detailed failure")
                validate_lake_frame(frame, start, end)
            except (ValueError, KeyError, TypeError) as exc:
                gaps.append(dict(item="symbol_window", symbol=symbol, status="DATA_GAP",
                                 evidence=str(exc), access=access))
                frames.pop(symbol, None)
            else:
                frames[symbol] = frame
        # Parquet integrity: size/mtime unchanged after read.
        if access == "oskh_parquet_1m":
            for item in inventory:
                if item.get("status") == "PRESENT" and "path" in item:
                    stat = Path(item["path"]).stat()
                    if (stat.st_size, stat.st_mtime_ns) != (item["size"], item["mtime_ns"]):
                        raise RuntimeError(f"Lake source changed while reading: {item['path']}")
        lake_status = "READ_OK" if len(frames) == len(symbols) else "DATA_GAP"
    gaps = publication + gaps
    gaps.extend(dict(item=item, status="DATA_GAP", evidence=evidence) for item, evidence in (
        ("real_volume_and_units", "OHLC path drops or lacks attested incremental shares/available_at"),
        ("official_limit_reference_and_corporate_actions", "Uses prior calendar-date 15:00 minute close proxy only; no official daily/name/ST/exdiv validation"),
        ("closed_cash_path_daily_marks_corporate_actions", "Independent injected events; no strategy NAV/DD/rank"),
        ("modeb_replay", "NOT_RUN; daily entry, instance calendar and clock not replayed")))
    clocks, audits, capacities = [], [], []
    for symbol in symbols:
        for day in dates:
            specs = [("Book", 585, "pending_chase")]
            specs += [("v7", hm, stage) for hm in (884, 885, 895) for stage in STAGES]
            for engine, hm, stage in specs:
                row, attempts, cap = lake_event(frames.get(symbol), engine=engine, symbol=symbol,
                                               day=day, hm=hm, stage=stage)
                row["source"] = access or "unavailable"
                row["source_lineage"] = SOURCE_LINEAGE
                clocks.append(row)
                audits.extend(attempts)
                capacities.extend(cap)
                if row["baseline_status"] == "DATA_GAP" or row["local_pair_status"] == "DATA_GAP":
                    gaps.append(dict(item="event", engine=engine, case_id=row["case_id"], status="DATA_GAP",
                                     evidence=row["baseline_reason"] if row["baseline_status"] == "DATA_GAP"
                                     else "missing_next_calendar_day_1455_exit_mark"))
    snapshots = [dict(symbol=symbol, bar_start=at, bar_end=at + timedelta(minutes=1),
                      bar_label_semantics=LAKE_LABEL, access=access, source_lineage=SOURCE_LINEAGE, **r)
                 for symbol, frame in sorted(frames.items())
                 for at, r in frame.to_dict("index").items()]
    if not snapshots:
        snapshots = [dict(symbol=s, status="DATA_GAP", bar_start=None, bar_end=None,
                          open=None, high=None, low=None, close=None) for s in symbols]
    payloads = {"clock_trades.csv": clocks, "clock_candidates.csv": audits,
                "clock_summary.csv": lake_summaries(clocks), "cost_sensitivity.csv": lake_cost_rows(clocks),
                "capacity.csv": capacities, "minute_frames.csv": snapshots, "data_gaps.csv": gaps,
                "modeb_baseline.csv": [dict(engine="ModeB", status="NOT_RUN", clock_status="NOT_RUN",
                                             scope=LAKE_SCOPE, **FULL_GAPS)]}
    if source_hashes() != before or any(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != digest
                                       for p, digest in reader_sources.items()):
        raise RuntimeError("Production source changed during run")
    output.mkdir(parents=True, exist_ok=False)
    for filename, rows in payloads.items():
        fields = ("engine", "case_id", "symbol", "candidate_start", "candidate_end", "submit_at",
                  "candidate_px", "previous_close", "outcome", "candidate_shares") if filename == "clock_candidates.csv" else ()
        write_csv(output / filename, rows, fields)
    manifest = dict(base=BASE, batch=2, mode="lake", git_head=subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), status="DATA_GAP",
        lake_read_status=lake_status, scope=LAKE_SCOPE, production_replay="DATA_GAP",
        source=SOURCE_LINEAGE, access=access, access_preference="qlib_bin_1min_then_oskh_parquet_1m",
        OSKH_SOURCE_PARQUET_ROOT=os.environ.get("OSKH_SOURCE_PARQUET_ROOT") or "unset",
        OSKH_AUTHORITY_HINT_ROOT=os.environ.get("OSKH_AUTHORITY_HINT_ROOT") or "unset",
        OSKH_PERIOD_1M_ROOT=os.environ.get("OSKH_PERIOD_1M_ROOT") or "unset",
        QLIB_1MIN_ROOT=os.environ.get("QLIB_1MIN_ROOT") or os.environ.get("OSKH_QLIB_1MIN_ROOT") or "unset",
        qlib_1min_root=str(qlib_used) if qlib_used is not None else None,
        default_qlib_1min_root=str(DEFAULT_QLIB_1MIN_ROOT),
        resolved_1m_root=str(period_root) if period_root is not None else None,
        lake_root=str(lake_root) if lake_root is not None else None, symbols=symbols,
        date_window=dict(start=start, end=end, format="YYYYMMDD"),
        bar_label_semantics=LAKE_LABEL, timezone="Asia/Shanghai",
        bar_label_evidence="4090 operator verified 600000.SH 20260916/17/18: hm585=09:45 START; qlib 1min bins dumped from none-adjusted 1m lake",
        note_same_dataset="qlib_bin is derived materialization of parquet lake; not a competing universe",
        close_available="bar.start + 1 minute", submit="close_available + 1 millisecond",
        next_open="first same-date continuous-session bar.start >= submit; expires at day end",
        same_close="original helper price; bookkeeping timestamp at close_available; no live fill assertion",
        injected_state="Book pending 10000 cash budget; v7 four independent stages, 100-share lot at earliest prior-date 09:30 real open; cash=1000000/event; gates pre-passed except local rules",
        limit_reference="prior calendar-date 15:00 minute close proxy; missing is DATA_GAP; no official daily/ST/exdiv claim",
        cost_exit="next calendar-date 14:55 close, predetermined price-only pair; no executable exit claim",
        volume_cap="separate p=0.1 scenario with unavailable typed volume, no fabricated volume",
        local_rank="NOT_RUN", quantities="clock/cost frozen from original baseline ledger",
        python=sys.version, pandas=pd.__version__, numpy=np.__version__,
        checked_sources_match_base=True, source_hashes_before=before, source_hashes_after=source_hashes(),
        reader_source_hashes=reader_sources,
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_files=inventory, input_provenance="qlib bin or parquet source; no full partition hash; no drive letter probing",
        files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())})
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dict(output=str(output), status="DATA_GAP", lake_read_status=lake_status, access=access,
                rows={k: len(v) for k, v in payloads.items()})



def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New, non-existing artifact directory")
    parser.add_argument("--mode", choices=("synthetic", "lake"), default=None,
                        help="Default: synthetic; --batch 2 selects lake (minute event batch)")
    parser.add_argument("--batch", choices=(1, 2), type=int)
    parser.add_argument("--symbols", action="append", help="Repeatable or comma-separated; default 600000.SH")
    parser.add_argument("--start", default="20260916", help="Minute window start YYYYMMDD")
    parser.add_argument("--end", default="20260918", help="Minute window end YYYYMMDD")
    parser.add_argument("--qlib-1min-root", type=Path, default=None,
                        help="Preferred qlib 1min bin root (default 4090 my_data_1min; env QLIB_1MIN_ROOT)")
    args = parser.parse_args()
    alias = {1: "synthetic", 2: "lake"}.get(args.batch)
    if alias and args.mode and args.mode != alias:
        parser.error("--batch and --mode disagree")
    mode = args.mode or alias or "synthetic"
    result = (run_lake(args.output_dir, symbols=args.symbols, start=args.start, end=args.end,
                       qlib_1min_root=args.qlib_1min_root)
              if mode == "lake" else run(args.output_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
