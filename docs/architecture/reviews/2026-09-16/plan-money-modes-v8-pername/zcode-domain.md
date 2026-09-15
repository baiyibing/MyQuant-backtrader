# 资金语义对抗评审（host: zcode-domain）

> 评审对象：[plan-money-modes-v8-pername-2026-09-16.md](../../../../backtest/plan-money-modes-v8-pername-2026-09-16.md) v1.0 · 2026-09-16
> 角色：domain-safety + dissent-steelman · 结论：**READY-AFTER-FIXES**

框架（策略书级 sizing、双模式、M-R5 逐字节回归锁）方向正确、无破坏成交核的 🔴；但 6 条 🟡 必须在 GO 前回写 plan（名单序偏差声明、chase 弃单终态、日线止盈时机与 docx 的显式差距、P1 默认翻转建议、per_name 强制 allow_add=False 的实施锁、跨 sizing 对比纪律），否则切完 per_name 的 v8 研究结论带有未声明的系统性偏差。

## 发现

### 🟡-1（Q1）skip_cash 对：但「名单序=CSV 序」在现实池上是「代码升序优先」，且 per_name 摧毁了唯一的日总额节流

**证据**
- 均分现状：`csv_simulate_loop.py:145` `per = min(daily_quota, st.cash) / len(planned)`（现金不足时**全体等比缩量**，无 skip）；`csv_daily_backtest.py:135` 日额度 100 万。
- 保序契约：`csv_pool.py:53-68` `parse_pool_csv_entries`「去重、保序」，行序即文件序；`stock_pool/20251023.csv` 实测为**代码升序**（000027、000089、000090、000530…），`pool-csv-contract.md` 未定义行序=优先级。
- 池宽实测：`stock_pool/20251023.csv` 38 行、20251024 32 行、20251027 42 行（窗口尾部 20260907–09 为 2/10/1 行）。
- v7 先例：`csv_minute_backtest_v7.py:48` `NAME_BUDGET=1M`、:189–193 `cost > state.cash → skip_cash`。
- 兜底拒单：`csv_ledger.py:199-200` `notional + comm > st.cash → return False`（不透支）。

**对抗两方**
- 反 skip（缩量派）：21M 现金、38 只名单 → 前 ~21 只吃满、后 ~17 只（约 45%）整笔 skip；由于 CSV 按代码升序，**入选集合系统性偏向小代码**，与信号质量零相关。早期名单占款后先发优势跨日复利（持仓占用现金，后来者继续 skip），等价于回测了一个「21 只低代码股」组合。缩量则每名都买到、无序偏差、资金利用率平滑。
- 保 skip（plan 方向）：docx §1 是「单个股票金额100万」——**字面上排除了 600K 缩量买**，缩量是没有任何业务方要过的第三种语义；v7 同款 skip 有先例；整笔制下每笔盈亏/风险口径干净（每股≈1M 敞口恒定），跨 lot 可比。

**裁决建议：保留 skip_cash（不改 M-R2 主语义），但 plan 必须补三件事**：
1. M-R2 加一句偏差声明：「现实 `stock_pool/` 文件为代码升序，现金受限日的入选集合偏向小代码；名单序语义=导出器契约，本 plan 不定义优先级」。
2. 切片 A 的 stats 增项从「skip_cash 计数」扩为 `skip_cash`（笔数）+ `skip_cash_notional`（被跳过目标金额）+ 按日名单宽度分布（M-R5 允许新增字段）。
3. 切片 D 报告固定输出「逐日 bought/skip/宽度」表，让人直接看到偏差幅度再决定是否未来给名单加排序列（另开 plan）。

对研究结论的影响：若不加声明，v8-pername 的 NAV/胜率相对 daily_quota 版本的差会被误读为「卖点/止损变更的效果」，其中混入了 ~45% 名单从未参与的容量效应。**这是本 plan 最大的结论污染源。**

### 🟡-2（Q2）chase 排单：现金不足是「按排单序先到先得、失败即永久弃单」，per_name 把爆仓面从 1M/n 放大到 1M/笔；不应预冻结

