---
date: 2026-09-28
timezone: Asia/Shanghai
base_sha: 8a6d6c3
base_sha_full: 8a6d6c3cf29006621093561df6bad4a8246b1fd7
analyst: Codex gpt-6-astra (analysis-only)
repository: baiyibing/MyQuant-backtrader
worktree: /workspace/wt-industry-gap-audit
note: "#230 docs P3 archive open（交接状态；未联网核验 PR 状态）— not a gap；defaults not flipped"
---

# 行业实践剩余差距审计

本报告只做分析。核对基线代码、仓内文档及外置 P3 记录，没有运行湖回测、单元测试或改动工作树。**主要剩余风险是默认研究路径的价格域/现金时序、数据版本与缓存、申报数量规则、历史可得性和研究可复现性；不是重做 hl、fen、TopK P1–P4 或 #135。**

证据优先级：当前源码确认“路径是否存在”，后续专项冻结说明和宿主归档确认“已完成什么”，旧 plan/review 只证明当时状态。报告中的行业对照以落盘 survey、engine 合同及审查为依据；它们不是全市场规则认证。没有落盘支持的行业推广或实际影响，明确写为 **未证实 / needs Human**。S=可能使研究账户/结论失去可比性；M=特定输入或路径改变成交；L=主要影响审计和复现。这是分析排序，不是实测损失分级。

三种状态严格分开：**已实现、默认 OFF（opt-in shipped）**；**目标能力完全缺失（missing entirely，限定所查入口）**；**仅文档/契约决策关闭（docs-only decision，行为未变）**。默认关闭本身不等于漏实现，明确延期的既有决策不进入待编码清单。

以下相对路径均以 `/workspace/wt-industry-gap-audit/` 为根；方括号证据编号链接到本机文件，后随章节/函数锚点。

## 1. 已关闭 / 已落地

### 1.1 核心三线与其他已实现能力

| 项目 | 当前状态与默认 | 已解决的范围；仍须保留的边界 | 证据 |
|---|---|---|---|
| #214 P1 / #228 分钟止损 | **已实现，hl opt-in，默认 close** | S1、S2 的 low 止损/high 固定目标、gap open、同 bar 止损优先、跌停封死顺延。不是 tick 路径；v7、version12 和 X-03 组合不接 hl | [D1] §1/4；[D3] 实现冻结；源码 `csv_minute_backtest.py` 的 parser/validate 与 scan |
| #214 P2 / #229 除权参考价 | **已实现，`--exdiv-ref-fen` 默认 OFF** | 成功映射参考价先 HALF_UP 到分；已登记 ex-date 的噪声门改为零。无 ex-date 的因子跳变兜底门槛仍在；不改持仓 k 精度 | [D4] R1/R2；`exdiv_map.py::mapped_prev_close/load_exdiv_ratios` |
| #214 P3 真湖归档 | **研究已完成；#230 仅 docs archive** | stamp `20260927e` 六格 PASS：s8 四格、s12 两格；s12 hl 两格是 SKIP，不是失败或待补实现。不能据此翻默认 | [D5] §1–5 |
| E-R6 主路径 | **已落地** | 对满足落日/行情条件的存量参考价与昨收映射；不等于股份/红利总回报账 | [D6] §0–1；[D7] §2.1 |
| TopK P1–P4 | **已实现，默认 close / walkdown OFF / qlib** | `open/intraday/vwap`、`--limit-walkdown`、`--topk-limit-rule real` 均 opt-in。P2 的 vwap 是固定时钟等金额 TWAP-style，不是真正按量 VWAP；vwap×walkdown 显式拒绝 | [D10] §2–5；[D11]–[D14] |
| TopK 三格/六格/real↔qlib | **已归档的研究，不重开** | stamps a/b/c/d；2026 窗、minute-none、nostop。2025 锚完整矩阵/完整 hash 对照不在已完成声明内 | [D15]–[D17] |
| X-07 ST 档位 | **真实 named-limit 路径已修正** | 板块+日期规则已进 `market_layer.limit_pct(..., as_of=...)`；并非所有 ST 仍统一 5%。只有 TopK 切真实规则须显式 real，不能把 X-07 整体误写为默认 OFF | [D14] 档位表、调用接线；当前 `market_layer.py` |
| #135 classic P1/P4 | **docs-only decision closed，A/A** | 14:57–15:00 仍按 as-built；成交资格与日线 close/NAV mark 分离。没有真实收盘集合竞价模型，不因此重开 | [D8] §4；[D9] §5；[D7] P1/P4 专节 |
| #135 classic P2 | **B 已实现** | 书 trades 两列 `session_phase` / `price_rule`；未知/不适用可空，v7 schema 不自动扩展 | [D7] “P2 trades 标签列”；[D8] §4 |
| δ1 费用、δ2 参考价契约 | **docs/tests decision closed** | 代理佣金及参考缩放边界有契约；不等于真实税费账或全量 PIT 因子模型 | [D18] §2/人裁；[D19] §2/5；[D7] §1.1/2.1 |
| δ3 名称 PIT | **原决策仅契约；后续已有 opt-in** | v7 **`--asof-pool-names` 默认 OFF**，开时用 by-day 名称；默认仍 flat。名称按日不证明源在决策时刻可得 | [D20] §0–2；[D23] raw/crosscheck-grok §4 D07；当前 v7 parser L939、main L1002–1020 |
| δ4 `limits=None` | **C/B/A 生产拒绝已实现** | v7 held stop/add/timer 在交易点拒绝缺档位；不是整日冻住 mark，也不是“合法无涨跌幅” | [D21] §2/5；[D7] §2.3 |
| δ5 容量核 | **API 已实现，默认 OFF** | `participation_rate=None`；共享桶、部分成交、可得时刻与量单位合同已实现。**共享 CLI/run 无通用 rate 接线**；特定策略保留量列≠通用 cap CLI 已上线 | [D22] §2/5/6；当前 minute `simulate` L664–665、`run` 签名 |
| δ6 公司行动权益 | **API 已实现，默认 OFF** | `exdiv_economics=None`；显式事件、增股、应收/到账、NAV、锁股已接。**无通用 CLI/湖事件 loader**；不从 k 猜现金或送股 | [D24] §5/8.4；[D7] §2.5 |
| X-01/X-02/X-03 | **均已实现，默认 OFF** | `--fix-s12-price-domain`、`--fix-minute-cash-order`、`--fix-s11-exit-domain`；目标分别是 s12 单位、分钟时序、s11 退出信号域，不能互相替代 | [D25]–[D27]；见 §2 G1 的验收更新 |
| 策略8独立持仓、追买预算、尾盘切片 | **前两项已落地；尾盘 opt-in 默认 OFF** | #212 已修审查旧 X-04“8.3 追买预算”。`--tail-window-buy` 的新 X-04 是另一项，须 X-02；不应把旧预算问题再列未修 | [D28]；[D29] 开头、开关与时钟 |
| joint-return 时钟 pack | **B–G 收官，Mode B 阻塞已解除** | 冻结意图、时钟与 seal 链的完成不能推导跨 hash 重生成成交不变；剩余事项见 G5 | [D30] 状态、§6b |

