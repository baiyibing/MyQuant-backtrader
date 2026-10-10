"""Frozen, data-free OFF matrix captured before X-01 at eff77f3.

The production writers are called unchanged. Their bytes are never normalized:
the shared pandas writer uses Linux LF and the standalone v7 csv writer CRLF.
The independent library serialization explicitly pins those same line endings.
Run this script with --check after implementation; generation refuses another
HEAD or an existing golden, so updating a baseline cannot hide a regression.
Checks retain the eff77f3 bytes/account contract and require the single #205
metadata addition. Canonical CSV/account checks always run; raw byte checks
require the golden's pandas major.minor (otherwise --check reports SKIP).
Six per_name strategy-8 books use the explicit 2026-09-26 correction overlay;
other historical cases use the immutable files unless explicitly overlaid.
version12 uses the 2026-10-04 whole-position MA10-stop overlay (69cf371);
--record-s12 records only its daily/minute cases and refuses overwrite.
version9 uses the 2026-10-05 trailing 20-day twice mean true range overlay;
--record-s9 records only its daily/minute cases and refuses overwrite.
version6_1 (20th book, bee0b91) is covered by a scoped additive overlay
(precedent #212): historical golden stays 19 books / 39 cases; --record-v61
writes only the two new cases and refuses overwrite. --record-s8 unchanged.
version9_1 (21st book) uses a scoped additive overlay; --record-v91 writes
only its daily/minute cases and refuses overwrite.
version9_2 (22nd book) uses the scoped additive 2026-10-04 overlay;
--record-v92 writes only its daily/minute cases; a new rule revision may replace that overlay.
version9_3 uses a scoped additive overlay; --record-v93 writes only its
daily/minute cases; a new rule revision may replace that overlay.
See docs/backtest/s8-independent-positions-2026-09-26.md and
docs/backtest/v61-off-byte-overlay-2026-10-02.md.
The 6.2-6.49 family (48 books, V6F overlay through v23) uses a scoped additive
overlay; --record-v6f writes its daily/minute cases and refuses overwrite.
version6_50 uses a scoped additive overlay; --record-v650 writes only its
daily/minute cases and refuses overwrite of this revision. Parking execution
is a new 20261008-park revision; the prior cont-rebuy overlay file stays.
Coverage for --check is asserted via assert_baseline_coverage() (registry-derived;
no hardcoded book/case totals beyond the frozen historical 19/39).
Industry overlays are additive and profile-scoped. P03-P10 stay immutable;
--record-industry-p11 uses only tests/fixtures/industry/v7_chronological.json
and refuses overwrite. P11 is the active industry revision.
--record-industry-default records the full CASES matrix with rule_profile
"industry" and the historical frozen_inputs path (no specialty fixture), while
leaving every historical, P03-P11, and prior industry-default golden immutable.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import inspect
import io
import json
import platform
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from backtest.research import csv_daily_backtest as daily
from backtest.research import csv_minute_backtest as minute
from backtest.research import csv_minute_backtest_v7 as v7
from backtest.research.csv_artifacts import write_run_artifacts
from backtest.research.csv_strategy_books import BOOKS

SOURCE = "eff77f375f5636e3e9659aa8fd753404035f2782"
GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_eff77f3.json"
CANONICAL_GOLDEN = ROOT / "tests/fixtures/off_canonical_baseline_eff77f3.json"
HISTORICAL_GOLDEN_SHA256 = "3bfe51b6d3e20b665c3fed0449ebf8569988022719da275b7fcc9635a9988c6c"
HISTORICAL_CANONICAL_SHA256 = "34f611da359f1a1d059bc78be75b2e9e2458c533b1dc3b46cfd61130fca7a04e"
S8_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_s8_independent_20260926.json"
S8_RULE_REVISION = "s8-independent-group-exits-2026-09-26"
S8_BOOK_NAMES = ("version8", "version8_2", "version8_3", "version8_4", "version8_5", "version8_6")
S8_CASES = tuple((book, engine) for book in S8_BOOK_NAMES for engine in ("daily", "minute"))
# Immutable eff77f3 matrix (19 books). New books extend via scoped overlay (#212).
HISTORICAL_BOOK_NAMES = (
    "version1", "version2", "version3", "version4", "version5", "version6",
    "version8", "version8_1", "version8_2", "version8_3", "version8_4",
    "version8_5", "version8_6", "version9", "version10", "version11",
    "version12", "topk_dropout", "topk_score_exit",
)
HISTORICAL_CASES = tuple(
    (book, engine) for book in HISTORICAL_BOOK_NAMES for engine in ("daily", "minute")
) + (("version7", "minute"),)
# v61 第一代 overlay（20261002）被首仓锚修复（stats 新增 cost_anchor 等）取代；
# 新修订路径未录制前，v6_1 用例跳过（见 test 端守卫）。
V61_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_v61_anchorfix_20261005.json"
V61_RULE_REVISION = "v61-first-lot-anchor-20261005"
V61_BOOK_NAMES = ("version6_1",)
V61_CASES = tuple((book, engine) for book in V61_BOOK_NAMES for engine in ("daily", "minute"))
V91_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_v91_20261004.json"
V91_RULE_REVISION = "v91-atr-turtle-20261004"
V91_BOOK_NAMES = ("version9_1",)
V91_CASES = tuple((book, engine) for book in V91_BOOK_NAMES for engine in ("daily", "minute"))
V92_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_v92_20261004.json"
V92_RULE_REVISION = "v92-range-absolute-stop-hold20-20261005"
V92_BOOK_NAMES = ("version9_2",)
V92_CASES = tuple((book, engine) for book in V92_BOOK_NAMES for engine in ("daily", "minute"))
V93_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_v93_20261006.json"
V93_RULE_REVISION = "v93-delay3-fixed-stop-tp10-hold20-20261006"
V93_BOOK_NAMES = ("version9_3",)
V93_CASES = tuple((book, engine) for book in V93_BOOK_NAMES for engine in ("daily", "minute"))
S12_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_s12_ma10_stop_20261004.json"
S12_RULE_REVISION = "s12-whole-position-ma10-stop-69cf371"
S12_BOOK_NAMES = ("version12",)
S12_CASES = tuple((book, engine) for book in S12_BOOK_NAMES for engine in ("daily", "minute"))
S9_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_s9_range_amp_20_trailing_20261004.json"
S9_RULE_REVISION = "s9-range-amp-20-trailing-20261004"
S9_BOOK_NAMES = ("version9",)
S9_CASES = tuple((book, engine) for book in S9_BOOK_NAMES for engine in ("daily", "minute"))
V6F_BOOK_NAMES = (
    "version6_2", "version6_3", "version6_4", "version6_5", "version6_6",
    "version6_7", "version6_8", "version6_9", "version6_10", "version6_11",
    "version6_12", "version6_13", "version6_14", "version6_15", "version6_16", "version6_17", "version6_18", "version6_19", "version6_20", "version6_21", "version6_22", "version6_23", "version6_24", "version6_25", "version6_26",
    "version6_27", "version6_28", "version6_29", "version6_30", "version6_31", "version6_32",
    "version6_33", "version6_34", "version6_35",
    "version6_36", "version6_37", "version6_38",
    "version6_39", "version6_40", "version6_41",
    "version6_42", "version6_43", "version6_44",
    "version6_45", "version6_46", "version6_47",
    "version6_48", "version6_49",
)
V6F_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_v6_family_v23_20261007.json"
V6F_RULE_REVISION = 'strategy6-family-v23-6_2-to-6_49-20261007'
V6F_CASES = tuple((book, engine) for book in V6F_BOOK_NAMES for engine in ("daily", "minute"))
V650_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_v650_parking_exec_20261008.json"
V650_RULE_REVISION = "v650-parking-exec-20261008"
V650_BOOK_NAMES = ("version6_50",)
V650_CASES = tuple((book, engine) for book in V650_BOOK_NAMES for engine in ("daily", "minute"))
# Registered in BOOKS but not yet in an authorized off-byte overlay.
PENDING_BOOK_NAMES = ("version6_51", "version6_52", "version6_53", "version6_54", "version6_55")
P03_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_industry_p03_order_commission_20261006.json"
P03_RULE_REVISION = "industry-p03-order-commission-20261006"
P03_BOOK_NAMES = ("version6", "version7", "version8")
P03_CASES = (
    ("version6", "daily"),
    ("version6", "minute"),
    ("version7", "minute-native"),
    ("version7", "standalone"),
    ("version8", "s8-group"),
)
P03_FIXTURE = ROOT / "tests/fixtures/industry/order_commission.json"
P04_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_industry_p04_stamp_duty_20261006.json"
P04_RULE_REVISION = "industry-p04-stamp-duty-20261006"
P04_BOOK_NAMES = ("version6", "version7", "version8")
P04_CASES = (
    ("version6", "daily-pre-cutover"),
    ("version6", "minute-post-cutover"),
    ("version7", "minute-native-pre-cutover"),
    ("version7", "standalone-post-cutover"),
    ("version8", "s8-group-post-cutover"),
)
P04_FIXTURE = ROOT / "tests/fixtures/industry/stamp_duty.json"
P05_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_industry_p05_transfer_fee_20261006.json"
P05_RULE_REVISION = "industry-p05-transfer-fee-20261006"
P05_BOOK_NAMES = ("version6", "version7", "version8")
P05_CASES = (
    ("version6", "daily-pre-cutover"),
    ("version6", "minute-post-cutover"),
    ("version7", "minute-native-pre-cutover"),
    ("version7", "standalone-post-cutover"),
    ("version8", "s8-group-post-cutover"),
)
P05_FIXTURE = ROOT / "tests/fixtures/industry/transfer_fee.json"
P06_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_industry_p06_no_topup_20261006.json"
P06_RULE_REVISION = "industry-p06-no-topup-20261006"
P06_BOOK_NAMES = ("version6",)
P06_CASES = (
    ("version6", "daily"),
    ("version6", "minute"),
)
P06_FIXTURE = ROOT / "tests/fixtures/industry/no_topup.json"
P07_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_industry_p07_fee_aware_sizing_20261006.json"
P07_RULE_REVISION = "industry-p07-fee-aware-sizing-20261006"
P07_BOOK_NAMES = ("version6", "version7")
P07_CASES = (
    ("version6", "daily"),
    ("version6", "minute"),
    ("version7", "minute-native"),
    ("version7", "standalone"),
)
P07_FIXTURE = ROOT / "tests/fixtures/industry/fee_aware_sizing.json"
P08_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_industry_p08_shrink_on_short_cash_20261006.json"
P08_RULE_REVISION = "industry-p08-shrink-on-short-cash-20261006"
P08_BOOK_NAMES = ("version8",)
P08_CASES = (
    ("version8", "daily"),
    ("version8", "minute"),
)
P08_FIXTURE = ROOT / "tests/fixtures/industry/shrink_on_short_cash.json"
P09_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_industry_p09_quantity_rules_20261006.json"
P09_RULE_REVISION = "industry-p09-quantity-rules-20261006"
P09_BOOK_NAMES = ("version6", "version7")
P09_CASES = tuple(
    (book, f"{engine}-{board}")
    for book, engines in (
        ("version6", ("daily", "minute")),
        ("version7", ("minute-native", "standalone")),
    )
    for engine in engines
    for board in ("star", "bse")
)
P09_FIXTURE = ROOT / "tests/fixtures/industry/quantity_rules.json"
P10_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_industry_p10_odd_lot_exit_20261006.json"
P10_RULE_REVISION = "industry-p10-odd-lot-exit-20261006"
P10_BOOK_NAMES = ("version9_2",)
P10_CASES = (("version9_2", "scale-out-star"),)
P10_FIXTURE = ROOT / "tests/fixtures/industry/odd_lot_exit.json"
P11_GOLDEN = ROOT / "tests/fixtures/off_byte_baseline_industry_p11_v7_chronological_20261006.json"
P11_RULE_REVISION = "industry-p11-v7-chronological-20261006"
P11_BOOK_NAMES = ("version7",)
P11_CASES = (
    ("version7", "minute-native"),
    ("version7", "standalone"),
)
P11_FIXTURE = ROOT / "tests/fixtures/industry/v7_chronological.json"
BOOK_NAMES = (
    HISTORICAL_BOOK_NAMES + V61_BOOK_NAMES + V91_BOOK_NAMES + V92_BOOK_NAMES
    + V93_BOOK_NAMES + V6F_BOOK_NAMES + V650_BOOK_NAMES
)
CODE = "600000.SH"
TOPK_CODES = (CODE, "600001.SH", "600002.SH")
CASES = tuple((book, engine) for book in BOOK_NAMES for engine in ("daily", "minute")) + (
    ("version7", "minute"),
)
INDUSTRY_DEFAULT_PREVIOUS_GOLDEN = (
    ROOT / "tests/fixtures/off_byte_baseline_industry_default_20261008.json"
)
INDUSTRY_DEFAULT_GOLDEN = (
    ROOT / "tests/fixtures/off_byte_baseline_industry_default_20261008_park.json"
)
INDUSTRY_DEFAULT_RULE_REVISION = "industry-default-20261008-park"
INDUSTRY_DEFAULT_BOOK_NAMES = BOOK_NAMES
INDUSTRY_DEFAULT_CASES = CASES
# Eight decimal places retain sub-cent fills/fees while removing float tails.
MONEY_QUANTUM = Decimal("0.00000001")
MONEY_FIELDS = frozenset({"price", "notional", "commission", "cash", "holdings", "equity"})
INTEGER_FIELDS = frozenset({"shares", "lot", "hm"})
CANONICAL_CONTRACT = {
    "schema": 1,
    "money_quantum": str(MONEY_QUANTUM),
    "rounding": "ROUND_HALF_EVEN",
    "money_fields": sorted(MONEY_FIELDS),
    "integer_fields": sorted(INTEGER_FIELDS),
    "text": "verbatim; preserve all columns and row/column order, including EOD_MARK",
    "hash": "sha256 of UTF-8 JSON; ensure_ascii=False, sort_keys=True, separators=(',', ':')",
}
P04_CANONICAL_CONTRACT = {
    **CANONICAL_CONTRACT,
    "money_fields": sorted(MONEY_FIELDS | {"stamp_duty"}),
}
P05_CANONICAL_CONTRACT = {
    **CANONICAL_CONTRACT,
    "money_fields": sorted(MONEY_FIELDS | {"stamp_duty", "transfer_fee"}),
}
P06_CANONICAL_CONTRACT = P05_CANONICAL_CONTRACT
P07_CANONICAL_CONTRACT = P05_CANONICAL_CONTRACT
P08_CANONICAL_CONTRACT = P05_CANONICAL_CONTRACT
P09_CANONICAL_CONTRACT = P05_CANONICAL_CONTRACT
P10_CANONICAL_CONTRACT = P05_CANONICAL_CONTRACT
P11_CANONICAL_CONTRACT = P05_CANONICAL_CONTRACT
INDUSTRY_DEFAULT_CANONICAL_CONTRACT = {
    **P11_CANONICAL_CONTRACT,
    "empty_numeric": (
        "preserve empty string when an EOD_MARK row predates a later-added fee column"
    ),
}


# 突破书（6.11/6.12）专用合成路径：涨跌停约束内的 1.25x 突破 + 加仓 + 回落离场。
BREAKOUT_PRICES = [10.] * 12 + [10., 10.5, 11.5, 12.5, 13.0, 13.5, 12.2] + [11.0] * 6


def frozen_inputs(prices=None):
    """Quarter/eighth prices avoid dependency-sensitive numeric construction."""
    dates = pd.bdate_range("2025-10-13", periods=25)
    if prices is None:
        prices = [10.] * 12 + [10., 10.5, 10.75, 11., 10.5, 9.75, 9.25,
                               9.75, 10.25, 10., 9.75, 10.25, 10.]
    bars = pd.DataFrame({
        "open": [p - .125 for p in prices],
        "high": [p + .25 for p in prices],
        "low": [p - .25 for p in prices],
        "close": prices,
        "volume": [100_000.] * len(prices),
    }, index=dates, dtype="float64")
    rows = []
    for day, price in zip(dates, prices):
        for hm, offset in ((570, -.125), (585, 0.), (870, .125), (895, 0.), (900, 0.)):
            rows.append({
                "time": day + pd.Timedelta(minutes=hm),
                "open": price - .125, "high": price + .25,
                "low": price - .25, "close": price + offset,
                "volume": 10_000., "ymd": day.strftime("%Y%m%d"), "hm": hm,
            })
    minutes = pd.DataFrame(rows).set_index("time")
    start, end = (dates[i].strftime("%Y%m%d") for i in (12, -1))
    pools = {dates[j].strftime("%Y%m%d"): [CODE] for j in (12, 14, 18)}
    return bars, minutes, pools, start, end, dates


def _eligible_buy(_code, _day):
    return True


def _p03_inputs():
    fixture = json.loads(P03_FIXTURE.read_text(encoding="utf-8"))
    daily_index = pd.to_datetime(fixture["daily_days"])
    bars = pd.DataFrame(
        fixture["daily_rows"],
        columns=["open", "high", "low", "close"],
        index=daily_index,
        dtype="float64",
    )
    minute_rows = fixture["minute_rows"]
    minutes = pd.DataFrame(
        [row[1:5] + [pd.Timestamp(row[0]).strftime("%Y%m%d"), row[5]] for row in minute_rows],
        columns=["open", "high", "low", "close", "ymd", "hm"],
        index=pd.to_datetime([row[0] for row in minute_rows]),
    ).astype({"open": "float64", "high": "float64", "low": "float64", "close": "float64"})
    return fixture, {fixture["symbol"]: bars}, {fixture["symbol"]: minutes}


def _run_p03_s8_group(rule_profile):
    from backtest.research.ashare_fees import resolve_account_fee_schedule
    from backtest.research.csv_ledger import (
        SimState,
        _sell,
        bind_account_fee_schedule,
        configure_s8,
        execute_buy,
        exit_positions,
    )
    from backtest.research.rule_profile import resolve_rule_profile

    fixture, _daily_bars, _minute_bars = _p03_inputs()
    profile = resolve_rule_profile(rule_profile)
    state = SimState(cash=fixture["cash_total"])
    configure_s8(
        state,
        {"name": "version8", "sizing": "per_name", "name_budget": fixture["daily_quota"]},
    )
    if profile.account_fee_schedule:
        bind_account_fee_schedule(
            state, resolve_account_fee_schedule(profile.account_fee_schedule)
        )
    state.stats.update(
        buy_cost_rate=state.buy_cost_rate,
        sell_cost_rate=state.sell_cost_rate,
        min_cost=state.min_cost,
    )
    symbol = fixture["symbol"]
    position_id = f"{symbol}@20251103"
    assert execute_buy(
        state, symbol, 10.0, 1000.0, 0, pd.Timestamp("2025-11-03"),
        position_id=position_id, entry_signal_date="20251103",
    )
    assert execute_buy(
        state, symbol, 10.0, 1000.0, 1, pd.Timestamp("2025-11-04"),
        reason="add:step20", position_id=position_id, entry_signal_date="20251103",
    )
    position = exit_positions(
        state, symbol, 2, day=pd.Timestamp("2025-11-05")
    )[0]
    assert _sell(
        state, symbol, position, 10.0, pd.Timestamp("2025-11-05"),
        "force_sell", day_i=2,
    ) == 200
    state.stats["chase_explained"] = 0
    if profile.name == "industry":
        state.stats["rule_profile"] = profile.name
        state.stats["rule_profile_revision"] = profile.revision
    state.equity_curve.append(("20251105", state.cash))
    return state


def run_p03_case(book: str, engine: str, *, rule_profile: str = "industry"):
    fixture, daily_bars, minute_bars = _p03_inputs()
    common = {
        "total_cash": fixture["cash_total"],
        "daily_quota": fixture["daily_quota"],
        "strategy": book,
        "stop_pct": 0.02,
        "rule_profile": rule_profile,
    }
    if (book, engine) == ("version6", "daily"):
        return daily.simulate(
            daily_bars, fixture["pool_days"], fixture["start"], fixture["end"], **common
        )
    if (book, engine) == ("version6", "minute"):
        return minute.simulate(
            minute_bars, daily_bars, fixture["pool_days"],
            fixture["start"], fixture["end"], **common,
        )
    if book == "version7":
        symbol = fixture["symbol"]
        days = [date.fromisoformat(value) for value in fixture["v7_days"]]
        prices = fixture["v7_prices"]
        minute_records = {
            symbol: [
                {
                    "date": days[0], "hm": 895, "open": prices[0], "high": prices[0],
                    "low": prices[0], "close": prices[0],
                },
                {
                    "date": days[1], "hm": 570, "open": prices[1], "high": prices[1],
                    "low": prices[1], "close": prices[1],
                },
            ]
        }
        v7_daily = {
            symbol: {
                days[0] - pd.Timedelta(days=1): prices[0],
                days[0]: fixture["v7_signal_close"],
            }
        }
        pools = {days[0]: [symbol]}
        if engine == "minute-native":
            from backtest.research.minute_engine_policies import MinutePolicyContext

            return minute.simulate(
                minute_records, v7_daily, pools, days[0], days[-1],
                strategy="version7", total_cash=fixture["cash_total"],
                policy_context=MinutePolicyContext(index_days=days),
                rule_profile=rule_profile,
            )
        if engine == "standalone":
            return v7.simulate_v7(
                minute_records, v7_daily, pools, days,
                cash_total=fixture["cash_total"], rule_profile=rule_profile,
            )
    if (book, engine) == ("version8", "s8-group"):
        return _run_p03_s8_group(rule_profile)
    raise KeyError((book, engine))


def _p04_inputs(period: str):
    fixture = json.loads(P04_FIXTURE.read_text(encoding="utf-8"))
    values = fixture["periods"][period]
    daily_index = pd.to_datetime(values["daily_days"])
    bars = pd.DataFrame(
        values["daily_rows"],
        columns=["open", "high", "low", "close"],
        index=daily_index,
        dtype="float64",
    )
    minute_rows = values["minute_rows"]
    minutes = pd.DataFrame(
        [row[1:5] + [pd.Timestamp(row[0]).strftime("%Y%m%d"), row[5]]
         for row in minute_rows],
        columns=["open", "high", "low", "close", "ymd", "hm"],
        index=pd.to_datetime([row[0] for row in minute_rows]),
    ).astype(
        {"open": "float64", "high": "float64", "low": "float64", "close": "float64"}
    )
    return fixture, values, {fixture["symbol"]: bars}, {fixture["symbol"]: minutes}


def _run_p04_s8_group(rule_profile):
    from backtest.research.ashare_fees import resolve_account_fee_schedule
    from backtest.research.csv_ledger import (
        SimState,
        _sell,
        bind_account_fee_schedule,
        configure_s8,
        execute_buy,
        exit_positions,
    )
    from backtest.research.rule_profile import resolve_rule_profile

    fixture, _values, _daily_bars, _minute_bars = _p04_inputs("post")
    profile = resolve_rule_profile(rule_profile)
    state = SimState(cash=fixture["cash_total"])
    configure_s8(
        state,
        {"name": "version8", "sizing": "per_name", "name_budget": fixture["daily_quota"]},
    )
    if profile.account_fee_schedule:
        bind_account_fee_schedule(
            state, resolve_account_fee_schedule(profile.account_fee_schedule)
        )
    state.stats.update(
        buy_cost_rate=state.buy_cost_rate,
        sell_cost_rate=state.sell_cost_rate,
        min_cost=state.min_cost,
    )
    symbol = fixture["symbol"]
    position_id = f"{symbol}@20230824"
    assert execute_buy(
        state, symbol, 10.0, 1000.0, 0, pd.Timestamp("2023-08-24"),
        position_id=position_id, entry_signal_date="20230824",
    )
    assert execute_buy(
        state, symbol, 10.0, 1000.0, 1, pd.Timestamp("2023-08-25"),
        reason="add:step20", position_id=position_id, entry_signal_date="20230824",
    )
    position = exit_positions(
        state, symbol, 2, day=pd.Timestamp("2023-08-28")
    )[0]
    assert _sell(
        state, symbol, position, 10.0, pd.Timestamp("2023-08-28"),
        "force_sell", day_i=2,
    ) == 200
    state.stats["chase_explained"] = 0
    if profile.name == "industry":
        state.stats["rule_profile"] = profile.name
        state.stats["rule_profile_revision"] = profile.revision
    state.equity_curve.append(("20230828", state.cash))
    return state


def run_p04_case(book: str, engine: str, *, rule_profile: str = "industry"):
    if (book, engine) == ("version8", "s8-group-post-cutover"):
        return _run_p04_s8_group(rule_profile)
    period = "pre" if engine.endswith("pre-cutover") else "post"
    fixture, values, daily_bars, minute_bars = _p04_inputs(period)
    common = dict(
        total_cash=fixture["cash_total"],
        daily_quota=fixture["daily_quota"],
        strategy=book,
        stop_pct=0.02,
        rule_profile=rule_profile,
    )
    if (book, engine) == ("version6", "daily-pre-cutover"):
        return daily.simulate(
            daily_bars, values["pool_days"], values["start"], values["end"], **common
        )
    if (book, engine) == ("version6", "minute-post-cutover"):
        return minute.simulate(
            minute_bars, daily_bars, values["pool_days"],
            values["start"], values["end"], **common,
        )
    if book == "version7":
        symbol = fixture["symbol"]
        days = [date.fromisoformat(value) for value in values["v7_days"]]
        prices = values["v7_prices"]
        minute_records = {
            symbol: [
                {
                    "date": days[0], "hm": 895, "open": prices[0], "high": prices[0],
                    "low": prices[0], "close": prices[0],
                },
                {
                    "date": days[1], "hm": 570, "open": prices[1], "high": prices[1],
                    "low": prices[1], "close": prices[1],
                },
            ]
        }
        v7_daily = {
            symbol: {
                days[0] - pd.Timedelta(days=1): prices[0],
                days[0]: fixture["v7_signal_close"],
            }
        }
        pools = {days[0]: [symbol]}
        if engine == "minute-native-pre-cutover":
            from backtest.research.minute_engine_policies import MinutePolicyContext

            return minute.simulate(
                minute_records, v7_daily, pools, days[0], days[-1],
                strategy="version7", total_cash=fixture["cash_total"],
                policy_context=MinutePolicyContext(index_days=days),
                rule_profile=rule_profile,
            )
        if engine == "standalone-post-cutover":
            return v7.simulate_v7(
                minute_records, v7_daily, pools, days,
                cash_total=fixture["cash_total"], rule_profile=rule_profile,
            )
    raise KeyError((book, engine))


def _p05_inputs(period: str):
    fixture = json.loads(P05_FIXTURE.read_text(encoding="utf-8"))
    values = fixture["periods"][period]
    symbol = values["symbol"]
    daily_index = pd.to_datetime(values["daily_days"])
    bars = pd.DataFrame(
        values["daily_rows"],
        columns=["open", "high", "low", "close"],
        index=daily_index,
        dtype="float64",
    )
    minute_rows = values["minute_rows"]
    minutes = pd.DataFrame(
        [row[1:5] + [pd.Timestamp(row[0]).strftime("%Y%m%d"), row[5]]
         for row in minute_rows],
        columns=["open", "high", "low", "close", "ymd", "hm"],
        index=pd.to_datetime([row[0] for row in minute_rows]),
    ).astype(
        {"open": "float64", "high": "float64", "low": "float64", "close": "float64"}
    )
    return fixture, values, {symbol: bars}, {symbol: minutes}


def _run_p05_s8_group(rule_profile):
    from backtest.research.ashare_fees import resolve_account_fee_schedule
    from backtest.research.csv_ledger import (
        SimState,
        _sell,
        bind_account_fee_schedule,
        configure_s8,
        execute_buy,
        exit_positions,
    )
    from backtest.research.rule_profile import resolve_rule_profile

    fixture, values, _daily_bars, _minute_bars = _p05_inputs("post")
    profile = resolve_rule_profile(rule_profile)
    state = SimState(cash=fixture["cash_total"])
    configure_s8(
        state,
        {"name": "version8", "sizing": "per_name", "name_budget": fixture["daily_quota"]},
    )
    if profile.account_fee_schedule:
        bind_account_fee_schedule(
            state, resolve_account_fee_schedule(profile.account_fee_schedule)
        )
    state.stats.update(
        buy_cost_rate=state.buy_cost_rate,
        sell_cost_rate=state.sell_cost_rate,
        min_cost=state.min_cost,
    )
    symbol = values["symbol"]
    position_id = f"{symbol}@20220429"
    assert execute_buy(
        state, symbol, 10.0, 1000.0, 0, pd.Timestamp("2022-04-29"),
        position_id=position_id, entry_signal_date="20220429",
    )
    assert execute_buy(
        state, symbol, 10.0, 1000.0, 1, pd.Timestamp("2022-05-05"),
        reason="add:step20", position_id=position_id, entry_signal_date="20220429",
    )
    position = exit_positions(
        state, symbol, 2, day=pd.Timestamp("2022-05-06")
    )[0]
    assert _sell(
        state, symbol, position, 10.0, pd.Timestamp("2022-05-06"),
        "force_sell", day_i=2,
    ) == 200
    state.stats["chase_explained"] = 0
    if profile.name == "industry":
        state.stats["rule_profile"] = profile.name
        state.stats["rule_profile_revision"] = profile.revision
    state.equity_curve.append(("20220506", state.cash))
    return state


def run_p05_case(book: str, engine: str, *, rule_profile: str = "industry"):
    if (book, engine) == ("version8", "s8-group-post-cutover"):
        return _run_p05_s8_group(rule_profile)
    period = "pre" if engine.endswith("pre-cutover") else "post"
    fixture, values, daily_bars, minute_bars = _p05_inputs(period)
    common = dict(
        total_cash=fixture["cash_total"],
        daily_quota=fixture["daily_quota"],
        strategy=book,
        stop_pct=0.02,
        rule_profile=rule_profile,
    )
    if (book, engine) == ("version6", "daily-pre-cutover"):
        return daily.simulate(
            daily_bars, values["pool_days"], values["start"], values["end"], **common
        )
    if (book, engine) == ("version6", "minute-post-cutover"):
        return minute.simulate(
            minute_bars, daily_bars, values["pool_days"],
            values["start"], values["end"], **common,
        )
    if book == "version7":
        symbol = values["symbol"]
        days = [date.fromisoformat(value) for value in values["v7_days"]]
        prices = values["v7_prices"]
        minute_records = {
            symbol: [
                {
                    "date": days[0], "hm": 895, "open": prices[0], "high": prices[0],
                    "low": prices[0], "close": prices[0],
                },
                {
                    "date": days[1], "hm": 570, "open": prices[1], "high": prices[1],
                    "low": prices[1], "close": prices[1],
                },
            ]
        }
        v7_daily = {
            symbol: {
                days[0] - pd.Timedelta(days=1): prices[0],
                days[0]: fixture["v7_signal_close"],
            }
        }
        pools = {days[0]: [symbol]}
        if engine == "minute-native-pre-cutover":
            from backtest.research.minute_engine_policies import MinutePolicyContext

            return minute.simulate(
                minute_records, v7_daily, pools, days[0], days[-1],
                strategy="version7", total_cash=fixture["cash_total"],
                policy_context=MinutePolicyContext(index_days=days),
                rule_profile=rule_profile,
            )
        if engine == "standalone-post-cutover":
            return v7.simulate_v7(
                minute_records, v7_daily, pools, days,
                cash_total=fixture["cash_total"], rule_profile=rule_profile,
            )
    raise KeyError((book, engine))


def _p06_inputs():
    fixture = json.loads(P06_FIXTURE.read_text(encoding="utf-8"))
    daily_bars = {}
    minute_bars = {}
    for symbol, values in fixture["symbols"].items():
        daily_bars[symbol] = pd.DataFrame(
            values["daily_rows"],
            columns=["open", "high", "low", "close"],
            index=pd.to_datetime(values["daily_days"]),
            dtype="float64",
        )
        minute_rows = values["minute_rows"]
        minute_bars[symbol] = pd.DataFrame(
            [
                row[1:5] + [pd.Timestamp(row[0]).strftime("%Y%m%d"), row[5]]
                for row in minute_rows
            ],
            columns=["open", "high", "low", "close", "ymd", "hm"],
            index=pd.to_datetime([row[0] for row in minute_rows]),
        ).astype(
            {
                "open": "float64",
                "high": "float64",
                "low": "float64",
                "close": "float64",
            }
        )
    return fixture, daily_bars, minute_bars


def run_p06_case(book: str, engine: str, *, rule_profile: str = "industry"):
    if (book, engine) not in P06_CASES:
        raise KeyError((book, engine))
    fixture, daily_bars, minute_bars = _p06_inputs()
    common = dict(
        total_cash=fixture["cash_total"],
        daily_quota=fixture["daily_quota"],
        strategy=book,
        stop_pct=0.02,
        rule_profile=rule_profile,
    )
    if engine == "daily":
        return daily.simulate(
            daily_bars,
            fixture["pool_days"],
            fixture["start"],
            fixture["end"],
            **common,
        )
    return minute.simulate(
        minute_bars,
        daily_bars,
        fixture["pool_days"],
        fixture["start"],
        fixture["end"],
        **common,
    )


def _p07_inputs():
    fixture = json.loads(P07_FIXTURE.read_text(encoding="utf-8"))
    bars = pd.DataFrame(
        fixture["daily_rows"],
        columns=["open", "high", "low", "close"],
        index=pd.to_datetime(fixture["daily_days"]),
        dtype="float64",
    )
    minute_rows = fixture["minute_rows"]
    minutes = pd.DataFrame(
        [
            row[1:5] + [pd.Timestamp(row[0]).strftime("%Y%m%d"), row[5]]
            for row in minute_rows
        ],
        columns=["open", "high", "low", "close", "ymd", "hm"],
        index=pd.to_datetime([row[0] for row in minute_rows]),
    ).astype(
        {"open": "float64", "high": "float64", "low": "float64", "close": "float64"}
    )
    symbol = fixture["symbol"]
    return fixture, {symbol: bars}, {symbol: minutes}


def run_p07_case(book: str, engine: str, *, rule_profile: str = "industry"):
    if (book, engine) not in P07_CASES:
        raise KeyError((book, engine))
    fixture, daily_bars, minute_bars = _p07_inputs()
    common = dict(
        total_cash=fixture["cash_total"],
        daily_quota=fixture["daily_quota"],
        strategy=book,
        stop_pct=0.02,
        rule_profile=rule_profile,
    )
    if (book, engine) == ("version6", "daily"):
        return daily.simulate(
            daily_bars,
            fixture["pool_days"],
            fixture["start"],
            fixture["end"],
            **common,
        )
    if (book, engine) == ("version6", "minute"):
        return minute.simulate(
            minute_bars,
            daily_bars,
            fixture["pool_days"],
            fixture["start"],
            fixture["end"],
            **common,
        )
    symbol = fixture["symbol"]
    days = [date.fromisoformat(value) for value in fixture["v7_days"]]
    prices = fixture["v7_prices"]
    minute_records = {
        symbol: [
            {
                "date": days[0],
                "hm": 895,
                "open": prices[0],
                "high": prices[0],
                "low": prices[0],
                "close": prices[0],
            },
            {
                "date": days[1],
                "hm": 570,
                "open": prices[1],
                "high": prices[1],
                "low": prices[1],
                "close": prices[1],
            },
        ]
    }
    v7_daily = {
        symbol: {
            days[0] - pd.Timedelta(days=1): prices[0],
            days[0]: fixture["v7_signal_close"],
        }
    }
    pools = {days[0]: [symbol]}
    if engine == "minute-native":
        from backtest.research.minute_engine_policies import MinutePolicyContext

        return minute.simulate(
            minute_records,
            v7_daily,
            pools,
            days[0],
            days[-1],
            strategy="version7",
            total_cash=fixture["cash_total"],
            policy_context=MinutePolicyContext(index_days=days),
            rule_profile=rule_profile,
        )
    return v7.simulate_v7(
        minute_records,
        v7_daily,
        pools,
        days,
        cash_total=fixture["cash_total"],
        rule_profile=rule_profile,
    )


def _p08_inputs():
    fixture = json.loads(P08_FIXTURE.read_text(encoding="utf-8"))
    bars = pd.DataFrame(
        fixture["daily_rows"],
        columns=["open", "high", "low", "close"],
        index=pd.to_datetime(fixture["daily_days"]),
        dtype="float64",
    )
    minute_rows = fixture["minute_rows"]
    minutes = pd.DataFrame(
        [
            row[1:5] + [pd.Timestamp(row[0]).strftime("%Y%m%d"), row[5]]
            for row in minute_rows
        ],
        columns=["open", "high", "low", "close", "ymd", "hm"],
        index=pd.to_datetime([row[0] for row in minute_rows]),
    ).astype(
        {"open": "float64", "high": "float64", "low": "float64", "close": "float64"}
    )
    symbol = fixture["symbol"]
    return fixture, {symbol: bars}, {symbol: minutes}


def run_p08_case(book: str, engine: str, *, rule_profile: str = "industry"):
    if (book, engine) not in P08_CASES:
        raise KeyError((book, engine))
    fixture, daily_bars, minute_bars = _p08_inputs()
    common = dict(
        total_cash=fixture["cash_total"],
        name_budget=fixture["name_budget"],
        strategy=book,
        stop_pct=0.02,
        rule_profile=rule_profile,
    )
    if engine == "daily":
        return daily.simulate(
            daily_bars,
            fixture["pool_days"],
            fixture["start"],
            fixture["end"],
            **common,
        )
    return minute.simulate(
        minute_bars,
        daily_bars,
        fixture["pool_days"],
        fixture["start"],
        fixture["end"],
        **common,
    )


def _p09_inputs(board: str):
    fixture = json.loads(P09_FIXTURE.read_text(encoding="utf-8"))
    values = fixture["boards"][board]
    symbol = values["symbol"]
    bars = pd.DataFrame(
        values["daily_rows"],
        columns=["open", "high", "low", "close"],
        index=pd.to_datetime(values["daily_days"]),
        dtype="float64",
    )
    minute_rows = values["minute_rows"]
    minutes = pd.DataFrame(
        [
            row[1:5] + [pd.Timestamp(row[0]).strftime("%Y%m%d"), row[5]]
            for row in minute_rows
        ],
        columns=["open", "high", "low", "close", "ymd", "hm"],
        index=pd.to_datetime([row[0] for row in minute_rows]),
    ).astype(
        {"open": "float64", "high": "float64", "low": "float64", "close": "float64"}
    )
    return fixture, values, {symbol: bars}, {symbol: minutes}


def run_p09_case(book: str, engine: str, *, rule_profile: str = "industry"):
    if (book, engine) not in P09_CASES:
        raise KeyError((book, engine))
    engine_kind, board = engine.rsplit("-", 1)
    fixture, values, daily_bars, minute_bars = _p09_inputs(board)
    symbol = values["symbol"]
    names = {symbol: values["name"]}
    pools = {fixture["start"]: [symbol]}
    common = dict(
        total_cash=fixture["cash_total"],
        strategy=book,
        stop_pct=0.02,
        pool_names=names,
        rule_profile=rule_profile,
    )
    if engine_kind == "daily":
        return daily.simulate(
            daily_bars,
            pools,
            fixture["start"],
            fixture["end"],
            daily_quota=fixture["daily_quota"],
            **common,
        )
    if engine_kind == "minute":
        return minute.simulate(
            minute_bars,
            daily_bars,
            pools,
            fixture["start"],
            fixture["end"],
            daily_quota=fixture["daily_quota"],
            **common,
        )
    days = [date.fromisoformat(value) for value in values["v7_days"]]
    prices = values["v7_prices"]
    minute_records = {
        symbol: [
            {
                "date": days[0],
                "hm": 895,
                "open": prices[0],
                "high": prices[0],
                "low": prices[0],
                "close": prices[0],
            },
            {
                "date": days[1],
                "hm": 570,
                "open": prices[1],
                "high": prices[1],
                "low": prices[1],
                "close": prices[1],
            },
        ]
    }
    v7_daily = {
        symbol: {
            days[0] - pd.Timedelta(days=1): prices[0],
            days[0]: values["v7_signal_close"],
        }
    }
    v7_pools = {days[0]: [symbol]}
    if engine_kind == "minute-native":
        from backtest.research.minute_engine_policies import MinutePolicyContext

        return minute.simulate(
            minute_records,
            v7_daily,
            v7_pools,
            days[0],
            days[-1],
            strategy="version7",
            total_cash=fixture["cash_total"],
            pool_names=names,
            policy_context=MinutePolicyContext(index_days=days),
            rule_profile=rule_profile,
        )
    return v7.simulate_v7(
        minute_records,
        v7_daily,
        v7_pools,
        days,
        cash_total=fixture["cash_total"],
        names=names,
        rule_profile=rule_profile,
    )


def run_p10_case(book: str, engine: str, *, rule_profile: str = "industry"):
    """Exercise one STAR scale-out whose legacy order strands 100 shares."""
    if (book, engine) not in P10_CASES:
        raise KeyError((book, engine))
    from backtest.research.ashare_fees import INDUSTRY_ACCOUNT_FEES
    from backtest.research.csv_ledger import (
        SimState,
        bind_account_fee_schedule,
        execute_buy,
    )
    from backtest.research.rule_profile import resolve_rule_profile
    from backtest.research.strategy9_2_engine import fill_pending, memory_for, plan_exit

    fixture = json.loads(P10_FIXTURE.read_text(encoding="utf-8"))
    profile = resolve_rule_profile(rule_profile)
    state = SimState(cash=fixture["cash_total"])
    state.rule_profile = profile
    if profile.account_fee_schedule:
        bind_account_fee_schedule(state, INDUSTRY_ACCOUNT_FEES)
        state.stats["rule_profile"] = profile.name
        state.stats["rule_profile_revision"] = profile.revision

    symbol = fixture["symbol"]
    buy_day = date.fromisoformat(fixture["buy_day"])
    sell_day = date.fromisoformat(fixture["sell_day"])
    assert execute_buy(
        state,
        symbol,
        fixture["buy_price"],
        fixture["buy_budget"],
        0,
        buy_day,
        shares_override=fixture["shares"],
    )
    after_buy_cash = state.cash
    memory = memory_for(state, symbol)
    memory.entry = memory.cost = fixture["buy_price"]
    memory.peak = fixture["sell_price"]
    memory.units = 1
    plan = plan_exit(
        state,
        symbol,
        fixture["sell_price"],
        sell_day,
        [],
        day_i=1,
        ds=sell_day.strftime("%Y%m%d"),
    )
    assert plan is not None and plan[0] == "profit_take:band:4"
    state.book_state["turtle_pending"] = {symbol: plan}
    fill_pending(
        state,
        symbol,
        SimpleNamespace(open=fixture["sell_price"]),
        sell_day,
        day_i=1,
        ds=sell_day.strftime("%Y%m%d"),
        limits=(fixture["sell_price"] * 1.1, fixture["sell_price"] * 0.9),
    )
    remaining = sum(pos.shares for pos in state.positions.get(symbol, []))
    state.equity_curve = [
        (
            buy_day.strftime("%Y%m%d"),
            after_buy_cash + fixture["shares"] * fixture["buy_price"],
        ),
        (
            sell_day.strftime("%Y%m%d"),
            state.cash + remaining * fixture["sell_price"],
        ),
    ]
    return state


def run_p11_case(book: str, engine: str, *, rule_profile: str = "industry"):
    """Exercise v7 tight cash where a later sell cannot fund an earlier buy."""
    if (book, engine) not in P11_CASES:
        raise KeyError((book, engine))
    fixture = json.loads(P11_FIXTURE.read_text(encoding="utf-8"))
    days = [date.fromisoformat(value) for value in fixture["days"]]
    minute_records = {
        symbol: [
            {
                "date": date.fromisoformat(day),
                "hm": hm,
                "open": opening,
                "high": max(opening, close),
                "low": min(opening, close),
                "close": close,
            }
            for day, hm, opening, close in fixture["minute_rows"][symbol]
        ]
        for symbol in fixture["symbols"]
    }
    daily_closes = {
        symbol: {
            date.fromisoformat(day): close
            for day, close in fixture["daily_closes"][symbol].items()
        }
        for symbol in fixture["symbols"]
    }
    pools = {
        date.fromisoformat(fixture["pool_day"]): list(fixture["symbols"])
    }
    if engine == "minute-native":
        from backtest.research.minute_engine_policies import MinutePolicyContext

        return minute.simulate(
            minute_records,
            daily_closes,
            pools,
            days[0],
            days[-1],
            strategy="version7",
            total_cash=fixture["cash_total"],
            policy_context=MinutePolicyContext(index_days=days),
            rule_profile=rule_profile,
        )
    return v7.simulate_v7(
        minute_records,
        daily_closes,
        pools,
        days,
        cash_total=fixture["cash_total"],
        rule_profile=rule_profile,
    )


def run_case(
    book: str,
    engine: str,
    *,
    explicit_false: bool = False,
    rule_profile: str = "legacy",
    fixture: str | None = None,
):
    if fixture == "p03":
        return run_p03_case(book, engine, rule_profile=rule_profile)
    if fixture == "p04":
        return run_p04_case(book, engine, rule_profile=rule_profile)
    if fixture == "p05":
        return run_p05_case(book, engine, rule_profile=rule_profile)
    if fixture == "p06":
        return run_p06_case(book, engine, rule_profile=rule_profile)
    if fixture == "p07":
        return run_p07_case(book, engine, rule_profile=rule_profile)
    if fixture == "p08":
        return run_p08_case(book, engine, rule_profile=rule_profile)
    if fixture == "p09":
        return run_p09_case(book, engine, rule_profile=rule_profile)
    if fixture == "p10":
        return run_p10_case(book, engine, rule_profile=rule_profile)
    if fixture == "p11":
        return run_p11_case(book, engine, rule_profile=rule_profile)
    if book in ("version6_11", "version6_12"):
        # 突破书：共享路径涨不到 A0x1.2，专用路径才有成交。
        bars, minutes, pools, start, end, dates = frozen_inputs(BREAKOUT_PRICES)
    else:
        bars, minutes, pools, start, end, dates = frozen_inputs()
    if book == "version9":
        # First evaluation is dates[13]: 13 prior frozen bars need 8 extra bars.
        extra = pd.bdate_range(end=dates[0] - pd.Timedelta(days=1), periods=8)
        prefix = pd.DataFrame([bars.iloc[0].to_dict()] * len(extra), index=extra)
        rows = []
        for day in extra:
            for _, row in minutes.loc[minutes["ymd"] == dates[0].strftime("%Y%m%d")].iterrows():
                values = row.to_dict()
                values["ymd"] = day.strftime("%Y%m%d")
                values["time"] = day + pd.Timedelta(minutes=int(values["hm"]))
                rows.append(values)
        bars = pd.concat([prefix, bars])
        minutes = pd.concat([pd.DataFrame(rows).set_index("time"), minutes])
    if book == "version9_1":
        # First evaluation is dates[13]: ATR(20) needs 21 prior bars; prepend 8 frozen bars.
        extra = pd.bdate_range(end=dates[0] - pd.Timedelta(days=1), periods=8)
        prefix = pd.DataFrame([bars.iloc[0].to_dict()] * len(extra), index=extra)
        rows = []
        for day in extra:
            for _, row in minutes.loc[minutes["ymd"] == dates[0].strftime("%Y%m%d")].iterrows():
                values = row.to_dict()
                values["ymd"] = day.strftime("%Y%m%d")
                values["time"] = day + pd.Timedelta(minutes=int(values["hm"]))
                rows.append(values)
        bars = pd.concat([prefix, bars])
        minutes = pd.concat([pd.DataFrame(rows).set_index("time"), minutes])
    daily_bars, minute_bars = {CODE: bars}, {CODE: minutes}
    index_gate = {d.strftime("%Y%m%d"): False for d in dates[12:]}
    kwargs = {"strategy": book, "ration": "file_order", "ration_seed": 0,
              "total_cash": 5_000_000., "daily_quota": 1_000_000.,
              "index_block_new": index_gate}
    if book == "version9":
        kwargs["max_hold"] = True
    if book.startswith("topk_"):
        daily_bars = {code: bars.copy() for code in TOPK_CODES}
        minute_bars = {code: minutes.copy() for code in TOPK_CODES}
        scores = {}
        for i, day in enumerate(dates[12:]):
            # Both ranking exits and SX0 have frozen, nonempty day plans.
            values = ((3., 2., 1.), (-1., 3., 2.), (3., 1., 2.))[i % 3]
            scores[day.strftime("%Y%m%d")] = dict(zip(TOPK_CODES, values))
        kwargs.update(scores_by_day=scores, topk=2, n_drop=1,
                      eligible_buy=_eligible_buy, keep_buy_vacancy=False)
    if book == "version7":
        return v7.simulate_v7(minute_bars, daily_bars, pools,
                              index_days={day.date(): 3000. for day in dates},
                              cash_total=5_000_000., start=start, end=end,
                              rule_profile=rule_profile)
    simulate = daily.simulate if engine == "daily" else minute.simulate
    if explicit_false:
        # The pre-change commit has no new API. Once added, every supported
        # default-OFF switch is passed explicitly (including non-s12 books).
        kwargs.update({name: False for name in inspect.signature(simulate).parameters
                       if name.startswith("fix_")})
    args = (daily_bars,) if engine == "daily" else (minute_bars, daily_bars)
    return simulate(*args, pools, start, end, rule_profile=rule_profile, **kwargs)


def _hash(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _canonical_value(field: str, value):
    if value == "":
        return ""
    if field in MONEY_FIELDS | INTEGER_FIELDS | {"stamp_duty", "transfer_fee"}:
        number = Decimal(str(value))
        assert number.is_finite(), (field, value, "non-finite number")
        if field in INTEGER_FIELDS:
            assert number == number.to_integral_value(), (field, value, "fractional integer")
            return int(number)
        with localcontext() as ctx:
            ctx.prec = 50
            return format(number.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN), "f")
    # Preserve dates, symbols, case, reasons and all other text verbatim.
    return str(value)


def _canonical_rows(columns, rows):
    columns = list(columns)
    assert columns and len(columns) == len(set(columns)), ("invalid columns", columns)
    result = []
    for row in rows:
        assert set(row) == set(columns), ("CSV/structured row schema mismatch", row)
        assert all(value is not None for value in row.values()), ("missing CSV value", row)
        result.append({field: _canonical_value(field, row[field]) for field in columns})
    # Column order, row order and every field remain part of the contract.
    return {"columns": columns, "rows": result}


def canonical_csv(blob: bytes) -> dict:
    """Parse with stdlib csv; never round-trip through pandas or binary floats."""
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8"), newline=""))
    return _canonical_rows(reader.fieldnames, reader)


def canonical_hash(table: dict) -> str:
    blob = json.dumps(table, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _hash(blob.encode("utf-8"))


def load_canonical_golden() -> dict:
    """The companion binds full eff77f3 CSVs (also EOD_MARK) to the raw golden.

    structured.fills alone cannot reconstruct EOD_MARK rows. The companion was
    generated from original eff77f3 outputs only after every raw hash matched.
    """
    golden = json.loads(CANONICAL_GOLDEN.read_text(encoding="utf-8"))
    assert golden["source"] == SOURCE
    assert golden["raw_golden_sha256"] == _hash(GOLDEN.read_bytes())
    assert golden["contract"] == CANONICAL_CONTRACT
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in HISTORICAL_CASES}
    return golden


def load_s8_golden() -> dict:
    """Only the authorized 12 cases may supersede their historical contract."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(S8_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == S8_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(S8_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in S8_CASES}
    return golden


