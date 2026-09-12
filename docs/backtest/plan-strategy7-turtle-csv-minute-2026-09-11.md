# Plan：策略 7 金榕元/海龟 CSV 分钟回测（v1）

> **落盘**：2026-09-11。
> **状态**：✅ **A–D 已合 master**（#10/#11/#13/#14，切片 D = `6ca8050`）。**E 真名单一窗已在本机跑完**；禁止在虚拟机重跑。
> **风险档**：**L2**（新回测引擎 + 分档仓位机 + 指数闸；不进实盘 / 不改 `presets.py`）。
> **范围**：MyQuant-backtrader 回测本地。OSkhQuant1.3 只读名单与规则对照，不改 Paper/live。
> **人裁会话**：2026-09-11 17:35 原文 + 18:23–19:03 止损/减试错锁。
> **对抗**：[`docs/architecture/reviews/2026-09-11/plan-strategy7-turtle-csv-minute-2026-09-11/review-by-cursor.md`](../architecture/reviews/2026-09-11/plan-strategy7-turtle-csv-minute-2026-09-11/review-by-cursor.md)。

---

## 0. 一句话

把 **1.3 金榕元/海龟原型**做成与策略 6 同构的 **分钟向量化回测**（手动 `stock_pool_turtle` 名单）。止损按 **今天人裁**（不是 Paper 的 7 成 +1% / 9 成 +2%）。指数闸用已补齐的 `index/period=1d` 上证，缺数直接失败。

---

## ⚠ 对抗回填（v1.1 · 2026-09-11）

| ID | 修正 |
|----|------|
| **H-R1** | 试错 lot 仍在的 7 成 **只**走 A×0.99 减试错；**禁用** 综合成本 ×0.99（否则先于 A×0.99 全清可卖腿，§4.4 死路径） |
| **H-R2** | 不写 `ProfitStrategy.Strategy7`；v1 唯一入口 = rules + `csv_minute_backtest_v7.py` |
| **H-R3** | 策略 6 只借湖 I/O / 涨跌停 HALF_UP / 佣金数字 / 落盘。**禁止** `execute_buy` `_sell` `SimState` `Position` `_buy_px` `scan_held_day` chase / 策略 6 卖核 / `summarize` / `maybe_compare_daily` |
| **H-R4** | 涨停**禁买可卖**；跌停**禁卖**（开盘跌停 **defer**，不成交）。禁止抄 v1 原文「涨停不能卖 / 跌停不能买」 |
| **H-R5** | T+1 = `lot.buy_date < today`。禁止仓位级 `can_sell` |
| **H-R6** | `gate[T] = f(index_close[≤T-1])`。自写 `load_index_daily("000001.SH")`，root=`resolve_index_daily_root()`。禁止 `StockDataReader`、禁止 `load_daily_bars` 读指数。裸 `000001` / `.SZ` → 失败 |
| **H-R7** | 峰值 = 已走过分钟 high 的 running max；满 9 成后才评回撤 |
| **H-R8** | `--pool-dir` 必填，或 env `OSKH_TURTLE_POOL_DIR`；缺则失败。帮助里可举例 1.3 路径，不写死默认 |
| **H-R9** | 本仓无 `turtle/stop.py`。止损/止盈写在 `strategy7_rules.py`。禁止 import 1.3 `stop.py`、禁止 `_eval_prototype_sell` |
| **H-R10** | 该票当日已因止损/计时/止盈清空可卖腿 → **当日禁止再新开** |
| **H-R11** | 新开成交价 = `hm==895` 的 close；缺根 skip。禁止 `_buy_px` 14:30 回退；禁止把湖时间再转 Asia/Shanghai |
| **H-R12** | 3a 后无新止损 = **人裁研究偏离**（相对金榕元「加仓后必有止损」）。必须有暴跌单测；不擅自加回 avg×0.99 |
| **H-R13** | 触线只用 **close**；禁止同一根 K 的 high 加仓 + low 止损。仅「开盘已破止损且非跌停」用 open |
| **H-R14** | 5 日：`last_add_date` 为第 0 日；第 5 个交易日 **开盘起** 清可卖腿。chop 后「下一档」= A1×1.04（3a），不是抄 `sell.py` 的 A×1.10 |
| **H-R15** | 指数 preload ≥ `--start` 之前 **11** 个交易日（v1.2）。缺分区 / 窗内缺日 / close≤0 / 暖机不足 → 抛错退出。股票分钟缺 bar **不**升格为进程失败（当日该票 skip） |
| **H-R16** | v1 禁 `chip_indicator` / front 日线。`docs/backtest/README.md` 的 LEBS/Cerebro 叙述与本仓不符，不以该文选型 |

