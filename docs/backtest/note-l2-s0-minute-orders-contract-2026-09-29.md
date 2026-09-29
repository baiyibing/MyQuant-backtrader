# minute_orders_research_v1：research contract v0（L2-S0）

2026-09-29 · **L2-S0 docs-only / Human GO** · 基线 `7bdc7f7`（#248 后，L1 四个 adapters 已合入）· `production_C=frozen`。

Human「开干 L2-S0 合同文档」冻结 **Q2=A / Q3=PLAN §4.2 窄包逐行签认 / Q4=机制参考自行实现**。本文是研究合同 v0，不是 production SSOT，不声称交易所精确撮合；**不是 L2-S1 implementation GO**。本片无 Python package、MatchCore、adapter 或 L1 views；L2-S1+ 仍须各片显式 GO，且保留 PLAN 的 L1-S5 前置门，四家 adapters 合入不自动替代该门。PR 须 Human「合」，勿自动合并。

后续状态：另获 Human GO 的 [L2-S1 types + MatchCore](note-l2-s1-matchcore-2026-09-29.md) 已落地为 **action-only**，[L2-S2 ledger + fee](note-l2-s2-ledger-fee-2026-09-29.md) 已实现账本、预留和累计费；Broker/Clock/runner 与 L1 注册仍受后续切片门禁约束。

授权依据（工作站外部文件，不是运行依赖）：

- `/workspace/handoffs/l1_l2_research_engine_plan_20260928/PLAN_L1_L2_RESEARCH_ENGINE.md` §4.1–4.6、§5 L2-S0、§9 Q2–Q4。
- `/workspace/handoffs/l1_l2_research_engine_l2s0_20260929/HUMAN_FREEZE_Q2_Q4.md`。

## 1. 首问与身份（Q2=A）

给定外部冻结的 BUY/SELL LIMIT 意图，在 **completed-bucket close** 的容量近似下，显式数量、partial、expiry、撤单、整手/T+1 与资源预留如何决定成交和残量？输入自行声明 `available_at/submitted_at/effective_at/expires_at`、symbol、side、limit、数量、稳定 ID/sequence；不读名单生成策略、不从旧 trades 倒造订单、不移植 JR pack。JR 已有 partial/expiry，本合同不是填补其不存在的功能。首版明确排除 B（next-open）和 C（在线 StrategyPort / 双触发），不提供 A/B/C flags。

| 身份项 | 冻结值 / 边界 |
|---|---|
| backend / contract | `minute_orders_research_v1` / `research contract v0 (L2-S0)`；独立于 BOOKS，不是 `version13` |
| 价格模型 | `completed_bucket_close`；必须与 bucket clock、可得时点一起记录，不能借旧 `close` 参数名表示等价 |
| 未来 package | `backtest/research/minute_orders_backend/`；仅冻结名称，本 PR 不创建目录或文件 |
| 未来 API | `run_minute_orders_research`；显式 opt-in，当前不存在；无旧入口 fallback |
| 未来输出根 | `backtest_output/minute_orders_research_v1/<run_id>/`；已存在即拒绝（包括空目录），不得覆盖/清空/复用成功目录 |
| 首版输入范围 | 显式小输入；long-only cash、单账户、普通主板股票 instrument facts、连续竞价分钟；L2 ≠ `l2_analytics/`、LEBS 或 MockQMT |

## 2. PLAN §4.2 逐行冻结（Q3）

下表每行均已由 **2026-09-29 Human freeze** 签认；“显式输入”不是实现者可补默认的空位。数值参数、可得性及覆盖证据缺失须失败，不能继承 production 默认。

