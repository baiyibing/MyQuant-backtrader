# Plan：M5 名单归因（R3 pred TopN vs 手工池；同一 version6 书）

> **落盘**：2026-09-13。
> **状态**：📄 **v1.0 · 工具链已合 [#27](https://github.com/baiyibing/MyQuant-backtrader/pull/27)；C 本机补跑已合 [#28](https://github.com/baiyibing/MyQuant-backtrader/pull/28)，数字在 [m5-list-attribution-2026-03.md](m5-list-attribution-2026-03.md)**。
> **后续**：长窗二轮见 [plan-m5-round2-2026-09-13.md](plan-m5-round2-2026-09-13.md)。不重开本文件 M5-R*。
> **风险档**：**L1**（对照跑 + 落盘隔离 + 宽度对齐；不重写引擎、不改卖点、不用 PortAna/R0 净值验收）。
> **范围**：本仓为主。MyQuant 只读：R3 之后的 `预测结果.csv` + 已有 `export_daily_pool.py`。
> **前序**：R2/R5 管道 [#24](https://github.com/baiyibing/MyQuant-backtrader/pull/24)；R3 厂 [#25](https://github.com/baiyibing/MyQuant-backtrader/pull/25) / MyQuant [#3](https://github.com/baiyibing/MyQuant/pull/3)。第 4 轮重训 2026-09-12 23:45 写出新 `预测结果.csv`（83903 行 / 16 日；pre-R3 为 87363 行，score 相关约 0.65）。
> **不做**：再开 R3、改 `--asof`、用 `exports/r0_*`、用 pre-R3 pred、用 Qlib PortAna 净值当对照。

---

## 0. 一句话

同一本 version6 书、同一资金、同一买入日窗，只换名单，看「Qlib 严格 TopN」和「本仓手工 `stock_pool/`」差在名单，不差在成交核。宽度必须对齐后再谈净值。

```text
R3 预测结果.csv
        ↓  已有 R2  --asof pred_minus_one --topk 10
exports/r2_pred_topn_r3_*          （10 码/日，15 个买入日文件）
        ↓  csv_daily --strategy version6 --out-dir <pred>

stock_pool/YYYYMMDD.csv            （8–49 码/日，几乎与 pred 无交集）
        ↓  原样跑 + 另切每日前 10 码再跑
        ↓  csv_daily --strategy version6 --out-dir <hand> / <hand10>
```

---

## 1. 本机已测到的事实（不是锁，禁止当完成定义）

2026-09-13 本机预跑（产物不入库；默认落盘路径会互盖，已拷走）：

| 名单 | 池天数 | 加载代码 | 买入 | 涨停跳过 | 全资金收益 | 最大回撤 |
|------|--------|----------|------|----------|------------|----------|
| R3 pred Top10（`pred_minus_one`） | 15 | 95 | 123 | 1 | −1.25% | −1.37% |
| `stock_pool/` 原样 | 15 | 329 | 317 | 67 | −1.21% | −1.24% |

逐日交集：15 天里 14 天交集为 0，仅 `20260309` 交集 1。手工池宽度 8–49，pred 固定 10。**这两条净值不能直接当「谁的名单更好」。** PortAna 里那组 IR / 基准收益是 Qlib 收盘账，禁止写进 M5 表当对照列。

`--asof` 维持 `pred_minus_one`。第 4 轮 `[alignment] pred 16d vs report 16d` 是 Qlib 自己的 pred/报告索引，不是本仓买入日文件名，**不要据此改成 identity**。

---

## 2. 非目标 / 禁改

| 不做 | 原因 |
|------|------|
| 改 `execute_buy` / `_sell` / 1–8 卖点 / `presets.py` / 策略 7 | 归因轮，不是成交核 |
| 用 R0 持仓 CSV | 已实现持仓 ≠ 当日信号 |
| 用 `预测结果.pre-r3-*.csv` | 脏工厂 |
| 把 PortAna / Cerebro 净值塞进对照表 | 第四套引擎禁令 |
| 改 `--asof` 默认或重开 Q3 | R2 已锁 |
| 把 16 天净值当模型晋升 / M3 | 窗太短；只归因名单 |
| 提交 `exports/`、`backtest_output/`、真 pred | gitignore |
| 在本仓 `import qlib` | 导出住 MyQuant |
| 等 `F:\qlibdata` 重灌再开 M5 | 2026-03 窗 pred 已够；灌数是 MyQuant 线 |

---

## 3. 现锁（M5-R*）

| ID | 锁 |
|----|----|
| **M5-R1** | 三列对照，缺一不算完成：① R3 后 pred TopN；② `stock_pool/` 原样；③ 手工池按文件原序截断为每日 TopN（默认 10，与 R2 `--topk` 相同）。禁止只比 ① vs ② 的净值。 |
| **M5-R2** | 书 = `version6`；窗 = 导出后 **pred 目录实际存在的首末文件名**（H0 下现为 `20260303`–`20260323`）。三列同一 `--start/--end`、同一 `--cash-total` / `--daily-quota`。version8 可选，另目录。不喂 7。日线。 |
| **M5-R3** | pred 输入必须是 R3 第 4 轮之后的 `my_scripts/预测结果.csv`（mtime ≥ 2026-09-12 23:45 或行数约 8.4 万）。`--asof pred_minus_one --topk 10`。输出目录名带 `r3`，禁止覆盖/误用 `exports/r0_*`。 |
| **M5-R4** | `csv_daily_backtest.py` 增加 `--out-dir`（可选）。缺省行为保持 `backtest_output/csv_daily_{book}_{start}_{end}/`。M5 三列必须显式 `--out-dir`，禁止互盖。 |
| **M5-R5** | 手工 TopN：`scripts/data/m5_hand_topn.py` 读 `stock_pool/YYYYMMDD.csv`，用现有 `parse_pool_csv` 保序，每文件取前 K 个裸六位，utf-8 无 BOM、无表头、LF。不写 `stock_pool/`。默认 `exports/m5_hand_top10_{start}_{end}/`（已 gitignore）。 |
| **M5-R6** | 报告只写本仓三件套数字：全资金收益、动用资金收益、最大回撤、买入/卖出桶、涨停跳过、加载代码数、池天数。外加「逐日 pred∩hand、pred∩hand10」。禁止 PortAna IR、禁止与 pre-R3 / R0 窗净值横比当结论。 |
| **M5-R7** | 结论允许且只允许三种：名单几乎不重叠 / 宽度主导 / 宽度对齐后仍分不出。禁止「模型优于手工」或「策略 6 失效」。 |

---

## 4. 切片

从当前 master（#25 / `da95936` 之后）开 `feat/m5-list-attribution`。不要在本 docs 分支改业务代码。

| 切片 | 做什么 | 完成定义 |
|------|--------|----------|
| **A · 落盘隔离** | `csv_daily_backtest.py` `--out-dir` | 指定则写入该目录；不指定旧路径不变。单测或最小 CLI 测即可 |
| **B · 手工 TopN** | `scripts/data/m5_hand_topn.py` + 单测 | 夹具 15 行截成 10；保序；不写 `stock_pool/` |
| **C · 三列实跑** | pred / hand / hand10 各一趟 version6 | 三个 `--out-dir` 都有 `summary.txt`；`validate_pool_dir` 对 pred 与 hand10 为空。产物不入库 |
| **D · 报告** | `docs/backtest/m5-list-attribution-2026-03.md` | 填 M5-R6 表 + 逐日交集 + M5-R7 三选一结论。链本文 |

A 与 B 分 commit。C 不提交数字文件，只在 D 摘录。

```text
D:\anaconda3\envs\vanna312\python.exe -m pytest -q tests/test_m5_hand_topn.py tests/test_csv_daily_outdir.py
```

（文件名实施时可合并。）

---

## 5. 代码落点

| 文件 | 动作 |
|------|------|
| `backtest/research/csv_daily_backtest.py` | A：`--out-dir` |
| `scripts/data/m5_hand_topn.py` | **新建** B |
| `tests/test_m5_hand_topn.py` 等 | A/B |
| `docs/backtest/m5-list-attribution-2026-03.md` | **新建** D |
| `docs/backtest/README.md` | D：SSOT 一行（本 PR 已链 plan） |

禁止改：`csv_ledger.py` 成交公式、`presets.py`、`csv_strategy_books.py`、v7、`export_daily_pool.py`、`--asof`、`docs/architecture/reviews/**`。

---

## 6. 风险

- 手工池与 pred 几乎不重叠：归因的是「两套选股」，不是「同一宇宙里排序好坏」。
- 手工原样列更宽、涨停跳过更多，净值会被宽度和涨停摩擦拖动。
- `stock_pool/` 不是 2026-03 当时冻结快照（仓内会续写）。M5 报告必须写清所用日期与「当时工作区内容」，不要假装历史复现。
- 本机 `OSKH_PERIOD_*` 已指向 F，湖警告可忽略只要 1d 分区在。

---

## 7. 修订程序

改 M5-R* 须改本文。改买入日语义须改 [pool-csv-contract.md](pool-csv-contract.md) 与 [plan-pool-pipeline-r2r5-2026-09-12.md](plan-pool-pipeline-r2r5-2026-09-12.md)。

---

## 8. Codex 工作方式

1. 从本仓当前 master 开 `feat/m5-list-attribution`。不要改 MyQuant 训练脚本。
2. A → B → C → D。不要提交 `exports/` / `backtest_output/`。
3. UTF-8 无 BOM，NUL=0。Python：`D:\anaconda3\envs\vanna312\python.exe`。
4. 三列净值写入 D 时照抄 `summary.txt`，不要四舍五入成「谁赢了」。