def load_v61_golden() -> dict:
    """Additive overlay for version6_1 only; historical files stay immutable."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(V61_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == V61_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(V61_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in V61_CASES}
    return golden


def load_v91_golden() -> dict:
    """Additive overlay for version9_1 only; historical files stay immutable."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(V91_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == V91_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(V91_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in V91_CASES}
    return golden


def load_v92_golden() -> dict:
    """Additive overlay for version9_2 only; historical files stay immutable."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(V92_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == V92_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(V92_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in V92_CASES}
    return golden


def load_v93_golden() -> dict:
    """Additive overlay for version9_3 only; historical files stay immutable."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(V93_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == V93_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(V93_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in V93_CASES}
    return golden


def load_v650_golden() -> dict:
    """Additive overlay for version6_50 only; historical files stay immutable."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(V650_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == V650_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(V650_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in V650_CASES}
    return golden


def load_v6f_golden() -> dict:
    """Additive overlay for the 6.2-6.49 family; historical files stay immutable."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(V6F_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == V6F_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(V6F_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in V6F_CASES}
    return golden


def load_s12_golden() -> dict:
    """Replacement overlay for version12 only; historical files stay immutable."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(S12_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == S12_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(S12_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in S12_CASES}
    return golden


def load_s9_golden() -> dict:
    """Replacement overlay for version9 only; historical files stay immutable."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(S9_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == S9_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(S9_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in S9_CASES}
    return golden


