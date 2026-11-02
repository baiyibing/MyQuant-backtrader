"""OP06: stock conversion stuffed into cash/bonus columns is hard-rejected."""

from datetime import date
from decimal import Decimal
import json
from pathlib import Path

import pytest

from backtest.research import corp_actions_econ_gate as gate

REASON = "unsupported_stock_conversion_in_cash_bonus_schema"


def wind_event(**changes):
    return {
        "code": "600001.SH",
        "event_id": "fixture-1",
        "source": "wind:wind_get_stock_events",
        "ex_date": date(2026, 10, 12),
        "record_date": date(2026, 10, 9),
        "pay_date": date(2026, 10, 12),
        "cash_div_per_share": Decimal(".199999"),
        "bonus_ratio": Decimal(".2999985"),
        "transfer_ratio": None,
        "bonus_list_date": date(2026, 10, 13),
        **changes,
    }


def test_pinned_constants_match_evidence_identity_facts():
    proof = json.loads(
        (
            Path(__file__).resolve().parent.parent
            / "docs/operations/evidence/hithink-artifact-2026-10-30/coverage-identity-facts.json"
        ).read_bytes()
    )
    fact = next(f for f in proof["facts"] if f["code"] == "601198.SH")
    assert fact["classification"] == "in_window_stock_merger"
    assert len(gate.PINNED_STOCK_CONVERSIONS) == 1
    pinned = gate.PINNED_STOCK_CONVERSIONS[0]
    assert pinned.source_code == fact["code"]
    assert pinned.target_code == fact["target_code"]
    assert pinned.target_shares_per_source_share == Decimal(fact["target_shares_per_source_share"])
    assert pinned.conversion_record_date == date.fromisoformat(fact["conversion_record_date"])
    assert pinned.delist_date == date.fromisoformat(fact["delist_date"])
    assert gate.UNSUPPORTED_STOCK_CONVERSION_REASON == REASON


def test_stuffed_601198_as_ordinary_cash_bonus_row_is_blocked():
    row = wind_event(code="601198.SH")
    accepted, blocked, reasons = gate.gate_rows_for_economics([row])
    assert not accepted and blocked == [row]
    assert reasons[0]["reasons"] == [REASON]


def test_601198_ratio_stuffed_into_bonus_ratio_is_blocked():
    row = wind_event(code="601198.SH", cash_div_per_share=None, bonus_ratio=Decimal("0.4376"))
    accepted, blocked, reasons = gate.gate_rows_for_economics([row])
    assert not accepted and blocked == [row]
    assert REASON in reasons[0]["reasons"]


def test_normal_wind_fixture_still_accepted():
    row = wind_event()
    assert gate.gate_rows_for_economics([row]) == ([row], [], [])


def test_unrelated_code_with_equal_bonus_ratio_stays_eligible():
    row = wind_event(bonus_ratio=Decimal("0.4376"))
    assert gate.gate_rows_for_economics([row]) == ([row], [], [])


@pytest.mark.parametrize(
    "changes",
    [
        {"bonus_ratio": Decimal("0.4376"), "event_id": "601198-to-601995-swap"},
        {"bonus_ratio": Decimal("0.4376"), "event_id": "announcement-601995"},
        {"bonus_ratio": Decimal("0.4376"), "event_id": "东兴证券换股吸收合并"},
        {"bonus_ratio": Decimal("0.4376"), "event_id": "fixture-conversion-note"},
        {"bonus_ratio": Decimal("0.4376"), "event_id": "fixture-stock_merger-note"},
        {"bonus_ratio": None, "transfer_ratio": Decimal("0.4376"), "event_id": "601995-conversion"},
    ],
)
def test_decoy_code_with_conversion_markers_and_stuffed_ratio_is_blocked(changes):
    row = wind_event(cash_div_per_share=Decimal("0"), **changes)
    accepted, blocked, reasons = gate.gate_rows_for_economics([row])
    assert not accepted and blocked == [row]
    assert reasons[0]["reasons"] == [REASON]