基本 T+1、跌停保护、Decimal 限价、零量/停牌估值、未知板块拒绝和固定热路径围栏已有实现与契约，不列为缺失。适用例外按具体书/研究臂记载，例如 TopK 日线 `--stop-fill close` 的 Q7 特例，不能用一句“全核完全统一”覆盖。[D7] §2；[D31] §8 Q7。

### 1.2 P3 与既有真湖证据的正确读法

[D5] 固定 **cash `5e8`、窗口 `20251023–20260909`、tip `8a6d6c3`**。s8 同一 trigger 下 fen ON 相对 OFF 的 NAV 均少 **7,702.29**；hl 两格的跌停顺延各 **1**。s12 两个 close 格在本窗 NAV 相同；它不走此 E-R6 fen 路径，不能解释成所有除权问题解决。首次 `21e6` 配方失败后才有人裁 re-GO，不能把 PASS 写回原资金配方。以上是外置归档原文，不是本次重跑或原始 RECEIPT 审计。

另一个状态纠正：[D25]/[D27] 仍写“真实数据未验证”，但后续 [D32] “附：本次实验链的最终状态”已记录 **X-01、X-03 真数据 PASS**。P3 又使用 s12 fix-on 和既有 transform。故本报告不写“X-01/X-03 没跑过真湖”；完整配置、逐事件差异和所有组合的验收程度仍需原回执确认，不将简要 PASS 外推成完整 PIT、Slice D 或 X-02×X-03 交互 PASS。

### 1.3 防止历史状态倒退

- [D1]/[D3]/[D4] 的“在 PR / P3 未做”以基线和 [D5] 为准；#230 未入 master 不构成工程缺口。
- [D7] 中“分钟无费率 kwargs”已与当前 `run/simulate` 参数不符；当前有 `buy_cost_rate/sell_cost_rate/min_cost`。旧 ST=5%、v7 无 by-day 接口也不能作为现状全称断言。
- `plan-industry-align-p3-d345-econ-index-2026-09-19.md` 的 δ5 design-only、δ6 尚未生产被各自 v0.4 与 [D7] §2.4/2.5 覆盖。
- [D23] 是 `057761a` 时点的审查。X-04、X-07、X-09 等已发生后续变化，不能整表复制成当前待办。

## 2. 仍开着的未决

下面是剩余**应用/验收差距、尚未关闭的问题或待裁合同**。提出“下一刀”只是供 Human 审阅，不授权本次实现。

