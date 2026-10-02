# -*- coding: utf-8 -*-
"""Offline self-check for raw_excerpt_crossvendor_daily_603196SH.json.

Recomputes the lake-vs-tencent-vs-sina comparison, the 10% limit-rule recalc
and the volume-unit observations purely from the package's embedded vendor
rows plus the pinned lake raw package. No network. Exit 0 = all consistent.

This validates internal consistency of a DRAFT raw excerpt
(bl2_raw_excerpt_draft_v0_host_review); it does not upgrade anything to
bl2_proof_v1 and does not unblock any R3 gate.
"""
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE / "raw_materials" / "raw_excerpt_crossvendor_daily_603196SH.json"
LAKE = HERE / "raw_materials" / "raw_lake_daily_603196SH_20251020_20251105.json"


def main() -> int:
    pkg = json.loads(PKG.read_text(encoding="utf-8"))
    lake = json.loads(LAKE.read_text(encoding="utf-8"))
    tx = {r[0]: r for r in pkg["vendor_rows"]["tencent_window"]}
    sina = {d["day"]: d for d in pkg["vendor_rows"]["sina_window"]}
    errors = []

    if pkg["sources"]["lake"]["parquet_sha256"] != lake["source"]["sha256"]:
        errors.append("lake parquet sha256 drift vs lake raw package")

    # 1. three-vendor OHLC + lake==tencent volume, per embedded lake day
    for r in lake["rows"]:
        d = r["trade_date"]
        t, s = tx.get(d), sina.get(d)
        if t is None or s is None:
            errors.append(f"{d}: vendor row missing")
            continue
        for f, lv, tv, sv in (
            ("open", r["open"], t[1], s["open"]),
            ("close", r["close"], t[2], s["close"]),
            ("high", r["high"], t[3], s["high"]),
            ("low", r["low"], t[4], s["low"]),
        ):
            if not (Decimal(lv) == Decimal(tv) == Decimal(sv)):
                errors.append(f"{d} {f}: lake={lv} tx={tv} sina={sv}")
        if int(r["volume"]) != int(Decimal(t[5])):
            errors.append(f"{d} volume: lake={r['volume']} tx={t[5]}")

    # 2. limit rule: prev close chain from tencent 2025-10-17, +-10%, half-up 0.01
    prev = Decimal(tx["2025-10-17"][2])
    for r in lake["rows"]:
        up = (prev * Decimal("1.1")).quantize(Decimal("0.01"), ROUND_HALF_UP)
        dn = (prev * Decimal("0.9")).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if Decimal(r["high"]) > up or Decimal(r["low"]) < dn:
            errors.append(f"{r['trade_date']}: limit violation up={up} dn={dn}")
        prev = Decimal(r["close"])

    # 3. volume unit: sina shares vs 100x lake hands
    exact = sum(
        1
        for r in lake["rows"]
        if int(sina[r["trade_date"]]["volume"]) == 100 * int(r["volume"])
    )
    odd = {
        r["trade_date"]: int(sina[r["trade_date"]]["volume"]) - 100 * int(r["volume"])
        for r in lake["rows"]
        if int(sina[r["trade_date"]]["volume"]) != 100 * int(r["volume"])
    }
    if exact != 12 or odd != {"2025-10-23": -41}:
        errors.append(f"unit observation drift: exact={exact} odd={odd}")

    # 4. claims inside the package match recomputation
    if not pkg["comparison"]["all_days_all_fields_equal"]:
        errors.append("package claim all_days_all_fields_equal=false")
    if pkg["limit_rule_check"]["violations"] != 0:
        errors.append("package limit violations != 0")

    if errors:
        for e in errors:
            print("FAIL", e)
        return 1
    print(
        "OK: 13d x (OHLC 3-vendor equal + lake==tencent volume) | "
        "limit recalc 0 violations | sina=100x lake 12/13d, odd-lot 2025-10-23 -41 shares"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
