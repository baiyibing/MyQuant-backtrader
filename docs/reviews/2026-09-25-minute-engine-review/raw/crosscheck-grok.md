# 分钟回测三份审查的交叉核对（Grok，2026-09-25）

- 对象：`/workspace/wt-bt-minute-review`，`HEAD = 057761a41028540b60e7438afa157635d84c84ba`（本轮 `git rev-parse` 复核）。三份报告都在：`report-codex.md`（Codex）、`report-kimi.md`（Kimi）、`report-grok.md`（Grok 首轮）。
- 做法：只读代码。合成路径只用 `~/.venvs/bt-ci/bin/python`，`PYTHONDONTWRITEBYTECODE=1`，直接调用公开 `simulate()`，不读湖、不跑会加载 `tests/conftest.py` 的 pytest（该 conftest 会在仓内写 `artifacts/pytest_tmp`）。人裁原文沿三份报告与工作树 plan / handoff / Slice D 回执；本轮把「现在代码是否仍是那个选择」对到行号，没有重开 `context/` 里每一条评论。
- 结论先说：三套策略的身份没有分歧。会改默认分钟账的硬问题里，**version12 混价域、共享书循环把全天卖款提前入账、version11 出场 SMA5 用原始价**，Grok 与 Codex 一致，本轮合成复现。Kimi 漏了前两条，并把「成交和估值全程是 none」写成了总规则，这句话对 version12 不成立。Codex 独有、本轮复现的还有 **8.3 涨停追买绕过 50% 试探** 和 **8.1 恰好 +60% 的浮点错档**。Kimi 独有、本轮复现的是 **止损卖掉 lot0 之后 +20% 台阶永久停加**。费用、同 bar 收盘、止损不看 low、14:57 后仍按连续竞价成交，是已经写进人裁的研究口径，保留默认，不要再标成实现写错。

## 0. 三套策略：三份报告怎么认，以谁为准

三份报告认的是同一组东西。任务清单里的编号顺序和当天落地顺序不一样，以提交时间为准。

| 当天顺序 | 是什么 | 代码 | 证据 |
|---|---|---|---|
| 1 | 策略 8 里程碑 **8.1 / 8.2 / 8.3**（一族三本，不是一本新类） | `backtest/research/strategy8_1_rules.py`、`strategy8_2_rules.py`、`strategy8_3_rules.py`（8.3 卖点委托 `livermore_exit_rules.py`）；注册 `csv_strategy_books.py:1339-1377` | `b2b406e` 2026-09-21 13:05 +0800，13:07 合入 `599a894`（`feat/v8-milestone-books`，无独立 PR 号）。本轮 `git log` 复核了时间 |
| 2 | **策略 12 / version12**，金榕元均线减仓书，`--strategy 12` | `strategy12_rules.py`、`strategy12_engine.py`；接线 `csv_strategy_books.py:648-672,1458-1470` | 报告一致：`#151` 当天合入，随后 `#158` / `#169` / `#170` |
| 3 | **策略 11 / version11**，ma_chip CSV 移植 | `strategy11_rules.py`、`scripts/data/export_strategy11_pool.py`；`csv_strategy_books.py:984-1003,1446-1456` | 报告一致：`#152` |

不算第三套：

- **#156** `fullstrat_research_*.py` 是研究回放，不进 `BOOKS`。三份报告一致。人裁留在第 4 节。
- **ma_infra**（`backtest/research/ma_infra.py`）是共享库。Codex 写明 `#150` 先合文档、代码在 `#154`。Kimi / Grok 也没有把它当成策略。
- **8.4 / 8.5 / 8.6** 是 `21ac511`（2026-09-23 14:57 +0800），不在 09-21 这三套里。Grok 写了，另外两份没有拿来充数。

分钟路径三本并不相同，Grok 的分法与代码一致：8.1/8.2/8.3 走共享扫描和 14:55 池买；策略 12 走 `run_minute_day`；策略 11 `minute_open=True`，买卖钉在 `hm==570` 的 open（`csv_minute_backtest.py:589-592,773-793`）。

Kimi 把策略 12 放在第 1 位，是任务清单顺序，不是当天提交顺序。身份本身没有需要改的地方。

## 1. 共识排序

严重度按「默认研究会不会算出另一本账」排，不按「是不是有人裁」排。有人裁的研究口径降到表后，避免和实现错误混在一张胜负榜里。`x/3` 是把它写成发现的报告数；本轮复现的，置信度高于「只有一份报告提到」。

| 排名 | 合并 ID | 严重度 | 状态 | 报告 | 位置 | 一句 |
|---:|---|---|---|---|---|---|
| 1 | X-01 `F-01`/`M01` | critical | confirmed | 2/3 | `csv_minute_backtest.py:1108-1125,1180-1186,990-996`；`strategy12_engine.py:223-267` | version12 分钟：front 日线做 MA、涨跌停和市值，none 分钟做成交 |
| 2 | X-02 `F-12`/`M02` | major | confirmed | 2/3 | `csv_minute_backtest.py:731-853` 然后 `:888-964` | 共享书循环先把全天卖出入账，再买 09:45 / 14:55；v7 跨股票同样逆时 |
| 3 | X-03 `F-11`/`M03` | major | confirmed | 2/3 | `strategy11_rules.py:102-106`；`csv_simulate_loop.py:535-539`；`export_strategy11_pool.py:281` | version11 进场在 front，出场 SMA5 在引擎 none 日线上 |
| 4 | X-04 `M04` | major | confirmed | 1/3 | `csv_simulate_loop.py:275-331`；`strategy8_3_rules.py:45-50` | 8.3 首笔涨停进追买队列时用的是 100 万，不是 50% 试探 |
| 5 | X-05 `M05` | major | confirmed | 1/3 | `strategy8_1_rules.py:41-48,89-92` | 峰值恰好 +60% 时 `peak/cost-1` 变成 `0.6000000000000001`，错进 +50% 地板 |
| 6 | X-06 `F-S12-1` | major | confirmed | 1/3 | `strategy12_rules.py:165-170`；`strategy12_engine.py:106-107`；`csv_ledger.py:285` | 止损可以卖光 lot0；同日留下的新 lot 没有 lot_id 0，台阶永久停加 |
| 7 | X-07 `F-14`/`M06` | major | confirmed | 2/3 | `market_layer.py:57-64` | 名称命中 ST 一律 5%，不看板块、不看 2026-07-06 |
| 8 | X-08 `F-02` | major | confirmed（幅度 needs-data） | 1/3 | `csv_minute_backtest.py:1108-1123`；`export_strategy11_pool.py:281`；`docs/backtest/data/daily-adjusted-update-ssot.md:22,59-64,94` | 整段 front 分区按最新锚落盘，加载器不按决策日重锚 |
| 9 | X-09 `F-13` | major | confirmed | 1/3 | `csv_daily_backtest.py:382-403`；`csv_minute_backtest.py:328-336` | 同一止损公式：日线用 low、按触发价卖；分钟不看 low、按 close 卖 |
| 10 | X-10 `F-03`/`M07`/`F-E5` | major | confirmed | 3/3 | `csv_ledger.py:223-233,254-259` | 所有板块买入都整百，688/689 可以买 100 股；卖出可以是任意正股数 |
| 11 | X-11 `M10` | major（公开 API） | confirmed | 1/3 | `csv_minute_backtest_v7.py:333-350`；CLI `:660-667` | v7 对 DataFrame 输入在不传 `index_days` 时日历只剩名单日 |
| 12 | X-12 `M08` | major | confirmed（是否已命中旧缓存 needs-data） | 1/3 | `ashare_bars.py:416-418,584-590` | 分钟缓存文件名只有 `minute_none_{start}_{end}`，命中不核对湖来源 |
| 13 | X-13 `M09` | major（仅显式打开权益时） | confirmed | 1/3 | `csv_minute_backtest.py:734-742`；`csv_minute_backtest_v7.py:373-381`；`strategy12_engine.py:217-218` | 默认没有公司行动。打开之后，主书和 v7 缺当天 bar 会跳过登记 |
| 14 | X-14 `F-05`/`F-E2` | major（模型，不是写错） | confirmed | 2/3 | `csv_minute_backtest.py:317-336`；`csv_minute_backtest_v7.py:400-403` | 分钟止损不看 low；触发按该根 close。HELP 已写「盘中触线按该分钟 close」 |
| 15 | X-15 `F-V11-6` | major（验收状态） | confirmed | 3/3 | `docs/backtest/reviews/slice-d-version11-seed30-universe-2026-09-21.md:6` | version11 Slice D 文档状态仍是 STOPPED，收益 / parity 没有对照 |

Kimi 没进前 15、但本轮认为不该升成缺陷的：同 bar 收盘（`F-E1`）、默认 10bp（`F-E4`/`F-04`）、收盘集合竞价不建模（`F-E3`）、cap 打开后 version11 开盘零成交（`F-V11-1`）。它们是人裁本身。见第 3 节。

## 2. 合并发现

状态只使用 **confirmed** / **disputed** / **needs-data**。plainly wrong 的句子在附录，不占排名。

### X-01 分钟策略 12 把 front 信号、none 成交、front 估值放进同一本账

