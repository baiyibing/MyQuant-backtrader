# M5 名单归因（2026-03 窗 · version6）

> **落盘**：2026-09-13。
> **计划 SSOT**：[plan-m5-list-attribution-2026-09-13.md](plan-m5-list-attribution-2026-09-13.md)（合入 [#26](https://github.com/baiyibing/MyQuant-backtrader/pull/26)）。
> **书 / 窗**：`version6`；买入日按 pred 导出文件名，H0 现为 `20260303`–`20260323`（15 个文件）。`--asof` 维持 `pred_minus_one`，本轮不重开。
> **不做**：R0 / `exports/r0_*`、PortAna / Cerebro 净值、改卖点、改 `--asof`、把 16 天净值当模型晋升。

同一本 version6 书、同一资金、同一买入日窗，只换名单。三列缺一不算完成（M5-R1）：

| 列 | 名单 | 输入 |
|----|------|------|
| ① | R3 后 pred TopN（`--topk 10`） | `exports/r2_pred_topn_r3_*`（本 VM **无** 该目录，也无 `预测结果.csv`） |
| ② | `stock_pool/` 原样 | 本仓工作区当时内容，不是 2026-03 冻结快照 |
| ③ | 手工池按文件原序截断 TopN（K=10） | `scripts/data/m5_hand_topn.py` → `exports/m5_hand_top10_20260303_20260323/`（gitignore，不入库） |

三列必须显式 `--out-dir`，禁止互盖（M5-R4）。

---

## 0. 本 VM 与本机预跑

实施仓是 Linux VM。日线湖 `resolve_period_root("1d")` → `/workspace/OSkhQuant1.3/stock_data/stock/period=1d` **不存在**。对 ③ 的探测跑（`--pool-dir exports/m5_hand_top10_20260303_20260323 --out-dir backtest_output/m5_hand10_probe_vm`）在 `loaded 0/127 daily series, 15 pool days` 后 `SystemExit: no daily bars in window`。与 [#24](https://github.com/baiyibing/MyQuant-backtrader/pull/24) R2 湖缺口同一模式。**本轮 C 未出三份 `summary.txt`，禁止把下面 ①② 预跑数字当合入门或当本 VM 实跑。**

本机 2026-09-13 已测 ①②（产物不入库；当时默认落盘会互盖，已拷走）。③ 等 host 在 `--out-dir` + `m5_hand_topn` 落地后补跑。

本 VM 已做、可复核的工具产物（不入库）：

- `m5_hand_topn.py --start 20260303 --end 20260323 --k 10` 写出 15 个 CSV
- `validate_pool_dir(exports/m5_hand_top10_20260303_20260323)` = `[]`
- 手工原样宽度 8–49；截断后 8–10（`20260317`=9，`20260323`=8，其余 10）

---

## 1. M5-R6 三件套

只写本仓向量化数字。禁止 PortAna IR / 基准收益，禁止与 pre-R3 / R0 窗净值横比。

| 列 | 名单 | 池天数 | 加载代码 | 买入 | 卖出桶 | 涨停跳过 | 全资金收益 | 动用资金收益 | 最大回撤 | 来源 |
|----|------|--------|----------|------|--------|----------|------------|--------------|----------|------|
| ① | R3 pred Top10（`pred_minus_one`） | 15 | 95 | 123 | pending | 1 | −1.25% | pending | −1.37% | **本机预跑** 2026-09-13；preview，非合入门、非本 VM 实跑 |
| ② | `stock_pool/` 原样 | 15 | 329 | 317 | pending | 67 | −1.21% | pending | −1.24% | 同上 |
| ③ | 手工截断 Top10 | 15 | pending | pending | pending | pending | pending | pending | pending | 本 VM 无日线湖，未出 `summary.txt`；**不编造 hand10 净值** |

卖出桶与动用资金收益本机预跑未摘进计划表，标 pending，等 host 三份 `summary.txt` 照抄补齐。净值两列接近（−1.25% vs −1.21%）是巧合，不是结论。

---

## 2. 逐日交集

| 对照 | 池天数 | ∩=0 的天数 | 非零日 | 宽度 |
|------|--------|------------|--------|------|
| pred ∩ hand | 15 | 14 | 仅 `20260309` ∩=1 | hand 8–49，pred 固定 10 |
| pred ∩ hand10 | 15 | pending | pending | hand10 8–10（本 VM 截断结果）；交集等 pred 目录 |

pred ∩ hand 来自**本机预跑**，本 VM 无 pred 目录，不能复算。pred ∩ hand10 必须等 host 用同一份 R3 导出再数；即使 `20260309` 那 1 码落在手工前 10，14 天仍是空集。

---

## 3. M5-R7 结论

**名单几乎不重叠。**

15 个买入日里 14 天 pred ∩ hand = 0，只在 `20260309` 交 1 码。这是两套选股宇宙，不是同一宇宙里的排序好坏。手工原样更宽（8–49 vs 固定 10）且涨停跳过更多（67 vs 1），① vs ② 的净值不能用来比名单。宽度对齐后的 ③ 还没有 `summary.txt`，因此现在不能改口成「宽度主导」或「宽度对齐后仍分不出」。host 补跑 hand10 之前，不要把 −1.25% / −1.21% 读成谁好谁坏。

禁止的说法（本报告未使用）：「模型优于手工」「策略 6 失效」。

---

## 4. Host 补齐 C 的命令

pred 必须是 R3 第 4 轮之后的 `my_scripts/预测结果.csv`（mtime ≥ 2026-09-12 23:45 或约 8.4 万行）。输出目录名带 `r3`，不要碰 `exports/r0_*`。

```text
python my_scripts/export_daily_pool.py --pred my_scripts\预测结果.csv --topk 10 --asof pred_minus_one --out-dir exports/r2_pred_topn_r3_20260303_20260323

python scripts/data/m5_hand_topn.py --start 20260303 --end 20260323 --k 10

python backtest/research/csv_daily_backtest.py --strategy version6 --start 20260303 --end 20260323 --pool-dir exports/r2_pred_topn_r3_20260303_20260323 --out-dir backtest_output/m5_pred_r3_20260303_20260323
python backtest/research/csv_daily_backtest.py --strategy version6 --start 20260303 --end 20260323 --pool-dir stock_pool --out-dir backtest_output/m5_hand_20260303_20260323
python backtest/research/csv_daily_backtest.py --strategy version6 --start 20260303 --end 20260323 --pool-dir exports/m5_hand_top10_20260303_20260323 --out-dir backtest_output/m5_hand10_20260303_20260323
```

`validate_pool_dir` 对 pred 与 hand10 应为 `[]`。把三份 `summary.txt` 的全资金 / 动用资金 / 回撤 / 买卖桶 / 涨停跳过 / 加载代码 / 池天数照抄回 §1，把 pred ∩ hand10 填进 §2。产物不入库。
