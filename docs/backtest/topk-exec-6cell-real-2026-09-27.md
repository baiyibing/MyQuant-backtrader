# TopK 分钟执行 real↔qlib 六格敏感性记录（20260927d）

日期：2026-09-27（Asia/Shanghai）。本页归档 4090 物理湖 Human-GO 的 P4 real 六格
4090bot PASS 回报；实现依据 [P4 说明](topk-exec-p4-2026-09-27.md)，对应
[计划 §3.4](plan-topk-exec-model-2026-09-26.md#34-敏感带交付) 的 **2026 窗六格**。
与已归档的 [qlib 六格 stamp `20260927c`](topk-exec-6cell-2026-09-27.md) 并列比较；
本次仅整理已提供的结果及宿主产物指针，未重跑 real 或 qlib，不代表 2025 锚配置完整矩阵已完成。

## 1. Stamp d 的共享常量

| 项目 | 固定值 |
|---|---|
| 代码 tip | **`5a3e6e2`（P4 #225 已合入）** |
| 宿主 / 湖 | 4090 物理湖；分钟湖价域 **`none`** |
| CLI | `backtest/research/csv_minute_backtest.py --strategy topk_dropout` |
| 涨停价格路径 | 六个新格均显式 **`--topk-limit-rule real`**；真实档位及 Decimal 路径见 P4 说明 |
| 格间变量 | `--topk-exec close\|open\|intraday` × walkdown off / `--limit-walkdown` on；各格独立 `--out-dir` |
| 资金 / 起日 / 结束日 | `--cash-total 100000000 --start 20260106 --end 20260914`；Human GO 保留与 c 相同的 Q9 窗口 |
| 策略参数 | `--stop-pct 0 --dividend-type none --topk 50 --n-drop 5` |
| pred / pool | recorder `8a061ea4`，与 `20260927c` 相同产物；`pred.pkl` 未覆盖、未改动 |
| qlib 基线 | stamp `20260927c`、tip `9e58bde`；沿用归档结果，不重跑，原 RECEIPT 未改动 |
| stamp | `20260927d` |

**价域为 minute lake `none`**：表中的 qlib 指涨停价格规则，不指 qlib 日线价源；
这些 NAV 不等同于 Q5 日线 qlib `$close` 后复权尺子，不得混比。
本次为 **nostop（`--stop-pct 0`）**，不同于书默认 `0.10`。
下表沿回报称呼写作 **intradate**，实际 CLI 值始终为 **`intraday`**。

## 2. Real 六格结果：Q9 原结束日

窗口：`20260106–20260914`，**未截尾到湖末 20260909**。
六格均有 `--end 20260914` 超过 `MINUTE_LAKE_END=20260909` 的 lake-end warning，与 c 不变；
六格均 **`skip_no_bar=0`、缺行情=6**。两项计数按回报并列保留，不据此消除警告或宣称湖覆盖完整。

| cell | walkdown | NAV | total ret | maxDD | buys | skip_limit_up | limit_retry_fills/exp | walkdown_fills/exh | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| close_plain | off | 96,406,973.66 | -3.59% | -36.83% | 871 | 68 | 0/0 | n/a | 201 |
| close_wd | on | 97,590,251.28 | -2.41% | -35.62% | 871 | 31 | 0/0 | 25/0 | 2071 |
| open_plain | off | 99,563,137.92 | -0.44% | -36.56% | 872 | 0 | 0/0 | n/a | 216 |
| open_wd | on | 99,563,137.92 | -0.44% | -36.56% | 872 | 0 | 0/0 | 0/0 | 1473 |
| intradate_plain（CLI `intraday`） | off | 99,563,137.92 | -0.44% | -36.56% | 872 | 0 | 0/0 | n/a | 212 |
| intradate_wd（CLI `intraday`） | on | 99,563,137.92 | -0.44% | -36.56% | 872 | 0 | 0/0 | 0/0 | 1625 |

`exp` = `limit_retry_expired`，`exh` = `walkdown_exhausted`；walkdown-off 的 `n/a` 不补写为零。
`wall_s` 为宿主回报耗时（秒），不作为执行契约或性能保证。

## 3. Real↔qlib 对照与跨格事实

qlib 收益及完整原表见 [stamp c 六格记录](topk-exec-6cell-2026-09-27.md#2-六格结果q9-原结束日)。
ΔNAV = real d − qlib c，按回报保留至 0.01M（M = 百万）：

| cell | qlib c total ret | real d total ret | ΔNAV vs c |
|---|---:|---:|---:|
| close_plain | -4.84% | -3.59% | +1.25M |
| close_wd | -1.64% | -2.41% | −0.77M |
| open_plain | -1.16% | -0.44% | +0.72M |
| open_wd | -1.29% | -0.44% | +0.85M |
| intradate_plain | -3.35% | -0.44% | +2.91M |
| intradate_wd | -1.29% | -0.44% | +0.85M |

- **real 下 open_plain ≡ open_wd ≡ intradate_plain ≡ intradate_wd 仅指回报的
  NAV / ret / maxDD / buys / skip_lu 相同**：99,563,137.92 / -0.44% / -36.56% / 872 / 0。
  open / intradate 在本窗无涨停拦截，walkdown 未发挥作用（on 格 `walkdown_fills=0`）；
  不据此声称产物 hash 相同、完整产物相同或两种执行契约等价。
- close 仍有涨停拦截：walkdown 使 `skip_limit_up` 从 **68→31**，替补成交 25。
  real close_wd 相对 real close_plain 的收益改善（-3.59%→-2.41%），但相对 qlib close_wd
  的 **ΔNAV 为负（−0.77M）**；不能概括为 real 或 walkdown 在所有格均改善收益。
- lake-end warning 与 c 不变；`skip_no_bar=0` 不代表 Q9 结束日前分钟湖完整。
  `20260927c` qlib RECEIPT 与 `pred.pkl` 均保持未改动。
- 本次仅为 **2026 窗 Human-GO 敏感性记录**，未完成 2025 锚配置完整矩阵，亦未交付完整产物 hash 对照。
  #214、Q8、vwap×walkdown 均不在范围；本次文档交付不改代码、不合并。
- **不是生产默认切换 GO**：`--topk-limit-rule` 默认仍为 **qlib**，`--topk-exec` 默认仍为 **close**，
  `--limit-walkdown` 默认仍为 **off**；代码、测试、fixtures、默认值与 CLI 均未改。

## 4. 4090 宿主产物指针

相对仓库路径；原始产物不随本文入库，逐格完整目录以 RECEIPT 为准：

- real RECEIPT：`backtest_output/RECEIPT_TOPK_EXEC6_REAL_8a061ea4_20260927d.md`
- real out-dir 模式：`backtest_output/topk_exec6_real_{close_plain,close_wd,open_plain,open_wd,intraday_plain,intraday_wd}_…_20260927d`
- 已归档且未改动的 qlib RECEIPT：`backtest_output/RECEIPT_TOPK_EXEC6_8a061ea4_20260927c.md`，见 [qlib 六格记录](topk-exec-6cell-2026-09-27.md#4-4090-宿主产物指针)。