- 来源：Grok `F-01` critical；Codex `M01` critical。Kimi 没有这条发现，§1.5 写「成交与估值全程 `dividend_type=none`」，§2.1 写人裁已全部落实。
- 状态：**confirmed**。严重度维持 **critical**。
- 代码：`run()` 对 version12 强制日线 `dividend_type=front`（`csv_minute_backtest.py:1108-1125`）。分钟默认 none，front 分钟可选且缺分区即失败（`:1049-1055,1129-1138`）。混域时 `exdiv=None`，不加载 E-R6（`:1180-1186`）。`run_minute_day` 用这份日线的昨收做 MA，并用 `_limits` 把同一昨收送进涨跌停（`strategy12_engine.py:223-234,128-135`）。净值 `mark_bars=daily_bars`（`csv_minute_backtest.py:990-996`，`csv_simulate_loop.py:565-571`）。
- 本轮合成（无湖）：现金 5,000,000，`name_budget=1,000,000`，`600000.SH`，分钟价全天 10。

| 日线收盘 | 首日权益 | 成交 |
|---:|---:|---|
| 10 | 4,999,000 | 买 100,000 @ 10，之后不卖 |
| 10.5 | 5,049,000 | 买 @ 10；次日卖 50,000，原因 `ma_signal:MA5-derisk`，价格仍是 10 |
| 12 | 5,199,000 | 买 @ 10；之后无卖出。`defer_sell_limit_down=0`。每根 open=10 低于用 front 昨收算出的跌停 10.80，扫描器在 `csv_minute_backtest.py:330-331` `continue`，不记延期 |
| 5 | 5,000,000 | 无成交，`skip_limit_up=1`。原始价 10 高于 front 涨停 5.50 |

这四行与 Grok 的表一致，也覆盖 Codex 的「front 更低则拒买、front 历史改写则该减不减」同一机制。现有测试夹具把日线和分钟都放在 10 元附近（`tests/test_strategy12_engine.py:22-28`），同域断言发现不了它。
- `#158` 批准的是「日线信号 front、分钟成交 none、禁止静默再乘 k」。代码把这三句接上了。它没有把 MA 换回原始价单位，也没有用 none 昨收算涨跌停，也没有用 none 收盘做市值。Grok / Codex 把这句说成缺口，成立。Kimi 把「接线符合人裁」说成「账是对的」，不成立。
- 已公开的分钟五本（`docs/backtest/reviews/slice-d-minute-five-book-20260922c-2026-09-22.md:13-37`）使用 `--dividend-type none`，tip `6aeffef`，其中 `s12_minute` NAV 19,384,883.71 / 收益 −7.69%。该回执自己写明不主张 parity。这张表不能拿来和四本 none 书比好坏。本轮没有重跑 4090。

### X-02 全天卖出先入账，后来的卖款可以支付更早的买单

- 来源：Grok `F-12` major；Codex `M02` major。Kimi §1.6 只写「卖出资金当日可用，与 A 股一致」，没有写日内顺序。
- 状态：**confirmed**。严重度维持 **major**。
- 代码：共享循环先对每只持仓扫完当天并 `_sell`（`csv_minute_backtest.py:731-853`），然后才 `run_chase_due_day`（`:888`）和 `run_pool_buys_day`（`:934`）。`execute_buy` 只看当时的 `st.cash`（`csv_ledger.py:263-266`）。
- 本轮合成：version8，`stop_pct=0.05`，现金 1001，A 以 10 元买 100 股后现金为 0。次日 A 在 14:59 以 9.4 卖出，B 的 14:55 报价为 6。记录顺序是先 `SELL A` 再 `BUY B` 100 股，现金余 **338.46**。与 Codex 的余数一致。本夹具里 A 的 14:59 开盘也是 9.4，所以原因落在 `stop_loss:gap_open`；Codex 写成 close 触发的 `touch`。两种触发都在卖扫阶段入账，14:55 的买单都看得到这笔钱。
- Grok 写「v7 按分钟向前，没有这条穿越」。这句 **不成立**，放进附录。v7 是「一只股票扫完当天所有 bar，再换下一只」（`csv_minute_backtest_v7.py:371-392`），现金是同一本 `state.cash`。排在前面的股票若在 15:00 卖掉，排在后面的股票当天上午就能用到这笔钱。同一只股票内部按 bar 顺序，这个范围内 Grok 是对的。
- 策略 12 的 `run_minute_day` 按 `hm` 前进（`strategy12_engine.py:242-290`），更晚分钟的卖出不会支付更早的买单。同一根 `hm` 上，卖出循环先于 `_normal_buys`，同一分钟的卖款可以支付同一分钟的买单。这是剩下的同刻顺序，比「用 15:00 的钱买 09:45」小。Codex 要求把同刻优先级写清楚，成立。

### X-03 version11 出场 SMA5 在原始价上，进场条件在前复权上

- 来源：Grok `F-11` major；Codex `M03` major。Kimi 未列。
- 状态：**confirmed**。严重度维持 **major**。
- 代码：导出器读 `1d/dividend_type=front`（`export_strategy11_pool.py:281`）。分钟 `run()` 只允许 version12 使用 front 日线，version11 的日线是 none（`csv_minute_backtest.py:1054-1055,1108`）。`run_eod_exits` 把这套日线的收盘序列交给 `eod_exit`（`csv_simulate_loop.py:535-539`）。`eod_exit` 对末尾 5 根做 `sma_series`（`strategy11_rules.py:102-106`）。`mapped_prev_close` 只改传给阴阳线的那一个昨收，不改 SMA 窗口。
- 本轮合成：买入日收盘 10.5 进入 HOLD；次日原始收盘 9.45。持仓 `pending_exit=ma_signal:SMA5`。原始窗口 SMA5 = **9.99**。同一经济路径若把除权前价格按 0.9 缩放，窗口 `[9, 9, 9, 9.45, 9.45]` 的 SMA5 = **9.18**，9.45 不破线。与 Codex 的两个 SMA 数字一致。
- 没有除权时两边可以重合。偏差出现在持仓跨过除权、原始均线跳空的时候。Slice D 没跑，这个偏差没有被旧档案吸收。

### X-04 8.3 涨停追买不用 50% 试探预算，还依赖名单里前一只

- 来源：只有 Codex `M04` major。Grok `F-09` 是另一件事（加仓笔数没有上限），见 X-23。
- 状态：**confirmed**。严重度维持 **major**。
- 代码：`run_pool_buys_day` 在循环外把 `per` 设成 `name_budget`（`csv_simulate_loop.py:275-276`）。涨停时 `queue_limit_up_chase(..., per, ...)` 发生在 `name_lot_budget` 之前（`:315-331`）。`lot_budget` 对空仓和已有仓都返回预算的 50%（`strategy8_3_rules.py:45-50`），但追买次日 `run_chase_due_day` 直接用队列里的 `per_ch`（`csv_simulate_loop.py:148,209`），不再调用 `name_lot_budget`。循环里一旦有普通买走过 `:330-331`，`per` 被改成 50 万，后面的涨停票就排队 50 万。
- 本轮合成：`name_budget=1,000,000`，次日 09:45 成交价 11。名单里只有涨停票时，追买 **90,900** 股，名义 **999,900**。前面先有一只普通买时，同一涨停票追买 **45,400** 股，名义 **499,400**。`_buy_size(1_000_000, 11)=(90900, 0)`，`_buy_size(500_000, 11)=(45400, 0)`。与 Codex 一致。
- 首仓可以接近预算的两倍，并且同一只票的股数随 CSV 行序变化。

### X-05 8.1 恰好 +60% 的峰值被分进更高一档

- 来源：只有 Codex `M05` major。
- 状态：**confirmed**。严重度维持 **major**。
- 代码：`peak_ret = peak/cost - 1` 后与区间右端做 `<=`（`strategy8_1_rules.py:41-48,89`）。档 `(0.40, 0.60]` 的地板是 +30%，`(0.60, 0.80]` 的地板是 +50%。
- 本轮：`16/10 - 1` 的 float 是 `0.6000000000000001`，`band_floor` 返回 **0.50**。`take_profit_reason(14, 10, 16)` 返回 `trail:band:50`。把同一比较的输入写成精确 `0.60` 时，地板是 **0.30**，现价 14 高于成本×1.30，不卖。这不是分以下的金额残差，边界上的持仓会被提前卖掉。

### X-06 止损卖掉 lot0 之后，+20% 台阶找不到父 lot

- 来源：只有 Kimi `F-S12-1` major。Grok / Codex 写了「止损不保留 lot0 地板」（`#170` 只钳减仓），没有把「台阶永久停加」列出来。
- 状态：**confirmed**。严重度维持 **major**。触发面比混价域窄：当天必须先留下一笔卖不掉的新 lot，再把旧 lot0 止损卖光。
- 代码：`keep_anchor` 只在原因是 `REDUCE` 时为真（`strategy12_engine.py:106-107`）。止损卖光后 lot 对象删除，`lot_id` 不回收（`csv_ledger.py:285,429-439`）。`step_add_due` 找不到 `lot_id==0` 就返回 False（`strategy12_rules.py:165-167`）。
- 本轮合成（`300001.SZ`，20% 档，止损线高于跌停）：池买 lot0 1000 股 → 减 500 → 买回 lot1 500 → 止损卖掉剩余 lot0 500。剩余只有 `(lot_id=1, shares=500)`。之后价格 12.5（相对成本 +25%）没有 `add:step20`，`steps` 仍为 0。
- 主板 10% 上，若 MA10 接近昨收，止损线 `MA10×0.90` 会落进跌停价，卖出被跌停门吃掉，这条路径更不容易出现。创业板 / 科创板 20% 档上，止损线可以落在跌停价之上，本轮就是这条。P13 只保护减仓，不保护止损。HELP 没有写这个分叉。

### X-07 名称里一带 ST 就用 5%

