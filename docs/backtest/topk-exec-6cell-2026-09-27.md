# TopK 分钟执行六格敏感性记录（20260927c）

日期：2026-09-27（Asia/Shanghai）。本页归档 4090 物理湖 Human-GO 的 P3 六格跑数回报；
实现依据 [P3 说明](topk-exec-p3-2026-09-27.md)，对应
[计划 §3.4](plan-topk-exec-model-2026-09-26.md#34-敏感带交付) 的 **2026 窗六格**。
本次仅整理已提供的结果及宿主产物指针，未在文档工作机重跑；不代表 2025 锚配置完整矩阵已完成。

## 1. Stamp c 的共享常量

| 项目 | 固定值 |
|---|---|
| 代码 tip | `9e58bde`（P3 #222 已合入） |
| 宿主 / 湖 | 4090 物理湖；`OSKH_SOURCE_PARQUET_ROOT = E:\stock_data`（本次宿主配置） |
| CLI | `backtest/research/csv_minute_backtest.py --strategy topk_dropout` |
| 格间变量 | `--topk-exec close\|open\|intraday` × walkdown off / `--limit-walkdown` on；各格独立 `--out-dir` |
| 资金 / 起日 / 结束日 | `--cash-total 100000000 --start 20260106 --end 20260914`；TopK `daily-quota` 自动配对到 cash，即 100000000 |
| 策略参数 | `--stop-pct 0 --dividend-type none --topk 50 --n-drop 5` |
| pred / pool | recorder `8a061ea4` 的 CSV 导出；pool 来自 `export_daily_pool`，topk50、asof `pred_minus_one`；不覆盖 `pred.pkl` |
| 未启用 | #214、Q8 gates、buy-state、vwap×walkdown、qlib minute/day roots |
| 涨停价格路径 | 既有 qlib 浮点带 `qlib_limit_pct=0.095`，未接真实档位；close 沿用旧 epsilon，open/intraday 沿用严格上限比较，见 P3 说明 |
| stamp | `20260927c` |

**价域为 minute lake `none`**：这些 NAV 不等同于 Q5 的日线 qlib `$close` 后复权尺子，
不得混成同一收益比较表。本次是 **nostop（`--stop-pct 0`）**，不同于书默认 `0.10`。
下表沿回报称呼写作 **intradate**，实际 CLI 值始终为 **`intraday`**。

## 2. 六格结果：Q9 原结束日

窗口：`20260106–20260914`。Human GO 保留 stamp a 的 Q9 窗口，**未截尾到湖末 20260909**。
六格均警告 `--end 20260914` 超过 `MINUTE_LAKE_END=20260909`；
本 stamp 六格 **`skip_no_bar = 0`**，不据此消除 lake-end warning 或宣称湖覆盖完整。

| cell | walkdown | NAV | total ret | maxDD | buys | skip_limit_up | limit_retry_fills | limit_retry_expired | walkdown_fills | walkdown_exhausted |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| close_plain | off | 95,156,972.16 | -4.84% | -37.02% | 868 | 118 | n/a | n/a | n/a | n/a |
| close_wd | on | 98,356,899.55 | -1.64% | -36.30% | 868 | 84 | 0 | 0 | 45 | 0 |
| open_plain | off | 98,842,351.57 | -1.16% | -37.29% | 868 | 8 | n/a | n/a | n/a | n/a |
| open_wd | on | 98,714,717.12 | -1.29% | -37.27% | 868 | 10 | — | — | 5 | 0 |
| intradate_plain（CLI `intraday`） | off | 96,652,299.18 | -3.35% | -37.66% | 868 | 3 | 4 | 1 | n/a | n/a |
| intradate_wd（CLI `intraday`） | on | 98,714,717.12 | -1.29% | -37.27% | 868 | 10 | — | — | 5 | — |

表内按宿主 RECEIPT 摘录保留计数：`n/a` 为不适用或本次未强调的字段（含 open_plain retry），
`—` 为该行回报未提供，均不补推为零。close_wd 的 retry `0/0` 与 open_wd 的 exhausted `0`
按回报原样记录，不将后者复制到 intradate_wd。

## 3. 跨格事实与边界

- plain（walkdown-off）三格的 NAV / total ret / maxDD / buys / skip_limit_up 与
  [三格记录 stamp `20260927a`](topk-exec-3cell-2026-09-27.md#2-stamp-aq9-原结束日湖覆盖不足) 一致；
  本 stamp 在 tip `9e58bde` 新增 walkdown-on 三格。`skip_no_bar = 0` 仅按本 stamp 回报记录，不回写旧 stamp。
- close_wd 的收益为 -1.64%、替补成交 45；open_wd 与 intradate_wd 均为 -1.29%、替补成交 5。
  walkdown-on 并非各模式收益均提升：open_plain 为 -1.16%，open_wd 为 -1.29%。
- **open_wd ≡ intradate_wd 仅限 `daily_equity` MD5 相同**，NAV / ret / maxDD / buys / skip_limit_up 亦相同；
  trades 与 `topk_execution.json` 仍不同，不能声称全产物相同，也不外推为两种执行契约等价。
- 六格均有 lake-end warning；保留 Q9 原结束日的 Human GO 不等于湖末之后有分钟覆盖。
- 本次是 **2026 窗 Human-GO 敏感性记录**，不宣称 2025 锚配置完整矩阵完成。
  #214、Q8、vwap×walkdown 不在范围；本次文档交付不改代码、不合并。
- **不是生产默认切换 GO**：`--topk-exec` 默认仍为 **close**，`--limit-walkdown` 默认仍为 **off**；
  代码、测试、fixtures、默认值与 CLI 均未改。

## 4. 4090 宿主产物指针

相对仓库路径；原始产物不随本文入库：

- RECEIPT：`backtest_output/RECEIPT_TOPK_EXEC6_8a061ea4_20260927c.md`
- 六个 out-dir 均在 4090 的 `backtest_output/` 下，stamp 为 `20260927c`；逐格路径与原始回报以该 RECEIPT 为准。
