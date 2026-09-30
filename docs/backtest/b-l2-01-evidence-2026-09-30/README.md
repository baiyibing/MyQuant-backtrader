# B-L2-01 R3 证据包（仓内副本，2026-09-30）

本目录是 4090 宿主侧 `D:\exports\b_l2_01_4090_r3_20260930\`（box 镜像
`/workspace/handoffs/b_l2_4090_live_r3_20260930/`）的**逐字节副本**，按 host 指示入库，
供任意机器的 agent 独立核对。叙事、文档关联与复算命令见
[../note-b-l2-01-r3-evidence-sweep-2026-09-30.md](../note-b-l2-01-r3-evidence-sweep-2026-09-30.md)。

**边界（先读）**：

- `raw_materials/` 内全部 `raw_*.json` 的封套是 `bl2_raw_excerpt_draft_v0_host_review`——
  **行式摘录草稿，不是 `bl2_proof_v1`，不含 issuer 认证**；host 逐行审核前不得进入任何
  proof 的 `source_refs`。
- `raw_excerpt_xtquant_docs.json` 的结论之一是「供应商 K线字段表**没有** volume 单位注记」——
  这是**缺失的证据的证据**，不是单位声明。
- `raw_excerpt_cross_repo_rules.json` 中 MyQuant ×100 与 R3 探针比率≈100 均标注
  **NON-ATTESTATION**（ingress §9.2 明禁启发式签 units proof）。
- #270 六个 `*.template.json` 空模板**不在本目录**（仍在
  [tests/fixtures/minute_orders_source_attestation/](../../../tests/fixtures/minute_orders_source_attestation/)
  与宿主 `evidence/`）；本包**不解除 R3 `BLOCKED/NOT_RUN`**，不构成 host certification /
  lake PASS / 任何 SSOT 结论；R4 发车仍需具名 Human GO。

## 文件清单（bytes SHA-256 与宿主侧一致，跨机可对）

| 文件 | bytes | sha256 | 角色 |
|---|---|---|---|
| `HOST_B_L2_01_R3.md` | 9384 | `44580633334e852c0903c9779bbddcfd48777ff1ef7d22e18bfb53e47105ab45` | R3 仓外收据（BLOCKED/NOT_RUN 原文） |
| `probe_summary.json` | 15380 | `19d58da9090cd4b9df6a26599d85064d4786e75d7fbc19151690c05dcca5afd6` | R3 探针摘要（2169 行/比率≈100 等 probe，非 attestation） |
| `artifact_hashes.json` | 845 | `9b7678d587fecc1093f3051f86f28a56dc82859c7e4651baf9e82eb0183e3d32` | R3 产物 hash 登记原件 |
| `_run_b_l2_01_r3.py` | 28319 | `d274fd600264302a566d8da39ed26426b4589af988f975bc934be8c37ff5c214` | R3 4090 驱动脚本（fail-closed 探针的 provenance） |
| `HOST_MATERIALS_MAP_R4.md` | 8555 | `b2487a9ba20f66b8e211b22536fb92d5dc60b0c2edb8eb2427c8d4c93e0e2fba` | host-assist 材料地图 + R4-A/B/C/D 行动清单 |
| `gen_raw_materials.py` | 11265 | `69cc6b2d536be4c45ca3069c6c21d46a74f343a5822b4fe4d40bc87603f373a8` | 六包 raw 材料的只读生成器（可重跑核验） |
| `raw_materials/raw_excerpt_xtquant_docs.json` | 17859 | `3884f478256f96c7938cb5f0f40075ceb03f8064665be1193e2d445612bc8a12` | xtquant 250516.1.1 字段语义行式摘录（含「无单位注记」缺失证明） |
| `raw_materials/raw_excerpt_cross_repo_rules.json` | 19067 | `96c1476e196d908117d7f6304b770053c3833fd8c4383d080a9543de9b40a524` | 1.3/本仓涨跌停实现 + MyQuant ×100 旁证（NON-ATTESTATION） |
| `raw_materials/raw_lake_daily_603196SH_20251020_20251105.json` | 3087 | `773eadfcb753e2e59104e12a8dcc9743ed1d349f7a134bd7783f838a467a8cee` | 湖日线原行（reference/limits 推导输入） |
| `raw_materials/raw_lake_minute_census_603196SH_20251023_20251104.json` | 404397 | `b4ee473bcf7d224d635ce0f788d0d64dde8a2e421034420c2c292e9c632b7188` | 2169 行逐格 census（END 标签/row_idx/零量清单/网格映射） |
| `raw_materials/raw_st_membership_603196SH.json` | 541 | `9353e3e09cb21525a66e666ccb58e04d89c63dd9be13a1eee5b678444b022c9a` | 603196.SH 非 ST 材料（st_daily 零命中） |
| `raw_materials/raw_corporate_actions_603196SH_window.json` | 530 | `fd8311f59ed93a5bee602044d98e75b739583fdd74c6d103dc112e59b2257015` | 窗口零公司行动材料（ex_date_index 零命中） |
| `raw_materials/web_rule_references_20260930.md` | 2767 | `ed73ae7ec6038706fd745aeea8fac116e000a94ea9f351667da4ebad4a5dd86e` | 交易所规则公式 / 2026-07-06 ST 新政公开来源引用 |
| `raw_materials/raw_excerpt_crossvendor_daily_603196SH.json` | 20441 | `c5f7a4324115f5325fe6b8476ed8a02d0018dfe2d1e9620e061527c8da06180a` | 湖日线 vs 腾讯/新浪双独立行情源对照 + 10% 涨跌停复算零违例 + 零股观察（NON-ATTESTATION 旁证） |
| `check_crossvendor_daily.py` | 3628 | `862a727b7ef687c571288a322af390568149d0bf7cf4bd7869c261b8c163c85d` | 上包离线自检器（无网络，重算三源对照/涨跌停/零股，exit 0=一致） |
| `raw_materials/raw_excerpt_wind_mcp_daily_603196SH.json` | 8367 | `bfef633889c83a043181f9be574e6772c36a4c9da8ac782ad770439c4229d904` | 湖日线 vs Wind（kimi-datasource MCP）第四源对照 + 字段目录无单位注记负结果（NON-ATTESTATION 旁证） |
| `raw_materials/wind_mcp_603196_daily_20251020_20251105.csv` | 861 | `0abc3b6c49fea853b92337518f49330ce1e0f8f7492df19e3fa78ed34f121b6e` | Wind MCP `wind_get_price` 原始响应（pin） |
| `raw_materials/wind_mcp_field_search_volume.csv` | 74 | `0afc4305874f59b6dec3b202114eeefc480e016dc38694c67e714e2b7240e882` | Wind MCP 字段目录 volume 条目原始响应（无单位注记负结果，pin） |
| `check_wind_mcp_daily.py` | 4418 | `0ed03e450ad0918504b0a5c3f63172a4cc71c0126065074a7535286a611dd3df` | 第八包离线自检器（无网络/MCP，重算湖↔Wind 对照/负结果/pin hash，exit 0=一致） |

## 关于 `gen_raw_materials.py` 的位置

该脚本按设计包含宿主绝对路径（`E:\stock_data` 湖、兄弟仓、xtquant 安装位置）作为
**pinned provenance**，因此放在 `docs/` 证据目录内，**刻意不进入**
`scripts/` / `tests/` / 生产包——`verify_no_hardcoded_machine_paths.py` 的扫描范围即代码树，
本脚本不属于它们；重生成输出须与上表 sha256 一致。
