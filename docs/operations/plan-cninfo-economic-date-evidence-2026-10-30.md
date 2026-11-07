# 巨潮经济日期补证（指针）

权威计划在 OSkhQuant1.3：`docs/operations/plan-cninfo-economic-date-evidence-2026-10-30.md`（第一片合同与验证计数器以该页为准）。

本仓这一片只做两件离线的事：

- `scripts/data/export_cninfo_economic_date_targets.py` 从冻结的 assembled events、宇宙和可选 D11 名单导出查询目标 JSON，并绑定文件哈希。D11 只有查询目标，不造事件行。
- `scripts/data/validate_cninfo_economic_date_evidence.py` 校验 1.3 证据目录（目标哈希、manifest、COMMITTED、文件哈希、相对路径、字段类型），写出日期建议、未解决清单和逐字段来源。

导出和校验都不是合湖授权，也不切换默认源。`owner_signature` 保持空。建议里的 `compatibility_policy_date` 与 `backtest_adopted_value` 本片留空；缺失的上市日不会被写成除权日。

未在本片实现：162+D11 真爬、东兴换股引擎、`reviewed_complete` 覆盖矩阵、prepare-merge。
