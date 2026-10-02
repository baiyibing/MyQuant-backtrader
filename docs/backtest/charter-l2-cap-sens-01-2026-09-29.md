# L2-CAP-SENS-01：参与率 / 容量敏感性 charter

2026-09-29 · Track C 首刀 · **docs-only** · 基线 `ba47154521bbfefc1a3c9b938a9cdd21cd781cca`。
Human C GO：「合入后，不等真跑出矩阵，直接C GO」。冻结依据：
`/workspace/handoffs/c_l2_cap_sens_01_20260929/HUMAN_GO.md`；
规格：`/workspace/handoffs/next_tracks_abcde_order_20260929/ORDER_EVAL.md` **§6**。
本 GO 授权编写 charter 与 SSOT 窄指针；尚无本单元实验、比较结果或最终审签。

## 1. 问题、证据与状态

**Unit ID：`L2-CAP-SENS-01`。** 对同一批冻结的外部 LIMIT commands，在固定 L2 合同下，
仅把 `participation_rate` 从 **0.05** 改为 **0.10**，成交率、残量、费用和资源预留如何变化？
容量仍按 `C = lot_size × floor(participation_rate × volume_shares / lot_size)` 计算，
同 symbol+bucket 双侧共享；不研究策略选股优劣、交易所队列或冲击模型。

| 范围 | 证据等级 / charter 状态 | 当前边界 |
|---|---|---|
| 具名合成单元 | `evidence_level=synthetic`；**proposed**（申请绿 S） | 待 Human「合」、完整身份与证据及外部授权记录；尚未授予绿 S |
| lake / real / 混合真实来源 | **blocked** | 必须另获 B-L2 GO，并取得适用于该单元的来源映射、执行与工件证据；B-native/旧家族 PASS 不替代 B-L2 |

绿 S 的原义是[分钟 SSOT §6](minute-fill-policy-ssot.md)的
**“分列的受控敏感性比较”**，仅限**该单元 / 该冻结来源 / 该轴**。
本申请不进入收益冠军榜，不授予**绿 R：同合同内排名**；绿 P / 绿 C / 成功 summary 均不代替比较授权。
本片不授权运行实验；后续运行须另有执行 GO。B-L2 完成也不自动把本 synthetic charter 升级为真实来源授权。

## 2. 运行前必须锁定的身份

以下是后续外部登记的必填清单，**当前均未填入真实 run/input/source IDs 或 hashes**。
不得把本片基线冒充未来执行 SHA，也不得把示例、文件名、mtime 或调用方声明当来源证明。
这些外部身份字段不是新增 writer schema；已有字段引用原工件，缺项保存在新外部登记中。

| 身份 | 运行前登记 / 固定要求 |
|---|---|
| unit / cells / runs | unit ID 固定；分别登记 p=0.05 / p=0.10 的 cell ID、唯一 run_id、新输出根、原生入口及完整 argv/调用参数；重试用新 ID 并保留失败记录 |
| family / backend / schema | `minute_orders_research` / `minute_orders_research_v1`；`research contract v0 (L2-S0)`；`minute_orders_artifacts_v1`；如走 CLI，pin `minute_orders_run_input_v1` codec |
| code / rule version | 两格相同的完整 code SHA、实际工作树与 dirty 证据、解释器/依赖版本；规则版本由该 SHA + contract_version + `price_model=completed_bucket_close` 联合锁定；unknown/dirty 未锁定实现不可比较 |
| input / contract IDs | 两格各自的 input ID、contract ID、原始 JSON 文件 SHA-256、`input_hash`、`contract_hash`、逐顶层 component hash/ref；按 §4 核对差异 |
| source ID / evidence | 同一 synthetic source ID、不可变快照 ref/hash、构造说明/版本；bars、calendar、instrument facts、commands、marks 与覆盖声明各有来源链；不得只写 synthetic 标签 |
| frozen commands | 同一 LIMIT submit + cancel 批次 ID/hash；固定 symbol/side/qty/limit、command_id/order_id、sequence、available/submitted/effective/expires 时点及原始序列；不从旧 trades 倒造订单 |
| window / clock | 相同 start_at/end_at、`Asia/Shanghai`、交易日历、session/bucket IDs 与 start/end、完成量可得时点；连续竞价桶截止 14:57；不混用 START/END 标签 |
| instrument / price domain | 普通主板、统一 raw；固定 tick/lot_size/reference/每日涨跌停 facts、增量 `volume_shares` 单位；halt/missing 覆盖与公司行动 attestation 固定且可核验；当前合同拒绝非空公司行动 |
| initial state | 完全相同的显式 `initial_cash`、全部 initial lots（ID/symbol/qty/acquire/sellable/reserved_qty）；初始预留为零，遵守整手与显式交易日 T+1；不猜现金或空仓 |
| fees / reservation | 相同 buy/sell rate、min_fee、rounding、累计名义额→累计费公式及差额扣费；BUY limit×残量+增量费上界、SELL 可卖 lots 预留，不足拒单、不缩量 |
| marks / policy | 相同 `marks` 与 `requires_marks`，mark IDs/来源/hash/价域/估值时刻/覆盖范围固定；空 marks 须显式登记；§5 的 NAV 资格单独核验 |
| expiry / ordering | 相同右开 expiry、仅撤残量、终态 no-op；同刻 expiry→cancel→bucket→match→submit→mark，match sell-first；全序键及 sequence 固定 |
| failure policy | 固定 §6 的失败、缺数据、不适用规则；失败保留证据，不自动 retry/recover、不覆盖已有根、不回填默认 |