### fan-out 回填（v1.2）

| ID | 修正 |
|----|------|
| **F-R1** | 指数 preload ≥ `--start` 之前 **11** 个交易日（`MA10[T-2]` 需要 T-11）。close≤0 校验范围 = preload ∪ [start, end]，不要扫 2004–2014 占位零 |
| **F-R2** | **新开** = 14:55 + 指数闸；**加仓** = 交易时段逐分钟 close 触线。§4.8-5 不得把加仓并进 14:55 |
| **F-R3** | 股票日线至少预载 start 前 **1** 个交易日（推荐与指数同一 preload）。无昨收 → 当日该票 skip + reason，不进程失败 |
| **F-R4** | 交替止盈：`frac = 1 − Π(1−ratio)`；每档记目标股数/已卖股数；可卖不足则部分成交，**未卖完的档次日续派**，seq 仅在该档目标卖完后推进 |
| **F-R5** | v7 CLI 自己解析 `--pool-dir` 或 `OSKH_TURTLE_POOL_DIR`，都无 → `SystemExit`。禁止 `load_pool_days(..., pool_dir=None)`。目录不存在 = 失败；目录在但窗内无 CSV = 空跑 0 笔（合法） |
| **F-R6** | 减试错后 3b **从下一根分钟起评**。若 close 仍 ≤ A1×0.96 → 清 3 成（A1×0.96 > A×0.99 的数字后果）。补单测，不发明「重新穿越」 |
| **F-R7** | 落盘：自写三件套，或 duck-type 只要求 `.trades` / `.equity_curve`。禁止构造 `SimState` |
| **F-R8** | 引擎分层：`simulate_v7(...)` 纯撮合可注入 bars；CLI 只负责加载。日历 = **指数日线交易日**（缺名单日仍评持仓） |
| **F-R9** | 同分钟已 ≥ A×1.10 且未加过 3 成 → **jump_nine 优先**，不先 +3 再 +2。5 日计时成交价 = 当日首根 **open**（跌停 defer） |
| **F-R10** | B 约束**当前目标仓位名义**，不是累计买入。`stage=nine` 一旦达到，交替减仓后回撤止盈仍启用 |
| **F-R11** | reason 补 `skip_cash` / `defer_limit_down` / `skip_no_1455` / `skip_no_prev_close`。多票同分钟抢现金 = 当日名单 CSV 顺序 |
| **H-R10 澄清** | 「当日禁止再新开」= 该票 **持仓股数已到 0**，不是「可卖腿为 0」（减试错后仍持 3 成，不是新开） |

---

## 1. 非目标 / 禁改

| 不做 | 原因 |
|------|------|
| 板块 / 十日线 / 布林彩虹打分选股 | 用户声明本期只做手动名单 |
| 日线近似引擎、Cerebro、LEBS 海龟轨 | v1 只做分钟向量化 |
| 策略 6 追涨停（T+1 09:45） | 策略 7 涨停当日跳过，不建延期 |
| 改 `trade_decision/presets.py` | 与 1.3 共享 SSOT |
| 改 `trade_decision/turtle/sell.py`；import 1.3 `turtle/stop.py` | 本仓无 `stop.py`；Paper 止损仍是 +1%/+2%；策略 7 自写规则 |
| 把 `stock_pool_turtle/` 拷进本仓 | `--pool-dir` / `OSKH_TURTLE_POOL_DIR` 外指 1.3，缺则失败 |
| 换源补指数分钟到 20250101 | 闸用日线；本机 miniQMT 指数 1m 约一年 |
| 风控增强组 / MA10 个股离场 / 账户熔断 | 与 1.3 默认关项一致，v1 不做 |

可复用、只读：`trade_decision/turtle/buy.py` 的 `TURTLE_ADD_BANDS` 元组（不要 import 1.3 加仓函数）。策略 6 只借 §3 白名单。