### G1｜正确价格域与现金时序已有开关，但默认结果和交互证据仍需管住（S）

- **现象**：s12 OFF+none 仍混用 front 信号/估值与 raw 成交；共享分钟/v7 OFF 仍可能先使用未来卖款；s11 OFF 的退出 SMA 仍可能受 raw 除权跳变影响。三项不能靠 hl/fen 修复，也不宜拿默认产物直接统一排名。
- **行业惯例对照**：[D2] §1 方案 C 要求连续信号与真实执行价域可转换；[D26] “开关与时钟”要求按实际阶段使用现金；[D27] 的退出合同要求 INITIAL/HOLD 一致信号域。这里的准确含义是价格单位一致与因果账户，不是“所有平台必须同一种撮合”。
- **本仓现状**：**default OFF but code exists**。X-01/X-03 已有后续真湖 PASS 摘要；X-02 已有合成证据，所读资料未找到其完整真湖验收归档，标 **未证实 / needs Human**；X-02×X-03 文档仍列后续交互。TopK 非 close 或 walkdown ON 自动进入时序路径，real 单开+close/OFF 不自动切现金时序。s12 拒绝 X-02，不能一律叠开。
- **证据路径**：[D25] “开关与账户含义/保留限制”；[D26] “真实数据未验证/保留限制”；[D27] “真实数据未验证/最后两段”；[D32] 附表；`csv_minute_backtest.py:820–842` 分支、L1230 起 run 默认。
- **建议下一刀**：只整理现有研究配方与验收覆盖表：列明价格域、现金时序、economics、真实档位、缓存、输入 hash 和已验组合；先补 X-01/X-03 原回执索引，再圈定 X-02 紧现金 A/B 与 X-02×X-03 的未验组合。不得重跑已归档 P3 冒充填补此项。
- **是否依赖人裁 GO**：**资料核对否；新真湖实验/正式配方采纳是**，须确定窗口、资金、输入及适用策略；默认翻转单独裁。

### G2｜旧分钟缓存没有来源/版本身份守卫（M）

- **现象**：同起止窗口换湖、修数或切快照后，旧缓存可能继续供行情；正常命中并不证明研究输入身份相同。是否已污染历史回测 **未证实 / needs Human**。
- **行业惯例对照**：[D25] “证据与失败条件”要求输入内容哈希绑定，[D32] 教训1/4/5要求可追溯配置和证据；[D7] §1 已明确 cache 无新鲜度守卫。此处是仓内研究复现标准，不把某个外部平台实现当强制标准。
- **本仓现状**：**目标守卫 missing entirely（旧共享窗口缓存路径）**；`minute_cache_path` 只编码 none/start/end，命中直接读。已有 `--no-cache`、rebuild，以及 X-01/volume-required 分支绕过，不是完全没有规避手段。v7 小名单 CLI 不使用这条共享缓存。
- **证据路径**：[D23] §1 X-12；`ashare_bars.py:442`、L600 起 `load_minute_bars`；[D25] “开关与账户含义”。
- **建议下一刀**：先提交独立身份合同供审：resolver 源身份、源内容/快照、价格域、schema 与窗口作为缓存认证；缺认证视为不可复用。先用相同日期、不同源的小样本证明失效规则，不读全湖。
- **是否依赖人裁 GO**：**是（实现）**，会改变缓存命中、耗时与旧产物来源；纯证据清单无需新 GO。

### G3｜申报数量仍是统一整百近似，未按板块/订单类别建模（M）

- **现象**：普通买入与 override 都向下整百，可生成科创板 100 股买单；部分卖出允许整数余股，不能直接当成合法独立申报。必须区分“合法订单的部分成交”与“把残量重新作为新订单”。
- **行业惯例对照**：[D23] §1 X-10/§4.6 记录科创板最低量、递增及零股限制。外部只作辅助核对：[上交所2026交易规则 §6.7](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)规定科创板单笔申报最低200股及不足200股余量卖出要求；全板块、订单类型和历史生效日规则表仍 **needs Human**，本报告不补造。
- **本仓现状**：**板块申报数量合同/开关 missing entirely（共享账本所查路径）**；并非没有整手或容量核。`_shares_for_buy` / `execute_buy` 固定100，`_sell` 与 cap 支持整数裁量。
- **证据路径**：`csv_ledger.py:441–449`、L514、`_sell`；[D22] §2.4；[D23] X-10。
- **建议下一刀**：先冻结“申报 vs fill vs 残量”表，选择科创板普通买入这一条入口讨论 opt-in 数量校验，提供不足200/恰200/非整百合法量/余量卖出反例。不能只把常数100换成200。
- **是否依赖人裁 GO**：**是**，改变资金占用、分片及部分成交；不新建策略版本，不重写 δ5。

### G4｜front 输入的历史可得性、出口信号的锚点不变性未完整证明（M）

