# Plan：名单源 B（技术分析 → 契约日 CSV）

> **落盘**：2026-09-13。
> **状态**：📄 **v1.0 · 计划，等人裁 GO 再编码**。
> **风险档**：**L1**（导出胶水 + 注入单测；不重写成交核、不改卖点、不写 `stock_pool/`、不 `import qlib`）。
> **范围**：本仓。MyQuant / 1.3 只读。
> **上游**：三仓路线图 §1 / §2.2（名单多源、同一契约）；[engine-positioning-ssot.md](engine-positioning-ssot.md) 源 B；契约 [pool-csv-contract.md](pool-csv-contract.md)。
> **前序**：R2 导出住 MyQuant；本仓只消费。M5 二轮（[#30](https://github.com/baiyibing/MyQuant-backtrader/pull/30)）证明 pred 与手工 `stock_pool/` **同日零交集**——手工不是可复现的源 B。

---

## 0. 一句话

把本仓**已经存在**的换手阻力过滤，写成和 Qlib 导出同一套 `YYYYMMDD.csv`。下游 6/8 只认契约，不认来源。本轮验收管道，不验收「比 pred 好」。

```text
湖日线宇宙（或注入代码表）
        ↓  TurnoverResistanceStore.load_cross_section(T, window=1000, require_bands=True)
        ↓  apply_turnover_resistance_filter(..., rule=resist_tr_bb_1000)
        ↓  裸六位、LF、无 BOM、无表头
exports/src_b_tr_bb1000_{start}_{end}/   （gitignore；禁止写 stock_pool/）
        ↓  可选后置：m5_hand_topn --k 10
csv_daily --strategy version6 --pool-dir <src_b>
```

---

## 1. 现状（禁止当本轮发明）

| 已有 | 不是源 B 的原因 |
|------|----------------|
| `stock_pool/` | 隔夜短线池，会续写；M5 二轮已冻结对照，仍与 pred 同日零交集 |
| MyQuant `export_daily_pool.py` | 源 A。禁止本仓第二份 Qlib 导出 |
| `scripts/misc/export_stock_pool_daily.py` | 按**已有**名单抽湖 K，不产生名单 |
| `ma_chip_edge_backtest.py` | Cerebro 化石路径；开盘买、不是日 CSV 源 |
| `full_market_chip_resist.py` | 单日宽表，不是契约池 |
| `strategies.tr_filter.apply_turnover_resistance_filter` | **过滤**，缺「宇宙 → 写盘」 |
| `oskh_data.turnover_resistance_store.TurnoverResistanceStore` | 已有 `load_cross_section`；生产要 bands |
| 标定 [tr_filter_resist_tr_bb_1000_calibration.md](chip/tr_filter_resist_tr_bb_1000_calibration.md) | 阈值已写：\|TR\|>20、bb≥0.5、tr_bb>0.5 |

M2 已判 BT 筹码与 MyQuant COST **不可比**。源 B 只用本仓 TR / store，不接对方 bin 字段。

---

## 2. 现锁（B-R*）

| ID | 锁 |
|----|----|
| **B-R1** | 输出字节与 R2 相同：`YYYYMMDD.csv`；utf-8 **无 BOM**；**LF**；**无表头**；每行恰好裸六位。`validate_pool_dir=[]`。当日 0 只过线 → **不写文件**（与 R2 空日一致）。 |
| **B-R2** | 文件名 = 买入日 T。计算只用 `date<=T` 的 K / 截面 / 名称（与 `name_asof` 同向）。6/8「当天读当天文件」、收盘成交。这不是 Qlib 的 `pred_minus_one`，禁止套用、禁止重开 `--asof`。 |
| **B-R3** | v0 **唯一**规则：`resist_tr_bb_1000`（`window=1000`，`apply_turnover_resistance_filter`）。禁止本轮新规则、新阈值、`resist_tr_bb_80`、`tr_breakout`、ma+chip 边缘。改规则须改本文另开片。 |
| **B-R4** | 候选宇宙默认 = 湖 `period=1d` 在 T 有 K 的代码（经现有 resolver，禁止盘符字面量）。允许 `--universe-file` 注入。禁止用 `stock_pool/` 或 pred 目录当默认宇宙（那是对照源，不是生成输入）。 |
| **B-R5** | `load_cross_section` 必须可注入。CI / 合入门只跑 fixture（假截面 → 契约字节）。全市场 1000 窗实跑是宿主，**不是**合入门。fail-closed 与现网 `tr_filter` 默认一致（缺行/空表失败，不静默放行）。 |
| **B-R6** | v0 **不**做 TopK：过线几只写几只，报告写每日宽度。宽度要对齐 pred 时，后置已有 `m5_hand_topn.py --k 10`（保序 = filter 输出序）。若加 `--topk`，必须在 help 写死排序键（建议 `\|turnover_resistance\|` 降序，并列用代码升序）；本轮不做 `--topk` 也算 A–C 完成。 |
| **B-R7** | 默认 `--out-dir exports/src_b_tr_bb1000_{start}_{end}/`。`refuses_stock_pool`。不写两仓 `stock_pool/`。不喂策略 7。 |
| **B-R8** | 完成定义 = 契约绿 +（宿主）至少一窗 `validate` + 一趟 `csv_daily --strategy version6 --out-dir` 出 `summary.txt`。禁止用该窗 NAV / 与 pred 重叠度宣称规则有效。对照列后置，不进本轮。 |

代码方言：store / filter 侧若给 `600000.SH`，写出前收成裸 `600000`（可复用现有 `_cell_to_bare` / `canonical` 的逆操作，禁止新方言）。

---

## 3. 非目标

| 不做 | 原因 |
|------|------|
| 改 `csv_ledger` / `presets` / 1–8 卖点 / v7 | 源，不是成交核 |
| 本仓 `import qlib` / 第二份 pred 导出 | 源 A 住 MyQuant |
| 写 `stock_pool/` 或当隔夜池 SSOT | 研究导出与交易日更池隔离 |
| 复活 Cerebro `ma_chip_edge` 当源 B | 化石；开盘语义不同 |
| 统一 MyQuant COST 与 `qlib_cost` | M2 不可比已关门 |
| 本轮 M5 四列（pred / 手工 / 源 B / 源 B Top10） | 先有可复现目录 |
| L2 / 1.3 `trade_decision` | 晋升链未到 |
| 为「每天全市场 1000 窗」做性能项目 | 宿主后置；Rust 已有，不本轮重写 |

---

## 4. 切片

从**当时 master** 开 `feat/source-b-ta-pool`。本 docs 分支只写计划。

| 切片 | 做什么 | 完成定义 |
|------|--------|----------|
| **A · 写盘纯函数** | `scripts/data/export_ta_pool.py`：`rows→YYYYMMDD.csv`；拒绝 `stock_pool/` | 夹具 2 日；字节契约；空日无文件 |
| **B · 接 filter** | 注入 `cross_section` + `candidates` → `apply_turnover_resistance_filter` → A | 单测：过线 / 未过线 / fail-closed 空表；不碰湖 |
| **C · CLI** | `--start/--end/--out-dir/--universe-file`；live 才调 store | `--help` 写 B-R2/B-R3；`--universe-file` 无 store 可跑通 B |
| **D · 文档** | README SSOT 一行；本文标已实施 | review |
| **E · 宿主烟测**（非合入门） | 短窗或单日真 store → `validate` → `csv_daily version6 --out-dir` | `summary.txt`；数字不入库 |

A/B 分 commit。E 不阻塞合入。

```text
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_export_ta_pool.py tests/test_selector_tr_filter.py
```

---

## 5. 代码落点（实施分支）

| 文件 | 动作 |
|------|------|
| `scripts/data/export_ta_pool.py` | **新建** |
| `tests/test_export_ta_pool.py` | **新建** |
| `docs/backtest/README.md` | D：链本文 |
| `strategies/tr_filter.py` / store | **默认不改**；缺的只加调用，不改阈值 |

禁止改：`csv_ledger.py`、`presets.py`、`csv_strategy_books.py`、v7、`--asof`、`docs/architecture/reviews/**`、MyQuant 仓。

---

## 6. 风险

- 全市场 `window=1000` + bands 可能慢或缺截面日；E 允许单日 / 小宇宙，缺日不写文件。
- filter 输出序是否稳定：并列时按代码排序后再写（B-R6 后置 TopN 才有意义）。
- 过线宽度可能 ≫10 或整天为 0；v0 如实写，不要为凑 10 只放宽阈值。
- 源 B 与 pred / 手工仍可能同日零交集——那是下一轮对照的合法结论，不是本轮失败。

---

## 7. 修订程序

改 B-R* 须改本文。改买入日语义须改 [pool-csv-contract.md](pool-csv-contract.md)。新规则（80 窗 / breakout / 均线+盈筹）另开 plan，不塞进 v0。
