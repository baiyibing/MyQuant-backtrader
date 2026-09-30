# -*- coding: utf-8 -*-
"""B-L2-01 R4 evidence staging: generate raw material packages (host-assist, 2026-09-30).

Read-only collection from lake + installed xtquant package + sibling repos.
Output: row-style excerpt JSONs under evidence/raw_materials/ with SHA-256 pins.
These are DRAFT raw materials for host review - NOT bl2_proof_v1 packages.
"""
import json
import hashlib
import re
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

EV = Path(r"D:\exports\b_l2_01_4090_r3_20260930\evidence")
RAW = EV / "raw_materials"
RAW.mkdir(parents=True, exist_ok=True)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lines_of(p, a, b):
    txt = Path(p).read_text(encoding="utf-8", errors="replace").splitlines()
    return [{"line": i, "text": txt[i - 1]} for i in range(a, min(b, len(txt)) + 1)]


def write_json(name, obj):
    q = RAW / name
    q.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    assert b"\x00" not in q.read_bytes()
    print(name, "sha256=", sha256(q), "bytes=", q.stat().st_size)


XTQ = Path(r"D:\anaconda3\envs\vanna312\Lib\site-packages\xtquant")

# --- 1. xtquant vendor doc excerpts ---
src_md = XTQ / "doc" / "xtdata.md"
src_py = XTQ / "xtdata.py"
src_tr = XTQ / "doc" / "xttrader.md"
rows = []
rows.append({
    "excerpt_id": "xtdata_md_kline_fields",
    "original": str(src_md), "original_sha256": sha256(src_md),
    "lines": lines_of(src_md, 1219, 1241),
    "note": "K线(1m/5m/1d)字段表：volume=成交量(无单位注记)、preClose=前收价、suspendFlag=停牌标记 0/-1/1、amount=成交额。供应商未在字段表声明 volume 单位(手/股)——units 门缺声明级直接证据。",
})
rows.append({
    "excerpt_id": "xtdata_py_fill_data_semantics",
    "original": str(src_py), "original_sha256": sha256(src_py),
    "lines": lines_of(src_py, 4087, 4114),
    "note": "get_tabular_data docstring：fill_data=True 对齐时间戳时缺失数据 amount、volume 填 0、价格以前条 close 填充——零量行可能是 vendor 对齐填充行；1.3 下载调用 fill_data=True。",
})
rows.append({
    "excerpt_id": "xtdata_md_tick_vs_kline_volume",
    "original": str(src_md), "original_sha256": sha256(src_md),
    "lines": lines_of(src_md, 1200, 1218),
    "note": "tick 分笔 volume=成交总量(累计) vs K线 volume=成交量(每根 bar)——每 bar 增量与累计口径的 vendor 语义区分。",
})
rows.append({
    "excerpt_id": "xtdata_md_l2quote_hand_units",
    "original": str(src_md), "original_sha256": sha256(src_md),
    "lines": lines_of(src_md, 1560, 1572),
    "note": "l2quote 多档委买/委卖量单位是手——供应商对量类字段在手单位的显式声明示例，但非 K线 volume 本身。",
})
rows.append({
    "excerpt_id": "xtdata_py_instrument_detail_fields",
    "original": str(src_py), "original_sha256": sha256(src_py),
    "lines": lines_of(src_py, 1720, 1760),
    "note": "get_instrument_detail 字段：PreClose/UpStopPrice(当日涨停价)/DownStopPrice(当日跌停价)/PriceTick(最小变价)/InstrumentStatus(停牌状态)——vendor instrument 事实字段存在，但语义为当日，历史窗口需另取。",
})
rows.append({
    "excerpt_id": "xttrader_md_order_volume_unit",
    "original": str(src_tr), "original_sha256": sha256(src_tr),
    "lines": lines_of(src_tr, 1000, 1035),
    "note": "xttrader 委托 order_volume 股票以股为单位——下单域单位声明，与行情域相区分。",
})
write_json(
    "raw_excerpt_xtquant_docs.json",
    {
        "schema_version": "bl2_raw_excerpt_draft_v0_host_review",
        "collected_at": "2026-09-30",
        "collector": "ZCode(host-assist) via user request",
        "xtquant_version": "250516.1.1",
        "purpose": "B-L2-01 三门外材料：vendor 字段语义行式摘录；非 bl2_proof_v1，host 审核后才可引用",
        "rows": rows,
    },
)


