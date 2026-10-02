# minute_orders_research_v1：L2-S4 artifacts + isolation

2026-09-29 · **L2-S4 / Human GO / synthetic research only** · 基线 `b065c99`（#253）。
Human：「下一刀默认 L2-S4 artifacts+isolation====GO」。冻结记录：
`/workspace/handoffs/l1_l2_research_engine_l2s4_20260929/HUMAN_GO.md`；
实施对应外部 PLAN 的 L2-S4，字段依据 [S0 §4](note-l2-s0-minute-orders-contract-2026-09-29.md)。
PR 后交 Human/Grok review；**未经 Human「合」不得合并**。`production_C=frozen`。

## 显式 API 与观察边界

```python
from backtest.research.minute_orders_backend.runner import (
    run_minute_orders_research, run_minute_orders_research_with_artifacts,
)
from backtest.research.minute_orders_backend.artifacts import write_minute_orders_artifacts

# request 是显式 RunInput；默认 API 及其原异常仍保持纯内存。
result = run_minute_orders_research(request)
# 已有结果或捕获的 Exception 可单独归档；不重跑撮合。
written = write_minute_orders_artifacts(
    request, result, parent, run_id="synthetic-a", evidence_level="synthetic",
)
# 需要逐状态预留与账本快照时，显式选择这个完整采集入口。
written = run_minute_orders_research_with_artifacts(
    request, parent, run_id="synthetic-b", evidence_level="synthetic",
)
```

`parent` 必填，可用 `Path(".")` 表示调用方 cwd；不会 chdir 或改 env。
两个落盘 API 返回 `ArtifactWriteResult(root,status,contract_hash,input_hash)`。
仅 wrapper 捕获普通 engine Exception，返回 `status=failed` 的归档结果；不重试。
writer 的编码/磁盘/校验失败抛 `ArtifactWriteError`，含 root、stage、evidence_error；
建根前错误（含 FileExistsError、坏 run_id/身份参数）直接向调用方报告。
S4 只接受显式 `evidence_level="synthetic"`；真实来源/湖另案，不自动升级证据等级。

wrapper 只覆盖 Broker 的 `_record` 观察点，记录原 handler 已提交的不可变 LedgerSnapshot。
`OrderTransition.ledger` 默认为 None；默认 S3 API 不采集、不读文件、不 eager import writer。
MatchCore/Ledger/Broker/Clock 的成交、费用、资源、相位均未修改；采集不执行第二次回放。
writer 的独立调用要求调用方提供同一 run 的输入与结果；不证明外部来源或重做引擎验证。
会核对订单输入、marks 与已提交 fills 的引用一致性；原 S3 result 没有历史预留快照，
其未知 `reservation_before/after`、对应历史 ledger_version **省略**，不从费用反算。
完整 schema 的逐状态证据请用 wrapper；直接 Exception 无快照时输出空结果流。

## 独立根与字段

```text
<parent>/backtest_output/minute_orders_research_v1/<run_id>/
  contract.json     inputs.json      commands.jsonl
  orders.jsonl     fills.jsonl       ledger.jsonl      marks.jsonl
  manifest.json
  summary.json     # 仅成功完成后发布
  failure.json     # 失败证据；与成功 summary 互斥
```

run_id 为 1–128 位 ASCII 单路径分量，首位字母/数字，其余可含 `._-`。
独占 mkdir 新根：空目录、文件、软链接、断链均视为已存在，**存在即失败**。
固定的 backtest_output/backend 名空间若是软链接或非目录也拒绝；不清空/复用旧根。
重复实验须新 run_id；只会写本次新建根，不触及四家旧 pins/writers/output。

| 文件 | S4 投影与引用规则 |
|---|---|
| contract | S0 v0 身份、price_model、clock/phase/lifecycle/capacity/lot/fee/mark/failure；显式 fees/p/marks 政策及 inputs 来源 |
| inputs | 完整 RunInput 的 data；每个顶层输入的 SHA-256 与 `inputs.json#/data/<field>`；包含 calendar、halt/missing、公司行动覆盖证明 |
| commands | 保留输入顺序及原 sequence，kind=submit/cancel；cancel 引用目标 order 并带已知 symbol/side，不补 qty/expiry |
| orders | 原全序状态流、event_key/phase/reason、原量/已成/残量、command/fill 引用；采集时列出前后现金/可卖量预留与账本版本 |
| fills | 增量量价/名义额/费用、逐订单累计额/费、bucket 起止/available/matched/booked 时钟、容量用前/后与 ledger_version |
| ledger | 逐状态及 mark 快照按 event_key 排序，最后追加 final/last_committed；lots 带 acquire/sellable、reserved/free qty，记录 fill IDs 与桶消耗 |
| marks | mark ID/time、来源/raw、逐持仓量价/market_value、ledger_version 与 valuation_valid；不生成交易或 NAV 产品 |
| summary | status=success、各状态计数、每单残量/active、成交笔数/股数/累计费、合法 mark 行引用；不强平未到期活跃单 |
| failure | status=failed、阶段/原因/error_type、已有输入/工件引用；有证据才列最后账本版本与最后记录事件，不将其冒充失败事件 |