- **现象**：X-01 的转换证据只覆盖所声明 s12 分钟上下文；X-03 只改退出域。s12 日线、s11 exporter/CYQK 与上游历史修数不因此获得完整 PIT 证明。
- **行业惯例对照**：[D2] §1 的域分离与 [D25] “证据与失败条件/schema v1”区分 PIT、事后重建、共同锚点；[D27] 最后两段明确不把退出夹具外推至 exporter。[D23] X-08 是调查线索，不足以断言“任何 front 均线必定导致经济前视”。
- **本仓现状**：**部分已实现，完整证明未证实**。共同正乘法/仿射变换可保持比较或经逆变换抵消；X-01 `common_affine_certificate_full_pit_unverified` 不是全数据历史版本认证。所查 exporter 没有被 X-03 改造；其完整 PIT 身份合同是否可由上游提供 **needs Human**。不重开 δ2 已冻结的因子恢复/缺失政策。
- **证据路径**：[D25] 证据与失败条件、两种 provenance；[D27] 最后两段；[D23] X-08、D35；`scripts/data/export_strategy11_pool.py` 的 front 输入与 prefix 合同。
- **建议下一刀**：只对一个 exporter 输入快照建立两锚点/截断日的信号前缀对照，把共同仿射、舍入边界、非共同修数、固定网格效应分开归因；先证明是否有信号差异，再决定修代码。
- **是否依赖人裁 GO**：**是（需要外部冻结快照或宿主实验）**；数据来源与历史版本不能由本仓自行认证/下载。

### G5｜joint-return 同分钟分配受 hash 身份影响（M；相对已知延期清单的意外）

- **现象**：[D30] §6b 记录语义及序列等价的 intents 在重新生成 hash 后发生 fills 漂移；归因于同分钟 `intent_id` 排序与共享余额/容量，非旧包在新引擎上的回归。本报告不把该记录升级为所有窗口都不稳健。
- **行业惯例对照**：[D32] 教训1/3/4要求区分输入身份与行为原因；[D30] 明确建议讨论语义化 tie-break。**“行业必须使用何种公平排序”没有落盘权威依据，未证实 / needs Human**；问题是研究经济分配是否应随非经济血统字段变化。
- **本仓现状**：当前排序合同已实现；**与 hash 血统无关的经济优先级/可选政策 missing entirely（所查回放分配路径）**。不是无排序，不是随机排序，不是 Mode B 未完成。
- **证据路径**：[D30] §6b（页首误指§7，实际在§6b）；`joint_return_replay.py:1141/1160` 的 SELL-first、intent_id 排序；与输入 `sort_intents` 不是同一层。
- **建议下一刀**：MQ/BT 联合写一个窄合同提案：仅变非经济 provenance 时是否应保持成交序列；先用两个同分钟争资意图描述现规则和稳定语义键候选，保留旧 pack/seal，不改回放核。
- **是否依赖人裁 GO**：**是**，这是既有 #187 经济排序契约的新裁决，涉及两仓；不得借 TopK P1–P4 重开它。

### G6｜v7 DataFrame API 在未给日历时可能只跑名单日（M）

- **现象**：frame-map 分支把 `minutes` 置空；无 `index_days` 时 calendar 用 `set(minutes)|set(pools)`，非名单的有行情持仓日可能不被处理，影响止损、timer、估值或应收到账。
- **行业惯例对照**：[D23] §1 X-11、§3.4 指明该接口问题；[D7] 停牌/持仓会话合同要求区分没有行情与没有循环。没有外部统一 API 规范，影响推论限于当前代码的日历构造。
- **本仓现状**：**该输入组合的完整行情日历/显式拒绝 missing entirely**；标准 CLI 已传 `index_days`，不受此项影响。
- **证据路径**：`csv_minute_backtest_v7.py:632–653`，`simulate_v7`；[D23] X-11。
- **建议下一刀**：给出 frame 与 records 同输入的最小等价合同，二选一裁“必须显式日历，否则拒绝”或“从有效 frame 日期构造”；只处理 API 边界，不改变 CLI/策略7。
- **是否依赖人裁 GO**：**是（接口行为变更）**；不会因是公开 API 就自动扩成所有入口重构。

### G7｜浮点等号边界仍可改变规则分档/退出（M）

- **现象**：8.1 用 `peak/cost-1` 后严格分档，数学边界可能被浮点推入下一档；X-03 文档另记录共同缩放下严格 `< SMA` 的等号翻转。fen 的 Decimal 只用于参考价，不能修这两类信号比较。
- **行业惯例对照**：[D23] X-05/§3.6 建议规则边界明定精度；[D27] 末段说明严格比较既有误差。不存在已引用的“全行业统一 epsilon”；具体容差 **needs Human**。
- **本仓现状**：**目标数值边界政策 missing entirely**；8.1 现有规则代码仍是 float 比较，X-03 明示未改 SMA/比较符号。湖内发生频率及收益影响 **未证实**。
- **证据路径**：`strategy8_1_rules.py::band_floor/take_profit_reason`；[D23] X-05；[D27] 最后两段。
- **建议下一刀**：先只裁 8.1 一个数学档位边界的表达方式与边界两侧例子，保持当前书；SMA 等号另列，不趁机全库加 epsilon。
- **是否依赖人裁 GO**：**是**，历史冻结规则在边界会产生不同成交；不自动批准新8.x版本。

