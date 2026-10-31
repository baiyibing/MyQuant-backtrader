#!/usr/bin/env python3
"""Wind/Kimi export or frozen Hithink import; prepare candidates, never apply.

Human GO 2026-10-24 is limited to this export workflow. See
docs/operations/corp-actions-incremental-driver.md for the 4090 runbook.
Human GO 2026-10-30 adds artifact-only Hithink intake from the 1.3 producer.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.infra.data_root import (  # noqa: E402
    UnconfiguredDataRootError,
    resolve_parquet_container,
    resolve_source_parquet,
)

MODELS = ("kimi-code/kimi-for-coding-highspeed", "kimi-code/kimi-for-coding", "kimi-code/k3")
BASE_FILES = ("manifest.json", "events.parquet", "listing.parquet", "failures.parquet")
EVENT_COLS = (
    "code", "event_id", "ex_date", "record_date", "pay_date",
    "cash_div_per_share", "bonus_ratio", "transfer_ratio", "bonus_list_date", "source",
)
DATES = ("ex_date", "record_date", "pay_date", "bonus_list_date")
NUMBERS = ("cash_div_per_share", "bonus_ratio", "transfer_ratio")
WIND_FIELDS = {
    "ex_date": "除权除息日", "record_date": "股权登记日", "pay_date": "派息日",
    "cash_div_per_share": "税前每股派息", "bonus_ratio": "送股比例",
    "transfer_ratio": "转增比例", "bonus_list_date": "红股上市日", "progress": "实施进度",
}
EVENT_SCHEMA = pa.schema([
    (key, pa.date32() if key in DATES else
     pa.decimal128(24, 12) if key in NUMBERS else pa.string())
    for key in EVENT_COLS
])
CST = timezone(timedelta(hours=8))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def iso_day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"expected YYYY-MM-DD, got {value!r}")
    return date.fromisoformat(value)


def wind_code(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{6}\.(SZ|SH|BJ)", value):
        raise ValueError(f"invalid Wind code: {value!r}")
    return value


def decimal_value(value):
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"bad decimal: {value!r}") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"non-finite or negative decimal: {value!r}")
    # Arrow checks precision/scale without rounding; preserve unknown versus zero.
    pa.scalar(number, type=pa.decimal128(24, 12))
    return number


def csv_rows(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    if "\x00" in text:
        raise ValueError(f"NUL in {path}")
    rows = list(csv.reader(io.StringIO(text), strict=True))
    if not rows or len(set(rows[0])) != len(rows[0]):
        raise ValueError(f"empty/duplicate CSV header: {path}")
    if any(len(row) != len(rows[0]) for row in rows[1:]):
        raise ValueError(f"ragged CSV: {path}")
    return rows[0], rows[1:]


def read_universe(path):
    if path.suffix.lower() == ".parquet":
        codes = pq.read_table(path, columns=["code"])["code"].to_pylist()
    elif path.suffix.lower() == ".csv":
        header, rows = csv_rows(path)
        codes = [row[header.index("code")] for row in rows]
    else:
        codes = path.read_text(encoding="utf-8-sig").splitlines()
    codes = sorted({wind_code(c.strip()) for c in codes if c and c.strip()})
    if not codes:
        raise ValueError("empty universe")
    return codes


def disjoint(a, b):
    return not (a.is_relative_to(b) or b.is_relative_to(a))


def protected_roots(lake, universe):
    roots = {lake.resolve(), universe.parent.resolve()}
    if os.environ.get("OSKH_SOURCE_PARQUET_ROOT") or os.environ.get("OSKH_AUTHORITY_HINT_ROOT"):
        roots.add(resolve_parquet_container().resolve())
    return sorted(str(p) for p in roots)


class Run:
    def __init__(self, out):
        self.out = Path(out).resolve()
        self.config = read_json(self.out / "run.json")
        if self.config["out_dir"] != str(self.out):
            raise ValueError("run directory moved; frozen paths must not change")
        self.channel = self.config.get("channel", "wind")
        if self.channel not in ("wind", "hithink"):
            raise ValueError("unknown frozen channel")
        if self.channel == "wind" and self.config["model"] not in MODELS:
            raise ValueError("only the two approved inexpensive Kimi aliases are allowed")
        if self.channel == "hithink" and self.config.get("model") is not None:
            raise ValueError("hithink cannot specify a model")
        self.path("run.json")

    def path(self, relative):
        path = (self.out / relative).resolve()
        roots = set(self.config["protected_roots"])
        # Also honor a configured lake container introduced after init.
        if os.environ.get("OSKH_SOURCE_PARQUET_ROOT") or os.environ.get("OSKH_AUTHORITY_HINT_ROOT"):
            roots.add(str(resolve_parquet_container().resolve()))
        if not path.is_relative_to(self.out) or any(
            not disjoint(self.out, Path(root).resolve()) for root in roots
        ):
            raise ValueError("output overlaps a protected input/lake or escapes out-dir")
        return path

    def write(self, relative, content):
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path(str(Path(relative).parent / (".tmp-" + uuid.uuid4().hex)))
        with temp.open("xb") as stream:
            stream.write(content)
        temp.replace(path)

    def save(self, state):
        self.write("work/tasks.json", json_bytes(state))

    def state(self):
        return read_json(self.path("work/tasks.json"))

    def verify_base(self):
        for name, expected in self.config["base_sha256"].items():
            if digest(Path(self.config["lake_dir"]) / name) != expected:
                raise ValueError(f"base lake changed: {name}; create a new run against the new base")
        if digest(self.config["universe_path"]) != self.config["universe_sha256"]:
            raise ValueError("universe input changed since init")

    @contextmanager
    def locked(self):
        path = self.path("work/runner.lock")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(str(os.getpid()) + "\n")
        try:
            yield
        finally:
            path.unlink()


def initialize(args):
    channel = getattr(args, "channel", None) or "wind"
    if channel == "hithink" and args.model is not None:
        raise ValueError("--model is not applicable to hithink")
    exclusions = None
    if channel == "hithink":
        exclusions = read_json(Path(args.exclusions) if getattr(args, "exclusions", None) else
                               Path(__file__).resolve().parents[2] / "config/corp_actions_hithink_exclusions.json")
        if exclusions.get("format_version") != 1 or not isinstance(exclusions.get("manual_overrides"), list):
            raise ValueError("invalid hithink exclusions config")
    elif getattr(args, "exclusions", None):
        raise ValueError("--exclusions is only applicable to hithink")
    lake = (Path(args.lake_dir) if args.lake_dir else resolve_source_parquet("corp_actions")).resolve()
    universe = (Path(args.universe) if args.universe else lake / "listing.parquet").resolve()
    out = Path(args.out_dir).resolve()
    roots = protected_roots(lake, universe)
    if any(not disjoint(out, Path(root)) for root in roots):
        raise ValueError("out-dir must be separate from lake, configured container and prior inputs")
    if out.exists() and any(out.iterdir()):
        raise ValueError("init requires a new/empty out-dir; use pending/pull to resume")
    hashes = {name: digest(lake / name) for name in BASE_FILES}
    manifest = read_json(lake / "manifest.json")
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported base manifest schema_version")
    ask_end = iso_day(manifest["coverage_window"]["ask_end"])
    if ask_end < date(2026, 10, 6):
        raise ValueError("base predates completed full pull; refusing historical re-pull")
    start = iso_day(args.start) if args.start else ask_end + timedelta(days=1)
    end = iso_day(args.end) if args.end else datetime.now(CST).date()
    if start != ask_end + timedelta(days=1) or end < start or end > datetime.now(CST).date():
        raise ValueError("window must start the day after ask_end and end between start and today CST")
    codes = read_universe(universe)
    config = {
        "format_version": 1, "out_dir": str(out), "lake_dir": str(lake),
        "base_revision": manifest["revision"], "base_snapshot": manifest["snapshot"],
        "base_ask_end": str(ask_end), "base_sha256": hashes,
        "start": str(start), "end": str(end), "model": args.model, "channel": channel,
        "universe_path": str(universe), "universe_sha256": digest(universe),
        "codes": codes, "protected_roots": roots,
        "lake_write_authorized": False,
    }
    out.mkdir(parents=True, exist_ok=True)
    # Exclusive create: never replace an existing run identity.
    with (out / "run.json").open("xb") as stream:
        stream.write(json_bytes(config))
    run = Run(out)
    run.save({"tasks": [
        {"id": f"ev_{i // 6:04d}", "codes": codes[i:i + 6], "status": "pending", "attempts": []}
        for i in (range(0, len(codes), 6) if channel == "wind" else [])
    ]})
    run.write("universe.txt", ("\n".join(codes) + "\n").encode("utf-8"))
    if exclusions is not None:
        run.write("hithink_exclusions.json", json_bytes(exclusions))
    return run


def question(config, codes):
    def cn(day):
        d = iso_day(day)
        return f"{d.year}年{d.month}月{d.day}日"
    return (f"{','.join(codes)} {cn(config['start'])}至{cn(config['end'])} "
            "分红送配 实施进度 除权除息日 股权登记日 派息日 税前每股派息 送股比例 转增比例 红股上市日")


def prompt_for(run, tasks):
    calls = []
    for task in tasks:
        params = {"question": question(run.config, task["codes"]), "file_path": str(run.path(task["raw"]))}
        calls.append(f"[{task['id']}] api_name=wind_get_stock_events params={json.dumps(params, ensure_ascii=False)}")
    return """只读增量取数，只用 kimi-datasource 的 wind 数据源。先 get_data_source_desc(name="wind") 一次，
