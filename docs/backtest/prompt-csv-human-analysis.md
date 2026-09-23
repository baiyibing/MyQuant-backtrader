# 提示词：本仓 CSV 回测盘后人工分析

> 配套代码：`backtest/research/csv_analysis_export.py`。CLI：`scripts/research/export_csv_human_analysis.py`。  
> 不是 MyQuant 的 `export_positions_trades.py`（那套吃 qlib PortAna `positions_normal_1day.pkl`）。

把下面整段发给做盘后阅读的人 / agent，并附上本次 `<run-dir>/analysis/` 路径。该目录里已经有 `字段说明.txt`，不必再另贴字段表。

---

## 角色

你在读**已经跑完**的本仓向量化 CSV 回测（`csv_daily_backtest.py` / `csv_minute_backtest.py` 等），做盘后人工复盘。不是再模拟一遍，不是改默认策略书，不是重训 MyQuant。

先读同目录的 `字段说明.txt`（文件和字段以它为准），再读 `human_analysis.txt`（收益率、最大回撤、胜率已算好），然后读 `summary.json`，按需打开 CSV。不要手算 `trades.csv` 差分，不要重跑 `--strategy`，不要自己重写一份字段说明，不要另算一套回撤或胜率口径。

## 产物（同一目录，稳定文件名）

| 文件 | 用途 |
|---|---|
| `字段说明.txt` | **每次导出必写**。文件与字段说明。开头是本次 `run_dir` 和窗口；正文来自 `docs/backtest/csv-analysis-fields.txt` |
| `human_analysis.txt` | **每次导出必写**。总收益率、最大回撤（日期、峰值、谷值）、已平仓胜率、含期末浮盈的胜率、按卖因拆开 |
| `win_by_reason.csv` | 已平仓按 `sell_reason` 的笔数、胜率、盈亏 |
| `summary.json` | 天数 / 买卖笔数 / 已实现+期末浮盈 / 与净值变动对账（`pnl_nav_diff`），并含上面的回撤和胜率字段 |
| `nav_daily.csv` | 组合日净值、回撤（来自 run 的 `daily_equity.csv`） |
| `daily_picks.csv` | **有 `--scores-dir` / `--pred-csv` 才写**。买入日 T 的全日分 TopK 对照是否实持 |
| `positions_daily.csv` | 每个净值日收盘后持仓（价=当日最后成交或 `EOD_MARK`） |
| `trades_daily.csv` | 引擎成交行（BUY/SELL/SKIP），已拼打分 / 旁路 / ST / 年龄（传了才有） |
| `round_trips.csv` | **主表**：FIFO 开平一行一笔；含打分、旁路 close/MA20/MA60/`$winratio`、卖因、盈亏 |
| `ledger_by_stock.csv` | 按票买/卖 + 期末未平 `hold` |
| `pnl_by_stock.csv` | 按股汇总（与 round_trips 同源） |
| `human_review.xlsx` | 仅 `--xlsx` 时写，多表一份 |

`daily_picks.action`（与 MyQuant 盘后包同名，语义按本仓成交）：

- `new_buy`：当日 TopK 且当日买入
- `held`：当日 TopK 且在仓、但不是当日新开
- `missed`：当日 TopK 但没买上（涨停跳过 / 资格闸 / 现金 / n_drop 惯性）
- `held_not_topk`：在仓但不在当日 TopK（dropout / 止损未平以外的留仓）

分数 as-of：**不要再 shift**。`--scores-dir` 的文件名已经是买入日 T（内容 = pred[T−1]）。`--pred-csv` 由加载器做 `pred_minus_one`。

买点旁路（`--buy-state-file`）条件与引擎一致、无 MA5 斜率：

1. close &lt; MA20 且 close &lt; MA60 且 `$winratio` &lt; 0.10
2. close &gt; MA20

`buy_state_label`：`cond1_below_ma_and_wr_lt_0.10` / `cond2_close_gt_ma20`。缺行 = `buy_sidecar_hit=false`（引擎 fail-closed，分析包只标注，不改成交）。

## 盘后清单（按这个顺序写，不要跳到「策略该怎么改」）

1. **净值与胜率**：直接引用 `human_analysis.txt`。最大回撤 = 净值相对此前峰值的最小值；已平仓胜率 = `realized_pnl > 0` 的已平笔 / 已平笔。`pnl_total` 与 `nav_delta` 的 `pnl_nav_diff` 只作对账；差大先查佣金是否进了 round_trips、未平仓是否缺 `EOD_MARK`。
2. **荐股 vs 实持**（有 `daily_picks` 时）：按日数 `missed` / `held_not_topk` / `new_buy`。missed 多 = 执行层或资格闸吃掉信号；held_not_topk 多 = dropout 惯性。
3. **个股**：对 `pnl_by_stock` 盈亏两端各翻 5 只，用 `round_trips` 看开平日、持有交易日、卖因（`stop_loss:*` / `topk_drop:bottom` / 书侧 trail 等）、买点 cond。
4. **结构**：持仓天数分布、单日是否顶满 topk、同一只反复进出、cond1 vs cond2 笔数。
5. **结论纪律**：单窗、单 run **不算数**。能写观察（「止损 354 笔里 cond2 占八成」），不能写「应把 topk 改成 20」除非任务书预锁了多窗门槛。

## 不要做

- 不要为了「再导出一次」去重跑 `csv_daily_backtest.py` / 分钟入口
- 不要调用 MyQuant `export_positions_trades.py --replay`（那是 PortAna）
- 不要在分析会话里改线上默认 topk / n_drop / 闸门 / HELP_LOCK
- 不要把本仓向量化净值当成 1.3 LEBS / MockQMT 签字
- 不要把 CYQ `winner_ratio` 湖和旁路 `$winratio` 混成一列

## 导出怎么来的（宿主备忘，不必贴进分析会话）

```text
D:\anaconda3\envs\vanna312\python.exe scripts/research/export_csv_human_analysis.py ^
  --run-dir backtest_output/<run> ^
  --scores-dir <MyQuant scores/ 或省略> ^
  --buy-state-file <sidecar.parquet 或省略> ^
  --st-daily-file <st_daily.parquet 或省略> ^
  --age-map-file <age_min_buy_60d.tsv 或省略> ^
  --topk 50 --xlsx
```

缺省写到 `<run-dir>/analysis/`，并写入 `字段说明.txt` 与 `human_analysis.txt`。只读三件套 `summary.txt` / `daily_equity.csv` / `trades.csv`，不模拟。字段正文改 `docs/backtest/csv-analysis-fields.txt`，不要在分析目录里手改。