---

## 2. 与 Paper / 金榕元的差（实现不得「改回去」）

对照：1.3 `金榕元交易策略-20260808.md`、`TurtleTrading_SDD.md`、1.3 `trade_decision/turtle/stop.py`（只读，禁止 import）。

| 项 | Paper / 金榕元 20260808 | **策略 7（本 plan）** |
|----|-------------------------|------------------------|
| 试错止损 | 成本 ×0.96 | **A ×0.96** |
| 7 成（试错 lot 仍在） | 综合成本 **×1.01** 全清 | **只** A×0.99 减试错（v1.1；不用综合成本 ×0.99） |
| 9 成止损 | 综合成本 **×1.02** | **最后加权均价 ×1.01** |
| 减试错再上车 | 无 | **有**（§4.4） |

xlsx 交替止盈数值（成本 ×1.3/1.5/1.8/2.0，卖剩余 30/20/30/20）与 5 日逐档计时、满仓回撤止盈，跟 SDD 原型对齐。金榕元与 xlsx 冲突时：止损以 **本 plan §4.3** 为准，止盈档位以 xlsx/SDD 为准。

---

## 3. 文件与入口

| 路径 | 作用 |
|------|------|
| `backtest/research/strategy7_rules.py` | 纯函数：档位、止损线、A/A1 梯子、交替/回撤止盈、5 日计时、指数闸日历 |
| `backtest/research/csv_minute_backtest_v7.py` | 分钟回测 CLI + 模拟（自写账本 / 买腿 / 卖 lots） |
| `tests/test_strategy7_rules.py` | 规则表驱动 |
| `tests/test_csv_minute_backtest_v7.py` | 合成分钟路径（T+1、减试错、闸） |
| `--pool-dir` | **必填**，或 env `OSKH_TURTLE_POOL_DIR`。缺则失败。帮助举例：`E:\PycharmProjects\OSkhQuant1.3\stock_pool_turtle` |

**不要**把逻辑塞进 `csv_minute_backtest.py`。不要写 `ProfitStrategy.Strategy7`。

**允许 import**：`utc_ms_range` / `warn_stale_period_env` / `_ymd` / `_limit_prices` / `hit_limit_up` / `hit_limit_down` / `round_fen` / `parse_pool_csv`（1.3 同口径，`canonical_from_bare_code`）/ `load_pool_days`（必须显式 `pool_dir`）/ `load_daily_bars`（**仅股票**昨收）/ `load_minute_bars` 与 cache 三件套（**v7 自己的 cache 文件名**）/ `write_run_artifacts` / `COMMISSION` / `TURTLE_ADD_BANDS` / `resolve_period_root` / `resolve_index_daily_root` / `to_partition_key` / `classify_daily_lake_kind`。

**禁止 import**：`execute_buy` `_buy_size` `_sell` `SimState` `Position` `chase_decision` `CHASE_HM` `DEFAULT_DAILY_QUOTA` `_buy_px` `scan_held_day` `warmup_start`（日历日暖机不够 10 个交易日）`STOP_PCT` `TIERS` `trail_hits` `summarize` `maybe_compare_daily` `chip_indicator` `StockDataReader` `trade_decision.turtle.sell` `presets` 1.3 `stop.py` / 1.3 加仓函数 `backtest.lebs`。

指数闸自写 loader：`resolve_index_daily_root() / dividend_type=none / symbol=000001_SH`。

建议 CLI：

```text
python backtest/research/csv_minute_backtest_v7.py --start 20260804 --end 20260909 --pool-dir E:\PycharmProjects\OSkhQuant1.3\stock_pool_turtle
```

落盘：`backtest_output/csv_minute_v7_{start}_{end}/` → `summary.txt`、`daily_equity.csv`、`trades.csv`（`reason` 见 §7）。

---

## 4. 锁定规则

### 4.1 名单 / 资金 / 成交

