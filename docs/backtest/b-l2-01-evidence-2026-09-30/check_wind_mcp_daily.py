# -*- coding: utf-8 -*-
"""Offline self-check for raw_excerpt_wind_mcp_daily_603196SH.json.

Recomputes the lake-vs-Wind(MCP) comparison, the pinned-CSV hashes and the
field-catalog negative result purely from the package's embedded rows plus
the pinned lake raw package. No network, no MCP. Exit 0 = all consistent.

This validates internal consistency of a DRAFT raw excerpt
(bl2_raw_excerpt_draft_v0_host_review); it does not upgrade anything to
bl2_proof_v1 and does not unblock any R3 gate.
"""
import csv
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw_materials"
PKG = RAW / "raw_excerpt_wind_mcp_daily_603196SH.json"
LAKE = RAW / "raw_lake_daily_603196SH_20251020_20251105.json"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    pkg = json.loads(PKG.read_text(encoding="utf-8"))
    lake = json.loads(LAKE.read_text(encoding="utf-8"))
    wind = {r["trade_date"]: r for r in pkg["vendor_rows"]["wind_window"]}
    errors = []

    # 0. pinned originals
    if pkg["sources"]["lake"]["parquet_sha256"] != lake["source"]["sha256"]:
        errors.append("lake parquet sha256 drift vs lake raw package")
    for key, fname in (
        ("wind_mcp", "wind_mcp_603196_daily_20251020_20251105.csv"),
        ("wind_mcp_field_catalog", "wind_mcp_field_search_volume.csv"),
    ):
        src = pkg["sources"][key]
        if src["response_csv"] != fname:
            errors.append(f"{key}: response_csv name drift")
        if sha256(RAW / fname) != src["response_csv_sha256"]:
            errors.append(f"{key}: pinned CSV sha256 mismatch")

    # 0b. pinned daily CSV rows == embedded wind_window rows
    with open(RAW / "wind_mcp_603196_daily_20251020_20251105.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            w = wind.get(row["trade_date"])
            if w is None:
                errors.append(f"{row['trade_date']}: CSV row not embedded")
                continue
            for c in ("open", "high", "low", "close", "volume", "amt"):
                if row[c] != w[c]:
                    errors.append(f"{row['trade_date']} {c}: csv={row[c]} embedded={w[c]}")

    # 1. lake vs wind: OHLC + amount equal per day; wind shares vs 100x lake
    exact = 0
    odd = {}
    for r in lake["rows"]:
        d = r["trade_date"]
        w = wind.get(d)
        if w is None:
            errors.append(f"{d}: wind row missing")
            continue
        for f in ("open", "high", "low", "close"):
            if Decimal(r[f]) != Decimal(w[f]):
                errors.append(f"{d} {f}: lake={r[f]} wind={w[f]}")
        if Decimal(r["amount"]) != Decimal(w["amt"]):
            errors.append(f"{d} amount: lake={r['amount']} wind={w['amt']}")
        diff = 100 * int(r["volume"]) - int(w["volume"])
        if diff == 0:
            exact += 1
        else:
            odd[d] = diff
    if exact != 12 or odd != {"2025-10-23": 41}:
        errors.append(f"unit observation drift: exact={exact} odd={odd}")

    # 2. field catalog negative result: no unit annotation on volume
    with open(RAW / "wind_mcp_field_search_volume.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1 or rows[0].get("field") != "volume":
        errors.append(f"field catalog drift: {rows}")
    elif set(rows[0]) != {"field", "category", "description", "aliases"}:
        errors.append(f"field catalog has extra columns (unit?): {set(rows[0])}")
    neg = pkg["field_catalog_negative_result"]
    if neg["unit_annotation"] is not None:
        errors.append("package claim unit_annotation!=null")

    # 3. package summary claims match recomputation
    cmp_ = pkg["comparison"]
    if not (cmp_["ohlc_all_equal"] and cmp_["amount_all_equal"]):
        errors.append("package ohlc/amount claims false")
    if cmp_["days_covered"] != "13/13" or len(cmp_["days"]) != 13:
        errors.append("package days_covered drift")

    if errors:
        for e in errors:
            print("FAIL", e)
        return 1
    print(
        "OK: 13d x (OHLC+amount lake==wind) | wind=100x lake 12/13d, odd-lot "
        "2025-10-23 lake+41 shares | field catalog: volume no unit annotation "
        "(negative result) | pinned CSVs hash-locked"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
