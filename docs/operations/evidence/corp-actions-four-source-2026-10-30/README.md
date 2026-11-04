# corp-actions 四源研究证据 — 2026-10-30

研究结论、窗口与分母见[研究说明](../../note-corp-actions-four-source-study-2026-10-30.md)。本包是离线核对和独立样本研究，不是可发布湖、生产增量或消费者验收文件。

## 固定 38 码

| 文件 | 内容 |
|---|---|
| `inputs_manifest.json` | 固定 Git 对象、输入路径、字节数和 SHA256 |
| `report.json` | 38 码四源指标、共同窗口、QMT/hithink 指纹与限制 |
| `four_source_events.csv` | 每公告事件的原始/适配值、来源、接受状态和逐字段比较 |
| `four_source_differences.csv` | 五个事件的精确数值差异，未给 hithink 自动套用 ROUND4 |
| `policy_derived_events.csv` | 62 个空腿适配事件及 10 个上市日缺省字段对应事件 |
| `semantic_findings.json` | 301266 两份原文的除权价格分母/经济候选区别与来源哈希 |
| `semantic_policy_trace.json` | 两份原文的观测式 v10 重放，字段/状态与归档一致 |
| `hithink_no_event_probe.json` | 8 码事件端点返回 `3002`；目录 7 个命中、1 个网络失败。原探针已脱敏 |
| `execution_versions.json` | 本机解释器、解析库、研究驱动及冻结抽取器/adapter 版本 |
| `lake_authority_observation.json` | resolver 根、宿主、marker 字节指纹、当前索引与冻结副本一致性及 sidecar 观察；不证明跨宿主同步 |
| `confirmed_case_notes.json` | 七份原文的五组观察：跨页漏提、原件→更正件、ROUND4 精度损失、股东类别与日聚合、北交所模板；定点核实而非全样本准确率 |

`UNKNOWN` 不按 0 处理；`NOT_ACCEPTED` 不计作适配后经济值。QMT 索引只提供日期/`dr`，本包没有核验 QMT 金额。原 147 个 Run B MATCH 不代表 147 个事件可自动消费。

## 独立扩样

`holdout_240.csv` 和 `holdout_manifest.json` 是在新样本查询前冻结的分层清单与合同。它们排除原 38 码和已用 MVP/预检代码，抽样不依赖 hithink/Wind 的可用性。完整运行解析 748 份文档、接受 559、拒绝 189；冻结查询完成 239/240 码。查询失败、日期未抽出、未接受和跨源窗口不同分别记录，不声明全市场召回率。

`query_audit/` 保存全部 959 页的响应哈希与结构检查、每码摘要、61 份返回代码不匹配的元数据和汇总。同 orgId 不代表已批准代码沿革映射；这些文档保持排除，本轮没有跨代码合并。

`holdout/` 保存冻结 `run.json`、完整统计、240 码覆盖、逐文档四源诊断、189 份 adapter 拒绝记录、200 份研究复核队列、参考键并集与 27 个历史未检出键、1334 份标题排除元数据、全部来源指纹及 748 次政策溯源。Wind 行数/event_id/现金分量保留，日求和不代表股东权益；13 个增量参考键均检出，11 份获接受，仍未评定 economics-ready。

`wind_frozen_universe.txt` 与不可变 Git 对象的 2774 码范围一致；`analysis_versions.json` 固定后处理库/脚本指纹，`artifact_manifest.json` 校验本包全部其他文件的原始字节。

## 复现

归档的 `*.py.txt` 是一次性研究脚本原文，不注册为本仓取数入口。使用 `scripts/_script_bootstrap.py::resolve_oskh_python()` 所选解释器，在仓库根的已忽略目录 `_agent_runs/pr531_lake_audit_20261030/` 中复制为同名 `.py` 后执行，禁止从证据目录直接启动抓取。

1. `fetch_inputs.py` 取得固定 Git 对象的 CSV/JSON；Wind 从 Git 对象读取，CNINFO 证据由 `gh api` 读取；各文件哈希须与 manifest 一致。
2. 固定 hithink 原件放在 `_agent_runs/pr531_lake_audit_20261029/hithink_dump.parquet`；固定 QMT 索引放在本轮 `inputs/qmt_ex_date_index.parquet`。两者均须与 `report.json` 的 SHA256 一致。本机保留了这些原件，未上传本包；不能以供应商新 dump 或其他宿主副本冒充同一快照。
3. `four_source_audit.py` 重算固定样本并冻结相同的独立样本；输入漂移须新 run，不覆盖本包。
4. 同时从本机原归档准备同级 `orgmap.json`（SHA256 由 `run.json` 固定），不得用更新的证券目录替换。`heldout_crawl.py` 是另获本次研究授权的一次性、限速查询/下载脚本；其独立 `bt_corp_actions_cninfo_backup_20261030` 目录固定输入和缓存哈希。离线重算直接使用完成后的原归档运行步骤 5–6，**不要重跑抓取器**：失败查询没有缓存，重跑会尝试联网。脚本原文归档不等于再次抓取授权或 C3。
5. `query_audit.py` 检查缓存响应与身份诊断，不改变抓取器；`confirmed_case_notes.py` 固定七份原文的五组事实观察。
6. 抓取结束后 `summarize_holdout.py` 做逐字段诊断、独立参考键并集对照及观测式政策溯源。观测 wrapper 只调用原 v10 函数，断言原字段、状态和事件身份不变。

新样本原始 PDF/txt、原始查询 JSON 和全部缓存只保留在本机研究目录。Git 仅保存统计、事实型 CSV、来源指纹和研究代码原文。`owner_signature=null`、`lake_write_authorized=false`，无调度/主源切换/合湖含义。
