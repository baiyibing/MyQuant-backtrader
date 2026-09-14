# Plan：名单源 B（技术分析 → 契约日 CSV）

> **落盘**：2026-09-13。
> **状态**：✅ **已实施**（A–C 夹具已合 [#32](https://github.com/baiyibing/MyQuant-backtrader/pull/32)；E 宿主烟测 2026-09-13 已跑，不是合入门，见 [s9-s10-host-smoke-2026-09-13.md](s9-s10-host-smoke-2026-09-13.md)）。
> **风险档**：**L1**（导出胶水 + 注入单测；不重写成交核、不写 `stock_pool/`、不 `import qlib`）。
> **范围**：本仓。MyQuant / 1.3 只读。
> **上游**：[#31](https://github.com/baiyibing/MyQuant-backtrader/pull/31) 计划原文。下游书号落成 **version10**（卖点复用 6）；契约 CSV 仍可喂 version6/8。
> **前序**：R2 导出住 MyQuant。手工 `stock_pool/` 不是可复现的源 B。

---

## 0. 一句话

把本仓**已经存在**的换手阻力过滤，写成和 Qlib 导出同一套 `YYYYMMDD.csv`。下游只认契约，不认来源。本轮验收管道，不验收「比 pred 好」。

```text
湖日线宇宙（或 --universe-file）
        ↓  注入截面 或 Store.load_cross_section(T, window=1000, require_bands=True)
        ↓  apply_turnover_resistance_filter(..., rule=resist_tr_bb_1000)
        ↓  裸六位、LF、无 BOM、无表头
exports/src_b_tr_bb1000_{start}_{end}/
        ↓  可选后置：m5_hand_topn --k 10
csv_daily --strategy version10 --pool-dir <src_b>
# 契约同样可喂 version6 / version8
```

入口：`scripts/data/export_ta_pool.py`（`export_strategy10_pool.py` 同入口）。

---

## 1. 现锁（B-R*）— 人裁确认的三句未改

| ID | 锁 |
|----|----|
| **B-R1** | 输出字节与 R2 相同：`YYYYMMDD.csv`；utf-8 **无 BOM**；**LF**；**无表头**；裸六位。`validate_pool_dir=[]`。0 只过线不写文件。 |
| **B-R2** | 文件名 = 买入日 T。只用 `date<=T` 的 K / 截面。不是 Qlib `pred_minus_one`，无 `--asof`。 |
| **B-R3** | v0 **唯一**规则：`resist_tr_bb_1000`（`window=1000`）。 |
| **B-R4** | 默认宇宙 = 湖 `period=1d` 在 T 有 K 的代码。`--universe-file` 注入。禁止默认 `stock_pool/` / pred。注入截面时必须同时给宇宙，禁止用截面成员冒充湖。 |
| **B-R5** | `load_cross_section` 可注入。CI 只跑 fixture。全市场 1000 窗不是合入门。宇宙非空而截面为空 / 缺行 → fail-closed。 |
| **B-R6** | v0 **不**做 TopK。过线几只写几只，`widths.txt` 记每日宽度。对齐宽度后置 `m5_hand_topn.py --k 10`。无 `--topk`。 |
| **B-R7** | 默认 `--out-dir exports/src_b_tr_bb1000_{start}_{end}/`。拒绝 `stock_pool/`。不喂策略 7。 |
| **B-R8** | 完成 = 夹具绿。宿主 `validate` + `csv_daily` 是 E，不是合入门。禁止用 NAV 宣称规则有效。 |

---

## 2. 切片

| 切片 | 状态 |
|------|------|
| **A · 写盘** | 已做：`write_tr_pool` |
| **B · 接 filter** | 已做：`scan_tr_days` + 注入截面 |
| **C · CLI** | 已做：`export_ta_pool.py` |
| **D · 文档** | 本文 + README |
| **E · 宿主烟测** | 2026-09-13 已跑：活 Store 缺带 fail-closed；湖⊃Store 缺行 fail-closed；带副本 + 宇宙⊆截面可出票。数字见烟测文。仍非合入门 |

```text
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_export_ta_pool.py tests/test_selector_tr_filter.py tests/test_strategy10_tr_pool.py
```