### G8｜策略12止损后的台阶锚生命周期仍待裁（M）

- **现象**：`step_add_due` 依赖 `lot_id==0`，其消失时返回 False；减仓留底与止损卖尽是不同路径。止损后是否应恢复台阶资格仍不能由“X-01 PASS”回答。
- **行业惯例对照**：[D23] X-06、D16/D29、§4.5 要求先裁策略意图。**没有通用行业规则要求必须保锚**；这是业务合同欠明，不是已证交易所违规。
- **本仓现状**：当前机制存在；**止损后的业务选择/恢复合同待裁**，不是新价格域功能缺失。[D25] “保留限制”明确未修。
- **证据路径**：`strategy12_rules.py::step_add_due`；`strategy12_engine.py::fill_exit`；[D23] X-06；[D25] 末节。
- **建议下一刀**：只整理 lot0 全卖、部分卖、买回后三种路径，Human 选择“台阶终止并声明”或“保留独立锚”；不触碰 latch=A/residual=2。
- **是否依赖人裁 GO**：**是**，属于策略规则选择，没有行业答案可以代裁。

### G9｜状态与证据索引滞后，存在把已完成项重新开刀的风险（L）

- **现象**：旧总表还写 δ5/δ6 未实现、ST 统一5%、X-01/X-03 未真湖验证；TopK 的 `skip_no_bar=0` 又不代表湖末覆盖完整。误读会直接改变下一轮实验与归因。
- **行业惯例对照**：[D32] 教训1/2/4/11/13给出了可审计研究交接纪律；[D17] §3 明确指标相同不等于完整产物 hash 相同。
- **本仓现状**：**文档同步/证据完整度不足**，不是生产功能 missing entirely。已有 manifest、审计 sidecar、归档不可说全无；X-01/X-03 PASS 摘要不能代替本次未读到的原始宿主产物。
- **证据路径**：本报告§1.2/1.3；[D10] §3.4/5；[D17] §2/3；[D32] 附表。
- **建议下一刀**：一份只读索引把当前默认、opt-in、最新验收、未验范围和已裁延期串起来；TopK 2025/hash follow-up 保持研究补证身份，不把已归档三/六格当失败重跑。
- **是否依赖人裁 GO**：**资料核对否**；发布 docs、调用宿主或新实验另按授权。本报告不修改仓内文档。

### 相对已知延期清单的意外

1. **joint-return hash tie-break（G5）** 是落盘已发现的跨包经济分配问题，与 #135 P1/P4 和 #214 R3/R4 无关。
2. **旧缓存身份（G2）、数量规则（G3）、v7 API 日历（G6）、精度边界（G7）** 在旧分钟审查有明确线索，当前只读代码仍支持对应机制；它们不是“hl/fen 默认未开”的同义词。
3. **反向意外：v7 as-of 已有开关，X-01/X-03 已有真湖 PASS**；容量/权益也不是 design-only。这些应减少待办，而非增加。
4. X-08 不能直接推成“全部前复权天然有前视”；共同变换可抵消，必须先分清信号、不变量、固定网格和数据修订。

## 3. 明确不做 / 范围外

下表记录真实限制，但遵守已有决策，不放进本次新的实现待办。**决策关闭不等于真实交易所模型已完备。**

