"""Isolated joint-return R1 replay; explicit synthetic or frozen MQ bundle + minute JSON only.

Wire lock: MQ #92 contract.md SHA256 CONTRACT_HASH. The incoming BT base is the
R0 contract's base; IMPLEMENTATION_BASE_BT records the separately authorized R1
base. Neither the sibling repository nor any lake/production module is imported.

``--intents`` names intents.csv; manifest.json, constraints.csv, pref_check.json
must be adjacent. ``--bars`` names one JSON object, with schema_version,
kind=synthetic, metadata, bars, corporate_actions and content_sha256 (hash of the
object without that last field). metadata requires calendar, timezone,
price_domain, bar_label=OPEN_TIME|CLOSE_TIME, interval_seconds=60, sessions
(date -> [[inclusive open, exclusive end], ...]), session_source, initial_at,
initial_lots (lot_id -> acquired_at, execution_symbol, mark_price, mark_at),
corporate_actions_complete=true and source. Each bar supplies instrument,
execution_symbol, timestamp, open, close, limit_up, limit_down, suspended and
capacity (shared executable shares per instrument/minute, not inferred volume).
No default session endpoints, price limits, acquisition dates or market prices.

M-LAG uses actual minute open strictly after available_at, >= effective_at.
M-REF uses the frozen reference price at a session open >= available/effective,
with ideal full liquidity, but retains T+1, missing/suspended bars and directional
limit gates. It is a hypothetical price/liquidity reference, NOT causal execution
at the original reference close. Both use only open for execution, close for
valuation; no high/low triggers. No stops or holding-period exits are generated.

Only an input SELL with reason exactly EXPIRY_EXIT denotes an original expiry
exit (MQ R1 currently emits none). If its original expiry session has no bar,
its deadline extends by market sessions until the first session with a bar;
original expires_at is never rewritten. An unrecognized expiry-like reason is
blocked instead of guessed. Ordinary unfilled orders expire at the deadline.

Corporate actions are explicit share->share quantity conversions, with the MQ
section 6 event fields. original/current_quantity describe a reference unit
quantity, not an arm's actual holding. Every affected lot/order records its own
before/after quantities, and outstanding quantities use reference_price_at as
the unit epoch. Fees are never rescaled. Carried marks divide by factor and keep
the original valuation time. This is NOT cash-dividend total return accounting.

Daily turnover uses NAV at the first execution attempt, after simultaneous open
marks and before any fills; no-attempt days use prior close NAV. Missing final
minutes retain the last known mark with its actual timestamp and STALE_MARK.
Initial NAV is included in the drawdown high-water mark. P-BASE is replayed
independently with the same fill/input even when only P-CHASE is requested.
Synthetic outputs remain SYNTHETIC_ONLY: synthetic green != real return.
Frozen control-only 50/5 packs use a separate contract pin and --bars with
kind=frozen_explicit, content_sha256, metadata.contract_hash and metadata.source.
Only P-BASE / M-LAG is enabled for frozen packs. M-REF is INPUT_BLOCKED because
sessions.json reference_price=1.0 placeholders are not market prices. Intents
and quantities are never rewritten. Frozen replay is research, not host source
or PIT acceptance. No Qlib root discovery/reader is implemented in this adapter.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
import hashlib
import io
import json
from pathlib import Path
import re
import shutil

SCHEMA_VERSION = "joint-return-v1"
CONTRACT_HASH = "dfa020d2c01e6cfe6612f09be2d569294ff94d82fd1ede5cea61a41d74a81737"
FROZEN_CONTRACT_HASH = "9ee8cc3c63c1e7a0910c777c9a58fa4b884a89a853586a65363dc818b54cfe41"
BASE_MQ = "4e4368b274ada2e27da5902f7420aa5a8ae5950c"
CONTRACT_BASE_BT = "1049b904bdd818dbb79f51f1830a008c8f83b141"
IMPLEMENTATION_BASE_BT = "073538d4486a07a71f561631c3f274ffa06eeecb"
ARMS = ("P-BASE", "P-CHASE")
FILL_MODES = ("M-REF", "M-LAG")
INTENT_FIELDS = (
    "arm_id", "intent_id", "instance_id", "lot_id", "instrument", "execution_symbol",
    "decision_at", "available_at", "side", "target_weight", "original_target_quantity",
    "quantity_unit", "quantity_conversion", "reference_price", "reference_price_at",
    "reason", "reference_state_hash", "source_plan_hash", "effective_at", "expires_at",
    "retry_policy", "conflict_policy", "expiry_policy", "native_stop",
)
CONSTRAINT_FIELDS = (
    "date", "arm_id", "instrument", "status", "reason", "score", "anti_rank",
    "t0_median", "reference_state_hash",
)
ORDER_POLICY = {
    "retry_policy": "NEXT_LEGAL_BAR_LIMIT_DOWN_NEXT_SESSION",
    "conflict_policy": "CANCEL_OLDER_REMAINDER_SELL_FIRST",
    "expiry_policy": "CANCEL_REMAINDER_EXPIRY_EXIT_DEFER_NO_BAR",
}
TERMINAL = {"FILLED", "REJECTED", "EXPIRED", "CANCELLED"}
EPS = Decimal("0.00000001")  # CNY only; quantity conservation is exact Decimal.


class ReplayError(ValueError):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail
        super().__init__(f"{status}: {detail}")


def require(ok, detail, status="INPUT_BLOCKED"):
    if not ok:
        raise ReplayError(status, detail)


def fields(value, names, context):
    require(isinstance(value, dict), f"{context}: expected object")
    require(set(names) <= value.keys(), f"{context}: missing {sorted(set(names) - value.keys())}")


def canonical_bytes(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ReplayError("INPUT_BLOCKED", "nonfinite/non-JSON input") from exc


def raw_hash(raw):
    return hashlib.sha256(raw).hexdigest()


def content_hash(value):
    return raw_hash(canonical_bytes(value))


def _unique(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, f"duplicate JSON key: {k}")
        result[k] = v
    return result


def load_json_bytes(raw):
    require(not raw.startswith(b"\xef\xbb\xbf") and b"\0" not in raw, "BOM/NUL forbidden")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeError, ValueError) as exc:
        if isinstance(exc, ReplayError):
            raise
        raise ReplayError("INPUT_BLOCKED", "invalid UTF-8 JSON") from exc
    canonical_bytes(value)
    return value


def read_bytes(path):
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise ReplayError("INPUT_BLOCKED", f"explicit input unavailable: {path}") from exc


def stamp(value):
    require(isinstance(value, str), "timestamp must be a string")
    try:
        t = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReplayError("INPUT_BLOCKED", f"invalid timestamp: {value}") from exc
    require(t.utcoffset() == timedelta(hours=8) and t.isoformat(timespec="seconds") == value,
            "timestamp requires seconds and Asia/Shanghai +08:00")
    return t


def date(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), "invalid date")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ReplayError("INPUT_BLOCKED", "invalid date") from exc


def sha(value, size=64):
    require(isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{size}}}", value), "invalid full hash")


def num(value, name, *, positive=False):
    require(type(value) in (int, float), f"{name}: finite number required")
    d = Decimal(str(value))
    require(d.is_finite() and (d > 0 if positive else d >= 0), f"{name}: invalid number")
    return d


def text_value(value, name):
    require(isinstance(value, str) and bool(value), f"{name}: nonempty string required")


def csv_bytes(rows, columns):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(canonical_bytes(row[k]).decode() for k in columns)
    return stream.getvalue().encode("utf-8")


def read_csv(raw, columns, *, frozen=False):
    require(not raw.startswith(b"\xef\xbb\xbf") and b"\0" not in raw, "BOM/NUL forbidden")
    try:
        reader = csv.reader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
        require(next(reader, None) == list(columns), "CSV column drift", "CONTRACT_MISMATCH")
        rows = []
        for cells in reader:
            require(len(cells) == len(columns), "CSV row width drift", "CONTRACT_MISMATCH")
            values = []
            for column, cell in zip(columns, cells):
                value = load_json_bytes(cell.encode())
                # Some frozen exports JSON-encode a scalar twice. Decode only
                # valid nested JSON; content/intent hashes still bind exact types.
                if frozen and isinstance(value, str) and (
                    value.startswith('"') or column in {
                        "target_weight", "original_target_quantity", "reference_price",
                        "score", "anti_rank", "t0_median",
                    }
                ):
                    try:
                        nested = load_json_bytes(value.encode())
                    except ReplayError:
                        pass
                    else:
                        value = nested
                values.append(value)
            require(all(not isinstance(v, (dict, list)) for v in values), "CSV cells must be JSON scalars")
            rows.append(dict(zip(columns, values)))
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise ReplayError("INPUT_BLOCKED", "invalid UTF-8 CSV") from exc


def sort_intents(rows):
    return sorted(rows, key=lambda r: (r["arm_id"], r["decision_at"], r["side"] != "SELL",
                                       r["instrument"], r["intent_id"]))


def validate_intents(rows):
    seen, symbols, reverse = set(), {}, {}
    for r in rows:
        require(set(r) == set(INTENT_FIELDS), "intent fields drift", "CONTRACT_MISMATCH")
        require(r["arm_id"] in ARMS and r["side"] in ("BUY", "SELL"), "invalid arm/side")
        for k in ("intent_id", "reference_state_hash", "source_plan_hash"):
            sha(r[k])
        require(r["intent_id"] not in seen, "duplicate intent id", "CONTRACT_MISMATCH")
        seen.add(r["intent_id"])
        require(r["intent_id"] == content_hash({k: v for k, v in r.items() if k != "intent_id"}),
                "intent identity drift", "CONTRACT_MISMATCH")
        for k in ("instance_id", "lot_id", "instrument", "execution_symbol", "reason"):
            text_value(r[k], k)
        d, a, e, x = (stamp(r[k]) for k in ("decision_at", "available_at", "effective_at", "expires_at"))
        require(stamp(r["reference_price_at"]) <= d <= a <= e < x, "intent clock violation", "CONTRACT_MISMATCH")
        require(r["quantity_unit"] == "share" and r["quantity_conversion"] == "SNAPSHOT_FIXED",
                "quantity mapping unproven", "SEMANTICS_BLOCKED")
        require(r["native_stop"] == "N/A", "stop injection", "CONTRACT_MISMATCH")
        require(all(r[k] == v for k, v in ORDER_POLICY.items()), "order policy drift", "CONTRACT_MISMATCH")
        q = num(r["original_target_quantity"], "quantity", positive=True)
        num(r["reference_price"], "reference price", positive=True)
        require(num(r["target_weight"], "target weight") <= 1, "invalid target weight")
        require(r["side"] != "BUY" or q % 100 == 0, "BUY LOT_ROUNDING", "CONTRACT_MISMATCH")
        require(r["side"] != "SELL" or r["target_weight"] == 0, "sell target weight must be zero")
        require("EXPIR" not in r["reason"].upper() or (r["reason"] == "EXPIRY_EXIT" and r["side"] == "SELL"),
                "expiry-exit discriminator is not proven", "CONTRACT_MISMATCH")
        inst, symbol = r["instrument"], r["execution_symbol"]
        require(symbols.setdefault(inst, symbol) == symbol and reverse.setdefault(symbol, inst) == inst,
                "execution symbol collision/drift", "SEMANTICS_BLOCKED")
    require(rows == sort_intents(rows), "intent order drift", "CONTRACT_MISMATCH")


def validate_state(state, *, topk=10):
    fields(state, ("cash", "positions", "quantity_unit", "native_stop"), "state")
    num(state["cash"], "cash")
    require(state["quantity_unit"] == "share" and state["native_stop"] == "N/A", "state units/stops drift")
    require(isinstance(state["positions"], dict) and len(state["positions"]) <= topk, "position count")
    lots = set()
    for inst, p in state["positions"].items():
        text_value(inst, "instrument")
        fields(p, ("quantity", "lot_id", "instance_id"), "position")
        num(p["quantity"], "held quantity", positive=True)
        for k in ("lot_id", "instance_id"):
            text_value(p[k], k)
        require(p["lot_id"] not in lots, "duplicate lot")
        lots.add(p["lot_id"])


def validate_manifest(m, rows):
    frozen = m.get("kind") == "frozen"
    arms = ("P-BASE",) if frozen else ARMS
    contract = FROZEN_CONTRACT_HASH if frozen else CONTRACT_HASH
    topk, n_drop = (50, 5) if frozen else (10, 3)
    plan_source = "backtest_rule_intents" if frozen else "frozen_original_intents"
    fields(m, ("schema_version", "run_id", "kind", "status", "input_status", "metadata", "snapshot",
               "contract_hash", "intent_hash", "arm_intent_hashes", "artifacts", "reference_states",
               "initial_state", "pairing", "input_raw_hashes_verified", "execution_status", "return_status"), "manifest")
    require(m["schema_version"] == SCHEMA_VERSION and m["contract_hash"] == contract,
            "real inputs/frozen contract hash/version drift", "CONTRACT_MISMATCH")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", m["run_id"] or ""), "unsafe run_id")
    if frozen:
        require(m["status"] == m["input_status"] == "INPUT_BLOCKED"
                and m.get("portfolio_status") == "PORTFOLIO_CONSTRAINTS_PASS"
                and m.get("scores_mode") == "control_only", "frozen control-only portfolio not ready")
    else:
        require(m["kind"] == "synthetic" and m["status"] == "MQ_DATA_FREE_PASS"
                and m["input_status"] == "SYNTHETIC_ONLY", "real inputs require host P-REF/raw/PIT/coverage acceptance")
    require(m["execution_status"] == "NOT_RUN" and m["input_raw_hashes_verified"] is False,
            "MQ R1 provenance status drift", "CONTRACT_MISMATCH")
    require(m["pairing"] == {"arms": list(arms), "fills": list(FILL_MODES), "bt_acceptance": "NOT_RUN"},
            "pairing drift", "CONTRACT_MISMATCH")
    md = m["metadata"]
    fields(md, ("code_shas", "implementation_bases", "contract_hash", "pred_recorder_id", "generated_at", "window", "calendar", "timezone", "price_domain", "strategy",
                "fees", "risk_budget", "valuation_version", "benchmark_version", "order_policy", "quantity_policy", "inputs"), "metadata")
    require(md["implementation_bases"] == {"MQ": BASE_MQ, "BT": CONTRACT_BASE_BT},
            "incoming R0 implementation bases drift", "CONTRACT_MISMATCH")
    fields(md["code_shas"], ("MQ", "BT"), "code_shas")
    for value in md["code_shas"].values():
        sha(value, 40)
    require(md["contract_hash"] == contract, "metadata contract hash drift", "CONTRACT_MISMATCH")
    if frozen:
        require(md.get("scores_mode") == "control_only" and md.get("arms", ["P-BASE"]) == ["P-BASE"]
                and md.get("candidate_recorder_id") is None and md.get("sidecar_sha256") is None,
                "frozen deferred inputs/arms drift", "CONTRACT_MISMATCH")
        require(md["pred_recorder_id"] == "8a061ea428e04bb3a199a485ade49d0e",
                "frozen recorder identity drift", "CONTRACT_MISMATCH")
        require(md["valuation_version"] == "research-none-mark-v1", "frozen valuation drift", "CONTRACT_MISMATCH")
    else:
        fields(md, ("candidate_recorder_id", "sidecar_sha256"), "metadata")
        require(md["pred_recorder_id"] == "8a061ea428e04bb3a199a485ade49d0e"
                and md["candidate_recorder_id"] == "d03e8ffcb6d14668b4d6fc2b192bc8c7"
                and md["sidecar_sha256"] == "27320f8b7f6de3854802f97325f682039732470ce387f21bc9cd6c3083b7b348",
                "frozen source identity drift", "CONTRACT_MISMATCH")
    stamp(md["generated_at"])
    require(md["timezone"] == "Asia/Shanghai" and md["price_domain"] == "none", "time/price domain drift", "SEMANTICS_BLOCKED")
    cal = md["calendar"]
    require(isinstance(cal, list) and cal and all(isinstance(d, str) for d in cal)
            and cal == sorted(set(cal)), "calendar missing/order/duplicates")
    fields(md["window"], ("start", "end"), "window")
    require(all(date(md["window"]["start"]) <= date(d) <= date(md["window"]["end"]) for d in cal), "calendar outside window")
    for k in ("valuation_version", "benchmark_version"):
        text_value(md[k], k)
    s = md["strategy"]
    fields(s, ("topk", "n_drop", "source", "native_stop", "eligibility_version", "eligibility_rules"), "strategy")
    require(s["topk"] == topk and s["n_drop"] == n_drop and s["source"] == plan_source
            and s["native_stop"] == "N/A" and bool(s["eligibility_version"])
            and isinstance(s["eligibility_rules"], dict) and bool(s["eligibility_rules"]), "frozen 10/3 or 50/5 strategy drift")
    require(md["order_policy"] == ORDER_POLICY and md["quantity_policy"] == {
        "unit": "share", "buy_lot": 100, "sell": "FULL_LOT_EXIT", "corporate_actions": "EXPLICIT_ONLY"}, "policy drift")
    require(num(md["risk_budget"], "risk budget") <= 1, "risk budget above one")
    f = md["fees"]
    fields(f, ("model", "buy_rate", "sell_rate", "minimum", "granularity", "source"), "fees")
    require(f["model"] == "commission_only" and f["granularity"] == "per_order", "fee model drift")
    text_value(f["source"], "fee source")
    for k in ("buy_rate", "sell_rate", "minimum"):
        num(f[k], k)
    fields(m["snapshot"], ("uri", "raw_sha256", "content_sha256", "raw_verified"), "snapshot")
    require(m["snapshot"]["raw_verified"] is True, "MQ snapshot was not verified")
    for source in [m["snapshot"]] + [md["inputs"].get(k, {}) for k in (("scores", "initial_state", "plans") if frozen else ("scores", "initial_state", "plans", "pref"))]:
        fields(source, ("uri", "raw_sha256", "content_sha256"), "source")
        text_value(source["uri"], "source URI")
        sha(source["raw_sha256"])
        sha(source["content_sha256"])
    validate_state(m["initial_state"], topk=topk)
    require(content_hash(m["initial_state"]) == md["inputs"]["initial_state"]["content_sha256"],
            "initial state hash drift", "CONTRACT_MISMATCH")
    require(not frozen or all(r["arm_id"] == "P-BASE" for r in rows), "frozen supports P-BASE only")
    validate_intents(rows)
    require(m["intent_hash"] == content_hash(rows), "intent table hash drift", "CONTRACT_MISMATCH")
    for arm in arms:
        require(m["arm_intent_hashes"].get(arm) == content_hash([r for r in rows if r["arm_id"] == arm]),
                "arm hash drift", "CONTRACT_MISMATCH")
    # Verify immutable reference chains and bind every intent back to its plan;
    # no selection, sizing or reference recursion is rerun on the BT side.
    histories, prior = {}, {a: m["initial_state"] for a in arms}
    require(isinstance(m["reference_states"], list), "reference history required")
    for h in m["reference_states"]:
        fields(h, ("date", "arm_id", "before", "after", "before_hash", "after_hash", "source_plan",
                   "reference_nav", "target_turnover", "initial_build"), "history")
        key = (h["date"], h["arm_id"])
        require(key not in histories and h["arm_id"] in arms, "duplicate/invalid reference history")
        histories[key] = h
    require(set(histories) == {(d, a) for d in cal for a in arms}, "reference arm-days missing/extra")
    plans = {}
    for d in cal:
        for a in arms:
            h = histories[d, a]
            validate_state(h["before"], topk=topk)
            validate_state(h["after"], topk=topk)
            require(h["before_hash"] == content_hash(h["before"]) == content_hash(prior[a])
                    and h["after_hash"] == content_hash(h["after"]), "reference chain drift", "CONTRACT_MISMATCH")
            p = h["source_plan"]
            fields(p, ("date", "arm_id", "pre_state_hash", "source", "corporate_actions", "sells", "buy_candidates",
                       "marks", "mark_at", "decision_at", "available_at", "effective_at", "expires_at"), "source plan")
            require((p["date"], p["arm_id"]) == (d, a) and p["pre_state_hash"] == h["before_hash"]
                    and p["source"] == plan_source, "source plan drift", "CONTRACT_MISMATCH")
            require(p["corporate_actions"] == [], "MQ corporate actions not supported", "SEMANTICS_BLOCKED")
            require(stamp(p["decision_at"]).date().isoformat() == d, "plan decision date drift", "CONTRACT_MISMATCH")
            num(h["reference_nav"], "reference NAV", positive=True)
            num(h["target_turnover"], "target turnover")
            require(type(h["initial_build"]) is bool, "initial build marker missing")
            plans[a, content_hash(p)] = p
            prior[a] = h["after"]
    for r in rows:
        p = plans.get((r["arm_id"], r["source_plan_hash"]))
        require(p is not None and r["reference_state_hash"] == p["pre_state_hash"], "intent plan binding drift", "CONTRACT_MISMATCH")
        require(all(r[k] == p[k] for k in ("decision_at", "available_at", "effective_at", "expires_at")), "plan clock drift", "CONTRACT_MISMATCH")
        candidates = p["sells"] if r["side"] == "SELL" else p["buy_candidates"]
        candidate = next((c for c in candidates if c["instrument"] == r["instrument"]), None)
        require(candidate is not None, "intent not in frozen candidates", "CONTRACT_MISMATCH")
        keys = ("execution_symbol", "instance_id", "lot_id", "target_weight", "original_target_quantity",
                "quantity_unit", "quantity_conversion", "reference_price", "reference_price_at")
        require(all(candidate.get(k) == r[k] for k in keys), "frozen quantity/identity drift", "CONTRACT_MISMATCH")
        require(candidate.get("approved" if r["side"] == "SELL" else "eligible") is True,
                "intent not authorized by frozen plan", "CONTRACT_MISMATCH")
        require(p["marks"].get(r["instrument"]) == r["reference_price"] and p["mark_at"] == r["reference_price_at"],
                "reference mark drift", "CONTRACT_MISMATCH")
        h = histories[p["date"], r["arm_id"]]
        if r["side"] == "SELL":
            held = h["before"]["positions"].get(r["instrument"], {})
            require(all(held.get(k) == r[k] for k in ("lot_id", "instance_id"))
                    and held.get("quantity") == r["original_target_quantity"],
                    "frozen SELL is not the full reference lot", "CONTRACT_MISMATCH")
        else:
            budget = num(r["target_weight"], "weight") * num(h["reference_nav"], "reference NAV")
            expected = ((budget + EPS) / (num(r["reference_price"], "reference price") * 100)).to_integral_value(rounding=ROUND_FLOOR) * 100
            require(expected == num(r["original_target_quantity"], "quantity"),
                    "frozen BUY quantity/weight conversion drift", "CONTRACT_MISMATCH")


def load_bundle(intents_path):
    path = Path(intents_path)
    if path.is_dir():
        path = path / "intents.csv"
    elif path.name == "manifest.json":
        path = path.with_name("intents.csv")
    raw_manifest = read_bytes(path.parent / "manifest.json")
    m = load_json_bytes(raw_manifest)
    fields(m, ("artifacts",), "manifest")
    products = {}
    for name, columns in (("intents.csv", INTENT_FIELDS), ("constraints.csv", CONSTRAINT_FIELDS), ("pref_check.json", None)):
        raw = read_bytes(path if name == "intents.csv" else path.parent / name)
        declared = m["artifacts"].get(name, {})
        require(declared.get("raw_sha256") == raw_hash(raw),
                f"{name}: raw/content hash drift", "CONTRACT_MISMATCH")
        product = read_csv(raw, columns, frozen=m.get("kind") == "frozen") if columns else load_json_bytes(raw)
        require(declared == {"raw_sha256": raw_hash(raw), "content_sha256": content_hash(product)},
                f"{name}: raw/content hash drift", "CONTRACT_MISMATCH")
        products[name] = product
    rows = products["intents.csv"]
    validate_manifest(m, rows)
    expected_pref = "NOT_RUN" if m["kind"] == "frozen" else "SYNTHETIC_PASS"
    require(products["pref_check.json"].get("status") == expected_pref, "MQ P-REF status drift")
    return m, rows, {"manifest_raw_sha256": raw_hash(raw_manifest), "manifest_content_sha256": content_hash(m)}


def validate_bars(bundle, m, intents):
    fields(bundle, ("schema_version", "kind", "metadata", "bars", "corporate_actions", "content_sha256"), "bars snapshot")
    require(bundle["content_sha256"] == content_hash({k: v for k, v in bundle.items() if k != "content_sha256"}),
            "bars content hash drift", "CONTRACT_MISMATCH")
    frozen = m["kind"] == "frozen"
    require(bundle["schema_version"] == SCHEMA_VERSION
            and bundle["kind"] == ("frozen_explicit" if frozen else "synthetic"), "price source kind mismatch")
    if frozen:
        require(bundle["metadata"].get("contract_hash") == FROZEN_CONTRACT_HASH,
                "bars contract hash drift", "CONTRACT_MISMATCH")
    md = bundle["metadata"]
    fields(md, ("calendar", "timezone", "price_domain", "bar_label", "interval_seconds", "sessions",
                "session_source", "initial_at", "initial_lots", "corporate_actions_complete", "source"), "minute metadata")
    require(md["calendar"] == m["metadata"]["calendar"], "minute/MQ calendars differ", "CONTRACT_MISMATCH")
    require(md["timezone"] == "Asia/Shanghai" and md["price_domain"] == "none", "minute time/price domain unproven", "SEMANTICS_BLOCKED")
    require(md["bar_label"] in ("OPEN_TIME", "CLOSE_TIME") and type(md["interval_seconds"]) is int
            and md["interval_seconds"] == 60, "minute label/interval unproven")
    text_value(md["session_source"], "session source")
    text_value(md["source"], "minute source")
    require(md["corporate_actions_complete"] is True, "corporate action coverage unproven", "SEMANTICS_BLOCKED")
    cal = md["calendar"]
    require(isinstance(md["sessions"], dict) and set(md["sessions"]) == set(cal), "session calendar incomplete")
    opportunities, ends = {}, {}
    for day in cal:
        intervals = md["sessions"][day]
        require(isinstance(intervals, list) and bool(intervals), "session endpoints missing")
        previous = None
        for interval in intervals:
            require(isinstance(interval, list) and len(interval) == 2, "session needs open/end")
            start, end = map(stamp, interval)
            require(start.date().isoformat() == day == end.date().isoformat() and start < end
                    and start.second == end.second == 0 and (previous is None or previous <= start), "session endpoints/order invalid")
            t = start
            while t < end:
                opportunities[t] = day
                t += timedelta(seconds=60)
            previous = end
        ends[day] = previous
    initial_at = stamp(md["initial_at"])
    require(initial_at < min(opportunities), "initial valuation must precede first session")
    for r in intents:
        require(initial_at <= stamp(r["available_at"]), "intent predates initial actual ledger")
        if r["reason"] == "EXPIRY_EXIT":
            expiry = stamp(r["expires_at"])
            require(ends.get(expiry.date().isoformat()) == expiry,
                    "EXPIRY_EXIT requires a proven session-end deadline", "CONTRACT_MISMATCH")
    mapping, reverse, lot_ids = {}, {}, set()

    def symbol(inst, value):
        text_value(value, "execution symbol")
        require(mapping.setdefault(inst, value) == value and reverse.setdefault(value, inst) == inst,
                "minute execution mapping drift/collision", "SEMANTICS_BLOCKED")

    for r in intents:
        symbol(r["instrument"], r["execution_symbol"])
    for inst, p in m["initial_state"]["positions"].items():
        lot = p["lot_id"]
        lot_ids.add(lot)
        entry = md["initial_lots"].get(lot, {})
        fields(entry, ("acquired_at", "execution_symbol", "mark_price", "mark_at"), "initial lot evidence")
        require(stamp(entry["acquired_at"]) <= initial_at and stamp(entry["mark_at"]) <= initial_at,
                "initial lot acquisition/mark is future", "CONTRACT_MISMATCH")
        num(entry["mark_price"], "initial mark", positive=True)
        symbol(inst, entry["execution_symbol"])
    require(set(md["initial_lots"]) == lot_ids, "initial lot evidence missing/extra")
    require(isinstance(bundle["bars"], list), "bars must be explicit list")
    bars, closes = {}, defaultdict(list)
    for raw in bundle["bars"]:
        fields(raw, ("instrument", "execution_symbol", "timestamp", "open", "close", "limit_up", "limit_down", "suspended", "capacity"), "minute bar")
        inst = raw["instrument"]
        require(inst in mapping, "bar instrument not in input intent/initial universe")
        symbol(inst, raw["execution_symbol"])
        t = stamp(raw["timestamp"])
        if md["bar_label"] == "CLOSE_TIME":
            t -= timedelta(seconds=60)
        require(t in opportunities, "bar outside frozen session endpoints")
        require((t, inst) not in bars, "duplicate minute bar")
        for k in ("open", "close", "limit_up", "limit_down"):
            num(raw[k], k, positive=True)
        require(raw["limit_down"] <= min(raw["open"], raw["close"])
                <= max(raw["open"], raw["close"]) <= raw["limit_up"], "bar outside explicit price limits")
        require(type(raw["suspended"]) is bool, "suspension evidence missing")
        num(raw["capacity"], "capacity")
        bars[t, inst] = raw
        closes[t + timedelta(seconds=60)].append(raw)
    events = bundle["corporate_actions"]
    require(isinstance(events, list), "quantity events must be explicit list")
    seen, previous = set(), None
    for e in events:
        fields(e, ("event_id", "instrument", "available_at", "effective_at", "from_unit", "to_unit",
                   "original_quantity", "factor", "current_quantity", "source_hash", "price_domain"), "quantity event")
        text_value(e["event_id"], "event id")
        require(e["event_id"] not in seen, "duplicate quantity event", "SEMANTICS_BLOCKED")
        seen.add(e["event_id"])
        available, effective = stamp(e["available_at"]), stamp(e["effective_at"])
        require(available <= effective and initial_at < effective <= ends[cal[-1]]
                and effective.date().isoformat() in cal, "quantity event PIT/window unproven", "SEMANTICS_BLOCKED")
        # Conversion must precede that day's first tradable minute; intraday
        # split timing and overnight mark domains require a separate contract.
        require(effective <= min(t for t, d in opportunities.items() if d == effective.date().isoformat()),
                "intraday quantity event unsupported", "SEMANTICS_BLOCKED")
        key = (effective, e["event_id"])
        require(previous is None or previous < key, "quantity events must be canonically ordered")
        previous = key
        require(e["instrument"] in mapping and e["from_unit"] == e["to_unit"] == "share"
                and e["price_domain"] == "none", "quantity event unit/domain unproven", "SEMANTICS_BLOCKED")
        sha(e["source_hash"])
        original = num(e["original_quantity"], "event original quantity", positive=True)
        factor = num(e["factor"], "quantity factor", positive=True)
        require(original * factor == num(e["current_quantity"], "event current quantity", positive=True),
                "quantity conversion mismatch", "SEMANTICS_BLOCKED")
        # MQ has no event-aware reference recursion in R1. Later plans may only
        # contain orders whose quantity snapshot already postdates the event.
        for r in intents:
            if r["instrument"] == e["instrument"] and stamp(r["reference_price_at"]) == effective:
                raise ReplayError("SEMANTICS_BLOCKED", "quantity snapshot at event boundary is ambiguous")
    if frozen:
        # Deliberately conservative: every symbol in the frozen universe must
        # have explicit evidence for every declared session minute, suspended
        # minutes included. Never manufacture missing bars or stale success.
        expected = len(opportunities) * len(mapping)
        coverage = dict(expected_symbol_minutes=expected, observed_symbol_minutes=len(bars),
                        missing_symbol_minutes=expected - len(bars))
        require(len(bars) == expected, f"explicit price coverage incomplete: {coverage}")
    return opportunities, ends, bars, closes


def plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


class _Replay:
    def __init__(self, m, rows, bundle, arm, fill_mode, validated):
        self.m, self.arm, self.fill_mode = m, arm, fill_mode
        self.opportunities, self.ends, self.bars, self.closes = validated
        self.bars_at = defaultdict(dict)
        self.bar_days = set()
        for (t, inst), bar in self.bars.items():
            self.bars_at[t][inst] = bar
            self.bar_days.add((t.date().isoformat(), inst))
        self.events = bundle["corporate_actions"]
        self.md = bundle["metadata"]
        self.calendar = m["metadata"]["calendar"]
        self.cash = num(m["initial_state"]["cash"], "cash")
        self.positions, self.marks, self.orders, self.fills, self.daily = {}, {}, [], [], []
        self.seen_lots = set()
        self.fees = {k: num(m["metadata"]["fees"][k], k) for k in ("buy_rate", "sell_rate", "minimum")}
        for inst, p in m["initial_state"]["positions"].items():
            evidence = self.md["initial_lots"][p["lot_id"]]
            self.positions[p["lot_id"]] = dict(instrument=inst, instance_id=p["instance_id"],
                quantity=num(p["quantity"], "position quantity"), acquired_at=stamp(evidence["acquired_at"]),
                execution_symbol=evidence["execution_symbol"], quantity_events=[])
            self.marks[inst] = (num(evidence["mark_price"], "mark"), stamp(evidence["mark_at"]), [])
            self.seen_lots.add(p["lot_id"])
        self.start_nav = self.nav()
        require(self.start_nav > 0, "initial NAV denominator must be positive")
        self.pair = dict(run_id=m["run_id"], contract_hash=m["contract_hash"], arm_id=arm,
                         arm_intent_hash=m["arm_intent_hashes"][arm], fill_id=fill_mode)
        for r in rows:
            if r["arm_id"] != arm:
                continue
            q = num(r["original_target_quantity"], "order quantity")
            self.orders.append(dict(intent=deepcopy(r), order_id=content_hash({**self.pair, "intent_id": r["intent_id"]}),
                status="CREATED", reason="NOT_AVAILABLE", current_quantity=q, cumulative_filled_quantity=Decimal(0),
                remaining_quantity=q, cancelled_quantity=Decimal(0), cumulative_notional=Decimal(0),
                cumulative_fee=Decimal(0), factor=Decimal(1), legal_execution_at=None, actual_fill_at=None, last_fill_price=None,
                last_attempt_at=None, limit_down_day=None, deferred_until=None, deferred_expiry=False, deferred_beyond_window=False,
                superseded_by=None, quantity_events=[], transitions=[], reject_after_partial=None))
            self.audit(self.orders[-1], "CREATED", "NOT_AVAILABLE", stamp(r["decision_at"]))
            self.audit(self.orders[-1], "WAITING", "NOT_AVAILABLE", stamp(r["decision_at"]))
        self.order_by_id = {o["intent"]["intent_id"]: o for o in self.orders}

    def nav(self):
        return self.cash + sum((p["quantity"] * self.marks[p["instrument"]][0]
                                for p in self.positions.values()), Decimal(0))

    def sellable(self, lot, t):
        p = self.positions.get(lot)
        if p and "tranches" in p:
            return sum((v["quantity"] for v in p["tranches"] if v["acquired_at"].date() < t.date()), Decimal(0))
        return p["quantity"] if p and p["acquired_at"].date() < t.date() else Decimal(0)

    def audit(self, o, status, reason, t, **detail):
        o["status"], o["reason"] = status, reason
        o["transitions"].append(dict(at=t, status=status, reason=reason, **detail))
        if status in ("EXPIRED", "CANCELLED", "REJECTED"):
            o["cancelled_quantity"] = o["remaining_quantity"]

    def snapshot_order(self, o, t):
        r = o["intent"]
        p = self.positions.get(r["lot_id"])
        mark = self.marks.get(r["instrument"])
        require(o["current_quantity"] == o["cumulative_filled_quantity"] + o["remaining_quantity"],
                "internal quantity conservation", "CONTRACT_MISMATCH")
        return {**r, **self.pair, **{k: v for k, v in o.items() if k not in (
                    "intent", "factor", "limit_down_day", "reject_after_partial", "reason", "last_fill_price")},
                "status_reason": o["reason"], "quantity_unit": "share", "price_domain": "none", "price": o["last_fill_price"],
                "last_valuation_price": None if mark is None else mark[0],
                "unfilled_quantity": o["remaining_quantity"], "cash": self.cash,
                "position_quantity": p["quantity"] if p else Decimal(0),
                "sellable_quantity": self.sellable(r["lot_id"], t),
                "last_valuation_at": mark[1] if mark else None,
                "valuation_stale": mark is None or mark[1] < t,
                "idealized_reference": self.fill_mode == "M-REF"}

    def convert(self, e, t):
        inst, factor = e["instrument"], num(e["factor"], "factor")
        for lot, p in self.positions.items():
            if p["instrument"] == inst:
                before = p["quantity"]
                p["quantity"] *= factor
                for tranche in p.get("tranches", []):
                    tranche["quantity"] *= factor
                p["quantity_events"].append({**e, "lot_id": lot, "applied_original_quantity": before,
                                             "applied_current_quantity": p["quantity"]})
        if inst in self.marks:
            price, at, history = self.marks[inst]
            self.marks[inst] = (price / factor, at, history + [e["event_id"]])
        for o in self.orders:
            r = o["intent"]
            if r["instrument"] == inst and stamp(r["reference_price_at"]) < t:
                before = o["current_quantity"]
                for k in ("current_quantity", "cumulative_filled_quantity", "remaining_quantity", "cancelled_quantity"):
                    o[k] *= factor
                o["factor"] *= factor
                o["quantity_events"].append({**e, "order_id": o["order_id"], "applied_original_quantity": before,
                                             "applied_current_quantity": o["current_quantity"]})

    def activate(self, o, t):
        r = o["intent"]
        # Cancel only strictly older, opposite-side remaining orders. At one
        # timestamp SELL executes first; no same-batch cancellation by row order.
        for old in self.orders:
            s = old["intent"]
            if (old is not o and old["status"] not in TERMINAL and old["status"] != "CREATED"
                    and s["instrument"] == r["instrument"] and s["side"] != r["side"]
                    and stamp(s["available_at"]) < t):
                old["superseded_by"] = r["intent_id"]
                self.audit(old, "CANCELLED", "SUPERSEDED", t, superseded_by=r["intent_id"])
        self.audit(o, "WAITING", "NOT_AVAILABLE", t)

    def expire(self, o, t):
        if o["status"] in TERMINAL or o["status"] == "CREATED" or o["deferred_beyond_window"]:
            return
        r = o["intent"]
        deadline = o["deferred_until"] or stamp(r["expires_at"])
        if t < deadline:
            return
        expiry_day = deadline.date().isoformat()
        # Existence, not tradability: suspended/locked bars do not authorize
        # Q36's missing-session exception. Never extend an ordinary order.
        has_bar = (expiry_day, r["instrument"]) in self.bar_days
        if r["reason"] == "EXPIRY_EXIT" and not has_bar:
            later = [d for d in self.calendar if d > expiry_day]
            o["deferred_expiry"] = True
            o["deferred_until"] = self.ends[later[0]] if later else None
            o["deferred_beyond_window"] = not later
            self.audit(o, "PARTIAL" if o["cumulative_filled_quantity"] else "WAITING", "NO_BAR", t,
                       original_expires_at=r["expires_at"], expiry_deferred=True)
        else:
            self.audit(o, "EXPIRED", "EXPIRED", t)

    def attempt(self, o, bar, t, capacity):
        r = o["intent"]
        o["last_attempt_at"] = t
        if o["legal_execution_at"] is None:
            o["legal_execution_at"] = t
        state = "PARTIAL" if o["cumulative_filled_quantity"] else "ACTIVE"
        self.audit(o, state, "", t)
        if bar is None:
            self.audit(o, state, "NO_BAR", t)
            return capacity
        if bar["suspended"]:
            self.audit(o, state, "SUSPENDED", t)
            return capacity
        if r["side"] == "SELL" and o["limit_down_day"] == t.date():
            # This day's first limit-down attempt froze further attempts. The
            # next market session rechecks the unchanged original intent.
            return capacity
        market_price = num(bar["open"], "open")
        if r["side"] == "BUY" and market_price >= num(bar["limit_up"], "limit up"):
            self.audit(o, state, "LIMIT_UP", t)
            return capacity
        if r["side"] == "SELL" and market_price <= num(bar["limit_down"], "limit down"):
            o["limit_down_day"] = t.date()
            self.audit(o, state, "LIMIT_DOWN", t)
            return capacity
        p = self.positions.get(r["lot_id"])
        if r["side"] == "SELL":
            if p is None or p["instrument"] != r["instrument"] or p["instance_id"] != r["instance_id"]:
                self.audit(o, "REJECTED", "SELLABLE_INSUFFICIENT", t)
                return capacity
            if o["remaining_quantity"] > p["quantity"]:
                self.audit(o, "REJECTED", "SELLABLE_INSUFFICIENT", t)
                return capacity
            if not self.sellable(r["lot_id"], t):
                self.audit(o, state, "T_PLUS_ONE", t)
                return capacity
        else:
            same_inst = [q for q in self.positions.values() if q["instrument"] == r["instrument"]]
            own_partial = bool(o["cumulative_filled_quantity"]) and p is not None and p["instance_id"] == r["instance_id"]
            if (same_inst and not own_partial) or (r["lot_id"] in self.seen_lots and not own_partial):
                self.audit(o, "REJECTED", "UNIT_MAPPING_BLOCKED", t)
                return capacity
        price = (num(r["reference_price"], "reference") / o["factor"]
                 if self.fill_mode == "M-REF" else market_price)
        quantity = o["remaining_quantity"] if self.fill_mode == "M-REF" else min(o["remaining_quantity"], capacity)
        if r["side"] == "SELL":
            quantity = min(quantity, self.sellable(r["lot_id"], t))
        if r["side"] == "BUY":
            quantity = (quantity / 100).to_integral_value(rounding=ROUND_FLOOR) * 100
        if quantity == 0:
            if r["side"] == "BUY" and o["remaining_quantity"] < 100:
                self.audit(o, "REJECTED", "LOT_ROUNDING", t)
            else:
                self.audit(o, state, "NO_BAR", t, detail="NO_EXECUTABLE_CAPACITY")
            return capacity
        rate = self.fees["buy_rate" if r["side"] == "BUY" else "sell_rate"]

        def incremental_fee(q):
            return max(self.fees["minimum"], (o["cumulative_notional"] + q * price) * rate) - o["cumulative_fee"]

        if r["side"] == "BUY" and quantity * price + incremental_fee(quantity) > self.cash + EPS:
            # Monotone binary search of board lots, retaining rejected remainder.
            lo, hi = 0, int(quantity / 100)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if mid * 100 * price + incremental_fee(Decimal(mid * 100)) <= self.cash + EPS:
                    lo = mid
                else:
                    hi = mid - 1
            quantity = Decimal(lo * 100)
            if quantity == 0:
                self.audit(o, "REJECTED", "CASH_INSUFFICIENT", t)
                return capacity
            o["reject_after_partial"] = "CASH_INSUFFICIENT"
        notional, fee = quantity * price, incremental_fee(quantity)
        if r["side"] == "SELL" and self.cash + notional - fee < -EPS:
            self.audit(o, "REJECTED", "CASH_INSUFFICIENT", t)
            return capacity
        cash_before = self.cash
        if r["side"] == "BUY":
            self.cash -= notional + fee
            if p is None:
                p = dict(instrument=r["instrument"], instance_id=r["instance_id"], quantity=Decimal(0),
                         acquired_at=t, execution_symbol=r["execution_symbol"], quantity_events=[])
                self.positions[r["lot_id"]] = p
                self.seen_lots.add(r["lot_id"])
            # A lot's partial buy may span sessions. Track each purchase date,
            # not a single earliest date, to prevent selling today's shares.
            p.setdefault("tranches", [{"quantity": p["quantity"], "acquired_at": p["acquired_at"]}])
            p["tranches"].append({"quantity": quantity, "acquired_at": t})
            p["quantity"] += quantity
        else:
            self.cash += notional - fee
            p["quantity"] -= quantity
            if "tranches" in p:
                left = quantity
                for tranche in p["tranches"]:
                    if tranche["acquired_at"].date() < t.date():
                        take = min(left, tranche["quantity"])
                        tranche["quantity"] -= take
                        left -= take
                require(left == 0, "internal T+1 tranche conservation", "CONTRACT_MISMATCH")
            if p["quantity"] == 0:
                del self.positions[r["lot_id"]]
        if abs(self.cash) <= EPS:
            self.cash = Decimal(0)
        o["cumulative_filled_quantity"] += quantity
        o["remaining_quantity"] -= quantity
        o["cumulative_notional"] += notional
        o["cumulative_fee"] += fee
        o["actual_fill_at"] = t
        o["last_fill_price"] = price
        self.audit(o, "FILLED" if not o["remaining_quantity"] else "PARTIAL", "", t)
        fill = self.snapshot_order(o, t)
        fill.update(fill_sequence=len(self.fills) + 1, actual_fill_at=t, price=price,
                    market_open=market_price, executed_quantity=quantity, notional=notional,
                    fee=fee, cash_before=cash_before, cash_after=self.cash)
        self.fills.append(deepcopy(fill))
        if o["reject_after_partial"] and o["remaining_quantity"]:
            self.audit(o, "REJECTED", o["reject_after_partial"], t)
        return capacity - quantity if self.fill_mode == "M-LAG" else capacity

    def run(self):
        events_at, arrivals = defaultdict(list), defaultdict(list)
        timeline = set(self.opportunities) | set(self.closes) | set(self.ends.values())
        last = max(self.ends.values())
        for e in self.events:
            events_at[stamp(e["effective_at"])].append(e)
            timeline.add(stamp(e["effective_at"]))
        for o in self.orders:
            r = o["intent"]
            a, x = stamp(r["available_at"]), stamp(r["expires_at"])
            arrivals[a].append(o)
            if a <= last:
                timeline.add(a)
            if x <= last:
                timeline.add(x)
        prior_nav = self.start_nav
        pre_nav, first_attempt = {}, {}
        for t in sorted(timeline):
            day = t.date().isoformat()
            for bar in self.closes.get(t, []):
                if not bar["suspended"]:
                    self.marks[bar["instrument"]] = (num(bar["close"], "close"), t, [])
            for e in events_at.get(t, []):
                self.convert(e, t)
            for o in self.orders:
                self.expire(o, t)
            for o in sorted(arrivals.get(t, []), key=lambda x: (x["intent"]["side"] != "SELL", x["intent"]["intent_id"])):
                self.activate(o, t)
            if t in self.opportunities:
                # All simultaneous open marks are visible before SELL-first fills.
                for inst, bar in self.bars_at.get(t, {}).items():
                    if not bar["suspended"]:
                        self.marks[inst] = (num(bar["open"], "open"), t, [])
                eligible = []
                for o in self.orders:
                    r = o["intent"]
                    available = stamp(r["available_at"])
                    if (o["status"] not in TERMINAL and o["status"] != "CREATED"
                            and t >= stamp(r["effective_at"])
                            and (t > available if self.fill_mode == "M-LAG" else t >= available)
                            and o["limit_down_day"] != t.date()):
                        eligible.append(o)
                if eligible and day not in pre_nav:
                    pre_nav[day], first_attempt[day] = self.nav(), t
                    require(pre_nav[day] > 0, "pre-rebalance NAV denominator must be positive")
                capacity = {inst: num(bar["capacity"], "capacity") for inst, bar in self.bars_at.get(t, {}).items()}
                for o in sorted(eligible, key=lambda x: (x["intent"]["side"] != "SELL", x["intent"]["intent_id"])):
                    inst = o["intent"]["instrument"]
                    capacity[inst] = self.attempt(o, self.bars.get((t, inst)), t, capacity.get(inst, Decimal(0)))
            if day in self.ends and t == self.ends[day]:
                nav = self.nav()
                require(prior_nav > 0 and nav > 0, "daily NAV denominator must be positive")
                fills = [f for f in self.fills if f["actual_fill_at"].date().isoformat() == day]
                buy = sum((f["notional"] for f in fills if f["side"] == "BUY"), Decimal(0))
                sell = sum((f["notional"] for f in fills if f["side"] == "SELL"), Decimal(0))
                fees = sum((f["fee"] for f in fills), Decimal(0))
                denominator = pre_nav.get(day, prior_nav)
                positions = []
                for lot, p in sorted(self.positions.items()):
                    price, at, conversions = self.marks[p["instrument"]]
                    positions.append({**deepcopy(p), "lot_id": lot, "mark_price": price, "last_valuation_at": at,
                                      "stale": at < t, "mark_quantity_events": conversions,
                                      "sellable_quantity": self.sellable(lot, t)})
                self.daily.append({**self.pair, "date": day, "event": "MARK", "nav": nav,
                    "nav_previous": prior_nav, "net_return": nav / prior_nav - 1,
                    "cash": self.cash, "positions_value": nav - self.cash, "positions": positions,
                    "buy_notional": buy, "sell_notional": sell, "two_sided_notional": buy + sell,
                    "fees": fees, "turnover": (buy + sell) / (2 * denominator), "turnover_denominator": denominator,
                    "pre_rebalance_at": first_attempt.get(day), "stale_marks": sum(p["stale"] for p in positions),
                    "last_valuation_at": min((p["last_valuation_at"] for p in positions), default=None),
                    "mark_at": t, "price_domain": "none"})
                prior_nav = nav
        require(len(self.daily) == len(self.calendar), "incomplete NAV calendar")
        return dict(orders=[self.snapshot_order(o, last) for o in self.orders], fills=self.fills,
                    daily_nav=self.daily, nav_start=self.start_nav)


def _metrics(daily, start_nav):
    peak, mdd = start_nav, Decimal(0)
    for d in daily:
        peak = max(peak, d["nav"])
        mdd = max(mdd, 1 - d["nav"] / peak)
    return dict(nav_start=start_nav, nav_end=daily[-1]["nav"], net_return=daily[-1]["nav"] / start_nav - 1,
                max_drawdown=mdd, turnover=sum((d["turnover"] for d in daily), Decimal(0)),
                turnover_daily_mean=sum((d["turnover"] for d in daily), Decimal(0)) / len(daily),
                turnover_denominators=[d["turnover_denominator"] for d in daily],
                buy_notional=sum((d["buy_notional"] for d in daily), Decimal(0)),
                sell_notional=sum((d["sell_notional"] for d in daily), Decimal(0)),
                two_sided_notional=sum((d["two_sided_notional"] for d in daily), Decimal(0)),
                fees=sum((d["fees"] for d in daily), Decimal(0)), calendar_days=len(daily))


def _summary(m, product, base, arm, fill_mode):
    daily = product["daily_nav"]
    orders = product["orders"]
    stats = _metrics(daily, product["nav_start"])
    baseline = _metrics(base["daily_nav"], base["nav_start"])
    stats.update(net_excess=stats["net_return"] - baseline["net_return"],
                 delta_max_drawdown=stats["max_drawdown"] - baseline["max_drawdown"])
    months = {}
    for month in sorted({d["date"][:7] for d in daily}):
        part = [d for d in daily if d["date"].startswith(month)]
        control = [d for d in base["daily_nav"] if d["date"].startswith(month)]
        metric = _metrics(part, part[0]["nav_previous"])
        b = _metrics(control, control[0]["nav_previous"])
        metric.update(net_excess=metric["net_return"] - b["net_return"],
                      delta_max_drawdown=metric["max_drawdown"] - b["max_drawdown"])
        months[month] = metric
    reason_orders = Counter()
    reason_attempts = Counter()
    for o in orders:
        reasons = [t["reason"] for t in o["transitions"] if t["reason"]]
        reason_orders.update(set(reasons))
        reason_attempts.update(reasons)
    denominator = sum((num(o["original_target_quantity"], "quantity") for o in orders), Decimal(0))
    # Convert fills back to each intent's original share units, so an action
    # cannot change the all-intent denominator or manufacture a fill-rate gain.
    numerator = sum((num(o["original_target_quantity"], "quantity") * o["cumulative_filled_quantity"] / o["current_quantity"]
                     for o in orders), Decimal(0))
    initial = [h for h in m["reference_states"] if h["arm_id"] == arm and h.get("initial_build")]
    return {"arm_id": arm, "fill_id": fill_mode, "arm_intent_hash": m["arm_intent_hashes"][arm],
        "window": m["metadata"]["window"], **stats, "months": months,
        "benchmark": {"arm_id": "P-BASE", "fill_id": fill_mode,
                      "arm_intent_hash": m["arm_intent_hashes"]["P-BASE"], **baseline},
        "daily_net_return_difference": [{"date": d["date"], "difference": d["net_return"] - b["net_return"]}
                                        for d, b in zip(daily, base["daily_nav"])],
        "paired_uncertainty": {"status": "NOT_ESTIMATED_SYNTHETIC_R1", "interval": None},
        "coverage": {"intent_count": len(orders), "fully_filled_orders": sum(o["status"] == "FILLED" for o in orders),
            "orders_with_fills": sum(o["cumulative_filled_quantity"] > 0 for o in orders),
            "order_fill_rate": sum(o["status"] == "FILLED" for o in orders) / len(orders) if orders else None,
            "original_quantity_denominator": denominator, "filled_original_quantity": numerator,
            "quantity_fill_rate": numerator / denominator if denominator else None,
            "unfilled_original_quantity": denominator - numerator,
            "terminal_states": dict(Counter(o["status"] for o in orders)),
            "reason_order_counts": dict(reason_orders), "reason_attempt_counts": dict(reason_attempts),
            "stale_mark_days": sum(d["stale_marks"] > 0 for d in daily),
            "open_order_count": sum(o["status"] not in TERMINAL for o in orders)},
        "target_turnover": [{"date": h["date"], "value": h.get("target_turnover"), "initial_build": h.get("initial_build")}
                            for h in m["reference_states"] if h["arm_id"] == arm],
        "initial_build_days": [h["date"] for h in initial],
        "ending_cash": daily[-1]["cash"], "ending_positions": daily[-1]["positions"],
        "fee_addback_return_attribution": stats["net_return"] + stats["fees"] / stats["nav_start"],
        "nav_version": m["metadata"]["valuation_version"], "benchmark_version": m["metadata"]["benchmark_version"],
        "infeasible": {"status": "RETAINED_IN_ALL_INTENT_DENOMINATORS", "reasons": dict(reason_orders)},
        "undefined_exposures": {"low_anti_weight": None, "industry_concentration": None, "size_tail": None}}


def replay(m, intents, bars, *, arm, fill_mode):
    """Pure validated replay. An arm selection never substitutes its state for BASE.

    All inputs are immutable. Use load_bundle/run_replay for disk hash checks;
    this entry validates manifest/content identities for both input paths.
    """
    require(arm in (*ARMS, "all") and fill_mode in (*FILL_MODES, "all"), "unknown arm/fill")
    validate_manifest(m, intents)
    if m["kind"] == "frozen":
        require(arm == "P-BASE", "frozen supports P-BASE only; P-CHASE/weak/Mode B INPUT_BLOCKED")
        require(fill_mode == "M-LAG", "frozen M-REF INPUT_BLOCKED: sessions reference_price placeholders forbidden")
    require(bars is not None, "explicit --bars price source required; no sessions.json price fallback")
    validated = validate_bars(bars, m, intents)
    chosen_arms = ARMS if arm == "all" else (arm,)
    modes = FILL_MODES if fill_mode == "all" else (fill_mode,)
    output = {"orders": [], "fills": [], "daily_nav": []}
    summaries = []
    for mode in modes:
        base = _Replay(m, intents, bars, "P-BASE", mode, validated).run()
        for chosen in chosen_arms:
            product = base if chosen == "P-BASE" else _Replay(m, intents, bars, chosen, mode, validated).run()
            summaries.append(_summary(m, product, base, chosen, mode))
            for d, b in zip(product["daily_nav"], base["daily_nav"]):
                d.update(benchmark_nav=b["nav"], benchmark_net_return=b["net_return"],
                         net_return_difference=d["net_return"] - b["net_return"])
            for key in output:
                output[key].extend(product[key])
    output["summary"] = dict(schema_version=SCHEMA_VERSION, run_id=m["run_id"], contract_hash=m["contract_hash"],
        status="BT_DATA_FREE_PASS", input_status="SYNTHETIC_ONLY", execution_status="SYNTHETIC_RUN",
        return_status="待实测", real_execution_status="INPUT_BLOCKED",
        input_code_shas=m["metadata"]["code_shas"], input_implementation_bases=m["metadata"]["implementation_bases"],
        implementation_base_bt=IMPLEMENTATION_BASE_BT, input_intent_hash=m["intent_hash"],
        bars_content_sha256=bars["content_sha256"], corporate_actions=bars["corporate_actions"],
        results=summaries, semantics=[
            "M-REF: hypothetical frozen reference price and full liquidity at legal minute opens; not real executable return",
            "M-LAG: minute open strictly later than available_at and at/after effective_at; no close-to-same-open backfill",
            "SELL first, then intent_id; shared explicit per-minute capacity; no generated stops or holding-period exits",
            "turnover=0.5*(buy+sell)/NAV before first daily attempt; complete calendar; initial NAV in drawdown peak",
            "MARK carries actual last valuation time; no SELL or commission at window end",
            "net_excess uses independently replayed same-fill P-BASE; daily return difference is not investable NAV",
            "commission_only is not complete tax/fees; addback is accounting attribution, not a no-fee rerun",
            "share conversion is not cash-dividend total return; real source/PIT/action completeness remain unverified",
            "R1 synthetic results do not establish real return, slippage, Sharpe or paired uncertainty",
        ])
    if m["kind"] == "frozen":
        output["summary"].update(status="BT_RESEARCH_REPLAY_PASS", input_status="FROZEN_EXPLICIT",
                                 execution_status="RESEARCH_RUN", mq_input_status=m["input_status"],
                                 deferred_arms={k: "INPUT_BLOCKED" for k in ("P-CHASE", "weak", "Mode B")})
    return plain(output)


# Empty tables still have stable headers. Nonempty tables preserve all intent
# fields and detailed JSON audit cells; unlike input intents, audit cells can
# contain structured quantities/transitions/positions.
ORDER_COLUMNS = tuple(dict.fromkeys((*INTENT_FIELDS, "run_id", "contract_hash", "arm_intent_hash", "fill_id",
    "order_id", "status", "status_reason", "current_quantity", "cumulative_filled_quantity", "remaining_quantity", "cancelled_quantity",
    "cumulative_notional", "cumulative_fee", "legal_execution_at", "actual_fill_at", "last_attempt_at",
    "deferred_until", "deferred_expiry", "deferred_beyond_window", "superseded_by", "quantity_events", "transitions", "price_domain", "price",
    "unfilled_quantity", "cash", "position_quantity", "sellable_quantity", "last_valuation_at", "last_valuation_price", "valuation_stale", "idealized_reference")))
FILL_COLUMNS = (*ORDER_COLUMNS, "fill_sequence", "market_open", "executed_quantity", "notional", "fee", "cash_before", "cash_after")
NAV_COLUMNS = ("run_id", "contract_hash", "arm_id", "arm_intent_hash", "fill_id", "date", "event", "nav", "nav_previous",
    "net_return", "cash", "positions_value", "positions", "buy_notional", "sell_notional", "two_sided_notional",
    "fees", "turnover", "turnover_denominator", "pre_rebalance_at", "stale_marks", "last_valuation_at", "mark_at",
    "price_domain", "benchmark_nav", "benchmark_net_return", "net_return_difference")


def run_replay(intents_path, bars_path, *, arm, fill_mode, out):
    """Write the four-file run only after all validation and replay succeed.

    summary.json is written last as completion marker. Existing directories are
    rejected, even if empty. No source URI in MQ metadata is dereferenced.
    """
    m, intents, provenance = load_bundle(intents_path)
    require(bars_path is not None, "explicit --bars price source required; no sessions.json price fallback")
    raw = read_bytes(bars_path)
    bars = load_json_bytes(raw)
    product = replay(m, intents, bars, arm=arm, fill_mode=fill_mode)
    path = Path(out)
    require(path.name == m["run_id"], "--out must be the final directory named by MQ run_id")
    require(not path.exists(), "output directory already exists", "OUTPUT_BLOCKED")
    data = {name + ".csv": csv_bytes(product[name], columns) for name, columns in
            (("orders", ORDER_COLUMNS), ("fills", FILL_COLUMNS), ("daily_nav", NAV_COLUMNS))}
    summary = product["summary"]
    summary["inputs"] = {**provenance, "bars_raw_sha256": raw_hash(raw), "bars_content_sha256": content_hash(bars),
                         "input_raw_hashes_verified": False, "snapshot_verification": "MQ_DECLARATION_ONLY"}
    summary["artifacts"] = {k: {"raw_sha256": raw_hash(v), "content_sha256": content_hash(product[k[:-4]])}
                            for k, v in data.items()}
    # Hash the exact executing adapter bytes as well as retaining input code
    # SHAs. This identifies pre-commit synthetic runs without claiming that an
    # input fixture's baseline SHA is the actual BT implementation commit.
    summary["replay_source_sha256"] = raw_hash(Path(__file__).read_bytes())
    data["summary.json"] = canonical_bytes(summary) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(exist_ok=False)
    try:
        for name, value in data.items():
            (path / name).write_bytes(value)
    except OSError:
        shutil.rmtree(path)
        raise
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Research replay: synthetic or frozen control-only MQ pack + explicit minute JSON")
    parser.add_argument("--intents", type=Path, required=True, help="explicit MQ intents.csv, directory or manifest.json; companion artifacts adjacent")
    parser.add_argument("--bars", type=Path, help="explicit synthetic or frozen_explicit minute JSON with content hash/provenance; absent => INPUT_BLOCKED; no Qlib auto-discovery")
    parser.add_argument("--arm", choices=(*ARMS, "all"), required=True)
    parser.add_argument("--fill-mode", choices=(*FILL_MODES, "all"), required=True)
    parser.add_argument("--out", type=Path, required=True, help="final backtest_output/joint-return-v1/<run_id> directory")
    args = parser.parse_args(argv)
    try:
        path = run_replay(args.intents, args.bars, arm=args.arm, fill_mode=args.fill_mode, out=args.out)
    except (ReplayError, OSError, KeyError, TypeError, AttributeError) as exc:
        print(canonical_bytes({"status": getattr(exc, "status", "INPUT_BLOCKED"), "detail": str(exc)}).decode())
        return 2
    summary = load_json_bytes(read_bytes(path / "summary.json"))
    print(canonical_bytes({"status": summary["status"], "input_status": summary["input_status"],
                          "summary": str(path / "summary.json")}).decode())
    return 0
