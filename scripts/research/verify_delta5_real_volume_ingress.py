"""Data-free δ5 native/API comparator. Run --help for the external-only CLI.

Fixture JSON contains source evidence/records, independently authored normalized
native inputs, parameters, and a manual fill oracle. It is not source certification.
"""

from __future__ import annotations

import argparse
from dataclasses import fields, is_dataclass
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from backtest.research import csv_minute_backtest as engine  # noqa: E402
from backtest.research.ashare_volume_cap import BucketVolume  # noqa: E402
from backtest.research.delta5_volume_ingress import (  # noqa: E402
    FrozenProvider, IngressError, Inputs, digest, normalize, require,
)

CONTRACT = REPO_ROOT / "docs/backtest/note-delta5-real-volume-ingress-2026-09-29.md"
MAPPING = REPO_ROOT / "backtest/research/delta5_volume_ingress.py"
CELLS = ("M1", "M2", "M3", "M4", "M5", "M6", "M6b", "M7", "M8", "M9", "M10", "M11")
OMITTED = object()


def no_exit(*_):
    """Explicit synthetic override for fixtures isolating capacity/stop exits."""
    return None


def raw(value):
    """Lossless structured state including all lots, groups, stats and cap state.

    Only callable implementation identities are represented by qualified name;
    provider identity is recorded separately with its complete call trace.
    """
    if is_dataclass(value):
        return {f.name: raw(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value):
            return {k: raw(v) for k, v in value.items()}
        return {"pairs": [[raw(k), raw(v)] for k, v in sorted(value.items())]}
    if isinstance(value, (list, tuple)):
        return [raw(v) for v in value]
    if isinstance(value, set):
        return {"set": [raw(v) for v in sorted(value)]}
    if callable(value):
        return {"callable": f"{value.__module__}.{value.__qualname__}"}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return {"timestamp": value.isoformat()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unhandled audit value: {type(value)}")


def snapshot(state):
    result = {k: raw(v) for k, v in vars(state).items() if k != "volume_cap"}
    cap = state.volume_cap
    result["volume_cap"] = None if cap is None else {
        "used": raw(cap.used), "samples": raw(cap._samples),
        "rate_ratio": [cap._numerator, cap._denominator],
    }
    return result


def native_inputs(spec):
    """Direct materialization only: no source mapper, clock shift or unit conversion.

    The fixture author supplies literal close keys, int samples and normalized
    prices separately. Equality is checked against ingress before either API run.
    """
    minute = {}
    for code, rows in spec["minute"].items():
        minute[code] = pd.DataFrame(
            [{k: row[k] for k in ("open", "high", "low", "close", "ymd", "hm")} for row in rows],
            index=pd.DatetimeIndex([row["time"] for row in rows]),
        )
    daily = {code: pd.DataFrame(
        [{k: row[k] for k in ("open", "high", "low", "close")} for row in rows],
        index=pd.DatetimeIndex([row["day"] for row in rows]),
    ) for code, rows in spec["daily"].items()}
    samples = {}
    for code, day, hm, sample in spec["samples"]:
        key = code, day, hm
        require(key not in samples, "native", f"duplicate oracle key {key}")
        if sample is not None:
            require(type(sample[0]) is int and type(sample[1]) is int,
                    "native", "manual native sample requires literal ints")
        samples[key] = None if sample is None else BucketVolume(*sample)
    return Inputs(minute, daily, spec["pool"], spec["names"], samples,
                  spec["start"], spec["end"], {})


def options(params):
    required = {"total_cash", "daily_quota", "name_budget", "stop_pct",
                "buy_cost_rate", "sell_cost_rate", "min_cost", "take_profit_mode"}
    require(set(params) == required, "parameters", "explicit cash/budget/stop/fees/exit mode required")
    for key in required - {"take_profit_mode"}:
        require(type(params[key]) in (int, float) and np.isfinite(params[key])
                and params[key] >= 0, "parameters", f"invalid {key}")
    require(params["take_profit_mode"] in ("book", "disabled"), "parameters", "unknown exit mode")
    # Bind every native kwarg, including all existing opt-ins OFF. No shared CLI.
    result = {k: p.default for k, p in inspect.signature(engine.simulate).parameters.items()
              if p.kind == inspect.Parameter.KEYWORD_ONLY and p.default is not inspect.Parameter.empty}
    result.update({k: v for k, v in params.items() if k != "take_profit_mode"})
    result.update(strategy="version8", minute_stop_trigger="close", exdiv=None,
                  exdiv_economics=None, fix_minute_cash_order=False, tail_window_buy=False,
                  take_profit=no_exit if params["take_profit_mode"] == "disabled" else None)
    return result


def invoke(inputs, kwargs, rate=OMITTED):
    provider = FrozenProvider(inputs.samples, forbidden=rate is OMITTED or rate is None)
    kwargs = {**kwargs, "pool_names": inputs.names, "volume_for_bucket": provider}
    if rate is OMITTED:
        kwargs.pop("participation_rate")
    else:
        kwargs["participation_rate"] = rate
    try:
        state = engine.simulate(inputs.minute, inputs.daily, inputs.pool, inputs.start, inputs.end, **kwargs)
    except Exception as exc:
        return {"status": "FAIL", "exception": {"type": type(exc).__name__, "message": str(exc)},
                "provider_calls": raw(provider.calls), "state": None}
    return {"status": "PASS", "exception": None, "provider_calls": raw(provider.calls),
            "state": snapshot(state)}


def differences(left, right, path=""):
    if type(left) is not type(right):
        return [path]
    if isinstance(left, dict):
        return [p for key in sorted(left.keys() | right.keys()) for p in (
            [f"{path}/{key}"] if key not in left or key not in right
            else differences(left[key], right[key], f"{path}/{key}"))]
    if isinstance(left, list):
        if len(left) != len(right):
            return [path + "/length"]
        return [p for i, (a, b) in enumerate(zip(left, right)) for p in differences(a, b, f"{path}/{i}")]
    return [] if left == right else [path]


def compare(fixture, rate=OMITTED):
    mapped = normalize(fixture["source"])
    native = native_inputs(fixture["native"])
    delta = differences(native.canonical(), mapped.canonical())
    require(not delta, "native_inputs", {"differences": delta})
    kwargs = options(fixture["parameters"])
    n, h = invoke(native, kwargs, rate), invoke(mapped, kwargs, rate)
    delta = differences(n, h)
    fills = [] if h["state"] is None else [
        [t["side"], t["shares"], t["price"], t["commission"]]
        for t in h["state"]["trades"] if t["side"] in ("BUY", "SELL")]
    oracle = {"expected": fixture["oracle"], "actual_fills": fills,
              "status": "PASS" if fills == fixture["oracle"]["fills"] else "FAIL"}
    passed = not delta and h["status"] == "PASS" and oracle["status"] == "PASS"
    return {"status": "PASS" if passed else "FAIL", "native": n, "harness": h,
            "differences": delta, "oracle": oracle, "coverage": mapped.audit,
            "canonical_hash": digest(native.canonical()),
            "parameters": {**raw({k: v for k, v in kwargs.items() if k != "volume_for_bucket"}),
                           "participation_rate": "omitted" if rate is OMITTED else rate,
                           "pool_names": mapped.names}}


def identity(path):
    data = path.read_bytes()
    stat = path.stat()
    return {"path": str(path.resolve()), "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "device": stat.st_dev, "inode": stat.st_ino, "mtime_ns": stat.st_mtime_ns}


def read_fixture(path, expected_hash):
    before = identity(path)
    require(before["sha256"] == expected_hash, "identity", {"expected": expected_hash, "actual": before})
    payload = path.read_bytes()
    after = identity(path)
    require(before == after and hashlib.sha256(payload).hexdigest() == expected_hash,
            "identity", "source changed during read")
    return json.loads(payload), before


def output_root(parent, run_id, input_root):
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_id), "output", "invalid run_id")
    require(parent.is_absolute(), "output", "explicit absolute external parent required")
    parent = parent.resolve()
    forbidden = [REPO_ROOT.resolve(), input_root.resolve()]
    forbidden.extend(Path(os.environ[k]).resolve() for k in (
        "OSKH_SOURCE_PARQUET_ROOT", "OSKH_AUTHORITY_HINT_ROOT", "OSKH_DATA_ROOT",
        "OSKH_PERIOD_1D_ROOT", "OSKH_PERIOD_1M_ROOT", "TURNOVER_RESIST_DATA_DIR",
    ) if os.environ.get(k))
    for path in forbidden:
        require(not (parent.is_relative_to(path) or path.is_relative_to(parent)),
                "output", f"external parent overlaps protected/input root {path}")
    parent.mkdir(parents=True, exist_ok=True)
    root = parent / run_id
    root.mkdir(exist_ok=False)
    return root


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True, help="synthetic source + independent native + manual oracle JSON")
    parser.add_argument("--fixture-sha256", required=True, help="pre-registered SHA-256 of the whole fixture")
    parser.add_argument("--human-go", type=Path, required=True)
    parser.add_argument("--external-parent", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--participation-rate", required=True, help="none, omitted, or explicit finite rate in [0,1]")
    args = parser.parse_args(argv)
    receipt = {"schema": "d5_ingress_v1", "run_id": args.run_id, "status": "FAIL",
               "comparison_status": "no_ssot_compare_authorization", "production_C": "frozen",
               "source_certification": "NOT_RUN", "real_lake_run": "NOT_RUN",
               "cache": "no read/write shared minute cache; no new cache",
               "matrix": {cell: {"status": "NOT_RUN"} for cell in CELLS},
               "outputs": {}, "stage": "output"}
    root = None
    try:
        root = output_root(args.external_parent, args.run_id, args.fixture.parent)
        receipt["stage"] = "identity"
        receipt["authority"] = {"contract_id": "D5-REAL-VOLUME-INGRESS-v1",
                                "contract": identity(CONTRACT), "human_go": identity(args.human_go)}
        receipt["code"] = {"sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
            "worktree_status": subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True),
            "mapping": identity(MAPPING), "harness": identity(Path(__file__)),
            "python": sys.version, "executable": sys.executable,
            "dependencies": {"numpy": np.__version__, "pandas": pd.__version__}}
        receipt["source"] = {"kind": "synthetic", "expected_sha256": args.fixture_sha256,
                             "path": str(args.fixture.resolve())}
        receipt["source"]["before"] = identity(args.fixture)
        fixture, before = read_fixture(args.fixture, args.fixture_sha256)
        receipt["stage"] = "participation_rate"
        rate = (OMITTED if args.participation_rate == "omitted" else
                None if args.participation_rate == "none" else float(args.participation_rate))
        require(rate is OMITTED or rate is None or (np.isfinite(rate) and 0 <= rate <= 1),
                "participation_rate", "expected none, omitted, or a finite rate in [0,1]")
        receipt["stage"] = "preflight_compare"
        result = compare(fixture, rate)
        receipt["source"]["after"] = identity(args.fixture)
        require(receipt["source"]["after"] == before, "identity", "source changed during run")
        receipt["stage"] = "write"
        for side in ("native", "harness"):
            (root / side).mkdir()
            write_json(root / side / "result.json", result[side])
        write_json(root / "comparison.json", result)
        cell = fixture["cell"]
        require(cell in CELLS, "schema", "unknown matrix cell")
        receipt["matrix"][cell] = {"status": result["status"], "layer": "N/H",
                                  "scope": fixture["scope"], "remaining_subcases": "NOT_RUN"}
        receipt.update(status=result["status"], stage="complete", canonical_hash=result["canonical_hash"],
                       parameters=result["parameters"], coverage=result["coverage"])
    except Exception as exc:
        receipt["failure"] = {"type": type(exc).__name__, "message": str(exc),
                              "stage": getattr(exc, "stage", receipt["stage"]),
                              "detail": getattr(exc, "detail", None)}
    if root is not None:
        receipt["outputs"] = {str(p.relative_to(root)): identity(p)
                              for p in sorted(root.rglob("*.json"))}
        receipt["output_files"] = [*receipt["outputs"], "receipt.json"]
        write_json(root / "receipt.json", receipt)  # No self-referential receipt hash.
    print(json.dumps({"status": receipt["status"], "root": str(root) if root else None,
                      "failure": receipt.get("failure")}, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
