# 三票 vendor→lake adapter：Phase2 staging dry-run

2026-10-01 Human GO via bt executor；基线 `8ff3433e6ac64eebd37de39f4ccb7079bb877d24`（#293）。本刀只交付 adapter CLI、合成测试与 staging 证据，**不写湖；勿合，等待 Human「合」**。

本计划改编自 `/workspace/handoffs/vendor_three_symbol_lake_ingest_plan_20261001/PLAN.md`，依据 [vendor bar alignment SSOT](../ssot/vendor-bar-alignment-ssot.md) §2–§8。原方案待裁事项在本刀已锁定，不重新开题。

## 已锁定契约

- Sparse **A**：只输出已观测 bar；缺分钟不补零、不造根，不推断缺失原因。
- 输出 at-rest **lots**：Wind 1m / 可选 THS 1d 输入为本批已接受的 shares，`volume_lots = shares // 100`；非整手余数逐行写入 `remainder_audit.json`，禁止静默。该转换仅用于本刀 staging，不改变历史 shares overlay。
- `minute_label=END; START 09:30/11:30/15:00 excluded`：删除 Wind **START 09:30** 竞价行及 **11:30 / 15:00** 边界行，再对保留的连续行 +1 分钟。09:31 START 保留，编码为 **09:32 END**；不会为了出现 09:31 END 而保留竞价或重标其他根。13:00 START → 13:01 END，END 无 13:00；不跨午休造根。
- 日线按交易日午夜键输出，不加一分钟；THS 日线竞价汇总范围仍未验证，不宣称与分钟聚合一致。

## Phase2 入口与产物

[adapter CLI](../../../scripts/research/vendor_to_lake_adapter.py) 使用 adapter 自有 START 读取 helper，先审计排除边界再校验连续区间；[只读 xcheck sibling](../../../scripts/research/vendor_bar_xcheck.py) 的默认 fail-closed 行为不变。

```bash
/workspace/.venv-bt-ssot/bin/python scripts/research/vendor_to_lake_adapter.py \
  --wind /path/to/wind_002231_1m.csv \
  --ths-daily /path/to/ths_002231_1d.csv \
  --out-dir /path/to/new_staging
```

`--wind` 必填，可重复/多文件；`--ths-daily` 可选、可重复。默认标的为 `002231.SZ 300379.SZ 600200.SH`，可用 `--symbols` 显式筛选。参数仅支持 START→END、lots、除数 100；`--auction-policy` 默认 `exclude_0930_1130_1500`，统一排除并审计 START 09:30 / 11:30 / 15:00（hm 570/690/900），连续映射不变。旧 `exclude_0930` 保留为等价兼容别名，传入别名时 PIN 的 `auction_policy` 仍记录规范值 `exclude_0930_1130_1500`；`auction_dropped` 仍仅计 09:30。dry-run 恒为 true，**没有 `--write-lake`**。

输出 hive-like `period={1m,1d}/dividend_type=none/symbol=XXX/data.parquet`，包含 symbol/time/OHLC/volume（lots）；1m END 上海墙钟以 `local_wall_as_utc_ms` 编码，1d 用同编码的交易日午夜。另输出 PIN.json、STATUS.json、REPORT.md、remainder_audit.json 与 coverage_audit.json。PIN 逐源列实际路径、周期、sha256、转换清单、Human acceptance；覆盖审计列输入/输出/竞价排除与逐标的计数，缺失请求标的明确列出，不伪造覆盖。零行输入或全部被排除时 FAIL。

输出必须是新建或空的独立 staging 目录。拒绝包含 stock_data 路径组件（含 Windows 拼写）、配置湖根及后代、解析 symlink 后命中的受保护路径、输入目录重叠和非空输出；所有产物限于 out-dir。该防护是 best-effort，无法识别任意命名且未配置的真实湖，调用方仍必须指定独立 staging。受保护路径拒绝时不写 FAIL receipt；安全 staging 中的输入/转换/验收错误留下 FAIL STATUS，非零退出。PASS 前读回 parquet、PIN 和余数审计并核对源 SHA 未变；失败目录不可进入下一阶段。

## 证据与后续门槛

Host 只读证据：`/workspace/handoffs/vendor_bar_xcheck_host_20261001/` 与 `/workspace/handoffs/topk_s1_cap_cli_host_20261001/`。已有副样本证明连续 START/END 区间与量比 100 的线索，但 scale100 核对仍 FAIL；000559 晨收盘价格/量残差不能抹掉。三票原湖缺目录，副样本结果不能替代三票验收；THS 1m 未证实，不作为输入。

Phase3 真三票 staging 验收另需 Human GO，包含源 RECEIPT SHA、开盘/午休/尾根、lots 余数、稀疏覆盖与逐项 OHLCV xcheck；本刀只跑合成测试，不派发 4090。Phase4 写湖必须独立明确 Human「写湖 GO」，本 CLI 不提供写湖能力。Phase5 研究路径切换另议。

**非目标：≠δ5 certified ≠R4；无 MatchCore/Fees/engine/simulate 改动；无湖写入、无下载/vendor merge、无自动合并、无 `gh pr ready`、无 Cursor Cloud Agents。** 回滚仅删除独立 staging；PR 保持 draft，等待 Human「合」。

## 2026-10-02 START boundary exclude 刀（Human GO）

Phase3 host staging 在 `73a7e68` 因 RECEIPT 中 hm=690（11:30）/900（15:00）落在 START 连续区间外而整文件 FAIL，证据目录 `/workspace/handoffs/vendor_lake_adapter_host_20261001/`。本刀将 hm∈{570,690,900} 在 +1min 映射前排除；`excluded_start_boundary` 在 coverage/PIN/STATUS/REPORT 记录总数、逐标的/逐 hm 计数及最多 20 条原始 START 键与原因。`auction_dropped` 继续只计 09:30。其他越界行仍 fail closed，并在 FAIL STATUS/REPORT 保留已计算的边界审计；排除后无连续 bar 仍 FAIL。

Sparse A、lots //100 与余数审计不变；只跑合成测试，仍 staging-only / 无湖写入 / ≠δ5 ≠R4 / 不改 MatchCore/Fees/engine/simulate。PR 保持 draft，**勿合，等待 Human「合」**。
