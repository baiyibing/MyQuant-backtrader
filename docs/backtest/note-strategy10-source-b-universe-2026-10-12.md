# 策略 10（换手阻力 / 源 B）宇宙与导出说明

> 落盘：2026-10-12。配套代码：`export_ta_pool.py` 的 `--universe-mode`、Store 会话缓存、`profile_export.json`。
> 上游计划：[plan-strategy10-tr-pool-2026-09-13.md](_archive/plans/plan-strategy10-tr-pool-2026-09-13.md) · 宿主烟测：[s9-s10-host-smoke-2026-09-13.md](s9-s10-host-smoke-2026-09-13.md)。

## 1. 策略是什么

| 项 | 口径 |
|----|------|
| 书 | `--strategy version10`（别名 `10` / `v10`）；导出侧仅此一本。2026-10-16 起（#473）回测注册 `version10_1`（卖点冻结 v9）/ `version10_2`（卖/仓位冻结 6.55 栈），买点复用同一池，**不改导出** |
| 买点 | 名单源 B：`resist_tr_bb_1000`（`window=1000`） |
| 导出 | `scripts/data/export_ta_pool.py`（别名 `export_strategy10_pool.py`） |
| 卖点 | 冻结策略 6 **旧公式**（止损 6%、+1% 锚后 T+1… 回撤）；`sell_logic=version6_legacy`，不跟现行 version6（止损 2% 等）漂移 |
| 名单 | 必须显式 `--pool-dir`；拒绝默认 `stock_pool/`；不做 TopK |

## 2. 两种宇宙：全湖 vs lake∩TR

导出过滤器在 `fail_closed=True` 时要求：**宇宙里每一只代码，当日 TR 截面都必须有一行**。缺行即 `ConfigurationError`。

| 模式 | CLI | 宇宙怎么定 | 结果 |
|------|-----|------------|------|
| 全湖有 K（严格 B-R4） | `--universe-mode lake_bar`（默认） | 湖 `period=1d/none` 当日有量 K 的代码 | 湖 ⊃ TR 时，常因缺行直接失败；且逐票开 parquet 很慢 |
| lake∩TR（宿主研究快路径） | `--universe-mode lake_tr` | 湖分区名 ∩ 当日 TR 截面（`require_bands=True`） | 宇宙 ⊆ 截面，fail_closed 能过；再跑 `resist_tr_bb_1000` |
| 注入 | `--universe-file` | 显式候选列表 | CI / 短窗烟测用 |

**不是「绝对不能用全湖」**，而是：在 TR store 未与湖同宽、且保持 fail_closed 时，全湖宇宙在设计上就会失败。策略 10 规则本身依赖 TR 行；没有截面的票也过不了门。lake∩TR ≈ 先丢掉注定缺 TR 的代码，再 fail_closed。

空截面日（`bdate_range` 里的周末 / 春节等）**跳过**，不再整段 fail-closed。缺行 fail-closed 仍适用于「有截面的交易日」。

## 3. lake∩TR 比全湖少多少、为什么少

宿主窗 **20260105–20260909**（TR store 实际有 bands 的区间；分钟湖端点可能更晚，以 store 为准）：

| 口径 | 数量 |
|------|------|
| 湖分区代码 | ~5610 |
| 当日 lake∩TR（中位） | ~5489 |
| 湖有、TR 无（中位） | **约 100–120 只（≈2.2%）** |
| 区间 | 大约少 99–168 只/日 |
| TR 有、湖无 | 中位 0（TR ⊆ 湖分区） |

以 **20260603** 拆桶（当天少 112 只有 bands 截面）：

| 类型 | 大约 | 说明 |
|------|------|------|
| 北交所 `.BJ` | ~50 | TR 流水线基本未写入 store |
| 深/沪 A 股 | ~55 | 多数从未进 store；少数曾有、当日已断档（停牌/退市/漏刷） |
| 指数 | 4 | 如 `000001.SH`、`000300.SH`、`399001.SZ`——湖有分区，不是 TR 股票宇宙 |
| ETF/基金 | ~3 | 如 `510050.SH`、`159915.SZ` |
| 其中「有 TR 行但无 bands」 | ~18 | `require_bands=True` 会丢掉 |

结论：少的百来只主要是 **湖更杂 + TR 未覆盖**，不是 lake∩TR 故意砍可交易票。策略 10 买点 anyway 过不了无 TR 行的代码。

全窗固定交集宇宙（所有交易日都在 TR∩湖）会更窄（同窗约 5412，相对全湖少 ~198）；`--universe-mode lake_tr` 是**按日**交集，更宽一点。

## 4. 导出性能与埋点

慢点曾是：`TurnoverResistanceStore.load_cross_section` 每个交易日整表 `read_parquet`（~300MB × 百余日）。

现口径：

- Store **会话缓存**（mtime 失效）：同进程整表只读一次
- `resist_tr_bb_*` 过滤向量化
- 宿主推荐：`--universe-mode lake_tr` + `--store-parquet …`
- 默认写 `profile_export.json`（`OSKH_PROFILE_SIM=0` / `--no-profile` 可关）
- 回测宿主仍写 `profile_sim.json`（与导出埋点分开）

同窗实测量级（研究机，非锁定 SLA）：

| 路径 | 墙钟 |
|------|------|
| 旧：逐日读 Store + 手造宇宙文件 | 名单相关约 8–9 min |
| 新：`lake_tr` + 缓存 | **~26 s**（`store_disk=1`） |
| 日线 / 分钟回测（bar_cache hit） | 数秒级 |

## 5. 推荐命令

```text
# 导出（宿主；lake∩TR）
D:\anaconda3\envs\vanna312\python.exe scripts/data/export_ta_pool.py ^
  --start 20260105 --end 20260909 ^
  --store-parquet E:/stock_data/turnover_resistance_daily.parquet ^
  --universe-mode lake_tr ^
  --out-dir exports/src_b_tr_bb1000_20260105_20260909

# 回测（书默认止损应以 strategy10 的 6% 为准；若 CLI 掺入 version6 的 2%，显式 --stop-pct 0.06）
D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_daily_backtest.py ^
  --strategy version10 --stop-pct 0.06 ^
  --pool-dir exports/src_b_tr_bb1000_20260105_20260909 ^
  --start 20260105 --end 20260909 ^
  --out-dir backtest_output/csv_daily_v10_20260105_20260909_stop06

D:\anaconda3\envs\vanna312\python.exe backtest/research/csv_minute_backtest.py ^
  --strategy version10 --stop-pct 0.06 ^
  --pool-dir exports/src_b_tr_bb1000_20260105_20260909 ^
  --start 20260105 --end 20260909 ^
  --out-dir backtest_output/csv_minute_v10_20260105_20260909_stop06
```

产物侧看：`exports/.../profile_export.json`、`backtest_output/.../profile_sim.json`、`summary.txt`。

## 6. 与「刷全市场 TR」的边界

若业务坚持字面全湖 + fail_closed：必须先把 TR store（含 bands）刷到与湖同宽，再开 `lake_bar`。那是 store / Rust 回填问题，不是导出器改 fail-open。本仓研究默认继续 **lake∩TR**。
