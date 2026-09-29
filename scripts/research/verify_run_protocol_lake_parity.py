#!/usr/bin/env python3
"""B-native-CV-01: external, resolver-backed native CLI / L1 fidelity receipt.

No engine imports at module import time; the comparator is data-free. Exit 0:
all cells covered and PASS; 1: FAIL; 2: BLOCKED/NOT_RUN; 3: NOT_COVERED.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "B-native-CV-01"
NORMAL_CASH = 1_000_000_000  # Frozen ample-capital recipe; native defaults stay unchanged.
ENTRIES = {
    "csv_minute": "backtest/research/csv_minute_backtest.py",
    "v7": "backtest/research/csv_minute_backtest_v7.py",
}
REQUIRED = {
    "csv_minute": ("trades.csv", "daily_equity.csv", "summary.txt",
                   "run-manifest.json", "execution-audit.json"),
    "v7": ("trades.csv", "daily_equity.csv", "summary.txt",
           "run-config.json", "execution-audit.json"),
}
# Only numeric duration captures may differ. Every surrounding byte must match.
DURATION_LINES = (
    r"  耗时: 池 (?P<pool>\d+\.\d+)s \| 日线 (?P<daily>\d+\.\d+)s \| 分钟 (?P<minute>\d+\.\d+)s \| 模拟 (?P<sim>\d+\.\d+)s(?: \| 缓存 [^\r\n]+)?\n?",
    r"loaded minute=lake daily=lake: minute_names=\d+ daily_names=\d+ exdiv_names=\d+ st_names=\d+ in (?P<load>\d+\.\d+)s\n?",
    r"timing load=(?P<load>\d+\.\d+)s simulate=(?P<sim>\d+\.\d+)s total=(?P<total>\d+\.\d+)s\n?",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def write_json(path: Path, value) -> None:
    # Receipts are append-only files, never overwritten or re-recorded goldens.
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


@dataclass(frozen=True)
class Observation:
    root: Path
    exit_code: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class ComparePolicy:
    required_files: tuple[str, ...] = ()
    # Explicit filename + JSON pointer; no wildcard economic-field exclusions.
    allowed_json_fields: tuple[tuple[str, str], ...] = ()
    duration_files: tuple[str, ...] = ()
    duration_stdout: bool = False
    verify_manifest: bool = False


def tree(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file()}


def compare_observations(left: Observation, right: Observation,
                         policy: ComparePolicy = ComparePolicy()) -> dict:
    """Compare all files and raw streams; retain every allowed difference.

    Raw-byte differences always fail, including JSON/CSV serialization changes,
    even when parsed differences are explicitly allowed. No float tolerance,
    row sorting, path substitution, timestamp wildcard, or byte-identity claim.
    """
    differences, raw = [], {}

    def diff(path, a, b, allowed=False, reason="exact comparison"):
        differences.append({"path": path, "left": a, "right": b,
                            "allowed": allowed, "reason": reason})

    def walk(a, b, filename, pointer="", allowed_fields=()):
        if type(a) is not type(b):
            diff(filename + pointer, a, b)
        elif isinstance(a, dict):
            for key in sorted(a.keys() | b.keys()):
                part = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
                if key not in a or key not in b:
                    diff(filename + part, a.get(key), b.get(key))
                else:
                    walk(a[key], b[key], filename, part, allowed_fields)
        elif isinstance(a, list):
            if len(a) != len(b):
                diff(filename + pointer + "/length", len(a), len(b))
            for i, (av, bv) in enumerate(zip(a, b)):
                walk(av, bv, filename, pointer + f"/{i}", allowed_fields)
        elif a != b:
            allowed = (filename, pointer) in allowed_fields
            diff(filename + pointer, a, b, allowed, "predeclared non-economic field" if allowed else "exact comparison")

    def text_compare(a, b, name, duration):
        aa, bb = a.splitlines(keepends=True), b.splitlines(keepends=True)
        if len(aa) != len(bb):
            diff(name + "/lines", len(aa), len(bb))
        for i, (av, bv) in enumerate(zip(aa, bb)):
            if av == bv:
                continue
            allowed = False
            if duration:
                for pattern in DURATION_LINES:
                    am, bm = re.fullmatch(pattern, av), re.fullmatch(pattern, bv)
                    if am and bm:
                        def skeleton(match):
                            value = match.string
                            for start, end in sorted((match.span(k) for k in match.groupdict()), reverse=True):
                                value = value[:start] + "<duration>" + value[end:]
                            return value
                        allowed = skeleton(am) == skeleton(bm)
                        if allowed:
                            break
            diff(f"{name}/line/{i + 1}", av, bv, allowed,
                 "duration numeric captures only" if allowed else "exact comparison")

    if left.exit_code != right.exit_code:
        diff("exit_code", left.exit_code, right.exit_code)
    lt, rt = tree(left.root), tree(right.root)
    for name in sorted(set(lt) | set(rt) | set(policy.required_files)):
        if name not in lt or name not in rt:
            diff("files/" + name, name in lt, name in rt, reason="missing required file or unequal file set")
    allowed_fields = set(policy.allowed_json_fields)
    # The native manifest hashes summary.txt, which contains measured durations.
    # Permit only its derived digests, and only after checking each digest against
    # its own raw file and comparing that file with the declared duration policy.
    if policy.verify_manifest:
        for side, files in (("left", lt), ("right", rt)):
            try:
                manifest = json.loads(files["run-manifest.json"].read_bytes())
                for i, row in enumerate(manifest["artifacts"]):
                    name = Path(row["path"]).name
                    if row["path"] != "artifacts/" + name or name not in files:
                        raise ValueError(f"unexpected manifest artifact {row['path']}")
                    data = files[name].read_bytes()
                    for algo in ("md5", "sha256"):
                        actual = hashlib.new(algo, data).hexdigest()
                        if row[algo] != actual:
                            diff(f"{side}/run-manifest.json/artifacts/{i}/{algo}", row[algo], actual)
                        if name == "summary.txt" and name in policy.duration_files:
                            allowed_fields.add(("run-manifest.json", f"/artifacts/{i}/{algo}"))
            except (KeyError, ValueError, TypeError) as exc:
                diff(side + "/run-manifest.json/integrity", str(exc), "valid native manifest")

    pairs = [(name, lt[name].read_bytes(), rt[name].read_bytes()) for name in sorted(lt.keys() & rt.keys())]
    pairs += [("stdout", left.stdout, right.stdout), ("stderr", left.stderr, right.stderr)]
    for name, a, b in pairs:
        raw[name] = {"left_sha256": digest(a), "right_sha256": digest(b), "byte_equal": a == b}
        if a == b:
            continue
        try:
            if name.endswith(".json"):
                walk(json.loads(a), json.loads(b), name, allowed_fields=allowed_fields)
            elif name.endswith(".csv"):
                # DictReader keeps row order and field values as exact strings.
                ar, br = csv.DictReader(io.StringIO(a.decode("utf-8-sig"))), csv.DictReader(io.StringIO(b.decode("utf-8-sig")))
                walk(ar.fieldnames, br.fieldnames, name, "/columns")
                walk(list(ar), list(br), name, "/rows")
            else:
                text_compare(a.decode("utf-8"), b.decode("utf-8"), name,
                             name in policy.duration_files or (name == "stdout" and policy.duration_stdout))
        except (UnicodeError, ValueError, csv.Error):
            pass
        diff(name + "/bytes", digest(a), digest(b), reason="raw bytes differ")
    failed = any(not item["allowed"] for item in differences)
    return {"status": "FAIL" if failed else "PASS", "differences": differences,
            "raw": raw, "byte_identical": not differences and set(lt) == set(rt),
            "policy": policy.__dict__}


def resolve_roots() -> dict:
    from common.infra.data_root import resolve_index_daily_root, resolve_period_root, resolve_source_parquet

    roots = {}
    for name, resolver in (
        ("minute", lambda: resolve_period_root("1m")),
        ("daily", lambda: resolve_period_root("1d")),
        ("index", resolve_index_daily_root),
        ("adj_factor", lambda: resolve_source_parquet("adj_factor.parquet")),
        ("ex_date_index", lambda: resolve_source_parquet("ex_date_index.parquet")),
    ):
        try:
            path = resolver().resolve()
            roots[name] = {"path": str(path), "exists": path.exists()}
            if not path.exists():
                roots[name]["error"] = f"FileNotFoundError: {path}"
        except (RuntimeError, OSError, ValueError, ImportError) as exc:
            roots[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return roots


def pool_identity(pool: Path, start: str, end: str) -> dict:
    from backtest.research.csv_pool import parse_pool_csv

    files = [p for p in sorted(pool.glob("*.csv"))
             if re.fullmatch(r"\d{8}", p.stem) and start <= p.stem <= end]
    rows = [{"path": str(p), "sha256": file_digest(p), "symbols": parse_pool_csv(p)} for p in files]
    if not rows or not any(row["symbols"] for row in rows):
        raise ValueError(f"no nonempty existing YYYYMMDD.csv pool in {pool} [{start}, {end}]")
    return {"path": str(pool), "files": rows,
            "symbols": sorted({symbol for row in rows for symbol in row["symbols"]})}


def source_identity(roots: dict, pool: dict, start: str, end: str) -> dict:
    """Hash whole native source partitions (including warmup), not invented bars."""
    from oskh_data.symbol_format import to_partition_key

    errors = [row["error"] for row in roots.values() if "error" in row]
    if errors:
        return {"errors": errors, "files": [], "calendar": None}
    files = []
    for key in ("minute", "daily"):
        for symbol in pool["symbols"]:
            files.append(Path(roots[key]["path"]) / "dividend_type=none" / f"symbol={to_partition_key(symbol)}" / "data.parquet")
    index_dir = Path(roots["index"]["path"]) / "dividend_type=none" / "symbol=000001_SH"
    index_files = sorted(index_dir.glob("*.parquet"))
    if not index_files:
        errors.append(f"FileNotFoundError: missing index daily partition: {index_dir}")
    files += index_files + [Path(roots[key]["path"]) for key in ("adj_factor", "ex_date_index")]
    identities = []
    for path in sorted(set(files)):
        if not path.is_file():
            errors.append(f"FileNotFoundError: {path}")
        else:
            identities.append({"path": str(path), "sha256": file_digest(path), "size": path.stat().st_size})
    calendar = None
    if not errors:
        try:
            # Existing native read-only calendar validator, no synthetic sessions.
            from backtest.research.csv_minute_backtest_v7 import load_index_daily
            dates = load_index_daily(datetime.strptime(start, "%Y%m%d").date(),
                                     datetime.strptime(end, "%Y%m%d").date())
            calendar = [day.isoformat() for day in sorted(dates)]
        except (RuntimeError, OSError, ValueError, ImportError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    return {"errors": errors, "files": identities, "calendar": calendar,
            "calendar_scope": "native SSE index preload + window; no fabricated holidays"}


def input_identity(pool_path: Path, start: str, end: str) -> dict:
    roots = resolve_roots()
    try:
        pool = pool_identity(pool_path, start, end)
    except (OSError, ValueError) as exc:
        return {"roots": roots, "pool": {"path": str(pool_path)},
                "sources": {"errors": [f"{type(exc).__name__}: {exc}"]
                            + [row["error"] for row in roots.values() if "error" in row]}}
    # CSV summary may read existing daily-run equity. Pin the candidate set too.
    baseline = [{"path": str(p), "sha256": file_digest(p)} for p in sorted(
        (ROOT / "backtest_output").glob(f"csv_daily_v8_{start}_*/daily_equity.csv"))]
    from common.infra.data_root import find_authority_marker

    configs = [ROOT / "config/runtime.local.yaml"]
    configs += [Path(p).resolve() for p in os.environ.get("MINIQMT_CONFIG_PATH", "").split(os.pathsep) if p]
    marker = find_authority_marker()
    if marker is not None:
        configs.append(marker.resolve())
    config_identity = [{"path": str(p), "sha256": file_digest(p) if p.is_file() else None}
                       for p in sorted(set(configs))]
    return {"roots": roots, "pool": pool, "sources": source_identity(roots, pool, start, end),
            "runtime_config_and_authority": config_identity, "csv_daily_comparison_candidates": baseline}


def native_argv(family: str, cell: str, pool: Path, start: str, end: str) -> list[str]:
    if cell == "invalid_config":
        return ["--start", start, "--end", end, "--minute-source", "B_NATIVE_INVALID"]
    args = ["--start", start, "--end", end, "--pool-dir", str(pool),
            "--minute-source", "lake", "--daily-source", "lake",
            "--cash-total", "1" if cell == "low_cash" else str(NORMAL_CASH),
            "--execution-audit-file", "artifacts/execution-audit.json"]
    if family == "csv_minute":
        args += ["--strategy", "version8", "--out-dir", "artifacts", "--no-cache",
                 "--workers", "1", "--dividend-type", "none", "--name-budget", "1000000",
                 "--daily-quota", "1000000", "--ration", "file_order", "--ration-seed", "0",
                 "--minute-stop-trigger", "close", "--emit-run-manifest"]
    else:
        args += ["--output-dir", "artifacts"]
    return args


L1_WORKER = """import json, pathlib, sys
from backtest.research.run_protocol import CliContext, NativeCliRequest, run
request = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
result = run(NativeCliRequest(family=request['family'], native_entry=request['entry'],
    argv=request['argv'], context=CliContext(cwd=request['cwd'])))