然后对以下列表逐个 call_data_source_tool(data_source_name="wind")。参数原样照抄；不扩大日期，
不合并/拆分、不重试。只通过指定 file_path 写原始CSV。不要用shell，不读写其他文件，不访问湖，
不用CNINFO/其他来源。遇额度耗尽或鉴权/限流错误立即停止余下调用。
全部或中断后，最后输出一行 RESULT_JSON: [{"id":"列表id","status":"ok或error", "rows":返回行数或null,
"error":"失败的供应商原文，否则空串"}, ...]。无数据也必须保留原错误，不推测无事件。
""" + "\n".join(calls)


def quota_hit(text):
    lower = text.lower()
    return any(s in lower for s in ("usage limit", "auth_error", "quota_exceeded", "rate limit exceeded", "too many requests")) or bool(
        re.search(r"\bhttp(?:/[\d.]+)?\s+(403|429)\b|"
                  r"\b(403|429)\b.{0,60}(quota|usage|auth|rate.limit)", lower)
    ) or any(
        # Kimi may echo stop policies (stop…if|on + gloss) or negate them in quotes (not "quota exhausted…").
        not (
            re.search(r"\bstop\b(?:[ \t]+\w+){0,6}[ \t]+(?:if|on)\b[^\n]{0,80}\Z", lower[:match.start()])
            or re.search(r"(?:\bnot|n't)[ \t]*[\"']\Z", lower[:match.start()])
        )
        for match in re.finditer(r"\bquota.{0,40}(exceeded|exhausted|reached)", lower)
    )


def result_entries(stdout):
    # Do not parse stderr thinking/prompt echoes as successful evidence.
    entries = None
    for match in re.finditer(r"RESULT_JSON:\s*", stdout):
        try:
            parsed, _ = json.JSONDecoder().raw_decode(stdout[match.end():])
            if isinstance(parsed, list):
                entries = parsed
        except ValueError:
            continue
    if entries is None or any(not isinstance(x, dict) or "id" not in x for x in entries):
        raise ValueError("missing/malformed RESULT_JSON")
    if len({x["id"] for x in entries}) != len(entries):
        raise ValueError("duplicate RESULT_JSON ids")
    return {x["id"]: x for x in entries}


def raw_events(path, requested):
    header, rows = csv_rows(path)
    indices = {}
    for key, suffix in WIND_FIELDS.items():
        matches = [i for i, name in enumerate(header) if name.endswith(suffix)]
        if len(matches) != 1:
            raise ValueError(f"missing/ambiguous Wind column {suffix}")
        indices[key] = matches[0]
    if header[0] not in ("Wind代码", "证券代码", "code"):
        raise ValueError("unrecognized Wind code column")
    result = []
    for row in rows:
        code = wind_code(row[0])
        if code not in requested:
            raise ValueError(f"unrequested code in raw response: {code}")
        item = {key: row[i].strip() for key, i in indices.items()}
        item["code"] = code
        result.append(item)
    return result


def split_task(task, state, codes):
    task["status"] = "split"
    for code in codes:
        state["tasks"].append({"id": task["id"] + "_" + code, "codes": [code],
                               "status": "pending", "attempts": []})


def skipped_entry(entry):
    # Stop-policy skip (e.g. after an auth error): the model never made the
    # vendor call, so the entry carries no vendor detail and must not count
    # as a bounded vendor attempt.
    if not isinstance(entry, dict) or entry.get("status") != "error":
        return False
    error = str(entry.get("error", "")).strip()
    return not error or error.lower().startswith("skipped")


def accept_result(run, task, entry, state):
    if not entry or entry.get("status") not in ("ok", "error"):
        raise ValueError("missing/invalid task result")
    if entry["status"] == "error":
        # Only singleton vendor no-data is terminal; a batch no-data must split.
        error = str(entry.get("error", ""))
        if "没找到数据" not in error or "API_CALL_ERROR" not in error:
            raise ValueError(error or "vendor error without detail")
        if len(task["codes"]) > 1:
            split_task(task, state, task["codes"])
        else:
            task["status"] = "no_data"
            task["no_data_evidence"] = error
        return
    rows = raw_events(run.path(task["raw"]), task["codes"])
    if type(entry.get("rows")) is not int or entry["rows"] != len(rows):
        raise ValueError("reported rows disagree with raw CSV")
    raw_sha256 = digest(run.path(task["raw"]))
    if len(rows) >= 100:
        if len(task["codes"]) == 1:
            raise ValueError("singleton reached 100-row cap; coverage unresolved, manual review required")
        split_task(task, state, task["codes"])
        return
    seen = {r["code"] for r in rows}
    missing = [c for c in task["codes"] if c not in seen]
    if missing:
        if len(task["codes"]) == 1:
            raise ValueError("header-only singleton is not confirmed vendor no-data")
        split_task(task, state, missing)
    else:
        task["status"] = "done"
    # Keep evidence only for codes actually present in an uncapped response.
    task["accepted_codes"] = sorted(seen)
    task["raw_sha256"] = raw_sha256


def attempts_used(task):
    return sum(a["status"] not in ("quota", "infra", "skipped") for a in task["attempts"])


def summary(state, max_attempts=3):
    tasks = state["tasks"]
    accepted = {c for t in tasks for c in t.get("accepted_codes", [])}
    no_data = {t["codes"][0] for t in tasks if t["status"] == "no_data"}
    unresolved = [t for t in tasks if t["status"] in ("pending", "running")]
    return {"tasks": len(tasks), "codes_with_raw_response": len(accepted),
            "codes_vendor_no_data": len(no_data), "unresolved_tasks": len(unresolved),
            "retryable_tasks": sum(attempts_used(t) < max_attempts for t in unresolved),
            "exhausted_tasks": sum(attempts_used(t) >= max_attempts for t in unresolved)}


def pull(run, args, runner=None):
    if run.channel == "hithink":
        from scripts.data.hithink_incremental import import_artifact
        return import_artifact(run, args.artifact_dir, refresh=args.refresh)
    if args.artifact_dir or args.refresh:
        raise ValueError("artifact-dir/refresh only apply to hithink")
    runner = runner or subprocess.run
    run.verify_base()
    stop = run.path("work/QUOTA_STOP.json")
    if stop.exists():
        if not args.resume_quota:
            return 3
        stop.rename(run.path(f"work/QUOTA_STOP.{uuid.uuid4().hex}.json"))
    state = run.state()
    while True:
        todo = [t for t in state["tasks"] if t["status"] in ("pending", "running")
                and attempts_used(t) < args.max_attempts][:args.calls_per_session]
        if not todo:
            return 2 if summary(state)["unresolved_tasks"] else 0
        session = uuid.uuid4().hex
        for task in todo:
            task["raw"] = f"raw_events/{task['id']}/{session}.csv"
            run.path(task["raw"]).parent.mkdir(parents=True, exist_ok=True)
            task["status"] = "running"
            task["attempts"].append({"session": session, "status": "interrupted"})
        prompt = prompt_for(run, todo)
        run.write(f"work/kimi_logs/{session}.prompt.txt", prompt.encode("utf-8"))
        run.save(state)  # Crash/interruption leaves a bounded, retryable attempt.
        command = [args.kimi_bin, "-m", run.config["model"], "-p", prompt,
                   "--output-format", "text", "--add-dir", str(run.out)]
        try:
            proc = runner(command, cwd=run.path("work"), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=args.timeout)
            stdout, stderr, returncode = proc.stdout or "", proc.stderr or "", proc.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr, returncode = "", "SESSION_TIMEOUT", -1
        except OSError as exc:
            stdout, stderr, returncode = "", str(exc), -1
        run.write(f"work/kimi_logs/{session}.stdout.txt", stdout.encode("utf-8"))
        run.write(f"work/kimi_logs/{session}.stderr.txt", stderr.encode("utf-8"))
        output = stdout + "\n" + stderr
        quota = quota_hit(output)
        infra = any(s in output.lower() for s in ("storage write failed", "eperm", "permission denied"))
        if quota:
            run.write("work/QUOTA_STOP.json", json_bytes({"session": session, "model": run.config["model"]}))
        try:
            results = result_entries(stdout)
        except ValueError:
            results = {}
        for task in todo:
            task["status"] = "pending"
            attempt = task["attempts"][-1]
            attempt["returncode"] = returncode
            attempt["logs_sha256"] = {
                f"work/kimi_logs/{session}.{suffix}": digest(run.path(f"work/kimi_logs/{session}.{suffix}"))
                for suffix in ("prompt.txt", "stdout.txt", "stderr.txt")
            }
            # Never accept possibly partial files from a stopped/nonzero session.
            if quota or infra:
                attempt["status"] = "quota" if quota else "infra"
                continue
            if not returncode and skipped_entry(results.get(task["id"])):
                attempt["status"] = "skipped"
                continue
            try:
                if returncode:
                    raise ValueError(f"Kimi exited {returncode}; see session logs")
                accept_result(run, task, results.get(task["id"]), state)
                attempt["status"] = "ok"
            except (ValueError, OSError, csv.Error) as exc:
                attempt.update(status="error", error=str(exc))
        run.save(state)
        print(json.dumps(summary(state, args.max_attempts)), flush=True)
        if quota:
            return 3
        if infra or returncode == -1:
            return 2  # No spin on startup failure/timeout; explicit next pull resumes.
        if not returncode and all(skipped_entry(results.get(t["id"])) for t in todo):
            # Every call was skipped under the stop policy (e.g. vendor auth
            # flapping); nothing was attempted, so stop instead of spinning.
            return 2


def normalize_event(raw, config):
    if raw["progress"] != "实施完毕":
        return None, "not_implemented"
    if not raw["ex_date"]:
        return None, "missing_ex_date"
    ex_date = iso_day(raw["ex_date"])
    if not iso_day(config["start"]) <= ex_date <= iso_day(config["end"]):
        return None, "outside_incremental_ex_date_window"
    row = {"code": raw["code"], "source": "wind:wind_get_stock_events"}
    for key in DATES + NUMBERS:
        value = raw[key]
        row[key] = None if value in ("", "None", "nan", "--") else (
            iso_day(value) if key in DATES else decimal_value(value))
    if row["record_date"] is None:
        raise ValueError("implemented event missing record_date")
    if row["record_date"] > ex_date or any(
        row[k] is not None and row[k] < ex_date for k in ("pay_date", "bonus_list_date")
    ):
        raise ValueError("inconsistent event dates")
    return row, None


def natural_key(row):
    return tuple(row[k] for k in ("code", "ex_date") + NUMBERS)


def table_bytes_csv(table):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(EVENT_COLS)
    for row in table.to_pylist():
        writer.writerow(["" if row[k] is None else str(row[k]) for k in EVENT_COLS])
    return stream.getvalue().encode("utf-8")


def assemble(run):
    if run.path("merge-prep").exists():
        raise ValueError("merge-prep already exists; immutable candidate and its assembly evidence")
    if run.channel == "hithink":
        from scripts.data.hithink_incremental import assemble as assemble_hithink
        return assemble_hithink(run)
    run.verify_base()
    state = run.state()
    events, rejected, evidence = {}, [], []
    for task in state["tasks"]:
        if task["status"] == "no_data" or task.get("accepted_codes"):
            for relative, expected in task["attempts"][-1]["logs_sha256"].items():
                if digest(run.path(relative)) != expected:
                    raise ValueError("accepted session evidence changed")
        if task["status"] == "no_data":
            evidence.append({"id": task["id"], "codes": task["codes"],
                             "no_data": task["no_data_evidence"], "attempts": task["attempts"]})
        if not task.get("accepted_codes"):
            continue
        path = run.path(task["raw"])
        if digest(path) != task["raw_sha256"]:
            raise ValueError("accepted raw evidence changed")
        evidence.append({"path": task["raw"], "sha256": task["raw_sha256"],
                         "accepted_codes": task["accepted_codes"],
                         "logs_sha256": task["attempts"][-1]["logs_sha256"]})
        for raw in raw_events(path, task["codes"]):
            if raw["code"] not in task["accepted_codes"]:
                continue
            row, reason = normalize_event(raw, run.config)
            if reason:
                rejected.append({"task": task["id"], "reason": reason, "raw": raw})
                continue
            assert row is not None
            key = natural_key(row)
            if key in events:
                old = events[key]
                for k, value in row.items():
                    if value is not None and old[k] is not None and value != old[k]:
                        raise ValueError(f"conflicting duplicate event field {k}: {key}")
                    if old[k] is None:
                        old[k] = value
            else:
                events[key] = row
    rows = sorted(events.values(), key=lambda r: tuple(str(r[k]) for k in ("code", "ex_date") + NUMBERS))
    for row in rows:
        identity = "|".join("NULL" if x is None else str(x.normalize()) if isinstance(x, Decimal) else str(x)
                            for x in natural_key(row))
        row["event_id"] = (f"{row['code']}_{row['ex_date']:%Y%m%d}_incr_" +
                           hashlib.sha256(identity.encode()).hexdigest()[:20])
    table = pa.Table.from_pylist(rows, schema=EVENT_SCHEMA)
    buffer = pa.BufferOutputStream()
    pq.write_table(table, buffer, compression="snappy", row_group_size=8192)
    run.write("assembled/events.parquet", buffer.getvalue().to_pybytes())
    run.write("assembled/corp_actions.csv", table_bytes_csv(table))
    run.write("assembled/rejected.json", json_bytes(rejected))
    code_dates = Counter((r["code"], r["ex_date"]) for r in rows)
    report = {**summary(state), "event_rows": len(rows), "rejected_rows": len(rejected),
              "null_counts": {k: table[k].null_count for k in EVENT_COLS},
              "multiple_event_code_dates": sum(n > 1 for n in code_dates.values()),
              "window": {k: run.config[k] for k in ("start", "end")}, "evidence": evidence,
              "events_sha256": digest(run.path("assembled/events.parquet")),
              "tasks_sha256": digest(run.path("work/tasks.json")),
              "coverage_is_vendor_query_only": True, "lake_write_authorized": False}
    run.write("assembled/summary.json", json_bytes(report))
    return table, report


def validate_base(table, config):
    if not table.schema.equals(EVENT_SCHEMA, check_metadata=False):
        raise ValueError(f"unexpected base events schema: {table.schema}")
    rows = table.to_pylist()
    ids = [r["event_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate base event_id")
    for row in rows:
        wind_code(row["code"])
        if not row["event_id"] or not row["source"] or row["ex_date"] is None:
            raise ValueError("base has null required fields")
        from oskh_data.hithink_artifact import SOURCE
        if not row["source"].startswith("wind:") and row["source"] != SOURCE:
            raise ValueError("unknown base source")
        if row["source"].startswith("wind:") and row["record_date"] is None:
            raise ValueError("base has null required fields")
        if ((row["record_date"] is not None and row["record_date"] > row["ex_date"])
                or any(row[k] is not None and row[k] < row["ex_date"] for k in ("pay_date", "bonus_list_date"))):
            raise ValueError("inconsistent base event dates")
        for key in NUMBERS:
            if row[key] is not None:
                decimal_value(row[key])
        if row["ex_date"] > iso_day(config["base_ask_end"]):
            raise ValueError("base contains events after ask_end; manual reconciliation required")
    return rows


def prepare_merge(run):
    if run.path("merge-prep").exists():
        raise ValueError("merge-prep already exists; immutable candidate, inspect rather than overwrite")
    delta, report = assemble(run)
    if report["unresolved_tasks"]:
        raise ValueError("unresolved/exhausted tasks; cannot prepare a candidate")
    if run.channel == "hithink":
        if report["mixed_economics_requires_review"]:
            raise ValueError("mixed economics with allotment requires review")
        covered = set(report["universe_hits"]) | set(report["codes_no_events"]) | set(report["vendor_unknown_classification"])
    else:
        covered = {c for t in run.state()["tasks"] for c in (
            t["codes"] if t["status"] == "no_data" else t.get("accepted_codes", []))}
    if covered != set(run.config["codes"]):
        raise ValueError("task evidence does not cover the frozen universe")
    lake = Path(run.config["lake_dir"])
    base = pq.read_table(lake / "events.parquet")
    old_rows = validate_base(base, run.config)
    old_ids = {r["event_id"] for r in old_rows}
    new_rows = delta.to_pylist()
    if any(r["event_id"] in old_ids for r in new_rows):
        raise ValueError("incremental event_id collides with base")
    if {(r["code"], r["ex_date"]) for r in old_rows} & {(r["code"], r["ex_date"]) for r in new_rows}:
        raise ValueError("incremental code/ex_date overlaps base; source-independent collision")
    candidate = pa.concat_tables([base.replace_schema_metadata(None), delta])
    candidate = candidate.sort_by([(k, "ascending") for k in ("code", "ex_date", "event_id")])
    if run.path("merge-prep").exists():
        raise ValueError("merge-prep already exists; immutable candidate, inspect rather than overwrite")
    relative = "work/merge-prep-" + uuid.uuid4().hex
    staging = run.path(relative)
    staging.mkdir()
    pq.write_table(candidate, run.path(relative + "/events.parquet"), compression="snappy", row_group_size=8192)
    for name in ("listing.parquet", "failures.parquet"):
        shutil.copyfile(lake / name, run.path(relative + "/" + name))
    if not pq.read_table(staging / "events.parquet").equals(candidate):
        raise ValueError("candidate round-trip mismatch")
    files = {name: {"sha256": digest(staging / name), "rows": pq.read_table(staging / name).num_rows}
             for name in BASE_FILES if name != "manifest.json"}
    plan = {
        "format_version": 1, "status": "PREPARED_REQUIRES_SEPARATE_HUMAN_GO",
        "lake_write_authorized": False, "automatically_applicable": False,
        "base": {"directory": str(lake), "sha256": run.config["base_sha256"],
                 "snapshot": run.config["base_snapshot"], "revision": run.config["base_revision"]},
        "candidate_files": files, "base_event_rows": base.num_rows, "added_event_rows": delta.num_rows,
        "deleted_event_rows": 0, "updated_event_rows": 0,
        "assembly_sha256": digest(run.path("assembled/summary.json")),
        "delta_quality": {k: report[k] for k in ("null_counts", "multiple_event_code_dates", "rejected_rows")},
        "run_sha256": digest(run.path("run.json")),
        "proposed_coverage_patch": {"ask_end": run.config["end"]},
        "coverage_patch_requires_vendor_window_review": True,
        "listing_and_failures": "byte-for-byte base copies; no refresh or resolution claimed",
        "review_requirements": [
            "Separate Human GO and owner-side publisher; this driver has no apply command.",
            "Recheck ALL base hashes before any later publication; allocate a new revision/snapshot.",
            "Wind date window may select report/announcement period rather than ex_date. Confirm coverage before advancing ask_end.",
            "No historical corrections/deletions or late payments/list dates for old ex-dates were queried.",
            "No-data means only this vendor question returned no data; it is not proof of no ex-date events.",
            "Review null economics/dates and multiple events per code/date before research consumption.",
        ],
    }
    if run.channel == "hithink":
        plan.update(channel="hithink", economics_ready=False,
                    vendor_unknown_classification=report["vendor_unknown_classification"],
                    manual_overrides_applied=report["manual_overrides_applied"],
                    exclusions_sha256=report["exclusions_sha256"])
        plan["review_requirements"] = [
            "Separate Human GO and owner-side publisher; this driver has no apply command.",
            "Recheck all base, artifact, exclusion and candidate hashes before any publication.",
            "Hithink has NULL record/pay/list dates; positive bonus requires an explicit listing date before economics.",
            "Hithink bonus is combined bonus/transfer; price-adjustment values need reviewed economic-basis evidence.",
            "Allotment sidecar is excluded; no inference for restructuring bonus gaps or missing vendor coverage.",
            "Dump window hits and maximum ex_date do not certify freshness or economic completeness.",
            "Review each effective override, its calendar expiry and event-date scope; re-evaluate before publication.",
            "No cross-source field stitching; historical changes require a separately reviewed revision.",
        ]
    # Deliberately a patch PLAN, not a replacement lake manifest or ready-to-run publisher.
    run.write(relative + "/manifest-patch-plan.json", json_bytes(plan))
    run.verify_base()
    if run.channel == "hithink" and digest(run.path("hithink_exclusions.json")) != report["exclusions_sha256"]:
        raise ValueError("exclusions changed during candidate preparation")
    staging.rename(run.path("merge-prep"))
    return plan


def parser():
    ap = argparse.ArgumentParser(description=(__doc__ or "Corporate-action incremental candidates").splitlines()[0])
    ap.add_argument("command", choices=("init", "pending", "pull", "assemble", "prepare-merge"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--lake-dir", help="init only: explicit read-only corp-actions directory; otherwise resolver")
    ap.add_argument("--universe", help="init only: prior universe.txt or listing CSV/Parquet; default lake listing")
    ap.add_argument("--start", help="init only: must equal base ask_end + 1 day")
    ap.add_argument("--end", help="init only: default today CST, then frozen for all resumes")
    ap.add_argument("--model", choices=MODELS, help="init only; default kimi-code/kimi-for-coding-highspeed")
    ap.add_argument("--channel", choices=("wind", "hithink"), help="init only; default wind")
    ap.add_argument("--exclusions", help="hithink init only: review config copied into the run")
    ap.add_argument("--artifact-dir", help="hithink pull only: committed 1.3 snapshot; never downloads")
    ap.add_argument("--refresh", action="store_true", help="hithink pull only; forbidden after assemble")
    ap.add_argument("--kimi-bin", default="kimi", help="pull only: executable on PATH or explicit path")
    ap.add_argument("--calls-per-session", type=int, default=6, help="serial sessions, 1..12 calls each")
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=1800, help="seconds per Kimi session")
    ap.add_argument("--resume-quota", action="store_true", help="pull only: archive quota marker and explicitly retry")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if not 1 <= args.calls_per_session <= 12 or args.max_attempts < 1 or args.timeout < 1:
            raise ValueError("invalid session/attempt/timeout bounds")
        if args.command == "init":
            if (args.channel or "wind") == "wind":
                args.model = args.model or MODELS[0]
            if args.artifact_dir or args.refresh:
                raise ValueError("artifact-dir/refresh only apply to pull")
            run = initialize(args)
            print(json.dumps(run.config, ensure_ascii=False, indent=2))
            return 0
        if any(getattr(args, k) is not None for k in ("lake_dir", "universe", "start", "end", "model", "channel", "exclusions")):
            raise ValueError("lake/universe/window/model are frozen; set them only on init")
        run = Run(args.out_dir)
        if args.command != "pull" and (args.artifact_dir or args.refresh):
            raise ValueError("artifact-dir/refresh only apply to pull")
        if args.command == "pending":
            run.verify_base()
            if run.channel == "hithink":
                from scripts.data.hithink_incremental import imported
                if run.path("work/hithink_committed.json").exists():
                    state, _, _ = imported(run)
                    print(json.dumps(state))
                else:
                    print(json.dumps({"channel": "hithink", "acquisition": "not_committed"}))
                return 0
            print(json.dumps({**summary(run.state(), args.max_attempts),
                              "quota_stopped": run.path("work/QUOTA_STOP.json").exists()}))
            return 0
        with run.locked():
            if args.command == "pull":
                return pull(run, args)
            if args.command == "assemble":
                _, report = assemble(run)
                print(json.dumps({k: v for k, v in report.items() if k != "evidence"}))
                return 2 if report["unresolved_tasks"] else 0
            plan = prepare_merge(run)
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            return 0
    except (ValueError, OSError, KeyError, csv.Error, pa.ArrowException, UnconfiguredDataRootError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