**证据**
- 排单：`csv_simulate_loop.py:164-165` 涨停 → `queue_limit_up_chase(st, pending_chase, code, per, day_i)`，per_name 下 `per_ch=1M`（M-R3）；`csv_ledger.py:114-118` 同码重复排单覆盖预算（chase_overwrite）。
- 累积：`pending_chase` 是 dict，多日多码并存（`csv_simulate_loop.py:91` `due = [... if day_i > sig]`）；停牌/缺 K 会 keep pending（E-R4，`engine-ashare-correctness.md:27`），恢复日集中到期。
- 成交序与终态：`csv_simulate_loop.py:104` **先 `pending_chase.pop(code)` 再 :123 `execute_buy`**——现金不足返回 False 只计 `chase_buy_fail`，**该码永久弃单、不重试**；dict 迭代序=排单日池 CSV 序。
- 时钟正当性：chase 在 pool 之前执行（日线 `csv_daily_backtest.py:425` vs :445；分钟 `csv_minute_backtest.py:908` vs :936），与真实 9:45 < 14:55 一致。
- 现状（daily_quota）：per_ch = min(1M, cash)/n（csv_simulate_loop.py:145），单笔 ≤ 1M/n，多日累积数十笔也只占几十万级，21M 池几乎不可能拒单 → **这个问题现状基本不存在**；切 per_name 后每笔排单 1M，一个 38 名单日全部涨停排队就是 38M > 21M，**确定性出现按代码序的先到先得弃单**。变坏，量级 ×n。

**裁决建议**：
- **不预冻结**。反方（冻结派）能拿到的唯一好处是到期日不再弃单，但代价是：弃买（市价<开盘，`chase_decision` abandon）前现金被锁死、需要跨日解冻状态机、与 v7（成交时点查现金，`csv_minute_backtest_v7.py:191`）不同构——为消除一个可观测、可计数的偏差引入一个新的资金死锁面，不值。
- 改 plan：§8 风险表第三条「execute_buy 现金不足拒单兜底」扩写为完整语义：「排单不冻结现金；到期按排单序成交，现金不足者**pop 后永久弃单**（chase_buy_fail），与 v7 同构」。
- 切片 A stats：把 `chase_buy_fail` 按「现金不足 / shares≤0」拆计数（shares≤0 在 force-min 下理论不可达，若出现说明 bug），与 skip_cash 一样留观测面。

### 🟡-3（Q3）止盈阶梯：峰值涨幅解读成立但要写死；日线「收盘评估→次日开盘成交」+ 不看日内 low 的差距必须在 plan 里显式声明

**证据**
- 区间开闭：`strategy8_rules.py:26-32` `BANDS=(0.15,0.40,0.15)…(1.00,1.20,0.90)`，`:40-41` `lo < peak_ret <= hi`——与 docx「15%＜涨幅≤40%→15%」的 (lo,hi] 完全一致；第一档 docx (0,15%]，现行有效档 `[6%,15%]`（:38 `SMALL_ARM <= peak_ret <= PROFIT_BASE`）——差异即 P1。
- 触发价：`:85` `px <= cost*(1+floor)`（回撤到绝对涨幅地板，含等号）；`:81-82` `px < cost → None` 守卫——跳空穿越地板到成本下方时 band 不触发，交由止损兜底。
- 峰值：`:63-65` `peak > cost*2.2` 武装、`px <= peak*0.8` 触发，与 docx「>120% 回撤最高价 20%」一致（120% 边界点归 90% 地板档，两侧开闭对齐）。
- 峰值更新：日线 `csv_daily_backtest.py:389` 用当日 high（买入日建仓于收盘后，当日 high 先于持仓，排除正确）；分钟 `csv_minute_backtest.py:550-556` T+0 跳过、14:55 买入后 14:55–15:00 的 high **不计峰值**（HELP_LOCK :108 已声明，轻微低估 docx「最高价」）。
- 执行时机差距：日线止盈只在**收盘价**评估（`csv_daily_backtest.py:401-414`），触发后 `pending_exit` **次日开盘**成交（:357-361）；盘中 low 跌破地板但收盘收回的情形**不触发**。分钟版逐分钟 close 评估、同 bar 成交（`csv_minute_backtest.py:590-593`），接近 docx 语义。

**解读歧义裁决**：docx 的「涨幅」只能解读为**持仓期峰值涨幅**（若按现价涨幅，规则自指：现价已跌到 2% 时现价涨幅就是 2%，永远落在第一档，高档地板形同虚设）——peak 解读是唯一自洽读法，现行实现正确。但 docx 只在 >120% 档写了「最高价」，前六档未定义峰值来源，plan §1 表应补一行把「涨幅=峰值/买价-1，峰值=持仓期最高价（日线日 high/分钟 bar high，T+1 起算）」写死，防后人重读 docx 翻案。