| 项 | 锁定 |
|----|------|
| 名单 | `stock_pool_turtle/YYYYMMDD.csv`（现窗约 20260804–20260909）。缺日 = 当日不开新仓。已持有则只走加仓/离场 |
| 单票预算 B | **1_000_000**。4 成 / 3 成 / 2 成 = 40/30/20 万，满仓 **90 万 = 0.9B** |
| 全局现金 | 与策略 6 同默认 **21_000_000**（`--cash-total`）。多票并行，受现金与 B 同时约束 |
| 价格 | 股票分钟 / 日线 **`adjust_type=none`**。指数闸读 `index/period=1d` none |
| 佣金 | 双边 0.1%，无最低 |
| 股数 | 向下整百；现金不够则该腿 skip 并记 reason，不拆碎股 |
| 新开仓时钟 | 成交价 = **`hm==895`（14:55）收盘**。该分钟缺失 → 当日该票不开新仓。禁止 14:30–14:54 回退。湖时间 = 中国交易钟点标成 UTC，取 hour/minute，**禁止**再转 Asia/Shanghai |
| 涨停 | 买价 ≥ 涨停（`round_fen` HALF_UP）→ 新开与加仓都 **跳过**。涨停**可以卖**。无追买。昨收 = none 日线、`index < day` |
| 跌停 | **不能卖**（含开盘跌停 → defer，次日重评）。默认不买跌停价 |
| 加仓/离场时钟 | 交易时段内逐分钟。触线只用当根 **close**。开盘已跌破止损且**非**跌停 → **开盘价**成交 |
| T+1 | 可卖股 = `sum(lot.shares for lot if lot.buy_date < today)`。残留次日 **重评**同一规则（价已离开触发线则不再卖，不是挂单扫尾） |

### 4.2 普通加仓（相对建仓价 A）

A = **首笔试错成交价**（不是加权成本）。线不因加仓重算。

| 条件 | 动作 | 仓位（相对 B） |
|------|------|----------------|
| 新开 | 买 4 成 | 4 成 |
| 现价 ≥ **A×1.04** 且尚未加过 3 成 | 加 3 成 | 7 成 |
| 现价 ≥ **A×1.10** 且已是 7 成、尚未加 2 成 | 加 2 成 | 9 成 |
| 已有试错、现价 ≥ **A×1.10**、**还没加过 3 成**（跳空/尾盘已超 10%） | **一次加 5 成到 9 成** | 9 成 |
| 同日可连做试错 + 加仓 | 允许（金榕元 §6） | — |

「尾盘涨幅＞10% 直接 9 成」= 上表跳空行，相对 **A**，不是相对昨收。

### 4.3 止损（人裁 2026-09-11，覆盖 Paper）

综合成本 / 加权均价 = 已成交买入的金额加权（含已实现部分卖出后的剩余成本；卖出按移动加权扣仓）。

| 状态 | 止损线 | 卖什么 |
|------|--------|--------|
| 仅试错 4 成 | **A × 0.96** | 能卖则全清试错 |
| 7 成且试错 lot 仍在 | **只 A × 0.99** 减试错 | 只卖试错 4 成。**禁用** 综合成本 ×0.99 |
| §4.4 减试错后只剩 3 成 | **A1 × 0.96** | 清这 3 成（当天新加则次日才能卖） |
| §4.4 走完 3a、未到 9 成 | **无新止损档**（H-R12 研究偏离） | 只等 A1×1.10 / 交替止盈 / 5 日计时 |
| **任意路径达到 9 成** | **最后加权均价 × 1.01**（触及 9 成时冻结，止盈后不重算止损线） | 跌破全清 |

9 成之后价格继续上行 → 只走 §4.5 止盈。成本 = 成交价加权，**不含佣金**。交替止盈按剩余股数比例切 lots（FIFO 先吃最早 lot）。

### 4.4 减试错再上车（人裁；替换「一加就无条件减」）

**没有「波动剧烈」开关。** T+1 只表示交易所可卖，**减试错还要碰到 A×0.99**。

A1 = 第一次加仓（A×1.04 那笔）的成交价。

| 步 | 条件 | 动作 | 仓位 |
|----|------|------|------|
| 1 | 涨到 **A×1.04** | 加 3 成 | 7 成 |
| 2 | 其后跌到 **A×0.99** | **只卖试错 4 成** | 剩刚加的 3 成 |
| 3a | 再涨到 **A1×1.04** | 加 4 成 | 7 成 |
| 3b | 未走 3a 且跌到 **A1×0.96** | 3 成清仓 | 0 |
| 4 | 已走 3a 且涨到 **A1×1.10** | 再加 2 成 | 9 成 |
| 5 | 已到 9 成 | §4.3 均价 ×1.01；上行走 §4.5 | — |