具体经济合同沿用 [S0](note-l2-s0-minute-orders-contract-2026-09-29.md)、
[S3](note-l2-s3-clock-broker-runner-2026-09-29.md)；工件/哈希采用
[S4](note-l2-s4-artifacts-isolation-2026-09-29.md)，CLI 见 [Track A](note-minute-orders-cli-2026-09-29.md)。

## 3. 固定轴与唯一变化轴

| 轴 | 本单元冻结值 / 规则 |
|---|---|
| **唯一输入变化轴** | **`participation_rate ∈ {0.05, 0.10}`**；使用显式 Decimal 字符串 `"0.05"` / `"0.10"`，来自本次 Human GO，不是引擎默认 |
| 固定轴 | §2 的 code/规则、命令批次、来源/窗口/行情、初态、lot/fee/mark/expiry/ordering/failure policy 全部相同 |
| 可变结果 | 原合同下由参与率差异产生的容量、fills、状态/残量、费用、现金/lots/预留；接受/拒绝可能受此前资源变化影响，须沿 trace 解释 |
| 运行身份 | 两格独立 run_id / 输出根，只作归档身份，不算第二个经济轴 |

不能随较低参与率调整下单数量、限价、取消时刻、样本窗口或费用来“保持成交”。
若两档都全成或无差异，如实报告“未观察到容量影响”；若全未成，登记原因与覆盖局限。
不得事后调订单/样本以追求非零差异或收益，亦不推断参与率与 NAV 单调。

## 4. Hash 政策与显式 allowed-diff 表

`participation_rate` 是现有 **artifact-contract 参数**，同时进入 inputs.data。
因此 0.05 / 0.10 的 **`contract_hash` / `input_hash` 可以且应不同**；强求相同反而掩盖身份变化。
采用 S4 原 canonical encoding / SHA-256，保留 Decimal 字面精度、序列顺序及原始 bytes，
不 scrub 参数、不伪造共享 hash、不重录历史 manifest。差异必须逐字段对应下表，不能只看总 hash。

| 对象 / 字段 | 允许差异 | 必须保持 / 审核依据 |
|---|---|---|
| `inputs.json#/data/participation_rate` | `"0.05"` ↔ `"0.10"` | inputs.data 的唯一允许变化字段；其余字段及序列、字面精度一致 |
| `contract.json#/parameters/participation_rate/value` | 同上 | 其 source ref 不变，contract 其他规则/参数逐字段一致 |
| `inputs.json#/components/participation_rate/sha256`、`input_hash`、`contract_hash` 及引用 | 按原编码重新计算后的变化 | 除 rate 外所有 component hashes 相同；不以总 hash 不同直接判失败或直接放行 |
| run_id、外部 cell ID / 新输出根 | 两格独立身份 | 一一映射相同 unit/source/code；根路径不充当经济参数 |
| orders/fills/ledger/marks/summary 结果 | 仅原合同从 rate 差异推导的结果变化 | mark **输入**固定，mark 持仓/市值观察可随成交变化；每项结果差异须有 trace 依据 |
| manifest/summary 的身份引用、工件文件 hashes | 上述身份/结果导致的派生变化 | 文件 hash 按实际完整 bytes 验证；backend/schema/code/evidence/比较状态固定；commands 文件应相同 |
| 其他输入、规则或来源变化 | **不允许** | 记为本单元不可比；新问题/来源/多轴实验另行命名与裁定 |

此表是人工审查契约，本片不实现 compare/report gate。
`comparison_status=no_ssot_compare_authorization` 保持原值；历史 manifest 表述生成时授权状态，
日后的外部授权也不回写 manifest、summary 或 writer。

## 5. 首要指标与 NAV 边界

所有指标先按 order/symbol/side 列示，再给同口径汇总；仅对完成证据齐全的两格分列比较。

| 主指标 | 冻结定义 / 证据要求 |
|---|---|
| fill ratio | 已提交 fills 的绝对成交股数 / 冻结 submit 总股数；分母包含被拒单，不随 Accepted 集合漂移，cancel 不新增分母；BUY/SELL 分列，总量不轧差；零分母为 N/A |
| expiry / cancel residual | 各订单进入 Expired / Cancelled 时的未成交股数及占同侧冻结 submit 股数比例；每单终态只计一次，终态后的 cancel no-op 不重复计；另外列 Rejected 数量与期末 active 残量 |
| fees | 按订单/side 汇总增量 fee_delta 并核对累计费与账本；零成交取消费为零，partial 不重复收最低费；相同费模型不要求总费用相同 |
| reserves | 逐状态前后 reserved/free cash 与各 symbol/lot reserved/free sellable qty，列峰值、终态释放及期末残留；金额与股数分开，不把预留当已支付成本 |