pathlib.Path('native-exit.json').write_text(json.dumps(result.native_exit_status), encoding='utf-8')
sys.stdout.buffer.write(result.stdout_bytes)
sys.stderr.buffer.write(result.stderr_bytes)
"""


def launch(side: str, family: str, argv: list[str], cwd: Path, interpreter: Path,
           env: dict, bad_output: bool) -> Observation:
    cwd.mkdir()
    if bad_output:
        (cwd / "artifacts").write_bytes(b"B-native-CV-01 refusal sentinel\n")
    request = {"family": family, "entry": ENTRIES[family], "argv": argv, "cwd": str(cwd)}
    write_json(cwd / "request.json", request)
    command = ([str(interpreter), str(ROOT / ENTRIES[family]), *argv] if side == "direct" else
               [str(interpreter), "-c", L1_WORKER, str(cwd / "request.json")])
    process = subprocess.run(command, cwd=cwd, env=env, capture_output=True, check=False)
    (cwd / "stdout.bin").write_bytes(process.stdout)
    (cwd / "stderr.bin").write_bytes(process.stderr)
    if side == "l1":
        if process.returncode != 0 or not (cwd / "native-exit.json").is_file():
            raise RuntimeError(f"L1 transport worker failed ({process.returncode}); see {cwd}/stderr.bin")
        status = json.loads((cwd / "native-exit.json").read_bytes())
    else:
        status = process.returncode
        write_json(cwd / "native-exit.json", status)
    if bad_output and (cwd / "artifacts").read_bytes() != b"B-native-CV-01 refusal sentinel\n":
        raise RuntimeError("native refusal changed the sentinel")
    return Observation(cwd / "artifacts", status, process.stdout, process.stderr)


def cell_verdict(family: str, cell: str, observations: list[Observation], comparison: dict) -> tuple[str, str]:
    if comparison["status"] == "FAIL":
        return "FAIL", "native / L1 mismatch; see comparison field paths"
    for observed in observations:
        if cell == "invalid_config":
            if observed.exit_code != 2 or b"invalid choice: 'B_NATIVE_INVALID'" not in observed.stderr:
                return "FAIL", "expected native argparse invalid-choice refusal was not observed"
        elif cell == "bad_output":
            marker = b"NotADirectoryError" if family == "csv_minute" else b"FileExistsError"
            if observed.exit_code == 0 or marker not in observed.stderr or b"artifacts" not in observed.stderr:
                return "FAIL", "expected native output-file refusal was not observed"
        elif cell == "low_cash" and family == "csv_minute":
            if observed.exit_code != 0:
                if not re.search(rb"(?:^|\n)(?:[\w.]+\.)?InsufficientCashError:.*date=.*code=", observed.stderr):
                    return "FAIL", "nonzero exit was not the native InsufficientCashError path"
            else:
                return "NOT_COVERED", "未覆盖: real InsufficientCashError did not trigger"
        elif observed.exit_code != 0:
            return "FAIL", "unexpected native nonzero exit"
        else:
            with (observed.root / "trades.csv").open(encoding="utf-8-sig", newline="") as handle:
                trades = list(csv.DictReader(handle))
            if cell == "low_cash":
                if not any(row.get("reason") == "skip_cash" and row.get("side") == "skip" for row in trades):
                    return "NOT_COVERED", "未覆盖: real v7 skip_cash did not trigger"
            else:
                sides = {row.get("side", "").lower() for row in trades if float(row.get("shares", 0)) > 0}
                with (observed.root / "daily_equity.csv").open(encoding="utf-8-sig", newline="") as handle:
                    equity = list(csv.DictReader(handle))
                audit = json.loads((observed.root / "execution-audit.json").read_bytes())
                if not {"buy", "sell"} <= sides or len(equity) < 2 or not audit["events"]:
                    return "NOT_COVERED", "未覆盖: need actual buys AND sells, >=2 equity rows and native audit events"
    return "PASS", "native fidelity and the named cell trigger both verified"


def aggregate_status(cells: list[dict]) -> tuple[str, int]:
    statuses = {cell["status"] for cell in cells}
    for status, code in (("FAIL", 1), ("BLOCKED", 2), ("NOT_RUN", 2), ("NOT_COVERED", 3)):
        if status in statuses:
            return status, code
    return "PASS", 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, help="new directory under a handoff or temp; must not exist")
    parser.add_argument("--start", default="20251023", help="native documented start, validated against existing pool files")
    parser.add_argument("--end", default="20251104", help="native CLI documented short-window end")
    parser.add_argument("--csv-pool-dir", type=Path, default=ROOT / "stock_pool")
    parser.add_argument("--v7-pool-dir", type=Path, default=ROOT / "stock_pool",
                        help="existing named lists; passed explicitly to v7, never its environment fallback")
    args = parser.parse_args(argv)
    for value in (args.start, args.end):
        if not re.fullmatch(r"\d{8}", value):
            parser.error("dates must be YYYYMMDD")
        datetime.strptime(value, "%Y%m%d")
    if args.end < args.start:
        parser.error("end precedes start")
    sys.path.insert(0, str(ROOT))
    from scripts._script_bootstrap import resolve_oskh_python

    interpreter = resolve_oskh_python().absolute()  # Preserve venv symlink identity.
    if interpreter != Path(sys.executable).absolute():
        parser.error("launch this harness with the same interpreter selected by resolve_oskh_python")
    out = args.output_root.absolute() if args.output_root else Path(tempfile.mkdtemp(prefix=EXPERIMENT + "-")) / "receipt"
    protected = [ROOT, args.csv_pool_dir.resolve(), args.v7_pool_dir.resolve()]
    for row in resolve_roots().values():
        if "path" in row:
            path = Path(row["path"])
            protected.append(path if path.is_dir() else path.parent)
    if any(out.resolve().is_relative_to(path) for path in protected):
        parser.error("output root must be outside the repository, input pools and resolver source roots")
    out.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "OSKH_MERGE_PYTHON": str(interpreter), "OSKH_TURTLE_POOL_DIR": "",
           "PYTHONPATH": str(ROOT), "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
           "NUMBA_CACHE_DIR": str(out / "numba-cache"), "TZ": "Asia/Shanghai"}
    pools = {"csv_minute": args.csv_pool_dir.resolve(), "v7": args.v7_pool_dir.resolve()}
    identities = {family: input_identity(pool, args.start, args.end) for family, pool in pools.items()}
    # Relative source settings must not change meaning in the isolated child cwd.
    roots = identities["csv_minute"].get("roots", {})
    for key, name in (("OSKH_PERIOD_1M_ROOT", "minute"), ("OSKH_PERIOD_1D_ROOT", "daily"),
                      ("OSKH_INDEX_DAILY_ROOT", "index")):
        if "path" in roots.get(name, {}):
            env[key] = roots[name]["path"]
    if "path" in roots.get("adj_factor", {}):
        env["OSKH_SOURCE_PARQUET_ROOT"] = str(Path(roots["adj_factor"]["path"]).parent)
    for key in ("OSKH_AUTHORITY_HINT_ROOT", "MINIQMT_CONFIG_PATH"):
        if env.get(key):
            env[key] = os.pathsep.join(str(Path(p).resolve()) for p in env[key].split(os.pathsep) if p)
    if env.get("OSKH_DATA_ROOT"):
        env["OSKH_DATA_ROOT"] = str(Path(env["OSKH_DATA_ROOT"]).resolve())
    cells = [{"family": family, "cell": cell,
              "argv": native_argv(family, cell, pools[family], args.start, args.end),
              "cwd": {side: str(out / f"{family}-{cell}" / side) for side in ("direct", "l1")}}
             for family in ENTRIES for cell in ("normal", "low_cash", "invalid_config", "bad_output")]
    git = lambda *tokens: subprocess.check_output(["git", *tokens], cwd=ROOT, text=True).strip()
    # Selected-interpreter environment identity: versions, no secret environment values.
    runtime = subprocess.check_output([str(interpreter), "-c",
        "import importlib.metadata as m,json,sys; print(json.dumps({'version':sys.version,'packages':sorted((d.metadata['Name'],d.version) for d in m.distributions())}))"], env=env)
    receipt = {
        "experiment": EXPERIMENT, "registered_utc": datetime.now(timezone.utc).isoformat(),
        "code_sha": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
        "worktree_status": git("status", "--porcelain"), "harness_sha256": file_digest(Path(__file__)),
        "tracked_diff_sha256": digest(git("diff", "HEAD", "--").encode()),
        "interpreter": {"path": str(interpreter), "path_sha256": digest(str(interpreter).encode()),
                        "binary_sha256": file_digest(interpreter), "runtime": json.loads(runtime)},
        "environment_sha256": digest(canonical(env)),
        "environment_public": {key: env.get(key) for key in (
            "OSKH_DATA_ROOT", "OSKH_SOURCE_PARQUET_ROOT", "OSKH_AUTHORITY_HINT_ROOT",
            "OSKH_PERIOD_1M_ROOT", "OSKH_PERIOD_1D_ROOT", "OSKH_INDEX_DAILY_ROOT",
            "OSKH_MERGE_PYTHON", "OSKH_TURTLE_POOL_DIR", "PYTHONPATH", "PYTHONHASHSEED",
            "PYTHONDONTWRITEBYTECODE", "NUMBA_CACHE_DIR", "TZ", "MINIQMT_CONFIG_PATH")},
        "window": {"start": args.start, "end": args.end, "origin": "native CLI documented defaults / explicit harness arguments"},
        "load_windows": {"csv_minute": "minute/daily: start minus native WARMUP_DAYS=10 calendar days through end",
                         "v7": "minute: start..end; daily: start minus native DAILY_PRELOAD_DAYS=40 through end",
                         "index": "native requested window plus 11 preceding sessions; files hashed in full"},
        "inputs": identities, "cells": cells, "output_root": str(out),
        "economic_flags": {"normal_cash": NORMAL_CASH, "low_cash": 1, "name_budget": 1000000,
                           "fee": "BILATERAL_10BP: buy=sell=0.001, floor=0",
                           "price_domain": "lake minute/daily none; native exdiv context",
                           "strategy": {"csv_minute": "version8", "v7": "native strategy7"},
                           "other_flags": "native pinned code defaults; no X-02/X-04 or production changes"},
        "cache": "CSV --no-cache; v7 native bars_from_pool use_cache=False; fresh processes; shared isolated numba code cache only",
        "compare_policy": {"duration_lines": DURATION_LINES, "duration_files": ["summary.txt"],
                           "stdout": "exact except listed duration captures", "stderr": "exact bytes",
                           "json": "exact ordered arrays and field values; no path/timestamp exclusions",
                           "manifest": "validate raw own-file hashes; allow summary duration-derived hashes only",
                           "required_success_files": REQUIRED,
                           "positions_phases": "native trade position IDs, audit phases/cash/fees and v7 holdings; no unexposed state fabricated"},
        "authority": "native-to-L1 fidelity only; no SSOT R/S, L2 lake, cross-family equality or production_C change",
    }
    write_json(out / "recipe.json", receipt)  # Must precede even data-free refusal runs.
    recipe_hash = file_digest(out / "recipe.json")

    def check_code_identity():
        if (git("rev-parse", "HEAD") != receipt["code_sha"]
                or digest(git("diff", "HEAD", "--").encode()) != receipt["tracked_diff_sha256"]
                or file_digest(Path(__file__)) != receipt["harness_sha256"]):
            raise RuntimeError("code identity drift after preregistration")

    results = []
    for cell in cells:
        family, name = cell["family"], cell["cell"]
        result = {**cell, "recipe_sha256": recipe_hash}
        errors = list(dict.fromkeys(identities[family]["sources"]["errors"]))
        if name != "invalid_config" and errors:
            result.update(status="NOT_RUN", reason="BLOCKED: " + " | ".join(errors))
        else:
            directory = out / f"{family}-{name}"
            directory.mkdir()
            try:
                observations = []
                for side in ("direct", "l1"):
                    check_code_identity()
                    if name != "invalid_config" and input_identity(pools[family], args.start, args.end) != identities[family]:
                        raise RuntimeError("input identity drift before " + side)
                    observations.append(launch(side, family, cell["argv"], Path(cell["cwd"][side]),
                                               interpreter, env, name == "bad_output"))
                    check_code_identity()
                    if name != "invalid_config" and input_identity(pools[family], args.start, args.end) != identities[family]:
                        raise RuntimeError("input identity drift after " + side)
                require = REQUIRED[family] if name in ("normal", "low_cash") and all(o.exit_code == 0 for o in observations) else ()
                policy = ComparePolicy(required_files=require, duration_files=("summary.txt",),
                                       duration_stdout=True, verify_manifest="run-manifest.json" in require)
                comparison = compare_observations(*observations, policy)
                write_json(directory / "comparison.json", comparison)
                status, reason = cell_verdict(family, name, observations, comparison)
                result.update(status=status, reason=reason, native_exit_codes=[o.exit_code for o in observations],
                              comparison=str(directory / "comparison.json"), byte_identical=comparison["byte_identical"])
            except Exception as exc:
                result.update(status="FAIL", reason=f"{type(exc).__name__}: {exc}")
        results.append(result)
        write_json(out / f"{family}-{name}.json", result)
        print(f"{family} / {name}: {result['status']} — {result['reason']}", flush=True)
    status, code = aggregate_status(results)
    if status == "NOT_RUN":
        status = "BLOCKED"
    write_json(out / "result.json", {"experiment": EXPERIMENT, "recipe_sha256": recipe_hash,
                                     "status": status, "exit_code": code, "cells": results})
    print(f"{EXPERIMENT}: {status} (exit {code}); receipt: {out}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