补充：

- 第 2 步没碰到 A×0.99：不减试错；下一档仍是 **A×1.10** 加 2 成；止损仍只是再碰 A×0.99 减试错（不是综合成本 ×0.99 全清）。
- 试错与第 1 步同一天：当天不减；**不隔日补无条件减**。次日价再碰 A×0.99 才减。
- 3b 从 **减试错之后的下一根分钟** 起评（当分钟止损桶已用掉）。A1×0.96 ≥ A×0.9984 > A×0.99：阴跌减试错后，下一根仍 ≤ A1×0.96 则清 3 成——这是数字后果，须有单测。`buy_date==今日` 则 3b 当天不成交，次日重评。
- 尾盘一次加满 9 成：不进入本表。chop 之后 **A 梯子作废**，只走 A1。
- `jump_nine` 现金不够：整腿 skip，下一根仍试 5 成，不退化成 +3。
- 3a 之后不要套综合成本 ×0.99。

### 4.5 止盈

**交替止盈**（xlsx / SDD §6.4.1；未满仓也可触发）：

- 档位价 = **当分钟成交前**移动均价 × **[1.3, 1.5, 1.8, 2.0]**
- 各档目标 = 触发时剩余持仓 × 30/20/30/20%；同分钟穿越多档 `frac = 1 − Π(1−r)`（抄公式，不 import `sell.py`）
- 每档记目标股数 / 已卖股数；可卖不足则部分成交，未卖完次日续；**seq 仅在该档目标卖完后推进**
- 未满仓也可触发，但常被 5 日计时压住；一旦 `stage=nine`，减仓后回撤止盈仍启用

**回撤止盈**（仅 **已满 9 成** 且峰值高于成本）：

```
peak_gain = (peak - cost) / cost
profit_dd = (peak - price) / (peak - cost)
peak_gain ≤ 20% → 阈值 50%
20% < peak_gain ≤ 50% → 40%
peak_gain > 50% → 20%
profit_dd ≥ 阈值 → 全清
```

峰值 = 满 9 成那根起、**已走过**的分钟 high 的 running max。禁止日线 high、禁止预计算整段 max。T+1 卖不完则次日重评。

### 4.6 5 日逐档计时（金榕元 §5 / SDD §6.4.3）

- `last_add_date` 为第 **0** 日；第 **5** 个交易日首根 **open** 清可卖腿（不论盈亏；开盘跌停 defer）
- 「下一档」：试错后 = A×1.04；普通 7 成后 = A×1.10；chop 后 = **A1×1.04（3a）**；3a 后 = A1×1.10。禁止抄 `sell.py` 的 `hold_days>=5` + `TURTLE_ADD_BANDS[units]`
- 仅未满 9 成适用；满仓后关掉
- 减试错不刷新锚；3a/4 / 普通加仓刷新。加仓刷新后 **当日**计时不再触发
- 停牌/无分钟：不成交；计时按指数/SSE 交易日递增（不停表）

### 4.7 上证十日线闸

- 标的死锁 **`000001.SH`**。`classify_daily_lake_kind` 必须为 `index`。裸 `000001` / `000001.SZ` / 股票树 → **失败**
- 路径：`resolve_index_daily_root() / dividend_type=none / symbol=000001_SH`。禁止 `StockDataReader`、禁止 `load_daily_bars`
- **`gate[T] = f(index_close[≤T-1], MA10[≤T-1])`**。T 日 14:55 不得读 T 日收盘
- 连续两个**已完成**交易日收盘 < MA10 → **从下一交易日**禁新开。收复日 R 收盘 ≥ MA10(R) → **R+1** 才恢复。收复日当天 14:55 仍拒新开
- MA10 含该已完成日。这是 **上证新开闸**，不是 SDD 个股 MA10 离场
- 开工前 preload：`--start` 之前 ≥**11** 个交易日。close≤0 / 缺日校验范围 = preload ∪ [start, end]。缺分区 / 暖机不足 → 抛错退出
- 本机口述：有效收到 2026-09-11。实现不得依赖「本机 0 缺日」，必须以加载结果为准