| 面 | 当前差距/状态 | 不重开的理由与证据 |
|---|---|---|
| #214 R3 配股价 | 精确 allotment 项未实现；因子比不是完整交易所公式 | [D1] §2 R3/§3、[D4]；“极罕见”只转述旧计划，本次未核频率。出现真实事件后须另裁数据和公式 |
| #214 R4 exdiv=None / version12-front | E-R6 不适用这些路径；fen 不补权益、不给 s12 重写除权语义 | [D1] R4、[D4]、[D25]；禁止静默双调。s12 fix-on 自有转换不等于 R4 已通用实现 |
| #135 P1 14:57、P2 标签、P4 touch/mark | A closed、B shipped、A closed；真实收盘集合竞价未建模 | [D8] §4/[D9] §5。无新增时间戳/影响证据足以重裁；本轮不联动禁15:00 mark |
| 默认翻转 | hl/fen、TopK exec/walkdown/real，以及 X-* 均保持现状 | [D5] §4、[D17] §3。正确性与收益优化不是同一个判据；现有记录没有默认翻转 GO，未来仍需人裁 |
| δ1 真实费用账 | 双边10bp代理、可覆写费率/floor存在；未建完整历史印花/过户账 | [D18]、[D7] §1.1 已裁 A/A/A。不重做经典费用刀，不引 live fee policy，不将代理成本和真实税再叠一次 |
| δ3 默认 flat 名称 | 默认仍可能读窗口末名称；as-of opt-in 已存在 | [D20]、[D23] raw/crosscheck D07；不把默认翻转包装成缺代码。完整外部名称 PIT 仍需来源证明 |
| δ5 剩余接线/容量模型 | API cap已落地；通用 CLI/日线 cap、真实量来源认证、排队/冲击未完整提供 | [D22] §5/6 的独立延后；不再列“实现 volume cap”。09:30 未完成桶拒绝是 volume=A 契约，不用未来量补开仓；TopK vwap 的前桶口径另属其冻结模型 |
| δ6/δ2 公司行动生命周期 | API economics存在；默认不派权益；无行情日事件可能漏记、无通用补发/恢复、税务/登记日/修订/跨运行恢复不完整；因子恢复错域/旧helper非幂等也已声明 | [D24] §3/5/边界；[D7] §2.1/2.5；[D26] 保留限制；当前 minute L856–868 先过滤 bar 再 apply。**这些是真实边界，但属于已明示延期面**，不借 P2/P3 再开 δ2/δ6；未来独立 GO 才能改变 |
| v4 SMA/raw、微额事件兜底 | E-R6/P2 未修整条信号历史；fen ON 只取消登记事件噪声门，无 ex-date 兜底仍有门槛 | [D6] §1.3、[D4] R2。历史 PX-5 等边界不重开；不能说 fen=全公司行动识别 |
| 无涨跌幅日、最低价位极端边界 | **缺少完整特殊 regime 合同**；`limits=None` 是未知/不可用，不是合法无限制 | [D1] §3 明示不做；[D2] §3.1；[D7] §2.3；[D25] 保留限制。survey 对上市/复牌的概括不能直接用作所有板块法条；若重开先核板块/日期规则与名单暴露，再单裁 |
| TopK 残余研究 | vwap是TWAP-style；vwap×walkdown拒绝；2025锚/hash follow-up、Q8仍有边界 | [D12]、[D14]/[D17]、[D31] §8 Q8。未定义的部分成交移交不得实现；Q8是实验业务闸选择，不是普遍行业缺陷；不重新实施 P1–P4 |
| OHLC内部路径、旧报价 fallback | hl止损优先、同close现金先卖后买、fallback报价时钟已有明确近似 | [D3]、[D26] B04/B11/保留限制。分钟 bar 无法证明 tick 内先后；不扩成订单簿、概率排队或真实竞价模拟 |
| version11 Slice D | 静态档案对照仍未完成；不声称策略收益有效 | [D27] 最后节、[D23] D41。X-03 PASS不是D完成；既有人裁跳过，仍归专门研究验收，不复活Cerebro |
| 云、OMS、live、LEBS | 不在本仓职责；本仓是向量化研究 | [D33] §1–5。LEBS/MockQMT在1.3且不等同；不以本仓NAV替柜台验收 |
| Cerebro / qlib PortAna / Exchange | 已停用或退场，禁止混栈复活 | [D33] §2；读取 qlib bin/冻结 intents 与恢复 PortAna 是两件事。Mode B float shares÷k 也不能移植到书账本冒充权益 |
| 数据采集/供应商 merge | 本仓只消费已配置湖 | `AGENTS.md` Data disks/Scope；缺根/文件即失败，不猜盘、不生成替代市场数据 |

其他旧审查的 X-20 预热、X-27 记忆归零 latch、X-26 缺 bar 计数、X-35 标签覆盖、X-36 qlib 字段 fallback，以及性能项，仍是各自范围的审查线索。本次没有完成其当前全部调用路径核验，**未证实 / needs Human**，不据旧表宣布新生产缺陷或创建第9条实施候选。§1 已关闭的 P2 不因标签留空再重开。[D23] §1次要项；[D27] 保留限制。

## 4. 建议优先级排序

以下最多8条，均是窄范围候选，不是本次执行授权；顺序兼顾影响与证据准备度。