**差距声明建议（改 M-R4）**：M-R4 现在只写「卖出执行时机沿用各引擎现行语义」——不够。应显式声明：「docx 为盘中回撤即时触发；日线引擎为收盘确认、次日开盘成交，且不看日内 low——相对 docx **少触发**止盈（日内击穿地板收盘收回的都不算）且成交价带隔夜跳空；跨引擎结论以分钟版为准，日线版仅做长窗近似」。这段话属于 docx 对照差异，不写就是给业务方埋认知雷。

### 🟡-4（Q4 + Q6/P1）30% 止损 × SMALL_ARM 保留的组合：pre-6% 峰值仓位的尾部风险被静默放大；建议 P1 翻转为按 docx 字面去武装

**证据**
- 现状武装：`strategy8_rules.py:20` `SMALL_ARM=0.06`（注释「用户口径：2%×2」）；`:38` 峰值 ∈ [6%,15%] 才有 2% 地板，峰值 ∈ (0,6%) 时 `band_floor` 返回 None → **该仓位只能走到 -30% 止损或期末 EOD**。
- 止损改为 0.30 意味着：保留武装时，「摸到 +5% 后回落」的仓位从「骑到 -20%」变成「骑到 -30%」——**武装是在 20% 止损时代定下的口径，plan 只改止损不改武装，等于业务从未确认过的组合**。这是 P1 默认「保留」最大的隐性代价，v1.0 §3 P1 行只写了「去武装会显著提高 +3%→+2% 早离场频率」，没写反方向的尾部放大，人裁信息不对称。
- 反方向 steelman（保武装）：docx 未提武装≠否认武装，0913 docx 只重写资金与止损，止盈段可能默认沿用既有口径；去武装后每个弱反弹都在 +2% 落袋，策略从「让利润奔跑」滑向高频刮痧；「改动最小」在引擎侧是真实美德。
- 去武装 steelman（docx 字面）：docx 是最新业务权威；七档边界写得极精确，若业务想要 6% 武装不会恰好漏写；且 30% 止损使武装的尾部代价变大——保留方需要业务重新背书，而不是默认继承。

**止损滑出量化**：10% 板连三跌停 0.9³=0.729>0.70 未到触发线，第四日 0.656 打开按开盘成交 ≈ **-34%**；20% 板两跌停 0.64 已穿 0.70，全程 defer（E-R1），打开日成交 ≈ **-45%~-50%**；30% 板 0.70 恰为触发且即跌停 defer，次日 0.49 → **-51%**。单 lot 实际最大亏损 ≈ 0.51M+佣金 ≈ **21M 的 2.4%**（无加仓前提；若 per_name 下保留加仓，单码敞口按日线性堆到现金上限——这是 P2 必须取消加仓的硬理由，见 🟡-5）。

**「滑出止损幅度」观测裁决**：加，但**不动 `csv_ledger`**（M-R6 明令禁碰）。做法：切片 D 的对照脚本从 `trades.csv` 事后计算（BUY lot 成本 × SELL `stop_loss*` 行成交价 → 实际亏损分布、最大滑出 pp、defer 后隔日成交占比），输出进对照短记；若日后要进 stats，另开 plan 改 M-R6。同时把 §8 第二条「回撤可能超 30% 才卖出——语义已知」补上量化区间（-34%~-51%）。

### 🟡-5（P2 实施 + Q8）P2 取消加仓裁决正确，但 plan 没锁实现点：per_name 必须在 hook 解析层强制 `allow_add=False`，否则 M-R3 被静默违反

