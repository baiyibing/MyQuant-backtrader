# 本机消费侧验收补充 · 2026-11-03

本片按 P11 → P14 → P15 → P03 顺序执行。行情湖只读；输出及分钟缓存位于独立任务目录。
没有改动 MyQuant-infra 搬迁、下载器、桥或交易进程。冻结 BT 运行源码为
`6f3a3305b2dacba6bb4fe49549a05284227ac43f`；当时 worktree clean。

| 项 | 本次结果 | 尚未代签 |
|---|---|---|
| P11 | [MyQuant #114](https://github.com/baiyibing/MyQuant/pull/114)：拟合边界标签泄漏修复、E3/E4 本机验收，三项 CI SUCCESS | PR 在该回执时 OPEN；不声明已合入 |
| P14 | [legacy 八格 PASS](p14/acceptance.json)：version8/v7 各 normal、low_cash、invalid_config、bad_output | 旧 Slice D 改造前基线和 reason/价格对照仍开放 |
| P15 | [六股 250,158 行](p15/acceptance.json)：miss 2.520s、hit 0.234s、mem 0.117s，帧摘要一致 | 不是清空 OS 缓存后的冷 IO；不是全市场数字或分片 GO |
| P03 | [11 个具名样本](p03/readout.json)：authority 稳定、workspace 分离、所读文件前后 hash 一致 | 001381 零价零量、512390 分钟停在 10/15；4090/75 NOT_RUN |

P14 的正常格 trades/equity/audit 在 native 与 L1 间逐字节一致，原始 reason 计数仅用于
本次输出留痕，不冒充旧 Slice D。11 月 1 日 industry 八格回执保留自己的代码及湖身份，
本片不宣称两套 profile 在同一来源快照上同时通过，也不宣称经济正确性或策略准入。

P15 在既有 11 月 1 日两股扫描探针之后，补六股跨板块样本以及现有单体缓存的独立进程
miss/hit 和同进程 mem。miss 进程采样进程树峰值约 214.75 MiB；其 Windows 生命周期
peak_wset 约 225.27 MiB，口径不同，均不是全市场内存预算。5575 仅沿用旧方案 FD 外推
示例数。没有实际 shard，append/repair 重建计数仍未实测；S1/S2/S3 仍须各自合同和验收。

P03 每份文件只读最后一个物理 row group；检查目标日存在、OHLC 有限正值/高低关系、
非负 volume/amount、组内目标时间重复。minute 的零量行本身不定为坏数据或停牌。
没有全历史/全市场覆盖结论、供应商事实裁决或 SHM 字段质量签收。

`recipe.json` 是运行前独占登记；`raw-record-hashes.json` 记录原始本机 JSON hash。
发布 JSON 将机器路径替换为 `$TASK/$REPO/$LAKE/$PYTHON_ENV`，其 hash 与原始记录不同；
发布文件另由 `publication-sha256.json` 记录。P14 的输入清单保留逐文件内容 hash。
原始交易/权益 CSV、Parquet 缓存及完整日志留在忽略的任务审计目录；不把行情数字产物入库。

`audit-sources/` 保存执行过的原始宿主脚本及 hash，用于审计，不是产品 CLI。
复现需恢复 `$TASK/bt` 的原任务布局、冻结 Git SHA、选定 vanna312 解释器和外部数据配置，
并选择新的输出目录；不得直接在归档目录运行。P15 先有计划复核 REQUEST_CHANGES，修订后
APPROVE，再执行；CLI 是 Claude Code 2.1.317，实际模型 GLM-5.3，非 Anthropic 模型。

统一盘点的 64 条冻结记录和既有关闭回执保持不变；只追加 implementation_refs。
P03/P14/P15 均保持整包开放，P11 的合入状态以其 PR 为准。

最终固定提交证据复核 ce45c052：**APPROVE**，见[原文及口径澄清](evidence-review.json)。CLI 禁用工具，依据固定源码/证据 bundle；不冒称复核运行了宿主场景。之后仅追加这条复核回执及发布摘要。