指数分钟 **不是**本闸输入。`index/period=1m` 已下完宇宙内 QMT 能给的部分，v1 不用。

### 4.8 同分钟优先级

1. 涨停：禁买（新开+加仓），**允许卖**。跌停：**禁卖**（开盘跌停 defer）。跌停价默认不买
2. 止损子序：开盘破线（非跌停）→ §4.4-2 减试错 → §4.4-3b → 其余 §4.3。同一分钟止损桶 **只执行一条**
3. 执行完止损后 **再评** 5 日计时（允许级联清掉剩余可卖腿）
4. 止盈：回撤全清优先于交替减仓
5. **加仓** = 逐分钟 close 触线（可在同分钟用刚回收的现金）。**新开** = 仅 14:55 + 指数闸。同分钟已 ≥ A×1.10 且未加过 3 成 → jump_nine 优先

该票本分钟/当日已因止损/计时/止盈清空可卖腿 → **当日禁止再新开**。禁止同一根 K 用 high 加仓同时用 low 止损。

---

## 5. 数据与窗口

| 数据 | 路径 / 约束 |
|------|-------------|
| 股票 1m | `resolve_period_root("1m")` / `dividend_type=none`。本机约 2025-01-02 → 2026-09-09（股票 1m 末日以湖为准；日线可到 09-10/11） |
| 股票 1d | 涨跌停昨收、指数闸对照日历 |
| 指数 1d | 自写 loader → `resolve_index_daily_root()`；preload ≥ start 前 **11** 个交易日 |
| 股票 1d | 与指数同一 preload，至少保证 start 前 1 个交易日有昨收 |
| 名单 | `--pool-dir` / `OSKH_TURTLE_POOL_DIR`。**不要**回落策略 6 `stock_pool/` |
| 建议首跑 | `--start 20260804 --end 20260909 --pool-dir <turtle池>` |
| 缓存 | 可复用同窗行情 parquet；v7 **自己的文件名/目录**。禁止「缓存命中 = 规则已校验」 |

跑前清残留 `OSKH_PERIOD_*`（unset ≠ 回退）。权威盘有 `F:\stock_data\.authority` 时走 F 湖。

---

## 6. 实现要点

1. **状态机按票**：`entry_A`、`add1_A1`、`avg_cost`、`shares`、`lots`（带买入日）、`stage`（trial / seven_normal / three_after_chop / seven_after_readd / nine）、`sell_band_seq`、`peak`、`last_add_date`、`chop_trial_dumped`。
2. **lots 账本**是 T+1 与部分卖的唯一来源。可卖 = `buy_date < today`。
3. 规则函数纯：输入须含 stage / A / A1 / avg / px / day / **可卖股** / 计时锚；引擎只撮合。
4. 指数闸开工前预计算 `gate[T]`；缺数抛错。
5. v7 自写 `summarize_v7`，不要调用策略 6 `summarize`。撮合入口 `simulate_v7(minute_bars, daily_bars, pool_days, index_days, ...)`，CLI 只加载。
6. 循环日历 = 指数日线交易日。多票同分钟现金按当日名单 CSV 顺序。

---

## 7. `trades.csv` reason（最低集）

| reason | 含义 |
|--------|------|
| `buy:trial` | 14:55 试错 4 成 |
| `buy:add_a104` | A×1.04 加 3 成 |
| `buy:add_a110` | A×1.10 加 2 成 |
| `buy:jump_nine` | 未过 7 成直接补到 9 成 |
| `buy:readd_a1_104` | §4.4 加 4 成 |
| `buy:readd_a1_110` | §4.4 加 2 成 |
| `skip_limit_up` | 涨停不买 |
| `skip_index_gate` | 指数闸拒新开 |
| `skip_cash` | 现金不够整腿 |
| `skip_no_1455` | 缺 14:55 根 |
| `skip_no_prev_close` | 无昨收，涨跌停算不了 |
| `defer_limit_down` | 开盘跌停，卖出顺延 |
| `stop:trial_a096` | 试错 A×0.96 |
| `stop:chop_trial_a099` | §4.4 减试错 |
| `stop:three_a1_096` | 剩 3 成 A1×0.96 |
| `stop:nine_avg101` | 9 成 均价×1.01 |
| `tp:band_{1-4}` | 交替止盈档 |
| `tp:drawdown` | 满仓回撤全清 |
| `exit:timer5` | 5 日未加仓清仓 |
| `EOD_MARK` | 期末估值 |

