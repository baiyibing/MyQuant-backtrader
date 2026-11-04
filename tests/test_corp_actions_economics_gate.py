from datetime import date
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from backtest.research import corp_actions_econ_gate as gate
from oskh_data.hithink_artifact import SOURCE, digest
from scripts.data.pull_corp_actions_incremental import EVENT_SCHEMA, json_bytes
from scripts.gates import verify_corp_actions_economics_fence as fence
from scripts.gates.verify_corp_actions_hithink_parity import compare


def event(**changes):
    return {
        "code": "600001.SH",
        "event_id": "fixture-1",
        "source": SOURCE,
        "ex_date": date(2026, 10, 12),
        "record_date": date(2026, 10, 9),
        "pay_date": date(2026, 10, 12),
        "cash_div_per_share": Decimal(".199999"),
        "bonus_ratio": Decimal(".2999985"),
        "transfer_ratio": None,
        "bonus_list_date": date(2026, 10, 13),
        **changes,
    }


def lake(tmp_path, rows):
    pq.write_table(pa.Table.from_pylist(rows, schema=EVENT_SCHEMA), tmp_path / "events.parquet")
    (tmp_path / "manifest.json").write_bytes(
        json_bytes(
            {
                "schema_version": 1,
                "revision": "fixture-r1",
                "files": {"events.parquet": {"sha256": digest(tmp_path / "events.parquet")}},
            }
        )
    )
    return tmp_path


def evidence(path, row):
    proof = {
        "format_version": 1,
        "revision": "fixture-r1",
        "events_sha256": digest(path / "events.parquet"),
        "entries": [
            {
                "event_id": row["event_id"],
                "fields_sha256": gate.fields_sha256(row),
                "reviewed_by": "fixture-human",
                "reviewed_at": "2026-10-24",
                "shareholder_class": "ordinary-A",
                "economic_basis": "actual per-share distribution",
                "policy_id": "fixture-policy-v1",
                "event_identity": "notice fixture 123 implementation",
                "announcement_chain": [
                    {"document_id": "fixture-123", "sha256": "0" * 64, "supersedes": None}
                ],
                "applicable_document_id": "fixture-123",
            }
        ],
    }
    (path / "evidence.json").write_bytes(json_bytes(proof))
    return proof


def test_dates_alone_and_self_asserted_revision_never_approve_hithink():
    row = event()
    for proof in (
        None,
        {"revision": "fixture-r1", "entries": [{"event_id": "fixture-1", "approved": True}]},
    ):
        accepted, blocked, reasons = gate.gate_rows_for_economics([row], evidence=proof)
        assert not accepted and blocked == [row]
        assert "unverified_economic_basis" in reasons[0]["reasons"]


@pytest.mark.parametrize("source", [SOURCE, "wind:wind_get_stock_events"])
def test_all_sources_report_missing_pay_and_bonus_list_dates(source):
    row = event(source=source, pay_date=None, bonus_list_date=None)
    accepted, blocked, reasons = gate.gate_rows_for_economics([row])
    assert not accepted and len(blocked) == 1
    assert {"missing_pay_date", "missing_bonus_list_date"} <= set(reasons[0]["reasons"])


def test_wind_regular_single_event_remains_eligible():
    row = event(source="wind:wind_get_stock_events")
    assert gate.gate_rows_for_economics([row]) == ([row], [], [])


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "cninfo:unsupported"},
        {"code": "INVALID"},
        {"ex_date": None},
        {"pay_date": "2026-10-12"},
        {"record_date": date(2026, 10, 13)},
        {"cash_div_per_share": Decimal("NaN")},
        {"bonus_ratio": Decimal("-.1")},
    ],
)
def test_identity_and_structure_fail_whole_batch(changes):
    with pytest.raises(ValueError):
        gate.gate_rows_for_economics([event(**changes)])


def test_loader_binds_revision_file_fields_and_full_review(tmp_path):
    row = event()
    lake(tmp_path, [row])
    proof = evidence(tmp_path, row)
    accepted, blocked, reasons = gate.load_corp_actions_for_economics(
        tmp_path, evidence_path=tmp_path / "evidence.json"
    )
    assert accepted == [row] and not blocked and not reasons
    proof["revision"] = "fixture-stale"
    (tmp_path / "evidence.json").write_bytes(json_bytes(proof))
    with pytest.raises(ValueError, match="revision/file"):
        gate.load_corp_actions_for_economics(tmp_path, evidence_path=tmp_path / "evidence.json")
    proof["revision"] = "fixture-r1"
    proof["entries"][0]["fields_sha256"] = "1" * 64
    (tmp_path / "evidence.json").write_bytes(json_bytes(proof))
    with pytest.raises(ValueError, match="event/fields"):
        gate.load_corp_actions_for_economics(tmp_path, evidence_path=tmp_path / "evidence.json")


@pytest.mark.parametrize(
    "changes",
    [
        {"announcement_chain": []},
        {"shareholder_class": ""},
        {"policy_id": ""},
        {"applicable_document_id": "wrong"},
        {"reviewed_at": "2099-01-01"},
    ],
)
def test_incomplete_review_is_explicitly_blocked(tmp_path, changes):
    row = event()
    lake(tmp_path, [row])
    proof = evidence(tmp_path, row)
    proof["entries"][0].update(changes)
    (tmp_path / "evidence.json").write_bytes(json_bytes(proof))
    accepted, blocked, reasons = gate.load_corp_actions_for_economics(
        tmp_path, evidence_path=tmp_path / "evidence.json"
    )
    assert not accepted and len(blocked) == 1 and reasons[0]["reasons"]


