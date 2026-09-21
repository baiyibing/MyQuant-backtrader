# 主笔侧对抗评审草案：plan-strategy12-jinrongyuan v0.3（2026-09-21）

- **评审人**：claude（主笔，本草案不计独立票）
- **方法**：3 路对抗子代理（dissent-steelman / domain-safety / pattern-evidence），三路均带文件工具完整取证
- **原则**：证据优先于票数；主笔让步逐条记录；外部四稿才是独立投票方
- **对象**：`docs/backtest/plan-strategy12-jinrongyuan-2026-09-21.md`（commit `4adad96`；注：commit 文案写 v0.3 而文件头仍标 v0.2——本勘误见 §5）

## §0 评审结论速览

| 维度 | 提案原立场 | 修正后立场 | 关键依据 |
|---|---|---|---|
| 部分卖方向 | 跨 lot FIFO | **is_step 先卖 + lot0 最后（LIFO 变体）** | `strategy8_rules.py:61-64` lot_id==0 锚 |
| 部分卖/买回落点 | opt-in 引擎通用钩子 | **γ：最小引擎面（shares 参数）+ 书侧专用状态机** | 单消费者 + 深耦合（`csv_daily_backtest.py:392-423`） |
| MA 口径 R3 | 只用昨收序列 | **昨收序列 PIT；现价合法（P2-B 保留但措辞修正）** | R3 字面 vs sma_live 自相矛盾 |
| P5 止损记忆 | 清空减仓记忆 | **双记忆并存**（docx 无作废条款） | docx 规则5 原文 |
| 买回四锁 | 「走既有门」 | **须新增：shares 覆写、t1_sellable 基数、送转缩放、per_name 合计上限** | domain-safety F1–F4 |
| 上证闸 P7 | 无闸 | 维持开放（dissent 主张开闸） | 交外部四稿 |

一句话：主体方向（v8 买侧 + 均线减仓书）存活，但引擎接触面、减仓顺序、买回不变量三处被实质重写；γ 方案以最小引擎面换掉原「通用钩子」表述。

## §1 关键发现（改变主笔立场）

- **F1【让步】部分卖 FIFO 会杀死台阶通道**（dissent + pattern-evidence 交叉）：`step_add_due` 以 `lot_id==0` 为锚（`strategy8_rules.py:61-64`），FIFO 先清 lot0 → parent=None → +20% 加仓永久失效。改为 **is_step lot 先卖，lot0 保底最后**。
- **F2【让步】P5 越权改写业务**（dissent）：docx「站上五日线买回减仓股份」无作废条件；止损不应清减仓记忆。双记忆并存，MA5/MA10 各买各的。
- **F3【让步】R3 与 P2-B 内部矛盾**（dissent）：`sma_live` 注入现价不违反 PIT（现价非未来信息），但违反 R3 字面。R3 改写为「MA **序列**只用截至昨收日线；现价只作探测值，不入序列」。
- **F4【让步】「引擎通用能力」过度设计**（dissent）：唯一消费者 + `csv_strategy_books.py:119-136` 已 18 个 setdefault + 卖出路径深耦合 → γ 方案（见 §3）。
- **F5【让步】买回四项不变量缺失**（domain-safety）：① `execute_buy` 股数由预算推导（`csv_ledger.py:219-229`），无 shares 覆写；② 减仓基数须= t1_sellable lots（分钟引擎当日买回当日再减无拦截，`csv_ledger.py:347` 仅 volume_cap 分支查 T+1）；③ 送转增股不缩放记忆股数（`csv_ledger.py:174-182` vs `:152-156`）→ 10送10 后买回腰斩，且 bonus 股可破坏整百股；④ 止损清仓后 pool 重买 + MA10 买回可破 per_name 100 万合计上限（`csv_simulate_loop.py:253-254` skip_held 仅挡持仓中）。
- **F6【让步】pending_exit 不能承载部分卖**（domain-safety）：per-lot 字符串原因（`csv_ledger.py:79`），volume_cap 下全或无（`:333-336`）→ 需独立的部分卖队列。
- **F7【部分让步】`ma12:` reason 落错 stats 桶**（domain-safety）：`csv_ledger.py:384-397` 无分支 → R5 扩到 stats 分派。
- **F8【部分让步】多 lot 拆卖费用偏差**（domain-safety）：QLIB `min_cost=5` 逐笔最低佣金略高估（`ashare_fees.py:22-27`）；研究引擎无印花税（`:9`）。记入 HELP_LOCK 声明，不改。

## §2 三方裁决对照

