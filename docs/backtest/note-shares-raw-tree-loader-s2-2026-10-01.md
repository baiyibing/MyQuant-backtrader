# shares-global S2：新树 shares 直读

授权：`/workspace/handoffs/shares_s2_loader_20261001/HUMAN_GO.md`；计划
`/workspace/handoffs/shares_global_plan_20261001/SHARES_GLOBAL_PLAN.md` 的 S2。
基线 tip：`38374f0f16376fb5753bd971bccd94f6d72c31fb`。

S1 契约与 pin：`/workspace/handoffs/shares_raw_tree_20261001/` 下的
`TREE_CONTRACT.md`、`SCHEMA.md`、`PIN.json`；host 导出目录为
`D:\exports\shares_raw_tree_20261001\`。导出侧显式 lots→shares 已完成，
新树 `volume` 字节为 shares，`unit=raw_shares_incremental`、`transformations=[]`。
本 S2 只实现 loader，并以临时目录内的 synthetic Parquet/JSON 验证；不读取 host 数据。

## Recipe / evidence 接入

沿用 `minute_orders_source_recipe_v1` 的显式 resolver、schema/SHA-256、proof binding
与 attestation scope。通过 `OSKH_SOURCE_PARQUET_ROOT` 指定新树容器；没有默认 host 路径。
新树 recipe 必须注册 `implementation.transform_version=shares_raw_tree_direct_read_v1`，
code SHA / Python / PyArrow 仍需与实际实现匹配。

分钟 `bars[].columns.volume` 固定选 `volume`，对应 `int64`；
`bars[].volume` 保持原有形状：

```json
{"kind": "incremental", "unit": "shares", "shares_per_unit": 1}
```

units proof 的 `basis=source_declaration`，binding 指向该 pinned minute source 和
`volume` 列；独立 pinned JSON observation 必须明确声明：

```json
{
  "basis": "source_declaration",
  "unit_declaration": {
    "column": "volume", "kind": "incremental", "unit": "shares", "shares_per_unit": 1
  },
  "contract": "raw_shares_incremental",
  "transformations": []
}
```

这是 observation 片段，不是完整 recipe 或已重冻的 units pack。每份匹配的 units proof
都须满足该声明。物理 `unit` 列须全部为 `raw_shares_incremental`（含排除行与仅供 mark
使用的行）；`volume_lots_source` 可保留作审计列，loader 不使用它、不据此推算成交量。
S1 `timestamp` 文本可用既有 `naive_shanghai` 解码；START/END label 仍须按独立 timing
证据显式填写，S2 不改变时钟语义。

新路径将非负整数 `volume` 直接赋给 `volume_shares`，无运行时 ×100；provenance 使用
独立版本标签，并记录 `volume_at_rest` 的 source declaration、raw-shares 单位及空
transformations。时间/价格的既有解析审计继续保留，空 transformations 指成交量单位转换。
raw-shares 声明与 lots/100、mapping 指令、混合 basis、冲突的物理单位或旧标签同时出现
均 fail closed，不自动猜测、不回落旧树。

## 历史边界与后续 GO

`bl2_source_transform_v8` 的 `authorized_mapping` ×100 仅保留给 B-L2 历史旧树，
仍须通过原有 exact approval / source / material pins；旧 source declarations 保持兼容。
该过渡路径在 global-shares / δ5 目标上 **superseded-by-native-shares**，绝不能充当
δ5 单位证据。v8 mapping 的 `contract=raw_shares_incremental` 只描述转换后的输出，
不证明旧树 at-rest 单位；它不得同时声称 `transformations=[]`。

S3（B-L2 单位包重落重冻及旧 pin 作废登记）、S4（δ5 五包与 recipe）、S5（4090 run）
尚未执行，均须独立 Human GO。此 PR 不改现有包/pin，不跑 δ5/R4，不改湖/QMT，
不改 MatchCore/Ledger/Fees/Clock economics；合并仍须 Human「合」。
**S2 synthetic tests PASS ≠ δ5 PASS ≠ R4l PASS。**