1. **现有正确性开关的正式研究配方与未验组合（G1）** · S · 既有回执/冻结输入，新增宿主实验需GO · 先避免把默认混域或逆时现金账用于横向排名。
2. **旧缓存来源/快照身份合同（G2）** · M · resolver与输入hash，实施需GO · 否则后续任何A/B都可能消费不同身份的旧行情。
3. **科创板申报量与部分成交分层合同（G3）** · M · 板块/日期/订单类型表，需GO · 当前100股路径是明确、可窄化的现实规则差异。
4. **s11出口/front历史不变性取证（G4）** · M · 两锚点快照/上游证明，宿主取证需GO · 退出域已修不代表入场信号PIT已证。
5. **joint-return语义tie-break决策稿（G5）** · M · MQ/BT共同人裁 · 已有跨hash成交漂移记录，先定经济优先级再动回放核。
6. **v7 frame API无日历时的显式合同（G6）** · M · 小型frame/records对照，行为变更需GO · 无湖即可界定，且不影响标准CLI。
7. **8.1数学档位等号边界（G7）** · M · 冻结规则意图/边界样例，需GO · 先修可证明的单一边界，不全库撒容差。
8. **状态/验收证据索引（G9）** · L · 只读资料核对不需新GO · 立刻消除“已实现却重开”的错误，G8另等业务裁决不抢成交核优先级。

## 5. 与三线的交叉依赖

| 交叉面 | 已有关系 | 为什么不要同时开刀 |
|---|---|---|
| TopK exec × 止损除权 #214 | TopK执行改变买时钟/是否替补；hl改变卖候选；fen改变限价参考。open/intraday/vwap或walkdown还切入时序现金路径 | 一起改会同时改变成交集合、现金可用和候补链，NAV差异难归因。先锁价格域/现金/输入，再只改一个轴；当前 TopK归档为nostop，不能冒充hl交互证据 |
| #214 × #135 δ2/δ6 | E-R6是参考缩放，fen只是参考价精度和登记事件噪声门；δ6是股份/现金权益 | 参考价对了不等于总回报对了。把增股/现金、恢复日补发和fen混做容易双算；保持R3/R4及δ边界独立 |
| TopK real × #135 ST/limits | real只选择板块/日期限价规则；名称时点、无涨跌幅regime是不同维度；None仍fail-closed | real已实现并不认证PIT名称或特殊regime。默认qlib不得因X-07已修而暗翻；不要重做δ4 |
| 三线 × #135 P1/P2/P4 | 所有改动仍受既有时钟标签、输出兼容和mark独立性约束 | 标签不能用作新成交过滤；触价窗口不能顺带裁掉日线close估值。P1/P4决策关闭不是待修bug |
| 容量/数量 × 现金时序 | cap部分成交、整手、fee floor、先卖后买共同决定后续资金；TopK分片与尾盘分片合同不同 | G3先定义订单和fill层次，再评估组合；不能同时改rate、数量步长、调度与费用，否则连基线也变了 |
| joint-return × 三线 | joint-return有独立冻结intents、seal、时钟与排序；本仓书的开关不自动适用 | G5必须独立MQ/BT合同；不能通过复制TopK调度或改其P1–P4解决，也不以各核NAV一致为验收 |

推荐依赖顺序是：**先核证据/快照和当前配方 → 界定单一未决合同 → 经Human GO做独立验证 → 最后才讨论默认或跨路径推广**。本报告完成前两步的分析，不启动任何新实现或实验。

### 证据索引与核验范围

下面列出实际读取的主要落盘证据；源码行号为本基线，旧文档内旧行号只作历史定位。

