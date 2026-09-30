# B-L2-01：L2 lake source → RunInput 接入合同

2026-09-29 · **B-L2 首刀 / docs-only** · 基线 `6528ac944c7036fad65743158d9ffc1ad75ceddb`。
Human GO：`/workspace/handoffs/b_l2_source_contract_20260929/HUMAN_GO.md`；
规格：`/workspace/handoffs/next_tracks_abcde_order_20260929/ORDER_EVAL.md`
§5 Track B「B-L2 的后续独立门」**仅第 1–2 项**；第 3–4 项各待后续具名 GO。
本片冻结来源要求与映射边界，未实现 loader、未读湖、未取得宿主 attestation 或运行 PASS。
`production_C=frozen`；PR 待 Human「合」，不得自动合并。

**2026-09-30 状态补记：** 上述为 #266 合同片的历史停点；ORDER_EVAL §5 item 3 已按
`/workspace/handoffs/b_l2_loader_impl_20260930/HUMAN_GO.md` 实现，接口与证据版本见 [§7](#7-item-3-实现接口与证据版本2026-09-30)。
item 4 / 4090 live 仍须另行 GO；未取得 host attestation、L2 lake PASS 或 SSOT 绿 R/S。
4090 首次 probe 已记 `BLOCKED/NOT_RUN`；本次 schema-adapt 与事实 sidecar 登记见
[§8](#8-schema-adapt与事实-sidecar2026-09-30)。**合并后重新运行 4090 仍需另一次 Human GO**。

## 1. 具名单元与当前停点

| 项目 | B-L2-01 合同 / 待证明项 |
|---|---|
| 单元 / 目的 | **B-L2-01**；验证来源映射、L2 自身轨迹和 native↔L1 委托；不做收益排名 |
| 窗口 | 默认提案 **`20251023`–`20251104`（两端日期包含）**；状态 **proposed，待 host attestation**；不是已验真窗口 |
| 宿主 | 后续 4090 GO 指定 `OSKH_SOURCE_PARQUET_ROOT=E:\stock_data`；仅为具名宿主配置，禁止写入 loader 默认或探盘 |
| 品种 / 价域 | 有事实证明的普通主板 `board="main"`、`price_domain="raw"`；湖分区 `dividend_type=none`；不混 front/back、不支持特殊上市日 |
| 订单来源 | 人为设计并预先冻结的小型 BUY/SELL **LIMIT** submit/cancel 集合；标注 **「真实行情驱动的合成订单研究」**，绝不称真实策略信号 |
| 当前证据 | bars、calendar、instrument、公司行动、halt/missing、marks 均 **待宿主核验**；本片无真实 source/run hashes，不填假值 |
| 运行身份 | 后续登记固定 symbol 全集、精确 `start_at/end_at`、命令批次、经济参数、mark 网格、完整 SHA 与新 run 根；未齐不得执行 |

日期提案复用 [B-native-CV-01](note-l1-lake-e2e-b-native-cv01-2026-09-29.md) 的短窗，
只借鉴其 recipe/hash、原字节、逐格状态和失败留证等材料的组织方式；不得将 B-native 的 hash 或原字节复制到 L2 收据。
该单元仅属 CSV/v7；其文档、宿主结果或 PASS **都不是 L2 lake PASS**，不证明此窗适用于 L2。
冻结后若窗口/品种不适用，记录原因并重新登记、裁定；不得按成交或收益挑换输入。

## 2. Resolver 与读取责任

接缝为 **已配置 resolver → 只读源快照与覆盖核验 → 显式 RunInput → 既有 runner**。
字段以 [现有 types](../../backtest/research/minute_orders_backend/types.py) 为准；
经济规则沿用 [S0](note-l2-s0-minute-orders-contract-2026-09-29.md) 与
[S3](note-l2-s3-clock-broker-runner-2026-09-29.md)，不让 loader 承担撮合/账本工作。

| 读取对象 | 显式定位 / 缺失处理 |
|---|---|
| 湖容器 | `common.infra.data_root.resolve_parquet_container()`；记录 SOURCE 或 AUTHORITY_HINT + `.authority` 的解析依据；未配置即失败 |
| 分钟 / 日线 raw | `resolve_period_root("1m"/"1d")` 后取 `dividend_type=none/symbol=<规范分区键>/data.parquet`；符号规范化统一走 [`oskh_data/symbol_format.py`](../../oskh_data/symbol_format.py)：`to_canonical_symbol` 用于 RunInput 的点号格式 `603196.SH`，`to_partition_key` 用于 Hive 目录 `symbol=603196_SH`，禁止临时 `.replace()`；记录实际根、period override、符号规范化版本和选取区间 |
| 公司行动证据 | `resolve_source_parquet("ex_date_index.parquet")`、`resolve_source_parquet("adj_factor.parquet")` 可作覆盖核验材料；必须另证其覆盖范围/完整性，不把文件存在或空筛选当无事件证明 |
| 日历、每日 facts、halt/missing、mark 证据 | 运行前登记已存在的明确源 ref、实际文件/分区及 schema/列映射；按所属树用既有 resolver，或显式受控 sidecar ref；本片不虚构这些源已存在 |
| 若用指数佐证日历 | 仅 `resolve_index_daily_root()`；不能借 stock 日线 override；指数有 K 也不能单独证明个股无停牌/无缺根 |

resolver 只定位，不保证文件存在：loader 必须逐项检查可读性、schema、覆盖及哈希。
不得回落 cwd `stock_data/`、workspace、其他盘符或旧缓存；不下载、不 merge、不修湖。
源根/必要分区/覆盖文件缺失应报带 ref 的失败，不能返回空表或造 missing 桶掩盖。
初版禁用无源指纹的旧缓存；若未来允许派生缓存，须绑定完整 source/transform/input 身份并独立核验。
此处 L2 是 `minute_orders_research_v1`，不是 `l2_analytics/` 或 tick ETL。

## 3. Resolver → 显式 RunInput 映射

下表是**下一实现必须满足的合同**，不是当前已提供的 loader/schema 功能。
每项都须同时有原始 source ref/hash、列/行键/过滤范围与转换记录；缺项拒绝，不静默补默认。

| RunInput 目标 | 源与转换 / 必须验证 |
|---|---|
| `start_at`, `end_at` | 从冻结 recipe 的显式时刻读取；日期提案不能自动补开收盘时间；命名 `Asia/Shanghai`、带偏移且一致，覆盖全部命令、桶和 marks |
| `calendar.trading_dates` | 独立可核验交易日历，有序唯一；含执行日、初始 lots 的 acquire/sellable 校验日及末次可能买入的下一交易日；不得自然日+1、仅按有 bar 日或工作日猜测 |
| `calendar.session_buckets` | 依据已认证日历及预登记的连续区间展开精确一分钟桶；只在 09:30–11:30、13:00–14:57；ID 稳定唯一，同一 session 所选区间内不得漏桶 |
| `buckets[].symbol/bucket_id/start/end` | 固定品种全集 × 全部声明桶逐格覆盖；原始时间按 §3.1 映射，与 session 一致，输出按 `(start,symbol)` 排序；源重复/冲突报错，不去重取最后值 |
| `buckets[].close/volume_shares` | 仅 raw 完成桶 close 与该桶增量股数；按 §3.1 精确转换；OHLC 其他价格不参与候选价，不从 amount/均价反造量 |
| `buckets[].missing/halted` | 按 §3.2 的逐格覆盖证据显式赋值；零量、合法缺根、停牌和坏输入分开；不能仅据无行推定停牌或无交易 |
| `instruments[]` | 按 symbol/trade_date 提供 main/raw、`tick_size/lot_size/reference_price/limit_down/limit_up`；覆盖 submit、bucket、mark 使用日；来源须含生效日、适用范围与可得性 |
| `calendar.company_actions_covered/company_actions` | 仅在 §3.2 证明覆盖且事件确为空后赋 `True/()`；JSON 为 `true/[]`；发现事件或证据不全即拒绝当前单元 |
| `commands[]` | 来自独立冻结的合成 LIMIT 批次，非 lake 派生信号；每条 command_id/order_id/sequence、available_at/submitted_at/effective_at；submit 另含 symbol/side/qty/limit/expires_at/order_type；cancel 显式指向订单，不补 qty/expiry |
| `initial_cash/initial_lots` | 来自具名合成账户 recipe，不冒充真实账户；显式现金、空 tuple 或每 lot 的 lot_id/symbol/qty/acquire_date/sellable_date/lot_size/reserved_qty；初始预留为零 |
| `buy_fees/sell_fees/participation_rate` | recipe 逐项给出有限 Decimal rate/min_fee、rounding 和 p；没有生产费率/10%参与率默认；本片不借 C charter 的两档值填参 |
| `marks/requires_marks` | B-L2-01 完整验收要求显式 `requires_marks=True`；预登记含期末及抽查时点的 mark 网格、来源和覆盖，逐条映射 `mark_id/event_time/available_at/prices/price_domain/source`；见 §3.3 |

### 3.1 时间、可得性与数量

- 宿主须给原 schema、时间单位/时区、**START 或 END 的权威说明及边界抽样**。
  START 标签 t → `[t,t+1min)`；END 标签 t → `[t-1min,t)`；不据首末行外观或旧 CSV 习惯猜。
  明确 epoch/naive 源的解码方法与证据后才转为 Asia/Shanghai；记录原值和转换后起止，不静默本地化。
- close 与 volume 在 bucket.end 才可见；现有 `CompletedBucket` 无独立延迟字段。
  attestation 须证明其符合完成桶可得性语义；已知晚于 end 才可得的源不能回填为 end，须拒绝适配。
  这是历史 bar 模型可得性，不声称实时 feed 到达延迟；文件采集时间不能冒充事件时间。
- 保持 `available_at <= submitted_at <= effective_at`；可撮合还须
  `submitted_at < bucket.start`、`effective_at <= bucket.start`、`bucket.end < expires_at`。
  不把同桶或未来 close/量用于更早命令的可得性；合成设计若参阅样本也须披露，不能声称因果策略信号。
- `[14:56,14:57)` 是最后合法成交桶；14:57–15:00 不得重标 continuous 或移时混入。
  所有排除行/边界行保留范围与计数；不得因排除竞价而删掉独立合法 mark 的来源。
- `volume_shares` 必须是该分钟的非负整数**增量股数**。源若为手，须有单位与换算因子证据并精确转股；
  原值、因子、结果均登记。累计量/单位不明拒绝本首实现，不凭差分、100 倍猜测或四舍五入修复。
- 原生价格/金额使用 Decimal；JSON 按 [v1 codec](note-minute-orders-cli-2026-09-29.md) 用字符串。
  decimal/text 源保留精度；double 源取已 pin 解释器的 `repr(value)` 最短往返十进制文本再转 Decimal，
  记录原类型/值、文本及转换版本；必须已满足分/tick，不以 float 运算或隐式 quantize 修价。
  非有限、负量、非整数股数及价域混用均失败。

### 3.2 日限、公司行动与缺根证据

每日 reference/上下限必须来自具名事实源；若是派生事实，须给输入、已批准规则版本及独立核验，
不能把前收盘 × 固定 10% 当主板事实。缺事实、特殊上市日或不支持品种拒绝；lot_size 不得跨日改变。
按冻结品种与执行/初始持仓所需经济覆盖区间，保存公司行动源的范围、完整性声明和筛选结果。
`ex_date_index/adj_factor` 的 hash 只证明身份；无行、因子未变或源缺失均不单独证明无事件。
真实事件非空时当前 v0 不适用；不编造空事件、不复权、不另加分红/红股处理来救活该单元。

| 源状态 | 映射 / 门禁 |
|---|---|
| 有效有根、无停牌，含真实零量 | `missing=False, halted=False`；close 与整数 volume 均必填；零量不成交 |
| 证据确认停牌且有根 | `halted=True, missing=False`；仍须合法 close/volume，不以停牌掩盖坏值 |
| 有覆盖证明的合法缺根 | `missing=True, close=None, volume_shares=None`；halted 按独立事实填；JSON null；不补 bar、不取前值 |
| 无源文件、无覆盖、未知缺口或坏字段 | 输入失败/运行前 BLOCKED；不能映射为零量、合法 missing 或空表 |

停牌/缺根记录须含 symbol、日期/桶区间、原因、事实 ref/hash、覆盖完整性与出具者。
所有 `False` 也需要覆盖依据；合法 missing/halt 只阻止成交，仍沿原合同保留订单至 cancel/expiry。

### 3.3 Marks 的独立来源

mark 网格在执行前固定；每点预供固定品种全集的 raw、合法 tick 价格，至少覆盖实际全部持仓。
须证明 `available_at=event_time` 且在 run 内；每个价格追到真实源行与转换版本。
15:00 mark 只有独立合法来源与可得性证据才可用，不意味着可增加 15:00 撮合桶。
禁止以 lot cost、前值、合成价格或最后成交价补缺；停牌也不豁免 mark 证据，缺项即失败。
原 API 的 `marks=(), requires_marks=False` 仍合法，但不能交作 B-L2-01 完整 mark 验收；
全程空仓/无有效估值抽查记未覆盖。mark 观察已提交账本，不造 SELL、不强平、不自动形成 NAV 产品。

## 4. 来源身份、转换链与 S4 门

以下为后续 **provenance/外部 receipt 的逻辑必填项**，不在本片扩展 RunInput 或现有 wire schema：

| 记录 | 必须绑定的身份 |
|---|---|
| recipe | unit、window、symbol 全集、全部显式参数/命令批次、mark 网格、新 run_id/parent、入口及精确调用、预登记时间 |
| snapshots | 各原始文件/分区 ref、完整 bytes SHA-256、schema/列/单位、筛选区间与计数；日历/facts/公司行动/halt/missing/marks、合成订单/账户各自独立来源 |
| attestation | 出具者/带时区时间、事实覆盖范围、证明材料 ref/hash、结论与局限；标签 `source_kind=lake_bar` 或 caller 声明不是证明 |
| transform | loader 完整 code SHA、转换版本、symbol/时间/数量/Decimal/筛选/排序规则；每项 source 行键/范围 → RunInput 字段 ref，足以重做核验 |
| input / artifacts | 原始 wire bytes hash（若用 CLI）、S4 `input_hash/contract_hash/component hashes`、工件 refs/hashes；外部来源记录以 input_hash 绑定同一次请求，另有自身 hash，不伪造输入相同 |
| execution | 实际实现 SHA/dirty、解释器/依赖、安全配置摘要、源核验前后 hashes、原始 streams/status、所有失败与未覆盖项；dirty/unknown 不能冒充已锁定实现 |

执行前后核验同一源快照；变动即 FAIL，保留两侧身份，不继续签 parity。
原始 refs/字节与派生 RunInput 分开保存；自证 input_hash 不等于认证真实来源或数据质量。
合成命令/账户与真实 bars 的混合身份必须可见；建议未来版本化 evidence 表达 **real-or-hybrid**，
其中 B-L2-01 为 **hybrid（真实行情 + 设计订单/账户）**；准确枚举/封套留待下一实施 GO 审签。

当前 [S4](note-l2-s4-artifacts-isolation-2026-09-29.md) 与 [A CLI](note-minute-orders-cli-2026-09-29.md)
仍只接受 `evidence_level="synthetic"`，`evidence_level=lake` 仍拒绝。
**禁止把真源贴 synthetic 标签、手改 manifest 或旁路 writer 来伪造 L2 湖证据。**
下一版须显式表达并验证来源链，保留旧 synthetic v1 格式、编码/hash 与失败/隔离语义兼容；
不得往严格 v1 codec 偷塞字段，或把新字段变成旧合成调用的必填项。

## 5. 硬锁与下一刀 allowlist 草图

- `comparison_status=no_ssot_compare_authorization` 原值保持；PASS 不授 SSOT 绿 R/S。
  [L2-CAP-SENS-01](charter-l2-cap-sens-01-2026-09-29.md) 是另一具名单元；不继承其参数或比较权限，
  也不因本片来源合同把其 lake/real blocked 改为通过。
- 禁止旧 trades 倒造 orders、把 stock_pool/JR pack 转成本单元信号；L2↔CSV/v7/JR/grid **无 expected-equality asserts**。
- 不猜 START/END、不填经济默认、不造公司行动/缺根/mark 证明；MatchCore/Ledger/Fees/Clock 及相位原样。
  保持无默认 family；旧 synthetic 格式、HELP_LOCK、旧引擎/工件、δ5 文件均不变；来源参考仍遵守
  [S0 来源决定](note-l2-s0-source-license-decision-2026-09-29.md)，无 vendor 移植或 runtime。

**另一个具名 implementation GO 才能落下列候选改动**；路径只是供下一刀收敛的 allowlist 草图：

| 候选路径 / 交付 | 允许职责 / 冻结边界 |
|---|---|
| `backtest/research/minute_orders_backend/source_loader.py`、`source_provenance.py`（或同职责模块） | 只读 resolver、来源预检、显式转换及 provenance；默认 runner 不加载湖，无策略生成器 |
| 独立 `tests/test_minute_orders_source_*.py`、明确 synthetic 的小 fixtures | 正反例覆盖标签/量单位/覆盖/哈希/缺根/mark/拒绝；不得把 fixture PASS 称真湖 PASS |
| S4 `artifacts.py` evidence schema/validation 与必要 wrapper 传参 | 版本化 real/hybrid 来源表达、绑定及失败留证；旧 synthetic 兼容、独占新根、summary 最后发布、比较状态不变；无经济核修改 |
| 若采用 A，专用 codec/CLI evidence 校验及测试 | 须在该 GO 中单独点名最小接线；保留旧 synthetic CLI/退出语义，无通用 `--lake` 绕门、无默认 family |
| 仓外 implementation receipt | 实际文件 allowlist、版本/测试、兼容性、未证明项及后续 host 入口；代码交付不能签真湖 PASS |

## 6. 后续 4090 live GO 与验收草图

**第 4 项另需具名 `B-L2-01` 4090 execution GO**，并先取得第 3 项实现/证据 schema 与宿主 attestation。
只消费宿主已配置 `E:\stock_data`，源只读；本片不派宿主任务、不执行上述计划。

1. 先封存 recipe、源清单/证明/转换/input hashes；不满足主板/raw、无公司行动覆盖、日历/limits、
   时间/量单位、halt/missing、marks 任一条件，记 BLOCKED/NOT_RUN，不改输入补洞。
2. 同一冻结 RunInput 做 **native API ↔ L1 API**；用完整 S4 wrapper 留逐状态预留证据。
   如采用 A，再做 native CLI ↔ L1 CLI 及 API↔CLI 一致性；pin code/环境，用隔离新根、受控相同逻辑 ID。
   比较全命令/状态/成交/账本/mark/工件集合与 hashes、native status/异常；CLI 比 exit 与原始 streams。
   预登记仅非经济身份差异的允许表，保留每项原字节/diff；不得 scrub 后声称 byte-identical。
3. 独立 spot-check **容量、expiry、T+1、fee、mark**：手算 `L×floor(p×V/L)` 的双侧共享容量；
   核 end=expiry 先到期/残量释放；当日买不可卖及下一显式交易日；累计费差额/最低费不重复；
   同刻 mark 的源价/全部持仓/ledger version。expected 从冻结源行与合同独立计算，不调用被测核或旧引擎生成。
   另核 partial/cancel、初始与终态预留、合法 missing/halt/零量；未实际触发的格记未覆盖，不伪造湖行补测试。
4. 单列来源正确性、委托 parity、独立 oracle 的 PASS/FAIL/NOT_RUN/未覆盖；`returned`、exit 0、
   非零 fills 或 summary 任一单项都不足以总 PASS。保存输入错误/engine/writer 失败原证据，不覆写或自动重试。
5. 新仓外 host receipt 绑定 GO、unit/各 run IDs、实际 SHA、源/输入/转换/工件 hashes、逐格结论及局限。
   **验收 PASS ≠ 市场可执行性/真实策略收益 ≠ SSOT 绿 R/S**；比较授权仍另行具名裁定。

本刀完成条件仅为文档 PR 打开与仓外 `BL2_CODEX_RECEIPT.md` 写入；实现、真湖与比较授权均未发车。

## 7. Item 3 实现接口与证据版本（2026-09-30）

本节为后续 implementation GO 的增量；不追改上文 #266 的历史授权范围。
[source_loader.py](../../backtest/research/minute_orders_backend/source_loader.py) 提供显式只读 API，
[source_provenance.py](../../backtest/research/minute_orders_backend/source_provenance.py) 负责来源绑定与重验。
普通 runner 不读湖；CLI 和严格 `minute_orders_run_input_v1` codec 均保持原样。

```python
from backtest.research.minute_orders_backend.source_loader import load_minute_orders_source
from backtest.research.minute_orders_backend.runner import run_minute_orders_research_with_artifacts

# 三个变量必须由获批且已冻结的调用方提供；此处不提供宿主路径/经济默认。
loaded = load_minute_orders_source(recipe_path, expected_sha256=recipe_sha256)
result = run_minute_orders_research_with_artifacts(
    loaded.run_input, parent, run_id=run_id, evidence_level="hybrid",
    source_provenance=loaded.provenance,
)
```

`recipe_path` 必须绝对路径、原始 bytes SHA-256 必填；parent/run_id 必须与 recipe 一致。
`minute_orders_source_recipe_v1` 全字段必填、拒绝未知字段/重复 JSON keys/JSON 浮点数；
完整、可生成的小型 **synthetic fixture** 见
[SyntheticCase](../../tests/test_minute_orders_source_loader.py)，不是可用于宿主验收的真实 recipe。

| 独立输入 | v1 表达 / 门禁 |
|---|---|
| recipe | `unit=B-L2-01`、`source_kind=lake\|synthetic_fixture`、注册时间、run_id/parent、精确 invocation、symbols、起止、连续 intervals、mark_grid、是否参阅样本的披露；implementation 显式 pin 完整 code SHA / Python version / PyArrow version / transform version |
| sources | 各 id、location、format、完整 schema、SHA-256；minute/daily 使用 raw resolver 分区；loose 仅 ex_date_index/adj_factor；其他事实为显式绝对 sidecar。Parquet 从已验 hash 的 bytes 解码、schema 精确匹配，不用旧缓存 |
| roles | 独立 calendar/instruments/status/actions/commands/account/attestation JSON 源；封套 `schema_version=bl2_<role>_v1` 与 `data`。commands 仅 `designed_limit_batch`；account 仅 `synthetic_account`，所有经济字段显式提供 |
| bars | 显式列映射、START/END、Asia/Shanghai、时间编码、完成桶可得性、raw、incremental shares/lots 与换算因子；支持带偏移文本、已声明的 naive Shanghai、整数 epoch s/ms/us、aware datetime；不猜标签、不差分、不修价 |
| facts/coverage | 每日主板/raw facts 的生效区间、available_at、ordinary_listing、事实或批准推导的证明；status 逐格含 missing/halted/reason/issuer/proofs，两个 False 也需证明；actions 须覆盖经济区间且 events=[] |
| attestation | issuer/issued_at、source_kind、symbols/日期完整覆盖、七类具名 claims、独立 `bl2_proof_v1` 材料 refs/hashes、limitations；`scope_hash=attestation_scope(recipe)` 绑定除 attestation 自身 descriptor 之外的完整 recipe 与源快照，避免循环 hash；变更单位、标签、参数或源须重做证明 |
| marks | 预登记末次与独立抽查点，每点全 symbol 的原始 Parquet 行号/列/时间转换；同一 minute 源必须沿用原 close/时间映射；15:00 可以来自排除于撮合网格之外的合法行，不能增加竞价成交桶；无补价 |

proof 材料的权威性仍由宿主独立审验；代码验证其存在、绑定与覆盖，不能签发 host certification。
湖源须 clean git HEAD，禁止 hybrid 的 caller code_sha override；fixture 允许 dirty 并如实记录。
loader 保存逐行来源与 Decimal/量/时间转换、排除行及计数、resolver 配置依据、实现文件 hashes、
S4 input/contract/各 component hashes；既有 validators 只用于预检，不执行成交事件。

S4 新路径为 `evidence_level=hybrid`、`minute_orders_artifacts_v2`、
`minute_orders_hybrid_evidence_v1` 与 `minute_orders_source_provenance_v1`；原转换版 `bl2_source_transform_v1`，
本次 §8 升为 `bl2_source_transform_v2`，须重新 pin implementation/recipe/attestation。
上述 v2 仅为 §8 历史记录；当前宿主须统一按 §9 / §9.5 以 `bl2_source_transform_v3` 为唯一版本重新 pin implementation/recipe/attestation。
它显式区分 market 来源与 synthetic commands/account；本单元不提供 real-only 或 `lake` evidence_level。
wrapper 执行前、writer 执行后重读冻结源并重建映射，不只信任调用方自报的 provenance hash。
增加 `source_provenance.json`、`source_checks.json`、成功路径的 `source_postflight.json`；
保留源核验前后身份与失败归档，summary 仍最后发布、已有根仍拒覆写。
provenance 的 canonical payload hash 与工件含换行 bytes hash 分别记录，不混为一个 hash。

旧 `evidence_level=synthetic` 无新增必填 tags；九份原有工件对 `58b6355` 原 writer 的 pinned fixture
逐文件 bytes SHA-256 保持一致。loader 的 mark.source 保留 `B-L2-01/` 来源标记，经过 v1 codec 后仍拒贴 synthetic；
真实来源不得去标记、手改 manifest 或旁路 writer。`comparison_status=no_ssot_compare_authorization` 不变。
全程空仓的有效业务运行记 `held_mark_coverage=not_covered`，不能作为完整 mark 验收。

**Fixture PASS != lake PASS。** 本实现只取得 data-free/synthetic 测试证据；没有真实来源/宿主 attestation、
4090 live、L2 native↔L1 湖 parity 或真湖独立 oracle，B-native CSV/v7 PASS 也不替代这些证据。
item 4 及其外部 streams/host receipt 仍按 §6 另行 GO，SSOT 绿 R/S 仍另行裁定。

## 8. Schema-adapt与事实 sidecar（2026-09-30）

针对 `HOST_B_L2_01.md` 的三项 schema/事实来源 BLOCKED，登记以下只读接口。
receipt：`/workspace/handoffs/b_l2_schema_adapt_20260930/HOST_B_L2_01.md`。
这里注册的是可 pin 的输入形状，**没有提供或认证宿主市场事实**；生成式小 fixture 见
[`test_minute_orders_source_schema_adapt.py`](../../tests/test_minute_orders_source_schema_adapt.py)。

### 8.1 Vendor 分区身份

已报告的物理 schema 为 `time:int64, open/high/low/close:double, volume:int64,
amount:double, __index_level_0__:timestamp[ns]`，无 `symbol` 列。
recipe 的 source 仍须 `location={"kind":"minute","symbol":"603196.SH"}`，
经 resolver 与 `to_partition_key` 定位 raw `symbol=603196_SH/data.parquet`，pin **完整物理 schema 与原文件 SHA-256**。
新模式显式写 `bars[].columns.symbol={"kind":"partition"}`；其余 time/close/volume 仍是实际列名。
引用同一 minute source 的 `mark_grid[].prices[].symbol_column` 也必须是 `{"kind":"partition"}`，
并保留同一 time/close 映射；mark 的 `symbol` 仍显式填写且必须匹配分区。

原 `columns.symbol="symbol"`（或其他具名身份列）模式保留：列不存在立即失败，不能自动切换模式。
partition 模式不生成/写入列；若文件已有物理 `symbol` 列，所有行必须规范化后匹配分区，
包括窗口外、排除的竞价行与仅供 mark 的行。具名身份列与物理 `symbol` 同时存在时两者都核对；
不同身份、null/非法身份、重复时间及混合品种文件拒绝。无身份列的文件仍须由宿主证明属于该分区，
代码不从 OHLC 猜品种。provenance 的 `symbol_binding` 保存模式、location、partition_key 与已检查列。
时间 int64 不自动等于 epoch_ms，volume int64 不证明手/股；原 START/END、时间单位和量单位 attestation 门保留。

### 8.2 登记、状态网格与每日 instrument facts

两类文件均由宿主显式提供，推荐置于受控的仓外 evidence 目录，不生成 lake parquet。
每份加入 `sources[]`：唯一 `id`、`location={"kind":"sidecar","path":"<绝对路径>"}`、
`format="json"`、下列 `schema` 和完整 bytes `sha256`；`roles.status/instruments` 各指向独立 source ID。
JSON 封套严格为 `{"schema_version":"<对应 schema>","data":{"rows":[...]}}`；不省略字段、不接受 JSON 浮点数。

| schema | 每个 `data.rows[]` 的完整字段 |
|---|---|
| `bl2_status_v1` | `symbol`、`start/end`（Asia/Shanghai 带 +08:00 的精确一分钟区间）、`missing/halted`（两个显式 bool）、`reason/issuer`（非空文本）、`proofs`（非空 proof source ID 数组） |
| `bl2_instruments_v1` | `facts`（见下行）、`effective_from/effective_through`（ISO 日期，包含 trade_date）、`available_at`（带 +08:00，不晚于该日首次使用）、`ordinary_listing=true`、`origin`、`proofs`、`derivation` |
| `facts` | `symbol/trade_date`、`board="main"`、`price_domain="raw"`、`tick_size/reference_price/limit_down/limit_up`（Decimal 字符串）、`lot_size`（正整数） |

status 的键是 `(规范 symbol,start,end)`，须精确覆盖冻结 symbol 全集 × `intervals` 展开的**每个 session 分钟桶**；
不是每交易日写一行 False 就算覆盖。缺格、多格、重复格、缺布尔/原因/出具者/证明均失败。
只有有证据的 missing 才映射为 null close/volume；missing 与实际源行冲突即失败，缺源行不自动变 missing。
halted 与 missing 独立取值，两个 False 同样需要证明。provenance `transform.status` 保留每格 source/行号及全部事实字段。

instrument 按 `(symbol,trade_date)` 唯一供给，覆盖 bucket、submit、mark 及初始持仓首次使用日；
跨日不沿用昨日 facts，缺日/重复/不可得/不支持 board 或价域均失败，既有 lot/tick/limits 校验继续生效。
`origin="source_fact"` 时 `derivation={}`；`origin="approved_derivation"` 时须完整给出
`derivation={"inputs":["<已 pin 的原始 source ID>"],"approved_rule_version":"<已批准规则版>",
"independent_verification":["<instruments proof ID>"]}`。
inputs 不能拿 proof/attestation 代替原始材料；loader 只验证并消费已供给数值，**不计算或默认 10% 上下限、tick、lot**。
instrument 的出具者保存在其具名 proofs 的 `issuer`；provenance 保存 facts source/行号、有效期、可得性、origin/proofs/derivation。

### 8.3 可 pin 的证明材料与剩余门禁

`proofs` 指向独立登记、带 bytes hash 的 JSON sidecar：`schema="bl2_proof_v1"`，
封套仍为 `schema_version/data`，其中 `data` 完整形状如下：

| 字段 | 内容 / 校验 |
|---|---|
| `issuer/subject` | 非空出具者；status 使用 `subject="status"`，instruments 及推导核验使用 `subject="instruments"` |
| `source_refs` | 非空、已 pin 的原始材料 ID 数组；不得指向 proof 或 attestation 自证；units/instruments/status 还不得引用 `bl2_instruments_v1` 或 `bl2_status_v1` 消费包作证明材料，见 §9.1 |
| `filter` | `symbols/from_date/through_date/predicate`；品种与日期覆盖使用该 proof 的事实行，predicate 非空 |
| `result` | `complete=true`、非空 `summary`、非空 `rows`；原观察字段为 `source/row/observation`，row 是零基索引；units/instruments/status 自 §9 起还必须有 `basis/binding`，纯文字观察不再充分 |
| `limitations` | 非空文本数组，记录权威性、范围及其他限制 |

观察行号必须存在于已 pin Parquet 行、JSON `data` 数组或 JSON `data.rows` 数组中；越界不能充当证明。
对应 attestation claims 仍为 `complete_halt_missing_grid` / `ordinary_main_raw_facts_verified`；
每份 claim proof 须覆盖整个 recipe 品种/日期窗口，逐行 proof 及 derivation verification 另核该行品种/日期。
宿主仍需独立审核原始材料、逐格结论和规则批准的真实性；非空文字与 hash 本身不认证市场事实。
calendar、公司行动、时间/量单位、marks 证明及完整 `scope_hash` 绑定要求全部保留。

本片 **fixture PASS ≠ lake PASS**；不解除原宿主 `BLOCKED/NOT_RUN` 收据，不签 native↔L1 湖 parity 或独立 oracle。
PR 合并仍待 Human「合」；**合并后 4090 re-run 需要另一次具名 Human GO**，不能沿用先前 probe 的 GO 自动发车。

## 9. Facts/attestation package GO（2026-09-30）

本片授权为 facts/attestation **接口登记、绑定收紧、空模板与 synthetic 测试**。
依据仓外 `/workspace/handoffs/b_l2_facts_attestation_20260930/HOST_B_L2_01_R2.md`，
R2 在 `47abe4d8d6221db8de3d6782e90ecdfea96780af` 为 **BLOCKED/NOT_RUN**。
schema 分区身份已支持，但三项市场事实门仍缺材料；下表是 host 的交付位置，不是 PASS 声明。

| R2 BLOCKED gate | Package ID / claim | Host-fillable artifact |
|---|---|---|
| `volume_units_attestation` | `bl2_proof_v1`, subject `units`; `claims.units.conclusion=incremental_volume_units_verified` | [units proof template](../../tests/fixtures/minute_orders_source_attestation/units.proof.template.json) |
| `instrument_limits_facts` | `bl2_instruments_v1` + `bl2_proof_v1`, subject `instruments`; `ordinary_main_raw_facts_verified` | [source facts](../../tests/fixtures/minute_orders_source_attestation/instruments.template.json)、[approved derivation](../../tests/fixtures/minute_orders_source_attestation/instruments.derived.template.json)、[instrument proof](../../tests/fixtures/minute_orders_source_attestation/instruments.proof.template.json) |
| `halt_missing_facts_source` | `bl2_status_v1` + `bl2_proof_v1`, subject `status`; `complete_halt_missing_grid` | [status grid](../../tests/fixtures/minute_orders_source_attestation/status.template.json)、[status proof](../../tests/fixtures/minute_orders_source_attestation/status.proof.template.json) |

模板集中在 [template README](../../tests/fixtures/minute_orders_source_attestation/README.md)。
`null`、空 refs、`complete=false` 表示未填写，**原样加载必须失败**；没有默认宿主 symbol、日期、
tick、lot、reference、limits、量因子或状态。文件名不是固定 source ID；host 为每份材料登记独立 ID。
合成接受/拒绝例见 [attestation tests](../../tests/test_minute_orders_source_attestation.py)，不得复制成市场事实。

### 9.1 Proof 封套与具体值绑定

封套仍为 `{"schema_version":"bl2_proof_v1","data":{...}}`，`data` **仅有六项必填字段**：

| 字段 | 冻结要求 |
|---|---|
| `issuer` | 非空、可追溯的出具者；host 审核身份与权限，不以随意填姓名代替认证 |
| `subject` | 本三门分别为 `units` / `instruments` / `status`，必须对应具名 claim 与事实行 |
| `source_refs` | 非空 source ID 数组，所有原始材料独立登记路径/schema/bytes SHA-256；不得引用 proof、attestation、`bl2_instruments_v1` 或 `bl2_status_v1` 消费包自证 |
| `filter` | 完整 `symbols/from_date/through_date/predicate`，品种与包含端点的日期范围覆盖所证明内容，predicate 说明实际筛选与证据含义 |
| `result` | 完整 `complete/summary/rows`；审核完成才写 `complete=true`；summary 非空，观察 rows 非空，每行见下文 |
| `limitations` | 非空文本数组，披露来源权威性、时点、覆盖、观察与推导限制，不能用限制语句豁免缺证据 |

三类 proof 的每个 `result.rows[]` 现在严格包含：
`source`（须在 source_refs 中）、`row`（原材料零基行号）、`observation`（非空审核说明）、
`basis`（下表枚举）、`binding`（保存的具体断言对象）。
原材料行必须存在于已 pin Parquet 行、JSON `data` 数组或 `data.rows` 数组中。
原始资料若不在这两种文件格式中，由 host 在获准的采集侧留存原件和可审核的行式摘录，再 pin 摘录；
本仓不抓取、不生成事实。说明原件身份与摘录方法属于 host 审核责任。

| subject | 允许的 basis | binding 内容与唯一键 |
|---|---|---|
| `units` | `source_declaration` | `source/column/kind/unit/shares_per_unit`；键 `(source,column)` |
| `instruments` | `source_fact` 或 `approved_derivation`，与消费行 origin 相同 | 完整 instrument 行去掉 `proofs` 及 `derivation.independent_verification`；键 `(canonical symbol,trade_date)` |
| `status` | `explicit_status` | 完整 status 行去掉 `proofs`；键 `(canonical symbol,start,end)` |

bindings 使用规范 symbol、带 `+08:00` 的规范时间及与消费包完全相同的 Decimal 字符串/整数/布尔值。
比较为 canonical JSON 精确相等（`false` 不等于 `0`，`"10.0"` 不等于 `"10.00"`），不替 host 修正值。
同一 proof 内重复键拒绝；claim 引用的多个 proof 若对同键给出冲突值也拒绝。
每条消费行必须有匹配 binding，日期范围内的一条泛泛观察不能替代该行断言。
status/instrument 行 proofs 及 derivation verification refs 都须出现在对应 attestation claim 中。
claim 与行级证据都要匹配，不能用不相关的总体证明遮住未证明的值。
原 §8 的 claim proof 全窗口覆盖要求保留；多 source 的 units proof 也须覆盖声明的所有 symbol 与运行日期。
calendar/timing/actions/marks 的已有 proof 形状不变。

代码验证的是材料字节、声明结构、具体值和覆盖的一致性；不判读 narrative 是否真实，也不签发身份认证。
host 必须逐行审核原始资料是否真正支持 `basis` 和 `binding`。手工把启发式改名为 `source_declaration`
或 `explicit_status` 不会产生市场事实，仍不满足 host attestation。

### 9.2 量单位：绑定到 raw minute 源与具体列

`bars[].volume={"kind":"incremental","unit":...,"shares_per_unit":...}` 全部显式提供。
shares 要求 factor=1；lots 要求正整数 factor，**没有默认 100**。
proof 的 binding.source 指向已 pin 的 minute source，binding.column 是其物理 volume 映射列；
kind/unit/factor 必须逐项匹配。证明还须覆盖该 source 的 symbol 及 recipe 起止日期。
`claims.units.proofs` 中没有匹配结果，即使重算了 `scope_hash`、填写 complete=true 或改成 lake 标签，也失败。
缺单位声明不通过；不得从另一 source/列、另一日期、旧 shares proof 或旧 factor 借证。
provenance 的 `transform.bars[].volume_proofs` 保存匹配 proof ID/观察行号/原材料 ID/原行号。

独立依据应为可审核的供应商字段语义/单位声明或其他具名权威材料，明确适用版本、品种与期间，
并说明成交量为每分钟增量而非累计量。minute/daily bars 本身不能充当此声明的 source_refs，
同字节行情文件换成 sidecar 别名也不能绕过独立性检查。
**amount/(close×volume)≈100 是启发式、明确 non-attestation**；R2 报告中的比率不是 lots×100 证明。
不论接近度或样本数量，都不能据此签 `incremental_volume_units_verified`。
int64、列名 volume、推测常见行情口径也不证明单位。

### 9.3 Instrument：来源事实与批准推导

消费形状沿用 §8.2，键为 `(symbol,trade_date)`；tick/reference/上下限为有限 Decimal 字符串，
lot_size 为正整数，禁止 bool 冒充。每个使用日完整覆盖，不跨日继承；保留 ordinary/main/raw、
有效期、available_at 和既有经济校验。issuer 位于对应 proof；不增添引擎经济字段。

`source_fact`：host 提供原始事实行，`derivation={}`；proof 的 `basis=source_fact`，binding 保存整个
facts、有效期、available_at、ordinary_listing、origin 和空 derivation。改一个 tick、lot、reference
或 limit 值而不取得新 proof 就失败。原始材料可分列来自不同来源，但必须能逐项审核其适用日与出处。

`approved_derivation`：不得因为缺事实就改标签。必须先有具名批准规则和冻结输入：

1. `derivation.inputs` 非空，指向已 pin 原始材料，不得用 proof/attestation/本次 facts 或 status 消费包替代。
2. `approved_rule_version` 非空，指向 host 已审验批准的规则版本；保存规则内容、批准材料、
   适用范围、参考价选择、舍入方式及例外条件的可审核材料，并在 inputs 中登记相应来源。
3. primary proofs 与 `independent_verification` 使用不同 proof IDs、不同 issuer；两组都引用全部 inputs，
   都保存相同输出事实、输入 IDs 和批准规则版本的 binding，并全部登记到 instruments claim。
4. 独立核验者审核规则批准与数值推导。代码不执行公式，也无法从版本字符串验证实际批准权；
   host 审核不通过，仍保持 BLOCKED。

**不硬编码或默认 10%**，不由价格轨迹、ST 名单存在、证券代码或 volume 启发式生成 tick/lot/limit。
`reference_price` 不自动等于昨日 close；无涨跌停事实/未覆盖特殊情况不能造一个范围让输入通过。
只消费已供给值；不同/非对称 limit 的 synthetic 测试证明代码没有重算 10%，不证明真实证券的限制。

### 9.4 Status：每 symbol × session-minute 的完整事实网格

host 按冻结的 `symbols × intervals` 展开网格，start/end 必须是每个一分钟桶；不从是否有成交猜网格。
每格显式填写 missing、halted、reason、issuer、proofs；两个 False 仍需 `explicit_status` binding。
binding 连同区间、两布尔、原因和出具者逐项一致。缺格、多格、重复格、无证据、只有日期级概述、
陈旧结论或其他分钟的 proof 均不通过。

`missing` 说明声明网格内该源分钟记录是否缺失；`halted` 是独立的停牌事实。
无源行不能自动设 missing，须有缺失核验；无源行、零 volume、ST 供应商目录、没有停牌公告结果，
均不能自动设 halted，也不能自动设 halted=false。**no halt-from-silence**。
允许有证据的四种 missing/halted 组合；missing 与源行同时存在则冲突失败，
missing=false 而源行缺失则失败，零量源行仍是存在的记录。
原始资料必须同时支撑源缺失结论与停牌结论；逐格 reason 应解释所用材料及覆盖规则。

### 9.5 4090 填写/冻结清单与停点

1. 从 R2 收据的 BLOCKED 项开始，确认获准窗口、symbol、连续分钟 intervals 与独立 mark grid；
   R2 的 2169 行、单位比率、零公司行动命中、两分钟提案均是 probe，不是已冻结事实或 GO。
2. 在湖外 evidence 目录填写上述模板，收集独立量单位声明、每日 instrument 原材料、逐分钟状态资料。
   每个未知字段继续为空；无法取证就记录 BLOCKED，不填“通常值”。
3. 审核所有 proof 的六字段与具体 bindings；需要推导时先审核规则批准及另一 issuer 的独立核验。
   全量状态覆盖、事实可得性和 source rows 都核对完才写 complete=true。
4. 先 pin 原始来源，再 pin proof 和消费包；所有文件加入 recipe.sources，填好 roles 和七类 claims。
   action/calendar/timing/marks/account/commands 等现有门仍必须满足；本三门不能替代它们。
5. 本片转换版升为 **`bl2_source_transform_v3`**；package/schema IDs 保持上述 v1，
   v2 的纯文字 units/instruments/status proof 不兼容本次收紧，必须补齐 basis/binding。
   pin 当前 clean code SHA、实际 Python/PyArrow/transform；按 §7 计算 `attestation_scope(recipe)`，
   写 attestation、pin 其 bytes SHA-256，最后冻结 recipe bytes/hash。任一变更均重新冻结；不改旧收据。
6. 获准做 host 预检时，使用 §7 的 `load_minute_orders_source(recipe_path, expected_sha256=...)`
   单独校验；该 API 不运行撮合事件、不生成 S4 工件。错误保留为错误，不能自动补值或调用 runner。
   本片测试使用显式 `OSKH_MERGE_PYTHON` 与 tmp_path fabricated sources，没有访问 4090/真实湖。
7. 将各 gate 的材料路径/hash、审核人、范围与局限提交新的 host receipt。
   `freeze_recipe_attestation` 是后续组合门，仅有这些模板不能将其判 PASS。

**本 PR 不解除 R2 BLOCKED，不宣称 lake PASS / host certification / native↔L1 湖 parity / 独立 oracle
覆盖 / 市场可执行性 / SSOT 绿 R/S。** `no_ssot_compare_authorization` 不变。
**PR 不合并；合并须 Human「合」。4090 R3 发车前还需要另一条具名 Human GO**，
即使模板填写完、校验通过或 PR 后续获准合并，也不沿用 R2/probe GO 自动调度。

## 10. R3 后证据采集登记（2026-09-30）

R3 已在 4090 执行：tip `a268e11` · transform `bl2_source_transform_v3` · verdict 仍
**`BLOCKED/NOT_RUN`**（同 §9 三门，收据与探针摘要已逐字节入库
[b-l2-01-evidence-2026-09-30/](b-l2-01-evidence-2026-09-30/)）。
随后 host 指示做了一轮湖外只读取证（1.3 / MyQuant / xtquant 包 / 湖本体 / 公开规则），
六包 `bl2_raw_excerpt_draft_v0_host_review` 原材料与 R4 行动清单（R4-A QMT 全字段回补
`preClose/suspendFlag`、R4-B 量单位声明 hunt、R4-C 规则文本/双 issuer、R4-D host 审核）
登记于 [note-b-l2-01-r3-evidence-sweep-2026-09-30.md](note-b-l2-01-r3-evidence-sweep-2026-09-30.md)。
**新材料是草稿摘录而非 proof：不解除任何 BLOCKED 门，不改上文合同一字；
量单位「vendor 无 K线单位注记」本身已按缺失证据 pin。R4 仍需具名 Human GO。**

2026-09-30 午增补：PR #272 评审跟进以腾讯/新浪两个湖外独立行情源对湖日线做交叉核对，
封第七包 `raw_excerpt_crossvendor_daily_603196SH.json`（同目录，附离线自检器）——
13 天三源 OHLC/volume 全等、10% 涨跌停复算零违例、零股解释探针比率 ≈99.98。
按 §9.2 仍为 NON-ATTESTATION 经验旁证，任何 BLOCKED 门状态不变。

2026-09-30 午增补 #2：评审环境接入 kimi-datasource MCP 的 Wind 数据源（授权行情），
封第八包 `raw_excerpt_wind_mcp_daily_603196SH.json`（同目录，附两份 pin CSV 与离线
自检器）——13 天湖≡Wind（OHLC/amount 全等，Wind 为股口径、零股日 2025-10-23 与新浪
逐股一致，等价链加强到四源）；同包 pin 负结果：MCP 自带 Wind 字段目录 volume 条
**无单位注记**，Wind 权威单位规范不在 MCP 暴露面，source_declaration 锚仍缺位。
按 §9.2 仍为 NON-ATTESTATION 经验旁证，任何 BLOCKED 门状态不变。

2026-09-30 Human GO 窄例外（仅覆盖本段）：[原始 GO 与 remap 包](b-l2-01-evidence-2026-09-30/attestation_packages/README.md)
接受 `603196.SH`、`20251023–20251104` 的 units `basis=cross_source_ratio`，依据 #1111
`ec19fd6` 的 daqmt 日量 ×100 对 THS/stock_finance_data 及逐日 `sum(1m)==1d`；单位手、
`shares_per_unit=100`、incremental 显式声明。此例外不成为通用 vendor `source_declaration`，
文档缺单位声明的负结果及 20251023 差 100 股仍须披露；§9.2 的 amount/close/volume 启发式禁令保留。
`bl2_source_transform_v4` 仅在显式 basis、固定 Human GO marker、此证券/窗口/列/因子与独立来源齐备时接受；
`source_declaration` 须有匹配的原材料 `unit_declaration`，不得把 ratio 改标签冒充声明。
六份 remapped drafts 的填充/结构验证 **≠ lake PASS**，instrument 未证实的历史可得性、ordinary listing
与规则批准仍 fail closed；不补造 10% 或 halt-from-silence。R3 仍 `BLOCKED/NOT_RUN`，
R4 仍须单独 Human「开 R4」，合并仍须 Human「合」，production_C=frozen。