def load_p03_golden() -> dict:
    """Immutable P03 profile overlay retained for registry verification."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(P03_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == P03_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == CANONICAL_CONTRACT
    assert golden["books"] == list(P03_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in P03_CASES}
    return golden


def load_p04_golden() -> dict:
    """Immutable P04 profile overlay retained for registry verification."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(P04_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == P04_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == P04_CANONICAL_CONTRACT
    assert golden["books"] == list(P04_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in P04_CASES}
    return golden


def load_p05_golden() -> dict:
    """Immutable P05 profile overlay retained for registry verification."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(P05_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == P05_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == P05_CANONICAL_CONTRACT
    assert golden["books"] == list(P05_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in P05_CASES}
    return golden


def load_p06_golden() -> dict:
    """Immutable P06 profile overlay retained for registry verification."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(P06_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == P06_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == P06_CANONICAL_CONTRACT
    assert golden["books"] == list(P06_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in P06_CASES}
    return golden


def load_p07_golden() -> dict:
    """Immutable P07 profile overlay retained for registry verification."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(P07_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == P07_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == P07_CANONICAL_CONTRACT
    assert golden["books"] == list(P07_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in P07_CASES}
    return golden


def load_p08_golden() -> dict:
    """Immutable P08 profile overlay retained for registry verification."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(P08_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == P08_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == P08_CANONICAL_CONTRACT
    assert golden["books"] == list(P08_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in P08_CASES}
    return golden