| 维度 | dissent-steelman | domain-safety | pattern-evidence | 主笔综合 |
|---|---|---|---|---|
| 部分卖落点 | 书内专用，禁动 ledger | 须扩 execute_buy + 新队列（否则不可实现） | 指出深耦合，不表态 | **γ**：两都对一半 |
| FIFO/LIFO | LIFO | 未裁（但 F2 隐含基数过滤） | 独立确认 lot0 不变量 | is_step 先卖 + lot0 最后 |
| P2-A/B | P2-A（防不可比） | 未裁 | sma_live 接口与 sell_gate 吻合 | P2-B 保留 + R3 改措辞；跨引擎差入 HELP_LOCK |
| 上证闸 | 开闸 | 未裁 | 指出「全复用 v8」与砍闸矛盾 | 开放，外部裁决 |
| 锚点质量 | —— | —— | 3 处事实错 + 行号漂移 | 全部回填（§5） |

核心分歧：dissent 的「完全书内」与 domain-safety 的「引擎必须扩」交集 = γ（最小引擎面：`execute_buy` 可选 shares、卖出路径可选 wanted_shares；状态机/编排全在书侧 `strategy12_rules` + 专用 helper）。

## §3 立场修正方案

- **α** = 原案：opt-in 引擎通用钩子（partial_sell_gate/buy_back_gate 挂 BOOKS）。弃：单消费者提前抽象 + 18 个 setdefault 的注册表再扩两钩。
- **β** = 对立全量：纯书内循环，引擎零改动。弃：`execute_buy` 无 shares 覆写、卖出路径无部分卖入口，β 不可实现（domain-safety F1/F5 证伪）。
- **γ（推荐）**= 最小引擎面 + 书侧状态机：① `execute_buy(..., shares_override=None)`；② 卖出路径支持 `wanted_shares`（按 t1_sellable 基数、is_step 先卖、整百股）；③ reduced/stopped 记忆放书侧 per-run dict（送转缩放钩子挂 exdiv 事件回调）；④ 买回编排在书侧 helper，走既有涨跌停/费用门；⑤ 两个引擎参数默认 None = 现行为逐字节不变（R2 不变）。
- 护栏：既有全量 pytest 不放宽；新参数默认路径与 HEAD 等价的 pin 测试；`ma12:` trades+stats 双标签。

## §4 留给外部四稿的必答题

1. γ 的最小引擎面是否仍嫌大？有无更小切口（如复用 volume_cap 的 shares 拆分路径）？
2. P2-B（分钟 sma_live / 日线昨收 MA）跨引擎口径差可接受，还是统一 P2-A 昨收判定？
3. P7 上证闸：docx 沉默时，以文档为准（无闸）还是以同族 v8 为准（开闸）？
4. 买回 per_name 合计上限语义：100 万是「持仓市值上限」还是「累计投入上限」？
5. 送转日记忆缩放：按 k 比例缩放记忆股数是否足够（现金红利显然不动股数）？

## §5 对提案稿的勘误（须回填）

| 位置 | 错误 | 修正 |
|---|---|---|
| 头部状态行 | 标 v0.2（commit 文案已 v0.3） | 回填升 v0.4，消除漂移 |
| §2 chase_decision | `:115-122` | `:115-121`；queue `:124-130` |
| §2 规则6「逐字对应、零新增」 | 过强 | T 日拦截在 `csv_simulate_loop.py:285-288`，T+1 判定在 chase_decision——跨两处 |
| §2 sell_gate 锚点 | `strategy4_rules.py:33-44` | buy_gate `:30-33`、sell_gate `:36-41`；分钟喂数点 `csv_minute_backtest.py:669` |
| §2 Position | `:73-87` | `:70-82` |
| §2 step_add_due | `:56-70` | `:57-69` |
| §2「add_gate=None」 | 错 | v8 实为 `may_add`（`csv_strategy_books.py:573`，恒 True）——功能等价、机制不同 |
| §2 version8 注册「约 :920-936」 | 错约百行 | `:1018-1031` |
| §2 HELP_LOCK pin 归属 | test_strategy8_milestones.py | 该文件锁注册+冻结语义；help_lock pin 在 `test_csv_strategy_books.py:176-179` |
| §3 缺口清单 | 漏 4 项 | 补 F5 的四项买回不变量 + pending_exit 不可承载 + ma12 stats 桶 |
| P3 建议 | FIFO | is_step 先卖、lot0 最后 |
| P5 建议 | 止损清减仓记忆 | 双记忆并存 |
| R3 措辞 | 「MA 输入只用昨收」 | 「MA 序列只用昨收；现价为探测值不入序列」 |
| R5 | 只锁 trades 标签 | 扩 stats 分派桶 |

## §6 最终立场

投 γ：v8 买侧 + 均线减仓书的主体成立，但以「最小引擎面 + 书侧状态机」替换「通用钩子」，FIFO→is_step 先卖，双记忆并存，买回四锁入切片 B/C DoD。请外部四稿重点裁决 §4 题 1/2/3。