| Theme | Frozen choice（Human-frozen 首版） | Explicit exclusions |
|---|---|---|
| Clock / availability | **已签认**：`Asia/Shanghai`；显式 bucket start/end，完成 close/volume 在 end 才可见；订单 `available_at <= submitted_at < bucket_start`，且 `effective_at <= bucket_start`；match 时点为 end，严格早于 expiry | 不猜 START/END；交易日历、午休、端点须验证；非连续桶拒绝；不用同桶完成量作更早决策 |
| Same-ts order | **已签认**：先 cancel/expiry，后合格活跃单 match 并逐笔原子入账，再处理该刻新 submit，最后 mark/观察；全序键 `(event_time, phase_rank, sell_before_buy, submitted_at, sequence, order_id)`；同单同相位命令也须由 sequence 区分，冲突键失败 | 不按输入行顺序仲裁；保持显式 sequence 的置换结果不变；sell-first 仅属本合同，不复制 vendor bid-first、不回改 CSV/JR |
| Lifecycle | **已签认**：LIMIT only；Submitted→Accepted/Rejected；Accepted/PartiallyFilled→PartiallyFilled/Filled/Cancelled/Expired；无 fill 时保留原活跃状态；终态不再成交，cancel 只处理残量；`expires_at` 必填、右开 | 无 GTC/DAY 默认、replace、stop、market；冲突 command ID fail-closed；终态不能自动复活 |
| Missing-root / halt | **已签认**：经日历/停牌覆盖证明的合法缺根或显式 halt 不 fill，订单存续到 expiry；关键字段缺失、桶乱序/重复、价域/单位不明为输入失败 | 不补根、不用 stale quote；缺覆盖证明不能假定可交易；不将坏输入包装为“无行情” |
| Capacity / partial | **已签认**：`participation_rate` 必填；完成桶 `volume_shares` 按 symbol+bucket 共享双侧总容量，数量按整手向下取整；零量不 fill，缺量失败；残量跨桶保留至到期 | 无默认 10%，无每单独领完整容量、无追补、无未完成量；未用容量不跨桶累计 |
| Price / trigger | **已签认**：BUY `close <= limit`、SELL `close >= limit` 才有候选；候选价仅 close，仍须资格/资源门通过 | 不用 open/H/L 改价或造 bar 内路径；不支持 stop/OHLC 合成 tick，不称修复 Q39/hl |
| Limit / instrument | **已签认**：显式板块、tick、当日上下限及 reference facts，Decimal 到分并验证 tick；采用涨停不买、跌停不卖的保守方向门；越界/坏事实失败 | 普通主板之外、上市特殊日、缺限价事实拒绝；不套固定 10% band；不借此修改旧 predicates |
| Lot / T+1 | **已签认**：买卖整手、整数且非负；买 lot 下一显式交易日才可卖；初始 lots 带 acquire/sellable 日期；SELL 接受时预留可卖量 | 不用自然日+1；负量/非整手输入失败；零股、红股、公司行动拒绝，不静默丢弃；不声明全板块适配 |
| Cash / reservation | **已签认**：BUY 接受前预留 `limit × remaining_qty + fee_upper_bound`；不足 Rejected、不 resizing；SELL 不足可卖量也 Rejected；partial 后按实际成交调整，终态释放残余预留 | 禁止超额/重复预留；已拒单不因后来卖款复活；该刻新 submit 只能使用此前已入账、未预留资源 |
| Fill / Fee | **已签认**：fill ID 唯一、可重放；价格/现金 Decimal、数量整数；每订单累计名义金额算累计费，本次只扣累计差额；费率、最低费、其他费及舍入规则显式输入；零成交取消费为零，残量取消不加费、不退已成交费 | 不按 partial 重扣最低费；无生产费率继承、隐式退款或实际全税费声明；Fee model 只出 proposal，不自行扣现金 |
| Ledger / Mark | **已签认**：Ledger 唯一拥有现金/预留/lots/fees/去重及容量提交状态；mark events 显式、独立于 match；缺合法 mark 停止并失败；公司行动须覆盖 attestation，首版事件非空拒绝 | mark 不造 SELL；不以 lot-cost/prior 补值；缺公司行动资料不等于无事件；不共享旧账本 |
| Failure / output | **已签认**：输入/合同/算术错误中止 run；业务 Rejected 是有效订单结果；fill+fee+容量+预留原子更新；保留失败证据，不返回成功 NAV、不写 success marker | 无自动 retry；不覆盖既有根；不猜盘、不下载、不接湖；失败不能留下半笔成交或伪成功摘要 |

### 2.1 手算所用的运算与边界