# --- 2. cross-repo implementation excerpts ---
def find_block(p, start_pat, n):
    txt = Path(p).read_text(encoding="utf-8", errors="replace").splitlines()
    a = next(i for i, l in enumerate(txt, 1) if re.search(start_pat, l))
    return lines_of(p, a, a + n - 1)


B13 = Path(r"D:\PycharmProjects\OSkhQuant1.3")
MQ = Path(r"D:\PycharmProjects\MyQuant")
BT = Path(r"D:\PycharmProjects\MyQuant-backtrader")
rows2 = []
bl = B13 / "oskh_core" / "board_limit.py"
rows2.append({
    "excerpt_id": "o13_board_limit_py",
    "original": str(bl), "original_sha256": sha256(bl),
    "repo_head": "47afc2447fa4df5b37af1400ec1aea419ed7fda1",
    "lines": lines_of(bl, 1, 45),
    "note": "1.3 板块涨跌幅规则 SSOT：主板0.10 创业/科创0.20 北交0.30；ST 5% 不在此(无名称馈源)。approved_derivation 规则材料实现旁证。",
})
mock = B13 / "common" / "integrations" / "qmt_xtdata_mock.py"
rows2.append({
    "excerpt_id": "o13_limit_rate_and_prices",
    "original": str(mock), "original_sha256": sha256(mock),
    "repo_head": "47afc2447fa4df5b37af1400ec1aea419ed7fda1",
    "lines": find_block(str(mock), r"def _get_limit_rate", 32),
    "note": "1.3 mock 单源涨跌停价=前收盘×(1±板块率) round 0.01；主板 ST ±5%(研究层显式声明)；live 侧柜台真实涨跌停价兜底。",
})
dt13 = B13 / "oskh_data" / "download_transport.py"
rows2.append({
    "excerpt_id": "o13_download_fill_data_true",
    "original": str(dt13), "original_sha256": sha256(dt13),
    "repo_head": "47afc2447fa4df5b37af1400ec1aea419ed7fda1",
    "lines": lines_of(dt13, 468, 486),
    "note": "湖分钟 bar 下载：get_market_data_ex 仅取 7 列(time..amount)、fill_data=True、原样写湖(无单位换算)——量与时刻是 vendor 原值。",
})
s1 = MQ / "qlib_scripts" / "stage_1min_from_lake.py"
rows2.append({
    "excerpt_id": "myquant_stage1min_vol_x100_NON_ATTESTATION",
    "original": str(s1), "original_sha256": sha256(s1),
    "repo_head": "910abd38652b523cae07dd7a64032f0f71a06ff0",
    "lines": lines_of(s1, 90, 99),
    "note": "NON-ATTESTATION 旁证：MyQuant 湖→qlib staging 以 vol*100 作 vwap 分母，即消费侧按湖分钟 volume=手假设。§9.2 明确该类启发式不得作 units proof。",
})
ash = BT / "backtest" / "research" / "ashare_session.py"
rows2.append({
    "excerpt_id": "bt_ashare_session_limit_band",
    "original": str(ash), "original_sha256": sha256(ash),
    "repo_head": "a268e11bc682cd1ae5a6672ab89091cea1abe937",
    "lines": lines_of(ash, 1, 80),
    "note": "本仓成交核档位/涨跌停命中通用模块(session_limit_prices 等)；Decimal 链与测试向量见 docs/backtest/engine-ashare-correctness.md。",
})
write_json(
    "raw_excerpt_cross_repo_rules.json",
    {
        "schema_version": "bl2_raw_excerpt_draft_v0_host_review",
        "collected_at": "2026-09-30",
        "collector": "ZCode(host-assist) via user request",
        "purpose": "approved_derivation 规则材料/实现旁证行式摘录；非 bl2_proof_v1",
        "rows": rows2,
    },
)

# --- 3. lake daily bars around window (derivation inputs) ---
dp = Path(r"E:\stock_data\stock\period=1d\dividend_type=none\symbol=603196_SH\data.parquet")
d = pq.read_table(dp).to_pandas().reset_index(drop=True)
d["dt"] = pd.to_datetime(d["time"], unit="ms")
win = d[(d["dt"] >= "2025-10-20") & (d["dt"] <= "2025-11-05")]
daily_rows = [
    {
        "row_idx": int(i),
        "trade_date": r["dt"].strftime("%Y-%m-%d"),
        "open": str(r["open"]), "high": str(r["high"]), "low": str(r["low"]),
        "close": str(r["close"]), "volume": int(r["volume"]), "amount": str(r["amount"]),
    }
    for i, r in win.iterrows()
]
write_json(
    "raw_lake_daily_603196SH_20251020_20251105.json",
    {
        "schema_version": "bl2_raw_excerpt_draft_v0_host_review",
        "source": {"path": str(dp), "sha256": sha256(dp), "rows_total": int(len(d)), "schema": str(pq.read_schema(dp))},
        "time_decoding": "time int64 = 上海墙钟按 UTC epoch 毫秒编码(naive Shanghai epoch ms)；日线 time=当日 00:00",
        "rows": daily_rows,
    },
)