---

## 8. 单测（编码完成的最低门槛）

`strategy7_rules.py`：

1. 试错 A×0.96；7 成+试错仍在 → 只 A×0.99 减试错（**不要**测综合成本 ×0.99 全清）；9 成 avg×1.01（**不要**测 Paper 1.01/1.02）。
2. §4.4：1→2→3a→4→9 成；1→2→3b；1 之后价格在 avg×0.99 与 A×0.99 之间 **不得**全清。另测 3a 后暴跌无新止损（H-R12）。
3. 跳空 A→A×1.12：一次 `jump_nine`。
4. 交替档位与回撤三档阈值。
5. 5 日：锚日=0，第 5 个交易日开盘可清；满 9 成后不计时；chop 后下一档=A1×1.04。
6. 指数闸：`gate[T]` 只用 T-1 及更早；两日 < MA10 → **下一交易日** `block_new`；收复日当天仍拒新开，R+1 放开。序列不足 → 抛错。裸 `000001` 失败。

`csv_minute_backtest_v7.py`：

7. T+1：14:55 试错后当日触 A×0.96 **不成交**。
8. 第 2 步：试错 `buy_date < 今日` 则可与加仓同日减；试错当天买则不减。第 3b 同日不可卖当天 3 成。
9. 缺 14:55 不开；14:55 涨停 skip。开盘跌停止损 defer。
10. 闸日名单票不进 `buy:trial`；已持仓仍可止损。计时清仓后当日不得再新开该票。

跑：`vanna312 -m pytest tests/test_strategy7_rules.py tests/test_csv_minute_backtest_v7.py -q`。Ruff 只扫新文件。

---

## 9. 切片（建议 Codex 按序）

| 切片 | 内容 | 完成定义 | 进度 |
|------|------|----------|------|
| **A** | `strategy7_rules.py` + 单测 1–6 | pytest 绿 | ✅ [#10](https://github.com/baiyibing/MyQuant-backtrader/pull/10) |
| **B** | `simulate_v7` + CLI：账本 / T+1 / 14:55 / 涨停 / 落盘 | 单测 7–9；窗内无 CSV = 0 笔跑通；未指定 pool-dir = 非 0 退出 | ✅ [#11](https://github.com/baiyibing/MyQuant-backtrader/pull/11) |
| **C** | §4.4 路径接进引擎 + 单测 8 | reason 对齐 | ✅ [#13](https://github.com/baiyibing/MyQuant-backtrader/pull/13) `409671e` |
| **D** | 指数闸 + 单测 10 | 缺数 fail | ✅ [#14](https://github.com/baiyibing/MyQuant-backtrader/pull/14) `6ca8050`（CI 绿，分支已删） |
| **E** | 真名单 20260804–20260909 一跑（勿开全市场 Cerebro） | `summary.txt` 有买卖计数；不要求正收益 | ✅ 本机已跑。**不在虚拟机执行** |

---

## 10. Codex 可直接执行的约束

- 解释器：`OSKH_MERGE_PYTHON` → `VANNA312_PYTHON` → `D:\anaconda3\envs\vanna312\python.exe`。禁止系统 `python`。
- 文本 UTF-8 无 BOM；写完 `.py`/`.md` 断言 NUL=0。
- 不改 `presets.py`、`turtle/sell.py`、策略 6 默认参数。本仓无 `stop.py`；禁止 import 1.3 `stop.py`。
- 不 `git commit`，除非用户另说。
- 不在 paper 测试机下指数分钟。
- **E 真名单一窗只在本机跑，不在虚拟机执行。**

---

## 11. 验收（人看）

- 规则数字与 §2 表一致（7 成减试错 A×0.99、9 成 ×1.01）。
- 真跑窗口内若上证两日跌破 MA10，summary 出现 `skip_index_gate`，且无闸日新开。
- 对照 1.3 名单天数：缺 CSV 的日子零 `buy:trial`。
- 不把策略 6 的净值拿来当策略 7 基线。