def load_p09_golden() -> dict:
    """Immutable P09 profile overlay retained for registry verification."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(P09_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == P09_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == P09_CANONICAL_CONTRACT
    assert golden["books"] == list(P09_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in P09_CASES}
    return golden


def load_p10_golden() -> dict:
    """Immutable P10 profile overlay retained for registry verification."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(P10_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == P10_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == P10_CANONICAL_CONTRACT
    assert golden["books"] == list(P10_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in P10_CASES}
    return golden


def load_p11_golden() -> dict:
    """Active opt-in industry profile overlay; all earlier files stay immutable."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(P11_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == P11_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == P11_CANONICAL_CONTRACT
    assert golden["books"] == list(P11_BOOK_NAMES)
    assert set(golden["cases"]) == {f"{book}/{engine}" for book, engine in P11_CASES}
    return golden


def load_industry_default_golden() -> dict:
    """Full synthetic matrix for the industry CLI/library default."""
    assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
    assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
    golden = json.loads(INDUSTRY_DEFAULT_GOLDEN.read_text(encoding="utf-8"))
    assert golden["rule_revision"] == INDUSTRY_DEFAULT_RULE_REVISION
    assert golden["historical_raw_sha256"] == HISTORICAL_GOLDEN_SHA256
    assert golden["historical_canonical_sha256"] == HISTORICAL_CANONICAL_SHA256
    assert golden["contract"] == INDUSTRY_DEFAULT_CANONICAL_CONTRACT
    assert golden["books"] == list(INDUSTRY_DEFAULT_BOOK_NAMES)
    assert set(golden["cases"]) == {
        f"{book}/{engine}" for book, engine in INDUSTRY_DEFAULT_CASES
    }
    return golden


def expected_case(
    book: str, engine: str, *, rule_profile: str = "legacy"
) -> tuple[dict, dict, str]:
    """Return account/raw, canonical hashes, and the recorded pandas version."""
    key = f"{book}/{engine}"
    if rule_profile == "industry-default":
        golden = load_industry_default_golden()
        if (book, engine) not in INDUSTRY_DEFAULT_CASES:
            raise KeyError(f"no industry-default baseline case: {key}")
        case = golden["cases"][key]
        canonical = {
            name: canonical_hash(table) for name, table in case["canonical_csv"].items()
        }
        return case, canonical, golden["captured_environment"]["pandas"]
    if rule_profile == "industry":
        if (book, engine) in P11_CASES:
            golden = load_p11_golden()
        elif (book, engine) in P10_CASES:
            golden = load_p10_golden()
        elif (book, engine) in P09_CASES:
            golden = load_p09_golden()
        elif (book, engine) in P08_CASES:
            golden = load_p08_golden()
        elif (book, engine) in P07_CASES:
            golden = load_p07_golden()
        elif (book, engine) in P06_CASES:
            golden = load_p06_golden()
        elif (book, engine) in P05_CASES:
            golden = load_p05_golden()
        else:
            raise KeyError(f"no industry baseline case: {key}")
        case = golden["cases"][key]
        canonical = {
            name: canonical_hash(table) for name, table in case["canonical_csv"].items()
        }
        return case, canonical, golden["captured_environment"]["pandas"]
    if rule_profile != "legacy":
        raise ValueError(f"unsupported baseline rule_profile: {rule_profile!r}")
    if (book, engine) in S8_CASES:
        golden = load_s8_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    if (book, engine) in V61_CASES:
        golden = load_v61_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    if (book, engine) in V91_CASES:
        golden = load_v91_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    if (book, engine) in V92_CASES:
        golden = load_v92_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    if (book, engine) in V93_CASES:
        golden = load_v93_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    if (book, engine) in V650_CASES:
        golden = load_v650_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    if (book, engine) in V6F_CASES:
        golden = load_v6f_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    if (book, engine) in S12_CASES:
        golden = load_s12_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    if (book, engine) in S9_CASES:
        golden = load_s9_golden()
        case = golden["cases"][key]
        canonical = {name: canonical_hash(table) for name, table in case["canonical_csv"].items()}
        return case, canonical, golden["captured_environment"]["pandas"]
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    case = post205_expected_case(book, golden["cases"][key])
    canonical = load_canonical_golden()["cases"][key]
    return case, canonical, golden["captured_environment"]["pandas"]


def assert_case_canonical(book: str, actual: dict, expected: dict, canonical_expected: dict):
    """Mandatory on every pandas version, before any byte-check skip."""
    for field, label in (("canonical_csv", "production"), ("library_canonical_csv", "library")):
        hashes = {name: canonical_hash(table) for name, table in actual[field].items()}
        assert hashes == canonical_expected, (book, f"canonical {label} CSV drift")
    assert _canonical_value("cash", actual["structured"]["cash"]) == _canonical_value(
        "cash", expected["structured"]["cash"]), (book, "canonical cash drift")
    assert actual["fill_counts"] == expected["fill_counts"]
    # Keep the original stronger, unrounded account/positions/stats assertion too.
    assert actual["structured"] == expected["structured"]


def byte_skip_reason(recorded_pandas: str) -> str | None:
    runtime = pd.__version__
    if runtime.split(".")[:2] != recorded_pandas.split(".")[:2]:
        return (f"raw CSV byte checks skipped: golden pandas={recorded_pandas}, "
                f"runtime pandas={runtime} (major.minor differs); "
                "canonical trades/equity/cash and full structured assertions passed")
    return None


def assert_case_bytes(actual: dict, expected: dict):
    """Original exact raw SHA-256 contract, including writer/library equality."""
    assert actual["sha256_csv_bytes"] == actual["library_sha256_csv_bytes"], "writer/library mismatch"
    assert actual["sha256_csv_bytes"] == expected["sha256_csv_bytes"]
    assert actual["library_sha256_csv_bytes"] == expected["library_sha256_csv_bytes"]


def _library_bytes(state, book: str):
    if book != "version7":
        return {
            "trades": pd.DataFrame(state.trades).to_csv(
                index=False, lineterminator="\n").encode("utf-8"),
            "equity": pd.DataFrame(state.equity_curve, columns=["date", "equity"]).to_csv(
                index=False, lineterminator="\n").encode("utf-8"),
        }
    result = {}
    trade_fields = ("date", "symbol", "hm", "side", "shares", "price", "reason")
    if any("transfer_fee" in row for row in state.trades):
        trade_fields = (
            "date", "symbol", "hm", "side", "shares", "price",
            "notional", "commission", "stamp_duty", "transfer_fee", "reason",
        )
    elif any("stamp_duty" in row for row in state.trades):
        trade_fields = (
            "date", "symbol", "hm", "side", "shares", "price",
            "notional", "commission", "stamp_duty", "reason",
        )
    elif any("commission" in row for row in state.trades):
        trade_fields = (
            "date", "symbol", "hm", "side", "shares", "price",
            "notional", "commission", "reason",
        )
    for name, rows, fields in (
        ("trades", state.trades, trade_fields),
        ("equity", state.equity_curve, ("date", "cash", "holdings", "equity")),
    ):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        result[name] = stream.getvalue().encode("utf-8")
    return result


def capture_case(
    book: str,
    engine: str,
    output_dir: Path,
    *,
    explicit_false: bool = False,
    rule_profile: str = "legacy",
    fixture: str | None = None,
):
    state = run_case(
        book, engine, explicit_false=explicit_false,
        rule_profile=rule_profile, fixture=fixture,
    )
    trades = [row for row in state.trades if row["side"].upper() in ("BUY", "SELL")]
    assert any(row["side"].upper() == "BUY" for row in trades), (book, engine, "no BUY")
    assert any(row["side"].upper() == "SELL" for row in trades), (book, engine, "no SELL")
    with contextlib.redirect_stdout(io.StringIO()):
        if book == "version7":
            v7.write_run_artifacts(state, output_dir)
        else:
            write_run_artifacts(output_dir, state, "Frozen OFF byte baseline", "")
    writer_bytes = {name: (output_dir / filename).read_bytes() for name, filename in (
        ("trades", "trades.csv"), ("equity", "daily_equity.csv"))}
    library_bytes = _library_bytes(state, book)
    # Assert canonical first in the caller. Raw hashes (including writer/library
    # equality) are then checked only on the recorded pandas major.minor.
    for blob in writer_bytes.values():
        assert not blob.startswith(b"\xef\xbb\xbf") and b"\0" not in blob
    positions = {code: ([asdict(pos) for pos in value] if isinstance(value, list)
                        else asdict(value)) for code, value in state.positions.items()}
    structured = {
        "fills": trades, "cash": state.cash, "positions": positions,
        "equity_curve": state.equity_curve,
    }
    if book != "version7":
        # OFF stats are frozen too: adding metadata to SimState is observable.
        structured["stats"] = state.stats
    return {
        "sha256_csv_bytes": {name: _hash(blob) for name, blob in writer_bytes.items()},
        "library_sha256_csv_bytes": {name: _hash(blob) for name, blob in library_bytes.items()},
        "canonical_csv": {name: canonical_csv(blob) for name, blob in writer_bytes.items()},
        "library_canonical_csv": {name: canonical_csv(blob) for name, blob in library_bytes.items()},
        "fill_counts": {side: sum(row["side"].upper() == side for row in trades)
                        for side in ("BUY", "SELL")},
        "structured": json.loads(json.dumps(structured, default=str)),
    }


def assert_baseline_coverage():
    """Check registry and overlay coverage without running simulations."""
    assert set(BOOKS) == set(BOOK_NAMES) | set(PENDING_BOOK_NAMES), (
        "Update coverage explicitly when BOOKS changes"
    )
    assert set(PENDING_BOOK_NAMES).isdisjoint(BOOK_NAMES)
    assert len(HISTORICAL_BOOK_NAMES) == 19 and len(HISTORICAL_CASES) == 39
    assert set(BOOK_NAMES) == (
        set(HISTORICAL_BOOK_NAMES) | set(V61_BOOK_NAMES) | set(V91_BOOK_NAMES)
        | set(V92_BOOK_NAMES) | set(V93_BOOK_NAMES) | set(V6F_BOOK_NAMES)
        | set(V650_BOOK_NAMES)
    )
    assert set(CASES) == {
        (book, engine) for book in BOOK_NAMES for engine in ("daily", "minute")
    } | {("version7", "minute")}
    assert INDUSTRY_DEFAULT_BOOK_NAMES == BOOK_NAMES
    assert INDUSTRY_DEFAULT_CASES == CASES
    assert set(P03_BOOK_NAMES) <= set(BOOK_NAMES) | {"version7"}
    assert set(P03_CASES) == {
        ("version6", "daily"),
        ("version6", "minute"),
        ("version7", "minute-native"),
        ("version7", "standalone"),
        ("version8", "s8-group"),
    }
    assert P03_FIXTURE.is_file()
    assert set(P04_BOOK_NAMES) <= set(BOOK_NAMES) | {"version7"}
    assert set(P04_CASES) == {
        ("version6", "daily-pre-cutover"),
        ("version6", "minute-post-cutover"),
        ("version7", "minute-native-pre-cutover"),
        ("version7", "standalone-post-cutover"),
        ("version8", "s8-group-post-cutover"),
    }
    assert P04_FIXTURE.is_file()
    assert set(P05_BOOK_NAMES) <= set(BOOK_NAMES) | {"version7"}
    assert set(P05_CASES) == {
        ("version6", "daily-pre-cutover"),
        ("version6", "minute-post-cutover"),
        ("version7", "minute-native-pre-cutover"),
        ("version7", "standalone-post-cutover"),
        ("version8", "s8-group-post-cutover"),
    }
    assert P05_FIXTURE.is_file()
    assert set(P06_BOOK_NAMES) <= set(BOOK_NAMES)
    assert set(P06_CASES) == {
        ("version6", "daily"),
        ("version6", "minute"),
    }
    assert P06_FIXTURE.is_file()
    assert set(P07_BOOK_NAMES) <= set(BOOK_NAMES) | {"version7"}
    assert set(P07_CASES) == {
        ("version6", "daily"),
        ("version6", "minute"),
        ("version7", "minute-native"),
        ("version7", "standalone"),
    }
    assert P07_FIXTURE.is_file()
    assert set(P08_BOOK_NAMES) <= set(BOOK_NAMES)
    assert set(P08_CASES) == {
        ("version8", "daily"),
        ("version8", "minute"),
    }
    assert P08_FIXTURE.is_file()
    assert set(P09_BOOK_NAMES) <= set(BOOK_NAMES) | {"version7"}
    assert set(P09_CASES) == {
        ("version6", "daily-star"),
        ("version6", "daily-bse"),
        ("version6", "minute-star"),
        ("version6", "minute-bse"),
        ("version7", "minute-native-star"),
        ("version7", "minute-native-bse"),
        ("version7", "standalone-star"),
        ("version7", "standalone-bse"),
    }
    assert P09_FIXTURE.is_file()
    assert set(P10_BOOK_NAMES) <= set(BOOK_NAMES)
    assert set(P10_CASES) == {("version9_2", "scale-out-star")}
    assert P10_FIXTURE.is_file()
    assert set(P11_BOOK_NAMES) <= set(BOOK_NAMES) | {"version7"}
    assert set(P11_CASES) == {
        ("version7", "minute-native"),
        ("version7", "standalone"),
    }
    assert P11_FIXTURE.is_file()


def capture_matrix(output_dir: Path, *, explicit_false: bool = False):
    assert_baseline_coverage()
    return {f"{book}/{engine}": capture_case(book, engine, output_dir / book / engine,
                                            explicit_false=explicit_false)
            for book, engine in CASES}


def post205_expected_case(book: str, frozen_case: dict) -> dict:
    """Require #205's quota echo while preserving every eff77f3 field/hash.

    The frozen inputs explicitly pass daily_quota=1M to simulate (including
    topk); CLI money-mode default resolution does not participate. Only the
    shared engines added this stats key. v7's entire snapshot stays unchanged.
    Build an expected copy instead of dropping metadata from the actual state,
    so a missing/wrong quota or any other new stats key still fails comparison.
    """
    if book == "version7":
        return frozen_case
    structured = frozen_case["structured"]
    stats = structured["stats"]
    assert "daily_quota" not in stats, "The original eff77f3 golden must remain unchanged"
    return {
        **frozen_case,
        "structured": {**structured, "stats": {**stats, "daily_quota": 1_000_000.0}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true",
        help="Compare historical cases plus the S8, version6_1, version12, version9, version9_1, version9_2 and version9_3 overlays",
    )
    mode.add_argument("--record-s8", action="store_true", help="Record only the 12 corrected S8 cases")
    mode.add_argument(
        "--record-v61", action="store_true",
        help="Record only the 2 additive version6_1 cases (scoped overlay)",
    )
    mode.add_argument(
        "--record-v91", action="store_true",
        help="Record only the 2 additive version9_1 cases (scoped overlay)",
    )
    mode.add_argument(
        "--record-v92", action="store_true",
        help="Record only the 2 additive version9_2 cases (scoped overlay)",
    )
    mode.add_argument(
        "--record-v93", action="store_true",
        help="Record only the 2 additive version9_3 cases (scoped overlay)",
    )
    mode.add_argument(
        "--record-v650", action="store_true",
        help="Record only the 2 additive version6_50 cases (scoped overlay)",
    )
    mode.add_argument(
        "--record-v6f", action="store_true",
        help="write the additive 6.2-6.49 family overlay (authorized pandas 3.0.6 only)",
    )
    mode.add_argument(
        "--record-v61-v2", action="store_true",
        help="re-record version6_1 after the first-lot anchor fix (authorized pandas 3.0.6/Linux only)",
    )
    mode.add_argument("--record-s12", action="store_true",
                      help="Record only the 2 version12 MA10-stop cases")
    mode.add_argument("--record-s9", action="store_true",
                      help="Record only the 2 version9 trailing 2x mean true range cases")
    mode.add_argument(
        "--record-industry-p03",
        action="store_true",
        help="Record the five synthetic industry P03 per-order commission cases",
    )
    mode.add_argument(
        "--record-industry-p04",
        action="store_true",
        help="Record the five synthetic industry P04 dated stamp-duty cases",
    )
    mode.add_argument(
        "--record-industry-p05",
        action="store_true",
        help="Record the five synthetic industry P05 dated transfer-fee cases",
    )
    mode.add_argument(
        "--record-industry-p06",
        action="store_true",
        help="Record the two synthetic industry P06 no-minimum-lot-top-up cases",
    )
    mode.add_argument(
        "--record-industry-p07",
        action="store_true",
        help="Record the four synthetic industry P07 fee-aware sizing cases",
    )
    mode.add_argument(
        "--record-industry-p08",
        action="store_true",
        help="Record the two synthetic industry P08 short-cash shrink cases",
    )
    mode.add_argument(
        "--record-industry-p09",
        action="store_true",
        help="Record the eight synthetic industry P09 STAR/BSE quantity cases",
    )
    mode.add_argument(
        "--record-industry-p10",
        action="store_true",
        help="Record the synthetic industry P10 STAR odd-lot scale-out case",
    )
    mode.add_argument(
        "--record-industry-p11",
        action="store_true",
        help="Record the two synthetic industry P11 v7 chronological cash-order cases",
    )
    mode.add_argument(
        "--record-industry-default",
        action="store_true",
        help="Record the full synthetic CASES matrix under the industry default profile",
    )
    args = parser.parse_args()
    if args.record_industry_default:
        if INDUSTRY_DEFAULT_GOLDEN.exists():
            parser.error("The industry-default overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error(
                "industry-default recording requires the authorized pandas 3.0.6 environment"
            )
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-default-byte-baseline-") as temp:
            root = Path(temp)
            cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / book / engine,
                    rule_profile="industry",
                )
                for book, engine in INDUSTRY_DEFAULT_CASES
            }
        for case in cases.values():
            assert_case_bytes(case, case)
        payload = {
            "rule_revision": INDUSTRY_DEFAULT_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(INDUSTRY_DEFAULT_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": INDUSTRY_DEFAULT_CANONICAL_CONTRACT,
            "cases": cases,
        }
        INDUSTRY_DEFAULT_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"Wrote {INDUSTRY_DEFAULT_GOLDEN}: "
            f"{len(cases)} industry-default cases"
        )
        return
    if args.record_industry_p11:
        if P11_GOLDEN.exists():
            parser.error("The industry P11 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("industry P11 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-p11-byte-baseline-") as temp:
            root = Path(temp)
            cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / "industry" / book / engine,
                    rule_profile="industry",
                    fixture="p11",
                )
                for book, engine in P11_CASES
            }
            legacy_cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / "legacy" / book / engine,
                    rule_profile="legacy",
                    fixture="p11",
                )
                for book, engine in P11_CASES
            }
        for key, case in cases.items():
            assert_case_bytes(case, case)
            assert case["fill_counts"] == {"BUY": 3, "SELL": 1}
            assert legacy_cases[key]["fill_counts"] == {"BUY": 3, "SELL": 1}
            assert case["canonical_csv"] != legacy_cases[key]["canonical_csv"]
            industry_add = next(
                row for row in case["structured"]["fills"]
                if row["reason"] == "buy:add_a104"
            )
            legacy_add = next(
                row for row in legacy_cases[key]["structured"]["fills"]
                if row["reason"] == "buy:add_a104"
            )
            assert industry_add["shares"] == 2100
            assert legacy_add["shares"] == 19200
        payload = {
            "rule_revision": P11_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(P11_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": P11_CANONICAL_CONTRACT,
            "cases": cases,
        }
        P11_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {P11_GOLDEN}: {len(cases)} industry cases")
        return
    if args.record_industry_p10:
        if P10_GOLDEN.exists():
            parser.error("The industry P10 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("industry P10 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-p10-byte-baseline-") as temp:
            root = Path(temp)
            cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / "industry" / book / engine,
                    rule_profile="industry",
                    fixture="p10",
                )
                for book, engine in P10_CASES
            }
            legacy_cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / "legacy" / book / engine,
                    rule_profile="legacy",
                    fixture="p10",
                )
                for book, engine in P10_CASES
            }
        for key, case in cases.items():
            assert_case_bytes(case, case)
            assert case["fill_counts"] == {"BUY": 1, "SELL": 1}
            assert case["canonical_csv"] != legacy_cases[key]["canonical_csv"]
            industry_sell = next(
                row for row in case["structured"]["fills"] if row["side"].upper() == "SELL"
            )
            legacy_sell = next(
                row
                for row in legacy_cases[key]["structured"]["fills"]
                if row["side"].upper() == "SELL"
            )
            assert industry_sell["shares"] == 200
            assert legacy_sell["shares"] == 100
            assert legacy_cases[key]["structured"]["positions"]["688001.SH"][0]["shares"] == 100
        payload = {
            "rule_revision": P10_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(P10_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": P10_CANONICAL_CONTRACT,
            "cases": cases,
        }
        P10_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {P10_GOLDEN}: {len(cases)} industry cases")
        return
    if args.record_industry_p09:
        if P09_GOLDEN.exists():
            parser.error("The industry P09 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("industry P09 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-p09-byte-baseline-") as temp:
            root = Path(temp)
            cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / "industry" / book / engine,
                    rule_profile="industry",
                    fixture="p09",
                )
                for book, engine in P09_CASES
            }
            legacy_cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / "legacy" / book / engine,
                    rule_profile="legacy",
                    fixture="p09",
                )
                for book, engine in P09_CASES
            }
        for key, case in cases.items():
            assert_case_bytes(case, case)
            assert case["fill_counts"] == {"BUY": 1, "SELL": 1}
            assert case["canonical_csv"] != legacy_cases[key]["canonical_csv"]
            buy = next(
                row for row in case["structured"]["fills"] if row["side"].upper() == "BUY"
            )
            board = key.rsplit("-", 1)[1]
            assert buy["shares"] >= (200 if board == "star" else 100)
            assert buy["shares"] % 100 != 0
        payload = {
            "rule_revision": P09_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(P09_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": P09_CANONICAL_CONTRACT,
            "cases": cases,
        }
        P09_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {P09_GOLDEN}: {len(cases)} industry cases")
        return
    if args.record_industry_p08:
        if P08_GOLDEN.exists():
            parser.error("The industry P08 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("industry P08 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-p08-byte-baseline-") as temp:
            root = Path(temp)
            cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / book / engine,
                    rule_profile="industry",
                    fixture="p08",
                )
                for book, engine in P08_CASES
            }
        from backtest.research.csv_ledger import InsufficientCashError

        for book, engine in P08_CASES:
            try:
                run_p08_case(book, engine, rule_profile="legacy")
            except InsufficientCashError:
                pass
            else:
                raise AssertionError((book, engine, "legacy S8 case must raise"))
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"] == {"BUY": 1, "SELL": 1}
            buy = next(
                row for row in case["structured"]["fills"] if row["side"].upper() == "BUY"
            )
            assert buy["shares"] == 1400
            assert buy["notional"] + buy["commission"] + buy["transfer_fee"] <= 15000.0
        payload = {
            "rule_revision": P08_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(P08_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": P08_CANONICAL_CONTRACT,
            "cases": cases,
        }
        P08_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {P08_GOLDEN}: {len(cases)} industry cases")
        return
    if args.record_industry_p07:
        if P07_GOLDEN.exists():
            parser.error("The industry P07 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("industry P07 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-p07-byte-baseline-") as temp:
            root = Path(temp)
            cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / "industry" / book / engine,
                    rule_profile="industry",
                    fixture="p07",
                )
                for book, engine in P07_CASES
            }
            legacy_cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    root / "legacy" / book / engine,
                    rule_profile="legacy",
                    fixture="p07",
                )
                for book, engine in P07_CASES
            }
        for key, case in cases.items():
            assert_case_bytes(case, case)
            assert case["fill_counts"] == {"BUY": 1, "SELL": 1}
            industry_buy = next(
                row for row in case["structured"]["fills"] if row["side"].upper() == "BUY"
            )
            legacy_buy = next(
                row
                for row in legacy_cases[key]["structured"]["fills"]
                if row["side"].upper() == "BUY"
            )
            budget = 2000.0 if key.startswith("version6/") else 200000.0
            assert legacy_buy["shares"] == industry_buy["shares"] + 100
            assert legacy_buy["shares"] * legacy_buy["price"] <= budget
            assert (
                legacy_buy["shares"] * legacy_buy["price"]
                + legacy_buy.get(
                    "commission",
                    legacy_buy["shares"] * legacy_buy["price"] * 0.001,
                )
                > budget
            )
            assert (
                industry_buy["notional"]
                + industry_buy["commission"]
                + industry_buy["transfer_fee"]
                <= budget
            )
        payload = {
            "rule_revision": P07_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(P07_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": P07_CANONICAL_CONTRACT,
            "cases": cases,
        }
        P07_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {P07_GOLDEN}: {len(cases)} industry cases")
        return
    if args.record_industry_p06:
        if P06_GOLDEN.exists():
            parser.error("The industry P06 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("industry P06 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-p06-byte-baseline-") as temp:
            cases = {
                f"{book}/{engine}": capture_case(
                    book,
                    engine,
                    Path(temp) / book / engine,
                    rule_profile="industry",
                    fixture="p06",
                )
                for book, engine in P06_CASES
            }
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"] == {"BUY": 1, "SELL": 1}
            assert case["structured"]["stats"]["skip_min_lot_budget"] == 1
            assert case["structured"]["stats"]["supplementary_used"] == 0.0
        payload = {
            "rule_revision": P06_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(P06_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": P06_CANONICAL_CONTRACT,
            "cases": cases,
        }
        P06_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {P06_GOLDEN}: {len(cases)} industry cases")
        return
    if args.record_industry_p05:
        if P05_GOLDEN.exists():
            parser.error("The industry P05 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("industry P05 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-p05-byte-baseline-") as temp:
            cases = {
                f"{book}/{engine}": capture_case(
                    book, engine, Path(temp) / book / engine,
                    rule_profile="industry", fixture="p05",
                )
                for book, engine in P05_CASES
            }
        from backtest.research.ledger_math import bilateral_transfer_fee
        from backtest.research.market_layer import transfer_fee_market

        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
            fills = case["structured"]["fills"]
            assert all("transfer_fee" in row for row in fills)
            for row in fills:
                symbol = row.get("code", row.get("symbol"))
                expected = bilateral_transfer_fee(
                    row["notional"], transfer_fee_market(symbol), row["date"]
                )
                assert row["transfer_fee"] == expected
        payload = {
            "rule_revision": P05_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(P05_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": P05_CANONICAL_CONTRACT,
            "cases": cases,
        }
        P05_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {P05_GOLDEN}: {len(cases)} industry cases")
        return
    if args.record_industry_p04:
        if P04_GOLDEN.exists():
            parser.error("The industry P04 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("industry P04 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-p04-byte-baseline-") as temp:
            cases = {
                f"{book}/{engine}": capture_case(
                    book, engine, Path(temp) / book / engine,
                    rule_profile="industry", fixture="p04",
                )
                for book, engine in P04_CASES
            }
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
            fills = case["structured"]["fills"]
            assert all("stamp_duty" in row for row in fills)
            assert all(row["stamp_duty"] == 0.0 for row in fills if row["side"].upper() == "BUY")
        pre_sells = [
            row for key, case in cases.items() if "pre-cutover" in key
            for row in case["structured"]["fills"] if row["side"].upper() == "SELL"
        ]
        post_sells = [
            row for key, case in cases.items() if "post-cutover" in key
            for row in case["structured"]["fills"] if row["side"].upper() == "SELL"
        ]
        assert pre_sells and post_sells
        assert all(
            row["stamp_duty"] == row["notional"] * 0.001 for row in pre_sells
        )
        assert all(
            row["stamp_duty"] == row["notional"] * 0.0005 for row in post_sells
        )
        payload = {
            "rule_revision": P04_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(P04_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": P04_CANONICAL_CONTRACT,
            "cases": cases,
        }
        P04_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {P04_GOLDEN}: {len(cases)} industry cases")
        return
    if args.record_industry_p03:
        if P03_GOLDEN.exists():
            parser.error("The industry P03 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("industry P03 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="industry-p03-byte-baseline-") as temp:
            cases = {
                f"{book}/{engine}": capture_case(
                    book, engine, Path(temp) / book / engine,
                    rule_profile="industry", fixture="p03",
                )
                for book, engine in P03_CASES
            }
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
        s8_fills = cases["version8/s8-group"]["structured"]["fills"]
        s8_sells = [row for row in s8_fills if row["side"] == "SELL"]
        assert len(s8_sells) == 2
        assert sum(row["commission"] for row in s8_sells) == 5.0
        assert any(row["commission"] == 5.0 for case in cases.values()
                   for row in case["structured"]["fills"])
        payload = {
            "rule_revision": P03_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(P03_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        P03_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {P03_GOLDEN}: {len(cases)} industry cases")
        return
    if args.record_s8:
        if S8_GOLDEN.exists():
            parser.error("The S8 correction overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("S8 correction recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="s8-byte-baseline-") as temp:
            cases = {f"{book}/{engine}": capture_case(book, engine, Path(temp) / book / engine)
                     for book, engine in S8_CASES}
        for case in cases.values():
            assert_case_bytes(case, case)
        payload = {
            "rule_revision": S8_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(S8_BOOK_NAMES),
            "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                     "platform": sys.platform},
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        S8_GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {S8_GOLDEN}: 12 corrected cases / 24 production CSV hashes")
        return
    if args.record_v61:
        if V61_GOLDEN.exists():
            parser.error("The version6_1 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("version6_1 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="v61-byte-baseline-") as temp:
            cases = {f"{book}/{engine}": capture_case(book, engine, Path(temp) / book / engine)
                     for book, engine in V61_CASES}
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
        payload = {
            "rule_revision": V61_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(V61_BOOK_NAMES),
            "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                     "platform": sys.platform},
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        V61_GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {V61_GOLDEN}: 2 additive cases / 4 production CSV hashes")
        return
    if args.record_v91:
        if V91_GOLDEN.exists():
            parser.error("The version9_1 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("version9_1 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="v91-byte-baseline-") as temp:
            cases = {f"{book}/{engine}": capture_case(book, engine, Path(temp) / book / engine)
                     for book, engine in V91_CASES}
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
        payload = {
            "rule_revision": V91_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(V91_BOOK_NAMES),
            "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                     "platform": sys.platform},
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        V91_GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {V91_GOLDEN}: 2 additive cases / 4 production CSV hashes")
        return
    if args.record_v92:
        if V92_GOLDEN.exists() and json.loads(V92_GOLDEN.read_text(encoding="utf-8"))["rule_revision"] == V92_RULE_REVISION:
            parser.error("The version9_2 overlay already exists for this rule revision; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("version9_2 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="v92-byte-baseline-") as temp:
            cases = {f"{book}/{engine}": capture_case(book, engine, Path(temp) / book / engine)
                     for book, engine in V92_CASES}
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
        payload = {
            "rule_revision": V92_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(V92_BOOK_NAMES),
            "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                     "platform": sys.platform},
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        V92_GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {V92_GOLDEN}: 2 additive cases / 4 production CSV hashes")
        return
    if args.record_v93:
        if V93_GOLDEN.exists() and json.loads(
            V93_GOLDEN.read_text(encoding="utf-8")
        )["rule_revision"] == V93_RULE_REVISION:
            parser.error(
                "The version9_3 overlay already exists for this rule revision; "
                "refusing to overwrite"
            )
        if pd.__version__ != "3.0.6":
            parser.error("version9_3 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="v93-byte-baseline-") as temp:
            cases = {
                f"{book}/{engine}": capture_case(
                    book, engine, Path(temp) / book / engine
                )
                for book, engine in V93_CASES
            }
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0
            assert case["fill_counts"]["SELL"] > 0
        payload = {
            "rule_revision": V93_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(V93_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        V93_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {V93_GOLDEN}: 2 additive cases / 4 production CSV hashes")
        return
    if args.record_v650:
        if V650_GOLDEN.exists() and json.loads(
            V650_GOLDEN.read_text(encoding="utf-8")
        )["rule_revision"] == V650_RULE_REVISION:
            parser.error(
                "The version6_50 overlay already exists for this rule revision; "
                "refusing to overwrite"
            )
        if pd.__version__ != "3.0.6":
            parser.error("version6_50 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="v650-byte-baseline-") as temp:
            cases = {
                f"{book}/{engine}": capture_case(
                    book, engine, Path(temp) / book / engine
                )
                for book, engine in V650_CASES
            }
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0
            assert case["fill_counts"]["SELL"] > 0
        payload = {
            "rule_revision": V650_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(V650_BOOK_NAMES),
            "captured_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "platform": sys.platform,
            },
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        V650_GOLDEN.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {V650_GOLDEN}: 2 additive cases / 4 production CSV hashes")
        return
    if args.record_s12:
        if S12_GOLDEN.exists():
            parser.error("The version12 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("version12 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="s12-byte-baseline-") as temp:
            cases = {f"{book}/{engine}": capture_case(book, engine, Path(temp) / book / engine)
                     for book, engine in S12_CASES}
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
        from backtest.research import strategy12_rules as rules
        assert rules.STOP_FACTOR == 1.0
        assert rules.buyback_plan(10., [10.] * 10, rules.Memory()) == 0
        for case in cases.values():
            assert not case["structured"]["positions"]
            assert all(row["reason"] == rules.STOP for row in case["structured"]["fills"]
                       if row["side"] == "SELL")
        payload = {
            "rule_revision": S12_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(S12_BOOK_NAMES),
            "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                     "platform": sys.platform},
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        S12_GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {S12_GOLDEN}: 2 corrected cases / 4 production CSV hashes")
        return
    if args.record_v61_v2:
        if V61_GOLDEN.exists():
            parser.error("The version6_1 v2 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("version6_1 v2 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="v61v2-byte-baseline-") as temp:
            cases = {f"{book}/{engine}": capture_case(book, engine, Path(temp) / book / engine)
                     for book, engine in V61_CASES}
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
        payload = {
            "rule_revision": "v61-first-lot-anchor-20261005",
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(V61_BOOK_NAMES),
            "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                     "platform": sys.platform},
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        V61_GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {V61_GOLDEN}: 2 additive cases")
        return
    if args.record_v6f:
        if V6F_GOLDEN.exists():
            parser.error("The 6.x family overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("6.x family recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="v6f-byte-baseline-") as temp:
            cases = {f"{book}/{engine}": capture_case(book, engine, Path(temp) / book / engine)
                     for book, engine in V6F_CASES}
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
        payload = {
            "rule_revision": V6F_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(V6F_BOOK_NAMES),
            "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                     "platform": sys.platform},
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        V6F_GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {V6F_GOLDEN}: {len(cases)} additive cases")
        return
    if args.record_s9:
        if S9_GOLDEN.name == "off_byte_baseline_s9_take_profit_10pct_20261004.json" or S9_GOLDEN.exists():
            parser.error("The version9 overlay already exists; refusing to overwrite")
        if pd.__version__ != "3.0.6":
            parser.error("version9 recording requires the authorized pandas 3.0.6 environment")
        assert _hash(GOLDEN.read_bytes()) == HISTORICAL_GOLDEN_SHA256
        assert _hash(CANONICAL_GOLDEN.read_bytes()) == HISTORICAL_CANONICAL_SHA256
        with tempfile.TemporaryDirectory(prefix="s9-byte-baseline-") as temp:
            cases = {f"{book}/{engine}": capture_case(book, engine, Path(temp) / book / engine)
                     for book, engine in S9_CASES}
        for case in cases.values():
            assert_case_bytes(case, case)
            assert case["fill_counts"]["BUY"] > 0 and case["fill_counts"]["SELL"] > 0
        from backtest.research import strategy9_rules as rules
        assert rules.TAKE_PROFIT_PCT == 0.10
        assert rules.MAX_HOLD == 20
        for case in cases.values():
            assert case["structured"]["stats"]["profit_target"] == 0.10
            assert case["structured"]["stats"]["max_hold"] == 20
            assert all(row["reason"] in {"stop_loss:gap_open", "stop_loss:touch", "stop_loss:close"}
                       for row in case["structured"]["fills"]
                       if row["side"] == "SELL" and row["reason"].startswith("stop_loss"))
        payload = {
            "rule_revision": S9_RULE_REVISION,
            "historical_raw_sha256": HISTORICAL_GOLDEN_SHA256,
            "historical_canonical_sha256": HISTORICAL_CANONICAL_SHA256,
            "books": list(S9_BOOK_NAMES),
            "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                     "platform": sys.platform},
            "contract": CANONICAL_CONTRACT,
            "cases": cases,
        }
        S9_GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {S9_GOLDEN}: 2 corrected cases / 4 production CSV hashes")
        return
    if not args.check:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        if head != SOURCE or GOLDEN.exists():
            parser.error("Generation requires original eff77f3 HEAD and an absent golden; use --check")
    with tempfile.TemporaryDirectory(prefix="off-byte-baseline-") as temp:
        cases = capture_matrix(Path(temp))
    if args.check:
        skipped = set()
        for book, engine in CASES:
            actual = cases[f"{book}/{engine}"]
            expected, canonical_expected, recorded_pandas = expected_case(book, engine)
            assert_case_canonical(book, actual, expected, canonical_expected)
            reason = byte_skip_reason(recorded_pandas)
            if reason:
                skipped.add(reason)
            else:
                assert_case_bytes(actual, expected)
        with tempfile.TemporaryDirectory(prefix="industry-default-check-") as temp:
            industry_default_cases = {
                (book, engine): capture_case(
                    book,
                    engine,
                    Path(temp) / book / engine,
                    rule_profile="industry",
                )
                for book, engine in INDUSTRY_DEFAULT_CASES
            }
        for (book, engine), actual in industry_default_cases.items():
            expected, canonical_expected, recorded_pandas = expected_case(
                book, engine, rule_profile="industry-default"
            )
            assert_case_canonical(book, actual, expected, canonical_expected)
            reason = byte_skip_reason(recorded_pandas)
            if reason:
                skipped.add(reason)
            else:
                assert_case_bytes(actual, expected)
        with tempfile.TemporaryDirectory(prefix="industry-p11-check-") as temp:
            industry_cases = {
                (book, engine): capture_case(
                    book, engine, Path(temp) / book / engine,
                    rule_profile="industry", fixture="p11",
                )
                for book, engine in P11_CASES
            }
        for (book, engine), actual in industry_cases.items():
            expected, canonical_expected, recorded_pandas = expected_case(
                book, engine, rule_profile="industry"
            )
            assert_case_canonical(book, actual, expected, canonical_expected)
            reason = byte_skip_reason(recorded_pandas)
            if reason:
                skipped.add(reason)
            else:
                assert_case_bytes(actual, expected)
        for reason in sorted(skipped):
            print(f"SKIP: {reason}")
        if not skipped:
            print(
                "PASS: production CSV + library hashes (raw bytes) for "
                f"{len(CASES)} legacy, {len(INDUSTRY_DEFAULT_CASES)} "
                f"industry-default, and {len(P11_CASES)} industry P11 cases"
            )
        print(
            f"PASS: {len(CASES)} legacy and {len(INDUSTRY_DEFAULT_CASES)} "
            "industry-default canonical CSV/account cases across the current registry "
            f"plus {len(P11_CASES)} industry P11 cases; pandas={pd.__version__}"
        )
        return
    for case in cases.values():
        assert case["sha256_csv_bytes"] == case["library_sha256_csv_bytes"], "writer/library mismatch"
    payload = {
        "source": SOURCE, "books": list(BOOK_NAMES),
        "captured_environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                 "platform": sys.platform},
        "writer_contract": "Unmodified writer bytes: shared LF (Linux); v7 CRLF; no float override",
        "cases": cases,
    }
    GOLDEN.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {GOLDEN}: 39 cases / 78 production CSV hashes")


if __name__ == "__main__":
    main()
