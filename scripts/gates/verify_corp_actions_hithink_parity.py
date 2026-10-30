"""Offline historical daily-sum diagnostic. Not an economic entitlement gate."""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import sys

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from oskh_data import hithink_artifact as artifact
from scripts.data import hithink_incremental
from scripts.data.pull_corp_actions_incremental import Run


def fact_key(row):
    if row["field"] not in ("cash", "bonus"):
        raise ValueError("unknown discrepancy field")
    return (artifact.code(row["code"]), str(artifact.day(row["ex_date"])), row["field"],
            str(Decimal(row["wind_value"]).normalize()), str(Decimal(row["hithink_value"]).normalize()))


def compare(wind, hithink, known, *, start, end, codes, classification, overrides):
    sums = [defaultdict(lambda: {"cash": Decimal(0), "bonus": Decimal(0), "components": []}) for _ in range(2)]
    for side, rows in enumerate((wind, hithink)):
        for row in rows:
            ticker = row["code"] if side == 0 else row["thscode"]
            ex_date = row["ex_date"]
            if ticker not in codes or not start <= ex_date <= end:
                continue
            key = (ticker, str(ex_date))
            item = sums[side][key]
            item["cash"] += row["cash_div_per_share"] or Decimal(0) if side == 0 else row["dividend_per_share"]
            item["bonus"] += ((row["bonus_ratio"] or Decimal(0)) + (row["transfer_ratio"] or Decimal(0))
                              if side == 0 else row["per_share_bonus"])
            item["components"].append({k: str(v) if isinstance(v, Decimal) or k.endswith("date") else v for k, v in row.items()})
    left, right = sums
    differences = []
    for key in sorted(left.keys() & right.keys()):
        for field in ("cash", "bonus"):
            a, b = left[key][field], right[key][field]
            if a != b:
                differences.append({"code": key[0], "ex_date": key[1], "field": field,
                                    "wind_value": str(a.normalize()), "hithink_value": str(b.normalize()),
                                    "threshold_difference": abs(a - b) >= Decimal(".0001"),
                                    "wind_components": left[key]["components"], "hithink_components": right[key]["components"]})
    actual = {fact_key(d) for d in differences if d["threshold_difference"]}
    expected = {fact_key(d) for d in known if d["code"] in codes}
    if len(expected) != len([d for d in known if d["code"] in codes]):
        raise ValueError("duplicate frozen discrepancy key")
    missing = []
    overrides = {item["code"]: item for item in overrides}
    for ticker, ex_date in sorted(left.keys() - right.keys()):
        info = classification.get(ticker, {})
        explained = info.get("classification") in ("delisted_explained", "delisted_no_history")
        applied = overrides.get(ticker)
        if applied and applied["classification"] != "unexplained":
            explained |= artifact.day(applied["scope_start"]) <= artifact.day(ex_date) <= artifact.day(applied["scope_end"])
        missing.append({"code": ticker, "ex_date": ex_date, "explained": explained,
                        "classification": info, "override": applied})
    return {"passed": actual == expected and all(r["explained"] for r in missing),
            "new_discrepancies": sorted(actual - expected), "missing_frozen_discrepancies": sorted(expected - actual),
            "differences": differences, "wind_only": missing, "hithink_only": sorted(right.keys() - left.keys()),
            "shared_keys": len(left.keys() & right.keys()), "economics_accepted": False,
            "policy": "daily sums; Wind NULL-as-zero and bonus+transfer; threshold 1e-4 is diagnostic only"}


def verify(run):
    if run.channel != "hithink":
        raise ValueError("parity requires a hithink run")
    run.verify_base()
    _, rows, probes = hithink_incremental.imported(run)
    exclusions, exclusions_sha256 = hithink_incremental.read_exclusions(run)
    facts = hithink_incremental.coverage(run, rows, probes, exclusions=(exclusions, exclusions_sha256))
    base = Path(run.config["lake_dir"])
    manifest = artifact.read_json(base / "manifest.json")
    window = manifest["coverage_window"]
    result = compare(pq.ParquetFile(base / "events.parquet").read().to_pylist(), rows,
                     exclusions["known_discrepancies"], start=artifact.day(window["ask_start"]),
                     end=artifact.day(window["ask_end"]), codes=set(run.config["codes"]),
                     classification=facts["vendor_unknown_classification"], overrides=facts["manual_overrides_applied"])
    result["unresolved_coverage_codes"] = facts["unresolved_codes"]
    result["passed"] &= not facts["unresolved_codes"]
    result["input_hashes"] = {"base": run.config["base_sha256"],
                              "import": artifact.digest(run.path("work/hithink_committed.json")),
                              "exclusions": exclusions_sha256}
    run.verify_base()
    if artifact.digest(run.path("hithink_exclusions.json")) != exclusions_sha256:
        raise ValueError("exclusions changed during parity")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args(argv)
    try:
        run = Run(args.run_dir)
        with run.locked():
            result = verify(run)
            run.write("parity/report.json", (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
            summary = ("# Hithink historical parity\n\n" + f"Passed: {result['passed']}\n\n"
                       + f"New keys: {len(result['new_discrepancies'])}; missing frozen keys: {len(result['missing_frozen_discrepancies'])}; "
                       + f"unexplained coverage: {len(result['unresolved_coverage_codes'])}.\n\n"
                       + "All exact differences and source components: [report.json](report.json).\n\n"
                       + "Daily sums are a historical diagnostic. They do not certify economic entitlements.\n")
            run.write("parity/report.md", summary.encode("utf-8"))
        print(summary)
        return 0 if result["passed"] else 2
    except (ValueError, KeyError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
