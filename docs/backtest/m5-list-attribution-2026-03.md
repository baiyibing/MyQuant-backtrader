# M5 名单归因（2026-03 窗 · version6）

> **落盘**：2026-09-13。C 本机补跑同日。
> **计划 SSOT**：[plan-m5-list-attribution-2026-09-13.md](plan-m5-list-attribution-2026-09-13.md)（[#26](https://github.com/baiyibing/MyQuant-backtrader/pull/26)）。工具链 [#27](https://github.com/baiyibing/MyQuant-backtrader/pull/27)。
> **书 / 窗**：`version6`；`20260303`–`20260323`（15 个买入日文件）。`--asof` 维持 `pred_minus_one`，不重开。
> **不做**：R0 / `exports/r0_*`、PortAna / Cerebro 净值、改卖点、改 `--asof`、把 16 天净值当模型晋升。

同一本 version6 书、同一资金、同一买入日窗，只换名单。三列已齐（M5-R1）：

| 列 | 名单 | 输入 | `--out-dir` |
|----|------|------|-------------|
| ① | R3 后 pred TopN（`--topk 10`） | `exports/r2_pred_topn_r3_20260303_20260323/`（gitignore） | `backtest_output/m5_pred_r3_20260303_20260323/` |
| ② | `stock_pool/` 原样 | 本仓工作区当时内容，不是 2026-03 冻结快照 | `backtest_output/m5_hand_20260303_20260323/` |
| ③ | 手工池按文件原序截断 TopN（K=10） | `exports/m5_hand_top10_20260303_20260323/`（gitignore） | `backtest_output/m5_hand10_20260303_20260323/` |

`validate_pool_dir`：① 与 ③ 均为 `[]`。产物不入库。

---

## 0. 谁跑了什么

实施仓 Linux VM 无 F 湖、无 R3 pred，C 跳过（[#27](https://github.com/baiyibing/MyQuant-backtrader/pull/27)）。本机 2026-09-13 用第 4 轮 `预测结果.csv`（mtime 2026-09-12 23:45，83903 行）重导 ①，并用已合入的 `m5_hand_topn.py` / `--out-dir` 跑齐三列。数字照抄三份 `summary.txt`，不四舍五入成输赢。

手工截断宽度：15 个文件；`20260317`=9、`20260323`=8，其余 10。

---

## 1. M5-R6 三件套

只写本仓向量化数字。禁止 PortAna IR / 基准收益，禁止与 pre-R3 / R0 窗净值横比。

| 列 | 名单 | 池天数 | 加载代码 | 买入 | 卖出桶 | 涨停跳过 | 全资金收益 | 动用资金收益 | 最大回撤 | 来源 |
|----|------|--------|----------|------|--------|----------|------------|--------------|----------|------|
| ① | R3 pred Top10（`pred_minus_one`） | 15 | 95 | 123 | 止损 55 / 锚定回撤 55 | 1 | −1.25% | −2.15% | −1.37% | 本机 C 2026-09-13；`m5_pred_r3_…/summary.txt` |
| ② | `stock_pool/` 原样 | 15 | 329 | 317 | 止损 161 / 锚定回撤 137 | 67 | −1.21% | −2.20% | −1.24% | 同上；`m5_hand_…/summary.txt` |
| ③ | 手工截断 Top10 | 15 | 127 | 124 | 止损 61 / 锚定回撤 48 | 21 | −1.66% | −2.78% | −1.65% | 同上；`m5_hand10_…/summary.txt` |

期末净值（/ 21,000,000）：① 20,738,198.69；② 20,745,919.55；③ 20,651,935.95。跌停顺延卖出：① 1、② 1、③ 0。

① vs ② 净值接近（−1.25% vs −1.21%）是巧合：② 更宽、涨停跳过 67 vs 1。宽度对齐后 ③ 是 −1.66%，不再贴着 ①。这仍不是「模型优于手工」。

---

## 2. 逐日交集

用 `parse_pool_csv` 后的裸六位。

| 对照 | 池天数 | ∩=0 的天数 | 非零日 | 宽度 |
|------|--------|------------|--------|------|
| pred ∩ hand | 15 | 14 | 仅 `20260309` ∩=1（`600546`） | hand 8–49，pred 固定 10 |
| pred ∩ hand10 | 15 | **15** | 无 | hand10 8–10；`600546` 不在该日前 10 |

---

## 3. M5-R7 结论

**名单几乎不重叠。**

15 个买入日 pred ∩ hand 有 14 天空集；宽度对齐后 pred ∩ hand10 **15 天全空**（唯一交点被截掉）。这是两套选股宇宙，不是同一宇宙里的排序好坏。

② 的净值不能用来比名单（宽池 + 涨停摩擦）。③ 补齐后，① vs ③ 仍禁止读成模型晋升：窗只有 16 个交易日，宇宙不重叠，手名单也不是当时冻结快照。

禁止的说法（本报告未使用）：「模型优于手工」「策略 6 失效」。

---

## 4. 已执行的 C 命令

```text
# MyQuant pred → 本仓 exports（目录名带 r3）
python my_scripts/export_daily_pool.py --pred my_scripts\预测结果.csv --topk 10 --asof pred_minus_one --out-dir <this-repo>/exports/r2_pred_topn_r3_20260303_20260323

python scripts/data/m5_hand_topn.py --start 20260303 --end 20260323 --k 10

python backtest/research/csv_daily_backtest.py --strategy version6 --start 20260303 --end 20260323 --pool-dir exports/r2_pred_topn_r3_20260303_20260323 --out-dir backtest_output/m5_pred_r3_20260303_20260323
python backtest/research/csv_daily_backtest.py --strategy version6 --start 20260303 --end 20260323 --pool-dir stock_pool --out-dir backtest_output/m5_hand_20260303_20260323
python backtest/research/csv_daily_backtest.py --strategy version6 --start 20260303 --end 20260323 --pool-dir exports/m5_hand_top10_20260303_20260323 --out-dir backtest_output/m5_hand10_20260303_20260323
```