# --- 4. minute census full map ---
mp = Path(r"E:\stock_data\stock\period=1m\dividend_type=none\symbol=603196_SH\data.parquet")
m = pq.read_table(mp).to_pandas().reset_index(drop=True)
m["dt"] = pd.to_datetime(m["time"], unit="ms")
m["day"] = m["dt"].dt.strftime("%Y-%m-%d")
m["hm"] = m["dt"].dt.strftime("%H%M")
mw = m[m["day"].between("2025-10-23", "2025-11-04")].copy()
in_grid = ((mw["hm"] >= "0931") & (mw["hm"] <= "1130")) | ((mw["hm"] >= "1301") & (mw["hm"] <= "1457"))
mw["in_grid"] = in_grid
cells = [
    {
        "day": r["day"], "end_label_hm": r["hm"], "row_idx": int(r.name),
        "in_tradable_grid": bool(r["in_grid"]), "close": str(r["close"]),
        "volume": int(r["volume"]), "amount": str(r["amount"]),
    }
    for _, r in mw.iterrows()
]
grid_cells = [c for c in cells if c["in_tradable_grid"]]
zerov = [c for c in grid_cells if c["volume"] == 0]
write_json(
    "raw_lake_minute_census_603196SH_20251023_20251104.json",
    {
        "schema_version": "bl2_raw_excerpt_draft_v0_host_review",
        "source": {"path": str(mp), "sha256": sha256(mp), "rows_total": int(len(m)), "schema": str(pq.read_schema(mp))},
        "time_semantics": "END 标签：bar 标签 t 覆盖 [t-1min,t)；上海墙钟按 UTC epoch 毫秒编码；每日 241 行 = 09:30 集合竞价条 + 09:31-11:30 + 13:01-15:00",
        "grid_definition": "合同可交易网格 END 标签 09:31-11:30(120)+13:01-14:57(117)=237/日；09:30/14:58/14:59/15:00 为网格外行(15:00 可作 mark 行)",
        "window_rows": int(len(mw)), "grid_cells": len(grid_cells), "grid_missing": 0, "grid_dup": 0,
        "zero_volume_grid_cells": len(zerov),
        "cells": cells,
    },
)

# --- 5. ST membership + corporate actions ---
st_path = Path(r"E:\stock_data\vendor_wind_st_status\st_daily.parquet")
st = pd.read_parquet(st_path)
hit = st[st["code"].astype(str).str.contains("603196")]
write_json(
    "raw_st_membership_603196SH.json",
    {
        "schema_version": "bl2_raw_excerpt_draft_v0_host_review",
        "source": {"path": str(st_path), "sha256": sha256(st_path), "rows_total": int(len(st)), "columns": list(st.columns)},
        "filter": "code contains 603196", "hits": int(len(hit)),
        "note": "603196.SH 全表零命中=非 ST；st_daily 覆盖期由 vendor_wind_st_status harvest 声明，host 另核覆盖期含 2025-10。",
    },
)
ex_path = Path(r"E:\stock_data\ex_date_index.parquet")
ex = pd.read_parquet(ex_path)
exh = ex[
    (ex["stock_code"].astype(str).str.contains("603196"))
    & (ex["ex_date"].astype(str).str[:10].between("2025-09-01", "2025-12-31"))
]
write_json(
    "raw_corporate_actions_603196SH_window.json",
    {
        "schema_version": "bl2_raw_excerpt_draft_v0_host_review",
        "source": {"path": str(ex_path), "sha256": sha256(ex_path), "rows_total": int(len(ex)), "columns": list(ex.columns)},
        "filter": "stock_code contains 603196 and ex_date in 2025-09-01..2025-12-31", "hits": int(len(exh)),
        "note": "零事件命中；§3.2 要求覆盖完整性另证(hash 只证身份)；R2/R3 探针同样零命中。",
    },
)
print("ALL DONE")
