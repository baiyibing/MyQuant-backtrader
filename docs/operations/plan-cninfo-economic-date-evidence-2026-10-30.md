# 巨潮经济日期补证（infra 消费指针）

OP04 的 targets 导出、采集和离线证据建议由 MyQuant-infra 维护。当前依赖固定为 `6bcf33f38ce88a92ddcdf0be4916cbb9cdd1def0`；正式入口及合同见该版本的 [disclosure 文档](https://github.com/baiyibing/MyQuant-infra/blob/6bcf33f38ce88a92ddcdf0be4916cbb9cdd1def0/myquant_infra/disclosure/README.md)与[权威计划](https://github.com/baiyibing/MyQuant-infra/blob/6bcf33f38ce88a92ddcdf0be4916cbb9cdd1def0/docs/operations/plan-cninfo-economic-date-evidence-2026-10-30.md)。

BT 已删除旧 `oskh_data/cninfo_economic_date_targets.py`、`scripts/data/export_cninfo_economic_date_targets.py`、`scripts/data/validate_cninfo_economic_date_evidence.py` 及产制单测。不保留数据格式转换或缺依赖时的本地实现。

先安装 `requirements.txt`，按 AGENTS 的解释器解析顺序设置 `OSKH_MERGE_PYTHON`，再显式调用 infra。下面的输入路径是占位示例，必须替换成实际冻结输入；不会自动寻找湖或数据盘。

```powershell
$op04Sandbox = Join-Path ([IO.Path]::GetTempPath()) 'bt_corp_actions_cninfo_backup_20261109'

& $env:OSKH_MERGE_PYTHON -m myquant_infra.disclosure.export_cninfo_economic_date_targets `
  --assembled-events inputs/assembled_events.json --universe inputs/universe.txt `
  --d11 inputs/d11.txt --window-start 2026-10-07 --window-end 2026-10-28 `
  --out "$op04Sandbox/targets/targets.json"

& $env:OSKH_MERGE_PYTHON -m myquant_infra.disclosure.cninfo_economic_date_recommendations `
  --targets "$op04Sandbox/targets/targets.json" `
  --assembled-events inputs/assembled_events.json --universe inputs/universe.txt `
  --evidence-dir evidence/op04_frozen `
  --out "$op04Sandbox/review/recommendations.json"
```

迁移差异：infra 导出使用 `--d11`，不接受旧 `--d11-codes` 或 `--run-manifest` / `--run-hash` 的本地绑定逻辑。旧 BT targets / evidence / suggestions 不能静默改名当作 infra 格式；由 infra 重新绑定冻结输入并校验包，缺少所需字段或文件即失败。旧文件与历史证据保留，不在本次清理或重写。

离线建议默认输出 stdout；显式 `--out` 只允许系统临时目录或 `bt_corp_actions_cninfo_backup_YYYYMMDD` 命名备份根中的全新报告，普通 `exports/` 目录不自动获准。示例的 targets、review 子目录互相独立；已有输出必须显式另选新目录，不能覆盖、写湖或与输入包重叠。退出码 0 表示完整包的待审阅报告，仍可含 unresolved；有效失败包输出 blocked 并返回 1；输入、哈希、路径或完整性错误返回 2。不能把退出码 0 当作经济批准或覆盖完整。

输出保持 `owner_signature=""`、`economic_approval=false`、`lake_write_authorized=false`、`reviewed_complete=false`。D11 仅 query-only / coverage unknown；缺失上市日不补成除权日，缺失送转腿不补经济零。此变更不接入 CSV 回测运行时，不授权网络采集、162+D11 真爬、合湖、默认源切换或 prepare-merge。

东兴换股/证券转换的事实与研究合同正本在 MyQuant-infra，见 [op06-research-contract-ssot.md](op06-research-contract-ssot.md)；BT 不实现换股引擎。
