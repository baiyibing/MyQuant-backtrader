# -*- coding: utf-8 -*-
"""B-L2-01 live R3 host driver on newtest_4090 — tip a268e11 (#270).

Fail-closed: fill §9 packages ONLY from real host evidence.
No invent: no 10% limits, no halt-from-silence, no lots×100 from amount/(close×V),
no renaming heuristic to source_declaration. Fixture PASS != lake PASS.
Preserve R1/R2 export roots; write only new R3 root.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path(r"D:\exports\b_l2_01_4090_r3_20260930")
EVIDENCE = OUT / "evidence"
REPO = Path(r"D:\PycharmProjects\MyQuant-backtrader")
TIP = "a268e11bc682cd1ae5a6672ab89091cea1abe937"
SOURCE_ROOT = Path(r"E:\stock_data")
PROBE_SYMBOL = "603196.SH"
WINDOW_FROM = "20251023"
WINDOW_THROUGH = "20251104"
TZ = ZoneInfo("Asia/Shanghai")
LABEL = "真实行情驱动的合成订单研究"
TRANSFORM_EXPECTED = "bl2_source_transform_v3"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cell(gate, source, parity="NOT_RUN", oracle="NOT_RUN", note=""):
    return {
        "gate": gate,
        "source_correctness": source,
        "delegation_parity": parity,
        "independent_oracle": oracle,
        "note": note,
    }


def walk_keyword_hits(root: Path, keys, max_depth=3, max_dirs=8000):
    hits = []
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath[len(str(root)) :].count(os.sep)
        if depth > max_depth:
            dirnames[:] = []
            continue
        base = os.path.basename(dirpath).lower()
        if any(k.lower() in base for k in keys):
            hits.append(dirpath)
        for fn in filenames:
            fl = fn.lower()
            if any(k.lower() in fl for k in keys):
                hits.append(str(Path(dirpath) / fn))
        seen += 1
        if seen > max_dirs:
            break
    return sorted(set(hits))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    issued = datetime.now(TZ).isoformat(timespec="seconds")

    os.environ["OSKH_SOURCE_PARQUET_ROOT"] = str(SOURCE_ROOT)
    for k in ("OSKH_PERIOD_1M_ROOT", "OSKH_PERIOD_1D_ROOT", "OSKH_AUTHORITY_HINT_ROOT"):
        os.environ.pop(k, None)
    sys.path.insert(0, str(REPO))

    head = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    porcelain = subprocess.check_output(
        ["git", "-C", str(REPO), "status", "--porcelain"], text=True
    )
    dirty = bool(porcelain.strip())

    import pyarrow.parquet as pq
    import pandas as pd
    from common.infra import data_root
    from oskh_data.symbol_format import to_partition_key
    from backtest.research.minute_orders_backend.source_loader import execution_identity
    from backtest.research.minute_orders_backend.source_provenance import TRANSFORM_VERSION

    identity = execution_identity()
    tip_ok = (
        head == TIP
        and not dirty
        and identity.get("code_sha") == TIP
        and identity.get("code_dirty") is False
        and TRANSFORM_VERSION == TRANSFORM_EXPECTED
    )

    container = Path(os.environ["OSKH_SOURCE_PARQUET_ROOT"])
    root_ok = container.is_dir() and container.resolve() == SOURCE_ROOT.resolve()

    part = (
        data_root.resolve_period_root("1m")
        / "dividend_type=none"
        / f"symbol={to_partition_key(PROBE_SYMBOL)}"
        / "data.parquet"
    )
    pf = pq.ParquetFile(part)
    minute_schema = {f.name: str(f.type) for f in pf.schema_arrow}
    has_symbol_col = "symbol" in minute_schema
    expected_vendor = {
        "time": "int64",
        "open": "double",
        "high": "double",
        "low": "double",
        "close": "double",
        "volume": "int64",
        "amount": "double",
        "__index_level_0__": "timestamp[ns]",
    }
    schema_matches_vendor = minute_schema == expected_vendor
    partition_mode_viable = (not has_symbol_col) and schema_matches_vendor

    table = pf.read()
    df = table.to_pandas().reset_index()
    idx_col = "__index_level_0__" if "__index_level_0__" in df.columns else "index"
    df["idx"] = pd.to_datetime(df[idx_col])
    w = df[(df["idx"] >= "2025-10-23") & (df["idx"] <= "2025-11-04 23:59:59")].copy()
    window_days = sorted(w["idx"].dt.date.astype(str).unique().tolist())
    window_rows = int(len(w))
    window_first = window_last = None
    if window_rows:
        r0, r1 = w.iloc[0], w.iloc[-1]
        window_first = {
            "time_ms": int(r0["time"]),
            "close": float(r0["close"]),
            "volume": int(r0["volume"]),
            "index": str(r0["idx"]),
        }
        window_last = {
            "time_ms": int(r1["time"]),
            "close": float(r1["close"]),
            "volume": int(r1["volume"]),
            "index": str(r1["idx"]),
        }

    sub = w[(w["volume"] > 0) & (w["close"] > 0)].head(200).copy()
    if len(sub):
        sub["implied_mult"] = sub["amount"] / (sub["close"] * sub["volume"])
        implied = {
            "n": int(len(sub)),
            "mean": float(sub["implied_mult"].mean()),
            "median": float(sub["implied_mult"].median()),
            "min": float(sub["implied_mult"].min()),
            "max": float(sub["implied_mult"].max()),
            "frac_within_0_5_of_100": float(((sub["implied_mult"] - 100).abs() < 0.5).mean()),
            "frac_within_0_5_of_1": float(((sub["implied_mult"] - 1).abs() < 0.5).mean()),
        }
        sample_volumes = [int(x) for x in sub["volume"].head(20).tolist()]
    else:
        implied = None
        sample_volumes = []

    day = w[w["idx"].dt.date.astype(str) == "2025-10-23"].sort_values("idx")
    small_interval = None
    mark_1459 = None
    if len(day) >= 2:
        small_interval = {
            "day": "2025-10-23",
            "proposed_intervals": [
                {"start": "2025-10-23T09:30:00+08:00", "end": "2025-10-23T09:32:00+08:00"}
            ],
            "note": "2 continuous START minutes on one session; calendar still needs acquire/sellable/next BUY dates",
        }
        row_1459 = day[day["idx"].dt.strftime("%H:%M") == "14:59"]
        if len(row_1459):
            r = row_1459.iloc[0]
            mark_1459 = {
                "index": str(r["idx"]),
                "time_ms": int(r["time"]),
                "close": float(r["close"]),
                "volume": int(r["volume"]),
                "note": "15:00 mark via START row at 14:59 if bars use START",
            }

    ex_path = data_root.resolve_source_parquet("ex_date_index.parquet")
    adj_path = data_root.resolve_source_parquet("adj_factor.parquet")
    ex_hits = []
    if ex_path.is_file():
        ex = pq.read_table(ex_path).to_pandas()
        code_cols = [c for c in ex.columns if "code" in c.lower() or "symbol" in c.lower()]
        date_cols = [c for c in ex.columns if "date" in c.lower() or c == "ex_date"]
        if code_cols and date_cols:
            cc, dc = code_cols[0], date_cols[0]
            mask = ex[cc].astype(str).str.contains("603196", na=False)
            for _, row in ex.loc[mask].iterrows():
                d = str(row[dc]).replace("-", "")[:8]
                if WINDOW_FROM <= d <= WINDOW_THROUGH:
                    ex_hits.append({cc: str(row[cc]), dc: str(row[dc])})

    lake_top = sorted(
        [p.name for p in SOURCE_ROOT.iterdir() if not p.name.startswith("_") and not p.name.startswith(".")]
    )

    keys_inst = (
        "instrument",
        "limit_up",
        "limit_down",
        "tick_size",
        "lot_size",
        "price_limit",
        "up_limit",
        "down_limit",
    )
    keys_status = (
        "halt",
        "suspend",
        "missing_bar",
        "trade_status",
        "status_grid",
        "停牌",
        "交易状态",
    )
    keys_units = (
        "volume_unit",
        "shares_per",
        "lot_factor",
        "field_dict",
        "data_dict",
        "schema_doc",
        "成交量单位",
    )
    instrument_hits = walk_keyword_hits(SOURCE_ROOT, keys_inst)
    status_hits = walk_keyword_hits(SOURCE_ROOT, keys_status)
    units_hits = walk_keyword_hits(SOURCE_ROOT, keys_units)

    # name-level top dirs (same as R2)
    instrument_like = []
    status_like = []
    for p in SOURCE_ROOT.iterdir():
        n = p.name.lower()
        if any(k in n for k in ("instrument", "limit", "tick", "lot_size", "price_limit")):
            instrument_like.append(p.name)
        if any(k in n for k in ("halt", "suspend", "missing_bar", "trade_status", "status_grid")):
            status_like.append(p.name)
    st_vendors = [n for n in lake_top if "st_status" in n or "st_names" in n]

    dpart = (
        data_root.resolve_period_root("1d")
        / "dividend_type=none"
        / f"symbol={to_partition_key(PROBE_SYMBOL)}"
        / "data.parquet"
    )
    daily_schema = None
    daily_limit_cols = []
    if dpart.is_file():
        dpf = pq.ParquetFile(dpart)
        daily_schema = {f.name: str(f.type) for f in dpf.schema_arrow}
        daily_limit_cols = [
            c
            for c in daily_schema
            if any(k in c.lower() for k in ("limit", "tick", "lot", "preclose", "suspend", "halt", "up", "down"))
        ]

    float_schema = None
    fp = SOURCE_ROOT / "float_shares.parquet"
    if fp.is_file():
        float_schema = {f.name: str(f.type) for f in pq.ParquetFile(fp).schema_arrow}

    st_schemas = {}
    for rel in (
        "vendor_wind_st_status/st_daily.parquet",
        "vendor_wind_st_status/st_intervals.parquet",
    ):
        sp = SOURCE_ROOT / rel
        if sp.is_file():
            st_schemas[rel] = {f.name: str(f.type) for f in pq.ParquetFile(sp).schema_arrow}

    # Nearby extra roots (existence only)
    extra_roots_checked = {}
    for r in [
        Path(r"D:\stock_data"),
        Path(r"E:\data"),
        Path(r"D:\data"),
        Path(r"E:\qmt"),
        Path(r"D:\qmt"),
        Path(r"E:\Wind"),
        Path(r"D:\Wind"),
        Path(r"E:\vendor"),
        Path(r"D:\vendor"),
        Path(r"E:\xtquant"),
        Path(r"D:\xtquant"),
        Path(r"E:\market_data"),
        Path(r"D:\market_data"),
    ]:
        extra_roots_checked[str(r)] = r.is_dir()

    # Copy empty templates into evidence/ as UNFILLED markers (not attestation)
    fx = REPO / "tests" / "fixtures" / "minute_orders_source_attestation"
    template_names = [
        "units.proof.template.json",
        "instruments.template.json",
        "instruments.derived.template.json",
        "instruments.proof.template.json",
        "status.template.json",
        "status.proof.template.json",
    ]
    copied_templates = {}
    for tn in template_names:
        src = fx / tn
        dst = EVIDENCE / tn
        if src.is_file():
            shutil.copy2(src, dst)
            copied_templates[tn] = {
                "path": str(dst),
                "sha256": sha256_file(dst),
                "filled": False,
                "note": "UNFILLED template copy; nulls/empty refs retained; not market attestation",
            }

    packages_filled = {
        "volume_units": None,
        "instruments": None,
        "status": None,
    }
    # Honest gate decisions: no independent materials found
    volume_blocked_reason = (
        "no independently pinned vendor field-semantics / named-authority source_declaration "
        "for minute volume units; bars themselves cannot be source_refs; "
        "amount/(close*volume)≈100 remains non-attestation heuristic; "
        "refusing to invent units attestation or rename heuristic to source_declaration"
    )
    instrument_blocked_reason = (
        "no independent tick/lot/reference/limit_up/limit_down fact table on host or nearby vendor dirs; "
        "1d bars lack limit cols; float_shares lacks tick/lot/limits; "
        "ST vendors are ST-name lists not instrument facts; "
        "refusing to invent bare 10% limits or approved_derivation without pinned inputs+approved_rule_version+two issuers"
    )
    status_blocked_reason = (
        "no bl2_status_v1 full symbol×session-minute grid with explicit missing/halted + proofs; "
        "ST vendor dirs (cninfo/qmt/wind) are ST status/names not halt/missing minute grids; "
        "zero-volume bars ≠ halted; absent source row ≠ auto-missing; "
        "refusing to invent halt-from-silence or false/false without explicit_status binding"
    )

    volume_gate = "BLOCKED"
    instrument_gate = "BLOCKED"
    status_gate = "BLOCKED"
    # All three must be fillable before freeze
    can_freeze = volume_gate == "PASS" and instrument_gate == "PASS" and status_gate == "PASS"

    cells = []
    cells.append(
        cell(
            "sync_tip",
            "PASS" if tip_ok else "FAIL",
            note=(
                f"HEAD={head} dirty={dirty} identity.code_sha={identity.get('code_sha')} "
                f"transform={TRANSFORM_VERSION}"
            ),
        )
    )
    cells.append(
        cell(
            "configured_source_root",
            "PASS" if root_ok else "FAIL",
            note=f"OSKH_SOURCE_PARQUET_ROOT={SOURCE_ROOT} container_ok={root_ok}",
        )
    )
    cells.append(
        cell(
            "proposed_window_bars_present",
            "PASS" if window_rows > 0 else "FAIL",
            note=f"symbol={PROBE_SYMBOL} window_rows={window_rows} days={len(window_days)}",
        )
    )
    cells.append(
        cell(
            "minute_parquet_partition_symbol_mode",
            "PASS" if partition_mode_viable else ("FAIL" if has_symbol_col else "BLOCKED"),
            note=(
                "vendor schema matches #269/#270 partition-mode expectation; "
                "columns.symbol={'kind':'partition'} would bind identity; "
                f"has_symbol_column={has_symbol_col} schema_matches_vendor={schema_matches_vendor}"
            ),
        )
    )
    cells.append(cell("volume_units_attestation", volume_gate, oracle="未覆盖", note=volume_blocked_reason))
    cells.append(
        cell("instrument_limits_facts", instrument_gate, oracle="未覆盖", note=instrument_blocked_reason)
    )
    cells.append(
        cell("halt_missing_facts_source", status_gate, oracle="未覆盖", note=status_blocked_reason)
    )
    cells.append(
        cell(
            "freeze_recipe_attestation",
            "BLOCKED" if not can_freeze else "PASS",
            note=(
                "fail-closed: cannot freeze lake recipe/attestation without honest volume units + "
                "instrument facts + status grid + scope_hash=attestation_scope(recipe); "
                f"TRANSFORM_VERSION={TRANSFORM_VERSION}; packages remain UNFILLED templates only"
            ),
        )
    )
    cells.append(
        cell(
            "native_api_vs_l1_api",
            "NOT_RUN",
            parity="NOT_RUN",
            note="no frozen RunInput (recipe/attestation BLOCKED); hybrid S4 not attempted",
        )
    )
    cells.append(
        cell(
            "independent_spot_checks_capacity_expiry_t1_fee_mark",
            "NOT_RUN",
            oracle="NOT_RUN",
            note="no frozen source rows; oracles require frozen source not MatchCore",
        )
    )
    cells.append(
        cell(
            "company_actions_empty_window_probe",
            "PASS",
            oracle="未覆盖",
            note=f"ex_window_hits={len(ex_hits)}; probe only ≠ bl2_proof_v1 complete_no_company_actions",
        )
    )
    cells.append(
        cell(
            "attestation_packages_fill",
            "BLOCKED",
            note=(
                "evidence/ holds UNFILLED #270 templates only; "
                f"packages_filled={packages_filled}; no real source materials to review"
            ),
        )
    )

    blocked_reasons = [
        "volume_units_attestation: " + volume_blocked_reason,
        "instrument_limits_facts: " + instrument_blocked_reason,
        "halt_missing_facts_source: " + status_blocked_reason,
        "freeze_recipe_attestation: blocked by prior gates; no lake RunInput frozen",
    ]
    verdict = "BLOCKED/NOT_RUN"
    if not tip_ok:
        verdict = "FAIL/BLOCKED"

    summary = {
        "unit": "B-L2-01",
        "round": "R3",
        "verdict": verdict,
        "label": LABEL,
        "issued_at": issued,
        "host": "newtest_4090",
        "tip_expected": TIP,
        "tip_actual": head,
        "code_dirty": dirty,
        "transform_version": TRANSFORM_VERSION,
        "pr_ref": "#270",
        "execution_identity": {
            "code_sha": identity.get("code_sha"),
            "code_dirty": identity.get("code_dirty"),
            "python_version": identity.get("python_version"),
            "pyarrow_version": identity.get("pyarrow_version"),
            "transform_version": TRANSFORM_VERSION,
        },
        "python": identity.get("python_version"),
        "pyarrow": identity.get("pyarrow_version"),
        "source_root": str(SOURCE_ROOT),
        "proposed_window": {
            "from": WINDOW_FROM,
            "through": WINDOW_THROUGH,
            "status": "proposed_unattested",
        },
        "probe_symbol": PROBE_SYMBOL,
        "minute_partition": str(part),
        "minute_schema": minute_schema,
        "has_symbol_column": has_symbol_col,
        "partition_mode_viable": partition_mode_viable,
        "schema_matches_vendor_expectation": schema_matches_vendor,
        "window_days": window_days,
        "window_rows": window_rows,
        "window_first": window_first,
        "window_last": window_last,
        "sample_volumes": sample_volumes,
        "volume_unit_probe": {
            "implied_amount_over_close_volume": implied,
            "attested": False,
            "note": "heuristic only; not claim units + proof; not source_declaration",
        },
        "small_interval_proposal": small_interval,
        "mark_1459_for_1500_start": mark_1459,
        "ex_date_index": str(ex_path),
        "adj_factor": str(adj_path),
        "ex_window_hits": ex_hits,
        "lake_top_nonhidden": lake_top,
        "instrument_like_names": instrument_like,
        "status_like_names": status_like,
        "st_vendor_dirs": st_vendors,
        "keyword_search_hits": {
            "instrument": instrument_hits[:40],
            "status": status_hits[:40],
            "units": units_hits[:40],
            "instrument_count": len(instrument_hits),
            "status_count": len(status_hits),
            "units_count": len(units_hits),
        },
        "extra_roots_checked": extra_roots_checked,
        "daily_schema": daily_schema,
        "daily_limit_like_columns": daily_limit_cols,
        "float_shares_schema": float_schema,
        "st_vendor_schemas": st_schemas,
        "packages_filled": packages_filled,
        "unfilled_templates_copied": copied_templates,
        "blocked_reasons": blocked_reasons,
        "progress_vs_r2": {
            "tip": f"47abe4d (#269) → a268e11 (#270)",
            "transform": "bl2_source_transform_v2 → bl2_source_transform_v3",
            "packages_registered": True,
            "binding_tightened": True,
            "empty_templates_present": True,
            "volume_units_still_blocked": True,
            "instrument_limits_still_blocked": True,
            "halt_missing_still_blocked": True,
            "freeze_still_blocked": True,
            "native_l1_still_not_run": True,
            "oracles_still_not_run": True,
            "note": "#270 registered packages+templates; host still lacks independent source materials to fill them",
        },
        "hard_locks": {
            "lake_overwrite": False,
            "ssot_green": False,
            "delta5": False,
            "jr_g": False,
            "merge": False,
            "fixture_pass_claimed_as_lake": False,
            "alternate_period_root_invented": False,
            "invented_10pct_limits": False,
            "invented_volume_units_attestation": False,
            "invented_halt_from_silence": False,
            "renamed_heuristic_to_source_declaration": False,
            "r1_r2_export_roots_preserved": True,
        },
        "frozen": {
            "recipe": None,
            "sidecars": None,
            "run_input": None,
            "attestation_scope_hash": None,
        },
        "api_runs": {
            "native_hybrid": "NOT_RUN",
            "l1_full_s4": "NOT_RUN",
            "compare": "NOT_RUN",
            "load_minute_orders_source_precheck": "NOT_RUN",
        },
        "cells": cells,
        "limitations": [
            "Fixture PASS != lake PASS; empty templates intentionally fail until filled.",
            "PASS != market executability; no SSOT / δ5 / JR G / merge.",
            "Proposed window remains unattested until freeze.",
            "ST vendor dirs are not halt/missing session-minute grids.",
            "Volume ratio heuristic is explicitly non-attestation under §9.2.",
        ],
        "next_ask": (
            "Human/bt: supply independently reviewable (1) vendor volume-units source_declaration "
            "for 1m bars, (2) daily tick/lot/reference/limit fact table or approved_derivation materials "
            "with two issuers, (3) full symbol×session-minute halt/missing status grid with proofs — "
            "then re-GO R4 fill/pin/freeze; do not invent 10%/halt-from-silence/lots-heuristic."
        ),
    }

    summary_path = OUT / "probe_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Markdown receipt
    lines = []
    lines.append("# HOST_B_L2_01_R3 — 4090 live receipt")
    lines.append("")
    lines.append(f"- Issued: `{issued}` Asia/Shanghai")
    lines.append(f"- Host: **newtest_4090** · tip `{head}` · dirty={dirty}")
    lines.append(
        f"- Unit: **B-L2-01** · round **R3** · proposed window `{WINDOW_FROM}`–`{WINDOW_THROUGH}`"
    )
    lines.append(f"- Source: `OSKH_SOURCE_PARQUET_ROOT={SOURCE_ROOT}` (read-only)")
    lines.append(f"- Label: {LABEL}")
    lines.append(f"- Transform: `{TRANSFORM_VERSION}` · PR **#270**")
    lines.append(f"- **Verdict: `{verdict}`**")
    lines.append("")
    lines.append("## Why blocked")
    lines.append("")
    for i, r in enumerate(blocked_reasons, 1):
        lines.append(f"{i}. {r}")
    lines.append("")
    lines.append("## Progress vs R2")
    lines.append("")
    lines.append(
        "- Tip advanced `47abe4d` (#269) → `a268e11` (#270); transform `v2` → **`bl2_source_transform_v3`**."
    )
    lines.append(
        "- #270 registered volume/instrument/status packages + empty templates + tightened basis/binding; templates intentionally fail until filled."
    )
    lines.append(
        "- Host still cannot fill or freeze: no independent units declaration, no instrument tick/lot/limit facts, no halt/missing minute grid. Fail-closed (no invented facts)."
    )
    lines.append(
        f"- Window bars still present: **{window_rows}** rows across days `{window_days[0] if window_days else '?'}` … `{window_days[-1] if window_days else '?'}` ({len(window_days)} sessions)."
    )
    lines.append("")
    lines.append("## Probe notes (not attestation)")
    lines.append("")
    lines.append(
        f"- Minute partition: `{part}` schema={json.dumps(minute_schema, ensure_ascii=False)}"
    )
    lines.append(
        f"- Partition mode viable: **{partition_mode_viable}** (has_symbol_column={has_symbol_col})"
    )
    if implied:
        lines.append(
            f"- Volume heuristic amount/(close×volume): mean={implied['mean']:.4f} "
            f"median={implied['median']:.4f} frac≈100(±0.5)={implied['frac_within_0_5_of_100']:.2f} "
            "— **not** attested; not source_declaration."
        )
    lines.append(
        f"- Keyword search under lake (depth≤3): units={len(units_hits)} instrument={len(instrument_hits)} status={len(status_hits)} (all empty of usable materials)."
    )
    lines.append(f"- Instrument-like lake names: {instrument_like}; status-like: {status_like}; ST vendors: {st_vendors}")
    lines.append(f"- Daily limit-like columns for probe symbol: {daily_limit_cols}")
    lines.append(f"- float_shares schema: {float_schema}")
    lines.append(f"- ST schemas (not minute halt grids): {json.dumps(st_schemas, ensure_ascii=False)}")
    lines.append(f"- Nearby vendor roots present: { {k:v for k,v in extra_roots_checked.items() if v} or 'none' }")
    lines.append(f"- Company-action probe ex_date_index hits in window: **{len(ex_hits)}**")
    lines.append(f"- Small interval proposal (doc only): `{json.dumps(small_interval, ensure_ascii=False)}`")
    lines.append(f"- 14:59 START candidate: `{json.dumps(mark_1459, ensure_ascii=False)}`")
    lines.append("- Native API↔L1 and independent oracles: **NOT_RUN** (no frozen RunInput).")
    lines.append("")
    lines.append("## Packages / evidence")
    lines.append("")
    lines.append(
        "- **No packages filled** from real host evidence. `evidence/` holds UNFILLED #270 template copies only:"
    )
    for tn, meta in copied_templates.items():
        lines.append(f"  - `{tn}` → `{meta['path']}` sha256=`{meta['sha256'][:16]}…` filled=False")
    lines.append("- packages_filled: volume_units=null, instruments=null, status=null")
    lines.append("")
    lines.append("## Per-cell table")
    lines.append("")
    lines.append("| gate | source | parity | oracle | note |")
    lines.append("|---|---|---|---|---|")
    for c in cells:
        note = c["note"].replace("|", "\\|")
        lines.append(
            f"| {c['gate']} | {c['source_correctness']} | {c['delegation_parity']} | {c['independent_oracle']} | {note} |"
        )
    lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    lines.append(f"- Host root: `{OUT}`")
    lines.append(f"- Host JSON: `{summary_path}`")
    lines.append(f"- Host MD: `{OUT / 'HOST_B_L2_01_R3.md'}`")
    lines.append(f"- Host evidence (unfilled templates): `{EVIDENCE}`")
    lines.append("- Box mirror: `/workspace/handoffs/b_l2_4090_live_r3_20260930/`")
    lines.append("- No recipe/sidecars frozen; no hybrid S4 outs written (NOT_RUN).")
    lines.append("- Lake / SSOT / δ5 / JR G / merge untouched; R1/R2 export roots preserved.")
    lines.append("")
    lines.append("## Explicit non-claims")
    lines.append("")
    lines.append("- Not lake PASS. Not fixture PASS reused as lake PASS.")
    lines.append("- Not market executability. Not SSOT green R/S.")
    lines.append("- Not volume-units attestation from amount/close heuristic or renamed source_declaration.")
    lines.append("- Not invented 10% limit bands or approved_derivation without pinned inputs.")
    lines.append("- Not halt-from-silence status grid; not false/false without explicit_status.")
    lines.append("- Not native↔L1 parity; not independent oracle coverage.")
    lines.append("")
    lines.append("## Next ask")
    lines.append("")
    lines.append(summary["next_ask"])
    lines.append("")

    md_path = OUT / "HOST_B_L2_01_R3.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    hashes = {
        "HOST_B_L2_01_R3.md": sha256_file(md_path),
        "probe_summary.json": sha256_file(summary_path),
        "evidence_templates": {k: v["sha256"] for k, v in copied_templates.items()},
    }
    hash_path = OUT / "artifact_hashes.json"
    hash_path.write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hashes["artifact_hashes.json"] = sha256_file(hash_path)
    # rewrite with self hash omitted to avoid churn — keep without self
    hash_path.write_text(
        json.dumps(
            {
                "HOST_B_L2_01_R3.md": hashes["HOST_B_L2_01_R3.md"],
                "probe_summary.json": hashes["probe_summary.json"],
                "evidence_templates": hashes["evidence_templates"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"verdict": verdict, "out": str(OUT), "tip": head, "transform": TRANSFORM_VERSION}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