| 编号 | 文件（章节锚点在正文列明） |
|---|---|
| D1 | [plan-minute-stop-and-exdiv-fix-2026-09-26.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-minute-stop-and-exdiv-fix-2026-09-26.md) |
| D2 | [note-minute-bar-industry-practices-2026-09-26.md](/workspace/wt-industry-gap-audit/docs/backtest/note-minute-bar-industry-practices-2026-09-26.md) |
| D3 | [minute-stop-trigger-hl-p1-2026-09-27.md](/workspace/wt-industry-gap-audit/docs/backtest/minute-stop-trigger-hl-p1-2026-09-27.md) |
| D4 | [exdiv-ref-fen-p2-2026-09-27.md](/workspace/wt-industry-gap-audit/docs/backtest/exdiv-ref-fen-p2-2026-09-27.md) |
| D5 | [外置P3真湖归档](/workspace/industry-gap-audit-inputs/stop-exdiv-p3-ab-2026-09-27.md)（不在master） |
| D6 | [plan-exdiv-refprice-2026-09-16.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-exdiv-refprice-2026-09-16.md) |
| D7 | [engine-ashare-correctness.md](/workspace/wt-industry-gap-audit/docs/backtest/engine-ashare-correctness.md) |
| D8 | [plan-industry-align-next-2026-09-19.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-industry-align-next-2026-09-19.md) |
| D9 | [plan-industry-align-refactor-2026-09-18.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-industry-align-refactor-2026-09-18.md) |
| D10 | [plan-topk-exec-model-2026-09-26.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-topk-exec-model-2026-09-26.md) |
| D11 | [topk-exec-p1-2026-09-27.md](/workspace/wt-industry-gap-audit/docs/backtest/topk-exec-p1-2026-09-27.md) |
| D12 | [topk-exec-p2-2026-09-27.md](/workspace/wt-industry-gap-audit/docs/backtest/topk-exec-p2-2026-09-27.md) |
| D13 | [topk-exec-p3-2026-09-27.md](/workspace/wt-industry-gap-audit/docs/backtest/topk-exec-p3-2026-09-27.md) |
| D14 | [topk-exec-p4-2026-09-27.md](/workspace/wt-industry-gap-audit/docs/backtest/topk-exec-p4-2026-09-27.md) |
| D15 | [topk-exec-3cell-2026-09-27.md](/workspace/wt-industry-gap-audit/docs/backtest/topk-exec-3cell-2026-09-27.md) |
| D16 | [topk-exec-6cell-2026-09-27.md](/workspace/wt-industry-gap-audit/docs/backtest/topk-exec-6cell-2026-09-27.md) |
| D17 | [topk-exec-6cell-real-2026-09-27.md](/workspace/wt-industry-gap-audit/docs/backtest/topk-exec-6cell-real-2026-09-27.md) |
| D18 | [plan-industry-align-p3-fees-2026-09-19.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-industry-align-p3-fees-2026-09-19.md) |
| D19 | [plan-industry-align-p3-d2-exdiv-2026-09-19.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-industry-align-p3-d2-exdiv-2026-09-19.md) |
| D20 | [plan-industry-align-p3-d3-st-pit-2026-09-19.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-industry-align-p3-d3-st-pit-2026-09-19.md) |
| D21 | [plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-industry-align-p3-d4-v7-limits-none-2026-09-19.md) |
| D22 | [plan-industry-align-p3-d5-volume-cap-2026-09-19.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-industry-align-p3-d5-volume-cap-2026-09-19.md) |
| D23 | [分钟审查README](/workspace/wt-industry-gap-audit/docs/reviews/2026-09-25-minute-engine-review/README.md)；[raw/crosscheck-grok.md](/workspace/wt-industry-gap-audit/docs/reviews/2026-09-25-minute-engine-review/raw/crosscheck-grok.md) |
| D24 | [plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md](/workspace/wt-industry-gap-audit/docs/backtest/plan-industry-align-p3-d6-exdiv-economics-2026-09-19.md) |
| D25 | [x01-s12-price-domain.md](/workspace/wt-industry-gap-audit/docs/backtest/x01-s12-price-domain.md) |
| D26 | [x02-minute-cash-order-2026-09-25.md](/workspace/wt-industry-gap-audit/docs/backtest/x02-minute-cash-order-2026-09-25.md) |
| D27 | [x03-s11-exit-domain.md](/workspace/wt-industry-gap-audit/docs/backtest/x03-s11-exit-domain.md) |
| D28 | [s8-independent-positions-2026-09-26.md](/workspace/wt-industry-gap-audit/docs/backtest/s8-independent-positions-2026-09-26.md) |
| D29 | [x04-tail-window-buy-2026-09-26.md](/workspace/wt-industry-gap-audit/docs/backtest/x04-tail-window-buy-2026-09-26.md) |
| D30 | [handoff-joint-return-clock-regen-2026-09-24.md](/workspace/wt-industry-gap-audit/docs/backtest/handoff-joint-return-clock-regen-2026-09-24.md) |
| D31 | [topk-joint-research-tracker-2026-09-22.md](/workspace/wt-industry-gap-audit/docs/backtest/topk-joint-research-tracker-2026-09-22.md) |
| D32 | [note-lessons-2026-09-25-26-experiment-chain.md](/workspace/wt-industry-gap-audit/docs/backtest/note-lessons-2026-09-25-26-experiment-chain.md) |
| D33 | [engine-positioning-ssot.md](/workspace/wt-industry-gap-audit/docs/backtest/engine-positioning-ssot.md) |

否定性核查范围：对 `backtest/` 与 `scripts/research/` 搜索 `participation-rate` / `exdiv-economics`，结合共享分钟 `run/parser/simulate` 与 v7 `parser/main/simulate_v7` 区分 API 和 CLI；读取 `ashare_bars` 的缓存命名/命中分支、`csv_ledger` 买卖数量、`market_layer` 档位函数及 `joint_return_replay` 分配排序。未扫描其他仓实现，未访问宿主湖或原始输出，因此“缺失”限定上述能力与路径，不作全生态不存在声明。

外部补充只核对已有落盘争点：上交所数量规则链接见G3；[Backtrader官方订单撮合说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)支持[D2]的Stop用open/H/L建模类比。后者不证明tick成交概率，也不构成复活Cerebro的理由。

交付边界：仅 `/workspace/INDUSTRY_GAPS_BT_2026-09-28.md`；未改 `.py`、测试、fixtures、CLI、配置或仓内文档；未commit、建branch、push、开PR或merge；未运行湖回测。工作树状态及HEAD在交付时复核。