def test_same_day_shareholder_classes_are_not_summed():
    rows = [
        event(source="wind:wind_get_stock_events", cash_div_per_share=Decimal(".4921")),
        event(
            source="wind:wind_get_stock_events",
            event_id="fixture-2",
            cash_div_per_share=Decimal(".3906"),
        ),
    ]
    accepted, blocked, reasons = gate.gate_rows_for_economics(rows)
    assert not accepted and blocked == rows
    assert all("multiple_events_require_explicit_selection" in r["reasons"] for r in reasons)


def test_loader_rejects_changed_manifest_hash(tmp_path):
    lake(tmp_path, [event()])
    (tmp_path / "events.parquet").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        gate.load_corp_actions_for_economics(tmp_path)


def test_fence_inventory_and_maintenance_exemptions():
    path = "backtest/research/csv_daily_backtest.py"
    bypass = "from pyarrow import parquet as pq\nx = pq.read_table(root / 'corp_actions' / 'events.parquet')"
    assert fence.violations(bypass, path)
    assert fence.violations("from scripts.data.hithink_incremental import imported", path)
    assert fence.violations(
        "import backtest.research.corp_actions_econ_gate as eg\neg.gate_rows_for_economics(rows)",
        path,
    )
    assert fence.violations("from backtest.research import corp_actions_econ_gate as eg", path)
    assert fence.violations("pq.read_table(events_path)", path)
    assert fence.violations("from pyarrow.parquet import read_table as rt\nrt(events_path)", path)
    assert not fence.violations(
        "from backtest.research.corp_actions_econ_gate import load_corp_actions_for_economics\nx=load_corp_actions_for_economics()",
        path,
    )
    assert not fence.violations(bypass, "scripts/data/pull_corp_actions_incremental.py")
    assert not fence.violations(bypass, "scripts/gates/verify_corp_actions_hithink_parity.py")
    assert fence.main() == 0


@pytest.mark.parametrize("parents", [[None, None], [None, "A", "A"]])
def test_review_rejects_unrelated_or_forked_revision_chains(tmp_path, parents):
    row = event()
    lake(tmp_path, [row])
    proof = evidence(tmp_path, row)
    entry = proof["entries"][0]
    entry["announcement_chain"] = [
        {"document_id": name, "sha256": "0" * 64, "supersedes": parent}
        for name, parent in zip("ABC", parents)
    ]
    entry["applicable_document_id"] = entry["announcement_chain"][-1]["document_id"]
    (tmp_path / "evidence.json").write_bytes(json_bytes(proof))
    accepted, blocked, reasons = gate.load_corp_actions_for_economics(
        tmp_path, evidence_path=tmp_path / "evidence.json"
    )
    assert (
        not accepted and blocked and "invalid_announcement_revision_chain" in reasons[0]["reasons"]
    )


def parity(wind, hi, known=None, **kwargs):
    return compare(
        wind,
        hi,
        known or [],
        start=date(2015, 1, 1),
        end=date(2026, 10, 24),
        codes={"600001.SH"},
        classification=kwargs.get("classification", {}),
        overrides=kwargs.get("overrides", []),
    )


def test_parity_exact_boundary_new_and_missing_keys_fail():
    w = [event(cash_div_per_share=Decimal(".0199"), bonus_ratio=Decimal(0))]
    h = [
        {
            "thscode": "600001.SH",
            "ex_date": date(2026, 10, 12),
            "dividend_per_share": Decimal(".02"),
            "per_share_bonus": Decimal(0),
        }
    ]
    result = parity(w, h)
    assert (
        not result["passed"] and len(result["new_discrepancies"]) == 1
    )  # exactly 1e-4, no float error
    key = {
        "code": "600001.SH",
        "ex_date": "2026-10-12",
        "field": "cash",
        "wind_value": ".0199",
        "hithink_value": ".02",
    }
    assert parity(w, h, [key])["passed"]
    h[0]["dividend_per_share"] = Decimal(".0199")
    assert parity(w, h, [key])["missing_frozen_discrepancies"]


def test_parity_subthreshold_still_reported_and_override_historical_scope_checked():
    w = [event(cash_div_per_share=Decimal(".2"), bonus_ratio=Decimal(0))]
    h = [
        {
            "thscode": "600001.SH",
            "ex_date": date(2026, 10, 12),
            "dividend_per_share": Decimal(".199999"),
            "per_share_bonus": Decimal(0),
        }
    ]
    result = parity(w, h)
    assert result["passed"] and len(result["differences"]) == 1 and not result["economics_accepted"]
    override = {
        "code": "600001.SH",
        "classification": "delisted_explained",
        "scope_start": "2026-10-13",
        "scope_end": "2026-10-24",
    }
    assert not parity(w, [], overrides=[override])["passed"]
    override["scope_start"] = "2026-10-12"
    assert parity(w, [], overrides=[override])["passed"]