预留历史须来自同次 run 的完整 wrapper/CLI trace；普通 S3 结果缺历史快照时该项记“未证实”，
不从 fee 反算、不填零，不能宣称本单元全部指标已覆盖。

**本单元默认不声明 NAV，也不声明收益排名。** `marks=[]` 且 `requires_marks=False` 的合法 run
只支持有证据的成交/费用/预留指标；成功 summary 或某个有效 mark 不自动获得 NAV 资格。
若后续申请 mark-based NAV 敏感性，须在运行前另行登记并审签估值公式与统一估值网格：
`equity(t) = cash(t) + Σ held_qty(symbol,t) × raw_mark(symbol,t)`；cash 包含预留现金，
费用已入账不重复扣除；若用归一化 NAV，须显式定义 `NAV(t)=equity(t)/equity(t0)` 且初值为正。
初始 lots、两格每个声明的估值时刻（含起止点）全部持仓均须有同价域、同源、可得且合法的 mark，
并对应同刻 mark phase 的账本；两格固定同一完整 mark 输入，不能各补自己的缺口。
缺任何 mark 即拒绝 NAV 资格；不以成本/前值填补，不拼接 cell 曲线，不以期末强平造估值。
这些是另行申请的必要条件，当前没有完整覆盖证据或 NAV 授权。

## 6. 失败、未覆盖与拒绝例

输入/合同/算术错误、engine failed、writer/目录错误、无有效成功 summary 或工件 hashes 不全，
均不进入成功比较。保留原始输入、错误与最后已提交证据，分列 FAIL / NOT_RUN / 未覆盖；
不得删除失败格后只保留赢家，不将 L1 `returned`、exit 0 或非零 fills 单独当完整成功证明。
合法业务 Rejected 是结果，不是 run failed；须纳入指标而不能静默丢掉。
经证明的 missing/halt 或零量遵循原合同不成交、继续至 expiry；缺量/覆盖/单位不明须失败，
缺数据不等于零成交；普通主板/raw 等适用范围不满足时登记“不适用”，不扩大合同来跑通。

| 拒绝例 | 裁定 |
|---|---|
| L2 与 CSV / v7 / JR / grid 比 NAV，或把本单元当全部 L2 的豁免 | **红**；跨入口收益混排，不属于本单元绿 S |
| 同时改 orders 与 rate，或悄改 clock/fee/窗口/初态 | 多轴/身份漂移，拒绝本单元资格 |
| 缺 mark 却声称 NAV 敏感性 | 拒绝 NAV；不得用合法无 mark run 或零持仓假设补资格 |
| 缺 source ID / snapshot hash / 来源链，或把真实 bars 标 synthetic 绕门 | 来源未证实，拒绝转绿；真实/混合来源保持 blocked |
| 混 raw/front 或价域/量单位未声明 | **红**；不能据此解释为参与率效应 |
| lot、费用、mark 政策、expiry、ordering、初始现金/lots 等业务参数不齐 | 未证实，拒绝猜默认及比较 |
| failed / incomplete run 或缺关键预留证据仍声称全指标 PASS | 拒绝对应比较/完整验收；保留失败与未覆盖记录 |
| synthetic PASS 冒充市场可执行性、真实策略收益或绿 R | 拒绝升级；完成桶容量近似只回答本合成问题 |

## 7. 待审签的不可变外部授权记录

**当前状态：awaits Human「合」+ optional signed receipt。批准人/批准时间/适用运行 IDs 均待填，
本文不伪造最终批准，也不把 C GO 当成已完成的实验验收。**
审批后在仓外新增不可变授权记录，原记录保留；更正用新记录及 supersedes 引用，不覆盖历史。

| 外部记录字段 | 当前占位 / 后续必填内容 |
|---|---|
| approval_record_id / ref / hash | 待审批后生成；保存 Human「合」原始证据 ref，可选签名回执及其校验信息 |
| approver / approved_at / decision | 待填真实批准人、带时区时间、明确授权内容；文档接受、执行 GO、比较授权分别记录 |
| applicable IDs | unit/cell/run/input/source/code/contract IDs 与各 hashes、commands 批次、charter 提交 SHA；不得写“所有 L2” |
| evidence / scope / metrics | 固定 synthetic、0.05/0.10、允许差异表、证据 ref/hash、失败/未覆盖记录及获准指标；默认不含 NAV；lake/real 仍 blocked |

没有填齐适用 IDs 与证据的记录不能据此宣布绿 S；如审批早于运行，后续以不可变补充记录绑定实际工件。
本片不改引擎/adapters/writers、旧 manifest/`comparison_status`、SSOT 历史颜色、
`production_C` 或任何默认；不读湖、不运行实验、不实现机器授权读取、不自动合并 PR。
