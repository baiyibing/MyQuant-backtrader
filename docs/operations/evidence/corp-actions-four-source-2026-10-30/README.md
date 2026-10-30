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

`UNKNOWN` 不按 0 处理；`NOT_ACCEPTED` 不计作适配后经济值。QMT 索引只提供日期/`dr`，本包没有核验 QMT 金额。原 147 个 Run B MATCH 不代表 147 个事件可自动消费。

## 独立扩样

`holdout_240.csv` 和 `holdout_manifest.json` 是在新样本查询前冻结的分层清单与合同。它们排除原 38 码和已用 MVP/预检代码，抽样不依赖 hithink/Wind 的可用性。样本研究结果在完成后归档；查询失败、日期未抽出、未接受和跨源窗口不同分别记录，不声明全市场召回率。

## 复现

归档的 `*.py.txt` 是一次性研究脚本原文，不注册为本仓取数入口。使用 `scripts/_script_bootstrap.py::resolve_oskh_python()` 所选解释器，在仓库根的已忽略目录 `_agent_runs/pr531_lake_audit_20261030/` 中复制为同名 `.py` 后执行，禁止从证据目录直接启动抓取。

1. `fetch_inputs.py` 取得固定 Git 对象的 CSV/JSON；Wind 从 Git 对象读取，CNINFO 证据由 `gh api` 读取；各文件哈希须与 manifest 一致。
2. 固定 hithink 原件放在 `_agent_runs/pr531_lake_audit_20261029/hithink_dump.parquet`；固定 QMT 索引放在本轮 `inputs/qmt_ex_date_index.parquet`。两者均须与 `report.json` 的 SHA256 一致。本机保留了这些原件，未上传本包；不能以供应商新 dump 或其他宿主副本冒充同一快照。
3. `four_source_audit.py` 重算固定样本并冻结相同的独立样本；输入漂移须新 run，不覆盖本包。
4. `heldout_crawl.py` 是另获本次研究授权的一次性、限速查询/下载脚本；其独立 `bt_corp_actions_cninfo_backup_20261030` 目录固定输入和缓存哈希。离线复现可用原缓存，不等于再次抓取授权或 C3。
5. 抓取结束后 `summarize_holdout.py` 做逐字段诊断、独立参考键并集对照及观测式政策溯源。观测 wrapper 只调用原 v10 函数，断言原字段、状态和事件身份不变。

新样本原始 PDF/txt、原始查询 JSON 和全部缓存只保留在本机研究目录。Git 仅保存统计、事实型 CSV、来源指纹和研究代码原文。`owner_signature=null`、`lake_write_authorized=false`，无调度/主源切换/合湖含义。
