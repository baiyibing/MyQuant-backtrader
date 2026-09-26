# 联合仓库 TopK 回测 · 问题记录

- 日期：2026-09-22
- 状态：**讨论中**。Q1–Q4 / Q6 / Q7 已裁；**Q5/Q9/Q10 已裁（2026-09-26）**：日线对照钉 qlib `$close` 日线后复权 bin + pred `8a061ea4` OOS `20260106–20260914` + cash 1e8；分钟价域归 #214/X-01 HOLD，非本页 impl GO。Q8 仍开。`--stop-fill close` 与 `--buy-state-file` 已落地，默认关；`--stop-fill` 默认 `touch`。不要把本页当「改默认成交」任务书。
- 范围：MyQuant 出分 / 买闸；本仓 `topk_dropout` 向量化成交。不复活 PortAna 当产品；不改线上 10/3。
- GitHub 问题：[#164](https://github.com/baiyibing/MyQuant-backtrader/issues/164)（本仓此前无专题 issue）。

兄弟仓 MyQuant 的 `docs/reviews/joint-return-v1/` 是另一条「规则意图 / 组合约束」链，**不是**本页。9 月 16 日 overlay 任务书已落地并冻结默认语义，本页是它后面的研究改进账。

本页覆盖：

| 你要找的 | 章节 |
|---|---|
| 背景、来龙去脉 | §1 |
| 两边对齐比什么 | §2 |
| 踩过的坑 | §3 |
| 已经做的工作（PR/文件） | §6.1–§6.4 |
| 日线 vs 分钟现实现 | §6.5 |
| 价源：数据湖 vs qlib bin | §6.6 |
| 怎么跑、资金、产出 | §6.7 |
| 宿主实验产物（不入库） | §6.10 |
| 开盘一次 decide | §6.8 |
| 不是本页的邻居书 | §6.9 |
| 本仓 CLI | §9 |
| MyQuant 出分 / 买闸开关 | §9.1 |
| 还没做 / 待裁 | §7、§8 |
| 本页怎么用 | §11 |

---

## 0. 一句话

MyQuant 负责全日截面分和（可选）买点资格；本仓用同一本策略书 `topk_dropout` 对着**引擎实仓**做 TopkDropout，再用 **CLI 开关**叠 ST / 年龄 / 止损阈值 / 止损价域。日线与分钟是**两个入口脚本**，不是策略版本。持续改进加开关、改 HELP_LOCK、在本页追加待裁，不复制 `strategy_topk_dropout_rules.py`。

```text
MyQuant                         MyQuant-backtrader
全日截面分 + 日 TopK CSV   →    csv_daily_backtest.py  或  csv_minute_backtest.py
买闸源：buy_eligibility.py      --strategy topk_dropout
CYQ winner_ratio 湖（H13）      开关：--stop-pct / --stop-fill / ST / 年龄 /
$winratio 旁路（联合买点）      --buy-state-file（默认关；盈筹=$winratio）
```

---

## 1. 来龙去脉

原先回测几乎都在 **MyQuant**：Alpha158 + LGB/Cat 出分，qlib `TopkDropoutStrategy`（`method_buy=top` / `method_sell=bottom` / `hold_thresh=1`）加 `PortAnaRecord` 出净值。线上研究默认宽度后来收成 **10/3 LGB**；仓内实验堆在 **50/5**。买闸（均线/盈筹、ST、年龄、5 日涨幅）是训练/重回测上的开关，默认全关，不是一本「versionX」。

2026-09-12 起三仓拆开（[MyQuant `docs/plan-three-repo-roadmap-2026-09-12.md`](../../../MyQuant/docs/plan-three-repo-roadmap-2026-09-12.md)；本仓 [engine-positioning-ssot.md](engine-positioning-ssot.md)）：

| 仓 | 角色 |
|---|---|
| MyQuant | 信号厂：训练、出分、导出日名单 / 全日分 |
| 本仓 | 研究脸：向量化日线/分钟，按规则把名单做成交 |
| OSkhQuant1.3 | 执行栈：LEBS 扫描 + MockQMT 真栈验收 |

Qlib `PortAnaRecord` **停用当产品**；本仓 Cerebro 退场。早期「联合」走错过一条捷径：MyQuant 导出每日 TopK CSV，丢进本仓 `version6`/`version8`。M5 已经证明 pred Top10 与手工池**几乎不重叠**（[m5-list-attribution-2026-03-09.md](m5-list-attribution-2026-03-09.md)）——换书不等于换选股宇宙。`live_pool/*sell.csv` 更不能当多日卖出（overlay **R-6**）。

真正的联合 TopK 是 2026-09-16 overlay（[plan-topk-dropout-overlay-2026-09-16.md](plan-topk-dropout-overlay-2026-09-16.md) · [handoff](handoff-topk-dropout-overlay-codex-impl-2026-09-16.md)）：

- MyQuant 只交 **全日截面分**（`pred_minus_one`：买入日 T 用 pred[T−1]）+ 便利 TopK 池。
- 本仓新书 `topk_dropout` 对着**引擎当前持仓**现算 qlib 同款淘汰，不是「今日 CSV 没有就清仓」。
- ST / 年龄挡新开、沿序补（BT-B）；10% 开仓价止损是额外卖（BT-C），空位次日再补。
- 硬边界（**目的 ≠ 手段**）：
  - **目的**：成交引擎不要绑回 qlib 运行时（`qlib.init` / handler / `Exchange` / `PortAnaRecord` / `qlib.contrib.strategy`）。三仓里本仓只做向量化成交；PortAna 停用当产品（R-7）。
  - **手段**：simulate 热路径不 `import qlib`（围栏 `test_ashare_simulate_import_fence.py`）；n_drop 不进成交核；不改 v6/v8。读 `$close` bin、对齐 `Mean($close, n)` / TopkDropout **算法语义**，用 numpy/纯函数即可。
  - 当时 **不开买点闸（R-8）** 是另一条产品冻结，与「均线能不能用 qlib Mean 语义」不是一件事。

研究上仍要和 qlib 纸面账对得上数字，于是 09-17 做了 **arm0 日线对齐片**（[#87](https://github.com/baiyibing/MyQuant-backtrader/pull/87)，评审 [pr-87-topk-arm0-qlib-align](../architecture/reviews/2026-09-17/pr-87-topk-arm0-qlib-align/grok-review.md)）：同一把尺子读 qlib `$close` bin、`--qlib-cost`、9.5% 统一板、`risk_degree=0.95`、dropout 当日收盘（`topk_drop` same-bar）、`--stop-pct 0`。这不是把 PortAna 做成第四台引擎。

对齐不是一次 PR 结束。同一窗同一 pred 上，两边名单/手数/净值曾差几百万，后来一坑一坑填（§3）。填完之后年化账把 **A 格：50/5 + ST+年龄+15%、止损关** 当成跨窗仍同号的研究锚；15% 闸和止损档跨年反号（`GATE_FLIP` / `STOP_FLIP`）。详见 MyQuant [2026-09-17-annual-lift-status-handoff.md](../../../MyQuant/docs/reviews/2026-09-17-annual-lift-status-handoff.md)。

本会话（2026-09-21～22）：用 pred `c5f4bccd` 再跑过日线 50/5、闸与止损关；口述四条规则（买点 / ST / 年龄 / **收盘** 10% 止损）对不上任何一本现成 version 书。共识是继续一书加开关，先日线收盘止损实验，默认触价不翻。尚未编码。

---

## 2. 两边 TopK 对齐在比什么

「对齐」曾经混过三件事。必须拆开：

| 层 | 要对的 | 不要当成已经对齐 |
|---|---|---|
| **算法** | qlib `TopkDropout` 的 top/bottom / `n_drop` / 对**实仓**现算；买点均线对齐 `Mean($close, 20/60)` | 「今日池文件没有的全卖」；在成交核 `import qlib` 才算用了 qlib 算法 |
| **研究尺子（arm0 / 年化账）** | 价 = qlib `$close` 后复权 bin；费 = 买 5bp / 卖 15bp / 最低 5；涨跌停 |Δ|≥9.5% 当日买卖都不做；现金部署 0.95；代码键 `000608.SZ`；ST 只认当日 `is_st`；年龄满 60 交易日；缺分 `(-score, code)`；整手向下 | 湖 `none`/`front` 价；双边 10bp 无最低；板块 10/20/30；qlib 官方 `+0.1` 抬一手 |
| **产品 / 线上** | 无。向量化回答「这份名单按规则怎么成交」 | PortAna 当对照基准或上线依据；用 50/5 改 10/3；本仓净值对 1.3 真栈 |

overlay **H-1 / R-7** 预锁：宿主烟测只比名单重叠、`reason`、可卖、涨跌停。年化账后来在**填坑后的尺子**上把 PortAna 与 BT 净值拧到同一格（A 格两端都是 109,653,546），那是研究对账，不是恢复 PortAna 产品地位。

官方 `qlib.contrib.strategy.TopkDropoutStrategy` **没有** ST、15% 涨幅、买点、开仓止损。那些是 MyQuant `BuyEligibilityFilter` / `custom_strategy.py` 和本仓 CLI 叠上去的。把 PortAna 净值差写成「Topk 算法不对」几乎总是错的。

asof：**文件名 = 买入日 T，内容 = pred[T−1]**（`pred_minus_one`）。日历必须能覆盖窗；`cn_data` 日历过旧（约止于 2025-10-14）不能扛 2026，要用 `my_data`。

---

## 3. 踩过的坑（禁止写回叙事）

明细与数字以填坑文为准：[MyQuant `docs/reviews/2026-09-16-scores-leading-zero-nav-lift.md`](../../../MyQuant/docs/reviews/2026-09-16-scores-leading-zero-nav-lift.md)。年化账「假高峰」与纪律：同目录 [2026-09-17-annual-lift-status-handoff.md](../../../MyQuant/docs/reviews/2026-09-17-annual-lift-status-handoff.md) §5–§8。本仓补丁侧：[PR #87](https://github.com/baiyibing/MyQuant-backtrader/pull/87)（`dtype=str` + zfill、年龄溢出 `99991231`）。

| 坑 | 现象 | 教训 |
|---|---|---|
| 读码丢前导零 | `pd.read_csv` 把 `000608` 读成 `608`，BT 丢掉整族 000/001/002/003。错误净值 **117.2M**，比修好后高约 475 万，比当时 PortAna 高约 730 万 | 更高净值可以是 bug。scores 必须字符串 + `zfill(6)` |
| ST 集合不一致 | PortAna：`is_st` ∪ 静态黑名单 ∪ `unknown_end` fallback；BT：只认 parquet 当日 `is_st`。第一天就买了不同的人，169 日连锁分叉 | 迁盘后 PIT 更全；旧「ST 不全」的 1.125 亿作废。对账要声明 ST 口径 |
| 5 日 15% × 停牌 NaN | 意图「缺收盘放过」；MyQuant 宽表里 NaN 被判超阈值扔掉。1 月 16 日一只买不同，后面 145 天跟着歪 | 不是官方 Topk 的 bug；`NaN` 与「票不在表」必须同一套缺数语义 |
| 缺分并列排序 | pandas `sort_values` 把 NaN 垫底、同值不稳；BT `(-score, code)`。4 月 14 日该卖哪只缺分票两边反了 | 并列键必须是 **`000608.SZ`**，不能是 qlib 字面 **`SZ000608`**（`H`/`Z` 会反转） |
| 整手 `+0.1` | qlib `round_amount_by_trade_unit` 在整手边上抬 100 股；BT `int(股/100)*100` 向下 | 官方注释写的是浮点，余量比误差大几个数量级。A 股回测向下取整，向 BT |
| 年龄日历溢出 | 新北交所票 `all.txt` 起始日距买入不足 60 日；溢出若写回上市日会**提前可买** | 越出日历 → `9999-12-31` fail-closed |
| 价域混用 | 湖 `--dividend-type front` 曾报超额 +34%；与 qlib bin 不是同一价 | 年化尺子锁 `$close` bin（N8）。湖 none/front 另账 |
| 池文件当轮换 | 只有 Top50 裸码，无法给已掉出榜的持仓打分；或「CSV 没有就清仓」比 50/5 狠 | 必须全日分；淘汰以 scores 为准，`--pool-dir` 只是日历/契约 |
| 静态 sell CSV | `live_pool/*sell.csv` 是一日纸面近似，叠止损第二天就歪 | overlay R-6 |
| 买点闸当免费 alpha | 50/5 三闸全开，超额 +23%→+9% | 年化 **N6：买入状态继续关**。本页若再接买点须另裁（Q2/Q3） |
| 单窗扫参升默认 | 2026 止损 20% 最好、2025 是 15%；15% 涨幅闸两年反号 | `STOP_FLIP` / `GATE_FLIP`。冠军不得直接升默认（N5） |
| 把 v6 止损改成 10% | 冒充「给 50/5 加规则」 | overlay R-4：10% 只挂新书 |
| 分钟 / 日线止损混谈 | overlay 任务书写过「分钟为准」；真正 0/5/…/30 扫是 **日线触价** | 频度换入口；价域另开开关。本页拟 `close` 只定义日终 |
| `cn_data` 日历扛 2026 | 日历过旧，窗盖不住 | 联合日线用 `my_data` |
| 20/3 旧表高峰 | 9 月 15 日闸全关旧环境 +25%/+28%；现尺子复现塌到 +1.9% | `WINDOW_DEPENDENT`，不当候选 |

**禁止**把读码 bug、前复权、旧 ST 表、单窗止损冠军写进可上线或新基线叙事。

---

## 4. 两仓分工（钉死）

| 层 | 谁做 | 现在代码 | 不要做 |
|---|---|---|---|
| 打分、pred、TopK 导出 | MyQuant | `export_daily_pool.py`（`pred_minus_one`）；全日分 sidecar | 本仓重训、覆盖 `8a061ea4` |
| TopkDropout 轮换 | 本仓策略书 | `decide_topk_dropout`；对**实仓**现算 | 成交核里复刻 n_drop；读 `live_pool/*sell.csv` |
| ST PIT / 上市年龄 | 本仓 CLI 可选 | `--st-daily-file` / `--age-map-file` / `--age-days`（默认 60） | 持仓变 ST 强制卖（另立项） |
| 买点（均线 / 盈筹） | MyQuant 算旁路；本仓查表 | `export_topk_buy_state_sidecar.py` + `--buy-state-file` | 成交热路径不 `import qlib`；默认 MQ `--buy-state-filter` 不翻 |
| 止损阈值 | 本仓 | `--stop-pct`；书默认 0.10；`0` 关闭 | 拿 v6 的 `--stop-pct` 冒充本需求 |
| 止损价域 | 日线触价；分钟逐 bar close | 见 §6.5 | 改默认去迁就新实验 |
| 执行验收 | OSkhQuant1.3 | LEBS / MockQMT | 本仓承诺与真栈净值对齐 |

CYQ 全日 `winner_ratio` feeder 留在 MyQuant（H13）。本仓 Rust 是 TR/Store，不在本页重写筹码。

---

## 5. 四条业务规则 vs 现码

口述目标：TopK 里仍要过买点；不买 ST；上市不满 60 交易日不买；跌破买入价 10% **当日收盘**止损。

| # | 口述 | 现况 | 缺口 |
|---|---|---|---|
| 1 | 双均线下且盈筹率 &lt;10%，**或**站上 MA20 | **Q2/Q4 已裁并落地**：条件 2 只认 `close > MA20`；盈筹 = `$winratio`。本仓 `--buy-state-file` 查表 | 默认不传=不滤（年化 N6 仍关）。MQ 现码 `--buy-state-filter` 仍是 `legacy`（MA5 斜率 + CYQ/Quantile），不改训练默认 |
| 2 | ST 不能买 | 本仓 `--st-daily-file`，只挡新开 | 路径与 PIT 文件要显式传；口径须是「只认当日 is_st」，不要静默并回静态黑名单 |
| 3 | 上市 ≥60 交易日 | 本仓 `--age-map-file` `--age-days 60` | 无日历时文件值须已是最早可买日；溢出 fail-closed |
| 4 | 收盘价相对开仓价 −10% 止损 | 默认仍是日线 **跳空 / 最低触触发价** | **已落地** `--stop-fill close`：按日终收盘卖。Q7 恰跌停仍成交；Q6 止损先于 dropout。分钟拒绝 `close` |

没有一本 version1–12 把四条打成一套。对得上的组合是：**qlib 风格 TopkDropout + 买闸 + 本仓止损**。

---

## 6. 已有基线（不要改默认去迁就）

### 6.1 Overlay（已实施，默认冻结）

权威：[plan-topk-dropout-overlay-2026-09-16.md](plan-topk-dropout-overlay-2026-09-16.md) · [handoff](handoff-topk-dropout-overlay-codex-impl-2026-09-16.md)

- 书名 `topk_dropout`（别名 `topk` / `version_topk`），不是 version11。
- 默认 50/5、10% 开仓价止损、无 trail。
- 日线止损 reason：`stop_loss:gap_open` / `stop_loss:touch`。
- `--stop-pct 0` 关闭止损（臂 0 / 对齐原生 Topk）。
- HELP_LOCK 在 `strategy_topk_dropout_rules.py`。

### 6.2 年化账止损扫（日线，不是分钟）

MyQuant [2026-09-17-annual-lift-status-handoff.md](../../../MyQuant/docs/reviews/2026-09-17-annual-lift-status-handoff.md)：2026 上扫 0/5/10/15/20/25/30。入口是本仓 **`csv_daily_backtest.py`** + `--qlib-data-root` + `--qlib-cost`。标签 **STOP_FLIP**（2025 峰值 15%，2026 峰值 20%）。C 格「仅 BT 扫参」，PortAna 未跟扫。

语义：开盘 ≤ 触发价 → 开盘卖；否则 **最低价**碰到 `cost×(1-p)` → **按触发价**卖。不是收盘。

### 6.3 本会话联合 50/5 烟测（闸与止损关）

`topk_dropout` + pred `c5f4bccd` + qlib `my_data` day.bin + `--qlib-cost` + `--stop-pct 0`，窗约 20260106–20260914。这是原生轮换臂，不是四条规则臂。

### 6.4 已经落地的工作（代码）

| 片 | 仓 | 落点 |
|---|---|---|
| MQ-A 全日分导出 | MyQuant | `export_daily_pool.py`；`scores/YYYYMMDD.csv`，文件名=买入日 |
| BT-A 轮换书 | 本仓 | `topk_dropout_rules.py` `decide_topk_dropout`；`strategy_topk_dropout_rules.py`；`csv_strategy_books.py` `register` 名 `topk_dropout`（别名 `topk` / `version_topk`） |
| 分数加载 | 本仓 | `topk_dropout_scores.py`（`dtype=str` + zfill；`--pred-csv` / `--scores-dir`） |
| BT-B 新开闸 | 本仓 | `topk_dropout_eligibility.py`；CLI `--st-daily-file` / `--age-map-file` / `--age-days` / `--return-threshold-filter` / `--buy-state-file` |
| 联合买点旁路 | MyQuant 算、本仓查 | MQ `export_topk_buy_state_sidecar.py`（`$close` / `Mean(20/60)` / `$winratio`）；BT `buy_state_oral_ok` |
| BT-C 止损阈值 | 本仓 | 书默认 `STOP_PCT=0.10`；`--stop-pct 0` 关闭。成交价域见 §6.5，**不是**收盘 |
| arm0 日线对齐 | 本仓 #87 | `qlib_bin_daily.py`；`--qlib-data-root`；`--qlib-cost`；topk 书 9.5% 板、`cash_deploy_frac=0.95`、`topk_drop` same-bar |
| data-free 单测 | 本仓 | `tests/test_topk_dropout_rules.py`、`test_topk_dropout_book_a.py` / `_b.py` / `_c.py`、`test_topk_buy_state.py` |
| HELP_LOCK | 本仓 | `strategy_topk_dropout_rules.py`（CLI `--help` 尾部） |

**还没落地：** 分钟侧 `--qlib-cost` / `--qlib-data-root`；分钟日终止损。

### 6.5 现有实现：日线 vs 分钟（as-built）

同一本书、同一套 `decide` / 买闸。**成交核分叉**，不要把一边的止损语义抄到另一边。

| | 日线 `csv_daily_backtest.py` | 分钟 `csv_minute_backtest.py` |
|---|---|---|
| 入口 | `--strategy topk_dropout` | 同左 |
| 产出目录 | `backtest_output/csv_daily_topk_dropout_{start}_{end}/` | `csv_minute_topk_dropout_{start}_{end}/` |
| 买成交 | 当日 **日线收盘** | 当日 **14:55 分钟收盘**（湖时钟标成 UTC=CST） |
| dropout 卖 | `topk_drop` **same-bar 收盘**（不是次日开盘 pending） | `sell_gate` 在扫描中命中后，按**那一根分钟 close** 卖 |
| 止损（`--stop-pct`∈(0,1)，默认 0.10） | ① 开盘 ≤ `cost×(1-p)` → `stop_loss:gap_open` 按开盘；② 否则 **最低价**碰到触发价 → `stop_loss:touch` **按触发价** | ① 开盘 ≤ 触发价 → `gap_open` 按开盘（`minute_gap_open`）；② 否则 **每一根** `close/cost-1 ≤ -p` → `touch` 按该根 close（`minute_trigger_bar_close`） |
| 止损相对 dropout | 先评止损，再评 `sell_gate`。**Q6：收盘臂同样止损先** | 扫描里同样先 gap/止损，再 `sell_gate` |
| T+1 | 买入当日不卖 | 同；T+0 不更新峰值 |
| 涨跌停 | 统一 \|Δ\|≥9.5%；买卖都不做；不追买；跌停不挂次日开盘（`limit_down_pending=False`） | 同书钩子；开盘已跌停则该根跳过 |
| 价源 | 默认湖；也可 qlib bin（§6.6） | 默认湖 1m；也可 `--qlib-1min-root`。日线辅助 `--qlib-day-root` **≠** 日线 `--qlib-data-root` |
| 费率 | 默认双边 10bp 无最低；`--qlib-cost` → 5/15bp min5 | **无 `--qlib-cost`**，默认双边 10bp |
| 联合 50/5 对账 | 年化账 / #87 / 本会话烟测都走这里 | **没有**同等 PortAna 对齐扫。overlay 曾写「止损分钟为准」，落盘扫参未走分钟 |
| 湖尽头 | 日线可接到今天 | 分钟湖短于窗口时会缺 bar；要接到今天用日线 |

卖出 reason：dropout 前缀 `topk_drop:bottom`；止损 `stop_loss:gap_open` / `stop_loss:touch`。无 trail。

代码锚：日线止损环 `csv_daily_backtest.py`（`gap_open` / `low` 触价）；分钟扫描 `csv_minute_backtest.py` `scan_held_day`（开盘价再逐根 close）。

### 6.6 价源：数据湖和 qlib bin 都可以（两套账，不要混比）

`topk_dropout` **不绑死**某一种行情。日线和分钟入口都既能读 **path-SSOT 数据湖**（默认），也能读 **qlib bin**（显式根目录）。价域不同，净值不能横比。湖路径走 resolvers（`OSKH_SOURCE_PARQUET_ROOT` 等），未设定或文件不存在即失败，禁止猜 E:/F:。

**费率是另一根轴。** `--qlib-cost` 只改佣金（5/15bp min5），只存在于**日线**入口；与读湖还是读 bin 正交。默认同为双边 10bp 无最低。

#### 日线 `csv_daily_backtest.py`

二选一，`--qlib-data-root` 一旦给出就 **跳过湖**。读的是 qlib 的 `$close` 文件，**不是**把 qlib 包挂进成交循环：

| 价源 | 怎么开 | 价是什么 | 除权 |
|---|---|---|---|
| 数据湖（默认） | 不传 `--qlib-data-root`；可选 `--dividend-type none\|front\|back`、`--daily-root` | hive `stock/period=1d/dividend_type=*` | `none` 走 E-R6 remap；`front`/`back` 已是连续价，跳过 E-R6 |
| qlib day.bin | `--qlib-data-root <my_data>` | `features/*.day.bin` 的 **`$close` 后复权** | dump 契约声明后复权；不读湖分区 |

```text
# 湖（默认 none）
csv_daily_backtest.py --strategy topk_dropout --pred-csv <pred> --stop-pct 0.10

# 湖前复权
csv_daily_backtest.py --strategy topk_dropout --pred-csv <pred> --dividend-type front

# qlib bin（年化 / PortAna 对账尺子；常与 --qlib-cost 一起）
csv_daily_backtest.py --strategy topk_dropout --pred-csv <pred> --qlib-data-root <my_data> --qlib-cost --stop-pct 0
```

日历：bin 的 `day.txt` 必须盖住窗口；`cn_data` 过旧不能扛 2026，用 `my_data`。

#### 分钟 `csv_minute_backtest.py`

两根轴互相独立：成交用的 **分钟 K**，以及涨跌停/除权用的 **日线辅助**。

| 轴 | 湖（默认） | qlib bin |
|---|---|---|
| 分钟成交 | `--minute-source lake`（缺省） | `--qlib-1min-root <my_data_1min>`（暗示 `qlib_1min`） |
| 日线辅助 | `--daily-source lake`（缺省） | `--qlib-day-root <my_data>`（暗示 `qlib_day`） |

topk 的分钟 `--dividend-type` 只能 `none`（`front` 仅 version12）。没有 `--qlib-data-root`，也没有 `--qlib-cost`。

```text
# 湖分钟 + 湖日线（默认）
csv_minute_backtest.py --strategy topk_dropout --pred-csv <pred> --stop-pct 0.10

# qlib 1min 成交 + qlib day 辅助
csv_minute_backtest.py --strategy topk_dropout --pred-csv <pred> --qlib-1min-root <my_data_1min> --qlib-day-root <my_data>
```

**危险组合（已记录，δ2 保持现状）：** 分钟 `--daily-source qlib_day` / `--qlib-day-root` **不会**像日线 `--qlib-data-root` 那样跳过 E-R6。qlib 后复权日线配湖 `none` 分钟是不同约定，读取器不认证 dump 域。见 [README CLI 价格域风险](README.md)。不要把「分钟开了 `--qlib-day-root`」说成已经对齐年化日线尺子。

#### 对照纪律

- 湖 `none`、湖 `front`、qlib `$close` 是三套价，§3 前复权假高峰就是混用。
- 年化 A 格 / #87 对齐锁的是 **日线 qlib bin + `--qlib-cost`**。默认可跑湖，只是另一套账（Q5）。
- 分数 sidecar 与价源无关：`--pred-csv` / `--scores-dir` 都要。

### 6.7 怎么跑、资金、产出

解释器：本仓 `vanna312`（`OSKH_MERGE_PYTHON` / `VANNA312_PYTHON`，否则 `D:\anaconda3\envs\vanna312\python.exe`）。不要系统 `python`。

**端到端（日线联合尺子）：**

```text
# MyQuant：全日分 + 便利 TopK 池。默认不过 ST/年龄/买点。
python my_scripts/export_daily_pool.py --pred <预测结果.csv> --topk 50 --asof pred_minus_one --out-dir exports/<run>

# 本仓：淘汰以 scores 为准；--pool-dir 只要日历/契约。
python backtest/research/csv_daily_backtest.py --strategy topk_dropout ^
  --pool-dir exports/<run> --scores-dir exports/<run>/scores ^
  --start <首个买入日> --end <末个买入日> ^
  --qlib-data-root <my_data> --qlib-cost --stop-pct 0
```

也可用 `--pred-csv` 代替 `--scores-dir`（买日 T 仍用 pred[T−1]）。分数 CSV：`code,score`，裸六位，UTF-8 无 BOM、LF。池契约：[pool-csv-contract.md](pool-csv-contract.md)（文件名=买入日 T）。

| 项 | 默认 | 年化账常用 |
|---|---|---|
| `--cash-total` | **2100 万** | **1e8**（须显式传，否则两套 NAV 不可比） |
| `--daily-quota` | 100 万 | 同；topk 新买额度再乘 0.95 / n_buy |
| 加仓 | `allow_add=False` | 不满仓只补 dropout/止损空位，名单再现不加第二笔 |
| `--workers` | 16 | |
| `--out-dir` | `backtest_output/csv_{daily\|minute}_topk_dropout_{start}_{end}/` | 目录已存在且非空则 **拒绝覆盖**，换戳 |

产物三件套：`summary.txt` / `daily_equity.csv` / `trades.csv`。对照看脚本 + 价源 + `--qlib-cost` + `--stop-pct` + 闸文件，不要只看策略名。盘后人工看成交走固定包：`scripts/research/export_csv_human_analysis.py --run-dir <该目录>`，提示词 [prompt-csv-human-analysis.md](prompt-csv-human-analysis.md)。

预热：默认向前 10 个交易日加载日线；开 `--return-threshold-filter` 则 20 日。warmup 日期必须落在 qlib `day.txt` 内，否则 SystemExit。

分钟另有 `--no-cache` / `--rebuild-cache`。分钟湖短于 `--end` 会缺 bar，接到今天改日线。

`--ration` / `--name-budget` 是共用引擎旗。topk 不是 `per_name`，买序来自 `planned_for_day` 分数 walk-down，不要拿文件行序当 50/5 轮换。

data-free 回归：`tests/test_topk_dropout_rules.py`、`test_topk_dropout_book_a.py` / `_b.py` / `_c.py`、`test_csv_strategy_books.py`。改止损核或 HELP_LOCK 必须带着跑。

### 6.8 开盘一次 decide（书侧时序）

每个交易日开盘：`bind_opening_held(ds, 当前持仓)` 调一次 `decide_topk_dropout`。当天的 `sell_gate` 与 `planned_for_day` **共用这一对 buy/sell**，卖完不重算。这是对齐 qlib one-shot 的关键，禁止「卖完再 decide 一次」造成多卖。

BT-B：`eligible_buy` 只过滤**新开**；不够 `len(buy)` 则沿未持仓分数序往下补。持仓变 ST **不**因此强制卖。止损卖掉后，次日仍在序且过闸 → **允许再买**。

缺分持仓按极低分参与排序并计数，不得因此多卖超过 `n_drop`。并列 `(-score, code)`，代码键 `000608.SZ`。

### 6.9 名字里带 TopK / 共用引擎 ≠ 本页这本书

本页只认 **`--strategy topk_dropout`**（别名 `topk` / `version_topk`）。下面几个容易撞名，关系如下。

**`topk_score_exit`：从这本书分出去的另一本书，不是 app 池。**  
同一套日线/分钟入口、同一套 TopkDropout 底座，多了一刀：开盘持仓当日分数 ≤0 则额外卖（`model_exit:nonpositive`，T6）。对照实验用 `topk_dropout` 当 control、这本书当 candidate。**不是**四条业务规则，也**不是** app 名单。

**`topk_app_dropout`：就是你说的 app 池那本，和 `topk_dropout` 不是同一本书。**  
独立入口 `csv_minute_backtest_topk_app_dropout.py`（仓位机借策略 7 的函数，**不改 v7**）。买池 = **app 日名单 ∩ qlib TopK**，不是对引擎实仓做 50/5 dropout。禁止 register 进 1–10。产物 `csv_minute_topk_app_dropout_*`。名字里的 topk 只表示和预测 TopK 求交。

**version6 / version8：和 TopK 轮换没有业务关系。**  
它们挂在 **`stock_pool`** 上做收益最大化（人工改书），和 `topk_dropout` **共用**成交核，卖点完全是另一套。唯一历史纠葛：早期曾把 TopK CSV **误塞进** v6/v8，M5 已证明名单宇宙对不上。不要改 v6 阈值冒充 50/5。总图：[research-backtest-entry.md](research-backtest-entry.md)。

**Mode A / Mode B：不是策略号。** 和策略 8 **同一棵 `stock_pool`、同一个收益最大化问题**；策略 8 是人工改书，Mode A/B 是机器网格（故意不抄 v8 规则）。给每天一份名单，名单上每出现一次就开一笔独立实例。买入都是名单当日**日线收盘**。差别只在卖：

- **模式 A**：只看日线，触发日按**日线收盘**卖。入口 `scripts/research/run_unified_exit_modea.py`。
- **模式 B**：卖改看**分钟**：先开盘跳空，否则该分钟收盘触价（不用 high/low）。入口 `scripts/research/run_unified_exit_modeb.py`。

不读预测分、不做 50/5 轮换、不走 `topk_dropout`。产出目录 `backtest_output/unified_exit_modea/` 与 `unified_exit_modeb/`，和 TopK 目录分家。提案：[stock-backtest-unified-exit-proposal-2026-09-17.md](stock-backtest-unified-exit-proposal-2026-09-17.md)。

另外：`joint-return-v1` 交接见 [handoff-joint-return-qlib-to-bt-2026-09-22.md](handoff-joint-return-qlib-to-bt-2026-09-22.md)（约束 PASS、旧钟 0 成交、Mode B 停）。不要和本页 NAV 对一个数。1.3 LEBS/MockQMT 是执行验收。

---

### 6.10 做过哪些实验、结果在哪、文件在哪

**没有**单独的「TopK 实验平台」仓库，也没有会进 git 的结果库。数字和 `summary.txt` 在宿主 `backtest_output/`（[`.gitignore`](../../.gitignore) 的 `/backtest_output/`），**不入库**。叙事以 MyQuant 年化账 / 填坑文为准。新跑必须另开目录，禁止覆盖。

可复用入口：

| 角色 | 路径 |
|---|---|
| 本仓成交（所有 BT 格的真身） | `backtest/research/csv_daily_backtest.py --strategy topk_dropout` |
| 本仓分数/闸 | `topk_dropout_scores.py` / `topk_dropout_eligibility.py` |
| MyQuant 导出 | `my_scripts/export_daily_pool.py` |
| MyQuant 现尺子重放 | `replay_highwater_current_ruler.py`、`replay_2025_st_age_vs_15.py`、`replay_10n3_two_year.py`、`replay_2024_oos_gates.py`、`replay_buy_stag15_once.py` |
| MyQuant 三闸诊断 | `diag_50n5_filters_on.py`、`diag_50n5_st_age.py` |
| 止损扫 | **没有**独立 grid runner；宿主对同一 CLI 换 `--stop-pct` / `--out-dir` |
| 结果叙事 | [年化账 §9](../../../MyQuant/docs/reviews/2026-09-17-annual-lift-status-handoff.md)；[填坑文](../../../MyQuant/docs/reviews/2026-09-16-scores-leading-zero-nav-lift.md)；T6：[lh3-flip](../../../MyQuant/docs/reviews/2026-09-17-annual-lift-next-knife-after-lh3-flip.md) |

本机 `backtest_output/` 里和这本书相关的目录（2026-09-22 盘点；换机器可能没有）：

| 批次 | 目录模式 | 什么 |
|---|---|---|
| overlay H-1 烟测（09-16） | `h1_topk_smoke_arm2_*`、`h1_topk_arm0_a_*`、`h1_topk_arm1_ab_*`、`h1_topk_arm2_abc_*`、`h1_topk_arm0_qlibalign_*`、`h1_topk_arm0_qliblimit_*` | 臂 0/1/2 + qlib 对齐中间态。早期有的还在追买，不是年化尺子 |
| 填坑链（09-16） | `lgb_zhangting_bt_stag15_*`（湖 / front / qlibbin / qlibcost / zfill / age） | 读码、价域、费率、ST/年龄逐步拧到 PortAna。假高峰目录仍在盘上，**禁止引用净值** |
| 年化对齐格（09-17） | `lgb_zhangting_bt_stag15_qlibbin_qlibcost_age_20260917` | 2026 A 格 BT；PortAna 在 MyQuant `exports/analysis/55c5bf77_replay_age_lot_20260917` |
| 2026 止损扫 | `lgb_zhangting_bt_2026_sweep_{nostop,stop05..stop30}` | 0/5/10/15/20/25/30，**日线触价** |
| 2025 止损扫 | `lgb_zhangting_bt_2025_sweep_*` | 同上，另一窗 |
| 宽度/闸重放 | `replay_20260917_*`、`replay_2025_8a061ea4_50n5_*`、`replay_10n3_2025_*`、`replay_10n3_2026_*` | 50/5 与 10/3、闸开/关 |
| T6 非正分退出 | `t6_sx0_control_*` / `t6_sx0_candidate_*` | 对照是 `topk_dropout`，候选是 **`topk_score_exit`**（另一本书） |
| 本会话 50/5 烟测（09-21） | `csv_daily_topk_dropout_qlib50n5_c5f4bccd_20260106_20260914` | pred `c5f4bccd`，闸与止损关，默认 **2100 万**本金（不是年化 1e8） |

**没有**找到 `csv_minute_topk_dropout_*`。分钟盘上只有邻居：`csv_minute_topk_app_dropout_*`（app∩TopK）、`csv_minute_topk_bcombo_*`。联合 50/5 对账从未落在分钟入口。

每个产物目录典型三件套：`summary.txt`、`daily_equity.csv`、`trades.csv`。要复现：对着 `summary.txt` 头几行的窗/费率，用 §6.7 命令另开 `--out-dir`，不要覆盖。

---

## 7. 会话共识（2026-09-22）

1. **不拆多本** `topk_dropout` / 不新开 `topk_dropout_close` / 不叫 version11。冲突来自改默认成交，不是共用一书。
2. **持续改进用开关**，并写进 HELP_LOCK 与本页。买点、ST、年龄、止损阈值、止损价域都是轴，不是新书。另开书的条件：买池或卖因变了（已有反例：`topk_app_dropout`、`topk_score_exit`）。
3. **默认止损价域保持触价**（`touch`）：旧扫参、BT-C 单测、HELP_LOCK 都不翻。
4. **日线 `--stop-fill close`**：T+1 后只看当日日线收盘是否 ≤ `cost×(1-p)`，是则按收盘卖；不先吃跳空、不按盘中最低触发价卖。默认 `touch` 不翻。分钟入口拒绝 `close`。
5. **日线 / 分钟用入口切换，不加 `--freq`**：
   - 日线：`backtest/research/csv_daily_backtest.py --strategy topk_dropout`
   - 分钟：`backtest/research/csv_minute_backtest.py --strategy topk_dropout`
6. **`close` 在两套引擎不是同一句话。** 分钟现扫描已是「开盘跳空 + 每根分钟 close」。日线 `close` = 日终收盘一判。在分钟语义单独立项之前，分钟入口遇到 `--stop-fill close` 应 **拒绝**，不要静默当成逐 bar close。若以后要分钟日终，另取值（例如 `eod_close`），不要把日线的 `close` 偷运过去。
7. 产出目录本来就分家：`csv_daily_topk_dropout_*` vs `csv_minute_topk_dropout_*`。对照看 **脚本 + `--stop-fill` + `--stop-pct` + 闸文件**，不要只看策略名。
8. 不复活 PortAna 当产品判据；50/5 研究账不改线上 10/3。
9. **买点条件 2 不要 MA5 斜率**（Q2）：只认 `close > MA20`。MyQuant 现码带斜率的 `--buy-state-filter` 标 `legacy`，不进本配方、不改线上默认。
10. **收盘止损遇跌停仍成交**（Q7）：拟 `--stop-fill close` 时，触发日收盘即使恰跌停，也按该收盘价卖出。不 skip、不 pending 到次日。这是本配方的研究约定，不是把默认触价/arm0 的涨跌停拒单改掉。
11. **同日止损先于 dropout**（Q6）：收盘臂与现核一样，先止损再 `sell_gate`。同日只卖一次，reason 走止损。

12. **买点旁路在 MyQuant 算、本仓查表**（Q3）：`export_topk_buy_state_sidecar.py` 写 close/MA20/MA60/`$winratio`；BT `--buy-state-file` 只查表。成交热路径不 `import qlib`。默认不传=不滤。
13. **盈筹用券商 `$winratio`**（Q4）：不是 CYQ parquet，也不做 250 日 Quantile 代理。这会改 0.10 买集，与旧闸不可混比。`topk_score_exit` 拒绝 `--buy-state-file`。

拟跑（编码后）：

```text
日线收盘止损：csv_daily_backtest.py --strategy topk_dropout --stop-pct 0.10 --stop-fill close
日线旧触价：  csv_daily_backtest.py --strategy topk_dropout --stop-pct 0.10
分钟（暂不改价域）：csv_minute_backtest.py --strategy topk_dropout --stop-pct 0.10
```

---

## 8. 待裁（停下来问人，不自裁）

| ID | 问 | 选项 / 备注 |
|---|---|---|
| Q1 | `--stop-fill` 取值名 | **已裁（2026-09-22）**：`touch`（默认）/ `close`（仅日线）。`close` = 日终收盘止损，使日线买/卖/止损都看 close（买与 dropout 本已收盘）。分钟对 `close` **拒绝**。分钟日终若要做，另取值，不复用 `close` |
| Q2 | 买点条件 2 | **已裁（2026-09-22）**：**不要 MA5 斜率**。条件 2 = `close > MA20`。现码带斜率的闸标 `legacy`，不进本配方、不改线上/年化默认 |
| Q3 | 买点接到哪 | **已裁（2026-09-22）**：MyQuant qlib 写旁路；本仓 `--buy-state-file` 查表。不在 simulate 热路径 `import qlib`。默认关（N6 / overlay R-8 训练默认不翻） |
| Q4 | 盈筹数据 | **已裁（2026-09-22）**：券商 `$winratio`（bins）。不用 CYQ `winner_ratio` parquet，不用 Quantile 代理 |
| Q5 | 价域 | **已裁（2026-09-26 修订）**：联合**日线**对照钉 qlib `$close` **日线**后复权 bin（`--qlib-data-root` + 常配 `--qlib-cost`）。湖日线 `none`/`front` 另账。分钟本仓仅 `none`——与日线 bin/湖 `front` 禁止混比；分钟价域归专题 [#214](https://github.com/baiyibing/MyQuant-backtrader/pull/214) / X-01（信号复权→成交 `none` 换算；#214 现 HOLD，非本页 impl GO），勿用分钟 `none` NAV 对齐年化日线尺子。生产默认「不传则湖」不翻。 |
| Q6 | 收盘止损与 dropout 同日 | **已裁（2026-09-22）**：**止损先**。与现核一致：先评止损（收盘臂按日终收盘），再评 `sell_gate` / dropout。同日只出一笔卖，reason 记止损 |
| Q7 | 跌停 | **已裁（2026-09-22）**：收盘止损臂上，收盘恰跌停 **仍按该收盘价成交**。不 defer、不记 skip。只约束拟 `--stop-fill close`；默认触价核与 arm0「涨跌停当日买卖都不做」不翻。书的 `limit_down_pending=False` 仍表示不把未成交卖挂到次日开盘 |
| Q8 | 本次是否同时开 ST/年龄 | **仍开**：年化 A 格还叠了 5 日涨幅&gt;15% 挡。四条口述未提这条，勿静默叠加 |
| Q9 | 窗与 pred | **已裁（2026-09-26）**：钉年化主 pred **`8a061ea4`** + 2026 OOS 窗 **`20260106–20260914`**。`c5f4bccd` 仅烟测，不作对照归因窗。不覆盖 `pred.pkl`。 |
| Q10 | `--cash-total` | **已裁（2026-09-26）**：对照实验一律显式 **`--cash-total 100000000`**，全臂同本金。CLI 默认 2100 万不翻。 |
| Q11 | 闸做在哪边 | **随 Q3**：分数导出仍不过闸；买点用独立 sidecar，BT 只查表。不要 MQ `--buy-state-filter` 滤完分数再让 BT 滤同一层 |

编码门槛：Q1–Q4/Q6/Q7 已裁（`--stop-fill close` 仅日线；买点旁路 + `$winratio`；止损先；收盘跌停仍成交）。对照实验 Q5/Q9/Q10 **已裁（2026-09-26）**，按上表钉日线价域、pred/OOS 窗与全臂本金。**Q8 仍开**，勿静默叠年化 A 格的 5 日涨幅&gt;15% 挡。本次仅记人裁，不改生产默认，不授权 #214 实施；分钟信号→`none` 换算 / X-01 仍归 #214 HOLD 专题。

不变边界：不传 `--qlib-data-root` 仍走湖；CLI 本金默认仍为 2100 万；`--stop-fill touch` 默认、线上 10/3 不翻；PortAna 不复活产品地位；seal bars = `qlib_bin`；validate 默认 `v1`。

---

## 9. 现有开关（CLI as-built；拟项单独标）

公共解析在 `add_csv_backtest_common_args` / `add_topk_dropout_args`。其它策略书会看见 topk 旗，但只有 `topk_dropout`（及 `topk_score_exit` 复用分数入口）消费。v6 的 `--stop-pct` **拒绝 0**；topk **允许 0**。

| 开关 | 默认 | 日线 | 分钟 | 作用 |
|---|---|---|---|---|
| `--strategy topk_dropout`（`topk` / `version_topk`） | 必填 | ✓ | ✓ | 选书 |
| `--pred-csv` / `--scores-dir` | 无则 fail-closed | ✓ | ✓ | 全日分；买日 T 用 pred[T−1] |
| `--pool-dir` | 仓内 `stock_pool/` | ✓ | ✓ | 日历/契约；**不以池 50 行当卖出** |
| `--topk` `--n-drop` | 50 / 5 | ✓ | ✓ | 轮换宽度 |
| `--stop-pct` | 书 0.10；显式 `0`=关 | ✓ | ✓ | 阈值。价域见 §6.5，两边**不是同一成交** |
| `--st-daily-file` | 不传=不滤 | ✓ | ✓ | PIT `is_st`，缺路径 fail-closed |
| `--age-map-file` `--age-days` | 不传=不滤；60 | ✓ | ✓ | 新开年龄 |
| `--return-threshold-filter` | 关 | ✓ | ✓ | 5 日收盘涨幅&gt;15% 挡新开 |
| `--dividend-type` | `none` | none/front/back | 非 v12 只能 none | 湖复权；front/back 跳过 E-R6 |
| `--daily-root` | 路径 SSOT 湖 | ✓ | — | 覆盖 1d hive |
| `--qlib-data-root` | 关 | ✓ | — | 日线 `$close` bin |
| `--qlib-cost` | 关（10bp/10bp） | ✓ | **无此旗** | 5bp/15bp/min5 |
| `--qlib-1min-root` / `--minute-source` | 湖 | — | ✓ | 分钟行情 |
| `--qlib-day-root` / `--daily-source` | 湖 | — | ✓ | 分钟引擎的日线辅助（涨跌停/除权），不是日线联合尺子 |
| `--start` `--end` `--cash-total` `--daily-quota` `--workers` `--out-dir` | 各入口缺省 | ✓ | ✓ | 窗与资金。日线默认 start `20251023` end `20260909`，**年化窗须改** |
| `--no-cache` `--rebuild-cache` | 用缓存 | — | ✓ | 分钟窗缓存 |
| `--ration` / `--name-budget` | file_order / 100 万 | 共用旗 | 共用旗 | topk 非 per_name；买序不是 CSV 行序 |
| **`--stop-fill`** | 默认 `touch` | 日线 `close` 已落地 | 拒绝 `close` | 见 Q1；`--stop-fill close` 只改止损成交 |
| **`--buy-state-file`** | 不传=不滤 | ✓ | ✓ | 见 Q3/Q4；新开；(close&lt;MA20 且 close&lt;MA60 且 `$winratio`&lt;0.10) 或 close&gt;MA20。`topk_score_exit` 拒绝 |
| **`--buy-state-rule`** | `oral` | ✓ | ✓ | `above-ma20` 关掉盈筹抄底，只留 close&gt;MA20。`above-ma20-week20` 再要求 close&gt;qlib 20 周均线（每周第一个交易日收盘的 20 期均值；用日线收盘算，分钟成交也可挂这道闸）。`above-ma5-ma20-week20` 再要求 close&gt;个股 5 日均线（含当日的 5 根收盘均值）。须配 `--buy-state-file` |
| **`--index-ma5-gate`** | 关 | ✓ | ✓ | 新开。全市场只看上证 000001.SH。信号日收盘 &lt; MA5 → 次日所有新开不买 |
| **`--keep-buy-vacancy`** | 关 | ✓ | ✓ | 原买名单没过闸则空着，不按分数往下补。资金仍按原名单只数分，空位留现金 |

### 9.1 MyQuant 侧（出分 / 闸，不是本仓 CLI）

导出（overlay MQ-A；**默认不过** ST/年龄/买点）：

```text
python my_scripts/export_daily_pool.py --pred <csv> --topk 50 --asof pred_minus_one --out-dir exports/<run>
```

写出每日 TopK 裸码 + `scores/YYYYMMDD.csv` 全日分。拒绝写进 `stock_pool/`。

```text
python my_scripts/export_topk_buy_state_sidecar.py --qlib-dir ~/.qlib/qlib_data/my_data \
  --start 2026-01-06 --end 2026-09-14 --out exports/buy_state_winratio.parquet
```

写出 `trade_date,code,close,ma20,ma60,winratio`。盈筹列是 `$winratio`，不是 CYQ。NaN 行丢弃；BT 缺行 fail-closed。

买闸在训练/重回测上，默认全关，见 `buy_eligibility.py`：

| 开关 | 默认 | 含义 |
|---|---|---|
| `--buy-state-filter` | 关 | 现码：双均线下且盈筹&lt;10%，**或**站上 MA20 **且** MA5 斜率 ≥ −30°（`legacy`）。**本配方 Q2：条件 2 无斜率**。年化 N6：50/5 继续关 |
| `--st-filter` | 关（导出不过） | 有 `st_daily.parquet` 时只认当日 `is_st`，与 BT 相同 |
| `--age-filter` | 关 | 上市不足 `age_days`（默认 60） |
| 5 日涨幅 15% | 策略层可选 | 与买点独立；BT 对应 `--return-threshold-filter` |

盈筹：联合配方用 `$winratio`（Q4）。现码 `--buy-state-filter` 仍优先 CYQ parquet `winner_ratio`，未命中回退 250 日收盘 10% 分位——那是 `legacy`，不进本配方。本仓不重做 CYQ feeder（H13）。

`custom_train_backtest.py` / 线上 10/3 **不要**为本页打开这些闸去改默认训练。Q3 已裁：MQ 出旁路、BT 查表，避免 MQ 滤完 BT 再滤同一层。Q2：联合旁路条件 2 不写 MA5 斜率。

年化 / 联合对账惯用（只日线 qlib bin）：

```text
csv_daily_backtest.py --strategy topk_dropout --pred-csv <MyQuant pred>
  --qlib-data-root <my_data> --qlib-cost --stop-pct 0
  [--st-daily-file ...] [--age-map-file ...] [--return-threshold-filter]
  [--buy-state-file exports/buy_state_winratio.parquet]
  [--stop-fill close]
```

默认可改走数据湖（不传 `--qlib-data-root`）。分钟默认同样是湖；qlib 1min/day 见 §6.6。分钟没有 `--qlib-cost`，不要用分钟入口冒充年化尺子。

---

## 10. 明确不做

- 为收盘止损复制策略书或 register 进 1–10。
- 把 overlay 日线触价默认改成收盘。
- 分钟 `--stop-fill close` 静默复用逐 bar close。
- 用 PortAna NAV 判本页胜负；用 50/5 研究账改线上 10/3。
- 把 Mode B / v8 分钟止损网格当成 TopK 联合轮换的同一条线。
- 在成交热路径 `import qlib` 去挂 `init` / Exchange / PortAna（禁的是运行时，不是 `Mean($close)` 语义；买点均线对已加载 `$close` 滚动即可）。
- 把 §3 里的假高峰（丢前导零 / 前复权 / 旧 ST）写进候选。
- 把湖 `none` / 湖 `front` / qlib `$close` 的净值合成一张表当同一把尺子。
- 默认 2100 万本金去对年化 1e8 的格。
- MyQuant 已过滤的名单上，BT 再开同一层闸还不声明。

---

## 11. 本页怎么用

本页是联合 TopK **活地图**：背景、已落地实现、开关、待裁。不是实施任务书，也不是 overlay 的替身。

| 文档 | 角色 |
|---|---|
| 本页 + [#164](https://github.com/baiyibing/MyQuant-backtrader/issues/164) | 持续改进账；GitHub 问题是入口，**正文以本文件为准** |
| [plan-topk-dropout-overlay-2026-09-16.md](plan-topk-dropout-overlay-2026-09-16.md) | 已 GO 的默认书，**冻结**；不要为新实验改它的默认触价 |
| HELP_LOCK `strategy_topk_dropout_rules.py` | CLI `--help` 契约；加开关必须改这里 + 本页 + 单测 |
| 年化账 / 填坑文（MyQuant `docs/reviews/`） | 数字与坑的明细；本页只摘要 |

加开关：一书加旗，不复制 `strategy_topk_dropout_rules.py`。改默认成交须先人裁。未 GO 不改止损核。

---

## 12. 修订

| 日期 | 什么 |
|---|---|
| 2026-09-22 | 建页。收录两仓分工、四条规则缺口、止损扫是日线、开关 vs 多版本、日线/分钟入口、待裁 Q1–Q9。 |
| 2026-09-22 | 补 §1 来龙去脉、§2 对齐尺子、§3 踩坑（引用 overlay / #87 / 填坑文 / 年化账 / 三仓定位）。 |
| 2026-09-22 | 补 §6.4 落地清单、§6.5 日线/分钟 as-built、§9 现成 CLI（含分钟无 `--qlib-cost`）。 |
| 2026-09-22 | 补 §6.6：日线/分钟均可湖或 qlib bin；费率与价源正交；禁止混比。 |
| 2026-09-22 | 补缺口：§6.7 怎么跑/资金/产出、§6.8 开盘一次 decide、§6.9 邻居、§9.1 MyQuant 闸、§11 本页维护、Q10–Q11。 |
| 2026-09-22 | 补 §6.10：宿主实验目录盘点（gitignore，不入库）；无独立 grid runner。 |
| 2026-09-22 | 改写 §6.9：分清 score_exit / app 池 / v6v8 与本页书的关系。 |
| 2026-09-22 | §6.9 补 Mode A/B 白话：统一卖出网格的日线/分钟两种成交，不是策略号。 |
| 2026-09-22 | §6.9：v8 与 Mode A/B 同属 `stock_pool` 收益最大化；总图 [research-backtest-entry.md](research-backtest-entry.md)。 |
| 2026-09-22 | §6.9：joint-return-v1 = Grok Bot/4090 意图回放，不是本页 CSV 书。 |
| 2026-09-22 | **Q2 人裁**：买点条件 2 不要 MA5 斜率，只认站上 MA20。现码带斜率闸当 `legacy`。 |
| 2026-09-22 | **Q7 人裁**：收盘止损臂上收盘恰跌停仍按收盘价成交。 |
| 2026-09-22 | **Q6 人裁**：收盘止损与当日 dropout 止损先（与现核一致）。 |
| 2026-09-22 | **Q1 人裁并落地**：`--stop-fill touch\|close`；日线 close 止损；分钟拒绝 close。 |
| 2026-09-22 | 写清禁 `import qlib`：**目的**是成交核不绑 qlib 运行时；**手段**是热路径不 import。对齐 `Mean($close)` 不是破例。 |
| 2026-09-22 | **Q3/Q4 人裁并落地**：MyQuant 旁路 `$close`/`Mean(20/60)`/`$winratio`；BT `--buy-state-file` 查表。score_exit 拒绝此旗。MQ `--buy-state-filter` 默认不翻。 |
| 2026-09-26 | **Q5/Q9/Q10 人裁**：日线对照钉 qlib `$close` 日线后复权 bin（`--qlib-data-root` + 常配 `--qlib-cost`），湖日线另账；分钟仅 `none`，禁与日线 bin/湖 `front` 混比，信号→`none` 换算归 #214/X-01 HOLD，非本页 impl GO。pred 钉 `8a061ea4` + OOS `20260106–20260914`，`c5f4bccd` 仅烟测、不作归因窗，不覆盖 `pred.pkl`；全臂显式 `--cash-total 100000000`。Q8 仍开，勿静默叠 5 日 15% 挡；生产默认与上述不变边界均不翻。 |
