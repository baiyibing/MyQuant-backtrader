# TopK 分钟执行三格敏感性记录（20260927a/b）

日期：2026-09-27（Asia/Shanghai）。本页归档 4090 物理湖 Human-GO 跑数回报；
实现依据 [P1 说明](topk-exec-p1-2026-09-27.md)，范围为
[计划 §3.4](plan-topk-exec-model-2026-09-26.md#34-敏感带交付) 六格中的 **walkdown-off 三格**。
本次仅整理已提供的结果及宿主产物指针，未在文档工作机重跑。

## 1. 两个 stamp 的共享常量

| 项目 | 固定值 |
|---|---|
| 代码 tip | `e38bc50`（P1 #218 已合入） |
| 宿主 / 湖 | 4090 物理湖；`OSKH_SOURCE_PARQUET_ROOT = E:\stock_data`（本次宿主配置） |
| CLI | `backtest/research/csv_minute_backtest.py --strategy topk_dropout` |
| 唯一格间变量 | `--topk-exec close\|open\|intraday` 及 `--out-dir` |
| 资金 / 起日 | `--cash-total 100000000 --start 20260106`；TopK `daily-quota` 自动配对到 cash，即 100000000 |
| 策略参数 | `--stop-pct 0 --dividend-type none --topk 50 --n-drop 5` |
| pred / pool | recorder `8a061ea4` 的 CSV 导出；pool 来自 `export_daily_pool`，topk50、asof `pred_minus_one`；不覆盖 `pred.pkl` |
| 未启用 | walkdown、vwap、Q8 gates、buy-state、#214、qlib minute/day roots |
| 涨停价格路径 | P1 既有 qlib 浮点带 `qlib_limit_pct=0.095`，未接真实档位；具体比较语义见 P1 说明 |

**价域为 minute lake `none`**：这些 NAV 不等同于 Q5 的日线 qlib `$close` 后复权尺子，
不得混成同一收益比较表。本次是 **nostop（`--stop-pct 0`）**，不同于书默认 `0.10`。
同一 stamp 三格共享结束日；b 经 a 后 Human GO 将结束日截到湖末，其他共享常量不变。
下表沿回报称呼写作 **intradate**，实际 CLI 值始终为 **`intraday`**。

## 2. Stamp a：Q9 原结束日，湖覆盖不足

窗口：`20260106–20260914`；stamp：`20260927a`。
三格均警告 `--end 20260914` 超过 `MINUTE_LAKE_END=20260909`，回报缺栏日 6；
open/intraday 的 `skip_no_bar` 约 75/74。三格 **end 未改**，保持同窗可比，仍须带覆盖不足的限制解读。

| cell | NAV | total ret | maxDD | buys | skip_limit_up | limit_retry_fills | limit_retry_expired |
|---|---:|---:|---:|---:|---:|---:|---:|
| close | 95,156,972.16 | -4.84% | -37.02% | 868 | 118 | n/a | n/a |
| open | 98,842,351.57 | -1.16% | -37.29% | 868 | 8 | 0 | 0 |
| intradate（CLI `intraday`） | 96,652,299.18 | -3.35% | -37.66% | 868 | 3 | 4 | 1 |

相对 close：open 收益 **+3.68pp**、NAV 约 **+3.685M**、`skip_limit_up` **−110**；
intradate 收益 **+1.49pp**、NAV 约 **+1.495M**、`skip_limit_up` **−115**，retry fills 4、expired 1。
pp 为百分点，M 为百万；差值沿用回报的舍入值。

4090 宿主产物指针（相对仓库路径；原始产物不随本文入库）：

- RECEIPT：`backtest_output/RECEIPT_TOPK_EXEC3_8a061ea4_20260927a.md`
- close：`backtest_output/topk_exec3_close_8a061ea4_20260106_20260914_20260927a`
- open：`backtest_output/topk_exec3_open_8a061ea4_20260106_20260914_20260927a`
- intraday：`backtest_output/topk_exec3_intraday_8a061ea4_20260106_20260914_20260927a`

## 3. Stamp b：Human GO 截尾到湖末

窗口：`20260106–20260909`；stamp：`20260927b`。
结束日匹配 `MINUTE_LAKE_END`，**无 lake-end warning**；但仍有 `skip_no_bar`：open=75、intraday=74，
summary 缺行情=8/cell。截尾不代表消除了窗口内缺行情；此处保留各回报字段口径，不将缺行情数与事件数混同。

| cell | NAV | total ret | maxDD | buys | skip_limit_up | limit_retry_fills | limit_retry_expired |
|---|---:|---:|---:|---:|---:|---:|---:|
| close | 96,610,060.24 | -3.39% | -37.02% | 854 | 118 | n/a | n/a |
| open | 100,365,550.22 | +0.37% | -37.29% | 854 | 8 | 0 | 0 |
| intradate（CLI `intraday`） | 98,148,058.35 | -1.85% | -37.66% | 854 | 3 | 4 | 1 |

相对 close：open 收益 **+3.76pp**、NAV 约 **+3.755M**；
intradate 收益 **+1.54pp**、NAV 约 **+1.538M**。

4090 宿主产物指针：

- RECEIPT：`backtest_output/RECEIPT_TOPK_EXEC3_8a061ea4_20260927b.md`
- close：`backtest_output/topk_exec3_close_8a061ea4_20260106_20260909_20260927b`
- open：`backtest_output/topk_exec3_open_8a061ea4_20260106_20260909_20260927b`
- intraday：`backtest_output/topk_exec3_intraday_8a061ea4_20260106_20260909_20260927b`

## 4. 跨 stamp 事实与边界

- 两窗总收益排序稳定为 **open ≫ intradate ≫ close**；仅描述本次三格结果。
- 截尾后各格收益比 a 提高约 **1.4–1.5pp**；`skip_limit_up` 计数不变，仍为 **118 / 8 / 3**。
- 两个 stamp 的产物契约均回报 OK：close 买入 reason=`pool` 且 **无** `topk_execution.json`；
  open 为 `pool:open` 且有 JSON；intradate 为 `pool:intraday` 且有 JSON。close retry 列的 n/a 不代表零次重试计数。
- `pred.pkl` 未触碰；跑数回报 blockers none。湖覆盖与剩余 `skip_no_bar` 限制仍如上所列。
- 仅完成 **walkdown-off 三格**；计划六格及 walkdown-on 仍待 P3，未完成 2025 锚配置的完整矩阵。
  P2 vwap、P3 walkdown、#214 与 Q8 均不在本次范围；不据此新增 GO。
- **不是生产默认切换 GO**：`--topk-exec` 默认仍为 **close**，open/intraday 仍为 opt-in；代码、测试、fixtures 与默认值均未改。