| 项目 | v0 的明确解释 |
|---|---|
| 桶容量 | 令显式整手单位为 `L`、桶量为 `V`、参与率为 `p`：`C = L × floor(p × V / L)`；同 symbol+bucket 的 BUY/SELL 增量成交绝对股数之和不得超过 C |
| 单次数量 | 有候选且资格通过时，按 `L` 下取整并取订单残量、剩余桶容量和已预留资源可支持量的最小值；0 不产 fill；不能把资源不足的 submit 缩量接受 |
| 价格与舍入 | 金额以 Decimal 运算；价/限价事实到分且符合 tick，不静默修价。费用模型须写明累计金额→费用的算式、到分舍入点和 rounding mode，无舍入默认；先得到累计应付费，再求差额 |
| 累计费 | 令累计成交名义金额为 N，显式模型为 `F_side(N)`，`F_side(0)=0`；本次 `fee_delta = F_side(N_after) - F_side(N_before)`，须非负；取消/到期保留已付费、不再收最低费 |
| 费用上界 | BUY 预留中的费用是模型给出的**未来增量费上界**；partial 后基于已付累计费和 limit 下的残量重算，不能再预留已付费；模型不能提供有效上界则失败 |
| 同刻终态 | 达到 `expires_at` 即 Expired，等于 match 先 expire；同刻 cancel 与 expiry 同指一单时以右开到期为准，cancel 不再变更终态/释放两次；未到期的有效 cancel 先于 match |
| 时点证据 | 分列 quote/bucket、available、submit/effective、match、booked 时点；close 候选及入账在桶 end；同刻新 submit 在 match 后处理，绝不回填已开始的桶 |

这些解释只服务新研究合同；完成桶 close+volume 仍是 bar 容量近似，不表示交易所队列、冲击或可执行收益。具体数值只来自显式输入，[手算草图](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md)的数字不是默认参数。

## 3. 职责与副作用

- **Clock**：管理全序、日历及可见字段，不算费用/止损。
- **BrokerCore**：管理生命周期、资格、命令排序并请求预留；资源权威仍在 Ledger。
- **MatchCore**：仅产生带 order ID / bucket 证据的 `CandidateMatch` 动作；不是 Fill，无现金、费用、lots 或容量扣减副作用。
- **Fill / Capacity / Fee proposal**：依据残量、整手、共享容量、预留资源产生数量/费用提案；不独立扣钱、扣容量。
- **Ledger**：唯一提交者；校验版本/身份、去重并原子应用 fill、fee、现金、lot、预留与容量。相同 fill 重放不重复入账，ID 内容冲突失败。
- **Mark**：仅读已入账状态并使用显式合法估值事件；不提交订单、不补成交。缺估值失败，不能返回成功净值。

首版是单进程确定性离线回放；不建 event bus、gateway、恢复服务，不扩 `ashare_fill_clock` 命名叶子职责，不用 L1 envelope 充当账本。

## 4. 工件 schema（仅文档，未来 writer 合同）

以下为独立根内的拟定文件及最小逻辑字段；JSON 金额/价格使用 Decimal 字符串，数量用整数，时间带时区，字段不可得不填零。当前不创建任何工件或 writer。