`#row=N` 为 JSONL 一基行号；event_key 为 S3 六元全序键。同一次 submit 的
Submitted 与 Accepted/Rejected 共享事件键，按原 transition 顺序保留。
末尾账本为运行结束快照，失败时不伪造 end_at/事件键；没有 marks 时仍创建空 marks.jsonl。
容量前后由已提交桶容量和原增量 fills 顺序投影；累计额/费用仅累加已提交数据。
金额投影使用精确整数分，不受调用方 Decimal 精度/舍入 context 影响，不重算 fee 模型。

## Identity / 固定编码 v1

`schema_version=minute_orders_artifacts_v1`，`backend_id=minute_orders_research_v1`。
固定 canonical encoding：dataclass 转字段对象；Enum 转值；Decimal 用 `str(value)`
保留输入 scale/exponent；date 用 ISO 日期，datetime 用带 offset 的 `isoformat()`。
对象中 None 字段省略，序列保留原顺序，frozenset 按元素 canonical bytes 排序。
未知对象、float、非有限 Decimal、无时区 datetime 拒绝；不填未知零值。
之后 `json.dumps(sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)`，
UTF-8 无 BOM。无 wall-clock 时间、绝对输出路径、随机 ID 或 mtime 参与内容。

- `contract_hash=SHA256(canonical(contract对象))`，包含规则和显式模型配置。
- `input_hash=SHA256(canonical(inputs.data))`，覆盖初始状态及全部参数/输入。
- component hash 同法作用于每个 data 顶层值；均不包含末尾换行。
- JSON 文件及每个 JSONL 行追加单个 LF；manifest 的文件 hash 覆盖**全部磁盘 bytes**。
- run_id 不进入 contract/input；相同字面输入+配置的主体 bytes 相同。
  run_id 在 manifest/summary 内，故二者及 manifest 中 summary 的文件 hash 随 ID 改变。
  Decimal 的不同字面精度、输入命令顺序属于不同输入身份，不声称排列不变 hash。

`code_sha` 默认读取实施 package 所在工作树的 Git HEAD，并记录 `code_sha_source=git_head`
与 package 范围 `code_dirty`；dirty=true 时 HEAD 只是基线，不能冒称干净实现已锁定。
显式 override 须完整 40 位小写 SHA，标 `caller_override`（测试使用真实基线 SHA）；
Git 不可用时省略 code_sha 并标 unavailable，不编造生产 SHA。
`comparison_status=no_ssot_compare_authorization` 固定，运行成功不改变比较资格。

## 完成、失败与测试

先写 contract/inputs/commands/结果流，再写 manifest，逐文件读回核对 bytes/hash 来源及 JSON。
summary 先写同根 `.summary.json.pending`、flush/fsync 并校验，再原子 rename 为 summary.json，
它是**最后发布的文件、唯一成功完成标志**；manifest 不自 hash，包含预先计算的 summary hash。
普通写入异常先撤除本次 summary，再写 failure 与 failed manifest；失败 manifest 仅列现存
证据文件（可含不完整字节），不列 pending。建根前失败绝不向既有根补写 failure。
输入无法编码时可缺 inputs/hash；记录编码错误及原 engine error，unknown 继续省略。
持续磁盘故障可能连失败证据也写不了，通过异常的 evidence_error 明报，不能伪称已归档。
强杀/KeyboardInterrupt 不保证有 failure/failed manifest，可能残留 pending 或 success manifest；
**缺少有效 summary 的根一律未完成**。不提供自动恢复/覆盖，不承诺整棵目录的断电持久性。

`tests/test_minute_orders_artifacts.py` 仅 temp roots：schema/手算预留与费用、旧目录隔离、
文件/目录/软链接拒覆写、输入/engine 失败、逐文件中断、发布边界、校验损坏、重复确定性、
空 marks/活跃残量/业务拒单、无 Git、默认纯内存及独立进程 import fence。
S1/S2/S3 原测试保持。**绿C = synthetic artifact/isolation oracle；绿C≠绿R/绿S**。
范围外：CLI 产品化、L1 注册、lake/vendor、在线 StrategyPort、production_C 改动、
旧 CSV/JR/v7/ModeB 路径和 NAV 可比性；不修改 HELP_LOCK/CI/presets/golden。

后续：另获 Human GO 的 [L2-S5 注册到 L1](note-l2-s5-l1-register-2026-09-29.md)
将内存 API 与本片 wrapper 分别注册为显式研究 entry（本 PR）；无 CLI/默认选择，比较资格不变。
