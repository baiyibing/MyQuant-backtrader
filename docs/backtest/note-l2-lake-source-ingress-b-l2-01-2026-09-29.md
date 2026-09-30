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
`minute_orders_hybrid_evidence_v1` 与 `minute_orders_source_provenance_v1`，转换版 `bl2_source_transform_v1`。
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