- 来源：Grok `F-14` major；Codex `M06` major。Kimi §1.3 把「ST 名称正则 5%」写成对齐，只把「注册制前 5 日无涨跌幅」标成缺口。
- 状态：**confirmed**。严重度维持 **major**。
- 代码：`is_st_name` 命中后直接 `return 0.05`，不再看前缀，函数也没有日期参数（`market_layer.py:57-64`）。未知前缀只要名称像 ST，同样是 5%，不是 fail-closed。
- 制度：2026-07-06 起沪深主板风险警示股票由 5% 改为 10%。当日公开报道（中国证券报、北京商报）写的是主板 ST/*ST，并举例主板涨跌停已按 10%。研究默认窗 `20251023–20260909`（`MINUTE_LAKE_END`，`ashare_bars.py:26`）跨过这一天。创业板 / 科创板 / 北交所风险警示与板块同幅（20% / 20% / 30%）是 Codex 所引的既有规则；本轮没有重下交易所 PDF。仅「见名即 5%」加「主板 2026-07-06 起应为 10%」已经足够说明档位错。Kimi 把 5% 写成对齐，漏了日期和板块。
- v7 默认还有第二层：`--asof-pool-names` 默认关，窗口末名铺满整段（`csv_minute_backtest_v7.py:609-611,650-667`）。这修不了 5% 本身。

### X-08 整段前复权分区含有未来除权

- 来源：Grok `F-02` major。Codex 在复权节写了 forward 序列必须和探测价同域，没有单独编号。Kimi 未列。
- 状态：机制 **confirmed**；窗口里改写了多少信号 **needs-data**（本轮未打开 parquet）。严重度维持 **major**（对用 front 做信号的 version12 日线和 version11 导出）。
- 代码：加载按整段分区读入，没有按日 `P_raw(t)×F(t)/F(D)`（`csv_minute_backtest.py:1108-1123`，`export_strategy11_pool.py:281`）。数据合同写明：除权股 delete 后全历史重下 QMT front；非除权日路径 B 把当日 front 写成当日 none（`docs/backtest/data/daily-adjusted-update-ssot.md:22,59-64,94`）。因此后发生的除权会改写更早的 front 价格。周线 `prefix_equivalent` 只截断周线样本，不重锚复权因子（`ma_infra.py:125-139`）。
- 日线策略 12 的 MA 和成交都在这份 front 上，单位内部一致，盈亏仍不是人民币现金。version11 的进场边缘同样读它，再叠 X-03。

### X-09 日线止损按最低价、以触发价成交；分钟止损按收盘

- 来源：Grok `F-13` major。Codex 在 §1.2 写了分钟不用 low，没有单独对比日线触发价。Kimi 只写了分钟。
- 状态：**confirmed**。严重度维持 **major**（同一套 8.x 公式的两个宿主，不是某一边抄错公式）。
- 代码：日线在 open 未破线时，若 `low <= trigger`，按触发价卖（`csv_daily_backtest.py:396-403`）。`--stop-fill close` 才改收盘价，分钟入口拒绝这个开关（`csv_minute_backtest.py:1043-1046`）。分钟扫描不读 low，`stop_loss:touch` 用 close（`:328-336`）。v7 第一根 open 已破用 open，否则用 close，同样不用 low（`csv_minute_backtest_v7.py:403`）。
- 影线击穿、收盘收回：日线会卖，分钟不卖。8.1/8.2/8.3 的日线账和分钟账不能当成同一成交模型。

### X-10 买入一律 100 股；科创板起点和零股卖出都没按交易所申报

- 来源：Grok `F-03` major；Codex `M07` major；Kimi `F-E5` minor，另有 `F-E7` inferred（零股可多次卖）。
- 状态：**confirmed**。严重度从 Kimi 的 minor **上调到 major**（688/689 在市场层是可交易的 20% 板块，`market_layer.py:17-18`，账本仍给 100 股首仓）。
- 代码：`_buy_size` 不足 100 也补到 100（`csv_ledger.py:223-233`）。`shares_override` 再 `//100*100`（`:259`）。容量裁剪买侧再整百（`ashare_volume_cap.py:83-84`）。卖出股数没有整百约束。策略 12 HELP 写明容量或锁定送股可以让实际卖出不整百（`strategy12_rules.py:198-199`），这是已裁的研究语义；交易所侧主板零股应一次卖完，代码没有这条约束。Kimi `F-E7` 的机制成立，并入本条，不另算一条缺陷。
- version11 全市场导出排 688，不代表引擎或其他池子排。默认 `stock_pool/` 的 8.x 和策略 12 可以含科创板。池子里实际有多少 688，**needs-data**。

### X-11 v7 的 DataFrame 日历丢掉名单以外的交易日

- 来源：只有 Codex `M10` major。
- 状态：**confirmed**（读路径，未再跑 Codex 的 89 元夹具）。严重度维持 **major**，范围限定在公开 `simulate_v7` 且调用方没传 `index_days`。标准 CLI 在有池时传入 `load_index_daily` 的指数日历（`csv_minute_backtest_v7.py:660-667`），不能把这条说成所有命令行必错。
- 代码：frame 输入把 `minutes` 设成 `{}`（`:333-334`）。未给 `index_days` 时日历是 `set(minutes)|set(pools)`（`:349-350`），frame 自己的交易日不进日历。没有名单的次日不会跑止损、计时退出和估值。

### X-12 分钟缓存命中不验证湖来源或版本

- 来源：Codex `M08` major。Kimi §1.7 只说缓存没有新鲜度守卫、文档已写。Grok 把它放在性能建议里。
- 状态：机制 **confirmed**。当前磁盘上的缓存是不是旧湖，**needs-data**。严重度维持 **major**（换湖或修数后仍可能命中旧行情）。
- 代码：路径是 `minute_none_{start}_{end}.parquet`（`ashare_bars.py:416-418`）。命中后按代码读取，不看 `lake_root`、mtime、schema（`:584-590`）。旁边的 JSON 只记起止、行数、创建时间（`:491-499`），读取不校验。`include_volume=True` 的 version11 绕过缓存（`:578-582`），front 分钟也不走这套缓存（`csv_minute_backtest.py:1129-1139`）。这两处绕过应保留。

### X-13 公司行动权益默认没有；打开后缺 bar 可能永久漏记

- 来源：Codex `M09` major，并写明这不是违反 δ6。Grok / Kimi 只把「默认关」写成已声明的研究残留。
- 状态：**confirmed**。默认关闭 **不是缺陷**，是 δ6。严重度只留给「API 已传入事件、当天却没有分钟 bar」：主书在 `apply_exdiv_economics` 之前就 `continue`（`csv_minute_backtest.py:734-742`），v7 无 records 时同样先跳过（`csv_minute_backtest_v7.py:373-381`）。策略 12 在看行情之前就 `_prepare_day`（`strategy12_engine.py:217-218`），不能套用同一句「缺 bar 必漏」。标准 CLI 不传 economics lookup，这句对默认命令不触发。
- 影响：默认跨除权的 raw 市值会在送转日掉下去，红利不进现金。这是人裁要留下的缺口。打开开关也不是「只要传了事件就一定入账」。

### X-14 分钟止损看收盘，不看最低价

- 来源：Grok `F-05` major；Kimi `F-E2` major。Codex 写在 §1.2，没有编成 M 项，因为合同已声明。
- 状态：**confirmed**。严重度保持 **major 的模型偏差**，从「实现错误」降下来：模块文档写「盘中触线按该分钟 close 走」（`csv_minute_backtest.py:165`）。影线不触发，触发后价格是 close，可以比止损线更差。v7 同样不用 low。
- 建议保留宿主默认。要「低点触发、下一根开盘成交」走研究格，不要改 8.x 冻结包所挂的这层。

### X-15 version11 Slice D 仍是 STOPPED

- 来源：Kimi `F-V11-6`；Grok §2.2；Codex §2.1。三份一致。
- 状态：**confirmed**（文档，不是新代码洞）。`docs/backtest/reviews/slice-d-version11-seed30-universe-2026-09-21.md:6` 写明 STOPPED，不主张收益 / parity。这是 PR 人裁的显式跳过，不是实现者私自漏做。业务上「ma_chip 是否有效」仍然没有对照。建议保留这个标签。

### X-16 同 bar 收盘成交，以及 bar 起点标签没有运行时断言

- 来源：Kimi `F-E1` major。Grok §1.2、Codex §1.2 都描述了，并把它当成已声明的研究口径。
- 状态：行为 **confirmed**；把它标成缺陷 **disputed**。严重度改为 **minor / 已声明口径**。
- 代码：池买是 14:55 close，缺根则用 14:30–14:55 最后一根 close（`csv_minute_backtest.py:127,565-572`）。卖出扫描在同一根上用 close 判定并用 close 成交（`:334-336,374-377`）。策略 12 分钟同样是当根 close（`strategy12_engine.py:254-267`）。策略 11 是例外：09:30 open。
- 标签：帮助文本写湖内时间是「中国交易时钟标成 UTC」（`csv_minute_backtest.py:7`）。`hm` 取 UTC 钟面的时分（`ashare_bars.py:362-363`）。会话含 09:30 和 15:00（`ashare_bars.py:27-28`）。代码不断言一天是 240 还是 241，也不断言标签是区间起点还是终点。当前湖到底是哪种标签，**needs-data**（本轮未读 parquet）。文档探针说是起点标签、241 根；若这个探针仍真，14:55 这根的 close 在下一分钟才完全可知，成交却记在这根上。这是有意的 cheat-on-close，minute-sensitivity 和 `#156` H2 已经把它留在研究对照里。

### X-17 默认费用不是 2023-08-28 之后的股票账单

- 来源：Grok `F-04` major；Kimi `F-E4` minor。Codex 放在 δ1，明确不把它当成实施违约。
- 状态：事实 **confirmed**；严重度改为 **minor**（人裁冻结的代理费率）。
- 代码：`BILATERAL_10BP` 双边 0.1%、最低 0（`ashare_fees.py:17-21,53-55`）。`--qlib-cost` 买 5bp / 卖 15bp / 最低 5 元（`csv_minute_backtest.py:1303-1307,1346-1348`）。没有印花、没有过户、没有 2023-08-28 的切换。热路径不 import `trade_fee_policy`。旧占位 `backtest/legacy/engine.py:29-31` 写了佣金 0.5bp、印花 5bp、最低 5 元，CSV 引擎不用它。
- 文档漂移是真的：`docs/backtest/engine-ashare-correctness.md:34` 仍写分钟 `simulate` **无**费率 kwargs。现行签名有 `buy_cost_rate` / `sell_cost_rate` / `min_cost`（`csv_minute_backtest.py:628-630`）并写进 `SimState`（`:684-689`）。Kimi `F-E8` 的「锚点漂移」至少这一处成立。
- 建议：默认 10bp 保留。要像账单，另做显式档，不要叠在 10bp 上。

### X-18 14:57–15:00 仍按连续竞价的 open/close 成交

- 来源：Kimi `F-E3` minor。Grok D-01、Codex §4.1 写成 P1=A，不编成缺陷。
- 状态：行为 **confirmed**；作为缺陷 **disputed**。`ashare_fill_clock.py:12-27` 把 `hm>=14:57` 标成 `closing_call`，标签不参与过滤。扫描仍可在这些 bar 上成交。人裁是保留这个行为。建议保留。湖里有没有 15:00 这一根，**needs-data**。

### X-19 `--participation-rate` 打开后，version11 的 09:30 单结构性不成交

- 来源：Kimi `F-V11-1` major。Grok D-29、Codex δ5.2 写成 volume=A 的直接后果，建议保留谓词、不要为了「有成交」去改它。
- 状态：行为 **confirmed**；作为实现错误 **disputed**。严重度改为 **minor（组合脚枪）**。
- 代码：买侧 `volume_at=AM_OPEN-1`（570−1=569）（`csv_minute_backtest.py:947`），卖侧 `at=AM_OPEN-1`（`:792`）。`VolumeCap.clamp` 要求 `bucket <= at`（`ashare_volume_cap.py:55-59`）。开盘桶 570 配 at 569，恒为 `skip_volume_unavailable:bucket_not_completed`。默认 `participation_rate=None`，不创建 `VolumeCap`，这条不触发。HELP 已写 volume=A（`strategy11_rules.py:28`）。
- 建议保留 `bucket<=at`。若要防静默空跑，在 CLI 对 version11 加容量时拒绝或打印一句，这是提示，不是改撮合。

### X-20 version11 执行预热只有 10 个自然日，SMA 不够就静默 HOLD

- 来源：Codex `M11` minor；Kimi `F-V11-3` minor，并写「生产预热 200+ 不受影响」。
- 状态：10 自然日 **confirmed**。Kimi 那句「200+ 所以执行侧不受影响」**disputed**，放进附录。
- 代码：`WARMUP_DAYS=10`（`csv_common.py:18`）。version11 不在 version4/12 的 22 日分支里（`csv_minute_backtest.py:1090-1093`）。`warmup_start` 减的是自然日（`csv_daily_loader.py:37-38`）。`eod_exit` 在 SMA5 为 None 时不写卖出（`strategy11_rules.py:92-95,102-106`）。导出器的 200 日筹码窗是另一条管道，不能给执行引擎的 SMA5 补历史。
- 影响集中在窗口起点和长期停牌、加载后仍不足 4 根昨收的票。中段正常持仓不受影响。严重度维持 **minor**。

### X-21 策略 12 每个分钟重建一次完整扫描；Numba 卖出核进不去

- 来源：Grok `F-06` major、`F-07` major；Kimi `F-S12-7` minor、H1；Codex `M12` minor。
- 状态：机制 **confirmed**。严重度改为 **minor（性能）**。Grok 标 major 过重：它不改变成交对错。测量见第 5 节。
- 代码：`run_minute_day` 对每个 `hm`、每只持仓调用一次 `scan_held_day`，并每次新建长度为 1 的数组（`strategy12_engine.py:243-263`）。MA 来自昨收，全天阈值不变，`sma_asof` 仍在 `exit_plan` 里每根重算（`strategy12_rules.py:70-81`）。昨收用 `daily.loc[daily.index < day]`（`strategy12_engine.py:228`），共享日路径已有 `searchsorted`（`csv_common.py:22-45`）。
- Numba：`can_offload` 要求 `reserve_state is None` 且没有 `take_profit` / `exit_plan`（`csv_minute_backtest.py:447-457`）。共享循环对每笔 lot 传入 `reserve_state`（`:799-828`），8.x 还有 `take_profit`。本轮把 `CSV_SCAN_HELD_DAY_BACKEND=numba` 打开后，基准脚本仍打印 `scan backend: python (simulate passes reserve_state; version8 supplies take_profit callable)`。Numba 库在，门没开。

### X-22 入口文档把 8.1 写成每票 100 万

- 来源：Grok `F-08` minor；Codex §2.1；Kimi `F-8-2` 后半。
- 状态：**confirmed**。严重度 **minor**。
- 代码：`version8_1` 注册没有写 `sizing`，数据类默认 `daily_quota`（`csv_strategy_books.py:72,1339-1348`）。8.1 HELP 自己写明日额度（`strategy8_1_rules.py:104`）。8.2/8.3/8/12 是 `per_name`。`docs/backtest/research-backtest-entry.md:85` 把 version8 / 8.1 / 8.2 / 8.3 写成同一句「per_name 100 万」。
- 建议改文档那一格。不要为了文档去改 8.1 的资金口径。

### X-23 8.3「再加 50 万」没有笔数上限

- 来源：Grok `F-09` minor。
- 状态：代码事实 **confirmed**；「HELP 承诺最多两笔」**disputed**。严重度维持 **minor**，未确认前不要改。
- 代码：`lot_budget` 在已有持仓时仍返回预算的 50%（`strategy8_3_rules.py:45-50`）。`may_add` 只看价格和 +3% 峰值，不数 lot（`:53-62`）。第三笔仍可以再放约 50 万。
- HELP 写的是「首笔 50 万试探，同码可再加 50 万」（`:95-96`），没有写「最多两笔」。这句可以读成「每一笔加仓 50 万」。Codex 把「追买也必须是 50%」写成合同（那是 X-04），没有把笔数上限写成已冻结的两笔。建议先补一句 HELP，再决定要不要在 `may_add` 里数 lot。

### X-24 v7 与书引擎的宿主分叉

- 来源：Grok `F-10` minor（峰值 + 名称）。Codex 把名称放在 δ3，把跨股票现金放在 `M02`。
- 状态：名称分叉 **confirmed**。峰值「会更早武装止损或加仓」**disputed**，附录删掉影响句。
- 名称：v7 默认窗口末名（`csv_minute_backtest_v7.py:384-387,650-651`）。书引擎按日 as-of。δ3 当时选择不改生产，后来才加可选 `--asof-pool-names`，默认关。建议做 ST 实验时打开它；默认先留着，否则旧 v7 数字对不上。
- 峰值：v7 在持仓存在的每一根 bar 上写 `position.peak`，含买入日（`:399-400`）。书引擎 T+0 不更新峰值（`csv_minute_backtest.py:318-320`）。本文件里 `position.peak` 只在除权时被缩放（`:198`），止损和加仓读的是 `stage` 与 `avg_cost`（`:401-402`）。字段会分叉，决策不会因此更早触发。

### X-25 `daily_quota_used` 在 per_name 下靠调用点恢复

- 来源：Kimi `F-E6` minor。
- 状态：**confirmed**。严重度 **minor**。当前 per_name 的池买、追买、台阶、买回都会在 `execute_buy` 之后把计数写回去（`csv_simulate_loop.py:224-226,351-354,427-444,498-516`）。`execute_buy` 仍无条件累加（`csv_ledger.py:281`）。现有调用没有算错账；新调用若忘记恢复，日额度会被偷走。

### X-26 几处缺 bar 静默 `continue`

- 来源：Kimi `F-S12-2`、`F-V11-2`。
- 状态：**confirmed**。严重度 **minor**。
- 策略 12 分钟：日线或分钟缺失、或当天不在日线索引里，直接 `continue`，没有 `skip_no_bar`（`strategy12_engine.py:226-231`）。`prev` 为空或 `slice_day` 为空同样跳过（`:230`）。
- version11 待卖：没有 `hm==570` 就 `continue`，无计数（`csv_minute_backtest.py:777-779`）。买侧同一情形计 `skip_no_bar`（`csv_simulate_loop.py:293-294`）。零量开盘卖出有 `defer_sell_volume`（`:784-786`）。卖侧缺 bar 和买侧不对称。

### X-27 `scale_memory` 把记忆打成 0 时不放开周期锁

- 来源：Kimi `F-S12-3`；Grok §2.1 也写了。
- 状态：**confirmed**。严重度 **minor**。只在显式 `exdiv_economics` 打开、送转把记忆缩到不足 100 股时走到（`strategy12_rules.py:157-161` 只改 `shares`）。`latched` 仍可为真，MA5 减仓会被挡住，直到一次合格 reclaim。默认 CLI 走不到。

### X-28 策略 12 `_normal_buys` 写死 `allow_add=True` / `buy_gate=None`

- 来源：Kimi `F-S12-4`。
- 状态：**confirmed**。严重度 **minor**。`strategy12_engine.py:141-147` 不读 hooks。当前书的 `allow_add` 就是 True，也没有 `buy_gate`，今天的回测不变。以后若在 `apply()` 里改这两个字段，分钟和日线买侧都不会跟着变。

### X-29 分钟跌停延期按 bar 计数

- 来源：Kimi `F-S12-5`，写「跌停日大约放大 240 倍」。
- 状态：机制 **confirmed**；「约 240 倍」**disputed**。
- `fill_exit` 每次被调用且开盘或成交价跌停，就 `defer_sell_limit_down += 1`（`strategy12_engine.py:101-103`）。`run_minute_day` 对每根触发了卖出计划的 bar 调用它。所以「计划成立、成交价再被跌停拦住」会按 bar 累加，日线路径按笔累加，两边的 stats 不能横比。
- 开盘本身已经跌停时，扫描器在返回之前 `continue`（`csv_minute_backtest.py:330-331`），`fill_exit` 不会被调用，计数可以是 0。X-01 里日线收盘 12、分钟价 10 的夹具就是 `defer=0` 且全天卖不出。不能把 240 当成跌停日的固定倍数。

### X-30 version11 日线「契约收盘买」没有自己的报价函数

- 来源：Kimi `F-V11-4` minor。
- 状态：**confirmed**。日线 `_pool_quote_for` 返回 `row["close"]`（`csv_daily_backtest.py:486-493`），version11 没有另写买钟。这与人裁「日线契约收盘」一致，今天不是错账。风险是以后改日线默认买钟会连带改 version11。建议加一条 price_rule 断言，严重度维持 minor。

### X-31 流通股本 asof 按 `stock_code` 精确相等

- 来源：Kimi `F-V11-5` minor。
- 状态：代码 **confirmed**；真实股本表的代码形态是否不一致 **needs-data**。
- `history["stock_code"] == stock_code`（`oskh_factors/bridge/turnover_resist.py:97`），没有归一。对不上时返回全 NaN，导出表现为 `skip_cyqk_nan`，不报格式错误。

### X-32 8.1 / 8.2 不设置 `reserve_limit_up`，落到引擎默认 False

- 来源：Kimi `F-8-2` minor。
- 状态：**confirmed**。`_apply_version8_1` / `_apply_version8_2` 只返回止损、止盈、参数记录（`csv_strategy_books.py:729-733,758-762`）。`setdefault("reserve_limit_up", False)` 在 `:138`。version8 显式用 `RESERVE_LIMIT_UP=True`（`strategy8_rules.py:36`，接线 `:701`）。8.1/8.2 因此没有涨停保留。模块文档说卖点冻结、引擎行为跟宿主，这个默认是宿主默认，不是 base 8 的涨停语义。HELP 没写。对比时要单列。严重度 minor。

### X-33 8.1/8.2/8.3 没有 plan / handoff / PR 人裁链

- 来源：Kimi `F-8-3` minor；Codex §4.6 标成 code default，不冒充逐条人裁。
- 状态：**confirmed**（提交信息与注册存在；批准通道本轮没有在评论区里找到）。`b2b406e` 本地分支直合。冻结语义在 `tests/test_strategy8_milestones.py` 和各书 HELP。建议补一页 retro，不要把缺文档说成卖点公式错了。

### X-34 8.3 自己的 `build_sse_ma10_block_new` 没有调用者

- 来源：Kimi `F-8-4` minor。
- 状态：**confirmed**。全库没有 `strategy8_3_rules.build_sse_ma10_block_new` 的引用。CLI 对 version8 和 version8_3 装载的是 `strategy8_rules.load_sse_ma10_block_new`（`csv_minute_backtest.py:1213-1221`），8.3 无条件打开。卖点闸门仍在，死的是 8.3 模块里的那份包装。严重度 minor，不是闸门失效。

### X-35 策略 12 分钟卖出不写 `session_phase`

- 来源：Grok §2.1；Codex 性能节。两人都没单独编号。
- 状态：**confirmed**。严重度 **minor**。`fill_exit` 调用 `_sell` 时不传 `hm`（`strategy12_engine.py:111-112`）。`_sell` 只在 `hm is not None` 时填 `session_phase`（`csv_ledger.py:392-396`）。钱不变，审计列是空字符串。优化回放若只看 reason 和日收益，对不上分钟时刻。

### X-36 qlib 1 分钟缺 open/high 时用 close 顶上

- 来源：Codex §1.2，没有编号。
- 状态：**confirmed**。`qlib_bin_1min.py:55-57`：open 或 high 读空则用 close。没有 low 列。这只影响 `minute_source=qlib_1min`。version11 拒绝这条源。不要把这种帧说成完整 OHLC。严重度 minor。

### X-37 8.1 HELP「2%×2」和代码 6%

- 来源：Kimi `F-8-1` 前半；Codex §4.6 说保留 6% 并澄清措辞。
- 状态：**confirmed** 的是措辞，不是算错。`SMALL_ARM=0.06`，注释写「用户口径 2% 的两倍按 6%」（`strategy8_1_rules.py:26`）。HELP 仍写「须先摸到 2%×2」（`:101`）。建议改 HELP 成「先到 +6%，再回撤到 +2%」。不要改成 4%。
- Kimi 同一条的后半（8.3 的 +50%/+100% 等号）是误读，见附录。

## 3. 被标成缺陷、实际是人裁的口径

这些行为都在代码里，三份报告也都写了。它们不进第 1 节的修复榜。

| 行为 | 人裁 | 代码 | 建议 |
|---|---|---|---|
| 14:57 后仍可按 bar 成交 | P1=A | `ashare_fill_clock.py:21-26` | 保留 |
| 当根 close 成交 | 策略 12 分钟人裁；8.x 宿主合同 | `csv_minute_backtest.py:334-336` | 保留生产；对照用 `#156` |
| 止损不看 low | HELP 已写 | `:328-336` | 保留 |
| 双边 10bp、无印花、无最低 5 元 | δ1=A/A/A | `ashare_fees.py:53-55` | 保留默认；账单另做开关 |
| version11 开盘量必须是已完成桶 | volume=A | `csv_minute_backtest.py:792,947` | 保留谓词；组合提示即可 |
| 除权权益默认关 | δ6 | `simulate(..., exdiv_economics=None)` | 保留；X-01 修好之前不要为了策略 12 默认打开 |
| version11 Slice D 不跑 | PR #152 07:28:14Z | 文档 STOPPED | 保留未验证标签 |

## 4. 决策点总表

下表把三份第 4 节合并。同一选择只留一行。「当时选的」与代码不一致时，写在「代码核对」列。过程性禁令（不许自动 merge、Ruff 版本）不改变数学，收成最后一行。

| ID | 问题的意思 | 当时选的 | 影响 | 是否合理 | 建议 | 来源与代码核对 |
|---|---|---|---|---|---|---|
| D01 | 14:57 之后还按普通分钟成交吗 | 不建集合竞价，只加名字 | 尾盘 trail / 止损 / 策略 12 仍可能在 14:57–15:00 成交 | 研究相对比较可接受，不是交易所规则 | 保留 | fill-clock P1=A；`ashare_fill_clock.py:12-27`。代码仍只贴标签 |
| D02 | 成交表要不要写时段和取价规则 | 书引擎加 `session_phase`、`price_rule`；v7 不加 | 钱不变。没标的是空字符串 | 合理 | 保留。策略 12 分钟卖出目前就是空的，见 X-35 | P2 由 A 改 B；`csv_ledger.py:392-409` |
| D03 | 以后若禁止 15:00 成交，净值还用不用当天收盘 | 两件事分开，都维持现状 | 市值用日线 close，可以不等于最后一笔分钟价 | 合理 | 保留分离。策略 12 要改的是价格域，不是改用最后一笔成交 | P4=A；`csv_simulate_loop.py:547-571` |
| D04 | 同根收盘会不会把收益看高，要不要立刻改生产时钟 | 先只读实验（GO B），随后默认不动（GO A），允许研究钩子但默认仍冻结（option 2） | 8.x / 11 / 12 的默认 NAV 不因实验改变 | 合理 | 保留。引用 bp 时写明样本 | `docs/backtest/reviews/plan-minute-sensitivity-b-2026-09-20.md` 与 defaults 卡；`fullstrat_research_hooks.py` 默认委托原引擎 |
| D05 | 研究默认用双边 10bp，还是 qlib 5/15+最低 5，以及能不能调用实盘费率 | 默认 10bp、无最低；`--qlib-cost` 才换；禁止再加一行印花；不 import `trade_fee_policy` | 往返 20bp，不是 2023-08-28 后的账单 | 人裁禁止双计是对的 | 保留默认；账单另做显式档 | δ1 A/A/A；`ashare_fees.py:53-55`；`csv_minute_backtest.py:1346-1348`。文档第 34 行已过时，见 X-17 |
| D06 | 除权日成本 / 峰值跟不跟价格跳，股数和现金动不动 | 只缩放 cost/peak 和昨收；不增股、不发现金；小跳变有噪声带；前复权日线跳过 | 止损线能跟上大除权；财富账不完整 | 合理，它修的是假止损 | 保留 | δ2；`csv_ledger.py:154-163`。version12 混域时这条 map 被关掉，见 X-01 |
| D07 | ST 改名后，前几天用当天的名字还是窗口最后的名字 | 当时不改代码。书引擎按日；v7 用窗口末名。后来 v7 加了可选 as-of，默认关 | 关掉时，后半段变成 ST 会让前半段也按 ST 档交易 | 默认冻结旧数字可理解 | 书引擎按日名称保留。v7 做 ST 实验打开 `--asof-pool-names`。档位本身见 X-07，as-of 修不了 5% | δ3；`csv_minute_backtest_v7.py:609-611,650-667` |
| D08 | 算不出涨跌停时，v7 已有仓位还能不能卖、加、到期卖 | 不能。记 skip，峰值和净值仍可更新 | 未知板块不会被当成没有涨跌停 | 合理 | 保留。`limits is None` 不能当成 IPO 合法无限制 | δ4=C/B/A；`csv_minute_backtest_v7.py:405-407` |
| D09 | 一分钟的成交量能不能限制本策略股数 | 默认关。打开后用已完成桶；开盘价不能用当根完成量；买侧再整百；没有 CLI | 默认与加这刀之前相同。version11 一打开，09:30 不成交 | 谓词合理 | 保留关闭。不要改 `bucket<=at`。见 X-19 | δ5=C/A/A/A；`ashare_volume_cap.py:52-59`；`csv_minute_backtest.py:693-694` |
| D10 | 送股和现金红利进不进账 | 默认关。打开后送股向下取整，现金先应收、派息日入现金；公司行动不收佣金、不占量 | 默认高送转净值偏悲观 | 合理 | 保留关闭。缺 bar 漏记见 X-13。策略 12 在 X-01 修好前不要默认打开 | δ6；`ashare_exdiv_economics.py` 由调用方事件驱动 |
| D11 | 板块和 ST 档怎么定 | 前缀 10/20/30，ST 优先 5%，未知且非 ST 则不交易；价格 Decimal 四舍五入到分 | 未知代码不会被猜成 10% | 未知拒绝合理；ST 5% 已过时 | 未知拒绝和 HALF_UP 保留。ST 见 X-07 | E-R2/E-R3；`market_layer.py:43-84`。1.65×10% 的 HALF_UP 合同仍在 |
| D12 | 停牌和追买挂单 | 整日成交量为 0 的分钟日被丢掉；净值用最近 close；追买一直挂到有 K 再判一次 | 不虚构当日成交 | 日级近似可接受 | 保留。日内临停没有单独资格 | E-R4；`ashare_bars.py:381-385`；`csv_ledger.py:201-214` |
| D13 | 所有卖出原因都躲跌停，还是只躲止损 | 所有卖因都躲 | MA、止盈、强平也会延后 | 合理 | 保留。这不是排队 | E-R1；`strategy12_engine.py:101-103`；`csv_minute_backtest.py:835-841` |
| D14 | 新书叫 11 还是 12 | version12；11 留给 ma_chip | 两个注册不互相覆盖 | 合理 | 保留 | 策略 12 P1；`csv_strategy_books.py:1446-1468` |
| D15 | 分钟跌破均线是每分钟都能卖，还是一天一次 | 昨收 MA；逐分钟 close 判定、当根 close 成交。日线收盘信号、次日开盘卖 | 分钟比「下一根开盘」乐观，也比日线更早 | 昨收符合时点；当根 close 是已批准的理想成交 | 保留，对外写明是当根收盘 | P2；`strategy12_rules.py:70-81,184-185`；`strategy12_engine.py:169-192,254-267` |
| D16 | 减多少、先卖哪一笔 | 可卖股数的 50%，向下到 100；不足 100 不减。台阶先卖，lot0 最后且减仓至少留 100 | 100–199 股可卖时一次不减 | 符合「减仓不清仓」 | 保留 | P3/P13；`strategy12_rules.py:90-136`。止损不留这 100，见 X-06 |
| D17 | 同一天跌破、站回、再跌破，还能再减吗 | latch=A：收复即再武装，没有每日锁 | 同一天可以多次减和买回 | 这是覆盖计划「每日一次」的有效裁定 | 保留 | PR #151 latch=A；`strategy12_rules.py:41-47` |
| D18 | 卖 150 买回 100 之后剩下的 50 股 | residual=2：两个通道都留下，并入下一轮；不足 100 且这次没买成也再武装 | 尘埃股不丢 | 覆盖「买回后清零」 | 保留 | PR #151 residual=2；`csv_simulate_loop.py:476-478`；`strategy12_rules.py:41-47` |
| D19 | 止损和减仓同一天都成立 | 先 MA10×0.90 止损，清可卖股；两套记忆都留 | 深跌时不是只减半 | 合理 | 保留。锚问题见 X-06 | P5；`strategy12_rules.py:128-130` |
| D20 | 一天里池、追买、台阶、买回能不能叠很多笔 | 不加笔数闸 | 单票日内名义可以远超 100 万 | 人裁明确 | 保留，HELP 已写 | P6；`strategy12_rules.py:196-197` |
| D21 | 要不要上证十日线停买 | 策略 12 不要 | 指数弱时策略 12 仍开新仓，8.3 会停 | 两书对比必须写明 | 保留 | P7；`csv_strategy_books.py:658` `index_blocks_add=False` |
| D22 | 名单从哪读 | 策略 12 和 8.x 默认 `stock_pool/`。9/10/11 拒绝这个默认 | 池文件一改，历史回测就变 | 入口选择合理 | 保留。复现时把池子版本写进 manifest | P8；`csv_strategy_books.py:55` |
| D23 | 池买或追买成功后，还买不买回已减的仓 | 成功新买清零两个通道的记忆；台阶计数不减 | 名单再现就不再负责买回那一段 | 防双倍仓位 | 保留 | P9④；`strategy12_rules.py:56-59`；`strategy12_engine.py:36-43` |
| D24 | 送转时买回记忆乘不乘股数 | 只在显式权益打开时按 `1+送股比例` 缩放，再取整到 100；现金红利不缩放 | 默认记忆不随除权变。打开后不足 100 的缩放零头丢掉，和 residual=2 不是同一条 | 已裁的取整 | 保留区分。缩成 0 仍 latched，见 X-27 | P9③；`strategy12_rules.py:145-161` |
| D25 | MA 用复权价还是原始价 | 日线信号固定 front；分钟成交默认 none，front 分钟可选且缺分区失败；禁止静默再乘 k | 状态机按这个裁定接了线。比较和估值的单位没接上 | 目标合理，实现不完整 | **修改比较、涨跌停和估值的实现**；保留「调整只做一次」 | #151 选项 2 / #158；`csv_minute_backtest.py:1108-1186`。见 X-01 |
| D26 | 要不要继承 version8 的 20% 止损、涨停保留、15 分钟峰距 | 都不要。止损只走 MA10×0.90；`peak_gap_min=0` | 策略 12 不会被 version8 的止损先清仓 | 合理 | 保留 | P12；`csv_strategy_books.py:652-657`；`strategy12_rules.py:16-17` |
| D27 | 日线信号之后当天下午新买的仓，次日能不能被这张卖单卖掉 | #169：卖单锁住信号当时可卖的 lot | 新仓留在账上 | 合理，已修 | 保留 | `strategy12_engine.py:88-96,183-192` |
| D28 | 部分卖出会不会把剩余股数删掉 | S1：按实际成交扣股，空 lot 才删 | 所有书的部分卖出受益 | 已修 | 保留 | `csv_ledger.py:428-439` |
| D29 | 次日开盘时 lot0 已经变小，还保不保 100 | #170：减仓 clamp 重新保底；止损不保 | 延迟减仓不会卖光锚。止损仍可以 | 减仓这半合理 | 减仓保留。止损见 X-06 | `strategy12_rules.py:108-122` |
| D30 | 跌停拖过一天、其间价格已经站回均线，次日还卖不卖 | 日线队列在卖出股数大于 0 时才删；零成交换单留作后续 | 次日开盘仍按旧单卖 | 与分钟「下一根重判」不同 | 保留现状并写明；零成交重试不要悄悄改 | `strategy12_engine.py:183-187`。Grok 描述与代码一致，Codex 标成未解决的延期 |
| D31 | cyqk>0.70 算不算已经验证的多头 | 框架移植先行，HELP 写明不是已验证多头 | 跑通不等于能赚钱 | 诚实 | 保留标签 | 策略 11 P0；`strategy11_rules.py:23` |
| D32 | 日线买收盘还是分钟买开盘 | 两个都做。分钟 09:30 open 为准；日线契约收盘 | 两本成交价本来就不同 | 合理 | 保留。日线侧没有专属 pin，见 X-30 | P1；`csv_minute_backtest.py:589-592`；`csv_daily_backtest.py:486-493` |
| D33 | 收盘决定卖，什么时候成交 | 日线 pending，次日开盘；分钟次日 09:30 open；跌停继续持有 | 卖出隔夜 | 合理 | 保留。缺开盘 bar 没有计数，见 X-26 | P2；`csv_minute_backtest.py:773-793` |
| D34 | 信号日和买入日怎么对齐，过期从哪天起 | D 是原信号日；T 是严格晚于 D 的第一根有 bar 的交易日；D→T ≤ 4 个自然日；计算只用 ≤ T−1 | 停牌超过 4 天的信号作废；不会用 D 日收盘去买 D 日开盘 | 严格时点 | 保留 | `export_strategy11_pool.py:99-112` |
| D35 | 周线是整段历史对齐，还是每个 D 都像数据在 D 截断 | 导出器显式 `prefix_equivalent=True`。默认 API 仍是整段向后对齐 | 导出窗口变长不会改写较早的周线信号。忘了传 flag 的其他调用仍会 | 分层正确 | 保留 opt-in。导出器必须继续传 True | `export_strategy11_pool.py:164-166`；`ma_infra.py:125-139` |
| D36 | 09:30 能不能用这一分钟结束后才知道的量 | 不能。`at=569`，`bucket=570` | cap 关时正量开盘可按 open 成交；cap 开时这笔消失 | 因果保守 | 保留。见 X-19 | PR #152 volume=A |
| D37 | 涨停买不进，要不要次日追 | 不要。`limit_up_chase=False` 写在 `apply()` 返回值里 | 信号消耗，不会留下长期挂单 | 与本书一致 | 保留 | `csv_strategy_books.py:993`。`setdefault` 不会把它盖回去 |
| D38 | 当天卖了还能马上买回吗 | 卖出日不重入 | 减少同日往返 | 合理 | 保留 | `csv_minute_backtest.py:948-949`；`csv_strategy_books.py:996` |
| D39 | 全市场排不排 ST 和科创板 | 全市场模式排；seed-30 沿旧档案，不按这套滤 | 两种导出的股票池不同 | 合理 | 跑全市场时显式 `--universe` | 导出器 V9。执行侧池子里若仍有 688，引擎仍按 100 股买，见 X-10 |
| D40 | 筹码和周线失败怎么办 | 坏窗口 NaN 则该日跳过；ValueError 则该码跳过；不切 Python 算法；股本逐日 backward asof，禁止快照 | 覆盖率换可复现 | 合理 | 保留。代码形态匹配见 X-31 | `turnover_resist.py:70-108` |
| D41 | 没有静态档案和真 Rust pyd，验收还阻塞吗 | 显式跳过 Slice D，不主张收益 | 只有框架证据 | 诚实 | 保留未验证标签 | 文档见 X-15 |
| D42 | 共享均线做哪些、用什么语言、放哪 | 八件 SMA/BB/周线；纯 Python；strategy4 只改 import；放 `ma_infra.py`；布林 ddof=1；默认周线不逐日截断 | 11/12 和导出器共用口径 | 合理 | 保留。`sma_live` 等预留无生产消费者，可接受 | #150/#154。`prefix_equivalent` 是 #152 追加的，不是 ma_infra 最初四问 |
| D43 | 8.1/8.2/8.3 是新规则还是旧包复活 | 卖点公式冻结，费用、涨跌停、追买时钟跟现行宿主 | 和当年 CSV 的差异来自宿主 | 对比口径要写「同引擎、异卖点」 | 保留。不要为了「冻结」去关追买，除非另裁 | 各书模块文档前 8 行；注册见 §0 |
| D44 | 8.1 的钱怎么分 | 代码和 HELP：当天 100 万日额度。入口文档写成每票 100 万 | 信号一多，8.1 仓位比 8.2/8.3 小一个数量级 | 代码口径清楚 | 改入口文档。代码维持日额度 | 见 X-22 |
| D45 | 8.1 小利润保护的阈值 | 先到 +6%，再回撤到成本×1.02 | 「2%×2」若读成 4% 会和代码不一致 | 代码注释已说明按 6% | 保留 6%，改 HELP 措辞 | `strategy8_1_rules.py:26,101` |
| D46 | 8.1 大利润分档 | `(15%,40%]/(40%,60%]/(60%,80%]/(80%,100%]/(100%,120%]` 用 15/30/50/70/90 地板；超过 120% 从最高价回撤 20% | 精确边界会被 float 送进下一档 | 数学区间本身可保留 | 保留区间，修比较方法，见 X-05 | `strategy8_1_rules.py:32-48` |
| D47 | 8.2 的分档等号 | `(0,6%)/[6%,15%)/[15%,50%]/(50%,100%]`，精确 50% 和 100% 留在较低档 | 与 8.3 的开闭不同 | 两书各自的冻结 | 保留，不要用 8.3 覆盖 | `strategy8_2_rules.py:38-55`。`p <= cost*1.50` 在 `:51` |
| D48 | 8.3 的分档等号 | `[6%,15%)/[15%,50%)/[50%,100%)/[100%,∞)` | 精确 +50% 进入 70% 保留，精确 +100% 进入 80% 保留 | HELP 与代码一致 | 保留 | `livermore_exit_rules.py:28-36`；`strategy8_3_rules.py:89-92`。Kimi 写成 `<=1.50` 是误读 |
| D49 | 8.3 首笔和加仓 | 首笔预算的 50%；之后每笔加仓仍是预算的 50%；要现价不低于各笔成本，且至少一笔峰值到过 +3% | 笔数不封顶时单票可以超过 100 万。涨停追买目前用的不是这 50% | 试探比例应覆盖所有首买路径 | 追买路径必须改到 50% 并消除前序依赖（X-04）。笔数上限另裁（X-23） | `strategy8_3_rules.py:45-62`；`csv_simulate_loop.py:315-331` |
| D50 | 8.3 上证闸 | 连续两日收在 MA10 下，第三日起新开和加仓都停；只用昨收。CLI 对 8.3 无条件装载 | 库调用若不传表，就没有这道门 | 昨收时点合理 | 保留闸。记录这次运行有没有装上表 | `csv_minute_backtest.py:1213-1221`；`strategy8_3_rules.py:72-77` 缺日默认不拦 |
| D51 | 8.1 和 8.2 的 T+1 止盈 | 8.1 规则不另禁，宿主 T+1 可卖门挡住实际成交。8.2 `n_days<2` 只止损、不止盈 | 两书兑现利润的最早日期不同 | 冻结史实 | 保留 | `strategy8_1_rules.py:84`；`strategy8_2_rules.py:83-84` |
| D52 | #156 研究格换不换全部成交 | H2：Book、v7、Mode B 全部改成下一根连续竞价开盘；严格当天到期；允许不成交和全现金；禁止退回 14:55 | 这是另一套交易集合。14:55 的入场经常当天没有合格开盘 | 实验合同，不是生产默认 | 留在研究格 | `fullstrat_research_hooks.py`；设计文档 H2 节。默认 `clock_mode=production_default` |
| D53 | 当天没卖掉，明天还排不排这张单 | 忘掉卖出意图，下一交易日按策略重判 | 条件次日消失就继续持有 | 只属于研究钩子 | 不要用这句去改策略 11 / 策略 12 日线 / 8.x 日线自己的 `pending_exit` | 设计文档卖单过期节 |
| D54 | 下一根更贵时，股数按信号价锁死还是按成交价重算 | Q2：按成交价重新整手。Q1 固定股数整笔拒绝作废 | 同样现金下更易成交、单笔更小 | 与实盘按成交价算可买股数一致，也与 `execute_buy` 一致 | 保留 Q2 | 设计文档 Q2；`fullstrat_research_book.py` |
| D55 | 研究格还改不改滑点、容量、费用、估值 | 时钟和滑点互斥；滑点只 0/5/10/20bp；容量另轴，传入即拒绝；费用仍 10bp；持仓估值不加滑点 | 好归因，没测交互项 | 本轮实验设计合理 | 保留隔离 | `fullstrat_research_hooks.py:21` 一带。Codex 列的实验合同与「默认委托原引擎」一致；本轮未逐行重放 H2 夹具 |
| D56 | 主分钟 CLI 的资金和窗口 | `--strategy` 必填。现金默认 21,000,000。日额度 1,000,000。每票预算 1,000,000。`--end` 默认 `20260909` | 决定仓位率和现金拒单的时点 | 显式参数合理 | 保留，并随结果记录 | `csv_ledger.py` 默认现金；`csv_common.py:17`；`ashare_bars.py:26`；`csv_strategy_books.py:378-383` |
| D57 | `--dividend-type` | 默认 none。分钟 front 只有 version12 可选。version12 日线信号始终 front。version11 分钟必须带量的 lake | 见 X-01 / X-03 | 分域目标对，version12 接线不完整 | 保留「none 成交、front 信号」；修改换算 | `csv_minute_backtest.py:1048-1055,1108,1294` |
| D58 | `--stop-pct` / `--stop-fill` | 8.x 可在 (0,1) 覆盖冻结止损。11 和 12 拒绝 `--stop-pct`。分钟拒绝 `--stop-fill close` | 不能用通用止损替换 MA 书；不能把 bar close 当成日收盘 | 合理 | 保留拒绝 | `csv_strategy_books.py:669-671,1000-1002`；`csv_minute_backtest.py:1043-1046` |
| D59 | 配给、缓存、清单 | `--ration` 默认 `file_order`，`seeded_shuffle` 用 seed 0。缓存默认开。`--strict-pool` / `--require-signal-bundle` / `--emit-run-manifest` 默认关 | 钱不够时 CSV 顺序决定谁先买到。默认产物不能单独证明名单被冻住 | 旧 CLI 兼容可保留 | 正式研究打开清单和 strict，并记录缓存身份。缓存身份见 X-12 | `csv_minute_backtest.py:1288-1323` |
| D60 | 买钟常量 | 池买 14:55（`BUY_HM=895`），追买 09:45，15:00 是 `CLOSE_CLEAR_HM` | 尾盘买、次日早盘追 | 与 8.x HELP 一致 | 保留 | `csv_minute_backtest.py:127-128`。`CHASE_HM` 由模块引入，`_chase_quotes` 在 `:575-586` |
| D61 | 策略 12 的价格域字段 | `record_strategy12_params` 先写 `price_domain=front`；分钟 `run()` 结束时改成成交域，并另存 `daily_signal_domain` / `minute_fill_domain` | 只调用 `simulate()`、不走 `run()` 时，stats 里的 `price_domain` 仍是 front | 两个字段职责容易混 | 固定字段含义，避免一个键先后表示两件事 | `strategy12_rules.py:207-212`；`csv_minute_backtest.py:1265-1268`。Codex §4.3 这句与代码一致 |
| D62 | 实施时代的合并禁令、编码、测试基线 | 多次禁止代理自动 merge；UTF-8；当时的测试计数不能当成现在的总数 | 不改变公式 | 历史流程 | 不把旧禁令当成新的数值授权。`#169`/`#170` 是实现修复，报告里没有新的用户问答 | Codex §4.2 / §4.7。本轮未重读评论原文，只核对了这两处修复仍在 `strategy12_engine.py:88-96` 和 `strategy12_rules.py:108-122` |

## 5. 性能：排序、测量、能不能复现

热路径是 Python 逐 bar，不是向量化撮合。三份报告和本轮用的都是 `scripts/research/bench_minute_simulate_hotpath.py`（version8，无湖）。该脚本的卖出占比是「包装后的 `scan_held_day`」，编排余量是总时间减去卖扫、追买、池买、估值。`day_slice` 和 `prev_close_prep` 已经含在上面几项里，不能再加一次。

| 谁测的 | 夹具 | 每次 `simulate` | 卖扫 | 编排 | 昨收准备 | Numba |
|---|---|---:|---:|---:|---:|---|
| 2026-09-15 文档 | 同脚本，旧代码，4090 | 1218 ms | 75.51% | 18.61% | 约 5% 量级 | 文档称打开环境变量也没加速 |
| Kimi | 默认 30 日 × 16 码 × 240 分钟 × 10 个池日 | 1257.19 ms | 52.63% | 40.29% | 8.14% | 脚本报告 python |
| Codex | 同上，热身 1、计时 3 | 1265.63 ms；请求 numba 时 1235.40 ms | 53.05% / 53.01% | 39.79% / 39.90% | 约 8.3% | 两次实际后端都是 Python |
| 本轮 | 同上，只计时 1 次 | 1270.73 ms；请求 numba 时 1164.16 ms | 52.14% / 54.45% | 41.16% / 38.76% | 8.07% / 7.80% | 后端字符串仍是 python。Numba 在库里，门被 `reserve_state` 和 `take_profit` 挡住 |
| Grok | 自写 20 日 × 20 码 × 240，价格持平，第 4 日 10 只入池 | version8 0.093 s；version12 0.511 s（5.5×） | 未分项 |  |  | 未重跑 numba |
| 本轮 | 同规模持平夹具 | version8 0.081 s；version12 0.544 s（6.7×） | 未分项 |  |  |  |

可以复现的部分：官方基准每次大约 1.26–1.27 秒，卖扫大约 52–54%，昨收准备大约 8%，编排大约 40%。Kimi、Codex 和本轮在这个夹具上差在一次运行的噪声里。Codex 说不要再把 09-15 的 75% 当成今天的占比，成立；卖扫仍是第一大头，编排占比比旧文档高。

不能当成稳定常数的部分：本轮单次「请求 numba」墙钟 1164 ms 低于 1271 ms，大约 8%。脚本明确没走 Numba。Codex 三次平均只差约 2.4%，并写了这不能解释成加速。单次差 8% 同样不能。Grok 的 5.5× 和本轮的 6.7× 都说明策略 12 的纯计算是 version8 的数倍，毫秒和倍数随夹具变，不要引用成一个精确倍数。

成交结果：官方基准本轮得到 160 个持仓、160 笔买、320 行成交（含 EOD_MARK），与 Codex 一致。

建议按预期收益排，都还没做。验收用成交元组（日期、代码、方向、价格、股数、原因、现金），不用旧权益字节。策略 12 在 X-01 修好之后净值本来就会变。

| 顺序 | 改什么 | 预期 | 风险 | 数字从哪来 |
|---|---|---|---|---|
| 1 | 策略 12：每天每只缓存 MA5/MA10/止损线；分钟循环内联「close 与阈值、涨跌停」，不要每根调用完整 `scan_held_day`；池买和追买只挂在真正的钟上 | 合成夹具上有机会吃掉大约 5–7 倍里的大头。Codex 对更小的 v12 夹具估计 1.5–3 倍，并写了 I/O 会稀释 | 中。同日再武装、先卖后买、部分成交必须保持 | 倍数来自合成计时，不是全市场墙钟 |
| 2 | 不用涨停保留、也没有 Python 回调的书，不要传 `reserve_state`，让已经写好的 Numba 轨迹核有机会运行 | 若卖扫占 53% 且核快 10 倍，Amdahl 上限大约 1.9 倍端到端。Codex 写了这个上限。本轮没有测到核的速度 | 中。先保持 Python 默认，用现有对照测试锁成交元组 | 53% 可复现；10 倍是假设，不是测量 |
| 3 | 昨收、涨跌停、09:30/09:45/14:55 报价按 (code, day) 算一次 | 基准里昨收准备约 8%，池买约 6%。Codex 估计纯 simulate 5–20%，这是区间不是承诺 | 低。索引必须升序，缺根回退要和现在一致 | 8% 和 6% 三份报告加本轮都在同一带 |
| 4 | v7 不要每天 `to_dict("records")`（`csv_minute_backtest_v7.py:300-313`）；version11 在 `minute_open` 分支前不要先做用不到的整天数组 | 未计时。全市场时读盘通常先于这层 | 中。先修 X-11 的日历，再动过滤 | 无测量 |
| 5 | 读 parquet 时按行组的 time/symbol 统计做谓词下推。现在 `ashare_bars.py:354` 先整表读再滤 | 取决于行组布局。本轮无湖，不给倍数 | 中。缓存必须先有 X-12 的身份，不能为了速度丢掉 volume | 无测量 |
| 6 | 不要把热路径改成逐笔 Decimal，也不要先把策略 12 状态机丢进 Numba/Rust | 涨跌停到分已经是按代码按日的 Decimal | 改 HALF_UP 会动成交正确性；状态机回归面大 | Codex 和 Grok 一致：这不是当前热点 |

Kimi 的 O1（把 `take_profit` 降成数值参数再扩 kernel）和上面第 2 行是一件事。O5「去掉 Decimal」与第 6 行冲突：档位边界已经有 X-05 这种 float 问题，限价这一层应继续用 Decimal 或整数分，不要改成 float round。联合收益那条 789s→237.6s 的性能弧，Kimi 说文档已收官；本轮没有重读那份 handoff 的计时原始日志，不把它算进分钟书的收益。

## 6. 附录：删掉的说法

这些句子和当前代码或工作树文档对不上，不进入排名。

| 说法 | 为什么删 |
|---|---|
| Kimi `F-8-1` 后半：8.3 HELP 写 `[15%,50%)` / `[50%,100%)`，代码却是 `<=1.50` / `<=2.00`，等号点文档失真 | `livermore_exit_rules.py:28-36` 是 `p < cost×1.15`、`p < cost×1.50`、`p < cost×2.00`。精确 +50% 进入下一档，与 HELP 的左闭右开一致。Grok 写「8.2 用 `<=`、8.3 用 `<`，两边 HELP 和代码一致」，这句成立 |
| Kimi §1.5：成交与估值全程 `dividend_type=none` | 8.x 和 version11 的默认成交、估值在 none 日线上，这半句成立。version12 的日线被强制读 front，净值乘的是这份 front 收盘。见 X-01 的 5,049,000 / 5,199,000 |
| Kimi §2.1：策略 12 人裁全部落实，未发现与 binding 人裁矛盾的实现 | 「不加载 E-R6、分钟读 none」落实了。MA、涨跌停、市值仍和 none 成交直接比，这是缺口，不是落实完毕 |
| Kimi `F-S12-6`：策略 12 实湖五本对比未执行 | `docs/backtest/reviews/slice-d-minute-five-book-20260922c-2026-09-22.md` 已回填 2026-09-22 的五本 NAV，tip `6aeffef`，并写明不主张 parity。过时的是 handoff 里「尚未执行」。剩下的问题是：这张表用了混价域的策略 12，而且不是 `#169`/`#170` 之后的 tip，不能当策略排名 |
| Kimi `F-V11-3`：生产预热 200+，所以短 SMA 不影响 | 200 是导出器筹码窗。执行引擎预热是 `WARMUP_DAYS=10` 个自然日。短历史仍会静默 HOLD，见 X-20 |
| Kimi `F-S12-5` 的「跌停日大约放大 240 倍」当成固定倍数 | 只有「卖出计划成立、成交价再被跌停拦住」才按 bar 累加。开盘已跌停时扫描器直接跳过该根，计数可以是 0。X-01 的 front=12 夹具 `defer_sell_limit_down=0` |
| Grok `F-12`：v7 按分钟向前，没有卖款穿越 | v7 按股票扫完整天才换下一只，跨股票现金仍可逆时。策略 12 的按分钟循环没有「用 15:00 的钱买 09:45」 |
| Grok `F-10`：v7 把买入日 high 计入峰值，因此会更早武装加仓或止损 | `position.peak` 会写、会随除权缩放，止损和加仓不读它。名称分叉是真的，峰值这条影响不成立 |
| 把 2026-09-15 剖面的卖扫 75% 当成当前 `simulate()` 的占比 | 本轮和 Kimi、Codex 的同脚本复测都在 52–54%。旧数字只描述旧版本 |

本轮没有改仓库，没有跑 pytest，没有读真实分钟 parquet。因此没有给出「默认研究窗里这些错误改变了多少 NAV」的市场样本数字。X-01、X-02、X-04、X-05、X-06 的合成数字是本机 `simulate()` 的直接输出，可以按第 2 节的输入重做。