| 工件 kind / 拟定文件 | 必须可追溯的内容 |
|---|---|
| contract / `contract.json` | contract_version、backend_id、price_model、clock/phase/lifecycle/capacity/lot/fee/mark/failure 规则；显式参数与其来源，不把样例当默认 |
| input identity / `inputs.json` | input_hash 与逐输入 hash/ref；订单/命令、桶、日历、instrument facts、初始现金/lots、mark、halt/公司行动覆盖 attestation |
| commands / `commands.jsonl` | command_id、order_id、kind（submit/cancel）、symbol/side、qty/limit（submit）、available/submitted/effective、expires_at（submit）、sequence；cancel 引用目标单 |
| orders / `orders.jsonl` | order_id、状态变迁事件/全序键、原因、original/filled/remaining qty、现金/可卖股预留变化、对应 command/fill ID |
| incremental fills / `fills.jsonl` | fill_id、order_id、symbol/side、增量 qty/price/notional/fee_delta、累计金额/累计费、bucket/clock 证据、容量用前/用后、ledger 版本 |
| ledger snapshots / `ledger.jsonl` | event_key、ledger_version、cash、reserved/free cash、lots 的 acquire/sellable 日期与 reserved/free qty、累计 fees、已提交 fill IDs 与桶容量消耗 |
| mark snapshots / `marks.jsonl` | mark event ID/time、来源/价域、逐持仓 mark、对应 ledger_version、估值有效性；不是交易记录 |
| manifest / `manifest.json` | schema_version、run_id、backend_id、contract_hash、code_sha、input_hash、evidence_level、comparison_status、status、工件相对路径/hashes；不得用旧 backend 身份 |
| completion summary / `summary.json` | 仅成功后最后写；status=`success`、订单终态/活跃残量及计数、fills/fees 汇总、合法 mark 引用。未到 expiry 的活跃残量如实列出，不默认 DAY/GTC 或强平；该文件是唯一成功完成标志 |
| failure evidence / `failure.json` | status=`failed`、失败阶段/原因、事件和输入引用、最后已提交版本/工件；不含成功 NAV。失败 manifest 标 failed，禁止写成功 summary |

`contract_hash` 标识冻结规则及显式模型配置，`input_hash` 标识包括初始状态/参数在内的本次输入；均用 SHA-256，具体编码须固定并登记。`code_sha` 是未来实际执行实现 SHA，本片基线不能冒充实现。`evidence_level` 区分 synthetic/真实来源；S0 只有文档手算、未执行。`comparison_status` 默认声明未获 SSOT 比较授权，不因成功运行自动变绿。

未来 writer 须独占创建新 run 根；存在即失败。所有工件及校验完成后才原子发布成功 `summary.json`；失败保留已提交证据而非成功净值。若失败发生在创建根之前，向调用方报告失败，不为了写 `failure.json` 覆盖既有目录。失败产物不成为可混排的 NAV run。

## 5. 验收、反例与范围外

**绿C = 新合同对独立手算 oracle 的 conformance；≠ 绿P（委托 parity）；≠ SSOT 绿R/绿S。** S0 只是验收草图，尚无任何运行 PASS / 绿C 声明；expected 不调用 CSV/JR/ModeB/L2 实现生成。完整必测类见[oracle 清单](note-l2-s0-handcalc-oracle-sketches-2026-09-29.md)，待测项仍是切片门禁，不能以文档存在代替通过。

L2 NAV 永不自动可比 CSV/v7/JR/grid Mode B；同合同研究也须后续按 [分钟 SSOT](minute-fill-policy-ssot.md) 的完整身份、实验轴和比较目的另裁，不授予绿R/绿S。

| 不可擦除的否决题 | L2 不能“修复”成同一模型 |
|---|---|
| Q39≠hl | SL95/TP105、O106/H107/L94/C100，资格门过时 Q39 先106止盈、hl 先95止损；合同逻辑反例，非本片跑数 |
| 三个 close | TopK 买侧14:55 close、分钟止损触发域 close、日线 EOD `stop_fill=close`（共享分钟拒绝）不能互换；L2 完成桶 close 另有全名 |
| JR≠CSV | JR 冻结数量/身份/寿命，CSV 按书和资金/仓位反馈生成交易；L2 不倒造 intents、不重新 sizing JR |
| 两个 Mode B | `grid` 卖出网格实例与 `joint_return` 冻结包 M-REF/M-LAG 分属名空间；不建立裸 Mode B 或共享账户 |

范围外：stops、market、replace、GTC/DAY 默认、公司行动、集合竞价成交、多账户、全板块、在线 StrategyPort、lake E2E、vendor runtime、Cerebro、L1 views、L1 adapters 改动及 L2 注册 L1。旧 fees/exdiv/fill-gates/JR/CSV/v7/ModeB、默认与 opt-in、HELP_LOCK/presets/golden 均不改。

Q4 采用[自行实现与来源决定](note-l2-s0-source-license-decision-2026-09-29.md)；不移植 vendor 源码、不复制 LICENSE、不声明许可已清理。产品边界继续见 [P0 note](note-l1-l2-research-engine-boundary-2026-09-28.md)。