**证据**
- 现状 v8 书 `ALLOW_ADD=True`（`strategy8_rules.py:14`），经 `csv_strategy_books.py:92` `hooks["allow_add"] = book.allow_add` 注入，引擎在两处消费：池内已持 `csv_simulate_loop.py:147`、chase 已持 `:94`。
- 若实施只在 `run_pool_buys_day` 加 per_name 分支算 `per` 而不动 `allow_add`，则 `:147` 的 `not allow_add` 为假 → **同码每日再买 1M**；chase 路径 `:94` 同理——与 M-R3 直接矛盾，且是静默的（会误计 `add_lots` 而非报错）。
- P2 两个方向 steelman：保加仓派——v8 HELP_LOCK 明文「已持仓票再次出现继续买，各笔 lot 独立」（`strategy8_rules.py:97`），是用户可见承诺；「每股票100万」可读作每次进场 100 万。取消派——docx「**单个股票**金额100万」最自然读法是单码总敞口上限，per_name+日频名单下保留加仓=单码敞口日增 1M 直至现金耗尽，既违反字面又叠加 🟡-4 的跌停尾部。

**裁决建议：P2 取消加仓（维持 plan 默认），但切片 B 完成定义加两条硬锁**：
1. `sizing="per_name"` 时在 `apply_csv_strategy`（`csv_strategy_books.py:89-105`）层面覆写 `hooks["allow_add"]=False`（不是在引擎分支里各改一处），保证池买/chase 两条路径同锁；
2. 新增单测：per_name 下同码次日再现名单 → `skip_held`+1、`add_lots` 恒 0；chase 到期日已持 → `chase_skip_held`+1。
另 `daily_quota` 模式下 v8 保留 `ALLOW_ADD=True` 供历史窗口复跑——两模式行为分叉要在 HELP_LOCK 文案里写明。

### 🟡-6（Q7）跨 sizing 可比性：plan 缺对比纪律条款，且 `maybe_compare_daily` 会拿切前旧日线工件打出误导性 caption

**证据**
- 切 v8=per_name 后，v8 与 1–6/9/10（daily_quota）的 NAV 不再同口径；v8 自身历史也在切换点断代，而 M-R1 禁 `--sizing` 开关意味着**切换后 CLI 无法再跑出 v8-daily_quota**——切片 D 的 A/B 只能靠「切前工件/切前 commit」。
- 具体陷阱：分钟引擎每次运行自动找 `csv_daily_v8_{start}_*` 最新净值做对照（`csv_daily_backtest.py:731-748` `maybe_compare_daily`、分钟侧 `csv_minute_backtest.py:1091-1095`），caption 固定写「**差来自卖点时钟**」（`csv_daily_backtest.py:714`）。切换后若 backtest_output 里还躺着切前 daily_quota 版 v8 日线工件，分钟 per_name 对照会把这个差错误归因为卖点时钟——**自动产出误导性研究结论**。

**裁决建议：新增 M-R8（对比纪律）**：
1. v8 跨策略表只允许同 sizing 比 NAV；不同 sizing 只比 lot 级指标（每笔收益分布/胜率/单码敞口），summary 自带 `sizing` 字段作为工件自描述。
2. v8 的 daily_quota 对照基线 = 切换前同窗同池工件（或 commit A 上重跑），并在切片 D 短记里记录基线工件的 commit/日期。
3. 切换后首次宿主烟测**必须先重跑 daily v8（per_name）覆盖/新建同窗工件**，再做分钟对照；或把 `format_equity_compare` caption 的触发条件改为双方 summary 的 sizing 一致才写「差来自卖点时钟」——二选一，写进切片 C/D。

### 🟢-7（Q5）force-min：保留，但 plan 两处措辞要修——它不是死代码（`--name-budget` 可激活），且「对齐 v7」在这一点上不成立

**证据**：`csv_ledger.py:168-178` `_buy_size`——1M 预算下触发条件是 `px > 10,000` 元，A 股无此价，**默认参数下确实是死路径**；但 M-R1 新增 `--name-budget` 可把预算降到任意值（如 200K → 茅台级股价即触发），force-min 是预算条件函数不是股价常量。docx「资金池补齐」与现状语义一致：超额部分从全局池支付、只记 `supplementary_used` 统计不占预算（`csv_ledger.py:203`）。**反例**：v7 `_buy`（`csv_minute_backtest_v7.py:189-193`）整百向下取整后 `shares<=0` 直接 `skip_cash`，**没有 force-min**——M-R2 写「对齐 v7 NAME_BUDGET」并括注「force-min 保留」是 v7 语义与 docx 语义的混合体，照抄 v7 写单测会断言错。

**建议**：保留 force-min（docx 明文 + `--name-budget` 交互 + M-R6 禁碰 `csv_ledger`）；M-R2 措辞改为「skip_cash 对齐 v7；force-min 为 docx「资金池补齐」条款、**v7 无此行为**」；切片 A 的 per_name force-min 单测用 `--name-budget` 小值构造（如 budget=3,000、px=40 → 强买 100 股、supp=1,000），别按 1M 写。

