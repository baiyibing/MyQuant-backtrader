# corp-actions 增量驱动 → MyQuant-infra（2026-11-06 迁移通告）

> **Human 裁定（2026-11-06）：BT 只消费成品数据，不处理数据。**
> 本文原为 BT 侧 corp-actions 增量驱动操作手册（pull/hithink_incremental/
> hithink_artifact/parity/econ_gate 五件）。五件已全部迁 MyQuant-infra 并自
> 本仓删除；原文在 git 历史（本文件本次提交的前一版本）中冻结留档，冻结
> run（`bt_corp_actions_incr_*`）的复现以历史签出为准。

## 现行归属

| 能力 | infra 位置 |
|---|---|
| 增量候选驱动（init/pull/assemble/prepare-merge） | `myquant_infra.corp_actions.candidates`（`python -m myquant_infra.corp_actions candidates --help`） |
| hithink 冻结产物导入/覆盖分类 | `myquant_infra.corp_actions.candidates.hithink` |
| 对拍门禁（historical parity） | `python -m myquant_infra.corp_actions.candidates.parity --run-dir <run>` |
| 经济学准入门（OP06 转股阻断/修订链/证据链） | `myquant_infra.corp_actions.econ_gate` |
| hithink 采集（dump 导出 + K 线） | `myquant_infra.hithink`（`export` / `kline`） |

## BT 侧残余

- `scripts/gates/verify_corp_actions_economics_fence.py`：消费侧守卫保留——
  注册消费者禁止直接读 corp-actions 数据、禁止 import 已迁走的处理模块；
  白名单已清空（机制保留）。
- 经济学口径消费形态：**由 infra 出"经济学合格"成品表，BT 回测只读
  parquet**；禁止在 BT 重建过滤逻辑。

## OP06 事实/研究合同（2026-11-08）

运行时转股阻断（#550 消费侧拒绝门，原因键 `unsupported_stock_conversion_in_cash_bonus_schema`）归属见上表 `myquant_infra.corp_actions.econ_gate`。本仓不删除、不削弱该拒绝合同，也不恢复已迁走的处理模块。

东兴换股/证券转换的**事实与研究合同**正本迁 MyQuant-infra，见 [op06-research-contract-ssot.md](op06-research-contract-ssot.md)。本仓不重实现该合同。