### 🟢-8（Q8）其余资金语义边界盘点（均不阻塞，择要声明即可）

1. **`daily_quota_used` 残迹**：`csv_ledger.py:202` 累加 `min(per, notional)`、每日重置（`csv_daily_backtest.py:339`），但**从未被读取做 enforcement**；per_name 下它累 1M/笔，是无意义数字。建议切片 A 顺手在 per_name 分支不累加或注释标注 vestigial，防后人误当额度利用率。
2. **daily_quota 模式的静默买败**：`csv_simulate_loop.py:172` `execute_buy` 返回值被忽略——佣金挤占下最后一笔现金不足时**无任何计数**静默跳过（现状既有）。per_name 加了 skip_cash 计数后两种模式观测面不对称，声明即可，不必修（M-R5 锁行为不变）。
3. **佣金口径**：0.1% 双边、无最低佣金、无印花税/过户费——既有约定，M-R6 已锁，docx 未提成本，不扩。
4. **多 lot 峰值独立**：每 lot 自带 cost/peak/entry（`csv_ledger.py:57-67`），daily_quota 遗留模式加仓语义完好；per_name+P2 后 v8 单 lot 化，无新边界。
5. **T+1 与 chase**：chase 成交记 `entry_idx=成交日`（`csv_ledger.py:207`），T+1 从成交日起算，符合 A 股规则；EOD_MARK 零佣金、不落现金，期末 NAV 不双重计费。
6. **停牌估值**：净值用最近有 K close 而非成本（E-R4），停牌期间 equity 不冻结在成本上——口径正确。
7. **日线止损 touch 按触发价成交**（`csv_daily_backtest.py:381-386` fill=trigger）偏乐观；分钟 touch 按 bar close 成交（`csv_minute_backtest.py:563-565`）更保守——既有引擎间差异，与 🟡-3 同属「日线 vs 分钟」声明族。
8. **skip 可观测性**：v7 的 skip_cash 落 trades 行（`csv_minute_backtest_v7.py:192`），共享引擎只进 stats——研究人员 grep trades.csv 会漏，切片 D 报告应从 stats/summary 取 skip 数据。

## 人裁点建议

| # | 裁决建议 | 一句理由 |
|---|----------|----------|
| **P1** | **翻转 plan 默认：按 docx 字面去 SMALL_ARM**，保留切片 D 的有/无武装 A/B 数据点；如业务重申「2%×2」口径再恢复（成本=一个常量+多处单测+文案） | SMALL_ARM 是 20% 止损时代口径，与 30% 止损组合后 pre-6% 峰值仓位从「骑到 -20%」变「骑到 -30%」——这个组合业务从未确认过，且 docx 七档边界之精确反证「漏写武装」的概率低。 |
| **P2** | **维持取消加仓**，但按 🟡-5 加两条硬锁（hook 层强制 `allow_add=False` + skip_held/chase_skip_held 单测） | docx「单个股票金额100万」读作单码总敞口；per_name+日频名单下保留加仓=单码敞口日增 1M 直至现金耗尽，叠加跌停 defer 尾部（-34%~-51%/lot）是唯一可能出 🔴 级集中度事故的路径。 |
| **P3（新增）** | 采纳 🟡-6 的 M-R8 对比纪律：v8 只与 v8 自身（切前 daily_quota 同窗工件）比 NAV；跨 sizing 只比 lot 级指标；切换后先重跑 daily per_name 工件再让分钟引擎自动对照（或 caption 改为 sizing 敏感） | `maybe_compare_daily` 的「差来自卖点时钟」caption 在混 sizing 对照下是自动生成的错误归因，这是切换后第一天就会踩的坑。 |
| **P4（新增）** | 把 🟡-1 的名单序偏差作为显式人裁项向业务确认一次：「现金不足整笔跳过时，入选优先级=名单行序（现实文件=代码升序）是否可接受？若不可接受，需在名单契约加排序列（另开 plan）」 | 早期窗 ~45% 名单因代码序买不进，这不是实现细节而是选股语义——业务一句「名单序无所谓」或「按评分排」决定 v8-pername 结论的有效域。 |
